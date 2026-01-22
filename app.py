# --- START OF FILE src/api.py ---

import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import pytz
from src.config import API_HEADERS, SEASON_ID 

# --- HILFSFUNKTIONEN ---
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
        return today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
    except: return "-"

# --- CORE FETCHING ---

@st.cache_data(ttl=600, show_spinner=False)
def get_player_metadata_cached(player_id):
    try:
        clean_id = str(player_id).replace(".0", "")
        url = f"https://api-s.dbbl.scb.world/season-players/{clean_id}"
        resp = requests.get(url, headers=API_HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            p = data.get("person", {})
            img = data.get("imageUrl", "")
            
            bdate = p.get("birthDate") or p.get("birthdate") or ""
            age = calculate_age(bdate)
            
            nat = "-"
            if "nationalities" in p and isinstance(p["nationalities"], list) and len(p["nationalities"]) > 0:
                nat = ", ".join(p["nationalities"])
            elif "nationality" in p:
                nat = p["nationality"].get("name", "-")

            pos = "-"
            p_obj = data.get("position") or p.get("position")
            if isinstance(p_obj, dict): pos = p_obj.get("name", "-")
            elif isinstance(p_obj, str): pos = p_obj.replace("_", " ")

            return {"img": img, "height": data.get("height", 0), "pos": pos, "age": age, "nationality": nat}
    except: pass
    return {"img": "", "height": "-", "pos": "-", "age": "-", "nationality": "-"}

@st.cache_data(ttl=600)
def fetch_team_details_raw(team_id, season_id):
    try:
        return requests.get(f"https://api-1.dbbl.scb.world/teams/{team_id}/{season_id}", headers=API_HEADERS).json()
    except: return None

@st.cache_data(ttl=600)
def fetch_team_data(team_id, season_id):
    # ... (Code wie zuvor, gekürzt für Übersicht, Logik bleibt identisch) ...
    # Wenn Sie den Code von vorher hier haben, ist das super.
    # WICHTIG: Damit der Code vollständig ist, hier die Kurzfassung der Logik:
    
    api_stats = f"https://api-s.dbbl.scb.world/teams/{team_id}/{season_id}/player-stats"
    api_team = f"https://api-s.dbbl.scb.world/seasons/{season_id}/team-statistics?displayType=MAIN_ROUND&teamId={team_id}"
    
    raw_details = fetch_team_details_raw(team_id, season_id)
    roster_lookup = {}
    if raw_details:
        squad = raw_details.get("squad", []) if isinstance(raw_details, dict) else []
        for entry in squad:
            p = entry.get("person", {})
            pid = str(p.get("id", "")).replace(".0", "")
            if pid:
                nat = "-"
                if "nationalities" in p and p["nationalities"]: nat = "/".join(p["nationalities"])
                elif "nationality" in p: nat = p["nationality"].get("name", "-")
                roster_lookup[pid] = {"birthdate": p.get("birthDate", ""), "nationality": nat, "height": p.get("height", "-")}

    try:
        r_stats = requests.get(api_stats, headers=API_HEADERS)
        r_team = requests.get(api_team, headers=API_HEADERS)
        if r_stats.status_code != 200: return None, None
        
        ts = {}
        if r_team.status_code == 200:
            raw_ts = r_team.json()
            if raw_ts and isinstance(raw_ts, list):
                td = raw_ts[0]
                ts = {k: td.get(v, 0) for k, v in {"ppg":"pointsPerGame","tot":"totalReboundsPerGame","as":"assistsPerGame","to":"turnoversPerGame","st":"stealsPerGame","bs":"blocksPerGame","pf":"foulsCommittedPerGame","2pct":"twoPointShotsSuccessPercent","3pct":"threePointShotsSuccessPercent","ftpct":"freeThrowsSuccessPercent","or":"offensiveReboundsPerGame","dr":"defensiveReboundsPerGame"}.items()}
                ts["fgpct"] = td.get("fieldGoalsSuccessPercent", 0)

        df = None
        raw_p = r_stats.json()
        p_list = raw_p if isinstance(raw_p, list) else raw_p.get("data", [])
        
        if p_list:
            df = pd.json_normalize(p_list)
            df.columns = [str(c).lower() for c in df.columns]
            
            # Mapping Logic (gekürzt)
            col_map = {"firstname": ["person.firstname", "firstname"], "lastname": ["person.lastname", "lastname"], "shirtnumber": ["shirtnumber", "jerseynumber", "no"], "id": ["personid", "playerid", "id"]}
            final_cols = {}
            for t, opts in col_map.items():
                for o in opts:
                    m = [c for c in df.columns if o in c]
                    if m: final_cols[t] = sorted(m, key=len)[0]; break
            
            def get_n(k, d=0.0):
                m = [c for c in df.columns if k in c]
                if m: return pd.to_numeric(df[sorted(m, key=len)[0]], errors="coerce").fillna(d)
                return pd.Series([d]*len(df), index=df.index)
            
            # DataFrame Construction
            fn = df[final_cols["firstname"]].fillna("") if "firstname" in final_cols else ""
            ln = df[final_cols["lastname"]].fillna("") if "lastname" in final_cols else ""
            df["NAME_FULL"] = (fn.astype(str) + " " + ln.astype(str)).str.strip()
            
            sn_col = final_cols.get("shirtnumber")
            df["NR"] = df[sn_col].fillna("-").astype(str).str.replace(".0", "") if sn_col else "-"
            
            id_col = final_cols.get("id")
            df["PLAYER_ID"] = df[id_col].astype(str).str.replace(".0", "") if id_col else ""

            # Merge
            df["NATIONALITY"] = df["PLAYER_ID"].apply(lambda x: roster_lookup.get(x, {}).get("nationality", "-"))
            df["AGE"] = df["PLAYER_ID"].apply(lambda x: calculate_age(roster_lookup.get(x, {}).get("birthdate")))
            df["HEIGHT"] = df["PLAYER_ID"].apply(lambda x: roster_lookup.get(x, {}).get("height", "-"))

            # Stats Cols
            df["GP"] = get_n("gamesplayed").replace(0,1)
            df["MIN_DISPLAY"] = get_n("minutespergame").apply(lambda x: f"{int(x)}:{int((x%1)*60):02d}")
            df["PPG"] = get_n("pointspergame"); df["TOT"] = get_n("totalreboundspergame")
            df["AS"] = get_n("assistspergame"); df["ST"] = get_n("stealspergame"); df["TO"] = get_n("turnoverspergame"); df["PF"] = get_n("foulscommittedpergame")
            
            df["FG%"] = get_n("fieldgoalssuccesspercent").apply(lambda x: round(x*100, 1) if x<=1 else x)
            df["3PCT"] = get_n("threepointshotsuccesspercent").apply(lambda x: round(x*100, 1) if x<=1 else x)
            df["FTPCT"] = get_n("freethrowssuccesspercent").apply(lambda x: round(x*100, 1) if x<=1 else x)
            
            df["select"] = False
        else:
            df = pd.DataFrame()
            
        return df, ts
    except: return None, None

@st.cache_data(ttl=300)
def fetch_schedule(team_id, season_id):
    """Lädt Spiele. Datum im Format DD.MM.YYYY."""
    # Diese Funktion wird auch als fetch_season_games verwendet
    url = f"https://api-s.dbbl.scb.world/games?currentPage=1&seasonTeamId={team_id}&pageSize=1000&gameType=all&seasonId={season_id}"
    try:
        resp = requests.get(url, headers=API_HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            clean = []
            for g in items:
                res = g.get("result", {}) or {}
                h_score = res.get('homeTeamFinalScore'); v_score = res.get('guestTeamFinalScore')
                score = f"{h_score} : {v_score}" if h_score is not None else "-"
                has_res = (h_score is not None)
                
                raw_d = g.get("scheduledTime", "")
                d_disp = raw_d
                if raw_d:
                    try: d_disp = datetime.fromisoformat(raw_d.replace("Z", "+00:00")).astimezone(pytz.timezone("Europe/Berlin")).strftime("%d.%m.%Y %H:%M")
                    except: pass
                
                clean.append({
                    "id": g.get("id"), "date": d_disp, "score": score, "has_result": has_res,
                    "home": g.get("homeTeam", {}).get("name", "?"), "guest": g.get("guestTeam", {}).get("name", "?"),
                    "homeTeamId": str(g.get("homeTeam", {}).get("teamId")), "home_score": h_score,
                    "guestTeamId": str(g.get("guestTeam", {}).get("teamId")), "guest_score": v_score
                })
            return clean
    except: pass
    return []

# Alias für app.py Kompatibilität
fetch_season_games = fetch_schedule

@st.cache_data(ttl=600)
def get_best_team_logo(team_id):
    """Gibt die URL zum Team-Logo zurück."""
    # Versuch 1: Spezifisch für Saison
    url = f"https://api-s.dbbl.scb.world/images/teams/logo/{SEASON_ID}/{team_id}"
    # Validierung ist teuer, wir geben einfach die URL zurück, Streamlit handled 404s in st.image meist okay oder zeigt Broken Image
    return url

@st.cache_data(ttl=600)
def fetch_league_standings(season_id, league_name_filter=None):
    """Lädt die Tabelle."""
    url = f"https://api-s.dbbl.scb.world/seasons/{season_id}/standings"
    try:
        r = requests.get(url, headers=API_HEADERS)
        if r.status_code == 200:
            data = r.json()
            # API Struktur variiert, oft ist es eine Liste von Gruppen
            rows = []
            groups = data if isinstance(data, list) else [data]
            
            for grp in groups:
                g_name = grp.get("name", "") # z.B. "2. DBBL Nord"
                
                # Filter Logik
                if league_name_filter:
                    if league_name_filter == "1. DBBL" and "1" not in g_name: continue
                    if league_name_filter == "Nord" and "Nord" not in g_name: continue
                    if league_name_filter == "Süd" and "Süd" not in g_name: continue
                
                for entry in grp.get("standings", []):
                    rows.append({
                        "Platz": entry.get("rank"),
                        "Team": entry.get("team", {}).get("name"),
                        "Spiele": entry.get("matches"),
                        "S/N": f"{entry.get('wins')}/{entry.get('losses')}",
                        "Punkte": entry.get("points"),
                        "Körbe": f"{entry.get('pointsScored')}:{entry.get('pointsAllowed')}",
                        "Diff": entry.get("pointsDifference")
                    })
            return pd.DataFrame(rows)
    except: pass
    return pd.DataFrame()

# ... restliche Funktionen (fetch_game_boxscore etc.) bleiben erhalten ...
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
        resp = requests.get(f"https://api-s.dbbl.scb.world/teams/{team_id}", headers=API_HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            venues = data.get("venues", [])
            main = next((v for v in venues if v.get("isMain")), venues[0] if venues else None)
            if main: return {"id": team_id, "venue": main}
    except: pass
    # Fallback via Schedule
    sched = fetch_schedule(team_id, SEASON_ID)
    if sched:
        # Sortiere umgekehrt nach Datum string (dd.mm.yyyy) funktioniert nicht direkt gut, aber für den Zweck 'irgendein Heimspiel' reichts oft
        # Besser: Nur Heimspiele filtern
        homes = [g for g in sched if str(g.get("homeTeamId")) == str(team_id)]
        for g in homes: # Nimm einfach das erste gefundene Heimspiel
            d = fetch_game_details(g['id'])
            if d and d.get("venue"): return {"id": team_id, "venue": d["venue"]}
    return {"id": team_id, "venue": None}
