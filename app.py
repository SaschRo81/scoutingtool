def render_analysis_page():
    st.button("🏠 Zurück zum Start", on_click=go_home)
    st.title("🎥 Spielnachbereitung")
    
    c1, c2 = st.columns([1, 2])
    with c1:
        staffel = st.radio("Staffel", ["Süd", "Nord"], horizontal=True, key="ana_staffel")
        teams_filtered = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == staffel}
        team_options = {v["name"]: k for k, v in teams_filtered.items()}
    with c2:
        my_team_name = st.selectbox("Dein Team:", list(team_options.keys()), key="ana_team")
        my_team_id = team_options[my_team_name]

    if my_team_id:
        games = fetch_schedule(my_team_id, SEASON_ID)
        if games:
            game_opts = {f"{g['date']} | {g['home']} vs {g['guest']} ({g['score']})": g['id'] for g in games}
            selected_label = st.selectbox("Wähle ein Spiel:", list(game_opts.keys()), key="ana_game_select")
            selected_id = game_opts[selected_label]
            
            if st.button("Analyse laden", type="primary"):
                st.session_state.selected_game_id = selected_id
                
            if st.session_state.selected_game_id == selected_id:
                st.divider()
                
                with st.spinner("Lade Boxscore..."):
                    box = fetch_game_boxscore(selected_id)
                    if box:
                        # 1. HEADER
                        render_game_header(box)
                        st.write("")

                        # 2. BOXSCORES (Namen werden jetzt IN der Funktion geholt)
                        # Wir übergeben hier nur noch den Fallback-Namen, falls alles schiefgeht
                        render_boxscore_table_pro(box.get("homeTeam", {}).get("playerStats", []), "Heimteam")
                        st.write("")
                        render_boxscore_table_pro(box.get("guestTeam", {}).get("playerStats", []), "Gastteam")
                        
                        st.divider()
                        
                        # 3. VERGLEICH & CHARTS
                        render_charts_and_stats(box)
                        
                    else:
                        st.error("Konnte Boxscore nicht laden.")
        else:
            st.warning("Keine Spiele gefunden.")
