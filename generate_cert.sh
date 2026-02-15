#!/bin/bash
# Generate self-signed SSL certificate for development

CERT_DIR="certs"
KEY_FILE="$CERT_DIR/key.pem"
CERT_FILE="$CERT_DIR/cert.pem"

# Create certs directory if it doesn't exist
mkdir -p "$CERT_DIR"

# Check if certificates already exist
if [ -f "$KEY_FILE" ] && [ -f "$CERT_FILE" ]; then
    echo "SSL certificates already exist in $CERT_DIR/"
    echo "Delete them first if you want to regenerate."
    exit 0
fi

echo "Generating self-signed SSL certificate..."
echo "This certificate is for development only. Browsers will show a security warning."

# Generate private key and certificate
# Include macbook-m1 for Tailscale access
openssl req -x509 -newkey rsa:4096 -nodes \
    -keyout "$KEY_FILE" \
    -out "$CERT_FILE" \
    -days 365 \
    -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,DNS:*.localhost,DNS:macbook-m1,IP:127.0.0.1,IP:0.0.0.0"

if [ $? -eq 0 ]; then
    echo "✓ SSL certificates generated successfully!"
    echo "  Key: $KEY_FILE"
    echo "  Cert: $CERT_FILE"
    echo ""
    echo "Note: For production, use certificates from a trusted CA (Let's Encrypt, etc.)"
else
    echo "✗ Failed to generate certificates. Make sure OpenSSL is installed."
    exit 1
fi




