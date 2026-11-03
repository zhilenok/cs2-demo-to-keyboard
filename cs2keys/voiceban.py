# -*- coding: utf-8 -*-
"""Временное снятие мута с игроков демо.

CS2 хранит игроков, которых вы замутили, в Steam\\userdata\\<ваш id>\\730\\remote\\voice_ban.dt — и в демо
их голос тоже не слышно. Перед запуском CS2 для демо программа делает копию файла, убирает из него
игроков этой демки, а после закрытия CS2 возвращает файл как был: в обычных матчах мут остаётся.
Если программа закрылась раньше CS2, файл вернётся при следующем запуске программы."""
import json
import os
import re
import shutil
import time

STEAM64_BASE = 76561197960265728


def _data_dir():
    return os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "CS2Keys")


def _marker():
    return os.path.join(_data_dir(), "voice_ban_restore.json")


def _backup():
    return os.path.join(_data_dir(), "voice_ban.backup.dt")


def file_for_user(steam_dir, account_id):
    if not steam_dir or not account_id:
        return None
    return os.path.join(steam_dir, "userdata", str(int(account_id)), "730", "remote", "voice_ban.dt")


def active_account():
    """Аккаунт Steam, который сейчас вошёл (Steam пишет его в реестр)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam\ActiveProcess") as k:
            return int(winreg.QueryValueEx(k, "ActiveUser")[0] or 0) or None
    except Exception:
        return None


# ---------- разбор KeyValues ----------
_TOK = re.compile(r'"((?:[^"\\]|\\.)*)"|(\{)|(\})|(//[^\n]*)|([^\s{}"]+)')


def _blocks(text):
    """Блоки { … } с позициями: [{start, end, key, key_start, depth, values}] или None, если скобки не сходятся."""
    out, stack, last = [], [], None          # last: (строка, начало) последней строки перед «{»
    for m in _TOK.finditer(text):
        s, ob, cb, com, bare = m.groups()
        if com is not None:
            continue
        if ob:
            stack.append({"start": m.start(), "key": last[0] if last else None,
                          "key_start": last[1] if last else m.start(), "depth": len(stack), "values": [],
                          "kids": 0})
            last = None
        elif cb:
            if not stack:
                return None
            b = stack.pop()
            b["end"] = m.end()
            if stack:
                stack[-1]["kids"] += 1
            out.append(b)
            last = None
        else:
            val = s if s is not None else bare
            if stack:
                stack[-1]["values"].append(val)
            last = (val, m.start())
    return None if stack else out


def _ids(steamids):
    ids = set()
    for sid in steamids:
        try:
            v = int(sid)
        except (TypeError, ValueError):
            continue
        if v > STEAM64_BASE:
            acc = v - STEAM64_BASE
            ids |= {str(v), str(acc), f"[U:1:{acc}]", f"U:1:{acc}"}
    return ids


def strip_players(text, steamids):
    """Текст файла без блоков этих игроков и число убранных блоков. Непонятный формат — (None, 0)."""
    blocks = _blocks(text)
    if blocks is None:
        return None, 0
    ids = _ids(steamids)
    cut = []
    for b in blocks:
        if b["kids"]:
            continue                              # блок со вложенными блоками — это общий список, не игрок
        own = b["key"] in ids or any(v in ids for v in b["values"])
        if own:
            cut.append((b["key_start"], b["end"]))
    # только самые внутренние совпадения, без вложенных друг в друга
    cut.sort()
    merged = []
    for a, e in cut:
        if merged and a < merged[-1][1]:
            continue
        merged.append((a, e))
    if not merged:
        return text, 0
    out, pos = [], 0
    for a, e in merged:
        ls = text.rfind("\n", 0, a) + 1           # убираем строки целиком, вместе с отступом
        a = ls if not text[ls:a].strip() else a
        le = text.find("\n", e)
        e = (le + 1) if le != -1 and not text[e:le].strip() else e
        out.append(text[pos:a])
        pos = e
    out.append(text[pos:])
    new = "".join(out)
    if _blocks(new) is None:
        return None, 0
    return new, len(merged)


def _read(path):
    with open(path, "rb") as f:
        raw = f.read()
    for enc in ("utf-8", "cp1251"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            pass
    return None, None


def unmute(path, steamids):
    """Убирает игроков демо из voice_ban.dt (с копией оригинала). Возвращает число размученных."""
    if not path or not os.path.isfile(path):
        return 0
    if os.path.exists(_marker()):            # прошлый раз не вернули — сначала возвращаем оригинал
        restore()
    text, enc = _read(path)
    if text is None:
        return 0
    new, n = strip_players(text, steamids)
    if not n or new is None:
        return 0
    os.makedirs(_data_dir(), exist_ok=True)
    shutil.copy2(path, _backup())
    with open(_marker(), "w", encoding="utf-8") as f:
        json.dump({"path": path, "time": time.time()}, f)
    with open(path, "w", encoding=enc, newline="") as f:
        f.write(new)
    return n


def pending():
    return os.path.exists(_marker())


def restore():
    """Возвращает оригинальный voice_ban.dt. Вызывать, когда CS2 закрыта."""
    try:
        with open(_marker(), encoding="utf-8") as f:
            path = json.load(f)["path"]
    except Exception:
        return False
    try:
        if os.path.exists(_backup()):
            shutil.copyfile(_backup(), path)      # копия с новым временем — Steam Cloud увидит её как свежую
            os.remove(_backup())
        os.remove(_marker())
        return True
    except Exception:
        return False
