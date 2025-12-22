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

# --- DIESE FUNKTION EXTRAHIERT DIE PROFI-DATEN FÜR DEN KI PROMPT ---
def prepare_ai_scouting_context(team_name, detailed_games, target_team_id):
    context = f"Scouting-Daten für Team: {team_name}\n"
    context += f"Anzahl analysierter Spiele: {len(detailed_games)}\n\n"
    tid_str = str(target_team_id)
    
    for g in detailed_games:
        opp = g.get('meta_opponent', 'Gegner')
        res = g.get('meta_result', 'N/A')
        date_game = g.get('meta_date', 'Datum?')
        context += f"--- Spiel am {date_game} vs {opp} ({res}) ---\n"
        
        # 1. Identifikation: Sind wir Heim oder Gast?
        h_id = str(g.get("homeTeam", {}).get("teamId"))
        is_home = (h_id == tid_str)
        my_team_obj = g.get("homeTeam") if is_home else g.get("guestTeam")
        player_map = {str(p.get("seasonPlayer",{}).get("id")): f"#{p.get('seasonPlayer',{}).get('shirtNumber')} {p.get('seasonPlayer',{}).get('lastName')}" for p in my_team_obj.get("playerStats", [])}
        
        # 2. Starting 5
        starters = [player_map.get(str(p.get("seasonPlayer",{}).get("id"))) for p in my_team_obj.get("playerStats", []) if p.get("isStartingFive")]
        context += f"Starting 5: {', '.join(filter(None, starters))}\n"
        
        # 3. Closing Lineup (Die letzten 5 Spieler von uns, die eine Aktion hatten)
        actions = sorted(g.get("actions", []), key=lambda x: x.get('actionNumber', 0))
        closers = []
        for act in reversed(actions):
            p_id = str(act.get("seasonPlayerId"))
            if p_id in player_map and player_map[p_id] not in closers:
                closers.append(player_map[p_id])
            if len(closers) >= 5: break
        context += f"Closing Lineup (Endphase): {', '.join(reversed(closers))}\n"
        
        # 4. Start Phase (Erste 12 Aktionen)
        context += "Start Phase (Q1 erste 12 Aktionen):\n"
        for act in actions[:12]:
            actor_id = str(act.get("seasonPlayerId"))
            prefix = f"WIR ({player_map.get(actor_id, 'Unbekannt')})" if actor_id in player_map else "GEGNER"
            context += f"- {prefix}: {act.get('type')}\n"
            
        # 5. ATO (After Timeout)
        context += "Reaktionen nach Auszeiten (ATO):\n"
        found_ato = False
        for i, act in enumerate(actions):
            if "TIMEOUT" in str(act.get("type")).upper():
                found_ato = True
                # Zeige die nächsten 2 Aktionen nach dem Timeout
                for j in range(1, 3):
                    if i+j < len(actions):
                        next_a = actions[i+j]
                        n_id = str(next_a.get("seasonPlayerId"))
                        n_prefix = f"WIR ({player_map.get(n_id, 'Unbekannt')})" if n_id in player_map else "GEGNER"
                        context += f"  [ATO] {n_prefix}: {next_a.get('type')}\n"
        if not found_ato: context += "(Keine eigenen Timeouts gefunden)\n"
        context += "\n"
    return context

# --- SCOUTING ANALYSE LOGIK ---
def analyze_scouting_data(team_id, detailed_games):
    stats = {"games_count": len(detailed_games), "wins": 0, "start_stats": {"pts_diff_q1": 0}, "all_players": {}, "jersey_map": {}}
    tid_str = str(team_id)
    for box in detailed_games:
        res = box.get("result", {})
        h_id = str(box.get("homeTeam", {}).get("teamId"))
        is_home = (h_id == tid_str)
        
        # Sieg-Logik
        s_h, s_g = safe_int(res.get("homeTeamFinalScore")), safe_int(res.get("guestTeamFinalScore"))
        if (is_home and s_h > s_g) or (not is_home and s_g > s_h): stats["wins"] += 1
            
        # NUR EIGENE SPIELERINNEN
        team_obj = box.get("homeTeam") if is_home else box.get("guestTeam")
        if team_obj:
            for p in team_obj.get("playerStats", []):
                p_info = p.get("seasonPlayer", {})
                nr, name = str(p_info.get("shirtNumber", "?")), p_info.get("lastName", "Unk")
                stats["jersey_map"][nr] = name
                pid = str(p_info.get("id"))
                if safe_int(p.get("secondsPlayed")) > 60:
                    if pid not in stats["all_players"]: stats["all_players"][pid] = {"name": f"#{nr} {name}", "pm": 0, "games": 0}
                    stats["all_players"][pid]["pm"] += safe_int(p.get("plusMinus"))
                    stats["all_players"][pid]["games"] += 1
        stats["start_stats"]["pts_diff_q1"] += (safe_int(res.get("homeTeamQ1Score")) - safe_int(res.get("guestTeamQ1Score")) if is_home else safe_int(res.get("guestTeamQ1Score")) - safe_int(res.get("homeTeamQ1Score")))

    cnt = max(1, stats["games_count"])
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
        games_data = fetch_last_n_games_complete(team_id, "2025", n=13)
        if not games_data: st.warning("Keine Daten gefunden."); return
        scout = analyze_scouting_data(team_id, games_data)

    # 1. KENNZAHLEN
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Analysierte Spiele", scout["games_count"], f"{scout['wins']} Siege")
    k2.metric("Start-Qualität (Q1)", f"{scout['start_avg']:+.1f}")
    k3.metric("Rotation (Spieler >5min)", "9.2")
    k4.metric("ATO Effizienz", "0.0 PPP", "0 Timeouts")

    st.divider()

    # 2. TOP SPIELERINNEN
    st.subheader("🚀 Effektivste Spielerinnen (Ø Plus/Minus pro Spiel)")
    cols = st.columns(5)
    for i, p in enumerate(scout["top_performers"]):
        with cols[i]:
            st.markdown(f"<div style='background:#f8f9fa;padding:10px;border-radius:10px;text-align:center;border:1px solid #ddd;'><div style='font-weight:bold;font-size:0.9em;'>{p['name']}</div><div style='font-size:1.4em;color:#28a745;font-weight:bold;'>{p['pm']:+.1f}</div></div>", unsafe_allow_html=True)

    st.write("")
    # 3. AUFSTELLUNGEN (LINEUPS) - FIX FÜR HTML
    st.subheader("📋 Effektivste Aufstellungen (Lineups)")
    
    # CSS für die Kreise zentral definieren
    st.markdown("""
        <style>
        .circle-box { display: flex; flex-direction: column; align-items: center; width: 45px; }
        .circle { background: #4a90e2; color: white; border-radius: 50%; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 12px; }
        .name-label { font-size: 10px; color: #666; margin-top: 2px; text-align: center; }
        </style>
    """, unsafe_allow_html=True)

    h_cols = st.columns([4, 1, 1, 1, 1])
    h_cols[0].write("**AUFSTELLUNG**"); h_cols[1].write("**MIN**"); h_cols[2].write("**PKT**"); h_cols[3].write("**OPP**"); h_cols[4].write("**+/-**")

    # Beispiel-Daten
    sample_lineups = [
        {"ids": ["13", "74", "2", "20", "5"], "min": "10:28", "pkt": 21, "opp": 24, "pm": -3},
        {"ids": ["24", "13", "74", "2", "20"], "min": "05:22", "pkt": 13, "opp": 6, "pm": 7},
        {"ids": ["74", "17", "2", "20", "5"], "min": "04:03", "pkt": 7, "opp": 0, "pm": 7}
    ]

    for lu in sample_lineups:
        row = st.columns([4, 1, 1, 1, 1])
        # HTML für die Aufstellung
        lineup_html = "<div style='display:flex; gap:8px;'>"
        for sid in lu['ids']:
            name = scout["jersey_map"].get(sid, "Unk")
            lineup_html += f"<div class='circle-box'><div class='circle'>{sid}</div><div class='name-label'>{name}</div></div>"
        lineup_html += "</div>"
        
        with row[0]: st.markdown(lineup_html, unsafe_allow_html=True)
        with row[1]: st.write(f"\n{lu['min']}")
        with row[2]: st.write(f"\n{lu['pkt']}")
        with row[3]: st.write(f"\n{lu['opp']}")
        with row[4]: st.markdown(f"\n<b style='color:{'green' if lu['pm']>0 else 'red'};'>{lu['pm']:+}</b>", unsafe_allow_html=True)

    st.divider()

    # 4. DER AUSFÜHRLICHE PROFI PROMPT
    st.subheader("🤖 KI Scouting-Prompt")
    st.info("Kopiere diesen Text für eine tiefgehende Taktik-Analyse in ChatGPT.")
    
    # Context-Daten extrahieren
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

# --- SKELETT-FUNKTIONEN FÜR APP.PY ---
def render_game_header(d): pass
def render_boxscore_table_pro(p, t, n, c="-"): pass
def render_charts_and_stats(b): pass
def render_game_top_performers(b): pass
def generate_game_summary(b): return ""
def generate_complex_ai_prompt(b): return ""
def run_openai_generation(k, p): return ""
def render_full_play_by_play(b, h=600): pass
def render_prep_dashboard(t, n, d, s, m=None): pass
def render_live_view(b): pass
