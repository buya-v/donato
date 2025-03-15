import os
from flask import Flask, render_template, request, redirect, url_for, session
from dotenv import load_dotenv
import requests
import psycopg2
from urllib.parse import urlparse
import hashlib
import base64
import json
import datetime
import uuid  # For generating unique tokens
import qrcode  # For generating QR codes
from io import BytesIO  # For working with in-memory images

# Determine the environment (test or production)
ENVIRONMENT = os.environ.get("ENVIRONMENT", "test").lower()
print(f"Running in {ENVIRONMENT} environment")

# Load environment variables from .env based on environment
dotenv_path = os.path.join(os.path.dirname(__file__), f".env.{ENVIRONMENT}")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    print(f"Loaded environment variables from {dotenv_path}")
else:
    print(
        f"No .env file found for {ENVIRONMENT} environment.  Loading from .env if present."
    )
    load_dotenv()  # Load from .env if .env.test or .env.production doesn't exist

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")
print(f" secret key used: {app.secret_key}")


# PostgreSQL Database Connection
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
        order_data_json = json.dumps(
            order_data, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")  # use separators and utf-8

        # 3. Hash the order_data_json using SHA256
        hashed_order_data = hashlib.sha256(order_data_json).digest()

        # 4. Verify the signature
        # This part REQUIRES the `cryptography` library and proper OpenSSL setup.
        # It's complex, and you may need to use a different approach depending on your environment.
        # This is a placeholder.  The real code would use a crypto library to verify
        # the signature using the public key and the SHA256 hash.

        # **IMPORTANT: Replace this with actual signature verification code!**
        is_valid = ordersign_decoded == hashed_order_data  # VERY INSECURE - REPLACE THIS

        is_valid = True # TODO: need to fix when completion of signature verification

        return is_valid
    except Exception as e:
        print(f"Error verifying signature: {e}")
        return False


# Function to generate a unique order number
def generate_unique_order_number():
    """
    Generates a unique order number with datestamp and 6-digit incremental number
    that restarts each day.
    """
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to the database.")
        return None

    try:
        cur = conn.cursor()
        today = datetime.datetime.now().strftime("%Y%m%d")  # YYYYMMDD
        # Check and get the last incremental number for today.
        cur.execute(
            "SELECT last_number FROM order_numbers WHERE datestamp = %s", (today,)
        )
        result = cur.fetchone()

        if result:
            last_number = result[0] + 1  # Increment the last number
        else:
            last_number = 1  # Start with 1 if today is new
            
        # Update order_numbers table with new last_number or create a new one if necessary.
        cur.execute("""
            INSERT INTO order_numbers (datestamp, last_number)
            VALUES (%s, %s)
            ON CONFLICT (datestamp)
            DO UPDATE SET last_number = %s
        """,(today, last_number, last_number)
        )
        conn.commit()

        incremental_number = str(last_number).zfill(6) # Pad with zeros

        return f"{today}{incremental_number}" #Return the full ID
    except Exception as e:
        print(f"Error generating unique order number: {e}")
        return None
    finally:
        conn.close()
    
# Function to generate a unique token
def generate_unique_token():
    return str(uuid.uuid4())  # Generate a UUID as a token

# Function to generate a QR code as a data URI
def generate_qr_code(data):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Convert image to BytesIO object, then to data URI
    img_buffer = BytesIO()
    img.save(img_buffer, format="PNG")  #save buffer format as PNG
    img_buffer.seek(0)
    img_data_uri = base64.b64encode(img_buffer.read()).decode("ascii")
    return f"data:image/png;base64,{img_data_uri}" #return as png image

# *** ADD THESE ROUTES ***
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/favicon.ico")
def favicon():
    return app.send_static_file("favicon.ico")  # Assumes favicon.ico in static/ directory


@app.route("/contribute", methods=["GET", "POST"])
def contribute():
    if request.method == "POST":
        contribution_amount = float(request.form["contribution_amount"])
        email = request.form["email"]  # get email of user

        # --- NEGDI Payment Integration (ec1000 - Create Order) ---
        negdi_api_url = os.environ.get("NEGDI_API_URL")  # From env variable
        terminalid = os.environ.get("NEGDI_TERMINAL_ID")
        username = os.environ.get("NEGDI_USERNAME")
        password = os.environ.get("NEGDI_PASSWORD")  # Replace with your data
        public_key = os.environ.get("NEGDI_PUBLIC_KEY")
        return_url = url_for("payment_confirmation", _external=True)

        ordernum = generate_unique_order_number()  # generate a unique number
        if ordernum is None:
            return render_template(
                "payment_error.html",
                error_message="Failed to generate a unique order number.  Please try again later.",
            )

        payload = {
            "ordertype": "3dsOrder",
            "terminalid": terminalid,
            "username": username,
            "password": password,
            "returnurl": return_url,
            "amount": contribution_amount,
            "currency": "USD",
            "ordernum": ordernum,  # Use the generated unique order number
        }
        # Important note: ordernum is order number of the Merchant
        headers = {"Content-Type": "application/json"}  # Remove Authorization header

        try:
            print(payload)
            response = requests.post(negdi_api_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            # print(data) #Check output in development environment

            # Verify the signature before trusting any data!
            order_data = data.get("order")
            ordersign = data.get("ordersign")

            is_signature_valid = verify_negdi_signature(order_data, ordersign, public_key)

            if not is_signature_valid:
                print("Signature verification failed!")
                return render_template("payment_error.html", error_message="Payment processing error: Invalid signature from payment gateway.")

            if "order" in data and "negdiurl" in data["order"]:
                negdi_url = data["order"]["negdiurl"]  # Get the redirect URL from the response
                session["email"] = email  # Store email in session
                session["ordernum"] = ordernum

                return redirect(negdi_url)  # Redirect to the Negdi payment page

            else:
                print(f"Negdi API Error: {data}")
                error_reason = data.get("order", {}).get("reason", "Unknown error")
                payment_status = data.get("order", {}).get("status", "Undefined status")
                print(f"Payment failed. Status: {payment_status}, Reason: {error_reason}")
                return render_template(
                    "payment_error.html", error_message=error_reason
                )

        except requests.exceptions.RequestException as e:
            print(f"Network Error: {e}")
            return render_template(
                "payment_error.html",
                error_message="Network error during payment. Please try again later.",
            )
        except Exception as e:
            print(f"Unexpected Error: {e}")
            return render_template(
                "payment_error.html",
                error_message="An unexpected error occurred. Please try again later.",
            )

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
        return render_template(
            "payment_error.html",
            error_message="Missing transaction information from payment gateway.",
        )

    # --- Verify Payment with ec1098 (Inquiry Order) ---
    negdi_inquiry_url = os.environ.get("NEGDI_INQUIRY_URL")  # From env variable
    terminalid = os.environ.get("NEGDI_TERMINAL_ID")
    username = os.environ.get("NEGDI_USERNAME")
    password = os.environ.get("NEGDI_PASSWORD")
    public_key = os.environ.get("NEGDI_PUBLIC_KEY")  # Public key from .env

    payload = {
        "terminalid": terminalid,
        "username": username,
        "password": password,
        "tranid": tranid,
        "checkid": checkid,
    }

    print(payload)

    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(negdi_inquiry_url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        print(data)

        # Verify signature again!
        order_data = data.get("order")
        ordersign = data.get("ordersign")
        is_signature_valid = verify_negdi_signature(order_data, ordersign, public_key)

        if not is_signature_valid:
            print("Signature verification failed (inquiry)!")
            return render_template("payment_error.html", error_message="Payment processing error: Invalid signature from payment gateway (inquiry).")

        if "order" in data and "status" in data["order"]:
            payment_status = data["order"]["status"]

            if (
                payment_status == "Approved"
            ):  # Replace with the correct success status from NEGDI
                # Payment was successful! Update the database.
                conn = get_db_connection()
                if conn:
                    try:
                        cur = conn.cursor()
                        email = session.pop("email", "No Email")
                        ordernum = session.pop("ordernum", "Unknown ordernum")
                        token = generate_unique_token()  # New generated unique token

                        # Generate a QRCode for the token
                        qr_code_data_uri = generate_qr_code(token)

                        # cur.execute(
                        #     "INSERT INTO users (id, email, password) VALUES (%s, %s, %s)",
                        #     (1, "test@itauco.mn", "completed"),
                        # )
                        cur.execute(
                            "INSERT INTO contributions (email, amount, transaction_id, status, ordernum, token, check_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                            (email, 100.00, tranid, "completed", ordernum, token, checkid),  # Insert the ordernum, token to database and checkid
                        )

                        conn.commit()
                        cur.close()
                        # Pass to template QR code uri
                        return render_template(
                            "payment_confirmation.html",
                            qr_code=qr_code_data_uri,
                            token=token,
                        )

                    except Exception as e:
                        print(f"Error updating database: {e}")
                        return render_template(
                            "payment_error.html",
                            error_message="Error updating the contribution. Contact support.",
                        )
                    finally:
                        conn.close()
                else:
                    return render_template(
                        "payment_error.html",
                        error_message="Cannot connect to the database.",
                    )
            else:
                # Payment failed
                print(f"Payment failed. Status: {payment_status}")
                return render_template("payment_failed.html")
        else:
            print(f"Negdi Inquiry API Error: {data}")
            error_reason = data.get("order", {}).get("reason", "Error without reason")
            payment_status = data.get("order", {}).get("status", "Undefined status")
            print(f"Payment failed. Status: {payment_status}, Reason: {error_reason}")
            return render_template(
                "payment_error.html", error_message=error_reason
            )

    except requests.exceptions.RequestException as e:
        print(f"Network Error (inquiry): {e}")
        return render_template(
            "payment_error.html",
            error_message="Network error during payment verification. Please try again later.",
        )
    except Exception as e:
        print(f"Unexpected Error (inquiry): {e}")
        return render_template(
            "payment_error.html",
            error_message="An unexpected error occurred during payment verification. Please try again later.",
        )


@app.route("/payment_failed")
def payment_failed():
    return render_template("payment_failed.html")


if __name__ == "__main__":
    app.run(debug=True)