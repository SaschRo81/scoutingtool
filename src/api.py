@st.cache_data(ttl=60)
def fetch_recent_games_combined():
    """
    Nutzt den /games/recent Endpunkt von Nord- und Süd-Servern, 
    um alle aktuellen Spiele (past, present, future) zu laden.
    """
    all_games = []
    # Wir fragen beide Subdomains ab, da 'recent' je nach Gruppe unterschiedlich sein kann
    for subdomain in ["api-s", "api-n"]:
        url = f"https://{subdomain}.dbbl.scb.world/games/recent?slotSize=200"
        
        try:
            resp = requests.get(url, headers=API_HEADERS, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                
                # Alle drei Kategorien (past, present, future) durchlaufen
                for slot in ["past", "present", "future"]:
                    if slot in data and isinstance(data[slot], list):
                        for g in data[slot]:
                            game_id = str(g.get("id"))
                            
                            # Eindeutige ID prüfen (verhindert Dopplungen)
                            if any(x['id'] == game_id for x in all_games):
                                continue
                            
                            # Zeitverarbeitung (Berlin Zeit)
                            raw_d = g.get("scheduledTime", "")
                            d_disp, date_only = "-", "-"
                            if raw_d:
                                try:
                                    dt_obj = datetime.fromisoformat(raw_d.replace("Z", "+00:00"))
                                    dt_berlin = dt_obj.astimezone(pytz.timezone("Europe/Berlin"))
                                    d_disp = dt_berlin.strftime("%d.%m.%Y %H:%M")
                                    date_only = dt_berlin.strftime("%d.%m.%Y")
                                except: pass
                            
                            # Score-Logik (homeScore / guestScore)
                            res = g.get("result") or {}
                            h_s = res.get("homeScore")
                            g_s = res.get("guestScore")
                            
                            # Fallback falls Felder anders benannt sind
                            if h_s is None: h_s = res.get("homeTeamFinalScore")
                            if g_s is None: g_s = res.get("guestTeamFinalScore")
                            
                            score = f"{h_s}:{g_s}" if h_s is not None else "-:-"
                            
                            all_games.append({
                                "id": game_id,
                                "date": d_disp,
                                "date_only": date_only,
                                "home": g.get("homeTeam", {}).get("name", "Heim"),
                                "guest": g.get("guestTeam", {}).get("name", "Gast"),
                                "score": score,
                                "status": g.get("status")
                            })
        except: continue
            
    return all_games
