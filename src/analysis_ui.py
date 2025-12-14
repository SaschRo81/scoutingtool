def render_full_play_by_play(box, height=600):
    """Rendert eine detaillierte Play-by-Play Tabelle auf Deutsch (Neueste zuerst)."""
    actions = box.get("actions", [])
    if not actions:
        st.info("Keine Play-by-Play Daten verfügbar.")
        return

    player_map = get_player_lookup(box)
    player_team_map = get_player_team_lookup(box)
    
    home_name = get_team_name(box.get("homeTeam", {}), "Heim")
    guest_name = get_team_name(box.get("guestTeam", {}), "Gast")
    home_id = str(box.get("homeTeam", {}).get("seasonTeamId", "HOME"))
    guest_id = str(box.get("guestTeam", {}).get("seasonTeamId", "GUEST"))

    data = []
    
    # Laufenden Score berechnen (Chronologisch durchgehen)
    running_h = 0
    running_g = 0

    for act in actions:
        h_pts = act.get("homeTeamPoints")
        g_pts = act.get("guestTeamPoints")
        
        # Score aktualisieren, falls im Datensatz vorhanden
        if h_pts is not None: running_h = safe_int(h_pts)
        if g_pts is not None: running_g = safe_int(g_pts)
        
        score_str = f"{running_h} : {running_g}"
        
        period = act.get("period", "")
        game_time = act.get("gameTime", "") 
        time_in_game = act.get("timeInGame", "") 
        
        if game_time:
            display_time = convert_elapsed_to_remaining(game_time, period)
        else:
            display_time = "-"
            if time_in_game and "M" in time_in_game:
                try:
                    t = time_in_game.replace("PT", "").replace("S", "")
                    m, s = t.split("M")
                    display_time = f"{m}:{s.zfill(2)}"
                except: pass

        time_label = f"Q{period} {display_time}" if period else "-"
        
        pid = str(act.get("seasonPlayerId"))
        actor = player_map.get(pid, "")
        
        tid = str(act.get("seasonTeamId"))
        if tid == home_id:
            team_display = home_name
        elif tid == guest_id:
            team_display = guest_name
        elif pid in player_team_map: 
            team_display = player_team_map[pid]
        else:
            team_display = "-" 

        raw_type = act.get("type", "")
        action_german = translate_text(raw_type)
        
        is_successful = act.get("isSuccessful")
        if "Wurf" in action_german or "Freiwurf" in action_german or "Treffer" in action_german or "Fehlwurf" in action_german:
             if "Treffer" not in action_german and "Fehlwurf" not in action_german:
                 if is_successful is True:
                     action_german += " (Treffer)"
                 elif is_successful is False:
                     action_german += " (Fehlwurf)"

        qualifiers = act.get("qualifiers", [])
        if qualifiers:
            qual_german = [translate_text(q) for q in qualifiers]
            action_german += f" ({', '.join(qual_german)})"
        
        if act.get("points"):
            action_german += f" (+{act.get('points')})"

        data.append({
            "Zeit": time_label,
            "Score": score_str,
            "Team": team_display,
            "Spieler": actor,
            "Aktion": action_german
        })

    df = pd.DataFrame(data)
    
    # WICHTIG: Immer umdrehen, damit die neuste Aktion oben steht
    if not df.empty:
        df = df.iloc[::-1]

    st.dataframe(df, use_container_width=True, hide_index=True, height=height)

def render_live_view(box):
    """Zeigt Live Stats und PBP nebeneinander für Mobile optimiert."""
    if not box: return

    # Team Namen
    h_name = get_team_name(box.get("homeTeam", {}), "Heim")
    g_name = get_team_name(box.get("guestTeam", {}), "Gast")
    
    # Metadaten Score (kann verzögert sein)
    res = box.get("result", {})
    s_h = res.get("homeTeamFinalScore", 0)
    s_g = res.get("guestTeamFinalScore", 0)
    
    actions = box.get("actions", [])
    period = res.get("period") or box.get("period", 1)
    
    # LOGIK-UPDATE: Wir schauen IMMER in die letzte Aktion für den aktuellsten Score.
    # Die DBBL API Result-Objekte hinken oft 30sek hinterher, die Actions sind live.
    last_h_live = 0
    last_g_live = 0
    found_score = False

    if actions:
        # Rückwärts suchen nach dem letzten validen Punktestand
        for act in reversed(actions):
            if act.get("homeTeamPoints") is not None and act.get("guestTeamPoints") is not None:
                last_h_live = safe_int(act.get("homeTeamPoints"))
                last_g_live = safe_int(act.get("guestTeamPoints"))
                if not period: period = act.get("period")
                found_score = True
                break
    
    # Wenn wir einen Score aus den Actions haben, nutzen wir diesen bevorzugt für die Anzeige
    if found_score:
        s_h = last_h_live
        s_g = last_g_live
    
    # Mapping Period
    p_map = {1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"}
    if safe_int(period) > 4: p_str = f"OT{safe_int(period)-4}"
    else: p_str = p_map.get(safe_int(period), f"Q{period}") if period else "-"
    
    time_str = convert_elapsed_to_remaining(box.get('gameTime', ''), period)

    # Scoreboard
    st.markdown(f"""
    <div style='text-align: center; background-color: #222; color: #fff; padding: 10px; border-radius: 10px; margin-bottom: 20px;'>
        <div style='font-size: 1.2em;'>{h_name} vs {g_name}</div>
        <div style='font-size: 3em; font-weight: bold;'>{s_h} : {s_g}</div>
        <div style='font-size: 0.9em; color: #ccc;'>{p_str} | {time_str}</div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns([1, 1])
    
    with c1:
        st.subheader("📊 Live Stats")
        
        # Funktion zum Erstellen der Spieler-Tabelle
        def create_live_player_table(team_data):
            players = team_data.get("playerStats", [])
            data = []
            for p in players:
                # Stats extrahieren
                sec = safe_int(p.get("secondsPlayed"))
                min_s = f"{int(sec//60):02d}:{int(sec%60):02d}" if sec > 0 else "00:00"
                
                # Nur Spieler anzeigen, die gespielt haben oder im Boxscore relevant sind
                if sec > 0 or safe_int(p.get("points")) > 0:
                    data.append({
                        "Nr": p.get('seasonPlayer', {}).get('shirtNumber', '-'),
                        "Name": p.get('seasonPlayer', {}).get('lastName', 'Unk'),
                        "Min": min_s,
                        "PTS": safe_int(p.get("points")),
                        "PF": safe_int(p.get("foulsCommitted"))
                    })
            
            # DataFrame erstellen und sortieren nach PTS
            df = pd.DataFrame(data)
            if not df.empty:
                df = df.sort_values(by="PTS", ascending=False)
            return df

        # Tabellen erstellen
        df_home = create_live_player_table(box.get("homeTeam", {}))
        df_guest = create_live_player_table(box.get("guestTeam", {}))

        # Anzeigen
        st.markdown(f"**{h_name}**")
        st.dataframe(df_home, hide_index=True, use_container_width=True)
        
        st.write("")
        st.markdown(f"**{g_name}**")
        st.dataframe(df_guest, hide_index=True, use_container_width=True)

    with c2:
        st.subheader("📜 Live Ticker")
        render_full_play_by_play(box, height=800)
