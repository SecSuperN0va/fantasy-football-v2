import datetime
import logging
import re
from typing import Dict, Any, Tuple
import requests
import lxml.html

from .models import SportsLeague, Team, TeamStanding

logger = logging.getLogger(__name__)


def clean_ordinal_date(date_str: str) -> str:
    """Converts strings like '20th October 2026 at 02:21' to '20 October 2026 at 02:21'"""
    return re.sub(r'(\d)(st|nd|rd|th)', r'\1', date_str)


class ScrapeError(Exception):
    pass


class BBCFootballScraper:
    BASE_URL = 'https://www.bbc.co.uk/sport/football/tables'
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-GB,en;q=0.9',
    }

    def fetch_page_content(self) -> str:
        try:
            response = requests.get(self.BASE_URL, headers=self.HEADERS, timeout=15)
            response.raise_for_status()
            if not response.content:
                raise ScrapeError("Empty response received from BBC Sport.")
            return response.content.decode('utf-8', errors='replace')
        except requests.RequestException as exc:
            logger.error(f"Network error fetching BBC tables: {exc}")
            raise ScrapeError(f"Network error fetching BBC tables: {exc}") from exc

    def parse_league_panel(self, panel_element) -> Tuple[list, datetime.datetime | None]:
        standings = []
        last_updated = None

        # Look for the last updated footer
        for footer_elem in panel_element.xpath(".//div[contains(@class, 'StyledKeyFooter')]"):
            text = footer_elem.text_content()
            if 'Last Updated' in text:
                date_spans = footer_elem.xpath("./p/span/text()")
                if date_spans:
                    try:
                        clean_dt = clean_ordinal_date(date_spans[0].strip())
                        dt_naive = datetime.datetime.strptime(clean_dt, "%d %B %Y at %H:%M")
                        import zoneinfo
                        tz = zoneinfo.ZoneInfo("Europe/London")
                        last_updated = dt_naive.replace(tzinfo=tz)
                    except Exception as e:
                        logger.warning(f"Could not parse last updated date '{date_spans[0]}': {e}")

        # Look for football tables
        tables = panel_element.xpath(".//table[@data-testid='football-table']")
        if not tables:
            # Fallback to any table if data-testid changes
            tables = panel_element.xpath(".//table")

        for table in tables:
            headings = []
            # Extract header column names
            for th_span in table.xpath("./thead/tr/th/span/@data-always"):
                headings.append(str(th_span))

            if not headings:
                # Fallback header labels
                for th in table.xpath("./thead/tr/th"):
                    headings.append(th.text_content().strip())

            for row in table.xpath("./tbody/tr"):
                team_data = {}
                tds = row.xpath("./td")
                for i, td in enumerate(tds):
                    aria_label = td.get("aria-label", "")
                    if "Form" in aria_label:
                        continue

                    field_name = headings[i] if i < len(headings) else f"col_{i}"

                    if aria_label == "Team" or "Team" in field_name:
                        # Extract rank and team name
                        ranks = td.xpath(".//span[contains(@class, 'Rank')]/text()")
                        team_rank = str(ranks[0]).strip() if ranks else str(len(standings) + 1)

                        team_names = td.xpath(".//span[contains(@class, 'VisuallyHidden')]/text()")
                        if not team_names:
                            # Fallback if visually hidden isn't used
                            team_names = td.xpath(".//a/text() | .//span/text()")

                        team_name = str(team_names[0]).strip() if team_names else td.text_content().strip()

                        team_data['Rank'] = team_rank
                        team_data['Team'] = team_name
                    else:
                        txt = td.text_content().strip()
                        try:
                            team_data[field_name] = int(txt)
                        except ValueError:
                            team_data[field_name] = txt

                if 'Team' in team_data:
                    standings.append(team_data)

        return standings, last_updated

    def get_all_standings(self) -> Tuple[Dict[str, list], Dict[str, datetime.datetime | None]]:
        html = self.fetch_page_content()
        try:
            tree = lxml.html.document_fromstring(html)
        except Exception as exc:
            raise ScrapeError(f"Failed to parse HTML document: {exc}") from exc

        all_standings = {}
        last_updated_times = {}

        panels = tree.xpath("//section[@role='tabpanel']")
        for panel in panels:
            league_id = panel.get("id")
            if not league_id:
                continue
            standings, last_updated = self.parse_league_panel(panel)
            all_standings[league_id] = standings
            last_updated_times[league_id] = last_updated

        return all_standings, last_updated_times


def update_league_database(target_season: str = None) -> Dict[str, Any]:
    from .models import FFLeague
    if not target_season:
        active_league = FFLeague.objects.filter(is_active=True).first()
        target_season = active_league.season if active_league else "2026"

    scraper = BBCFootballScraper()
    result = {
        'status': 'success',
        'season': target_season,
        'updated_leagues': [],
        'teams_updated': 0,
        'errors': [],
        'skipped_leagues': []
    }

    try:
        standings_by_slug, updated_times = scraper.get_all_standings()
    except Exception as exc:
        logger.exception("Scraper failed to retrieve standings.")
        result['status'] = 'failed'
        result['errors'].append(str(exc))
        return result

    for slug, team_rows in standings_by_slug.items():
        try:
            league = SportsLeague.objects.get(bbc_name_slug=slug)
        except SportsLeague.DoesNotExist:
            result['errors'].append(f"Sports league with BBC slug '{slug}' not found in database.")
            continue

        if not league.active:
            result['skipped_leagues'].append(league.name)
            continue

        teams_count = 0
        for row in team_rows:
            team_name = row.get('Team')
            if not team_name:
                continue

            try:
                rank = int(row.get('Rank', 0))
            except (ValueError, TypeError):
                rank = 0

            try:
                points = int(row.get('Points', 0))
            except (ValueError, TypeError):
                points = 0

            team, _ = Team.objects.get_or_create(name=team_name.strip())
            standing, _ = TeamStanding.objects.get_or_create(team=team, league=league, season=target_season)
            standing.rank = rank
            standing.points = points
            standing.played = int(row.get('Played', 0)) if str(row.get('Played', '')).isdigit() else 0
            standing.won = int(row.get('Won', 0)) if str(row.get('Won', '')).isdigit() else 0
            standing.drawn = int(row.get('Drawn', 0)) if str(row.get('Drawn', '')).isdigit() else 0
            standing.lost = int(row.get('Lost', 0)) if str(row.get('Lost', '')).isdigit() else 0
            standing.goal_difference = int(row.get('GD', 0)) if isinstance(row.get('GD'), int) or (isinstance(row.get('GD'), str) and row.get('GD').lstrip('-+').isdigit()) else 0
            standing.save()
            teams_count += 1

        if slug in updated_times and updated_times[slug]:
            league.last_updated = updated_times[slug]
        else:
            league.last_updated = datetime.datetime.now(datetime.timezone.utc)
        league.save(update_fields=['last_updated'])

        result['updated_leagues'].append(f"{league.name} ({teams_count} teams)")
        result['teams_updated'] += teams_count

    return result
