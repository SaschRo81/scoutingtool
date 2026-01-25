import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import pytz
# WICHTIG: Hier kommt fetch_last_n_games_complete her
from src.api import get_player_metadata_cached, get_best_team_logo, fetch_last_n_games_complete

# --- KONSTANTEN & HELPERS ---
ACTION_TRANSLATION = {
    "2pt_fg": "2er Wurf", "3pt_fg": "3er Wurf", "free_throw": "Freiwurf",
    "rebound_defensive": "Def. Rebound", "rebound_offensive": "Off. Rebound",
    "turnover": "Turnover", "steal": "Steal", "foul": "Foul", "substitution": "Wechsel"
}

def get_team_name(team_obj, fallback="Team"):
    return team_obj.get("name", fallback) if team_obj else fallback

def render_game_header(boxscore_data):
    # Header mit Scores, Logos etc.
    if not boxscore_data: return
    home = boxscore_data.get("homeTeam", {})
    guest = boxscore_data.get("guestTeam", {})
    res = boxscore_data.get("result", {})
    
    c1, c2, c3 = st.columns([1, 0.8, 1])
    with c1:
        st.markdown(f"<div style='text-align:center;'><h3>{get_team_name(home)}</h3></div>", unsafe_allow_html=True)
        lid = home.get("id") or home.get("teamId")
        logo = get_best_team_logo(lid)
        if logo: st.image(logo, width=120)
    with c2:
        st.markdown(f"<div style='text-align:center; font-size:40px; font-weight:bold; margin-top:40px;'>{res.get('homeScore',0)} : {res.get('guestScore',0)}</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='text-align:center; color:grey;'>{boxscore_data.get('scheduledTime','').split('T')[0]}</div>", unsafe_allow_html=True)
    with c3:
        st.markdown(f"<div style='text-align:center;'><h3>{get_team_name(guest)}</h3></div>", unsafe_allow_html=True)
        lid = guest.get("id") or guest.get("teamId")
        logo = get_best_team_logo(lid)
        if logo: st.image(logo, width=120)

def render_boxscore_table_pro(player_stats, game_stat, team_name, coach):
    st.subheader(f"Statistik: {team_name}")
    st.caption(f"Head Coach: {coach}")
    if not player_stats:
        st.info("Keine Spielerdaten.")
        return

    data = []
    for p in player_stats:
        sp = p.get("seasonPlayer", {})
        nm = f"{sp.get('firstName','')} {sp.get('lastName','')}"
        nr = sp.get("shirtNumber", "#")
        # Zeit formatieren
        sec = p.get("secondsPlayed", 0)
        mins = f"{int(sec)//60}:{int(sec)%60:02d}"
        
        data.append({
            "NR": nr, "Name": nm, "MIN": mins,
            "PTS": p.get("points", 0),
            "FG": f"{p.get('fieldGoalsMade')}/{p.get('fieldGoalsAttempted')}",
            "3PT": f"{p.get('threePointShotsMade')}/{p.get('threePointShotsAttempted')}",
            "FT": f"{p.get('freeThrowsMade')}/{p.get('freeThrowsAttempted')}",
            "REB": p.get("totalRebounds", 0),
            "AST": p.get("assists", 0),
            "STL": p.get("steals", 0),
            "BLK": p.get("blocks", 0),
            "TO": p.get("turnovers", 0),
            "PF": p.get("foulsCommitted", 0),
            "EFF": int(p.get("efficiency", 0)),
            "+/-": int(p.get("plusMinus", 0))
        })
    
    df = pd.DataFrame(data)
    st.dataframe(df, hide_index=True, use_container_width=True)

def render_charts_and_stats(box):
    # Einfache Charts
    st.subheader("Team Vergleich")
    h = box.get("homeTeam", {}).get("gameStat", {})
    g = box.get("guestTeam", {}).get("gameStat", {})
    
    metrics = ["points", "totalRebounds", "assists", "steals", "turnovers", "efficiency"]
    rows = []
    for m in metrics:
        rows.append({"Metric": m, "Team": "Home", "Value": h.get(m, 0)})
        rows.append({"Metric": m, "Team": "Guest", "Value": g.get(m, 0)})
    
    df = pd.DataFrame(rows)
    c = alt.Chart(df).mark_bar().encode(
        x='Value:Q',
        y=alt.Y('Metric:N', sort=None),
        color='Team:N',
        tooltip=['Metric', 'Team', 'Value']
    ).properties(height=300)
    st.altair_chart(c, use_container_width=True)

def render_game_top_performers(box):
    st.subheader("Top Performer (EFF)")
    c1, c2 = st.columns(2)
    
    for i, team_key in enumerate(["homeTeam", "guestTeam"]):
        players = box.get(team_key, {}).get("playerStats", [])
        if not players: continue
        # Sort by EFF
        top = sorted(players, key=lambda x: float(x.get("efficiency", 0)), reverse=True)[0]
        sp = top.get("seasonPlayer", {})
        name = f"{sp.get('firstName','')} {sp.get('lastName','')}"
        
        with (c1 if i==0 else c2):
            st.markdown(f"**{get_team_name(box.get(team_key))}**")
            pid = sp.get("id")
            meta = get_player_metadata_cached(pid)
            if meta and meta.get("img"):
                st.image(meta["img"], width=150)
            st.metric("MVP", name, f"EFF {int(top.get('efficiency',0))}")

def generate_game_summary(box):
    # Simpler Text-Generator
    if not box: return "Keine Daten."
    h = box.get("homeTeam", {})
    g = box.get("guestTeam", {})
    res = box.get("result", {})
    return f"**Endstand**: {get_team_name(h)} {res.get('homeScore')} - {res.get('guestScore')} {get_team_name(g)}. "

def generate_complex_ai_prompt(box):
    return f"Erstelle einen Spielbericht für: {generate_game_summary(box)}"

def render_full_play_by_play(box):
    # Dummy implementation oder PBP Parsing
    st.write("Play-by-Play Daten werden hier geladen...")
    # Falls PBP Daten in 'actions' liegen:
    actions = box.get("actions", [])
    if actions:
        st.dataframe(pd.DataFrame(actions))
    else:
        st.info("Keine PBP Daten verfügbar.")

def render_prep_dashboard(opp_id, opp_name, df_roster, schedule, metadata_callback):
    st.title(f"Vorbereitung: {opp_name}")
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("Letzte Spiele")
        # Nutzt fetch_last_n_games_complete
        games = fetch_last_n_games_complete(opp_id, "2025", 3)
        if games:
            for g in games:
                res = g.get("meta_result", "-")
                opp = g.get("meta_opponent", "?")
                loc = "Heim" if g.get("meta_is_home") else "Gast"
                with st.expander(f"{g.get('meta_date')} vs {opp} ({loc}) -> {res}"):
                    # Mini Boxscore
                    stats = g.get("homeTeam" if g.get("meta_is_home") else "guestTeam", {}).get("gameStat", {})
                    st.write(f"PTS: {stats.get('points')} | FG%: {stats.get('fieldGoalsPercentage')}% | TO: {stats.get('turnovers')}")
        else:
            st.write("Keine vergangenen Spiele gefunden.")
    
    with c2:
        st.subheader("Kader Übersicht")
        if df_roster is not None:
            st.dataframe(df_roster[["NR", "NAME_FULL", "PPG", "GP"]], hide_index=True)

def render_live_view(box):
    # Live View Wrapper
    render_game_header(box)
    t1, t2 = st.tabs(["Boxscore", "Verlauf"])
    with t1:
        h = box.get("homeTeam", {})
        g = box.get("guestTeam", {})
        render_boxscore_table_pro(h.get("playerStats", []), h.get("gameStat", {}), get_team_name(h), h.get("headCoachName"))
        render_boxscore_table_pro(g.get("playerStats", []), g.get("gameStat", {}), get_team_name(g), g.get("headCoachName"))
    with t2:
        render_full_play_by_play(box)

def render_team_analysis_dashboard(tid, tname):
    st.title(f"Deep Dive: {tname}")
    st.write("Erweiterte Statistiken (Clutch, Lineups) kommen hier.")
