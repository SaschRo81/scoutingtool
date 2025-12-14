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
    except Exception:
        pass
    return {"img": "", "height": 0, "pos": "-"}

def calculate_age(birthdate_str):
    """Berechnet das Alter aus einem ISO-Datum (YYYY-MM-DD...)."""
    if not birthdate_str or str(birthdate_str) == "nan": return "-"
    try:
        # Formate können variieren: "2000-01-01T00:00:00Z" oder "2000-01-01"
        clean_date = str(birthdate_str).split("T")[0]
        bd = datetime.strptime(clean_date, "%Y-%m-%d")
        today = datetime.now()
        return today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
    except:
        return "-"

@st.cache_data(ttl=600)
def fetch_team_details_raw(team_id, season_id):
    """
    Lädt die detaillierte Kaderliste (Stammdaten) vom neuen Endpunkt.
    """
    url = f"https://api-1.dbbl.scb.world/teams/{team_id}/{season_id}"
    try:
        resp = requests.get(url, headers=API_HEADERS)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"DEBUG: Fehler fetch_team_details_raw: {e}")
    return None

@st.cache_data(ttl=600)
def fetch_team_data(team_id, season_id):
    """Lädt Kader (Stats + Stammdaten) für die Saison."""
    
    # 1. Stats laden (wie bisher)
    api_stats_url = f"https://api-s.dbbl.scb.world/teams/{team_id}/{season_id}/player-stats"
    api_team_url = f"https://api-s.dbbl.scb.world/seasons/{season_id}/team-statistics?displayType=MAIN_ROUND&teamId={team_id}"
    
    # 2. Stammdaten laden (NEU)
    roster_data_raw = fetch_team_details_raw(team_id, season_id)
    
    # Lookup-Table für Stammdaten bauen (PlayerID -> {Age, Nat, Height})
    roster_lookup = {}
    if roster_data_raw:
        # Die Struktur ist oft: { "squad": [ ... ] } oder direkt eine Liste
        squad_list = roster_data_raw.get("squad", []) if isinstance(roster_data_raw, dict) else []
        
        for entry in squad_list:
            # Person ID finden
            person = entry.get("person", {})
            pid = str(person.get("id", ""))
            if not pid: continue
            
            # Daten extrahieren
            birthdate = person.get("birthdate", "")
            nat = person.get("nationality", {}).get("name", "-") # oft verschachtelt
            if not nat and "nationality" in entry: # Manchmal direkt im entry
                 nat = entry.get("nationality", {}).get("name", "-")
            
            height = person.get("height", "-")
            
            roster_lookup[pid] = {
                "birthdate": birthdate,
                "nationality": nat,
                "height": height
            }

    try:
        resp_players = requests.get(api_stats_url, headers=API_HEADERS)
        resp_team_stats = requests.get(api_team_url, headers=API_HEADERS)
        
        if resp_players.status_code != 200: return None, None
        
        raw_player_data = resp_players.json()
        # Team Stats
        ts = {}
        if resp_team_stats.status_code == 200:
            raw_ts = resp_team_stats.json()
            if raw_ts and isinstance(raw_ts, list):
                td = raw_ts[0]
                ts = {
                    "ppg": td.get("pointsPerGame", 0), 
                    "2m": td.get("twoPointShotsMadePerGame", 0), "2a": td.get("twoPointShotsAttemptedPerGame", 0), "2pct": td.get("twoPointShotsSuccessPercent", 0),
                    "3m": td.get("threePointShotsMadePerGame", 0), "3a": td.get("threePointShotsAttemptedPerGame", 0), "3pct": td.get("threePointShotsSuccessPercent", 0),
                    "ftm": td.get("freeThrowsMadePerGame", 0), "fta": td.get("freeThrowsAttemptedPerGame", 0), "ftpct": td.get("freeThrowsSuccessPercent", 0),
                    "dr": td.get("defensiveReboundsPerGame", 0), "or": td.get("offensiveReboundsPerGame", 0), "tot": td.get("totalReboundsPerGame", 0),
                    "as": td.get("assistsPerGame", 0), "to": td.get("turnoversPerGame", 0), "st": td.get("stealsPerGame", 0),
                    "bs": td.get("blocksPerGame", 0), "pf": td.get("foulsCommittedPerGame", 0)
                }

        # Player DataFrame bauen
        df = None
        player_list = raw_player_data if isinstance(raw_player_data, list) else raw_player_data.get("data", [])
        
        if player_list:
            df = pd.json_normalize(player_list)
            df.columns = [str(c).lower() for c in df.columns]
            
            # Mapping Stats
            col_map = {
                "firstname": ["seasonplayer.person.firstname", "person.firstname", "firstname"], 
                "lastname": ["seasonplayer.person.lastname", "person.lastname", "lastname"],
                "shirtnumber": ["seasonplayer.shirtnumber", "jerseynumber", "shirtnumber", "no"], 
                "id": ["seasonplayer.personid", "seasonplayer.id", "playerid", "person.id", "id"]
            }
            
            final_cols = {}
            for target_col, potential_api_names in col_map.items():
                for api_name_part in potential_api_names:
                    matching_cols = [col for col in df.columns if api_name_part in col]
                    if matching_cols:
                        final_cols[target_col] = sorted(matching_cols, key=len)[0]
                        break 
            
            # Strings
            def get_s(k): 
                c = final_cols.get(k)
                return df[c].astype(str).fillna("") if c and c in df.columns else pd.Series([""]*len(df), index=df.index)

            df["NAME_FULL"] = (get_s("firstname") + " " + get_s("lastname")).str.strip()
            df["NR"] = get_s("shirtnumber").str.replace(".0", "", regex=False)
            df["PLAYER_ID"] = get_s("id").str.replace(".0", "", regex=False) # ID sauber machen

            # --- MERGE MIT STAMMDATEN (Alter, Nat) ---
            # Wir wenden die Lookup-Tabelle auf die PLAYER_ID Spalte an
            df["BIRTHDATE"] = df["PLAYER_ID"].apply(lambda x: roster_lookup.get(x, {}).get("birthdate", ""))
            df["NATIONALITY"] = df["PLAYER_ID"].apply(lambda x: roster_lookup.get(x, {}).get("nationality", "-"))
            df["HEIGHT_ROSTER"] = df["PLAYER_ID"].apply(lambda x: roster_lookup.get(x, {}).get("height", "-"))
            
            df["AGE"] = df["BIRTHDATE"].apply(calculate_age)
            
            # Numeric Stats
            def get_n(key, default=0.0):
                matches = [c for c in df.columns if key in c]
                if matches:
                    col = sorted(matches, key=len)[0]
                    return pd.to_numeric(df[col], errors="coerce").fillna(default)
                return pd.Series([default]*len(df), index=df.index)
            
            def pct(v): return round(v*100, 1)

            df["GP"] = get_n("gamesplayed").replace(0,1)
            min_raw = get_n("minutespergame"); sec_total = get_n("secondsplayed")
            df["MIN_FINAL"] = min_raw
            mask_zero = (df["MIN_FINAL"] <= 0) & (df["GP"] > 0)
            if not df.loc[mask_zero].empty:
                df.loc[mask_zero, "MIN_FINAL"] = sec_total[mask_zero] / df.loc[mask_zero, "GP"]
            df["MIN_DISPLAY"] = df["MIN_FINAL"].apply(format_minutes)
            
            df["PPG"] = get_n("pointspergame")
            df["TOT"] = get_n("totalreboundspergame")
            df["AS"] = get_n("assistspergame")
            
            # Shooting
            df["FG%"] = ( (get_n("twopointshotsmadepergame") + get_n("threepointshotsmadepergame")) / 
                          (get_n("twopointshotsattemptedpergame") + get_n("threepointshotsattemptedpergame")) * 100 ).fillna(0).round(1)
            
            df["3PCT"] = get_n("threepointshotsuccesspercent").apply(pct)
            
            df["select"] = False
        else:
            df = pd.DataFrame()
            
        return df, ts

    except Exception as e:
        print(f"Error fetch_team_data: {e}")
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
                has_result = False
                
                if res and isinstance(res, dict):
                    h = res.get('homeTeamFinalScore')
                    v = res.get('guestTeamFinalScore')
                    if h is not None and v is not None:
                        score_str = f"{h} : {v}"
                        has_result = True
                
                raw_date = g.get("scheduledTime", "")
                date_display = raw_date
                if raw_date:
                    try:
                        dt_utc = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                        berlin = pytz.timezone("Europe/Berlin")
                        date_display = dt_utc.astimezone(berlin).strftime("%Y-%m-%d %H:%M")
                    except: pass

                clean_games.append({
                    "id": g.get("id"),
                    "date": date_display,
                    "home": g.get("homeTeam", {}).get("name", "?"),
                    "guest": g.get("guestTeam", {}).get("name", "?"),
                    "score": score_str,
                    "has_result": has_result, # Wichtig für Filterung
                    "homeTeamId": str(g.get("homeTeam", {}).get("teamId")), 
                    "guestTeamId": str(g.get("guestTeam", {}).get("teamId")) 
                })
            return clean_games
    except Exception:
        pass
    return []

@st.cache_data(ttl=600)
def fetch_game_boxscore(game_id):
    url = f"https://api-s.dbbl.scb.world/games/{game_id}/stats"
    try:
        resp = requests.get(url, headers=API_HEADERS)
        if resp.status_code == 200: return resp.json()
    except: pass
    return None

@st.cache_data(ttl=600)
def fetch_game_details(game_id):
    url = f"https://api-s.dbbl.scb.world/games/{game_id}"
    try:
        resp = requests.get(url, headers=API_HEADERS)
        if resp.status_code == 200: return resp.json()
    except: pass
    return None

@st.cache_data(ttl=3600) 
def fetch_team_info_basic(team_id):
    # 1. Versuch Direkt
    try:
        resp = requests.get(f"https://api-s.dbbl.scb.world/teams/{team_id}", headers=API_HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            venues = data.get("venues", [])
            main = next((v for v in venues if v.get("isMain")), venues[0] if venues else None)
            if main: return {"id": team_id, "venue": main}
    except: pass

    # 2. Fallback über Schedule
    sched = fetch_schedule(team_id, SEASON_ID)
    if sched:
        # Nur Heimspiele
        homes = [g for g in sched if str(g.get("homeTeamId")) == str(team_id)]
        homes.sort(key=lambda x: x['date'], reverse=True)
        for g in homes:
            det = fetch_game_details(g['id'])
            if det and det.get("venue"): return {"id": team_id, "venue": det["venue"]}
            
    return {"id": team_id, "venue": None}
