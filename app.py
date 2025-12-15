# --- START OF FILE app.py ---

import streamlit as st
import pandas as pd
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
from src.utils import get_logo_url, optimize_image_base64
# KORREKTUR: Komma hinzugefügt vor fetch_season_games
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

# HIER WERDEN ALLE BENÖTIGTEN FUNKTIONEN AUS analysis_ui IMPORTIERT
from src.analysis_ui import (
    render_game_header, render_boxscore_table_pro, render_charts_and_stats, 
    get_team_name, render_game_top_performers, generate_game_summary,
    generate_complex_ai_prompt, render_full_play_by_play, run_openai_generation,
    render_prep_dashboard, render_live_view 
)

st.set_page_config(page_title=f"DBBL Scouting Pro {VERSION}", layout="wide", page_icon="🏀")

# --- SESSION STATE ---
for key, default in [
    ("current_page", "home"), ("print_mode", False), ("final_html", ""), ("pdf_bytes", None),
    ("roster_df", None), ("team_stats", None), ("game_meta", {}),
    ("report_filename", "scouting_report.pdf"), ("saved_notes", {}), ("saved_colors", {}),
    ("facts_offense", pd.DataFrame([{"Fokus": "Run", "Beschreibung": "fastbreaks"}])),
    ("facts_defense", pd.DataFrame([{"Fokus": "Rebound", "Beschreibung": "box out!"}])),
    ("facts_about", pd.DataFrame([{"Fokus": "Together", "Beschreibung": "Fight!"}])),
    ("selected_game_id", None), ("generated_ai_report", None), ("live_game_id", None)
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

# --- STANDARD-SEITENHEADER ---
def render_page_header(page_title):
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
    # CSS für Hintergrundbild und Styling
    st.markdown(
        """
        <style>
        /* 
           Hintergrundbild auf dem Hauptcontainer 
           Wir nutzen einen Trick: Ein lineares Gradient (75% Weiß) liegt ÜBER dem Bild.
           Dadurch wirkt das Bild blass (Opacity ca. 0.25), ohne dass wir z-index Probleme haben.
        */
        [data-testid="stAppViewContainer"] {
            background: linear-gradient(rgba(255,255,255,0.85), rgba(255,255,255,0.85)), 
                        url("https://cdn.pixabay.com/photo/2022/11/22/20/25/ball-7610545_1280.jpg");
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            background-attachment: fixed;
        }
        
        /* Buttons Stylen - Deckend Weiß & Schwebend */
        div.stButton > button {
            width: 100%;
            height: 4em;
            font-size: 18px;
            font-weight: bold;
            border-radius: 10px;
            box-shadow: 0px 4px 6px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
            background-color: #ffffff !important; /* Wichtig: Überschreibt Theme */
            color: #333333 !important;
            border: 1px solid #ddd;
            opacity: 1 !important; /* Keine Transparenz */
        }
        
        div.stButton > button:hover {
            transform: scale(1.02);
            box-shadow: 0px 6px 8px rgba(0,0,0,0.15);
            border-color: #ff4b4b;
            background-color: #ffffff !important;
            color: #ff4b4b !important;
        }
        
        /* Titel Box - Deckend Weiß */
        .title-container {
            background-color: #ffffff; 
            padding: 20px; 
            border-radius: 15px; 
            box-shadow: 0px 4px 6px rgba(0,0,0,0.1); 
            text-align: center; 
            margin-bottom: 40px; 
            max-width: 800px; 
            margin-left: auto; 
            margin-right: auto; 
            border: 1px solid #f0f0f0;
            opacity: 1 !important;
        }
        </style>
        """, unsafe_allow_html=True
    )
    
    st.markdown(f"""<div class="title-container"><h1 style='margin:0; color: #333;'>🏀 DBBL Scouting Suite</h1><p style='margin:0; margin-top:10px; color: #555; font-weight: bold;'>Version {VERSION} | by Sascha Rosanke</p></div>""", unsafe_allow_html=True)
    
    # Grid Layout für die Buttons
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
            if st.button("📝 Scouting Report", use_container_width=True): go_scouting(); st.rerun()
        with r2_c2: 
            if st.button("🎥 Spielnachbereitung", use_container_width=True): go_analysis(); st.rerun()
        
        st.write("") 
        
        r3_c1, r3_c2 = st.columns(2)
        with r3_c1:
            if st.button("🔮 Spielvorbereitung", use_container_width=True): go_prep(); st.rerun()
        with r3_c2:
             if st.button("🔴 Live Game Center", use_container_width=True): go_live(); st.rerun()
        
        st.write("")
        
        _, c5, _ = st.columns([1, 2, 1])
        with c5:
             if st.button("📍 Spielorte", use_container_width=True): go_game_venue(); st.rerun()

def render_comparison_page():
    render_page_header("📊 Head-to-Head Vergleich") 
    c1, c2, c3 = st.columns([1, 2, 2])
    with c1: 
        staffel = st.radio("Staffel:", ["Süd", "Nord"], horizontal=True, key="comp_staffel")
        teams = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == staffel}
        team_opts = {v["name"]: k for k, v in teams.items()}
    with c2:
        h_name = st.selectbox("Heim:", list(team_opts.keys()), 0, key="comp_home")
        h_id = team_opts[h_name]; st.image(optimize_image_base64(get_logo_url(h_id, SEASON_ID)), width=60)
    with c3:
        g_name = st.selectbox("Gast:", list(team_opts.keys()), 1, key="comp_guest")
        g_id = team_opts[g_name]; st.image(optimize_image_base64(get_logo_url(g_id, SEASON_ID)), width=60)
    st.divider()
    if st.button("Vergleich starten", type="primary"):
        with st.spinner("Lade Daten..."):
            _, ts_h = fetch_team_data(h_id, SEASON_ID); _, ts_g = fetch_team_data(g_id, SEASON_ID)
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
        df1, _ = fetch_team_data(tid1, SEASON_ID)
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
        df2, _ = fetch_team_data(tid2, SEASON_ID)
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
            df, _ = fetch_team_data(opp_id, SEASON_ID)
            sched = fetch_schedule(opp_id, SEASON_ID)
            if df is not None: render_prep_dashboard(opp_id, opp_name, df, sched, metadata_callback=get_player_metadata_cached)
            else: st.error("Fehler beim Laden.")

def render_live_page():
    # Helper Button zum Zurückkehren
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

    # DETAILANSICHT (Wenn Spiel gewählt)
    if st.session_state.live_game_id:
        gid = st.session_state.live_game_id
        auto = st.checkbox("🔄 Auto-Refresh (15s)", value=False, key="live_auto_refresh")
        st.divider()
        
        # Daten laden
        box = fetch_game_boxscore(gid)
        det = fetch_game_details(gid)
        
        if box and det:
            box["gameTime"] = det.get("gameTime")
            box["period"] = det.get("period")
            box["result"] = det.get("result") # Wichtig für Score
            render_live_view(box)
            
            if auto:
                time_module.sleep(15)
                st.rerun()
        else:
            st.info("Warte auf Datenverbindung...")

    # ÜBERSICHTSANSICHT (Alle Spiele von heute)
    else:
        st.markdown("### Spiele von heute")
        with st.spinner("Lade aktuellen Spielplan..."):
            all_games = fetch_season_games(SEASON_ID)
            
        if not all_games:
            st.warning("Keine Spieldaten gefunden.")
            return

        # Datum von heute ermitteln
        today_str = datetime.now().strftime("%d.%m.%Y")
        
        # Filtern nach Datum = Heute
        # (Alternativ können wir hier auch alle Spiele anzeigen, wenn wir today_str auskommentieren,
        # aber "Live Games" impliziert aktuelle Spiele)
        todays_games = [g for g in all_games if g['date_only'] == today_str]
        
        if not todays_games:
            st.info(f"Keine Spiele für heute ({today_str}) gefunden.")
            # Fallback: Zeige die letzten 5 oder nächsten 5 Spiele, damit man was sieht zum Testen?
            # Hier optional: todays_games = all_games[:4] 
        else:
            # Sortieren nach Uhrzeit
            todays_games.sort(key=lambda x: x['date'])

            # Grid Layout für die Spiele
            cols = st.columns(3) # 3 Spalten Layout
            for i, game in enumerate(todays_games):
                col = cols[i % 3]
                with col:
                    # Container Stylen
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
                        # Der Button muss eindeutig sein (key=game['id'])
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
        games = fetch_schedule(tid, SEASON_ID)
        if games:
            games.sort(key=lambda x: datetime.strptime(x['date'], "%d.%m.%Y %H:%M"), reverse=True)
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
        games = fetch_schedule(tid, SEASON_ID)
        if games:
            opts = {f"{g['date']} | {g['home']} vs {g['guest']} ({g['score']})": g['id'] for g in games}
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

def render_scouting_page():
    render_page_header("📝 Scouting") 
    if st.session_state.print_mode:
        st.subheader("Vorschau & Export")
        c1, c2 = st.columns([1, 4])
        with c1:
            if st.button("⬅️ Bearbeiten", key="exit_print"): st.session_state.print_mode = False; st.rerun()
        with c2:
            if st.session_state.pdf_bytes: st.download_button("📄 Download PDF", st.session_state.pdf_bytes, st.session_state.report_filename, "application/pdf")
            else: st.warning("PDF Fehler.")
        st.divider()
        if st.session_state.final_html: st.markdown("### HTML-Vorschau"); st.markdown(CSS_STYLES + st.session_state.final_html, unsafe_allow_html=True)
    else:
        with st.sidebar: 
            st.header("💾 Spielstand")
            up = st.file_uploader("Laden (JSON)", type=["json"], key="scout_up")
            if up and st.button("Wiederherstellen", key="scout_restore"):
                s, m = load_session_state(up); st.success(m) if s else st.error(m)
            st.divider()
            if st.session_state.roster_df is not None:
                st.download_button("💾 Speichern", export_session_state(), f"Save_{date.today()}.json", "application/json", key="scout_save")
        st.subheader("1. Spieldaten")
        c1, c2, c3 = st.columns([1, 2, 2])
        with c1: 
            s = st.radio("Staffel:", ["Süd", "Nord"], horizontal=True, key="scout_staffel")
            t = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == s}
            to = {v["name"]: k for k, v in t.items()}
        with c2:
            idx = 0
            if "home_name" in st.session_state.game_meta and st.session_state.game_meta["home_name"] in to: idx = list(to.keys()).index(st.session_state.game_meta["home_name"])
            hn = st.selectbox("Heim:", list(to.keys()), index=idx, key="sel_home"); hid = to[hn]
            if "logo_h" not in st.session_state or st.session_state.game_meta.get("home_name") != hn: st.session_state.logo_h = optimize_image_base64(get_logo_url(hid, SEASON_ID))
            st.image(st.session_state.logo_h, width=80)
        with c3:
            idxg = 1
            if "guest_name" in st.session_state.game_meta and st.session_state.game_meta["guest_name"] in to: idxg = list(to.keys()).index(st.session_state.game_meta["guest_name"])
            gn = st.selectbox("Gast:", list(to.keys()), index=idxg, key="sel_guest"); gid = to[gn]
            if "logo_g" not in st.session_state or st.session_state.game_meta.get("guest_name") != gn: st.session_state.logo_g = optimize_image_base64(get_logo_url(gid, SEASON_ID))
            st.image(st.session_state.logo_g, width=80)
        st.write("---")
        idx_t = 0
        if st.session_state.game_meta.get("selected_target") == "Heimteam": idx_t = 1
        target = st.radio("Target:", ["Gastteam (Gegner)", "Heimteam"], horizontal=True, index=idx_t, key="sel_target") 
        tid = gid if target == "Gastteam (Gegner)" else hid
        c_d, c_t = st.columns(2)
        d_inp = c_d.date_input("Datum", date.today(), key="scout_date"); t_inp = c_t.time_input("Tip-Off", time(16,0), key="scout_time") 
        st.divider()
        cur_tid = st.session_state.get("current_tid")
        click_load = st.button(f"2. Kader von {target} laden", type="primary", key="load_scout")
        
        if click_load or (st.session_state.roster_df is None and cur_tid != tid) or (st.session_state.roster_df is not None and cur_tid != tid):
            with st.spinner("Lade Daten..."):
                df, ts = fetch_team_data(tid, SEASON_ID)
                if df is not None and not df.empty: 
                    st.session_state.roster_df = df; st.session_state.team_stats = ts; st.session_state.current_tid = tid 
                    st.session_state.game_meta = { "home_name": hn, "home_logo": st.session_state.logo_h, "guest_name": gn, "guest_logo": st.session_state.logo_g, "date": d_inp.strftime("%d.%m.%Y"), "time": t_inp.strftime("%H-%M"), "selected_target": target }
                    st.session_state.print_mode = False 
                else: st.error("Fehler API."); st.session_state.roster_df = pd.DataFrame(); st.session_state.team_stats = {}; st.session_state.game_meta = {} 
        elif st.session_state.roster_df is None or st.session_state.roster_df.empty: st.info("Bitte laden.")
        
        if st.session_state.roster_df is not None and not st.session_state.roster_df.empty: 
            st.subheader("3. Auswahl & Notizen")
            cols = { "select": st.column_config.CheckboxColumn("Auswahl", default=False, width="small"), "NR": st.column_config.TextColumn("#", width="small"), "NAME_FULL": st.column_config.TextColumn("Name"), "GP": st.column_config.NumberColumn("GP", format="%d"), "PPG": st.column_config.NumberColumn("PPG", format="%.1f"), "FG%": st.column_config.NumberColumn("FG%", format="%.1f %%"), "TOT": st.column_config.NumberColumn("REB", format="%.1f") }
            edited = st.data_editor(st.session_state.roster_df[["select", "NR", "NAME_FULL", "GP", "PPG", "FG%", "TOT"]], column_config=cols, disabled=["NR", "NAME_FULL", "GP", "PPG", "FG%", "TOT"], hide_index=True, key="player_table_scout") 
            sel_idx = edited[edited["select"]].index
            if len(sel_idx) > 0:
                st.divider()
                with st.form("scout_form", clear_on_submit=False): 
                    sel = st.session_state.roster_df.loc[sel_idx]; res = []; cmap = {"Grau": "#999999", "Grün": "#5c9c30", "Rot": "#d9534f"}
                    for i, (_, r) in enumerate(sel.iterrows()): 
                        pid = r["PLAYER_ID"]; c_h, c_c = st.columns([3, 1]); c_h.markdown(f"**#{r['NR']} {r['NAME_FULL']}**"); sc = st.session_state.saved_colors.get(pid, "Grau"); ix = list(cmap.keys()).index(sc) if sc in cmap else 0
                        col = c_c.selectbox("Farbe", list(cmap.keys()), key=f"c_{pid}_{i}", index=ix, label_visibility="collapsed") 
                        c1, c2 = st.columns(2); n = {}
                        for k in ["l1", "l2", "l3", "l4", "r1", "r2", "r3", "r4"]: val = st.session_state.saved_notes.get(f"{k}_{pid}", ""); n[k] = (c1 if k.startswith("l") else c2).text_input(k, value=val, key=f"n_{k}_{pid}_{i}", label_visibility="collapsed")
                        st.divider(); res.append({"row": r, "pid": pid, "color": col, "notes": n})
                    c1, c2, c3 = st.columns(3)
                    with c1: st.caption("Offense"); eo = st.data_editor(st.session_state.facts_offense, num_rows="dynamic", hide_index=True, key="eo_scout")
                    with c2: st.caption("Defense"); ed = st.data_editor(st.session_state.facts_defense, num_rows="dynamic", hide_index=True, key="ed_scout")
                    with c3: st.caption("About"); ea = st.data_editor(st.session_state.facts_about, num_rows="dynamic", hide_index=True, key="ea_scout")
                    up = st.file_uploader("Plays", accept_multiple_files=True, type=["png","jpg"], key="up_scout")
                    if st.form_submit_button("Generieren", type="primary"):
                        st.session_state.facts_offense = eo
                        st.session_state.facts_defense = ed
                        st.session_state.facts_about = ea
                        
                        for item in res:
                            st.session_state.saved_colors[item["pid"]] = item["color"]
                            for k, v in item["notes"].items():
                                st.session_state.saved_notes[f"{k}_{item['pid']}"] = v
                        
                        # --- KORREKTUR: Variablen gn/hn/target statt guest_name_selected etc. nutzen ---
                        tn = (gn if target == "Gastteam (Gegner)" else hn).replace(" ", "_")
                        
                        st.session_state.report_filename = f"Scouting_Report_{tn}_{d_inp.strftime('%d.%m.%Y')}.pdf"
                        
                        html = generate_header_html(st.session_state.game_meta)
                        html += generate_top3_html(st.session_state.roster_df)
                        
                        for item in res:
                            meta = get_player_metadata_cached(item["pid"])
                            html += generate_card_html(item["row"].to_dict(), meta, item["notes"], cmap[item["color"]])
                        
                        html += generate_team_stats_html(st.session_state.team_stats)
                        
                        # --- HIER LAG DER FEHLER (Einrückung beachten!) ---
                        if up:
                            html += "<div style='page-break-before:always'><h2>Plays</h2>"
                            for f in up:
                                b64 = base64.b64encode(f.getvalue()).decode()
                                # KORREKTUR: Hier stand vorher fälschlicherweise max-height:80px (vom Header kopiert)
                                # Jetzt: width:100% und height:auto für volle Breite und korrekte Proportionen
                                html += f"<div style='margin-bottom:20px; text-align:center;'><img src='data:image/png;base64,{b64}' style='width:100%; height:auto; border:1px solid #ccc;'></div>"
                        
                        html += generate_custom_sections_html(eo, ed, ea)
                        st.session_state.final_html = html
                        
                        if HAS_PDFKIT:
                            try:
                                opts = {
                                    "page-size": "A4", "orientation": "Portrait", 
                                    "margin-top": "5mm", "margin-right": "5mm", 
                                    "margin-bottom": "5mm", "margin-left": "5mm", 
                                    "encoding": "UTF-8", "zoom": "0.42", 
                                    "load-error-handling": "ignore", 
                                    "load-media-error-handling": "ignore", 
                                    "javascript-delay": "1000"
                                    "zoom": "0.6",
                                }
                                st.session_state.pdf_bytes = pdfkit.from_string(
                                    f"<!DOCTYPE html><html><head><meta charset='utf-8'>{CSS_STYLES}</head><body>{html}</body></html>", 
                                    False, options=opts
                                )
                                st.session_state.print_mode = True
                                st.rerun()
                            except Exception as e:
                                st.error(f"PDF Error: {e}")
                                st.session_state.pdf_bytes = None
                                st.session_state.print_mode = True
                                st.rerun()
                        else:
                            st.warning("PDFKit fehlt.")
                            st.session_state.pdf_bytes = None
                            st.session_state.print_mode = True
                            st.rerun()

# --- MAIN LOOP ---
if st.session_state.current_page == "home": render_home()
elif st.session_state.current_page == "scouting": render_scouting_page()
elif st.session_state.current_page == "comparison": render_comparison_page()
elif st.session_state.current_page == "analysis": render_analysis_page()
elif st.session_state.current_page == "player_comparison": render_player_comparison_page()
elif st.session_state.current_page == "game_venue": render_game_venue_page()
elif st.session_state.current_page == "prep": render_prep_page()
elif st.session_state.current_page == "live": render_live_page()
