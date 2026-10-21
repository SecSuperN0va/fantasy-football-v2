# UK Fantasy Football (Winner/Loser League)

A modern Django web application built for managing a custom UK football league where players pick **one winning team** and **one losing team** for each division.

### Scoring Rule
$$\text{Player Total Score} = \sum_{\text{leagues}} (\text{Winner Team Points} - \text{Loser Team Points})$$

---

## 🌟 Key Features

1. **Modern Responsive UI / UX**:
   - Clean, professional dashboard with podium cards for top performers.
   - Dual-view Scoreboard: Full **Grid View** & **Player Cards View** with real-time toggle.
   - Visual pick pills (🟢 Winner / 🔴 Loser / 📊 Net points).

2. **Dedicated League Admin Hub**:
   - Simple, intuitive screens to add new players and create new seasons.
   - Checkbox roster management to enroll players into any season.
   - User-friendly team selection form per player with division grouping and validation to prevent choosing the same team as both winner and loser.

3. **Live BBC Sports Web Scraper**:
   - Scrapes official BBC football tables (Premier League, Championship, League One, League Two, etc.).
   - One-click **"Refresh Scores"** button directly in the navigation bar.
   - Real-time BBC table browser displaying positions, games played, goal differences, and points.
   - Timezone-aware timestamp updates.

4. **Robust Django Architecture**:
   - Proper app structure (`leagues` app).
   - Pre-computed, database-optimized leaderboard queries (`get_standings_data`).
   - Clean URLs and Class-Based Views (CBVs).
   - Complete Django admin configuration with inlines and search.

---

## 🚀 How to Run Locally

1. Open PowerShell or Terminal in this folder:
   ```bash
   python manage.py runserver
   ```

2. Open your browser and navigate to:
   - **Dashboard & Leaderboard:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
   - **Admin Hub:** [http://127.0.0.1:8000/admin-hub/](http://127.0.0.1:8000/admin-hub/)
   - **User Help Guide:** [http://127.0.0.1:8000/help/](http://127.0.0.1:8000/help/)
   - **Live BBC Tables:** [http://127.0.0.1:8000/real-tables/](http://127.0.0.1:8000/real-tables/)
   - **Django Admin:** [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/) (Login: `admin` / `admin123`)

---

## 🍓 Raspberry Pi Automated Deployment

To install this on a Raspberry Pi so it runs on boot and updates automatically:

1. **Clone repository on the Raspberry Pi**:
   ```bash
   git clone <YOUR_GITHUB_REPO_URL> /home/pi/fantasy_football
   cd /home/pi/fantasy_football
   ```

2. **Run the One-Step Setup Script**:
   ```bash
   bash scripts/setup_pi.sh
   ```

That's it!
- The app runs in the background as a systemd service (`fantasy-football.service`).
- Automatically starts on bootup (safe to power cycle anytime).
- Pulls updates from GitHub every 4 hours via `scripts/update.sh` and restarts gracefully.
- Access from any phone/tablet/laptop connected to the same Wi-Fi at `http://raspberrypi.local:8000` (or `http://<PI_IP>:8000`).
