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
APP_DIR="$HOME/magnetmanager"
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

# === FETCH THE SCRIPT FROM GITHUB ===
echo "Fetching script from GitHub..."
if [ -d "$APP_DIR" ]; then
    # If directory exists but is not a git repo, back it up
    if [ ! -d "$APP_DIR/.git" ]; then
        echo "Directory exists but is not a git repository. Backing it up..."
        mv "$APP_DIR" "${APP_DIR}_backup_$(date +%Y%m%d%H%M%S)"
        git clone "$GITHUB_REPO" "$APP_DIR"
    else
        # If it's already a git repo, just pull updates
        cd "$APP_DIR"
        git pull origin main
    fi
else
    # Directory doesn't exist, create it and clone
    mkdir -p "$(dirname "$APP_DIR")"
    git clone "$GITHUB_REPO" "$APP_DIR"
fi

# === SETUP PYTHON VIRTUAL ENVIRONMENT ===
echo "Creating virtual environment..."
cd "$APP_DIR"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

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
