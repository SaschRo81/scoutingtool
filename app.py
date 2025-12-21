import streamlit as st
import pandas as pd
import requests  
from datetime import datetime, date, time 
import time as time_module 
from urllib.parse import quote_plus 
import base64 
import pytz # <--- NEU HINZUGEFÜGT

# ... (restliche Imports und Konfigurationen bleiben gleich)

def render_live_page():
    # 1. Detailansicht: Wenn ein Spiel ausgewählt wurde
    if st.session_state.live_game_id:
        c_back, c_title = st.columns([1, 5])
        with c_back:
            if st.button("⬅️ Zurück zur Liste", key="live_back_btn"): 
                st.session_state.live_game_id = None
                st.rerun()
        
        gid = st.session_state.live_game_id
        auto = st.checkbox("🔄 Auto-Refresh (15s)", value=True)
        st.divider()
        
        # Daten abrufen
        box = fetch_game_boxscore(gid)
        det = fetch_game_details(gid)
        
        if box:
            if det:
                box["gameTime"] = det.get("gameTime")
                box["period"] = det.get("period")
                box["result"] = det.get("result")
            render_live_view(box)
            if auto:
                time_module.sleep(15)
                st.rerun()
        else:
            st.error("Keine Live-Daten für dieses Spiel verfügbar.")

    # 2. Heutige Spiele Übersicht
    else:
        render_page_header("🔴 Live Game Center")
        
        # Aktuelles Datum in Berlin ermitteln
        berlin_tz = pytz.timezone("Europe/Berlin")
        today_str = datetime.now(berlin_tz).strftime("%d.%m.%Y")
        
        st.markdown(f"### Spiele von heute ({today_str})")
        
        with st.spinner("Lade aktuellen Spielplan..."): 
            # Nutzt die neue kombinierte Recent-Logik aus der api.py
            from src.api import fetch_recent_games_combined
            all_games = fetch_recent_games_combined()
        
        # Strenge Filterung auf das heutige Datum
        todays_games = [g for g in all_games if g['date_only'] == today_str]
        
        if not todays_games:
            st.info(f"Für heute ({today_str}) sind aktuell keine Spiele im Live-Pool gefunden worden.")
            
            # Debug-Hilfe, falls gar nichts angezeigt wird
            if all_games:
                with st.expander("System-Status"):
                    st.write(f"Gesamt-Pool: {len(all_games)} Spiele geladen.")
                    st.write("Spiele heute nicht dabei. Prüfe die nächsten anstehenden:")
                    future_games = [g for g in all_games if g['status'] not in ["ENDED", "CLOSED"]]
                    future_games.sort(key=lambda x: x['date'])
                    for fg in future_games[:3]:
                        st.write(f"- {fg['date']}: {fg['home']} vs {fg['guest']}")
        else:
            # Sortieren nach Uhrzeit
            todays_games.sort(key=lambda x: x['date'])
            
            cols = st.columns(3) 
            for i, game in enumerate(todays_games):
                col = cols[i % 3]
                with col:
                    with st.container(border=True):
                        # Status-Design
                        is_live = game['status'] in ["RUNNING", "LIVE"]
                        status_color = "#d9534f" if is_live else "#555"
                        status_text = "🔴 LIVE" if is_live else game['date'].split(' ')[1] + " Uhr"
                        
                        st.markdown(f"""
                            <div style="text-align:center;">
                                <div style="font-weight:bold; color:{status_color};">{status_text}</div>
                                <div style="margin:10px 0; font-size:1.1em;">
                                    <b>{game['home']}</b><br>vs<br><b>{game['guest']}</b>
                                </div>
                                <div style="font-size:1.5em; font-weight:bold;">{game['score']}</div>
                            </div>
                        """, unsafe_allow_html=True)
                        
                        if st.button("Scouten", key=f"btn_live_{game['id']}", use_container_width=True):
                            st.session_state.live_game_id = game['id']
                            st.rerun()
