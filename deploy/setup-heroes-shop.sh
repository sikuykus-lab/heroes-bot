#!/bin/bash
set -euo pipefail

APP_DIR="/opt/heroes-bot"
DOMAIN="82-25-174-162.nip.io"
SSL_PORT="8444"
MINIAPP_PORT="8080"
NGINX_SITE="/etc/nginx/sites-available/heroes-shop"

echo "==> Prepare app dir"
mkdir -p "$APP_DIR"
mkdir -p /var/www/acme

echo "==> Python venv + deps"
if [ ! -d "$APP_DIR/.venv" ]; then
  python3 -m venv "$APP_DIR/.venv"
fi
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

echo "==> Nginx site (HTTP + shop proxy)"
cat > "$NGINX_SITE" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/acme;
        default_type text/plain;
    }

    location /shop/ {
        proxy_pass http://127.0.0.1:${MINIAPP_PORT}/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

ln -sf "$NGINX_SITE" /etc/nginx/sites-enabled/heroes-shop
nginx -t
systemctl reload nginx

echo "==> SSL certificate (acme.sh)"
if [ ! -f "/root/.acme.sh/${DOMAIN}_ecc/fullchain.cer" ]; then
  /root/.acme.sh/acme.sh --set-default-ca --server letsencrypt
  /root/.acme.sh/acme.sh --issue -d "$DOMAIN" -w /var/www/acme --keylength ec-256 --accountemail "admin@example.com"
fi

CERT="/root/.acme.sh/${DOMAIN}_ecc/fullchain.cer"
KEY="/root/.acme.sh/${DOMAIN}_ecc/${DOMAIN}.key"

cat > "$NGINX_SITE" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/acme;
        default_type text/plain;
    }

    location /shop/ {
        return 301 https://\$host:${SSL_PORT}\$request_uri;
    }
}

server {
    listen ${SSL_PORT} ssl;
    listen [::]:${SSL_PORT} ssl;
    server_name ${DOMAIN};

    ssl_certificate ${CERT};
    ssl_certificate_key ${KEY};
    ssl_protocols TLSv1.2 TLSv1.3;

    location /shop/ {
        proxy_pass http://127.0.0.1:${MINIAPP_PORT}/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

nginx -t
systemctl reload nginx

echo "==> systemd"
install -m 644 "$APP_DIR/deploy/heroes-bot.service" /etc/systemd/system/heroes-bot.service
systemctl daemon-reload
systemctl enable heroes-bot
systemctl restart heroes-bot

sleep 2
if curl -sf "http://127.0.0.1:${MINIAPP_PORT}/" >/dev/null; then
  echo "Mini App backend: OK"
else
  echo "WARN: Mini App backend not responding on ${MINIAPP_PORT}"
fi

if curl -sfk "https://127.0.0.1:${SSL_PORT}/shop/" >/dev/null; then
  echo "HTTPS shop proxy: OK"
else
  echo "WARN: HTTPS shop proxy check failed"
fi

echo "SHOP_MINIAPP_URL=https://${DOMAIN}:${SSL_PORT}/shop"
