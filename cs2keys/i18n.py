# -*- coding: utf-8 -*-
"""Русский / английский интерфейс. Исходные строки — русские, перевод подставляется при показе."""
import re

LANG = "ru"

EN = {
    # --- стартовый экран ---
    "Нажатия игрока из демо — поверх игры и синхронно с ней": "A player's inputs from a demo — on top of the game, in sync",
    "Открыть демо": "Open demo",
    "Файл клавиатуры…": "Keyboard file…",
    "НЕДАВНИЕ": "RECENT",
    "или перетащите файл .dem в это окно": "or drop a .dem file into this window",
    "Отпустите, чтобы открыть демо": "Release to open the demo",
    "Удалить демо": "Delete demo",
    "Удалить демо?": "Delete this demo?",
    "«Убрать из списка» — файл останется на диске.\n«Удалить файл» — демо отправится в корзину Windows.":
        "“Remove from list” keeps the file on disk.\n“Delete file” moves the demo to the Recycle Bin.",
    "Удалить файл": "Delete file",
    "Убрать из списка": "Remove from list",
    "Отмена": "Cancel",
    "Не удалось удалить файл — возможно, он открыт в CS2.": "Could not delete the file — it may be open in CS2.",
    "Это сжатое демо FACEIT (.dem.zst). Распакуйте его в .dem (WinRAR или 7-Zip ZS) и перетащите ещё раз.":
        "This is a compressed FACEIT demo (.dem.zst). Extract it to .dem (WinRAR or 7-Zip ZS) and drop it again.",
    "Перетащите файл демо .dem или файл клавиатуры .cs2keys.": "Drop a .dem demo or a .cs2keys keyboard file.",
    "Начали за КТ": "Started as CT",
    "Начали за Т": "Started as T",
    "Демо": "Demo",
    "Читаю демо…": "Reading demo…",
    "Выберите игрока — нажатия извлекутся автоматически": "Pick a player — inputs are extracted automatically",
    # --- экран просмотра ---
    "CS2 подключена": "CS2 connected",
    "CS2 не подключена": "CS2 not connected",
    "Скорость": "Speed",
    "CS2 и управление": "CS2 & controls",
    "Проверить связь": "Test connection",
    "Загрузить демо в CS2": "Load demo in CS2",
    "Камера на игрока": "Spectate player",
    "Следовать за управлением в CS2": "Follow in-game demo controls",
    "Бинды на цифровом блоке": "Numpad binds",
    "вернуть мои": "restore mine",
    "5 пауза · + ×4 · − ×0.5 · Enter ×1 · 4/6 раунды · 0 камера\n"
    "F6 камера · F7 пауза · F8 синхронизация · F5/F9 раунды · F10 ×0.5 · F11 ×4":
        "5 pause · + ×4 · − ×0.5 · Enter ×1 · 4/6 rounds · 0 camera\n"
        "F6 camera · F7 pause · F8 resync · F5/F9 rounds · F10 ×0.5 · F11 ×4",
    "Голос и чат (FACEIT)": "Voice & chat (FACEIT)",
    "Чат игроков": "Player chat",
    "Панель «кто говорит»": "“Who's talking” panel",
    "Клавиатура поверх игры": "Keyboard overlay",
    "Показывать": "Show",
    "Прозрачный фон": "Transparent background",
    "Режим перемещения": "Move mode",
    "Найти на экране": "Find on screen",
    "Размер": "Size",
    "Прозрачность": "Opacity",
    "Двигать": "Move",
    "клавиатуру": "keyboard",
    "панель голоса": "voice panel",
    "✥  Зажмите и тащите": "✥  Hold and drag",
    "колесо мыши — размер": "mouse wheel — size",
    "Точная настройка": "Fine tuning",
    "Поправка, тиков": "Offset, ticks",
    "1 тик = 1/64 с": "1 tick = 1/64 s",
    "Ждать перемотку, с": "Seek wait, s",
    "если CS2 не успевает": "if CS2 lags behind",
    "Порт консоли": "Console port",
    "как в -netconport": "same as -netconport",
    "Сохранить файл клавиатуры…": "Save keyboard file…",
    "Консоль CS2": "CS2 console",
    "точные нажатия": "exact inputs",
    "приблизительные нажатия": "approximate inputs",
    "Загрузите демо в CS2, выберите раунд и нажмите ▶.": "Load the demo in CS2, pick a round and press ▶.",
    # голос
    "Выкл": "Off", "Все": "All", "Т": "T", "КТ": "CT", "Команда игрока": "Player's team", "Соперники": "Enemies",
    # --- сообщения логики ---
    "Читаю демо… большие файлы — до минуты": "Reading demo… large files take up to a minute",
    "Это не файл клавиатуры CS2 Demo to Keyboard.": "This is not a keyboard file.",
    "CS2 не подключена: клавиатура играет без игры.": "CS2 not connected: the keyboard plays on its own.",
    "CS2 не выполняет команды (нет ответа на проверку)": "CS2 doesn't execute commands (no reply to the check)",
    "Демо и клавиатура стартовали вместе.": "Demo and keyboard started together.",
    "Догоняю CS2 после перемотки в игре.": "Catching up with CS2 after an in-game seek.",
    "Пауза из CS2.": "Paused from CS2.",
    "Воспроизведение из CS2.": "Playing from CS2.",
    "Пауза в игре и в клавиатуре.": "Paused in game and keyboard.",
    "Продолжаем синхронно.": "Resumed in sync.",
    "Это последний раунд.": "This is the last round.",
    "Демо загружается в CS2. Когда пойдёт, нажмите «Играть».": "The demo is loading in CS2. Press play once it runs.",
    "CS2 не отвечает на команды.": "CS2 doesn't respond to commands.",
    "Связь есть: CS2 выполняет команды.": "Connected: CS2 executes commands.",
    "ищу…": "searching…",
    "Бинды для демо прописаны в CS2 (цифровой блок). Старые вернутся при выходе.":
        "Demo binds set in CS2 (numpad). Your old binds come back on exit.",
    "Возвращать нечего: программа ничего не меняла.": "Nothing to restore: no binds were changed.",
    "Ваши прежние бинды возвращены.": "Your previous binds are restored.",
    "Не удалось вернуть бинды (CS2 не подключена?). Попробую при следующем подключении.":
        "Couldn't restore binds (CS2 not connected?). Will retry on next connection.",
    "Клавиатура захвачена — тащите.": "Keyboard grabbed — drag it.",
    "Сначала извлеките нажатия игрока — клавиатура появится после этого.":
        "Extract a player's inputs first — the keyboard appears after that.",
    "Клавиатура в центре экрана. Тащите за любое место, размер — за зелёный уголок, потом снимите «Переместить».":
        "The keyboard is in the center. Drag it anywhere, resize by the green corner, then turn off move mode.",
    "Выберите игрока в списке.": "Pick a player in the list.",
    "Готово. Загрузите демо в CS2, затем выберите раунд и нажмите «Играть».":
        "Ready. Load the demo in CS2, pick a round and press play.",
    # файлы и диалоги
    "Демо CS2": "CS2 demo", "Все файлы": "All files", "Файл клавиатуры": "Keyboard file",
    "Клавиатура CS2 Demo to Keyboard": "CS2 Demo to Keyboard file", "Сохранить клавиатуру": "Save keyboard",
    # --- запуск CS2 ---
    "Запустить CS2 и демо": "Launch CS2 & demo",
    "Запускаю…": "Launching…",
    "Программа сама запустит игру с параметрами для демо": "The app launches the game with demo parameters for you",
    "Проверяю, запущена ли CS2…": "Checking whether CS2 is running…",
    "CS2 запущена без нужных параметров": "CS2 is running without demo parameters",
    "Чтобы смотреть демо синхронно, CS2 нужно перезапустить с параметрами для демо. Перезапустить сейчас?":
        "To watch the demo in sync, CS2 has to be restarted with demo parameters. Restart now?",
    "Перезапустить": "Restart",
    "Запуск отменён.": "Launch cancelled.",
    "CS2 запущена, загружаю демо…": "CS2 is up, loading the demo…",
    "Закрываю CS2…": "Closing CS2…",
    "Запускаю CS2 с параметрами для демо…": "Launching CS2 with demo parameters…",
    "Жду CS2… Если открылось окно Workshop Tools, нажмите в нём «Launch Tools».":
        "Waiting for CS2… If the Workshop Tools window opened, click “Launch Tools”.",
    "Где находится cs2.exe?": "Where is cs2.exe?",
    "не удалось закрыть CS2 — закройте её вручную и нажмите ещё раз":
        "could not close CS2 — close it manually and press again",
    "CS2 не открыла консольный порт — проверьте, что игра запустилась":
        "CS2 did not open the console port — check that the game started",
    "Запускать CS2 через Workshop Tools (нужно для консоли на Windows)":
        "Launch CS2 via Workshop Tools (needed for the console on Windows)",
    "Закрыть CS2, запущенную для просмотра демо?\nВ этом режиме игра не пускает в матчмейкинг — для обычной игры её нужно перезапустить.":
        "Close CS2 that was launched for demo viewing?\nIn this mode matchmaking is unavailable — restart the game to play normally.",
    "Закрыть": "Close",
    # --- настройка клавиш ---
    "Настройка клавиш": "Key settings",
    "Нажмите на клавишу справа и затем новую клавишу. Esc — отмена.":
        "Click a key on the right, then press the new key. Esc cancels.",
    "нажмите клавишу…": "press a key…",
    "Поверх игры": "Over the game",
    "Работают, даже когда активно окно CS2": "Work even while the CS2 window is active",
    "Бинды в CS2": "CS2 binds",
    "Прописываются в игру при включённом переключателе «Бинды»": "Written into the game when “Numpad binds” is on",
    "По умолчанию": "Defaults",
    "Сохранить": "Save",
    "Клавиши сохранены.": "Keys saved.",
    "В CS2": "In CS2",
    "Пауза / продолжить": "Pause / resume", "Пересинхронизировать": "Resync",
    "Раунд назад": "Previous round", "Раунд вперёд": "Next round",
    "Замедление ×0.5": "Slow down ×0.5", "Ускорение ×4": "Speed up ×4", "Обычная скорость ×1": "Normal speed ×1",
    "пауза": "pause", "синхронизация": "resync", "камера": "camera", "раунд назад": "prev round",
    "раунд вперёд": "next round",
    # --- оверлей ---
    "Пробел": "Space",
    "мёртв": "dead",
    "Перетащите  •  уголок — размер": "Drag  •  corner to resize",
    "Панель голоса": "Voice panel",
    "прыжок": "jump", "выстрел": "shot", "примерно": "approx.",
    "Дым": "Smoke", "Флешка": "Flash", "HE": "HE", "Молотов": "Molotov", "Зажигательная": "Incendiary",
    "Декой": "Decoy", "Дымовая": "Smoke Grenade", "Осколочная": "HE Grenade", "Бомба C4": "C4",
    # --- версия ---
    "Версия {v}": "Version {v}",
    "Поддержать автора": "Support the author",
}

# строки с подставленными значениями: (шаблон, замена)
PATTERNS = [
    (r"(.+)   ·   раундов (.+)   ·   (.+)", r"\1   ·   \2 rounds   ·   \3"),
    (r"Извлекаю нажатия (.+)… около минуты", r"Extracting \1's inputs… about a minute"),
    (r"Извлекаю нажатия (.+)…", r"Extracting \1's inputs…"),
    (r"Не удалось прочитать демо:\n(.*)", r"Could not read the demo:\n\1"),
    (r"Не удалось извлечь нажатия:\n(.*)", r"Could not extract inputs:\n\1"),
    (r"Демо (.+) не найдено по сохранённому пути\.\n.*", r"Demo \1 was not found at its saved path.\n"
     r"The keyboard will open, but the demo has to be loaded in CS2 manually (playdemo)."),
    (r"Сохранено: (.+)", r"Saved: \1"),
    (r"Камера на (.+) \(F6\)", r"Spectate \1 (F6)"),
    (r"Камера на (.+)\.", r"Camera on \1."),
    (r"Камера на (.+)", r"Spectate \1"),
    (r"Раунд (\d+)   тик (\d+)", r"Round \1   tick \2"),
    (r"Раунд (\d+)", r"Round \1"),
    (r"Автопропуск: раунд (\d+)", r"Auto-skip: round \1"),
    (r"Синхронизация: CS2 перематывает, ждём (.+) с…", r"Syncing: CS2 is seeking, waiting \1 s…"),
    (r"CS2 ответила: (.+)", r"CS2 replied: \1"),
    (r"Ошибка: (.+)", r"Error: \1"),
    (r"CS2 сменила скорость: ×(.+)", r"CS2 changed speed: ×\1"),
    (r"Скорость ×(.+)", r"Speed ×\1"),
    (r"CS2 не найдена: (.+)", r"CS2 not found: \1"),
    (r"Голос: (.+)", r"Voice: \1"),
    (r"Не удалось прописать бинды: (.+)", r"Could not set binds: \1"),
    (r"Запускаю CS2… (\d+) с", r"Launching CS2… \1 s"),
    (r"Заняты другой программой: (.+)", r"Taken by another program: \1"),
    (r"порт (\d+) закрыт: запустите CS2 через Workshop Tools с -netconport (\d+)",
     r"port \1 is closed: start CS2 via Workshop Tools with -netconport \2"),
    (r"порт (\d+) не отвечает", r"port \1 does not respond"),
    (r"Не удалось узнать, что раньше было на клавишах: (.+)\.\n.*",
     r"Could not read your old binds for: \1.\nDemo binds stay on them — rebind in CS2 settings if needed."),
]


def set_lang(lang):
    global LANG
    LANG = "en" if lang == "en" else "ru"


def tr(s):
    """Перевод строки для показа. В русском режиме возвращает как есть."""
    if LANG == "ru" or not isinstance(s, str) or not s:
        return s
    if s in EN:
        return EN[s]
    for pat, rep in PATTERNS:
        m = re.fullmatch(pat, s, flags=re.S)
        if m:
            if pat.startswith("Голос"):
                return "Voice: " + tr(m.group(1))
            if pat.startswith("Ошибка"):
                return "Error: " + tr(m.group(1))
            return m.expand(rep)
    if "   " in s:                                # склеенные метки («прыжок   Флешка»)
        return "   ".join(tr(p) for p in s.split("   "))
    return s


def install():
    """Переводит заголовки и тексты стандартных окон tkinter (сообщения, выбор файла)."""
    from tkinter import messagebox, filedialog
    if getattr(messagebox, "_i18n", False):
        return

    def wrap_msg(fn):
        def w(title=None, message=None, **kw):
            return fn(tr(title), tr(message), **kw)
        return w

    def wrap_dlg(fn):
        def w(**kw):
            if "title" in kw:
                kw["title"] = tr(kw["title"])
            if "filetypes" in kw:
                kw["filetypes"] = [(tr(a), b) for a, b in kw["filetypes"]]
            return fn(**kw)
        return w
    for name in ("showinfo", "showerror", "showwarning", "askyesno"):
        setattr(messagebox, name, wrap_msg(getattr(messagebox, name)))
    for name in ("askopenfilename", "asksaveasfilename"):
        setattr(filedialog, name, wrap_dlg(getattr(filedialog, name)))
    messagebox._i18n = True
