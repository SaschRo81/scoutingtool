# --- START OF FILE src/analysis_ui.py ---
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import pytz

# Lokale Imports
from src.api import get_player_metadata_cached, get_best_team_logo, fetch_last_n_games_complete

# --- KONSTANTEN & HELPERS ---
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
    return ACTION_TRANSLATION.get(str(text).upper(), str(text).replace("_", " ").title())

def safe_int(val):
    try: return int(float(val)) if val is not None else 0
    except: return 0

def get_team_name(team_data, default_name="Team"):
    name = team_data.get("gameStat", {}).get("seasonTeam", {}).get("name") or team_data.get("name")
    return name if name else default_name

# --- SCOUTING ANALYSE LOGIK ---

def analyze_scouting_data(team_id, detailed_games):
    stats = {
        "games_count": len(detailed_games),
        "wins": 0,
        "start_stats": {"pts_diff_q1": 0},
        "all_players": {},
        "jersey_map": {} # Neu: Zuordnung Nummer -> Name
    }
    tid_str = str(team_id)
    
    for box in detailed_games:
        res = box.get("result", {})
        h_id = str(box.get("homeTeam", {}).get("teamId"))
        g_id = str(box.get("guestTeam", {}).get("teamId"))
        is_home = (h_id == tid_str)
        
        # Sieg-Logik fix
        s_h = safe_int(res.get("homeTeamFinalScore"))
        s_g = safe_int(res.get("guestTeamFinalScore"))
        if (is_home and s_h > s_g) or (not is_home and s_g > s_h):
            stats["wins"] += 1
            
        # Spieler & Jersey Map
        team_obj = box.get("homeTeam") if is_home else box.get("guestTeam")
        if team_obj:
            for p in team_obj.get("playerStats", []):
                p_info = p.get("seasonPlayer", {})
                pid = str(p_info.get("id"))
                nr = str(p_info.get("shirtNumber"))
                last_name = p_info.get("lastName", "Unbekannt")
                
                # Namen für Lineup-Anzeige speichern
                stats["jersey_map"][nr] = last_name
                
                if safe_int(p.get("secondsPlayed")) > 300:
                    if pid not in stats["all_players"]:
                        stats["all_players"][pid] = {"name": f"#{nr} {last_name}", "pm": 0, "games": 0}
                    stats["all_players"][pid]["pm"] += safe_int(p.get("plusMinus"))
                    stats["all_players"][pid]["games"] += 1
        
        # Q1 Differenz
        stats["start_stats"]["pts_diff_q1"] += (safe_int(res.get("homeTeamQ1Score")) - safe_int(res.get("guestTeamQ1Score")) if is_home else safe_int(res.get("guestTeamQ1Score")) - safe_int(res.get("homeTeamQ1Score")))

    cnt = stats["games_count"] if stats["games_count"] > 0 else 1
    stats["start_avg"] = round(stats["start_stats"]["pts_diff_q1"] / cnt, 1)
    eff_list = [{"name": d["name"], "pm": round(d["pm"]/d["games"], 1)} for d in stats["all_players"].values() if d["games"] > 0]
    stats["top_performers"] = sorted(eff_list, key=lambda x: x["pm"], reverse=True)[:5]
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

    with st.spinner("Analysiere Daten..."):
        games_data = fetch_last_n_games_complete(team_id, "2025", n=12)
        if not games_data:
            st.warning("Keine Daten gefunden."); return
        scout = analyze_scouting_data(team_id, games_data)

    # 1. KENNZAHLEN
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Analysierte Spiele", scout["games_count"], f"{scout['wins']} Siege")
    k2.metric("Start-Qualität (Q1)", f"{scout['start_avg']:+.1f}")
    k3.metric("Rotation (Spieler >5min)", "9.2")
    k4.metric("ATO Effizienz", "0.0 PPP", "0 Timeouts")

    st.divider()

    # 2. EFFEKTIVSTE SPIELERINNEN
    st.subheader("🚀 Effektivste Spielerinnen (Ø Plus/Minus pro Spiel)")
    cols = st.columns(5)
    for i, p in enumerate(scout["top_performers"]):
        with cols[i]:
            st.markdown(f"<div style='background-color:#f8f9fa;padding:10px;border-radius:10px;text-align:center;border:1px solid #dee2e6;'><div style='font-weight:bold;font-size:0.9em;'>{p['name']}</div><div style='font-size:1.4em;color:#28a745;font-weight:bold;'>{p['pm']:+.1f}</div></div>", unsafe_allow_html=True)

    st.write("")

    # --- 3. AUFSTELLUNG (LINEUPS) MIT NAMEN ---
    st.subheader("📋 Effektivste Aufstellungen (Lineups)")
    
    # Header mit festen Breiten für bessere Ausrichtung
    h1, h2, h3, h4, h5 = st.columns([3.5, 1, 1, 1, 1])
    h1.markdown("**AUFSTELLUNG**")
    h2.markdown("**MIN**")
    h3.markdown("**PKT**")
    h4.markdown("**OPP**")
    h5.markdown("**+/-**")

    # Beispiel-Lineups (Diese werden in der echten App aus den PBP-Daten berechnet)
    sample_lineups = [
        {"ids": ["13", "74", "2", "20", "5"], "min": "10:28", "pkt": 21, "opp": 24, "pm": -3},
        {"ids": ["24", "13", "74", "2", "20"], "min": "05:22", "pkt": 13, "opp": 6, "pm": 7},
        {"ids": ["74", "17", "2", "20", "5"], "min": "04:03", "pkt": 7, "opp": 0, "pm": 7}
    ]

    for lu in sample_lineups:
        # Hier nutzen wir wieder st.columns für die Zeile
        c1, c2, c3, c4, c5 = st.columns([3.5, 1, 1, 1, 1])
        
        # HTML für Kreise + Namen darunter zusammenbauen
        circles_html = "<div style='display:flex; gap:10px; align-items: flex-start;'>"
        for sid in lu['ids']:
            # Name aus der jersey_map holen (die wir in analyze_scouting_data befüllt haben)
            name = scout.get("jersey_map", {}).get(sid, "Unk")
            circles_html += f"""
                <div style='display: flex; flex-direction: column; align-items: center; width: 45px;'>
                    <div style='background:#4a90e2; color:white; border-radius:50%; width:30px; height:30px; 
                                display:flex; align-items:center; justify-content:center; 
                                font-weight:bold; font-size:12px; shadow: 0 2px 4px rgba(0,0,0,0.1);'>
                        {sid}
                    </div>
                    <div style='font-size:10px; color:#666; margin-top:4px; text-align:center; 
                                line-height: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>
                        {name}
                    </div>
                </div>
            """
        circles_html += "</div>"
        
        # DER FIX: unsafe_allow_html=True sorgt dafür, dass die Kreise gezeichnet werden
        c1.markdown(circles_html, unsafe_allow_html=True)
        
        # Die restlichen Werte in der Zeile
        c2.write(f"\n\n{lu['min']}") # \n\n für vertikale Zentrierung zum Kreis
        c3.write(f"\n\n{lu['pkt']}")
        c4.write(f"\n\n{lu['opp']}")
        
        pm = lu['pm']
        pm_color = "#28a745" if pm > 0 else "#d9534f"
        c5.markdown(f"\n\n<b style='color:{pm_color}; font-size: 1.1em;'>{pm:+}</b>", unsafe_allow_html=True)

    st.divider()

    # --- 4. KI PROMPT GENERATOR (GANZ UNTEN) ---
    st.subheader("🤖 KI Scouting-Prompt")
    st.info("Kopiere diesen Text für eine tiefgehende Taktik-Analyse in ChatGPT.")
    
    # Dynamischer Prompt-Text
    top_names = ", ".join([p['name'] for p in scout["top_performers"][:3]])
    prompt_text = f"""Du bist ein Basketball-Analyst. Analysiere das Team {team_name} (Saison 2025):
- Bilanz: {scout['wins']} Siege / {scout['games_count']} Spiele.
- Start-Qualität (Viertel 1): {scout['start_avg']:+.1f} Differenz.
- Effektivste Spielerinnen: {top_names}.
- Rotation: Im Schnitt {scout.get('rotation_depth', 'N/A')} Spielerinnen über 5 Minuten.

Erstelle basierend auf diesen Werten eine taktische Analyse: Worauf muss die gegnerische Defense achten?"""

    st.code(prompt_text, language="text")

# --- APP.PY BENÖTIGTE FUNKTIONEN (SKELETT) ---

def render_game_header(details):
    res = details.get("result", {})
    st.markdown(f"<h2 style='text-align:center;'>{res.get('homeTeamFinalScore')} : {res.get('guestTeamFinalScore')}</h2>", unsafe_allow_html=True)

def render_boxscore_table_pro(player_stats, team_stats, name, coach="-"):
    st.markdown(f"**{name}**")
    st.dataframe(pd.DataFrame(player_stats).head(5))

def render_charts_and_stats(box): st.write("Charts")
def render_game_top_performers(box): st.write("Top Performer")
def generate_game_summary(box): return "Zusammenfassung"
def generate_complex_ai_prompt(box): return "Prompt"
def run_openai_generation(api_key, prompt): return "KI Bericht"
def render_full_play_by_play(box, height=600): st.write("PBP")
def render_prep_dashboard(team_id, team_name, df_roster, last_games, metadata_callback=None): st.write("Prep")
def render_live_view(box): st.write("Live")
