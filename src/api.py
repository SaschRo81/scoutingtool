# --- START OF FILE src/api.py ---

import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import pytz
from src.config import API_HEADERS, SEASON_ID 

# Lokale Hilfsfunktionen
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
    except:
        return "-"

def extract_nationality(data_obj):
    if not data_obj: return "-"
    if "nationalities" in data_obj and isinstance(data_obj["nationalities"], list) and data_obj["nationalities"]:
        first = data_obj["nationalities"][0]
        if isinstance(first, str): return "/".join(data_obj["nationalities"])
        elif isinstance(first, dict): return "/".join([n.get("name", "") for n in data_obj["nationalities"]])
    if "nationality" in data_obj and isinstance(data_obj["nationality"], dict):
        return data_obj["nationality"].get("name", "-")
    return "-"

@st.cache_data(ttl=3600, show_spinner=False)
def get_player_metadata_cached(player_id):
    try:
        clean_id = str(player_id).replace(".0", "")
        url = f"https://api-s.dbbl.scb.world/season-players/{clean_id}"
        resp = requests.get(url, headers=API_HEADERS, timeout=2)
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
    url = f"https://api-1.dbbl.scb.world/teams/{team_id}/{season_id}"
    try:
        resp = requests.get(url, headers=API_HEADERS, timeout=3)
        if resp.status_code == 200: return resp.json()
    except: pass
    return None

@st.cache_data(ttl=600)
def fetch_team_data(team_id, season_id):
    """
    Lädt Team-Statistiken UND Spieler-Statistiken.
    Nutzt jetzt den direkten Team-Statistik Endpunkt.
    """
    # 1. URLs definieren
    # NEU: Direkter Team-Link wie von dir vorgeschlagen
    api_team_direct = f"https://api-s.dbbl.scb.world/teams/{team_id}/{season_id}/statistics/season"
    # Fallback: Globale Suche (falls direkt fehlschlägt)
    api_team_fallback = f"https://api-s.dbbl.scb.world/seasons/{season_id}/team-statistics?displayType=MAIN_ROUND&teamId={team_id}"
    
    api_stats_players = f"https://api-s.dbbl.scb.world/teams/{team_id}/{season_id}/player-stats"
    
    ts = {}
    df = pd.DataFrame()

    # ---------------------------------------------------------
    # TEIL A: TEAM STATS LADEN
    # ---------------------------------------------------------
    try:
        # Versuch 1: Direkter Link (bevorzugt)
        r_team = requests.get(api_team_direct, headers=API_HEADERS, timeout=3)
        
        td = None
        if r_team.status_code == 200:
            td = r_team.json() # Hier kommt meist direkt das Objekt
        
        # Versuch 2: Fallback Link, falls Direktlink 404/leer
        if not td:
            r_fallback = requests.get(api_team_fallback, headers=API_HEADERS, timeout=3)
            if r_fallback.status_code == 200:
                raw_list = r_fallback.json()
                if raw_list and isinstance(raw_list, list):
                    td = next((item for item in raw_list if str(item.get("teamId")) == str(team_id)), raw_list[0])

        # Daten mappen, wenn vorhanden
        if td:
            ts = {
                "ppg": td.get("pointsPerGame", 0), "tot": td.get("totalReboundsPerGame", 0),
                "as": td.get("assistsPerGame", 0), "to": td.get("turnoversPerGame", 0),
                "st": td.get("stealsPerGame", 0), "bs": td.get("blocksPerGame", 0),
                "pf": td.get("foulsCommittedPerGame", 0),
                "2m": td.get("twoPointShotsMadePerGame", 0), "2a": td.get("twoPointShotsAttemptedPerGame", 0), "2pct": td.get("twoPointShotsSuccessPercent", 0),
                "3m": td.get("threePointShotsMadePerGame", 0), "3a": td.get("threePointShotsAttemptedPerGame", 0), "3pct": td.get("threePointShotsSuccessPercent", 0),
                "ftm": td.get("freeThrowsMadePerGame", 0), "fta": td.get("freeThrowsAttemptedPerGame", 0), "ftpct": td.get("freeThrowsSuccessPercent", 0),
                "dr": td.get("defensiveReboundsPerGame", 0), "or": td.get("offensiveReboundsPerGame", 0),
                "fgpct": td.get("fieldGoalsSuccessPercent", 0)
            }
    except Exception as e:
        print(f"Error fetching team stats: {e}")

    # ---------------------------------------------------------
    # TEIL B: PLAYER STATS LADEN
    # ---------------------------------------------------------
    try:
        # Lookup für Metadaten vorbereiten (Geburtstag etc.)
        roster_lookup = {}
        raw_details = fetch_team_details_raw(team_id, season_id)
        if raw_details:
            squad = raw_details.get("squad", []) if isinstance(raw_details, dict) else []
            for entry in squad:
                p = entry.get("person", {})
                raw_id = p.get("id") or entry.get("id")
                if not raw_id: continue
                pid = str(raw_id).replace(".0", "")
                bdate = p.get("birthDate") or p.get("birthdate") or entry.get("birthDate")
                nat = extract_nationality(p)
                if nat == "-": nat = extract_nationality(entry)
                roster_lookup[pid] = {"birthdate": bdate, "nationality": nat, "height": p.get("height", "-")}

        # Spieler Stats abrufen
        r_stats = requests.get(api_stats_players, headers=API_HEADERS, timeout=3)
        
        if r_stats.status_code == 200:
            raw_p = r_stats.json()
            p_list = raw_p if isinstance(raw_p, list) else raw_p.get("data", [])
            
            if p_list:
                df = pd.json_normalize(p_list)
                df.columns = [str(c).lower() for c in df.columns]
                
                col_map = {
                    "firstname": ["seasonplayer.person.firstname", "person.firstname", "firstname"], 
                    "lastname": ["seasonplayer.person.lastname", "person.lastname", "lastname"],
                    "shirtnumber": ["seasonplayer.shirtnumber", "jerseynumber", "shirtnumber", "no"], 
                    "id": ["seasonplayer.personid", "seasonplayer.id", "playerid", "person.id", "id"]
                }
                final_cols = {}
                for target, opts in col_map.items():
                    for opt in opts:
                        matches = [c for c in df.columns if opt in c]
                        if matches: final_cols[target] = sorted(matches, key=len)[0]; break
                
                def get_s(k): 
                    c = final_cols.get(k)
                    return df[c].astype(str).fillna("") if c in df.columns else pd.Series([""]*len(df), index=df.index)
                
                def get_n(k, default=0.0):
                    matches = [c for c in df.columns if k in c]
                    if matches:
                        col = sorted(matches, key=len)[0]
                        return pd.to_numeric(df[col], errors="coerce").fillna(default)
                    return pd.Series([default]*len(df), index=df.index)
                
                df["NAME_FULL"] = (get_s("firstname") + " " + get_s("lastname")).str.strip()
                df["NR"] = get_s("shirtnumber").str.replace(".0", "", regex=False)
                df["PLAYER_ID"] = get_s("id").str.replace(".0", "", regex=False)
                
                df["BIRTHDATE"] = df["PLAYER_ID"].apply(lambda x: roster_lookup.get(x, {}).get("birthdate", ""))
                df["NATIONALITY"] = df["PLAYER_ID"].apply(lambda x: roster_lookup.get(x, {}).get("nationality", "-"))
                df["HEIGHT_ROSTER"] = df["PLAYER_ID"].apply(lambda x: roster_lookup.get(x, {}).get("height", "-"))
                df["AGE"] = df["BIRTHDATE"].apply(calculate_age)
                
                df["GP"] = get_n("gamesplayed").replace(0,1)
                min_raw = get_n("minutespergame")
                df["MIN_FINAL"] = min_raw
                mask_zero = (df["MIN_FINAL"] <= 0) & (df["GP"] > 0)
                if not df.loc[mask_zero].empty:
                    sec_cols = [c for c in df.columns if "secondsplayed" in c]
                    if sec_cols:
                        sec_series = pd.to_numeric(df[sec_cols[0]], errors="coerce").fillna(0)
                        df.loc[mask_zero, "MIN_FINAL"] = sec_series[mask_zero] / df.loc[mask_zero, "GP"]
                
                df["MIN_DISPLAY"] = df["MIN_FINAL"].apply(format_minutes)
                df["PPG"] = get_n("pointspergame"); df["TOT"] = get_n("totalreboundspergame"); df["AS"] = get_n("assistspergame")
                df["TO"] = get_n("turnoverspergame"); df["ST"] = get_n("stealspergame"); df["BS"] = get_n("blockspergame"); df["PF"] = get_n("foulscommittedpergame")
                
                m2 = get_n("twopointshotsmadepergame"); a2 = get_n("twopointshotsattemptedpergame")
                m3 = get_n("threepointshotsmadepergame"); a3 = get_n("threepointshotsattemptedpergame")
                df["2M"] = m2; df["2A"] = a2
                df["3M"] = m3; df["3A"] = a3
                
                total_att = a2 + a3
                df["FG%"] = pd.Series([0.0]*len(df), index=df.index)
                mask_att = total_att > 0
                df.loc[mask_att, "FG%"] = ((m2[mask_att]+m3[mask_att]) / total_att[mask_att] * 100).round(1)
                
                df["2PCT"] = get_n("twopointshotsuccesspercent").apply(lambda x: round(x*100, 1) if x <= 1 else round(x, 1))
                df["3PCT"] = get_n("threepointshotsuccesspercent").apply(lambda x: round(x*100, 1) if x <= 1 else round(x, 1))
                df["FTM"] = get_n("freethrowsmadepergame"); df["FTA"] = get_n("freethrowsattemptedpergame")
                df["FTPCT"] = get_n("freethrowssuccesspercent").apply(lambda x: round(x*100, 1) if x <= 1 else round(x, 1))
                df["OR"] = get_n("offensivereboundspergame"); df["DR"] = get_n("defensivereboundspergame")
                
                df["select"] = False
    except Exception as e:
        print(f"Error fetching player stats: {e}")

    # Rückgabe: Erfolg, wenn zumindest eines von beiden da ist
    if ts or (not df.empty):
        return df, ts
    
    return None, None

@st.cache_data(ttl=300)
def fetch_schedule(team_id, season_id):
    url = f"https://api-s.dbbl.scb.world/games?currentPage=1&seasonTeamId={team_id}&pageSize=1000&gameType=all&seasonId={season_id}"
    try:
        resp = requests.get(url, headers=API_HEADERS, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            clean = []
            for g in items:
                res = g.get("result")
                score = "-"
                has_res = False
                h_score = 0
                g_score = 0
                if res and isinstance(res, dict):
                    h_score = res.get('homeTeamFinalScore')
                    g_score = res.get('guestTeamFinalScore')
                    if h_score is not None and g_score is not None:
                        score = f"{h_score} : {g_score}"; has_res = True
                
                raw_d = g.get("scheduledTime", "")
                d_disp = raw_d
                if raw_d:
                    try: 
                        d_disp = datetime.fromisoformat(raw_d.replace("Z", "+00:00")).astimezone(pytz.timezone("Europe/Berlin")).strftime("%d.%m.%Y %H:%M")
                    except: pass
                
                clean.append({
                    "id": g.get("id"), "date": d_disp, "score": score, "has_result": has_res,
                    "home": g.get("homeTeam", {}).get("name", "?"), "guest": g.get("guestTeam", {}).get("name", "?"),
                    "homeTeamId": str(g.get("homeTeam", {}).get("teamId")), 
                    "guestTeamId": str(g.get("guestTeam", {}).get("teamId")),
                    "home_score": h_score, "guest_score": g_score
                })
            return clean
    except: pass
    return []

@st.cache_data(ttl=10)
def fetch_game_boxscore(game_id):
    try: return requests.get(f"https://api-s.dbbl.scb.world/games/{game_id}/stats", headers=API_HEADERS, timeout=3).json()
    except: return None

@st.cache_data(ttl=10)
def fetch_game_details(game_id):
    try: return requests.get(f"https://api-s.dbbl.scb.world/games/{game_id}", headers=API_HEADERS, timeout=3).json()
    except: return None

@st.cache_data(ttl=3600) 
def fetch_team_info_basic(team_id):
    try:
        resp = requests.get(f"https://api-s.dbbl.scb.world/teams/{team_id}", headers=API_HEADERS, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            venues = data.get("venues", [])
            main = next((v for v in venues if v.get("isMain")), venues[0] if venues else None)
            if main: return {"id": team_id, "venue": main}
    except: pass
    return {"id": team_id, "venue": None}

@st.cache_data(ttl=600)
def fetch_season_games(season_id):
    url = f"https://api-s.dbbl.scb.world/games?seasonId={season_id}&pageSize=3000"
    try:
        resp = requests.get(url, headers=API_HEADERS, timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            clean = []
            for g in items:
                raw_d = g.get("scheduledTime", "")
                dt_obj = None
                d_disp = "-"
                date_only = "-"
                if raw_d:
                    try:
                        dt_obj = datetime.fromisoformat(raw_d.replace("Z", "+00:00")).astimezone(pytz.timezone("Europe/Berlin"))
                        d_disp = dt_obj.strftime("%d.%m.%Y %H:%M")
                        date_only = dt_obj.strftime("%d.%m.%Y")
                    except: pass
                
                res = g.get("result") or {}
                h_s = res.get("homeTeamFinalScore", 0)
                g_s = res.get("guestTeamFinalScore", 0)
                
                clean.append({
                    "id": g.get("id"),
                    "date": d_disp,
                    "date_only": date_only,
                    "home": g.get("homeTeam", {}).get("name", "?"),
                    "guest": g.get("guestTeam", {}).get("name", "?"),
                    "score": f"{h_s}:{g_s}" if g.get("status") == "ENDED" else "-:-",
                    "status": g.get("status")
                })
            return clean
    except: pass
    return []
