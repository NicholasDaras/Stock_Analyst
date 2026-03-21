#!/bin/bash
# Stock Analyst Dashboard - VPS Deploy Script
# Usage: scp this to your VPS then run: bash deploy.sh

set -e

# --- Configuration ---
APP_DIR="/opt/stock-analyst"
SERVICE_NAME="stock-analyst"
SCANNER_HOUR="2"  # Run nightly scan at 2 AM

# --- Colors ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

step() { echo -e "\n${GREEN}[$1/$TOTAL_STEPS] $2${NC}"; }
warn() { echo -e "${YELLOW}  -> $1${NC}"; }

TOTAL_STEPS=7

# --- Step 1: System packages ---
step 1 "Installing system packages"
apt update -qq
apt install -y -qq python3 python3-pip python3-venv ufw > /dev/null 2>&1
echo "  Done."

# --- Step 2: Virtual environment ---
step 2 "Setting up Python virtual environment"
cd "$APP_DIR"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --quiet streamlit yfinance pandas
echo "  Done."

# --- Step 3: Password setup ---
step 3 "Configuring password protection"
mkdir -p ~/.streamlit
if [ ! -f ~/.streamlit/secrets.toml ]; then
    read -sp "  Choose a dashboard password: " DASH_PASS
    echo
    cat > ~/.streamlit/secrets.toml << EOF
password = "$DASH_PASS"
EOF
    echo "  Password saved."
else
    warn "Password already configured, skipping."
fi

# --- Step 4: Streamlit config ---
step 4 "Configuring Streamlit"
cat > ~/.streamlit/config.toml << 'EOF'
[server]
headless = true
address = "0.0.0.0"
port = 8501
enableCORS = false
enableXsrfProtection = true

[browser]
gatherUsageStats = false
EOF
echo "  Done."

# --- Step 5: Systemd service ---
step 5 "Creating systemd service"
cat > /etc/systemd/system/${SERVICE_NAME}.service << EOF
[Unit]
Description=Stock Analyst Dashboard
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${APP_DIR}
ExecStart=${APP_DIR}/venv/bin/streamlit run dashboard.py
Restart=always
RestartSec=5
Environment=HOME=/root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ${SERVICE_NAME} > /dev/null 2>&1
systemctl restart ${SERVICE_NAME}
echo "  Service started."

# --- Step 6: Cron job for nightly scan ---
step 6 "Setting up nightly scanner cron job"
CRON_CMD="0 ${SCANNER_HOUR} * * * cd ${APP_DIR} && ${APP_DIR}/venv/bin/python3 scanner.py >> ${APP_DIR}/scan.log 2>&1"
# Add cron job only if it doesn't already exist
(crontab -l 2>/dev/null | grep -v "scanner.py"; echo "$CRON_CMD") | crontab -
echo "  Scanner will run nightly at ${SCANNER_HOUR}:00 AM."

# --- Step 7: Firewall ---
step 7 "Configuring firewall"
ufw allow 22 > /dev/null 2>&1
ufw allow 8501 > /dev/null 2>&1
ufw --force enable > /dev/null 2>&1
echo "  Ports 22 (SSH) and 8501 (Dashboard) open."

# --- Done ---
VPS_IP=$(hostname -I | awk '{print $1}')
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Deployment complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "  Dashboard: http://${VPS_IP}:8501"
echo "  Service:   systemctl status ${SERVICE_NAME}"
echo "  Logs:      journalctl -u ${SERVICE_NAME} -f"
echo "  Scan log:  tail -f ${APP_DIR}/scan.log"
echo ""
echo "  To redeploy after code changes:"
echo "    scp -r ./* root@${VPS_IP}:${APP_DIR}/"
echo "    ssh root@${VPS_IP} systemctl restart ${SERVICE_NAME}"
echo ""
