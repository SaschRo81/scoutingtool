# --- TEIL VON src/analysis_ui.py ---
# (Stelle sicher, dass fetch_team_rank oben importiert ist, falls du Imports explizit machst, 
# oder lade es über src.api)

from src.api import fetch_team_rank # <-- Falls nötig oben importieren oder in src/api.py sicherstellen

def render_prep_dashboard(team_id, team_name, df_roster, last_games, metadata_callback=None):
    # Rank holen
    from src.config import CURRENT_SEASON_ID # Sicherstellen, dass die ID da ist
    rank_info = fetch_team_rank(team_id, CURRENT_SEASON_ID)

    st.subheader(f"Analyse: {team_name}")
    
    # Layout Spalten
    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.markdown("#### Top 4 Spieler (nach PPG)")
        if df_roster is not None and not df_roster.empty:
            # Sortieren
            top4 = df_roster.sort_values(by="PPG", ascending=False).head(4)
            
            for _, row in top4.iterrows():
                with st.container(border=True):
                    col_img, col_stats = st.columns([1, 3])
                    
                    # Metadaten holen
                    age = row.get('AGE', '-')
                    nat = row.get('NATIONALITY', '-')
                    height = row.get('HEIGHT_ROSTER', '-') 
                    img_url = None
                    if metadata_callback:
                        meta = metadata_callback(row["PLAYER_ID"])
                        if meta:
                            if age in ["-", ""]: age = meta.get("age", "-")
                            if nat in ["-", ""]: nat = meta.get("nationality", "-")
                            if height in ["-", ""]: height = meta.get("height", "-")
                            img_url = meta.get("img")
                    
                    with col_img:
                        if img_url:
                            st.image(img_url, width=110)
                        else:
                            st.markdown(f"<div style='font-size:40px; text-align:center;'>👤</div>", unsafe_allow_html=True)

                    with col_stats:
                        st.markdown(f"**#{row['NR']} {row['NAME_FULL']}** <span style='color:gray; font-size:0.9em;'>({age} J | {nat} | {height})</span>", unsafe_allow_html=True)
                        
                        # Neue Tabellen-Ansicht für Stats
                        stats_html = f"""
                        <table style="width:100%; text-align:center; border-collapse: collapse; font-size: 14px;">
                            <tr style="background-color: #f0f0f0; border-bottom: 1px solid #ddd; color: #555;">
                                <th style="padding: 4px;">PPG</th>
                                <th style="padding: 4px;">FG%</th>
                                <th style="padding: 4px;">3P%</th>
                                <th style="padding: 4px;">REB</th>
                                <th style="padding: 4px;">AST</th>
                            </tr>
                            <tr style="font-weight: bold;">
                                <td style="padding: 4px; color: #333;">{row['PPG']}</td>
                                <td style="padding: 4px;">{row['FG%']}%</td>
                                <td style="padding: 4px;">{row['3PCT']}%</td>
                                <td style="padding: 4px;">{row['TOT']}</td>
                                <td style="padding: 4px;">{row['AS']}</td>
                            </tr>
                        </table>
                        """
                        st.markdown(stats_html, unsafe_allow_html=True)
        else:
            st.warning("Keine Kaderdaten verfügbar.")

    with c2:
        # --- TEIL 1: TABELLENPLATZ ---
        st.markdown("#### Aktueller Status")
        if rank_info:
            r = rank_info['rank']
            w = rank_info['wins']
            l = rank_info['losses']
            pts = rank_info['points']
            
            # Farbe je nach Platzierung (Top 8 Playoff grün, unten rot)
            rank_color = "#28a745" if r <= 8 else "#6c757d"
            if r >= 11: rank_color = "#dc3545"

            st.markdown(f"""
            <div style="background-color: white; border: 1px solid #ddd; border-radius: 10px; padding: 15px; text-align: center; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                <div style="font-size: 14px; color: #666; margin-bottom: 5px;">Tabellenplatz</div>
                <div style="font-size: 48px; font-weight: bold; color: {rank_color}; line-height: 1;">{r}.</div>
                <div style="margin-top: 10px; font-size: 16px; font-weight: bold;">
                    {w} Siege - {l} Niederlagen
                </div>
                <div style="font-size: 12px; color: #888;">{pts} Punkte</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Tabellenplatz konnte nicht geladen werden.")

        # --- TEIL 2: FORMKURVE ---
        st.markdown("#### Formkurve (Letzte 5)")
        if last_games:
            played_games = [g for g in last_games if g.get('has_result')]
            def parse_date(d_str):
                try: return datetime.strptime(d_str, "%d.%m.%Y %H:%M")
                except: return datetime.min
            
            # Sortiere nach Datum absteigend, nimm die letzten 5
            games_sorted = sorted(played_games, key=lambda x: parse_date(x['date']), reverse=True)[:5]
            
            if games_sorted:
                # Wir drehen die Liste um, damit links das älteste der 5 und rechts das aktuellste ist (klassische Lesart) 
                # ODER wir lassen es so: Links = Neuestes. Meistens ist Links = Neuestes bei "Last 5 Games".
                # Ich lasse es Links = Neuestes (Matchday -1).
                
                cols_form = st.columns(5)
                for idx, g in enumerate(games_sorted):
                    h_score = g.get('home_score', 0)
                    g_score = g.get('guest_score', 0)
                    is_home = (g.get('homeTeamId') == str(team_id))
                    
                    # Win/Loss Logik
                    win = False
                    if is_home and h_score > g_score: win = True
                    elif not is_home and g_score > h_score: win = True
                    
                    bg_color = "#28a745" if win else "#dc3545" 
                    char = "W" if win else "L"
                    score_text = f"{g['home_score']}:{g['guest_score']}"
                    opp_name = g['guest'] if is_home else g['home']
                    # Kurzname Gegner (erste 3 Buchstaben)
                    opp_short = opp_name[:3].upper()
                    loc_char = "vs" if is_home else "@"

                    tooltip_text = f"{g['date'].split(' ')[0]} | {loc_char} {opp_name} ({score_text})"
                    
                    with cols_form[idx]:
                        st.markdown(f"""
                        <div style='background-color:{bg_color}; color:white; text-align:center; padding:5px 0; border-radius:5px; font-weight:bold; font-size:14px; margin-bottom:2px;' title='{tooltip_text}'>
                            {char}
                        </div>
                        <div style='text-align:center; font-size:10px; color:#555;'>
                            {loc_char} {opp_short}
                        </div>
                        """, unsafe_allow_html=True)
            else: 
                st.info("Keine gespielten Spiele.")
        else: 
            st.info("Keine Spiele.")
