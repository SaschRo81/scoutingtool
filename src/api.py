# --- START OF FILE src/api.py ---

import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import pytz
from src.config import API_HEADERS, SEASON_ID 

# Lokale Hilfsfunktionen
def optimize_image_base64(url): return url 
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

@st.cache_data(ttl=600, show_spinner="Lade Spieler-Metadaten...")
def get_player_metadata_cached(player_id):
    try:
        clean_id = str(player_id).replace(".0", "")
        url = f"https://api-s.dbbl.scb.world/season-players/{clean_id}"
        resp = requests.get(url, headers=API_HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            person = data.get("person", {})
            
            def get_attr(keys, source):
                for k in keys:
                    val = source.get(k)
                    if val: return val
                return None

            img = data.get("imageUrl", "")
            bdate = get_attr(["birthDate", "birthdate"], person) or get_attr(["birthDate", "birthdate"], data)
            age = calculate_age(bdate)
            nat = "-"
            nats = get_attr(["nationalities"], person) or get_attr(["nationalities"], data)
            if nats and isinstance(nats, list): nat = ", ".join(nats)
            else:
                n_obj = get_attr(["nationality"], person) or get_attr(["nationality"], data)
                if n_obj and isinstance(n_obj, dict): nat = n_obj.get("name", "-")
            height = get_attr(["height"], person) or get_attr(["height"], data) or "-"
            pos = "-"
            p_obj = get_attr(["position"], data) or get_attr(["position"], person)
            if isinstance(p_obj, dict): pos = p_obj.get("name", "-")
            elif isinstance(p_obj, str): pos = p_obj
            if pos: pos = pos.replace("_", " ")
            
            return {"img": img, "height": height, "pos": pos, "age": age, "nationality": nat}
    except: pass
    return {"img": "", "height": "-", "pos": "-", "age": "-", "nationality": "-"}

@st.cache_data(ttl=600)
def fetch_team_details_raw(team_id, season_id):
    url = f"https://api-1.dbbl.scb.world/teams/{team_id}/{season_id}"
    try:
        resp = requests.get(url, headers=API_HEADERS)
        if resp.status_code == 200: return resp.json()
    except: pass
    return None

@st.cache_data(ttl=600)
def fetch_team_data(team_id, season_id):
    api_stats = f"https://api-s.dbbl.scb.world/teams/{team_id}/{season_id}/player-stats"
    raw_details = fetch_team_details_raw(team_id, season_id)
    roster_lookup = {}
    
    if raw_details:
        squad = raw_details.get("squad", []) if isinstance(raw_details, dict) else []
        for entry in squad:
            p = entry.get("person", {})
            raw_id = p.get("id") or entry.get("id")
            if not raw_id: continue
            pid = str(raw_id).replace(".0", "")
            def find_val(keys):
                for k in keys:
                    if k in p and p[k]: return p[k]
                    if k in entry and entry[k]: return entry[k]
                return None
            bdate = find_val(["birthDate", "birthdate"]) or ""
            nat = "-"
            nats_list = find_val(["nationalities"])
            if nats_list and isinstance(nats_list, list): nat = ", ".join(nats_list)
            else:
                nat_obj = find_val(["nationality"])
                if nat_obj and isinstance(nat_obj, dict): nat = nat_obj.get("name", "-")
            height = find_val(["height"]) or "-"
            pos = "-"
            pos_raw = find_val(["position"])
            if isinstance(pos_raw, dict): pos = pos_raw.get("name", "-")
            elif isinstance(pos_raw, str): pos = pos_raw
            if pos: pos = pos.replace("_", " ")
            roster_lookup[pid] = {"birthdate": bdate, "nationality": nat, "height": height, "position": pos}

    try:
        r_stats = requests.get(api_stats, headers=API_HEADERS)
        if r_stats.status_code != 200: return None, None
        
        ts = {}
        # Team Stats (simplified, as they are part of the standings call now)
        
        df = None
        raw_p = r_stats.json()
        p_list = raw_p if isinstance(raw_p, list) else raw_p.get("data", [])
        
        if p_list:
            df = pd.json_normalize(p_list)
            df.columns = [str(c).lower() for c in df.columns]
            
            # NAME FIX: Add 'displayname' as a fallback
            col_map = {
                "firstname": ["seasonplayer.person.firstname", "person.firstname"], 
                "lastname": ["seasonplayer.person.lastname", "person.lastname"],
                "displayname": ["seasonplayer.displayname", "displayname"],
                "shirtnumber": ["seasonplayer.shirtnumber", "jerseynumber"], 
                "id": ["seasonplayer.personid", "seasonplayer.id", "playerid"],
                "position": ["seasonplayer.position", "position"]
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
            
            # Create name from first/last, then use displayname as fallback
            df["NAME_FULL"] = (get_s("firstname") + " " + get_s("lastname")).str.strip()
            display_name_col = final_cols.get("displayname")
            if display_name_col in df.columns:
                df.loc[df["NAME_FULL"] == "", "NAME_FULL"] = df[display_name_col]

            df["NR"] = get_s("shirtnumber").str.replace(".0", "", regex=False)
            df["PLAYER_ID"] = get_s("id").str.replace(".0", "", regex=False)
            df["POS"] = get_s("position").apply(lambda x: x.replace("_", " "))
            df["BIRTHDATE"] = df["PLAYER_ID"].apply(lambda x: roster_lookup.get(x, {}).get("birthdate", ""))
            df["NATIONALITY"] = df["PLAYER_ID"].apply(lambda x: roster_lookup.get(x, {}).get("nationality", "-"))
            df["HEIGHT_ROSTER"] = df["PLAYER_ID"].apply(lambda x: roster_lookup.get(x, {}).get("height", "-"))
            df["AGE"] = df["BIRTHDATE"].apply(calculate_age)
            df["POS_ROSTER"] = df["PLAYER_ID"].apply(lambda x: roster_lookup.get(x, {}).get("position", "-"))
            df["POS"] = df.apply(lambda x: x["POS_ROSTER"] if x["POS_ROSTER"] != "-" else x["POS"], axis=1)
            df["GP"] = get_n("gamesplayed").replace(0,1)
            df["MIN_FINAL"] = get_n("minutespergame")
            df["MIN_DISPLAY"] = df["MIN_FINAL"].apply(format_minutes)
            df["PPG"] = get_n("pointspergame"); df["TOT"] = get_n("totalreboundspergame"); df["AS"] = get_n("assistspergame")
            df["TO"] = get_n("turnoverspergame"); df["ST"] = get_n("stealspergame"); df["BS"] = get_n("blockspergame"); df["PF"] = get_n("foulscommittedpergame")
            m2 = get_n("twopointshotsmadepergame"); a2 = get_n("twopointshotsattemptedpergame")
            m3 = get_n("threepointshotsmadepergame"); a3 = get_n("threepointshotsattemptedpergame")
            total_att = a2 + a3
            df["FG%"] = pd.Series([0.0]*len(df), index=df.index)
            mask_att = total_att > 0
            df.loc[mask_att, "FG%"] = ((m2[mask_att]+m3[mask_att]) / total_att[mask_att] * 100).round(1)
            df["3PCT"] = get_n("threepointshotsuccesspercent").apply(lambda x: round(x*100, 1) if x <= 1 else round(x, 1))
            df["FTPCT"] = get_n("freethrowssuccesspercent").apply(lambda x: round(x*100, 1) if x <= 1 else round(x, 1))
            df["select"] = False
        else:
            df = pd.DataFrame()
        return df, ts
    except Exception:
        return None, None

# ... (alle anderen fetch funktionen bleiben gleich) ...

@st.cache_data(ttl=300)
def fetch_schedule(team_id, season_id):
    url = f"https://api-s.dbbl.scb.world/games?currentPage=1&seasonTeamId={team_id}&pageSize=1000&gameType=all&seasonId={season_id}"
    try:
        resp = requests.get(url, headers=API_HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            clean = []
            for g in items:
                res = g.get("result")
                score, has_res, h_score, g_score = "-", False, 0, 0
                if res and isinstance(res, dict):
                    h_score = res.get('homeTeamFinalScore'); g_score = res.get('guestTeamFinalScore')
                    if h_score is not None and g_score is not None: score, has_res = f"{h_score} : {g_score}", True
                raw_d = g.get("scheduledTime", "")
                d_disp = raw_d
                if raw_d:
                    try: d_disp = datetime.fromisoformat(raw_d.replace("Z", "+00:00")).astimezone(pytz.timezone("Europe/Berlin")).strftime("%d.%m.%Y %H:%M")
                    except: pass
                clean.append({"id": g.get("id"), "date": d_disp, "score": score, "has_result": has_res, "home": g.get("homeTeam", {}).get("name", "?"), "guest": g.get("guestTeam", {}).get("name", "?"), "homeTeamId": str(g.get("homeTeam", {}).get("teamId")), "guestTeamId": str(g.get("guestTeam", {}).get("teamId")), "home_score": h_score, "guest_score": g_score})
            return clean
    except: pass
    return []

@st.cache_data(ttl=2)
def fetch_game_boxscore(game_id):
    try: return requests.get(f"https://api-s.dbbl.scb.world/games/{game_id}/stats", headers=API_HEADERS).json()
    except: return None

@st.cache_data(ttl=2)
def fetch_game_details(game_id):
    try: return requests.get(f"https://api-s.dbbl.scb.world/games/{game_id}", headers=API_HEADERS).json()
    except: return None

@st.cache_data(ttl=3600) 
def fetch_team_info_basic(team_id):
    try:
        resp = requests.get(f"https://api-s.dbbl.scb.world/teams/{team_id}", headers=API_HEADERS)
        if resp.status_code == 200:
            venues = resp.json().get("venues", [])
            main = next((v for v in venues if v.get("isMain")), venues[0] if venues else None)
            if main: return {"id": team_id, "venue": main}
    except: pass
    sched = fetch_schedule(team_id, SEASON_ID)
    if sched:
        def parse_date(d): 
             try: return datetime.strptime(d, "%d.%m.%Y %H:%M") 
             except: return datetime.min
        homes = [g for g in sched if str(g.get("homeTeamId")) == str(team_id)]
        homes.sort(key=lambda x: parse_date(x['date']), reverse=True)
        for g in homes:
            det = fetch_game_details(g['id'])
            if det and det.get("venue"): return {"id": team_id, "venue": det["venue"]}
    return {"id": team_id, "venue": None}

@st.cache_data(ttl=60)
def fetch_season_games(season_id):
    url = f"https://api-s.dbbl.scb.world/games?currentPage=1&pageSize=2000&gameType=all&seasonId={season_id}"
    try:
        resp = requests.get(url, headers=API_HEADERS)
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            clean = []
            for g in items:
                res = g.get("result")
                score, has_res, h_score, g_score = "0 : 0", False, 0, 0
                if res and isinstance(res, dict):
                    h_score = res.get('homeTeamFinalScore', 0); g_score = res.get('guestTeamFinalScore', 0)
                    if h_score is not None and g_score is not None:
                        score = f"{h_score} : {g_score}"
                        if h_score > 0 or g_score > 0: has_res = True
                raw_d = g.get("scheduledTime", "")
                d_disp, date_only = raw_d, ""
                if raw_d:
                    try: 
                        dt = datetime.fromisoformat(raw_d.replace("Z", "+00:00")).astimezone(pytz.timezone("Europe/Berlin"))
                        d_disp, date_only = dt.strftime("%d.%m.%Y %H:%M"), dt.strftime("%d.%m.%Y")
                    except: pass
                clean.append({"id": g.get("id"), "date": d_disp, "date_only": date_only, "score": score, "has_result": has_res, "home": g.get("homeTeam", {}).get("name", "?"), "guest": g.get("guestTeam", {}).get("name", "?"), "home_logo_id": str(g.get("homeTeam", {}).get("teamId")), "guest_logo_id": str(g.get("guestTeam", {}).get("teamId"))})
            return clean
    except: pass
    return []

@st.cache_data(ttl=3600)
def fetch_standings(season_id, staffel):
    """Lädt die Tabelle für die angegebene Staffel (Nord oder Süd)."""
    staffel_short = "n" if staffel.lower() == "nord" else "s"
    url = f"https://api-{staffel_short}.dbbl.scb.world/seasons/{season_id}/team-statistics?displayType=MAIN_ROUND"
    
    standings_data = []
    try:
        # TABELLEN-FIX: Die Anfrage wird OHNE die API-Header gesendet.
        resp = requests.get(url)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                standings_data = data
    except requests.exceptions.RequestException:
        return {}
            
    standings_map = {}
    for entry in standings_data:
        tid = str(entry.get("teamId", ""))
        if tid:
            standings_map[tid] = {
                "rank": entry.get("rank", "-"), "team": {"name": entry.get("teamName", "Unbekannt")},
                "matchesPlayed": entry.get("gamesPlayed", 0), "wins": entry.get("wins", 0), "losses": entry.get("losses", 0),
                "points": entry.get("points", 0), "pointsScored": entry.get("pointsScored", 0),
                "pointsConceded": entry.get("pointsConceded", 0), "pointsDifference": entry.get("pointsDifference", 0),
                "streak": entry.get("streak", "-"), "homePerformance": entry.get("homePerformance", {}),
                "guestPerformance": entry.get("guestPerformance", {})
            }
    return standings_map
