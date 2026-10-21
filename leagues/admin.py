from django.contrib import admin
from .models import Team, SportsLeague, TeamStanding, Player, FFLeague, Selection


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'short_code')
    search_fields = ('name',)


class TeamStandingInline(admin.TabularInline):
    model = TeamStanding
    extra = 0
    readonly_fields = ('team', 'rank', 'points', 'played', 'won', 'drawn', 'lost', 'goal_difference')
    can_delete = False


@admin.register(SportsLeague)
class SportsLeagueAdmin(admin.ModelAdmin):
    list_display = ('name', 'bbc_name_slug', 'active', 'order_idx', 'last_updated')
    list_editable = ('active', 'order_idx')
    inlines = [TeamStandingInline]


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('name', 'email')
    search_fields = ('name', 'email')


class SelectionInline(admin.TabularInline):
    model = Selection
    extra = 1
    autocomplete_fields = ('winner', 'loser')


@admin.register(FFLeague)
class FFLeagueAdmin(admin.ModelAdmin):
    list_display = ('name', 'season', 'is_active', 'created_at')
    list_filter = ('is_active', 'season')
    filter_horizontal = ('players',)
    inlines = [SelectionInline]


@admin.register(Selection)
class SelectionAdmin(admin.ModelAdmin):
    list_display = ('player', 'ff_league', 'league', 'winner', 'loser', 'total_points')
    list_filter = ('ff_league', 'league', 'player')
    search_fields = ('player__name', 'winner__name', 'loser__name')
