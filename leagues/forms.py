from django import forms
from .models import FFLeague, Player, SportsLeague, Selection, Team


class FFLeagueForm(forms.ModelForm):
    class Meta:
        model = FFLeague
        fields = ['name', 'season', 'is_active', 'players']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Season 2026/27'}),
            'season': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 2026-2027'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'players': forms.CheckboxSelectMultiple(attrs={'class': 'list-unstyled player-checklist'}),
        }


class PlayerForm(forms.ModelForm):
    class Meta:
        model = Player
        fields = ['name', 'email']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Player name (e.g. Dave, John, Kev)'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Optional email for notifications'}),
        }


class PlayerSelectionsForm(forms.Form):
    """
    Form to easily configure winning and losing team selections for a player in a league.
    Dynamically generates fields for each active SportsLeague.
    """
    def __init__(self, *args, **kwargs):
        ff_league = kwargs.pop('ff_league')
        player = kwargs.pop('player')
        super().__init__(*args, **kwargs)

        self.ff_league = ff_league
        self.player = player
        self.sports_leagues = list(SportsLeague.objects.filter(active=True).order_by('order_idx'))

        # Fetch existing selections for quick initial population
        existing = {
            s.league_id: s
            for s in Selection.objects.filter(ff_league=ff_league, player=player)
        }

        for sp_league in self.sports_leagues:
            # Query teams that actually belong to this sports league
            teams_in_league = Team.objects.filter(standings__league=sp_league).distinct().order_by('name')
            # If no standings exist yet, fallback to all teams
            if not teams_in_league.exists():
                teams_in_league = Team.objects.all().order_by('name')

            win_field_name = f"winner_{sp_league.id}"
            lose_field_name = f"loser_{sp_league.id}"

            cur_sel = existing.get(sp_league.id)

            self.fields[win_field_name] = forms.ModelChoiceField(
                queryset=teams_in_league,
                label=f"{sp_league.name} - Winner Pick",
                required=False,
                initial=cur_sel.winner if cur_sel else None,
                widget=forms.Select(attrs={'class': 'form-select select-winner'})
            )
            self.fields[lose_field_name] = forms.ModelChoiceField(
                queryset=teams_in_league,
                label=f"{sp_league.name} - Loser Pick",
                required=False,
                initial=cur_sel.loser if cur_sel else None,
                widget=forms.Select(attrs={'class': 'form-select select-loser'})
            )

    @property
    def league_fields(self):
        """Yields tuples of (sports_league, winner_bound_field, loser_bound_field) for template rendering."""
        pairs = []
        for sp in self.sports_leagues:
            pairs.append({
                'sports_league': sp,
                'winner_field': self[f"winner_{sp.id}"],
                'loser_field': self[f"loser_{sp.id}"],
            })
        return pairs

    def clean(self):
        cleaned_data = super().clean()
        for sp_league in self.sports_leagues:
            winner = cleaned_data.get(f"winner_{sp_league.id}")
            loser = cleaned_data.get(f"loser_{sp_league.id}")

            if winner and loser and winner == loser:
                self.add_error(
                    f"loser_{sp_league.id}",
                    f"In {sp_league.name}, you cannot choose {winner.name} as both the winner and the loser!"
                )
            if (winner and not loser) or (loser and not winner):
                self.add_error(
                    f"loser_{sp_league.id}" if not loser else f"winner_{sp_league.id}",
                    f"Please provide both a winner and a loser for {sp_league.name}."
                )
        return cleaned_data

    def save(self):
        saved_selections = []
        for sp_league in self.sports_leagues:
            winner = self.cleaned_data.get(f"winner_{sp_league.id}")
            loser = self.cleaned_data.get(f"loser_{sp_league.id}")

            if winner and loser:
                sel, _ = Selection.objects.update_or_create(
                    ff_league=self.ff_league,
                    player=self.player,
                    league=sp_league,
                    defaults={'winner': winner, 'loser': loser}
                )
                saved_selections.append(sel)
            else:
                Selection.objects.filter(
                    ff_league=self.ff_league,
                    player=self.player,
                    league=sp_league
                ).delete()
        return saved_selections
