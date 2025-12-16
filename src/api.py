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

# --- CACHED API CALLS ---

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
    # Probiert alle Server durch, um den Kader zu finden
    urls = [
        f"https://api-1.dbbl.scb.world/teams/{team_id}/{season_id}",
        f"{get_base_url(team_id)}/teams/{team_id}/{season_id}",
        f"https://api-s.dbbl.scb.world/teams/{team_id}/{season_id}",
        f"https://api-n.dbbl.scb.world/teams/{team_id}/{season_id}"
    ]
    for url in urls:
        try:
            resp = requests.get(url, headers=API_HEADERS, timeout=2)
            if resp.status_code == 200: return resp.json()
        except: pass
    return None

# --- HAUPTFUNKTION (KEIN CACHE!) ---
def fetch_team_data(team_id, season_id):
    base_url = get_base_url(team_id)
    
    api_stats_players = f"{base_url}/teams/{team_id}/{season_id}/player-stats"
    api_team_direct = f"{base_url}/teams/{team_id}/{season_id}/statistics/season"
    
    ts = {}
    df = pd.DataFrame()

    # 1. TEAM STATS LADEN (MIT ID-FILTER!)
    try:
        r_team = requests.get(api_team_direct, headers=API_HEADERS, timeout=3)
        if r_team.status_code == 200:
            data = r_team.json()
            
            # WICHTIGER FIX: Wir suchen das richtige Team aus der Liste!
            td = None
            if isinstance(data, list):
                for item in data:
                    # Prüfe verschiedene Stellen wo die ID stehen könnte
                    check_id = str(item.get("teamId", ""))
                    check_season_id = str(item.get("seasonTeam", {}).get("teamId", ""))
                    
                    if str(team_id) == check_id or str(team_id) == check_season_id:
                        td = item
                        break
                # Fallback: Wenn nicht gefunden, nimm das erste (besser als nichts)
                if not td and data: td = data[0]
            else:
                td = data
            
            if isinstance(td, dict):
                gp = td.get("gamesPlayed") or 1
                if gp == 0: gp = 1
                
                fgm = td.get("fieldGoalsMade") or 0; fga = td.get("fieldGoalsAttempted") or 0
                m3 = td.get("threePointShotsMade") or 0; a3 = td.get("threePointShotsAttempted") or 0
                ftm = td.get("freeThrowsMade") or 0; fta = td.get("freeThrowsAttempted") or 0
                m2 = fgm - m3; a2 = fga - a3

                ts = {
                    "ppg": (td.get("points") or 0) / gp, "tot": (td.get("totalRebounds") or 0) / gp,
                    "as": (td.get("assists") or 0) / gp, "to": (td.get("turnovers") or 0) / gp,
                    "st": (td.get("steals") or 0) / gp, "bs": (td.get("blocks") or 0) / gp,
                    "pf": (td.get("foulsCommitted") or 0) / gp, "or": (td.get("offensiveRebounds") or 0) / gp,
                    "dr": (td.get("defensiveRebounds") or 0) / gp,
                    
                    "2m": m2 / gp, "2a": a2 / gp, "3m": m3 / gp, "3a": a3 / gp, "ftm": ftm / gp, "fta": fta / gp,
                    "fgpct": (fgm / fga * 100) if fga > 0 else 0,
                    "2pct": (m2 / a2 * 100) if a2 > 0 else 0,
                    "3pct": (m3 / a3 * 100) if a3 > 0 else 0,
                    "ftpct": (ftm / fta * 100) if fta > 0 else 0,
                }
    except Exception as e:
        print(f"Fehler Team Stats: {e}")

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
                    roster_lookup[pid] = {
                        "birthdate": bdate, "nationality": nat, "height": p.get("height", "-")
                    }
        
        r_stats = requests.get(api_stats_players, headers=API_HEADERS, timeout=4)
        if r_stats.status_code == 200:
            raw_p = r_stats.json()
            p_list = raw_p if isinstance(raw_p, list) else raw_p.get("data", [])
            
            if p_list:
                df = pd.json_normalize(p_list)
                df.columns = [str(c).lower() for c in df.columns]
                
                def get_val(key, default=0.0):
                    matches = [c for c in df.columns if key == c or (key in c and 'pergame' not in c and 'percent' not in c)]
                    if matches:
                        c = sorted(matches, key=len)[0]
                        return pd.to_numeric(df[c], errors="coerce").fillna(default)
                    return pd.Series([default]*len(df), index=df.index)

                col_fn = next((c for c in df.columns if "firstname" in c), None)
                col_ln = next((c for c in df.columns if "lastname" in c), None)
                col_nr = next((c for c in df.columns if "shirtnumber" in c or "jerseynumber" in c), None)
                col_id = next((c for c in df.columns if "personid" in c or "seasonplayer.id" in c), None)

                df["NAME_FULL"] = (df[col_fn].astype(str) + " " + df[col_ln].astype(str)).str.strip() if col_fn and col_ln else "Unknown"
                df["NR"] = df[col_nr].astype(str).str.replace(".0","",regex=False) if col_nr else "-"
                df["PLAYER_ID"] = df[col_id].astype(str).str.replace(".0","",regex=False) if col_id else "0"
                
                def get_meta(pid, field):
                    val = roster_lookup.get(pid, {}).get(field)
                    if val and val != "-": return val
                    meta = get_player_metadata_cached(pid)
                    if field == "birthdate": return None 
                    return meta.get(field, "-")
                
                df["AGE"] = df["PLAYER_ID"].apply(lambda pid: calculate_age(roster_lookup.get(pid, {}).get("birthdate")))
                mask_no_age = df["AGE"] == "-"
                if mask_no_age.any():
                    df.loc[mask_no_age, "AGE"] = df.loc[mask_no_age, "PLAYER_ID"].apply(lambda pid: get_player_metadata_cached(pid).get("age", "-"))

                df["NATIONALITY"] = df["PLAYER_ID"].apply(lambda pid: get_meta(pid, "nationality"))
                df["HEIGHT_ROSTER"] = df["PLAYER_ID"].apply(lambda pid: get_meta(pid, "height"))
                
                df["GP"] = get_val("gamesplayed").replace(0, 1)
                df["TOTAL_MINUTES"] = get_val("secondsplayed") / 60
                
                df["TOTAL_PTS"] = get_val("points"); df["TOTAL_REB"] = get_val("totalrebounds")
                df["TOTAL_AST"] = get_val("assists"); df["TOTAL_STL"] = get_val("steals")
                df["TOTAL_TO"] = get_val("turnovers"); df["TOTAL_BLK"] = get_val("blocks")
                df["TOTAL_PF"] = get_val("foulscommitted"); df["TOTAL_OR"] = get_val("offensiverebounds")
                df["TOTAL_DR"] = get_val("defensiverebounds"); df["TOTAL_FGM"] = get_val("fieldgoalsmade")
                df["TOTAL_FGA"] = get_val("fieldgoalsattempted"); df["TOTAL_3M"] = get_val("threepointshotsmade")
                df["TOTAL_3A"] = get_val("threepointshotsattempted"); df["TOTAL_FTM"] = get_val("freethrowsmade")
                df["TOTAL_FTA"] = get_val("freethrowsattempted"); df["TOTAL_2M"] = df["TOTAL_FGM"] - df["TOTAL_3M"]
                df["TOTAL_2A"] = df["TOTAL_FGA"] - df["TOTAL_3A"]
                
                gp_safe = df["GP"].replace(0, 1)
                df["MIN_DISPLAY"] = (df["TOTAL_MINUTES"] * 60 / gp_safe).apply(format_minutes)
                df["PPG"] = (df["TOTAL_PTS"] / gp_safe).round(1); df["TOT"] = (df["TOTAL_REB"] / gp_safe).round(1)
                df["AS"] = (df["TOTAL_AST"] / gp_safe).round(1); df["ST"] = (df["TOTAL_STL"] / gp_safe).round(1)
                df["TO"] = (df["TOTAL_TO"] / gp_safe).round(1); df["BS"] = (df["TOTAL_BLK"] / gp_safe).round(1)
                df["PF"] = (df["TOTAL_PF"] / gp_safe).round(1); df["OR"] = (df["TOTAL_OR"] / gp_safe).round(1)
                df["DR"] = (df["TOTAL_DR"] / gp_safe).round(1); df["2M"] = (df["TOTAL_2M"] / gp_safe).round(1)
                df["2A"] = (df["TOTAL_2A"] / gp_safe).round(1); df["3M"] = (df["TOTAL_3M"] / gp_safe).round(1)
                df["3A"] = (df["TOTAL_3A"] / gp_safe).round(1); df["FTM"] = (df["TOTAL_FTM"] / gp_safe).round(1)
                df["FTA"] = (df["TOTAL_FTA"] / gp_safe).round(1)

                df["FG%"] = (df["TOTAL_FGM"] / df["TOTAL_FGA"] * 100).round(1).fillna(0)
                df["3PCT"] = (df["TOTAL_3M"] / df["TOTAL_3A"] * 100).round(1).fillna(0)
                df["FTPCT"] = (df["TOTAL_FTM"] / df["TOTAL_FTA"] * 100).round(1).fillna(0)
                
                df["2PCT"] = 0.0
                mask2 = df["TOTAL_2A"] > 0
                df.loc[mask2, "2PCT"] = (df.loc[mask2, "TOTAL_2M"] / df.loc[mask2, "TOTAL_2A"] * 100).round(1)

                df["select"] = False

    except Exception as e:
        print(f"Error Player Stats ({base_url}): {e}")

    # Fallback Berechnung, wenn Team Stats API leer
    if not ts and not df.empty:
        tg = df["GP"].max() if not df.empty else 1
        if tg == 0: tg = 1

        t_fgm = df["TOTAL_FGM"].sum(); t_fga = df["TOTAL_FGA"].sum()
        t_3m = df["TOTAL_3M"].sum(); t_3a = df["TOTAL_3A"].sum()
        t_ftm = df["TOTAL_FTM"].sum(); t_fta = df["TOTAL_FTA"].sum()
        t_2m = t_fgm - t_3m; t_2a = t_fga - t_3a

        ts = {
            "ppg": df["TOTAL_PTS"].sum()/tg, "tot": df["TOTAL_REB"].sum()/tg,
            "as": df["TOTAL_AST"].sum()/tg, "st": df["TOTAL_STL"].sum()/tg,
            "to": df["TOTAL_TO"].sum()/tg, "bs": df["TOTAL_BLK"].sum()/tg,
            "pf": df["TOTAL_PF"].sum()/tg, "or": df["TOTAL_OR"].sum()/tg,
            "dr": df["TOTAL_DR"].sum()/tg,
            "2m": t_2m/tg, "2a": t_2a/tg, "3m": t_3m/tg, "3a": t_3a/tg, "ftm": t_ftm/tg, "fta": t_fta/tg,
            "fgpct": (t_fgm/t_fga*100) if t_fga>0 else 0,
            "2pct": (t_2m/t_2a*100) if t_2a>0 else 0,
            "3pct": (t_3m/t_3a*100) if t_3a>0 else 0,
            "ftpct": (t_ftm/t_fta*100) if t_fta>0 else 0,
        }

    # SAFETY: Spalten auffüllen
    if df is not None and not df.empty:
        required = ["2M", "2A", "2PCT", "3M", "3A", "3PCT", "FTM", "FTA", "FTPCT", 
                    "DR", "OR", "TOT", "AS", "TO", "ST", "PF", "BS", "PPG", "MIN_DISPLAY"]
        for c in required:
            if c not in df.columns: df[c] = 0

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
