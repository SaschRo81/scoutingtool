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
def fetch_team_details_raw(team_id, season_id):
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

def fetch_team_data(team_id, season_id):
    base_url = get_base_url(team_id)
    api_stats_players = f"{base_url}/teams/{team_id}/{season_id}/player-stats"
    api_team_direct = f"{base_url}/teams/{team_id}/{season_id}/statistics/season"
    ts = {}; df = pd.DataFrame()
    
    try:
        r_team = requests.get(api_team_direct, headers=API_HEADERS, timeout=3)
        if r_team.status_code == 200:
            data = r_team.json()
            td = data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else None)
            if isinstance(td, dict) and td.get("gamesPlayed"):
                gp = td.get("gamesPlayed") or 1
                ts = {
                    "ppg": (td.get("points") or 0) / gp, "tot": (td.get("totalRebounds") or 0) / gp,
                    "as": (td.get("assists") or 0) / gp, "to": (td.get("turnovers") or 0) / gp,
                    "st": (td.get("steals") or 0) / gp, "bs": (td.get("blocks") or 0) / gp,
                    "pf": (td.get("foulsCommitted") or 0) / gp,
                    "2pct": (td.get("twoPointShotsMade",0) / td.get("twoPointShotsAttempted",1) * 100),
                    "3pct": (td.get("threePointShotsMade",0) / td.get("threePointShotsAttempted",1) * 100),
                    "ftpct": (td.get("freeThrowsMade",0) / td.get("freeThrowsAttempted",1) * 100)
                }
    except: pass

    try:
        r_stats = requests.get(api_stats_players, headers=API_HEADERS, timeout=4)
        if r_stats.status_code == 200:
            p_list = r_stats.json()
            if isinstance(p_list, dict): p_list = p_list.get("data", [])
            if p_list:
                df = pd.json_normalize(p_list)
                df.columns = [str(c).lower() for c in df.columns]
                
                # Robust Spalten finden
                def find_c(sub):
                    matches = [c for c in df.columns if sub in c]
                    return sorted(matches, key=len)[0] if matches else None

                c_fn = find_c("firstname")
                c_ln = find_c("lastname")
                c_id = find_c("player.id") or find_c("personid") or find_c("id")
                c_nr = find_c("shirtnumber") or find_c("jerseynumber")

                df["NAME_FULL"] = (df[c_fn].astype(str) + " " + df[c_ln].astype(str)).str.strip() if c_fn and c_ln else "Unknown Player"
                df["PLAYER_ID"] = df[c_id].astype(str).str.replace(".0", "", regex=False) if c_id else "0"
                df["NR"] = df[c_nr].astype(str).str.replace(".0", "", regex=False) if c_nr else "-"
                
                df["GP"] = pd.to_numeric(df[find_c("gamesplayed") or "gamesplayed"], errors="coerce").fillna(1)
                df["PPG"] = (pd.to_numeric(df[find_c("points") or "points"], errors="coerce") / df["GP"].replace(0,1)).round(1)
                
                # Fehlende Stats für Vergleich auffüllen
                for col in ["TOT", "AS", "ST", "TO", "PF", "BS"]:
                    api_col = find_c(col.lower()) or col.lower()
                    if api_col in df.columns:
                        df[col] = (pd.to_numeric(df[api_col], errors="coerce") / df["GP"].replace(0,1)).round(1)
                    else: df[col] = 0.0

                df["FG%"] = (pd.to_numeric(df[find_c("fieldgoalssuccesspercent") or "fieldgoalssuccesspercent"], errors="coerce") * 100).round(1).fillna(0)
                df["3PCT"] = (pd.to_numeric(df[find_c("threepointshotsuccesspercent") or "threepointshotsuccesspercent"], errors="coerce") * 100).round(1).fillna(0)
                df["FTPCT"] = (pd.to_numeric(df[find_c("freethrowssuccesspercent") or "freethrowssuccesspercent"], errors="coerce") * 100).round(1).fillna(0)
                df["MIN_DISPLAY"] = "0:00" # Placeholder
                df["select"] = False
    except: pass
    return df, ts

@st.cache_data(ttl=300)
def fetch_schedule(team_id, season_id):
    urls = [f"https://api-s.dbbl.scb.world/games?currentPage=1&seasonTeamId={team_id}&pageSize=100&seasonId={season_id}"]
    for url in urls:
        try:
            resp = requests.get(url, headers=API_HEADERS, timeout=3)
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                clean = []
                for g in items:
                    raw_d = g.get("scheduledTime", "")
                    d_disp, date_only = "-", "-"
                    if raw_d:
                        dt = datetime.fromisoformat(raw_d.replace("Z", "+00:00")).astimezone(pytz.timezone("Europe/Berlin"))
                        d_disp = dt.strftime("%d.%m.%Y %H:%M"); date_only = dt.strftime("%d.%m.%Y")
                    res = g.get("result") or {}
                    h_s = res.get("homeTeamFinalScore")
                    g_s = res.get("guestTeamFinalScore")
                    clean.append({
                        "id": g.get("id"), "date": d_disp, "date_only": date_only, 
                        "home": g.get("homeTeam",{}).get("name"), "guest": g.get("guestTeam",{}).get("name"), 
                        "score": f"{h_s if h_s is not None else '-'}:{g_s if g_s is not None else '-'}", 
                        "has_result": h_s is not None, "homeTeamId": str(g.get("homeTeam", {}).get("teamId")), 
                        "guestTeamId": str(g.get("guestTeam", {}).get("teamId")),
                        "home_score": h_s, "guest_score": g_s
                    })
                return clean
        except: pass
    return []

@st.cache_data(ttl=10)
def fetch_game_boxscore(game_id):
    for sub in ["api-s", "api-n"]:
        try:
            r = requests.get(f"https://{sub}.dbbl.scb.world/games/{game_id}/stats", headers=API_HEADERS, timeout=2)
            if r.status_code == 200: return r.json()
        except: pass
    return None

@st.cache_data(ttl=10)
def fetch_game_details(game_id):
    for sub in ["api-s", "api-n"]:
        try:
            r = requests.get(f"https://{sub}.dbbl.scb.world/games/{game_id}", headers=API_HEADERS, timeout=2)
            if r.status_code == 200: return r.json()
        except: pass
    return None

@st.cache_data(ttl=3600)
def fetch_team_info_basic(team_id):
    base = get_base_url(team_id)
    try:
        resp = requests.get(f"{base}/teams/{team_id}", headers=API_HEADERS, timeout=3)
        if resp.status_code == 200:
            v = resp.json().get("venues", [])
            return {"id": team_id, "venue": v[0] if v else None}
    except: pass
    return {"id": team_id, "venue": None}

@st.cache_data(ttl=60)
def fetch_recent_games_combined():
    all_games = []
    for subdomain in ["api-s", "api-n"]:
        url = f"https://{subdomain}.dbbl.scb.world/games/recent?slotSize=200"
        try:
            resp = requests.get(url, headers=API_HEADERS, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                for slot in ["past", "present", "future"]:
                    if slot in data and isinstance(data[slot], list):
                        for g in data[slot]:
                            game_id = str(g.get("id"))
                            if any(x['id'] == game_id for x in all_games): continue
                            raw_d = g.get("scheduledTime", "")
                            d_disp, date_only = "-", "-"
                            if raw_d:
                                try:
                                    dt = datetime.fromisoformat(raw_d.replace("Z", "+00:00")).astimezone(pytz.timezone("Europe/Berlin"))
                                    d_disp = dt.strftime("%d.%m.%Y %H:%M"); date_only = dt.strftime("%d.%m.%Y")
                                except: pass
                            res = g.get("result") or {}
                            h_s = res.get("homeScore") if res.get("homeScore") is not None else res.get("homeTeamFinalScore")
                            g_s = res.get("guestScore") if res.get("guestScore") is not None else res.get("guestTeamFinalScore")
                            score = f"{h_s}:{g_s}" if h_s is not None else "-:-"
                            all_games.append({"id": game_id, "date": d_disp, "date_only": date_only, "home": g.get("homeTeam", {}).get("name", "Heim"), "guest": g.get("guestTeam", {}).get("name", "Gast"), "score": score, "status": g.get("status")})
        except: continue
    return all_games
