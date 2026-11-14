# -*- coding: utf-8 -*-
"""Аватарки игроков из открытого профиля Steam (без ключа API): steamcommunity.com/profiles/<id>?xml=1.

Скачиваются в фоне и кэшируются в %APPDATA%/CS2Keys/avatars. Если интернета нет или профиль закрыт —
просто нет аватарки, панель рисует букву ника."""
import os
import re
import threading
import urllib.request

from PIL import Image

_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "CS2Keys", "avatars")
_mem = {}            # steamid -> Image | None (None — не получилось)
_pending = set()
_lock = threading.Lock()
UA = "Mozilla/5.0 (CS2 Demo to Keyboard)"


def _path(sid):
    return os.path.join(_DIR, f"{sid}.png")


def get(sid):
    """Аватарка (RGBA 64×64) или None. Если её ещё нет — запускает скачивание в фоне."""
    sid = str(sid or "")
    if not sid.isdigit():
        return None
    with _lock:
        if sid in _mem:
            return _mem[sid]
    p = _path(sid)
    if not os.path.exists(p):
        p = _steam_cache(sid) or p
    if os.path.exists(p):
        try:
            im = Image.open(p).convert("RGBA")
            with _lock:
                _mem[sid] = im
            return im
        except Exception:
            pass
    with _lock:
        if sid in _pending:
            return None
        _pending.add(sid)
    threading.Thread(target=_fetch, args=(sid,), daemon=True).start()
    return None


def _steam_dir():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            return winreg.QueryValueEx(k, "SteamPath")[0]
    except Exception:
        return None


def _steam_cache(sid):
    """Аватарка из кэша самого Steam (config/avatarcache) — есть для друзей и тех, кого Steam уже показывал."""
    d = _steam_dir()
    if not d:
        return None
    p = os.path.join(d, "config", "avatarcache", f"{sid}.png")
    return p if os.path.exists(p) else None


def pending():
    with _lock:
        return bool(_pending)


def _fetch(sid):
    im = None
    try:
        req = urllib.request.Request(f"https://steamcommunity.com/profiles/{sid}?xml=1", headers={"User-Agent": UA})
        xml = urllib.request.urlopen(req, timeout=8).read().decode("utf-8", "replace")
        m = re.search(r"<avatarMedium><!\[CDATA\[(.*?)\]\]>", xml) or re.search(r"<avatarFull><!\[CDATA\[(.*?)\]\]>", xml)
        if m and m.group(1).startswith("https://"):
            req = urllib.request.Request(m.group(1), headers={"User-Agent": UA})
            raw = urllib.request.urlopen(req, timeout=8).read()
            import io
            im = Image.open(io.BytesIO(raw)).convert("RGBA").resize((64, 64), Image.LANCZOS)
            try:
                os.makedirs(_DIR, exist_ok=True)
                im.save(_path(sid))
            except Exception:
                pass
    except Exception:
        im = None
    with _lock:
        _mem[sid] = im
        _pending.discard(sid)
