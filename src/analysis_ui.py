# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import pytz
from src.api import get_player_metadata_cached, get_best_team_logo, fetch_last_n_games_complete
from src.utils import clean_pos

# --- HELPERS ---
ACTION_TRANSLATION = {
    "TWO_POINT_SHOT_MADE": "2P Treffer", "TWO_POINT_SHOT_MISSED": "2P Fehl",
    "THREE_POINT_SHOT_MADE": "3P Treffer", "THREE_POINT_SHOT_MISSED": "3P Fehl",
    "FREE_THROW_MADE": "FW Treffer", "FREE_THROW_MISSED": "FW Fehl",
    "REBOUND": "Rebound", "FOUL": "Foul", "TURNOVER": "TO",
    "ASSIST": "Assist", "STEAL": "Steal", "BLOCK": "Block"
}

def translate_text(text):
    if not text: return ""
    return ACTION_TRANSLATION.get(str(text).upper(), str(text).replace("_", " ").capitalize())

def safe_int(val):
    try: return int(float(val)) if val is not None else 0
    except: return 0

def get_team_name(team_data, default_name="Team"):
    if not team_data: return default_name
    return team_data.get("name") or team_data.get("seasonTeam", {}).get("name") or default_name

# --- UI KOMPONENTEN ---

def render_game_header(details):
    h_data, g_data = details.get("homeTeam", {}), details.get("guestTeam", {})
    res = details.get("result", {})
    st.markdown(f"<h2 style='text-align:center;'>{get_team_name(h_data)} {res.get('homeTeamFinalScore',0)} : {res.get('guestTeamFinalScore',0)} {get_team_name(g_data)}</h2>", unsafe_allow_html=True)

def render_boxscore_table_pro(player_stats, team_stats_official, team_name, coach_name="-"):
    data = []
    for p in player_stats:
        info = p.get("seasonPlayer", {})
        data.append({
            "#": info.get('shirtNumber', '-'),
            "Name": f"{info.get('lastName','')} {info.get('firstName','')}",
            "PTS": p.get("points", 0), "REB": p.get("totalRebounds", 0), "AST": p.get("assists", 0)
        })
    st.markdown(f"**{team_name}**")
    st.dataframe(pd.DataFrame(data), hide_index=True, width="stretch")

def render_game_top_performers(box):
    st.subheader("Top Performer")
    st.write("Statistiken werden geladen...")

def render_charts_and_stats(box):
    st.subheader("Team Stats")
    st.info("Statistiken verfügbar, sobald Daten fließen.")

def render_full_play_by_play(box, height=400):
    actions = box.get("actions", [])
    if actions:
        df = pd.DataFrame([{"Zeit": a.get("gameTime"), "Aktion": translate_text(a.get("type"))} for a in actions])
        st.dataframe(df, height=height, width="stretch")

def render_prep_dashboard(team_id, team_name, df_roster, last_games, metadata_callback=None):
    st.title(f"Vorbereitung: {team_name}")

def render_live_view(box):
    if not box: return
    render_game_header(box)
    render_full_play_by_play(box)

def render_team_analysis_dashboard(team_id, team_name):
    st.subheader(f"Analyse: {team_name}")
    games = fetch_last_n_games_complete(team_id, "2025", n=5)
    st.write(f"{len(games)} Spiele gefunden.")

def generate_game_summary(box): return "Zusammenfassung..."
def generate_complex_ai_prompt(box): return "Prompt..."

# --- DIE MISSING WRAPPERS FÜR DEN ROUTER ---

def render_analysis_page():
    st.title("🎥 Spielnachbereitung")
    st.info("Funktion zur Video-Analyse.")

def render_game_venue_page():
    st.title("📍 Spielorte")
    st.write("Anfahrt und Halleninfos.")

def render_team_analysis_page():
    st.title("🧠 Team Spielanalyse")
    tid = st.session_state.get("stats_team_id")
    if tid:
        render_team_analysis_dashboard(tid, "Gewähltes Team")
    else:
        st.warning("Bitte wählen Sie zuerst ein Team unter 'Team Stats' aus.")
