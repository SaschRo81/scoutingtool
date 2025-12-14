# --- START OF FILE src/api.py ---

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
    if not birthdate_str or str(birthdate_str).lower() == "nan": return "-"
    try:
        clean_date = str(birthdate_str).split("T")[0]
        bd = datetime.strptime(clean_date, "%Y-%m-%d")
        today = datetime.now()
        return today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
    except:
        return "-"

@st.cache_data(ttl=600)
def fetch_team_details_raw(team_id, season_id):
    """Lädt Stammdaten (Alter, Nat) vom detaillierten Team-Endpunkt."""
    url = f"https://api-1.dbbl.scb.world/teams/{team_id}/{season_id}"
    try:
        resp = requests.get(url, headers=API_HEADERS)
        if resp.status_code == 200: return resp.json()
    except: pass
    return None

@st.cache_data(ttl=600)
def fetch_team_data(team_id, season_id):
    """Lädt Kader (Stats + Stammdaten)."""
    api_stats = f"https://api-s.dbbl.scb.world/teams/{team_id}/{season_id}/player-stats"
    api_team = f"https://api-s.dbbl.scb.world/seasons/{season_id}/team-statistics?displayType=MAIN_ROUND&teamId={team_id}"
    
    # Stammdaten Lookup erstellen
    raw_details = fetch_team_details_raw(team_id, season_id)
    roster_lookup = {}
    if raw_details:
        squad = raw_details.get("squad", []) if isinstance(raw_details, dict) else []
        for entry in squad:
            p = entry.get("person", {})
            pid = str(p.get("id", ""))
            if pid:
                nat = p.get("nationality", {}).get("name") or entry.get("nationality", {}).get("name", "-")
                roster_lookup[pid] = {
                    "birthdate": p.get("birthdate", ""),
                    "nationality": nat,
                    "height": p.get("height", "-")
                }

    try:
        r_stats = requests.get(api_stats, headers=API_HEADERS)
        r_team = requests.get(api_team, headers=API_HEADERS)
        
        if r_stats.status_code != 200: return None, None
        
        # Team Stats
        ts = {}
        if r_team.status_code == 200:
            raw_ts = r_team.json()
            if raw_ts and isinstance(raw_ts, list):
                td = raw_ts[0]
                ts = {
                    "ppg": td.get("pointsPerGame", 0), "tot": td.get("totalReboundsPerGame", 0),
                    "as": td.get("assistsPerGame", 0), "to": td.get("turnoversPerGame", 0),
                    "st": td.get("stealsPerGame", 0), "bs": td.get("blocksPerGame", 0),
                    "pf": td.get("foulsCommittedPerGame", 0),
                    "2m": td.get("twoPointShotsMadePerGame", 0), "2a": td.get("twoPointShotsAttemptedPerGame", 0), "2pct": td.get("twoPointShotsSuccessPercent", 0),
                    "3m": td.get("threePointShotsMadePerGame", 0), "3a": td.get("threePointShotsAttemptedPerGame", 0), "3pct": td.get("threePointShotsSuccessPercent", 0),
                    "ftm": td.get("freeThrowsMadePerGame", 0), "fta": td.get("freeThrowsAttemptedPerGame", 0), "ftpct": td.get("freeThrowsSuccessPercent", 0),
                    "dr": td.get("defensiveReboundsPerGame", 0), "or": td.get("offensiveReboundsPerGame", 0)
                }

        # Player DataFrame
        df = None
        raw_p = r_stats.json()
        p_list = raw_p if isinstance(raw_p, list) else raw_p.get("data", [])
        
        if p_list:
            df = pd.json_normalize(p_list)
            df.columns = [str(c).lower() for c in df.columns]
            
            # Mapping
            col_map = {
                "firstname": ["seasonplayer.person.firstname", "person.firstname", "firstname"], 
                "lastname": ["seasonplayer.person.lastname", "person.lastname", "lastname"],
                "shirtnumber": ["seasonplayer.shirtnumber", "jerseynumber", "shirtnumber", "no"], 
                "id": ["seasonplayer.personid", "seasonplayer.id", "playerid", "person.id", "id"]
            }
            final_cols = {}
            for target, opts in col_map.items():
                for opt in opts:
                    # Suche Spalte die den Namen enthält
                    matches = [c for c in df.columns if opt in c]
                    if matches:
                        final_cols[target] = sorted(matches, key=len)[0]
                        break
            
            # Safe Accessors
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
            
            # Merge Stammdaten
            df["BIRTHDATE"] = df["PLAYER_ID"].apply(lambda x: roster_lookup.get(x, {}).get("birthdate", ""))
            df["NATIONALITY"] = df["PLAYER_ID"].apply(lambda x: roster_lookup.get(x, {}).get("nationality", "-"))
            df["HEIGHT_ROSTER"] = df["PLAYER_ID"].apply(lambda x: roster_lookup.get(x, {}).get("height", "-"))
            df["AGE"] = df["BIRTHDATE"].apply(calculate_age)
            
            # Stats
            df["GP"] = get_n("gamesplayed").replace(0,1)
            min_raw = get_n("minutespergame"); sec_total = get_n("secondsplayed")
            df["MIN_FINAL"] = min_raw
            mask_zero = (df["MIN_FINAL"] <= 0) & (df["GP"] > 0)
            if not df.loc[mask_zero].empty:
                # Suche nach secondsplayed Spalte
                sec_cols = [c for c in df.columns if "secondsplayed" in c]
                if sec_cols:
                    sec_series = pd.to_numeric(df[sec_cols[0]], errors="coerce").fillna(0)
                    df.loc[mask_zero, "MIN_FINAL"] = sec_series[mask_zero] / df.loc[mask_zero, "GP"]
            
            df["MIN_DISPLAY"] = df["MIN_FINAL"].apply(format_minutes)
            df["PPG"] = get_n("pointspergame")
            df["TOT"] = get_n("totalreboundspergame")
            df["AS"] = get_n("assistspergame")
            df["TO"] = get_n("turnoverspergame")
            df["ST"] = get_n("stealspergame")
            df["BS"] = get_n("blockspergame")
            df["PF"] = get_n("foulscommittedpergame")
            
            m2 = get_n("twopointshotsmadepergame"); a2 = get_n("twopointshotsattemptedpergame")
            m3 = get_n("threepointshotsmadepergame"); a3 = get_n("threepointshotsattemptedpergame")
            
            df["FG%"] = ((m2+m3)/(a2+a3)*100).fillna(0).round(1)
            df["3PCT"] = get_n("threepointshotsuccesspercent").apply(lambda x: round(x*100, 1))
            df["FTPCT"] = get_n("freethrowssuccesspercent").apply(lambda x: round(x*100, 1))
            
            df["select"] = False
        else:
            df = pd.DataFrame()
            
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
            clean = []
            for g in items:
                res = g.get("result")
                score = "-"
                has_res = False
                if res and isinstance(res, dict):
                    h = res.get('homeTeamFinalScore'); v = res.get('guestTeamFinalScore')
                    if h is not None and v is not None:
                        score = f"{h} : {v}"; has_res = True
                
                raw_d = g.get("scheduledTime", "")
                d_disp = raw_d
                if raw_d:
                    try: d_disp = datetime.fromisoformat(raw_d.replace("Z", "+00:00")).astimezone(pytz.timezone("Europe/Berlin")).strftime("%Y-%m-%d %H:%M")
                    except: pass
                
                clean.append({
                    "id": g.get("id"), "date": d_disp, "score": score, "has_result": has_res,
                    "home": g.get("homeTeam", {}).get("name", "?"), "guest": g.get("guestTeam", {}).get("name", "?"),
                    "homeTeamId": str(g.get("homeTeam", {}).get("teamId")), 
                    "guestTeamId": str(g.get("guestTeam", {}).get("teamId")) 
                })
            return clean
    except: pass
    return []

@st.cache_data(ttl=10)
def fetch_game_boxscore(game_id):
    try:
        return requests.get(f"https://api-s.dbbl.scb.world/games/{game_id}/stats", headers=API_HEADERS).json()
    except: return None

@st.cache_data(ttl=10)
def fetch_game_details(game_id):
    try:
        return requests.get(f"https://api-s.dbbl.scb.world/games/{game_id}", headers=API_HEADERS).json()
    except: return None

@st.cache_data(ttl=3600) 
def fetch_team_info_basic(team_id):
    # 1. Direkt
    try:
        resp = requests.get(f"https://api-s.dbbl.scb.world/teams/{team_id}", headers=API_HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            venues = data.get("venues", [])
            main = next((v for v in venues if v.get("isMain")), venues[0] if venues else None)
            if main: return {"id": team_id, "venue": main}
    except: pass
    # 2. Fallback
    sched = fetch_schedule(team_id, SEASON_ID)
    if sched:
        homes = [g for g in sched if str(g.get("homeTeamId")) == str(team_id)]
        homes.sort(key=lambda x: x['date'], reverse=True)
        for g in homes:
            det = fetch_game_details(g['id'])
            if det and det.get("venue"): return {"id": team_id, "venue": det["venue"]}
    return {"id": team_id, "venue": None}
