# --- START OF FILE app.py ---

import streamlit as st
import pandas as pd
import requests  
from datetime import datetime, date, time 
import time as time_module 
from urllib.parse import quote_plus 
import base64 

try:
    import pdfkit
    HAS_PDFKIT = True
except ImportError:
    HAS_PDFKIT = False

from src.config import VERSION, TEAMS_DB, SEASON_ID, CSS_STYLES
from src.utils import get_logo_url 
from src.api import (
    fetch_team_data, get_player_metadata_cached, fetch_schedule, 
    fetch_game_boxscore, fetch_game_details, fetch_team_info_basic,
    fetch_season_games
)
from src.html_gen import (
    generate_header_html, generate_top3_html, generate_card_html, 
    generate_team_stats_html, generate_custom_sections_html,
    generate_comparison_html
)
from src.state_manager import export_session_state, load_session_state
from src.analysis_ui import (
    render_game_header, render_boxscore_table_pro, render_charts_and_stats, 
    get_team_name, render_game_top_performers, generate_game_summary,
    generate_complex_ai_prompt, render_full_play_by_play, run_openai_generation,
    render_prep_dashboard, render_live_view, render_season_analysis_page
)

# --- KONFIGURATION ---
CURRENT_SEASON_ID = "2025" 

st.set_page_config(page_title=f"DBBL Scouting Pro {VERSION}", layout="wide", page_icon="🏀")

# --- ZENTRALE CSS & BILD FUNKTION ---
def inject_custom_css():
    base_css = """
    <style>
    div.stButton > button {
        width: 100%;
        height: 3em;
        font-size: 16px;
        font-weight: bold;
        border-radius: 8px;
        box-shadow: 0px 2px 4px rgba(0,0,0,0.1);
        background-color: #ffffff !important; 
        color: #333333 !important;
        border: 1px solid #ddd;
        opacity: 1 !important; 
    }
    div.stButton > button:hover {
        transform: scale(1.01);
        border-color: #ff4b4b;
        color: #ff4b4b !important;
    }
    .title-container {
        background-color: #ffffff; padding: 20px; border-radius: 15px; 
        box-shadow: 0px 4px 6px rgba(0,0,0,0.1); text-align: center; 
        margin-bottom: 40px; max-width: 800px; margin-left: auto; margin-right: auto; 
        border: 1px solid #f0f0f0; opacity: 1 !important;
    }
    </style>
    """
    st.markdown(base_css, unsafe_allow_html=True)

    if st.session_state.current_page == "home":
        bg_css = """
        <style>
        [data-testid="stAppViewContainer"] {
            background-image: linear-gradient(rgba(255, 255, 255, 0.8), rgba(255, 255, 255, 0.8)), 
                              url("https://cdn.pixabay.com/photo/2022/11/22/20/25/ball-7610545_1280.jpg");
            background-size: cover; background-position: center; background-repeat: no-repeat;
            background-attachment: fixed;
        }
        [data-testid="stHeader"] { background-color: rgba(0,0,0,0); }
        </style>
        """
        st.markdown(bg_css, unsafe_allow_html=True)
    else:
        clean_css = """
        <style>
        [data-testid="stAppViewContainer"] {
            background-image: none !important;
            background-color: #ffffff !important;
        }
        [data-testid="stHeader"] { background-color: #ffffff !important; }
        </style>
        """
        st.markdown(clean_css, unsafe_allow_html=True)

# --- BILDER LADE LOGIK ---
@st.cache_data(ttl=3600, show_spinner=False)
def get_best_team_logo(team_id):
    if not team_id: return None
    candidates = [
        f"https://api-s.dbbl.scb.world/images/teams/logo/{CURRENT_SEASON_ID}/{team_id}",
        f"https://api-n.dbbl.scb.world/images/teams/logo/{CURRENT_SEASON_ID}/{team_id}",
        f"https://api-s.dbbl.scb.world/images/teams/logo/2024/{team_id}",
        f"https://api-n.dbbl.scb.world/images/teams/logo/2024/{team_id}"
    ]
    headers = { "User-Agent": "Mozilla/5.0", "Accept": "image/*", "Referer": "https://dbbl.de/" }
    for url in candidates:
        try:
            r = requests.get(url, headers=headers, timeout=1.0)
            if r.status_code == 200 and len(r.content) > 500: 
                b64 = base64.b64encode(r.content).decode()
                mime = "image/jpeg" if "jpg" in url or "jpeg" in url else "image/png"
                return f"data:{mime};base64,{b64}"
        except: continue
    return None

def image_to_base64_str(img_bytes):
    if not img_bytes: return ""
    try: return f"data:image/png;base64,{base64.b64encode(img_bytes).decode()}"
    except: return ""

# --- SESSION STATE ---
for key, default in [
    ("current_page", "home"), ("print_mode", False), ("final_html", ""), ("pdf_bytes", None),
    ("roster_df", None), ("team_stats", None), ("game_meta", {}),
    ("report_filename", "scouting_report.pdf"), ("saved_notes", {}), ("saved_colors", {}),
    ("facts_offense", pd.DataFrame([{"Fokus": "Run", "Beschreibung": "fastbreaks & quick inbounds"}])),
    ("facts_defense", pd.DataFrame([{"Fokus": "Rebound", "Beschreibung": "box out!"}])),
    ("facts_about", pd.DataFrame([{"Fokus": "Together", "Beschreibung": "Fight!"}])),
    ("selected_game_id", None), ("generated_ai_report", None), ("live_game_id", None),
    ("stats_team_id", None)
]:
    if key not in st.session_state: st.session_state[key] = default

# --- NAVIGATIONS-HELFER ---
def go_home(): st.session_state.current_page = "home"; st.session_state.print_mode = False
def go_scouting(): st.session_state.current_page = "scouting"
def go_comparison(): st.session_state.current_page = "comparison"
def go_analysis(): st.session_state.current_page = "analysis"
def go_player_comparison(): st.session_state.current_page = "player_comparison"
def go_game_venue(): st.session_state.current_page = "game_venue" 
def go_prep(): st.session_state.current_page = "prep"
def go_live(): st.session_state.current_page = "live"
def go_team_stats(): st.session_state.current_page = "team_stats"
def go_season_analysis(): st.session_state.current_page = "season_analysis"

# --- STANDARD-SEITENHEADER ---
def render_page_header(page_title):
    inject_custom_css()
    header_col1, header_col2 = st.columns([1, 4])
    with header_col1:
        st.button("🏠 Home", on_click=go_home, key=f"home_button_header_{st.session_state.current_page}")
    with header_col2:
        st.markdown("<h3 style='text-align: right; color: #666;'>DBBL Scouting Pro by Sascha Rosanke</h3>", unsafe_allow_html=True)
    st.title(page_title) 
    st.divider()

# ==========================================
# SEITE 1: HOME
# ==========================================
def render_home():
    inject_custom_css()
    st.markdown(f"""<div class="title-container"><h1 style='margin:0; color: #333;'>🏀 DBBL Scouting Suite</h1><p style='margin:0; margin-top:10px; color: #555; font-weight: bold;'>Version {VERSION} | by Sascha Rosanke</p></div>""", unsafe_allow_html=True)
    _, col_center, _ = st.columns([1, 2, 1])
    with col_center:
        r1_c1, r1_c2 = st.columns(2)
        with r1_c1: 
            if st.button("📊 Teamvergleich", use_container_width=True): go_comparison(); st.rerun()
        with r1_c2: 
            if st.button("🤼 Spielervergleich", use_container_width=True): go_player_comparison(); st.rerun()
        st.write("") 
        r2_c1, r2_c2 = st.columns(2)
        with r2_c1:
            if st.button("🔮 Spielvorbereitung", use_container_width=True): go_prep(); st.rerun()
        with r2_c2: 
            if st.button("🎥 Spielnachbereitung", use_container_width=True): go_analysis(); st.rerun()
        st.write("") 
        r3_c1, r3_c2 = st.columns(2)
        with r3_c1: 
            if st.button("📝 PreGame Report", use_container_width=True): go_scouting(); st.rerun()
        with r3_c2:
             if st.button("🔴 Live Game Center", use_container_width=True): go_live(); st.rerun()
        st.write("")
        r4_c1, r4_c2 = st.columns(2)
        with r4_c1:
             if st.button("📈 Team Stats", use_container_width=True): go_team_stats(); st.rerun()
        with r4_c2:
             if st.button("📍 Spielorte", use_container_width=True): go_game_venue(); st.rerun()
        st.write("")
        # NEUER BUTTON HIER
        if st.button("📊 Saison Analyse", use_container_width=True): go_season_analysis(); st.rerun()

def render_team_stats_page():
    if st.session_state.stats_team_id:
        tid = st.session_state.stats_team_id
        col_back, col_head = st.columns([1, 5])
        with col_back:
            if st.button("⬅️ Zur Übersicht", key="back_from_stats"):
                st.session_state.stats_team_id = None
                st.rerun()
        
        with st.spinner("Lade Team Statistiken..."):
            df, ts = fetch_team_data(tid, CURRENT_SEASON_ID)
            
        has_data = (df is not None and not df.empty) or (ts and len(ts) > 0)

        if has_data:
            t_info = TEAMS_DB.get(tid, {})
            name = t_info.get("name", "Team")
            logo_b64 = get_best_team_logo(tid)
            
            c1, c2 = st.columns([1, 4])
            with c1: 
                if logo_b64: st.image(logo_b64, width=100)
                else: st.markdown("🏀", unsafe_allow_html=True)
            with c2: 
                st.title(f"Statistik: {name}")
            
            st.divider()
            st.subheader(f"Saison Durchschnittswerte (Saison {CURRENT_SEASON_ID})")
            if ts:
                m1, m2, m3, m4, m5, m6 = st.columns(6)
                m1.metric("Punkte", f"{ts.get('ppg', 0):.1f}")
                m2.metric("Rebounds", f"{ts.get('tot', 0):.1f}")
                m3.metric("Assists", f"{ts.get('as', 0):.1f}")
                m4.metric("Steals", f"{ts.get('st', 0):.1f}")
                m5.metric("Turnovers", f"{ts.get('to', 0):.1f}")
                m6.metric("FG %", f"{ts.get('fgpct', 0):.1f}%")
                m1, m2, m3, m4, m5, m6 = st.columns(6)
                m1.metric("3er %", f"{ts.get('3pct', 0):.1f}%")
                m2.metric("FW %", f"{ts.get('ftpct', 0):.1f}%")
                m3.metric("Fouls", f"{ts.get('pf', 0):.1f}")
                m4.metric("Off. Reb", f"{ts.get('or', 0):.1f}")
                m5.metric("Def. Reb", f"{ts.get('dr', 0):.1f}")
                m6.metric("Blocks", f"{ts.get('bs', 0):.1f}")
            
            st.divider()
            st.subheader("Aktueller Kader & Stats")
            if df is not None and not df.empty:
                df = df.sort_values(by="PPG", ascending=False)
                display_cols = ["NR", "NAME_FULL", "GP", "MIN_DISPLAY", "PPG", "FG%", "3PCT", "FTPCT", "TOT", "AS", "ST", "TO", "PF"]
                col_config = {
                    "NR": st.column_config.TextColumn("#", width="small"),
                    "NAME_FULL": st.column_config.TextColumn("Name", width="medium"),
                    "GP": st.column_config.NumberColumn("Spiele"),
                    "MIN_DISPLAY": st.column_config.TextColumn("Min"),
                    "PPG": st.column_config.NumberColumn("PTS", format="%.1f"),
                    "FG%": st.column_config.NumberColumn("FG%", format="%.1f %%"),
                    "3PCT": st.column_config.NumberColumn("3P%", format="%.1f %%"),
                    "FTPCT": st.column_config.NumberColumn("FW%", format="%.1f %%"),
                    "TOT": st.column_config.NumberColumn("REB", format="%.1f"),
                    "AS": st.column_config.NumberColumn("AST", format="%.1f"),
                    "ST": st.column_config.NumberColumn("STL", format="%.1f"),
                    "TO": st.column_config.NumberColumn("TO", format="%.1f"),
                    "PF": st.column_config.NumberColumn("PF", format="%.1f"),
                }
                st.dataframe(df[display_cols], column_config=col_config, hide_index=True, use_container_width=True, height=600)
            else: st.info("Keine Spielerdaten verfügbar.")
        else: st.error(f"Daten konnten für Saison {CURRENT_SEASON_ID} nicht geladen werden.")
    else:
        render_page_header("📈 Team Statistiken")
        tab_nord, tab_sued = st.tabs(["Nord", "Süd"])
        def render_logo_grid(staffel_name):
            teams = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == staffel_name}
            cols = st.columns(5)
            for idx, (tid, info) in enumerate(teams.items()):
                col = cols[idx % 5]
                with col:
                    with st.container(border=True):
                        logo_b64 = get_best_team_logo(tid)
                        c_l, c_m, c_r = st.columns([1, 2, 1])
                        with c_m:
                            if logo_b64: st.image(logo_b64, width=100)
                            else: st.markdown(f"<div style='font-size: 40px; text-align:center;'>🏀</div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='text-align:center; font-weight:bold; height: 3em; display:flex; align-items:center; justify-content:center;'>{info['name']}</div>", unsafe_allow_html=True)
                        if st.button("Stats anzeigen", key=f"btn_stats_{tid}", use_container_width=True):
                            st.session_state.stats_team_id = tid
                            st.rerun()
        with tab_nord: st.subheader("Teams Nord"); render_logo_grid("Nord")
        with tab_sued: st.subheader("Teams Süd"); render_logo_grid("Süd")

def render_comparison_page():
    render_page_header("📊 Head-to-Head Vergleich") 
    c1, c2, c3 = st.columns([1, 2, 2])
    with c1: 
        staffel = st.radio("Staffel:", ["Süd", "Nord"], horizontal=True, key="comp_staffel")
        teams = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == staffel}
        team_opts = {v["name"]: k for k, v in teams.items()}
    with c2:
        h_name = st.selectbox("Heim:", list(team_opts.keys()), 0, key="comp_home")
        h_id = team_opts[h_name]
        l_b64 = get_best_team_logo(h_id)
        if l_b64: st.image(l_b64, width=80)
        else: st.markdown("🏀")
    with c3:
        g_name = st.selectbox("Gast:", list(team_opts.keys()), 1, key="comp_guest")
        g_id = team_opts[g_name]
        l_b64 = get_best_team_logo(g_id)
        if l_b64: st.image(l_b64, width=80)
        else: st.markdown("🏀")
    st.divider()
    if st.button("Vergleich starten", type="primary"):
        with st.spinner("Lade Daten..."):
            _, ts_h = fetch_team_data(h_id, CURRENT_SEASON_ID)
            _, ts_g = fetch_team_data(g_id, CURRENT_SEASON_ID)
            if ts_h and ts_g: st.markdown(generate_comparison_html(ts_h, ts_g, h_name, g_name), unsafe_allow_html=True)
            else: st.error("Daten nicht verfügbar.")

def render_player_comparison_page():
    render_page_header("🤼 Head-to-Head Spielervergleich") 
    c1, c2, c3 = st.columns([1, 0.1, 1])
    with c1:
        st.subheader("Spieler A")
        s1 = st.radio("Staffel A", ["Süd", "Nord"], horizontal=True, key="pc_s_a")
        t1 = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == s1}
        tn1 = st.selectbox("Team", list({v["name"]: k for k, v in t1.items()}.keys()), key="pc_t_a")
        tid1 = {v["name"]: k for k, v in t1.items()}[tn1]
        df1, _ = fetch_team_data(tid1, CURRENT_SEASON_ID)
        if df1 is not None and not df1.empty: 
            p1 = st.selectbox("Spieler", df1["NAME_FULL"].tolist(), key="pc_p_a")
            row1 = df1[df1["NAME_FULL"] == p1].iloc[0]
            m1 = get_player_metadata_cached(row1["PLAYER_ID"])
            if m1["img"]: st.image(m1["img"], width=150)
        else: st.error("Daten nicht geladen."); row1 = None
    with c2: st.write("") 
    with c3:
        st.subheader("Spieler B")
        s2 = st.radio("Staffel B", ["Süd", "Nord"], horizontal=True, key="pc_s_b")
        t2 = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == s2}
        tn2 = st.selectbox("Team", list({v["name"]: k for k, v in t2.items()}.keys()), key="pc_t_b")
        tid2 = {v["name"]: k for k, v in t2.items()}[tn2]
        df2, _ = fetch_team_data(tid2, CURRENT_SEASON_ID)
        if df2 is not None and not df2.empty: 
            p2 = st.selectbox("Spieler", df2["NAME_FULL"].tolist(), key="pc_p_b")
            row2 = df2[df2["NAME_FULL"] == p2].iloc[0]
            m2 = get_player_metadata_cached(row2["PLAYER_ID"])
            if m2["img"]: st.image(m2["img"], width=150)
        else: st.error("Daten nicht geladen."); row2 = None
    st.divider()
    if row1 is not None and row2 is not None:
        metrics = [("Spiele", "GP", int), ("Punkte", "PPG", float), ("Minuten", "MIN_DISPLAY", str), ("FG %", "FG%", float), ("3er %", "3PCT", float), ("FW %", "FTPCT", float), ("Reb", "TOT", float), ("Assists", "AS", float), ("TO", "TO", float), ("Steals", "ST", float), ("Blocks", "BS", float), ("Fouls", "PF", float)]
        h1, h2, h3 = st.columns([1, 1, 1]); h1.markdown(f"<h3 style='text-align: right;'>{p1}</h3>", unsafe_allow_html=True); h2.markdown(f"<div style='text-align: center; font-weight: bold;'>VS</div>", unsafe_allow_html=True); h3.markdown(f"<h3 style='text-align: left;'>{p2}</h3>", unsafe_allow_html=True); st.write("")
        for l, c, t in metrics:
            v1 = row1[c]; v2 = row2[c]; s1="color:#444;"; s2="color:#444;"
            if t in [int, float]:
                try:
                    vf1=float(v1); vf2=float(v2)
                    if c in ["TO", "PF"]: 
                        if vf1 < vf2: s1="font-weight:bold;"
                        elif vf2 < vf1: s2="font-weight:bold;"
                    else:
                        if vf1 > vf2: s1="font-weight:bold;"
                        elif vf2 > vf1: s2="font-weight:bold;"
                except: pass
            c1, c2, c3 = st.columns([1, 1.5, 1])
            with c1: st.markdown(f"<div style='text-align: right; {s1}'>{v1}</div>", unsafe_allow_html=True)
            with c2: st.markdown(f"<div style='text-align: center; background:#f8f9fa;'>{l}</div>", unsafe_allow_html=True)
            with c3: st.markdown(f"<div style='text-align: left; {s2}'>{v2}</div>", unsafe_allow_html=True)

def render_prep_page():
    render_page_header("🔮 Spielvorbereitung")
    c1, c2 = st.columns([1, 2])
    with c1:
        s = st.radio("Staffel", ["Süd", "Nord"], horizontal=True, key="prep_staffel")
        t = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == s}
    with c2:
        opp_name = st.selectbox("Gegner-Team:", list({v["name"]: k for k, v in t.items()}.keys()), key="prep_team")
        opp_id = {v["name"]: k for k, v in t.items()}[opp_name]
    if st.button("Vorbereitung starten", type="primary"):
        with st.spinner("Lade Daten..."):
            df, _ = fetch_team_data(opp_id, CURRENT_SEASON_ID)
            sched = fetch_schedule(opp_id, CURRENT_SEASON_ID)
            if df is not None: 
                render_prep_dashboard(opp_id, opp_name, df, sched, metadata_callback=get_player_metadata_cached)
            else: 
                st.error("Fehler beim Laden der Spielerdaten.")

def render_live_page():
    if st.session_state.live_game_id:
        c_back, c_title = st.columns([1, 5])
        with c_back:
            if st.button("⬅️ Zurück", key="live_back_btn"):
                st.session_state.live_game_id = None
                st.rerun()
        with c_title:
             st.title("🔴 Live View")
    else:
        render_page_header("🔴 Live Games Übersicht")

    if st.session_state.live_game_id:
        gid = st.session_state.live_game_id
        auto = st.checkbox("🔄 Auto-Refresh (15s)", value=False, key="live_auto_refresh")
        st.divider()
        box = fetch_game_boxscore(gid)
        det = fetch_game_details(gid)
        if box and det:
            box["gameTime"] = det.get("gameTime")
            box["period"] = det.get("period")
            box["result"] = det.get("result") 
            render_live_view(box)
            if auto:
                time_module.sleep(15)
                st.rerun()
        else:
            st.info("Warte auf Datenverbindung...")
    else:
        st.markdown("### Spiele von heute")
        with st.spinner("Lade aktuellen Spielplan..."):
            all_games = fetch_season_games(CURRENT_SEASON_ID)
        if not all_games:
            st.warning("Keine Spieldaten gefunden.")
            return
        today_str = datetime.now().strftime("%d.%m.%Y")
        todays_games = [g for g in all_games if g['date_only'] == today_str]
        if not todays_games:
            st.info(f"Keine Spiele für heute ({today_str}) gefunden.")
        else:
            todays_games.sort(key=lambda x: x['date'])
            cols = st.columns(3) 
            for i, game in enumerate(todays_games):
                col = cols[i % 3]
                with col:
                    with st.container():
                        st.markdown(
                            f"""
                            <div style="border:1px solid #ddd; border-radius:10px; padding:15px; margin-bottom:10px; background-color:white; text-align:center;">
                                <div style="font-weight:bold; color:#555;">{game['date'].split(' ')[1]} Uhr</div>
                                <div style="font-size:1.1em; margin:10px 0;">
                                    <b>{game['home']}</b><br>vs<br><b>{game['guest']}</b>
                                </div>
                                <div style="font-size:1.5em; font-weight:bold; color:#d9534f;">
                                    {game['score']}
                                </div>
                            </div>
                            """, 
                            unsafe_allow_html=True
                        )
                        if st.button(f"Zum Spiel ({game['home'][:3]} vs {game['guest'][:3]})", key=f"btn_live_{game['id']}", use_container_width=True):
                            st.session_state.live_game_id = game['id']
                            st.rerun()

def render_game_venue_page():
    render_page_header("📍 Spielorte der Teams") 
    c1, c2 = st.columns([1, 2])
    with c1:
        s = st.radio("Staffel", ["Süd", "Nord"], horizontal=True, key="venue_staffel")
        t = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == s}
        to = {v["name"]: k for k, v in t.items()}
    with c2:
        tn = st.selectbox("Wähle ein Team:", list(to.keys()), key="venue_team_select")
        tid = to[tn]
    st.divider()
    if tid:
        st.subheader(f"Standard-Heimspielort von {tn}")
        with st.spinner(f"Lade Daten..."):
            info = fetch_team_info_basic(tid)
            venue = info.get("venue") if info else None
            if venue:
                st.markdown(f"**Halle:** {venue.get('name', 'N/A')}"); st.markdown(f"**Adresse:** {venue.get('address', 'N/A')}")
                if venue.get('address'):
                    u = f"https://www.google.com/maps/search/?api=1&query={quote_plus(f'{venue.get('name', '')}, {venue.get('address', '')}')}"
                    st.markdown(f"**Route:** [Google Maps öffnen]({u})", unsafe_allow_html=True)
            else: st.warning("Nicht gefunden.")
        st.divider()
        st.subheader(f"Alle Spiele von {tn}")
        games = fetch_schedule(tid, CURRENT_SEASON_ID)
        if games:
            def date_sorter(x):
                try: return datetime.strptime(x['date'], "%d.%m.%Y %H:%M")
                except: return datetime.min
            games.sort(key=date_sorter, reverse=True)
            for g in games:
                gid = g.get("id")
                if str(g.get("homeTeamId")) == str(tid):
                    with st.expander(f"🏟️ Heim: {g.get('date')} vs {g.get('guest')} ({g.get('score')})"):
                        if gid:
                            d = fetch_game_details(gid)
                            if d and d.get("venue"):
                                v = d.get("venue")
                                st.markdown(f"**Ort:** {v.get('name', '-')}, {v.get('address', '-')}")
                else:
                    with st.expander(f"🚌 Gast: {g.get('date')} bei {g.get('home')} ({g.get('score')})"):
                        if gid:
                            d = fetch_game_details(gid)
                            if d and d.get("venue"):
                                v = d.get("venue")
                                st.markdown(f"**Ort:** {v.get('name', '-')}, {v.get('address', '-')}")

def render_analysis_page():
    render_page_header("🎥 Spielnachbereitung") 
    c1, c2 = st.columns([1, 2])
    with c1:
        s = st.radio("Staffel", ["Süd", "Nord"], horizontal=True, key="ana_staffel")
        t = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == s}
        to = {v["name"]: k for k, v in t.items()}
    with c2:
        tn = st.selectbox("Dein Team:", list(to.keys()), key="ana_team")
        tid = to[tn]
    if tid:
        games = fetch_schedule(tid, CURRENT_SEASON_ID)
        if games:
            played_games = [g for g in games if g.get('has_result')]
            opts = {f"{g['date']} | {g['home']} vs {g['guest']} ({g['score']})": g['id'] for g in played_games}
            
            if not opts:
                st.warning("Keine gespielten Spiele für dieses Team in dieser Saison gefunden.")
                return

            sel = st.selectbox("Wähle ein Spiel:", list(opts.keys()), key="ana_game_select")
            gid = opts[sel]
            if st.button("Analyse laden", type="primary"):
                st.session_state.selected_game_id = gid
                if "generated_ai_report" in st.session_state: del st.session_state["generated_ai_report"]
            if st.session_state.selected_game_id == gid:
                st.divider()
                with st.spinner("Lade Daten..."):
                    box = fetch_game_boxscore(gid); details = fetch_game_details(gid)
                    if box and details: 
                        box["venue"] = details.get("venue"); box["result"] = details.get("result"); box["referee1"] = details.get("referee1"); box["referee2"] = details.get("referee2"); box["referee3"] = details.get("referee3"); box["scheduledTime"] = details.get("scheduledTime"); box["attendance"] = details.get("result", {}).get("spectators"); box["id"] = details.get("id") 
                        render_game_header(box)
                        st.markdown("### 📝 Spielberichte & PBP")
                        t1, t2, t3 = st.tabs(["⚡ Kurzbericht", "📋 Prompt Kopieren", "📜 Play-by-Play"])
                        with t1:
                            st.markdown(generate_game_summary(box)); st.divider()
                            hn = get_team_name(box.get("homeTeam", {}), "Heim"); gn = get_team_name(box.get("guestTeam", {}), "Gast")
                            hc = box.get("homeTeam", {}).get("headCoachName", "-"); gc = box.get("guestTeam", {}).get("headCoachName", "-")
                            render_boxscore_table_pro(box.get("homeTeam", {}).get("playerStats", []), box.get("homeTeam", {}).get("gameStat", {}), hn, hc)
                            st.write(""); render_boxscore_table_pro(box.get("guestTeam", {}).get("playerStats", []), box.get("guestTeam", {}).get("gameStat", {}), gn, gc)
                            st.divider(); render_game_top_performers(box); st.divider(); render_charts_and_stats(box)
                        with t2:
                            st.info("ChatGPT Prompt:"); st.code(generate_complex_ai_prompt(box), language="text")
                        with t3: render_full_play_by_play(box)
                    else: st.error("Fehler beim Laden.")
        else: st.warning("Keine Spiele.")

# NEU: Seite für Saison-Analyse
def render_season_analysis_wrapper():
    render_page_header("📊 Saison Analyse")
    with st.spinner("Lade alle Saisondaten..."):
        all_games = fetch_season_games(CURRENT_SEASON_ID)
        render_season_analysis_page(all_games)

# --- MAIN LOOP ---
if st.session_state.current_page == "home": render_home()
elif st.session_state.current_page == "scouting": render_scouting_page()
elif st.session_state.current_page == "comparison": render_comparison_page()
elif st.session_state.current_page == "analysis": render_analysis_page()
elif st.session_state.current_page == "player_comparison": render_player_comparison_page()
elif st.session_state.current_page == "game_venue": render_game_venue_page()
elif st.session_state.current_page == "prep": render_prep_page()
elif st.session_state.current_page == "live": render_live_page()
elif st.session_state.current_page == "team_stats": render_team_stats_page()
elif st.session_state.current_page == "season_analysis": render_season_analysis_wrapper()
