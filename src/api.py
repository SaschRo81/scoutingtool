# --- START OF FILE src/api.py ---

import streamlit as st
import requests
import pandas as pd
from datetime import datetime, date
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

def calculate_age(birthdate_str):
    """Berechnet das Alter aus einem ISO-Datum (YYYY-MM-DD...)."""
    if not birthdate_str or str(birthdate_str).lower() == "nan": return "-"
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
    Lädt Stammdaten (Alter, Nat, Height) vom detaillierten Team-Endpunkt.
    Wir brauchen das für die Spielerdetails.
    """
    url = f"https://api-1.dbbl.scb.world/teams/{team_id}/{season_id}" # Korrekter Endpunkt
    try:
        resp = requests.get(url, headers=API_HEADERS)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"DEBUG: Fehler beim Abrufen von Teamdetails {team_id} (Status {resp.status_code}): {resp.text[:200]}")
    except requests.exceptions.RequestException as e:
        print(f"DEBUG: Netzwerkfehler beim Abrufen von Teamdetails {team_id}: {e}")
    except Exception as e:
        print(f"DEBUG: Unerwarteter Fehler beim Abrufen von Teamdetails {team_id}: {e}")
        import traceback
        traceback.print_exc()
    return None

@st.cache_data(ttl=600)
def fetch_team_data(team_id, season_id):
    """Lädt Kader (Stats + Stammdaten) für die Saison."""
    api_stats_url = f"https://api-s.dbbl.scb.world/teams/{team_id}/{season_id}/player-stats"
    api_team_stats_url = f"https://api-s.dbbl.scb.world/seasons/{season_id}/team-statistics?displayType=MAIN_ROUND&teamId={team_id}"
    
    print(f"DEBUG: fetch_team_data startet für Team {team_id}, Saison {season_id}")

    # 1. Stammdaten laden (Alter, Nationalität, etc.)
    roster_details_raw = fetch_team_details_raw(team_id, season_id)
    roster_lookup = {}
    if roster_details_raw:
        # Die Struktur kann sein: { "squad": [...] } oder direkt eine Liste
        squad_list = roster_details_raw.get("squad", []) if isinstance(roster_details_raw, dict) else []
        for entry in squad_list:
            person = entry.get("person", {})
            pid = str(person.get("id", ""))
            if pid:
                birthdate = person.get("birthdate", "")
                nat = person.get("nationality", {}).get("name") or entry.get("nationality", {}).get("name", "-") # Try nested path first
                height = person.get("height", "-")
                roster_lookup[pid] = {
                    "birthdate": birthdate,
                    "nationality": nat,
                    "height": height
                }

    try:
        resp_players = requests.get(api_stats_url, headers=API_HEADERS)
        resp_team_stats = requests.get(api_team_url, headers=API_HEADERS)
        
        if resp_players.status_code != 200:
            print(f"DEBUG: Fehler beim Abrufen der Spielerstatistik. Status: {resp_players.status_code}")
            return None, None
        if resp_team_stats.status_code != 200:
            print(f"DEBUG: Fehler beim Abrufen der Teamstatistik. Status: {resp_team_stats.status_code}")
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
            
            col_map = {
                "firstname": ["seasonplayer.person.firstname", "person.firstname", "firstname"], 
                "lastname": ["seasonplayer.person.lastname", "person.lastname", "lastname"],
                "shirtnumber": ["seasonplayer.shirtnumber", "jerseynumber", "shirtnumber", "no"], 
                "id": ["seasonplayer.personid", "seasonplayer.id", "playerid", "person.id", "id"],
                "birthdate": ["seasonplayer.person.birthdate", "person.birthdate", "birthdate"],
                "nationality": ["seasonplayer.person.nationality.name", "person.nationality.name", "nationality", "nationality.name"]
            }
            
            final_cols = {}
            for target_col, potential_api_names in col_map.items():
                for api_name_part in potential_api_names:
                    matches = [c for c in df.columns if api_name_part in c] # Fuzzy matching wieder aktivieren
                    if matches:
                        final_cols[target_col] = sorted(matches, key=len)[0]
                        break 
            
            # Safe Accessors für Spalten
            def get_string_series_for_column(col_key, default_value=""):
                col_name = final_cols.get(col_key)
                if col_name and col_name in df.columns:
                    return df[col_name].astype(str).fillna(default_value)
                return pd.Series([default_value] * len(df), index=df.index)
            
            firstname_series = get_string_series_for_column("firstname")
            lastname_series = get_string_series_for_column("lastname")
            df["NAME_FULL"] = (firstname_series + " " + lastname_series).str.strip()

            df["NR"] = get_string_series_for_column("shirtnumber").str.replace(".0", "", regex=False)
            df["PLAYER_ID"] = get_string_series_for_column("id").str.replace(".0", "", regex=False) # Sicherstellen, dass ID auch sauber ist
            
            # Neue Spalten für Vorbericht
            df["BIRTHDATE"] = df["PLAYER_ID"].apply(lambda x: roster_lookup.get(x, {}).get("birthdate", ""))
            df["NATIONALITY"] = df["PLAYER_ID"].apply(lambda x: roster_lookup.get(x, {}).get("nationality", "-"))
            df["HEIGHT_ROSTER"] = df["PLAYER_ID"].apply(lambda x: roster_lookup.get(x, {}).get("height", "-"))
            df["AGE"] = df["BIRTHDATE"].apply(calculate_age)
            
            # Numeric Stats
            def get_numeric_series_for_column(col_key, default_value=0.0):
                col_name = final_cols.get(col_key)
                if col_name and col_name in df.columns:
                    return pd.to_numeric(df[col_name], errors="coerce").fillna(default_value)
                return pd.Series([default_value]*len(df), index=df.index) 
            
            def pct(v): 
                return round(v*100, 1) if v <= 1 and v > 0 else round(v, 1) 
            
            df["GP"] = get_numeric_series_for_column("gamesplayed").replace(0,1)
            min_raw = get_numeric_series_for_column("minutespergame"); sec_total = get_numeric_series_for_column("secondsplayed")
            df["MIN_FINAL"] = min_raw
            mask_zero = (df["MIN_FINAL"] <= 0) & (df["GP"] > 0) 
            if not df.loc[mask_zero].empty:
                if "secondsplayed" in [c for c in df.columns if "secondsplayed" in c]:
                    sec_col = [c for c in df.columns if "secondsplayed" in c][0]
                    sec_series = pd.to_numeric(df[sec_col], errors="coerce").fillna(0)
                    df.loc[mask_zero, "MIN_FINAL"] = sec_series[mask_zero] / df.loc[mask_zero, "GP"]
            df["MIN_DISPLAY"] = df["MIN_FINAL"].apply(format_minutes)
            df["PPG"] = get_numeric_series_for_column("pointspergame")
            df["TOT"] = get_numeric_series_for_column("totalreboundspergame")
            df["AS"] = get_numeric_series_for_column("assistspergame")
            df["TO"] = get_numeric_series_for_column("turnoverspergame")
            df["ST"] = get_numeric_series_for_column("stealspergame")
            df["PF"] = get_numeric_series_for_column("foulscommittedpergame")
            df["BS"] = get_numeric_series_for_column("blockspergame")
            df["2M"] = get_numeric_series_for_column("twopointshotsmadepergame"); df["2A"] = get_numeric_series_for_column("twopointshotsattemptedpergame"); df["2PCT"] = get_numeric_series_for_column("twopointshotsuccesspercent").apply(pct)
            df["3M"] = get_numeric_series_for_column("threepointshotsmadepergame"); df["3A"] = get_numeric_series_for_column("threepointshotsattemptedpergame"); df["3PCT"] = get_numeric_series_for_column("threepointshotsuccesspercent").apply(pct)
            df["FTM"] = get_numeric_series_for_column("freethrowsmadepergame"); df["FTA"] = get_numeric_series_for_column("freethrowsattemptedpergame"); df["FTPCT"] = get_numeric_series_for_column("freethrowssuccesspercent").apply(pct)
            
            total_made_fg = df["2M"] + df["3M"]; total_att_fg = df["2A"] + df["3A"]
            if not total_att_fg.empty and (total_att_fg != 0).any(): df["FG%"] = (total_made_fg / total_att_fg * 100).fillna(0).round(1)
            else: df["FG%"] = pd.Series([0.0]*len(df), index=df.index)
            
            df["select"] = False
        return df, ts
    except Exception as e:
        print(f"Error fetch_team_data: {e}")
        return None, None

@st.cache_data(ttl=300)
def fetch_schedule(team_id, season_id):
    """Lädt Spiele."""
    url = f"https://api-s.dbbl.scb.world/games?currentPage=1&seasonTeamId={team_id}&pageSize=1000&gameType=all&seasonId={season_id}"
    try:
        resp = requests.get(url, headers=API_HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            clean_games = []
            for g in items:
                res = g.get("result")
                score = "-"
                has_result = False
                if res and isinstance(res, dict):
                    h = res.get('homeTeamFinalScore'); v = res.get('guestTeamFinalScore')
                    if h is not None and v is not None: score = f"{h} : {v}"; has_result = True
                raw_date = g.get("scheduledTime", "")
                date_display = raw_date
                if raw_date:
                    try: dt_utc = datetime.fromisoformat(raw_date.replace("Z", "+00:00")); berlin = pytz.timezone("Europe/Berlin"); date_display = dt_utc.astimezone(berlin).strftime("%Y-%m-%d %H:%M")
                    except: pass
                clean_games.append({"id": g.get("id"), "date": date_display, "score": score, "has_result": has_result, "home": g.get("homeTeam", {}).get("name", "?"), "guest": g.get("guestTeam", {}).get("name", "?"), "homeTeamId": str(g.get("homeTeam", {}).get("teamId")), "guestTeamId": str(g.get("guestTeam", {}).get("teamId")) })
            return clean_games
    except Exception as e:
        st.error(f"Fehler beim Laden des Spielplans: {e}")
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
    try:
        resp = requests.get(f"https://api-s.dbbl.scb.world/teams/{team_id}", headers=API_HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            venues = data.get("venues", [])
            main = next((v for v in venues if v.get("isMain")), venues[0] if venues else None)
            if main: return {"id": team_id, "venue": main}
    except: pass
    sched = fetch_schedule(team_id, SEASON_ID)
    if sched:
        homes = [g for g in sched if str(g.get("homeTeamId")) == str(team_id)]
        homes.sort(key=lambda x: datetime.strptime(x['date'], "%Y-%m-%d %H:%M"), reverse=True)
        for g in homes:
            det = fetch_game_details(g['id'])
            if det and det.get("venue"): return {"id": team_id, "venue": det["venue"]}
    return {"id": team_id, "venue": None}
