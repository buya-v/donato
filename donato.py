import os
from flask import Flask, render_template, request, redirect, url_for, session
from dotenv import load_dotenv
import requests
import psycopg2
from urllib.parse import urlparse
import hashlib
import base64
import json

# Determine the environment (test or production)
ENVIRONMENT = os.environ.get("ENVIRONMENT", "test").lower() # Default to "test" if not set
print(f"Running in {ENVIRONMENT} environment")

# Load environment variables from .env based on environment
dotenv_path = os.path.join(os.path.dirname(__file__), f'.env.{ENVIRONMENT}')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    print(f"Loaded environment variables from {dotenv_path}")
else:
    print(f"No .env file found for {ENVIRONMENT} environment.  Loading from .env (if present).")
    load_dotenv()  # Load from .env if .env.test or .env.production doesn't exist

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")

# PostgreSQL Database Connection (same as before)
def get_db_connection():
    try:
        db_url = os.environ.get("DATABASE_URL")
        parsed_url = urlparse(db_url)
        db_name = parsed_url.path[1:]
        db_user = parsed_url.username
        db_password = parsed_url.password
        db_host = parsed_url.hostname
        db_port = parsed_url.port

        conn = psycopg2.connect(
            dbname=db_name,
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port
        )
        return conn

    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        return None


def init_db():
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            with open("schema.sql", "r") as f:
                cur.execute(f.read())
            conn.commit()
            cur.close()
        except Exception as e:
            print(f"Error initializing database: {e}")
        finally:
            conn.close()

# init_db()

# Function to verify NEGDI response signature (CRITICAL for security)
def verify_negdi_signature(order_data, ordersign, public_key):
    """
    Verifies the NEGDI response signature using OPENSSL_ALGO_SHA256.
    In test environment, skips signature verification.
    """
    if ENVIRONMENT == "test":
        print("Test environment: Skipping signature verification")
        return True  # Bypass signature verification in test

    try:
        # 1. Decode the ordersign from base64
        ordersign_decoded = base64.b64decode(ordersign)

        # 2. Convert the order_data (which should be a dictionary) to a JSON string
        order_data_json = json.dumps(order_data, separators=(',', ':'), ensure_ascii=False).encode('utf-8') # use separators and utf-8

        # 3. Hash the order_data_json using SHA256
        hashed_order_data = hashlib.sha256(order_data_json).digest()

        # 4. Verify the signature
        # This part REQUIRES the `cryptography` library and proper OpenSSL setup.
        # It's complex, and you may need to use a different approach depending on your environment.
        # This is a placeholder.  The real code would use a crypto library to verify
        # the signature using the public key and the SHA256 hash.

        # **IMPORTANT: Replace this with actual signature verification code!**
        is_valid = ordersign_decoded == hashed_order_data # VERY INSECURE - REPLACE THIS

        return is_valid
    except Exception as e:
        print(f"Error verifying signature: {e}")
        return False

# *** ADD THESE ROUTES ***
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/favicon.ico")
def favicon():
    return app.send_static_file("favicon.ico") #Assumes favicon.ico in static/ directory

@app.route("/contribute", methods=["GET", "POST"])
def contribute():
    if request.method == "POST":
        contribution_amount = float(request.form["contribution_amount"])

        # --- NEGDI Payment Integration (ec1000 - Create Order) ---
        negdi_api_url = os.environ.get("NEGDI_API_URL")  # From env variable
        terminalid = os.environ.get("NEGDI_TERMINAL_ID")
        username = os.environ.get("NEGDI_USERNAME")
        password = os.environ.get("NEGDI_PASSWORD") # Replace with your data
        public_key = os.environ.get("NEGDI_PUBLIC_KEY")
        return_url = url_for("payment_confirmation", _external=True)

        payload = {
            "ordertype": "3dsOrder",
            "terminalid": "1", 
            "username": "user",
            "password": "123456",
            "returnurl": return_url,
            "amount": contribution_amount,
            "currency": "USD",
            "ordernum": "20250306001"  # Replace with your unique order number
        }
        #Important note: ordernum is order number of the Merchant
        headers = {"Content-Type": "application/json"} # Remove Authorization header

        try:
            print(payload)
            response = requests.post(negdi_api_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            #print(data) #Check output in development environment

            # Verify the signature before trusting any data!
            order_data = data.get("order")
            ordersign = data.get("ordersign")

            is_signature_valid = verify_negdi_signature(order_data, ordersign, public_key)

            if not is_signature_valid:
                print("Signature verification failed!")
                return render_template("payment_error.html", error_message="Payment processing error: Invalid signature from payment gateway.")


            if 'order' in data and 'negdiurl' in data['order']:
                negdi_url = data['order']['negdiurl'] # Get the redirect URL from the response
                return redirect(negdi_url) # Redirect to the Negdi payment page

            else:
                print(f"Negdi API Error: {data}")
                return render_template("payment_error.html", error_message="Payment processing error: Could not retrieve payment URL.")

        except requests.exceptions.RequestException as e:
            print(f"Network Error: {e}")
            return render_template("payment_error.html", error_message="Network error during payment. Please try again later.")
        except Exception as e:
            print(f"Unexpected Error: {e}")
            return render_template("payment_error.html", error_message="An unexpected error occurred. Please try again later.")

    return render_template("contribute.html")


@app.route("/payment_confirmation")
def payment_confirmation():
    """
    Handles the redirect from NEGDI after payment.  Verifies the transaction status
    using the ec1098 API.
    """
    tranid = request.args.get("tranid")
    checkid = request.args.get("checkid")

    if not tranid or not checkid:
        return render_template("payment_error.html", error_message="Missing transaction information from payment gateway.")

    # --- Verify Payment with ec1098 (Inquiry Order) ---
    negdi_inquiry_url = os.environ.get("NEGDI_API_URL") #From env variable
    terminalid = os.environ.get("NEGDI_TERMINAL_ID")
    username = os.environ.get("NEGDI_USERNAME")
    password = os.environ.get("NEGDI_PASSWORD")
    public_key = os.environ.get("NEGDI_PUBLIC_KEY") # Public key from .env

    payload = {
        "terminalid": "1",
        "username": "user",
        "password": "123456",
        "tranid": tranid,
        "checkid": checkid
    }

    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(negdi_inquiry_url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        # Verify signature again!
        order_data = data.get("order")
        ordersign = data.get("ordersign")
        is_signature_valid = verify_negdi_signature(order_data, ordersign, public_key)

        if not is_signature_valid:
            print("Signature verification failed (inquiry)!")
            return render_template("payment_error.html", error_message="Payment processing error: Invalid signature from payment gateway (inquiry).")


        if 'order' in data and 'status' in data['order']:
            payment_status = data['order']['status']

            if payment_status == "Approved": # Replace with the correct success status from NEGDI
                # Payment was successful! Update the database.
                conn = get_db_connection()
                if conn:
                    try:
                        cur = conn.cursor()
                        cur.execute(
                            "INSERT INTO contributions (user_id, amount, transaction_id, status) VALUES (%s, %s, %s, %s)",
                            (1, 100.00, tranid, "completed"),
                        )  # Replace with actual user_id, amount and dynamic values

                        conn.commit()
                        cur.close()
                        return render_template("payment_confirmation.html")

                    except Exception as e:
                        print(f"Error updating database: {e}")
                        return render_template("payment_error.html", error_message="Error updating the contribution. Contact support.")
                    finally:
                        conn.close()
                else:
                    return render_template("payment_error.html", error_message="Cannot connect to the database.")
            else:
                # Payment failed
                print(f"Payment failed. Status: {payment_status}")
                return render_template("payment_failed.html")
        else:
            print(f"Negdi Inquiry API Error: {data}")
            return render_template("payment_error.html", error_message="Payment processing error: Could not retrieve payment status.")

    except requests.exceptions.RequestException as e:
        print(f"Network Error (inquiry): {e}")
        return render_template("payment_error.html", error_message="Network error during payment verification. Please try again later.")
    except Exception as e:
        print(f"Unexpected Error (inquiry): {e}")
        return render_template("payment_error.html", error_message="An unexpected error occurred during payment verification. Please try again later.")



@app.route("/payment_failed")
def payment_failed():
    return render_template("payment_failed.html")


if __name__ == "__main__":
    app.run(debug=True)