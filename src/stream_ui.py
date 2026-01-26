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

# --- OBS ULTRA CLEAN CSS (FINAL) ---
OBS_ULTRA_CLEAN_CSS = """
<style>
/* 1. HARTES AUSBLENDEN ALLER STREAMLIT ELEMENTE */
header, footer, #MainMenu, 
[data-testid="stHeader"], 
[data-testid="stStatusWidget"], 
[data-testid="stToolbar"], 
.stAppDeployButton, 
button[kind="header"],
.viewerBadge_container__1QSob, 
[data-testid="stDecoration"],
[data-testid="stSidebar"] {
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
    opacity: 0 !important;
    pointer-events: none !important;
}

/* 2. TRANSPARENZ & RESET */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMainViewContainer"], .block-container {
    background-color: transparent !important;
    background-image: none !important;
    padding: 0 !important;
    margin: 0 !important;
}
body {
    background-color: transparent !important;
    overflow: hidden !important;
    margin: 0; padding: 0;
}

/* 3. TV OVERLAY STYLES */
.overlay-container {
    position: fixed; bottom: 40px; left: 50%; transform: translateX(-50%);
    width: 1550px; display: flex; flex-direction: column; z-index: 9999;
}
.header-bar {
    background: linear-gradient(90deg, #001f5b 0%, #00338d 100%);
    color: white; padding: 12px 35px; display: flex; align-items: center; justify-content: space-between;
    border-top: 5px solid #ff6600; border-radius: 10px 10px 0 0; box-shadow: 0 5px 15px rgba(0,0,0,0.5);
}
.team-info { display: flex; align-items: center; gap: 20px; }
.team-logo { height: 65px; object-fit: contain; }
.team-name { font-size: 34px; font-weight: 900; text-transform: uppercase; font-family: sans-serif; }
.coach-info { text-align: right; font-size: 16px; color: #ddd; text-transform: uppercase; font-family: sans-serif; }
.coach-name { font-weight: bold; color: white; display: block; font-size: 22px; }

/* Starting 5 Grid */
.players-row {
    display: flex; justify-content: space-between; background: white;
    padding: 20px; border-radius: 0 0 10px 10px; border-bottom: 5px solid #001f5b;
}
.player-card { width: 19%; text-align: center; position: relative; display: flex; flex-direction: column; align-items: center; }
.img-wrapper { position: relative; width: 150px; height: 150px; margin-bottom: 10px; }
.p-img { width: 100%; height: 100%; object-fit: cover; border-radius: 8px; border: 3px solid #001f5b; background: #eee; }
.p-nr {
    position: absolute; bottom: -8px; left: -8px; background: #ff6600; color: white; font-weight: 900;
    width: 42px; height: 42px; display: flex; align-items: center; justify-content: center;
    font-size: 22px; border: 2px solid white; border-radius: 5px;
}
.p-name { font-size: 20px; font-weight: bold; color: #001f5b; font-family: sans-serif; text-transform: uppercase; }

/* TABELLE / STANDINGS */
.obs-content-wrapper {
    position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
    width: 1400px; background: white; padding: 0;
    border-radius: 15px; border: 3px solid #00338d;
    color: #333; font-family: sans-serif; overflow: hidden; box-shadow: 0 0 50px rgba(0,0,0,0.8);
}
.obs-header-row {
    background: linear-gradient(90deg, #001f5b 0%, #00338d 100%);
    color: white; padding: 10px 40px; 
    display: flex; align-items: center; justify-content: space-between; 
    border-bottom: 5px solid #ff6600; min-height: 120px;
}
.header-title { font-size: 40px; font-weight: 900; text-transform: uppercase; letter-spacing: 1px; white-space: nowrap; }
.header-logo-img { 
    height: 100px !important; width: auto; object-fit: contain; 
    filter: drop-shadow(0 0 8px rgba(255,255,255,0.8)); margin-left: 20px; flex-shrink: 0;
}
.obs-table { width: 100%; font-size: 26px; border-collapse: collapse; text-align: center; }
.obs-table th { background: #eee; color: #001a4d; padding: 15px; text-transform: uppercase; font-size: 22px; border-bottom: 3px solid #001a4d; }
.obs-table td { padding: 12px; border-bottom: 1px solid #ccc; font-weight: bold; vertical-align: middle; color: #333; }
.obs-table tr:nth-child(even) { background-color: #f9f9f9; }

/* Trend Bubbles */
.trend-w, .trend-l {
    display: inline-block; width: 30px; height: 30px; line-height: 30px;
    text-align: center; border-radius: 50%; font-size: 16px; font-weight: bold;
    margin-right: 4px; color: white;
}
.trend-w { background-color: #28a745; }
.trend-l { background-color: #dc3545; }

/* POTG CARD */
.potg-card {
    width: 450px; margin: 100px auto; background: white;
    border: 4px solid #ff6600; border-radius: 20px; padding: 30px; text-align: center;
    color: #333; box-shadow: 0 0 50px rgba(0,0,0,0.8); font-family: sans-serif;
}
.potg-stat-box {
    display: flex; justify-content: center; gap: 15px; margin-top: 25px; 
    background: #f0f0f0; padding: 15px; border-radius: 10px; border: 1px solid #ddd;
}
.potg-stat-item { text-align: center; min-width: 60px; }
.potg-stat-label { font-size: 14px; color: #666; margin-bottom: 2px; }
.potg-stat-val { font-size: 28px; font-weight: 900; color: #00338d; }

/* --- FINAL BANNER STYLES --- */
.fb-container {
    position: fixed; bottom: 80px; left: 50%; transform: translateX(-50%);
    width: 1600px; font-family: sans-serif;
    box-shadow: 0 10px 40px rgba(0,0,0,0.6);
}
.fb-header {
    background: linear-gradient(90deg, #001040 0%, #002060 100%); /* Deep Blue */
    color: white; height: 110px; display: flex; align-items: center; justify-content: space-between;
    padding: 0 50px; border-top: 6px solid #ff6600;
}
.fb-team-name { font-size: 40px; font-weight: 900; text-transform: uppercase; letter-spacing: 1px; width: 42%; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.fb-team-name.right { text-align: right; }
.fb-logos { display: flex; align-items: center; gap: 30px; }
.fb-logo-img { height: 90px; object-fit: contain; filter: drop-shadow(0 0 8px rgba(255,255,255,0.2)); }
.fb-vs { font-size: 32px; font-weight: 900; color: #ff6600; font-style: italic; font-family: sans-serif; }

.fb-footer {
    background: white; height: 80px; display: flex; align-items: center; justify-content: space-between;
    padding: 0; position: relative;
    border-bottom: 4px solid #ccc;
}
.fb-player-box {
    width: 38%; display: flex; align-items: center; padding: 0 40px; font-size: 26px; font-weight: bold; color: #001f5b; text-transform: uppercase;
}
.fb-player-box.right { justify-content: flex-end; }
.fb-pts { margin-left: 20px; color: #555; font-size: 22px; font-weight: normal; }
.fb-pts.right { margin-left: 0; margin-right: 20px; }

.fb-center-box {
    position: absolute; top: -30px; left: 50%; transform: translateX(-50%);
    background: white; padding: 10px 50px; border-radius: 12px 12px 0 0;
    text-align: center; border-top: 5px solid #ff6600;
    box-shadow: 0 -5px 20px rgba(0,0,0,0.15);
}
.fb-center-label { font-size: 15px; font-weight: 900; color: #001f5b; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 2px; }
.fb-center-sub { font-size: 12px; font-weight: 900; color: #ff6600; text-transform: uppercase; letter-spacing: 1px; }
.fb-center-score { font-size: 48px; font-weight: 900; color: #001f5b; line-height: 1; margin-top: 5px; }
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
        dbbl_logo = "https://toyota-dbbl.de/app/themes/dbbl/src/assets/toyota-DBBL-logo.svg"
        region_display = region.capitalize()
        title_text = f"2. Damen Basketball Bundesliga {region_display}"
        
        html = f"""<div class='obs-content-wrapper'><div class='obs-header-row'><span class='header-title'>{title_text}</span><img src='{dbbl_logo}' class='header-logo-img'></div>"""
        html += "<table class='obs-table'><thead><tr><th style='width:60px;'>#</th><th style='text-align:left;'>Team</th><th>Sp</th><th>S</th><th>N</th><th>Diff</th></tr></thead><tbody>"
        
        for _, row in df.iterrows():
            platz = row.get('Platz', 0); team = row.get('Team', 'Unknown'); sp = row.get('Sp', 0)
            s = row.get('S', 0); n = row.get('N', 0); diff = row.get('Diff', '0')
            try: rank_val = int(platz)
            except: rank_val = 99
            
            row_style = ""
            if rank_val <= 4: row_style = "background-color: #e8f5e9; border-left: 8px solid #28a745;"
            elif rank_val <= 8: row_style = "background-color: #f8f9fa; border-left: 8px solid #6c757d;"
            else: row_style = "background-color: #fce8e6; border-left: 8px solid #dc3545;"

            diff_style = "color:#28a745;" if (str(diff).startswith("+")) else ("color:#dc3545;" if str(diff).startswith("-") else "color:#999;")
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
        st.markdown("<div class='obs-content-wrapper' style='padding:20px; background:white;'>", unsafe_allow_html=True)
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
                eff = float(p.get("efficiency", 0)); sec = int(p.get("secondsPlayed") or 0)
                min_str = f"{sec//60:02d}:{sec%60:02d}"; reb = int(p.get("totalRebounds") or 0)
                players.append({"id": str(p.get("seasonPlayer", {}).get("id")), "name": f"{p.get('seasonPlayer', {}).get('firstName','')} {p.get('seasonPlayer', {}).get('lastName','')}", "nr": p.get('seasonPlayer', {}).get('shirtNumber', ''), "eff": eff, "pts": int(p.get("points", 0)), "reb": reb, "min": min_str})
            except: pass
    if players:
        mvp = sorted(players, key=lambda x: x["eff"], reverse=True)[0]
        meta = get_player_metadata_cached(mvp["id"])
        img = meta.get("img") or "https://via.placeholder.com/300"
        html = f"<div class='potg-card'><h2 style='color:#ff6600; margin:0 0 15px 0; font-size:24px; text-transform:uppercase;'>Player of the Game</h2><img src='{img}' style='width:220px; height:220px; border-radius:50%; border:5px solid #00338d; object-fit:cover;'><h1 style='margin:15px 0 5px 0; font-size:32px; color:#001f5b;'>{mvp['name']}</h1><h2 style='margin:0; color:#666;'>#{mvp['nr']}</h2><div class='potg-stat-box'><div class='potg-stat-item'><div class='potg-stat-label'>MIN</div><div class='potg-stat-val'>{mvp['min']}</div></div><div class='potg-stat-item'><div class='potg-stat-label'>PTS</div><div class='potg-stat-val'>{mvp['pts']}</div></div><div class='potg-stat-item'><div class='potg-stat-label'>REB</div><div class='potg-stat-val'>{mvp['reb']}</div></div><div class='potg-stat-item'><div class='potg-stat-label'>EFF</div><div class='potg-stat-val'>{mvp['eff']:.0f}</div></div></div></div>"
        st.markdown(html, unsafe_allow_html=True)

def render_obs_final_banner():
    st.markdown(OBS_ULTRA_CLEAN_CSS, unsafe_allow_html=True)
    gid = st.query_params.get("game_id")
    if not gid: return
    box = fetch_game_boxscore(gid)
    if not box: return

    # --- DATEN-EXTRAKTION (UPDATE) ---
    h_data = box.get("homeTeam", {})
    g_data = box.get("guestTeam", {})
    
    # 1. Namen (nameFull)
    h_name = h_data.get("nameFull") or h_data.get("name") or "HEIM"
    g_name = g_data.get("nameFull") or g_data.get("name") or "GAST"
    
    # 2. Logos (logoUrl aus JSON nehmen)
    h_logo = h_data.get("logoUrl")
    if not h_logo:
        # Fallback auf ID construction
        hid = str(h_data.get("seasonTeamId") or h_data.get("teamId") or "")
        h_logo = get_best_team_logo(hid)
        
    g_logo = g_data.get("logoUrl")
    if not g_logo:
        gid_val = str(g_data.get("seasonTeamId") or g_data.get("teamId") or "")
        g_logo = get_best_team_logo(gid_val)
        
    # Placeholder wenn immer noch leer
    empty_img = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
    if not h_logo: h_logo = empty_img
    if not g_logo: g_logo = empty_img

    # 3. Score (Result)
    res = box.get("result", {})
    sh = res.get("homeTeamFinalScore")
    sg = res.get("guestTeamFinalScore")
    
    # Fallback Berechnung
    if sh is None or sg is None:
        sh = sum([int(p.get("points",0)) for p in h_data.get("playerStats",[])])
        sg = sum([int(p.get("points",0)) for p in g_data.get("playerStats",[])])

    # 4. Top Performer
    def get_top(t_key):
        pl = box.get(t_key, {}).get("playerStats", [])
        if not pl: return "N/A", 0
        best = sorted(pl, key=lambda x: int(x.get("points", 0)), reverse=True)[0]
        sp = best.get('seasonPlayer',{})
        n = f"{sp.get('firstName','')} {sp.get('lastName','')}"
        if not n.strip(): n = "PLAYER"
        return n, int(best.get("points", 0))

    tp_h_name, tp_h_pts = get_top("homeTeam")
    tp_g_name, tp_g_pts = get_top("guestTeam")

    # HTML
    html = f"""
    <div class='fb-container'>
        <div class='fb-header'>
            <div class='fb-team-name'>{h_name}</div>
            <div class='fb-logos'>
                <img src='{h_logo}' class='fb-logo-img'>
                <div class='fb-vs'>VS</div>
                <img src='{g_logo}' class='fb-logo-img'>
            </div>
            <div class='fb-team-name right'>{g_name}</div>
        </div>
        <div class='fb-footer'>
            <div class='fb-player-box'>
                {tp_h_name} <span class='fb-pts'>{tp_h_pts} PTS</span>
            </div>
            <div class='fb-center-box'>
                <div class='fb-center-label'>TOP PERFORMER</div>
                <div class='fb-center-sub'>FINAL SCORE</div>
                <div class='fb-center-score'>{sh} | {sg}</div>
            </div>
            <div class='fb-player-box right'>
                <span class='fb-pts right'>{tp_g_pts} PTS</span> {tp_g_name}
            </div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
