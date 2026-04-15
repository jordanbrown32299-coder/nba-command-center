import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from nba_api.stats.static import teams
from nba_api.stats.endpoints import shotchartdetail, commonteamroster, leaguegamefinder

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
            team_id_nullable=team_id, season_nullable='2025-26'
        ).get_data_frames()[0]
        games['GAME_DATE'] = pd.to_datetime(games['GAME_DATE'])
        games = games[games['GAME_DATE'] >= '2025-10-21'].sort_values('GAME_DATE').reset_index(drop=True)
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
        else:
            params['season_nullable'] = '2025-26'
        df = shotchartdetail.ShotChartDetail(**params).get_data_frames()[0]
        if df.empty: return pd.DataFrame()
        base_url = "https://www.nba.com/stats/events/?flag=1&sct=plot&Season=2025-26"
        df['VIDEO_URL'] = base_url + "&GameID=" + df['GAME_ID'].astype(str) + "&GameEventID=" + df['GAME_EVENT_ID'].astype(str)
        df['id'] = df.index.astype(str)
        # Pre-compute shot zone once at fetch time
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
    if outcome == "Made": mask &= df['SHOT_MADE_FLAG'] == 1
    elif outcome == "Missed": mask &= df['SHOT_MADE_FLAG'] == 0
    if bag_filters: mask &= df['ACTION_TYPE'].isin(bag_filters)
    return df[mask]

# ==========================================
# 4. ANALYTICS ENGINE
# ==========================================
def get_shot_zone(x, y):
    dist = np.sqrt(x**2 + y**2)
    if abs(x) > 220 and y <= 90: return 'Corner 3'
    if dist <= 40: return 'Restricted Area'
    if dist > 237.5: return 'Above the Break 3'
    if abs(x) < 80 and y < 190: return 'In The Paint'
    return 'Mid-Range'

def compute_zone_stats(df):
    """Returns zone-level FG% and volume for the shot zone grid."""
    zones = ['Restricted Area', 'In The Paint', 'Mid-Range', 'Corner 3', 'Above the Break 3']
    stats = {}
    total = max(len(df), 1)
    for z in zones:
        zdf = df[df['Zone'] == z]
        n = len(zdf)
        pct = zdf['SHOT_MADE_FLAG'].mean() if n > 0 else 0
        stats[z] = {'n': n, 'pct': pct, 'freq': n / total}
    return stats

def generate_badges(df, is_team=False):
    if df.empty: return []
    badges = []
    total = len(df)
    fg_pct = df['SHOT_MADE_FLAG'].mean()
    threes = df[df['Zone'].str.contains('3', na=False)]
    paint = df[df['Zone'].isin(['Restricted Area', 'In The Paint'])]

    if is_team:
        if total > 0 and (len(threes) / total) >= 0.40:
            badges.append({'icon': '☔', 'name': 'Rainmakers', 'bg': 'rgba(94,92,230,0.18)', 'color': '#BF5AF2'})
        if total > 0 and (len(paint) / total) >= 0.45:
            badges.append({'icon': '🏰', 'name': 'Paint Beasts', 'bg': 'rgba(255,59,48,0.18)', 'color': '#FF3B30'})
        if fg_pct >= 0.48:
            badges.append({'icon': '🔥', 'name': 'High Octane', 'bg': 'rgba(255,149,0,0.18)', 'color': '#FF9500'})
        clutch = df[df['PERIOD'] >= 4]
        if not clutch.empty and clutch['SHOT_MADE_FLAG'].mean() >= 0.45:
            badges.append({'icon': '⏱️', 'name': 'Clutch City', 'bg': 'rgba(52,199,89,0.18)', 'color': '#30D158'})
    else:
        if len(threes) >= 4 and threes['SHOT_MADE_FLAG'].mean() >= 0.40:
            badges.append({'icon': '🎯', 'name': 'Sniper', 'bg': 'rgba(48,209,88,0.18)', 'color': '#30D158'})
        ra = df[df['Zone'] == 'Restricted Area']
        if len(ra) >= 4 and ra['SHOT_MADE_FLAG'].mean() >= 0.65:
            badges.append({'icon': '🔨', 'name': 'Finisher', 'bg': 'rgba(10,132,255,0.18)', 'color': '#0A84FF'})
        mr = df[df['Zone'] == 'Mid-Range']
        if len(mr) >= 3 and mr['SHOT_MADE_FLAG'].mean() >= 0.50:
            badges.append({'icon': '🧙', 'name': 'Mid-Range', 'bg': 'rgba(191,90,242,0.18)', 'color': '#BF5AF2'})
        if total >= 15:
            badges.append({'icon': '🚀', 'name': 'Volume', 'bg': 'rgba(255,159,10,0.18)', 'color': '#FF9F0A'})
        if total >= 8 and fg_pct <= 0.35:
            badges.append({'icon': '🧊', 'name': 'Cold', 'bg': 'rgba(100,210,255,0.18)', 'color': '#64D2FF'})
    return badges

def generate_insights(df, is_team=False):
    if df.empty or len(df) < 5:
        return [("ℹ️", "Gathering Data", "Select more games or adjust filters to see patterns.")]
    insights = []
    total = len(df)
    threes_freq = len(df[df['Zone'].str.contains('3', na=False)]) / total

    if is_team:
        if threes_freq > 0.45:
            insights.append(("🏹", "Modern Offense", f"3-ball heavy — {threes_freq:.0%} of all attempts from deep."))
        else:
            insights.append(("⚖️", "Balanced Attack", "Good distribution across all 3 scoring levels."))
    else:
        zone_counts = df['Zone'].value_counts(normalize=True)
        if not zone_counts.empty:
            fav = zone_counts.idxmax()
            insights.append(("📍", "Zone Heavy", f"{zone_counts.max():.0%} of shots in the {fav}."))
        threes = df[df['Zone'].str.contains('3', na=False)]
        if len(threes) >= 5:
            pct = threes['SHOT_MADE_FLAG'].mean()
            if pct > 0.40:
                insights.append(("🔥", "Sniper Alert", f"Shooting {pct:.1%} from deep — elite efficiency."))
        made = df['SHOT_MADE_FLAG'].sum()
        tpm = df[df['Zone'].str.contains('3', na=False)]['SHOT_MADE_FLAG'].sum()
        pps = ((made * 2) + tpm) / total
        if pps > 1.25:
            insights.append(("📈", "High Value", f"Generating {pps:.2f} points per shot attempt."))
    if not insights:
        insights.append(("⚖️", "Standard", "Performance aligns with league norms."))
    return insights[:3]

# ==========================================
# 5. CHART ENGINE
# ==========================================
def hex_to_rgba(hex_code, alpha=1.0):
    h = hex_code.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

def get_arc(cx, cy, r, start, end, steps=50):
    t = np.linspace(np.radians(start), np.radians(end), steps)
    path = f"M {cx + r*np.cos(t[0]):.2f} {cy + r*np.sin(t[0]):.2f}"
    for i in range(1, len(t)):
        path += f" L {cx + r*np.cos(t[i]):.2f} {cy + r*np.sin(t[i]):.2f}"
    return path

def draw_court(fig, team_theme=DEFAULT_THEME, team_id=None):
    primary, _ = team_theme
    glow = hex_to_rgba(primary, 0.55)
    core = "rgba(255,255,255,0.85)"
    paint_fill = hex_to_rgba(primary, 0.08)

    shapes = [
        dict(type="rect", x0=-250, y0=-52.5, x1=250, y1=417.5,
             line=dict(width=0), fillcolor="rgba(0,0,0,0)", layer="below"),
        dict(type="rect", x0=-80, y0=-52.5, x1=80, y1=137.5,
             line=dict(width=0), fillcolor=paint_fill, layer="below"),
    ]

    def neon(shape_type, **kwargs):
        shapes.append(dict(type=shape_type, layer="below",
                           line=dict(color=glow, width=3.5), **kwargs))
        shapes.append(dict(type=shape_type, layer="below",
                           line=dict(color=core, width=0.8), **kwargs))

    neon("rect", x0=-250, y0=-52.5, x1=250, y1=417.5)
    neon("rect", x0=-80, y0=-52.5, x1=80, y1=137.5)
    neon("line", x0=-30, y0=-12.5, x1=30, y1=-12.5)
    neon("path", path=get_arc(0, 0, 40, 0, 180))
    neon("path", path=get_arc(0, 137.5, 60, 0, 180))
    shapes.append(dict(type="path", path=get_arc(0, 137.5, 60, 180, 360),
                       line=dict(color=glow, width=1.5, dash='dot'), layer="below"))
    neon("line", x0=-220, y0=-52.5, x1=-220, y1=89.47)
    neon("line", x0=220, y0=-52.5, x1=220, y1=89.47)
    neon("path", path=get_arc(0, 0, 237.5, 22, 158))
    neon("path", path=get_arc(0, 417.5, 60, 180, 360))
    neon("path", path=get_arc(0, 417.5, 20, 180, 360))
    shapes.append(dict(type="circle", x0=-7.5, y0=-7.5, x1=7.5, y1=7.5,
                       xref="x", yref="y", line=dict(color="#FF9F0A", width=2), layer="below"))

    fig.update_layout(shapes=shapes)
    if team_id:
        fig.add_layout_image(dict(
            source=f"https://cdn.nba.com/logos/nba/{team_id}/global/L/logo.svg",
            xref="x", yref="y", x=0, y=210, sizex=140, sizey=140,
            xanchor="center", yanchor="middle", opacity=0.12, layer="below"
        ))

def draw_radar(df, color):
    if df.empty: return go.Figure()
    total = len(df)
    paint = len(df[df['Zone'].isin(['Restricted Area', 'In The Paint'])]) / total
    mid = len(df[df['Zone'] == 'Mid-Range']) / total
    three = len(df[df['Zone'].str.contains('3', na=False)]) / total
    eff = df['SHOT_MADE_FLAG'].mean()
    corner = len(df[df['Zone'] == 'Corner 3']) / total
    values = [
        min(paint / 0.6, 1.0), min(three / 0.6, 1.0),
        min(mid / 0.4, 1.0), min(eff / 0.6, 1.0), min(corner / 0.2, 1.0)
    ]
    cats = ['Paint', 'Deep Range', 'Mid', 'Efficiency', 'Corner']
    rgba = hex_to_rgba(color, 0.25)
    fig = go.Figure(go.Scatterpolar(
        r=values, theta=cats, fill='toself',
        line=dict(color=color, width=2),
        fillcolor=rgba
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=False, range=[0, 1]),
            bgcolor='rgba(0,0,0,0)',
            angularaxis=dict(
                tickfont=dict(size=9, color='rgba(255,255,255,0.5)'),
                linecolor='rgba(255,255,255,0.08)'
            )
        ),
        showlegend=False,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor='rgba(0,0,0,0)',
        height=180
    )
    return fig

# ==========================================
# 6. CSS / THEME SYSTEM
# ==========================================
def inject_css(primary, secondary):
    p_glow = hex_to_rgba(primary, 0.35)
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;700;800&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap');

        :root {{
            --primary: {primary};
            --primary-glow: {p_glow};
            --secondary: {secondary};
            --bg: #080808;
            --surface: rgba(18,18,18,0.85);
            --border: rgba(255,255,255,0.07);
            --text-dim: rgba(255,255,255,0.45);
            --text-mid: rgba(255,255,255,0.7);
        }}

        /* Base */
        .stApp {{
            background-color: var(--bg);
            background-image:
                radial-gradient(ellipse 80% 50% at 50% -10%, {hex_to_rgba(primary, 0.12)} 0%, transparent 70%),
                linear-gradient(180deg, #0a0a0a 0%, #050505 100%);
            font-family: 'DM Sans', sans-serif;
            color: #fff;
        }}

        /* Sidebar */
        section[data-testid="stSidebar"] {{
            background: rgba(6,6,6,0.95) !important;
            border-right: 1px solid var(--border);
        }}
        section[data-testid="stSidebar"] > div {{
            padding-top: 1.5rem;
        }}

        /* Typography */
        h1, h2, h3 {{ font-family: 'Barlow Condensed', sans-serif !important; text-transform: uppercase; }}

        /* Panels */
        .panel {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 16px;
            backdrop-filter: blur(12px);
        }}
        .panel-accent {{
            border-color: {hex_to_rgba(primary, 0.4)};
            box-shadow: 0 0 24px {hex_to_rgba(primary, 0.1)};
        }}

        /* Stat cells */
        .stat-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }}
        .stat-cell {{
            background: rgba(255,255,255,0.03);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 14px 12px;
            text-align: center;
        }}
        .stat-cell-val {{
            font-family: 'DM Mono', monospace;
            font-size: 26px;
            font-weight: 500;
            color: {primary};
            line-height: 1;
            text-shadow: 0 0 16px {p_glow};
        }}
        .stat-cell-label {{
            font-family: 'DM Mono', monospace;
            font-size: 9px;
            letter-spacing: 1.5px;
            color: var(--text-dim);
            text-transform: uppercase;
            margin-top: 4px;
        }}

        /* Zone grid */
        .zone-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
        .zone-row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: rgba(255,255,255,0.03);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 8px 12px;
            font-family: 'DM Mono', monospace;
            font-size: 10px;
        }}
        .zone-name {{ color: var(--text-mid); font-size: 9px; letter-spacing: 0.5px; }}
        .zone-pct {{ color: {primary}; font-weight: 500; }}
        .zone-bar-wrap {{
            width: 100%; height: 2px;
            background: rgba(255,255,255,0.08);
            border-radius: 2px; margin-top: 4px;
        }}
        .zone-bar {{ height: 100%; background: {primary}; border-radius: 2px; }}

        /* Badge */
        .badge {{
            display: inline-flex; align-items: center; gap: 5px;
            padding: 3px 9px; border-radius: 4px;
            font-family: 'DM Mono', monospace;
            font-size: 9px; font-weight: 500;
            letter-spacing: 0.8px; text-transform: uppercase;
            border: 1px solid rgba(255,255,255,0.08);
        }}

        /* Insight cards */
        .insight-card {{
            display: flex; align-items: flex-start; gap: 12px;
            background: rgba(255,255,255,0.02);
            border: 1px solid var(--border);
            border-left: 3px solid {primary};
            border-radius: 0 8px 8px 0;
            padding: 12px 14px;
            margin-bottom: 8px;
        }}
        .insight-icon {{ font-size: 18px; line-height: 1; }}
        .insight-title {{
            font-family: 'Barlow Condensed', sans-serif;
            font-size: 13px; font-weight: 700;
            text-transform: uppercase;
            color: white; letter-spacing: 0.5px;
        }}
        .insight-body {{
            font-size: 11px; color: var(--text-mid);
            margin-top: 2px; line-height: 1.4;
        }}

        /* Hero */
        .hero-name {{
            font-family: 'Barlow Condensed', sans-serif;
            font-size: 44px; font-weight: 800;
            text-transform: uppercase;
            line-height: 1; color: white;
            letter-spacing: 1px;
        }}
        .hero-sub {{
            font-family: 'DM Mono', monospace;
            font-size: 11px; color: var(--text-dim);
            letter-spacing: 1px; margin-top: 4px;
            text-transform: uppercase;
        }}

        /* Sidebar labels */
        .sidebar-label {{
            font-family: 'DM Mono', monospace;
            font-size: 9px; letter-spacing: 2px;
            color: var(--text-dim); text-transform: uppercase;
            margin: 16px 0 6px;
            padding-bottom: 6px;
            border-bottom: 1px solid var(--border);
        }}

        /* Clutch pill */
        .clutch-pill {{
            text-align: center;
            font-family: 'DM Mono', monospace;
            font-size: 9px; color: #FF453A;
            background: rgba(255,69,58,0.12);
            border: 1px solid rgba(255,69,58,0.3);
            border-radius: 4px;
            padding: 4px 10px;
            letter-spacing: 1.5px;
            text-transform: uppercase;
            margin-top: -8px; margin-bottom: 10px;
        }}

        /* Streamlit overrides */
        div[data-baseweb="select"] > div,
        .stTextInput > div > div {{
            background: rgba(15,15,15,0.6) !important;
            border-color: var(--border) !important;
            color: white !important;
            font-family: 'DM Mono', monospace;
            font-size: 12px;
            border-radius: 6px !important;
        }}
        .stSlider > div > div > div > div {{ background: {primary} !important; }}
        .stButton > button {{
            background: rgba(255,255,255,0.04);
            border: 1px solid var(--border);
            color: white;
            font-family: 'DM Mono', monospace;
            font-size: 11px;
            letter-spacing: 1px;
            border-radius: 6px;
            transition: all 0.2s;
        }}
        .stButton > button:hover {{
            background: {hex_to_rgba(primary, 0.15)};
            border-color: {hex_to_rgba(primary, 0.5)};
            color: white;
        }}
        .stLinkButton > a {{
            background: {primary} !important;
            color: #000 !important;
            font-family: 'DM Mono', monospace;
            font-size: 11px;
            letter-spacing: 1px;
            border-radius: 6px;
            font-weight: 700;
        }}
        /* Section dividers */
        .section-divider {{
            display: flex; align-items: center; gap: 10px;
            margin: 20px 0 12px;
        }}
        .section-divider-line {{
            flex: 1; height: 1px; background: var(--border);
        }}
        .section-divider-label {{
            font-family: 'DM Mono', monospace;
            font-size: 9px; letter-spacing: 2px;
            color: var(--text-dim); text-transform: uppercase;
            white-space: nowrap;
        }}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 7. HELPER RENDERERS
# ==========================================
def render_stat_grid(df):
    if df.empty: return
    total = len(df)
    made = int(df['SHOT_MADE_FLAG'].sum())
    pct = made / total if total else 0
    threes = df[df['Zone'].str.contains('3', na=False)]
    three_pct = threes['SHOT_MADE_FLAG'].mean() if len(threes) > 0 else 0
    pps = ((made * 2) + threes['SHOT_MADE_FLAG'].sum()) / total if total else 0
    st.markdown(f"""
    <div class="stat-grid">
        <div class="stat-cell">
            <div class="stat-cell-val">{total}</div>
            <div class="stat-cell-label">FGA</div>
        </div>
        <div class="stat-cell">
            <div class="stat-cell-val">{pct:.1%}</div>
            <div class="stat-cell-label">FG%</div>
        </div>
        <div class="stat-cell">
            <div class="stat-cell-val">{three_pct:.1%}</div>
            <div class="stat-cell-label">3P%</div>
        </div>
        <div class="stat-cell" style="grid-column: span 1;">
            <div class="stat-cell-val">{made}</div>
            <div class="stat-cell-label">FGM</div>
        </div>
        <div class="stat-cell" style="grid-column: span 2;">
            <div class="stat-cell-val">{pps:.2f}</div>
            <div class="stat-cell-label">Pts / Shot</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_zone_grid(df, primary):
    if df.empty: return
    stats = compute_zone_stats(df)
    zone_labels = {
        'Restricted Area': 'Rim / RA',
        'In The Paint': 'Paint',
        'Mid-Range': 'Mid-Range',
        'Corner 3': 'Corner 3',
        'Above the Break 3': 'ATB 3'
    }
    rows_html = ""
    for zone, label in zone_labels.items():
        s = stats.get(zone, {'n': 0, 'pct': 0, 'freq': 0})
        pct_str = f"{s['pct']:.0%}" if s['n'] > 0 else "—"
        bar_w = int(s['freq'] * 100)
        rows_html += f"""
        <div style="margin-bottom:8px;">
            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                <span class="zone-name">{label}</span>
                <span style="font-family:'DM Mono',monospace; font-size:10px; color:var(--text-mid);">
                    <span class="zone-pct">{pct_str}</span>
                    <span style="color:var(--text-dim); margin-left:6px;">{s['n']} att</span>
                </span>
            </div>
            <div class="zone-bar-wrap">
                <div class="zone-bar" style="width:{bar_w}%;"></div>
            </div>
        </div>
        """
    st.markdown(f"""
    <div class="panel" style="margin-top:0;">
        <div class="sidebar-label" style="margin-top:0;">Zone Breakdown</div>
        {rows_html}
    </div>
    """, unsafe_allow_html=True)

def render_insights(df, is_team, primary):
    insights = generate_insights(df, is_team)
    cards = ""
    for icon, title, body in insights:
        cards += f"""
        <div class="insight-card">
            <div class="insight-icon">{icon}</div>
            <div>
                <div class="insight-title">{title}</div>
                <div class="insight-body">{body}</div>
            </div>
        </div>
        """
    st.markdown(f"""
    <div class="panel">
        <div class="sidebar-label" style="margin-top:0;">Scouting Report</div>
        {cards}
    </div>
    """, unsafe_allow_html=True)

def render_replay_panel(selected_shot, primary):
    if not selected_shot:
        st.markdown("""
        <div class="panel" style="height:160px; display:flex; align-items:center; justify-content:center;
            border-style:dashed; border-color:rgba(255,255,255,0.1);">
            <div style="text-align:center; color:rgba(255,255,255,0.25);">
                <div style="font-size:22px; margin-bottom:8px;">↑</div>
                <div style="font-family:'DM Mono',monospace; font-size:9px; letter-spacing:2px;">
                    CLICK A SHOT
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        return
    s = selected_shot
    st.markdown(f"""
    <div class="panel panel-accent">
        <div style="font-family:'DM Mono',monospace; font-size:9px; letter-spacing:2px;
            color:var(--text-dim); text-transform:uppercase; margin-bottom:10px;">Replay Center</div>
        <div style="font-family:'Barlow Condensed',sans-serif; font-size:22px;
            font-weight:700; text-transform:uppercase; color:white;">{s['action']}</div>
        <div style="font-family:'DM Mono',monospace; font-size:11px;
            color:var(--text-mid); margin-top:4px; margin-bottom:16px;">
            {s['distance']} FT &nbsp;·&nbsp; Q{s['period']}
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.link_button("▶ WATCH FILM", s['url'], use_container_width=True)

# ==========================================
# 8. SIDEBAR
# ==========================================
teams_map = get_teams_map()

with st.sidebar:
    st.markdown("""
    <div style="font-family:'Barlow Condensed',sans-serif; font-size:22px;
        font-weight:800; text-transform:uppercase; color:white; letter-spacing:1px;
        margin-bottom:16px;">
        NBA Shot Lab
        <span style="font-family:'DM Mono',monospace; font-size:10px;
            color:rgba(255,255,255,0.3); vertical-align:middle; margin-left:6px;">v5</span>
    </div>
    """, unsafe_allow_html=True)

    st.text_input(
        "Command", placeholder="e.g. Tatum vs Lakers, show dunks...",
        key="command_input", on_change=process_command, label_visibility="collapsed"
    )

    st.markdown("<div class='sidebar-label'>Team</div>", unsafe_allow_html=True)
    team_name = st.selectbox(
        "Team", sorted(teams_map.keys()),
        index=sorted(teams_map.keys()).index(st.session_state.team_pick),
        label_visibility="collapsed", key="team_pick", on_change=on_team_change
    )
    team_id = teams_map[team_name]
    current_theme = TEAM_THEMES.get(team_name, DEFAULT_THEME)

    # Inject CSS once with current theme
    inject_css(current_theme[0], current_theme[1])

    st.markdown("<div class='sidebar-label'>Player</div>", unsafe_allow_html=True)
    roster = get_roster(team_id)
    player_names = ["All Players"] + sorted(list(roster.keys()))
    if st.session_state.player_pick not in player_names:
        st.session_state.player_pick = "All Players"
    player_name = st.selectbox(
        "Player", player_names,
        index=player_names.index(st.session_state.player_pick),
        label_visibility="collapsed", key="player_pick"
    )
    player_id = roster.get(player_name, 0)

    # Clutch toggle
    st.markdown("<div class='sidebar-label'>Mode</div>", unsafe_allow_html=True)
    if st.button("⏱ Clutch Time" + (" [ON]" if st.session_state.clutch_mode else ""), use_container_width=True):
        st.session_state.clutch_mode = not st.session_state.clutch_mode
        st.rerun()
    if st.session_state.clutch_mode:
        st.markdown("<div class='clutch-pill'>Active · Q4 / OT Only</div>", unsafe_allow_html=True)

    # Fetch base data once
    base_df = fetch_shots(player_id, team_id, game_id=None)

    # The Bag
    st.markdown("<div class='sidebar-label'>The Bag</div>", unsafe_allow_html=True)
    available_actions = sorted(base_df['ACTION_TYPE'].unique().tolist()) if not base_df.empty else []
    bag_filters = st.multiselect(
        "Shot Actions", available_actions,
        default=[a for a in st.session_state.bag_pick if a in available_actions],
        placeholder="All shot types...", key="bag_selector", label_visibility="collapsed"
    )
    st.session_state.bag_pick = bag_filters

    # Radar DNA
    if not base_df.empty:
        st.markdown("""
        <div class="section-divider">
            <div class="section-divider-line"></div>
            <div class="section-divider-label">Playstyle DNA</div>
            <div class="section-divider-line"></div>
        </div>
        """, unsafe_allow_html=True)
        dna_fig = draw_radar(base_df, current_theme[0])
        st.plotly_chart(dna_fig, use_container_width=True, config={'displayModeBar': False})

# ==========================================
# 9. MAIN AREA
# ==========================================
is_clutch = st.session_state.clutch_mode
schedule = fetch_schedule(team_id, team_name)
selected_game_id = None
opponent_display = ""
game_label_display = ""
display_theme = current_theme

if not schedule.empty:
    st.markdown("""
    <div class="section-divider" style="margin-top:0; margin-bottom:8px;">
        <div class="section-divider-line"></div>
        <div class="section-divider-label">Season Timeline</div>
        <div class="section-divider-line"></div>
    </div>
    """, unsafe_allow_html=True)
    slider_options = ["Full Season"] + schedule['Label'].tolist()
    if st.session_state.game_id_pick not in slider_options:
        st.session_state.game_id_pick = "Full Season"
    selected_label = st.select_slider(
        "Game Tape", options=slider_options,
        value=st.session_state.game_id_pick,
        key="game_tape_slider", on_change=on_slider_change,
        label_visibility="collapsed"
    )
    if selected_label != "Full Season":
        game_row = schedule[schedule['Label'] == selected_label].iloc[0]
        selected_game_id = str(game_row['GAME_ID']).zfill(10)
        matchup = game_row['MATCHUP']
        opp_code = matchup.split(' ')[-1]
        wl = game_row['WL']
        pts = game_row['PTS']
        game_label_display = f"{selected_label} · {wl} ({pts} pts)"
        opp_team = next((t for t in teams.get_teams() if t['abbreviation'] == opp_code), None)
        if opp_team:
            opp_id = opp_team['id']
            opponent_display = f"https://cdn.nba.com/logos/nba/{opp_id}/global/L/logo.svg"
            display_theme = TEAM_THEMES.get(opp_team['full_name'], DEFAULT_THEME)

# Fetch main data
df_main = fetch_shots(player_id, team_id, game_id=selected_game_id)

# ---- HERO HEADER ----
if not df_main.empty:
    if selected_game_id and opponent_display:
        img_url = opponent_display
        hero_name = matchup.split(' ')[-1]
        hero_sub = game_label_display
    else:
        img_url = (
            f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"
            if player_id else
            f"https://cdn.nba.com/logos/nba/{team_id}/global/L/logo.svg"
        )
        hero_name = player_name if player_id else team_name
        hero_sub = "2025–26 Season"

    badges = generate_badges(df_main, is_team=(player_id == 0))
    badge_html = "".join([
        f"<span class='badge' style='background:{b['bg']}; color:{b['color']};'>{b['icon']} {b['name']}</span>"
        for b in badges
    ])

    st.markdown(f"""
    <div class="panel" style="display:flex; align-items:center; gap:24px; margin-bottom:16px;">
        <img src="{img_url}" style="
            width:88px; height:88px; border-radius:50%;
            border:2px solid {display_theme[0]};
            object-fit:contain; background:rgba(0,0,0,0.3); padding:5px;
            box-shadow: 0 0 28px {hex_to_rgba(display_theme[0], 0.3)};
            flex-shrink:0;
        ">
        <div style="min-width:0;">
            <div class="hero-name">{hero_name}</div>
            <div class="hero-sub">{hero_sub}</div>
            <div style="display:flex; flex-wrap:wrap; gap:6px; margin-top:10px;">{badge_html}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ---- STAGE ----
@st.fragment
def render_stage(df_in, theme, pid, tid):
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        outcome = st.selectbox("Result", ["All", "Made", "Missed"], label_visibility="collapsed")
    with col_f2:
        s_type = st.selectbox("Shot Type", ["All", "2PT", "3PT"], label_visibility="collapsed")

    shot_type_api = {"All": "All", "2PT": "2PT Field Goal", "3PT": "3PT Field Goal"}[s_type]
    df = filter_shots(df_in, st.session_state.clutch_mode, shot_type_api, outcome, st.session_state.bag_pick)

    col_chart, col_panel = st.columns([2.5, 1])

    with col_chart:
        if df.empty:
            st.warning("No shots match the current filters.")
        else:
            fig = go.Figure()
            draw_court(fig, team_theme=theme, team_id=tid)

            miss = df[df['SHOT_MADE_FLAG'] == 0]
            made = df[df['SHOT_MADE_FLAG'] == 1]

            fig.add_trace(go.Scattergl(
                x=miss['LOC_X'], y=miss['LOC_Y'],
                mode='markers', name='Miss',
                customdata=np.stack((
                    miss['PLAYER_NAME'], miss['SHOT_DISTANCE'],
                    miss['ACTION_TYPE'], miss['id']
                ), axis=-1),
                hovertemplate="<b>%{customdata[0]}</b><br>Miss · %{customdata[1]} ft<br>%{customdata[2]}<extra></extra>",
                marker=dict(symbol='x', size=7, color='rgba(255,255,255,0.35)', line=dict(width=1.2))
            ))
            fig.add_trace(go.Scattergl(
                x=made['LOC_X'], y=made['LOC_Y'],
                mode='markers', name='Make',
                customdata=np.stack((
                    made['PLAYER_NAME'], made['SHOT_DISTANCE'],
                    made['ACTION_TYPE'], made['id']
                ), axis=-1),
                hovertemplate="<b>%{customdata[0]}</b><br>Make · %{customdata[1]} ft<br>%{customdata[2]}<extra></extra>",
                marker=dict(
                    symbol='circle', size=9,
                    color=theme[0],
                    line=dict(color='white', width=1.2),
                    opacity=0.8
                )
            ))

            fig.update_layout(
                height=620,
                autosize=True,
                xaxis=dict(visible=False, range=[-250, 250], fixedrange=True),
                yaxis=dict(visible=False, range=[-52.5, 417.5], scaleanchor="x", scaleratio=1, fixedrange=True),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=0, r=0, t=0, b=0),
                showlegend=False,
                hovermode='closest',
                clickmode='event+select',
                dragmode='pan'
            )

            event = st.plotly_chart(
                fig, use_container_width=True,
                on_select="rerun", selection_mode="points",
                key="shot_chart", config={'displayModeBar': False}
            )

            if event and event.get("selection", {}).get("points"):
                pt = event["selection"]["points"][0]
                trace_idx = pt["curve_number"]
                pt_idx = pt["point_index"]
                try:
                    target = made if trace_idx == 1 else miss
                    if not target.empty:
                        row = target.iloc[pt_idx]
                        st.session_state.selected_shot = {
                            "id": row['id'],
                            "action": row['ACTION_TYPE'],
                            "player": row['PLAYER_NAME'],
                            "distance": row['SHOT_DISTANCE'],
                            "period": row['PERIOD'],
                            "url": row['VIDEO_URL']
                        }
                except:
                    pass

    with col_panel:
        # Stats
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        render_stat_grid(df)
        st.markdown("</div>", unsafe_allow_html=True)

        # Zone breakdown
        render_zone_grid(df, theme[0])

        # Insights
        render_insights(df, is_team=(pid == 0), primary=theme[0])

        # Replay
        render_replay_panel(st.session_state.selected_shot, theme[0])

if not df_main.empty:
    render_stage(df_main, display_theme, player_id, team_id)
else:
    st.markdown("""
    <div class="panel" style="text-align:center; padding:60px 20px; border-style:dashed; border-color:rgba(255,255,255,0.08);">
        <div style="font-family:'Barlow Condensed',sans-serif; font-size:28px; text-transform:uppercase; color:rgba(255,255,255,0.2);">
            No Shot Data
        </div>
        <div style="font-family:'DM Mono',monospace; font-size:11px; color:rgba(255,255,255,0.15); margin-top:8px;">
            Select a team or player to begin
        </div>
    </div>
    """, unsafe_allow_html=True)
