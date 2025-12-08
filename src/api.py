import streamlit as st
import pandas as pd
import datetime
import base64

# ... (deine Imports bleiben gleich) ...
from src.config import VERSION, TEAMS_DB, SEASON_ID, CSS_STYLES
from src.utils import get_logo_url, optimize_image_base64
from src.api import fetch_team_data, get_player_metadata_cached
from src.html_gen import (
    generate_header_html, generate_top3_html, generate_card_html, 
    generate_team_stats_html, generate_custom_sections_html
)
# NEU: Import des State Managers
from src.state_manager import export_session_state, load_session_state

st.set_page_config(page_title=f"DBBL Scouting {VERSION}", layout="wide", page_icon="🏀")

# --- SESSION STATE INITIALISIERUNG ---
# (Dieser Block bleibt genau wie er war) ... 
for key, default in [
    ("print_mode", False), ("final_html", ""), ("pdf_bytes", None),
    ("roster_df", None), ("team_stats", None), ("game_meta", {}),
    ("report_filename", "scouting_report.pdf"), ("saved_notes", {}), ("saved_colors", {}),
    ("facts_offense", pd.DataFrame([{"Fokus": "Run", "Beschreibung": "fastbreaks & quick inbounds"}])),
    ("facts_defense", pd.DataFrame([{"Fokus": "Rebound", "Beschreibung": "box out!"}])),
    ("facts_about", pd.DataFrame([{"Fokus": "Energy", "Beschreibung": "100% effort"}]))
]:
    if key not in st.session_state: st.session_state[key] = default


# --- NEU: SIDEBAR FÜR SPEICHERN / LADEN ---
with st.sidebar:
    st.header("💾 Spielstand")
    
    # 1. LADEN
    uploaded_state = st.file_uploader("Alten Stand laden (JSON)", type=["json"])
    if uploaded_state:
        if st.button("Daten wiederherstellen"):
            success, msg = load_session_state(uploaded_state)
            if success:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
    
    st.divider()
    
    # 2. SPEICHERN
    # Nur anzeigen, wenn wir schon Daten haben
    if st.session_state.roster_df is not None:
        json_data = export_session_state()
        file_name = f"Savegame_{datetime.date.today()}.json"
        st.download_button(
            label="💾 Aktuellen Stand sichern",
            data=json_data,
            file_name=file_name,
            mime="application/json"
        )

# --- ANSICHT: BEARBEITUNG ---
if not st.session_state.print_mode:
    # ... (ab hier dein ganz normaler Code wie vorher) ...
    st.title(f"🏀 DBBL Scouting Pro {VERSION}")
    # ...
