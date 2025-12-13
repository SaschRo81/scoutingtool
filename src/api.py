# --- START OF FILE api.py ---

import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import pytz
from src.config import API_HEADERS
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
    except Exception:
        pass
    return {"img": "", "height": 0, "pos": "-"}

@st.cache_data(ttl=600)
def fetch_team_data(team_id, season_id):
    """Lädt Kader und Team-Statistiken für die Saison."""
    api_url = f"https://api-s.dbbl.scb.world/teams/{team_id}/{season_id}/player-stats"
    api_team = f"https://api-s.dbbl.scb.world/seasons/{season_id}/team-statistics?displayType=MAIN_ROUND&teamId={team_id}"
    
    try:
        resp = requests.get(api_url, headers=API_HEADERS)
        resp_t = requests.get(api_team, headers=API_HEADERS)
        
        if resp.status_code != 200: return None, None
        if resp_t.status_code != 200: return None, None

        raw_data = resp.json()
        team_data_list = resp_t.json()

        # 1. Team Stats
        ts = {}
        if team_data_list and isinstance(team_data_list, list):
            td = team_data_list[0]
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

        # 2. Player Stats
        df = None
        raw = raw_data if isinstance(raw_data, list) else raw_data.get("data", [])
        if raw:
            df = pd.json_normalize(raw)
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
                    m = [c for c in df.columns if p in c]
                    if m: final_cols[t] = sorted(m, key=len)[0]; break
            
            fn = df[final_cols["firstname"]].fillna("") if "firstname" in final_cols else ""
            ln = df[final_cols["lastname"]].fillna("") if "lastname" in final_cols else ""
            df["NAME_FULL"] = (fn + " " + ln).str.strip()
            df["NR"] = df[final_cols["shirtnumber"]].fillna("-").astype(str).str.replace(".0", "", regex=False) if "shirtnumber" in final_cols else "-"
            df["PLAYER_ID"] = df[final_cols["id"]].astype(str) if "id" in final_cols else ""
            
            def get_v(k): return pd.to_numeric(df[final_cols[k]], errors="coerce").fillna(0) if k in final_cols else pd.Series([0.0]*len(df))
            def pct(v): return round(v*100, 1) if v<=1 else round(v,1)
            
            df["GP"] = get_v("gp").replace(0,1)
            min_raw = get_v("min_sec"); sec_total = get_v("sec_total")
            df["MIN_FINAL"] = min_raw
            mask_zero = df["MIN_FINAL"] <= 0
            df.loc[mask_zero, "MIN_FINAL"] = sec_total[mask_zero] / df.loc[mask_zero, "GP"]
            df["MIN_DISPLAY"] = df["MIN_FINAL"].apply(format_minutes)
            df["PPG"] = get_v("ppg"); df["TOT"] = get_v("tot")
            df["2M"] = get_v("2m"); df["2A"] = get_v("2a"); df["2PCT"] = get_v("2pct").apply(pct)
            df["3M"] = get_v("3m"); df["3A"] = get_v("3a"); df["3PCT"] = get_v("3pct").apply(pct)
            df["FTM"] = get_v("ftm"); df["FTA"] = get_v("fta"); df["FTPCT"] = get_v("ftpct").apply(pct)
            total_made = df["2M"] + df["3M"]; total_att = df["2A"] + df["3A"]
            df["FG%"] = (total_made / total_att * 100).fillna(0).round(1)
            df["DR"] = get_v("dr"); df["OR"] = get_v("or"); df["AS"] = get_v("as")
            df["TO"] = get_v("to"); df["ST"] = get_v("st"); df["PF"] = get_v("pf"); df["BS"] = get_v("bs")
            df["select"] = False
        return df, ts
    except Exception as e:
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
                
                # DATUM FIXEN
                raw_date = g.get("scheduledTime", "")
                date_display = raw_date
                if raw_date:
                    try:
                        dt_utc = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                        berlin = pytz.timezone("Europe/Berlin")
                        dt_berlin = dt_utc.astimezone(berlin)
                        date_display = dt_berlin.strftime("%Y-%m-%d %H:%M")
                    except:
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
                    "stage": stage_name
                })
            return clean_games
    except Exception as e:
        st.error(f"Fehler beim Laden des Spielplans: {e}")
    return []

@st.cache_data(ttl=600)
def fetch_game_boxscore(game_id):
    """Lädt die Statistiken (Boxscore)."""
    url = f"https://api-s.dbbl.scb.world/games/{game_id}/stats"
    try:
        resp = requests.get(url, headers=API_HEADERS)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None

@st.cache_data(ttl=600)
def fetch_game_details(game_id):
    """Lädt die Metadaten (Schiris, Halle, Quarter-Scores)."""
    url = f"https://api-s.dbbl.scb.world/games/{game_id}"
    try:
        resp = requests.get(url, headers=API_HEADERS)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None

@st.cache_data(ttl=3600) # Cache für eine Stunde
def fetch_team_info_basic(team_id):
    """
    Lädt grundlegende Teaminformationen inklusive Spielort-Details.
    Verwendet api-s.dbbl.scb.world/teams/{team_id} und extrahiert die Hauptspielstätte.
    """
    url = f"https://api-s.dbbl.scb.world/teams/{team_id}" 
    st.info(f"DEBUG: Versuche Spielort-Daten für Team-ID {team_id} von {url} zu laden...") # Debugging
    
    try:
        resp = requests.get(url, headers=API_HEADERS)
        
        if resp.status_code == 200:
            team_data = resp.json()
            st.info(f"DEBUG: API-Antwort (Status 200) für Team-ID {team_id}. Hat 'venues' Daten: {'venues' in team_data and len(team_data.get('venues', [])) > 0}") # Debugging
            
            main_venue = None
            
            # Überprüfe, ob der 'venues'-Schlüssel existiert und eine Liste ist
            if "venues" in team_data and isinstance(team_data["venues"], list) and len(team_data["venues"]) > 0:
                for venue in team_data["venues"]:
                    if venue.get("isMain"):
                        main_venue = venue
                        break
                # Wenn keine Hauptspielstätte gefunden, nimm die erste (falls vorhanden)
                if not main_venue:
                    main_venue = team_data["venues"][0]
            
            if main_venue:
                st.info(f"DEBUG: Hauptspielstätte gefunden: {main_venue.get('name', 'k.A.')}") # Debugging
                return {"id": team_data.get("id"), "venue": main_venue}
            else:
                st.warning(f"DEBUG: Keine Hauptspielstätte oder andere Spielstätten in der API-Antwort für Team-ID {team_id} gefunden.") # Debugging
                return {"id": team_data.get("id"), "venue": None} # Team-ID zurückgeben, aber keine Venue
        else:
            st.warning(f"DEBUG: Fehler beim Laden der Basis-Teaminformationen für Team-ID {team_id}. HTTP Status: {resp.status_code}. Antwort: {resp.text[:200]}") # Debugging
            return None
    except requests.exceptions.RequestException as req_e:
        st.error(f"DEBUG: Netzwerkfehler beim Laden der Team-Info für {team_id}: {req_e}") # Debugging
    except Exception as e:
        st.error(f"DEBUG: Unerwarteter Fehler beim Parsen der Team-Info für {team_id}: {e}") # Debugging
    return None```
