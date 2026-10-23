# -*- coding: utf-8 -*-
"""Чтение демо CS2: список игроков и раундов, извлечение нажатий одного игрока."""
import os
import numpy as np

TPS = 64
FORMAT_VERSION = 9

# (бит в сырой команде клиента usercmd_buttonstate_1, ключ). Порядок = номер бита в нашей маске.
BITS = [(3, "W"), (9, "A"), (4, "S"), (10, "D"), (1, "SPACE"), (2, "CTRL"), (16, "SHIFT"),
        (0, "LMB"), (11, "RMB"), (13, "R"), (5, "E"), (35, "F"), (33, "TAB")]
KEYS = [k for _, k in BITS]
AIR_BIT = 13
ALIVE_BIT = 14
GAP_BIT = 15           # в этот тик в демо нет сырых команд игрока — показано по запасным данным
# запасной вариант для демо без сырых команд: поля парсера (SCOREBOARD у парсера на деле бит шага)
FALLBACK = {"W": "FORWARD", "A": "LEFT", "S": "BACK", "D": "RIGHT", "LMB": "FIRE", "RMB": "RIGHTCLICK",
            "R": "RELOAD", "E": "USE", "F": "INSPECT", "SHIFT": "SCOREBOARD", "CTRL": "ducking"}

GRENADES = {"weapon_smokegrenade": "Дым", "weapon_flashbang": "Флешка", "weapon_hegrenade": "HE",
            "weapon_molotov": "Молотов", "weapon_incgrenade": "Зажигательная", "weapon_decoy": "Декой"}


def _side(w):
    if w is None:
        return None
    s = str(w).strip().upper()
    if s in ("CT", "3", "3.0"):
        return 3
    if s in ("T", "TERRORIST", "2", "2.0"):
        return 2
    return None


def _parser(path):
    from demoparser2 import DemoParser
    return DemoParser(path)


def scan(path):
    """Быстрый обзор демо: карта, игроки, раунды."""
    p = _parser(path)
    try:
        header = p.parse_header() or {}
    except Exception:
        header = {}
    info = p.parse_player_info()
    players = []
    for _, r in info.iterrows():
        sid = str(r["steamid"])
        if sid in ("0", "None", "nan") or not str(r["name"]).strip():
            continue
        players.append({"name": str(r["name"]), "steamid": sid, "team": int(r.get("team_number", 0) or 0)})

    ends = []
    try:
        re_ = p.parse_event("round_end")
        for _, r in re_.iterrows():
            side = _side(r.get("winner"))
            if side is not None:
                ends.append((int(r["tick"]), side))
    except Exception:
        pass
    ends.sort()
    # раунды до рестарта матча (begin_new_match) не считаются: счёт после него обнуляется
    try:
        bnm = [int(t) for t in p.parse_event("begin_new_match")["tick"]]
    except Exception:
        bnm = []
    match_start = max([t for t in bnm if not ends or t < ends[-1][0]], default=1)
    ends = [(t, sd) for t, sd in ends if t > match_start]
    try:
        fz = sorted(int(t) for t in p.parse_event("round_freeze_end")["tick"])
    except Exception:
        fz = []

    rounds, prev = [], match_start
    for i, (e, side) in enumerate(ends):
        f = [t for t in fz if prev <= t < e]
        rounds.append({"n": i + 1, "s": prev, "f": f[-1] if f else prev, "e": e, "winner": side})
        prev = e

    teams, slots = {}, {}
    if rounds:
        tn = p.parse_ticks(["team_num", "user_id"], ticks=[r["f"] for r in rounds])
        for _, r in tn.iterrows():
            tk, sid = int(r["tick"]), str(r["steamid"])
            teams.setdefault(tk, {})[sid] = int(r["team_num"] or 0)
            try:
                slots.setdefault(tk, {})[sid] = int(r["user_id"])      # номер слота игрока (для голоса)
            except (TypeError, ValueError):
                pass
    for r in rounds:
        r["teams"] = teams.get(r["f"], {})
        r["slots"] = slots.get(r["f"], {})

    end = (ends[-1][0] + 5 * TPS) if ends else 0
    return {"path": os.path.abspath(path), "map": header.get("map_name", ""), "players": players,
            "rounds": rounds, "end": end, "voice": voice_intervals(p)}


# запас патронов в начале (CS2): точного значения в демо нет — считаем от полного запаса и вычитаем перезарядки
def voice_intervals(p, gap=20):
    """Когда кто говорил: пакеты голоса игрока, склеенные в отрезки (пауза больше gap тиков — новый отрезок)."""
    try:
        packets = p.parse_voice()
    except Exception:
        return {}
    by = {}
    for x in packets or []:
        by.setdefault(str(x["steamid"]), set()).add(int(x["tick"]))
    out = {}
    for sid, ts in by.items():
        ts = sorted(ts)
        runs, s, prev = [], ts[0], ts[0]
        for t in ts[1:]:
            if t - prev > gap:
                runs.append([s, prev])
                s = t
            prev = t
        runs.append([s, prev])
        out[sid] = runs
    return out


def _rle(ticks, values):
    ch = np.r_[0, np.nonzero(np.diff(values))[0] + 1]
    out = []
    for i in ch:
        out += [int(ticks[i]), int(values[i])]
    return out


def extract_player(path, steamid, info=None):
    """Нажатия, оружие, выстрелы, гранаты, убийства одного игрока. Возвращает словарь для JSON."""
    info = info or scan(path)
    p = _parser(path)
    sid = int(steamid)
    name = next((pl["name"] for pl in info["players"] if pl["steamid"] == str(steamid)), str(steamid))

    # Сырые команды читаем ОТДЕЛЬНЫМ запросом: вместе с другими полями парсер «протягивает»
    # последнее значение через пропуски, и, например, отпущенный пробел выглядит зажатым 15 секунд.
    d = p.parse_ticks(["is_alive", "is_airborne", "active_weapon_name"], players=[sid])
    d = d.sort_values("tick").drop_duplicates("tick").reset_index(drop=True)
    if d.empty:
        raise ValueError("В демо нет данных по этому игроку")
    ticks = d["tick"].to_numpy()
    alive = d["is_alive"].fillna(False).astype(bool).to_numpy() if "is_alive" in d else np.ones(len(d), bool)

    def aligned(props):
        """Поля игрока по тем же тикам. Если в демо таких полей нет — пустая таблица (без падения)."""
        import pandas as pd
        try:
            x = p.parse_ticks(props, players=[sid])
        except Exception:
            x = None
        if x is None or "tick" not in getattr(x, "columns", ()):
            return pd.DataFrame(index=ticks)
        return x.drop_duplicates("tick").set_index("tick").reindex(ticks)

    raw_df = aligned(["usercmd_buttonstate_1"])
    raw = raw_df["usercmd_buttonstate_1"] if "usercmd_buttonstate_1" in raw_df else None
    fb = aligned(sorted(set(FALLBACK.values())))
    have = raw.notna().to_numpy() if raw is not None else np.zeros(len(d), bool)
    precise = have.sum() > len(d) * 0.3

    # 1) точные нажатия там, где сырые команды есть (в некоторых демо их нет совсем)
    mask = np.zeros(len(d), dtype=np.int64)
    raw_vals = raw.to_numpy() if raw is not None else np.zeros(len(d))
    b = np.array([int(x) if h else 0 for x, h in zip(raw_vals, have)], dtype=np.uint64)
    for i, (bit, _) in enumerate(BITS):
        mask |= (((b >> np.uint64(bit)) & np.uint64(1)).astype(np.int64)) << i
    # 2) в пропусках — по сетевому состоянию персонажа
    fbm = np.zeros(len(d), dtype=np.int64)
    for i, k in enumerate(KEYS):
        col = FALLBACK.get(k)
        if col and col in fb:
            fbm |= fb[col].map(lambda v: bool(v) if v is not None and v == v else False).to_numpy().astype(np.int64) << i
    air = d["is_airborne"].fillna(False).astype(bool).to_numpy() if "is_airborne" in d else np.zeros(len(d), bool)
    takeoff = air & ~np.r_[False, air[:-1]]
    jump = takeoff | np.r_[False, takeoff[:-1]]            # пробел на 2 тика в момент отрыва
    fbm |= jump.astype(np.int64) << KEYS.index("SPACE")
    mask = np.where(have, mask, fbm | (1 << GAP_BIT))

    mask &= np.where(alive, -1, 0)
    mask |= (air & alive).astype(np.int64) << AIR_BIT
    mask |= alive.astype(np.int64) << ALIVE_BIT

    w = d["active_weapon_name"].fillna("").astype(str).where(alive, "") if "active_weapon_name" in d else None
    wn, wr = [], []
    if w is not None:
        wn = sorted(set(w) - {""})
        wi = np.array([wn.index(x) if x else -1 for x in w])
        wr = _rle(ticks, wi)

    sh, gr = [], []
    try:
        ev = p.parse_event("weapon_fire")
        ev = ev[ev["user_steamid"].astype(str) == str(steamid)]
        for t, wpn in zip(ev["tick"], ev["weapon"].astype(str)):
            if wpn in GRENADES:
                gr.append([int(t), GRENADES[wpn]])
            elif not any(k in wpn for k in ("knife", "bayonet", "c4")):
                sh.append(int(t))
    except Exception:
        pass
    kills, deaths = [], []
    try:
        k = p.parse_event("player_death")
        kills = [int(t) for t in k[k["attacker_steamid"].astype(str) == str(steamid)]["tick"]]
        deaths = [int(t) for t in k[k["user_steamid"].astype(str) == str(steamid)]["tick"]]
    except Exception:
        pass

    # сдвиг между тиком демо и игровым тиком CS2 (консоль пишет «paused on tick N» в игровых тиках)
    gt_off = None
    try:
        probe = [int(x) for x in np.linspace(ticks[0], ticks[-1], 7)]
        g = p.parse_ticks(["game_time"], ticks=probe).drop_duplicates("tick")
        vals = sorted(int(round(gt * TPS - t)) for t, gt in zip(g["tick"], g["game_time"]) if gt == gt)
        if vals:
            gt_off = vals[len(vals) // 2]
    except Exception:
        pass

    vi = info.get("voice")
    if vi is None:
        vi = voice_intervals(p)

    rounds = []
    for r in info["rounds"]:
        team = r["teams"].get(str(steamid))
        sl = r.get("slots", {})
        rounds.append({"n": r["n"], "s": r["s"], "f": r["f"], "e": r["e"], "team": team, "winner": r["winner"],
                       "sides": r["teams"],
                       "won": (team == r["winner"]) if team in (2, 3) else None,
                       "t_slots": sorted(sl[s] for s, tm in r["teams"].items() if tm == 2 and s in sl),
                       "ct_slots": sorted(sl[s] for s, tm in r["teams"].items() if tm == 3 and s in sl)})

    return {"format": "cs2keys", "version": FORMAT_VERSION, "precise": bool(precise),
            "demo_path": info["path"], "demo_name": os.path.basename(info["path"]), "map": info["map"],
            "player": name, "steamid": str(steamid), "tps": TPS, "keys": KEYS,
            "rle": _rle(ticks, mask), "wn": wn, "wr": wr, "sh": sh, "gr": gr, "kills": kills, "deaths": deaths,
            "rounds": rounds, "gt_off": gt_off, "start": int(ticks[0]),
            "speakers": [{"name": pl["name"], "steamid": pl["steamid"], "iv": vi.get(pl["steamid"], [])}
                         for pl in info["players"]], "end": max(int(ticks[-1]), info["end"])}
