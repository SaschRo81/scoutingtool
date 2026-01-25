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

# --- OBS ULTRA CLEAN CSS ---
OBS_ULTRA_CLEAN_CSS = """
<style>
/* Verstecke ALLES von Streamlit */
header, footer, [data-testid="stSidebar"], [data-testid="stHeader"], 
[data-testid="stStatusWidget"], .viewerBadge_container__1QSob, 
.stAppDeployButton, [data-testid="stDecoration"], #MainMenu {
    display: none !important;
    visibility: hidden !important;
}

/* Transparenz erzwingen */
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

/* --- TV LOOK DESIGN --- */
.overlay-container {
    position: fixed; bottom: 40px; left: 50%; transform: translateX(-50%);
    width: 1550px; display: flex; flex-direction: column; z-index: 9999;
}
.header-bar {
    background: linear-gradient(90deg, #001f5b 0%, #00338d 100%);
    color: white; padding: 12px 35px; display: flex; align-items: center; justify-content: space-between;
    border-top: 5px solid #ff6600; border-radius: 10px 10px 0 0; box-shadow: 0 -5px 15px rgba(0,0,0,0.5);
}
.team-info { display: flex; align-items: center; gap: 20px; }
.team-logo { height: 65px; object-fit: contain; }
.team-name { font-size: 34px; font-weight: 900; text-transform: uppercase; font-family: sans-serif; }
.coach-info { text-align: right; font-size: 16px; color: #ddd; text-transform: uppercase; font-family: sans-serif; }
.coach-name { font-weight: bold; color: white; display: block; font-size: 22px; }
.players-row {
    display: flex; justify-content: space-between; background: rgba(0, 20, 60, 0.9);
    padding: 20px; border-radius: 0 0 10px 10px;
}
.player-card { width: 19%; text-align: center; position: relative; display: flex; flex-direction: column; align-items: center; }
.img-wrapper { position: relative; width: 150px; height: 150px; margin-bottom: 10px; }
.p-img { width: 100%; height: 100%; object-fit: cover; border-radius: 8px; border: 3px solid white; background: #555; }
.p-nr {
    position: absolute; bottom: -8px; left: -8px; background: #ff6600; color: white; font-weight: 900;
    width: 42px; height: 42px; display: flex; align-items: center; justify-content: center;
    font-size: 22px; border: 2px solid white; border-radius: 5px;
}
.p-name { font-size: 20px; font-weight: bold; color: white; font-family: sans-serif; text-transform: uppercase; text-shadow: 2px 2px 4px black; }

/* TABELLE */
.obs-content-wrapper {
    width: 1500px; margin: 60px auto; background: rgba(0,0,0,0.9);
    padding: 0; border-radius: 15px; border: 3px solid #00338d;
    color: white; font-family: sans-serif; overflow: hidden; box-shadow: 0 0 30px rgba(0,0,0,0.8);
}
.obs-header-row {
    background: linear-gradient(90deg, #001f5b 0%, #00338d 100%);
    color: white; padding: 15px; text-align: center; font-size: 36px; font-weight: 900;
    border-bottom: 5px solid #ff6600; text-transform: uppercase;
}
.obs-table { width: 100%; font-size: 24px; border-collapse: collapse; text-align: center; }
.obs-table th { background: #001a4d; color: #ff6600; padding: 12px; text-transform: uppercase; font-size: 20px; border-bottom: 2px solid #555; }
.obs-table td { padding: 10px; border-bottom: 1px solid #444; font-weight: bold; vertical-align: middle; }
/* Entfernt: .obs-table tr:first-child td { color: #ffd700; }  da wir jetzt Farb-Coding nutzen */

.trend-w, .trend-l {
    display: inline-block; width: 28px; height: 28px; line-height: 28px;
    text-align: center; border-radius: 50%; font-size: 16px; font-weight: bold;
    margin-right: 3px; color: white;
}
.trend-w { background-color: #28a745; }
.trend-l { background-color: #dc3545; }

/* POTG */
.potg-card {
    width: 450px; margin: 100px auto; background: linear-gradient(180deg, #001f5b 0%, #000 100%);
    border: 4px solid #ff6600; border-radius: 20px; padding: 30px; text-align: center;
    color: white; box-shadow: 0 0 30px rgba(0,0,0,0.8); font-family: sans-serif;
}
.potg-stat-box {
    display: flex; justify-content: center; gap: 15px; margin-top: 25px; 
    background: rgba(255,255,255,0.1); padding: 15px; border-radius: 10px;
}
.potg-stat-item { text-align: center; min-width: 60px; }
.potg-stat-label { font-size: 14px; color: #ccc; margin-bottom: 2px; }
.potg-stat-val { font-size: 28px; font-weight: 900; color: white; }
</style>
"""

def render_obs_starting5():
    st.markdown(OBS_ULTRA_CLEAN_CSS, unsafe_allow_html=True)
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
        html += f"<div class='team-name'>{team_name}</div></div><div class='coach-info'>Head Coach<span class='coach-name'>{coach_name}</span></div></div><div class='players-row'>"
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
    st.markdown(OBS_ULTRA_CLEAN_CSS, unsafe_allow_html=True)
    region = st.query_params.get("region", "Süd")
    season = st.query_params.get("season", "2025")
    df = fetch_league_standings(season, region)
    
    if not df.empty:
        html = f"<div class='obs-content-wrapper'><div class='obs-header-row'>Tabelle {region.upper()}</div>"
        html += "<table class='obs-table'><thead><tr><th style='width:50px;'>#</th><th style='text-align:left;'>Team</th><th>Sp</th><th>S</th><th>N</th><th>Diff</th></tr></thead><tbody>"
        
        for _, row in df.iterrows():
            platz = row.get('Platz', 0)
            team = row.get('Team', 'Unknown')
            sp = row.get('Sp', 0)
            s = row.get('S', 0)
            n = row.get('N', 0)
            diff = row.get('Diff', '0')
            
            # --- FARB-LOGIK ---
            try:
                rank_val = int(platz)
            except:
                rank_val = 99
            
            row_style = ""
            if rank_val <= 4:
                # Grün (Top 4) - Subtiler grüner Hintergrund + Grüner Rand links
                row_style = "background-color: rgba(40, 167, 69, 0.15); border-left: 6px solid #28a745;"
            elif rank_val <= 8:
                # Grau (Mittelfeld)
                row_style = "background-color: rgba(108, 117, 125, 0.15); border-left: 6px solid #6c757d;"
            else:
                # Rot (Abstieg)
                row_style = "background-color: rgba(220, 53, 69, 0.15); border-left: 6px solid #dc3545;"

            # Diff Farbe (Positiv/Negativ)
            diff_style = "color:#00ff00;" if (str(diff).startswith("+")) else ("color:#ff4444;" if str(diff).startswith("-") else "color:#aaa;")
            
            html += f"<tr style='{row_style}'><td>{platz}</td><td style='text-align:left;'>{team}</td><td>{sp}</td><td>{s}</td><td>{n}</td><td style='{diff_style}'>{diff}</td></tr>"
            
        html += "</tbody></table></div>"
        st.markdown(html, unsafe_allow_html=True)

def render_obs_comparison():
    st.markdown(OBS_ULTRA_CLEAN_CSS, unsafe_allow_html=True)
    hid = st.query_params.get("hid"); gid = st.query_params.get("gid")
    hname = st.query_params.get("hname"); gname = st.query_params.get("gname")
    if hid and gid:
        _, ts_h = fetch_team_data(hid, "2025")
        _, ts_g = fetch_team_data(gid, "2025")
        st.markdown("<div class='obs-content-wrapper' style='padding:20px;'>", unsafe_allow_html=True)
        st.markdown(generate_comparison_html(ts_h, ts_g, hname, gname), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

def render_obs_potg():
    st.markdown(OBS_ULTRA_CLEAN_CSS, unsafe_allow_html=True)
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
                    "eff": eff,
                    "pts": int(p.get("points", 0)),
                    "reb": reb,
                    "min": min_str
                })
            except: pass
            
    if players:
        mvp = sorted(players, key=lambda x: x["eff"], reverse=True)[0]
        meta = get_player_metadata_cached(mvp["id"])
        img = meta.get("img") or "https://via.placeholder.com/300"
        
        html = f"""
        <div class='potg-card'>
            <h2 style='color:#ff6600; margin:0 0 15px 0; font-size:24px;'>PLAYER OF THE GAME</h2>
            <img src='{img}' style='width:220px; height:220px; border-radius:50%; border:5px solid white; object-fit:cover;'>
            <h1 style='margin:15px 0 5px 0; font-size:32px;'>{mvp['name']}</h1>
            <h2 style='margin:0; color:#ccc;'>#{mvp['nr']}</h2>
            
            <div class='potg-stat-box'>
                <div class='potg-stat-item'>
                    <div class='potg-stat-label'>MIN</div>
                    <div class='potg-stat-val'>{mvp['min']}</div>
                </div>
                <div class='potg-stat-item'>
                    <div class='potg-stat-label'>PTS</div>
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
        st.markdown(html, unsafe_allow_html=True)
