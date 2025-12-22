# --- START OF FILE src/analysis_ui.py ---
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import pytz
import openai # Falls für run_openai_generation benötigt

# Lokale Imports
from src.api import get_player_metadata_cached, get_best_team_logo, fetch_last_n_games_complete

# --- KONSTANTEN & HELPERS ---
ACTION_TRANSLATION = {
    "TWO_POINT_SHOT_MADE": "2P Treffer", "TWO_POINT_SHOT_MISSED": "2P Fehl",
    "THREE_POINT_SHOT_MADE": "3P Treffer", "THREE_POINT_SHOT_MISSED": "3P Fehl",
    "FREE_THROW_MADE": "FW Treffer", "FREE_THROW_MISSED": "FW Fehl",
    "REBOUND": "Rebound", "FOUL": "Foul", "TURNOVER": "TO",
    "ASSIST": "Assist", "STEAL": "Steal", "BLOCK": "Block",
    "SUBSTITUTION": "Wechsel", "TIMEOUT": "Auszeit",
    "JUMP_BALL": "Sprungball", "START": "Start", "END": "Ende",
    "offensive": "Off", "defensive": "Def"
}

def translate_text(text):
    if not text: return ""
    text_upper = str(text).upper()
    if text_upper in ACTION_TRANSLATION: return ACTION_TRANSLATION[text_upper]
    return text.replace("_", " ").title()

def safe_int(val):
    if val is None: return 0
    try: return int(float(val))
    except: return 0

def get_team_name(team_data, default_name="Team"):
    name = team_data.get("gameStat", {}).get("seasonTeam", {}).get("name")
    if name: return name
    name = team_data.get("seasonTeam", {}).get("name")
    if name: return name
    return team_data.get("name", default_name)

def format_date_time(iso_string):
    if not iso_string: return "-"
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        berlin = pytz.timezone("Europe/Berlin")
        return dt.astimezone(berlin).strftime("%d.%m.%Y | %H:%M Uhr")
    except: return iso_string

def get_player_lookup(box):
    lookup = {}
    for team_key in ['homeTeam', 'guestTeam']:
        for p in box.get(team_key, {}).get('playerStats', []):
            pid = str(p.get('seasonPlayer', {}).get('id'))
            name = f"{p.get('seasonPlayer', {}).get('lastName', '')}" 
            nr = p.get('seasonPlayer', {}).get('shirtNumber', '')
            lookup[pid] = f"#{nr} {name}"
    return lookup

def get_player_team_lookup(box):
    lookup = {}
    h_name = get_team_name(box.get("homeTeam", {}), "Heim")
    g_name = get_team_name(box.get("guestTeam", {}), "Gast")
    for p in box.get("homeTeam", {}).get('playerStats', []):
        pid = str(p.get('seasonPlayer', {}).get('id'))
        lookup[pid] = h_name
    for p in box.get("guestTeam", {}).get('playerStats', []):
        pid = str(p.get('seasonPlayer', {}).get('id'))
        lookup[pid] = g_name
    return lookup

def convert_elapsed_to_remaining(time_str, period):
    if not time_str: return "-"
    base_minutes = 10
    try:
        if int(period) > 4: base_minutes = 5
    except: pass
    try:
        parts = time_str.split(":")
        sec = 0
        if len(parts) == 3: sec = int(parts[0])*3600 + int(parts[1])*60 + int(parts[2])
        elif len(parts) == 2: sec = int(parts[0])*60 + int(parts[1])
        else: return time_str
        rem = (base_minutes * 60) - sec
        if rem < 0: rem = 0
        return f"{rem // 60:02d}:{rem % 60:02d}"
    except: return time_str

# --- SCOUTING ANALYSE FUNKTIONEN (GELBER BEREICH FIX) ---

def analyze_scouting_data(team_id, detailed_games):
    stats = {
        "games_count": len(detailed_games),
        "wins": 0,
        "ato_stats": {"possessions": 0, "points": 0},
        "start_stats": {"pts_diff_first_5min": 0},
        "all_players": {},
        "rotation_depth": 0
    }
    tid_str = str(team_id)
    for box in detailed_games:
        # 1. Sieg-Logik korrigiert (Vergleich Punkte via Team-ID)
        res = box.get("result", {})
        h_id = str(box.get("homeTeam", {}).get("teamId"))
        g_id = str(box.get("guestTeam", {}).get("teamId"))
        s_h = safe_int(res.get("homeTeamFinalScore"))
        s_g = safe_int(res.get("guestTeamFinalScore"))
        is_home = (h_id == tid_str)
        if (is_home and s_h > s_g) or (not is_home and s_g > s_h):
            stats["wins"] += 1
            
        # 2. Rotation & Spieler (Format: #Nummer Name)
        team_obj = box.get("homeTeam") if is_home else box.get("guestTeam")
        if team_obj:
            players = team_obj.get("playerStats", [])
            active_count = 0
            for p in players:
                p_info = p.get("seasonPlayer", {})
                pid = str(p_info.get("id"))
                nr = p_info.get("shirtNumber", "?")
                last_name = p_info.get("lastName", "Unbekannt")
                p_display_name = f"#{nr} {last_name}"
                
                sec = safe_int(p.get("secondsPlayed"))
                if sec > 300: active_count += 1 
                
                if pid not in stats["all_players"]:
                    stats["all_players"][pid] = {"name": p_display_name, "pts": 0, "pm": 0, "games": 0}
                stats["all_players"][pid]["pts"] += safe_int(p.get("points"))
                stats["all_players"][pid]["pm"] += safe_int(p.get("plusMinus"))
                stats["all_players"][pid]["games"] += 1
            stats["rotation_depth"] += active_count

        # 3. Start-Qualität (Q1)
        q1_h = safe_int(res.get("homeTeamQ1Score"))
        q1_g = safe_int(res.get("guestTeamQ1Score"))
        stats["start_stats"]["pts_diff_first_5min"] += (q1_h - q1_g if is_home else q1_g - q1_h)

    cnt = stats["games_count"] if stats["games_count"] > 0 else 1
    stats["rotation_depth"] = round(stats["rotation_depth"] / cnt, 1)
    stats["start_avg"] = round(stats["start_stats"]["pts_diff_first_5min"] / cnt, 1)
    eff_list = [{"name": d["name"], "ppg": round(d["pts"]/d["games"], 1), "pm": round(d["pm"]/d["games"], 1)} 
                for d in stats["all_players"].values() if d["games"] > 0]
    stats["top_performers"] = sorted(eff_list, key=lambda x: x["pm"], reverse=True)[:5]
    return stats

def render_team_analysis_dashboard(team_id, team_name):
    logo = get_best_team_logo(team_id)
    c1, c2 = st.columns([1, 4])
    with c1:
        if logo: st.image(logo, width=100)
    with c2:
        st.title(f"Scouting Report: {team_name}")
        st.caption("Basierend auf der Play-by-Play Analyse der gesamten Saison")

    with st.spinner("Analysiere Spieldaten..."):
        games_data = fetch_last_n_games_complete(team_id, "2025", n=50)
        if not games_data:
            st.warning("Keine Daten gefunden."); return
        scout = analyze_scouting_data(team_id, games_data)

    k1, k2, k3, k4 = st.columns(4)
    with k1: st.metric("Analysierte Spiele", scout["games_count"], f"{scout['wins']} Siege")
    with k2: st.metric("Start-Qualität (Q1)", f"{scout['start_avg']:+.1f}")
    with k3: st.metric("Rotation (Spieler >5min)", scout["rotation_depth"])
    with k4: st.metric("ATO Effizienz", "0.0 PPP", "0 Timeouts", delta_color="off")

    st.divider()
    st.subheader("🚀 Effektivste Spielerinnen (Ø Plus/Minus pro Spiel)")
    if scout["top_performers"]:
        cols = st.columns(5)
        for idx, player in enumerate(scout["top_performers"]):
            with cols[idx]:
                st.markdown(f"<div style='background-color:#f8f9fa;padding:10px;border-radius:10px;text-align:center;border:1px solid #dee2e6;'><div style='font-weight:bold;'>{player['name']}</div><div style='font-size:1.4em;color:#28a745;'>{player['pm']:+.1f}</div></div>", unsafe_allow_html=True)

# --- UI FUNKTIONEN FÜR APP.PY ---

def render_game_header(details):
    res = details.get("result", {})
    h_name = get_team_name(details.get("homeTeam", {}))
    g_name = get_team_name(details.get("guestTeam", {}))
    st.markdown(f"<h2 style='text-align:center;'>{h_name} {res.get('homeTeamFinalScore')} : {res.get('guestTeamFinalScore')} {g_name}</h2>", unsafe_allow_html=True)

def render_boxscore_table_pro(player_stats, team_stats, team_name, coach="-"):
    df = pd.DataFrame([{"#": p.get("seasonPlayer",{}).get("shirtNumber"), "Name": p.get("seasonPlayer",{}).get("lastName"), "PTS": p.get("points"), "REB": p.get("totalRebounds"), "AST": p.get("assists")} for p in player_stats])
    st.markdown(f"**{team_name}** (Coach: {coach})")
    st.dataframe(df, hide_index=True, use_container_width=True)

def render_charts_and_stats(box):
    st.info("Charts & erweiterte Team-Stats")

def render_game_top_performers(box):
    st.info("Top Performer des Spiels")

def generate_game_summary(box):
    return "Kurze Zusammenfassung des Spielverlaufs..."

def generate_complex_ai_prompt(box):
    return "ChatGPT Prompt Kontext..."

def run_openai_generation(api_key, prompt):
    return "KI Antwort Platzhalter"

def render_full_play_by_play(box, height=600):
    actions = box.get("actions", [])
    df = pd.DataFrame([{"Zeit": a.get("gameTime"), "Aktion": translate_text(a.get("type")), "Score": f"{a.get('homeTeamPoints')}:{a.get('guestTeamPoints')}"} for a in actions])
    st.dataframe(df.iloc[::-1], height=height, use_container_width=True, hide_index=True)

def render_prep_dashboard(team_id, team_name, df_roster, last_games, metadata_callback=None):
    st.subheader(f"Vorbereitung: {team_name}")
    st.dataframe(df_roster[["NR", "NAME_FULL", "PPG"]].head(5), hide_index=True)

def create_live_boxscore_df(team_data):
    players = team_data.get("playerStats", [])
    return pd.DataFrame([{"#": p.get("seasonPlayer",{}).get("shirtNumber"), "Name": p.get("seasonPlayer",{}).get("lastName"), "PTS": p.get("points")} for p in players])

def render_live_view(box):
    res = box.get("result", {})
    st.title(f"LIVE: {res.get('homeTeamFinalScore')} : {res.get('guestTeamFinalScore')}")
    render_full_play_by_play(box, height=400)
