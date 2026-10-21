#!/bin/sh
# Create monolith/.env from .env.example with freshly generated secrets.
set -eu

cd "$(dirname "$0")/.."

if [ -e .env ]; then
    echo ".env already exists; refusing to overwrite it." >&2
    exit 1
fi

gen() { python3 -c "import secrets; print(secrets.token_urlsafe($1))"; }
fernet() { python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"; }

umask 077
sed \
    -e "s|^SECRET_KEY=.*|SECRET_KEY=$(gen 64)|" \
    -e "s|^FIELD_ENCRYPTION_KEY=.*|FIELD_ENCRYPTION_KEY=$(fernet)|" \
    -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(gen 32)|" \
    -e "s|^GATEWAY_TOKEN=.*|GATEWAY_TOKEN=$(gen 32)|" \
    .env.example > .env

echo "Created .env with new secrets (mode 600). Review ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS."
