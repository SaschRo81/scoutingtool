# --- START OF FILE src/stream_ui.py ---
import streamlit as st
import pandas as pd
from src.api import get_player_metadata_cached, fetch_game_boxscore, get_best_team_logo, fetch_league_standings, fetch_team_data, get_team_name
from src.utils import optimize_image_base64
from src.html_gen import generate_comparison_html

# CSS für OBS (Transparent, Groß, Keine Scrollbars)
OBS_CSS = """
<style>
    /* Streamlit UI Elemente ausblenden */
    header {visibility: hidden;}
    footer {visibility: hidden;}
    [data-testid="stSidebar"] {display: none;}
    .stApp {background: transparent !important;}
    .block-container {padding: 0 !important; max-width: 100% !important;}
    
    /* Basis Design */
    body {font-family: 'Arial', sans-serif; overflow: hidden; color: white;}
    
    /* Starting 5 Grid */
    .s5-container {
        display: flex; flex-direction: column; gap: 20px; width: 100vw; padding: 20px;
        background: rgba(0,0,0,0.0); /* Transparent */
    }
    .s5-row {
        display: flex; justify-content: space-around; align-items: center;
        background: rgba(17, 34, 68, 0.9); /* Dunkelblau semi-transparent */
        border-radius: 15px; padding: 10px; border: 2px solid #e35b00;
    }
    .s5-card {
        text-align: center; width: 18%; position: relative;
    }
    .s5-img {
        width: 100px; height: 100px; border-radius: 50%; object-fit: cover;
        border: 3px solid white; background: #ccc;
    }
    .s5-name { font-size: 24px; font-weight: bold; margin-top: 5px; text-shadow: 2px 2px 4px #000; color: white;}
    .s5-nr { 
        position: absolute; top: 0; right: 10px; 
        background: #e35b00; color: white; font-weight: bold; 
        border-radius: 50%; width: 35px; height: 35px; 
        display: flex; align-items: center; justify-content: center;
        border: 2px solid white; font-size: 18px;
    }
    .team-label { 
        position: absolute; left: 20px; font-size: 40px; font-weight: bold; 
        color: rgba(255,255,255,0.1); z-index: 0; pointer-events: none;
    }

    /* POTG Card */
    .potg-container {
        width: 600px; height: 800px; margin: 20px;
        background: linear-gradient(135deg, #112244 0%, #000000 100%);
        border: 4px solid #e35b00; border-radius: 20px;
        display: flex; flex-direction: column; align-items: center;
        box-shadow: 0 0 20px rgba(0,0,0,0.8);
        color: white; padding: 20px;
    }
    .potg-title { font-size: 40px; font-weight: bold; margin-bottom: 20px; color: #e35b00; text-transform: uppercase;}
    .potg-img { 
        width: 300px; height: 300px; object-fit: cover; border-radius: 50%; 
        border: 5px solid white; margin-bottom: 20px;
    }
    .potg-name { font-size: 36px; font-weight: bold; margin-bottom: 5px; text-align: center;}
    .potg-team { font-size: 24px; color: #ccc; margin-bottom: 30px;}
    .potg-stats { display: flex; gap: 20px; justify-content: center; width: 100%; flex-wrap: wrap;}
    .stat-bubble {
        background: rgba(255,255,255,0.1); border-radius: 10px; padding: 15px;
        text-align: center; min-width: 100px;
    }
    .stat-val { font-size: 40px; font-weight: bold; color: #e35b00; line-height: 1;}
    .stat-label { font-size: 16px; text-transform: uppercase; color: #aaa;}

    /* Standings Table */
    .obs-table {
        width: 100%; font-size: 28px; border-collapse: collapse; background: rgba(0,0,0,0.8); color: white;
    }
    .obs-table th { background: #e35b00; padding: 10px; text-align: left;}
    .obs-table td { padding: 10px; border-bottom: 1px solid #444;}
    .obs-table tr:nth-child(even) { background: rgba(255,255,255,0.05); }
</style>
"""

def inject_obs_css():
    st.markdown(OBS_CSS, unsafe_allow_html=True)

def render_obs_starting5():
    inject_obs_css()
    # IDs aus URL Parametern holen (Format: ?h_ids=1,2,3&g_ids=4,5,6&h_name=X&g_name=Y)
    try:
        h_ids = st.query_params.get("h_ids", "").split(",")
        g_ids = st.query_params.get("g_ids", "").split(",")
        h_name = st.query_params.get("h_name", "HEIM")
        g_name = st.query_params.get("g_name", "GAST")
        
        # Leere Strings filtern
        h_ids = [x for x in h_ids if x]
        g_ids = [x for x in g_ids if x]

        def render_row(ids, team_name):
            html = f"<div class='s5-row'><div class='team-label'>{team_name}</div>"
            for pid in ids:
                meta = get_player_metadata_cached(pid)
                img = meta.get("img") or "https://via.placeholder.com/150/555555/FFFFFF?text=No+Img"
                # Wir müssen hier leider einen Trick anwenden, um den Namen zu bekommen, 
                # da get_player_metadata_cached nur Bild/Alter liefert, nicht den Namen.
                # Workaround: Wir nutzen die Session oder übergeben Namen auch in URL. 
                # BESSER: Wir cachen die Namen kurz in API oder holen sie schnell.
                # Da wir hier 'stateless' sind, ist der Name im Metadata-Cache idealerweise nachzutragen.
                # FIX: Wir nutzen den Namen aus dem URL Parameter P_NAMES (siehe unten) oder Placeholder.
                name = st.query_params.get(f"n_{pid}", "Player")
                nr = st.query_params.get(f"nr_{pid}", "#")
                
                html += f"""
                <div class='s5-card'>
                    <div class='s5-nr'>{nr}</div>
                    <img src='{img}' class='s5-img'>
                    <div class='s5-name'>{name}</div>
                </div>
                """
            html += "</div>"
            return html

        st.markdown("<div class='s5-container'>", unsafe_allow_html=True)
        st.markdown(render_row(h_ids, h_name), unsafe_allow_html=True)
        st.markdown(render_row(g_ids, g_name), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Fehler beim Laden der Starting 5: {e}")

def render_obs_standings():
    inject_obs_css()
    region = st.query_params.get("region", "Süd")
    season = st.query_params.get("season", "2025")
    
    df = fetch_league_standings(season, region)
    
    if not df.empty:
        # Custom HTML Table für OBS Style
        html = f"<h2 style='text-align:center; background:#112244; padding:10px; margin:0;'>Tabelle {region}</h2>"
        html += "<table class='obs-table'><thead><tr><th>#</th><th>Team</th><th>W</th><th>L</th></tr></thead><tbody>"
        for _, row in df.iterrows():
            html += f"<tr><td>{row['Platz']}</td><td>{row['Team']}</td><td>{row['W']}</td><td>{row['L']}</td></tr>"
        html += "</tbody></table>"
        st.markdown(html, unsafe_allow_html=True)
    else:
        st.warning("Keine Tabellendaten.")

def render_obs_comparison():
    inject_obs_css()
    # Hier nutzen wir einfach die existierende Funktion, stylen sie aber um
    try:
        hid = st.query_params.get("hid")
        gid = st.query_params.get("gid")
        hname = st.query_params.get("hname")
        gname = st.query_params.get("gname")
        
        if hid and gid:
            _, ts_h = fetch_team_data(hid, "2025")
            _, ts_g = fetch_team_data(gid, "2025")
            
            # CSS Injection um die Standard-Tabelle OBS-tauglich zu machen
            st.markdown("""
            <style>
                table { color: white !important; font-size: 24px !important; background: rgba(0,0,0,0.8); }
                th { background-color: #e35b00 !important; color: white !important; }
                td { border-bottom: 1px solid #555 !important; color: white !important; }
                h3 { color: white !important; display: none; } /* Titel ausblenden */
            </style>
            """, unsafe_allow_html=True)
            
            st.markdown(generate_comparison_html(ts_h, ts_g, hname, gname), unsafe_allow_html=True)
    except:
        st.error("Daten fehlen.")

def render_obs_potg():
    inject_obs_css()
    # Auto-Refresh für OBS Browser Source
    st.markdown('<meta http-equiv="refresh" content="30">', unsafe_allow_html=True)
    
    gid = st.query_params.get("game_id")
    if not gid: return

    box = fetch_game_boxscore(gid)
    if not box: st.error("Lade..."); return

    # Logik: MVP finden (Höchste Effizienz oder Punkte)
    players = []
    for team_key in ["homeTeam", "guestTeam"]:
        t_name = get_team_name(box.get(team_key))
        for p in box.get(team_key, {}).get("playerStats", []):
            try:
                eff = float(p.get("efficiency", 0))
                pts = float(p.get("points", 0))
                pid = str(p.get("seasonPlayer", {}).get("id"))
                name = f"{p.get('seasonPlayer', {}).get('firstName','')} {p.get('seasonPlayer', {}).get('lastName','')}"
                nr = p.get('seasonPlayer', {}).get('shirtNumber', '')
                reb = float(p.get("totalRebounds", 0))
                ast = float(p.get("assists", 0))
                
                players.append({
                    "id": pid, "name": name, "nr": nr, "team": t_name,
                    "eff": eff, "pts": int(pts), "reb": int(reb), "ast": int(ast)
                })
            except: pass
            
    if players:
        # Sortiere nach Effizienz
        mvp = sorted(players, key=lambda x: x["eff"], reverse=True)[0]
        meta = get_player_metadata_cached(mvp["id"])
        img = meta.get("img") or "https://via.placeholder.com/300"
        
        html = f"""
        <div class="potg-container">
            <div class="potg-title">Player of the Game</div>
            <img src="{img}" class="potg-img">
            <div class="potg-name">{mvp['name']}</div>
            <div class="potg-team">#{mvp['nr']} | {mvp['team']}</div>
            
            <div class="potg-stats">
                <div class="stat-bubble">
                    <div class="stat-val">{mvp['pts']}</div>
                    <div class="stat-label">Punkte</div>
                </div>
                <div class="stat-bubble">
                    <div class="stat-val">{mvp['eff']:.0f}</div>
                    <div class="stat-label">EFF</div>
                </div>
                <div class="stat-bubble">
                    <div class="stat-val">{mvp['reb']}</div>
                    <div class="stat-label">REB</div>
                </div>
                <div class="stat-bubble">
                    <div class="stat-val">{mvp['ast']}</div>
                    <div class="stat-label">AST</div>
                </div>
            </div>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)
    else:
        st.warning("Noch keine Stats verfügbar.")
