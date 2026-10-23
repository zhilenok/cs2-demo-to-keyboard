# -*- coding: utf-8 -*-
"""Современный тёмный интерфейс CS2 Keys (customtkinter). Логика — в main.App, здесь только вид."""
import json
import math
import os
import time
import tkinter as tk
import tkinter.font
from tkinter import filedialog, messagebox

import customtkinter as ctk

from . import extract
from .main import (App, APP, TPS, VOICE_MODES, CACHE_DIR, DATA_DIR, _extract_job, save_settings,
                   HOTKEY_ACTIONS, DEFAULT_HOTKEYS, CS2_ACTIONS, DEFAULT_CS2_KEYS)
from .i18n import tr, set_lang
from . import i18n

# ---------- палитра ----------
BG = "#0c0d0f"
CARD = "#15171b"
CARD2 = "#1c1f24"
LINE = "#262a31"
TEXT = "#ecebe8"
MUTED = "#8b909a"
ACC = "#1fae52"
ACC_H = "#25c55e"
LOSS = "#d0573f"
T_COL = "#e0a33a"
CT_COL = "#5b9bd5"
RIBBON = ["#1fae52", "#1bc4a0", "#3fa7e0", "#7b6cf0", "#d05ac8", "#f0a13a", "#1fae52"]

F = "Segoe UI"
BRAND = "Russo One"          # шрифт логотипа (в папке fonts, лицензия OFL)


def brand_image(h=40):
    """Значок из логотипа для шапки (скруглённые углы)."""
    try:
        from PIL import Image, ImageDraw
        import sys as _sys
        base = getattr(_sys, "_MEIPASS", None)
        here = os.path.join(base, "cs2keys") if base else os.path.dirname(os.path.abspath(__file__))
        em = Image.open(os.path.join(here, "assets", "logo_emblem.png")).convert("RGBA")
        S = 3
        em = em.resize((int(em.width * h * S / em.height), h * S), Image.LANCZOS)
        mask = Image.new("L", em.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, em.width, em.height), radius=h * S // 6, fill=255)
        em.putalpha(mask)
        em = em.resize((em.width // S, h), Image.LANCZOS)
        return ctk.CTkImage(light_image=em, dark_image=em, size=em.size)
    except Exception:
        return None


def brand_font(size):
    fams = set(tk.font.families()) if hasattr(tk, "font") else set()
    return ctk.CTkFont(family=BRAND if BRAND in fams else F, size=size, weight="normal" if BRAND in fams else "bold")


def font(size=13, weight="normal"):
    return ctk.CTkFont(family=F, size=size, weight=weight)


def mix(a, b, t):
    a = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(x + (y - x) * t) for x, y in zip(a, b))


MODIFIER_KEYS = {"Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Meta_L", "Meta_R",
                 "Super_L", "Super_R", "Caps_Lock", "Num_Lock", "Win_L", "Win_R"}
NUMPAD = {0x60: ("KP_INS", "Num 0"), 0x61: ("KP_END", "Num 1"), 0x62: ("KP_DOWNARROW", "Num 2"),
          0x63: ("KP_PGDN", "Num 3"), 0x64: ("KP_LEFTARROW", "Num 4"), 0x65: ("KP_5", "Num 5"),
          0x66: ("KP_RIGHTARROW", "Num 6"), 0x67: ("KP_HOME", "Num 7"), 0x68: ("KP_UPARROW", "Num 8"),
          0x69: ("KP_PGUP", "Num 9"), 0x6A: ("KP_MULTIPLY", "Num *"), 0x6B: ("KP_PLUS", "Num +"),
          0x6D: ("KP_MINUS", "Num −"), 0x6E: ("KP_DEL", "Num ."), 0x6F: ("KP_SLASH", "Num /")}
CS2_SPECIAL = {"Home": "HOME", "End": "END", "Insert": "INS", "Delete": "DEL", "Prior": "PGUP", "Next": "PGDN",
               "Up": "UPARROW", "Down": "DOWNARROW", "Left": "LEFTARROW", "Right": "RIGHTARROW",
               "space": "SPACE", "Tab": "TAB", "BackSpace": "BACKSPACE", "Return": "ENTER", "Pause": "PAUSE"}


def cs2_pretty(name):
    """Как показать название клавиши CS2 человеку: KP_5 → Num 5."""
    for code, (cs, pretty) in NUMPAD.items():
        if cs == name:
            return pretty
    if name == "KP_ENTER":
        return "Num Enter"
    return name.upper() if len(name) == 1 else name.replace("ARROW", "").title() if name.endswith("ARROW") else name


def event_to_hotkey(e):
    """Нажатие → [код Windows, модификаторы, подпись] для глобальной горячей клавиши."""
    if e.keysym in MODIFIER_KEYS:
        return None
    mods, parts = 0, []
    if e.state & 0x4:
        mods |= 2
        parts.append("Ctrl")
    if e.state & 0x20000 or e.state & 0x8 and os.name != "nt":
        mods |= 1
        parts.append("Alt")
    if e.state & 0x1:
        mods |= 4
        parts.append("Shift")
    vk = e.keycode
    if vk in NUMPAD:
        name = NUMPAD[vk][1]
    elif e.keysym == "KP_Enter":
        name = "Num Enter"
    elif len(e.keysym) == 1:
        name = e.keysym.upper()
    else:
        name = e.keysym
    return [vk, mods, "+".join(parts + [name])]


def event_to_cs2(e):
    """Нажатие → название клавиши для команды bind в CS2."""
    if e.keysym in MODIFIER_KEYS:
        return None
    if e.keycode in NUMPAD:
        return NUMPAD[e.keycode][0]
    if e.keysym == "KP_Enter":
        return "KP_ENTER"
    if e.keysym in CS2_SPECIAL:
        return CS2_SPECIAL[e.keysym]
    if len(e.keysym) == 1:
        return e.keysym.lower()
    if e.keysym.startswith("F") and e.keysym[1:].isdigit():
        return e.keysym
    return e.keysym.upper()


def to_recycle_bin(path):
    """В корзину Windows (можно восстановить). На других системах — обычное удаление."""
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            class SHFILEOPSTRUCTW(ctypes.Structure):
                _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR),
                            ("pTo", wintypes.LPCWSTR), ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL),
                            ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]
            FO_DELETE, FOF_ALLOWUNDO, FOF_NOCONFIRMATION, FOF_SILENT = 3, 0x40, 0x10, 0x4
            op = SHFILEOPSTRUCTW(None, FO_DELETE, os.path.abspath(path) + "\0", None,
                                 FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT, False, None, None)
            return ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op)) == 0 and not os.path.exists(path)
        os.remove(path)
        return True
    except Exception:
        return False


class Ribbon(tk.Canvas):
    """Анимированная цветная лента вместо полосы прогресса."""

    def __init__(self, master, height=8, bg=CARD):
        super().__init__(master, height=height, bg=bg, highlightthickness=0, bd=0)
        self.phase = 0.0
        self.job = None

    def start(self):
        if self.job is None:
            self._tick()

    def stop(self):
        if self.job is not None:
            self.after_cancel(self.job)
            self.job = None
        self.delete("all")

    def _tick(self):
        self.delete("all")
        w = max(1, self.winfo_width())
        h = int(self["height"])
        n = 48
        seg = w / n
        for i in range(n):
            p = (i / n + self.phase) % 1.0
            k = p * (len(RIBBON) - 1)
            j = int(k)
            col = mix(RIBBON[j], RIBBON[min(j + 1, len(RIBBON) - 1)], k - j)
            # лёгкая «волна» яркости
            glow = 0.5 + 0.5 * math.sin((i / n) * math.pi * 2 - self.phase * math.pi * 6)
            col = mix(col, "#ffffff", 0.15 * glow)
            self.create_rectangle(i * seg, 0, (i + 1) * seg + 1, h, fill=col, outline="")
        self.phase = (self.phase + 0.012) % 1.0
        self.job = self.after(30, self._tick)


class SafeNum:
    """Число из поля ввода: неправильный текст не роняет программу."""

    def __init__(self, var, cast, default):
        self.var, self.cast, self.default = var, cast, default

    def get(self):
        try:
            return self.cast(str(self.var.get()).replace(",", ".").strip() or self.default)
        except (ValueError, tk.TclError):
            return self.default

    def set(self, v):
        self.var.set(str(v))


class ModernApp(App):
    def __init__(self, root):
        super().__init__(root)
        self.gsi_cleanup()

    # ================= построение =================
    def _build(self):
        r = self.root
        r.title(APP)
        r.configure(fg_color=BG)
        r.geometry("600x300")
        r.minsize(560, 250)

        # переменные, которые использует логика
        self.speed_var = tk.StringVar(value=f"×{self.s['speed']:g}")
        self._off_sv = tk.StringVar(value=str(self.s["offset"]))
        self._wait_sv = tk.StringVar(value=str(self.s["wait"]))
        self._port_sv = tk.StringVar(value=str(self.s["port"]))
        self.offset_var = SafeNum(self._off_sv, int, 0)
        self.wait_var = SafeNum(self._wait_sv, float, 3.0)
        self.port_var = SafeNum(self._port_sv, int, 2121)
        self.follow_var = tk.BooleanVar(value=bool(self.s.get("follow", True)))
        self.binds_var = tk.BooleanVar(value=bool(self.s.get("binds_on", True)))
        self.chat_var = tk.BooleanVar(value=bool(self.s.get("chat", False)))
        self.ov_var = tk.BooleanVar(value=bool(self.s["overlay_on"]))
        self.move_var = tk.BooleanVar(value=False)
        self.tr_var = tk.BooleanVar(value=bool(self.s.get("overlay_transparent", True)))
        self.vp_var = tk.BooleanVar(value=bool(self.s.get("vpanel_on", True)))
        self.scale_var = tk.DoubleVar(value=float(self.s["scale"]))
        self.alpha_var = tk.DoubleVar(value=float(self.s["alpha"]))
        self.target_var = tk.StringVar(value=self.s.get("move_target", "kb"))

        self._build_screens()
        self._setup_dnd()

        r.bind("<space>", lambda e: (self.toggle() if not isinstance(e.widget, tk.Entry) else None))
        r.bind("<Left>", lambda e: self.seek(self.tick - 5 * TPS) if not isinstance(e.widget, tk.Entry) else None)
        r.bind("<Right>", lambda e: self.seek(self.tick + 5 * TPS) if not isinstance(e.widget, tk.Entry) else None)
        r.bind("<Prior>", lambda e: self.prev_round())
        r.bind("<Next>", lambda e: self.next_round())

    def _build_screens(self):
        r = self.root
        r.title(APP)
        self.start_screen = ctk.CTkScrollableFrame(r, fg_color=BG, corner_radius=0,
                                                   scrollbar_button_color=LINE, scrollbar_button_hover_color=MUTED)
        self.play_screen = ctk.CTkScrollableFrame(r, fg_color=BG, corner_radius=0,
                                                  scrollbar_button_color=LINE, scrollbar_button_hover_color=MUTED)
        self._build_start(self.start_screen)
        self._build_play(self.play_screen)
        self.start_screen.pack(fill="both", expand=True)
        if not hasattr(self, "_screen"):
            self._screen = "start"
        r.after(50, self._fit_start)

        # зона «отпустите файл» поверх окна при перетаскивании
        self.drop_zone = ctk.CTkFrame(r, fg_color=mix(BG, ACC, 0.12), corner_radius=18, border_width=2,
                                      border_color=ACC)
        self.label(self.drop_zone, "⇩", 40, "bold", ACC).place(relx=0.5, rely=0.42, anchor="center")
        self.label(self.drop_zone, "Отпустите, чтобы открыть демо", 16, "bold", TEXT).place(relx=0.5, rely=0.54,
                                                                                          anchor="center")

    # ---------- язык ----------
    def lang_switch(self, master):
        seg = ctk.CTkSegmentedButton(master, values=["RU", "EN"], command=self.set_lang_ui, width=80, height=26,
                                     selected_color=ACC, selected_hover_color=ACC_H, unselected_color=CARD2,
                                     unselected_hover_color=LINE, fg_color=CARD2, text_color=TEXT,
                                     font=font(11, "bold"))
        seg.set("EN" if i18n.LANG == "en" else "RU")
        return seg

    def set_lang_ui(self, value):
        lang = "en" if value == "EN" else "ru"
        if lang == i18n.LANG:
            return
        set_lang(lang)
        self.s["lang"] = lang
        save_settings(self.s)
        self.root.after(10, self._rebuild_ui)

    def _rebuild_ui(self):
        """Пересобирает экраны на новом языке, не трогая воспроизведение."""
        screen = getattr(self, "_screen", "start")
        pick_visible = self.info is not None and bool(self.pick_card.winfo_manager())
        for w in (self.start_screen, self.play_screen, self.drop_zone):
            w.destroy()
        self.round_btns = []
        self._build_screens()
        self._setup_dnd()
        if self.info and pick_visible:
            self._scan_done(self.info, remember=False)
        if self.data:
            self._fill_play(self.data)
            self._render(force=True)
        if screen == "play" and self.data:
            self.show_play()
        else:
            self.show_start()
        self._update_play_btn()
        for w in (self.overlay, self.vpanel):
            if w:
                w.set_scale(w.scale)

    def ask_yes_no(self, title, text, callback, yes="Перезапустить", no="Отмена"):
        dlg = ctk.CTkToplevel(self.root)
        dlg.title(tr(title))
        dlg.configure(fg_color=CARD)
        dlg.resizable(False, False)
        dlg.transient(self.root)
        self.label(dlg, title, 16, "bold", TEXT, anchor="w").pack(anchor="w", padx=22, pady=(18, 6))
        self.label(dlg, text, 12, anchor="w", justify="left", wraplength=420).pack(anchor="w", padx=22)
        row = ctk.CTkFrame(dlg, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=16)

        def done(v):
            dlg.grab_release()
            dlg.destroy()
            callback(v)
        self.btn(row, yes, lambda: done(True), primary=True).pack(side="left", padx=4)
        self.btn(row, no, lambda: done(False), width=90).pack(side="right", padx=4)
        dlg.protocol("WM_DELETE_WINDOW", lambda: done(False))
        dlg.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - dlg.winfo_width()) // 2
        dlg.geometry(f"+{max(0, x)}+{max(0, self.root.winfo_rooty() + 120)}")
        dlg.after(50, lambda: (dlg.lift(), dlg.focus_force(), dlg.grab_set()))

    def _vpanel_size(self):
        v = round(float(self.vscale_var.get()), 2)
        self.s["vpanel_scale"] = v
        save_settings(self.s)
        if self.vpanel and abs(self.vpanel.scale - v) > 0.02:
            self.vpanel.set_scale(v)

    # ---------- настройки клавиш ----------
    def version_button(self, master):
        """Номер версии. По клику открывается страница с версиями на GitHub (программа сама не обновляется)."""
        from .version import VERSION, RELEASES_URL
        import webbrowser
        return ctk.CTkButton(master, text=tr("Версия {v}").format(v=VERSION), height=20, width=10, corner_radius=6,
                             fg_color="transparent", hover_color=CARD2, text_color=MUTED, font=font(11),
                             command=lambda: webbrowser.open(RELEASES_URL))

    def donate_button(self, master):
        """Кнопка «Поддержать автора» — открывает страницу для донатов. Без ссылки не показывается."""
        from .version import DONATE_URL
        if not DONATE_URL:
            return None
        import webbrowser
        return ctk.CTkButton(master, text="♥  " + tr("Поддержать автора"), height=26, width=10, corner_radius=13,
                             fg_color="transparent", hover_color=CARD2, border_width=1, border_color=ACC,
                             text_color=ACC, font=font(12, "bold"), command=lambda: webbrowser.open(DONATE_URL))

    def gear(self, master):
        return ctk.CTkButton(master, text="⚙", width=30, height=26, corner_radius=8, fg_color=CARD2,
                             hover_color=LINE, text_color=TEXT, font=font(15), command=self.open_hotkeys)

    def _update_hints(self):
        if not hasattr(self, "hints_lbl"):
            return
        hk, ck = self.hotkey_table(), self.cs2_keys()
        short = {"toggle": "пауза", "resync": "синхронизация", "camera": "камера", "prev_round": "раунд назад",
                 "next_round": "раунд вперёд", "slow": "×0.5", "fast": "×4", "pause": "пауза", "normal": "×1"}
        a = " · ".join(f"{cs2_pretty(ck[k])} {tr(short.get(k, ''))}" for k, _, _ in CS2_ACTIONS if ck.get(k))
        b = " · ".join(f"{hk[k][2]} {tr(short.get(k, ''))}" for k, _ in HOTKEY_ACTIONS if hk.get(k) and hk[k][0])
        self.hints_lbl.configure(text=f"{tr('В CS2')}: {a}\n{tr('Поверх игры')}: {b}")

    def open_hotkeys(self):
        dlg = ctk.CTkToplevel(self.root)
        dlg.title(tr("Настройка клавиш"))
        dlg.configure(fg_color=BG)
        dlg.resizable(False, False)
        dlg.transient(self.root)
        hk = {k: list(v) for k, v in self.hotkey_table().items()}
        ck = dict(self.cs2_keys())
        state = {"wait": None}           # что сейчас ждёт нажатия: ("hk"|"cs", действие, кнопка)
        btns = {}

        self.label(dlg, "Настройка клавиш", 18, "bold", TEXT).pack(anchor="w", padx=22, pady=(18, 2))
        self.label(dlg, "Нажмите на клавишу справа и затем новую клавишу. Esc — отмена.", 11).pack(anchor="w", padx=22)

        def show(kind, act):
            if kind == "hk":
                v = hk.get(act)
                return v[2] if v and v[0] else "—"
            v = ck.get(act)
            return cs2_pretty(v) if v else "—"

        def refresh():
            for (kind, act), b in btns.items():
                waiting = state["wait"] and state["wait"][:2] == (kind, act)
                b.configure(text=tr("нажмите клавишу…") if waiting else show(kind, act),
                            fg_color=ACC if waiting else CARD2, border_color=ACC if waiting else LINE)

        def ask(kind, act):
            state["wait"] = (kind, act)
            refresh()
            dlg.focus_force()

        def on_key(e):
            if not state["wait"]:
                return
            kind, act = state["wait"]
            if e.keysym == "Escape":
                state["wait"] = None
                return refresh()
            if kind == "hk":
                v = event_to_hotkey(e)
                if not v:
                    return
                for other, ov in hk.items():            # одна клавиша — одно действие
                    if other != act and ov and ov[0] == v[0] and ov[1] == v[1]:
                        hk[other] = [0, 0, "—"]
                hk[act] = v
            else:
                v = event_to_cs2(e)
                if not v:
                    return
                for other, ov in ck.items():
                    if other != act and ov == v:
                        ck[other] = ""
                ck[act] = v
            state["wait"] = None
            refresh()
        dlg.bind("<KeyPress>", on_key)

        def block(title, sub, rows, kind):
            c = self.card(dlg)
            c.pack(fill="x", padx=16, pady=6)
            self.label(c, title, 13, "bold", TEXT).pack(anchor="w", padx=16, pady=(12, 0))
            self.label(c, sub, 11).pack(anchor="w", padx=16, pady=(0, 6))
            g = ctk.CTkFrame(c, fg_color="transparent")
            g.pack(fill="x", padx=12, pady=(0, 12))
            g.grid_columnconfigure(0, weight=1)
            for i, (act, lbl) in enumerate(rows):
                self.label(g, lbl, 12, color=TEXT, anchor="w").grid(row=i, column=0, sticky="w", padx=4, pady=3)
                b = ctk.CTkButton(g, text="", width=150, height=30, corner_radius=8, fg_color=CARD2, hover_color=LINE,
                                  border_width=1, border_color=LINE, text_color=TEXT, font=font(12, "bold"),
                                  command=lambda k=kind, a=act: ask(k, a))
                b.grid(row=i, column=1, pady=3)
                btns[(kind, act)] = b
        block("Поверх игры", "Работают, даже когда активно окно CS2", HOTKEY_ACTIONS, "hk")
        block("Бинды в CS2", "Прописываются в игру при включённом переключателе «Бинды»",
              [(a, lbl) for a, lbl, _ in CS2_ACTIONS], "cs")
        refresh()

        def reset():
            hk.clear()
            hk.update({k: list(v) for k, v in DEFAULT_HOTKEYS.items()})
            ck.clear()
            ck.update(DEFAULT_CS2_KEYS)
            state["wait"] = None
            refresh()

        def save():
            self.s["hotkeys"] = hk
            self.s["cs2_keys"] = ck
            save_settings(self.s)
            dlg.grab_release()
            dlg.destroy()
            self.reload_hotkeys()
            self.rebind_cs2()
            self._update_hints()
            self.msg("Клавиши сохранены.")
        row = ctk.CTkFrame(dlg, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(4, 16))
        self.btn(row, "По умолчанию", reset).pack(side="left")
        self.btn(row, "Отмена", lambda: (dlg.grab_release(), dlg.destroy()), width=90).pack(side="right", padx=(6, 0))
        self.btn(row, "Сохранить", save, primary=True, width=120).pack(side="right")
        dlg.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - dlg.winfo_width()) // 2
        dlg.geometry(f"+{max(0, x)}+{max(0, self.root.winfo_rooty() + 30)}")
        dlg.after(50, lambda: (dlg.lift(), dlg.focus_force(), dlg.grab_set()))
        self._hk_dialog = dlg

    # ---------- общие элементы ----------
    def card(self, master, **kw):
        return ctk.CTkFrame(master, fg_color=CARD, corner_radius=16, border_width=1, border_color=LINE, **kw)

    def btn(self, master, text, command, primary=False, **kw):
        kw.setdefault("height", 36)
        kw.setdefault("corner_radius", 10)
        kw.setdefault("font", font(13, "bold" if primary else "normal"))
        return ctk.CTkButton(master, text=tr(text), command=command,
                             fg_color=ACC if primary else CARD2, hover_color=ACC_H if primary else LINE,
                             text_color="#ffffff" if primary else TEXT, **kw)

    def switch(self, master, text, var, command):
        return ctk.CTkSwitch(master, text=tr(text), variable=var, command=command, onvalue=True, offvalue=False,
                             progress_color=ACC, button_color=TEXT, button_hover_color="#ffffff",
                             fg_color=LINE, text_color=TEXT, font=font(12))

    def label(self, master, text, size=12, weight="normal", color=MUTED, **kw):
        return ctk.CTkLabel(master, text=tr(text), font=font(size, weight), text_color=color, **kw)

    # ---------- экран 1: демо и игрок ----------
    def _build_start(self, root):
        head = ctk.CTkFrame(root, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=(22, 10))
        self.gear(head).pack(side="right", anchor="n", padx=(6, 0))
        self.lang_switch(head).pack(side="right", anchor="n")

        mark = ctk.CTkFrame(head, fg_color="transparent")
        mark.pack(anchor="w")
        img = brand_image()
        if img is not None:
            ctk.CTkLabel(mark, text="", image=img).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(mark, text="CS2", font=brand_font(28), text_color=ACC).pack(side="left")
        ctk.CTkLabel(mark, text=" DEMO TO KEYBOARD", font=brand_font(28), text_color=TEXT).pack(side="left")
        self.label(head, "Нажатия игрока из демо — поверх игры и синхронно с ней", 12).pack(anchor="w")
        brow = ctk.CTkFrame(head, fg_color="transparent")
        brow.pack(anchor="w", pady=(6, 0))
        self.version_button(brow).pack(side="left")
        don = self.donate_button(brow)
        if don is not None:
            don.pack(side="left", padx=(8, 0))

        c = self.card(root)
        c.pack(fill="x", padx=20, pady=6)
        row = ctk.CTkFrame(c, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(16, 10))
        self.btn(row, "Открыть демо", self.open_demo, primary=True, width=170, height=42,
                 font=font(14, "bold")).pack(side="left")
        self.btn(row, "Файл клавиатуры…", self.open_keys, height=42).pack(side="left", padx=8)
        self.drop_hint = self.label(c, "", 11, anchor="w")
        self.drop_hint.pack(anchor="w", padx=18, pady=(0, 10))
        self.recent_title = self.label(c, "НЕДАВНИЕ", 11, "bold")
        self.recent_box = ctk.CTkFrame(c, fg_color="transparent")
        self._fill_recent()

        # карточка выбора игрока — появляется после чтения демо
        self.pick_card = self.card(root)
        top = ctk.CTkFrame(self.pick_card, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(14, 4))
        self.pick_title = self.label(top, "", 15, "bold", TEXT, anchor="w")
        self.pick_title.pack(anchor="w")
        self.pick_sub = self.label(top, "", 12, anchor="w", justify="left")
        self.pick_sub.pack(anchor="w")
        self.teams_box = ctk.CTkFrame(self.pick_card, fg_color="transparent")
        self.teams_box.pack(fill="x", padx=12, pady=(6, 8))
        self.ribbon = Ribbon(self.pick_card, height=8)
        self.busy_lbl = self.label(self.pick_card, "", 12, anchor="w")

        # «пустые» объекты, к которым обращается общая логика
        self.extract_btn = ctk.CTkButton(root)
        self.demo_lbl = ctk.CTkLabel(root)

    def _fill_recent(self):
        for w in self.recent_box.winfo_children():
            w.destroy()
        items = [x for x in self.s.get("recent", []) if os.path.exists(x.get("path", ""))][:5]
        if not items:
            self.recent_title.pack_forget()
            self.recent_box.pack_forget()
            self.label(self.recent_box, "").pack()
            return
        self.recent_title.pack(anchor="w", padx=18, pady=(2, 2))
        self.recent_box.pack(fill="x", padx=12, pady=(0, 12))
        for it in items:
            rowf = ctk.CTkFrame(self.recent_box, fg_color=CARD2, corner_radius=10, cursor="hand2")
            rowf.pack(fill="x", pady=3)
            rowf.grid_columnconfigure(0, weight=1)
            txt = ctk.CTkFrame(rowf, fg_color="transparent")
            txt.grid(row=0, column=0, sticky="ew")
            name = os.path.basename(it["path"])
            name = name if len(name) < 48 else name[:45] + "…"
            a = self.label(txt, name, 13, "bold", TEXT, anchor="w")
            a.pack(fill="x", padx=14, pady=(6, 0))
            b = self.label(txt, f"{it.get('map') or '?'}   ·   раундов {it.get('rounds', '?')}   ·   "
                                f"{time.strftime('%d.%m %H:%M', time.localtime(it.get('ts', 0)))}", 11, anchor="w")
            b.pack(fill="x", padx=14, pady=(0, 6))
            trash = ctk.CTkButton(rowf, text="🗑", width=34, height=34, corner_radius=8, fg_color="transparent",
                                  hover_color=mix(CARD2, LOSS, 0.45), text_color=MUTED, font=font(15),
                                  command=lambda p=it["path"]: self.confirm_delete(p))
            trash.grid(row=0, column=1, padx=(4, 8))
            go = lambda e, p=it["path"]: self.open_demo_path(p)
            on = lambda e, f=rowf: f.configure(fg_color=LINE)
            off = lambda e, f=rowf: f.configure(fg_color=CARD2)
            for w in (rowf, txt, a, b):
                w.bind("<Button-1>", go)
                w.bind("<Enter>", on)
                w.bind("<Leave>", off)

    # ---------- удаление демо ----------
    def confirm_delete(self, path):
        """Тёмное окно подтверждения: убрать из списка или удалить файл (в корзину)."""
        dlg = ctk.CTkToplevel(self.root)
        dlg.title(tr("Удалить демо"))
        dlg.configure(fg_color=CARD)
        dlg.resizable(False, False)
        dlg.transient(self.root)
        name = os.path.basename(path)
        self.label(dlg, "Удалить демо?", 17, "bold", TEXT).pack(anchor="w", padx=22, pady=(20, 4))
        self.label(dlg, name if len(name) < 56 else name[:53] + "…", 12, anchor="w").pack(anchor="w", padx=22)
        self.label(dlg, "«Убрать из списка» — файл останется на диске.\n"
                        "«Удалить файл» — демо отправится в корзину Windows.", 11, anchor="w",
                   justify="left").pack(anchor="w", padx=22, pady=(10, 14))
        row = ctk.CTkFrame(dlg, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(0, 18))

        def done(kind):
            dlg.grab_release()
            dlg.destroy()
            if kind:
                self.delete_demo(path, from_disk=(kind == "disk"))
        ctk.CTkButton(row, text=tr("Удалить файл"), fg_color=LOSS, hover_color=mix(LOSS, "#ffffff", 0.15),
                      text_color="#ffffff", corner_radius=10, height=36, font=font(13, "bold"),
                      command=lambda: done("disk")).pack(side="left", padx=4)
        self.btn(row, "Убрать из списка", lambda: done("list")).pack(side="left", padx=4)
        self.btn(row, "Отмена", lambda: done(None), width=90).pack(side="right", padx=4)
        dlg.bind("<Escape>", lambda e: done(None))
        dlg.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - dlg.winfo_width()) // 2
        y = self.root.winfo_rooty() + 160
        dlg.geometry(f"+{max(0, x)}+{max(0, y)}")
        dlg.after(50, lambda: (dlg.lift(), dlg.focus_force(), dlg.grab_set()))

    def delete_demo(self, path, from_disk=False):
        self.s["recent"] = [x for x in self.s.get("recent", []) if x.get("path") != path]
        save_settings(self.s)
        # кэш этого демо тоже больше не нужен
        try:
            prefix = os.path.basename(self._cache_name(path, "")).rstrip(".")
            for f in os.listdir(CACHE_DIR):
                if f.startswith(prefix + "."):
                    os.remove(os.path.join(CACHE_DIR, f))
        except OSError:
            pass
        if from_disk and os.path.exists(path):
            if not to_recycle_bin(path):
                messagebox.showerror(APP, "Не удалось удалить файл — возможно, он открыт в CS2.")
        if self.info and self.info.get("path") == path:
            self.info = None
            self.pick_card.pack_forget()
        self._fill_recent()
        self._fit_start()

    # ---------- перетаскивание файлов ----------
    def _setup_dnd(self):
        if getattr(self, "dnd_ok", False):
            self.drop_hint.configure(text=tr("или перетащите файл .dem в это окно"))
            return
        try:
            from tkinterdnd2 import DND_FILES
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind("<<DropEnter>>", self._drop_enter)
            self.root.dnd_bind("<<DropLeave>>", self._drop_leave)
            self.root.dnd_bind("<<Drop>>", self._drop)
            self.dnd_ok = True
        except Exception:
            self.dnd_ok = False
        if self.dnd_ok:
            self.drop_hint.configure(text=tr("или перетащите файл .dem в это окно"))
        else:
            self.drop_hint.pack_forget()

    def _drop_enter(self, e):
        self.drop_zone.place(relx=0.03, rely=0.03, relwidth=0.94, relheight=0.94)
        self.drop_zone.lift()
        return e.action

    def _drop_leave(self, e):
        self.drop_zone.place_forget()
        return e.action

    def _drop(self, e):
        self.drop_zone.place_forget()
        files = [f for f in self.root.tk.splitlist(e.data)]
        demo = next((f for f in files if f.lower().endswith(".dem")), None)
        keys = next((f for f in files if f.lower().endswith(".cs2keys")), None)
        if demo:
            self.show_start()
            self.open_demo_path(demo)
        elif keys:
            self.open_keys_path(keys)
        elif any(f.lower().endswith(".zst") for f in files):
            messagebox.showinfo(APP, "Это сжатое демо FACEIT (.dem.zst). Распакуйте его в .dem (WinRAR или 7-Zip ZS) "
                                     "и перетащите ещё раз.")
        else:
            messagebox.showinfo(APP, "Перетащите файл демо .dem или файл клавиатуры .cs2keys.")
        return e.action

    # ---------- экран 2: воспроизведение ----------
    def _build_play(self, root):
        top = ctk.CTkFrame(root, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(14, 6))
        ctk.CTkButton(top, text="←", width=38, height=38, corner_radius=12, fg_color=CARD2, hover_color=LINE,
                      text_color=TEXT, font=font(16, "bold"), command=self.show_start).pack(side="left")
        tt = ctk.CTkFrame(top, fg_color="transparent")
        tt.pack(side="left", padx=12)
        self.player_lbl = ctk.CTkLabel(tt, text="", font=brand_font(22), text_color=TEXT, anchor="w")
        self.player_lbl.pack(anchor="w")
        self.demo_lbl2 = self.label(tt, "", 11, anchor="w")
        self.demo_lbl2.pack(anchor="w")
        self.gear(top).pack(side="right", padx=(6, 0))
        self.lang_switch(top).pack(side="right", padx=(8, 0))

        self.status_pill = ctk.CTkFrame(top, fg_color=CARD2, corner_radius=14)
        self.status_pill.pack(side="right")
        self.dot_lbl = self.label(self.status_pill, "●", 13, color=LOSS)
        self.dot_lbl.pack(side="left", padx=(10, 4), pady=4)
        self.cs_lbl = self.label(self.status_pill, "CS2 не подключена", 12, color=TEXT)
        self.cs_lbl.pack(side="left", padx=(0, 12))

        # --- воспроизведение ---
        # полоса «CS2 не подключена — запустить» (исчезает, когда связь есть)
        self.launch_bar = ctk.CTkFrame(root, fg_color=mix(CARD, ACC, 0.10), corner_radius=16, border_width=1,
                                       border_color=mix(LINE, ACC, 0.5))
        lb_txt = ctk.CTkFrame(self.launch_bar, fg_color="transparent")
        lb_txt.pack(side="left", padx=16, pady=10)
        self.label(lb_txt, "CS2 не подключена", 13, "bold", TEXT, anchor="w").pack(anchor="w")
        self.label(lb_txt, "Программа сама запустит игру с параметрами для демо", 11, anchor="w").pack(anchor="w")
        self.launch_btn = self.btn(self.launch_bar, "Запустить CS2 и демо", self.launch_and_load, primary=True,
                                   height=40, font=font(13, "bold"))
        self.launch_btn.pack(side="right", padx=14)
        self.launch_bar.pack(fill="x", padx=14, pady=(6, 0))

        pc = self.card(root)
        pc.pack(fill="x", padx=14, pady=6)
        self._play_card = pc
        self.rounds_fr = ctk.CTkFrame(pc, fg_color="transparent")
        self.rounds_fr.pack(fill="x", padx=12, pady=(12, 4))
        mid = ctk.CTkFrame(pc, fg_color="transparent")
        mid.pack(fill="x", padx=12, pady=6)
        self.play_btn = ctk.CTkButton(mid, text="▶", width=64, height=64, corner_radius=32, fg_color=ACC,
                                      hover_color=ACC_H, font=font(24, "bold"), command=self.toggle)
        self.play_btn.pack(side="left")
        clk = ctk.CTkFrame(mid, fg_color="transparent")
        clk.pack(side="left", padx=14)
        self.clock = ctk.CTkLabel(clk, text="0:00.00", font=brand_font(30), text_color=TEXT, anchor="w")
        self.clock.pack(anchor="w")
        self.clock_sub = self.label(clk, "—", 11, anchor="w")
        self.clock_sub.pack(anchor="w")
        nav = ctk.CTkFrame(mid, fg_color="transparent")
        nav.pack(side="right")
        self.btn(nav, "⏮", self.prev_round, width=44).pack(side="left", padx=2)
        self.btn(nav, "⏭", self.next_round, width=44).pack(side="left", padx=2)
        self.resync_btn = self.btn(nav, "⟳", self.play_synced, width=44)
        self.resync_btn.pack(side="left", padx=2)
        self.timeline = ctk.CTkSlider(pc, from_=0, to=1, command=self._timeline_moved, height=16,
                                      button_color=TEXT, button_hover_color="#ffffff", progress_color=ACC,
                                      fg_color=LINE)
        self.timeline.pack(fill="x", padx=14, pady=(4, 8))
        sp = ctk.CTkFrame(pc, fg_color="transparent")
        sp.pack(fill="x", padx=12, pady=(0, 12))
        self.label(sp, "Скорость", 12).pack(side="left", padx=(2, 8))
        self.speed_seg = ctk.CTkSegmentedButton(sp, values=["×0.25", "×0.5", "×1", "×2", "×4"],
                                                command=lambda v: self.set_speed(float(v[1:])),
                                                selected_color=ACC, selected_hover_color=ACC_H,
                                                unselected_color=CARD2, unselected_hover_color=LINE,
                                                fg_color=CARD2, text_color=TEXT, font=font(12, "bold"))
        self.speed_seg.pack(side="left")
        self.msg_lbl = self.label(pc, "", 11, anchor="w", wraplength=520, justify="left")
        self.msg_lbl.pack(fill="x", padx=16, pady=(0, 10))

        # --- раскрывающиеся разделы ---
        s1 = self.section(root, "CS2 и управление")
        row = ctk.CTkFrame(s1, fg_color="transparent")
        row.pack(fill="x", pady=(0, 6))
        self.btn(row, "Проверить связь", self.ping).pack(side="left")
        self.load_btn = self.btn(row, "Загрузить демо в CS2", self.load_demo)
        self.load_btn.pack(side="left", padx=6)
        self.cam_btn = self.btn(row, "Камера на игрока", self.camera)
        self.cam_btn.pack(side="left")
        self.switch(s1, "Следовать за управлением в CS2", self.follow_var, self._follow_changed).pack(anchor="w", pady=3)
        rb = ctk.CTkFrame(s1, fg_color="transparent")
        rb.pack(fill="x", pady=3)
        self.switch(rb, "Бинды на цифровом блоке", self.binds_var, self._binds_changed).pack(side="left")
        ctk.CTkButton(rb, text="вернуть мои", width=90, height=26, corner_radius=8, fg_color="transparent",
                      hover_color=LINE, text_color=MUTED, font=font(11), command=self.restore_binds).pack(side="left", padx=8)
        self.hints_lbl = self.label(s1, "", 11, anchor="w", justify="left")
        self.hints_lbl.pack(anchor="w", pady=(2, 0))
        self._update_hints()

        s2 = self.section(root, "Голос и чат (FACEIT)")
        self.voice_seg = ctk.CTkSegmentedButton(s2, values=[tr(lbl) for _, lbl in VOICE_MODES],
                                                command=self._voice_seg,
                                                selected_color=ACC, selected_hover_color=ACC_H,
                                                unselected_color=CARD2, unselected_hover_color=LINE,
                                                fg_color=CARD2, text_color=TEXT, font=font(12, "bold"))
        self.voice_seg.pack(anchor="w", pady=(0, 6))
        vr = ctk.CTkFrame(s2, fg_color="transparent")
        vr.pack(fill="x")
        self.switch(vr, "Чат игроков", self.chat_var, self._chat_changed).pack(side="left")
        self.switch(vr, "Панель «кто говорит»", self.vp_var, self._vpanel_toggle).pack(side="left", padx=16)

        s3 = self.section(root, "Клавиатура поверх игры")
        g = ctk.CTkFrame(s3, fg_color="transparent")
        g.pack(fill="x")
        self.switch(g, "Показывать", self.ov_var, self._overlay_toggle).grid(row=0, column=0, sticky="w", pady=3)
        self.switch(g, "Прозрачный фон", self.tr_var, self._overlay_transparent).grid(row=0, column=1, sticky="w", padx=16)
        self.switch(g, "Режим перемещения", self.move_var, self._overlay_move).grid(row=1, column=0, sticky="w", pady=3)
        self.btn(g, "Найти на экране", self._overlay_find, height=30).grid(row=1, column=1, sticky="w", padx=16)
        sl = ctk.CTkFrame(s3, fg_color="transparent")
        sl.pack(fill="x", pady=(8, 4))
        self.label(sl, "Размер", 12).grid(row=0, column=0, sticky="w")
        ctk.CTkSlider(sl, from_=0.5, to=1.8, variable=self.scale_var, command=lambda v: self._overlay_scale(),
                      button_color=TEXT, progress_color=ACC, fg_color=LINE, width=180).grid(row=0, column=1, padx=8)
        self.label(sl, "Прозрачность", 12).grid(row=1, column=0, sticky="w")
        ctk.CTkSlider(sl, from_=0.3, to=1.0, variable=self.alpha_var, command=lambda v: self._overlay_alpha(),
                      button_color=TEXT, progress_color=ACC, fg_color=LINE, width=180).grid(row=1, column=1, padx=8)
        self.vscale_var = tk.DoubleVar(value=float(self.s.get("vpanel_scale", 1.0)))
        self.label(sl, "Панель голоса", 12).grid(row=2, column=0, sticky="w")
        ctk.CTkSlider(sl, from_=0.4, to=1.6, variable=self.vscale_var, command=lambda v: self._vpanel_size(),
                      button_color=TEXT, progress_color=ACC, fg_color=LINE, width=180).grid(row=2, column=1, padx=8)
        mv = ctk.CTkFrame(s3, fg_color="transparent")
        mv.pack(fill="x", pady=(8, 2))
        left = ctk.CTkFrame(mv, fg_color="transparent")
        left.pack(side="left")
        self.label(left, "Двигать", 12).pack(anchor="w")
        names = {"kb": tr("клавиатуру"), "voice": tr("панель голоса")}
        tseg = ctk.CTkSegmentedButton(left, values=list(names.values()),
                                      command=lambda v: (self.target_var.set({b: a for a, b in names.items()}[v]),
                                                         self._target_changed()),
                                      selected_color=ACC, selected_hover_color=ACC_H, unselected_color=CARD2,
                                      unselected_hover_color=LINE, fg_color=CARD2, text_color=TEXT,
                                      font=font(12, "bold"))
        tseg.set(names.get(self.target_var.get(), names["kb"]))
        tseg.pack(anchor="w", pady=4)
        pad = tk.Canvas(mv, width=200, height=64, bg=CARD2, highlightthickness=0, cursor="fleur")
        pad.pack(side="left", padx=12)
        pad.create_text(100, 24, text="✥  Зажмите и тащите", fill=TEXT, font=(F, 10, "bold"))
        pad.create_text(100, 44, text="колесо мыши — размер", fill=MUTED, font=(F, 9))
        pad.bind("<ButtonPress-1>", self._pad_start)
        pad.bind("<B1-Motion>", self._pad_move)
        pad.bind("<ButtonRelease-1>", self._pad_end)
        pad.bind("<MouseWheel>", self._pad_wheel)
        nud = ctk.CTkFrame(mv, fg_color="transparent")
        nud.pack(side="left")
        for (dx, dy, t, r_, c_) in ((0, -20, "▲", 0, 1), (-20, 0, "◀", 1, 0), (20, 0, "▶", 1, 2), (0, 20, "▼", 2, 1)):
            ctk.CTkButton(nud, text=t, width=28, height=22, corner_radius=6, fg_color=CARD2, hover_color=LINE,
                          text_color=TEXT, font=font(10), command=lambda a=dx, b=dy: self._overlay_nudge(a, b)
                          ).grid(row=r_, column=c_, padx=1, pady=1)

        s4 = self.section(root, "Точная настройка")
        fr = ctk.CTkFrame(s4, fg_color="transparent")
        fr.pack(fill="x")
        for i, (lbl, sv, hint) in enumerate((("Поправка, тиков", self._off_sv, "1 тик = 1/64 с"),
                                             ("Ждать перемотку, с", self._wait_sv, "если CS2 не успевает"),
                                             ("Порт консоли", self._port_sv, "как в -netconport"))):
            self.label(fr, lbl, 12, color=TEXT).grid(row=i, column=0, sticky="w", pady=3)
            e = ctk.CTkEntry(fr, textvariable=sv, width=80, fg_color=CARD2, border_color=LINE, text_color=TEXT)
            e.grid(row=i, column=1, padx=8)
            e.bind("<FocusOut>", lambda ev: (self._save_numbers(), self._port_changed()))
            e.bind("<Return>", lambda ev: (self._save_numbers(), self._port_changed()))
            self.label(fr, hint, 11).grid(row=i, column=2, sticky="w")
        self.tools_var = tk.BooleanVar(value=bool(self.s.get("use_tools", True)))
        self.switch(s4, "Запускать CS2 через Workshop Tools (нужно для консоли на Windows)", self.tools_var,
                    lambda: (self.s.__setitem__("use_tools", bool(self.tools_var.get())), save_settings(self.s))
                    ).pack(anchor="w", pady=(8, 2))
        self.btn(s4, "Сохранить файл клавиатуры…", self.save_keys, height=30).pack(anchor="w", pady=(8, 4))
        self.save_btn = ctk.CTkButton(root)          # совместимость с общей логикой
        self.label(s4, "Консоль CS2", 11, "bold").pack(anchor="w", pady=(6, 2))
        self.log = ctk.CTkTextbox(s4, height=110, fg_color=CARD2, text_color=MUTED, font=ctk.CTkFont("Consolas", 11),
                                  corner_radius=10)
        self.log.pack(fill="x")
        self.log.configure(state="disabled")

    def section(self, master, title, opened=False):
        title = tr(title)
        wrap = self.card(master)
        wrap.pack(fill="x", padx=14, pady=5)
        body = ctk.CTkFrame(wrap, fg_color="transparent")
        head = ctk.CTkButton(wrap, text=("▾  " if opened else "▸  ") + title, anchor="w", fg_color="transparent",
                             hover_color=CARD2, text_color=TEXT, font=font(13, "bold"), height=40, corner_radius=14)

        def flip():
            if body.winfo_ismapped():
                body.pack_forget()
                head.configure(text="▸  " + title)
            else:
                body.pack(fill="x", padx=16, pady=(0, 14))
                head.configure(text="▾  " + title)
        head.configure(command=flip)
        head.pack(fill="x", padx=4, pady=4)
        if opened:
            flip()
        return body

    # ================= экраны =================
    def _fit_start(self):
        """Высота стартового окна — по содержимому: без пустого места при первом запуске."""
        if getattr(self, "_screen", "start") != "start":
            return
        self.root.update_idletasks()
        try:
            k = ctk.ScalingTracker.get_window_scaling(self.root)
        except Exception:
            k = 1.0
        h = int(self.start_screen.winfo_reqheight() / k) + 24
        fits = h <= 800
        h = max(200, min(h, 800))
        self.root.minsize(560, min(h, 200))
        self.root.geometry(f"600x{h}")
        # полоса прокрутки — только когда содержимое не помещается
        try:
            sb = self.start_screen._scrollbar
            sb.grid_remove() if fits else sb.grid()
        except Exception:
            pass

    def show_start(self):
        self._screen = "start"
        self.play_screen.pack_forget()
        self._fill_recent()
        self.start_screen.pack(fill="both", expand=True)
        self._fit_start()

    def show_play(self):
        self._screen = "play"
        self.root.minsize(560, 560)
        self.start_screen.pack_forget()
        self.play_screen.pack(fill="both", expand=True)
        self.root.geometry("640x760")

    # ================= демо и игрок =================
    def _scan_done(self, info, remember=True):
        self.info = info
        if remember:
            rec = [x for x in self.s.get("recent", []) if x.get("path") != info["path"]]
            rec.insert(0, {"path": info["path"], "map": info.get("map"), "rounds": len(info["rounds"]), "ts": time.time()})
            self.s["recent"] = rec[:8]
            save_settings(self.s)

        for w in self.teams_box.winfo_children():
            w.destroy()
        first = info["rounds"][0]["teams"] if info["rounds"] else {}
        wins = {}
        for rd in info["rounds"]:
            for sid, tm in rd["teams"].items():
                if tm == rd["winner"]:
                    wins[sid] = wins.get(sid, 0) + 1
        groups = {3: [], 2: []}
        for p in info["players"]:
            groups.setdefault(first.get(p["steamid"], p["team"]), []).append(p)
        cols = [(3, "Начали за КТ", CT_COL), (2, "Начали за Т", T_COL)]
        for ci, (side, title, col) in enumerate(cols):
            colf = ctk.CTkFrame(self.teams_box, fg_color="transparent")
            colf.grid(row=0, column=ci, sticky="nsew", padx=4)
            self.teams_box.grid_columnconfigure(ci, weight=1)
            members = sorted(groups.get(side, []), key=lambda p: p["name"].lower())
            score = wins.get(members[0]["steamid"], 0) if members else 0
            hdr = ctk.CTkFrame(colf, fg_color="transparent")
            hdr.pack(fill="x", pady=(0, 4))
            ctk.CTkFrame(hdr, width=4, height=18, fg_color=col, corner_radius=2).pack(side="left", padx=(2, 8))
            title = tr(title)
            self.label(hdr, title, 12, "bold", TEXT).pack(side="left")
            self.label(hdr, str(score), 16, "bold", col).pack(side="right", padx=4)
            for p in members:
                ctk.CTkButton(colf, text=p["name"], anchor="w", height=40, corner_radius=12, fg_color=CARD2,
                              hover_color=mix(CARD2, col, 0.35), border_width=1, border_color=LINE,
                              text_color=TEXT, font=font(13, "bold"),
                              command=lambda pl=p: self.pick_player(pl)).pack(fill="x", pady=3)
        self.pick_title.configure(text=info["map"] or tr("Демо"))
        nm = os.path.basename(info["path"])
        self.pick_sub.configure(text=(nm if len(nm) < 60 else nm[:57] + "…") + "\n" +
                                tr("Выберите игрока — нажатия извлекутся автоматически"))
        self.pick_card.pack(fill="x", padx=20, pady=8)
        self.load_btn.configure(state="normal")
        self._fit_start()

    def pick_player(self, p):
        cache = self._cache_name(self.info["path"], f"{p['steamid']}.v{extract.FORMAT_VERSION}.cs2keys")
        if os.path.exists(cache):
            try:
                with open(cache, encoding="utf-8") as f:
                    return self._set_data(json.load(f))
            except Exception:
                pass
        self._busy(True, f"Извлекаю нажатия {p['name']}… около минуты")
        fut = self.pool.submit(_extract_job, self.info["path"], p["steamid"], self.info)
        fut.add_done_callback(lambda f: self.ui(lambda: self._extract_result(f, cache)))

    def open_demo_path(self, path):
        self.pick_card.pack(fill="x", padx=20, pady=8)
        self.pick_title.configure(text=tr("Читаю демо…"))
        self.pick_sub.configure(text=os.path.basename(path))
        for w in self.teams_box.winfo_children():
            w.destroy()
        super().open_demo_path(path)
        self._fit_start()

    def _busy(self, on, text=""):
        self.root.after(10, self._fit_start)
        self.busy_lbl.configure(text=tr(text))
        if on:
            self.ribbon.pack(fill="x", padx=16, pady=(4, 4))
            self.busy_lbl.pack(fill="x", padx=18, pady=(0, 12))
            self.ribbon.start()
            for w in self.teams_box.winfo_children():
                for b in w.winfo_children():
                    if isinstance(b, ctk.CTkButton):
                        b.configure(state="disabled")
        else:
            self.ribbon.stop()
            self.ribbon.pack_forget()
            self.busy_lbl.pack_forget()
            for w in self.teams_box.winfo_children():
                for b in w.winfo_children():
                    if isinstance(b, ctk.CTkButton):
                        b.configure(state="normal")

    def _set_data(self, d):
        self.data = d
        rle = d["rle"]
        self.T, self.M = rle[0::2], rle[1::2]
        self.WT, self.WI = d["wr"][0::2], d["wr"][1::2]
        self.GT = [g[0] for g in d["gr"]]
        self.rounds = d["rounds"]
        self.t0 = self.rounds[0]["s"] if self.rounds else d["start"]
        self.t1 = d["end"]
        self._fill_play(d)
        self.playing = False
        self.tick = float(self.rounds[0]["f"] - 3 * TPS) if self.rounds else float(self.t0)
        self.show_play()
        self._ensure_overlay(rebuild=True)
        self._ensure_vpanel()
        self._paint_speed()
        self._paint_voice()
        self.msg("Загрузите демо в CS2, выберите раунд и нажмите ▶.")
        self._render(force=True)

    def _fill_play(self, d):
        self.timeline.configure(from_=self.t0, to=self.t1)
        for b in self.round_btns:
            b.destroy()
        self.round_btns = []
        for i, rd in enumerate(self.rounds):
            won = rd.get("won")
            b = ctk.CTkButton(self.rounds_fr, text=str(rd["n"]), width=30, height=26, corner_radius=8,
                              fg_color=CARD2, hover_color=LINE, border_width=1,
                              border_color=ACC if won else (LOSS if won is False else LINE),
                              text_color=TEXT, font=font(11, "bold"),
                              command=lambda r_=rd: self.seek(r_["f"] - 3 * TPS))
            b.grid(row=i // 15, column=i % 15, padx=2, pady=2)
            self.round_btns.append(b)
        self._cur_round = None
        wins = sum(1 for r in self.rounds if r.get("won"))
        losses = sum(1 for r in self.rounds if r.get("won") is False)
        acc = tr("точные нажатия" if d.get("precise") else "приблизительные нажатия")
        self.player_lbl.configure(text=d["player"])
        self.demo_lbl2.configure(text=f"{d.get('map') or ''}   ·   {wins}:{losses}   ·   {acc}")
        self.cam_btn.configure(text=tr(f"Камера на {d['player']}"))
        self._paint_speed()
        self._paint_voice()

    # ================= отрисовка =================
    def _mark_round(self, ri):
        if ri == getattr(self, "_cur_round", None):
            return
        for i, b in enumerate(self.round_btns):
            b.configure(fg_color=ACC if i == ri else CARD2)
        self._cur_round = ri

    def _update_play_btn(self):
        self.play_btn.configure(text="❚❚" if self.playing else "▶")

    def _paint_speed(self):
        v = self._speed()
        if hasattr(self, "speed_seg"):
            self.speed_seg.set(f"×{v:g}")

    def _paint_voice(self):
        if hasattr(self, "voice_seg"):
            self.voice_seg.set(tr(dict(VOICE_MODES).get(self.s.get("voice", "off"), "Выкл")))

    def _voice_seg(self, label):
        key = {tr(lbl): k for k, lbl in VOICE_MODES}[label]
        self.set_voice(key)

    def _show_cs2(self, ok, err, lines):
        if hasattr(self, "launch_bar"):
            if ok and self.launch_bar.winfo_manager():
                self.launch_bar.pack_forget()
            elif not ok and not self.launch_bar.winfo_manager():
                self.launch_bar.pack(fill="x", padx=14, pady=(6, 0), before=self._play_card)
            busy = getattr(self, "_launching", False)
            self.launch_btn.configure(state="disabled" if busy else "normal",
                                      text=tr("Запускаю…" if busy else "Запустить CS2 и демо"))
        self.dot_lbl.configure(text_color=ACC if ok else LOSS)
        self.cs_lbl.configure(text=tr("CS2 подключена" if ok else "CS2 не подключена"))
        if not ok and err:
            self.status_pill.configure(fg_color=CARD2)
        txt = "\n".join(lines)
        if txt != getattr(self, "_log_txt", None):
            self._log_txt = txt
            self.log.configure(state="normal")
            self.log.delete("1.0", "end")
            self.log.insert("end", txt)
            self.log.see("end")
            self.log.configure(state="disabled")

    def _pad_wheel(self, e, direction=None):
        super()._pad_wheel(e, direction)
