from django.urls import path
from . import views

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('league/<int:league_id>/', views.LeagueDetailView.as_view(), name='league_detail'),
    path('admin-hub/', views.AdminHubView.as_view(), name='admin_hub'),
    path('admin-hub/players/add/', views.PlayerCreateView.as_view(), name='player_create'),
    path('admin-hub/leagues/add/', views.LeagueCreateView.as_view(), name='league_create'),
    path('admin-hub/league/<int:league_id>/roster/', views.LeagueManageRosterView.as_view(), name='league_manage_roster'),
    path('admin-hub/league/<int:league_id>/toggle-lock/', views.LeagueToggleLockView.as_view(), name='league_toggle_lock'),
    path('admin-hub/league/<int:league_id>/archive/', views.LeagueArchiveView.as_view(), name='league_archive'),
    path('admin-hub/league/<int:league_id>/delete/', views.LeagueDeleteView.as_view(), name='league_delete'),
    path('admin-hub/league/<int:league_id>/set-active/', views.LeagueSetActiveView.as_view(), name='league_set_active'),
    path('admin-hub/league/<int:league_id>/player/<int:player_id>/picks/', views.ConfigurePlayerSelectionsView.as_view(), name='configure_picks'),
    path('real-tables/', views.RealLeagueTableView.as_view(), name='real_tables'),
    path('help/', views.HelpView.as_view(), name='help'),
    path('scrape/trigger/', views.ScrapeTriggerView.as_view(), name='scrape_trigger'),
]
