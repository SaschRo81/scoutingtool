# --- START OF FILE app.py ---
# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd
import requests
import base64
from datetime import datetime
import time as time_module

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
    fetch_season_games, fetch_standings_complete, fetch_1dbbl_teams
)
from src.html_gen import (
    generate_header_html, generate_top3_html, generate_card_html, 
    generate_team_stats_html, generate_custom_sections_html
)
from src.state_manager import export_session_state, load_session_state
from src.analysis_ui import (
    render_game_header, render_boxscore_table_pro, render_charts_and_stats, 
    render_game_top_performers, generate_game_summary,
    generate_complex_ai_prompt, render_full_play_by_play, render_live_view,
    render_prep_dashboard 
)

# --- CONFIG ---
CURRENT_SEASON_ID = "2025" 
BASKETBALL_ICON = "\U0001F3C0"
st.set_page_config(page_title=f"DBBL Scouting Pro {VERSION}", layout="wide", page_icon=BASKETBALL_ICON)

# --- INIT STATE ---
DEFAULTS = {
    "current_page": "home", "selected_league": None, "selected_team_id": None, 
    "selected_player_id": None, "print_mode": False, "pdf_bytes": None, 
    "roster_df": None, "live_game_id": None, "comparison_ids": [],
    "facts_offense": pd.DataFrame([{"Fokus": "Run", "Beschreibung": "fastbreaks"}]),
    "facts_defense": pd.DataFrame([{"Fokus": "Man2Man", "Beschreibung": "aggressiv"}]),
    "facts_about": pd.DataFrame([{"Fokus": "Team", "Beschreibung": "Together"}]),
    "saved_colors": {}, "saved_notes": {}, "game_meta": {}, 
    "team_stats": None, "logo_h": None, "logo_g": None
}
for k, v in DEFAULTS.items():
    if k not in st.session_state: st.session_state[k] = v

# --- NAVIGATION HELPER ---
def nav_to(page): 
    st.session_state.current_page = page

def go_home(): 
    st.session_state.selected_league = None
    st.session_state.selected_team_id = None
    st.session_state.selected_player_id = None
    st.session_state.current_page = "home"

# --- CSS & ASSETS ---
def inject_custom_css():
    st.markdown("""<style>
    div.stButton > button { 
        width: 100%; border-radius: 8px; font-weight: bold; height: 3em;
        border: 1px solid #ddd;
    }
    div.stButton > button:hover {
        border-color: #ff4b4b; color: #ff4b4b;
    }
    [data-testid="stVerticalBlock"] > [style*="flex-direction: column;"] > [data-testid="stVerticalBlock"] {
        gap: 1rem;
    }
    </style>""", unsafe_allow_html=True)

    if st.session_state.current_page == "home":
        st.markdown("""<style>[data-testid="stAppViewContainer"] { 
            background-image: linear-gradient(rgba(255,255,255,0.9), rgba(255,255,255,0.9)), url("https://cdn.pixabay.com/photo/2022/11/22/20/25/ball-7610545_1280.jpg"); 
            background-size: cover; background-attachment: fixed; }</style>""", unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def get_best_team_logo(team_id):
    if not team_id: return None
    # Jetzt auch api-1 prüfen
    candidates = [
        f"https://api-1.dbbl.scb.world/images/teams/logo/{CURRENT_SEASON_ID}/{team_id}",
        f"https://api-s.dbbl.scb.world/images/teams/logo/{CURRENT_SEASON_ID}/{team_id}",
        f"https://api-n.dbbl.scb.world/images/teams/logo/{CURRENT_SEASON_ID}/{team_id}"
    ]
    for url in candidates:
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=0.5)
            if r.status_code == 200 and len(r.content) > 500:
                b64 = base64.b64encode(r.content).decode()
                return f"data:image/png;base64,{b64}"
        except: continue
    return None

# --- SUCHE (GLOBAL) ---
def search_player_and_redirect(query):
    with st.spinner(f"Suche nach '{query}'..."):
        found = []
        # Kombiniere TEAMS_DB (2. Liga) mit 1. Liga Teams
        all_teams = TEAMS_DB.copy()
        dbbl1 = fetch_1dbbl_teams(CURRENT_SEASON_ID)
        all_teams.update(dbbl1)
        
        for tid, info in all_teams.items():
            df, _ = fetch_team_data(tid, CURRENT_SEASON_ID)
            if df is not None and not df.empty:
                matches = df[df["NAME_FULL"].str.contains(query, case=False, na=False)]
                for _, row in matches.iterrows():
                    found.append({"id": row["PLAYER_ID"], "name": row["NAME_FULL"], "team": info["name"], "tid": tid})
        return found

# --- RENDER PAGES ---

def render_header(title):
    inject_custom_css()
    c1, c2 = st.columns([1, 6])
    with c1: st.button("🏠 Home", on_click=go_home)
    with c2: st.markdown(f"<h2 style='margin:0; padding-top:5px;'>{title}</h2>", unsafe_allow_html=True)
    st.divider()

def render_home():
    inject_custom_css()
    st.markdown(f"<div style='text-align:center; padding: 30px;'><h1 style='margin:0;'>{BASKETBALL_ICON} DBBL Scouting Suite {VERSION}</h1><p style='color:gray;'>Scouting & Analysis Tool</p></div>", unsafe_allow_html=True)
    
    with st.container():
        c_search, _ = st.columns([2, 1])
        with c_search:
            st.markdown("##### 🔍 Spieler Schnellsuche")
            # FIXED KEY to prevent DuplicateElementError
            sq = st.text_input("Name eingeben...", key="home_search_v6", label_visibility="collapsed", placeholder="Spielername...")
            if sq and len(sq) > 2:
                results = search_player_and_redirect(sq)
                if results:
                    opts = {f"{r['name']} ({r['team']})": r for r in results}
                    sel = st.selectbox("Ergebnisse:", list(opts.keys()))
                    if st.button("Zum Profil", type="primary"):
                        choice = opts[sel]
                        st.session_state.selected_team_id = choice['tid']
                        st.session_state.selected_player_id = choice['id']
                        st.session_state.current_page = "player_profile"
                        st.rerun()
                else: st.warning("Keine Spieler gefunden.")
    
    st.markdown("---")
    
    # GRID LAYOUT
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        with st.container(border=True):
            st.markdown("#### 📊 Team Stats")
            st.caption("Ligen, Tabellen, Roster")
            st.button("Öffnen", key="btn_team_stats", on_click=nav_to, args=("team_stats_hub",))
    with c2:
        with st.container(border=True):
            st.markdown("#### 🤼 Vergleich")
            st.caption("Head-to-Head Spieler")
            st.button("Öffnen", key="btn_compare", on_click=nav_to, args=("comparison",))
    with c3:
        with st.container(border=True):
            st.markdown("#### 🔮 Prep")
            st.caption("Spielvorbereitung")
            st.button("Öffnen", key="btn_prep", on_click=nav_to, args=("prep",))
    with c4:
        with st.container(border=True):
            st.markdown("#### 🔴 Live")
            st.caption("Scores & Ticker")
            st.button("Öffnen", key="btn_live", on_click=nav_to, args=("live",))

    st.write("") 
    c5, c6, c7, c8 = st.columns(4)
    with c5:
        with st.container(border=True):
            st.markdown("#### 📝 Scouting")
            st.caption("PreGame Report PDF")
            st.button("Öffnen", key="btn_scout", on_click=nav_to, args=("scouting",))
    with c6:
        with st.container(border=True):
            st.markdown("#### 🎥 Analyse")
            st.caption("PostGame & AI")
            st.button("Öffnen", key="btn_ana", on_click=nav_to, args=("analysis",))
    with c7:
        with st.container(border=True):
            st.markdown("#### 📍 Orte")
            st.caption("Hallen & Routen")
            st.button("Öffnen", key="btn_venue", on_click=nav_to, args=("game_venue",))
    with c8:
        with st.container(border=True):
            st.markdown("#### ℹ️ Info")
            st.caption(f"Version {VERSION}")
            st.button("Reload", on_click=st.rerun)

def render_stats_hub():
    render_header("📊 Ligen Übersicht")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        with st.container(border=True):
            st.markdown("### 1. DBBL")
            st.caption("1. Bundesliga")
            if st.button("Zur Liga", key="btn_1dbbl"): 
                st.session_state.selected_league = "1. DBBL"
                nav_to("league_view")
            
    with col2:
        with st.container(border=True):
            st.markdown("### 2. DBBL Nord")
            st.caption("2. Bundesliga Nord")
            if st.button("Zur Liga", key="btn_nord"): 
                st.session_state.selected_league = "Nord"
                nav_to("league_view")
                
    with col3:
        with st.container(border=True):
            st.markdown("### 2. DBBL Süd")
            st.caption("2. Bundesliga Süd")
            if st.button("Zur Liga", key="btn_sued"): 
                st.session_state.selected_league = "Süd"
                nav_to("league_view")

def render_league_view():
    league = st.session_state.selected_league
    if not league: go_home(); return
    
    render_header(f"{league} Übersicht")
    
    # Logik: 2. Liga aus Config, 1. Liga dynamisch laden
    if league == "1. DBBL":
        with st.spinner("Lade 1. DBBL Teams..."):
            teams = fetch_1dbbl_teams(CURRENT_SEASON_ID)
            # Standings fetcher für 1. DBBL
            standings = fetch_standings_complete(CURRENT_SEASON_ID, "1. DBBL")
    else:
        teams = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == league}
        grp = "NORTH" if league == "Nord" else "SOUTH"
        standings = fetch_standings_complete(CURRENT_SEASON_ID, grp)
    
    c_teams, c_table = st.columns([2, 1])
    
    with c_teams:
        st.subheader("Teams")
        cols = st.columns(4)
        for idx, (tid, info) in enumerate(teams.items()):
            with cols[idx % 4]:
                with st.container(border=True):
                    # Bei 1. DBBL ist logo_url schon im dict, sonst holen
                    if "logo_url" in info:
                        st.image(info["logo_url"], use_container_width=True)
                    else:
                        logo = get_best_team_logo(tid)
                        if logo: st.image(logo, use_container_width=True)
                        else: st.markdown(f"<div style='text-align:center; font-size:40px;'>{BASKETBALL_ICON}</div>", unsafe_allow_html=True)
                    
                    if st.button(info['name'], key=f"t_{tid}"):
                        st.session_state.selected_team_id = tid
                        nav_to("team_view")

    with c_table:
        st.subheader("Tabelle")
        if standings:
            df_std = pd.DataFrame(standings)[["rank", "team", "wins", "losses", "points"]]
            st.dataframe(df_std, column_config={
                "rank": st.column_config.NumberColumn("#", format="%d", width="small"),
                "team": "Team", "wins": "W", "losses": "L", "points": "Pts"
            }, hide_index=True, use_container_width=True, height=600)
        else: st.info("Tabelle nicht geladen.")

def render_team_view():
    tid = st.session_state.selected_team_id
    if not tid: nav_to("team_stats_hub"); return
    
    # Info aus Config ODER dynamisch (für 1. DBBL)
    if tid in TEAMS_DB:
        info = TEAMS_DB[tid]
    else:
        # Versuche 1. DBBL Map wiederherzustellen oder generischer Fall
        # Wir machen es einfach: wir haben keine Infos, wir laden einfach Logo und Name
        info = {"name": f"Team {tid}"} # Fallback Name

    # Wenn wir in 1. DBBL sind, können wir den Namen evtl. aus den API Daten fischen
    # Aber `fetch_team_data` liefert keine Meta-Daten zurück, nur Stats.
    # Wir lassen es beim Fallback oder holen es via fetch_team_info_basic
    basic = fetch_team_info_basic(tid)
    
    render_header(f"Team Stats (ID: {tid})")
    
    logo = get_best_team_logo(tid)
    c_head, c_stats = st.columns([1, 3])
    with c_head:
        if logo: st.image(logo, width=150)
    
    with st.spinner("Lade Team Daten..."):
        df_roster, t_stats = fetch_team_data(tid, CURRENT_SEASON_ID)
        schedule = fetch_schedule(tid, CURRENT_SEASON_ID)
    
    with c_stats:
        if t_stats:
            st.markdown("### Season Averages")
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("PPG", f"{t_stats.get('ppg',0):.1f}")
            m2.metric("REB", f"{t_stats.get('tot',0):.1f}")
            m3.metric("AST", f"{t_stats.get('as',0):.1f}")
            m4.metric("FG%", f"{t_stats.get('fgpct',0):.1f}%")
            m5.metric("3P%", f"{t_stats.get('3pct',0):.1f}%")
    
    st.divider()
    
    c_games, c_roster = st.columns([1, 2])
    
    with c_games:
        st.subheader("Letzte Spiele")
        if schedule:
            for g in schedule[:8]: 
                with st.container(border=True):
                    c_date, c_res = st.columns([2, 1])
                    with c_date:
                        st.markdown(f"**{g['date_display']}**")
                        st.caption(f"{g['home']} vs {g['guest']}")
                    with c_res:
                         st.markdown(f"### {g['score']}")
        else: st.info("Keine Spiele.")

    with c_roster:
        st.subheader("Kader (Profil öffnen)")
        if df_roster is not None and not df_roster.empty:
            df_roster = df_roster.sort_values(by="PPG", ascending=False)
            
            for _, p in df_roster.iterrows():
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([0.5, 2, 1.5, 1])
                    with c1: st.markdown(f"**#{p['NR']}**")
                    with c2: st.markdown(f"**{p['NAME_FULL']}**")
                    with c3: st.caption(f"{p['PPG']} PPG | {p['TOT']} REB")
                    with c4: 
                        if st.button("Profil", key=f"prof_{p['PLAYER_ID']}"):
                            st.session_state.selected_player_id = p['PLAYER_ID']
                            nav_to("player_profile")

def render_player_profile():
    pid = st.session_state.selected_player_id
    tid = st.session_state.selected_team_id
    
    if not pid or not tid: nav_to("home"); return
    
    df_roster, _ = fetch_team_data(tid, CURRENT_SEASON_ID)
    
    if df_roster is None or df_roster.empty:
        st.error("Datenfehler."); st.button("Zurück", on_click=lambda: nav_to("team_view")); return

    player_row = df_roster[df_roster["PLAYER_ID"] == str(pid)]
    if player_row.empty:
        st.error("Spieler nicht gefunden."); st.button("Zurück", on_click=lambda: nav_to("team_view")); return
        
    p = player_row.iloc[0]
    meta = get_player_metadata_cached(pid)
    
    inject_custom_css()
    c1, c2 = st.columns([1, 6])
    with c1: st.button("⬅️ Team", on_click=lambda: nav_to("team_view"))
    
    st.markdown(f"""
    <div style='background-color:#FFD700; padding:20px; border-radius:10px; margin-bottom:20px; color:black;'>
        <h1 style='margin:0;'>{p['NAME_FULL'].upper()}</h1>
        <p style='margin:0; font-weight:bold;'>{meta.get('pos','-')} | {meta.get('nationality','-')} | Geb: {meta.get('age','-')} Jahre</p>
    </div>
    """, unsafe_allow_html=True)
    
    c_img, c_info = st.columns([1, 2])
    with c_img:
        if meta.get("img"): st.image(meta["img"], width=250)
        else: st.markdown(f"<div style='font-size:100px; text-align:center; border:1px solid #ccc;'>👤</div>", unsafe_allow_html=True)
    
    with c_info:
        st.subheader("Saison Statistiken (AVG)")
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Minuten", p['MIN_DISPLAY'])
        s2.metric("Punkte", p['PPG'])
        s3.metric("Rebounds", p['TOT'])
        s4.metric("Assists", p['AS'])
        
        st.divider()
        
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("FG %", f"{p['FG%']}%")
        s2.metric("3P %", f"{p['3PCT']}%")
        s3.metric("FW %", f"{p['FTPCT']}%")
        s4.metric("Effizienz", p.get('EFF', '-'))

    st.divider()
    st.markdown("### Letzte Spiele des Teams")
    schedule = fetch_schedule(tid, CURRENT_SEASON_ID)
    if schedule:
        df_sched = pd.DataFrame(schedule[:8])
        st.dataframe(df_sched[["date_display", "home", "guest", "score"]], hide_index=True, use_container_width=True)

# --- COMPARISON ---

def render_comparison():
    render_header("🤼 Spieler Vergleich")
    
    num = st.slider("Anzahl Spieler für Vergleich wählen:", 1, 4, 2)
    st.divider()
    
    cols = st.columns(num)
    selected_players = []
    
    # Hole alle Teams (2. + 1. Liga) für die Auswahl
    all_teams_data = TEAMS_DB.copy()
    all_teams_data.update(fetch_1dbbl_teams(CURRENT_SEASON_ID))
    
    for i in range(num):
        with cols[i]:
            st.markdown(f"##### Spieler {i+1}")
            # Ligen Filter
            leagues = ["1. DBBL", "Nord", "Süd"]
            s = st.selectbox(f"Liga", leagues, key=f"c_s_{i}", label_visibility="collapsed")
            
            # Team Filter
            t_subset = {k: v for k, v in all_teams_data.items() if v["staffel"] == s}
            if not t_subset:
                 st.info("Keine Teams")
                 continue
                 
            t_name = st.selectbox(f"Team", [v['name'] for v in t_subset.values()], key=f"c_t_{i}")
            tid = next(k for k, v in t_subset.items() if v['name'] == t_name)
            
            df, _ = fetch_team_data(tid, CURRENT_SEASON_ID)
            if df is not None:
                p_name = st.selectbox(f"Name", df["NAME_FULL"].tolist(), key=f"c_p_{i}")
                row = df[df["NAME_FULL"] == p_name].iloc[0]
                meta = get_player_metadata_cached(row["PLAYER_ID"])
                selected_players.append({"row": row, "meta": meta})
                
                if meta.get("img"): st.image(meta["img"], width=120)
            else:
                st.error("Ladefehler")

    st.divider()
    
    if selected_players:
        metrics = ["GP", "MIN_DISPLAY", "PPG", "FG%", "3PCT", "FTPCT", "TOT", "AS", "ST", "TO", "PF"]
        comp_data = {}
        for p in selected_players:
            col_name = p["row"]["NAME_FULL"]
            vals = []
            for m in metrics:
                vals.append(p["row"][m])
            comp_data[col_name] = vals
            
        df_comp = pd.DataFrame(comp_data, index=metrics)
        st.dataframe(df_comp, use_container_width=True, height=500)

# --- WRAPPERS ---
def render_prep_page():
    render_header("🔮 Spielvorbereitung")
    # Nur 2. Liga vorerst, da Scouting DB auf 2. Liga config basiert (kann man erweitern)
    c1, c2 = st.columns([1, 2])
    with c1:
        s = st.radio("Staffel", ["Süd", "Nord"], horizontal=True, key="prep_staffel")
        t = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == s}
    with c2:
        opp_name = st.selectbox("Gegner-Team:", list({v["name"]: k for k, v in t.items()}.keys()), key="prep_team"); opp_id = {v["name"]: k for k, v in t.items()}[opp_name]
    
    if st.button("Vorbereitung starten", type="primary"):
        with st.spinner("Lade Daten..."):
            df, _ = fetch_team_data(opp_id, CURRENT_SEASON_ID); sched = fetch_schedule(opp_id, CURRENT_SEASON_ID)
            if df is not None: 
                render_prep_dashboard(opp_id, opp_name, df, sched, metadata_callback=get_player_metadata_cached)

def render_live_page():
    render_live_view(None) if not st.session_state.live_game_id else render_live_view(fetch_game_boxscore(st.session_state.live_game_id))

def render_analysis_page():
    render_header("🎥 Spielnachbereitung")
    c1, c2 = st.columns([1, 2])
    with c1: s = st.radio("Staffel", ["Süd", "Nord"], horizontal=True, key="ana_staffel"); t = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == s}; to = {v["name"]: k for k, v in t.items()}
    with c2: tn = st.selectbox("Dein Team:", list(to.keys()), key="ana_team"); tid = to[tn]
    if tid:
        games = fetch_schedule(tid, CURRENT_SEASON_ID)
        if games:
            played_games = [g for g in games if g.get('has_result')]
            opts = {f"{g['date_display']} | {g['home']} vs {g['guest']} ({g['score']})": g['id'] for g in played_games}
            sel = st.selectbox("Wähle ein Spiel:", list(opts.keys()), key="ana_game_select")
            if sel and st.button("Analyse laden", type="primary"): 
                st.session_state.selected_game_id = opts[sel]
            if st.session_state.get("selected_game_id"):
                 box = fetch_game_boxscore(st.session_state.selected_game_id)
                 det = fetch_game_details(st.session_state.selected_game_id)
                 if box and det:
                     render_game_header(det)
                     t1, t2 = st.tabs(["Stats", "AI Report"])
                     with t1: render_charts_and_stats(box)
                     with t2: st.code(generate_complex_ai_prompt(box), language="text")

def render_scouting_page():
    render_header("📝 Scouting Report")
    st.info("Funktionalität analog zu V5.")
    st.button("Dummy", on_click=lambda: None)

def render_venue_page():
    render_header("📍 Spielorte")
    s = st.radio("Staffel", ["Süd", "Nord"], horizontal=True); t = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == s}
    tn = st.selectbox("Team:", list({v["name"]: k for k, v in t.items()}.keys()))
    tid = {v["name"]: k for k, v in t.items()}[tn]
    info = fetch_team_info_basic(tid)
    if info and info.get("venue"):
        v = info["venue"]
        st.markdown(f"**Halle:** {v.get('name')}")
        st.markdown(f"**Adresse:** {v.get('address')}")

# --- MAIN ROUTING ---

if st.session_state.current_page == "home": render_home()
elif st.session_state.current_page == "team_stats_hub": render_stats_hub()
elif st.session_state.current_page == "league_view": render_league_view()
elif st.session_state.current_page == "team_view": render_team_view()
elif st.session_state.current_page == "player_profile": render_player_profile()
elif st.session_state.current_page == "comparison": render_comparison()
elif st.session_state.current_page == "prep": render_prep_page()
elif st.session_state.current_page == "live": render_live_page()
elif st.session_state.current_page == "scouting": render_scouting_page()
elif st.session_state.current_page == "analysis": render_analysis_page()
elif st.session_state.current_page == "game_venue": render_venue_page()
