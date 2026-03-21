#!/bin/bash
# ── Rule #1 Dashboard — VPS Setup Script ──
# Run this on your Hostinger VPS (Ubuntu/Debian)
# Usage: bash setup.sh

set -e

APP_DIR="/opt/rule1-dashboard"
APP_USER="rule1"

echo "==> Installing system dependencies..."
apt-get update -qq
apt-get install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx

echo "==> Creating app user..."
id -u $APP_USER &>/dev/null || useradd -r -m -s /bin/bash $APP_USER

echo "==> Setting up app directory..."
mkdir -p $APP_DIR
cp -r ../rule1.py ../portfolio.py ../dashboard.py ../scanner.py ../requirements.txt $APP_DIR/
mkdir -p $APP_DIR/.streamlit
cp ../.streamlit/config.toml $APP_DIR/.streamlit/

# Create secrets file — user must edit the password
cat > $APP_DIR/.streamlit/secrets.toml << 'SECRETS'
# IMPORTANT: Change this password!
password = "changeme"
SECRETS

echo "==> Creating virtual environment..."
cd $APP_DIR
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install streamlit yfinance lxml

echo "==> Setting permissions..."
chown -R $APP_USER:$APP_USER $APP_DIR

echo "==> Installing systemd service..."
cat > /etc/systemd/system/rule1-dashboard.service << 'SERVICE'
[Unit]
Description=Rule #1 Investing Dashboard
After=network.target

[Service]
Type=simple
User=rule1
WorkingDirectory=/opt/rule1-dashboard
ExecStart=/opt/rule1-dashboard/venv/bin/streamlit run dashboard.py --server.port 8501 --server.address 127.0.0.1
Restart=always
RestartSec=5
Environment=HOME=/opt/rule1-dashboard

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable rule1-dashboard
systemctl start rule1-dashboard

echo "==> Setting up nightly scanner cron job..."
# Run scanner at 2 AM daily as the rule1 user
CRON_CMD="0 2 * * * cd /opt/rule1-dashboard && /opt/rule1-dashboard/venv/bin/python3 scanner.py >> /opt/rule1-dashboard/scan.log 2>&1"
(crontab -u $APP_USER -l 2>/dev/null | grep -v "scanner.py"; echo "$CRON_CMD") | crontab -u $APP_USER -

echo "==> Running initial scan in background..."
su - $APP_USER -c "cd $APP_DIR && ./venv/bin/python3 scanner.py" &

echo "==> Setting up Nginx reverse proxy..."
cat > /etc/nginx/sites-available/rule1 << 'NGINX'
server {
    listen 80;
    server_name _;  # Replace _ with your domain if you have one

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
}
NGINX

ln -sf /etc/nginx/sites-available/rule1 /etc/nginx/sites-enabled/rule1
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo ""
echo "========================================="
echo "  Dashboard deployed!"
echo "========================================="
echo ""
echo "  1. Edit the password:"
echo "     nano /opt/rule1-dashboard/.streamlit/secrets.toml"
echo ""
echo "  2. Restart after changes:"
echo "     systemctl restart rule1-dashboard"
echo ""
echo "  3. Access at: http://<your-vps-ip>"
echo ""
echo "  4. Scanner runs nightly at 2 AM."
echo "     First scan is running in background now."
echo "     Check progress: tail -f /opt/rule1-dashboard/scan.log"
echo ""
echo "  5. (Optional) Add SSL with a domain:"
echo "     certbot --nginx -d yourdomain.com"
echo "========================================="
