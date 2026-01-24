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

# --- OBS STYLE ---
OBS_CSS = """
<style>
    /* Streamlit UI Elemente ausblenden */
    header {visibility: hidden;}
    footer {visibility: hidden;}
    [data-testid="stSidebar"] {display: none;}
    .stApp {background: transparent !important;}
    .block-container {padding: 0 !important; max-width: 100% !important;}
    
    /* Global Reset */
    body { font-family: 'Arial', sans-serif; overflow: hidden; margin: 0; padding: 0; }

    /* --- STARTING 5 LAYOUT (TV Style) --- */
    .overlay-container {
        position: fixed;
        bottom: 50px;
        left: 50%;
        transform: translateX(-50%);
        width: 1600px; /* Breite des Overlays */
        display: flex;
        flex-direction: column;
    }

    /* Blaue Kopfleiste (Team & Infos) */
    .header-bar {
        background: linear-gradient(90deg, #001f5b 0%, #00338d 100%); /* Dunkelblau wie im Bild */
        color: white;
        padding: 10px 30px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        border-top: 4px solid #ff6600; /* Orange Akzentlinie oben */
        border-radius: 8px 8px 0 0;
        box-shadow: 0 -4px 10px rgba(0,0,0,0.5);
    }

    .team-info { display: flex; align-items: center; gap: 20px; }
    .team-logo { height: 60px; object-fit: contain; filter: drop-shadow(0 0 5px rgba(255,255,255,0.5)); }
    .team-name { font-size: 32px; font-weight: 900; text-transform: uppercase; letter-spacing: 1px; }
    
    .coach-info { text-align: right; font-size: 18px; color: #ccc; }
    .coach-name { font-weight: bold; color: white; display: block; font-size: 22px; text-transform: uppercase;}

    /* Spieler Reihe */
    .players-row {
        display: flex;
        justify-content: space-between;
        background: rgba(0, 31, 91, 0.85); /* Halbtransparenter Hintergrund für Spieler */
        padding: 20px 10px;
        border-radius: 0 0 8px 8px;
    }

    /* Einzelne Spieler Karte */
    .player-card {
        width: 19%; /* 5 Spieler passen rein */
        text-align: center;
        position: relative;
        display: flex;
        flex-direction: column;
        align-items: center;
    }

    /* Bild Container */
    .img-wrapper {
        position: relative;
        width: 140px;
        height: 140px;
        margin-bottom: 10px;
    }

    .p-img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        border-radius: 10px;
        border: 3px solid white;
        background: #999;
    }

    /* Nummer Badge (Links unten am Bild im Beispiel) */
    .p-nr {
        position: absolute;
        bottom: -10px;
        left: -10px;
        background: #ff6600;
        color: white;
        font-weight: bold;
        width: 40px;
        height: 40px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 20px;
        border: 2px solid white;
        border-radius: 5px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.5);
    }

    .p-name {
        font-size: 20px;
        font-weight: bold;
        color: white;
        text-transform: uppercase;
        line-height: 1.1;
        margin-top: 5px;
        text-shadow: 1px 1px 3px black;
    }

    /* --- TABELLE & POTG (Styles behalten) --- */
    .obs-table-container { width: 90%; margin: 20px auto; background: rgba(0,0,0,0.85); border-radius: 15px; overflow: hidden; border: 2px solid #444; }
    .obs-table { width: 100%; font-size: 24px; border-collapse: collapse; color: white; text-align: center; }
    .obs-table th { background: #e35b00; padding: 15px; text-transform: uppercase; font-size: 20px;}
    .obs-table td { padding: 12px; border-bottom: 1px solid #444; font-weight: bold;}
    .obs-header { background: #112244; color: white; padding: 15px; text-align: center; font-size: 32px; font-weight: bold; border-bottom: 4px solid #e35b00; }
    
    .potg-container { width: 500px; margin: 40px auto; background: linear-gradient(135deg, #112244 0%, #000000 100%); border: 4px solid #e35b00; border-radius: 20px; display: flex; flex-direction: column; align-items: center; box-shadow: 0 0 30px rgba(0,0,0,0.8); color: white; padding: 30px; }
    .potg-title { font-size: 32px; font-weight: bold; margin-bottom: 20px; color: #e35b00; text-transform: uppercase; letter-spacing: 2px;}
    .potg-img { width: 250px; height: 250px; object-fit: cover; border-radius: 50%; border: 6px solid white; margin-bottom: 20px; box-shadow: 0 0 20px rgba(255,255,255,0.2); }
    .potg-name { font-size: 32px; font-weight: bold; margin-bottom: 5px; text-align: center; text-transform: uppercase;}
    .potg-team { font-size: 22px; color: #ccc; margin-bottom: 30px;}
    .potg-stats { display: flex; gap: 15px; justify-content: center; width: 100%; flex-wrap: wrap;}
    .stat-bubble { background: rgba(255,255,255,0.1); border-radius: 10px; padding: 10px 15px; text-align: center; min-width: 80px; border: 1px solid rgba(255,255,255,0.2); }
    .stat-val { font-size: 36px; font-weight: bold; color: #e35b00; line-height: 1;}
    .stat-label { font-size: 14px; text-transform: uppercase; color: #aaa; margin-top: 5px;}
    
    .comp-container table { width: 100%; font-size: 24px; color: white; background: rgba(0,0,0,0.9); border-radius: 15px; overflow: hidden; }
    .comp-container th { background: #e35b00 !important; color: white !important; padding: 15px; }
    .comp-container td { border-bottom: 1px solid #555 !important; padding: 10px; }
</style>
"""

def inject_obs_css():
    st.markdown(OBS_CSS, unsafe_allow_html=True)

def render_obs_starting5():
    inject_obs_css()
    try:
        # Wir erwarten jetzt spezifische Parameter für EINE Mannschaft
        # Format: ?ids=1,2,3,4,5&name=TeamName&logo_id=123&coach=Name
        
        ids_str = st.query_params.get("ids", "")
        team_name = st.query_params.get("name", "TEAM")
        coach_name = st.query_params.get("coach", "")
        logo_id = st.query_params.get("logo_id", "")
        
        # Logo URL holen
        logo_url = get_best_team_logo(logo_id) if logo_id else ""
        
        ids = [x for x in ids_str.split(",") if x]
        
        if not ids:
            st.warning("Keine Spieler-IDs übergeben.")
            return

        # HTML Aufbauen
        html = f"""
        <div class='overlay-container'>
            <div class='header-bar'>
                <div class='team-info'>
                    {'<img src="' + logo_url + '" class="team-logo">' if logo_url else ''}
                    <div class='team-name'>{team_name}</div>
                </div>
                <div class='coach-info'>
                    Head Coach
                    <span class='coach-name'>{coach_name}</span>
                </div>
            </div>
            
            <div class='players-row'>
        """
        
        for pid in ids:
            meta = get_player_metadata_cached(pid)
            img = meta.get("img") or "https://via.placeholder.com/150/555555/FFFFFF?text=No+Img"
            
            # Name und Nummer aus URL Parametern holen (um API Calls zu minimieren/Backup)
            p_name = st.query_params.get(f"n_{pid}", "Player")
            # Nachnamen extrahieren (alles nach dem ersten Leerzeichen, falls vorhanden)
            parts = p_name.split(" ")
            last_name = parts[-1] if len(parts) > 1 else p_name
            full_name_disp = f"{parts[0][0]}. {last_name}" if len(parts) > 1 else p_name # Format: M. Mustermann
            
            p_nr = st.query_params.get(f"nr_{pid}", "#")
            
            html += f"""
                <div class='player-card'>
                    <div class='img-wrapper'>
                        <img src='{img}' class='p-img'>
                        <div class='p-nr'>{p_nr}</div>
                    </div>
                    <div class='p-name'>{full_name_disp}</div>
                </div>
            """
            
        html += """
            </div>
        </div>
        """
        
        st.markdown(html, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Fehler: {e}")

def render_obs_standings():
    inject_obs_css()
    region = st.query_params.get("region", "Süd")
    season = st.query_params.get("season", "2025")
    df = fetch_league_standings(season, region)
    if not df.empty:
        html = f"<div class='obs-table-container'><div class='obs-header'>Tabelle {region}</div>"
        html += "<table class='obs-table'><thead><tr><th>#</th><th>Team</th><th>W</th><th>L</th></tr></thead><tbody>"
        for _, row in df.iterrows():
            html += f"<tr><td>{row['Platz']}</td><td>{row['Team']}</td><td>{row['W']}</td><td>{row['L']}</td></tr>"
        html += "</tbody></table></div>"
        st.markdown(html, unsafe_allow_html=True)

def render_obs_comparison():
    inject_obs_css()
    try:
        hid = st.query_params.get("hid"); gid = st.query_params.get("gid")
        hname = st.query_params.get("hname"); gname = st.query_params.get("gname")
        if hid and gid:
            _, ts_h = fetch_team_data(hid, "2025")
            _, ts_g = fetch_team_data(gid, "2025")
            st.markdown("<div class='comp-container'>", unsafe_allow_html=True)
            st.markdown(generate_comparison_html(ts_h, ts_g, hname, gname), unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
    except: pass

def render_obs_potg():
    inject_obs_css()
    st.markdown('<meta http-equiv="refresh" content="30">', unsafe_allow_html=True)
    gid = st.query_params.get("game_id")
    if not gid: return
    box = fetch_game_boxscore(gid)
    if not box: st.error("Lade..."); return
    players = []
    def get_tname(tobj): return tobj.get("name", "Team") if tobj else "Team"
    for team_key in ["homeTeam", "guestTeam"]:
        t_name = get_tname(box.get(team_key))
        for p in box.get(team_key, {}).get("playerStats", []):
            try:
                eff = float(p.get("efficiency", 0))
                players.append({
                    "id": str(p.get("seasonPlayer", {}).get("id")), 
                    "name": f"{p.get('seasonPlayer', {}).get('firstName','')} {p.get('seasonPlayer', {}).get('lastName','')}", 
                    "nr": p.get('seasonPlayer', {}).get('shirtNumber', ''), 
                    "team": t_name, "eff": eff, "pts": int(p.get("points", 0)), 
                    "reb": int(p.get("totalRebounds", 0)), "ast": int(p.get("assists", 0))
                })
            except: pass
    if players:
        mvp = sorted(players, key=lambda x: x["eff"], reverse=True)[0]
        meta = get_player_metadata_cached(mvp["id"])
        img = meta.get("img") or "https://via.placeholder.com/300"
        html = f"<div class='potg-container'><div class='potg-title'>Player of the Game</div><img src='{img}' class='potg-img'><div class='potg-name'>{mvp['name']}</div><div class='potg-team'>#{mvp['nr']} | {mvp['team']}</div><div class='potg-stats'><div class='stat-bubble'><div class='stat-val'>{mvp['pts']}</div><div class='stat-label'>PTS</div></div><div class='stat-bubble'><div class='stat-val'>{mvp['eff']:.0f}</div><div class='stat-label'>EFF</div></div><div class='stat-bubble'><div class='stat-val'>{mvp['reb']}</div><div class='stat-label'>REB</div></div><div class='stat-bubble'><div class='stat-val'>{mvp['ast']}</div><div class='stat-label'>AST</div></div></div></div>"
        st.markdown(html, unsafe_allow_html=True)
