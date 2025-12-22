def calculate_real_lineups(team_id, detailed_games):
    """
    Intelligenter Lineup-Tracker: 
    Verarbeitet Wechsel UND korrigiert die Aufstellung automatisch, 
    wenn Spielerinnen Aktionen ausführen, aber nicht eingewechselt wurden.
    """
    lineup_stats = {}
    tid_str = str(team_id)

    for box in detailed_games:
        actions = sorted(box.get("actions", []), key=lambda x: x.get('actionNumber', 0))
        h_id = str(box.get("homeTeam", {}).get("teamId"))
        is_home = (h_id == tid_str)
        
        # 1. Start-Aufstellung sicherstellen
        my_team_obj = box.get("homeTeam") if is_home else box.get("guestTeam")
        starters = [str(p.get("seasonPlayer",{}).get("id")) for p in my_team_obj.get("playerStats", []) if p.get("isStartingFive")]
        
        # Falls keine Starter markiert sind, nehmen wir die ersten 5, die eine Aktion haben
        current_lineup = set(starters[:5])
        
        last_time_total_secs = 0
        last_h_score = 0
        last_g_score = 0

        for act in actions:
            # Zeit-Berechnung (Absolut in Sekunden über das ganze Spiel)
            raw_time = act.get("gameTime", "00:00")
            try:
                parts = raw_time.split(':')
                # Wir rechnen: (Viertel-1)*600 + abgelaufene Sekunden im Viertel
                m, s = int(parts[-2]), int(parts[-1])
                current_time_total_secs = (act.get("period", 1)-1)*600 + (m*60 + s)
            except: 
                current_time_total_secs = last_time_total_secs

            # AUTOMATISCHE KORREKTUR (Wichtig!):
            # Wenn eine Spielerin eine Aktion macht (Punkt, Rebound etc.), MUSS sie auf dem Feld sein.
            act_pid = str(act.get("seasonPlayerId"))
            act_tid = str(act.get("seasonTeamId"))
            
            if act_tid == tid_str and act_pid and act_pid != "None":
                if act_pid not in current_lineup:
                    # Wenn wir schon 5 haben, kicken wir die "älteste" (einfache Heuristik)
                    if len(current_lineup) >= 5:
                        current_lineup.pop() 
                    current_lineup.add(act_pid)

            # Statistiken für das aktuelle Lineup loggen
            if len(current_lineup) == 5:
                l_key = tuple(sorted(list(current_lineup)))
                if l_key not in lineup_stats:
                    lineup_stats[l_key] = {"secs": 0, "pts_for": 0, "pts_agn": 0}
                
                duration = max(0, current_time_total_secs - last_time_total_secs)
                lineup_stats[l_key]["secs"] += duration
                
                new_h = safe_int(act.get("homeTeamPoints"))
                new_g = safe_int(act.get("guestTeamPoints"))
                
                if is_home:
                    lineup_stats[l_key]["pts_for"] += max(0, new_h - last_h_score)
                    lineup_stats[l_key]["pts_agn"] += max(0, new_g - last_g_score)
                else:
                    lineup_stats[l_key]["pts_for"] += max(0, new_g - last_g_score)
                    lineup_stats[l_key]["pts_agn"] += max(0, new_h - last_h_score)

            # Werte für nächsten Schritt speichern
            last_time_total_secs = current_time_total_secs
            last_h_score = safe_int(act.get("homeTeamPoints"))
            last_g_score = safe_int(act.get("guestTeamPoints"))

            # Offizielle Wechsel verarbeiten
            if act.get("type") == "SUBSTITUTION" and str(act.get("seasonTeamId")) == tid_str:
                p_out = str(act.get("seasonPlayerId"))
                p_in = str(act.get("relatedSeasonPlayerId"))
                if p_out in current_lineup: current_lineup.remove(p_out)
                if p_in and p_in != "None": current_lineup.add(p_in)

    # Ergebnisse aufbereiten
    final_lineups = []
    for ids, data in lineup_stats.items():
        if data["secs"] > 45: # Mindestens 45 Sekunden zusammen auf dem Feld
            final_lineups.append({
                "ids": list(ids),
                "min": f"{data['secs']//60:02d}:{data['secs']%60:02d}",
                "pkt": data["pts_for"],
                "opp": data["pts_agn"],
                "pm": data["pts_for"] - data["pts_agn"]
            })
    
    # Sortieren nach Plus/Minus (höchstes zuerst)
    return sorted(final_lineups, key=lambda x: x["pm"], reverse=True)[:3]
