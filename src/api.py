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

    # 1. PLAYER STATS LADEN
    try:
        r_stats = requests.get(api_stats_players, headers=API_HEADERS, timeout=4)
        if r_stats.status_code == 200:
            raw_p = r_stats.json()
            p_list = raw_p if isinstance(raw_p, list) else raw_p.get("data", [])
            
            if p_list:
                df = pd.json_normalize(p_list)
                df.columns = [str(c).lower() for c in df.columns]
                
                # Dynamisches Mapping & Datenbereinigung
                def get_val(key, default=0.0):
                    matches = [c for c in df.columns if key in c and 'percent' not in c]
                    if matches:
                        c = sorted(matches, key=len)[0]
                        return pd.to_numeric(df[c], errors="coerce").fillna(default)
                    return pd.Series([default]*len(df), index=df.index)

                def get_pct(key, default=0.0):
                    matches = [c for c in df.columns if key in c and 'percent' in c]
                    if matches:
                        c = sorted(matches, key=len)[0]
                        s = pd.to_numeric(df[c], errors="coerce").fillna(default)
                        # Wenn Werte > 1, sind sie schon %, sonst * 100
                        return s.apply(lambda x: round(x, 1) if x > 1 else round(x * 100, 1))
                    return pd.Series([default]*len(df), index=df.index)

                col_fn = next((c for c in df.columns if "firstname" in c), "")
                col_ln = next((c for c in df.columns if "lastname" in c), "")
                col_nr = next((c for c in df.columns if "shirtnumber" in c or "jerseynumber" in c), "")
                col_id = next((c for c in df.columns if "personid" in c or "seasonplayer.id" in c), "")

                if col_fn and col_ln:
                    df["NAME_FULL"] = (df[col_fn].astype(str) + " " + df[col_ln].astype(str)).str.strip()
                else: df["NAME_FULL"] = "Unknown"
                
                df["NR"] = df[col_nr].astype(str).str.replace(".0","",regex=False) if col_nr else "-"
                df["PLAYER_ID"] = df[col_id].astype(str).str.replace(".0","",regex=False) if col_id else "0"
                
                df["GP"] = get_val("gamesplayed").replace(0, 1)
                sec = get_val("secondsplayed")
                if sec.sum() > 0: df["MIN_FINAL"] = sec / df["GP"]
                else: df["MIN_FINAL"] = get_val("minutespergame")
                df["MIN_DISPLAY"] = df["MIN_FINAL"].apply(format_minutes)

                # Stats
                df["PPG"] = get_val("pointspergame"); df["TOT"] = get_val("totalreboundspergame")
                df["AS"] = get_val("assistspergame"); df["TO"] = get_val("turnoverspergame")
                df["ST"] = get_val("stealspergame"); df["BS"] = get_val("blockspergame")
                df["PF"] = get_val("foulscommittedpergame")
                
                # Shooting Made/Attempted
                df["2M"] = get_val("twopointshotsmade"); df["2A"] = get_val("twopointshotsattempted")
                df["3M"] = get_val("threepointshotsmade"); df["3A"] = get_val("threepointshotsattempted")
                df["FTM"] = get_val("freethrowsmade"); df["FTA"] = get_val("freethrowsattempted")

                # FG% berechnen
                att = df["2A"] + df["3A"]
                made = df["2M"] + df["3M"]
                df["FG%"] = 0.0
                mask = att > 0
                df.loc[mask, "FG%"] = (made[mask] / att[mask] * 100).round(1)

                df["3PCT"] = get_pct("threepointshotsuccess")
                df["FTPCT"] = get_pct("freethrowssuccess")
                
                df["OR"] = get_val("offensivereboundspergame"); df["DR"] = get_val("defensivereboundspergame")
                df["select"] = False
    except Exception as e:
        print(f"Error Player Stats ({base_url}): {e}")

    # 2. TEAM STATS LADEN ODER BERECHNEN
    try:
        r_team = requests.get(api_team_direct, headers=API_HEADERS, timeout=3)
        if r_team.status_code == 200:
            data = r_team.json()
            td = data[0] if isinstance(data, list) and data else data
            if isinstance(td, dict):
                ts = {
                    "ppg": td.get("pointsPerGame", 0), "tot": td.get("totalReboundsPerGame", 0),
                    "as": td.get("assistsPerGame", 0), "to": td.get("turnoversPerGame", 0),
                    "st": td.get("stealsPerGame", 0), "bs": td.get("blocksPerGame", 0),
                    "pf": td.get("foulsCommittedPerGame", 0), "fgpct": td.get("fieldGoalsSuccessPercent", 0),
                    "3pct": td.get("threePointShotsSuccessPercent", 0), "ftpct": td.get("freeThrowsSuccessPercent", 0),
                    "or": td.get("offensiveReboundsPerGame", 0), "dr": td.get("defensiveReboundsPerGame", 0)
                }
    except: pass

    # FALLBACK: Wenn Team Stats API leer, aber Spieler da -> Summiere Spieler!
    if not ts and not df.empty:
        total_gp = df["GP"].max() if not df.empty else 1
        
        # Absolute Summen pro Spiel berechnen
        sum_2m = (df["2M"] * df["GP"]).sum() / total_gp
        sum_2a = (df["2A"] * df["GP"]).sum() / total_gp
        sum_3m = (df["3M"] * df["GP"]).sum() / total_gp
        sum_3a = (df["3A"] * df["GP"]).sum() / total_gp
        sum_ftm = (df["FTM"] * df["GP"]).sum() / total_gp
        sum_fta = (df["FTA"] * df["GP"]).sum() / total_gp

        # Prozente korrekt aus Summen berechnen
        fgpct = (sum_2m + sum_3m) / (sum_2a + sum_3a) * 100 if (sum_2a + sum_3a) > 0 else 0
        pct3 = sum_3m / sum_3a * 100 if sum_3a > 0 else 0
        ftpct = sum_ftm / sum_fta * 100 if sum_fta > 0 else 0

        ts = {
            "ppg": df["PPG"].sum(), "tot": df["TOT"].sum(), "as": df["AS"].sum(),
            "to": df["TO"].sum(), "st": df["ST"].sum(), "bs": df["BS"].sum(),
            "pf": df["PF"].sum(), "or": df["OR"].sum(), "dr": df["DR"].sum(),
            "fgpct": fgpct, "3pct": pct3, "ftpct": ftpct
        }

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
                    
                    # Vermeidung von Duplikaten
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
