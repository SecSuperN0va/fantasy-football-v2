# Device Setup & Deployment Guide

This guide walks through setting up a brand-new Raspberry Pi (or similar Linux device) to host the **Fantasy Football UK** web application with automatic boot autostart, background updates from GitHub, and zero-maintenance resilience.

---

## 🎯 Architecture Overview

```
                      +-----------------------------+
                      |   GitHub Remote Repository   |
                      +-----------------------------+
                                     |
                         git fetch / git pull
                       (every 4 hours via cron)
                                     v
+-------------------------------------------------------------------------+
| Raspberry Pi (Home Network)                                             |
|                                                                         |
|  [systemd: fantasy-football.service]                                    |
|   - Starts automatically on boot                                        |
|   - Auto-restarts if process crashes                                    |
|   - Runs Gunicorn WSGI server on port 8000                              |
|                                                                         |
|  [cron: scripts/update.sh]                                              |
|   - Backs up db.sqlite3 before updating                                 |
|   - Pulls latest commits from origin/main                               |
|   - Runs database migrations & package updates                          |
|   - Restarts fantasy-football service seamlessly                        |
+-------------------------------------------------------------------------+
        |                                                 |
        v                                                 v
  Dad's iPhone / iPad                              Dad's Laptop / PC
  http://raspberrypi.local:8000                    http://192.168.1.X:8000
```

---

## 📋 Prerequisites

1. A Raspberry Pi running **Raspberry Pi OS** (Lite or Desktop) connected to the local home Wi-Fi or Ethernet.
2. The fantasy football codebase pushed to a **GitHub repository**.

---

## 🚀 Step 1: Push Codebase to GitHub (From Your PC)

If your local codebase is not already connected to GitHub, push it from your computer terminal:

```bash
cd c:\Users\Jordan\Documents\Antigravity\FantasyFootball

git init
git add .
git commit -m "Initial commit of UK Fantasy Football application"
git branch -M main
git remote add origin https://github.com/<YOUR-USERNAME>/<YOUR-REPO-NAME>.git
git push -u origin main
```

---

## 🍓 Step 2: One-Step Setup on the Raspberry Pi

1. **Connect to the Raspberry Pi** via SSH (or open Terminal on the Pi desktop):
   ```bash
   ssh pi@raspberrypi.local
   ```
   *(Default username is usually `pi`, or whatever account you created during OS flashing)*.

2. **Clone the repository**:
   ```bash
   git clone https://github.com/<YOUR-USERNAME>/<YOUR-REPO-NAME>.git /home/pi/fantasy_football
   ```

   > [!TIP]
   > **For Private Repositories:**
   > If your GitHub repository is private, configure an SSH Deploy Key or GitHub Personal Access Token so Git can pull without prompting for credentials:
   > ```bash
   > ssh-keygen -t ed25519 -C "raspberrypi-fantasy-football"
   > cat ~/.ssh/id_ed25519.pub
   > # Add this public key under your GitHub Repo -> Settings -> Deploy Keys
   > git clone git@github.com:<YOUR-USERNAME>/<YOUR-REPO-NAME>.git /home/pi/fantasy_football
   > ```

3. **Run the Automated Setup Script**:
   ```bash
   cd /home/pi/fantasy_football
   bash scripts/setup_pi.sh
   ```

---

## ⚙️ What the Setup Script Configures Automatically

The `setup_pi.sh` script executes end-to-end configuration unattended:

1. **System Libraries**: Installs `python3-venv`, `python3-dev`, `libxml2-dev`, `libxslt1-dev`, `git`, and `curl`.
2. **Python Environment**: Creates `/home/pi/fantasy_football/venv` and installs all packages from `requirements.txt` (including production WSGI server `gunicorn`).
3. **Database Setup**: Applies all SQLite migrations and creates the default superuser (`admin` / `admin123`).
4. **Boot Autostart (`systemd`)**:
   - Copies `scripts/fantasy-football.service` to `/etc/systemd/system/`.
   - Customizes the working directory and username automatically.
   - Enables the service: **it starts automatically on boot and recovers after power cuts**.
5. **Auto-Updater & Scraper (`cron`)**:
   - Configures `scripts/update.sh` to check GitHub every 4 hours.
   - Configures an automatic nightly BBC Sport scrape check at 22:00.

---

## 📱 Accessing the Application

Once the installation completes, the application is live on the local network. Anyone connected to the home Wi-Fi can open it in a browser:

* **By Hostname:** [http://raspberrypi.local:8000/](http://raspberrypi.local:8000/)
* **By IP Address:** `http://<RPI-LOCAL-IP>:8000/` (e.g., `http://192.168.1.50:8000/`)

> [!NOTE]
> Bookmark this link on your dad's phone or laptop home screen for one-tap access.

---

## 🛠️ Ongoing Maintenance & Remote Updates

### Pushing Updates
Whenever you develop new features or fix bugs, simply push them to GitHub from your computer:
```bash
git add .
git commit -m "Update feature XYZ"
git push origin main
```
The Raspberry Pi will:
1. Detect the new commit within 4 hours.
2. Create a timestamped backup of the database in `/home/pi/fantasy_football/backups/`.
3. Fast-forward the code and run any new database migrations.
4. Restart the web server gracefully.

### Manual Update Trigger
If you want to pull an update immediately without waiting for the cron timer:
```bash
ssh pi@raspberrypi.local "bash /home/pi/fantasy_football/scripts/update.sh"
```

### Useful Management Commands (On the Pi)

* **Check web server status:**
  ```bash
  sudo systemctl status fantasy-football.service
  ```
* **Restart the server manually:**
  ```bash
  sudo systemctl restart fantasy-football.service
  ```
* **View live server logs:**
  ```bash
  sudo journalctl -u fantasy-football.service -f
  ```
* **View auto-update logs:**
  ```bash
  cat /home/pi/fantasy_football/update.log
  ```
* **View database backups:**
  ```bash
  ls -lh /home/pi/fantasy_football/backups/
  ```

---

## 🔌 Power Cycling & Troubleshooting

* **If anything freezes or stops responding**: Power-cycle the device (unplug power cable, wait 5 seconds, plug back in). The systemd service will start the web app automatically within 30 seconds of booting.
* **If Wi-Fi changes**: Plug the Pi into the home router using an Ethernet cable, or update `/etc/wpa_supplicant/wpa_supplicant.conf` with the new Wi-Fi credentials.
