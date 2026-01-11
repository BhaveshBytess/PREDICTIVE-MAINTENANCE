#!/bin/bash
# ==============================================================================
# Predictive Maintenance - Linux Setup Script
# ==============================================================================
# This script sets up the backend on a bare-metal Linux server.
# Run with sudo: sudo ./setup_linux.sh
# ==============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Predictive Maintenance - Linux Setup${NC}"
echo -e "${GREEN}========================================${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run as root (sudo ./setup_linux.sh)${NC}"
    exit 1
fi

# Get the actual user (not root)
ACTUAL_USER=${SUDO_USER:-$USER}
APP_DIR="/opt/predictive-maintenance"
VENV_DIR="$APP_DIR/venv"

# ==============================================================================
# Step 1: Install System Dependencies
# ==============================================================================
echo -e "${YELLOW}[1/5] Installing system dependencies...${NC}"

apt-get update
apt-get install -y python3 python3-pip python3-venv git curl

echo -e "${GREEN}✓ System dependencies installed${NC}"

# ==============================================================================
# Step 2: Create Application Directory
# ==============================================================================
echo -e "${YELLOW}[2/5] Creating application directory...${NC}"

mkdir -p "$APP_DIR"
chown -R "$ACTUAL_USER:$ACTUAL_USER" "$APP_DIR"

echo -e "${GREEN}✓ Application directory created: $APP_DIR${NC}"

# ==============================================================================
# Step 3: Copy Application Files (if running from source)
# ==============================================================================
echo -e "${YELLOW}[3/5] Copying application files...${NC}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -d "$SCRIPT_DIR/backend" ]; then
    cp -r "$SCRIPT_DIR/backend" "$APP_DIR/"
    cp -r "$SCRIPT_DIR/tests" "$APP_DIR/" 2>/dev/null || true
    cp "$SCRIPT_DIR/requirements.txt" "$APP_DIR/" 2>/dev/null || true
    chown -R "$ACTUAL_USER:$ACTUAL_USER" "$APP_DIR"
    echo -e "${GREEN}✓ Application files copied${NC}"
else
    echo -e "${YELLOW}⚠ No backend directory found. Please copy manually.${NC}"
fi

# ==============================================================================
# Step 4: Create Virtual Environment and Install Dependencies
# ==============================================================================
echo -e "${YELLOW}[4/5] Setting up Python virtual environment...${NC}"

sudo -u "$ACTUAL_USER" python3 -m venv "$VENV_DIR"
sudo -u "$ACTUAL_USER" "$VENV_DIR/bin/pip" install --upgrade pip

if [ -f "$APP_DIR/requirements.txt" ]; then
    sudo -u "$ACTUAL_USER" "$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt"
else
    # Install core dependencies
    sudo -u "$ACTUAL_USER" "$VENV_DIR/bin/pip" install \
        fastapi uvicorn pydantic influxdb-client pandas numpy \
        scikit-learn joblib reportlab openpyxl
fi

echo -e "${GREEN}✓ Virtual environment created: $VENV_DIR${NC}"

# ==============================================================================
# Step 5: Install Systemd Service
# ==============================================================================
echo -e "${YELLOW}[5/5] Installing systemd service...${NC}"

cp "$SCRIPT_DIR/scripts/backend.service" /etc/systemd/system/predictive-maintenance.service 2>/dev/null || \
cat > /etc/systemd/system/predictive-maintenance.service << 'EOF'
[Unit]
Description=Predictive Maintenance Backend API
After=network.target influxdb.service
Wants=influxdb.service

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/opt/predictive-maintenance
Environment="PATH=/opt/predictive-maintenance/venv/bin"
Environment="PYTHONPATH=/opt/predictive-maintenance"
ExecStart=/opt/predictive-maintenance/venv/bin/uvicorn backend.api.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable predictive-maintenance
systemctl start predictive-maintenance

echo -e "${GREEN}✓ Systemd service installed and started${NC}"

# ==============================================================================
# Summary
# ==============================================================================
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Application directory: $APP_DIR"
echo "Virtual environment:   $VENV_DIR"
echo "Service name:          predictive-maintenance"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status predictive-maintenance  # Check status"
echo "  sudo systemctl restart predictive-maintenance # Restart service"
echo "  sudo journalctl -u predictive-maintenance -f  # View logs"
echo ""
echo "API available at: http://localhost:8000"
echo ""
