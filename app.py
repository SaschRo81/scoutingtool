if st.session_state.selected_game_id == selected_id:
                st.divider()
                
                with st.spinner("Lade Spieldaten..."):
                    # BEIDE APIs aufrufen:
                    box = fetch_game_boxscore(selected_id)
                    details = fetch_game_details(selected_id)
                    
                    # Wenn wir Boxscore haben, nehmen wir den. Wenn nicht, aber Details da sind, versuchen wir es damit.
                    # Am besten: Wir "mergen" die Details (Header-Infos) in den Boxscore, falls der Boxscore da ist.
                    
                    if box and details:
                        # Schreibe wichtige Meta-Daten aus Details in das Box-Objekt für render_game_header
                        box["venue"] = details.get("venue")
                        box["result"] = details.get("result")
                        box["referee1"] = details.get("referee1")
                        box["referee2"] = details.get("referee2")
                        box["referee3"] = details.get("referee3")
                        # ... usw
                        
                        render_game_header(details) # Header nutzt jetzt direkt das details Objekt!
                        st.write("")

                        h_name = get_team_name(box.get("homeTeam", {}), "Heim")
                        g_name = get_team_name(box.get("guestTeam", {}), "Gast")
                        
                        render_boxscore_table_pro(box.get("homeTeam", {}).get("playerStats", []), h_name)
                        st.write("")
                        render_boxscore_table_pro(box.get("guestTeam", {}).get("playerStats", []), g_name)
                        
                        st.divider()
                        
                        render_game_top_performers(box)
                        st.divider()
                        render_charts_and_stats(box)
                        
                    elif box: # Fallback: Nur Boxscore da
                         render_game_header(box)
                         # ... Rest wie oben ...
                    elif details: # Nur Details da (noch keine Stats?)
                         render_game_header(details)
                         st.info("Noch keine Spieler-Statistiken verfügbar.")
                    else:
                        st.error("Konnte Spieldaten nicht laden.")
