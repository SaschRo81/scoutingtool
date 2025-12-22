# --- START OF FILE src/analysis_ui.py ---
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import pytz
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

# --- SCOUTING ANALYSE LOGIK ---

def analyze_scouting_data(team_id, detailed_games):
    """Analysiert Spiele auf Siege, Rotation und Start-Qualität."""
    stats = {
        "games_count": len(detailed_games),
        "wins": 0,
        "ato_stats": {"possessions": 0, "points": 0, "score_pct": 0},
        "start_stats": {"pts_diff_first_5min": 0},
        "all_player_stats": {},
        "rotation_depth": 0
    }
    
    tid_str = str(team_id)
    
    for box in detailed_games:
        # Sieg-Logik korrigiert (Vergleich Heim/Gast Punkte basierend auf Team-ID)
        res = box.get("result", {})
        h_id = str(box.get("homeTeam", {}).get("teamId"))
        g_id = str(box.get("guestTeam", {}).get("teamId"))
        
        s_h = safe_int(res.get("homeTeamFinalScore"))
        s_g = safe_int(res.get("guestTeamFinalScore"))
        
        is_home = (h_id == tid_str)
        if (is_home and s_h > s_g) or (not is_home and s_g > s_h):
            stats["wins"] += 1
            
        # Rotation & Spieler Aggregation
        team_obj = box.get("homeTeam") if is_home else box.get("guestTeam")
        if team_obj:
            players = team_obj.get("playerStats", [])
            active_this_game = 0
            for p in players:
                p_info = p.get("seasonPlayer", {})
                pid = str(p_info.get("id"))
                # Format: #Nummer Name
                p_display_name = f"#{p_info.get('shirtNumber', '?')} {p_info.get('lastName', 'Unbekannt')}"
                
                pts = safe_int(p.get("points"))
                sec = safe_int(p.get("secondsPlayed"))
                pm = safe_int(p.get("plusMinus"))
                
                if sec > 300: active_this_game += 1 # Mehr als 5 Min
                
                if pid not in stats["all_player_stats"]:
                    stats["all_player_stats"][pid] = {"name": p_display_name, "pts": 0, "games": 0, "pm_total": 0}
                
                stats["all_player_stats"][pid]["pts"] += pts
                stats["all_player_stats"][pid]["pm_total"] += pm
                stats["all_player_stats"][pid]["games"] += 1
            
            stats["rotation_depth"] += active_this_game

        # Start Qualität (Q1 Punkte-Differenz)
        q1_h = safe_int(res.get("homeTeamQ1Score"))
        q1_g = safe_int(res.get("guestTeamQ1Score"))
        stats["start_stats"]["pts_diff_first_5min"] += (q1_h - q1_g if is_home else q1_g - q1_h)

    # Averages
    cnt = stats["games_count"] if stats["games_count"] > 0 else 1
    stats["rotation_depth"] = round(stats["rotation_depth"] / cnt, 1)
    stats["start_avg"] = round(stats["start_stats"]["pts_diff_first_5min"] / cnt, 1)
    
    # Effektivste Spieler (nach Plus/Minus pro Spiel)
    eff_list = []
    for pid, d in stats["all_player_stats"].items():
        if d["games"] > 0:
            eff_list.append({
                "Spielerin": d["name"], 
                "PPG": round(d["pts"] / d["games"], 1), 
                "Avg +/-": round(d["pm_total"] / d["games"], 1)
            })
    stats["effective_5"] = sorted(eff_list, key=lambda x: x["Avg +/-"], reverse=True)[:5]

    return stats

# --- DASHBOARD RENDERING ---

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

    # 1. Key Metrics (Der gelbe Bereich)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Analysierte Spiele", scout["games_count"], f"{scout['wins']} Siege")
    k2.metric("Start-Qualität (Q1)", f"{scout['start_avg']:+.1f}", help="Vorsprung/Rückstand nach dem 1. Viertel")
    k3.metric("Rotation (Spieler >5min)", scout["rotation_depth"])
    k4.metric("ATO Effizienz", "0.0 PPP", "0 Timeouts", delta_color="off")

    st.divider()

    # 2. Die Effektivsten 5
    st.subheader("🚀 Effektivste 5 Spielerinnen (nach +/- Rating)")
    st.info("Diese Spielerinnen haben den größten positiven Einfluss auf den Punktestand, wenn sie auf dem Feld stehen.")
    
    if scout["effective_5"]:
        cols = st.columns(5)
        for i, player in enumerate(scout["effective_5"]):
            with cols[i]:
                st.markdown(f"""
                <div style="background-color:#f0f2f6; padding:10px; border-radius:10px; text-align:center;">
                    <div style="font-size:1.1em; font-weight:bold; color:#0e1117;">{player['Spielerin']}</div>
                    <div style="font-size:1.5em; color:#28a745;">{player['Avg +/-']:+.1f}</div>
                    <div style="font-size:0.8em; color:#666;">Avg +/- pro Spiel</div>
                </div>
                """, unsafe_allow_html=True)
    
    st.divider()

    # 3. Spiele & KI Prompt
    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("📅 Spiel-Historie")
        for g in games_data[:5]:
            st.write(f"**{g.get('meta_date')}** vs {g.get('meta_opponent')} ({g.get('meta_result')})")

    with col_right:
        st.subheader("🤖 KI Scouting Kontext")
        st.caption("Kopiere diesen Text für eine tiefe Taktik-Analyse in ChatGPT.")
        st.code(f"Analysiere Team {team_name}. Siege: {scout['wins']}/{scout['games_count']}. Top Lineup: {scout['effective_5'][0]['Spielerin'] if scout['effective_5'] else 'N/A'}", language="text")

# --- BESTEHENDE FUNKTIONEN (LIVE VIEW ETC.) ---
# ... (Hier folgen deine restlichen Funktionen wie render_live_view, render_full_play_by_play etc.)
# Diese bleiben unverändert erhalten.
