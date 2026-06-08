#!/bin/bash
# Полная настройка Mini App магазина на VPS (запуск на сервере).
set -euo pipefail

APP_DIR="/opt/heroes-bot"
DOMAIN="82-25-174-162.nip.io"
SSL_PORT="8444"
MINIAPP_PORT="8080"
NGINX_SITE="/etc/nginx/sites-available/heroes-shop"
SSL_FALLBACK="/etc/nginx/ssl/heroes-shop"

echo "==> Python"
mkdir -p "$APP_DIR" /var/www/acme "$SSL_FALLBACK"
if [ ! -d "$APP_DIR/.venv" ]; then
  python3 -m venv "$APP_DIR/.venv"
fi
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

echo "==> Nginx HTTP (ACME + shop)"
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

echo "==> SSL certificate"
printf '%s\n' \
  "ACCOUNT_EMAIL='admin@example.com'" \
  "DEFAULT_ACME_SERVER='https://acme-v02.api.letsencrypt.org/directory'" \
  > /root/.acme.sh/account.conf

CERT_LE="/root/.acme.sh/${DOMAIN}_ecc/fullchain.cer"
KEY_LE="/root/.acme.sh/${DOMAIN}_ecc/${DOMAIN}.key"

if [ ! -f "$CERT_LE" ]; then
  rm -rf /root/.acme.sh/ca
  if ! /root/.acme.sh/acme.sh --issue -d "$DOMAIN" -w /var/www/acme --keylength ec-256 -m admin@example.com; then
    echo "LE failed, using self-signed (для Telegram нужен валидный сертификат — настройте DNS на домен)"
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
      -keyout "$SSL_FALLBACK/key.pem" \
      -out "$SSL_FALLBACK/cert.pem" \
      -subj "/CN=${DOMAIN}" 2>/dev/null
    CERT="$SSL_FALLBACK/cert.pem"
    KEY="$SSL_FALLBACK/key.pem"
  else
    CERT="$CERT_LE"
    KEY="$KEY_LE"
  fi
else
  CERT="$CERT_LE"
  KEY="$KEY_LE"
fi

echo "==> Nginx HTTPS"
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

echo "==> heroes-bot.service"
if [ ! -f "$APP_DIR/.env" ]; then
  echo "ERROR: $APP_DIR/.env missing" >&2
  exit 1
fi
grep -q '^SHOP_MINIAPP_URL=' "$APP_DIR/.env" || \
  echo "SHOP_MINIAPP_URL=https://${DOMAIN}:${SSL_PORT}/shop" >> "$APP_DIR/.env"
grep -q '^MINIAPP_HOST=' "$APP_DIR/.env" || echo "MINIAPP_HOST=127.0.0.1" >> "$APP_DIR/.env"
grep -q '^MINIAPP_PORT=' "$APP_DIR/.env" || echo "MINIAPP_PORT=8080" >> "$APP_DIR/.env"

install -m 644 "$APP_DIR/deploy/heroes-bot.service" /etc/systemd/system/heroes-bot.service
systemctl daemon-reload
systemctl enable heroes-bot
systemctl restart heroes-bot

sleep 3
systemctl is-active heroes-bot
curl -sf "http://127.0.0.1:${MINIAPP_PORT}/" >/dev/null && echo "Backend :8080 OK"
curl -sfk "https://127.0.0.1:${SSL_PORT}/shop/" >/dev/null && echo "HTTPS /shop OK"
echo "URL: https://${DOMAIN}:${SSL_PORT}/shop"
