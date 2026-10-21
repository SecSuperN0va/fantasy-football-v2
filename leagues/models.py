from django.db import models


class Team(models.Model):
    name = models.CharField(max_length=120, unique=True)
    short_code = models.CharField(max_length=10, blank=True, null=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class SportsLeague(models.Model):
    """Real-world sports league scraped from BBC (e.g. Premier League, Championship)"""
    name = models.CharField(max_length=120)
    bbc_name_slug = models.CharField(max_length=100, unique=True, help_text="Tab/section ID from BBC table page")
    last_updated = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True, help_text="Set to true to include in fantasy scoring & scraping")
    order_idx = models.IntegerField(default=0, help_text="Display order in table columns")

    class Meta:
        ordering = ['order_idx', 'name']
        verbose_name = "Sports League"
        verbose_name_plural = "Sports Leagues"

    def __str__(self):
        return self.name


class FFLeague(models.Model):
    """A Fantasy Football competition / season (e.g. Season 2025/2026)"""
    name = models.CharField(max_length=100)
    season = models.CharField(max_length=50, blank=True, help_text="Unique season identifier, e.g. 2025-2026")
    is_active = models.BooleanField(default=True, help_text="Active season being played and updated by live scraping")
    is_locked = models.BooleanField(default=False, help_text="Locked once matches start to prevent pick changes")
    is_archived = models.BooleanField(default=False, help_text="Archived at season end with frozen final scores")
    created_at = models.DateTimeField(auto_now_add=True)
    players = models.ManyToManyField('Player', related_name='ff_leagues', blank=True)

    class Meta:
        ordering = ['-is_active', '-created_at', 'name']
        verbose_name = "Fantasy League"
        verbose_name_plural = "Fantasy Leagues"

    def __str__(self):
        status = "Active" if self.is_active else "Archived" if self.is_archived else "Inactive"
        return f"{self.name} ({status})"

    def save(self, *args, **kwargs):
        # Automatically assign season string from name if left empty
        if not self.season:
            self.season = self.name.strip()
        super().save(*args, **kwargs)

    def get_standings_data(self):
        """
        Precomputes structured data for the scoreboard table and cards.
        Uses standings matching this league's specific season identifier.
        """
        sports_leagues = list(SportsLeague.objects.filter(active=True).order_by('order_idx'))
        all_players = list(self.players.all())

        # Preload standings scoped to this league's season
        standings_qs = TeamStanding.objects.filter(league__in=sports_leagues, season=self.season).select_related('team')
        # If no standings exist yet under this season (e.g. freshly created season before scrape), fallback to any available standings
        if not standings_qs.exists():
            standings_qs = TeamStanding.objects.filter(league__in=sports_leagues).select_related('team')

        standings_map = {
            (ts.team_id, ts.league_id): ts
            for ts in standings_qs
        }

        # Preload all selections for this FFLeague
        selections = (
            Selection.objects.filter(ff_league=self)
            .select_related('player', 'winner', 'loser', 'league')
        )
        selections_map = {
            (s.player_id, s.league_id): s
            for s in selections
        }

        leaderboard = []
        for player in all_players:
            total_score = 0
            league_breakdown = []

            for sp_league in sports_leagues:
                sel = selections_map.get((player.id, sp_league.id))
                if sel:
                    win_standing = standings_map.get((sel.winner_id, sp_league.id))
                    lose_standing = standings_map.get((sel.loser_id, sp_league.id))

                    win_pts = win_standing.points if win_standing else 0
                    win_rank = win_standing.rank if win_standing else None
                    lose_pts = lose_standing.points if lose_standing else 0
                    lose_rank = lose_standing.rank if lose_standing else None

                    diff = win_pts - lose_pts
                    total_score += diff

                    league_breakdown.append({
                        'sports_league': sp_league,
                        'has_selection': True,
                        'winner_name': sel.winner.name,
                        'winner_points': win_pts,
                        'winner_rank': win_rank,
                        'loser_name': sel.loser.name,
                        'loser_points': lose_pts,
                        'loser_rank': lose_rank,
                        'net_points': diff,
                    })
                else:
                    league_breakdown.append({
                        'sports_league': sp_league,
                        'has_selection': False,
                        'winner_name': '-',
                        'winner_points': 0,
                        'loser_name': '-',
                        'loser_points': 0,
                        'net_points': 0,
                    })

            leaderboard.append({
                'player': player,
                'total_score': total_score,
                'breakdown': league_breakdown,
            })

        leaderboard.sort(key=lambda x: x['total_score'], reverse=True)

        current_rank = 1
        for idx, row in enumerate(leaderboard):
            if idx > 0 and row['total_score'] < leaderboard[idx - 1]['total_score']:
                current_rank = idx + 1
            row['rank'] = current_rank

        return {
            'sports_leagues': sports_leagues,
            'leaderboard': leaderboard,
        }


class TeamStanding(models.Model):
    """
    Standing for a real team in a sports league, scoped to a specific football season.
    This guarantees that previous years' scores are preserved when a new season starts.
    """
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="standings")
    league = models.ForeignKey(SportsLeague, on_delete=models.CASCADE, related_name="standings")
    season = models.CharField(max_length=50, default="2026", db_index=True, help_text="Season identifier (e.g. 2026 or 2026-2027)")
    points = models.IntegerField(default=0)
    rank = models.IntegerField(default=0)
    played = models.IntegerField(default=0)
    won = models.IntegerField(default=0)
    drawn = models.IntegerField(default=0)
    lost = models.IntegerField(default=0)
    goal_difference = models.IntegerField(default=0)

    class Meta:
        unique_together = ('team', 'league', 'season')
        ordering = ['rank', '-points', 'team__name']

    def __str__(self):
        return f"{self.rank}. {self.team.name} ({self.points} pts) - {self.league.name} [{self.season}]"


class Player(models.Model):
    """A friend / participant in the fantasy league"""
    name = models.CharField(max_length=100, unique=True)
    email = models.EmailField(blank=True, null=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def league_score(self, ff_league):
        """Total fantasy points for this player in a specific fantasy league."""
        total = 0
        selections = self.selections.filter(ff_league=ff_league).select_related('winner', 'loser', 'league')
        for sel in selections:
            total += sel.total_points
        return total


class Selection(models.Model):
    """
    Each player's team pick in an active sports league for an FF league season:
    One team to win (points added) and one team to lose (points subtracted).
    """
    ff_league = models.ForeignKey(FFLeague, on_delete=models.CASCADE, related_name="selections")
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="selections")
    league = models.ForeignKey(SportsLeague, on_delete=models.CASCADE, related_name="selections")
    winner = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="winning_selections")
    loser = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="losing_selections")

    class Meta:
        unique_together = ('ff_league', 'player', 'league')
        verbose_name = "Player Selection"
        verbose_name_plural = "Player Selections"

    def __str__(self):
        return f"{self.player.name} in {self.league.name} [Win: {self.winner.name}, Lose: {self.loser.name}]"

    def _get_standing(self, team):
        # Look for standing within this league's season
        standing = TeamStanding.objects.filter(team=team, league=self.league, season=self.ff_league.season).first()
        if not standing:
            standing = TeamStanding.objects.filter(team=team, league=self.league).first()
        return standing

    @property
    def winner_standing(self):
        return self._get_standing(self.winner)

    @property
    def loser_standing(self):
        return self._get_standing(self.loser)

    @property
    def total_points(self):
        win_pts = self.winner_standing.points if self.winner_standing else 0
        lose_pts = self.loser_standing.points if self.loser_standing else 0
        return win_pts - lose_pts
