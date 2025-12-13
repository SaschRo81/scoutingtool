# --- START OF FILE app.py ---

import streamlit as st
import pandas as pd
import datetime
import base64
import altair as alt

# Externe Imports prüfen
try:
    import pdfkit
    HAS_PDFKIT = True
except ImportError:
    HAS_PDFKIT = False

# Module aus SRC
from src.config import VERSION, TEAMS_DB, SEASON_ID, CSS_STYLES
from src.utils import get_logo_url, optimize_image_base64
from src.api import fetch_team_data, get_player_metadata_cached, fetch_schedule, fetch_game_boxscore, fetch_game_details
from src.html_gen import (
    generate_header_html, generate_top3_html, generate_card_html, 
    generate_team_stats_html, generate_custom_sections_html,
    generate_comparison_html
)
from src.state_manager import export_session_state, load_session_state
# HIER NEU: generate_game_summary importieren
from src.analysis_ui import (
    render_game_header, render_boxscore_table_pro, render_charts_and_stats, 
    get_team_name, render_game_top_performers, generate_game_summary
)

st.set_page_config(page_title=f"DBBL Scouting Suite {VERSION}", layout="wide", page_icon="🏀")

# --- SESSION STATE ---
# ... (wie bisher) ...
for key, default in [
    ("current_page", "home"),
    # ... restliche keys ...
    ("selected_game_id", None)
]:
    if key not in st.session_state: st.session_state[key] = default

# --- NAVIGATIONS-HELFER ---
def go_home(): st.session_state.current_page = "home"; st.session_state.print_mode = False
def go_scouting(): st.session_state.current_page = "scouting"
def go_comparison(): st.session_state.current_page = "comparison"
def go_analysis(): st.session_state.current_page = "analysis"
# NEU:
def go_player_comparison(): st.session_state.current_page = "player_comparison"

# ==========================================
# SEITE 1: HOME (UPDATE)
# ==========================================
def render_home():
    st.markdown("<h1 style='text-align: center;'>🏀 DBBL Scouting Suite by Sascha Rosanke</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center; color: gray;'>Version {VERSION}</p>", unsafe_allow_html=True)
    st.write(""); st.write("")
    c1, c2, c3 = st.columns([3, 2, 3])
    with c2:
        st.markdown("<style>div.stButton > button:first-child { width: 100%; height: 3em; font-size: 18px; margin-bottom: 10px; }</style>", unsafe_allow_html=True)
        if st.button("📊 Teamvergleich"): go_comparison(); st.rerun()
        if st.button("🤼 Spielervergleich"): go_player_comparison(); st.rerun() # NEU
        if st.button("📝 Scouting Report"): go_scouting(); st.rerun()
        if st.button("🎥 Spielnachbereitung"): go_analysis(); st.rerun()

# ==========================================
# NEU: SEITE - SPIELERVERGLEICH
# ==========================================
def render_player_comparison_page():
    st.button("🏠 Zurück zum Start", on_click=go_home)
    st.title("🤼 Head-to-Head Spielervergleich")

    col_left, col_mid, col_right = st.columns([1, 0.1, 1])

    # --- LINKE SEITE (SPIELER A) ---
    with col_left:
        st.subheader("Spieler A")
        staffel_a = st.radio("Staffel A", ["Süd", "Nord"], horizontal=True, key="pc_s_a")
        teams_a = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == staffel_a}
        t_name_a = st.selectbox("Team", list({v["name"]: k for k, v in teams_a.items()}.keys()), key="pc_t_a")
        tid_a = {v["name"]: k for k, v in teams_a.items()}[t_name_a]
        
        # Daten laden (Cached)
        df_a, _ = fetch_team_data(tid_a, SEASON_ID)
        
        if df_a is not None:
            p_opts_a = df_a["NAME_FULL"].tolist()
            p_name_a = st.selectbox("Spieler", p_opts_a, key="pc_p_a")
            # Zeile extrahieren
            row_a = df_a[df_a["NAME_FULL"] == p_name_a].iloc[0]
            
            # Bild
            meta_a = get_player_metadata_cached(row_a["PLAYER_ID"])
            if meta_a["img"]:
                st.image(meta_a["img"], width=150)
        else:
            st.error("Daten nicht geladen")
            row_a = None

    with col_mid:
        st.write("") # Spacer

    # --- RECHTE SEITE (SPIELER B) ---
    with col_right:
        st.subheader("Spieler B")
        staffel_b = st.radio("Staffel B", ["Süd", "Nord"], horizontal=True, key="pc_s_b")
        teams_b = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == staffel_b}
        t_name_b = st.selectbox("Team", list({v["name"]: k for k, v in teams_b.items()}.keys()), key="pc_t_b")
        tid_b = {v["name"]: k for k, v in teams_b.items()}[t_name_b]
        
        df_b, _ = fetch_team_data(tid_b, SEASON_ID)
        
        if df_b is not None:
            p_opts_b = df_b["NAME_FULL"].tolist()
            p_name_b = st.selectbox("Spieler", p_opts_b, key="pc_p_b")
            row_b = df_b[df_b["NAME_FULL"] == p_name_b].iloc[0]
            
            meta_b = get_player_metadata_cached(row_b["PLAYER_ID"])
            if meta_b["img"]:
                st.image(meta_b["img"], width=150)
        else:
            row_b = None

    st.divider()

    # --- VERGLEICH ---
    if row_a is not None and row_b is not None:
        metrics = [
            ("Spiele (GP)", "GP", int),
            ("Punkte (PPG)", "PPG", float),
            ("Minuten", "MIN_DISPLAY", str),
            ("FG %", "FG%", float),
            ("3er %", "3PCT", float),
            ("Freiwurf %", "FTPCT", float),
            ("Rebounds (RPG)", "TOT", float),
            ("Assists (APG)", "AS", float),
            ("Turnovers (TO)", "TO", float),
            ("Steals (ST)", "ST", float),
            ("Blocks (BS)", "BS", float),
            ("Fouls (PF)", "PF", float)
        ]

        st.markdown(f"#### Vergleich: {p_name_a} vs. {p_name_b}")
        
        # Tabelle bauen
        data = []
        for label, col, dtype in metrics:
            val_a = row_a[col]
            val_b = row_b[col]
            
            # Formatierung für Anzeige
            disp_a = val_a
            disp_b = val_b
            
            # Differenz und Farbe (nur für Zahlen)
            diff_display = ""
            bg_style = ""
            
            if dtype in [int, float] and col != "PF" and col != "TO":
                if float(val_a) > float(val_b):
                    diff_display = "◀" 
                elif float(val_b) > float(val_a):
                    diff_display = "▶"
            
            data.append({
                "Kategorie": label,
                t_name_a: disp_a,
                " ": diff_display,
                t_name_b: disp_b
            })

        df_comp = pd.DataFrame(data)
        st.table(df_comp)

        # Kleines Chart für PPG, REB, AST
        try:
            chart_data = pd.DataFrame({
                "Kategorie": ["PPG", "RPG", "APG"] * 2,
                "Wert": [row_a["PPG"], row_a["TOT"], row_a["AS"], row_b["PPG"], row_b["TOT"], row_b["AS"]],
                "Spieler": [p_name_a]*3 + [p_name_b]*3
            })
            
            c = alt.Chart(chart_data).mark_bar().encode(
                x=alt.X('Kategorie', axis=None),
                y=alt.Y('Wert'),
                color='Spieler',
                column='Kategorie'
            ).properties(height=250)
            st.altair_chart(c, use_container_width=True)
        except:
            pass

# ==========================================
# SEITE 3: SPIELNACHBEREITUNG (UPDATE)
# ==========================================
def render_analysis_page():
    st.button("🏠 Zurück zum Start", on_click=go_home)
    st.title("🎥 Spielnachbereitung")
    
    # ... (Selektoren Code bleibt gleich bis zum Button "Analyse laden") ...
    c1, c2 = st.columns([1, 2])
    with c1:
        staffel = st.radio("Staffel", ["Süd", "Nord"], horizontal=True, key="ana_staffel")
        teams_filtered = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == staffel}
        team_options = {v["name"]: k for k, v in teams_filtered.items()}
    with c2:
        my_team_name = st.selectbox("Dein Team:", list(team_options.keys()), key="ana_team")
        my_team_id = team_options[my_team_name]

    if my_team_id:
        games = fetch_schedule(my_team_id, SEASON_ID)
        if games:
            game_opts = {f"{g['date']} | {g['home']} vs {g['guest']} ({g['score']})": g['id'] for g in games}
            selected_label = st.selectbox("Wähle ein Spiel:", list(game_opts.keys()), key="ana_game_select")
            selected_id = game_opts[selected_label]
            
            if st.button("Analyse laden", type="primary"):
                st.session_state.selected_game_id = selected_id
                
            if st.session_state.selected_game_id == selected_id:
                st.divider()
                
                with st.spinner("Lade Boxscore & Details..."):
                    box = fetch_game_boxscore(selected_id)
                    details = fetch_game_details(selected_id)
                    
                    if box and details:
                        # Merge Data
                        box["venue"] = details.get("venue")
                        box["result"] = details.get("result")
                        box["referee1"] = details.get("referee1")
                        box["referee2"] = details.get("referee2")
                        box["referee3"] = details.get("referee3")
                        box["scheduledTime"] = details.get("scheduledTime")
                        box["attendance"] = details.get("result", {}).get("spectators")
                        
                        render_game_header(box)

                        # --- NEU: AUTOMATISCHER SPIELBERICHT ---
                        with st.expander("📝 Automatischer Spielbericht (KI-Generiert)", expanded=False):
                            report_text = generate_game_summary(box)
                            st.markdown(report_text)
                            st.caption("Text kopieren und für Presseberichte anpassen.")
                        # ---------------------------------------
                        
                        st.write("")
                        # Rest der Analyse Seite
                        h_name = get_team_name(box.get("homeTeam", {}), "Heim")
                        g_name = get_team_name(box.get("guestTeam", {}), "Gast")
                        h_coach = box.get("homeTeam", {}).get("headCoachName", "-")
                        g_coach = box.get("guestTeam", {}).get("headCoachName", "-")
                        
                        render_boxscore_table_pro(box.get("homeTeam", {}).get("playerStats", []), h_name, h_coach)
                        st.write("")
                        render_boxscore_table_pro(box.get("guestTeam", {}).get("playerStats", []), g_name, g_coach)
                        st.divider()
                        render_game_top_performers(box)
                        st.divider()
                        render_charts_and_stats(box)
                    # ... Error Handling wie im Original ...
                    elif box:
                         render_game_header(box)
                         # ...
                    elif details:
                         render_game_header(details)
                         # ...
                    else:
                        st.error("Konnte Spieldaten nicht laden.")
        else:
            st.warning("Keine Spiele gefunden.")


# ==========================================
# HAUPT STEUERUNG (UPDATE)
# ==========================================
if st.session_state.current_page == "home": render_home()
elif st.session_state.current_page == "scouting": render_scouting_page()
elif st.session_state.current_page == "comparison": render_comparison_page()
elif st.session_state.current_page == "analysis": render_analysis_page()
elif st.session_state.current_page == "player_comparison": render_player_comparison_page() # NEU
