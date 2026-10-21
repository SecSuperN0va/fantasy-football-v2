#!/usr/bin/env bash
# ==============================================================================
# One-Command Installation Script for Raspberry Pi
# Prepares Python environment, systemd service, auto-updater cron, and database
# ==============================================================================

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_NAME="fantasy-football.service"
CURRENT_USER="$(whoami)"

echo "=========================================================="
echo "Installing Fantasy Football UK on Raspberry Pi"
echo "Working directory: $APP_DIR"
echo "Running as user: $CURRENT_USER"
echo "=========================================================="

# 1. Install system packages
echo "[1/6] Installing necessary system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3-pip python3-venv python3-dev libxml2-dev libxslt1-dev git curl

# 2. Setup Virtual Environment
echo "[2/6] Setting up Python virtual environment..."
if [ ! -d "$APP_DIR/venv" ]; then
    python3 -m venv "$APP_DIR/venv"
fi
"$APP_DIR/venv/bin/pip" install --quiet --upgrade pip setuptools wheel
"$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

# 3. Initialize Django Database & Default Superuser
echo "[3/6] Running database migrations..."
"$APP_DIR/venv/bin/python" "$APP_DIR/manage.py" migrate --noinput

# Create superuser if none exists
"$APP_DIR/venv/bin/python" -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fantasy_football.settings')
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Created default admin account: admin / admin123')
else:
    print('Admin account already exists.')
"

# 4. Configure systemd Service for Boot Autostart
echo "[4/6] Configuring systemd autostart service..."
SERVICE_DEST="/etc/systemd/system/$SERVICE_NAME"
sudo cp "$APP_DIR/scripts/$SERVICE_NAME" "$SERVICE_DEST"

# Replace placeholder path and user with actual current user and app dir
sudo sed -i "s|User=pi|User=$CURRENT_USER|g" "$SERVICE_DEST"
sudo sed -i "s|Group=pi|Group=$CURRENT_USER|g" "$SERVICE_DEST"
sudo sed -i "s|/home/pi/fantasy_football|$APP_DIR|g" "$SERVICE_DEST"

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

# 5. Set up Auto-Update & Daily BBC Scrape Cron Jobs
echo "[5/6] Setting up cron jobs (Auto-update + scheduled BBC scraper)..."
chmod +x "$APP_DIR/scripts/update.sh"

CRON_JOB_UPDATE="0 */4 * * * $APP_DIR/scripts/update.sh >> $APP_DIR/update.log 2>&1"
CRON_JOB_SCRAPE="0 22 * * * $APP_DIR/venv/bin/python $APP_DIR/manage.py shell -c \"from leagues.scraper import update_league_database; print(update_league_database())\" >> $APP_DIR/scrape.log 2>&1"

(crontab -l 2>/dev/null | grep -Fv "update.sh" | grep -Fv "update_league_database" ; echo "$CRON_JOB_UPDATE" ; echo "$CRON_JOB_SCRAPE") | crontab -

# 6. Verify Service Status and IP Address
echo "[6/6] Verifying installation..."
sleep 2

LOCAL_IP=$(hostname -I | awk '{print $1}')
echo "=========================================================="
echo "✅ Installation Complete!"
echo "Service status: $(systemctl is-active $SERVICE_NAME)"
echo ""
echo "Access the app on any device on your home network at:"
echo "👉 http://$LOCAL_IP:8000/"
echo "👉 or http://raspberrypi.local:8000/"
echo ""
echo "Login credentials: Username: admin | Password: admin123"
echo "=========================================================="
