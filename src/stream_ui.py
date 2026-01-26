import streamlit as st
import pandas as pd
from src.api import (
    get_player_metadata_cached, 
    fetch_game_boxscore, 
    fetch_game_details,
    get_best_team_logo, 
    fetch_league_standings, 
    fetch_team_data
)
from src.html_gen import generate_comparison_html

# --- OBS ULTRA CLEAN CSS (Vollständig & Aggressiv) ---
OBS_ULTRA_CLEAN_CSS = """
<style>
/* UI Elemente verstecken */
header, footer, #MainMenu, [data-testid="stHeader"], [data-testid="stStatusWidget"], 
.stAppDeployButton, .viewerBadge_container__1QSob, [data-testid="stDecoration"], 
[data-testid="stSidebar"], [data-testid="stToolbar"], button[kind="header"] {
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
    opacity: 0 !important;
}

/* Transparenz erzwingen */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMainViewContainer"], .block-container {
    background: transparent !important;
    background-color: transparent !important;
    padding: 0 !important;
    margin: 0 !important;
}
body {
    background: transparent !important;
    background-color: transparent !important;
}

/* Störende Linien entfernen */
hr, [data-testid="stVerticalBlock"] > div > div > div[style*="border-bottom"] { 
    display: none !important; 
}
</style>
"""

# --- 1. STARTING 5 ---
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

        html = f"<div class='overlay-container' style='position:fixed; bottom:40px; left:50%; transform:translateX(-50%); width:1550px; display:flex; flex-direction:column; z-index:9999;'>"
        html += f"<div class='header-bar' style='background:linear-gradient(90deg, #001f5b 0%, #00338d 100%); color:white; padding:12px 35px; display:flex; align-items:center; justify-content:space-between; border-top:5px solid #ff6600; border-radius:10px 10px 0 0; box-shadow: 0 5px 15px rgba(0,0,0,0.5);'>"
        html += f"<div style='display:flex; align-items:center; gap:20px;'>"
        if logo_url: html += f"<img src='{logo_url}' style='height:65px; object-fit:contain;'>"
        html += f"<div style='font-size:34px; font-weight:900; text-transform:uppercase; font-family:sans-serif;'>{team_name}</div></div>"
        html += f"<div style='text-align:right; font-size:16px; color:#ddd; text-transform:uppercase; font-family:sans-serif;'>Head Coach<span style='font-weight:bold; color:white; display:block; font-size:22px;'>{coach_name}</span></div></div>"
        html += f"<div style='display:flex; justify-content:space-between; background:white; padding:20px; border-radius:0 0 10px 10px; border-bottom:5px solid #001f5b;'>"
        
        for pid in ids:
            meta = get_player_metadata_cached(pid)
            img = meta.get("img") or "https://via.placeholder.com/150"
            p_name = st.query_params.get(f"n_{pid}", "Player")
            parts = p_name.split(" ")
            display_name = f"{parts[0][0]}. {parts[-1]}" if len(parts) > 1 else p_name
            p_nr = st.query_params.get(f"nr_{pid}", "#")
            html += f"<div style='width:19%; text-align:center; position:relative; display:flex; flex-direction:column; align-items:center;'>"
            html += f"<div style='position:relative; width:150px; height:150px; margin-bottom:10px;'>"
            html += f"<img src='{img}' style='width:100%; height:100%; object-fit:cover; border-radius:8px; border:3px solid #001f5b; background:#eee;'>"
            html += f"<div style='position:absolute; bottom:-8px; left:-8px; background:#ff6600; color:white; font-weight:900; width:42px; height:42px; display:flex; align-items:center; justify-content:center; font-size:22px; border:2px solid white; border-radius:5px; font-family:sans-serif;'>{p_nr}</div></div>"
            html += f"<div style='font-size:20px; font-weight:bold; color:#001f5b; text-transform:uppercase; font-family:sans-serif;'>{display_name}</div></div>"
        
        html += "</div></div>"
        st.markdown(html, unsafe_allow_html=True)
    except Exception as e: st.error(f"Fehler: {e}")

# --- 2. STANDINGS (TABELLE) ---
def render_obs_standings():
    st.markdown(OBS_ULTRA_CLEAN_CSS, unsafe_allow_html=True)
    region = st.query_params.get("region", "Süd")
    season = st.query_params.get("season", "2025")
    df = fetch_league_standings(season, region)
    
    if not df.empty:
        dbbl_logo = "https://toyota-dbbl.de/app/themes/dbbl/src/assets/toyota-DBBL-logo.svg"
        title_text = f"2. Damen Basketball Bundesliga {region.capitalize()}"
        
        html = f"<div style='position:fixed; top:50%; left:50%; transform:translate(-50%, -50%); width:1400px; background:white; border-radius:15px; border:3px solid #00338d; overflow:hidden; box-shadow:0 0 50px rgba(0,0,0,0.8); font-family:sans-serif;'>"
        html += f"<div style='background:linear-gradient(90deg, #001f5b 0%, #00338d 100%); color:white; padding:10px 40px; display:flex; align-items:center; justify-content:space-between; border-bottom:5px solid #ff6600; height:120px;'>"
        html += f"<span style='font-size:40px; font-weight:900; text-transform:uppercase; letter-spacing:1px;'>{title_text}</span>"
        html += f"<img src='{dbbl_logo}' style='height:100px; width:auto; object-fit:contain; filter:drop-shadow(0 0 8px rgba(255,255,255,0.8));'></div>"
        html += "<table style='width:100%; font-size:26px; border-collapse:collapse; text-align:center;'><thead>"
        html += "<tr style='background:#eee; color:#001a4d; text-transform:uppercase; font-size:22px; border-bottom:3px solid #001a4d;'><th style='padding:15px; width:60px;'>#</th><th style='text-align:left; padding:15px;'>Team</th><th>Sp</th><th>S</th><th>N</th><th>Diff</th></tr></thead><tbody>"
        
        for _, row in df.iterrows():
            platz = row.get('Platz', 0); team = row.get('Team', 'Unknown')
            try: rank_val = int(platz)
            except: rank_val = 99
            
            row_bg = "#e8f5e9" if rank_val <= 4 else ("#f8f9fa" if rank_val <= 8 else "#fce8e6")
            row_border = "#28a745" if rank_val <= 4 else ("#6c757d" if rank_val <= 8 else "#dc3545")
            diff_color = "#28a745" if str(row.get('Diff', '0')).startswith("+") else "#dc3545"

            html += f"<tr style='background-color:{row_bg}; border-left:8px solid {row_border}; border-bottom:1px solid #ccc; color:#333; font-weight:bold;'>"
            html += f"<td style='padding:12px;'>{platz}</td><td style='text-align:left; padding:12px;'>{team}</td><td>{row.get('Sp',0)}</td><td>{row.get('S',0)}</td><td>{row.get('N',0)}</td><td style='color:{diff_color};'>{row.get('Diff','0')}</td></tr>"
            
        html += "</tbody></table></div>"
        st.markdown(html, unsafe_allow_html=True)

# --- 3. TEAM COMPARISON (HEAD TO HEAD) - GOLD ---
def render_obs_comparison():
    st.markdown(OBS_ULTRA_CLEAN_CSS, unsafe_allow_html=True)
    hid = st.query_params.get("hid"); gid = st.query_params.get("gid")
    hname = st.query_params.get("hname", "Team A"); gname = st.query_params.get("gname", "Team B")
    
    if not hid or not gid: return

    _, ts_h = fetch_team_data(hid, "2025")
    _, ts_g = fetch_team_data(gid, "2025")

    metrics = [
        ("Points Per Game", "ppg"), ("Field Goal %", "fgpct"), ("3-Point %", "3pct"),
        ("Free Throw %", "ftpct"), ("Rebounds (Total)", "tot"), ("Defensive Rebs", "dr"),
        ("Offensive Rebs", "or"), ("Assists", "as"), ("Turnovers", "to"),
        ("Steals", "st"), ("Blocks", "bs"), ("Fouls", "pf")
    ]

    # CONTAINER
    html = f"<div style='position:fixed; top:50%; left:50%; transform:translate(-50%, -50%); width:1100px; background:#FFD700; border-radius:15px; padding:0; overflow:hidden; box-shadow:0 20px 60px rgba(0,0,0,0.8); font-family:sans-serif; z-index:9999; border: 4px solid #000;'>"
    html += f"<table style='width:100%; border-collapse:collapse;'>"
    
    # Header Zeile
    html += f"<tr><th style='background:#000; color:#FFD700; padding:15px; font-size:24px; font-weight:900; width:40%; text-align:center; text-transform:uppercase; border-bottom:4px solid #000;'>{hname}</th>"
    html += f"<th style='background:#222; color:white; width:20%; text-align:center; font-size:16px; letter-spacing:2px; border-bottom:4px solid #000;'>STATS</th>"
    html += f"<th style='background:#000; color:#FFD700; padding:15px; font-size:24px; font-weight:900; width:40%; text-align:center; text-transform:uppercase; border-bottom:4px solid #000;'>{gname}</th></tr>"

    for label, key in metrics:
        try:
            v_h = float(ts_h.get(key, 0))
            v_g = float(ts_g.get(key, 0))
        except:
            v_h = 0.0; v_g = 0.0

        is_negative_stat = key in ["to", "pf"]
        h_win = (v_h < v_g) if is_negative_stat else (v_h > v_g)
        g_win = (v_g < v_h) if is_negative_stat else (v_g > v_h)
        
        # Style Definitionen - JETZT EINHEITLICHE GRÖSSE (28px)
        # Nur die Farbe unterscheidet sich noch (Grün für den besseren Wert)
        base_style = "font-size:28px; padding:10px; background:#ffffff;"
        
        s_h = f"{base_style} color:#004d00; font-weight:900;" if h_win else f"{base_style} color:#000; font-weight:800;"
        s_g = f"{base_style} color:#004d00; font-weight:900;" if g_win else f"{base_style} color:#000; font-weight:800;"
        
        if "pct" in key:
            f_h = f"{v_h:.1f}%"; f_g = f"{v_g:.1f}%"
        else:
            f_h = f"{v_h:.1f}"; f_g = f"{v_g:.1f}"

        html += f"<tr style='border-bottom:1px solid #d4b000; text-align:center;'>"
        html += f"<td style='{s_h}'>{f_h}</td>"
        html += f"<td style='background:#fff; color:#000; font-size:16px; font-weight:bold; text-transform:uppercase; letter-spacing:0.5px; border-left:1px solid #d4b000; border-right:1px solid #d4b000;'>{label}</td>"
        html += f"<td style='{s_g}'>{f_g}</td></tr>"

    html += "</table></div>"
    st.markdown(html, unsafe_allow_html=True)

# --- 4. PLAYER OF THE GAME (GOLD THEME) ---
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
                players.append({
                    "id": str(p.get("seasonPlayer", {}).get("id")),
                    "name": f"{p.get('seasonPlayer', {}).get('firstName','')} {p.get('seasonPlayer', {}).get('lastName','')}",
                    "nr": p.get('seasonPlayer', {}).get('shirtNumber', ''),
                    "eff": eff, "pts": int(p.get("points", 0)), "reb": int(p.get("totalRebounds", 0)),
                    "min": f"{int(p.get('secondsPlayed', 0))//60:02d}:00"
                })
            except: pass
            
    if players:
        mvp = sorted(players, key=lambda x: x["eff"], reverse=True)[0]
        meta = get_player_metadata_cached(mvp["id"])
        img = meta.get("img") or "https://via.placeholder.com/300"
        
        # DESIGN UPDATE: Goldener Hintergrund, Schwarzer Rand, Schwarze Schrift
        html = f"<div style='width:450px; margin:100px auto; background:#FFD700; border:4px solid #000; border-radius:20px; padding:30px; text-align:center; color:#000; font-family:sans-serif; box-shadow:0 0 50px rgba(0,0,0,0.8);'>"
        html += f"<h2 style='color:#000; margin:0 0 15px 0; font-size:24px; text-transform:uppercase; font-weight:900;'>Player of the Game</h2>"
        html += f"<img src='{img}' style='width:220px; height:220px; border-radius:50%; border:5px solid #000; object-fit:cover;'>"
        html += f"<h1 style='margin:15px 0 5px 0; font-size:32px; color:#000; font-weight:900;'>{mvp['name']}</h1>"
        html += f"<h2 style='margin:0; color:#333;'>#{mvp['nr']}</h2>"
        # Stats Box: Weißer Hintergrund für Kontrast
        html += "<div style='display:flex; justify-content:center; gap:15px; margin-top:25px; background:#fff; padding:15px; border-radius:10px; border:1px solid #000;'>"
        html += f"<div><div style='font-size:12px; color:#666;'>MIN</div><div style='font-size:24px; font-weight:900;'>{mvp['min']}</div></div>"
        html += f"<div><div style='font-size:12px; color:#666;'>PTS</div><div style='font-size:24px; font-weight:900;'>{mvp['pts']}</div></div>"
        html += f"<div><div style='font-size:12px; color:#666;'>REB</div><div style='font-size:24px; font-weight:900;'>{mvp['reb']}</div></div>"
        html += f"<div><div style='font-size:12px; color:#666;'>EFF</div><div style='font-size:24px; font-weight:900; color:#001f5b;'>{mvp['eff']:.0f}</div></div></div></div>"
        st.markdown(html, unsafe_allow_html=True)

# --- 5. FINAL SCORE BANNER ---
def render_obs_final_banner():
    st.markdown(OBS_ULTRA_CLEAN_CSS, unsafe_allow_html=True)
    gid = st.query_params.get("game_id")
    if not gid: return
    
    details = fetch_game_details(gid)
    box = fetch_game_boxscore(gid)
    if not details: return

    h_data = details.get("homeTeam", {}); g_data = details.get("guestTeam", {})
    h_name = h_data.get("nameFull") or h_data.get("name") or "Heim"
    g_name = g_data.get("nameFull") or g_data.get("name") or "Gast"
    h_logo = h_data.get("logoUrl") or ""; g_logo = g_data.get("logoUrl") or ""
    sh = details.get("result", {}).get("homeTeamFinalScore", 0)
    sg = details.get("result", {}).get("guestTeamFinalScore", 0)
    
    if (sh == 0 and sg == 0) and box:
        sh = sum([int(p.get("points",0)) for p in box.get("homeTeam", {}).get("playerStats",[])])
        sg = sum([int(p.get("points",0)) for p in box.get("guestTeam", {}).get("playerStats",[])])

    def get_fs(name):
        l = len(str(name))
        return "22px" if l > 28 else ("28px" if l > 20 else "38px")

    html = f"<div style='position:fixed; bottom:80px; left:50%; transform:translateX(-50%); width:1600px; font-family:sans-serif; box-shadow:0 15px 50px rgba(0,0,0,0.7);'>"
    html += f"<div style='background:linear-gradient(90deg, #001040 0%, #002060 100%); color:white; height:95px; display:flex; align-items:center; justify-content:space-between; padding:0 40px; border-top:6px solid #ff6600;'>"
    html += f"<div style='font-size:{get_fs(h_name)}; font-weight:900; text-transform:uppercase; width:45%; line-height:1.1;'>{h_name}</div>"
    html += f"<div style='font-size:24px; font-weight:900; color:#ff6600; font-style:italic;'>VS</div>"
    html += f"<div style='font-size:{get_fs(g_name)}; font-weight:900; text-transform:uppercase; width:45%; text-align:right; line-height:1.1;'>{g_name}</div></div>"
    html += f"<div style='background:white; height:110px; display:flex; align-items:center; justify-content:space-between; padding:0 40px; position:relative; border-bottom:4px solid #ccc;'>"
    if h_logo: html += f"<img src='{h_logo}' style='height:90px; filter:drop-shadow(0 4px 4px rgba(0,0,0,0.1));'>"
    else: html += "<div></div>"
    html += f"<div style='position:absolute; top:-35px; left:50%; transform:translateX(-50%); background:white; padding:15px 60px; border-radius:12px 12px 0 0; text-align:center; border-top:5px solid #ff6600; box-shadow:0 -5px 20px rgba(0,0,0,0.15);'>"
    html += f"<div style='font-size:16px; font-weight:900; color:#ff6600;'>FINAL SCORE</div><div style='font-size:60px; font-weight:900; color:#001f5b;'>{sh} | {sg}</div></div>"
    if g_logo: html += f"<img src='{g_logo}' style='height:90px; filter:drop-shadow(0 4px 4px rgba(0,0,0,0.1));'>"
    else: html += "<div></div>"
    html += "</div></div>"
    st.markdown(html, unsafe_allow_html=True)
