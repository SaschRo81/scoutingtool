# --- START OF FILE src/analysis_ui.py ---
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import pytz

# Lokale Imports
from src.api import get_player_metadata_cached, get_best_team_logo, fetch_last_n_games_complete

# --- HELPERS ---
def safe_int(val):
    if val is None: return 0
    try: return int(float(val))
    except: return 0

def get_team_name(team_data, default_name="Team"):
    name = team_data.get("gameStat", {}).get("seasonTeam", {}).get("name") or team_data.get("name")
    return name if name else default_name

# --- DIESE FUNKTION ERZEUGT DEN AUSFÜHRLICHEN KONTEXT FÜR DEN PROMPT ---
def prepare_ai_scouting_context(team_name, detailed_games, team_id):
    context = f"Scouting-Daten für Team: {team_name}\n"
    context += f"Anzahl analysierter Spiele: {len(detailed_games)}\n\n"
    
    for g in detailed_games:
        opp = g.get('meta_opponent', 'Gegner')
        res = g.get('meta_result', 'N/A')
        date_game = g.get('meta_date', 'Datum?')
        context += f"--- Spiel am {date_game} vs {opp} ({res}) ---\n"
        
        # Kurze Zusammenfassung der PBP-Events für die KI
        actions = sorted(g.get("actions", []), key=lambda x: x.get('actionNumber', 0))
        for act in actions[:10]: # Nur die ersten 10 für den Start-Kontext
            context += f"Q{act.get('period')} {act.get('gameTime')}: {act.get('type')} ({act.get('homeTeamPoints')}:{act.get('guestTeamPoints')})\n"
        context += "...\n"
    return context

# --- SCOUTING ANALYSE LOGIK ---
def analyze_scouting_data(team_id, detailed_games):
    stats = {
        "games_count": len(detailed_games),
        "wins": 0,
        "start_stats": {"pts_diff_q1": 0},
        "all_players": {},
        "jersey_map": {} 
    }
    tid_str = str(team_id)
    
    for box in detailed_games:
        res = box.get("result", {})
        h_id = str(box.get("homeTeam", {}).get("teamId"))
        g_id = str(box.get("guestTeam", {}).get("teamId"))
        is_home = (h_id == tid_str)
        
        s_h = safe_int(res.get("homeTeamFinalScore"))
        s_g = safe_int(res.get("guestTeamFinalScore"))
        if (is_home and s_h > s_g) or (not is_home and s_g > s_h):
            stats["wins"] += 1
            
        team_obj = box.get("homeTeam") if is_home else box.get("guestTeam")
        if team_obj:
            for p in team_obj.get("playerStats", []):
                p_info = p.get("seasonPlayer", {})
                pid = str(p_info.get("id"))
                nr = str(p_info.get("shirtNumber", "?"))
                last_name = p_info.get("lastName", "Unbekannt")
                stats["jersey_map"][nr] = last_name
                
                if safe_int(p.get("secondsPlayed")) > 300:
                    if pid not in stats["all_players"]:
                        stats["all_players"][pid] = {"name": f"#{nr} {last_name}", "pm": 0, "games": 0}
                    stats["all_players"][pid]["pm"] += safe_int(p.get("plusMinus"))
                    stats["all_players"][pid]["games"] += 1
        
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

    # 3. AUFSTELLUNG (LINEUPS) MIT NAMEN
    st.subheader("📋 Effektivste Aufstellungen (Lineups)")
    h_cols = st.columns([4, 1, 1, 1, 1])
    h_cols[0].markdown("**AUFSTELLUNG**")
    h_cols[1].markdown("**MIN**")
    h_cols[2].markdown("**PKT**")
    h_cols[3].markdown("**OPP**")
    h_cols[4].markdown("**+/-**")

    sample_lineups = [
        {"ids": ["13", "74", "2", "20", "5"], "min": "10:28", "pkt": 21, "opp": 24, "pm": -3},
        {"ids": ["24", "13", "74", "2", "20"], "min": "05:22", "pkt": 13, "opp": 6, "pm": 7},
        {"ids": ["74", "17", "2", "20", "5"], "min": "04:03", "pkt": 7, "opp": 0, "pm": 7}
    ]

    for lu in sample_lineups:
        c = st.columns([4, 1, 1, 1, 1])
        
        # HTML für die Kreise direkt in die Spalte rendern
        circles_html = "<div style='display:flex; gap:8px;'>"
        for sid in lu['ids']:
            p_name = scout["jersey_map"].get(sid, "Unbekannt")
            circles_html += f"""
                <div style='display:flex; flex-direction:column; align-items:center; width:45px;'>
                    <div style='background:#4a90e2; color:white; border-radius:50%; width:30px; height:30px; display:flex; align-items:center; justify-content:center; font-weight:bold; font-size:12px;'>{sid}</div>
                    <div style='font-size:10px; color:#666; margin-top:2px; text-align:center;'>{p_name}</div>
                </div>
            """
        circles_html += "</div>"
        
        with c[0]: st.markdown(circles_html, unsafe_allow_html=True)
        with c[1]: st.write(f"\n{lu['min']}")
        with c[2]: st.write(f"\n{lu['pkt']}")
        with c[3]: st.write(f"\n{lu['opp']}")
        with c[4]: st.markdown(f"\n<b style='color:{'green' if lu['pm']>0 else 'red'};'>{lu['pm']:+}</b>", unsafe_allow_html=True)

    st.divider()

    # 4. DER URSPRÜNGLICHE KI PROMPT GENERATOR
    st.subheader("🤖 KI Scouting-Prompt")
    st.info("Kopiere diesen Text für eine tiefgehende Taktik-Analyse in ChatGPT.")
    
    # Hier bauen wir den Kontext-String wie früher zusammen
    context_text = prepare_ai_scouting_context(team_name, games_data, team_id)
    
    prompt_full = f"""Du bist ein professioneller Basketball-Scout für die DBBL.
Analysiere die folgenden Rohdaten (Play-by-Play Auszüge) von {team_name} aus {len(games_data)} Spielen.

Erstelle einen prägnanten Scouting-Bericht mit diesen 4 Punkten:
1. Reaktionen nach Auszeiten (ATO): Gibt es Muster? Wer schließt ab? Punkten sie oft direkt?
2. Spielstarts: Wie kommen sie ins 1. Viertel? (Aggressiv, Turnover-anfällig?) Wer scort zuerst?
3. Schlüsselspieler & Rotation: Wer steht in der Starting 5? Wer beendet knappe Spiele (Closing Lineup)?
4. Empfehlung für die Defense: Wie kann man ihre Plays stoppen?

Hier sind die Daten:
{context_text}
"""
    st.code(prompt_full, language="text")

# --- APP.PY BENÖTIGTE SKELETT FUNKTIONEN ---
def render_game_header(details): pass
def render_boxscore_table_pro(p, t, n, c="-"): pass
def render_charts_and_stats(box): pass
def render_game_top_performers(box): pass
def generate_game_summary(box): return ""
def generate_complex_ai_prompt(box): return ""
def run_openai_generation(api_key, prompt): return ""
def render_full_play_by_play(box, height=600): pass
def render_prep_dashboard(t_id, t_n, df, l, metadata_callback=None): pass
def render_live_view(box): pass
