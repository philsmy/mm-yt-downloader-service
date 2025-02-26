#!/bin/bash

# Installer script for Raspberry Pi
# Sets up dependencies, downloads the script, and configures the systemd service

set -e  # Exit on error

# === CHECK FOR REDIS URL ARGUMENT ===
if [ -z "$1" ]; then
    echo "Usage: $0 <redis_url>"
    echo "Example: $0 redis://user:password@host:port/db"
    exit 1
fi

REDIS_URL="$1"  # Store Redis URL from command-line argument

# === CONFIGURATION ===
APP_DIR="/home/pi/magnetmanager"
VENV_DIR="$APP_DIR/venv"
SCRIPT_NAME="yt_downloader.py"
SERVICE_NAME="yt_downloader.service"
GITHUB_REPO="https://github.com/philsmy/mm-yt-downloader-service.git"  # Replace with your actual repo

# === UPDATE SYSTEM ===
echo "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# === INSTALL SYSTEM DEPENDENCIES ===
echo "Installing required system packages..."
sudo apt install -y python3 python3-venv python3-pip redis git

# === SETUP APPLICATION DIRECTORY ===
echo "Setting up application directory at $APP_DIR..."
mkdir -p "$APP_DIR"
cd "$APP_DIR"

# === SETUP PYTHON VIRTUAL ENVIRONMENT ===
echo "Creating virtual environment..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# === FETCH THE SCRIPT FROM GITHUB ===
echo "Fetching script from GitHub..."
if [ ! -d "$APP_DIR/.git" ]; then
    git clone "$GITHUB_REPO" "$APP_DIR"
else
    cd "$APP_DIR"
    git pull origin main
fi

# === INSTALL PYTHON DEPENDENCIES ===
echo "Installing Python dependencies..."
pip install -r "$APP_DIR/requirements.txt"

# === CREATE SYSTEMD SERVICE FILE ===
echo "Creating systemd service..."

cat <<EOF | sudo tee /etc/systemd/system/$SERVICE_NAME
[Unit]
Description=YouTube Transcript Processor Service
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=$APP_DIR
ExecStart=$VENV_DIR/bin/python $APP_DIR/$SCRIPT_NAME $REDIS_URL
Restart=always
RestartSec=5
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
EOF

# === RELOAD SYSTEMD, ENABLE AND START SERVICE ===
echo "Enabling and starting systemd service..."
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl start "$SERVICE_NAME"

# === VERIFY INSTALLATION ===
echo "Installation complete!"
echo "Checking service status..."
sudo systemctl status "$SERVICE_NAME"

