# --- START OF FILE src/api.py ---

import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from src.config import API_HEADERS, TEAMS_DB

# --- HILFSFUNKTIONEN ---

def get_base_url(team_id):
    """Ermittelt Server (Nord/Süd) anhand der Team-ID."""
    try:
        tid = int(team_id)
        team_info = TEAMS_DB.get(tid)
        if team_info and team_info.get("staffel") == "Nord":
            return "https://api-n.dbbl.scb.world"
    except: pass
    return "https://api-s.dbbl.scb.world"

def format_minutes(seconds):
    if seconds is None: return "00:00"
    try:
        sec = int(seconds); m = sec // 60; s = sec % 60; return f"{m:02d}:{s:02d}"
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

# --- CACHED API CALLS (Nur Stammdaten) ---

@st.cache_data(ttl=3600, show_spinner=False)
def get_player_metadata_cached(player_id):
    clean_id = str(player_id).replace(".0", "")
    for subdomain in ["api-s", "api-n"]:
        url = f"https://{subdomain}.dbbl.scb.world/season-players/{clean_id}"
        try:
            resp = requests.get(url, headers=API_HEADERS, timeout=1.0)
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
    urls = [
        f"https://api-1.dbbl.scb.world/teams/{team_id}/{season_id}",
        f"https://api-s.dbbl.scb.world/teams/{team_id}/{season_id}",
        f"https://api-n.dbbl.scb.world/teams/{team_id}/{season_id}"
    ]
    for url in urls:
        try:
            resp = requests.get(url, headers=API_HEADERS, timeout=2)
            if resp.status_code == 200: return resp.json()
        except: pass
    return None

# --- HAUPTFUNKTION (LIVE ABFRAGE) ---
# Name geändert zu 'get_team_data_no_cache', damit Streamlit den Cache verwirft!
def get_team_data_no_cache(team_id, season_id):
    base_url = get_base_url(team_id)
    
    api_stats_players = f"{base_url}/teams/{team_id}/{season_id}/player-stats"
    api_team_direct = f"{base_url}/teams/{team_id}/{season_id}/statistics/season"
    
    ts = {}
    df = pd.DataFrame()

    # 1. TEAM STATS LADEN
    try:
        r_team = requests.get(api_team_direct, headers=API_HEADERS, timeout=3)
        if r_team.status_code == 200:
            data = r_team.json()
            td = data[0] if isinstance(data, list) and data else data
            
            if isinstance(td, dict) and td.get("gamesPlayed"):
                gp = td.get("gamesPlayed") or 1
                
                fgm = td.get("fieldGoalsMade") or 0; fga = td.get("fieldGoalsAttempted") or 0
                m3 = td.get("threePointShotsMade") or 0; a3 = td.get("threePointShotsAttempted") or 0
                ftm = td.get("freeThrowsMade") or 0; fta = td.get("freeThrowsAttempted") or 0
                m2 = fgm - m3; a2 = fga - a3

                ts = {
                    "ppg": (td.get("points") or 0) / gp,
                    "tot": (td.get("totalRebounds") or 0) / gp,
                    "as": (td.get("assists") or 0) / gp,
                    "to": (td.get("turnovers") or 0) / gp,
                    "st": (td.get("steals") or 0) / gp,
                    "bs": (td.get("blocks") or 0) / gp,
                    "pf": (td.get("foulsCommitted") or 0) / gp,
                    "or": (td.get("offensiveRebounds") or 0) / gp,
                    "dr": (td.get("defensiveRebounds") or 0) / gp,
                    
                    "2m": m2 / gp, "2a": a2 / gp, 
                    "3m": m3 / gp, "3a": a3 / gp, 
                    "ftm": ftm / gp, "fta": fta / gp,

                    "fgpct": (fgm / fga * 100) if fga > 0 else 0,
                    "2pct": (m2 / a2 * 100) if a2 > 0 else 0,
                    "3pct": (m3 / a3 * 100) if a3 > 0 else 0,
                    "ftpct": (ftm / fta * 100) if fta > 0 else 0,
                }
    except: pass

    # 2. PLAYER STATS LADEN
    try:
        roster_lookup = {}
        raw_details = fetch_team_details_raw(team_id, season_id)
        if raw_details:
            squad = raw_details.get("squad", []) if isinstance(raw_details, dict) else []
            for entry in squad:
                p = entry.get("person", {})
                raw_id = p.get("id") or entry.get("id")
                if raw_id:
                    pid = str(raw_id).replace(".0", "")
                    bdate = p.get("birthDate") or p.get("birthdate") or entry.get("birthDate") or entry.get("birthdate")
                    nat = extract_nationality(p)
                    if nat == "-": nat = extract_nationality(entry)
                    roster_lookup[pid] = {"birthdate": bdate, "nationality": nat, "height": p.get("height", "-")}
        
        r_stats = requests.get(api_stats_players, headers=API_HEADERS, timeout=4)
        if r_stats.status_code == 200:
            raw_p = r_stats.json()
            p_list = raw_p if isinstance(raw_p, list) else raw_p.get("data", [])
            
            if p_list:
                df = pd.json_normalize(p_list)
                df.columns = [str(c).lower() for c in df.columns]
                
                # Mapping Helpers
                def get_col(candidates):
                    for cand in candidates:
                        found = [c for c in df.columns if cand in c]
                        if found: return sorted(found, key=len)[0]
                    return None

                col_fn = get_col(["firstname"]); col_ln = get_col(["lastname"])
                col_nr = get_col(["shirtnumber", "jerseynumber", "no"])
                col_id = get_col(["personid", "seasonplayer.id", "playerid", "id"])

                df["NAME_FULL"] = (df[col_fn].astype(str) + " " + df[col_ln].astype(str)).str.strip() if col_fn and col_ln else "Unknown"
                df["NR"] = df[col_nr].astype(str).str.replace(".0","",regex=False) if col_nr else "-"
                df["PLAYER_ID"] = df[col_id].astype(str).str.replace(".0","",regex=False) if col_id else "0"
                
                # Metadaten
                df["BIRTHDATE"] = df["PLAYER_ID"].apply(lambda pid: roster_lookup.get(pid, {}).get("birthdate"))
                df["NATIONALITY"] = df["PLAYER_ID"].apply(lambda pid: roster_lookup.get(pid, {}).get("nationality", "-"))
                df["HEIGHT_ROSTER"] = df["PLAYER_ID"].apply(lambda pid: roster_lookup.get(pid, {}).get("height", "-"))
                df["AGE"] = df["BIRTHDATE"].apply(calculate_age)
                
                # Fallback für Metadaten wenn leer
                mask_no_age = (df["AGE"] == "-")
                if mask_no_age.any():
                    df.loc[mask_no_age, "AGE"] = df.loc[mask_no_age, "PLAYER_ID"].apply(lambda pid: get_player_metadata_cached(pid).get("age", "-"))
                
                # Stats Mapping
                def get_val(key, default=0.0):
                    c = get_col([key])
                    return pd.to_numeric(df[c], errors="coerce").fillna(default) if c else pd.Series([default]*len(df), index=df.index)

                df["GP"] = get_val("gamesplayed").replace(0, 1)
                
                sec = get_val("secondsplayed")
                if sec.sum() > 0: df["MIN_FINAL"] = sec / df["GP"]
                else: df["MIN_FINAL"] = get_val("minutespergame")
                df["MIN_DISPLAY"] = df["MIN_FINAL"].apply(format_minutes)

                df["PPG"] = get_val("pointspergame"); df["TOT"] = get_val("totalreboundspergame")
                df["AS"] = get_val("assistspergame"); df["TO"] = get_val("turnoverspergame")
                df["ST"] = get_val("stealspergame"); df["BS"] = get_val("blockspergame")
                df["PF"] = get_val("foulscommittedpergame")
                
                m2 = get_val("twopointshotsmadepergame"); a2 = get_val("twopointshotsattemptedpergame")
                m3 = get_val("threepointshotsmadepergame"); a3 = get_val("threepointshotsattemptedpergame")
                df["2M"] = m2; df["2A"] = a2; df["3M"] = m3; df["3A"] = a3
                
                df["FTM"] = get_val("freethrowsmadepergame"); df["FTA"] = get_val("freethrowsattemptedpergame")
                df["OR"] = get_val("offensivereboundspergame"); df["DR"] = get_val("defensivereboundspergame")

                # Prozentberechnung Player
                att = a2 + a3
                df["FG%"] = 0.0
                mask = att > 0
                df.loc[mask, "FG%"] = ((m2[mask] + m3[mask]) / att[mask] * 100).round(1)
                
                df["3PCT"] = get_val("threepointshotsuccesspercent").apply(lambda x: round(x*100,1) if x<=1 else round(x,1))
                df["FTPCT"] = get_val("freethrowssuccesspercent").apply(lambda x: round(x*100,1) if x<=1 else round(x,1))
                
                # 2-Punkt Quote
                df["2PCT"] = 0.0
                mask2 = df["2A"] > 0
                df.loc[mask2, "2PCT"] = (df.loc[mask2, "2M"] / df.loc[mask2, "2A"] * 100).round(1)

                df["select"] = False

    except Exception as e:
        print(f"Error Player Stats ({base_url}): {e}")

    # Fallback für Team Stats, wenn API leer, aber Spieler da
    if not ts and not df.empty:
        tg = df["GP"].max() if not df.empty else 1
        # Hier vereinfachte Summen, da wir nur PerGame Werte haben
        ts = {
            "ppg": df["PPG"].sum(), "tot": df["TOT"].sum(),
            "as": df["AS"].sum(), "st": df["ST"].sum(), "to": df["TO"].sum(), "bs": df["BS"].sum(),
            "pf": df["PF"].sum(), "or": df["OR"].sum(), "dr": df["DR"].sum(),
            "fgpct": df[df["FG%"]>0]["FG%"].mean() if not df.empty else 0,
            "3pct": df[df["3PCT"]>0]["3PCT"].mean() if not df.empty else 0,
            "ftpct": df[df["FTPCT"]>0]["FTPCT"].mean() if not df.empty else 0,
            # Dummy Values für HTML Gen
            "2m": 0, "2a": 0, "2pct": 0, "3m": 0, "3a": 0, "ftm": 0, "fta": 0
        }

    # SAFETY: Spalten auffüllen für HTML Report
    if df is not None and not df.empty:
        required = ["2M", "2A", "2PCT", "3M", "3A", "3PCT", "FTM", "FTA", "FTPCT", 
                    "DR", "OR", "TOT", "AS", "TO", "ST", "PF", "BS", "PPG", "MIN_DISPLAY"]
        for c in required:
            if c not in df.columns: df[c] = 0

    return df, ts

# Dieser Alias ist wichtig, falls app.py noch die alte Bezeichnung nutzt
fetch_team_data = get_team_data_no_cache

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
                    "home_score": h_s, "guest_score": g_s,
                    "has_result": (h_s is not None and g_s is not None)
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
