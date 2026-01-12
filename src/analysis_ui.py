# --- START OF FILE src/analysis_ui.py ---
import base64
from datetime import datetime

import pandas as pd
import pytz
import streamlit as st
import altair as alt  # (aktuell nicht genutzt, aber belassen)

from src.api import get_player_metadata_cached, get_best_team_logo, fetch_last_n_games_complete


# --- KONSTANTEN & HELPERS ---
ACTION_TRANSLATION = {
    "TWO_POINT_SHOT_MADE": "2P Treffer",
    "TWO_POINT_SHOT_MISSED": "2P Fehl",
    "THREE_POINT_SHOT_MADE": "3P Treffer",
    "THREE_POINT_SHOT_MISSED": "3P Fehl",
    "FREE_THROW_MADE": "FW Treffer",
    "FREE_THROW_MISSED": "FW Fehl",
    "REBOUND": "Rebound",
    "FOUL": "Foul",
    "TURNOVER": "TO",
    "ASSIST": "Assist",
    "STEAL": "Steal",
    "BLOCK": "Block",
    "SUBSTITUTION": "Wechsel",
    "TIMEOUT": "Auszeit",
    "JUMP_BALL": "Sprungball",
    "START": "Start",
    "END": "Ende",
    "TWO_POINT_THROW": "2P Wurf",
    "THREE_POINT_THROW": "3P Wurf",
    "FREE_THROW": "Freiwurf",
    "LAYUP": "Korbleger",
    "JUMP_SHOT": "Sprung",
    "DUNK": "Dunk",
    "OFFENSIVE": "Off",
    "DEFENSIVE": "Def",
    "PERSONAL_FOUL": "Persönlich",
    "TECHNICAL_FOUL": "Technisch",
    "UNSPORTSMANLIKE_FOUL": "Unsportlich",
}


def translate_text(text):
    if not text:
        return ""
    text_upper = str(text).upper()
    if text_upper in ACTION_TRANSLATION:
        return ACTION_TRANSLATION[text_upper]
    return str(text).replace("_", " ").title()


def safe_int(val):
    if val is None:
        return 0
    try:
        return int(float(val))
    except Exception:
        return 0


def get_team_name(team_data, default_name="Team"):
    if not team_data:
        return default_name
    name = team_data.get("gameStat", {}).get("seasonTeam", {}).get("name")
    if name:
        return name
    name = team_data.get("seasonTeam", {}).get("name")
    if name:
        return name
    return team_data.get("name", default_name)


def format_date_time(iso_string):
    if not iso_string:
        return "-"
    try:
        dt = datetime.fromisoformat(str(iso_string).replace("Z", "+00:00"))
        berlin = pytz.timezone("Europe/Berlin")
        return dt.astimezone(berlin).strftime("%d.%m.%Y | %H:%M Uhr")
    except Exception:
        return str(iso_string)


def get_player_lookup(box):
    lookup = {}
    for team_key in ["homeTeam", "guestTeam"]:
        for p in box.get(team_key, {}).get("playerStats", []):
            pid = str(p.get("seasonPlayer", {}).get("id"))
            name = f"{p.get('seasonPlayer', {}).get('lastName', '')}"
            nr = p.get("seasonPlayer", {}).get("shirtNumber", "")
            lookup[pid] = f"#{nr} {name}".strip()
    return lookup


def get_player_team_map(box):
    player_team = {}
    h_name = get_team_name(box.get("homeTeam", {}), "Heim")
    g_name = get_team_name(box.get("guestTeam", {}), "Gast")
    for p in box.get("homeTeam", {}).get("playerStats", []):
        player_team[str(p.get("seasonPlayer", {}).get("id"))] = h_name
    for p in box.get("guestTeam", {}).get("playerStats", []):
        player_team[str(p.get("seasonPlayer", {}).get("id"))] = g_name
    return player_team


def get_time_info(time_str, period):
    """
    time_str kann sein: "PTxxxS" oder "mm:ss" oder "hh:mm:ss"
    Rückgabe: (restzeit_mm:ss, vergangen_mm:ss)
    """
    if not time_str:
        return "10:00", "00:00"

    p_int = safe_int(period)
    base_min = 5 if p_int > 4 else 10
    total_sec = base_min * 60
    elapsed_sec = 0

    try:
        s = str(time_str)

        if "PT" in s:
            t = s.replace("PT", "").replace("S", "")
            if "M" in t:
                parts = t.split("M")
                elapsed_sec = int(float(parts[0])) * 60 + int(float(parts[1] or 0))
            else:
                elapsed_sec = int(float(t))

        elif ":" in s:
            parts = s.split(":")
            if len(parts) == 3:
                elapsed_sec = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif len(parts) == 2:
                elapsed_sec = int(parts[0]) * 60 + int(parts[1])
            else:
                elapsed_sec = int(float(s))

        else:
            elapsed_sec = int(float(s))

        rem_sec = total_sec - elapsed_sec
        if rem_sec < 0:
            rem_sec = 0

        return f"{rem_sec // 60:02d}:{rem_sec % 60:02d}", f"{elapsed_sec // 60:02d}:{elapsed_sec % 60:02d}"

    except Exception:
        return "10:00", str(time_str)


def _logo_to_src(logo):
    """
    Unterstützt:
    - URL (str) -> direkt als src
    - bytes -> data URL
    """
    if not logo:
        return None
    if isinstance(logo, str):
        return logo
    if isinstance(logo, (bytes, bytearray)):
        b64 = base64.b64encode(logo).decode("utf-8")
        return f"data:image/png;base64,{b64}"
    return None


def get_team_fouls_in_period(actions, period, home_ids, guest_ids):
    """
    Teamfouls im aktuellen Viertel (max 5 angezeigt).
    Als Teamfoul zählen wir alle Aktionen, deren type "FOUL" enthält.
    """
    h_fouls = 0
    g_fouls = 0
    p = safe_int(period)

    for a in actions or []:
        if safe_int(a.get("period")) != p:
            continue
        t = str(a.get("type") or "").upper()
        if "FOUL" not in t:
            continue

        sid = str(a.get("seasonTeamId"))
        if sid in home_ids:
            h_fouls += 1
        elif sid in guest_ids:
            g_fouls += 1

    return min(h_fouls, 5), min(g_fouls, 5)


# --- VISUELLE KOMPONENTEN ---

def render_live_comparison_bars(box):
    h_stat = box.get("homeTeam", {}).get("gameStat", {}) or {}
    g_stat = box.get("guestTeam", {}).get("gameStat", {}) or {}
    h_name = get_team_name(box.get("homeTeam", {}))
    g_name = get_team_name(box.get("guestTeam", {}))

    def get_pct(made, att):
        m, a = safe_int(made), safe_int(att)
        return round((m / a * 100), 1) if a > 0 else 0.0

    stats_to_show = [
        ("2 PUNKTE", "twoPointShotsMade", "twoPointShotsAttempted", True),
        ("3 PUNKTE", "threePointShotsMade", "threePointShotsAttempted", True),
        ("FIELDGOALS", "fieldGoalsMade", "fieldGoalsAttempted", True),
        ("FREIWÜRFE", "freeThrowsMade", "freeThrowsAttempted", True),
        ("DEF. REBOUNDS", "defensiveRebounds", None, False),
        ("OFF. REBOUNDS", "offensiveRebounds", None, False),
        ("ASSISTS", "assists", None, False),
        ("STEALS", "steals", None, False),
        ("BLOCKS", "blocks", None, False),
        ("TURNOVERS", "turnovers", None, False),
        ("FOULS", "foulsCommitted", None, False),
    ]

    st.markdown(
        """
        <style>
          .stat-container { margin-bottom: 12px; width: 100%; }
          .stat-label { text-align: center; font-weight: bold; font-style: italic; color: #555; font-size: 0.85em; }
          .bar-wrapper { display: flex; align-items: center; justify-content: center; gap: 8px; height: 10px; }
          .bar-bg { background-color: #eee; flex-grow: 1; height: 100%; border-radius: 2px; position: relative; }
          .bar-fill-home { background-color: #e35b00; height: 100%; position: absolute; right: 0; }
          .bar-fill-guest { background-color: #333; height: 100%; position: absolute; left: 0; }
          .val-text { width: 85px; font-weight: bold; font-size: 0.85em; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    c1, _, c3 = st.columns([1, 1, 1])
    c1.markdown(f"<h4 style='text-align:right; color:#e35b00;'>{h_name}</h4>", unsafe_allow_html=True)
    c3.markdown(f"<h4 style='text-align:left; color:#333;'>{g_name}</h4>", unsafe_allow_html=True)

    for label, km, ka, is_p in stats_to_show:
        hv, gv = safe_int(h_stat.get(km)), safe_int(g_stat.get(km))

        if is_p:
            ha, ga = safe_int(h_stat.get(ka)), safe_int(g_stat.get(ka))
            hp, gp = get_pct(hv, ha), get_pct(gv, ga)
            hd, gd = f"{hp}%", f"{gp}%"
            hf, gf = hp, gp
        else:
            hd, gd = str(hv), str(gv)
            mv = max(hv, gv, 1)
            hf, gf = (hv / mv) * 100, (gv / mv) * 100

        st.markdown(
            f"""
            <div class="stat-container">
              <div class="stat-label">{label}</div>
              <div class="bar-wrapper">
                <div class="val-text" style="text-align:right;">{hd}</div>
                <div class="bar-bg"><div class="bar-fill-home" style="width:{hf}%;"></div></div>
                <div class="bar-bg"><div class="bar-fill-guest" style="width:{gf}%;"></div></div>
                <div class="val-text" style="text-align:left;">{gd}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# --- REINE ANALYSIS-FUNKTIONEN ---

def render_game_header(details):
    h_data, g_data = details.get("homeTeam", {}), details.get("guestTeam", {})
    h_name, g_name = get_team_name(h_data, "Heim"), get_team_name(g_data, "Gast")
    res = details.get("result", {})
    sh, sg = res.get("homeTeamFinalScore", 0), res.get("guestTeamFinalScore", 0)
    time_str = format_date_time(details.get("scheduledTime"))
    venue = details.get("venue", {})
    vs = f"{venue.get('name', '-')}, {venue.get('address', '').split(',')[-1].strip()}"

    st.markdown(f"<div style='text-align: center; color: #666;'>📍 {vs} | 🕒 {time_str}</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([2, 1, 2])
    c1.markdown(f"<h2 style='text-align:right;'>{h_name}</h2>", unsafe_allow_html=True)
    c2.markdown(f"<h1 style='text-align:center;'>{sh}:{sg}</h1>", unsafe_allow_html=True)
    c3.markdown(f"<h2 style='text-align:left;'>{g_name}</h2>", unsafe_allow_html=True)


def render_boxscore_table_pro(player_stats, team_stats_official, team_name, coach_name="-"):
    if not player_stats:
        return

    data = []

    # Summen-Variablen (Player Sums)
    s_pts = 0
    s_m2 = 0
    s_a2 = 0
    s_m3 = 0
    s_a3 = 0
    s_mf = 0
    s_af = 0
    s_mfg = 0
    s_afg = 0
    s_or = 0
    s_dr = 0
    s_tr = 0
    s_as = 0
    s_st = 0
    s_to = 0
    s_bs = 0
    s_pf = 0
    s_eff = 0
    s_pm = 0
    s_sec = 0

    def fmt_stat(made, att):
        pct = int((made / att) * 100) if att > 0 else 0
        return f"{made}/{att} ({pct}%)"

    for p in player_stats:
        info = p.get("seasonPlayer", {})
        sec = safe_int(p.get("secondsPlayed"))
        s_sec += sec

        pts = safe_int(p.get("points"))
        s_pts += pts

        m2 = safe_int(p.get("twoPointShotsMade"))
        a2 = safe_int(p.get("twoPointShotsAttempted"))
        s_m2 += m2
        s_a2 += a2

        m3 = safe_int(p.get("threePointShotsMade"))
        a3 = safe_int(p.get("threePointShotsAttempted"))
        s_m3 += m3
        s_a3 += a3

        mf = safe_int(p.get("freeThrowsMade"))
        af = safe_int(p.get("freeThrowsAttempted"))
        s_mf += mf
        s_af += af

        fgm = safe_int(p.get("fieldGoalsMade"))
        fga = safe_int(p.get("fieldGoalsAttempted"))
        if fga == 0:
            fgm = m2 + m3
            fga = a2 + a3
        s_mfg += fgm
        s_afg += fga

        oreb = safe_int(p.get("offensiveRebounds"))
        dreb = safe_int(p.get("defensiveRebounds"))
        treb = safe_int(p.get("totalRebounds"))
        ast = safe_int(p.get("assists"))
        stl = safe_int(p.get("steals"))
        tov = safe_int(p.get("turnovers"))
        blk = safe_int(p.get("blocks"))
        pf = safe_int(p.get("foulsCommitted"))
        eff = safe_int(p.get("efficiency"))
        pm = safe_int(p.get("plusMinus"))

        s_or += oreb
        s_dr += dreb
        s_tr += treb
        s_as += ast
        s_st += stl
        s_to += tov
        s_bs += blk
        s_pf += pf
        s_eff += eff
        s_pm += pm

        data.append(
            {
                "#": str(info.get("shirtNumber", "-")),
                "Name": f"{info.get('lastName','-')}, {info.get('firstName','')}".strip().strip(","),
                "Min": f"{sec // 60:02d}:{sec % 60:02d}",
                "PTS": pts,
                "2P": fmt_stat(m2, a2),
                "3P": fmt_stat(m3, a3),
                "FG": fmt_stat(fgm, fga),
                "FT": fmt_stat(mf, af),
                "OR": oreb,
                "DR": dreb,
                "TR": treb,
                "AS": ast,
                "ST": stl,
                "TO": tov,
                "BS": blk,
                "PF": pf,
                "EFF": eff,
                "+/-": pm,
            }
        )

    # Team / Coach Zeile (Differenzen)
    t = team_stats_official or {}
    tm_pts = safe_int(t.get("points")) - s_pts
    tm_or = safe_int(t.get("offensiveRebounds")) - s_or
    tm_dr = safe_int(t.get("defensiveRebounds")) - s_dr
    tm_tr = safe_int(t.get("totalRebounds")) - s_tr
    tm_as = safe_int(t.get("assists")) - s_as
    tm_to = safe_int(t.get("turnovers")) - s_to
    tm_st = safe_int(t.get("steals")) - s_st
    tm_bs = safe_int(t.get("blocks")) - s_bs
    tm_pf = safe_int(t.get("foulsCommitted")) - s_pf
    tm_eff = safe_int(t.get("efficiency")) - s_eff

    if any([tm_pts, tm_or, tm_dr, tm_tr, tm_as, tm_to, tm_st, tm_bs, tm_pf, tm_eff]):
        data.append(
            {
                "#": "",
                "Name": "Team / Coach",
                "Min": None,
                "PTS": tm_pts if tm_pts else None,
                "2P": None,
                "3P": None,
                "FG": None,
                "FT": None,
                "OR": tm_or if tm_or else 0,
                "DR": tm_dr if tm_dr else 0,
                "TR": tm_tr if tm_tr else 0,
                "AS": tm_as if tm_as else 0,
                "ST": tm_st if tm_st else 0,
                "TO": tm_to if tm_to else 0,
                "BS": tm_bs if tm_bs else 0,
                "PF": tm_pf if tm_pf else 0,
                "EFF": tm_eff if tm_eff else 0,
                "+/-": None,
            }
        )

    totals_row = {
        "#": "",
        "Name": "TOTALS",
        "Min": "200:00",
        "PTS": safe_int(t.get("points", s_pts)),
        "2P": fmt_stat(safe_int(t.get("twoPointShotsMade", s_m2)), safe_int(t.get("twoPointShotsAttempted", s_a2))),
        "3P": fmt_stat(safe_int(t.get("threePointShotsMade", s_m3)), safe_int(t.get("threePointShotsAttempted", s_a3))),
        "FG": fmt_stat(safe_int(t.get("fieldGoalsMade", s_mfg)), safe_int(t.get("fieldGoalsAttempted", s_afg))),
        "FT": fmt_stat(safe_int(t.get("freeThrowsMade", s_mf)), safe_int(t.get("freeThrowsAttempted", s_af))),
        "OR": safe_int(t.get("offensiveRebounds", s_or)),
        "DR": safe_int(t.get("defensiveRebounds", s_dr)),
        "TR": safe_int(t.get("totalRebounds", s_tr)),
        "AS": safe_int(t.get("assists", s_as)),
        "ST": safe_int(t.get("steals", s_st)),
        "TO": safe_int(t.get("turnovers", s_to)),
        "BS": safe_int(t.get("blocks", s_bs)),
        "PF": safe_int(t.get("foulsCommitted", s_pf)),
        "EFF": safe_int(t.get("efficiency", s_eff)),
        "+/-": None,
    }
    data.append(totals_row)

    df = pd.DataFrame(data)
    if not df.empty:
        df["#"] = df["#"].astype(str)

    def style_rows(row):
        if row["Name"] == "TOTALS":
            return ["font-weight: bold; background-color: #e0e0e0; border-top: 2px solid #999"] * len(row)
        if row["Name"] == "Team / Coach":
            return ["font-style: italic; color: #666; background-color: #f9f9f9"] * len(row)
        return [""] * len(row)

    st.markdown(f"#### {team_name} (HC: {coach_name})")
    st.dataframe(df.style.apply(style_rows, axis=1), hide_index=True, width="stretch")


def render_game_top_performers(box):
    st.markdown("### Top Performer")
    c1, c2 = st.columns(2)
    for i, tkey in enumerate(["homeTeam", "guestTeam"]):
        td = box.get(tkey, {})
        players = sorted(td.get("playerStats", []), key=lambda x: safe_int(x.get("points")), reverse=True)[:3]
        with [c1, c2][i]:
            st.write(f"**{get_team_name(td)}**")
            for p in players:
                st.write(f"{p.get('seasonPlayer', {}).get('lastName')}: {p.get('points')} Pkt")


def render_charts_and_stats(box):
    st.markdown("### Team Statistik")
    render_live_comparison_bars(box)


def generate_game_summary(box):
    h = get_team_name(box.get("homeTeam"))
    g = get_team_name(box.get("guestTeam"))
    res = box.get("result", {})
    return f"Spiel zwischen {h} und {g}. Endstand {res.get('homeTeamFinalScore', 0)}:{res.get('guestTeamFinalScore', 0)}."


def generate_complex_ai_prompt(box):
    return f"KI-Prompt für Game ID {box.get('id', '-')}"


def run_openai_generation(api_key, prompt):
    return "KI-Dienst momentan über Prompt-Generator verfügbar."


# --- LIVE VIEW & TICKER ---

def render_full_play_by_play(box, height=600):
    actions = box.get("actions", [])
    if not actions:
        st.info("Keine Play-by-Play Daten verfügbar.")
        return

    player_map = get_player_lookup(box)
    team_map = get_player_team_map(box)
    h_name = get_team_name(box.get("homeTeam"))
    g_name = get_team_name(box.get("guestTeam"))

    h_ids = [
        str(box.get("homeTeam", {}).get("seasonTeamId")),
        str(box.get("homeTeam", {}).get("teamId")),
        str(box.get("homeTeam", {}).get("seasonTeam", {}).get("id")),
    ]
    g_ids = [
        str(box.get("guestTeam", {}).get("seasonTeamId")),
        str(box.get("guestTeam", {}).get("teamId")),
        str(box.get("guestTeam", {}).get("seasonTeam", {}).get("id")),
    ]

    data = []
    run_h, run_g = 0, 0
    actions_sorted = sorted(actions, key=lambda x: x.get("actionNumber", 0))

    for act in actions_sorted:
        hr, gr = act.get("homeTeamPoints"), act.get("guestTeamPoints")
        if hr is not None and gr is not None:
            nh, ng = safe_int(hr), safe_int(gr)
            if (nh + ng) >= (run_h + run_g):
                run_h, run_g = nh, ng

        p = act.get("period", "")
        t_rem, t_orig = get_time_info(act.get("gameTime") or act.get("timeInGame"), p)

        pid = str(act.get("seasonPlayerId"))
        team = team_map.get(pid) or (
            h_name if str(act.get("seasonTeamId")) in h_ids else (g_name if str(act.get("seasonTeamId")) in g_ids else "-")
        )

        actor = player_map.get(pid, "")
        desc = translate_text(act.get("type"))
        if act.get("points"):
            desc += f" (+{act.get('points')})"

        data.append(
            {
                "Zeit": f"Q{p} | {t_rem} ({t_orig})",
                "Score": f"{run_h}:{run_g}",
                "Team": team,
                "Spieler": actor,
                "Aktion": desc,
            }
        )

    df = pd.DataFrame(data)
    if not df.empty:
        df = df.iloc[::-1]

    st.dataframe(df, hide_index=True, height=height, width="stretch")


def create_live_boxscore_df(team_data):
    stats = []

    # Summen-Variablen (Live View)
    s_pts = 0
    s_m2 = 0
    s_a2 = 0
    s_m3 = 0
    s_a3 = 0
    s_mf = 0
    s_af = 0
    s_mfg = 0
    s_afg = 0
    s_or = 0
    s_dr = 0
    s_tr = 0
    s_as = 0
    s_st = 0
    s_to = 0
    s_bs = 0
    s_pf = 0
    s_sec = 0

    def fmt(m, a):
        return f"{m}/{a} ({int(m / a * 100) if a > 0 else 0}%)"

    for p in team_data.get("playerStats", []):
        sec = safe_int(p.get("secondsPlayed"))
        s_sec += sec

        pts = safe_int(p.get("points"))
        s_pts += pts

        m2 = safe_int(p.get("twoPointShotsMade"))
        a2 = safe_int(p.get("twoPointShotsAttempted"))
        s_m2 += m2
        s_a2 += a2

        m3 = safe_int(p.get("threePointShotsMade"))
        a3 = safe_int(p.get("threePointShotsAttempted"))
        s_m3 += m3
        s_a3 += a3

        mf = safe_int(p.get("freeThrowsMade"))
        af = safe_int(p.get("freeThrowsAttempted"))
        s_mf += mf
        s_af += af

        fgm = safe_int(p.get("fieldGoalsMade"))
        fga = safe_int(p.get("fieldGoalsAttempted"))
        s_mfg += fgm
        s_afg += fga

        oreb = safe_int(p.get("offensiveRebounds"))
        dreb = safe_int(p.get("defensiveRebounds"))
        treb = safe_int(p.get("totalRebounds"))
        ast = safe_int(p.get("assists"))
        stl = safe_int(p.get("steals"))
        tov = safe_int(p.get("turnovers"))
        blk = safe_int(p.get("blocks"))
        pf = safe_int(p.get("foulsCommitted"))

        s_or += oreb
        s_dr += dreb
        s_tr += treb
        s_as += ast
        s_st += stl
        s_to += tov
        s_bs += blk
        s_pf += pf

        stats.append(
            {
                "#": str(p.get("seasonPlayer", {}).get("shirtNumber", "-")),
                "Name": p.get("seasonPlayer", {}).get("lastName", "Unk"),
                "Min": f"{sec // 60:02d}:{sec % 60:02d}",
                "PTS": pts,
                "FG": fmt(fgm, fga),
                "2P": fmt(m2, a2),
                "3P": fmt(m3, a3),
                "FT": fmt(mf, af),
                "OR": oreb,
                "DR": dreb,
                "TR": treb,
                "AS": ast,
                "TO": tov,
                "ST": stl,
                "BS": blk,
                "PF": pf,
                "+/-": safe_int(p.get("plusMinus")),
                "OnCourt": bool(p.get("onCourt", False) or p.get("isOnCourt", False)),
            }
        )

    df = pd.DataFrame(stats)
    if not df.empty:
        df = df.sort_values(by=["PTS", "Min"], ascending=[False, False])

    # OFFIZIELLE TEAM STATS
    gs = team_data.get("gameStat", {}) or {}
    t_pts = safe_int(gs.get("points"))
    t_or = safe_int(gs.get("offensiveRebounds"))
    t_dr = safe_int(gs.get("defensiveRebounds"))
    t_tr = safe_int(gs.get("totalRebounds"))
    t_as = safe_int(gs.get("assists"))
    t_to = safe_int(gs.get("turnovers"))
    t_st = safe_int(gs.get("steals"))
    t_bs = safe_int(gs.get("blocks"))
    t_pf = safe_int(gs.get("foulsCommitted"))

    # Differenzen
    d_pts = t_pts - s_pts
    d_or = t_or - s_or
    d_dr = t_dr - s_dr
    d_tr = t_tr - s_tr
    d_as = t_as - s_as
    d_to = t_to - s_to
    d_st = t_st - s_st
    d_bs = t_bs - s_bs
    d_pf = t_pf - s_pf

    if any([d_pts, d_or, d_dr, d_tr, d_as, d_to, d_st, d_bs, d_pf]) and t_pts > 0:
        df_team = pd.DataFrame(
            [
                {
                    "#": "",
                    "Name": "Team / Coach",
                    "Min": None,
                    "PTS": d_pts if d_pts else None,
                    "FG": None,
                    "2P": None,
                    "3P": None,
                    "FT": None,
                    "OR": d_or if d_or else 0,
                    "DR": d_dr if d_dr else 0,
                    "TR": d_tr if d_tr else 0,
                    "AS": d_as if d_as else 0,
                    "TO": d_to if d_to else 0,
                    "ST": d_st if d_st else 0,
                    "BS": d_bs if d_bs else 0,
                    "PF": d_pf if d_pf else 0,
                    "+/-": None,
                    "OnCourt": False,
                }
            ]
        )
        df = pd.concat([df, df_team], ignore_index=True)

        # Totals an offizielle Werte anpassen
        s_pts += d_pts
        s_or += d_or
        s_dr += d_dr
        s_tr += d_tr
        s_as += d_as
        s_to += d_to
        s_st += d_st
        s_bs += d_bs
        s_pf += d_pf

    totals = {
        "#": "",
        "Name": "TOTALS",
        "Min": f"{s_sec // 60:02d}:{s_sec % 60:02d}",
        "PTS": s_pts,
        "FG": fmt(s_mfg, s_afg),
        "2P": fmt(s_m2, s_a2),
        "3P": fmt(s_m3, s_a3),
        "FT": fmt(s_mf, s_af),
        "OR": s_or,
        "DR": s_dr,
        "TR": s_tr,
        "AS": s_as,
        "TO": s_to,
        "ST": s_st,
        "BS": s_bs,
        "PF": s_pf,
        "+/-": None,
        "OnCourt": False,
    }

    df_totals = pd.DataFrame([totals])

    # Arrow-safe
    if not df.empty:
        df["#"] = df["#"].astype(str)

    return pd.concat([df, df_totals], ignore_index=True)


def render_live_view(box):
    if not box:
        return

    h_data, g_data = box.get("homeTeam", {}), box.get("guestTeam", {})
    h_name, g_name = get_team_name(h_data), get_team_name(g_data)

    res = box.get("result", {})
    sh = safe_int(res.get("homeTeamFinalScore"))
    sg = safe_int(res.get("guestTeamFinalScore"))

    period = res.get("period") or box.get("period", 1)
    actions = box.get("actions", [])

    # fallback score/period aus letzter Action
    if sh == 0 and sg == 0 and actions:
        last = sorted(actions, key=lambda x: x.get("actionNumber", 0))[-1]
        sh = safe_int(last.get("homeTeamPoints"))
        sg = safe_int(last.get("guestTeamPoints"))
        if not period:
            period = last.get("period")

    if not period or period == 0:
        for act in reversed(actions):
            if act.get("period"):
                period = act.get("period")
                break

    t_rem, t_orig = get_time_info(box.get("gameTime") or (actions[-1].get("gameTime") if actions else None), period)
    p_int = safe_int(period)
    p_str = f"OT{p_int - 4}" if p_int > 4 else f"{p_int}Q"

    # Team-IDs zum Zuordnen
    home_ids = set(
        [
            str(h_data.get("seasonTeamId")),
            str(h_data.get("teamId")),
            str(h_data.get("seasonTeam", {}).get("id")),
            str(h_data.get("gameStat", {}).get("seasonTeam", {}).get("id")),
        ]
    )
    guest_ids = set(
        [
            str(g_data.get("seasonTeamId")),
            str(g_data.get("teamId")),
            str(g_data.get("seasonTeam", {}).get("id")),
            str(g_data.get("gameStat", {}).get("seasonTeam", {}).get("id")),
        ]
    )

    # Teamfouls im aktuellen Viertel
    h_fouls, g_fouls = get_team_fouls_in_period(actions, period, home_ids, guest_ids)

    # Logos
    h_logo = _logo_to_src(get_best_team_logo(h_data.get("seasonTeamId") or h_data.get("teamId")))
    g_logo = _logo_to_src(get_best_team_logo(g_data.get("seasonTeamId") or g_data.get("teamId")))

    def dots_html(n):
        out = []
        for i in range(5):
            cls = "dot dot-on" if i < n else "dot dot-off"
            out.append(f"<span class='{cls}'></span>")
        return "".join(out)

    st.markdown(
        """
        <style>
          .scorebug-wrap{
            width:100%;
            background:#0f1a2a;
            border-radius:14px;
            padding:14px 16px;
            box-shadow: 0 6px 18px rgba(0,0,0,.28);
            color:#fff;
            margin-bottom: 18px;
          }
          .scorebug{
            display:flex;
            align-items:center;
            justify-content:space-between;
            gap:14px;
          }
          .team{
            display:flex;
            align-items:center;
            gap:12px;
            min-width: 260px;
          }
          .team.right{ justify-content:flex-end; }
          .logo{
            width:46px; height:46px;
            object-fit:contain;
            border-radius:10px;
            background: rgba(255,255,255,.08);
            padding:6px;
          }
          .team-name{
            font-weight:800;
            letter-spacing:.4px;
            font-size: 22px;
            line-height: 1.05;
          }
          .fouls{
            margin-top:6px;
            display:flex;
            gap:6px;
            align-items:center;
          }
          .dot{
            width:9px; height:9px;
            border-radius:50%;
            display:inline-block;
            border:1px solid rgba(255,255,255,.7);
          }
          .dot-off{ background: rgba(255,255,255,.18); }
          .dot-on{ background: #ff2d2d; border-color:#ff2d2d; }

          .center{ display:flex; align-items:center; gap:10px; }
          .scorebox{
            display:flex;
            align-items:center;
            justify-content:center;
            width:64px;
            height:52px;
            background:#f6c43b;
            border-radius:10px;
            color:#111;
            font-weight:900;
            font-size:34px;
          }
          .dash{
            color: rgba(255,255,255,.6);
            font-weight:900;
            font-size:28px;
            margin: 0 2px;
          }

          .rightinfo{
            display:flex;
            flex-direction:column;
            align-items:flex-end;
            gap:6px;
            min-width: 110px;
          }
          .clock{ font-weight:900; font-size: 26px; letter-spacing:.5px; color:#fff; }
          .quarter{ font-weight:900; font-size: 18px; color:#f6c43b; }

          @media (max-width: 900px){
            .team{ min-width: 180px; }
            .team-name{ font-size:18px; }
            .scorebox{ width:56px; height:48px; font-size:30px; }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    h_logo_tag = f"<img class='logo' src='{h_logo}'/>" if h_logo else "<div class='logo'></div>"
    g_logo_tag = f"<img class='logo' src='{g_logo}'/>" if g_logo else "<div class='logo'></div>"

    st.markdown(
        f"""
        <div class="scorebug-wrap">
          <div class="scorebug">
            <div class="team left">
              {h_logo_tag}
              <div>
                <div class="team-name">{h_name}</div>
                <div class="fouls">{dots_html(h_fouls)}</div>
              </div>
            </div>

            <div class="center">
              <div class="scorebox">{sh}</div>
              <div class="dash">|</div>
              <div class="scorebox">{sg}</div>
            </div>

            <div class="team right">
              <div style="text-align:right;">
                <div class="team-name">{g_name}</div>
                <div class="fouls" style="justify-content:flex-end;">{dots_html(g_fouls)}</div>
              </div>
              {g_logo_tag}
            </div>

            <div class="rightinfo">
              <div class="clock">{t_rem}</div>
              <div class="quarter">{p_str}</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    t1, t2, t3 = st.tabs(["📋 Boxscore", "📊 Team-Vergleich", "📜 Play-by-Play"])

    def style_live(row):
        if row.get("Name") == "TOTALS":
            return ["font-weight: bold; background-color: #e0e0e0; border-top: 2px solid #999"] * len(row)
        if row.get("Name") == "Team / Coach":
            return ["font-style: italic; color: #666; background-color: #f9f9f9"] * len(row)
        if row.get("OnCourt"):
            return ["background-color: #d4edda; color: #155724"] * len(row)
        return [""] * len(row)

    with t1:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"### {h_name}")
            dfh = create_live_boxscore_df(h_data)
            if not dfh.empty:
                st.dataframe(
                    dfh.style.apply(style_live, axis=1),
                    hide_index=True,
                    width="stretch",
                    height=(len(dfh) + 1) * 35 + 3,
                )
        with c2:
            st.markdown(f"### {g_name}")
            dfg = create_live_boxscore_df(g_data)
            if not dfg.empty:
                st.dataframe(
                    dfg.style.apply(style_live, axis=1),
                    hide_index=True,
                    width="stretch",
                    height=(len(dfg) + 1) * 35 + 3,
                )

    with t2:
        render_live_comparison_bars(box)

    with t3:
        render_full_play_by_play(box)


# --- PREP & SCOUTING (Team-Analyse) ---

def render_prep_dashboard(team_id, team_name, df_roster, last_games, metadata_callback=None):
    st.subheader(f"Analyse: {team_name}")
    c1, c2 = st.columns([2, 1])

    with c1:
        st.markdown("#### Top 4 Spieler")
        if df_roster is not None and not df_roster.empty:
            top4 = df_roster.sort_values(by="PPG", ascending=False).head(4)
            for _, row in top4.iterrows():
                with st.container(border=True):
                    ci, cs = st.columns([1, 4])
                    img = metadata_callback(row["PLAYER_ID"]).get("img") if metadata_callback else None
                    if img:
                        ci.image(img, width=80)
                    else:
                        ci.markdown("<div style='font-size:30px;'>👤</div>", unsafe_allow_html=True)
                    cs.markdown(f"**#{row.get('NR','-')} {row.get('NAME_FULL','Unk')}**")
                    cs.markdown(f"**{row.get('PPG',0)} PPG** | FG: {row.get('FG%',0)}% | 3P: {row.get('3PCT',0)}%")

    with c2:
        st.markdown("#### Formkurve")
        for g in (last_games[:5] if last_games else []):
            with st.container(border=True):
                st.caption(f"{g.get('date','').split(' ')[0]}")
                st.write(f"vs {g.get('home') if team_name not in g.get('home') else g.get('guest')}")
                st.write(f"**{g.get('score')}**")


def analyze_scouting_data(team_id, detailed_games):
    stats = {
        "games_count": len(detailed_games),
        "wins": 0,
        "ato_stats": {"possessions": 0, "points": 0},
        "start_stats": {"avg_diff": 0},
        "rotation_depth": 0,
        "top_scorers": {},
    }

    for box in detailed_games:
        is_h = box.get("meta_is_home", False)
        sh = safe_int(box.get("result", {}).get("homeTeamFinalScore") or box.get("homeTeamPoints"))
        sg = safe_int(box.get("result", {}).get("guestTeamFinalScore") or box.get("guestTeamPoints"))
        if (is_h and sh > sg) or ((not is_h) and sg > sh):
            stats["wins"] += 1

        to = box.get("homeTeam") if is_h else box.get("guestTeam")
        if to:
            act_p = 0
            for p in to.get("playerStats", []):
                pid = p.get("seasonPlayer", {}).get("id")
                pts = safe_int(p.get("points"))
                sec = safe_int(p.get("secondsPlayed"))
                if sec > 300:
                    act_p += 1
                if pid not in stats["top_scorers"]:
                    stats["top_scorers"][pid] = {"name": p.get("seasonPlayer", {}).get("lastName", "Unk"), "pts": 0, "games": 0}
                stats["top_scorers"][pid]["pts"] += pts
                stats["top_scorers"][pid]["games"] += 1
            stats["rotation_depth"] += act_p

        actions = sorted(box.get("actions", []), key=lambda x: x.get("actionNumber", 0))
        hs, gs = 0, 0
        for act in actions:
            if act.get("period") != 1:
                break
            if act.get("homeTeamPoints") is not None:
                hs, gs = safe_int(act.get("homeTeamPoints")), safe_int(act.getl = act.get("guestTeamPoints"))
                # (Bugfix: verhindert Tippfehler - wird unten überschrieben)
                gs = safe_int(act.get("guestTeamPoints"))
            if safe_int(act.get("actionNumber")) > 25:
                break
        stats["start_stats"]["avg_diff"] += (hs - gs) if is_h else (gs - hs)

    cnt = stats["games_count"] or 1
    stats["rotation_depth"] = round(stats["rotation_depth"] / cnt, 1)
    stats["start_stats"]["avg_diff"] = round(stats["start_stats"]["avg_diff"] / cnt, 1)

    scorer = []
    for d in stats["top_scorers"].values():
        if d["games"] > 0:
            scorer.append({"name": d["name"], "ppg": round(d["pts"] / d["games"], 1)})
    stats["top_scorers_list"] = sorted(scorer, key=lambda x: x["ppg"], reverse=True)[:5]

    return stats


def prepare_ai_scouting_context(team_name, detailed_games, team_id):
    ctx = f"Scouting-Daten für {team_name}\nAnzahl Spiele: {len(detailed_games)}\n\n"
    for g in detailed_games:
        is_h = g.get("meta_is_home", False)
        mysid = str(g.get("homeTeam" if is_h else "guestTeam", {}).get("seasonTeamId"))
        ctx += f"--- Spiel vs {g.get('meta_opponent')} ({g.get('meta_result')}) ---\n"
        pmap = get_player_lookup(g)

        starters = []
        for p in g.get("homeTeam" if is_h else "guestTeam", {}).get("playerStats", []):
            if p.get("isStartingFive"):
                starters.append(pmap.get(str(p.get("seasonPlayer", {}).get("id")), "Unk"))
        ctx += f"Starter: {', '.join(starters)}\n"

        actions = sorted(g.get("actions", []), key=lambda x: x.get("actionNumber", 0))
        ctx += "Start Phase Q1:\n"
        for act in actions[:12]:
            tid = str(act.get("seasonTeamId"))
            actor = "WIR" if tid == mysid else "GEGNER"
            pn = pmap.get(str(act.get("seasonPlayerId")), "")
            desc = translate_text(act.get("type", ""))
            ctx += f"- {actor}{' (' + pn + ')' if pn and actor == 'WIR' else ''}: {desc} {act.get('points','')}Pkt\n"

        ctx += "ATO:\n"
        for i, act in enumerate(actions):
            if "TIMEOUT" in str(act.get("type")).upper() and str(act.get("seasonTeamId")) == mysid:
                ctx += "TIMEOUT (WIR). Next:\n"
                for j in range(1, 5):
                    if i + j < len(actions):
                        na = actions[i + j]
                        who = "WIR" if str(na.get("seasonTeamId")) == mysid else "GEGNER"
                        ctx += f"  -> {who}: {translate_text(na.get('type',''))} {na.get('points','')}Pkt\n"
        ctx += "\n"
    return ctx


def analyze_game_flow(actions, home_label="Heim", guest_label="Gast"):
    """
    Minimaler Fallback, damit render_team_analysis_dashboard nicht crasht,
    falls du hier später noch eine detaillierte Flow-Analyse einbauen willst.
    """
    if not actions:
        return "Keine Aktionen vorhanden."
    actions_sorted = sorted(actions, key=lambda x: x.get("actionNumber", 0))
    first = actions_sorted[0]
    last = actions_sorted[-1]
    return f"Aktionsbereich: #{first.get('actionNumber')} bis #{last.get('actionNumber')} | Perioden: {first.get('period')}..{last.get('period')}"


def render_team_analysis_dashboard(team_id, team_name):
    logo = get_best_team_logo(team_id)
    c1, c2 = st.columns([1, 4])
    if logo:
        c1.image(logo, width=100)
    c2.title(f"Scouting Report: {team_name}")

    with st.spinner("Analysiere..."):
        games = fetch_last_n_games_complete(team_id, "2025", n=50)
        if not games:
            st.warning("Keine Daten.")
            return
        scout = analyze_scouting_data(team_id, games)

    k1, k2, k3 = st.columns(3)
    k1.metric("Spiele", scout["games_count"], f"{scout['wins']} Siege")
    k2.metric("Start Q1", f"{scout['start_stats']['avg_diff']:+.1f}")
    k3.metric("Rotation", scout["rotation_depth"])

    st.divider()
    col_l, col_r = st.columns([1, 1])

    with col_l:
        st.subheader("🔑 Schlüsselspieler")
        if scout.get("top_scorers_list"):
            st.dataframe(pd.DataFrame(scout["top_scorers_list"]), hide_index=True, width="stretch")

        st.markdown("---")
        st.subheader("🤖 KI-Prompt")
        st.code(
            f"Du bist ein professioneller Basketball-Scout. Analysiere {team_name}...\n\n{prepare_ai_scouting_context(team_name, games, team_id)}",
            language="text",
        )

    with col_r:
        st.subheader("📅 Spiele")
        for g in games:
            with st.expander(f"{g.get('meta_date')} vs {g.get('meta_opponent')} ({g.get('meta_result')})"):
                st.caption(analyze_game_flow(g.get("actions", []), "Heim", "Gast"))

# --- END OF FILE src/analysis_ui.py ---
