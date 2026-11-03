# -*- coding: utf-8 -*-
"""Коды ошибок с подсказками и отчёт для автора («Скопировать отчёт»).

Отчёт собирается только на компьютере пользователя и никуда не отправляется: его копируют
в буфер обмена и сами присылают автору. Пути к папке пользователя в отчёте заменяются на %USERPROFILE%."""
import os
import platform
import re
import subprocess
import time

from .version import VERSION

NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# код -> (заголовок, подсказки)
CODES = {
    "E101": ("Steam не запущен",
             ["Откройте Steam и войдите в аккаунт.",
              "Потом снова нажмите «Запустить CS2 и демо»."]),
    "E102": ("Не удалось закрыть CS2",
             ["Закройте CS2 вручную: Диспетчер задач (Ctrl+Shift+Esc) → cs2.exe → «Снять задачу».",
              "Потом снова нажмите «Запустить CS2 и демо»."]),
    "E103": ("CS2 закрылась во время запуска",
             ["Steam → CS2 → Свойства → Установленные файлы → «Проверить целостность файлов».",
              "Проверьте, что Counter-Strike 2 Workshop Tools установлены и обновлены (Свойства → Дополнительный контент).",
              "Попробуйте выключить «Запускать CS2 через Workshop Tools» в настройках программы.",
              "Обновите драйвер видеокарты и закройте оверлеи (MSI Afterburner / RivaTuner, Discord)."]),
    "E104": ("CS2 закрылась во время загрузки демо",
             ["Откройте эту демку без программы (консоль CS2: playdemo). Если вылетает и так — демка "
              "повреждена или записана на старой версии CS2: после крупных обновлений старые демки не открываются.",
              "Демо FACEIT: проверьте, что архив .dem.zst распакован полностью, или скачайте его заново.",
              "Попробуйте выключить «Запускать CS2 через Workshop Tools» в настройках программы.",
              "Проверьте целостность файлов CS2 в Steam."]),
    "E105": ("CS2 закрылась во время просмотра",
             ["Запустите демо ещё раз — разовые вылеты CS2 бывают и без программы.",
              "Обновите драйвер видеокарты и закройте оверлеи (MSI Afterburner / RivaTuner, Discord).",
              "Попробуйте выключить «Запускать CS2 через Workshop Tools» в настройках программы."]),
    "E106": ("CS2 не ответила программе",
             ["Если открылось окно Workshop Tools — нажмите в нём «Launch Tools».",
              "Проверьте, что Counter-Strike 2 Workshop Tools установлены.",
              "Порт консоли может быть занят другой программой — смените его в настройках (например, 2122)."]),
    "E107": ("CS2 не смогла открыть демо",
             ["Проверьте, что файл демо на месте и не переименован.",
              "Откройте демку без программы (консоль CS2: playdemo), чтобы проверить, открывается ли она вообще.",
              "Старые демки после крупных обновлений CS2 часто не открываются."]),
    "E201": ("Не удалось прочитать демо",
             ["Проверьте, что это демо CS2 (.dem), а не CS:GO.",
              "Демо FACEIT сначала распакуйте из .dem.zst (7-Zip).",
              "Если файл скачался не полностью — скачайте его заново."]),
    "E202": ("Не удалось извлечь нажатия игрока",
             ["Попробуйте выбрать другого игрока.",
              "Если ошибка повторяется на этой демке — пришлите отчёт автору."]),
}

# подсказка по имени модуля, в котором упала CS2 (из журнала Windows)
MODULE_HINTS = [
    (("nvwgf2um", "nvlddmkm", "nvgpucomp", "nvoglv"), "сбой видеодрайвера NVIDIA — обновите или переустановите драйвер"),
    (("atiumd", "amdxx", "amdvlk", "atidxx", "atig6"), "сбой видеодрайвера AMD — обновите или переустановите драйвер"),
    (("igd", "igxelp", "igc64", "intelocl"), "сбой видеодрайвера Intel — обновите драйвер"),
    (("discord",), "оверлей Discord — выключите его для CS2"),
    (("rtsshooks", "rtss"), "RivaTuner / MSI Afterburner — закройте их"),
    (("gameoverlayrenderer",), "оверлей Steam — выключите его в свойствах CS2"),
    (("obs", "graphics-hook"), "захват OBS — попробуйте без него"),
    (("tools", "toolframework", "vconsole"), "Workshop Tools — выключите «Запускать CS2 через Workshop Tools»"),
    (("kernelbase", "ntdll"), "системный модуль Windows — проверьте целостность файлов CS2 и обновите Windows"),
]


def title(code):
    return CODES.get(code, ("Ошибка", []))[0]


def hints(code):
    return list(CODES.get(code, ("", []))[1])


def _hide_user(text):
    text = re.sub(r"(?i)([a-z]:[\\/]+users[\\/]+)[^\\/\r\n:*?\"<>|]+", "%USERPROFILE%", text)
    home = os.path.expanduser("~")
    if home and len(home) > 3:
        text = re.sub(re.escape(home), "%USERPROFILE%", text, flags=re.I)
        text = re.sub(re.escape(home.replace("\\", "/")), "%USERPROFILE%", text, flags=re.I)
    return text


def _decode(raw):
    for enc in ("utf-8",):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    try:
        import ctypes
        return raw.decode(f"cp{ctypes.windll.kernel32.GetOEMCP()}", errors="replace")
    except Exception:
        return raw.decode("cp866", errors="replace")


def windows_crash(minutes=30):
    """Последние записи журнала Windows о вылете cs2.exe: (текст, подсказка) или (None, None)."""
    if os.name != "nt":
        return None, None
    q = ("*[System[(Provider[@Name='Application Error'] or Provider[@Name='Application Hang']) "
         f"and TimeCreated[timediff(@SystemTime) <= {int(minutes * 60000)}]]]")
    try:
        raw = subprocess.run(["wevtutil", "qe", "Application", f"/q:{q}", "/c:6", "/rd:true", "/f:text"],
                             capture_output=True, creationflags=NO_WINDOW, timeout=8).stdout
    except Exception:
        return None, None
    text = _decode(raw or b"")
    blocks = [b for b in re.split(r"(?m)^Event\[\d+\]", text) if "cs2.exe" in b.lower()]
    if not blocks:
        return None, None
    b = blocks[0]
    lines = [ln.strip() for ln in b.splitlines() if ln.strip()]
    keep = [ln for ln in lines if re.match(r"(?i)(date|дата|source|источник)", ln)]
    desc = False
    for ln in lines:
        if re.match(r"(?i)^description:", ln):
            desc = True
            continue
        if desc:
            keep.append(ln)
    keep = keep[:16]
    low = b.lower()
    hint = None
    m = re.search(r"(?im)(?:faulting module name|имя сбойного модуля)\s*:\s*([^,\r\n]+)", b)
    mod = (m.group(1).strip().lower() if m else low)
    for keys, h in MODULE_HINTS:
        if any(k in mod for k in keys):
            hint = h
            break
    return _hide_user("\n".join(keep)), hint


def console_tail(cs2_exe, n=40):
    """Последние строки консоли CS2 (её пишет параметр -condebug в game/csgo/console.log)."""
    if not cs2_exe:
        return None
    game = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(cs2_exe))))   # …/game
    path = os.path.join(game, "csgo", "console.log")
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 64 * 1024))
            data = f.read().decode("utf-8", errors="replace")
        age = time.time() - os.path.getmtime(path)
    except Exception:
        return None
    lines = [ln.rstrip() for ln in data.splitlines() if ln.strip()][-n:]
    head = f"(console.log обновлён {int(age // 60)} мин назад)"
    return _hide_user(head + "\n" + "\n".join(lines))


def build_report(code, detail="", context=None, cs2_exe=None, history=None):
    """Текст отчёта для автора. context — словарь «что происходило»."""
    out = [f"CS2 Demo to Keyboard {VERSION} — отчёт об ошибке",
           f"Код: {code} — {title(code)}",
           f"Время: {time.strftime('%Y-%m-%d %H:%M:%S')}",
           f"Windows: {platform.platform()}"]
    if detail:
        out.append(f"Подробности: {detail}")
    for k, v in (context or {}).items():
        out.append(f"{k}: {v}")
    crash, hint = (None, None)
    if code in ("E103", "E104", "E105"):
        crash, hint = windows_crash()
        out.append("")
        out.append("Журнал Windows (вылет cs2.exe):")
        out.append(crash or "записей о вылете cs2.exe за последние 30 минут нет")
        if hint:
            out.append(f"Возможная причина: {hint}")
    if history:
        out.append("")
        out.append("Последние шаги программы:")
        out += [f"  {h}" for h in history[-15:]]
    tail = console_tail(cs2_exe)
    if tail:
        out.append("")
        out.append("Консоль CS2 (последние строки):")
        out.append(tail)
    return _hide_user("\n".join(out)), hint


class CodedError(Exception):
    """Ошибка с кодом из CODES."""

    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {title(code)}" + (f" ({detail})" if detail else ""))
        self.code, self.detail = code, detail
