import streamlit as st
import pandas as pd
import altair as alt
from src.api import get_player_metadata_cached, get_best_team_logo, fetch_last_n_games_complete

# --- HELPER ---
ACTION_MAP = {
    "TWO_POINT_THROW": "2-Punkt Wurf", "THREE_POINT_THROW": "3-Punkt Wurf", "FREE_THROW": "Freiwurf", 
    "REBOUND": "Rebound", "TURNOVER": "Ballverlust", "ASSIST": "Assist", "BLOCK": "Block", 
    "STEAL": "Steal", "FOUL": "Foul", "TIMEOUT": "Auszeit", "SUBSTITUTION": "Wechsel", 
    "JUMP_BALL": "Sprungball", "TEAM_TURN_OVER": "Team Turnover", "PERSONAL_FOUL": "Persönliches Foul",
    "START": "Spielstart", "END": "Spielende"
}

def get_team_name(team_obj, fallback="Team"):
    return team_obj.get("name", fallback) if team_obj else fallback

def render_game_header(box, details=None):
    if not box: return
    home = box.get("homeTeam", {}); guest = box.get("guestTeam", {}); res = box.get("result", {})
    period = "Ende"; time_str = ""
    if details:
        p_raw = details.get("period", 0)
        time_raw = details.get("gameTime", "00:00")
        status = details.get("status", "SCHEDULED")
        if status == "RUNNING": period = f"Q{p_raw}"; time_str = f" | {time_raw}"
        elif status == "ENDED": period = "Final"
        elif status == "SCHEDULED": period = "Vorschau"; time_str = f" | {box.get('scheduledTime', '').split('T')[0]}"
            
    c_h, c_score, c_g = st.columns([1, 1.5, 1])
    with c_h:
        lid = home.get("id") or home.get("teamId")
        logo = get_best_team_logo(lid)
        st.markdown(f"<div style='text-align:center;'>", unsafe_allow_html=True)
        if logo: st.image(logo, width=100)
        st.markdown(f"<h3 style='text-align:center;'>{get_team_name(home)}</h3></div>", unsafe_allow_html=True)
    with c_score:
        h_s = res.get("homeScore") if res.get("homeScore") is not None else res.get("homeTeamFinalScore", 0)
        g_s = res.get("guestScore") if res.get("guestScore") is not None else res.get("guestTeamFinalScore", 0)
        st.markdown(f"<div style='text-align:center; background:#f8f9fa; padding:15px; border-radius:10px;'><div style='color:#666;'>{period}{time_str}</div><div style='font-size:48px; font-weight:900;'>{h_s} : {g_s}</div></div>", unsafe_allow_html=True)
    with c_g:
        lid = guest.get("id") or guest.get("teamId")
        logo = get_best_team_logo(lid)
        st.markdown(f"<div style='text-align:center;'>", unsafe_allow_html=True)
        if logo: st.image(logo, width=100)
        st.markdown(f"<h3 style='text-align:center;'>{get_team_name(guest)}</h3></div>", unsafe_allow_html=True)
    st.divider()

def render_boxscore_table_pro(player_stats, game_stat, team_name, coach):
    st.markdown(f"#### {team_name}"); st.caption(f"Coach: {coach}")
    if not player_stats: st.info("Noch keine Stats."); return
    rows = []
    for p in player_stats:
        sp = p.get("seasonPlayer", {})
        nm = f"{sp.get('firstName','')[0]}. {sp.get('lastName','')}"
        nr = sp.get("shirtNumber", "#"); sec = p.get("secondsPlayed", 0)
        mins = f"{int(sec)//60:02d}:{int(sec)%60:02d}"
        fg = f"{p.get('fieldGoalsMade')}/{p.get('fieldGoalsAttempted')}"
        p3 = f"{p.get('threePointShotsMade')}/{p.get('threePointShotsAttempted')}"
        ft = f"{p.get('freeThrowsMade')}/{p.get('freeThrowsAttempted')}"
        rows.append({"#": nr, "Name": nm, "Min": mins, "PTS": p.get("points", 0), "REB": p.get("totalRebounds", 0), "AST": p.get("assists", 0), "STL": p.get("steals", 0), "TO": p.get("turnovers", 0), "BLK": p.get("blocks", 0), "PF": p.get("foulsCommitted", 0), "EFF": int(p.get("efficiency", 0)), "+/-": int(p.get("plusMinus", 0)), "FG": fg, "3P": p3, "FT": ft})
    
    # Füge Team Stats als letzte Zeile hinzu (Fix für ValueError)
    if game_stat:
        rows.append({"#": "", "Name": "TEAM", "Min": "", "PTS": game_stat.get("points",0), "REB": game_stat.get("totalRebounds",0), "AST": game_stat.get("assists",0), "STL": game_stat.get("steals",0), "TO": game_stat.get("turnovers",0), "BLK": game_stat.get("blocks",0), "PF": game_stat.get("foulsCommitted",0), "EFF": game_stat.get("efficiency",0), "+/-": "", "FG": "", "3P": "", "FT": ""})
        
    df = pd.DataFrame(rows)
    cols = ["#", "Name", "PTS", "REB", "AST", "EFF", "Min", "FG", "3P", "FT", "TO", "STL", "BLK", "PF", "+/-"]
    st.dataframe(df[cols], hide_index=True, use_container_width=True)

def render_full_play_by_play(box):
    actions = box.get("actions", [])
    if not actions: st.info("Noch keine Play-by-Play Daten."); return
    actions_rev = sorted(actions, key=lambda x: x.get("orderId", 0), reverse=True)
    p_map = {}
    for t_key in ["homeTeam", "guestTeam"]:
        for p in box.get(t_key, {}).get("playerStats", []):
            sid = str(p.get("seasonPlayer", {}).get("id"))
            p_map[sid] = f"{p.get('seasonPlayer', {}).get('firstName','')} {p.get('seasonPlayer', {}).get('lastName','')}"

    st.markdown("### Spielverlauf")
    for a in actions_rev:
        time = a.get("gameTime", "00:00"); q = a.get("period", 1); raw_type = a.get("type", "UNKNOWN")
        type_de = ACTION_MAP.get(raw_type, raw_type)
        pid = str(a.get("seasonPlayerId", "")); p_name = p_map.get(pid, "")
        h_p = a.get("homeTeamPoints"); g_p = a.get("guestTeamPoints")
        score_badge = f"<span style='background:#333; color:white; padding:2px 6px; border-radius:4px; font-size:12px;'>{h_p}:{g_p}</span>" if h_p is not None else ""
        icon = "🏀"
        if "FOUL" in raw_type: icon = "🛑"
        elif "TURNOVER" in raw_type: icon = "⚠️"
        elif "TIMEOUT" in raw_type: icon = "⏱️"
        elif "SUBSTITUTION" in raw_type: icon = "🔄"
        desc = f"**{p_name}**" if p_name else ""
        qual = a.get("qualifiers", [])
        if "Missed" in str(qual) or not a.get("isSuccessful", True): desc += f" verfehlt {type_de}"; icon = "❌"
        else: desc += f" {type_de}"
        st.markdown(f"<div style='border-bottom:1px solid #eee; padding:8px 0; display:flex; align-items:center;'><div style='width:60px; font-weight:bold; color:#666;'>Q{q} {time}</div><div style='width:30px;'>{icon}</div><div style='flex-grow:1;'>{desc}</div><div>{score_badge}</div></div>", unsafe_allow_html=True)

def render_charts_and_stats(box):
    st.subheader("Team Statistik Vergleich")
    h = box.get("homeTeam", {}); g = box.get("guestTeam", {}); h_stats = h.get("gameStat", {}); g_stats = g.get("gameStat", {})
    metrics = {"points": "Punkte", "totalRebounds": "Rebounds", "assists": "Assists", "turnovers": "Turnovers", "steals": "Steals", "foulsCommitted": "Fouls", "efficiency": "Effizienz"}
    data = []
    for k, label in metrics.items():
        data.append({"Team": get_team_name(h, "Heim"), "Wert": h_stats.get(k, 0), "Metrik": label})
        data.append({"Team": get_team_name(g, "Gast"), "Wert": g_stats.get(k, 0), "Metrik": label})
    c = alt.Chart(pd.DataFrame(data)).mark_bar().encode(y=alt.Y('Metrik:N', sort=None), x='Wert:Q', color='Team:N', tooltip=['Team', 'Metrik', 'Wert']).properties(height=350)
    st.altair_chart(c, use_container_width=True)
    
    actions = box.get("actions", [])
    if actions:
        st.subheader("Punkteverlauf")
        score_data = []
        for a in actions:
            if a.get("homeTeamPoints") is not None:
                gt = a.get("gameTime", "00:00"); mins, secs = map(int, gt.split(":")); q = a.get("period", 1)
                total_min = (q-1)*10 + (10 - mins + (60-secs)/60.0)
                score_data.append({"Min": total_min, "Team": get_team_name(h, "Heim"), "Score": a.get("homeTeamPoints")})
                score_data.append({"Min": total_min, "Team": get_team_name(g, "Gast"), "Score": a.get("guestTeamPoints")})
        if score_data:
            chart_score = alt.Chart(pd.DataFrame(score_data)).mark_line().encode(x=alt.X('Min', title="Spielminute"), y='Score', color='Team').properties(height=300)
            st.altair_chart(chart_score, use_container_width=True)

# --- WRAPPER FÜR APP.PY ---
def render_game_top_performers(box): pass
def generate_game_summary(box): return ""
def generate_complex_ai_prompt(box): return ""

def render_prep_dashboard(opp_id, opp_name, df_roster, schedule, metadata_callback):
    st.title(f"Vorbereitung: {opp_name}")
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("Letzte Spiele")
        games = fetch_last_n_games_complete(opp_id, "2025", 3)
        if games:
            for g in games:
                res = g.get("meta_result", "-"); opp = g.get("meta_opponent", "?"); loc = "Heim" if g.get("meta_is_home") else "Gast"
                with st.expander(f"{g.get('meta_date')} vs {opp} ({loc}) -> {res}"):
                    stats = g.get("homeTeam" if g.get("meta_is_home") else "guestTeam", {}).get("gameStat", {})
                    st.write(f"PTS: {stats.get('points')} | FG%: {stats.get('fieldGoalsPercentage')}% | TO: {stats.get('turnovers')}")
        else: st.write("Keine vergangenen Spiele gefunden.")
    with c2:
        st.subheader("Kader Übersicht")
        if df_roster is not None: st.dataframe(df_roster[["NR", "NAME_FULL", "PPG", "GP"]], hide_index=True)

def render_live_view(box):
    render_game_header(box, box)
    tab1, tab2, tab3 = st.tabs(["📊 Boxscore", "📜 Verlauf", "📈 Vergleich"])
    with tab1:
        c1, c2 = st.columns(2)
        h = box.get("homeTeam", {}); g = box.get("guestTeam", {})
        with c1: render_boxscore_table_pro(h.get("playerStats", []), h.get("gameStat", {}), get_team_name(h), h.get("headCoachName"))
        with c2: render_boxscore_table_pro(g.get("playerStats", []), g.get("gameStat", {}), get_team_name(g), g.get("headCoachName"))
    with tab2: render_full_play_by_play(box)
    with tab3: render_charts_and_stats(box)

def render_team_analysis_dashboard(tid, tname):
    st.title(f"Deep Dive: {tname}"); st.write("Erweiterte Statistiken (Clutch, Lineups) kommen hier.")
