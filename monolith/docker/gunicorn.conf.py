import multiprocessing
import os

bind = "0.0.0.0:8000"
workers = int(os.environ.get("GUNICORN_WORKERS", min(multiprocessing.cpu_count() * 2 + 1, 5)))
timeout = 60
graceful_timeout = 30
max_requests = 1000
max_requests_jitter = 100
accesslog = "-"
errorlog = "-"
# Only Cloudflare Tunnel on the host can reach the container port.
forwarded_allow_ips = "*"
# The app directory is read-only for the runtime user; the control socket is not needed.
control_socket_disable = True
