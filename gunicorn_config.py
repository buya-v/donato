# gunicorn_config.py

import os

# Port to bind to
bind = "0.0.0.0:8000"  # Listen on all interfaces, port 8000

# Number of worker processes
workers = 3  # Adjust based on your server's CPU cores

# Application module
module = "donato:app"  # donato.py, Flask app named 'app'

# Worker type (sync is the default, but consider async workers for high concurrency)
worker_class = "sync"  # or "gevent", "eventlet", "tornado"

# Log level
loglevel = "info"  # or "debug", "warning", "error", "critical"

# Access log file
accesslog = "-"  # "-" for stdout

# Error log file
errorlog = "-"  # "-" for stderr

# Timeout (in seconds)
timeout = 30

# Keep-alive timeout
keepalive = 2

# Preload application (reduces startup time)
preload_app = True

# Graceful restart timeout (in seconds)
graceful_timeout = 30

# Server certificate (for HTTPS)
# certfile = "/path/to/your/certificate.pem"  # Optional
# keyfile = "/path/to/your/key.pem"          # Optional

# --- Advanced Settings (Uncomment and Adjust if Needed) ---

# User to run the worker processes as
# user = "your_user"

# Group to run the worker processes as
# group = "your_group"

# Daemonize (run in the background)
# daemon = True

# Pid file (if daemonized)
# pidfile = "/path/to/your/pidfile.pid"

# Maximum number of requests a worker will process before restarting
# max_requests = 1000

# Maximum jitter to add to the max_requests setting
# max_requests_jitter = 50

# Settings to set a new process name.
# proc_name = 'donato'

# When preloading an application, the application server typically shares its
# memory space with its workers. This results in reduced memory usage, as the
# application's code and data are only loaded into memory once. However, if
# your application contains any global state that is modified at runtime, you
# may need to disable preloading to avoid memory corruption or unexpected
# behavior. This can be accomplished by setting the preload_app setting to False.
# This can also be accomplished by disabling shared address space using the
# --no-shared-address-space option.
# no_shared_address = True