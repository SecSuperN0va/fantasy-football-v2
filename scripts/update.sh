#!/usr/bin/env bash
# ==============================================================================
# Auto-Update Script for Raspberry Pi
# 1. Pulls latest changes from GitHub repository
# 2. Backs up database before migrations
# 3. Updates dependencies and applies database migrations
# 4. Restarts the systemd gunicorn service gracefully
# ==============================================================================

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_BIN="$APP_DIR/venv/bin"
LOG_FILE="$APP_DIR/update.log"
BACKUP_DIR="$APP_DIR/backups"

timestamp() {
    date "+%Y-%m-%d %H:%M:%S"
}

log() {
    echo "[$(timestamp)] $1" | tee -a "$LOG_FILE"
}

cd "$APP_DIR"

log "Starting auto-update check..."

# Ensure git safe directory
git config --global --add safe.directory "$APP_DIR" || true

# Fetch remote changes
git fetch origin main || git fetch origin master || {
    log "Network or git fetch failed. Skipping update."
    exit 0
}

# Determine default branch
BRANCH="main"
if ! git rev-parse --verify origin/main >/dev/null 2>&1; then
    BRANCH="master"
fi

LOCAL_HASH=$(git rev-parse HEAD)
REMOTE_HASH=$(git rev-parse "origin/$BRANCH")

if [ "$LOCAL_HASH" = "$REMOTE_HASH" ]; then
    log "Application is already up to date ($LOCAL_HASH)."
    exit 0
fi

log "New version detected! Local: $LOCAL_HASH -> Remote: $REMOTE_HASH"

# Backup database prior to migration
mkdir -p "$BACKUP_DIR"
if [ -f "$APP_DIR/db.sqlite3" ]; then
    BACKUP_FILE="$BACKUP_DIR/db_backup_$(date +%Y%m%d_%H%M%S).sqlite3"
    cp "$APP_DIR/db.sqlite3" "$BACKUP_FILE"
    log "Created database backup at $BACKUP_FILE"
    # Keep only the last 7 backups
    ls -tp "$BACKUP_DIR"/db_backup_*.sqlite3 | tail -n +8 | xargs -I {} rm -- {} 2>/dev/null || true
fi

# Pull updates
log "Pulling code updates from origin/$BRANCH..."
git reset --hard "origin/$BRANCH"

# Install any updated dependencies
if [ -f "$APP_DIR/requirements.txt" ]; then
    log "Updating Python virtualenv packages..."
    "$VENV_BIN/pip" install --quiet --upgrade -r "$APP_DIR/requirements.txt"
fi

# Run migrations
log "Running database migrations..."
"$VENV_BIN/python" "$APP_DIR/manage.py" migrate --noinput

# Load initial fixture data once if not already loaded
if [ -f "$APP_DIR/leagues/fixtures/initial_data.json" ] && [ ! -f "$APP_DIR/.initial_data_loaded" ]; then
    log "Loading initial database fixture..."
    "$VENV_BIN/python" "$APP_DIR/manage.py" loaddata initial_data.json
    touch "$APP_DIR/.initial_data_loaded"
    log "Initial database fixture loaded."
fi

# Collect static files if required
log "Collecting static assets..."
"$VENV_BIN/python" "$APP_DIR/manage.py" collectstatic --noinput 2>/dev/null || true

# Update systemd service file if changed and restart
SERVICE_DEST="/etc/systemd/system/fantasy-football.service"
CURRENT_USER="$(whoami)"
log "Updating systemd service configuration..."
sudo cp "$APP_DIR/scripts/fantasy-football.service" "$SERVICE_DEST"
sudo sed -i "s|User=pi|User=$CURRENT_USER|g" "$SERVICE_DEST"
sudo sed -i "s|Group=pi|Group=$CURRENT_USER|g" "$SERVICE_DEST"
sudo sed -i "s|/home/pi/fantasy_football|$APP_DIR|g" "$SERVICE_DEST"
sudo systemctl daemon-reload

# Restart systemd service
log "Restarting fantasy-football service..."
sudo systemctl restart fantasy-football.service

log "Auto-update successfully finished!"
