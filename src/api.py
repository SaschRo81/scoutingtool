# --- START OF FILE src/api.py ---
import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import pytz
from src.config import API_HEADERS, SEASON_ID 
from src.utils import optimize_image_base64, format_minutes

def calculate_age(birthdate_str):
    if not birthdate_str or str(birthdate_str).lower() == "nan": return "-"
    try:
        clean_date = str(birthdate_str).split("T")[0]
        bd = datetime.strptime(clean_date, "%Y-%m-%d")
        today = datetime.now()
        return today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
    except: return "-"

@st.cache_data(ttl=600)
def fetch_team_details_raw(team_id, season_id):
    """Holt den detaillierten Kader (Fotos, Alter, Herkunft)."""
    url = f"https://api-1.dbbl.scb.world/teams/{team_id}/{season_id}"
    try:
        resp = requests.get(url, headers=API_HEADERS)
        if resp.status_code == 200: return resp.json()
    except: pass
    return None

@st.cache_data(ttl=600)
def fetch_team_data(team_id, season_id):
    """Kombiniert Statistiken mit Stammdaten."""
    api_stats = f"https://api-s.dbbl.scb.world/teams/{team_id}/{season_id}/player-stats"
    
    # 1. Stammdaten (api-1) laden
    raw_details = fetch_team_details_raw(team_id, season_id)
    roster_lookup = {}
    if raw_details:
        squad = raw_details.get("squad", [])
        for entry in squad:
            p = entry.get("person", {})
            pid = str(p.get("id", ""))
            if pid:
                roster_lookup[pid] = {
                    "birthdate": p.get("birthdate", ""),
                    "nationality": p.get("nationality", {}).get("name", "-"),
                    "imageUrl": p.get("imageUrl", ""),
                    "height": p.get("height", "-")
                }

    try:
        r_stats = requests.get(api_stats, headers=API_HEADERS)
        if r_stats.status_code != 200: return None, None
        
        # 2. Team Statistiken holen (für Team-Zeile)
        api_team = f"https://api-s.dbbl.scb.world/seasons/{season_id}/team-statistics?displayType=MAIN_ROUND&teamId={team_id}"
        r_team = requests.get(api_team, headers=API_HEADERS)
        ts = {}
        if r_team.status_code == 200:
            raw_ts = r_team.json()
            if raw_ts:
                td = raw_ts[0]
                ts = {"ppg": td.get("pointsPerGame", 0), "tot": td.get("totalReboundsPerGame", 0), "as": td.get("assistsPerGame", 0), "to": td.get("turnoversPerGame", 0), "st": td.get("stealsPerGame", 0), "bs": td.get("blocksPerGame", 0), "pf": td.get("foulsCommittedPerGame", 0)}

        # 3. Spieler DataFrame bauen
        raw_p = r_stats.json()
        p_list = raw_p if isinstance(raw_p, list) else raw_p.get("data", [])
        if not p_list: return pd.DataFrame(), ts
        
        df = pd.json_normalize(p_list)
        df.columns = [str(c).lower() for c in df.columns]

        # Spalten-Mapping (Suche nach Teilstrings)
        def find_col(key):
            matches = [c for c in df.columns if key in c]
            return sorted(matches, key=len)[0] if matches else None

        c_fn = find_col("firstname"); c_ln = find_col("lastname")
        c_nr = find_col("shirtnumber"); c_id = find_col("personid") or find_col(".id")

        df["PLAYER_ID"] = df[c_id].astype(str).str.replace(".0", "", regex=False) if c_id else ""
        df["NAME_FULL"] = (df[c_fn].fillna("") + " " + df[c_ln].fillna("")).str.strip()
        df["NR"] = df[c_nr].fillna("-").astype(str).str.replace(".0", "", regex=False)
        
        # Merge mit Stammdaten
        df["NATIONALITY"] = df["PLAYER_ID"].apply(lambda x: roster_lookup.get(x, {}).get("nationality", "-"))
        df["AGE"] = df["PLAYER_ID"].apply(lambda x: calculate_age(roster_lookup.get(x, {}).get("birthdate", "")))
        df["IMAGE_URL"] = df["PLAYER_ID"].apply(lambda x: roster_lookup.get(x, {}).get("imageUrl", ""))
        df["HEIGHT"] = df["PLAYER_ID"].apply(lambda x: roster_lookup.get(x, {}).get("height", "-"))

        # Numerische Werte
        def get_n(k):
            col = find_col(k)
            return pd.to_numeric(df[col], errors="coerce").fillna(0) if col else pd.Series([0.0]*len(df))

        df["PPG"] = get_n("pointspergame")
        df["TOT"] = get_n("totalreboundspergame")
        df["AS"] = get_n("assistspergame")
        df["FG%"] = get_n("fieldgoalssuccesspercent").round(1)
        df["3PCT"] = (get_n("threepointshotsuccesspercent") * 100).round(1)
        df["GP"] = get_n("gamesplayed").astype(int)
        
        return df, ts
    except: return None, None

@st.cache_data(ttl=300)
def fetch_schedule(team_id, season_id):
    url = f"https://api-s.dbbl.scb.world/games?currentPage=1&seasonTeamId={team_id}&pageSize=1000&gameType=all&seasonId={season_id}"
    try:
        resp = requests.get(url, headers=API_HEADERS)
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            clean = []
            for g in items:
                res = g.get("result")
                h_score = res.get('homeTeamFinalScore') if res else None
                g_score = res.get('guestTeamFinalScore') if res else None
                clean.append({
                    "id": g.get("id"),
                    "date": g.get("scheduledTime", ""),
                    "home": g.get("homeTeam", {}).get("name", "?"),
                    "guest": g.get("guestTeam", {}).get("name", "?"),
                    "home_score": h_score,
                    "guest_score": g_score,
                    "home_id": str(g.get("homeTeam", {}).get("teamId")),
                    "guest_id": str(g.get("guestTeam", {}).get("teamId")),
                    "has_result": h_score is not None
                })
            return clean
    except: pass
    return []

@st.cache_data(ttl=10)
def fetch_game_boxscore(game_id):
    try: return requests.get(f"https://api-s.dbbl.scb.world/games/{game_id}/stats", headers=API_HEADERS).json()
    except: return None

@st.cache_data(ttl=10)
def fetch_game_details(game_id):
    try: return requests.get(f"https://api-s.dbbl.scb.world/games/{game_id}", headers=API_HEADERS).json()
    except: return None

@st.cache_data(ttl=3600) 
def fetch_team_info_basic(team_id):
    try:
        data = requests.get(f"https://api-s.dbbl.scb.world/teams/{team_id}", headers=API_HEADERS).json()
        venues = data.get("venues", [])
        main = next((v for v in venues if v.get("isMain")), venues[0] if venues else None)
        return {"id": team_id, "venue": main}
    except: return {"id": team_id, "venue": None}
