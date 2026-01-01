# --- START OF FILE src/analysis_ui.py ---
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import time

# --- HELPER FUNCTIONS ---

def safe_int(val):
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0

def get_team_name(team_obj, default_name):
    """Safely extracts team name from a team dictionary."""
    if not team_obj:
        return default_name
    return team_obj.get("name", default_name)

# --- UI COMPONENTS ---

def render_game_header(box):
    """Renders the top scoreboard header for a game."""
    if not box:
        st.error("Keine Spieldaten übergeben.")
        return

    home = box.get("homeTeam", {})
    guest = box.get("guestTeam", {})
    
    # Extract scores safely
    res = box.get("result", {})
    h_score = res.get("homeScore") if res.get("homeScore") is not None else "-"
    g_score = res.get("guestScore") if res.get("guestScore") is not None else "-"
    
    # Layout
    c1, c2, c3 = st.columns([2, 1, 2])
    with c1:
        st.markdown(f"<h2 style='text-align:center; color: #333;'>{home.get('name', 'Heim')}</h2>", unsafe_allow_html=True)
        st.markdown(f"<h1 style='text-align:center; font-size: 3.5em; margin:0;'>{h_score}</h1>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div style='text-align:center; padding-top: 30px; font-weight:bold; color:#888;'>vs</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='text-align:center; font-size: 0.8em; color:#666;'>{box.get('scheduledTime', '')}</div>", unsafe_allow_html=True)
        if box.get("period"):
             st.markdown(f"<div style='text-align:center; color:#d9534f;'>Q{box.get('period')}</div>", unsafe_allow_html=True)
    with c3:
        st.markdown(f"<h2 style='text-align:center; color: #333;'>{guest.get('name', 'Gast')}</h2>", unsafe_allow_html=True)
        st.markdown(f"<h1 style='text-align:center; font-size: 3.5em; margin:0;'>{g_score}</h1>", unsafe_allow_html=True)

    # Venue Info
    if box.get("venue"):
        v = box.get("venue")
        st.caption(f"📍 {v.get('name', '')}, {v.get('address', '')}")

def render_boxscore_table_pro(player_stats, game_stats, team_name, coach_name):
    """Renders a detailed stats table for a team."""
    st.markdown(f"### {team_name}")
    if coach_name and coach_name != "-":
        st.caption(f"Head Coach: {coach_name}")
        
    if not player_stats:
        st.info("Keine Spielerstatistiken verfügbar.")
        return

    data = []
    for p in player_stats:
        pl = p.get("seasonPlayer", {})
        row = {
            "#": pl.get("shirtNumber", ""),
            "Name": pl.get("name", "Unknown"),
            "MIN": p.get("minutes", "00:00"),
            "PTS": p.get("points", 0),
            "FG": f"{p.get('fieldGoalsMade',0)}/{p.get('fieldGoalsAttempted',0)}",
            "3P": f"{p.get('threePointsMade',0)}/{p.get('threePointsAttempted',0)}",
            "FT": f"{p.get('freeThrowsMade',0)}/{p.get('freeThrowsAttempted',0)}",
            "REB": p.get("reboundsTotal", 0),
            "AST": p.get("assists", 0),
            "STL": p.get("steals", 0),
            "BLK": p.get("blocks", 0),
            "TO": p.get("turnovers", 0),
            "PF": p.get("foulsPersonal", 0),
            "+/-": p.get("plusMinus", 0)
        }
        data.append(row)
    
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df, hide_index=True, use_container_width=True)

def render_charts_and_stats(box):
    """Renders charts (placeholder logic)."""
    st.subheader("📊 Wurfverteilung & Trends")
    st.info("Hier könnten Shooting-Charts oder Scoring-Runs visualisiert werden (erfordert Play-by-Play Analyse).")

def render_game_top_performers(box):
    """Displays top scorer for home and guest."""
    st.subheader("🔥 Top Performer")
    c1, c2 = st.columns(2)
    
    h_stats = box.get("homeTeam", {}).get("playerStats", [])
    g_stats = box.get("guestTeam", {}).get("playerStats", [])
    
    with c1:
        if h_stats:
            top = max(h_stats, key=lambda x: x.get("points", 0))
            name = top.get("seasonPlayer", {}).get("name", "?")
            st.metric(f"Top {box.get('homeTeam', {}).get('name')}", f"{name}", f"{top.get('points')} PTS")
            
    with c2:
        if g_stats:
            top = max(g_stats, key=lambda x: x.get("points", 0))
            name = top.get("seasonPlayer", {}).get("name", "?")
            st.metric(f"Top {box.get('guestTeam', {}).get('name')}", f"{name}", f"{top.get('points')} PTS")

def generate_game_summary(box):
    """Generates a simple text summary string."""
    h = box.get("homeTeam", {}).get("name")
    g = box.get("guestTeam", {}).get("name")
    res = box.get("result", {})
    return f"**Zusammenfassung:** Spiel zwischen {h} und {g}. Endstand {res.get('homeScore',0)}:{res.get('guestScore',0)}."

def generate_complex_ai_prompt(box):
    """Generates a prompt for AI analysis."""
    return "Erstelle einen Spielbericht basierend auf den Boxscore-Daten..."

def run_openai_generation(prompt):
    """Mock function for AI generation."""
    return "AI-Modul ist nicht aktiv."

def render_full_play_by_play(box):
    """Renders the Play-by-Play list."""
    actions = box.get("actions", [])
    if not actions:
        st.info("Keine Play-by-Play Daten verfügbar.")
        return

    # Sort descending by action number
    actions = sorted(actions, key=lambda x: x.get('actionNumber', 0), reverse=True)

    st.markdown("### Play-by-Play (Ticker)")
    
    # Convert to DataFrame for cleaner look
    pbp_data = []
    for a in actions:
        pbp_data.append({
            "Q": a.get("period"),
            "Time": a.get("gameTime"),
            "Score": f"{a.get('homeTeamPoints')}:{a.get('guestTeamPoints')}",
            "Team": "Home" if str(a.get("seasonTeamId")) == str(box.get("homeTeam",{}).get("teamId")) else "Guest",
            "Action": a.get("actionType"),
            "Detail": a.get("subType") or ""
        })
    
    if pbp_data:
        st.dataframe(pd.DataFrame(pbp_data), use_container_width=True, hide_index=True)

def render_prep_dashboard(opp_id, opp_name, df, sched, metadata_callback=None):
    """Renders the preparation dashboard."""
    st.subheader(f"Gegner-Analyse: {opp_name}")
    st.dataframe(df, use_container_width=True)
    st.write("Matchups und letzte Spiele:")
    if sched:
        st.json(sched[:3]) # Show last 3 games raw as example

def render_live_view(box):
    """Renders the live view page content."""
    render_game_header(box)
    st.divider()
    t1, t2 = st.tabs(["Boxscore", "Live Ticker"])
    with t1:
        c1, c2 = st.columns(2)
        with c1:
            render_boxscore_table_pro(box.get("homeTeam", {}).get("playerStats", []), {}, box.get("homeTeam", {}).get("name"), "-")
        with c2:
            render_boxscore_table_pro(box.get("guestTeam", {}).get("playerStats", []), {}, box.get("guestTeam", {}).get("name"), "-")
    with t2:
        render_full_play_by_play(box)

# --- ANALYTICS LOGIC ---

def calculate_real_lineups(team_id, detailed_games):
    """
    Berechnet Lineup-Statistiken basierend auf PBP-Daten.
    Korrigiert automatisch fehlende Wechsel, wenn Spieler Aktionen ausführen.
    """
    lineup_stats = {}
    tid_str = str(team_id)

    for box in detailed_games:
        actions = sorted(box.get("actions", []), key=lambda x: x.get('actionNumber', 0))
        h_id = str(box.get("homeTeam", {}).get("teamId"))
        is_home = (h_id == tid_str)
        
        # Start-Aufstellung ermitteln
        my_team_obj = box.get("homeTeam") if is_home else box.get("guestTeam")
        starters = [str(p.get("seasonPlayer",{}).get("id")) for p in my_team_obj.get("playerStats", []) if p.get("isStartingFive")]
        
        # Fallback, falls keine Starter markiert sind: Nimm die ersten 5 Spieler aus den Stats
        if len(starters) < 5:
             all_players = [str(p.get("seasonPlayer",{}).get("id")) for p in my_team_obj.get("playerStats", [])]
             starters = all_players[:5]

        current_lineup = set(starters)
        
        last_time_total_secs = 0
        last_h_score = 0
        last_g_score = 0

        for act in actions:
            # Zeit in Sekunden berechnen
            raw_time = act.get("gameTime", "00:00")
            try:
                parts = raw_time.split(':')
                m, s = int(parts[-2]), int(parts[-1])
                # (Periode - 1) * 10 Minuten * 60 Sekunden + abgelaufene Zeit im Viertel
                # Achtung: PBP Zeit läuft oft RUNTER. DBBL API ist oft "played time". 
                # Annahme hier: gameTime steigt an (00:00 -> 10:00).
                current_time_total_secs = (act.get("period", 1)-1)*600 + (m*60 + s)
            except: 
                current_time_total_secs = last_time_total_secs

            # AUTOMATISCHE KORREKTUR: Spieler mit Aktion MUSS auf dem Feld sein
            act_pid = str(act.get("seasonPlayerId"))
            act_tid = str(act.get("seasonTeamId"))
            
            if act_tid == tid_str and act_pid and act_pid != "None":
                if act_pid not in current_lineup:
                    # Heuristik: Wenn wir >5 haben, entfernen wir einen (den wir nicht wissen). 
                    # Hier einfach: Wenn voll, nimm einen raus, damit der aktive rein kann.
                    if len(current_lineup) >= 5:
                        current_lineup.pop() 
                    current_lineup.add(act_pid)

            # Statistik für aktuelles Lineup (nur wenn 5 Spieler)
            if len(current_lineup) == 5:
                l_key = tuple(sorted(list(current_lineup)))
                if l_key not in lineup_stats:
                    lineup_stats[l_key] = {"secs": 0, "pts_for": 0, "pts_agn": 0}
                
                duration = max(0, current_time_total_secs - last_time_total_secs)
                lineup_stats[l_key]["secs"] += duration
                
                # Score Deltas
                cur_h = safe_int(act.get("homeTeamPoints"))
                cur_g = safe_int(act.get("guestTeamPoints"))
                
                if is_home:
                    diff_for = max(0, cur_h - last_h_score)
                    diff_agn = max(0, cur_g - last_g_score)
                else:
                    diff_for = max(0, cur_g - last_g_score)
                    diff_agn = max(0, cur_h - last_h_score)

                lineup_stats[l_key]["pts_for"] += diff_for
                lineup_stats[l_key]["pts_agn"] += diff_agn

            # State update
            last_time_total_secs = current_time_total_secs
            last_h_score = safe_int(act.get("homeTeamPoints"))
            last_g_score = safe_int(act.get("guestTeamPoints"))

            # Wechsel verarbeiten
            if act.get("type") == "SUBSTITUTION" and str(act.get("seasonTeamId")) == tid_str:
                p_out = str(act.get("seasonPlayerId"))
                p_in = str(act.get("relatedSeasonPlayerId"))
                if p_out in current_lineup: 
                    current_lineup.remove(p_out)
                if p_in and p_in != "None": 
                    current_lineup.add(p_in)

    # Ergebnisse filtern
    final_lineups = []
    for ids, data in lineup_stats.items():
        if data["secs"] > 60: # Nur Lineups mit >1 Minute Spielzeit
            final_lineups.append({
                "ids": list(ids),
                "min": f"{data['secs']//60:02d}:{data['secs']%60:02d}",
                "pkt": data["pts_for"],
                "opp": data["pts_agn"],
                "pm": data["pts_for"] - data["pts_agn"]
            })
    
    # Sortieren nach Plus/Minus
    return sorted(final_lineups, key=lambda x: x["pm"], reverse=True)[:5]

def render_team_analysis_dashboard(tid, t_name):
    """
    Dashboard Entry Point für Team-Analyse.
    Lädt Daten on-demand, um Imports zu entkoppeln.
    """
    # Import hier, um Zirkelbezug zu vermeiden, da app.py beide importiert
    from src.api import fetch_season_games, fetch_game_details
    
    st.subheader(f"Deep Dive Analyse: {t_name}")
    st.info("Hinweis: Diese Analyse lädt die detaillierten Play-by-Play Daten der letzten Spiele. Dies kann einen Moment dauern.")
    
    if st.button("Analyse starten"):
        with st.spinner("Lade Spieldaten & berechne Lineups..."):
            games = fetch_season_games(tid, "2025")
            detailed = []
            if games:
                # Nur Spiele mit Ergebnis nehmen
                played = [g for g in games if g.get('has_result')]
                # Wir nehmen max. die letzten 3 Spiele für die Demo, um API Limits zu schonen
                target_games = played[:3] 
                
                for g in target_games:
                    gid = g['id']
                    d = fetch_game_details(gid)
                    if d: detailed.append(d)
            
            if detailed:
                lineups = calculate_real_lineups(tid, detailed)
                if lineups:
                    st.success(f"Top Lineups (basierend auf {len(detailed)} Spielen)")
                    cols = st.columns(3)
                    for i, l in enumerate(lineups[:3]):
                        with cols[i]:
                            st.markdown(f"**#{i+1} PM: {l['pm']:+d}**")
                            st.caption(f"Min: {l['min']} | {l['pkt']} : {l['opp']}")
                            # Hier könnte man IDs zu Namen mappen, wenn man das Roster hat
                            st.code(", ".join(l['ids']))
                else:
                    st.warning("Keine stabilen Lineups gefunden.")
            else:
                st.error("Keine detaillierten Spieldaten gefunden.")
