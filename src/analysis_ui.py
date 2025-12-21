import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import pytz
import openai 
from src.api import fetch_team_rank 

ACTION_TRANSLATION = {
    "TWO_POINT_SHOT_MADE": "2P Treffer", "TWO_POINT_SHOT_MISSED": "2P Fehl",
    "THREE_POINT_SHOT_MADE": "3P Treffer", "THREE_POINT_SHOT_MISSED": "3P Fehl",
    "FREE_THROW_MADE": "FW Treffer", "FREE_THROW_MISSED": "FW Fehl",
    "REBOUND": "Rebound", "FOUL": "Foul", "TURNOVER": "TO",
    "ASSIST": "Assist", "STEAL": "Steal", "BLOCK": "Block",
    "SUBSTITUTION": "Wechsel", "TIMEOUT": "Auszeit"
}

def translate_text(text):
    if not text: return ""
    return ACTION_TRANSLATION.get(str(text).upper(), str(text).replace("_", " ").capitalize())

def safe_int(val):
    try: return int(float(val)) if val is not None else 0
    except: return 0

def get_team_name(team_data, default_name="Team"):
    n = team_data.get("gameStat", {}).get("seasonTeam", {}).get("name") or team_data.get("name")
    return n if n else default_name

def render_full_play_by_play(box, height=600):
    actions = box.get("actions", [])
    if not actions: return st.info("Keine PBP Daten.")
    data = []
    for act in sorted(actions, key=lambda x: x.get('actionNumber', 0), reverse=True):
        data.append({
            "Zeit": f"Q{act.get('period')} {act.get('gameTime', '-')}",
            "Score": f"{act.get('homeTeamPoints',0)}:{act.get('guestTeamPoints',0)}",
            "Aktion": translate_text(act.get("type"))
        })
    st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True, height=height)

def render_game_header(details):
    res = details.get("result", {})
    st.markdown(f"<h1 style='text-align:center;'>{res.get('homeTeamFinalScore')} : {res.get('guestTeamFinalScore')}</h1>", unsafe_allow_html=True)

def render_boxscore_table_pro(player_stats, team_stats, name, coach="-"):
    st.markdown(f"**{name}**")
    st.dataframe(pd.DataFrame(player_stats).head(12), use_container_width=True)

def render_charts_and_stats(box):
    st.write("Statistiken & Diagramme werden geladen...")

def render_game_top_performers(box):
    st.write("Top Performer Übersicht")

def generate_game_summary(box):
    return "Automatischer Spielbericht wird basierend auf den Boxscore-Daten generiert."

def generate_complex_ai_prompt(box):
    return "KI Prompt für detaillierte Analyse..."

def run_openai_generation(api_key, prompt):
    return "KI Service ist bereit."

def render_prep_dashboard(opp_id, opp_name, df, sched, metadata_callback=None):
    st.subheader(f"Vorbereitung gegen {opp_name}")
    st.dataframe(df.head(10), use_container_width=True)

def render_live_view(box):
    res = box.get("result", {})
    st.markdown(f"## Live: {res.get('homeTeamFinalScore', 0)} : {res.get('guestTeamFinalScore', 0)}")
