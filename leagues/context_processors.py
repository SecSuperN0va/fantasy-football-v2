from .models import FFLeague, SportsLeague


def global_league_context(request):
    """Provides navigation links, active league, and BBC scraping freshness across all pages."""
    all_ff_leagues = FFLeague.objects.all()
    active_ff_league = FFLeague.objects.filter(is_active=True).first()
    active_sports_leagues = SportsLeague.objects.filter(active=True).order_by('order_idx')
    latest_update = SportsLeague.objects.filter(last_updated__isnull=False).order_by('-last_updated').first()

    return {
        'nav_ff_leagues': all_ff_leagues,
        'nav_active_league': active_ff_league,
        'nav_sports_leagues': active_sports_leagues,
        'latest_scrape_time': latest_update.last_updated if latest_update else None,
    }
