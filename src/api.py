# --- START OF FILE src/api.py ---
import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import pytz
from src.config import API_HEADERS, TEAMS_DB

# --- HILFSFUNKTIONEN ---
def get_base_url(team_id=None):
    # Einfache Logik, kann erweitert werden
    if team_id:
        try:
            tid = int(team_id)
            if tid in TEAMS_DB and TEAMS_DB[tid]["staffel"] == "Nord":
                return "https://api-n.dbbl.scb.world"
        except: pass
    return "https://api-s.dbbl.scb.world"

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

# --- CACHED API CALLS ---

@st.cache_data(ttl=3600, show_spinner=False)
def get_player_metadata_cached(player_id):
    clean_id = str(player_id).replace(".0", "")
    for subdomain in ["api-s", "api-n"]:
        url = f"https://{subdomain}.dbbl.scb.world/season-players/{clean_id}"
        try:
            resp = requests.get(url, headers=API_HEADERS, timeout=1.5)
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
    """Holt die komplette Tabelle für eine Gruppe (NORTH/SOUTH)."""
    subdomain = "api-n" if group_name == "NORTH" else "api-s"
    url = f"https://{subdomain}.dbbl.scb.world/standings?seasonId={season_id}&group={group_name}"
    
    try:
        r = requests.get(url, headers=API_HEADERS, timeout=4)
        if r.status_code == 200:
            data = r.json()
            items = data if isinstance(data, list) else data.get("items", [])
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
                    "points": entry.get("points") # Tabellenpunkte (oder scores)
                })
            return sorted(standings, key=lambda x: x['rank'])
    except Exception as e:
        print(f"Standings Error: {e}")
    return []

def fetch_team_data(team_id, season_id):
    base_url = get_base_url(team_id)
    api_stats_players = f"{base_url}/teams/{team_id}/{season_id}/player-stats"
    api_team_direct = f"{base_url}/teams/{team_id}/{season_id}/statistics/season"
    ts = {}; df = pd.DataFrame()

    try:
        r_team = requests.get(api_team_direct, headers=API_HEADERS, timeout=3)
        if r_team.status_code == 200:
            data = r_team.json()
            # Logik zum Finden des korrekten Eintrags (vereinfacht)
            td = data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else {})
            if td:
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
    except: pass

    try:
        r_stats = requests.get(api_stats_players, headers=API_HEADERS, timeout=4)
        if r_stats.status_code == 200:
            raw_p = r_stats.json()
            p_list = raw_p if isinstance(raw_p, list) else raw_p.get("data", [])
            if p_list:
                df = pd.json_normalize(p_list)
                df.columns = [str(c).lower() for c in df.columns]
                
                # Helper für dynamische Spaltenwahl
                def get_val(key, default=0.0):
                    matches = [c for c in df.columns if key == c or (key in c and 'pergame' not in c and 'percent' not in c)]
                    if matches: return pd.to_numeric(df[sorted(matches, key=len)[0]], errors="coerce").fillna(default)
                    return pd.Series([default]*len(df), index=df.index)

                col_id_opts = ["seasonplayer.id", "seasonplayerid", "personid", "playerid", "id"]
                col_id = next((sorted([c for c in df.columns if opt in c], key=len)[0] for opt in col_id_opts if any(opt in c for c in df.columns)), None)
                col_fn = next((c for c in df.columns if "firstname" in c), None)
                col_ln = next((c for c in df.columns if "lastname" in c), None)
                col_nr = next((c for c in df.columns if "shirtnumber" in c or "jerseynumber" in c), None)

                if col_fn and col_ln: df["NAME_FULL"] = (df[col_fn].astype(str) + " " + df[col_ln].astype(str)).str.strip()
                else: df["NAME_FULL"] = "Unknown"
                
                df["NR"] = df[col_nr].astype(str).str.replace(".0","",regex=False) if col_nr else "-"
                df["PLAYER_ID"] = df[col_id].astype(str).str.replace(".0","",regex=False) if col_id else "0"
                
                # Stats calculation
                df["GP"] = get_val("gamesplayed").replace(0, 1)
                df["MIN_DISPLAY"] = (get_val("secondsplayed") / 60 / df["GP"]).apply(format_minutes)
                
                df["PPG"] = (get_val("points")/df["GP"]).round(1)
                df["TOT"] = (get_val("totalrebounds")/df["GP"]).round(1)
                df["AS"] = (get_val("assists")/df["GP"]).round(1)
                df["ST"] = (get_val("steals")/df["GP"]).round(1)
                df["TO"] = (get_val("turnovers")/df["GP"]).round(1)
                df["BS"] = (get_val("blocks")/df["GP"]).round(1)
                df["PF"] = (get_val("foulscommitted")/df["GP"]).round(1)
                df["OR"] = (get_val("offensiverebounds")/df["GP"]).round(1)
                df["DR"] = (get_val("defensiverebounds")/df["GP"]).round(1)
                
                df["FGM"] = (get_val("fieldgoalsmade")/df["GP"]).round(1)
                df["FGA"] = (get_val("fieldgoalsattempted")/df["GP"]).round(1)
                df["3M"] = (get_val("threepointshotsmade")/df["GP"]).round(1)
                df["3A"] = (get_val("threepointshotsattempted")/df["GP"]).round(1)
                df["FTM"] = (get_val("freethrowsmade")/df["GP"]).round(1)
                df["FTA"] = (get_val("freethrowsattempted")/df["GP"]).round(1)
                df["2M"] = (df["FGM"] - df["3M"]).round(1)
                df["2A"] = (df["FGA"] - df["3A"]).round(1)

                df["FG%"] = (get_val("fieldgoalsmade") / get_val("fieldgoalsattempted") * 100).round(1).fillna(0)
                df["3PCT"] = (get_val("threepointshotsmade") / get_val("threepointshotsattempted") * 100).round(1).fillna(0)
                df["FTPCT"] = (get_val("freethrowsmade") / get_val("freethrowsattempted") * 100).round(1).fillna(0)
                
                df["select"] = False
    except: pass
    
    return df, ts

@st.cache_data(ttl=300)
def fetch_schedule(team_id, season_id):
    # Kombinierter Call auf beide APIs zur Sicherheit
    clean = []
    for subdomain in ["api-s", "api-n"]:
        url = f"https://{subdomain}.dbbl.scb.world/games?currentPage=1&seasonTeamId={team_id}&pageSize=100&seasonId={season_id}"
        try:
            r = requests.get(url, headers=API_HEADERS, timeout=2)
            if r.status_code == 200:
                items = r.json().get("items", [])
                for g in items:
                    if any(x['id'] == g.get('id') for x in clean): continue # Duplikate vermeiden
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
                if clean: break # Wenn Daten gefunden, brich Loop ab
        except: pass
    
    # Sortieren
    def parse_dt(d_str):
        try: return datetime.fromisoformat(d_str.replace("Z", "+00:00"))
        except: return datetime.min
    clean.sort(key=lambda x: parse_dt(x['date']), reverse=True)
    
    # Formatierung für UI
    for g in clean:
        dt = parse_dt(g['date'])
        if dt != datetime.min:
             g['date_display'] = dt.astimezone(pytz.timezone("Europe/Berlin")).strftime("%d.%m.%Y")
        else: g['date_display'] = "-"
        
    return clean

@st.cache_data(ttl=10)
def fetch_game_boxscore(game_id):
    for subdomain in ["api-s", "api-n"]:
        try:
            r = requests.get(f"https://{subdomain}.dbbl.scb.world/games/{game_id}/stats", headers=API_HEADERS, timeout=2)
            if r.status_code == 200: return r.json()
        except: pass
    return None

@st.cache_data(ttl=10)
def fetch_game_details(game_id):
    for subdomain in ["api-s", "api-n"]:
        try:
            r = requests.get(f"https://{subdomain}.dbbl.scb.world/games/{game_id}", headers=API_HEADERS, timeout=2)
            if r.status_code == 200: return r.json()
        except: pass
    return None

@st.cache_data(ttl=3600) 
def fetch_team_info_basic(team_id):
    base_url = get_base_url(team_id)
    try:
        resp = requests.get(f"{base_url}/teams/{team_id}", headers=API_HEADERS, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            venues = data.get("venues", [])
            main = next((v for v in venues if v.get("isMain")), venues[0] if venues else None)
            return {"id": team_id, "venue": main}
    except: pass
    return {"id": team_id, "venue": None}

@st.cache_data(ttl=600)
def fetch_season_games(season_id):
    all_games = []
    for subdomain in ["api-s", "api-n"]:
        url = f"https://{subdomain}.dbbl.scb.world/games?seasonId={season_id}&pageSize=3000"
        try:
            r = requests.get(url, headers=API_HEADERS, timeout=4)
            if r.status_code == 200:
                items = r.json().get("items", [])
                for g in items:
                    if not any(x['id'] == g.get("id") for x in all_games):
                        dt_obj = datetime.fromisoformat(g.get("scheduledTime").replace("Z", "+00:00")).astimezone(pytz.timezone("Europe/Berlin"))
                        res = g.get("result") or {}
                        all_games.append({
                            "id": g.get("id"),
                            "date": dt_obj.strftime("%d.%m.%Y %H:%M"),
                            "date_only": dt_obj.strftime("%d.%m.%Y"),
                            "home": g.get("homeTeam", {}).get("name", "?"),
                            "guest": g.get("guestTeam", {}).get("name", "?"),
                            "score": f"{res.get('homeTeamFinalScore',0)}:{res.get('guestTeamFinalScore',0)}" if g.get("status") == "ENDED" else "-:-"
                        })
        except: pass
    return all_games

@st.cache_data(ttl=1800)
def fetch_team_rank(team_id, season_id):
    # Fallback Funktion
    return None # Nicht mehr benötigt für V6 (verwenden standings_complete)
