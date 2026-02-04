# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import pytz

# Importe aus deinen API- und Utility-Modulen
from src.api import get_player_metadata_cached, get_best_team_logo, fetch_last_n_games_complete
from src.utils import clean_pos

# --- KONSTANTEN & TRANSLATION ---
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
    text_upper = str(text).upper()
    return ACTION_TRANSLATION.get(text_upper, text.replace("_", " ").capitalize())

def safe_int(val):
    try: return int(float(val)) if val is not None else 0
    except: return 0

def safe_div(num, den):
    return round((num / den) * 100, 1) if den and den != 0 else 0.0

def get_team_name(team_data, default_name="Team"):
    if not team_data: return default_name
    name = team_data.get("name") or team_data.get("nameFull")
    if not name and "seasonTeam" in team_data:
        name = team_data["seasonTeam"].get("name")
    return name or default_name

def format_date_time(iso_string):
    if not iso_string: return "-"
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        berlin = pytz.timezone("Europe/Berlin")
        return dt.astimezone(berlin).strftime("%d.%m.%Y | %H:%M Uhr")
    except: return iso_string

# --- UI KOMPONENTEN FÜR APP.PY ---

def render_game_header(details):
    h_data, g_data = details.get("homeTeam", {}), details.get("guestTeam", {})
    h_name, g_name = get_team_name(h_data, "Heim"), get_team_name(g_data, "Gast")
    res = details.get("result", {})
    sh, sg = res.get("homeTeamFinalScore", 0), res.get("guestTeamFinalScore", 0)
    
    st.markdown(f"""
        <div style='text-align: center; background-color: #f8f9fa; padding: 20px; border-radius: 10px; border: 1px solid #ddd; margin-bottom: 20px;'>
            <div style='display: flex; justify-content: space-around; align-items: center;'>
                <div style='width: 40%;'><h2>{h_name}</h2></div>
                <div style='width: 20%;'><h1 style='font-size: 3em; margin: 0;'>{sh}:{sg}</h1></div>
                <div style='width: 40%;'><h2>{g_name}</h2></div>
            </div>
            <div style='color: #666; margin-top: 10px;'>{format_date_time(details.get("scheduledTime"))}</div>
        </div>
    """, unsafe_allow_html=True)

def render_boxscore_table_pro(player_stats, team_stats_official, team_name, coach_name="-"):
    if not player_stats:
        st.info(f"Keine Spielerdaten für {team_name} verfügbar.")
        return
    data = []
    for p in player_stats:
        info = p.get("seasonPlayer", {})
        data.append({
            "#": info.get('shirtNumber', '-'),
            "Name": f"{info.get('lastName','-')}, {info.get('firstName','')}",
            "Min": f"{safe_int(p.get('secondsPlayed'))//60:02d}:00",
            "PTS": p.get("points", 0),
            "REB": p.get("totalRebounds", 0),
            "AS": p.get("assists", 0),
            "ST": p.get("steals", 0),
            "TO": p.get("turnovers", 0),
            "PF": p.get("foulsCommitted", 0),
            "EFF": p.get("efficiency", 0)
        })
    st.markdown(f"#### {team_name} (HC: {coach_name})")
    st.dataframe(pd.DataFrame(data), hide_index=True, width="stretch")

def render_game_top_performers(box):
    st.subheader("Top Performer")
    c1, c2 = st.columns(2)
    for i, tkey in enumerate(["homeTeam", "guestTeam"]):
        with [c1, c2][i]:
            team_data = box.get(tkey, {})
            st.write(f"**{get_team_name(team_data)}**")
            p_stats = team_data.get("playerStats", [])
            if p_stats:
                top = sorted(p_stats, key=lambda x: safe_int(x.get("points")), reverse=True)[:3]
                for p in top:
                    st.write(f"- {p.get('seasonPlayer',{}).get('lastName')}: {p.get('points')} Pkt, {p.get('efficiency')} EFF")

def render_charts_and_stats(box):
    st.subheader("Team-Vergleich")
    h_stat = box.get("homeTeam", {}).get("gameStat", {})
    g_stat = box.get("guestTeam", {}).get("gameStat", {})
    stats = [("Punkte", "points"), ("Rebounds", "totalRebounds"), ("Assists", "assists"), ("Steals", "steals"), ("Turnover", "turnovers")]
    for label, key in stats:
        hv, gv = safe_int(h_stat.get(key)), safe_int(g_stat.get(key))
        total = hv + gv if (hv + gv) > 0 else 1
        st.write(f"**{label}**")
        c1, c2, c3 = st.columns([1, 4, 1])
        c1.write(hv)
        c2.progress(hv / total)
        c3.write(gv)

def render_full_play_by_play(box, height=500):
    actions = box.get("actions", [])
    if not actions:
        st.info("Keine Ticker-Daten vorhanden.")
        return
    data = []
    for a in sorted(actions, key=lambda x: x.get('actionNumber', 0), reverse=True):
        data.append({
            "Zeit": a.get("gameTime", "-"),
            "Team": "Heim" if a.get("homeTeamPoints") is not None else "Gast",
            "Aktion": translate_text(a.get("type")),
            "Score": f"{a.get('homeTeamPoints', 0)}:{a.get('guestTeamPoints', 0)}"
        })
    st.dataframe(pd.DataFrame(data), height=height, width="stretch", hide_index=True)

def render_prep_dashboard(team_id, team_name, df_roster, last_games, metadata_callback=None):
    st.title(f"Scouting Report: {team_name}")
    st.subheader("Top Scorer")
    st.dataframe(df_roster.sort_values("PPG", ascending=False)[["NR", "NAME_FULL", "PPG"]].head(5), hide_index=True)

def render_live_view(box):
    if not box: return
    render_game_header(box)
    t1, t2, t3 = st.tabs(["📋 Boxscore", "📊 Stats", "📜 Ticker"])
    with t1:
        render_game_top_performers(box)
        c1, c2 = st.columns(2)
        with c1: render_boxscore_table_pro(box.get("homeTeam",{}).get("playerStats"), {}, "Heim")
        with c2: render_boxscore_table_pro(box.get("guestTeam",{}).get("playerStats"), {}, "Gast")
    with t2: render_charts_and_stats(box)
    with t3: render_full_play_by_play(box)

def render_team_analysis_dashboard(team_id, team_name):
    st.subheader(f"Video- & Datenanalyse: {team_name}")
    games = fetch_last_n_games_complete(team_id, "2025", n=10)
    st.write(f"Analysiere {len(games)} Spiele der Saison...")

def generate_game_summary(box):
    return f"Spielzusammenfassung: {get_team_name(box.get('homeTeam'))} vs {get_team_name(box.get('guestTeam'))}"

def generate_complex_ai_prompt(box):
    return "KI-Prompt generiert..."

def run_openai_generation(api_key, prompt):
    return "KI Dienst ist momentan deaktiviert."

# --- PAGE WRAPPERS FÜR DEN ROUTER IN APP.PY ---

def render_analysis_page():
    st.title("🎥 Spielnachbereitung")
    st.info("Funktion wird geladen...")

def render_game_venue_page():
    st.title("📍 Spielorte & Hallen")
    st.info("Halleninformationen in Vorbereitung.")

def render_team_analysis_page():
    st.title("🧠 Team Spielanalyse")
    tid = st.session_state.get("stats_team_id")
    tname = st.session_state.get("selected_team_name", "Team")
    if tid:
        render_team_analysis_dashboard(tid, tname)
    else:
        st.info("Bitte wählen Sie zuerst ein Team unter 'Team Stats' aus.")
