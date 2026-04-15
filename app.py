import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from nba_api.stats.static import teams, players
from nba_api.stats.endpoints import shotchartdetail, commonteamroster, leaguegamefinder, commonplayerinfo

# ==========================================
# 1. CONFIGURATION & ASSETS
# ==========================================
st.set_page_config(layout="wide", page_title="NBA Shot Lab", page_icon="🏀")

TEAM_THEMES = {
    'Atlanta Hawks': ['#E03A3E', '#C8102E'], 'Boston Celtics': ['#00C957', '#BA9653'],
    'Brooklyn Nets': ['#FFFFFF', '#333333'], 'Charlotte Hornets': ['#00B2A9', '#1D1160'],
    'Chicago Bulls': ['#CE1141', '#000000'], 'Cleveland Cavaliers': ['#860038', '#FDBB30'],
    'Dallas Mavericks': ['#007DC5', '#002B5E'], 'Denver Nuggets': ['#FEC524', '#0E2240'],
    'Detroit Pistons': ['#C8102E', '#1D428A'], 'Golden State Warriors': ['#1D428A', '#FFC72C'],
    'Houston Rockets': ['#CE1141', '#000000'], 'Indiana Pacers': ['#FDBB30', '#002D62'],
    'Los Angeles Clippers': ['#C8102E', '#1D428A'], 'Los Angeles Lakers': ['#FDB927', '#552583'],
    'Memphis Grizzlies': ['#5D76A9', '#12173F'], 'Miami Heat': ['#98002E', '#F9A01B'],
    'Milwaukee Bucks': ['#00471B', '#EEE1C6'], 'Minnesota Timberwolves': ['#236192', '#0C2340'],
    'New Orleans Pelicans': ['#B4975A', '#0C2340'], 'New York Knicks': ['#F58426', '#006BB6'],
    'Oklahoma City Thunder': ['#007AC1', '#EF3B24'], 'Orlando Magic': ['#0077C0', '#C4CED4'],
    'Philadelphia 76ers': ['#006BB6', '#ED174C'], 'Phoenix Suns': ['#E56020', '#1D1160'],
    'Portland Trail Blazers': ['#E03A3E', '#000000'], 'Sacramento Kings': ['#5A2D81', '#63727A'],
    'San Antonio Spurs': ['#C4CED4', '#000000'], 'Toronto Raptors': ['#CE1141', '#000000'],
    'Utah Jazz': ['#F9A01B', '#002B5C'], 'Washington Wizards': ['#E31837', '#002B5C']
}
DEFAULT_THEME = ['#C4CED4', '#000000']

RIVALRIES = {
    'Boston Celtics': ['LAL', 'PHI', 'MIA', 'NYK'],
    'Los Angeles Lakers': ['BOS', 'GSW', 'LAC', 'DEN'],
    'Golden State Warriors': ['LAL', 'MEM', 'PHX', 'SAC'],
    'New York Knicks': ['BOS', 'BKN', 'PHI', 'MIA'],
    'Philadelphia 76ers': ['BOS', 'NYK', 'MIL'],
    'Milwaukee Bucks': ['MIA', 'BOS', 'PHI', 'IND'],
    'Miami Heat': ['BOS', 'MIL', 'NYK', 'ORL'],
    'Dallas Mavericks': ['PHX', 'LAC', 'SAS', 'HOU'],
    'Phoenix Suns': ['DAL', 'LAL', 'GSW', 'DEN'],
    'Denver Nuggets': ['LAL', 'MIN', 'PHX', 'MIA']
}

# ==========================================
# 2. STATE MANAGEMENT
# ==========================================
def init_state():
    defaults = {
        'selected_shot': None, 'clutch_mode': False,
        'team_pick': 'Boston Celtics', 'player_pick': 'All Players',
        'game_id_pick': 'Full Season', 'bag_pick': []
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

def process_command():
    query = st.session_state.command_input.lower()
    if not query: return
    
    for t in teams.get_teams():
        if t['full_name'].lower() in query or t['nickname'].lower() in query:
            st.session_state.team_pick = t['full_name']
            on_team_change()
            break
            
    for p in players.get_active_players():
        if p['full_name'].lower() in query:
            try:
                info = commonplayerinfo.CommonPlayerInfo(player_id=p['id']).get_data_frames()[0]
                team_id = info['TEAM_ID'].iloc[0]
                team_name = next(t['full_name'] for t in teams.get_teams() if t['id'] == team_id)
                
                st.session_state.team_pick = team_name
                st.session_state.player_pick = p['full_name']
                st.session_state.game_id_pick = 'Full Season'
                break
            except:
                pass

    bag_keywords = {
        'step back': 'Step Back Jump shot', 'dunk': 'Dunk',
        'layup': 'Layup', 'floater': 'Floating Jump shot', 'fadeaway': 'Fadeaway Jump Shot'
    }
    found = [action for word, action in bag_keywords.items() if word in query]
    if found: st.session_state.bag_pick = found
    
    st.session_state.command_input = ""

def on_team_change():
    st.session_state.player_pick = 'All Players'
    st.session_state.selected_shot = None
    st.session_state.game_id_pick = 'Full Season'

def on_slider_change():
    st.session_state.game_id_pick = st.session_state.game_tape_slider

# ==========================================
# 3. DATA ENGINE
# ==========================================
@st.cache_data(ttl=86400)
def get_teams_map():
    return {t['full_name']: t['id'] for t in teams.get_teams()}

@st.cache_data(ttl=86400)
def get_roster(team_id):
    try:
        r = commonteamroster.CommonTeamRoster(team_id=team_id, season='2025-26').get_data_frames()[0]
        return {row['PLAYER']: row['PLAYER_ID'] for _, row in r.iterrows()}
    except:
        return {}

@st.cache_data(ttl=3600)
def fetch_schedule(team_id, team_name):
    try:
        games = leaguegamefinder.LeagueGameFinder(
            team_id_nullable=team_id
        ).get_data_frames()[0]
        
        games['GAME_DATE'] = pd.to_datetime(games['GAME_DATE'])
        games = games[(games['GAME_DATE'] >= '2025-10-21') & (games['GAME_DATE'] <= '2026-06-30')]
        games = games.sort_values('GAME_DATE').reset_index(drop=True)
        
        if games.empty: return pd.DataFrame()

        rivals = RIVALRIES.get(team_name, [])
        def create_label(row, i):
            date_str = row['GAME_DATE'].strftime('%b %d')
            matchup = row['MATCHUP']
            opp = matchup.split(' ')[-1]
            icons = ""
            if i == 0: icons += " 🚀"
            if row['GAME_DATE'].month == 12 and row['GAME_DATE'].day == 25: icons += " 🎄"
            is_cup = (row['GAME_DATE'].month == 11) or (row['GAME_DATE'].month == 12 and row['GAME_DATE'].day <= 17)
            if is_cup and row['GAME_DATE'].weekday() in [1, 4]: icons += " 🏆"
            if opp in rivals: icons += " 🔥"
            return f"{date_str} {matchup}{icons}"

        games['Label'] = [create_label(r, i) for i, r in games.iterrows()]
        return games
    except:
        return pd.DataFrame()

@st.cache_data(ttl=600)
def fetch_shots(player_id, team_id, game_id=None):
    try:
        params = {
            'player_id': player_id or 0,
            'team_id': team_id,
            'context_measure_simple': 'FGA'
        }
        
        if game_id:
            params['game_id_nullable'] = str(game_id).zfill(10)
            df = shotchartdetail.ShotChartDetail(**params).get_data_frames()[0]
        else:
            params['season_nullable'] = '2025-26'
            
            def get_season_shots(stype):
                try:
                    return shotchartdetail.ShotChartDetail(**params, season_type_all_star=stype).get_data_frames()[0]
                except:
                    return pd.DataFrame()
            
            df_rs = get_season_shots('Regular Season')
            df_pi = get_season_shots('PlayIn')
            df_po = get_season_shots('Playoffs')
            
            valid_shots = [d for d in [df_rs, df_pi, df_po] if not d.empty]
            if not valid_shots: return pd.DataFrame()
            df = pd.concat(valid_shots, ignore_index=True)

        if df.empty: return pd.DataFrame()
        
        base_url = "https://www.nba.com/stats/events/?flag=1&sct=plot&Season=2025-26"
        df['VIDEO_URL'] = base_url + "&GameID=" + df['GAME_ID'].astype(str) + "&GameEventID=" + df['GAME_EVENT_ID'].astype(str)
        df['id'] = df.index.astype(str)
        df['Zone'] = df.apply(lambda row: get_shot_zone(row['LOC_X'], row['LOC_Y']), axis=1)
        return df
    except:
        return pd.DataFrame()

def filter_shots(df, is_clutch, shot_type, outcome, bag_filters):
    if df.empty: return df
    mask = pd.Series(True, index=df.index)
    if is_clutch: mask &= df['PERIOD'] >= 4
    if shot_type == "2PT Field Goal": mask &= df['SHOT_TYPE'] == '2PT Field Goal'
    elif shot_type == "3PT Field Goal": mask &= df['SHOT_TYPE'] == '3PT Field Goal'
    if outcome == "Made": mask &= df['SHOT_MADE_FLAG'] ==
