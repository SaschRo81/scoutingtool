# --- START OF FILE src/api.py ---

import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import pytz
from src.config import API_HEADERS, SEASON_ID, TEAMS_DB

# --- HILFSFUNKTIONEN ---

def get_base_url(team_id):
    """Ermittelt Server (Nord/Süd) anhand der Team-ID."""
    try:
        tid = int(team_id)
        team_info = TEAMS_DB.get(tid)
        if team_info and team_info.get("staffel") == "Nord":
            return "https://api-n.dbbl.scb.world"
    except:
        pass
    return "https://api-s.dbbl.scb.world"

def format_minutes(seconds):
    if seconds is None: return "00:00"
    try:
        sec = int(seconds); m = sec // 60; s = sec % 60; return f"{m:02d}:{s:02d}"
    except: return "00:00"

def calculate_age(birthdate_str):
    if not birthdate_str or str(birthdate_str).lower() in ["nan", "none", "", "-"]: return "-"
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
                bdate = person.get("birthDate") or person.get("birthdate")
                age = calculate_age(bdate)
                nat = extract_nationality(person)
                if nat == "-": nat = extract_nationality(data)
                return {"img": img, "height": data.get("height", 0), "pos": data.get("position", "-"), "age": age, "nationality": nat}
        except: pass
    return {"img": "", "height": 0, "pos": "-", "age": "-", "nationality": "-"}

@st.cache_data(ttl=600)
def fetch_team_details_raw(team_id, season_id):
    base = get_base_url(team_id)
    url = f"{base}/teams/{team_id}/{season_id}"
    try:
        resp = requests.get(url, headers=API_HEADERS, timeout=3)
        if resp.status_code == 200: return resp.json()
    except: pass
    return None

@st.cache_data(ttl=300)
def fetch_team_data(team_id, season_id):
    base_url = get_base_url(team_id)
    
    api_stats_players = f"{base_url}/teams/{team_id}/{season_id}/player-stats"
    api_team_direct = f"{base_url}/teams/{team_id}/{season_id}/statistics/season"
    
    ts = {}
    df = pd.DataFrame()

    # 1. TEAM STATS LADEN (MIT KORREKTEN FELDNAMEN)
    try:
        r_team = requests.get(api_team_direct, headers=API_HEADERS, timeout=3)
        if r_team.status_code == 200:
            data = r_team.json()
            td = data[0] if isinstance(data, list) and data else data
            
            # SICHERHEITSCHECK: Nur verarbeiten, wenn es ein Dictionary mit Daten ist
            if isinstance(td, dict) and td.get("pointsPerGame") is not None:
                ts = {
                    "ppg": td.get("pointsPerGame") or 0,
                    "tot": td.get("totalReboundsPerGame") or 0,
                    "as": td.get("assistsPerGame") or 0,
                    "to": td.get("turnoversPerGame") or 0,
                    "st": td.get("stealsPerGame") or 0,
                    "bs": td.get("blocksPerGame") or 0,
                    "pf": td.get("foulsCommittedPerGame") or 0,
                    "or": td.get("offensiveReboundsPerGame") or 0,
                    "dr": td.get("defensiveReboundsPerGame") or 0,
                    # WICHTIG: Die Prozentwerte kommen oft als Zahl > 1, nicht als 0.xx
                    "fgpct": td.get("fieldGoalsSuccessPercent") or 0,
                    "3pct": td.get("threePointShotSuccessPercent") or 0,
                    "ftpct": td.get("freeThrowsSuccessPercent") or 0,
                }
    except Exception as e:
        print(f"Fehler bei Team Stats API: {e}")

    # 2. PLAYER STATS LADEN (falls verfügbar)
    try:
        r_stats = requests.get(api_stats_players, headers=API_HEADERS, timeout=4)
        if r_stats.status_code == 200:
            raw_p = r_stats.json()
            p_list = raw_p if isinstance(raw_p, list) else raw_p.get("data", [])
            
            if p_list:
                df = pd.json_normalize(p_list)
                df.columns = [str(c).lower() for c in df.columns]
                
                # Helfer zum sicheren Abrufen von Werten
                def get_val(key, default=0.0):
                    # Sucht nach exakten oder teilweisen Übereinstimmungen
                    matches = [c for c in df.columns if key == c or (key in c and 'pergame' not in c and 'percent' not in c)]
                    if matches:
                        c = sorted(matches, key=len)[0]
                        return pd.to_numeric(df[c], errors="coerce").fillna(default)
                    return pd.Series([default]*len(df), index=df.index)
                
                # Basis Daten
                col_fn = next((c for c in df.columns if "firstname" in c), None)
                col_ln = next((c for c in df.columns if "lastname" in c), None)
                col_nr = next((c for c in df.columns if "shirtnumber" in c or "jerseynumber" in c), None)
                col_id = next((c for c in df.columns if "personid" in c or "seasonplayer.id" in c), None)

                if col_fn and col_ln:
                    df["NAME_FULL"] = (df[col_fn].astype(str) + " " + df[col_ln].astype(str)).str.strip()
                else: df["NAME_FULL"] = "Unknown"
                
                df["NR"] = df[col_nr].astype(str).str.replace(".0","",regex=False) if col_nr else "-"
                df["PLAYER_ID"] = df[col_id].astype(str).str.replace(".0","",regex=False) if col_id else "0"
                
                df["GP"] = get_val("gamesplayed").replace(0, 1)
                
                # TOTALS (ABSOLUTE WERTE) aus der API ziehen
                df["TOTAL_MINUTES"] = get_val("secondsplayed") / 60
                df["TOTAL_PTS"] = get_val("points")
                df["TOTAL_REB"] = get_val("totalrebounds")
                df["TOTAL_AST"] = get_val("assists")
                df["TOTAL_STL"] = get_val("steals")
                df["TOTAL_TO"] = get_val("turnovers")
                df["TOTAL_BLK"] = get_val("blocks")
                df["TOTAL_PF"] = get_val("foulscommitted")
                df["TOTAL_OR"] = get_val("offensiverebounds")
                df["TOTAL_DR"] = get_val("defensiverebounds")

                df["TOTAL_FGM"] = get_val("fieldgoalsmade")
                df["TOTAL_FGA"] = get_val("fieldgoalsattempted")
                df["TOTAL_3M"] = get_val("threepointshotsmade")
                df["TOTAL_3A"] = get_val("threepointshotsattempted")
                df["TOTAL_FTM"] = get_val("freethrowsmade")
                df["TOTAL_FTA"] = get_val("freethrowsattempted")
                df["TOTAL_2M"] = df["TOTAL_FGM"] - df["TOTAL_3M"]
                df["TOTAL_2A"] = df["TOTAL_FGA"] - df["TOTAL_3A"]
                
                # PER GAME (DURCHSCHNITTSWERTE) für die Tabelle berechnen
                gp_safe = df["GP"].replace(0, 1) # Division durch 0 vermeiden
                df["MIN_DISPLAY"] = (df["TOTAL_MINUTES"] * 60 / gp_safe).apply(format_minutes)
                df["PPG"] = (df["TOTAL_PTS"] / gp_safe).round(1)
                df["TOT"] = (df["TOTAL_REB"] / gp_safe).round(1)
                df["AS"] = (df["TOTAL_AST"] / gp_safe).round(1)
                df["ST"] = (df["TOTAL_STL"] / gp_safe).round(1)
                df["TO"] = (df["TOTAL_TO"] / gp_safe).round(1)
                df["BS"] = (df["TOTAL_BLK"] / gp_safe).round(1)
                df["PF"] = (df["TOTAL_PF"] / gp_safe).round(1)
                df["OR"] = (df["TOTAL_OR"] / gp_safe).round(1)
                df["DR"] = (df["TOTAL_DR"] / gp_safe).round(1)
                df["2M"] = (df["TOTAL_2M"] / gp_safe).round(1)
                df["2A"] = (df["TOTAL_2A"] / gp_safe).round(1)
                df["3M"] = (df["TOTAL_3M"] / gp_safe).round(1)
                df["3A"] = (df["TOTAL_3A"] / gp_safe).round(1)
                df["FTM"] = (df["TOTAL_FTM"] / gp_safe).round(1)
                df["FTA"] = (df["TOTAL_FTA"] / gp_safe).round(1)

                df["FG%"] = (df["TOTAL_FGM"] / df["TOTAL_FGA"] * 100).round(1).fillna(0)
                df["3PCT"] = (df["TOTAL_3M"] / df["TOTAL_3A"] * 100).round(1).fillna(0)
                df["FTPCT"] = (df["TOTAL_FTM"] / df["TOTAL_FTA"] * 100).round(1).fillna(0)
                df["select"] = False

    except Exception as e:
        print(f"Error Player Stats ({base_url}): {e}")

    return df, ts

@st.cache_data(ttl=300)
def fetch_schedule(team_id, season_id):
    base_url = get_base_url(team_id)
    url = f"{base_url}/games?currentPage=1&seasonTeamId={team_id}&pageSize=1000&gameType=all&seasonId={season_id}"
    try:
        resp = requests.get(url, headers=API_HEADERS, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            clean = []
            for g in items:
                res = g.get("result", {}) or {}
                h_s = res.get('homeTeamFinalScore')
                g_s = res.get('guestTeamFinalScore')
                score = f"{h_s} : {g_s}" if (h_s is not None) else "-"
                
                raw_d = g.get("scheduledTime", "")
                d_disp = raw_d
                if raw_d:
                    try: 
                        d_disp = datetime.fromisoformat(raw_d.replace("Z", "+00:00")).astimezone(pytz.timezone("Europe/Berlin")).strftime("%d.%m.%Y %H:%M")
                    except: pass
                
                clean.append({
                    "id": g.get("id"), "date": d_disp, "score": score,
                    "home": g.get("homeTeam", {}).get("name", "?"), "guest": g.get("guestTeam", {}).get("name", "?"),
                    "homeTeamId": str(g.get("homeTeam", {}).get("teamId")), 
                    "guestTeamId": str(g.get("guestTeam", {}).get("teamId")),
                    "home_score": h_s, "guest_score": g_s
                })
            return clean
    except: pass
    return []

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
            if main: return {"id": team_id, "venue": main}
    except: pass
    return {"id": team_id, "venue": None}

@st.cache_data(ttl=600)
def fetch_season_games(season_id):
    all_games = []
    
    for subdomain in ["api-s", "api-n"]:
        url = f"https://{subdomain}.dbbl.scb.world/games?seasonId={season_id}&pageSize=3000"
        try:
            resp = requests.get(url, headers=API_HEADERS, timeout=4)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                for g in items:
                    raw_d = g.get("scheduledTime", "")
                    dt_obj = None; d_disp = "-"; date_only = "-"
                    if raw_d:
                        try:
                            dt_obj = datetime.fromisoformat(raw_d.replace("Z", "+00:00")).astimezone(pytz.timezone("Europe/Berlin"))
                            d_disp = dt_obj.strftime("%d.%m.%Y %H:%M")
                            date_only = dt_obj.strftime("%d.%m.%Y")
                        except: pass
                    res = g.get("result") or {}
                    
                    if not any(x['id'] == g.get("id") for x in all_games):
                        all_games.append({
                            "id": g.get("id"), "date": d_disp, "date_only": date_only,
                            "home": g.get("homeTeam", {}).get("name", "?"),
                            "guest": g.get("guestTeam", {}).get("name", "?"),
                            "score": f"{res.get('homeTeamFinalScore',0)}:{res.get('guestTeamFinalScore',0)}" if g.get("status") == "ENDED" else "-:-",
                            "status": g.get("status")
                        })
        except: pass
        
    return all_games
