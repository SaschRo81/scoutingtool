import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import time

# Helper function used in your snippet
def safe_int(val):
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0

def get_team_name(team_obj, default_name):
    return team_obj.get("name", default_name) if team_obj else default_name

# --- 1. GAME HEADER & SUMMARY ---
def render_game_header(box):
    """Renders the top scoreboard and game info."""
    home = box.get("homeTeam", {})
    guest = box.get("guestTeam", {})
    
    # Simple scoreboard layout
    c1, c2, c3 = st.columns([2, 1, 2])
    with c1:
        st.markdown(f"<h2 style='text-align:center'>{home.get('name', 'Home')}</h2>", unsafe_allow_html=True)
        st.markdown(f"<h1 style='text-align:center; font-size: 3em;'>{box.get('result', {}).get('homeScore', '-')}</h1>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div style='text-align:center; padding-top: 20px;'>vs</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='text-align:center'>{box.get('scheduledTime', '')}</div>", unsafe_allow_html=True)
    with c3:
        st.markdown(f"<h2 style='text-align:center'>{guest.get('name', 'Guest')}</h2>", unsafe_allow_html=True)
        st.markdown(f"<h1 style='text-align:center; font-size: 3em;'>{box.get('result', {}).get('guestScore', '-')}</h1>", unsafe_allow_html=True)

    # Meta info
    if box.get("venue"):
        st.caption(f"📍 {box['venue'].get('name', '')}, {box['venue'].get('address', '')}")

def generate_game_summary(box):
    """Generates a short text summary (placeholder for logic)."""
    h_score = safe_int(box.get("result", {}).get("homeScore"))
    g_score = safe_int(box.get("result", {}).get("guestScore"))
    winner = box.get("homeTeam", {}).get("name") if h_score > g_score else box.get("guestTeam", {}).get("name")
    return f"**Endstand:** {h_score}:{g_score}. Sieger: {winner}. Zuschauer: {box.get('attendance', 'k.A.')}."

def generate_complex_ai_prompt(box):
    """Generates a string prompt for AI analysis."""
    return f"Analysiere das Spiel {box.get('homeTeam',{}).get('name')} vs {box.get('guestTeam',{}).get('name')}. Ergebnis: {box.get('result',{}).get('homeScore')}:{box.get('result',{}).get('guestScore')}."

def run_openai_generation(prompt):
    # Placeholder for OpenAI call
    return "AI Feature not configured."

# --- 2. BOXSCORE & STATS ---
def render_boxscore_table_pro(player_stats, team_stats, team_name, coach_name):
    """Renders a detailed dataframe for player stats."""
    st.subheader(f"{team_name} (Coach: {coach_name})")
    if not player_stats:
        st.info("Keine Spielerstatistiken verfügbar.")
        return

    # Flatten data for DataFrame
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
    
    df = pd.DataFrame(data)
    st.dataframe(df, hide_index=True, use_container_width=True)

def render_game_top_performers(box):
    """Simple view for top scorers."""
    st.subheader("Top Performer")
    c1, c2 = st.columns(2)
    # Simplified logic: find max points in lists
    h_stats = box.get("homeTeam", {}).get("playerStats", [])
    g_stats = box.get("guestTeam", {}).get("playerStats", [])
    
    if h_stats:
        top_h = max(h_stats, key=lambda x: x.get("points", 0))
        c1.metric(f"Top {box['homeTeam']['name']}", f"{top_h.get('seasonPlayer',{}).get('name')} ({top_h['points']} Pts)")
    if g_stats:
        top_g = max(g_stats, key=lambda x: x.get("points", 0))
        c2.metric(f"Top {box['guestTeam']['name']}", f"{top_g.get('seasonPlayer',{}).get('name')} ({top_g['points']} Pts)")

def render_charts_and_stats(box):
    """Placeholder for charts."""
    st.write("📊 Erweiterte Diagramme (Shooting Charts, Flow) hier.")

def render_full_play_by_play(box):
    """Renders PBP list."""
    actions = box.get("actions", [])
    if not actions:
        st.info("Kein Play-by-Play verfügbar.")
        return
    
    # Sort by action number desc
    actions = sorted(actions, key=lambda x: x.get('actionNumber', 0), reverse=True)
    
    st.subheader(f"Play-by-Play ({len(actions)} Aktionen)")
    for a in actions[:50]: # Show last 50
        time_str = f"Q{a.get('period')} {a.get('gameTime')}"
        score = f"{a.get('homeTeamPoints')}:{a.get('guestTeamPoints')}"
        text = a.get('actionType', 'Action')
        st.text(f"{time_str} | {score} | {text}")
    if len(actions) > 50:
        st.caption("... ältere Aktionen ausgeblendet.")

# --- 3. LIVE & PREP ---
def render_live_view(box):
    """Renders the live view for the game center."""
    render_game_header(box)
    st.divider()
    
    t1, t2 = st.tabs(["Boxscore", "Play-by-Play"])
    with t1:
        hn = box.get("homeTeam", {}).get("name")
        gn = box.get("guestTeam", {}).get("name")
        render_boxscore_table_pro(box.get("homeTeam", {}).get("playerStats", []), {}, hn, "HC")
        render_boxscore_table_pro(box.get("guestTeam", {}).get("playerStats", []), {}, gn, "HC")
    with t2:
        render_full_play_by_play(box)

def render_prep_dashboard(opp_id, opp_name, df, sched, metadata_callback):
    """Renders the scouting preparation dashboard."""
    st.title(f"Scouting: {opp_name}")
    st.dataframe(df, use_container_width=True)
    st.caption("Hier können detaillierte Matchups und Video-Links hinzugefügt werden.")

# --- 4. ADVANCED TEAM ANALYSIS (Lineups) ---
def calculate_real_lineups(team_id, detailed_games):
    """
    Intelligenter Lineup-Tracker: 
    Verarbeitet Wechsel UND korrigiert die Aufstellung automatisch.
    """
    lineup_stats = {}
    tid_str = str(team_id)

    for box in detailed_games:
        actions = sorted(box.get("actions", []), key=lambda x: x.get('actionNumber', 0))
        h_id = str(box.get("homeTeam", {}).get("teamId"))
        is_home = (h_id == tid_str)
        
        my_team_obj = box.get("homeTeam") if is_home else box.get("guestTeam")
        starters = [str(p.get("seasonPlayer",{}).get("id")) for p in my_team_obj.get("playerStats", []) if p.get("isStartingFive")]
        
        current_lineup = set(starters[:5])
        last_time_total_secs = 0
        last_h_score = 0
        last_g_score = 0

        for act in actions:
            raw_time = act.get("gameTime", "00:00")
            try:
                parts = raw_time.split(':')
                m, s = int(parts[-2]), int(parts[-1])
                current_time_total_secs = (act.get("period", 1)-1)*600 + (m*60 + s)
            except: 
                current_time_total_secs = last_time_total_secs

            act_pid = str(act.get("seasonPlayerId"))
            act_tid = str(act.get("seasonTeamId"))
            
            if act_tid == tid_str and act_pid and act_pid != "None":
                if act_pid not in current_lineup:
                    if len(current_lineup) >= 5:
                        current_lineup.pop() 
                    current_lineup.add(act_pid)

            if len(current_lineup) == 5:
                l_key = tuple(sorted(list(current_lineup)))
                if l_key not in lineup_stats:
                    lineup_stats[l_key] = {"secs": 0, "pts_for": 0, "pts_agn": 0}
                
                duration = max(0, current_time_total_secs - last_time_total_secs)
                lineup_stats[l_key]["secs"] += duration
                
                new_h = safe_int(act.get("homeTeamPoints"))
                new_g = safe_int(act.get("guestTeamPoints"))
                
                if is_home:
                    lineup_stats[l_key]["pts_for"] += max(0, new_h - last_h_score)
                    lineup_stats[l_key]["pts_agn"] += max(0, new_g - last_g_score)
                else:
                    lineup_stats[l_key]["pts_for"] += max(0, new_g - last_g_score)
                    lineup_stats[l_key]["pts_agn"] += max(0, new_h - last_h_score)

            last_time_total_secs = current_time_total_secs
            last_h_score = safe_int(act.get("homeTeamPoints"))
            last_g_score = safe_int(act.get("guestTeamPoints"))

            if act.get("type") == "SUBSTITUTION" and str(act.get("seasonTeamId")) == tid_str:
                p_out = str(act.get("seasonPlayerId"))
                p_in = str(act.get("relatedSeasonPlayerId"))
                if p_out in current_lineup: current_lineup.remove(p_out)
                if p_in and p_in != "None": current_lineup.add(p_in)

    final_lineups = []
    for ids, data in lineup_stats.items():
        if data["secs"] > 45: 
            final_lineups.append({
                "ids": list(ids),
                "min": f"{data['secs']//60:02d}:{data['secs']%60:02d}",
                "pkt": data["pts_for"],
                "opp": data["pts_agn"],
                "pm": data["pts_for"] - data["pts_agn"]
            })
    
    return sorted(final_lineups, key=lambda x: x["pm"], reverse=True)[:5]

def render_team_analysis_dashboard(tid, t_name):
    """
    Main entry point for the Team Analysis Page.
    """
    st.title(f"Taktik-Analyse: {t_name}")
    
    # Needs to import here to avoid circular imports if src.api imports this file
    from src.api import fetch_season_games, fetch_game_boxscore, fetch_game_details
    
    with st.spinner("Lade alle Saisonspiele für Lineup-Analyse..."):
        # 1. Fetch schedule
        games = fetch_season_games(tid, "2025") # Assuming 2025 as default
        
        # 2. Filter for played games and fetch details for detailed lineup tracking
        detailed_games = []
        if games:
            played = [g for g in games if g.get('has_result')]
            # Limit to last 3 games to save API calls/time for demo
            st.caption(f"Analysiere die letzten {min(len(played), 3)} Spiele im Detail...")
            for g in played[:3]: 
                gid = g['id']
                d = fetch_game_details(gid) # Need details for PBP actions
                if d: detailed_games.append(d)
        
    if detailed_games:
        # Calculate Lineups
        top_lineups = calculate_real_lineups(tid, detailed_games)
        
        st.subheader("Top Lineups (Last 3 Games)")
        if top_lineups:
            # Display nicely
            for l in top_lineups:
                st.markdown(f"**Lineup PM: {l['pm']:+d}** (Min: {l['min']}, {l['pkt']}:{l['opp']})")
                # Here you would map IDs to names if you had the roster dict
                st.code(", ".join(l['ids'])) 
        else:
            st.warning("Keine Lineups mit signifikanter Spielzeit gefunden.")
    else:
        st.warning("Keine Spieldaten verfügbar.")
