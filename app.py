import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from nba_api.stats.static import teams
from nba_api.stats.endpoints import shotchartdetail, commonteamroster, leaguegamefinder

# ==========================================
# 1. CONFIGURATION & ASSETS
# ==========================================
st.set_page_config(layout="wide", page_title="NBA Command Center V4.8 (Turbo)", page_icon="🏀")

# TEAM COLORS (Updated for Neon Pop)
TEAM_THEMES = {
    'Atlanta Hawks': ['#E03A3E', '#C8102E'], 'Boston Celtics': ['#00FF41', '#BA9653'], 
    'Brooklyn Nets': ['#FFFFFF', '#333333'], 'Charlotte Hornets': ['#00FFFF', '#1D1160'], 
    'Chicago Bulls': ['#FF0000', '#000000'], 'Cleveland Cavaliers': ['#860038', '#FDBB30'],
    'Dallas Mavericks': ['#007DC5', '#002B5E'], 'Denver Nuggets': ['#FEC524', '#0E2240'],
    'Detroit Pistons': ['#FF0000', '#1D428A'], 'Golden State Warriors': ['#1D428A', '#FFC72C'],
    'Houston Rockets': ['#FF0000', '#000000'], 'Indiana Pacers': ['#FDBB30', '#002D62'],
    'Los Angeles Clippers': ['#FF0000', '#1D428A'], 'Los Angeles Lakers': ['#FDB927', '#552583'],
    'Memphis Grizzlies': ['#5D76A9', '#12173F'], 'Miami Heat': ['#FF0000', '#F9A01B'],
    'Milwaukee Bucks': ['#00FF00', '#EEE1C6'], 'Minnesota Timberwolves': ['#00FF00', '#236192'],
    'New Orleans Pelicans': ['#B4975A', '#0C2340'], 'New York Knicks': ['#FF5500', '#006BB6'],
    'Oklahoma City Thunder': ['#007AC1', '#EF3B24'], 'Orlando Magic': ['#0077C0', '#C4CED4'],
    'Philadelphia 76ers': ['#006BB6', '#ED174C'], 'Phoenix Suns': ['#FF5500', '#1D1160'],
    'Portland Trail Blazers': ['#FF0000', '#000000'], 'Sacramento Kings': ['#A020F0', '#63727A'],
    'San Antonio Spurs': ['#C4CED4', '#000000'], 'Toronto Raptors': ['#FF0000', '#000000'],
    'Utah Jazz': ['#F9A01B', '#002B5C'], 'Washington Wizards': ['#FF0000', '#002B5C']
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

# --- STATE MANAGEMENT ---
if 'selected_shot' not in st.session_state: st.session_state.selected_shot = None
if 'clutch_mode' not in st.session_state: st.session_state.clutch_mode = False
if 'team_pick' not in st.session_state: st.session_state.team_pick = 'Boston Celtics'
if 'player_pick' not in st.session_state: st.session_state.player_pick = 'All Players'
if 'game_id_pick' not in st.session_state: st.session_state.game_id_pick = "Full Season"
if 'bag_pick' not in st.session_state: st.session_state.bag_pick = []

# --- COMMAND AI ---
def process_command():
    query = st.session_state.command_input.lower()
    if not query: return
    all_teams = teams.get_teams()
    for t in all_teams:
        if t['full_name'].lower() in query or t['nickname'].lower() in query:
            st.session_state.team_pick = t['full_name']
            on_team_change()
            break
    bag_keywords = {'step back': 'Step Back Jump shot', 'dunk': 'Dunk', 'layup': 'Layup', 'floater': 'Floating Jump shot', 'fadeaway': 'Fadeaway Jump Shot'}
    found_moves = [action for word, action in bag_keywords.items() if word in query]
    if found_moves: st.session_state.bag_pick = found_moves
    st.session_state.command_input = ""

def on_team_change():
    st.session_state.player_pick = 'All Players'
    st.session_state.selected_shot = None
    st.session_state.game_id_pick = "Full Season"

def on_slider_change():
    st.session_state.game_id_pick = st.session_state.game_tape_slider

# ==========================================
# 2. DATA ENGINE
# ==========================================
@st.cache_data(ttl=86400)
def get_teams_map():
    return {t['full_name']: t['id'] for t in teams.get_teams()}

@st.cache_data(ttl=86400)
def get_roster(team_id):
    try:
        r = commonteamroster.CommonTeamRoster(team_id=team_id, season='2025-26').get_data_frames()[0]
        return {row['PLAYER']: row['PLAYER_ID'] for _, row in r.iterrows()}
    except: return {}

@st.cache_data(ttl=3600)
def fetch_schedule(team_id, team_name):
    try:
        gamefinder = leaguegamefinder.LeagueGameFinder(team_id_nullable=team_id, season_nullable='2025-26')
        games = gamefinder.get_data_frames()[0]
        games['GAME_DATE'] = pd.to_datetime(games['GAME_DATE'])
        games = games[games['GAME_DATE'] >= '2025-10-21'].sort_values('GAME_DATE').reset_index(drop=True)
        if games.empty: return pd.DataFrame()

        def create_label(row, index):
            date_str = row['GAME_DATE'].strftime('%b %d')
            matchup = row['MATCHUP']
            opp_code = matchup.split(' ')[-1]
            icons = ""
            if index == 0: icons += " 🚀"
            if row['GAME_DATE'].month == 12 and row['GAME_DATE'].day == 25: icons += " 🎄"
            is_cup_window = (row['GAME_DATE'].month == 11) or (row['GAME_DATE'].month == 12 and row['GAME_DATE'].day <= 17)
            if is_cup_window and row['GAME_DATE'].weekday() in [1, 4]: icons += " 🏆"
            rivals = RIVALRIES.get(team_name, [])
            if opp_code in rivals: icons += " 🔥"
            return f"{date_str} {matchup}{icons}"
        games['Label'] = [create_label(row, i) for i, row in games.iterrows()]
        return games
    except: return pd.DataFrame()

@st.cache_data(ttl=600)
def fetch_shots_v2(player_id, team_id, game_id=None):
    try:
        p_id = player_id if player_id else 0
        params = {'player_id': p_id, 'team_id': team_id, 'context_measure_simple': 'FGA'}
        if game_id:
            params['game_id_nullable'] = str(game_id).zfill(10)
        else:
            params['season_nullable'] = '2025-26'
        df = shotchartdetail.ShotChartDetail(**params).get_data_frames()[0]
        if df.empty: return pd.DataFrame()
        base_url = "https://www.nba.com/stats/events/?flag=1&sct=plot&Season=2025-26"
        df['VIDEO_URL'] = base_url + "&GameID=" + df['GAME_ID'].astype(str) + "&GameEventID=" + df['GAME_EVENT_ID'].astype(str)
        df['id'] = df.index.astype(str)
        return df
    except: return pd.DataFrame()

def filter_shots_v2(df, is_clutch, shot_type, outcome, bag_filters):
    if df.empty: return df
    if is_clutch: df = df[df['PERIOD'] >= 4]
    if shot_type == "2PT Field Goal": df = df[df['SHOT_TYPE'] == '2PT Field Goal']
    elif shot_type == "3PT Field Goal": df = df[df['SHOT_TYPE'] == '3PT Field Goal']
    if outcome == "Made": df = df[df['SHOT_MADE_FLAG'] == 1]
    elif outcome == "Missed": df = df[df['SHOT_MADE_FLAG'] == 0]
    if bag_filters: df = df[df['ACTION_TYPE'].isin(bag_filters)]
    return df

# ==========================================
# 3. ANALYTICS ENGINE
# ==========================================
class AnalyticsEngine:
    @staticmethod
    def get_shot_zone(x, y):
        distance = np.sqrt(x**2 + y**2)
        if abs(x) > 220 and y <= 90: return 'Corner 3'
        if distance <= 40: return 'Restricted Area'
        if distance > 237.5: return 'Above the Break 3'
        if abs(x) < 80 and y < 190: return 'In The Paint (Non-RA)'
        return 'Mid-Range'

class BadgeEngine:
    @staticmethod
    def generate_badges(df, is_team=False):
        if df.empty: return []
        badges = []
        df = df.copy()
        df['Zone'] = df.apply(lambda row: AnalyticsEngine.get_shot_zone(row['LOC_X'], row['LOC_Y']), axis=1)
        total_shots = len(df); fg_pct = (df['SHOT_MADE_FLAG'] == 1).mean()
        if is_team:
            threes = df[df['Zone'].str.contains('3')]
            if total_shots > 0 and (len(threes) / total_shots) >= 0.40: badges.append({'icon': '☔', 'name': 'Rainmakers', 'color': 'rgba(94, 92, 230, 0.2)', 'text': '#BF5AF2'})
            paint = df[df['Zone'].isin(['Restricted Area', 'In The Paint (Non-RA)'])]
            if total_shots > 0 and (len(paint) / total_shots) >= 0.45: badges.append({'icon': '🏰', 'name': 'Paint Beasts', 'color': 'rgba(255, 59, 48, 0.2)', 'text': '#FF3B30'})
            if fg_pct >= 0.48: badges.append({'icon': '🔥', 'name': 'High Octane', 'color': 'rgba(255, 149, 0, 0.2)', 'text': '#FF9500'})
            clutch = df[df['PERIOD'] >= 4]
            if not clutch.empty and clutch['SHOT_MADE_FLAG'].mean() >= 0.45: badges.append({'icon': '⏱️', 'name': 'Clutch City', 'color': 'rgba(52, 199, 89, 0.2)', 'text': '#30D158'})
        else:
            threes = df[df['Zone'].str.contains('3')]
            if len(threes) >= 4 and threes['SHOT_MADE_FLAG'].mean() >= 0.40: badges.append({'icon': '🎯', 'name': 'Sniper', 'color': 'rgba(48, 209, 88, 0.2)', 'text': '#30D158'})
            zone_stats = df.groupby('Zone')['SHOT_MADE_FLAG'].agg(['mean', 'count'])
            if 'Restricted Area' in zone_stats.index:
                ra = zone_stats.loc['Restricted Area']
                if ra['count'] >= 4 and ra['mean'] >= 0.65: badges.append({'icon': '🔨', 'name': 'Finisher', 'color': 'rgba(10, 132, 255, 0.2)', 'text': '#0A84FF'})
            if 'Mid-Range' in zone_stats.index:
                mr = zone_stats.loc['Mid-Range']
                if mr['count'] >= 3 and mr['mean'] >= 0.50: badges.append({'icon': '🧙‍♂️', 'name': 'Mid-Range', 'color': 'rgba(191, 90, 242, 0.2)', 'text': '#BF5AF2'})
            if total_shots >= 15: badges.append({'icon': '🚀', 'name': 'Volume', 'color': 'rgba(255, 159, 10, 0.2)', 'text': '#FF9F0A'})
            if total_shots >= 8 and fg_pct <= 0.35: badges.append({'icon': '🧊', 'name': 'Cold', 'color': 'rgba(100, 210, 255, 0.2)', 'text': '#64D2FF'})
        return badges

class InsightsEngine:
    @staticmethod
    def generate_insights(df, is_team=False):
        if df.empty or len(df) < 5: return ["ℹ️ **Gathering Data:** Select more games or a different filter to see patterns."]
        insights = []
        df = df.copy()
        total_shots = len(df)
        df['Zone'] = df.apply(lambda row: AnalyticsEngine.get_shot_zone(row['LOC_X'], row['LOC_Y']), axis=1)
        if is_team:
            threes_freq = df[df['Zone'].str.contains('3')].shape[0] / total_shots
            if threes_freq > 0.45: insights.append(f"🏹 **Modern Offense:** Heavily reliant on the 3-ball ({threes_freq:.0%} of shots).")
            else: insights.append("⚖️ **Balanced Attack:** Good distribution across all 3 levels.")
        else:
            zone_counts = df['Zone'].value_counts(normalize=True)
            if not zone_counts.empty:
                fav_zone = zone_counts.idxmax()
                insights.append(f"📍 **Zone Heavy:** Taking {zone_counts.max():.0%} of shots in the {fav_zone}.")
            threes = df[df['Zone'].str.contains('3')]
            if len(threes) >= 5:
                pct = threes['SHOT_MADE_FLAG'].mean()
                if pct > 0.40: insights.append(f"🔥 **Sniper Alert:** Shooting {pct:.1%} from deep.")
            made = df['SHOT_MADE_FLAG'].sum()
            tpm = df[df['Zone'].str.contains('3')]['SHOT_MADE_FLAG'].sum()
            pps = ((made * 2) + tpm) / total_shots
            if pps > 1.25: insights.append(f"📈 **High Value:** Generating {pps:.2f} Points Per Shot.")
        if not insights: insights.append("⚖️ **Standard Deviation:** Performance aligns with league norms.")
        return insights[:3]

# ==========================================
# 4. CHART ENGINE (V4.8: TURBO GL)
# ==========================================
class ChartEngine:
    @staticmethod
    def hex_to_rgba(hex_code, alpha=1.0):
        hex_code = hex_code.lstrip('#')
        return f"rgba{tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4)) + (alpha,)}"

    @staticmethod
    def draw_court(fig, team_theme=DEFAULT_THEME, team_id=None):
        primary, secondary = team_theme
        glow_color = ChartEngine.hex_to_rgba(primary, 0.6) 
        core_color = "rgba(255, 255, 255, 0.9)"
        paint_fill = ChartEngine.hex_to_rgba(primary, 0.1)
        floor_tint = "rgba(255,255,255,0.01)"
        
        common_glow = dict(line=dict(color=glow_color, width=4), layer="below")
        common_core = dict(line=dict(color=core_color, width=1), layer="below")
        
        def get_arc(cx, cy, r, start, end):
            t = np.linspace(np.radians(start), np.radians(end), 50)
            path = f"M {cx + r*np.cos(t[0]):.2f} {cy + r*np.sin(t[0]):.2f}"
            for i in range(1, len(t)): path += f" L {cx + r*np.cos(t[i]):.2f} {cy + r*np.sin(t[i]):.2f}"
            return path

        shapes = [
            dict(type="rect", x0=-250, y0=-52.5, x1=250, y1=417.5, line=dict(width=0), fillcolor=floor_tint, layer="below"),
            dict(type="rect", x0=-80, y0=-52.5, x1=80, y1=137.5, line=dict(width=0), fillcolor=paint_fill, layer="below"),
        ]
        
        def add_neon_shape(shape_type, **kwargs):
            glow_kwargs = kwargs.copy(); glow_kwargs.update(common_glow)
            shapes.append(dict(type=shape_type, **glow_kwargs))
            core_kwargs = kwargs.copy(); core_kwargs.update(common_core)
            shapes.append(dict(type=shape_type, **core_kwargs))

        add_neon_shape("rect", x0=-250, y0=-52.5, x1=250, y1=417.5)
        add_neon_shape("rect", x0=-80, y0=-52.5, x1=80, y1=137.5)
        add_neon_shape("line", x0=-30, y0=-12.5, x1=30, y1=-12.5)
        add_neon_shape("path", path=get_arc(0, 0, 40, 0, 180))
        add_neon_shape("path", path=get_arc(0, 137.5, 60, 0, 180))
        shapes.append(dict(type="path", path=get_arc(0, 137.5, 60, 180, 360), line=dict(color=glow_color, width=2, dash='dot'), layer="below"))
        add_neon_shape("line", x0=-220, y0=-52.5, x1=-220, y1=89.47)
        add_neon_shape("line", x0=220, y0=-52.5, x1=220, y1=89.47)
        add_neon_shape("path", path=get_arc(0, 0, 237.5, 22, 158))
        add_neon_shape("path", path=get_arc(0, 417.5, 60, 180, 360))
        add_neon_shape("path", path=get_arc(0, 417.5, 20, 180, 360))
        shapes.append(dict(type="circle", x0=-7.5, y0=-7.5, x1=7.5, y1=7.5, xref="x", yref="y", line=dict(color="#FF9F0A", width=2), layer="below"))

        fig.update_layout(shapes=shapes, autosize=True)
        if team_id:
            logo_url = f"https://cdn.nba.com/logos/nba/{team_id}/global/L/logo.svg"
            fig.add_layout_image(dict(source=logo_url, xref="x", yref="y", x=0, y=417.5, sizex=100, sizey=100, xanchor="center", yanchor="middle", opacity=0.2, layer="below"))

    @staticmethod
    def draw_radar_dna(df, color):
        if df.empty: return go.Figure()
        df = df.copy()
        total = len(df)
        df['Zone'] = df.apply(lambda row: AnalyticsEngine.get_shot_zone(row['LOC_X'], row['LOC_Y']), axis=1)
        paint_vol = len(df[df['Zone'].isin(['Restricted Area', 'In The Paint (Non-RA)'])] ) / total
        mid_vol = len(df[df['Zone'] == 'Mid-Range']) / total
        three_vol = len(df[df['Zone'].str.contains('3')]) / total
        efficiency = df['SHOT_MADE_FLAG'].mean()
        corner_vol = len(df[df['Zone'] == 'Corner 3']) / total
        values = [min(paint_vol / 0.6, 1.0), min(three_vol / 0.6, 1.0), min(mid_vol / 0.4, 1.0), min(efficiency / 0.6, 1.0), min(corner_vol / 0.2, 1.0)]
        categories = ['Paint Presence', 'Deep Range', 'Mid-Range', 'Efficiency', 'Corner Spec']
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(r=values, theta=categories, fill='toself', line=dict(color=color), fillcolor=f"rgba{tuple(int(color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)) + (0.3,)}"))
        fig.update_layout(polar=dict(radialaxis=dict(visible=False, range=[0, 1]), bgcolor='rgba(0,0,0,0)', angularaxis=dict(tickfont=dict(size=10, color='rgba(255,255,255,0.6)'), linecolor='rgba(255,255,255,0.1)')), showlegend=False, margin=dict(l=20, r=20, t=20, b=20), paper_bgcolor='rgba(0,0,0,0)', height=200)
        return fig

# ==========================================
# 5. UI SYSTEM: "V4.8 OPTIMIZED MESH"
# ==========================================
def render_v3_css(theme_colors):
    primary = theme_colors[0]
    secondary = theme_colors[1]
    css = f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@500;700&family=Inter:wght@300;400;600&family=JetBrains+Mono:wght@400;700&display=swap');
        .stApp {{
            background-color: #050505;
            background-image: radial-gradient(#222 1px, transparent 1px);
            background-size: 20px 20px;
            font-family: 'Inter', sans-serif;
            color: #FFFFFF;
        }}
        .stApp::before {{
            content: ""; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: radial-gradient(circle, transparent 40%, #000000 100%);
            pointer-events: none; z-index: 0;
        }}
        h1, h2, h3, .hero-text-main {{ font-family: 'Oswald', sans-serif !important; text-transform: uppercase; }}
        section[data-testid="stSidebar"] {{ background-color: rgba(5, 5, 5, 0.9); border-right: 1px solid rgba(255, 255, 255, 0.05); }}
        .glass-panel {{ 
            background: rgba(30, 30, 30, 0.4); 
            backdrop-filter: blur(16px); 
            border: 1px solid rgba(255, 255, 255, 0.08); 
            border-radius: 12px; padding: 24px; 
            box-shadow: 0 4px 20px rgba(0,0,0,0.5); 
            margin-bottom: 20px; position: relative; z-index: 1;
        }}
        .hero-text-main {{ font-size: 42px; font-weight: 700; letter-spacing: 1px; color: white; margin: 0; padding: 0; line-height: 1.1; }}
        .stat-label {{ font-family: 'JetBrains Mono', monospace; font-size: 11px; letter-spacing: 1px; color: rgba(255,255,255,0.4); text-transform: uppercase; }}
        .stat-val {{ font-family: 'JetBrains Mono', monospace; font-size: 28px; font-weight: 700; color: {primary}; text-shadow: 0 0 10px {primary}44; }}
        .scout-badge {{ display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 4px; font-family: 'JetBrains Mono', monospace; font-size: 10px; font-weight: 700; border: 1px solid rgba(255,255,255,0.1); text-transform: uppercase; }}
        div[data-baseweb="select"] > div, .stTextInput > div > div {{ background-color: rgba(20,20,20,0.5) !important; border-color: rgba(255,255,255,0.1) !important; color: white !important; font-family: 'JetBrains Mono', monospace; font-size: 12px; }}
        .stSlider > div > div > div > div {{ background-color: {primary} !important; }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

# ==========================================
# 6. MAIN APP LOGIC
# ==========================================
with st.sidebar:
    st.markdown("<div style='font-family:Oswald; font-size: 24px; color:white; margin-bottom: 20px;'>COMMAND CENTER <span style='color:#FF4B4B; font-size:12px; vertical-align:top;'>V4.8</span></div>", unsafe_allow_html=True)
    st.text_input("AI Assistant", placeholder="Search 'Tatum vs Lakers'...", key="command_input", on_change=process_command, label_visibility="collapsed")
    
    teams_map = get_teams_map()
    team_name = st.selectbox("Team Organization", sorted(teams_map.keys()), index=sorted(teams_map.keys()).index(st.session_state.team_pick), label_visibility="collapsed", key="team_pick", on_change=on_team_change)
    team_id = teams_map[team_name]
    
    current_theme = TEAM_THEMES.get(team_name, DEFAULT_THEME)
    render_v3_css(current_theme) 
    
    roster = get_roster(team_id)
    player_names = ["All Players"] + sorted(list(roster.keys()))
    if st.session_state.player_pick not in player_names: st.session_state.player_pick = "All Players"
    player_name = st.selectbox("Roster", player_names, index=player_names.index(st.session_state.player_pick), label_visibility="collapsed", key="player_pick")
    player_id = roster.get(player_name, 0)
    
    if st.button("🔥 Clutch Time Mode", use_container_width=True):
        st.session_state.clutch_mode = not st.session_state.clutch_mode
        st.rerun()
    if st.session_state.clutch_mode:
        st.markdown(f"<div style='text-align:center; font-family:JetBrains Mono; font-size:10px; color:#FF4B4B; margin-top:-10px; margin-bottom:10px;'>[ACTIVE: Q4/OT]</div>", unsafe_allow_html=True)

    st.markdown("<div class='stat-label' style='margin-top:20px; margin-bottom:5px;'>The Bag</div>", unsafe_allow_html=True)
    base_df = fetch_shots_v2(player_id, team_id, game_id=None) 
    available_actions = sorted(base_df['ACTION_TYPE'].unique().tolist()) if not base_df.empty else []
    bag_filters = st.multiselect("Shot Actions", available_actions, default=st.session_state.bag_pick, placeholder="Select moves...", key="bag_selector", label_visibility="collapsed")
    if st.session_state.bag_pick != bag_filters: st.session_state.bag_pick = bag_filters

    if not base_df.empty:
        st.markdown("<div class='stat-label' style='margin-top:20px; text-align:center;'>Playstyle DNA</div>", unsafe_allow_html=True)
        dna_fig = ChartEngine.draw_radar_dna(base_df, current_theme[0])
        st.plotly_chart(dna_fig, use_container_width=True, config={'displayModeBar': False})

is_clutch = st.session_state.clutch_mode
schedule = fetch_schedule(team_id, team_name)
selected_game_id = None
opponent_display = ""
game_label_display = ""

if not schedule.empty:
    st.markdown("<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:5px;'><span class='stat-label'>SEASON TIMELINE</span><span style='font-family:JetBrains Mono; font-size:9px; opacity:0.5;'>[GAME TAPE]</span></div>", unsafe_allow_html=True)
    slider_options = ["Full Season"] + schedule['Label'].tolist()
    if st.session_state.game_id_pick not in slider_options: st.session_state.game_id_pick = "Full Season"
    selected_label = st.select_slider("Game Tape", options=slider_options, value=st.session_state.game_id_pick, key="game_tape_slider", on_change=on_slider_change, label_visibility="collapsed")
    
    if selected_label != "Full Season":
        game_row = schedule[schedule['Label'] == selected_label].iloc[0]
        selected_game_id = str(game_row['GAME_ID']).zfill(10)
        matchup = game_row['MATCHUP']
        opp_code = matchup.split(' ')[-1]
        wl = game_row['WL']; pts = game_row['PTS']
        game_label_display = f"{selected_label} • {wl} ({pts} pts)"
        teams_list = teams.get_teams()
        opp_team = next((t for t in teams_list if t['abbreviation'] == opp_code), None)
        if opp_team:
            opp_id = opp_team['id']
            opponent_display = f"https://cdn.nba.com/logos/nba/{opp_id}/global/L/logo.svg"
            current_theme = TEAM_THEMES.get(opp_team['full_name'], DEFAULT_THEME)
            render_v3_css(current_theme)

df_base_context = fetch_shots_v2(player_id, team_id, game_id=selected_game_id)
if not df_base_context.empty:
    if selected_game_id and opponent_display:
        main_img_url = opponent_display
        main_text = f"vs {matchup.split(' ')[-1]}"
        sub_text = game_label_display
    else:
        main_img_url = f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png" if player_id != 0 else f"https://cdn.nba.com/logos/nba/{team_id}/global/L/logo.svg"
        main_text = player_name if player_id != 0 else team_name
        sub_text = "2025-26 Season Overview"
        
    badges = BadgeEngine.generate_badges(df_base_context, is_team=(player_id == 0))
    badge_html = "".join([f"<div class='scout-badge' style='background-color:{b['color']}; color:{b['text']}'>{b['icon']} {b['name']}</div>" for b in badges])

    st.markdown(f"""
    <div class="glass-panel" style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px;">
        <div style="display:flex; align-items:center; gap: 24px;">
            <div style="position:relative;">
                <img src="{main_img_url}" style="width: 100px; height: 100px; border-radius: 50%; border: 3px solid {current_theme[0]}; object-fit: contain; background: rgba(0,0,0,0.3); padding: 5px; box-shadow: 0 0 30px {current_theme[0]}44;">
            </div>
            <div>
                <div class="hero-text-main">{main_text}</div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 14px; color: rgba(255,255,255,0.6); margin-top: 4px;">{sub_text}</div>
                <div style="display: flex; gap: 8px; margin-top: 12px;">{badge_html}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

@st.fragment
def render_stage(df_in, theme, pid, tid, gameid):
    c1, c2 = st.columns(2)
    with c1: outcome = st.selectbox("Shot Result", ["All", "Made", "Missed"])
    with c2: s_type = st.selectbox("Zone Filter", ["All", "2PT", "3PT"])
    
    shot_type_api = {"All": "All", "2PT": "2PT Field Goal", "3PT": "3PT Field Goal"}[s_type]
    df = filter_shots_v2(df_in, st.session_state.clutch_mode, shot_type_api, outcome, st.session_state.bag_pick)
    
    col_chart, col_details = st.columns([2.5, 1])
    
    with col_chart:
        if df.empty:
            st.warning("No shots found for these filters.")
        else:
            fig = go.Figure()
            ChartEngine.draw_court(fig, team_theme=theme, team_id=tid)
            
            miss = df[df['SHOT_MADE_FLAG'] == 0]
            made_shots = df[df['SHOT_MADE_FLAG'] == 1]
            
            # TURBO MODE: go.Scattergl (WebGL)
            # Make sure hoverinfo is enabled for GL traces
            fig.add_trace(go.Scattergl(
                x=miss['LOC_X'], y=miss['LOC_Y'], mode='markers', name='Miss',
                customdata=np.stack((miss['PLAYER_NAME'], miss['SHOT_DISTANCE'], miss['ACTION_TYPE'], miss['id']), axis=-1),
                hovertemplate="<b>%{customdata[0]}</b><br>Miss | %{customdata[1]} ft<br>%{customdata[2]}<extra></extra>",
                marker=dict(symbol='x', size=8, color='rgba(255,255,255,0.4)', line=dict(width=1))
            )) 
            fig.add_trace(go.Scattergl(
                x=made_shots['LOC_X'], y=made_shots['LOC_Y'], mode='markers', name='Make',
                customdata=np.stack((made_shots['PLAYER_NAME'], made_shots['SHOT_DISTANCE'], made_shots['ACTION_TYPE'], made_shots['id']), axis=-1),
                hovertemplate="<b>%{customdata[0]}</b><br>Make | %{customdata[1]} ft<br>%{customdata[2]}<extra></extra>",
                marker=dict(symbol='circle', size=10, color=theme[0], line=dict(color='white', width=1.5), opacity=0.7)
            )) 
            
            fig.update_layout(height=650, autosize=True, xaxis=dict(visible=False, range=[-250, 250], fixedrange=True), yaxis=dict(visible=False, range=[-52.5, 417.5], scaleanchor="x", scaleratio=1, fixedrange=True), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=0, r=0, t=0, b=0), showlegend=False, hovermode='closest', clickmode='event+select', dragmode='pan')
            
            event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", selection_mode="points", key="shot_chart", config={'displayModeBar': False})
            
            if event and "selection" in event and event.selection and "points" in event.selection:
                 if len(event.selection["points"]) > 0:
                     point_data = event.selection["points"][0]
                     trace_idx = point_data["curve_number"]
                     point_idx = point_data["point_index"]
                     try:
                         target_df = made_shots if trace_idx == 1 else miss
                         if not target_df.empty:
                             shot_data = target_df.iloc[point_idx]
                             st.session_state.selected_shot = {"id": shot_data['id'], "action": shot_data['ACTION_TYPE'], "player": shot_data['PLAYER_NAME'], "distance": shot_data['SHOT_DISTANCE'], "period": shot_data['PERIOD'], "url": shot_data['VIDEO_URL']}
                     except: pass

    with col_details:
        insights = InsightsEngine.generate_insights(df, is_team=(pid == 0))
        insights_html = "".join([f"<div style='margin-bottom:8px;'>{i}</div>" for i in insights])
        st.markdown(f"<div class='glass-panel'><div class='stat-label'>Scouting Report</div><div style='font-family:Inter; font-size:13px; color:rgba(255,255,255,0.8); line-height:1.6;'>{insights_html}</div></div>", unsafe_allow_html=True)

        if st.session_state.selected_shot:
            s = st.session_state.selected_shot
            st.markdown(f"""
            <div class="glass-panel" style="text-align: center; border-color: {theme[0]};">
                <div class='stat-label' style='margin-bottom:10px;'>REPLAY CENTER</div>
                <div style="font-family:'Oswald'; font-size: 22px; color: white;">{s['action']}</div>
                <div style="font-family:'JetBrains Mono'; font-size: 14px; color: rgba(255,255,255,0.7); margin-bottom: 20px;">{s['distance']} FT • Q{s['period']}</div>
            </div>
            """, unsafe_allow_html=True)
            st.link_button("▶ WATCH FILM", s['url'], type="primary", use_container_width=True)
        else:
             st.markdown(f"""
            <div class="glass-panel" style="height: 180px; display: flex; align-items: center; justify-content: center; color: rgba(255,255,255,0.3); border: 1px dashed rgba(255,255,255,0.1);">
                <div style='text-align:center;'>
                    <div style='font-size:20px;'>👆</div>
                    <div style='font-family:JetBrains Mono; font-size:10px; margin-top:10px;'>[SELECT SHOT]</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

render_stage(df_base_context, current_theme, player_id, team_id, selected_game_id)