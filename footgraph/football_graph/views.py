from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Q
from .models import League, Club, Player, Data
import numpy as np
import json
from django.core.cache import cache
import pandas as pd
import logging
import plotly.express as px
import plotly.graph_objects as go
from plotly.offline import plot
import plotly

logger = logging.getLogger(__name__)

def home(request):
    """Main view for player filtering and visualization"""
    try:
        cache_key_prefix = 'dropdown_data'
        leagues = cache.get(f'{cache_key_prefix}_leagues')
        clubs = cache.get(f'{cache_key_prefix}_clubs')
        countries = cache.get(f'{cache_key_prefix}_countries')
        positions = cache.get(f'{cache_key_prefix}_positions')
        
        if not all([leagues, clubs, countries, positions]):
            leagues = League.objects.all().order_by('name')
            clubs = Club.objects.all().order_by('name')
            countries = list(Player.objects.values_list('country', flat=True).distinct().order_by('country'))
            
            positions_raw = Player.objects.exclude(position__isnull=True).exclude(position='').values_list('position', flat=True)
            unique_positions = set()
            for pos in positions_raw:
                if pos:
                    cleaned_pos = pos.split(',')[0].strip()
                    unique_positions.add(cleaned_pos)
            positions = sorted(list(unique_positions))
            
            # set cache with a 1-hour expiration for more efficient data retrieval
            cache.set(f'{cache_key_prefix}_leagues', leagues, 3600)
            cache.set(f'{cache_key_prefix}_clubs', clubs, 3600)
            cache.set(f'{cache_key_prefix}_countries', countries, 3600)
            cache.set(f'{cache_key_prefix}_positions', positions, 3600)

        if request.method == 'POST':
            return handle_post_request(request, leagues, clubs, countries, positions)
        else:
            return handle_get_request(request, leagues, clubs, countries, positions)
            
    except Exception as e:
        logger.error(f"Error in home view: {str(e)}")
        return render(request, 'football_graph/error.html', {'error': 'An error occurred while loading the page.'})

def handle_post_request(request, leagues, clubs, countries, positions):
    """Handle POST request for filtering and chart generation"""
    try:
        form_data = extract_form_data(request)
        
        players = apply_filters(form_data)
        
        if not players.exists():
            context = build_context(leagues, clubs, countries, positions, form_data)
            context['error'] = 'No players found matching the selected criteria.'
            return render(request, 'football_graph/home.html', context)
        
        chart_data = create_player_scatter_plot(players, form_data['x_axis'], form_data['y_axis'])
        
        if chart_data is None:
            context = build_context(leagues, clubs, countries, positions, form_data)
            context['error'] = 'No data available for the selected statistics.'
            return render(request, 'football_graph/home.html', context)

        context = build_context(leagues, clubs, countries, positions, form_data, chart_data, players)
        return render(request, 'football_graph/home.html', context)
        
    except Exception as e:
        logger.error(f"Error in POST request: {str(e)}")
        context = build_context(leagues, clubs, countries, positions)
        context['error'] = 'An error occurred while processing your request.'
        return render(request, 'football_graph/home.html', context)

def handle_get_request(request, leagues, clubs, countries, positions):
    """Handle GET request for initial page load"""
    context = build_context(leagues, clubs, countries, positions)
    return render(request, 'football_graph/home.html', context)

def extract_form_data(request):
    """Extract and validate form data from POST request"""
    try:
        return {
            'league_ids': [int(x) for x in request.POST.getlist('league') if x.isdigit()],
            'club_ids': [int(x) for x in request.POST.getlist('club') if x.isdigit()],
            'countries_selected': request.POST.getlist('country'),
            'positions_selected': request.POST.getlist('position'),
            'min_age': max(0, int(request.POST.get('min_age', 0) or 0)),
            'max_age': min(100, int(request.POST.get('max_age', 100) or 100)),
            'min_height': max(0, int(request.POST.get('min_height', 0) or 0)),
            'max_height': min(250, int(request.POST.get('max_height', 250) or 250)),
            'min_market_value': max(0, int(request.POST.get('min_market_value', 0) or 0)) * 1000000,
            'max_market_value': min(500000000, int(request.POST.get('max_market_value', 500) or 500)) * 1000000,
            'x_axis': request.POST.get('x_axis', 'expected_goals'),
            'y_axis': request.POST.get('y_axis', 'goals'),
            'min_market_value_display': int(request.POST.get('min_market_value', 0) or 0),
            'max_market_value_display': int(request.POST.get('max_market_value', 500) or 500),
        }
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid form data: {str(e)}")
        return {
            'league_ids': [], 'club_ids': [], 'countries_selected': [], 'positions_selected': [],
            'min_age': 0, 'max_age': 100, 'min_height': 0, 'max_height': 250,
            'min_market_value': 0, 'max_market_value': 500000000,
            'x_axis': 'expected_goals', 'y_axis': 'goals',
            'min_market_value_display': 0, 'max_market_value_display': 500,
        }

def apply_filters(form_data):
    """Apply filters to player queryset"""
    players = Player.objects.select_related('club', 'club__league').prefetch_related('data')
    print(f"Initial player count: {players.count()}")
    if form_data['league_ids']:
        players = players.filter(club__league_id__in=form_data['league_ids'])
        print(f"Player count after league filter: {players.count()}")
    
    if form_data['club_ids']:
        players = players.filter(club_id__in=form_data['club_ids'])
        print(f"Player count after club filter: {players.count()}")
    
    if form_data['countries_selected']:
        players = players.filter(country__in=form_data['countries_selected'])
        print(f"Player count after country filter: {players.count()}")
    
    if form_data['positions_selected']:
        position_q = Q()
        for position in form_data['positions_selected']:
            position_q |= Q(position__icontains=position)
        players = players.filter(position_q)
        print(f"Player count after position filter: {players.count()}")
    
    # Age
    if form_data['min_age'] > 0:
        players = players.filter(age__gte=form_data['min_age'])
    if form_data['max_age'] < 100:
        players = players.filter(age__lte=form_data['max_age'])
    print(f"Player count after age filter: {players.count()}")
    
    # Height
    if form_data['min_height'] > 0:
        players = players.filter(height__gte=form_data['min_height'])
    if form_data['max_height'] < 250:
        players = players.filter(height__lte=form_data['max_height'])
    print(f"Player count after height filter: {players.count()}")
    
    # Market value
    if form_data['min_market_value'] > 0:
        players = players.filter(market_value__gte=form_data['min_market_value'])
    if form_data['max_market_value'] < 500000000:
        players = players.filter(market_value__lte=form_data['max_market_value'])
    print(f"Player count after market value filter: {players.count()}")
    
    return players.order_by('name')

def build_context(leagues, clubs, countries, positions, form_data=None, chart_data=None, players=None):
    """Build context dictionary for template rendering"""
    context = {
        'leagues': leagues,
        'clubs': clubs,
        'countries': countries,
        'positions': positions,
        'data_field_choices': get_data_field_choices(),
    }
    
    if form_data:
        context.update({
            'selected_leagues': [str(x) for x in form_data['league_ids']],
            'selected_clubs': [str(x) for x in form_data['club_ids']],
            'selected_countries': form_data['countries_selected'],
            'selected_positions': form_data['positions_selected'],
            'form_data': {
                'min_age': form_data['min_age'],
                'max_age': form_data['max_age'],
                'min_height': form_data['min_height'],
                'max_height': form_data['max_height'],
                'min_market_value': form_data['min_market_value_display'],
                'max_market_value': form_data['max_market_value_display'],
                'x_axis': form_data['x_axis'],
                'y_axis': form_data['y_axis'],
            }
        })
    
    if chart_data:
        context.update({
            'chart_data': {
                'graphic': chart_data['graphic'],
            },
            'x_axis_label': form_data['x_axis'].replace('_', ' ').title(),
            'y_axis_label': form_data['y_axis'].replace('_', ' ').title(),
        })
    
    if players is not None:
        context['players'] = players
        context['player_count'] = players.count()
    
    return context

def create_player_scatter_plot(players, x_axis, y_axis):
    """Create interactive scatter plot with Plotly"""
    if not players.exists():
        logger.warning("No players found for the scatter plot.")
        return None

    plot_data = []
    for player in players:
        data_obj = player.data.first()
        if not data_obj:
            logger.warning(f"No data found for player: {player.name}")
            continue

        x_value = getattr(data_obj, x_axis, None)
        y_value = getattr(data_obj, y_axis, None)

        if x_value is None or y_value is None:
            logger.warning(f"Missing x or y value for player: {player.name}")
            continue

        if x_value >= 0 and y_value >= 0:
            plot_data.append({
                'name': player.name,
                'club': player.club.name if player.club else 'Unknown',
                'country': player.country or 'Unknown',
                'position': player.position or 'Unknown',
                'age': player.age or 'Unknown',
                'market_value': f"€{float(player.market_value)/1000000:.1f}M" if player.market_value and str(player.market_value).isdigit() else 'Unknown',
                'x': float(x_value),
                'y': float(y_value)
            })

    if not plot_data:
        logger.warning("No valid data points for the scatter plot.")
        return None

    df = pd.DataFrame(plot_data)
    print(f"DataFrame shape: {df.shape}")
    print(f"DataFrame columns: {df.columns.tolist()}")
    print("Sample data:")
    print(df.head())

    # Create the scatter plot
    fig = px.scatter(
        df,
        x='x',
        y='y',
        title=f'{x_axis.replace("_", " ").title()} vs {y_axis.replace("_", " ").title()}',
        labels={
            'x': x_axis.replace('_', ' ').title(), 
            'y': y_axis.replace('_', ' ').title()
        }
    )

    fig.update_traces(
        marker=dict(
            size=12, 
            color='steelblue', 
            line=dict(width=2, color='white'),
            opacity=0.8
        ),
        hovertemplate='<b>%{text}</b><br>' +
                     f'{x_axis.replace("_", " ").title()}: %{{x}}<br>' +
                     f'{y_axis.replace("_", " ").title()}: %{{y}}<br>' +
                     'Club: %{customdata[0]}<br>' +
                     'Country: %{customdata[1]}<br>' +
                     'Position: %{customdata[2]}<br>' +
                     'Age: %{customdata[3]}<br>' +
                     'Market Value: %{customdata[4]}' +
                     '<extra></extra>',
        text=df['name'],
        customdata=df[['club', 'country', 'position', 'age', 'market_value']].values
    )

    fig.update_layout(
        title_x=0.5,
        title_font_size=18,
        width=900,
        height=650,
        plot_bgcolor='rgba(248,249,250,0.8)',
        paper_bgcolor='white',
        font=dict(size=12),
        showlegend=False,
        xaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(0,0,0,0.1)',
            title_font_size=14,
            zeroline=True,
            zerolinecolor='rgba(0,0,0,0.2)',
            zerolinewidth=1
        ),
        yaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(0,0,0,0.1)',
            title_font_size=14,
            zeroline=True,
            zerolinecolor='rgba(0,0,0,0.2)',
            zerolinewidth=1
        ),
        margin=dict(l=50, r=50, t=80, b=50)
    )

    # Convert to HTML div for embedding
    graph_html = fig.to_html(include_plotlyjs=True, div_id="scatter-plot")

    return {
        'graphic': graph_html
    }

def get_data_field_choices():
    """Return all available data fields for axis selection"""
    return [
        # Shooting
        ('goals', 'Goals'),
        ('expected_goals', 'Expected Goals'),
        ('xg_on_target', 'xG on Target'),
        ('penalty_goals', 'Penalty Goals'),
        ('non_penalty_xg', 'Non-Penalty xG'),
        ('shots', 'Shots'),
        ('shots_on_target', 'Shots on Target'),
        
        # Passing
        ('assists', 'Assists'),
        ('expected_assists', 'Expected Assists'),
        ('successful_passes', 'Successful Passes'),
        ('pass_accuracy', 'Pass Accuracy'),
        ('accurate_long_balls', 'Accurate Long Balls'),
        ('long_ball_accuracy', 'Long Ball Accuracy'),
        ('chances_created', 'Chances Created'),
        ('successful_crosses', 'Successful Crosses'),
        ('cross_accuracy', 'Cross Accuracy'),
        
        # Possession
        ('successful_dribbles', 'Successful Dribbles'),
        ('dribble_success', 'Dribble Success'),
        ('touches', 'Touches'),
        ('touches_in_opposition_box', 'Touches in Opposition Box'),
        ('dispossessed', 'Dispossessed'),
        ('fouls_won', 'Fouls Won'),
        ('penalties_awarded', 'Penalties Awarded'),
        
        # Defending
        ('tackles_won', 'Tackles Won'),
        ('tackles_won_percentage', 'Tackles Won Percentage'),
        ('duels_won', 'Duels Won'),
        ('duels_won_percentage', 'Duels Won Percentage'),
        ('aerial_duels_won', 'Aerial Duels Won'),
        ('aerial_duels_won_percentage', 'Aerial Duels Won Percentage'),
        ('interceptions', 'Interceptions'),
        ('blocked', 'Blocked'),
        ('fouls_committed', 'Fouls Committed'),
        ('recoveries', 'Recoveries'),
        ('possession_won_final_3rd', 'Possession Won Final 3rd'),
        ('dribbled_past', 'Dribbled Past'),
        
        # Discipline
        ('yellow_cards', 'Yellow Cards'),
        ('red_cards', 'Red Cards'),
        
        # Goalkeeping
        ('saves', 'Saves'),
        ('save_percentage', 'Save Percentage'),
        ('goals_conceded', 'Goals Conceded'),
        ('goals_prevented', 'Goals Prevented'),
        ('clean_sheets', 'Clean Sheets'),
        ('error_led_to_goal', 'Error Led to Goal'),
        ('high_claim', 'High Claim'),
        
        # Goalkeeping Distribution
        ('gk_pass_accuracy', 'GK Pass Accuracy'),
        ('gk_accurate_long_balls', 'GK Accurate Long Balls'),
        ('gk_long_ball_accuracy', 'GK Long Ball Accuracy'),
    ]