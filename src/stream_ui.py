import streamlit as st
import pandas as pd
from src.api import (
    get_player_metadata_cached, 
    fetch_game_boxscore, 
    get_best_team_logo, 
    fetch_league_standings, 
    fetch_team_data
)
from src.html_gen import generate_comparison_html

# --- OBS DARK MODE CSS (BLUE THEME) ---
OBS_DARK_CSS = """
<style>
/* 1. Alles von Streamlit verstecken */
header, footer, [data-testid="stSidebar"], [data-testid="stHeader"], 
[data-testid="stStatusWidget"], .viewerBadge_container__1QSob, 
.stAppDeployButton, [data-testid="stDecoration"], #MainMenu {
    display: none !important;
    visibility: hidden !important;
}

/* 2. Hintergrund transparent machen */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMainViewContainer"], .block-container {
    background-color: transparent !important;
    background-image: none !important;
    padding: 0 !important;
    margin: 0 !important;
}

/* Body Reset */
body {
    background-color: transparent !important;
    overflow: hidden !important;
    margin: 0;
    padding: 0;
}

/* --- COMPONENTS DESIGN (DARK BLUE THEME) --- */

/* Header Bar */
.overlay-container {
    position: fixed; bottom: 40px; left: 50%; transform: translateX(-50%);
    width: 1550px; display: flex; flex-direction: column; z-index: 9999;
}
.header-bar {
    background: linear-gradient(90deg, #001f5b 0%, #00338d 100%);
    color: white; padding: 12px 35px; display: flex; align-items: center; justify-content: space-between;
    border-top: 5px solid #ff6600; border-radius: 10px 10px 0 0; 
    box-shadow: 0 5px 15px rgba(0,0,0,0.5);
}
.team-info { display: flex; align-items: center; gap: 20px; }
.team-logo { height: 65px; object-fit: contain; }
.team-name { font-size: 34px; font-weight: 900; text-transform: uppercase; font-family: sans-serif; }
.coach-info { text-align: right; font-size: 16px; color: #ccc; text-transform: uppercase; font-family: sans-serif; }
.coach-name { font-weight: bold; color: white; display: block; font-size: 22px; }

/* Starting 5 Container (DUNKELBLAU) */
.players-row {
    display: flex; justify-content: space-between; 
    background: #001a4d; /* DUNKELBLAU */
    padding: 20px; border-radius: 0 0 10px 10px;
    border-bottom: 5px solid #ff6600; /* Orange Akzent unten */
}
.player-card { width: 19%; text-align: center; position: relative; display: flex; flex-direction: column; align-items: center; }
.img-wrapper { position: relative; width: 150px; height: 150px; margin-bottom: 10px; }
.p-img { width: 100%; height: 100%; object-fit: cover; border-radius: 8px; border: 3px solid #ff6600; background: #eee; }
.p-nr {
    position: absolute; bottom: -8px; left: -8px; background: #00338d; color: white; font-weight: 900;
    width: 42px; height: 42px; display: flex; align-items: center; justify-content: center;
    font-size: 22px; border: 2px solid #ff6600; border-radius: 5px;
}
.p-name { 
    font-size: 20px; font-weight: bold; font-family: sans-serif; 
    color: white; /* WEISSE SCHRIFT */
    text-transform: uppercase; text-shadow: 1px 1px 2px black;
}

/* Content Wrapper (Standings & Comparison) - DUNKEL */
.obs-content-wrapper {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 1400px; 
    background: #001a4d; /* DUNKELBLAU */
    padding: 0;
    border-radius: 15px;
    border: 3px solid #ff6600; /* Orange Border */
    color: white; 
    font-family: sans-serif;
    box-shadow: 0 0 50px rgba(0,0,0,0.8);
    z-index: 10000;
}

.obs-header-row {
    background: linear-gradient(90deg, #001f5b 0%, #00338d 100%);
    color: white; 
    padding: 15px 30px; 
    display: flex;
    align-items: center;
    justify-content: center; 
    border-bottom: 3px solid #ff6600;
    min-height: 80px;
}
.header-title {
    font-size: 42px; font-weight: 900; text-transform: uppercase;
    letter-spacing: 2px; color: white;
}

/* Tabellen Styles - DARK MODE */
.obs-content-wrapper table {
    width: 100%; border-collapse: collapse; font-size: 24px; text-align: center; margin: 0;
}
.obs-content-wrapper th { 
    background: #002661; /* Etwas helleres Blau für Header */
    color: #ff6600; /* Orange Schrift im Header */
    padding: 15px; 
    text-transform: uppercase; font-size: 22px; border-bottom: 2px solid #ff6600; 
}
.obs-content-wrapper td { 
    padding: 12px; border-bottom: 1px solid #444; font-weight: bold; vertical-align: middle; 
    color: white; /* Weisser Text */
}
/* Alternierende Zeilen (sehr subtil) */
.obs-content-wrapper tr:nth-child(even) { background-color: rgba(255,255,255,0.05); }

/* POTG Card Style - DARK MODE */
.potg-card {
    width: 500px; margin: 80px auto; 
    background: #001a4d; /* DUNKELBLAU */
    border: 4px solid #ff6600; border-radius: 20px; padding: 30px; 
    text-align: center; color: white; 
    box-shadow: 0 0 50px rgba(0,0,0,0.8); font-family: sans-serif;
}
.potg-stat-box {
    display: flex; justify-content: center; gap: 15px; margin-top: 25px; 
    background: rgba(255,255,255,0.1); /* Halb-Transparent */
    padding: 15px; border-radius: 10px; border: 1px solid #444;
}
.potg-stat-item { text-align: center; min-width: 70px; }
.potg-stat-label { font-size: 16px; color: #ccc; margin-bottom: 4px; font-weight: bold; }
.potg-stat-val { font-size: 32px; font-weight: 900; color: #ff6600; /* Orange Zahlen */ }
</style>
"""

def render_obs_starting5():
    st.markdown(OBS_DARK_CSS, unsafe_allow_html=True)
    try:
        ids_str = st.query_params.get("ids", "")
        team_name = st.query_params.get("name", "TEAM")
        coach_name = st.query_params.get("coach", "")
        logo_id = st.query_params.get("logo_id", "")
        logo_url = get_best_team_logo(logo_id) if logo_id else ""
        ids = [x for x in ids_str.split(",") if x]
        if not ids: return

        html = f"<div class='overlay-container'><div class='header-bar'><div class='team-info'>"
        if logo_url: html += f"<img src='{logo_url}' class='team-logo'>"
        # HIER: "Trainer" statt "Head Coach"
        html += f"<div class='team-name'>{team_name}</div></div><div class='coach-info'>Trainer<span class='coach-name'>{coach_name}</span></div></div><div class='players-row'>"
        for pid in ids:
            meta = get_player_metadata_cached(pid)
            img = meta.get("img") or "https://via.placeholder.com/150"
            p_name = st.query_params.get(f"n_{pid}", "Player")
            parts = p_name.split(" ")
            display_name = f"{parts[0][0]}. {parts[-1]}" if len(parts) > 1 else p_name
            p_nr = st.query_params.get(f"nr_{pid}", "#")
            html += f"<div class='player-card'><div class='img-wrapper'><img src='{img}' class='p-img'><div class='p-nr'>{p_nr}</div></div><div class='p-name'>{display_name}</div></div>"
        html += "</div></div>"
        st.markdown(html, unsafe_allow_html=True)
    except Exception as e: st.error(f"Fehler: {e}")

def render_obs_standings():
    st.markdown(OBS_DARK_CSS, unsafe_allow_html=True)
    region = st.query_params.get("region", "Süd")
    season = st.query_params.get("season", "2025")
    df = fetch_league_standings(season, region)
    
    if not df.empty:
        region_display = region.capitalize()
        title_text = f"2. DBBL {region_display}"
        
        html = f"""
        <div class='obs-content-wrapper'>
            <div class='obs-header-row'><span class='header-title'>{title_text}</span></div>
            <table><thead><tr>
                <th style='width:60px;'>#</th><th style='text-align:left;'>Team</th>
                <th>Sp</th><th>S</th><th>N</th><th>Diff</th>
            </tr></thead><tbody>
        """
        for _, row in df.iterrows():
            platz = row.get('Platz', 0)
            team = row.get('Team', 'Unknown')
            sp = row.get('Sp', 0); s = row.get('S', 0); n = row.get('N', 0)
            diff = row.get('Diff', '0')
            try: rank_val = int(platz)
            except: rank_val = 99
            
            # Farb-Indikatoren (nur kleiner Balken links), Rest dunkel
            row_style = ""
            if rank_val <= 4: row_style = "border-left: 8px solid #28a745;"
            elif rank_val <= 8: row_style = "border-left: 8px solid #6c757d;"
            else: row_style = "border-left: 8px solid #dc3545;"

            diff_style = "color:#28a745;" if (str(diff).startswith("+")) else ("color:#dc3545;" if str(diff).startswith("-") else "color:#999;")
            html += f"<tr style='{row_style}'><td>{platz}</td><td style='text-align:left;'>{team}</td><td>{sp}</td><td>{s}</td><td>{n}</td><td style='{diff_style}'>{diff}</td></tr>"
        html += "</tbody></table></div>"
        st.markdown(html, unsafe_allow_html=True)

def render_obs_comparison():
    st.markdown(OBS_DARK_CSS, unsafe_allow_html=True)
    hid = st.query_params.get("hid"); gid = st.query_params.get("gid")
    hname = st.query_params.get("hname"); gname = st.query_params.get("gname")
    
    if hid and gid:
        _, ts_h = fetch_team_data(hid, "2025")
        _, ts_g = fetch_team_data(gid, "2025")
        
        content_html = generate_comparison_html(ts_h, ts_g, hname, gname)
        
        # HIER: "Direkter Vergleich" statt "Head-to-Head"
        html = f"""
        <div class='obs-content-wrapper' style='padding-bottom:10px;'>
             <div class='obs-header-row'>
                <span class='header-title'>Direkter Vergleich (Schnitt)</span>
            </div>
            {content_html}
        </div>
        """
        html = html.replace('\n', ' ')
        st.markdown(html, unsafe_allow_html=True)

def render_obs_potg():
    st.markdown(OBS_DARK_CSS, unsafe_allow_html=True)
    gid = st.query_params.get("game_id")
    if not gid: return
    box = fetch_game_boxscore(gid)
    if not box: return
    
    players = []
    for team_key in ["homeTeam", "guestTeam"]:
        for p in box.get(team_key, {}).get("playerStats", []):
            try:
                eff = float(p.get("efficiency", 0))
                sec = int(p.get("secondsPlayed") or 0)
                min_str = f"{sec//60:02d}:{sec%60:02d}"
                reb = int(p.get("totalRebounds") or 0)
                players.append({
                    "id": str(p.get("seasonPlayer", {}).get("id")),
                    "name": f"{p.get('seasonPlayer', {}).get('firstName','')} {p.get('seasonPlayer', {}).get('lastName','')}",
                    "nr": p.get('seasonPlayer', {}).get('shirtNumber', ''),
                    "eff": eff, "pts": int(p.get("points", 0)), "reb": reb, "min": min_str
                })
            except: pass
            
    if players:
        mvp = sorted(players, key=lambda x: x["eff"], reverse=True)[0]
        meta = get_player_metadata_cached(mvp["id"])
        img = meta.get("img") or "https://via.placeholder.com/300"
        
        # HIER: "Spielerin des Spiels" auf Deutsch
        html = f"""
        <div class='potg-card'>
            <h2 style='color:#ff6600; margin:0 0 15px 0; font-size:24px; text-transform:uppercase;'>Spielerin des Spiels</h2>
            <img src='{img}' style='width:220px; height:220px; border-radius:50%; border:5px solid #ff6600; object-fit:cover;'>
            <h1 style='margin:15px 0 5px 0; font-size:36px; color:white; text-transform:uppercase;'>{mvp['name']}</h1>
            <h2 style='margin:0; color:#ccc; font-size:28px;'>#{mvp['nr']}</h2>
            <div class='potg-stat-box'>
                <div class='potg-stat-item'>
                    <div class='potg-stat-label'>MIN</div>
                    <div class='potg-stat-val'>{mvp['min']}</div>
                </div>
                <div class='potg-stat-item'>
                    <div class='potg-stat-label'>PKT</div>
                    <div class='potg-stat-val'>{mvp['pts']}</div>
                </div>
                <div class='potg-stat-item'>
                    <div class='potg-stat-label'>REB</div>
                    <div class='potg-stat-val'>{mvp['reb']}</div>
                </div>
                <div class='potg-stat-item'>
                    <div class='potg-stat-label'>EFF</div>
                    <div class='potg-stat-val'>{mvp['eff']:.0f}</div>
                </div>
            </div>
        </div>
        """
        html_safe = html.replace("\n", " ")
        st.markdown(html_safe, unsafe_allow_html=True)
