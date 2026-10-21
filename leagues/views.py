import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import View, TemplateView, ListView, DetailView
from django.contrib import messages
from django.urls import reverse

from .models import FFLeague, Player, SportsLeague, Selection, TeamStanding
from .forms import FFLeagueForm, PlayerForm, PlayerSelectionsForm
from .scraper import update_league_database

logger = logging.getLogger(__name__)


class DashboardView(TemplateView):
    """
    Main landing page showing:
    - Active fantasy league standings summary
    - Fast navigation to detailed views
    - Status of BBC sport tables
    """
    template_name = "leagues/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        active_league = FFLeague.objects.filter(is_active=True).first()
        if not active_league:
            active_league = FFLeague.objects.first()

        ctx['active_league'] = active_league
        if active_league:
            ctx['standings_data'] = active_league.get_standings_data()
        
        ctx['all_leagues'] = FFLeague.objects.all()
        ctx['sports_leagues'] = SportsLeague.objects.all().order_by('order_idx')
        ctx['players_count'] = Player.objects.count()
        return ctx


class LeagueDetailView(DetailView):
    """
    Full interactive scoreboard for a given fantasy league:
    - Leaderboard ranking
    - Per-division breakdown with interactive visual pills
    - Grid view & Card view switch
    """
    model = FFLeague
    template_name = "leagues/league_detail.html"
    context_object_name = "ff_league"
    pk_url_kwarg = "league_id"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        league = self.get_object()
        ctx['standings_data'] = league.get_standings_data()
        ctx['all_leagues'] = FFLeague.objects.all()
        return ctx


class AdminHubView(TemplateView):
    """
    League Management Hub:
    - Add new season / fantasy league
    - Quick add new player
    - Manage player rosters & pick configuration links
    """
    template_name = "leagues/admin_hub.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['ff_leagues'] = FFLeague.objects.all().prefetch_related('players')
        ctx['players'] = Player.objects.all().prefetch_related('ff_leagues')
        ctx['player_form'] = PlayerForm()
        ctx['league_form'] = FFLeagueForm()
        ctx['sports_leagues'] = SportsLeague.objects.all().order_by('order_idx')
        return ctx


class PlayerCreateView(View):
    def post(self, request, *args, **kwargs):
        form = PlayerForm(request.POST)
        if form.is_valid():
            player = form.save()
            messages.success(request, f"Player '{player.name}' was created successfully!")
            # If an active league exists, auto-add player to it optionally
            active_league = FFLeague.objects.filter(is_active=True).first()
            if active_league:
                active_league.players.add(player)
        else:
            err_msg = " ".join([f"{f}: {e[0]}" for f, e in form.errors.items()])
            messages.error(request, f"Could not create player: {err_msg}")
        return redirect('admin_hub')


class LeagueCreateView(View):
    def post(self, request, *args, **kwargs):
        form = FFLeagueForm(request.POST)
        if form.is_valid():
            league = form.save()
            messages.success(request, f"Fantasy League '{league.name}' was successfully created!")
            return redirect('league_manage_roster', league_id=league.id)
        else:
            err_msg = " ".join([f"{f}: {e[0]}" for f, e in form.errors.items()])
            messages.error(request, f"Could not create league: {err_msg}")
            return redirect('admin_hub')


class LeagueManageRosterView(View):
    """Manage which players are participating in this fantasy season."""
    template_name = "leagues/league_manage_roster.html"

    def get(self, request, league_id):
        league = get_object_or_404(FFLeague, pk=league_id)
        all_players = Player.objects.all()
        league_player_ids = set(league.players.values_list('id', flat=True))

        return render(request, self.template_name, {
            'league': league,
            'all_players': all_players,
            'league_player_ids': league_player_ids,
            'sports_leagues': SportsLeague.objects.filter(active=True),
        })

    def post(self, request, league_id):
        league = get_object_or_404(FFLeague, pk=league_id)
        if league.is_locked:
            messages.error(request, f"Cannot update roster: Season '{league.name}' is locked.")
            return redirect('league_manage_roster', league_id=league.id)

        selected_ids = request.POST.getlist('player_ids')
        players = Player.objects.filter(id__in=selected_ids)
        league.players.set(players)
        messages.success(request, f"Updated roster for {league.name}: {len(players)} players participating.")
        return redirect('league_manage_roster', league_id=league.id)


class ConfigurePlayerSelectionsView(View):
    """
    Dedicated, user-friendly page for configuring winning/losing picks
    for a single player in a specific fantasy league.
    """
    template_name = "leagues/configure_selections.html"

    def get(self, request, league_id, player_id):
        ff_league = get_object_or_404(FFLeague, pk=league_id)
        player = get_object_or_404(Player, pk=player_id)
        if ff_league.is_locked:
            messages.warning(request, f"Picks for '{ff_league.name}' are locked and cannot be edited.")
            return redirect('league_manage_roster', league_id=ff_league.id)

        form = PlayerSelectionsForm(ff_league=ff_league, player=player)
        return render(request, self.template_name, {
            'ff_league': ff_league,
            'player': player,
            'form': form,
            'sports_leagues': form.sports_leagues,
        })

    def post(self, request, league_id, player_id):
        ff_league = get_object_or_404(FFLeague, pk=league_id)
        player = get_object_or_404(Player, pk=player_id)
        if ff_league.is_locked:
            messages.error(request, f"Picks for '{ff_league.name}' are locked and cannot be modified.")
            return redirect('league_manage_roster', league_id=ff_league.id)

        form = PlayerSelectionsForm(request.POST, ff_league=ff_league, player=player)
        if form.is_valid():
            form.save()
            messages.success(request, f"Saved team picks for {player.name} in {ff_league.name}!")
            return redirect('league_manage_roster', league_id=ff_league.id)
        else:
            messages.error(request, "Please resolve the errors highlighted below.")
            return render(request, self.template_name, {
                'ff_league': ff_league,
                'player': player,
                'form': form,
                'sports_leagues': form.sports_leagues,
            })


class LeagueToggleLockView(View):
    """Toggle lock on a season's picks (prevents accidental or mid-season edits)."""
    def post(self, request, league_id):
        league = get_object_or_404(FFLeague, pk=league_id)
        league.is_locked = not league.is_locked
        league.save(update_fields=['is_locked'])
        state = "locked 🔒" if league.is_locked else "unlocked 🔓"
        messages.success(request, f"Picks for '{league.name}' are now {state}.")
        return redirect('league_manage_roster', league_id=league.id)


class LeagueArchiveView(View):
    """
    Archive a completed season:
    - Freezes its final standings snapshot
    - Marks it is_locked=True and is_archived=True
    - Sets is_active=False
    """
    def post(self, request, league_id):
        league = get_object_or_404(FFLeague, pk=league_id)
        league.is_locked = True
        league.is_archived = True
        league.is_active = False
        league.save(update_fields=['is_locked', 'is_archived', 'is_active'])
        messages.success(request, f"Season '{league.name}' has been safely archived! Its final standings and scores are permanently frozen.")
        return redirect('admin_hub')


class LeagueSetActiveView(View):
    """Mark a season as the current active season for live BBC scraping."""
    def post(self, request, league_id):
        league = get_object_or_404(FFLeague, pk=league_id)
        FFLeague.objects.filter(is_active=True).exclude(pk=league.id).update(is_active=False)
        league.is_active = True
        league.save(update_fields=['is_active'])
        messages.success(request, f"Season '{league.name}' is now the active season.")
        return redirect('admin_hub')


class LeagueDeleteView(View):
    """
    Delete a season and its associated player selections from the database
    after verification (requiring season name typed for confirmation).
    """
    def post(self, request, league_id):
        league = get_object_or_404(FFLeague, pk=league_id)
        confirm_name = request.POST.get('confirm_name', '').strip()
        league_name = league.name.strip()

        if confirm_name != league_name:
            messages.error(
                request,
                f"Delete cancelled: The confirmation name entered ('{confirm_name}') did not exactly match '{league_name}'."
            )
            return redirect('admin_hub')

        season_tag = league.season
        # Delete season selections and league record
        league.delete()

        # Clean up any season-scoped standings if no other league references this season
        if not FFLeague.objects.filter(season=season_tag).exists():
            TeamStanding.objects.filter(season=season_tag).delete()

        # If deleted league was active, promote another league if one exists
        if not FFLeague.objects.filter(is_active=True).exists():
            fallback = FFLeague.objects.first()
            if fallback:
                fallback.is_active = True
                fallback.save(update_fields=['is_active'])

        messages.success(request, f"Season '{league_name}' and all its selections were successfully deleted.")
        return redirect('admin_hub')


class RealLeagueTableView(TemplateView):
    """View the scraped real-life football league tables, filtered by season."""
    template_name = "leagues/real_tables.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        all_seasons = list(TeamStanding.objects.values_list('season', flat=True).distinct().order_by('-season'))
        
        # Determine target season: URL param ?season= or active season or most recent
        selected_season = self.request.GET.get('season')
        active_league = FFLeague.objects.filter(is_active=True).first()
        
        if not selected_season:
            selected_season = active_league.season if active_league else (all_seasons[0] if all_seasons else "2026")

        from django.db.models import Prefetch
        standings_qs = TeamStanding.objects.filter(season=selected_season).select_related('team').order_by('rank', '-points')
        sports_leagues = SportsLeague.objects.filter(active=True).prefetch_related(
            Prefetch('standings', queryset=standings_qs, to_attr='season_standings')
        )

        ctx['sports_leagues'] = sports_leagues
        ctx['selected_season'] = selected_season
        ctx['all_seasons'] = all_seasons
        ctx['active_league'] = active_league
        return ctx


class HelpView(TemplateView):
    """Visual step-by-step help and walkthroughs guide for league managers."""
    template_name = "leagues/help.html"


class ScrapeTriggerView(View):
    """Button to refresh scores by scraping BBC sports live."""
    def post(self, request, *args, **kwargs):
        result = update_league_database()
        if result['status'] == 'success':
            msg = f"Updated standings from BBC! Refreshed {len(result['updated_leagues'])} leagues ({result['teams_updated']} teams)."
            messages.success(request, msg)
        else:
            err = "; ".join(result['errors'])
            messages.error(request, f"Scrape failed: {err}")

        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or reverse('dashboard')
        return redirect(next_url)
