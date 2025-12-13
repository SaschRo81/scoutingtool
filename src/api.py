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

    try:
        resp_players = requests.get(api_url, headers=API_HEADERS)
        resp_team_stats = requests.get(api_team, headers=API_HEADERS)
        
        if resp_players.status_code != 200:
            print(f"DEBUG: Fehler beim Abrufen der Spielerstatistik. Status: {resp_players.status_code}, Antwort: {resp_players.text[:200]}")
            return None, None
        if resp_team_stats.status_code != 200:
            print(f"DEBUG: Fehler beim Abrufen der Teamstatistik. Status: {resp_team_stats.status_code}, Antwort: {resp_team_stats.text[:200]}")
            return None, None

        raw_player_data = resp_players.json()
        raw_team_stats_list = resp_team_stats.json()

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
        else:
            ts = {} 

        # 2. Player Stats
        df = None
        player_list = raw_player_data if isinstance(raw_player_data, list) else raw_player_data.get("data", [])
        
        if player_list:
            df = pd.json_normalize(player_list)
            df.columns = [str(c).lower() for c in df.columns]
            
            print(f"DEBUG: DataFrame Spalten nach Lowercase: {df.columns.tolist()}") 

            # KORRIGIERT: Erweiterte col_map für robustere Spaltenerkennung mit Prioritäten
            # UND Wiederherstellung der "fuzzy" Suche `p in c`
            col_map = {
                "firstname": ["seasonplayer.person.firstname", "person.firstname", "firstname"], 
                "lastname": ["seasonplayer.person.lastname", "person.lastname", "lastname"],
                "shirtnumber": ["seasonplayer.shirtnumber", "jerseynumber", "shirtnumber", "no", "jersey_number"], 
                "id": ["seasonplayer.personid", "seasonplayer.id", "playerid", "person.id", "id"],
                "gp": ["matches", "gamesplayed", "games"], 
                "ppg": ["pointspergame"], 
                "tot": ["totalreboundspergame"],
                "min_sec": ["secondsplayedpergame", "minutespergame", "avgminutes"], 
                "sec_total": ["secondsplayed"],
                "2m": ["twopointshotsmadepergame"], "2a": ["twopointshotsattemptedpergame"], "2pct": ["twopointshotsuccesspercent"],
                "3m": ["threepointshotsmadepergame"], "3a": ["threepointshotsattemptedpergame"], "3pct": ["threepointshotsuccesspercent"],
                "ftm": ["freethrowsmadepergame"], "fta": ["freethrowsattemptedpergame"], "ftpct": ["freethrowssuccesspercent"],
                "dr": ["defensivereboundspergame"], "or": ["offensivereboundspergame"], "as": ["assistspergame"],
                "to": ["turnoverspergame"], "st": ["stealspergame"], "pf": ["foulscommittedpergame"], "bs": ["blockspergame"]
            }
            
            final_cols = {}
            for target_col, potential_api_names in col_map.items():
                for api_name_part in potential_api_names: # api_name_part kann ein Teil des Spaltennamens sein
                    # Suche nach Spalten, die `api_name_part` enthalten
                    matching_cols = [col for col in df.columns if api_name_part in col]
                    if matching_cols:
                        # Nimm den kürzesten passenden Spaltennamen, um präziser zu sein
                        final_cols[target_col] = sorted(matching_cols, key=len)[0]
                        break 
            
            print(f"DEBUG: Final Column Map: {final_cols}") 

            # Helper to safely get a Series for a column
            # Ensure it always returns a Series of strings, replacing None/NaN with empty strings
            def get_string_series_for_column(col_key, default_value=""):
                col_name = final_cols.get(col_key)
                if col_name and col_name in df.columns:
                    return df[col_name].astype(str).fillna(default_value)
                return pd.Series([default_value] * len(df), index=df.index)
            
            # Robusterer Zugriff auf Spalten für NAME_FULL
            firstname_series = get_string_series_for_column("firstname")
            lastname_series = get_string_series_for_column("lastname")
            
            print(f"DEBUG: Content of 'firstname_series' before concat:\n{firstname_series.to_list()}")
            print(f"DEBUG: Content of 'lastname_series' before concat:\n{lastname_series.to_list()}")

            df["NAME_FULL"] = (firstname_series + " " + lastname_series).str.strip()

            # Robusterer Zugriff auf Spalten für NR und PLAYER_ID
            df["NR"] = get_string_series_for_column("shirtnumber").str.replace(".0", "", regex=False)
            df["PLAYER_ID"] = get_string_series_for_column("id")
            
            print(f"DEBUG: DataFrame nach NAME_FULL, NR, PLAYER_ID Erstellung. Head:\n{df[['NAME_FULL', 'NR', 'PLAYER_ID']].head()}")

            # Helper to safely get numeric series
            def get_numeric_series_for_column(col_key, default_value=0.0):
                col_name = final_cols.get(col_key)
                if col_name and col_name in df.columns:
                    return pd.to_numeric(df[col_name], errors="coerce").fillna(default_value)
                return pd.Series([default_value]*len(df), index=df.index) 
            
            def pct(v): 
                return round(v*100, 1) if v <= 1 and v > 0 else round(v, 1) 
            
            df["GP"] = get_numeric_series_for_column("gp").replace(0,1)
            min_raw = get_numeric_series_for_column("min_sec"); sec_total = get_numeric_series_for_column("sec_total")
            
            df["MIN_FINAL"] = min_raw
            mask_zero = (df["MIN_FINAL"] <= 0) & (df["GP"] > 0) 
            if not df.loc[mask_zero].empty: 
                df.loc[mask_zero, "MIN_FINAL"] = sec_total[mask_zero] / df.loc[mask_zero, "GP"]

            df["MIN_DISPLAY"] = df["MIN_FINAL"].apply(format_minutes)
            
            df["PPG"] = get_numeric_series_for_column("ppg"); 
            df["TOT"] = get_numeric_series_for_column("tot")
            df["2M"] = get_numeric_series_for_column("2m"); df["2A"] = get_numeric_series_for_column("2a"); df["2PCT"] = get_numeric_series_for_column("2pct").apply(pct)
            df["3M"] = get_numeric_series_for_column("3m"); df["3A"] = get_numeric_series_for_column("3a"); df["3PCT"] = get_numeric_series_for_column("3pct").apply(pct)
            df["FTM"] = get_numeric_series_for_column("ftm"); df["FTA"] = get_numeric_series_for_column("fta"); df["FTPCT"] = get_numeric_series_for_column("ftpct").apply(pct)
            
            total_made_fg = df["2M"] + df["3M"]
            total_att_fg = df["2A"] + df["3A"]
            
            if not total_att_fg.empty and (total_att_fg != 0).any():
                df["FG%"] = (total_made_fg / total_att_fg * 100).fillna(0).round(1)
            else:
                df["FG%"] = pd.Series([0.0]*len(df), index=df.index)
            
            df["DR"] = get_numeric_series_for_column("dr"); 
            df["OR"] = get_numeric_series_for_column("or"); 
            df["AS"] = get_numeric_series_for_column("as")
            df["TO"] = get_numeric_series_for_column("to"); 
            df["ST"] = get_numeric_series_for_column("st"); 
            df["PF"] = get_numeric_series_for_column("pf"); 
            df["BS"] = get_numeric_series_for_column("bs")
            df["select"] = False
        else:
            df = pd.DataFrame() 
            
        return df, ts
    except requests.exceptions.Timeout:
        st.error(f"Die Anfrage an die DBBL-API hat einen Timeout verursacht. Bitte versuchen Sie es später erneut.")
        return None, None
    except requests.exceptions.RequestException as e:
        st.error(f"Ein Netzwerkfehler ist aufgetreten: {e}. Bitte prüfen Sie Ihre Internetverbindung oder versuchen Sie es später erneut.")
        return None, None
    except Exception as e:
        import traceback
        traceback.print_exc() 
        st.error(f"Ein unerwarteter Fehler ist aufgetreten: {e}. Bitte kontaktieren Sie den Entwickler.")
        return None, None

@st.cache_data(ttl=300)
def fetch_schedule(team_id, season_id):
    """Lädt die Spiele eines Teams für die Saison."""
    url = f"https://api-s.dbbl.scb.world/games?currentPage=1&seasonTeamId={team_id}&pageSize=1000&gameType=all&seasonId={season_id}"
    
    try:
        resp = requests.get(url, headers=API_HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            
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
                    except Exception:
                        pass 

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
        st.error(f"Fehler beim Laden des Spielplans: {e}. Bitte versuchen Sie es später erneut.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        st.error(f"Unerwarteter Fehler beim Laden des Spielplans: {e}. Bitte kontaktieren Sie den Entwickler.")
    return []

@st.cache_data(ttl=600)
def fetch_game_boxscore(game_id):
    """Lädt die Statistiken (Boxscore)."""
    url = f"https://api-s.dbbl.scb.world/games/{game_id}/stats"
    
    try:
        resp = requests.get(url, headers=API_HEADERS)
        if resp.status_code == 200:
            return resp.json()
    except requests.exceptions.RequestException as e:
        pass
    except Exception as e:
        import traceback
        traceback.print_exc()
    return None

@st.cache_data(ttl=600)
def fetch_game_details(game_id):
    """Lädt die Metadaten (Schiris, Halle, Quarter-Scores)."""
    url = f"https://api-s.dbbl.scb.world/games/{game_id}"
    
    try:
        resp = requests.get(url, headers=API_HEADERS)
        if resp.status_code == 200:
            return resp.json()
    except requests.exceptions.RequestException as e:
        pass
    except Exception as e:
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
                return {"id": team_data.get("id"), "venue": main_venue}

    except requests.exceptions.RequestException:
        pass 
    except Exception:
        pass 

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
                game_details = fetch_game_details(game_id)
                if game_details and game_details.get("venue"):
                    return {"id": team_id, "venue": game_details["venue"]}
    
    return {"id": team_id, "venue": None}
