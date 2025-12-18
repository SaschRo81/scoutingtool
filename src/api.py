# --- START OF FILE src/api.py ---
import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import pytz
from src.config import API_HEADERS, TEAMS_DB

# --- KONSTANTEN ---
BASE_URL_1 = "https://api-1.dbbl.scb.world"
BASE_URL_2 = "https://api-2.dbbl.scb.world"

# --- HILFSFUNKTIONEN ---

def get_base_url(team_id=None):
    """Ermittelt die wahrscheinlichste API-URL anhand der Team-ID."""
    if team_id:
        try:
            tid = int(team_id)
            # Wenn Team in der 2. Liga DB ist -> api-2
            if tid in TEAMS_DB:
                return BASE_URL_2
        except: pass
    # Fallback: Wir wissen es nicht, müssen eh beide probieren.
    return BASE_URL_1

def format_minutes(seconds):
    if seconds is None: return "00:00"
    try: sec = int(seconds); m = sec // 60; s = sec % 60; return f"{m:02d}:{s:02d}"
    except: return "00:00"

def calculate_age(birthdate_str):
    if not birthdate_str or str(birthdate_str).lower() in ["nan", "none", "", "-", "null"]: return "-"
    try:
        clean_date = str(birthdate_str).split("T")[0]
        bd = datetime.strptime(clean_date, "%Y-%m-%d")
        today = datetime.now()
        age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
        return str(age)
    except: return "-"

def extract_nationality(data_obj):
    if not data_obj: return "-"
    if "nationalities" in data_obj and isinstance(data_obj["nationalities"], list) and data_obj["nationalities"]:
        first = data_obj["nationalities"][0]
        if isinstance(first, str): return "/".join(data_obj["nationalities"])
        elif isinstance(first, dict): return "/".join([n.get("name", "") for n in data_obj["nationalities"]])
    if "nationality" in data_obj and isinstance(data_obj["nationality"], dict):
        return data_obj["nationality"].get("name", "-")
    return "-"

# --- API FUNKTIONEN ---

@st.cache_data(ttl=3600)
def fetch_1dbbl_teams(season_id):
    """Holt die Teams der 1. DBBL von api-1."""
    url = f"{BASE_URL_1}/teams?seasonId={season_id}"
    teams_map = {}
    try:
        r = requests.get(url, headers=API_HEADERS, timeout=4)
        if r.status_code == 200:
            data = r.json()
            # Robuste Datenextraktion: items, data oder Liste direkt
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get("items") or data.get("data") or []
            
            for item in items:
                # Manchmal ist das Team-Objekt direkt das Item, manchmal nested in 'seasonTeam'
                team_obj = item.get('seasonTeam') or item 
                
                tid = team_obj.get('teamId') or team_obj.get('id')
                # ID fixen (manchmal seasonTeamId vs teamId)
                if not tid and 'team' in item:
                     tid = item['team'].get('id')

                if tid:
                    try: tid = int(tid)
                    except: continue
                    
                    teams_map[tid] = {
                        "name": team_obj.get('name', 'Unknown Team'),
                        "staffel": "1. DBBL",
                        "logo_url": f"{BASE_URL_1}/images/teams/logo/{season_id}/{tid}"
                    }
    except Exception as e:
        print(f"Error fetching 1. DBBL: {e}")
    return teams_map

@st.cache_data(ttl=3600, show_spinner=False)
def get_player_metadata_cached(player_id):
    clean_id = str(player_id).replace(".0", "")
    # Prüfe beide APIs
    for base_url in [BASE_URL_1, BASE_URL_2]:
        url = f"{base_url}/season-players/{clean_id}"
        try:
            resp = requests.get(url, headers=API_HEADERS, timeout=1.0)
            if resp.status_code == 200:
                data = resp.json()
                person = data.get("person", {})
                img = data.get("imageUrl", "")
                bdate = data.get("birthDate") or person.get("birthDate") or person.get("birthdate")
                age = calculate_age(bdate)
                nat = extract_nationality(data)
                if nat == "-": nat = extract_nationality(person)
                height = data.get("height") or person.get("height", "-")
                return {"img": img, "height": height, "pos": data.get("position", "-"), "age": age, "nationality": nat}
        except: pass
    return {"img": "", "height": "-", "pos": "-", "age": "-", "nationality": "-"}

@st.cache_data(ttl=600)
def fetch_standings_complete(season_id, group_name):
    # Auswahl der URL basierend auf Liga
    if group_name == "1. DBBL":
        url = f"{BASE_URL_1}/standings?seasonId={season_id}"
    else:
        # Für 2. Liga (Nord/Süd) nutzen wir api-2 mit Group-Filter
        url = f"{BASE_URL_2}/standings?seasonId={season_id}&group={group_name}"
    
    try:
        r = requests.get(url, headers=API_HEADERS, timeout=4)
        if r.status_code == 200:
            data = r.json()
            items = []
            if isinstance(data, list): items = data
            elif isinstance(data, dict): items = data.get("items") or data.get("data") or []
            
            standings = []
            for entry in items:
                st_obj = entry.get("seasonTeam", {})
                standings.append({
                    "rank": entry.get("rank"),
                    "team": st_obj.get("name"),
                    "teamId": st_obj.get("teamId"),
                    "games": entry.get("totalGames"),
                    "wins": entry.get("totalVictories"),
                    "losses": entry.get("totalLosses"),
                    "points": entry.get("points"),
                    # Kompatibilität für Legacy Rank Fetcher
                    "totalVictories": entry.get("totalVictories"),
                    "totalLosses": entry.get("totalLosses"),
                    "totalGames": entry.get("totalGames"),
                    "last10Victories": entry.get("last10Victories", 0),
                    "last10Losses": entry.get("last10Losses", 0)
                })
            return sorted(standings, key=lambda x: x['rank'])
    except Exception as e:
        print(f"Standings Error: {e}")
    return []

# --- KOMPATIBILITÄTS-FUNKTION ---
@st.cache_data(ttl=1800)
def fetch_team_rank(team_id, season_id):
    try:
        tid = int(team_id)
        group = None
        # Check 2. Liga config
        if tid in TEAMS_DB:
            staffel = TEAMS_DB[tid]["staffel"]
            if staffel == "Nord": group = "NORTH"
            elif staffel == "Süd": group = "SOUTH"
        
        # Check 1. Liga via Fetch
        if not group:
            dbbl1 = fetch_1dbbl_teams(season_id)
            if tid in dbbl1: group = "1. DBBL"
        
        # Suche überall, wenn unbekannt
        groups_to_check = [group] if group else ["NORTH", "SOUTH", "1. DBBL"]
        
        for g in groups_to_check:
            standings = fetch_standings_complete(season_id, g)
            for entry in standings:
                if str(entry.get("teamId")) == str(tid):
                    return {
                        "rank": entry.get("rank", 0),
                        "totalGames": entry.get("totalGames", 0),
                        "totalVictories": entry.get("totalVictories", 0),
                        "totalLosses": entry.get("totalLosses", 0),
                        "last10Victories": entry.get("last10Victories", 0),
                        "last10Losses": entry.get("last10Losses", 0),
                        "points": entry.get("points", 0)
                    }
    except: pass
    return None

def fetch_team_data(team_id, season_id):
    # Wir durchsuchen explizit api-1 UND api-2, da wir die ID evtl. nicht zuordnen können
    base_urls = [BASE_URL_1, BASE_URL_2]
    
    # Optimierung: Wenn wir wissen, wo das Team hingehört, priorisieren wir
    if int(team_id) in TEAMS_DB:
        base_urls = [BASE_URL_2, BASE_URL_1] # Priorität 2. Liga

    ts = {}
    df = pd.DataFrame()
    found_url = None

    # 1. Team Stats
    for base_url in base_urls:
        try:
            r = requests.get(f"{base_url}/teams/{team_id}/{season_id}/statistics/season", headers=API_HEADERS, timeout=2)
            if r.status_code == 200:
                data = r.json()
                # API gibt manchmal Liste, manchmal Dict
                td = None
                if isinstance(data, list) and len(data) > 0: td = data[0]
                elif isinstance(data, dict): td = data
                
                if td:
                    found_url = base_url
                    gp = td.get("gamesPlayed") or 1
                    fgm = td.get("fieldGoalsMade") or 0; fga = td.get("fieldGoalsAttempted") or 0
                    m3 = td.get("threePointShotsMade") or 0; a3 = td.get("threePointShotsAttempted") or 0
                    ftm = td.get("freeThrowsMade") or 0; fta = td.get("freeThrowsAttempted") or 0
                    m2 = fgm - m3; a2 = fga - a3
                    ts = {
                        "ppg": (td.get("points") or 0)/gp, "tot": (td.get("totalRebounds") or 0)/gp,
                        "as": (td.get("assists") or 0)/gp, "to": (td.get("turnovers") or 0)/gp,
                        "st": (td.get("steals") or 0)/gp, "bs": (td.get("blocks") or 0)/gp,
                        "pf": (td.get("foulsCommitted") or 0)/gp, "or": (td.get("offensiveRebounds") or 0)/gp,
                        "dr": (td.get("defensiveRebounds") or 0)/gp,
                        "2m": m2/gp, "2a": a2/gp, "3m": m3/gp, "3a": a3/gp, "ftm": ftm/gp, "fta": fta/gp,
                        "fgpct": (fgm/fga*100) if fga>0 else 0, "2pct": (m2/a2*100) if a2>0 else 0,
                        "3pct": (m3/a3*100) if a3>0 else 0, "ftpct": (ftm/fta*100) if fta>0 else 0,
                    }
                    break
        except: pass

    # 2. Player Stats
    loop_urls = [found_url] if found_url else base_urls
    for base_url in loop_urls:
        if not base_url: continue
        try:
            r = requests.get(f"{base_url}/teams/{team_id}/{season_id}/player-stats", headers=API_HEADERS, timeout=4)
            if r.status_code == 200:
                raw_p = r.json()
                p_list = []
                if isinstance(raw_p, list): p_list = raw_p
                elif isinstance(raw_p, dict): p_list = raw_p.get("data", [])
                
                if p_list:
                    df = pd.json_normalize(p_list)
                    df.columns = [str(c).lower() for c in df.columns]

                    col_id = None
                    for opt in ["seasonplayer.id", "seasonplayerid", "personid", "playerid", "id"]:
                        matches = [c for c in df.columns if opt in c]
                        if matches: col_id = sorted(matches, key=len)[0]; break
                    
                    col_fn = next((c for c in df.columns if "firstname" in c), None)
                    col_ln = next((c for c in df.columns if "lastname" in c), None)
                    col_nr = next((c for c in df.columns if "shirtnumber" in c or "jerseynumber" in c), None)

                    df["NAME_FULL"] = (df[col_fn].astype(str) + " " + df[col_ln].astype(str)).str.strip() if (col_fn and col_ln) else "Unknown"
                    df["NR"] = df[col_nr].astype(str).str.replace(".0","",regex=False) if col_nr else "-"
                    df["PLAYER_ID"] = df[col_id].astype(str).str.replace(".0","",regex=False) if col_id else "0"

                    def get_v(row, key, df_cols):
                        matches = [c for c in df_cols if key == c or (key in c and 'pergame' not in c and 'percent' not in c)]
                        if matches:
                            col = sorted(matches, key=len)[0]
                            val = pd.to_numeric(row[col], errors='coerce')
                            return 0.0 if pd.isna(val) else val
                        return 0.0

                    df["GP"] = df.apply(lambda x: get_v(x, "gamesplayed", df.columns), axis=1).replace(0, 1)
                    
                    for k_dest, k_src in [
                        ("PTS_TOT", "points"), ("REB_TOT", "totalrebounds"), ("AST_TOT", "assists"),
                        ("STL_TOT", "steals"), ("TO_TOT", "turnovers"), ("BLK_TOT", "blocks"),
                        ("PF_TOT", "foulscommitted"), ("OR_TOT", "offensiverebounds"), ("DR_TOT", "defensiverebounds"),
                        ("FGM", "fieldgoalsmade"), ("FGA", "fieldgoalsattempted"),
                        ("3M_TOT", "threepointshotsmade"), ("3A_TOT", "threepointshotsattempted"),
                        ("FTM_TOT", "freethrowsmade"), ("FTA_TOT", "freethrowsattempted"),
                        ("SEC_TOT", "secondsplayed")
                    ]:
                        df[k_dest] = df.apply(lambda x: get_v(x, k_src, df.columns), axis=1)

                    # FIX: Division durch GP, damit Avg Minutes rauskommen
                    df["MIN_DISPLAY"] = (df["SEC_TOT"] / df["GP"]).apply(format_minutes)
                    
                    df["PPG"] = (df["PTS_TOT"] / df["GP"]).round(1)
                    df["TOT"] = (df["REB_TOT"] / df["GP"]).round(1)
                    df["AS"] = (df["AST_TOT"] / df["GP"]).round(1)
                    df["ST"] = (df["STL_TOT"] / df["GP"]).round(1)
                    df["TO"] = (df["TO_TOT"] / df["GP"]).round(1)
                    df["BS"] = (df["BLK_TOT"] / df["GP"]).round(1)
                    df["PF"] = (df["PF_TOT"] / df["GP"]).round(1)
                    df["OR"] = (df["OR_TOT"] / df["GP"]).round(1)
                    df["DR"] = (df["DR_TOT"] / df["GP"]).round(1)
                    
                    df["FGM_AVG"] = (df["FGM"] / df["GP"]).round(1)
                    df["FGA_AVG"] = (df["FGA"] / df["GP"]).round(1)
                    df["3M"] = (df["3M_TOT"] / df["GP"]).round(1)
                    df["3A"] = (df["3A_TOT"] / df["GP"]).round(1)
                    df["FTM"] = (df["FTM_TOT"] / df["GP"]).round(1)
                    df["FTA"] = (df["FTA_TOT"] / df["GP"]).round(1)
                    
                    df["2M_TOT"] = df["FGM"] - df["3M_TOT"]
                    df["2A_TOT"] = df["FGA"] - df["3A_TOT"]
                    df["2M"] = (df["2M_TOT"] / df["GP"]).round(1)
                    df["2A"] = (df["2A_TOT"] / df["GP"]).round(1)

                    df["FG%"] = (df["FGM"] / df["FGA"] * 100).fillna(0).round(1)
                    df["3PCT"] = (df["3M_TOT"] / df["3A_TOT"] * 100).fillna(0).round(1)
                    df["FTPCT"] = (df["FTM_TOT"] / df["FTA_TOT"] * 100).fillna(0).round(1)
                    
                    df["select"] = False
                    break 
        except: pass
    
    return df, ts

@st.cache_data(ttl=300)
def fetch_schedule(team_id, season_id):
    clean = []
    # Abfrage über api-1 und api-2
    for base_url in [BASE_URL_1, BASE_URL_2]:
        try:
            r = requests.get(f"{base_url}/games?currentPage=1&seasonTeamId={team_id}&pageSize=100&seasonId={season_id}", headers=API_HEADERS, timeout=2)
            if r.status_code == 200:
                data = r.json()
                items = []
                if isinstance(data, list): items = data
                elif isinstance(data, dict): items = data.get("items") or data.get("data") or []
                
                for g in items:
                    if any(x['id'] == g.get('id') for x in clean): continue
                    res = g.get("result", {}) or {}
                    h_s = res.get('homeTeamFinalScore')
                    clean.append({
                        "id": g.get("id"),
                        "date": g.get("scheduledTime"),
                        "home": g.get("homeTeam", {}).get("name", "?"),
                        "guest": g.get("guestTeam", {}).get("name", "?"),
                        "score": f"{h_s}:{res.get('guestTeamFinalScore')}" if h_s is not None else "-:-",
                        "homeTeamId": str(g.get("homeTeam", {}).get("teamId")),
                        "has_result": (h_s is not None)
                    })
                if clean: break # Gefunden!
        except: pass
    
    def get_date(x): return x.get('date') or "1970-01-01T00:00:00Z"
    clean.sort(key=get_date, reverse=True)
    
    for g in clean:
        try:
            dt = datetime.fromisoformat(g['date'].replace("Z", "+00:00"))
            g['date_display'] = dt.astimezone(pytz.timezone("Europe/Berlin")).strftime("%d.%m.%Y")
        except: g['date_display'] = "-"
    return clean

@st.cache_data(ttl=10)
def fetch_game_boxscore(game_id):
    for base_url in [BASE_URL_1, BASE_URL_2]:
        try:
            r = requests.get(f"{base_url}/games/{game_id}/stats", headers=API_HEADERS, timeout=2)
            if r.status_code == 200: return r.json()
        except: pass
    return None

@st.cache_data(ttl=10)
def fetch_game_details(game_id):
    for base_url in [BASE_URL_1, BASE_URL_2]:
        try:
            r = requests.get(f"{base_url}/games/{game_id}", headers=API_HEADERS, timeout=2)
            if r.status_code == 200: return r.json()
        except: pass
    return None

@st.cache_data(ttl=3600) 
def fetch_team_info_basic(team_id):
    for base_url in [BASE_URL_1, BASE_URL_2]:
        try:
            r = requests.get(f"{base_url}/teams/{team_id}", headers=API_HEADERS, timeout=3)
            if r.status_code == 200:
                data = r.json()
                venues = data.get("venues", [])
                main = next((v for v in venues if v.get("isMain")), venues[0] if venues else None)
                return {"id": team_id, "venue": main}
        except: pass
    return {"id": team_id, "venue": None}

@st.cache_data(ttl=600)
def fetch_season_games(season_id):
    all_games = []
    # Scan beide APIs
    for base_url in [BASE_URL_1, BASE_URL_2]:
        try:
            r = requests.get(f"{base_url}/games?seasonId={season_id}&pageSize=3000", headers=API_HEADERS, timeout=4)
            if r.status_code == 200:
                data = r.json()
                items = []
                if isinstance(data, list): items = data
                elif isinstance(data, dict): items = data.get("items") or data.get("data") or []
                
                for g in items:
                    if not any(x['id'] == g.get("id") for x in all_games):
                        try:
                            dt = datetime.fromisoformat(g.get("scheduledTime").replace("Z", "+00:00")).astimezone(pytz.timezone("Europe/Berlin"))
                            d_str = dt.strftime("%d.%m.%Y %H:%M")
                            d_only = dt.strftime("%d.%m.%Y")
                        except: d_str = "-"; d_only = "-"
                        res = g.get("result") or {}
                        all_games.append({
                            "id": g.get("id"),
                            "date": d_str, "date_only": d_only,
                            "home": g.get("homeTeam", {}).get("name", "?"),
                            "guest": g.get("guestTeam", {}).get("name", "?"),
                            "score": f"{res.get('homeTeamFinalScore',0)}:{res.get('guestTeamFinalScore',0)}" if g.get("status") == "ENDED" else "-:-"
                        })
        except: pass
    return all_games
