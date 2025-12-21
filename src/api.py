# --- START OF FILE src/api.py ---
import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import pytz
from src.config import API_HEADERS, SEASON_ID, TEAMS_DB

# --- HILFSFUNKTIONEN ---
def get_base_url(team_id):
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
        return str(today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day)))
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

@st.cache_data(ttl=3600, show_spinner=False)
def get_player_metadata_cached(player_id):
    clean_id = str(player_id).replace(".0", "")
    for subdomain in ["api-s", "api-n"]:
        url = f"https://{subdomain}.dbbl.scb.world/season-players/{clean_id}"
        try:
            resp = requests.get(url, headers=API_HEADERS, timeout=1.5)
            if resp.status_code == 200:
                data = resp.json(); person = data.get("person", {})
                bdate = data.get("birthDate") or person.get("birthDate") or person.get("birthdate")
                nat = extract_nationality(data)
                if nat == "-": nat = extract_nationality(person)
                return {"img": data.get("imageUrl", ""), "height": data.get("height") or person.get("height", "-"), "pos": data.get("position", "-"), "age": calculate_age(bdate), "nationality": nat}
        except: pass
    return {"img": "", "height": "-", "pos": "-", "age": "-", "nationality": "-"}

@st.cache_data(ttl=600)
def fetch_team_details_raw(team_id, season_id):
    urls = [f"{get_base_url(team_id)}/teams/{team_id}/{season_id}"]
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
            td = r_team.json()
            if isinstance(td, list): td = td[0] if td else {}
            if td.get("gamesPlayed"):
                gp = td.get("gamesPlayed") or 1
                ts = {"ppg": (td.get("points") or 0)/gp, "tot": (td.get("totalRebounds") or 0)/gp, "as": (td.get("assists") or 0)/gp, "to": (td.get("turnovers") or 0)/gp, "st": (td.get("steals") or 0)/gp, "bs": (td.get("blocks") or 0)/gp, "pf": (td.get("foulsCommitted") or 0)/gp, "or": (td.get("offensiveRebounds") or 0)/gp, "dr": (td.get("defensiveRebounds") or 0)/gp, "fgpct": ((td.get("fieldGoalsMade") or 0)/(td.get("fieldGoalsAttempted") or 1)*100), "3pct": ((td.get("threePointShotsMade") or 0)/(td.get("threePointShotsAttempted") or 1)*100), "ftpct": ((td.get("freeThrowsMade") or 0)/(td.get("freeThrowsAttempted") or 1)*100)}
    except: pass
    try:
        r_stats = requests.get(api_stats_players, headers=API_HEADERS, timeout=4)
        if r_stats.status_code == 200:
            p_list = r_stats.json(); df = pd.json_normalize(p_list if isinstance(p_list, list) else p_list.get("data", []))
            df.columns = [str(c).lower() for c in df.columns]
            df["NAME_FULL"] = (df.get("seasonplayer.firstname", "") + " " + df.get("seasonplayer.lastname", "")).str.strip()
            df["NR"] = df.get("seasonplayer.shirtnumber", "-").astype(str).str.replace(".0","")
            df["PLAYER_ID"] = df.get("seasonplayer.id", "0").astype(str).str.replace(".0","")
            df["GP"] = pd.to_numeric(df.get("gamesplayed", 1)).replace(0,1)
            df["PPG"] = (pd.to_numeric(df.get("points", 0)) / df["GP"]).round(1)
            df["FG%"] = pd.to_numeric(df.get("fieldgoalssuccesspercent", 0)).round(1)
            df["3PCT"] = pd.to_numeric(df.get("threepointshotsuccesspercent", 0)).round(1)
            df["FTPCT"] = pd.to_numeric(df.get("freethrowssuccesspercent", 0)).round(1)
            df["TOT"] = (pd.to_numeric(df.get("totalrebounds", 0)) / df["GP"]).round(1)
            df["AS"] = (pd.to_numeric(df.get("assists", 0)) / df["GP"]).round(1)
            df["ST"] = (pd.to_numeric(df.get("steals", 0)) / df["GP"]).round(1)
            df["TO"] = (pd.to_numeric(df.get("turnovers", 0)) / df["GP"]).round(1)
            df["BS"] = (pd.to_numeric(df.get("blocks", 0)) / df["GP"]).round(1)
            df["PF"] = (pd.to_numeric(df.get("foulscommitted", 0)) / df["GP"]).round(1)
            df["MIN_DISPLAY"] = (pd.to_numeric(df.get("secondsplayed", 0)) / df["GP"]).apply(format_minutes)
            df["select"] = False
    except: pass
    return df, ts

@st.cache_data(ttl=300)
def fetch_schedule(team_id, season_id):
    url = f"{get_base_url(team_id)}/games?seasonTeamId={team_id}&pageSize=100&seasonId={season_id}"
    try:
        r = requests.get(url, headers=API_HEADERS, timeout=3)
        if r.status_code == 200:
            items = r.json().get("items", [])
            return [{"id": g.get("id"), "date": datetime.fromisoformat(g["scheduledTime"].replace("Z", "+00:00")).astimezone(pytz.timezone("Europe/Berlin")).strftime("%d.%m.%Y %H:%M") if g.get("scheduledTime") else "-", "score": f"{g.get('result',{}).get('homeScore','?')}:{g.get('result',{}).get('guestScore','?')}", "home": g.get("homeTeam",{}).get("name","?"), "guest": g.get("guestTeam",{}).get("name","?"), "homeTeamId": str(g.get("homeTeam",{}).get("teamId")), "guestTeamId": str(g.get("guestTeam",{}).get("teamId")), "home_score": g.get("result",{}).get("homeScore"), "guest_score": g.get("result",{}).get("guestScore"), "has_result": g.get("status")=="ENDED"} for g in items]
    except: pass
    return []

@st.cache_data(ttl=10)
def fetch_game_boxscore(game_id):
    for s in ["api-s", "api-n"]:
        try:
            r = requests.get(f"https://{s}.dbbl.scb.world/games/{game_id}/stats", headers=API_HEADERS, timeout=2)
            if r.status_code == 200: return r.json()
        except: pass
    return None

@st.cache_data(ttl=10)
def fetch_game_details(game_id):
    for s in ["api-s", "api-n"]:
        try:
            r = requests.get(f"https://{s}.dbbl.scb.world/games/{game_id}", headers=API_HEADERS, timeout=2)
            if r.status_code == 200: return r.json()
        except: pass
    return None

@st.cache_data(ttl=3600)
def fetch_team_info_basic(team_id):
    try:
        r = requests.get(f"{get_base_url(team_id)}/teams/{team_id}", headers=API_HEADERS, timeout=3)
        if r.status_code == 200:
            v = r.json().get("venues", []); main = next((x for x in v if x.get("isMain")), v[0] if v else None)
            return {"id": team_id, "venue": main}
    except: pass
    return {"id": team_id, "venue": None}

@st.cache_data(ttl=600)
def fetch_season_games(season_id):
    all = []
    for s in ["api-s", "api-n"]:
        try:
            r = requests.get(f"https://{s}.dbbl.scb.world/games?seasonId={season_id}&pageSize=1000", headers=API_HEADERS, timeout=4)
            if r.status_code == 200:
                for g in r.json().get("items", []):
                    dt = datetime.fromisoformat(g["scheduledTime"].replace("Z", "+00:00")).astimezone(pytz.timezone("Europe/Berlin")) if g.get("scheduledTime") else None
                    all.append({"id": g.get("id"), "date": dt.strftime("%d.%m.%Y %H:%M") if dt else "-", "date_only": dt.strftime("%d.%m.%Y") if dt else "-", "home": g.get("homeTeam",{}).get("name","?"), "guest": g.get("guestTeam",{}).get("name","?"), "score": f"{g.get('result',{}).get('homeScore',0)}:{g.get('result',{}).get('guestScore',0)}" if g.get("status")=="ENDED" else "-:-", "status": g.get("status")})
        except: pass
    return all

@st.cache_data(ttl=1800)
def fetch_team_rank(team_id, season_id):
    staffel = TEAMS_DB.get(int(team_id), {}).get("staffel", "")
    grp = "SOUTH" if staffel == "Süd" else "NORTH"
    for s in ["api-s", "api-n"]:
        try:
            r = requests.get(f"https://{s}.dbbl.scb.world/standings?seasonId={season_id}&group={grp}", headers=API_HEADERS, timeout=3)
            if r.status_code == 200:
                for e in r.json():
                    if str(e.get("seasonTeam",{}).get("teamId")) == str(team_id):
                        return {"rank": e.get("rank"), "totalGames": e.get("totalGames"), "totalVictories": e.get("totalVictories"), "totalLosses": e.get("totalLosses"), "last10Victories": e.get("last10Victories"), "last10Losses": e.get("last10Losses")}
        except: pass
    return None

@st.cache_data(ttl=1800)
def fetch_league_standings(season_id, league_selection):
    grp = "NORTH" if league_selection == "Nord" else ("SOUTH" if league_selection == "Süd" else "")
    for s in ["api-s", "api-n"]:
        try:
            r = requests.get(f"https://{s}.dbbl.scb.world/standings?seasonId={season_id}&group={grp}", headers=API_HEADERS, timeout=3)
            if r.status_code == 200:
                return pd.DataFrame([{"Platz": e.get("rank"), "Team": e.get("seasonTeam",{}).get("name"), "W": e.get("totalVictories"), "L": e.get("totalLosses")} for e in r.json()]).sort_values("Platz")
        except: pass
    return pd.DataFrame()

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
                                    dt_obj = datetime.fromisoformat(raw_d.replace("Z", "+00:00"))
                                    dt_berlin = dt_obj.astimezone(pytz.timezone("Europe/Berlin"))
                                    d_disp = dt_berlin.strftime("%d.%m.%Y %H:%M")
                                    date_only = dt_berlin.strftime("%d.%m.%Y")
                                except: pass
                            res = g.get("result") or {}
                            h_s = res.get("homeScore") or res.get("homeTeamFinalScore")
                            g_s = res.get("guestScore") or res.get("guestTeamFinalScore")
                            all_games.append({"id": game_id, "date": d_disp, "date_only": date_only, "home": g.get("homeTeam", {}).get("name", "Heim"), "guest": g.get("guestTeam", {}).get("name", "Gast"), "score": f"{h_s}:{g_s}" if h_s is not None else "-:-", "status": g.get("status")})
        except: continue
    return all_games
