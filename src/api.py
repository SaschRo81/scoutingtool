# --- START OF FILE api.py ---

import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import pytz
from src.config import API_HEADERS, SEASON_ID 
from src.utils import optimize_image_base64, format_minutes

@st.cache_data(ttl=600, show_spinner="Lade Spieler-Metadaten...")
def get_player_metadata_cached(player_id):
    try:
        url = f"https://api-s.dbbl.scb.world/season-players/{player_id}"
        resp = requests.get(url, headers=API_HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            raw_img = data.get("imageUrl", "")
            opt_img = optimize_image_base64(raw_img) if raw_img else ""
            return {
                "img": opt_img,
                "height": data.get("height", 0),
                "pos": data.get("position", "-"),
            }
    except Exception as e:
        print(f"DEBUG: Fehler in get_player_metadata_cached für Player-ID {player_id}: {e}")
        pass
    return {"img": "", "height": 0, "pos": "-"}

@st.cache_data(ttl=600)
def fetch_team_data(team_id, season_id):
    """Lädt Kader und Team-Statistiken für die Saison."""
    api_url = f"https://api-s.dbbl.scb.world/teams/{team_id}/{season_id}/player-stats"
    api_team = f"https://api-s.dbbl.scb.world/seasons/{season_id}/team-statistics?displayType=MAIN_ROUND&teamId={team_id}"
    
    print(f"DEBUG: fetch_team_data startet für Team {team_id}, Saison {season_id}")
    print(f"DEBUG: API URL (Spielerstats): {api_url}")
    print(f"DEBUG: API URL (Teamstats): {api_team}")

    try:
        resp_players = requests.get(api_url, headers=API_HEADERS)
        resp_team_stats = requests.get(api_team, headers=API_HEADERS)
        
        print(f"DEBUG: Spielerstats API Status: {resp_players.status_code}")
        print(f"DEBUG: Teamstats API Status: {resp_team_stats.status_code}")

        if resp_players.status_code != 200:
            print(f"DEBUG: Fehler beim Abrufen der Spielerstatistik. Status: {resp_players.status_code}, Antwort: {resp_players.text[:200]}")
            return None, None
        if resp_team_stats.status_code != 200:
            print(f"DEBUG: Fehler beim Abrufen der Teamstatistik. Status: {resp_team_stats.status_code}, Antwort: {resp_team_stats.text[:200]}")
            return None, None

        raw_player_data = resp_players.json()
        raw_team_stats_list = resp_team_stats.json()

        print(f"DEBUG: Raw Spielerdaten Typ: {type(raw_player_data)}, Länge/Keys: {len(raw_player_data) if isinstance(raw_player_data, list) else list(raw_player_data.keys()) if isinstance(raw_player_data, dict) else 'n/a'}")
        print(f"DEBUG: Raw Teamstats Typ: {type(raw_team_stats_list)}, Länge/Keys: {len(raw_team_stats_list) if isinstance(raw_team_stats_list, list) else list(raw_team_stats_list.keys()) if isinstance(raw_team_stats_list, dict) else 'n/a'}")

        # 1. Team Stats
        ts = {}
        if raw_team_stats_list and isinstance(raw_team_stats_list, list) and len(raw_team_stats_list) > 0:
            td = raw_team_stats_list[0] 
            blocks = td.get("blocksPerGame", td.get("blockedShotsPerGame", 0))
            ts = {
                "ppg": td.get("pointsPerGame", 0), 
                "2m": td.get("twoPointShotsMadePerGame", 0), "2a": td.get("twoPointShotsAttemptedPerGame", 0), "2pct": td.get("twoPointShotsSuccessPercent", 0),
                "3m": td.get("threePointShotsMadePerGame", 0), "3a": td.get("threePointShotsAttemptedPerGame", 0), "3pct": td.get("threePointShotsSuccessPercent", 0),
                "ftm": td.get("freeThrowsMadePerGame", 0), "fta": td.get("freeThrowsAttemptedPerGame", 0), "ftpct": td.get("freeThrowsSuccessPercent", 0),
                "dr": td.get("defensiveReboundsPerGame", 0), "or": td.get("offensiveReboundsPerGame", 0), "tot": td.get("totalReboundsPerGame", 0),
                "as": td.get("assistsPerGame", 0), "to": td.get("turnoversPerGame", 0), "st": td.get("stealsPerGame", 0),
                "bs": blocks, "pf": td.get("foulsCommittedPerGame", 0)
            }
            print(f"DEBUG: Teamstats erfolgreich geparst: {ts.get('ppg')} PPG")
        else:
            print("DEBUG: Keine Teamstatistik-Daten gefunden oder Liste leer.")

        # 2. Player Stats
        df = None
        player_list = raw_player_data if isinstance(raw_player_data, list) else raw_player_data.get("data", [])
        if player_list:
            df = pd.json_normalize(player_list)
            df.columns = [str(c).lower() for c in df.columns]
            
            col_map = {
                "firstname": ["person.firstname", "firstname"], "lastname": ["person.lastname", "lastname"],
                "shirtnumber": ["jerseynumber", "shirtnumber", "no"], "id": ["id", "person.id", "personid"],
                "gp": ["matches", "gamesplayed", "games"], "ppg": ["pointspergame"], "tot": ["totalreboundspergame"],
                "min_sec": ["secondsplayedpergame", "minutespergame", "avgminutes"], "sec_total": ["secondsplayed"],
                "2m": ["twopointshotsmadepergame"], "2a": ["twopointshotsattemptedpergame"], "2pct": ["twopointshotsuccesspercent"],
                "3m": ["threepointshotsmadepergame"], "3a": ["threepointshotsattemptedpergame"], "3pct": ["threepointshotsuccesspercent"],
                "ftm": ["freethrowsmadepergame"], "fta": ["freethrowsattemptedpergame"], "ftpct": ["freethrowssuccesspercent"],
                "dr": ["defensivereboundspergame"], "or": ["offensivereboundspergame"], "as": ["assistspergame"],
                "to": ["turnoverspergame"], "st": ["stealspergame"], "pf": ["foulscommittedpergame"], "bs": ["blockspergame"]
            }
            
            final_cols = {}
            for t, p_list in col_map.items():
                for p in p_list:
                    m = [c for c in df.columns if p == c] 
                    if m: final_cols[t] = m[0]; break 
            
            fn_col = final_cols.get("firstname")
            ln_col = final_cols.get("lastname")
            sn_col = final_cols.get("shirtnumber")
            id_col = final_cols.get("id")

            # KORRIGIERTER BEREICH: Sicherstellen, dass immer Series-Objekte verwendet werden
            firstname_series = df[fn_col].fillna("") if fn_col and fn_col in df.columns else pd.Series([""] * len(df), index=df.index)
            lastname_series = df[ln_col].fillna("") if ln_col and ln_col in df.columns else pd.Series([""] * len(df), index=df.index)

            df["NAME_FULL"] = (firstname_series + " " + lastname_series).str.strip()

            df["NR"] = df[sn_col].fillna("-").astype(str).str.replace(".0", "", regex=False) if sn_col and sn_col in df.columns else pd.Series(["-"] * len(df), index=df.index)
            df["PLAYER_ID"] = df[id_col].astype(str) if id_col and id_col in df.columns else pd.Series([""] * len(df), index=df.index)
            
            def get_v(k): 
                col_name = final_cols.get(k)
                if col_name and col_name in df.columns:
                    return pd.to_numeric(df[col_name], errors="coerce").fillna(0)
                return pd.Series([0.0]*len(df), index=df.index) # Wichtig: Gleicher Index für Series-Operationen
            
            def pct(v): 
                return round(v*100, 1) if v <= 1 and v > 0 else round(v, 1) 
            
            df["GP"] = get_v("gp").replace(0,1)
            min_raw = get_v("min_sec"); sec_total = get_v("sec_total")
            
            df["MIN_FINAL"] = min_raw
            mask_zero = (df["MIN_FINAL"] <= 0) & (df["GP"] > 0) 
            # Sicherstellen, dass df.loc eine Series von gleicher Länge zurückgibt
            if not df.loc[mask_zero, "GP"].empty:
                df.loc[mask_zero, "MIN_FINAL"] = sec_total[mask_zero] / df.loc[mask_zero, "GP"]
            else: # Fallback, falls keine Spieler die Bedingung erfüllen
                 df["MIN_FINAL"] = df["MIN_FINAL"].replace(0,0) # Keine Änderung

            df["MIN_DISPLAY"] = df["MIN_FINAL"].apply(format_minutes)
            
            df["PPG"] = get_v("ppg"); df["TOT"] = get_v("tot")
            df["2M"] = get_v("2m"); df["2A"] = get_v("2a"); df["2PCT"] = get_v("2pct").apply(pct)
            df["3M"] = get_v("3m"); df["3A"] = get_v("3a"); df["3PCT"] = get_v("3pct").apply(pct)
            df["FTM"] = get_v("ftm"); df["FTA"] = get_v("fta"); df["FTPCT"] = get_v("ftpct").apply(pct)
            
            total_made_fg = df["2M"] + df["3M"]
            total_att_fg = df["2A"] + df["3A"]
            
            # Vermeide Division durch Null für FG%
            df["FG%"] = (total_made_fg / total_att_fg * 100).fillna(0).round(1) if not total_att_fg.empty and (total_att_fg != 0).any() else pd.Series([0.0]*len(df), index=df.index)
            
            df["DR"] = get_v("dr"); df["OR"] = get_v("or"); df["AS"] = get_v("as")
            df["TO"] = get_v("to"); df["ST"] = get_v("st"); df["PF"] = get_v("pf"); df["BS"] = get_v("bs")
            df["select"] = False
            print(f"DEBUG: DataFrame für Spielerstats erfolgreich erstellt. Reihen: {len(df)}")
        else:
            print("DEBUG: Keine Spielerstatistik-Daten gefunden oder Liste leer.")

        return df, ts
    except requests.exceptions.Timeout:
        print(f"DEBUG: API-Anfrage Timeout für Team {team_id}, Saison {season_id}")
        st.error(f"Die Anfrage an die DBBL-API hat einen Timeout verursacht. Bitte versuchen Sie es später erneut.")
        return None, None
    except requests.exceptions.RequestException as e:
        print(f"DEBUG: Netzwerkfehler für Team {team_id}, Saison {season_id}: {e}")
        st.error(f"Ein Netzwerkfehler ist aufgetreten: {e}. Bitte prüfen Sie Ihre Internetverbindung oder versuchen Sie es später erneut.")
        return None, None
    except Exception as e:
        print(f"DEBUG: Unerwarteter Fehler in fetch_team_data für Team {team_id}, Saison {season_id}: {e}")
        import traceback
        traceback.print_exc() 
        st.error(f"Ein unerwarteter Fehler ist aufgetreten: {e}. Bitte kontaktieren Sie den Entwickler.")
        return None, None

@st.cache_data(ttl=300)
def fetch_schedule(team_id, season_id):
    """Lädt die Spiele eines Teams für die Saison."""
    url = f"https://api-s.dbbl.scb.world/games?currentPage=1&seasonTeamId={team_id}&pageSize=1000&gameType=all&seasonId={season_id}"
    print(f"DEBUG: fetch_schedule startet für Team {team_id}, Saison {season_id} von {url}")

    try:
        resp = requests.get(url, headers=API_HEADERS)
        print(f"DEBUG: fetch_schedule API Status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            print(f"DEBUG: {len(items)} Spiele für Team {team_id} gefunden.")
            
            clean_games = []
            for g in items:
                res = g.get("result")
                score_str = "-"
                if res and isinstance(res, dict):
                    score_str = f"{res.get('homeTeamFinalScore', 0)} : {res.get('guestTeamFinalScore', 0)}"
                
                raw_date = g.get("scheduledTime", "")
                date_display = raw_date
                if raw_date:
                    try:
                        dt_utc = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                        berlin = pytz.timezone("Europe/Berlin")
                        dt_berlin = dt_utc.astimezone(berlin)
                        date_display = dt_berlin.strftime("%Y-%m-%d %H:%M")
                    except Exception as date_e:
                        print(f"DEBUG: Fehler beim Datumsformat für Spiel {g.get('id')}: {date_e}")
                        pass # Nutze rohes Datum, wenn Formatierung fehlschlägt

                home_val = g.get("homeTeam")
                guest_val = g.get("guestTeam")
                home_name = home_val.get("name", "Unknown") if isinstance(home_val, dict) else "Unknown"
                guest_name = guest_val.get("name", "Unknown") if isinstance(guest_val, dict) else "Unknown"
                
                stage_val = g.get("stage")
                stage_name = stage_val.get("name", "-") if isinstance(stage_val, dict) else str(stage_val)

                clean_games.append({
                    "id": g.get("id"),
                    "date": date_display,
                    "home": home_name,
                    "guest": guest_name,
                    "score": score_str,
                    "stage": stage_name,
                    "homeTeamId": home_val.get("teamId"), 
                    "guestTeamId": guest_val.get("teamId") 
                })
            return clean_games
    except requests.exceptions.RequestException as e:
        print(f"DEBUG: Netzwerkfehler in fetch_schedule für Team {team_id}: {e}")
        st.error(f"Fehler beim Laden des Spielplans: {e}. Bitte versuchen Sie es später erneut.")
    except Exception as e:
        print(f"DEBUG: Unerwarteter Fehler in fetch_schedule für Team {team_id}: {e}")
        import traceback
        traceback.print_exc()
        st.error(f"Unerwarteter Fehler beim Laden des Spielplans: {e}. Bitte kontaktieren Sie den Entwickler.")
    return []

@st.cache_data(ttl=600)
def fetch_game_boxscore(game_id):
    """Lädt die Statistiken (Boxscore)."""
    url = f"https://api-s.dbbl.scb.world/games/{game_id}/stats"
    print(f"DEBUG: fetch_game_boxscore startet für Game {game_id} von {url}")

    try:
        resp = requests.get(url, headers=API_HEADERS)
        print(f"DEBUG: fetch_game_boxscore API Status: {resp.status_code}")
        if resp.status_code == 200:
            return resp.json()
    except requests.exceptions.RequestException as e:
        print(f"DEBUG: Netzwerkfehler in fetch_game_boxscore für Game {game_id}: {e}")
    except Exception as e:
        print(f"DEBUG: Unerwarteter Fehler in fetch_game_boxscore für Game {game_id}: {e}")
        import traceback
        traceback.print_exc()
    return None

@st.cache_data(ttl=600)
def fetch_game_details(game_id):
    """Lädt die Metadaten (Schiris, Halle, Quarter-Scores)."""
    url = f"https://api-s.dbbl.scb.world/games/{game_id}"
    print(f"DEBUG: fetch_game_details startet für Game {game_id} von {url}")

    try:
        resp = requests.get(url, headers=API_HEADERS)
        print(f"DEBUG: fetch_game_details API Status: {resp.status_code}")
        if resp.status_code == 200:
            return resp.json()
    except requests.exceptions.RequestException as e:
        print(f"DEBUG: Netzwerkfehler in fetch_game_details für Game {game_id}: {e}")
    except Exception as e:
        print(f"DEBUG: Unerwarteter Fehler in fetch_game_details für Game {game_id}: {e}")
        import traceback
        traceback.print_exc()
    return None

@st.cache_data(ttl=3600) 
def fetch_team_info_basic(team_id):
    """
    Lädt grundlegende Teaminformationen inklusive Spielort-Details.
    Versucht zuerst den /teams/{team_id} Endpunkt (api-s), und falls dort keine Venue gefunden wird,
    versucht es einen Spielort von einem der letzten Heimspiele zu extrahieren.
    """
    print(f"DEBUG: fetch_team_info_basic startet für Team {team_id}")

    # 1. Versuch: Spielort direkt vom Team-Endpunkt bekommen
    team_url_direct = f"https://api-s.dbbl.scb.world/teams/{team_id}" 
    
    try:
        resp = requests.get(team_url_direct, headers=API_HEADERS)
        if resp.status_code == 200:
            team_data = resp.json()
            main_venue = None
            
            venues_list = team_data.get("venues")
            if venues_list and isinstance(venues_list, list) and len(venues_list) > 0:
                for venue in venues_list:
                    if venue.get("isMain"):
                        main_venue = venue
                        break
                if not main_venue:
                    main_venue = venues_list[0] 
            
            if main_venue:
                print(f"DEBUG: fetch_team_info_basic - Direkter Treffer für Venue für Team {team_id}")
                return {"id": team_data.get("id"), "venue": main_venue}

    except requests.exceptions.RequestException as e:
        print(f"DEBUG: fetch_team_info_basic - Netzwerkfehler bei direktem Venue-Abruf für Team {team_id}: {e}")
    except Exception as e:
        print(f"DEBUG: fetch_team_info_basic - Parsing-Fehler bei direktem Venue-Abruf für Team {team_id}: {e}")

    print(f"DEBUG: fetch_team_info_basic - Direkter Venue-Abruf fehlgeschlagen oder keine Main Venue gefunden. Versuche Fallback über Spieleplan.")

    # 2. Fallback-Logik: Keine Venue über /teams/{team_id} gefunden,
    # versuchen wir, sie über ein aktuelles Heimspiel zu finden.
    
    all_games = fetch_schedule(team_id, SEASON_ID) 
    
    if all_games:
        home_games = [g for g in all_games if str(g.get("homeTeamId")) == str(team_id)]
        
        home_games_sorted = sorted(home_games, 
                                   key=lambda x: datetime.strptime(x['date'], "%Y-%m-%d %H:%M"), 
                                   reverse=True)
        
        for game in home_games_sorted:
            game_id = game.get("id")
            if game_id:
                print(f"DEBUG: fetch_team_info_basic - Versuche Venue von Spiel {game_id} zu laden (Fallback)")
                game_details = fetch_game_details(game_id)
                if game_details and game_details.get("venue"):
                    print(f"DEBUG: fetch_team_info_basic - Venue von Spiel {game_id} gefunden: {game_details['venue'].get('name')}")
                    return {"id": team_id, "venue": game_details["venue"]}
    
    print(f"DEBUG: fetch_team_info_basic - Nach allen Versuchen keine Venue für Team {team_id} gefunden.")
    return {"id": team_id, "venue": None}
