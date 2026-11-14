# -*- coding: utf-8 -*-
"""Поиск CS2, проверка запуска, закрытие и запуск с параметрами для демо.
Параметры передаются только в этот запуск — в свойствах Steam ничего не меняется."""
import os
import re
import subprocess
import time

IS_WIN = os.name == "nt"
REL_EXE = os.path.join("steamapps", "common", "Counter-Strike Global Offensive", "game", "bin", "win64", "cs2.exe")
NO_WINDOW = 0x08000000 if IS_WIN else 0


def steam_path():
    if not IS_WIN:
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            return winreg.QueryValueEx(k, "SteamPath")[0].replace("/", "\\")
    except OSError:
        return None


def library_folders(steam):
    """Все библиотеки Steam из libraryfolders.vdf; первой — та, где стоит CS2 (приложение 730)."""
    libs, with_cs2 = [steam], []
    vdf = os.path.join(steam, "steamapps", "libraryfolders.vdf")
    try:
        text = open(vdf, encoding="utf-8", errors="replace").read()
        for block in re.split(r'\n\s*"\d+"\s*\n', text)[1:]:
            m = re.search(r'"path"\s*"([^"]+)"', block)
            if not m:
                continue
            p = m.group(1).replace("\\\\", "\\")
            libs.append(p)
            if re.search(r'"730"\s*"', block):
                with_cs2.append(p)
    except OSError:
        pass
    seen, out = set(), []
    for p in with_cs2 + libs:
        if p and p.lower() not in seen:
            seen.add(p.lower())
            out.append(p)
    return out


def find_cs2_exe(saved=None):
    if saved and os.path.isfile(saved):
        return saved
    steam = steam_path()
    cands = library_folders(steam) if steam else []
    cands += [r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam", r"D:\Steam", r"D:\SteamLibrary",
              r"E:\SteamLibrary", r"C:\SteamLibrary"]
    for lib in cands:
        exe = os.path.join(lib, REL_EXE)
        if os.path.isfile(exe):
            return exe
    return None


def find_addon(exe):
    """Любой аддон Workshop Tools, чтобы режим инструментов открылся сразу, без окна выбора."""
    if not exe:
        return None
    game = os.path.dirname(os.path.dirname(os.path.dirname(exe)))          # ...\game
    for base in (os.path.join(game, "csgo_addons"), os.path.join(os.path.dirname(game), "content", "csgo_addons")):
        try:
            names = sorted(n for n in os.listdir(base) if os.path.isdir(os.path.join(base, n)))
        except OSError:
            continue
        if "cs_script_demo" in names:
            return "cs_script_demo"
        if names:
            return names[0]
    return None


def cs2_running():
    if not IS_WIN:
        return False
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq cs2.exe", "/FO", "CSV", "/NH"],
                             capture_output=True, text=True, creationflags=NO_WINDOW, timeout=10).stdout
        return "cs2.exe" in out.lower()
    except Exception:
        return False


def close_cs2(timeout=20.0):
    """Сначала просим закрыться по-хорошему, если не вышло — завершаем принудительно."""
    if not IS_WIN:
        return True
    try:
        subprocess.run(["taskkill", "/IM", "cs2.exe"], capture_output=True, creationflags=NO_WINDOW, timeout=10)
    except Exception:
        pass
    end = time.time() + timeout
    while time.time() < end:
        if not cs2_running():
            return True
        time.sleep(0.5)
    try:
        subprocess.run(["taskkill", "/F", "/IM", "cs2.exe"], capture_output=True, creationflags=NO_WINDOW, timeout=10)
    except Exception:
        pass
    time.sleep(2)
    return not cs2_running()


def steam_ready():
    """Steam запущен и пользователь вошёл (Steam пишет ActiveUser в реестр)."""
    if not IS_WIN:
        return True
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam\ActiveProcess") as k:
            pid = int(winreg.QueryValueEx(k, "pid")[0] or 0)
            user = int(winreg.QueryValueEx(k, "ActiveUser")[0] or 0)
    except Exception:
        return False
    if not pid or not user:
        return False
    try:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                             capture_output=True, text=True, creationflags=NO_WINDOW, timeout=10).stdout
        return "steam.exe" in out.lower()
    except Exception:
        return True


def ensure_steam(progress=None, timeout=180):
    """Если Steam не запущен — запускаем его и ждём входа в аккаунт. Без Steam CS2 не стартует."""
    if steam_ready():
        return True
    steam = steam_path()
    exe = os.path.join(steam, "steam.exe") if steam else None
    try:
        if exe and os.path.exists(exe):
            subprocess.Popen([exe, "-silent"], cwd=steam)
        else:
            os.startfile("steam://open/main")
    except Exception:
        return False
    start = time.time()
    while time.time() - start < timeout:
        if steam_ready():
            time.sleep(5)                      # даём Steam догрузиться после входа
            return True
        if progress:
            progress(int(time.time() - start))
        time.sleep(2)
    return False


def launch_cs2(exe, port=2121, tools=True):
    """Запуск CS2 для просмотра демо. Steam должен быть запущен (см. ensure_steam)."""
    args = [exe]
    if tools:
        args.append("-tools")
        addon = find_addon(exe)
        if addon:
            args += ["-addon", addon]
    # -condebug: CS2 пишет свою консоль в game/csgo/console.log — по нему видно, на чём она упала
    args += ["-netconport", str(int(port)), "-insecure", "-novid", "-condebug"]
    return subprocess.Popen(args, cwd=os.path.dirname(exe))


def console_log_path(cs2_exe):
    """…/game/bin/win64/cs2.exe → …/game/csgo/console.log (его пишет параметр -condebug)."""
    game = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(cs2_exe))))
    return os.path.join(game, "csgo", "console.log")
