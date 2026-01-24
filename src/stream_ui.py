def render_streaminfos_page():
    render_page_header("📡 Stream Overlays (OBS)")
    st.info("Hier kannst du Links generieren, die du als 'Browser Source' in OBS einfügst.")

    tab1, tab2, tab3, tab4 = st.tabs(["5️⃣ Starting 5", "🏆 Tabelle", "📊 Vergleich", "🔥 Player of the Game"])

    # 1. STARTING 5 (Getrennt für Heim/Gast)
    with tab1:
        st.markdown("### Teams & Starting 5 wählen")
        # Teams wählen (Süd Filter)
        south_teams = {k:v for k,v in TEAMS_DB.items() if v["staffel"] == "Süd"}
        team_opts = {v["name"]: k for k,v in south_teams.items()}
        
        col_home, col_guest = st.columns(2)
        
        # --- HEIM TEAM CONFIG ---
        with col_home:
            st.markdown("#### 🏠 Heimteam")
            h_name = st.selectbox("Team wählen", list(team_opts.keys()), key="obs_h_sel")
            h_id = team_opts[h_name]
            h_coach = st.text_input("Head Coach Name", key="obs_h_coach") # Manuelles Feld für Coach
            
            st.write("Wähle 5 Spieler:")
            df_h, _ = fetch_team_data(h_id, CURRENT_SEASON_ID)
            h_players = []
            if df_h is not None and not df_h.empty:
                p_map_h = {f"#{r['NR']} {r['NAME_FULL']}": {"id": r["PLAYER_ID"], "nr": r["NR"], "name": r["NAME_FULL"]} for _, r in df_h.iterrows()}
                sel_h = st.multiselect("Kader Heim", list(p_map_h.keys()), max_selections=5, key="obs_h_p")
                for s in sel_h: h_players.append(p_map_h[s])
            
            if st.button("🔗 Link HEIM generieren", type="primary"):
                if len(h_players) < 1: st.warning("Wähle Spieler aus.")
                else:
                    params = {
                        "view": "obs_starting5",
                        "name": h_name,
                        "logo_id": h_id,
                        "coach": h_coach,
                        "ids": ",".join([p["id"] for p in h_players])
                    }
                    for p in h_players: 
                        params[f"n_{p['id']}"] = p["name"]
                        params[f"nr_{p['id']}"] = p["nr"]
                    
                    qs = urlencode(params)
                    st.code(f"/?{qs}", language="text")
                    st.success("Kopiere diesen Link für die Heim-Szene in OBS.")

        # --- GAST TEAM CONFIG ---
        with col_guest:
            st.markdown("#### 🚌 Gastteam")
            g_name = st.selectbox("Team wählen", list(team_opts.keys()), index=1, key="obs_g_sel")
            g_id = team_opts[g_name]
            g_coach = st.text_input("Head Coach Name", key="obs_g_coach")
            
            st.write("Wähle 5 Spieler:")
            df_g, _ = fetch_team_data(g_id, CURRENT_SEASON_ID)
            g_players = []
            if df_g is not None and not df_g.empty:
                p_map_g = {f"#{r['NR']} {r['NAME_FULL']}": {"id": r["PLAYER_ID"], "nr": r["NR"], "name": r["NAME_FULL"]} for _, r in df_g.iterrows()}
                sel_g = st.multiselect("Kader Gast", list(p_map_g.keys()), max_selections=5, key="obs_g_p")
                for s in sel_g: g_players.append(p_map_g[s])

            if st.button("🔗 Link GAST generieren", type="primary"):
                if len(g_players) < 1: st.warning("Wähle Spieler aus.")
                else:
                    params = {
                        "view": "obs_starting5",
                        "name": g_name,
                        "logo_id": g_id,
                        "coach": g_coach,
                        "ids": ",".join([p["id"] for p in g_players])
                    }
                    for p in g_players: 
                        params[f"n_{p['id']}"] = p["name"]
                        params[f"nr_{p['id']}"] = p["nr"]
                    
                    qs = urlencode(params)
                    st.code(f"/?{qs}", language="text")
                    st.success("Kopiere diesen Link für die Gast-Szene in OBS.")

    # 2. TABELLE
    with tab2:
        st.write("Generiert eine Ansicht der Südstaffel-Tabelle.")
        if st.button("🔗 Link Tabelle"):
            st.code("/?view=obs_standings&region=Süd&season=2025", language="text")

    # 3. VERGLEICH
    with tab3:
        h_c = st.selectbox("Team A", list(team_opts.keys()), key="obs_comp_h")
        g_c = st.selectbox("Team B", list(team_opts.keys()), index=1, key="obs_comp_g")
        if st.button("🔗 Link Vergleich"):
            params = {
                "view": "obs_comparison",
                "hid": team_opts[h_c], "gid": team_opts[g_c],
                "hname": h_c, "gname": g_c
            }
            st.code(f"/?{urlencode(params)}", language="text")

    # 4. PLAYER OF THE GAME
    with tab4:
        st.write("Verbindet sich mit dem Live-Game und zeigt den MVP (basierend auf Effizienz) an.")
        # Nutze die Recent Games Logik aus app.py, aber vereinfacht
        from src.api import fetch_schedule
        # Wir nehmen einfach ein Team, um an den Spielplan zu kommen, oder User gibt ID ein
        st.caption("Suche Spiel über Team:")
        sel_t = st.selectbox("Team wählen", list(team_opts.keys()), key="obs_potg_t")
        sch = fetch_schedule(team_opts[sel_t], CURRENT_SEASON_ID)
        
        # Filtere auf heutige/zukünftige/gerade beendete
        game_opts = {f"{g['date']} vs {g['guest'] if g['home']==sel_t else g['home']}": g['id'] for g in sch}
        sel_g = st.selectbox("Spiel wählen", list(game_opts.keys()))
        
        if st.button("🔗 Link POTG"):
            gid = game_opts[sel_g]
            st.code(f"/?view=obs_potg&game_id={gid}", language="text")
            st.caption("Dieser Link aktualisiert sich in OBS automatisch alle 30 Sekunden.")
