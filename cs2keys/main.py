# -*- coding: utf-8 -*-
"""CS2 Keys — клавиатура игрока из демо поверх CS2 с синхронным воспроизведением."""
import bisect, json, os, queue, re, sys, threading, time, traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from concurrent.futures import ProcessPoolExecutor

from . import extract, launcher
from .netcon import Netcon
from .overlay import Overlay, VoicePanel
from .i18n import tr, set_lang, install as install_i18n

APP = "CS2 Demo to Keyboard"
TPS = 64
BG, PANEL, LINE, INK, MUTED = "#E6DAC2", "#D8C9AA", "#BFAB86", "#23262B", "#6F634C"
GO, LOSS = "#1FAE52", "#B5452F"
DATA_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "CS2Keys")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
SETTINGS = os.path.join(DATA_DIR, "settings.json")
DEFAULTS = {"port": 2121, "offset": 0, "wait": 3.0, "speed": 1.0, "scale": 1.0, "alpha": 0.95,
            "overlay_pos": [80, 80], "overlay_on": True, "overlay_transparent": True, "follow": True, "binds_on": True, "saved_binds": {}, "voice": "off", "chat": False, "vpanel_on": True, "vpanel_pos": [80, 420], "vpanel_scale": 1.0,
            "move_target": "kb", "lang": "ru", "hotkeys": {}, "cs2_keys": {}, "cs2_exe": "", "use_tools": True,
            "last_dir": ""}
# бинды, которые программа прописывает в CS2 при подключении (и возвращает старые при выходе)
DEMO_BINDS = [("KP_5", "demo_togglepause", "пауза"),
              ("KP_PLUS", "demo_timescale 4", "×4"),
              ("KP_MINUS", "demo_timescale 0.5", "×0.5"),
              ("KP_ENTER", "demo_timescale 1", "×1"),
              ("KP_LEFTARROW", "echo CS2KEYS:prev_round", "раунд назад"),
              ("KP_RIGHTARROW", "echo CS2KEYS:next_round", "раунд вперёд"),
              ("KP_INS", "echo CS2KEYS:camera", "камера на игрока")]
UNKNOWN = "__unknown__"
VOICE_MODES = [("off", "Выкл"), ("all", "Все"), ("t", "Т"), ("ct", "КТ"),
               ("mine", "Команда игрока"), ("enemy", "Соперники")]
# --- настраиваемые клавиши (значения по умолчанию) ---
# горячие клавиши программы: действие -> (подпись, код клавиши Windows, модификаторы, название)
HOTKEY_ACTIONS = [("toggle", "Пауза / продолжить"), ("resync", "Пересинхронизировать"),
                  ("camera", "Камера на игрока"), ("prev_round", "Раунд назад"), ("next_round", "Раунд вперёд"),
                  ("slow", "Замедление ×0.5"), ("fast", "Ускорение ×4")]
DEFAULT_HOTKEYS = {"camera": [0x75, 0, "F6"], "toggle": [0x76, 0, "F7"], "resync": [0x77, 0, "F8"],
                   "prev_round": [0x74, 0, "F5"], "next_round": [0x78, 0, "F9"],
                   "slow": [0x79, 0, "F10"], "fast": [0x7A, 0, "F11"]}
# бинды в самой CS2: действие -> (подпись, консольная команда)
CS2_ACTIONS = [("pause", "Пауза / продолжить", "demo_togglepause"),
               ("fast", "Ускорение ×4", "demo_timescale 4"),
               ("slow", "Замедление ×0.5", "demo_timescale 0.5"),
               ("normal", "Обычная скорость ×1", "demo_timescale 1"),
               ("prev_round", "Раунд назад", "echo CS2KEYS:prev_round"),
               ("next_round", "Раунд вперёд", "echo CS2KEYS:next_round"),
               ("camera", "Камера на игрока", "echo CS2KEYS:camera")]
DEFAULT_CS2_KEYS = {"pause": "KP_5", "fast": "KP_PLUS", "slow": "KP_MINUS", "normal": "KP_ENTER",
                    "prev_round": "KP_LEFTARROW", "next_round": "KP_RIGHTARROW", "camera": "KP_INS"}
HOTKEYS = {1: (0x75, "F6", "camera"), 2: (0x76, "F7", "toggle"), 3: (0x77, "F8", "resync"),
           4: (0x74, "F5", "prev_round"), 5: (0x78, "F9", "next_round"),
           6: (0x79, "F10", "slow"), 7: (0x7A, "F11", "fast")}
WEAPON_RU = {"Smoke Grenade": "Дымовая", "High Explosive Grenade": "Осколочная", "Flashbang": "Флешка",
             "Molotov": "Молотов", "Incendiary Grenade": "Зажигательная", "Decoy Grenade": "Декой",
             "C4 Explosive": "Бомба C4"}


def load_settings():
    s = dict(DEFAULTS)
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            s.update(json.load(f))
    except Exception:
        pass
    if s.get("move_target") not in ("kb", "voice"):
        s["move_target"] = "kb"
    return s


def save_settings(s):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(SETTINGS, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def fmt(sec):
    neg = sec < 0
    sec = abs(sec)
    m = int(sec // 60)
    return ("−" if neg else "") + f"{m}:{sec - m * 60:05.2f}"


def _quiet():
    # в фоновом процессе без консоли (pythonw) печать некуда выводить
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")


def _scan_job(path):
    _quiet()
    return extract.scan(path)


def _extract_job(path, steamid, info):
    _quiet()
    return extract.extract_player(path, steamid, info)


class App:
    def __init__(self, root):
        self.root = root
        self.s = load_settings()
        self.ui_q = queue.Queue()
        self.pool = ProcessPoolExecutor(max_workers=1)
        self.net = Netcon(int(self.s["port"]))
        self.info = None          # обзор демо
        self.data = None          # нажатия выбранного игрока
        self.tick = 0.0
        self.playing = False
        self.syncing = False
        self.clean = False        # после паузы позицию не меняли
        self.cs_tick = None
        self.seek_job = None
        self.last_t = time.perf_counter()
        self.overlay = None
        self.vpanel = None
        self._scale_busy = False
        self.round_btns = []
        self.last_probe = None          # (игровой тик, время) последнего замера во время игры
        self.net.on_event = lambda kind, gt, ts: self.ui(lambda: self._cs_event(kind, gt, ts))
        self._build()
        self._start_hotkeys()
        self.root.after(1500, self._probe)
        self.root.after(10, self._loop)
        self.root.after(500, self._poll_cs2)
        self.root.protocol("WM_DELETE_WINDOW", self._quit)

    # ================= интерфейс =================
    def _build(self):
        r = self.root
        r.title(APP)
        r.configure(bg=BG)
        r.minsize(760, 620)
        st = ttk.Style(r)
        st.theme_use("clam")
        base = ("Segoe UI", 10)
        st.configure(".", background=BG, foreground=INK, font=base, fieldbackground="#F3ECDD")
        st.configure("TLabelframe", background=BG, bordercolor=LINE)
        st.configure("TLabelframe.Label", background=BG, foreground=INK, font=("Segoe UI", 10, "bold"))
        st.configure("TButton", background=PANEL, bordercolor=LINE, padding=(10, 5))
        st.map("TButton", background=[("active", "#CDBB98"), ("disabled", BG)])
        st.configure("Big.TButton", font=("Segoe UI", 12, "bold"), padding=(16, 8), background=INK, foreground=BG)
        st.map("Big.TButton", background=[("active", "#3a3e45"), ("disabled", "#8a8a8a")])
        st.configure("Muted.TLabel", foreground=MUTED)
        st.configure("Clock.TLabel", font=("Segoe UI", 20, "bold"))
        st.configure("TCheckbutton", background=BG)
        st.configure("Horizontal.TScale", background=BG, troughcolor=PANEL)

        pad = dict(padx=10, pady=6)
        # --- демо ---
        f1 = ttk.LabelFrame(r, text="1. Демо и игрок")
        f1.pack(fill="x", **pad)
        row = ttk.Frame(f1)
        row.pack(fill="x", padx=8, pady=(6, 2))
        ttk.Button(row, text="Открыть демо (.dem)…", command=self.open_demo).pack(side="left")
        ttk.Button(row, text="Открыть файл клавиатуры…", command=self.open_keys).pack(side="left", padx=6)
        self.save_btn = ttk.Button(row, text="Сохранить файл клавиатуры…", command=self.save_keys, state="disabled")
        self.save_btn.pack(side="left")
        self.demo_lbl = ttk.Label(f1, text="Демо не выбрано", style="Muted.TLabel")
        self.demo_lbl.pack(fill="x", padx=8)
        row = ttk.Frame(f1)
        row.pack(fill="x", padx=8, pady=6)
        self.players = tk.Listbox(row, height=5, activestyle="none", bg="#F3ECDD", fg=INK, bd=0,
                                  highlightthickness=1, highlightbackground=LINE, selectbackground=GO,
                                  font=("Segoe UI", 10), exportselection=False)
        self.players.pack(side="left", fill="x", expand=True)
        self.players.bind("<Double-Button-1>", lambda e: self.extract_selected())
        col = ttk.Frame(row)
        col.pack(side="left", padx=(8, 0), anchor="n")
        self.extract_btn = ttk.Button(col, text="Извлечь нажатия", command=self.extract_selected, state="disabled")
        self.extract_btn.pack(fill="x")
        self.prog = ttk.Progressbar(col, mode="indeterminate", length=160)
        self.prog.pack(fill="x", pady=6)
        self.busy_lbl = ttk.Label(col, text="", style="Muted.TLabel", wraplength=180)
        self.busy_lbl.pack(fill="x")

        # --- CS2 ---
        f2 = ttk.LabelFrame(r, text="2. Связь с CS2")
        f2.pack(fill="x", **pad)
        row = ttk.Frame(f2)
        row.pack(fill="x", padx=8, pady=6)
        self.dot = tk.Canvas(row, width=14, height=14, bg=BG, highlightthickness=0)
        self.dot_item = self.dot.create_oval(2, 2, 12, 12, fill=LOSS, outline="")
        self.dot.pack(side="left")
        self.cs_lbl = ttk.Label(row, text="CS2 не подключена")
        self.cs_lbl.pack(side="left", padx=(4, 12))
        ttk.Button(row, text="Проверить связь", command=self.ping).pack(side="left")
        self.load_btn = ttk.Button(row, text="Загрузить демо в CS2", command=self.load_demo, state="disabled")
        self.load_btn.pack(side="left", padx=6)
        self.cam_btn = ttk.Button(row, text="Камера на игрока (F6)", command=self.camera, state="disabled")
        self.cam_btn.pack(side="left")
        self.follow_var = tk.BooleanVar(value=bool(self.s.get("follow", True)))
        ttk.Checkbutton(row, text="Следовать за управлением в CS2", variable=self.follow_var,
                        command=self._follow_changed).pack(side="left", padx=(12, 0))
        row_b = ttk.Frame(f2)
        row_b.pack(fill="x", padx=8, pady=(0, 6))
        self.binds_var = tk.BooleanVar(value=bool(self.s.get("binds_on", True)))
        ttk.Checkbutton(row_b, text="Прописывать бинды в CS2 (цифровой блок):", variable=self.binds_var,
                        command=self._binds_changed).pack(side="left")
        ttk.Label(row_b, text="5 пауза, + ×4, − ×0.5, Enter ×1, 4/6 раунд назад/вперёд, 0 камера",
                  style="Muted.TLabel").pack(side="left", padx=6)
        ttk.Button(row_b, text="Вернуть мои бинды", command=self.restore_binds).pack(side="right")
        row_v = ttk.Frame(f2)
        row_v.pack(fill="x", padx=8, pady=(0, 6))
        ttk.Label(row_v, text="Голос в демо (FACEIT):").pack(side="left")
        self.voice_btns = {}
        for key, label in VOICE_MODES:
            b = tk.Button(row_v, text=label, relief="flat", bd=0, padx=10, pady=3, font=("Segoe UI", 9, "bold"),
                          bg=PANEL, fg=INK, activebackground="#CDBB98", command=lambda k=key: self.set_voice(k))
            b.pack(side="left", padx=2)
            self.voice_btns[key] = b
        self.chat_var = tk.BooleanVar(value=bool(self.s.get("chat", False)))
        ttk.Checkbutton(row_v, text="Чат игроков", variable=self.chat_var,
                        command=self._chat_changed).pack(side="left", padx=(12, 0))
        self._paint_voice()
        ttk.Label(row, text="Порт").pack(side="left", padx=(12, 2))
        self.port_var = tk.IntVar(value=int(self.s["port"]))
        sp = ttk.Spinbox(row, from_=1024, to=65535, width=6, textvariable=self.port_var, command=self._port_changed)
        sp.pack(side="left")
        sp.bind("<FocusOut>", lambda e: self._port_changed())

        # --- воспроизведение ---
        f3 = ttk.LabelFrame(r, text="3. Воспроизведение")
        f3.pack(fill="both", expand=True, **pad)
        self.rounds_fr = tk.Frame(f3, bg=BG)
        self.rounds_fr.pack(fill="x", padx=8, pady=(6, 2))
        row = ttk.Frame(f3)
        row.pack(fill="x", padx=8, pady=6)
        self.play_btn = ttk.Button(row, text="▶  Играть (F7)", style="Big.TButton", command=self.toggle, state="disabled")
        self.play_btn.pack(side="left")
        clk = ttk.Frame(row)
        clk.pack(side="left", padx=14)
        self.clock = ttk.Label(clk, text="0:00.00", style="Clock.TLabel")
        self.clock.pack(anchor="w")
        self.clock_sub = ttk.Label(clk, text="—", style="Muted.TLabel")
        self.clock_sub.pack(anchor="w")
        self.resync_btn = ttk.Button(row, text="Пересинхронизировать (F8)", command=self.play_synced, state="disabled")
        self.resync_btn.pack(side="right")
        row2 = ttk.Frame(f3)
        row2.pack(fill="x", padx=8, pady=(0, 6))
        ttk.Button(row2, text="⏮  Раунд назад (F5)", command=self.prev_round).pack(side="left")
        ttk.Button(row2, text="Раунд вперёд (F9)  ⏭", command=self.next_round).pack(side="left", padx=(6, 18))
        self.speed_btns = {}
        for val, label in ((0.5, "×0.5 (F10)"), (1.0, "×1"), (4.0, "×4 (F11)")):
            b = tk.Button(row2, text=label, relief="flat", bd=0, padx=12, pady=4, font=("Segoe UI", 10, "bold"),
                          bg=PANEL, fg=INK, activebackground="#CDBB98", command=lambda v=val: self.set_speed(v))
            b.pack(side="left", padx=2)
            self.speed_btns[val] = b
        self.timeline = ttk.Scale(f3, from_=0, to=1, orient="horizontal", command=self._timeline_moved)
        self.timeline.pack(fill="x", padx=8)
        row = ttk.Frame(f3)
        row.pack(fill="x", padx=8, pady=6)
        ttk.Label(row, text="Скорость").pack(side="left")
        self.speed_var = tk.StringVar(value=f"×{self.s['speed']:g}")
        cb = ttk.Combobox(row, width=6, state="readonly", textvariable=self.speed_var,
                          values=["×0.1", "×0.25", "×0.5", "×1", "×2", "×4"])
        cb.pack(side="left", padx=(4, 14))
        cb.bind("<<ComboboxSelected>>", lambda e: self._speed_changed())
        ttk.Label(row, text="Поправка, тиков").pack(side="left")
        self.offset_var = tk.IntVar(value=int(self.s["offset"]))
        ttk.Spinbox(row, from_=-640, to=640, width=6, textvariable=self.offset_var,
                    command=self._save_numbers).pack(side="left", padx=(4, 14))
        ttk.Label(row, text="Ждать перемотку, с").pack(side="left")
        self.wait_var = tk.DoubleVar(value=float(self.s["wait"]))
        ttk.Spinbox(row, from_=0.5, to=20, increment=0.5, width=5, textvariable=self.wait_var,
                    command=self._save_numbers).pack(side="left", padx=4)
        self.msg_lbl = ttk.Label(f3, text="Откройте демо и выберите игрока.", style="Muted.TLabel")
        self.msg_lbl.pack(fill="x", padx=8, pady=(0, 4))
        self.log = tk.Text(f3, height=5, bg="#F3ECDD", fg=MUTED, bd=0, font=("Consolas", 9),
                           highlightthickness=1, highlightbackground=LINE, state="disabled")
        self.log.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # --- оверлей ---
        f4 = ttk.LabelFrame(r, text="4. Клавиатура поверх игры")
        f4.pack(fill="x", **pad)
        row = ttk.Frame(f4)
        row.pack(fill="x", padx=8, pady=6)
        self.ov_var = tk.BooleanVar(value=bool(self.s["overlay_on"]))
        ttk.Checkbutton(row, text="Показывать", variable=self.ov_var, command=self._overlay_toggle).pack(side="left")
        self.move_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row, text="Переместить / изменить размер", variable=self.move_var,
                        command=self._overlay_move).pack(side="left", padx=12)
        ttk.Button(row, text="Найти клавиатуру", command=self._overlay_find).pack(side="left", padx=(0, 12))
        self.tr_var = tk.BooleanVar(value=bool(self.s.get("overlay_transparent", True)))
        ttk.Checkbutton(row, text="Прозрачный фон", variable=self.tr_var,
                        command=self._overlay_transparent).pack(side="left", padx=(0, 12))
        self.vp_var = tk.BooleanVar(value=bool(self.s.get("vpanel_on", True)))
        ttk.Checkbutton(row, text="Кто говорит (голос)", variable=self.vp_var,
                        command=self._vpanel_toggle).pack(side="left", padx=(0, 12))
        row = ttk.Frame(f4)
        row.pack(fill="x", padx=8, pady=(0, 6))
        # положение без мыши: сдвиг стрелками и 9 точек экрана
        nud = tk.Frame(row, bg=BG)
        nud.pack(side="right")
        for (dx, dy, t, r_, c_) in ((0, -20, "▲", 0, 1), (-20, 0, "◀", 1, 0), (20, 0, "▶", 1, 2), (0, 20, "▼", 2, 1)):
            tk.Button(nud, text=t, width=2, relief="flat", bd=0, bg=PANEL, fg=INK, activebackground="#CDBB98",
                      font=("Segoe UI", 8), command=lambda a=dx, b=dy: self._overlay_nudge(a, b)
                      ).grid(row=r_, column=c_, padx=1, pady=1)
        ttk.Label(row, text="Сдвиг", style="Muted.TLabel").pack(side="right", padx=(12, 6))
        # что двигают площадка, стрелки и колесо
        self.target_var = tk.StringVar(value=self.s.get("move_target", "kb"))
        tgt = ttk.Frame(row)
        tgt.pack(side="right", padx=(0, 8))
        ttk.Label(tgt, text="Двигать:", style="Muted.TLabel").pack(anchor="w")
        ttk.Radiobutton(tgt, text="клавиатуру", value="kb", variable=self.target_var,
                        command=self._target_changed).pack(anchor="w")
        ttk.Radiobutton(tgt, text="панель голоса", value="voice", variable=self.target_var,
                        command=self._target_changed).pack(anchor="w")
        # площадка в окне программы: зажать и тащить — клавиатура едет следом, колесо — размер
        pad = tk.Canvas(row, width=230, height=58, bg=PANEL, highlightthickness=1, highlightbackground=LINE,
                        cursor="fleur")
        pad.pack(side="right", padx=(0, 4))
        pad.create_text(115, 21, text="✥  Зажмите и тащите", fill=INK, font=("Segoe UI", 10, "bold"))
        pad.create_text(115, 41, text="колесо мыши — размер", fill=MUTED, font=("Segoe UI", 9))
        pad.bind("<ButtonPress-1>", self._pad_start)
        pad.bind("<B1-Motion>", self._pad_move)
        pad.bind("<ButtonRelease-1>", self._pad_end)
        pad.bind("<MouseWheel>", self._pad_wheel)
        pad.bind("<Button-4>", lambda e: self._pad_wheel(e, 1))
        pad.bind("<Button-5>", lambda e: self._pad_wheel(e, -1))
        ttk.Label(row, text="Размер").pack(side="left")
        self.scale_var = tk.DoubleVar(value=float(self.s["scale"]))
        ttk.Scale(row, from_=0.5, to=1.8, variable=self.scale_var, length=120,
                  command=lambda v: self._overlay_scale()).pack(side="left", padx=(4, 12))
        ttk.Label(row, text="Прозрачность").pack(side="left")
        self.alpha_var = tk.DoubleVar(value=float(self.s["alpha"]))
        ttk.Scale(row, from_=0.3, to=1.0, variable=self.alpha_var, length=100,
                  command=lambda v: self._overlay_alpha()).pack(side="left", padx=4)
        ttk.Label(r, text="Горячие клавиши работают прямо в игре: F6 камера на игрока, F7 пауза/продолжить, "
                          "F8 пересинхронизировать, F5/F9 раунд назад/вперёд, F10 замедление ×0.5, F11 ускорение ×4 (повторное нажатие возвращает ×1). Пробел в окне программы — пауза.", style="Muted.TLabel",
                  wraplength=740).pack(fill="x", padx=12, pady=(0, 8))
        r.bind("<space>", lambda e: (self.toggle() if not isinstance(e.widget, (ttk.Entry, tk.Entry)) else None))
        r.bind("<Left>", lambda e: self.seek(self.tick - 5 * TPS))
        r.bind("<Right>", lambda e: self.seek(self.tick + 5 * TPS))
        r.bind("<Prior>", lambda e: self.prev_round())
        r.bind("<Next>", lambda e: self.next_round())

    def msg(self, text):
        self.msg_lbl.configure(text=tr(text))

    def ui(self, fn):
        self.ui_q.put(fn)

    # ================= демо и игрок =================
    def open_demo(self):
        path = filedialog.askopenfilename(title="Демо CS2", initialdir=self.s.get("last_dir") or None,
                                          filetypes=[("Демо CS2", "*.dem"), ("Все файлы", "*.*")])
        if not path:
            return
        self.open_demo_path(path)

    def open_demo_path(self, path):
        self.s["last_dir"] = os.path.dirname(path)
        save_settings(self.s)
        cache = self._cache_name(path, f"scan.v{extract.FORMAT_VERSION}.json")
        if os.path.exists(cache):
            try:
                with open(cache, encoding="utf-8") as f:
                    return self._scan_done(json.load(f))
            except Exception:
                pass
        self._busy(True, "Читаю демо… большие файлы — до минуты")
        fut = self.pool.submit(_scan_job, path)
        fut.add_done_callback(lambda f: self.ui(lambda: self._scan_result(f, path)))

    def _cache_name(self, path, suffix):
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        base = os.path.splitext(os.path.basename(path))[0][:60]
        return os.path.join(CACHE_DIR, f"{base}_{size}.{suffix}")

    def _scan_result(self, fut, path):
        self._busy(False)
        try:
            info = fut.result()
        except Exception as e:
            return messagebox.showerror(APP, f"Не удалось прочитать демо:\n{e}")
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(self._cache_name(path, f"scan.v{extract.FORMAT_VERSION}.json"), "w", encoding="utf-8") as f:
                json.dump(info, f, ensure_ascii=False)
        except Exception:
            pass
        self._scan_done(info)

    def _scan_done(self, info):
        self.info = info
        self.players.delete(0, "end")
        first = info["rounds"][0]["teams"] if info["rounds"] else {}
        order = sorted(info["players"], key=lambda p: (first.get(p["steamid"], p["team"]), p["name"].lower()))
        self._player_order = order
        for p in order:
            t = first.get(p["steamid"], p["team"])
            side = {2: "T ", 3: "CT"}.get(t, "  ")
            self.players.insert("end", f"  {side}   {p['name']}")
        self.demo_lbl.configure(text=f"{os.path.basename(info['path'])}   карта {info['map'] or '?'}, "
                                     f"раундов {len(info['rounds'])}. Выберите игрока и нажмите «Извлечь нажатия».")
        self.extract_btn.configure(state="normal")
        self.load_btn.configure(state="normal")

    def extract_selected(self):
        sel = self.players.curselection()
        if not self.info or not sel:
            return messagebox.showinfo(APP, "Выберите игрока в списке.")
        p = self._player_order[sel[0]]
        cache = self._cache_name(self.info["path"], f"{p['steamid']}.v{extract.FORMAT_VERSION}.cs2keys")
        if os.path.exists(cache):
            try:
                with open(cache, encoding="utf-8") as f:
                    return self._set_data(json.load(f))
            except Exception:
                pass
        self._busy(True, f"Извлекаю нажатия {p['name']}…")
        fut = self.pool.submit(_extract_job, self.info["path"], p["steamid"], self.info)
        fut.add_done_callback(lambda f: self.ui(lambda: self._extract_result(f, cache)))

    def _extract_result(self, fut, cache):
        self._busy(False)
        try:
            data = fut.result()
        except Exception as e:
            return messagebox.showerror(APP, f"Не удалось извлечь нажатия:\n{e}")
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(cache, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            pass
        self._set_data(data)

    def open_keys(self):
        path = filedialog.askopenfilename(title="Файл клавиатуры", initialdir=self.s.get("last_dir") or None,
                                          filetypes=[("Клавиатура CS2 Demo to Keyboard", "*.cs2keys"), ("Все файлы", "*.*")])
        if not path:
            return
        self.open_keys_path(path)

    def open_keys_path(self, path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            assert data.get("format") == "cs2keys"
        except Exception:
            return messagebox.showerror(APP, "Это не файл клавиатуры CS2 Demo to Keyboard.")
        if not os.path.exists(data.get("demo_path", "")):
            messagebox.showinfo(APP, f"Демо {data.get('demo_name')} не найдено по сохранённому пути.\n"
                                     "Клавиатура откроется, но загрузить демо в CS2 кнопкой не получится — "
                                     "откройте его в игре вручную (playdemo).")
        self._set_data(data)

    def save_keys(self):
        if not self.data:
            return
        name = f"{os.path.splitext(self.data['demo_name'])[0]}_{self.data['player']}.cs2keys"
        path = filedialog.asksaveasfilename(title="Сохранить клавиатуру", initialfile=name, defaultextension=".cs2keys",
                                            filetypes=[("Клавиатура CS2 Demo to Keyboard", "*.cs2keys")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, separators=(",", ":"))
            self.msg(f"Сохранено: {path}")

    def _busy(self, on, text=""):
        self.busy_lbl.configure(text=text)
        if on:
            self.prog.start(12)
            self.extract_btn.configure(state="disabled")
        else:
            self.prog.stop()
            self.extract_btn.configure(state="normal" if self.info else "disabled")

    def _set_data(self, d):
        self.data = d
        rle = d["rle"]
        self.T, self.M = rle[0::2], rle[1::2]
        self.WT, self.WI = d["wr"][0::2], d["wr"][1::2]
        self.GT = [g[0] for g in d["gr"]]
        self.rounds = d["rounds"]
        self.t0 = self.rounds[0]["s"] if self.rounds else d["start"]
        self.t1 = d["end"]
        self.timeline.configure(from_=self.t0, to=self.t1)
        for b in self.round_btns:
            b.destroy()
        self.round_btns = []
        for i, rd in enumerate(self.rounds):
            won = rd.get("won")
            b = tk.Button(self.rounds_fr, text=str(rd["n"]), width=3, relief="flat", bd=0,
                          bg=PANEL if won else BG, fg=INK if won else (LOSS if won is False else MUTED),
                          activebackground="#CDBB98", font=("Segoe UI", 9, "bold"),
                          highlightthickness=2, highlightbackground=LOSS if won is False else LINE,
                          command=lambda r=rd: self.seek(r["f"] - 3 * TPS))
            b.grid(row=i // 16, column=i % 16, padx=2, pady=2)
            self.round_btns.append(b)
        wins = sum(1 for r in self.rounds if r.get("won"))
        losses = sum(1 for r in self.rounds if r.get("won") is False)
        acc = "точные нажатия из команд клиента" if d.get("precise") else "приблизительные нажатия (в демо нет сырых команд)"
        self.demo_lbl.configure(text=f"{d['demo_name']}   игрок {d['player']}, раунды {wins}:{losses}, {acc}")
        self.cam_btn.configure(text=f"Камера на {d['player']} (F6)")
        for b in (self.play_btn, self.resync_btn, self.save_btn, self.cam_btn, self.load_btn):
            b.configure(state="normal")
        self.playing = False
        self.tick = float(self.rounds[0]["f"] - 3 * TPS) if self.rounds else float(self.t0)
        self._ensure_overlay(rebuild=True)
        self._ensure_vpanel()
        self._paint_speed()
        self.msg("Готово. Загрузите демо в CS2, затем выберите раунд и нажмите «Играть».")
        self._render(force=True)

    # ================= состояние в момент времени =================
    def _at(self, arr, t):
        i = bisect.bisect_right(arr, t) - 1
        return i

    def _state(self, t):
        i = self._at(self.T, t)
        mask = self.M[i] if i >= 0 else 0
        wi = self._at(self.WT, t)
        wname = self.data["wn"][self.WI[wi]] if wi >= 0 and self.WI[wi] >= 0 else ""
        wname = WEAPON_RU.get(wname, wname)
        tags = []
        if mask >> 13 & 1:
            tags.append("прыжок")
        return mask, wname, "   ".join(tags)

    def _mask_range(self, a, b):
        """Все клавиши, нажатые хоть на один тик в промежутке (a, b] — чтобы не терять короткие клики между кадрами."""
        i = self._at(self.T, a)
        mask = self.M[i] if i >= 0 else 0
        j = bisect.bisect_right(self.T, b)
        for k in range(max(i + 1, 0), j):
            mask |= self.M[k]
        return mask

    def _shot_in(self, a, b):
        sh = self.data["sh"]
        i = bisect.bisect_right(sh, a)
        return i < len(sh) and sh[i] <= b

    def _round_at(self, t):
        idx = 0
        for i, r in enumerate(self.rounds):
            if t >= r["s"]:
                idx = i
        return idx

    # ================= главный цикл =================
    def _loop(self):
        now = time.perf_counter()
        dt = now - self.last_t
        self.last_t = now
        while True:
            try:
                self.ui_q.get_nowait()()
            except queue.Empty:
                break
            except Exception:
                traceback.print_exc()
        if self.data and self.playing:
            self.tick += dt * TPS * self._speed()
            if self.tick >= self.t1:
                self.tick = self.t1
                self.playing = False
                self._update_play_btn()
            self._cam_watch(self.tick)
        if self.data:
            self._render()
        self.root.after(4, self._loop)

    def _render(self, force=False):
        t = int(self.tick)
        mask, weapon, tag = self._state(t)
        alive = mask >> 14 & 1
        prev = getattr(self, "_prev_t", None)
        if self.playing and prev is not None and 0 < t - prev < 64:
            rng = self._mask_range(prev, t)
            mask = (mask & (1 << 14)) | (rng & ~(1 << 14))
            if alive and self._shot_in(prev - 1, t):
                mask |= 1 << 7                      # выстрел = нажатая ЛКМ
        elif alive and self._shot_in(t - 3, t):
            mask |= 1 << 7
        self._prev_t = t
        # короткие нажатия держим на экране минимум 60 мс, чтобы глаз успел заметить
        now = time.perf_counter()
        latch = getattr(self, "_latch", {})
        for b in range(14):
            if mask >> b & 1:
                latch[b] = now + 0.06
        if self.playing and alive:
            for b, until in latch.items():
                if until > now:
                    mask |= 1 << b
        self._latch = latch
        if alive and mask >> 15 & 1:
            tag = (tag + "   примерно").strip()
        if self.overlay:
            self.overlay.update_state(mask, weapon, tag)
        if self.vpanel:
            self.vpanel.update_state(self._speakers_at(t))
        if force or not hasattr(self, "_lbl_t") or now_ms() - self._lbl_t > 50:
            self._lbl_t = now_ms()
            if self.rounds:
                ri = self._round_at(t)
                r = self.rounds[ri]
                self.clock.configure(text=fmt((t - r["f"]) / TPS))
                self.clock_sub.configure(text=tr(f"Раунд {r['n']}   тик {t}"))
                self._mark_round(ri)
            self._scale_busy = True
            self.timeline.set(t)
            self._scale_busy = False
            self._voice_follow_round()

    def _mark_round(self, ri):
        for i, b in enumerate(self.round_btns):
            b.configure(relief="solid" if i == ri else "flat")

    def _speed(self):
        try:
            return float(self.speed_var.get().replace("×", ""))
        except ValueError:
            return 1.0

    def _update_play_btn(self):
        self.play_btn.configure(text="❚❚  Пауза (F7)" if self.playing else "▶  Играть (F7)")

    # ================= синхронизация с CS2 =================
    def _cs2(self):
        return self.net.sock is not None

    def _bg(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    def play_synced(self):
        if not self.data:
            return
        if not self._cs2():
            self.playing = True
            self.last_t = time.perf_counter()
            self._update_play_btn()
            return self.msg("CS2 не подключена: клавиатура играет без игры.")
        if self.syncing:
            return
        self.syncing, self.playing, self.clean = True, False, False
        self._update_play_btn()
        t = int(self.tick)
        tick = t + int(self.offset_var.get() or 0)
        wait = max(0.5, min(20.0, float(self.wait_var.get() or 3)))
        frm = getattr(self, "_seek_from", None)
        if frm is not None and 0 <= t - frm <= 180 * TPS:
            wait = min(wait, 0.8 + (t - frm) / TPS / 60)        # короткий прыжок вперёд — CS2 перематывает быстро
        self._seek_from = None
        speed = self._speed()
        player = self.cam_target()
        self.msg(f"Синхронизация: CS2 перематывает, ждём {wait:g} с…")
        self.play_btn.configure(state="disabled")

        def job():
            err = None
            try:
                if not self.net.ping():
                    raise ConnectionError("CS2 не выполняет команды (нет ответа на проверку)")
                seq = self.net.mark()
                self.net.send("engine_no_focus_sleep 0", f"demo_timescale {speed:g}",
                              f"demo_gototick {tick} 0 1", "echo SYNC_SEEK")
                self.net.wait_for("SYNC_SEEK", seq, 3)
                time.sleep(wait)
                bad = self.net.problems(seq)
                if bad:
                    raise RuntimeError("CS2 ответила: " + bad[-1])
                self.net.send(self._spec_cmd(player), "demo_resume")
                sent = time.perf_counter()
                # после смены раунда CS2 может сама переключить камеру — повторяем ещё несколько раз
                for delay in (0.4, 1.0, 2.0):
                    threading.Timer(delay, lambda: self._send_quiet(self._spec_cmd(player))).start()
            except Exception as e:
                err = str(e)

            def done():
                self.syncing = False
                self._sync_end = time.perf_counter()
                self._speed_cand = None
                self.last_probe = None
                self.play_btn.configure(state="normal")
                if err:
                    return self.msg("Ошибка: " + err)
                self.tick = t + (time.perf_counter() - sent) * TPS * speed
                self.last_t = time.perf_counter()
                self.playing = True
                self._update_play_btn()
                self.msg("Демо и клавиатура стартовали вместе.")
            self.ui(done)
        self._bg(job)

    # ================= CS2 ведёт: следим за паузой, перемоткой и скоростью в игре =================
    def _follow_changed(self):
        self.s["follow"] = bool(self.follow_var.get())
        save_settings(self.s)

    def _gt_off(self):
        return (self.data or {}).get("gt_off")

    def _cs_event(self, kind, gt, ts):
        if kind == "action":
            fn = {"prev_round": self.prev_round, "next_round": self.next_round, "camera": self.camera}.get(gt)
            if fn:
                fn()
            return
        if not self.data or not self.follow_var.get() or self._gt_off() is None:
            return
        off = self._gt_off() + int(self.offset_var.get() or 0)
        t = gt - off
        now = time.perf_counter()
        if kind == "paused":
            if self.syncing:
                return
            pp = getattr(self, "_probe_paused", None)
            if pp and ts - pp < 1.0 and not self.playing:
                # CS2 играла, а мы думали, что пауза: продолжаем обе стороны с её тика
                self._probe_paused = None
                self._probing = True
                self.tick = float(max(self.t0, min(self.t1, t)))
                self.last_probe = None
                self._send_bg("demo_resume")
                self.msg("Догоняю CS2 после перемотки в игре.")
                return
            # замер скорости по двум точкам, пока запись шла.
            # После перемотки CS2 какое-то время подгружает демо и «тормозит» — такие замеры ложные
            # (из-за них раньше сама включалась замедленная скорость). Поэтому:
            #  - первые 5 с после любой синхронизации/перемотки замеры не учитываются;
            #  - скорость меняется, только если два замера подряд показали одно и то же.
            if self.playing and self.last_probe and time.perf_counter() - getattr(self, "_sync_end", 0) > 5 \
                    and not getattr(self, "_auto_job", None):
                g0, t0 = self.last_probe
                dt = ts - t0
                if 0.8 < dt < 10 and gt > g0:
                    rate = (gt - g0) / (dt * TPS)
                    known = [0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0]
                    best = min(known, key=lambda k: abs(k - rate))
                    if abs(best - rate) / best < 0.12 and abs(best - self._speed()) > 1e-6:
                        if getattr(self, "_speed_cand", None) == best:
                            self._speed_cand = None
                            self.speed_var.set(f"×{best:g}")
                            self.s["speed"] = best
                            self._paint_speed()
                            self.msg(f"CS2 сменила скорость: ×{best:g}")
                        else:
                            self._speed_cand = best                 # ждём подтверждения следующим замером
                    else:
                        self._speed_cand = None
            self.tick = float(max(self.t0, min(self.t1, t)))
            self.cs_tick, self.clean = int(self.tick), True
            if not getattr(self, "_probing", False):
                if self.playing:
                    self.msg("Пауза из CS2.")
                self.playing = False
                self._update_play_btn()
            self._render(force=True)
        else:  # unpaused
            if getattr(self, "_probing", False):
                self._probing = False
            elif not self.playing and not self.syncing:
                self.msg("Воспроизведение из CS2.")
            self.tick = float(max(self.t0, min(self.t1, t + (now - ts) * TPS * self._speed())))
            self.last_t = now
            if not self.syncing:
                self.playing = True
                self._update_play_btn()
            self.last_probe = (gt, ts)

    def _probe(self):
        """Раз в 1,5 с сверяемся с CS2.
        Если запись идёт — мгновенная пауза+продолжение (0–1 тик) даёт точный тик.
        Если у нас пауза — шлём только паузу: если CS2 на самом деле играет (например, после перемотки
        ползунком в самой игре), она ответит «paused on tick N», мы сразу продолжим и догоним.
        Если CS2 и правда на паузе, команда ничего не меняет."""
        try:
            if (self.data and not self.syncing and self.follow_var.get()
                    and self._gt_off() is not None and self._cs2()):
                if self.playing:
                    self._probing = True
                    self._send_bg("demo_pause", "demo_resume")
                else:
                    self._probe_paused = time.perf_counter()
                    self._send_bg("demo_pause")
        finally:
            self.root.after(1500, self._probe)

    def pause(self):
        self.playing = False
        self._update_play_btn()
        if self.seek_job:
            self.root.after_cancel(self.seek_job)
            self.seek_job = None
        if self._cs2():
            self.cs_tick, self.clean = int(self.tick), True
            self._send_bg("demo_pause", ok="Пауза в игре и в клавиатуре.")

    def resume(self):
        if not self._cs2():
            return self.play_synced()
        if not self.clean:
            return self.play_synced()
        self.clean = False

        def job():
            try:
                self.net.send("demo_resume")
                sent = time.perf_counter()
                self.ui(lambda: self._resumed(sent))
            except Exception as e:
                self.ui(lambda: self.msg("Ошибка: " + str(e)))
        self._bg(job)

    def _resumed(self, sent):
        self._sync_end = time.perf_counter()
        self._speed_cand = None
        self.tick += 0  # позиция не менялась
        self.last_t = sent
        self.playing = True
        self._update_play_btn()
        self.msg("Продолжаем синхронно.")

    def toggle(self):
        if not self.data or self.syncing:
            return
        self.pause() if self.playing else self.resume()

    def seek(self, t):
        if not self.data:
            return
        self._sync_end = time.perf_counter()
        self._speed_cand = None
        self._seek_from = self.tick
        self.tick = float(max(self.t0, min(self.t1, t)))
        self._render(force=True)
        if not self._cs2() or self.syncing:
            return
        if self.seek_job:
            self.root.after_cancel(self.seek_job)
        if self.playing:
            self.seek_job = self.root.after(300, self.play_synced)
            return
        self.clean = False
        self.seek_job = self.root.after(300, self._seek_cs2)

    def _seek_cs2(self):
        self.seek_job = None
        self.cs_tick = int(self.tick)
        tick = self.cs_tick + int(self.offset_var.get() or 0)
        self._send_bg(f"demo_gototick {tick} 0 1")

    def _timeline_moved(self, v):
        if not self._scale_busy:
            self.seek(float(v))

    def set_speed(self, v):
        self.speed_var.set(f"×{v:g}")
        self._speed_changed()

    def _speed_changed(self):
        v = self._speed()
        self.s["speed"] = v
        save_settings(self.s)
        self._paint_speed()
        self.last_probe = None     # замер скорости начинаем заново
        # скорость меняем на ходу, без перемотки: CS2 и клавиатура просто продолжают с новым темпом
        if self._cs2():
            self._send_bg(f"demo_timescale {v:g}", ok=f"Скорость ×{v:g}")
        else:
            self.msg(f"Скорость ×{v:g}")

    def _paint_speed_reset(self):
        self.last_probe = None

    def _paint_speed(self):
        v = self._speed()
        for val, b in getattr(self, "speed_btns", {}).items():
            on = abs(val - v) < 1e-6
            b.configure(bg=GO if on else PANEL, fg="#ffffff" if on else INK)

    def _round_index(self):
        return self._round_at(int(self.tick)) if self.rounds else 0

    def next_round(self):
        if not self.data or not self.rounds:
            return
        i = self._round_index()
        # если мы ещё до конца закупки текущего раунда — «вперёд» ведёт к его началу
        target = i if self.tick < self.rounds[i]["f"] - 3 * TPS - 32 else i + 1
        if target >= len(self.rounds):
            return self.msg("Это последний раунд.")
        self.seek(self.rounds[target]["f"] - 3 * TPS)
        self.msg(f"Раунд {self.rounds[target]['n']}")

    def prev_round(self):
        if not self.data or not self.rounds:
            return
        i = self._round_index()
        # если раунд идёт больше 3 секунд — сначала в его начало, повторное нажатие — в прошлый
        start = self.rounds[i]["f"] - 3 * TPS
        target = i if self.tick > start + 3 * TPS else max(0, i - 1)
        self.seek(self.rounds[target]["f"] - 3 * TPS)
        self.msg(f"Раунд {self.rounds[target]['n']}")

    def _send_quiet(self, *cmds):
        try:
            self.net.send(*cmds)
        except Exception:
            pass

    def _send_bg(self, *cmds, ok=None):
        def job():
            try:
                self.net.send(*cmds)
                if ok:
                    self.ui(lambda: self.msg(ok))
            except Exception as e:
                self.ui(lambda: self.msg("Ошибка: " + str(e)))
        self._bg(job)

    def _spec_cmd(self, name):
        # всегда в кавычках; кавычки и «;» из ника убираем, чтобы ник не сломал консольную команду
        clean = str(name).replace('"', "").replace(";", "")
        return f'spec_player "{clean}"'

    def cam_target(self):
        """Ник игрока, за которым должна быть камера."""
        return (self.data or {}).get("player", "")

    def camera(self):
        if self.data:
            name = self.cam_target()
            self._send_bg(self._spec_cmd(name), ok=f"Камера на {name}.")

    def _cam_watch(self, t):
        """Сторож камеры: когда выбранный игрок возрождается или начинается раунд — камеру на него (2 раза)."""
        if not (self.playing and not self.syncing and self._cs2() and self.data and self.rounds):
            return
        alive = self._target_alive(int(t))
        ri = self._round_at(int(t))
        prev = getattr(self, "_cam_prev", None)
        self._cam_prev = (alive, ri)
        if prev is None:
            return
        if (alive and not prev[0]) or (ri != prev[1] and alive):
            now = time.perf_counter()
            if now - getattr(self, "_cam_last", 0) < 0.6:
                return
            self._cam_last = now
            cmd = self._spec_cmd(self.cam_target())
            self._send_quiet(cmd)
            threading.Timer(1.0, lambda: self._send_quiet(cmd) if self.playing else None).start()

    def _target_alive(self, t):
        i = bisect.bisect_right(self.T, t) - 1
        return bool(self.M[i] >> 14 & 1) if i >= 0 else False

    def load_demo(self):
        path = (self.data or {}).get("demo_path") or (self.info or {}).get("path")
        if not path:
            return
        cmd = 'playdemo "%s"' % path.replace("\\", "/")

        def job():
            try:
                seq = self.net.mark()
                self.net.send(*self._voice_cmds(), cmd)      # голос задаём до загрузки демо
                time.sleep(2)
                bad = self.net.problems(seq)
                self.ui(lambda: self.msg(("CS2 ответила: " + bad[-1]) if bad else
                                         "Демо загружается в CS2. Когда пойдёт, нажмите «Играть»."))
            except Exception as e:
                self.ui(lambda: self.msg("Ошибка: " + str(e)))
        self._bg(job)

    # ================= запуск CS2 для демо =================
    def launch_and_load(self):
        """Кнопка «Запустить CS2 и демо»: запускает (или перезапускает) CS2 с нужными параметрами
        только на этот раз и загружает демо. В свойствах Steam ничего не меняется."""
        if getattr(self, "_launching", False):
            return
        if not ((self.data or {}).get("demo_path") or (self.info or {}).get("path")):
            return
        if self._cs2():                      # CS2 уже запущена с параметрами — просто грузим демо
            return self.load_demo()
        exe = launcher.find_cs2_exe(self.s.get("cs2_exe"))
        if not exe:
            exe = filedialog.askopenfilename(title="Где находится cs2.exe?",
                                             filetypes=[("cs2.exe", "cs2.exe"), ("Все файлы", "*.*")])
            if not exe:
                return
        self.s["cs2_exe"] = exe
        save_settings(self.s)
        self._launching = True
        self.msg("Проверяю, запущена ли CS2…")

        def check():
            running = launcher.cs2_running()
            if running:
                self.net.last_try = 0
                _ = self.net.connected          # вдруг порт уже открыт, просто ещё не подключились
            # запущена, но порт не отвечает — значит, без нужных параметров
            self.ui(lambda: self._launch_step(exe, running))
        self._bg(check)

    def _launch_step(self, exe, running):
        if running and self._cs2():
            self._launching = False
            return self.load_demo()
        if running:
            self.ask_yes_no("CS2 запущена без нужных параметров",
                            "Чтобы смотреть демо синхронно, CS2 нужно перезапустить с параметрами для демо. "
                            "Перезапустить сейчас?",
                            lambda ok: self._bg(lambda: self._restart_and_launch(exe)) if ok else self._launch_cancel())
        else:
            self._bg(lambda: self._restart_and_launch(exe, close_first=False))

    def _launch_cancel(self):
        self._launching = False
        self.msg("Запуск отменён.")

    def _restart_and_launch(self, exe, close_first=True):
        try:
            if close_first:
                self.ui(lambda: self.msg("Закрываю CS2…"))
                if not launcher.close_cs2():
                    raise RuntimeError("не удалось закрыть CS2 — закройте её вручную и нажмите ещё раз")
                time.sleep(2)
            self.ui(lambda: self.msg("Запускаю CS2 с параметрами для демо…"))
            launcher.launch_cs2(exe, self.net.port, tools=bool(self.s.get("use_tools", True)))
            self._launched_by_us = True
            start = time.time()
            hinted = False
            while time.time() - start < 400:
                if self.net.connected:
                    break
                el = int(time.time() - start)
                if el > 45 and not hinted:
                    hinted = True
                    self.ui(lambda: self.msg("Жду CS2… Если открылось окно Workshop Tools, нажмите в нём «Launch Tools»."))
                elif not hinted:
                    self.ui(lambda el=el: self.msg(f"Запускаю CS2… {el} с"))
                time.sleep(2)
            else:
                raise RuntimeError("CS2 не открыла консольный порт — проверьте, что игра запустилась")
            # игра открыла порт, ждём, пока консоль начнёт выполнять команды
            self.ui(lambda: self.msg("CS2 запущена, загружаю демо…"))
            for _ in range(60):
                try:
                    if self.net.ping(timeout=2):
                        break
                except Exception:
                    pass
                time.sleep(2)
            time.sleep(3)
            self.ui(self.load_demo)
        except Exception as e:
            self.ui(lambda: self.msg("Ошибка: " + str(e)))
        finally:
            self._launching = False

    def ask_yes_no(self, title, text, callback):
        callback(messagebox.askyesno(title, text))

    def ping(self):
        def job():
            try:
                ok = self.net.ping()
                self.ui(lambda: self.msg("Связь есть: CS2 выполняет команды." if ok else "CS2 не отвечает на команды."))
            except Exception as e:
                self.ui(lambda: self.msg("Ошибка: " + str(e)))
        self._bg(job)

    def _port_changed(self):
        try:
            port = int(self.port_var.get())
        except (ValueError, tk.TclError):
            return
        if port != self.net.port:
            self.net.port = port
            if self.net.sock:
                try:
                    self.net.sock.close()
                except OSError:
                    pass
                self.net.sock = None
            self.s["port"] = port
            save_settings(self.s)

    def _poll_cs2(self):
        def job():
            ok = self.net.connected
            err = self.net.last_error
            lines = self.net.recent(40)
            self.ui(lambda: self._cs2_status(ok, err, lines))
        self._bg(job)
        self.root.after(1500, self._poll_cs2)

    def _cs2_status(self, ok, err, lines):
        if ok and not getattr(self, "_was_ok", False):
            if self.s.get("voice", "off") != "off" or self.chat_var.get():
                self.apply_voice(quiet=True)
            if self.binds_var.get():
                self.apply_binds()
            elif self.s.get("saved_binds"):
                self.restore_binds()
        self._was_ok = ok
        self._show_cs2(ok, err, lines)

    def _show_cs2(self, ok, err, lines):
        self.dot.itemconfigure(self.dot_item, fill=GO if ok else LOSS)
        self.cs_lbl.configure(text="CS2 подключена" if ok else f"CS2 не найдена: {err or 'ищу…'}")
        txt = "\n".join(lines)
        if txt != getattr(self, "_log_txt", None):
            self._log_txt = txt
            self.log.configure(state="normal")
            self.log.delete("1.0", "end")
            self.log.insert("end", txt)
            self.log.see("end")
            self.log.configure(state="disabled")

    # ================= голос и чат в демо =================
    def _voice_mask(self):
        """Битовая маска слотов игроков, которых слышно, для текущего раунда (стороны меняются в перерыве)."""
        mode = self.s.get("voice", "off")
        if mode == "off":
            return 0, 0
        if mode == "all" or not self.data or not self.rounds:
            return -1, -1
        r = self.rounds[self._round_at(int(self.tick))]
        t, ct = r.get("t_slots"), r.get("ct_slots")
        if t is None or ct is None:
            return -1, -1              # старый файл без слотов — включаем всех
        team = r.get("team")
        pick = {"t": t, "ct": ct,
                "mine": t if team == 2 else ct,
                "enemy": ct if team == 2 else t}[mode]
        lo = hi = 0
        for sl in pick:
            if sl < 32:
                lo |= 1 << sl
            else:
                hi |= 1 << (sl - 32)
        to_i32 = lambda v: v - (1 << 32) if v >= (1 << 31) else v     # CS2 читает значение как int32 со знаком
        return to_i32(lo), to_i32(hi)

    def _voice_cmds(self):
        lo, hi = self._voice_mask()
        cmds = [f"tv_listen_voice_indices {lo}", f"tv_listen_voice_indices_h {hi}"]
        chat = 2 if self.chat_var.get() else 0
        cmds.append(f"tv_relaytextchat {chat}")
        return cmds

    def apply_voice(self, quiet=False):
        self._voice_key = (self.s.get("voice"), self._round_at(int(self.tick)) if self.data and self.rounds else -1)
        if self._cs2():
            names = dict(VOICE_MODES)
            self._send_bg(*self._voice_cmds(), ok=None if quiet else f"Голос: {names.get(self.s.get('voice'), '')}")

    def set_voice(self, mode):
        self.s["voice"] = mode
        save_settings(self.s)
        self._paint_voice()
        self.apply_voice()

    def _chat_changed(self):
        self.s["chat"] = bool(self.chat_var.get())
        save_settings(self.s)
        self.apply_voice(quiet=True)

    def _paint_voice(self):
        cur = self.s.get("voice", "off")
        for k, b in getattr(self, "voice_btns", {}).items():
            on = k == cur
            b.configure(bg=GO if on else PANEL, fg="#ffffff" if on else INK)

    def _voice_follow_round(self):
        # при смене раунда (и сторон в перерыве) пересчитываем, кого слышно
        mode = self.s.get("voice", "off")
        if mode in ("t", "ct", "mine", "enemy") and self.data and self.rounds and self._cs2():
            key = (mode, self._round_at(int(self.tick)))
            if key != getattr(self, "_voice_key", None):
                self.apply_voice(quiet=True)

    # ================= настраиваемые клавиши =================
    def hotkey_table(self):
        hk = dict(DEFAULT_HOTKEYS)
        hk.update(self.s.get("hotkeys") or {})
        return hk

    def cs2_keys(self):
        ck = dict(DEFAULT_CS2_KEYS)
        ck.update(self.s.get("cs2_keys") or {})
        return ck

    def demo_binds(self):
        keys = self.cs2_keys()
        return [(keys[a], cmd, lbl) for a, lbl, cmd in CS2_ACTIONS if keys.get(a)]

    def reload_hotkeys(self):
        tid = getattr(self, "_hk_tid", None)
        if tid and os.name == "nt":
            import ctypes
            ctypes.windll.user32.PostThreadMessageW(tid, 0x8001, 0, 0)    # WM_APP+1: перерегистрировать

    def rebind_cs2(self):
        """После смены клавиш: вернуть старые бинды и поставить новые."""
        if self._cs2() and self.binds_var.get():
            if self.s.get("saved_binds"):
                self.restore_binds(wait=True)
            self.apply_binds()

    # ================= уборка после старой функции GSI =================
    def gsi_cleanup(self):
        """Функция GSI убрана: если её файл остался в папке CS2 — удаляем."""
        try:
            from . import gsi
            gsi.remove_cfg(gsi.cfg_dir(launcher.find_cs2_exe(self.s.get("cs2_exe"))))
        except Exception:
            pass
        had = [self.s.pop(k, None) for k in ("gsi_on", "gsi_token")]
        if any(v is not None for v in had):
            save_settings(self.s)

    # ================= бинды в CS2 =================
    def _binds_changed(self):
        self.s["binds_on"] = bool(self.binds_var.get())
        save_settings(self.s)
        if self._cs2():
            self.apply_binds() if self.binds_var.get() else self.restore_binds()

    def _query_bind(self, key):
        """Что сейчас висит на клавише в CS2 (None — ничего)."""
        seq = self.net.mark()
        self.net.send(f"bind {key}", "echo SYNC_BINDQ")
        self.net.wait_for("SYNC_BINDQ", seq, 1.5)
        for line in self.net.since(seq):
            low = line.lower()
            if key.lower() in low:
                if "not bound" in low or "unbound" in low:
                    return None
                mm = re.search(r'=\s*"(.*)"\s*$', line)
                if mm:
                    return mm.group(1)
        return UNKNOWN          # ответ не распознан — такую клавишу при выходе не трогаем

    def apply_binds(self):
        saved = dict(self.s.get("saved_binds") or {})

        def job():
            try:
                ours = {k: c for k, c, _ in self.demo_binds()}
                for key, cmd in ours.items():
                    if key not in saved:
                        cur = self._query_bind(key)
                        if cur != cmd:              # свой бинд за «родной» не принимаем
                            saved[key] = cur
                    self.net.send(f'bind "{key}" "{cmd}"')
                self.s["saved_binds"] = saved
                save_settings(self.s)
                self.ui(lambda: self.msg("Бинды для демо прописаны в CS2 (цифровой блок). Старые вернутся при выходе."))
            except Exception as e:
                self.ui(lambda: self.msg("Не удалось прописать бинды: " + str(e)))
        self._bg(job)

    def restore_binds(self, wait=False):
        saved = dict(self.s.get("saved_binds") or {})
        if not saved:
            return self.msg("Возвращать нечего: программа ничего не меняла.")

        def job():
            try:
                cmds = [(f'bind "{k}" "{v}"' if v else f'unbind "{k}"') for k, v in saved.items() if v != UNKNOWN]
                unknown = [k for k, v in saved.items() if v == UNKNOWN]
                if cmds:
                    self.net.send(*cmds)
                if unknown:
                    self.ui(lambda: messagebox.showinfo(APP, "Не удалось узнать, что раньше было на клавишах: "
                                                             + ", ".join(unknown) + ".\nНа них остались бинды для демо — "
                                                             "при необходимости переназначьте их в настройках CS2."))
                self.s["saved_binds"] = {}
                save_settings(self.s)
                self.ui(lambda: self.msg("Ваши прежние бинды возвращены."))
            except Exception as e:
                self.ui(lambda: self.msg("Не удалось вернуть бинды (CS2 не подключена?). Попробую при следующем подключении."))
        if wait:
            job()
        else:
            self._bg(job)

    def _save_numbers(self):
        try:
            self.s["offset"] = int(self.offset_var.get())
            self.s["wait"] = float(self.wait_var.get())
        except (ValueError, tk.TclError):
            return
        save_settings(self.s)
        if self._cs2() and not self.playing:
            self.clean = False

    # ================= оверлей =================
    def _ensure_overlay(self, rebuild=False):
        if not self.ov_var.get() or not self.data:
            return
        if self.overlay is None:
            self.overlay = Overlay(self.root, extract.KEYS + [], scale=float(self.scale_var.get()),
                                   alpha=float(self.alpha_var.get()), pos=self.s["overlay_pos"],
                                   on_moved=self._overlay_moved, transparent=bool(self.tr_var.get()),
                                   on_scaled=self._overlay_scaled)
            self.overlay.on_press = lambda: self.msg("Клавиатура захвачена — тащите.")
            self.overlay.set_unlocked(self.move_var.get())

    def _ensure_vpanel(self):
        if not self.vp_var.get() or not self.data or not self.data.get("speakers") or self.vpanel is not None:
            return
        self.vpanel = VoicePanel(self.root, scale=float(self.s.get("vpanel_scale", 1.0)),
                                 alpha=float(self.alpha_var.get()), pos=self.s.get("vpanel_pos", [80, 420]),
                                 on_moved=self._vpanel_moved, transparent=bool(self.tr_var.get()),
                                 on_scaled=self._vpanel_scaled)
        self.vpanel.set_unlocked(self.move_var.get())

    def _vpanel_toggle(self):
        self.s["vpanel_on"] = bool(self.vp_var.get())
        save_settings(self.s)
        if self.vp_var.get():
            self._ensure_vpanel()
        elif self.vpanel:
            self.vpanel.destroy()
            self.vpanel = None

    def _vpanel_moved(self, x, y):
        self.s["vpanel_pos"] = [x, y]
        save_settings(self.s)

    def _vpanel_scaled(self, v):
        self.s["vpanel_scale"] = v
        save_settings(self.s)
        if hasattr(self, "vscale_var"):
            self.vscale_var.set(v)

    def _speaking_sids(self, t):
        """Steam ID тех, кто говорит в момент t (с учётом фильтра голоса, как на панели «кто говорит»)."""
        sp = (self.data or {}).get("speakers") or []
        if not sp or not self.rounds:
            return set()
        r = self.rounds[self._round_at(int(t))]
        sides, mode, me_side = r.get("sides", {}), self.s.get("voice", "off"), r.get("team")
        out = set()
        for s in sp:
            starts = s.setdefault("_starts", [a for a, _ in s["iv"]])
            i = bisect.bisect_right(starts, t) - 1
            if i >= 0 and t <= s["iv"][i][1] + 10:
                side = sides.get(s["steamid"])
                if (mode == "all" or (mode == "t" and side == 2) or (mode == "ct" and side == 3)
                        or (mode == "mine" and side == me_side) or (mode == "enemy" and side not in (None, me_side))
                        or mode == "off"):
                    out.add(s["steamid"])
        return out

    def _speakers_at(self, t):
        """Кто говорит в тик t: (имя, сторона, слышно ли при текущем фильтре, это выбранный игрок)."""
        sp = self.data.get("speakers") or []
        if not sp or not self.rounds:
            return []
        r = self.rounds[self._round_at(t)]
        sides = r.get("sides", {})
        mode = self.s.get("voice", "off")
        me_side = r.get("team")
        out = []
        for s in sp:
            starts = s.setdefault("_starts", [a for a, _ in s["iv"]])
            i = bisect.bisect_right(starts, t) - 1
            if i >= 0 and t <= s["iv"][i][1] + 10:
                side = sides.get(s["steamid"])
                audible = (mode == "all" or (mode == "t" and side == 2) or (mode == "ct" and side == 3)
                           or (mode == "mine" and side == me_side) or (mode == "enemy" and side not in (None, me_side)))
                if audible:                    # на панели только выбранная команда (те, кого слышно)
                    out.append((s["name"], side, audible, s["steamid"] == self.data.get("steamid")))
        out.sort(key=lambda x: (x[1] or 9, x[0].lower()))
        return out[:VoicePanel.ROWS]

    def _overlay_toggle(self):
        self.s["overlay_on"] = bool(self.ov_var.get())
        save_settings(self.s)
        if self.ov_var.get():
            self._ensure_overlay()
            if self.overlay:
                self._render(force=True)
        elif self.overlay:
            self.overlay.destroy()
            self.overlay = None

    def _overlay_find(self):
        if not self.ov_var.get():
            self.ov_var.set(True)
            self._overlay_toggle()
        if self.overlay is None:
            self._ensure_overlay()
        if self.overlay is None:
            return self.msg("Сначала извлеките нажатия игрока — клавиатура появится после этого.")
        self.overlay.center()
        self.move_var.set(True)
        self.overlay.set_unlocked(True)
        self.msg("Клавиатура в центре экрана. Тащите за любое место, размер — за зелёный уголок, "
                 "потом снимите «Переместить».")

    def _overlay_transparent(self):
        self.s["overlay_transparent"] = bool(self.tr_var.get())
        save_settings(self.s)
        for w in (self.overlay, self.vpanel):
            if w:
                w.set_transparent(bool(self.tr_var.get()))

    def _overlay_move(self):
        for w in (self.overlay, self.vpanel):
            if w:
                w.set_unlocked(self.move_var.get())

    def _overlay_moved(self, x, y):
        self.s["overlay_pos"] = [x, y]
        save_settings(self.s)

    def _target(self):
        if self.target_var.get() == "voice":
            self._ensure_vpanel()
            return self.vpanel
        self._ensure_overlay()
        return self.overlay

    def _target_changed(self):
        self.s["move_target"] = self.target_var.get()
        save_settings(self.s)

    def _pad_start(self, e):
        w = self._target()
        if w:
            self._pad = (w, e.x_root, e.y_root, w.winfo_x(), w.winfo_y())

    def _pad_move(self, e):
        if getattr(self, "_pad", None):
            w, x0, y0, wx, wy = self._pad
            x, y = w._snap(wx + e.x_root - x0, wy + e.y_root - y0)
            w.geometry(f"+{x}+{y}")

    def _pad_end(self, e):
        if getattr(self, "_pad", None):
            w = self._pad[0]
            if w.on_moved:
                w.on_moved(w.winfo_x(), w.winfo_y())
        self._pad = None

    def _pad_wheel(self, e, direction=None):
        w = self._target()
        if not w:
            return
        d = direction if direction is not None else (1 if e.delta > 0 else -1)
        if w is self.overlay:
            v = round(max(0.5, min(1.8, float(self.scale_var.get()) + 0.05 * d)), 2)
            self.scale_var.set(v)
            self._overlay_scale()
        else:
            v = round(max(0.5, min(1.8, w.scale + 0.05 * d)), 2)
            w.set_scale(v)
            self._vpanel_scaled(v)

    def _overlay_place(self, ax, ay):
        self._ensure_overlay()
        if self.overlay:
            self.overlay.move_to(ax, ay)

    def _overlay_nudge(self, dx, dy):
        w = self._target()
        if w:
            w.nudge(dx, dy)

    def _overlay_scaled(self, v):
        self.scale_var.set(v)
        self.s["scale"] = v
        save_settings(self.s)

    def _overlay_scale(self):
        v = round(float(self.scale_var.get()), 2)
        self.s["scale"] = v
        if self.overlay and abs(self.overlay.scale - v) > 0.02:
            self.overlay.set_scale(v)
        save_settings(self.s)

    def _overlay_alpha(self):
        v = round(float(self.alpha_var.get()), 2)
        self.s["alpha"] = v
        for w in (self.overlay, self.vpanel):
            if w:
                w.set_alpha(v)
        save_settings(self.s)

    # ================= горячие клавиши Windows =================
    def _start_hotkeys(self):
        if os.name != "nt":
            return

        def loop():
            import ctypes
            import ctypes.wintypes as wt
            u32 = ctypes.windll.user32
            self._hk_tid = ctypes.windll.kernel32.GetCurrentThreadId()
            ids = {}

            def register():
                for hid in list(ids):
                    u32.UnregisterHotKey(None, hid)
                ids.clear()
                busy = []
                for n, (act, _) in enumerate(HOTKEY_ACTIONS, start=1):
                    v = self.hotkey_table().get(act)
                    if not v or not v[0]:
                        continue
                    vk, mods, name = v
                    if u32.RegisterHotKey(None, n, 0x4000 | int(mods), int(vk)):
                        ids[n] = act
                    else:
                        busy.append(name)
                if busy:
                    self.ui(lambda: self.msg("Заняты другой программой: " + ", ".join(busy)))
            register()
            m = wt.MSG()
            while u32.GetMessageW(ctypes.byref(m), None, 0, 0) != 0:
                if m.message == 0x8001:
                    register()
                elif m.message == 0x0312 and m.wParam in ids:
                    act = ids[m.wParam]
                    self.ui({"camera": self.camera, "toggle": self.toggle, "resync": self.play_synced,
                             "prev_round": self.prev_round, "next_round": self.next_round,
                             "slow": lambda: self.set_speed(1.0 if self._speed() == 0.5 else 0.5),
                             "fast": lambda: self.set_speed(1.0 if self._speed() == 4.0 else 4.0)}[act])
        threading.Thread(target=loop, daemon=True).start()

    def _quit(self):
        """Закрытие: возвращаем настройки CS2."""
        if self.s.get("saved_binds") and self._cs2():
            self.restore_binds(wait=True)
        # CS2, запущенную программой, закрываем: параметры для демо действуют только на этот запуск
        if getattr(self, "_launched_by_us", False) and launcher.cs2_running():
            if messagebox.askyesno(APP, "Закрыть CS2, запущенную для просмотра демо?\n"
                                        "В этом режиме игра не пускает в матчмейкинг — для обычной игры "
                                        "её нужно перезапустить."):
                try:
                    import subprocess
                    subprocess.Popen(["taskkill", "/IM", "cs2.exe"], creationflags=launcher.NO_WINDOW)
                except Exception:
                    pass
        save_settings(self.s)
        try:
            self.pool.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
        self.root.destroy()


def load_fonts():
    """Подключает шрифт логотипа (Russo One, лицензия OFL) только для этой программы."""
    base = getattr(sys, "_MEIPASS", None)
    here = os.path.join(base, "cs2keys", "fonts") if base else os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
    try:
        for f in os.listdir(here):
            if f.lower().endswith(".ttf") and os.name == "nt":
                import ctypes
                ctypes.windll.gdi32.AddFontResourceExW(os.path.join(here, f), 0x10, 0)   # FR_PRIVATE
    except Exception:
        pass


def now_ms():
    return time.perf_counter() * 1000


def selftest(path):
    """Проверка сборки без окна: читает демо и извлекает нажатия первого игрока в фоновом процессе."""
    import multiprocessing as mp
    out = []
    try:
        with ProcessPoolExecutor(1, mp_context=mp.get_context("spawn")) as ex:
            info = ex.submit(_scan_job, path).result()
            out.append(f"scan ok: map={info['map']} players={len(info['players'])} rounds={len(info['rounds'])}")
            p = info["players"][0]
            d = ex.submit(_extract_job, path, p["steamid"], info).result()
            out.append(f"extract ok: {p['name']} changes={len(d['rle']) // 2} precise={d['precise']}")
        ok = True
    except Exception:
        out.append(traceback.format_exc())
        ok = False
    text = "\n".join(out)
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(os.path.join(DATA_DIR, "selftest.log"), "w", encoding="utf-8") as f:
            f.write(text)
    except Exception:
        pass
    if sys.stdout:
        print(text)
    return ok


def app_icon():
    base = getattr(sys, "_MEIPASS", None)
    here = os.path.join(base, "cs2keys") if base else os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(here, "assets", "app.ico")
    return p if os.path.exists(p) else None


def run():
    if "--selftest" in sys.argv:
        i = sys.argv.index("--selftest")
        sys.exit(0 if selftest(sys.argv[i + 1]) else 1)
    try:
        if os.name == "nt":
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)   # чёткий интерфейс на мониторах с масштабом
            ctypes.windll.winmm.timeBeginPeriod(1)            # таймер 1 мс вместо 15,6 мс — кадры чаще
    except Exception:
        pass
    set_lang(load_settings().get("lang", "ru"))
    install_i18n()
    load_fonts()
    try:
        import customtkinter as ctk
        from .ui import ModernApp
        ctk.set_appearance_mode("dark")
        try:
            from tkinterdnd2 import TkinterDnD

            class Root(ctk.CTk, TkinterDnD.DnDWrapper):      # окно с поддержкой перетаскивания файлов
                def __init__(self):
                    super().__init__()
                    self.TkdndVersion = TkinterDnD._require(self)
            root = Root()
        except Exception:
            root = ctk.CTk()
        AppClass = ModernApp
    except ImportError:            # без customtkinter — старый интерфейс
        root = tk.Tk()
        AppClass = App

    def report(exc, val, tb):
        err = "".join(traceback.format_exception(exc, val, tb))
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(os.path.join(DATA_DIR, "crash.log"), "a", encoding="utf-8") as f:
                f.write(err + "\n")
        except Exception:
            pass
        print(err, file=sys.stderr or open(os.devnull, "w"))
    root.report_callback_exception = report
    ico = app_icon()
    if ico and os.name == "nt":
        try:
            root.iconbitmap(ico)
            root.after(300, lambda: root.iconbitmap(ico))     # customtkinter ставит свою иконку с задержкой
        except Exception:
            pass
    try:
        AppClass(root)
        root.mainloop()
    except Exception:
        err = traceback.format_exc()
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(os.path.join(DATA_DIR, "crash.log"), "w", encoding="utf-8") as f:
                f.write(err)
        except Exception:
            pass
        messagebox.showerror(APP, "Программа упала. Подробности в файле:\n"
                             + os.path.join(DATA_DIR, "crash.log") + "\n\n" + err[-800:])
