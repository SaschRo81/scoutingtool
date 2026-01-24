import streamlit as st
from src.api import (
    get_player_metadata_cached, 
    fetch_game_boxscore, 
    get_best_team_logo, 
    fetch_team_data
)

# Das CSS für den TV-Look
OBS_CSS = """
<style>
    header, footer, [data-testid="stSidebar"] {display: none !important;}
    .stApp {background: transparent !important;}
    .block-container {padding: 0 !important; max-width: 100% !important;}
    body { font-family: 'Arial', sans-serif; overflow: hidden; margin: 0; padding: 0; }

    .overlay-container {
        position: fixed;
        bottom: 40px;
        left: 50%;
        transform: translateX(-50%);
        width: 1550px;
        display: flex;
        flex-direction: column;
    }

    .header-bar {
        background: linear-gradient(90deg, #001f5b 0%, #00338d 100%);
        color: white;
        padding: 12px 35px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        border-top: 5px solid #ff6600;
        border-radius: 10px 10px 0 0;
        box-shadow: 0 -5px 15px rgba(0,0,0,0.5);
    }

    .team-info { display: flex; align-items: center; gap: 20px; }
    .team-logo { height: 65px; object-fit: contain; }
    .team-name { font-size: 34px; font-weight: 900; text-transform: uppercase; }
    
    .coach-info { text-align: right; font-size: 16px; color: #ddd; text-transform: uppercase; }
    .coach-name { font-weight: bold; color: white; display: block; font-size: 22px; }

    .players-row {
        display: flex;
        justify-content: space-between;
        background: rgba(0, 20, 60, 0.85);
        padding: 20px;
        border-radius: 0 0 10px 10px;
    }

    .player-card {
        width: 19%;
        text-align: center;
        position: relative;
        display: flex;
        flex-direction: column;
        align-items: center;
    }

    .img-wrapper { position: relative; width: 150px; height: 150px; margin-bottom: 10px; }
    .p-img {
        width: 100%; height: 100%; object-fit: cover;
        border-radius: 8px; border: 3px solid white; background: #555;
    }

    .p-nr {
        position: absolute; bottom: -8px; left: -8px;
        background: #ff6600; color: white; font-weight: 900;
        width: 42px; height: 42px; display: flex;
        align-items: center; justify-content: center;
        font-size: 22px; border: 2px solid white; border-radius: 5px;
    }

    .p-name {
        font-size: 20px; font-weight: bold; color: white;
        text-transform: uppercase; text-shadow: 2px 2px 4px black;
    }
</style>
"""

def render_obs_starting5():
    st.markdown(OBS_CSS, unsafe_allow_html=True)
    try:
        # Parameter aus der URL ziehen
        ids_str = st.query_params.get("ids", "")
        team_name = st.query_params.get("name", "TEAM")
        coach_name = st.query_params.get("coach", "")
        logo_id = st.query_params.get("logo_id", "")
        
        logo_url = get_best_team_logo(logo_id) if logo_id else ""
        ids = [x for x in ids_str.split(",") if x]
        
        if not ids:
            return

        # HTML ohne Einrückung zusammenbauen
        html = f"<div class='overlay-container'><div class='header-bar'><div class='team-info'>"
        if logo_url:
            html += f"<img src='{logo_url}' class='team-logo'>"
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
    except Exception as e:
        st.error(f"Fehler: {e}")

def render_obs_standings():
    inject_obs_css()
    region = st.query_params.get("region", "Süd")
    season = st.query_params.get("season", "2025")
    df = fetch_league_standings(season, region)
    if not df.empty:
        html = f"<div class='obs-table-container'><div class='obs-header'>Tabelle {region}</div><table class='obs-table'><thead><tr><th>#</th><th>Team</th><th>W</th><th>L</th></tr></thead><tbody>"
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
