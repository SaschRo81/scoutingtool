# --- START OF FILE src/analysis_ui.py ---
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import pytz
import openai 
from src.config import SEASON_ID
from src.api import fetch_standings

# ... (der ganze obere Teil der Datei bleibt unverändert) ...
# ... (ACTION_TRANSLATION, helper functions, etc.) ...
# ...
def render_prep_dashboard(team_id, team_name, df_roster, last_games, metadata_callback=None, staffel="Süd"):
    st.subheader(f"Analyse: {team_name}")
    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.markdown("#### Top 4 Spieler (nach PPG)")
        if df_roster is not None and not df_roster.empty:
            top4 = df_roster.sort_values(by="PPG", ascending=False).head(4)
            for _, row in top4.iterrows():
                with st.container():
                    col_img, col_stats = st.columns([1, 4])
                    
                    age = row.get('AGE', '-')
                    nat = row.get('NATIONALITY', '-')
                    height = row.get('HEIGHT_ROSTER', '-')

                    img_url = None
                    if metadata_callback:
                        meta = None
                        if age in ["-", ""] or nat in ["-", ""] or height in ["-", ""] or not row.get("img"):
                            meta = metadata_callback(row["PLAYER_ID"])
                        
                        if meta:
                            if age in ["-", ""]: age = meta.get("age", "-")
                            if nat in ["-", ""]: nat = meta.get("nationality", "-")
                            if height in ["-", ""]: height = meta.get("height", "-")
                            img_url = meta.get("img")
                        else:
                            img_url = row.get("img")
                    else:
                        img_url = row.get("img")

                    with col_img:
                        if img_url:
                            st.image(img_url, width=100)
                        else:
                            st.markdown(f"<div style='font-size:30px; text-align:center;'>👤</div>", unsafe_allow_html=True)

                    with col_stats:
                        st.markdown(f"**#{row['NR']} {row['NAME_FULL']}**")
                        st.caption(f"Alter: {age} | Nat: {nat} | Größe: {height}")
                        st.markdown(f"**PPG: {row['PPG']}** | FG%: {row['FG%']} | 3P%: {row['3PCT']}% | REB: {row['TOT']} | AST: {row['AS']}")
                    st.divider()
        else: st.warning("Keine Kaderdaten.")

    with c2:
        st.markdown("#### Formkurve")
        if last_games:
            played_games = [g for g in last_games if g.get('has_result')]
            def parse_date(d_str):
                try: return datetime.strptime(d_str, "%d.%m.%Y %H:%M")
                except: return datetime.min
            
            games_sorted = sorted(played_games, key=lambda x: parse_date(x['date']), reverse=True)[:5]
            if games_sorted:
                st.write("") 
                cols_form = st.columns(len(games_sorted))
                for idx, g in enumerate(games_sorted):
                    h_score = g.get('home_score', 0)
                    g_score = g.get('guest_score', 0)
                    is_home = (g.get('homeTeamId') == str(team_id))
                    
                    win = False
                    if is_home and h_score > g_score: win = True
                    elif not is_home and g_score > h_score: win = True
                    
                    color = "#28a745" if win else "#dc3545"
                    char = "W" if win else "L"
                    
                    with cols_form[idx]:
                        st.markdown(f"<div style='background-color:{color};color:white;text-align:center;padding:10px;border-radius:5px;font-weight:bold;' title='{g['date']}\n{g['home']} vs {g['guest']}\n{g['score']}'>{char}</div>", unsafe_allow_html=True)
            else: st.info("Keine gespielten Spiele.")
        else: st.info("Keine Spiele.")
        
        st.write("")
        st.markdown("#### Aktueller Tabellenplatz")
        
        standings_map = fetch_standings(SEASON_ID, staffel)
        
        if standings_map:
            team_stat = standings_map.get(str(team_id))
            if team_stat:
                rank = team_stat.get("rank", "-")
                team_n = team_stat.get("team", {}).get("name", team_name)
                played = team_stat.get("matchesPlayed", 0)
                wins = team_stat.get("wins", 0)
                losses = team_stat.get("losses", 0)
                pts = team_stat.get("points", 0)
                diff = team_stat.get("pointsDifference", 0)
                streak = team_stat.get("streak", "-")
                
                html_table = f"""
                <table style="width:100%; font-size:12px; border-collapse: collapse; text-align: center;">
                    <tr style="background-color: #f0f0f0; border-bottom: 1px solid #ddd;">
                        <th style="padding: 4px;">PL</th><th style="padding: 4px; text-align: left;">Team</th><th>G</th><th>S</th><th>N</th><th>PKT</th><th>Diff</th><th>Serie</th>
                    </tr>
                    <tr style="border-bottom: 1px solid #eee;">
                        <td style="font-weight: bold;">{rank}</td>
                        <td style="text-align: left;">{team_n}</td>
                        <td>{played}</td>
                        <td style="color: green;">{wins}</td>
                        <td style="color: red;">{losses}</td>
                        <td style="font-weight: bold;">{pts}</td>
                        <td>{diff}</td>
                        <td>{streak}</td>
                    </tr>
                </table>
                """
                st.markdown(html_table, unsafe_allow_html=True)
            else:
                 st.warning(f"Team (ID: {team_id}) nicht in den Tabellendaten für Staffel '{staffel}' (Saison {SEASON_ID}) gefunden.")
        else:
            st.warning(f"Tabellendaten für Staffel '{staffel}' (Saison {SEASON_ID}) konnten nicht geladen werden. Bitte prüfen Sie die `SEASON_ID` und die Netzwerkverbindung.")

# ... (Rest der Datei, render_live_view etc. bleibt unverändert) ...
