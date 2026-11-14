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

from . import errors, extract
from .main import (_extract_all_job, App, APP, TPS, VOICE_MODES, CACHE_DIR, DATA_DIR, _extract_job, save_settings,
                   HOTKEY_ACTIONS, DEFAULT_HOTKEYS, CS2_ACTIONS, DEFAULT_CS2_KEYS)
from .i18n import tr, set_lang
from . import i18n

# ---------- палитра: геймерский стиль ----------
BG = "#0d0f13"
CARD = "#12151c"
CARD2 = "#181c25"
LINE = "#252b38"
TEXT = "#e9edf3"
MUTED = "#8a93a6"
ACC = "#ff8a1f"            # оранжевый акцент
ACC_H = "#ffa040"
ACC_TXT = "#0d0f13"        # текст на оранжевом
YEL = "#ffc21f"
OK = "#22c55e"             # «CS2 подключена»
LOSS = "#ff4d4d"
T_COL = "#ff8a1f"
CT_COL = "#4a9eff"
SEG_SEL = "#e8741a"        # выбранный пункт переключателей (белый текст читается)
RIBBON = ["#ff8a1f", "#ffc21f", "#ff8a1f", "#ff5e1f", "#ffc21f", "#ff8a1f"]
# полоса раундов: (пройдено, впереди)
R_WIN = ("#ff8a1f", "#7a4a1e")
R_LOSS = ("#4a9eff", "#1f3a5c")
R_NONE = ("#5f6878", "#262b36")
RADIUS = 6                 # углы карточек
BRADIUS = 4                # углы кнопок

F_FALLBACK = "Segoe UI"
F_BODY = "Exo 2 CS2K"      # шрифты в папке fonts (лицензия OFL), подключаются только для программы
F_HEAD = "Oswald CS2K"
F = F_FALLBACK
BRAND = F_HEAD
_FAMS = None


def _fams():
    global _FAMS
    if _FAMS is None:
        try:
            _FAMS = set(tk.font.families())
        except Exception:
            return set()
    return _FAMS


def body_family():
    return F_BODY if F_BODY in _fams() else F_FALLBACK


def head_family():
    return F_HEAD if F_HEAD in _fams() else F_FALLBACK


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


def brand_font(size, weight="bold"):
    return ctk.CTkFont(family=head_family(), size=size, weight=weight)


def font(size=13, weight="normal"):
    return ctk.CTkFont(family=body_family(), size=size, weight=weight)


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


class RoundStrip(tk.Canvas):
    """Раунды и ползунок в одной полосе: ширина отрезка = длительность раунда, цвет — кто выиграл
    (оранжевый — команда игрока, синий — соперник). Клик по раунду — перемотка на его начало,
    перетаскивание — перемотка внутри раунда. Белая черта с меткой — текущее место."""

    BAR_Y, BAR_H = 24, 18
    GAP, HALF_GAP = 2, 10

    def __init__(self, master, app, bg=CARD):
        super().__init__(master, height=66, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        self.app = app
        self.rounds, self.t0, self.t1, self.t = [], 0, 1, 0
        self.segs = []                         # (x0, x1, раунд)
        self._press = None
        self._hover = None
        self._seek_job = None
        self.bind("<Configure>", lambda e: self._layout())
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda e: self._set_hover(None))

    # совместимость со старым ползунком (main.App вызывает .set(t) и .configure(from_, to))
    def configure(self, cnf=None, **kw):
        a, b = kw.pop("from_", None), kw.pop("to", None)
        if a is not None or b is not None:
            self.t0 = a if a is not None else self.t0
            self.t1 = b if b is not None else self.t1
        if kw or cnf:
            return super().configure(cnf, **kw)

    config = configure

    def set_rounds(self, rounds, t0, t1):
        self.rounds, self.t0, self.t1 = list(rounds or []), t0, t1
        self._layout()

    def set(self, t):
        if int(t) == int(self.t):
            return
        self.t = t
        self._draw()

    def _layout(self):
        w = max(50, self.winfo_width())
        pad = 6
        rs = self.rounds
        if not rs:
            self.segs = []
            return self._draw()
        gaps = []
        for i in range(1, len(rs)):
            gaps.append(self.HALF_GAP if rs[i].get("team") != rs[i - 1].get("team") else self.GAP)
        dur = [max(1, r["e"] - r["s"]) for r in rs]
        avail = w - 2 * pad - sum(gaps)
        total = sum(dur)
        x = pad
        self.segs = []
        for i, r in enumerate(rs):
            sw = max(3.0, avail * dur[i] / total)
            self.segs.append((x, x + sw, r))
            x += sw + (gaps[i] if i < len(gaps) else 0)
        self._draw()

    def _seg_at_x(self, x):
        best = None
        for i, (x0, x1, r) in enumerate(self.segs):
            if x0 - 2 <= x <= x1 + 2:
                return i
            if best is None or abs((x0 + x1) / 2 - x) < abs((self.segs[best][0] + self.segs[best][1]) / 2 - x):
                best = i
        return best

    def _x_of(self, t):
        for x0, x1, r in self.segs:
            if t < r["e"]:
                k = max(0.0, min(1.0, (t - r["s"]) / max(1, r["e"] - r["s"])))
                return x0 + (x1 - x0) * k
        return self.segs[-1][1] if self.segs else 0

    def _tick_of(self, x):
        i = self._seg_at_x(x)
        if i is None:
            return None, None
        x0, x1, r = self.segs[i]
        k = max(0.0, min(1.0, (x - x0) / max(1, x1 - x0)))
        return i, r["s"] + (r["e"] - r["s"]) * k

    def _draw(self):
        self.delete("all")
        if not self.segs:
            return
        y0, y1 = self.BAR_Y, self.BAR_Y + self.BAR_H
        t = self.t
        cur = None
        for i, (x0, x1, r) in enumerate(self.segs):
            won = r.get("won")
            cols = R_WIN if won else (R_LOSS if won is False else R_NONE)
            if t >= r["e"]:
                self.create_rectangle(x0, y0, x1, y1, fill=cols[0], outline="")
            elif t < r["s"]:
                self.create_rectangle(x0, y0, x1, y1, fill=cols[1], outline="")
            else:
                cur = i
                xm = x0 + (x1 - x0) * (t - r["s"]) / max(1, r["e"] - r["s"])
                self.create_rectangle(x0, y0, x1, y1, fill=cols[1], outline="")
                self.create_rectangle(x0, y0, xm, y1, fill=cols[0], outline="")
            if i == self._hover:
                self.create_rectangle(x0, y0 - 3, x1, y0 - 1, fill=TEXT, outline="")
        # под полосой: «1 … 6 : 6 · СМЕНА СТОРОН · 2 : 7 … 21»
        fnt = (body_family(), 9, "bold")
        blocks, start = [], 0
        for i in range(1, len(self.segs) + 1):
            if i == len(self.segs) or self.segs[i][2].get("team") != self.segs[i - 1][2].get("team"):
                blocks.append((start, i))
                start = i
        parts = []
        for a, b in blocks:
            rs = [s[2] for s in self.segs[a:b]]
            parts.append(f"{sum(1 for r in rs if r.get('won'))} : {sum(1 for r in rs if r.get('won') is False)}")
        mid = f"   ·   {tr('СМЕНА СТОРОН')}   ·   ".join(parts)
        self.create_text(self.winfo_width() / 2, y1 + 12, text=mid, fill=MUTED, font=fnt)
        self.create_text(self.segs[0][0], y1 + 12, text=str(self.segs[0][2]["n"]), fill=MUTED, font=fnt, anchor="w")
        self.create_text(self.segs[-1][1], y1 + 12, text=str(self.segs[-1][2]["n"]), fill=MUTED, font=fnt, anchor="e")
        # текущее место: белая черта и метка «R4 · 1:00»
        if cur is None:
            cur = len(self.segs) - 1 if t >= self.segs[-1][2]["e"] else 0
        x = self._x_of(t)
        r = self.segs[cur][2]
        sec = max(0.0, (t - r.get("f", r["s"])) / 64)
        lbl = f"R{r['n']} · {int(sec // 60)}:{int(sec % 60):02d}"
        if self._hover is not None and self._hover != cur:
            hr = self.segs[self._hover][2]
            lbl = f"{tr('Раунд')} {hr['n']}"
            x = (self.segs[self._hover][0] + self.segs[self._hover][1]) / 2
        lf = (head_family(), 10, "bold")
        tw = tk.font.Font(family=lf[0], size=lf[1], weight="bold").measure(lbl) + 12
        lx = max(tw / 2, min(self.winfo_width() - tw / 2, x))
        self.create_rectangle(lx - tw / 2, 2, lx + tw / 2, 19, fill=TEXT, outline="")
        self.create_text(lx, 11, text=lbl, fill=ACC_TXT, font=lf)
        px = self._x_of(t)
        self.create_rectangle(px - 1, y0 - 5, px + 2, y1 + 5, fill="#ffffff", outline="")

    # ---------- мышь ----------
    def _set_hover(self, i):
        if i != self._hover:
            self._hover = i
            self._draw()

    def _on_motion(self, e):
        if self._press is None and self.BAR_Y - 6 <= e.y <= self.BAR_Y + self.BAR_H + 6:
            self._set_hover(self._seg_at_x(e.x))
        elif self._press is None:
            self._set_hover(None)

    def _on_press(self, e):
        self._press = (e.x, False)

    def _on_drag(self, e):
        if self._press is None:
            return
        x0, moved = self._press
        if not moved and abs(e.x - x0) < 4:
            return
        self._press = (x0, True)
        self._hover = None
        i, t = self._tick_of(e.x)
        if t is None:
            return
        self.t = t
        self._draw()
        if self._seek_job is None:                       # перематываем не чаще раза в 60 мс
            def go():
                self._seek_job = None
                self.app.seek(self.t)
            self._seek_job = self.after(60, go)

    def _on_release(self, e):
        if self._press is None:
            return
        x0, moved = self._press
        self._press = None
        if self._seek_job is not None:
            self.after_cancel(self._seek_job)
            self._seek_job = None
        if moved:
            i, t = self._tick_of(e.x)
            if t is not None:
                self.app.seek(t)
            return
        i = self._seg_at_x(e.x)
        if i is not None:
            self.app.seek(self.app._round_start(self.segs[i][2]))


class PlayButton(tk.Canvas):
    """Оранжевая кнопка ▶ / ❚❚ со скошенными краями."""

    def __init__(self, master, command, w=74, h=42):
        super().__init__(master, width=w, height=h, bg=CARD, highlightthickness=0, bd=0, cursor="hand2")
        self.command, self.w, self.h = command, w, h
        self.playing = False
        self.hover = False
        self.bind("<Button-1>", lambda e: self.command())
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self._draw()

    def _set_hover(self, on):
        self.hover = on
        self._draw()

    def configure(self, cnf=None, **kw):
        t = kw.pop("text", None)
        if t is not None:
            self.playing = t != "▶"
            self._draw()
        if kw or cnf:
            return super().configure(cnf, **kw)

    config = configure

    def _draw(self):
        self.delete("all")
        w, h, k = self.w, self.h, 9
        self.create_polygon(k, 0, w, 0, w - k, h, 0, h, fill=ACC_H if self.hover else ACC, outline="")
        cx, cy = w / 2, h / 2
        if self.playing:
            for dx in (-6, 3):
                self.create_rectangle(cx + dx, cy - 8, cx + dx + 4, cy + 8, fill=ACC_TXT, outline="")
        else:
            self.create_polygon(cx - 6, cy - 9, cx - 6, cy + 9, cx + 9, cy, fill=ACC_TXT, outline="")


def sync_icon(size, color):
    """Значок «две стрелки по кругу» (сглаженный, рисуется через Pillow)."""
    try:
        from PIL import Image, ImageDraw, ImageTk
        S = 6
        n = size * S
        im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        col = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5)) + (255,)
        lw = int(n * 0.12)
        m = int(n * 0.2)
        box = (m, m, n - m, n - m)
        r = (n - 2 * m) / 2
        c = n / 2
        d.arc(box, 192, 335, fill=col, width=lw)            # верхняя дуга (углы по часовой от «3 часов»)
        d.arc(box, 12, 155, fill=col, width=lw)             # нижняя дуга
        a = n * 0.17
        # стрелка слева вниз и справа вверх
        lx, rx = c - r, c + r
        d.polygon([(lx - a, c - a * 0.35), (lx + a, c - a * 0.35), (lx, c + a * 0.9)], fill=col)
        d.polygon([(rx - a, c + a * 0.35), (rx + a, c + a * 0.35), (rx, c - a * 0.9)], fill=col)
        im = im.resize((size, size), Image.LANCZOS)
        return ImageTk.PhotoImage(im)
    except Exception:
        return None


class SyncButton(tk.Canvas):
    """Пересинхронизация: значок из двух стрелок по кругу + клавиша (F8)."""

    def __init__(self, master, command, key="", w=None, h=42):
        self.key = key or ""
        w = w or (44 if not self.key else 58 + 9 * len(self.key))
        super().__init__(master, width=w, height=h, bg=CARD, highlightthickness=0, bd=0, cursor="hand2")
        self.command, self.w, self.h = command, w, h
        self.hover = False
        self._icon = None
        self.bind("<Button-1>", lambda e: self.command())
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self._draw()

    def _set_hover(self, on):
        self.hover = on
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = self.w, self.h
        self.create_rectangle(0, 0, w - 1, h - 1, fill=LINE if self.hover else CARD2, outline=LINE)
        cx, cy, r = 22, h / 2, 9
        self._icon = self._icon or sync_icon(26, YEL)
        if self._icon is not None:
            self.create_image(cx, cy, image=self._icon)
        else:
            self.create_text(cx, cy, text="⟳", fill=YEL, font=(body_family(), 15, "bold"))
        if self.key:
            self.create_text(cx + r + 9, cy, text=self.key, anchor="w", fill=YEL, font=(body_family(), 12, "bold"))


class SpeedRow(ctk.CTkFrame):
    """Скорость: квадратные кнопки ¼ ½ 1× 2× 4×, выбранная — с жёлтой рамкой."""
    VALUES = [(0.25, "¼"), (0.5, "½"), (1.0, "1×"), (2.0, "2×"), (4.0, "4×")]

    def __init__(self, master, command):
        super().__init__(master, fg_color="transparent")
        self.btns = {}
        for v, lbl in self.VALUES:
            b = ctk.CTkButton(self, text=lbl, width=34, height=34, corner_radius=2, border_width=1,
                              font=font(12, "bold"), command=lambda v=v: command(v))
            b.pack(side="left", padx=2)
            self.btns[v] = b
        self.set("×1")

    def set(self, value):
        try:
            cur = float(str(value).replace("×", ""))
        except ValueError:
            cur = 1.0
        for v, b in self.btns.items():
            on = abs(v - cur) < 1e-6
            b.configure(fg_color="#2a2210" if on else CARD2, hover_color=mix(CARD2, YEL, 0.2),
                        border_color=YEL if on else LINE, text_color=YEL if on else MUTED)


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
        self.vtr_var = tk.BooleanVar(value=bool(self.s.get("vpanel_transparent", self.s.get("overlay_transparent", True))))
        self.valpha_var = tk.DoubleVar(value=float(self.s.get("vpanel_alpha", self.s["alpha"])))
        self.vmove_var = tk.BooleanVar(value=False)

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
        seg = ctk.CTkSegmentedButton(master, values=["RU", "EN"], command=self.set_lang_ui, width=80, height=28,
                                     corner_radius=BRADIUS,
                                     selected_color=SEG_SEL, selected_hover_color=ACC, unselected_color=CARD2,
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

    def _copy_info_report(self):
        """Отчёт без ошибки: что делала программа (камера, переключения, синхронизация) — для поиска багов."""
        rep, _ = self.make_report("E000")
        self.root.clipboard_clear()
        self.root.clipboard_append(rep)
        self.msg("Отчёт скопирован — вставьте его в комментарии Telegram-канала (Ctrl+V).")

    def show_error(self, code, detail=""):
        """Окно ошибки: код, что случилось, что делать и кнопка «Скопировать отчёт» для автора."""
        import threading
        self.msg(f"Ошибка {code}: {errors.title(code)}")
        old = getattr(self, "_err_dlg", None)
        if old is not None:
            try:
                old.destroy()
            except Exception:
                pass
        dlg = ctk.CTkToplevel(self.root)
        self._err_dlg = dlg
        dlg.title(f"{APP} — {code}")
        dlg.configure(fg_color=CARD)
        dlg.resizable(False, False)
        dlg.transient(self.root)
        head = ctk.CTkFrame(dlg, fg_color="transparent")
        head.pack(fill="x", padx=22, pady=(18, 4))
        ctk.CTkLabel(head, text=f" {code} ", font=font(13, "bold"), text_color="#ffffff", fg_color=LOSS,
                     corner_radius=6).pack(side="left")
        self.label(head, errors.title(code), 16, "bold", TEXT, anchor="w").pack(side="left", padx=10)
        if detail:
            self.label(dlg, detail, 11, anchor="w", justify="left", wraplength=460).pack(anchor="w", padx=22)
        self.label(dlg, "Что делать:", 12, "bold", TEXT, anchor="w").pack(anchor="w", padx=22, pady=(10, 2))
        for i, h in enumerate(errors.hints(code), 1):
            self.label(dlg, f"{i}. {tr(h)}", 12, anchor="w", justify="left", wraplength=460, color=TEXT
                       ).pack(anchor="w", padx=22, pady=1)
        cause = self.label(dlg, "", 12, "bold", anchor="w", justify="left", wraplength=460, color=T_COL)
        note = self.label(dlg, "Не помогло? Нажмите «Сообщить о баге»: отчёт скопируется, а в Telegram-канале "
                               "останется вставить его в комментарии (Ctrl+V). В отчёте нет личных данных.",
                          11, anchor="w", justify="left", wraplength=460)
        note.pack(anchor="w", padx=22, pady=(10, 0))
        row = ctk.CTkFrame(dlg, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=16)
        state = {"report": None}

        def build():
            try:
                rep, hint = self.make_report(code, detail)
            except Exception as e:
                rep, hint = f"{code}: {errors.title(code)}\n{detail}\n(отчёт не собрался: {e})", None
            state["report"] = rep

            def put():
                try:
                    if hint and dlg.winfo_exists():
                        cause.configure(text=tr("Возможная причина: ") + hint)
                        cause.pack(anchor="w", padx=22, pady=(8, 0), before=note)
                except Exception:
                    pass
            self.ui(put)
        threading.Thread(target=build, daemon=True).start()

        def copy():
            rep = state["report"]
            if rep is None:
                rep = self.make_report(code, detail)[0]
            self.root.clipboard_clear()
            self.root.clipboard_append(rep)
            copy_btn.configure(text=tr("✓ Скопировано"))
            dlg.after(2500, lambda: copy_btn.winfo_exists() and copy_btn.configure(text=tr("Скопировать отчёт")))

        def close():
            try:
                dlg.grab_release()
            except Exception:
                pass
            dlg.destroy()
        copy_btn = self.btn(row, "Скопировать отчёт", copy, primary=True)
        copy_btn.pack(side="left", padx=4)
        from .version import BUGS_URL
        if BUGS_URL:
            def report_bug():
                copy()                                      # отчёт сразу в буфере — останется вставить
                import webbrowser
                webbrowser.open(BUGS_URL)
            self.btn(row, "Сообщить о баге", report_bug).pack(side="left", padx=4)
        self.btn(row, "Закрыть", close, width=90).pack(side="right", padx=4)
        dlg.protocol("WM_DELETE_WINDOW", close)
        dlg.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - dlg.winfo_width()) // 2
        dlg.geometry(f"+{max(0, x)}+{max(0, self.root.winfo_rooty() + 100)}")
        dlg.after(50, lambda: (dlg.lift(), dlg.focus_force()))

    def _fill_target_box(self):
        """Настройки выбранного окна: клавиатуры или панели голоса — у каждого свои."""
        box = self._tgt_box
        for w in box.winfo_children():
            w.destroy()
        voice = self.target_var.get() == "voice"
        if not voice:
            vr3 = ctk.CTkFrame(box, fg_color="transparent")
            vr3.pack(fill="x", pady=(0, 8))
            self.label(vr3, "Вид", 12).pack(side="left", padx=(0, 8))
            styles = {"glass": tr("Стекло (компактная)"), "classic": tr("Классическая")}
            kseg = ctk.CTkSegmentedButton(vr3, values=list(styles.values()),
                                          command=lambda v: self.set_kb_style({b: a for a, b in styles.items()}[v]),
                                          selected_color=SEG_SEL, selected_hover_color=ACC, unselected_color=CARD2,
                                          unselected_hover_color=LINE, fg_color=CARD2, text_color=TEXT,
                                          corner_radius=BRADIUS, font=font(12, "bold"))
            kseg.set(styles.get(self.s.get("kb_style", "glass"), styles["glass"]))
            kseg.pack(side="left")
        g = ctk.CTkFrame(box, fg_color="transparent")
        g.pack(fill="x")
        if voice:
            show, trv, mv_, find = (self.vp_var, self._vpanel_toggle), (self.vtr_var, self._vpanel_transparent), \
                (self.vmove_var, self._vpanel_move), self._vpanel_find
        else:
            show, trv, mv_, find = (self.ov_var, self._overlay_toggle), (self.tr_var, self._overlay_transparent), \
                (self.move_var, self._overlay_move), self._overlay_find
        self.switch(g, "Показывать", *show).grid(row=0, column=0, sticky="w", pady=3)
        self.switch(g, "Прозрачный фон", *trv).grid(row=0, column=1, sticky="w", padx=16)
        self.switch(g, "Режим перемещения", *mv_).grid(row=1, column=0, sticky="w", pady=3)
        self.btn(g, "Найти на экране", find, height=30).grid(row=1, column=1, sticky="w", padx=16)
        if not voice:
            def _speed_toggle():
                self.s["show_speed"] = bool(self.speed_show_var.get())
                save_settings(self.s)
                self._render(force=True)
            self.switch(g, "Скорость игрока под клавиатурой", self.speed_show_var, _speed_toggle
                        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=3)
        sl = ctk.CTkFrame(box, fg_color="transparent")
        sl.pack(fill="x", pady=(8, 4))
        if voice:
            size = (0.4, 2.5, self.vscale_var, self._vpanel_size)
            alpha = (self.valpha_var, self._vpanel_alpha)
        else:
            size = (0.5, 1.8, self.scale_var, self._overlay_scale)
            alpha = (self.alpha_var, self._overlay_alpha)
        self.label(sl, "Размер", 12).grid(row=0, column=0, sticky="w")
        ctk.CTkSlider(sl, from_=size[0], to=size[1], variable=size[2], command=lambda v, f=size[3]: f(),
                      button_color=TEXT, progress_color=ACC, fg_color=LINE, width=200).grid(row=0, column=1, padx=8)
        self.label(sl, "Прозрачность", 12).grid(row=1, column=0, sticky="w")
        ctk.CTkSlider(sl, from_=0.3, to=1.0, variable=alpha[0], command=lambda v, f=alpha[1]: f(),
                      button_color=TEXT, progress_color=ACC, fg_color=LINE, width=200).grid(row=1, column=1, padx=8)
        mv = ctk.CTkFrame(box, fg_color="transparent")
        mv.pack(fill="x", pady=(8, 2))
        pad = tk.Canvas(mv, width=200, height=64, bg=CARD2, highlightthickness=0, cursor="fleur")
        pad.pack(side="left")
        pad.create_text(100, 24, text="✥  " + tr("Зажмите и тащите"), fill=TEXT, font=(body_family(), 10, "bold"))
        pad.create_text(100, 44, text=tr("колесо мыши — размер"), fill=MUTED, font=(body_family(), 9))
        pad.bind("<ButtonPress-1>", self._pad_start)
        pad.bind("<B1-Motion>", self._pad_move)
        pad.bind("<ButtonRelease-1>", self._pad_end)
        pad.bind("<MouseWheel>", self._pad_wheel)
        nud = ctk.CTkFrame(mv, fg_color="transparent")
        nud.pack(side="left", padx=12)
        for (dx, dy, t, r_, c_) in ((0, -20, "▲", 0, 1), (-20, 0, "◀", 1, 0), (20, 0, "▶", 1, 2), (0, 20, "▼", 2, 1)):
            ctk.CTkButton(nud, text=t, width=28, height=22, corner_radius=2, fg_color=CARD2, hover_color=LINE,
                          text_color=TEXT, font=font(10), command=lambda a=dx, b=dy: self._overlay_nudge(a, b)
                          ).grid(row=r_, column=c_, padx=1, pady=1)
        hint = "снизу по центру" if not voice else "слева посередине"
        dcol = ctk.CTkFrame(mv, fg_color="transparent")
        dcol.pack(side="left", padx=(4, 0))
        self.btn(dcol, "По умолчанию", lambda: self.default_place("voice" if voice else "kb"), height=30
                 ).pack(anchor="w")
        self.label(dcol, hint, 11).pack(anchor="w", pady=(2, 0))

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
        return ctk.CTkButton(master, text=tr("Версия {v}").format(v=VERSION), height=22, width=10, corner_radius=BRADIUS,
                             fg_color="transparent", hover_color=CARD2, text_color=MUTED, font=font(11),
                             command=lambda: webbrowser.open(RELEASES_URL))

    def donate_button(self, master):
        """Кнопка «Поддержать автора» — открывает страницу для донатов. Без ссылки не показывается."""
        from .version import DONATE_URL
        if not DONATE_URL:
            return None
        import webbrowser
        return ctk.CTkButton(master, text="♥  " + tr("Поддержать автора"), height=26, width=10, corner_radius=BRADIUS,
                             fg_color="transparent", hover_color=CARD2, border_width=1, border_color=ACC,
                             text_color=ACC, font=font(12, "bold"), command=lambda: webbrowser.open(DONATE_URL))

    def bug_button(self, master, compact=False):
        """Кнопка «Сообщить о баге» — открывает Telegram-канал (там открыты комментарии)."""
        from .version import BUGS_URL
        if not BUGS_URL:
            return None
        import webbrowser
        text = "⚠" if compact else "⚠  " + tr("Сообщить о баге")      # в верхней панели — только значок, места мало
        return ctk.CTkButton(master, text=text, height=26 if not compact else 38, width=38 if compact else 10,
                             corner_radius=BRADIUS, fg_color="transparent" if not compact else CARD2,
                             hover_color=CARD2 if not compact else LINE, border_width=0 if compact else 1,
                             border_color=LINE, text_color=MUTED if not compact else TEXT, font=font(12, "bold"),
                             command=lambda: webbrowser.open(BUGS_URL))

    def gear(self, master):
        return ctk.CTkButton(master, text="⚙", width=32, height=28, corner_radius=BRADIUS, fg_color=CARD2,
                             hover_color=LINE, border_width=1, border_color=LINE, text_color=TEXT, font=font(15),
                             command=self.open_hotkeys)

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
        kw.setdefault("corner_radius", RADIUS)
        return ctk.CTkFrame(master, fg_color=CARD, border_width=1, border_color=LINE, **kw)

    def btn(self, master, text, command, primary=False, **kw):
        kw.setdefault("height", 36)
        kw.setdefault("corner_radius", BRADIUS)
        kw.setdefault("font", font(13, "bold"))
        if not primary:
            kw.setdefault("border_width", 1)
            kw.setdefault("border_color", LINE)
        return ctk.CTkButton(master, text=tr(text), command=command,
                             fg_color=ACC if primary else CARD2, hover_color=ACC_H if primary else LINE,
                             text_color=ACC_TXT if primary else TEXT, **kw)

    def switch(self, master, text, var, command):
        return ctk.CTkSwitch(master, text=tr(text), variable=var, command=command, onvalue=True, offvalue=False,
                             progress_color=ACC, button_color=TEXT, button_hover_color="#ffffff",
                             fg_color=LINE, text_color=TEXT, font=font(12), corner_radius=BRADIUS)

    def head(self, master, text, size=13, color=TEXT, **kw):
        """Заголовок заглавными буквами (Oswald)."""
        return ctk.CTkLabel(master, text=tr(text).upper(), font=brand_font(size), text_color=color, **kw)

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
            ctk.CTkLabel(mark, text="", image=img).pack(side="left", padx=(0, 12))
        ctk.CTkLabel(mark, text="CS2", font=brand_font(30), text_color=ACC).pack(side="left")
        ctk.CTkLabel(mark, text=" DEMO TO KEYBOARD", font=brand_font(30), text_color=TEXT).pack(side="left")
        self.label(head, "Нажатия игрока из демо — поверх игры и синхронно с ней", 12, "bold").pack(anchor="w")
        brow = ctk.CTkFrame(head, fg_color="transparent")
        brow.pack(anchor="w", pady=(8, 0))
        self.version_button(brow).pack(side="left")
        don = self.donate_button(brow)
        if don is not None:
            don.pack(side="left", padx=(8, 0))
        bug = self.bug_button(brow)
        if bug is not None:
            bug.pack(side="left", padx=(8, 0))

        c = self.card(root)
        c.pack(fill="x", padx=20, pady=6)
        row = ctk.CTkFrame(c, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkButton(row, text=tr("Открыть демо").upper(), command=self.open_demo, width=200, height=48,
                      corner_radius=BRADIUS, fg_color=ACC, hover_color=ACC_H, text_color=ACC_TXT,
                      font=brand_font(17)).pack(side="left")
        self.btn(row, "Файл клавиатуры…", self.open_keys, height=48).pack(side="left", padx=8)
        self.drop_hint = self.label(c, "", 11, "bold", anchor="w")
        self.drop_hint.pack(anchor="w", padx=18, pady=(0, 10))
        self.recent_title = self.head(c, "Недавние", 12, MUTED)
        self.recent_box = ctk.CTkFrame(c, fg_color="transparent")
        self._fill_recent()

        # карточка выбора игрока — появляется после чтения демо
        self.pick_card = self.card(root)
        top = ctk.CTkFrame(self.pick_card, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(14, 4))
        self.pick_title = ctk.CTkLabel(top, text="", font=brand_font(20), text_color=TEXT, anchor="w")
        self.pick_title.pack(anchor="w")
        self.pick_sub = self.label(top, "", 12, anchor="w", justify="left")
        self.pick_sub.pack(anchor="w")
        self.teams_box = ctk.CTkFrame(self.pick_card, fg_color="transparent")
        self.teams_box.pack(fill="x", padx=12, pady=(6, 8))
        self.ribbon = Ribbon(self.pick_card, height=6)
        self.busy_lbl = self.label(self.pick_card, "", 12, "bold", anchor="w")

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
        self.recent_title.pack(anchor="w", padx=18, pady=(4, 2))
        self.recent_box.pack(fill="x", padx=12, pady=(0, 12))
        for it in items:
            rowf = ctk.CTkFrame(self.recent_box, fg_color=CARD2, corner_radius=BRADIUS, cursor="hand2")
            rowf.pack(fill="x", pady=3)
            rowf.grid_columnconfigure(1, weight=1)
            bar = ctk.CTkFrame(rowf, width=3, height=10, fg_color=CARD2, corner_radius=0)
            bar.grid(row=0, column=0, sticky="ns", padx=(0, 0))
            txt = ctk.CTkFrame(rowf, fg_color="transparent")
            txt.grid(row=0, column=1, sticky="ew")
            name = os.path.basename(it["path"])
            name = name if len(name) < 48 else name[:45] + "…"
            a = self.label(txt, name, 13, "bold", TEXT, anchor="w")
            a.pack(fill="x", padx=12, pady=(6, 0))
            b = self.label(txt, f"{(it.get('map') or '?').upper()}   ·   раундов {it.get('rounds', '?')}   ·   "
                                f"{time.strftime('%d.%m %H:%M', time.localtime(it.get('ts', 0)))}", 11, "bold", anchor="w")
            b.pack(fill="x", padx=12, pady=(0, 6))
            trash = ctk.CTkButton(rowf, text="🗑", width=34, height=34, corner_radius=BRADIUS, fg_color="transparent",
                                  hover_color=mix(CARD2, LOSS, 0.45), text_color=MUTED, font=font(15),
                                  command=lambda p=it["path"]: self.confirm_delete(p))
            trash.grid(row=0, column=2, padx=(4, 8))
            go = lambda e, p=it["path"]: self.open_demo_path(p)
            on = lambda e, f=rowf, br=bar: (f.configure(fg_color=LINE), br.configure(fg_color=ACC))
            off = lambda e, f=rowf, br=bar: (f.configure(fg_color=CARD2), br.configure(fg_color=CARD2))
            for w in (rowf, txt, a, b, bar):
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
        ctk.CTkButton(top, text="‹", width=40, height=40, corner_radius=BRADIUS, fg_color=CARD2, hover_color=LINE,
                      border_width=1, border_color=LINE, text_color=ACC, font=font(22, "bold"),
                      command=self.show_start).pack(side="left")
        tt = ctk.CTkFrame(top, fg_color="transparent")
        tt.pack(side="left", padx=12)
        self.player_lbl = ctk.CTkLabel(tt, text="", font=brand_font(24), text_color=TEXT, anchor="w", height=28)
        self.player_lbl.pack(anchor="w")
        self.demo_lbl2 = self.label(tt, "", 12, "bold", anchor="w")
        self.demo_lbl2.pack(anchor="w")
        self.gear(top).pack(side="right", padx=(6, 0))
        self.lang_switch(top).pack(side="right", padx=(8, 0))
        # режим «все игроки»: ряд ников под заголовком (появляется только в этом режиме)
        self.allp_fr = ctk.CTkFrame(root, fg_color="transparent")
        self._allp_after = top

        self.status_pill = ctk.CTkFrame(top, fg_color=CARD2, corner_radius=BRADIUS)
        self.status_pill.pack(side="right")
        self.status_bar = ctk.CTkFrame(self.status_pill, width=3, height=22, fg_color=LOSS, corner_radius=1)
        self.status_bar.pack(side="left", padx=(0, 6), pady=4)
        self.dot_lbl = self.label(self.status_pill, "●", 11, color=LOSS)
        self.dot_lbl.pack(side="left", padx=(2, 4), pady=4)
        self.cs_lbl = self.label(self.status_pill, "CS2 не подключена", 12, "bold", color=TEXT)
        self.cs_lbl.pack(side="left", padx=(0, 12))

        # --- воспроизведение ---
        # большая кнопка «Запустить CS2 и демо» (исчезает, когда связь есть)
        self.launch_bar = ctk.CTkFrame(root, fg_color="transparent")
        self.launch_btn = ctk.CTkButton(self.launch_bar, text="▶  " + tr("Запустить CS2 и демо").upper(),
                                        command=self.launch_and_load, height=50, corner_radius=BRADIUS,
                                        fg_color=ACC, hover_color=ACC_H, text_color=ACC_TXT, font=brand_font(17))
        self.launch_btn.pack(fill="x")
        self.label(self.launch_bar, "Программа сама запустит игру с параметрами для демо", 11).pack(anchor="w", padx=2,
                                                                                                    pady=(3, 0))
        self.launch_bar.pack(fill="x", padx=14, pady=(6, 0))

        pc = self.card(root)
        pc.pack(fill="x", padx=14, pady=8)
        self._play_card = pc
        sc = ctk.CTkFrame(pc, fg_color="transparent")
        sc.pack(fill="x", padx=16, pady=(12, 0))
        sc.grid_columnconfigure(1, weight=1)
        self.score_us = ctk.CTkLabel(sc, text="0", font=brand_font(30), text_color=ACC, width=56)
        self.score_us.grid(row=0, column=0, rowspan=2, sticky="w")
        self.round_lbl = ctk.CTkLabel(sc, text="", font=font(13, "bold"), text_color=MUTED, height=18)
        self.round_lbl.grid(row=0, column=1)
        self.clock = ctk.CTkLabel(sc, text="0:00.00", font=brand_font(42), text_color="#ffffff", height=46)
        self.clock.grid(row=1, column=1)
        self.score_them = ctk.CTkLabel(sc, text="0", font=brand_font(30), text_color=CT_COL, width=56)
        self.score_them.grid(row=0, column=2, rowspan=2, sticky="e")
        self.clock_sub = ctk.CTkLabel(pc, text="")                     # main.App пишет сюда «Раунд N тик T»
        self.rounds_fr = ctk.CTkFrame(pc, fg_color="transparent")       # совместимость
        self.timeline = RoundStrip(pc, self, bg=CARD)
        self.timeline.pack(fill="x", padx=10, pady=(6, 2))

        ctl = ctk.CTkFrame(pc, fg_color="transparent")
        ctl.pack(fill="x", padx=14, pady=(6, 4))
        tb = dict(width=42, height=42, corner_radius=2, fg_color=CARD2, hover_color=LINE, border_width=1,
                  border_color=LINE, text_color=TEXT, font=font(14, "bold"))
        ctk.CTkButton(ctl, text="⏮", command=self.prev_round, **tb).pack(side="left", padx=(0, 4))
        self.play_btn = PlayButton(ctl, self.toggle)
        self.play_btn.pack(side="left", padx=2)
        ctk.CTkButton(ctl, text="⏭", command=self.next_round, **tb).pack(side="left", padx=4)
        rs = (self.hotkey_table().get("resync") or [0, 0, ""])[2]
        self.resync_btn = SyncButton(ctl, self.play_synced, key=rs if rs and rs != "—" else "")
        self.resync_btn.pack(side="left", padx=4)
        self.speed_seg = SpeedRow(ctl, lambda v: self.set_speed(v))
        self.speed_seg.pack(side="right")
        self.tick_lbl = self.label(pc, "", 11, "bold", anchor="w")
        self.tick_lbl.pack(fill="x", padx=16, pady=(4, 0))
        self.msg_lbl = self.label(pc, "", 11, anchor="w", wraplength=560, justify="left")
        self.msg_lbl.pack(fill="x", padx=16, pady=(0, 10))

        # разделы настроек: плитки 2×2, открытый раздел — под ними
        self._sec_grid = ctk.CTkFrame(root, fg_color="transparent")
        self._sec_grid.pack(fill="x", padx=11, pady=(0, 0))
        self._sec_grid.grid_columnconfigure((0, 1), weight=1, uniform="sec")
        self._sec_holder = self.card(root)
        self._sections = []

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
        self.hints_lbl = self.label(s1, "", 11, anchor="w", justify="left", wraplength=540)
        self.hints_lbl.pack(anchor="w", pady=(2, 0))
        self._update_hints()

        s2 = self.section(root, "Голос и чат")
        self.voice_seg = ctk.CTkSegmentedButton(s2, values=[tr(lbl) for _, lbl in VOICE_MODES],
                                                command=self._voice_seg,
                                                selected_color=SEG_SEL, selected_hover_color=ACC,
                                                unselected_color=CARD2, unselected_hover_color=LINE,
                                                fg_color=CARD2, text_color=TEXT, font=font(12, "bold"))
        self.voice_seg.pack(anchor="w", pady=(0, 6))
        vr = ctk.CTkFrame(s2, fg_color="transparent")
        vr.pack(fill="x")
        self.switch(vr, "Чат игроков", self.chat_var, self._chat_changed).pack(side="left")
        self.switch(vr, "Панель «кто говорит»", self.vp_var, self._vpanel_toggle).pack(side="left", padx=16)
        self.unmute_var = tk.BooleanVar(value=bool(self.s.get("unmute_demo", True)))
        self.switch(s2, "Слышать замученных игроков в демо (мут вернётся после закрытия CS2)", self.unmute_var,
                    lambda: (self.s.__setitem__("unmute_demo", bool(self.unmute_var.get())), save_settings(self.s))
                    ).pack(anchor="w", pady=(8, 0))

        s3 = self.section(root, "Клавиатура в игре")
        top3 = ctk.CTkFrame(s3, fg_color="transparent")
        top3.pack(fill="x", pady=(0, 10))
        self.label(top3, "Настроить", 12).pack(side="left", padx=(0, 8))
        names = {"kb": tr("Клавиатуру"), "voice": tr("Панель голоса")}
        tseg = ctk.CTkSegmentedButton(top3, values=list(names.values()),
                                      command=lambda v: (self.target_var.set({b: a for a, b in names.items()}[v]),
                                                         self._target_changed(), self._fill_target_box()),
                                      selected_color=SEG_SEL, selected_hover_color=ACC, unselected_color=CARD2,
                                      unselected_hover_color=LINE, fg_color=CARD2, text_color=TEXT,
                                      corner_radius=BRADIUS, font=font(12, "bold"))
        tseg.set(names.get(self.target_var.get(), names["kb"]))
        tseg.pack(side="left")
        self._tgt_box = ctk.CTkFrame(s3, fg_color="transparent")
        self._tgt_box.pack(fill="x")
        self.vscale_var = tk.DoubleVar(value=float(self.s.get("vpanel_scale", 1.0)))
        self.speed_show_var = tk.BooleanVar(value=bool(self.s.get("show_speed", True)))
        self._fill_target_box()

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
        pr = ctk.CTkFrame(s4, fg_color="transparent")
        pr.pack(fill="x", pady=(8, 2))
        self.label(pr, "Сверка с CS2, раз в", 12, color=TEXT).pack(side="left", padx=(0, 8))
        en = i18n.LANG == "en"
        probe_vals = {(f"{v:g} s" if en else f"{v:g} с".replace(".", ",")): v for v in (0.5, 1.0, 1.5, 3.0)}
        cur = min(probe_vals, key=lambda k: abs(probe_vals[k] - float(self.s.get("probe", 1.0) or 1.0)))

        def set_probe(v):
            self.s["probe"] = probe_vals.get(v, 1.0)
            save_settings(self.s)
        seg = ctk.CTkSegmentedButton(pr, values=list(probe_vals), command=set_probe,
                                     selected_color=SEG_SEL, selected_hover_color=ACC,
                                     unselected_color=CARD2, unselected_hover_color=LINE,
                                     fg_color=CARD2, text_color=TEXT, font=font(12, "bold"))
        seg.set(cur)
        seg.pack(side="left")
        self.label(s4, "Чаще — клавиатура точнее держится за игрой, но CS2 каждый раз встаёт на паузу на долю "
                       "кадра: на слабом ПК возможны микрорывки и щелчки в голосе.", 11, anchor="w",
                   justify="left", wraplength=520).pack(anchor="w", pady=(0, 4))
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
        """Плитка раздела в сетке 2×2. Открыт только один раздел — его содержимое под сеткой."""
        title = tr(title)
        i = len(self._sections)
        head = ctk.CTkFrame(self._sec_grid, fg_color=CARD, corner_radius=2, border_width=1, border_color=LINE,
                            height=44, cursor="hand2")
        head.grid(row=i // 2, column=i % 2, sticky="ew", padx=3, pady=3)
        head.grid_propagate(False)
        head.pack_propagate(False)
        name = ctk.CTkLabel(head, text=title.upper(), font=font(13, "bold"), text_color=TEXT, anchor="w")
        name.pack(side="left", padx=(14, 4))
        sign = ctk.CTkLabel(head, text="+", font=font(15, "bold"), text_color=ACC, width=20)
        sign.pack(side="right", padx=10)
        body = ctk.CTkFrame(self._sec_holder, fg_color="transparent")
        sec = {"head": head, "sign": sign, "body": body}
        self._sections.append(sec)

        def flip(e=None):
            opened_now = body.winfo_manager() != ""
            for o in self._sections:
                o["body"].pack_forget()
                o["sign"].configure(text="+")
                o["head"].configure(border_color=LINE)
            if opened_now:
                self._sec_holder.pack_forget()
                return
            body.pack(fill="x", padx=16, pady=14)
            sign.configure(text="–")
            head.configure(border_color=ACC)
            if not self._sec_holder.winfo_manager():
                self._sec_holder.pack(fill="x", padx=14, pady=(4, 10), after=self._sec_grid)
        for w in (head, name, sign):
            w.bind("<Button-1>", flip)
            w.bind("<Enter>", lambda e: head.configure(fg_color=CARD2))
            w.bind("<Leave>", lambda e: head.configure(fg_color=CARD))
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
            colf = ctk.CTkFrame(self.teams_box, fg_color=mix(CARD, col, 0.06), corner_radius=BRADIUS)
            colf.grid(row=1, column=ci, sticky="nsew", padx=4)
            self.teams_box.grid_columnconfigure(ci, weight=1)
            ctk.CTkFrame(colf, height=3, fg_color=col, corner_radius=0).pack(fill="x")
            members = sorted(groups.get(side, []), key=lambda p: p["name"].lower())
            score = wins.get(members[0]["steamid"], 0) if members else 0
            hdr = ctk.CTkFrame(colf, fg_color="transparent")
            hdr.pack(fill="x", padx=8, pady=(6, 4))
            ctk.CTkLabel(hdr, text=tr(title).upper(), font=brand_font(13), text_color=col).pack(side="left")
            ctk.CTkLabel(hdr, text=str(score), font=brand_font(20), text_color=col).pack(side="right", padx=2)
            for p in members:
                ctk.CTkButton(colf, text=p["name"], anchor="w", height=36, corner_radius=BRADIUS, fg_color=CARD2,
                              hover_color=mix(CARD2, col, 0.45), border_width=0,
                              text_color=TEXT, font=font(14, "bold"),
                              command=lambda pl=p: self.pick_player(pl)).pack(fill="x", padx=8, pady=2)
            ctk.CTkFrame(colf, height=6, fg_color="transparent").pack()
        allb = ctk.CTkButton(self.teams_box, text=tr("Все игроки сразу — клавиатура следует за камерой CS2"),
                             height=38, corner_radius=BRADIUS, fg_color="transparent", hover_color=CARD2, border_width=1,
                             border_color=ACC, text_color=ACC, font=font(12, "bold"), command=self.pick_all)
        allb.grid(row=0, column=0, columnspan=2, sticky="ew", padx=4, pady=(2, 10))
        self.pick_title.configure(text=(info["map"] or tr("Демо")).upper())
        nm = os.path.basename(info["path"])
        self.pick_sub.configure(text=(nm if len(nm) < 60 else nm[:57] + "…") + "\n" +
                                tr("Выберите игрока — нажатия извлекутся автоматически"))
        self.pick_card.pack(fill="x", padx=20, pady=8)
        self.load_btn.configure(state="normal")
        self._fit_start()

    def pick_all(self):
        """Тест: нажатия всех игроков за один проход; клавиатура переключается вслед за камерой CS2."""
        if not self.info:
            return
        cache = self._cache_name(self.info["path"], f"all.v{extract.FORMAT_VERSION}.cs2keys")
        if os.path.exists(cache):
            try:
                with open(cache, encoding="utf-8") as f:
                    return self._set_all(json.load(f))
            except Exception:
                pass
        self._busy(True, "Извлекаю нажатия всех игроков… около минуты")
        fut = self.pool.submit(_extract_all_job, self.info["path"], self.info)
        fut.add_done_callback(lambda f: self.ui(lambda: self._all_result(f, cache)))

    def _all_result(self, fut, cache):
        self._busy(False)
        try:
            alld = fut.result()
            if not alld:
                raise ValueError("ни у одного игрока нет данных")
        except Exception as e:
            return self.show_error("E202", str(e))
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(cache, "w", encoding="utf-8") as f:
                json.dump(alld, f, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            pass
        self._set_all(alld)

    def _set_all(self, alld):
        order = [p["steamid"] for p in self.info["players"] if p["steamid"] in alld] if self.info else list(alld)
        start = self.observed if getattr(self, "observed", None) in alld else order[0]
        self.all_data = alld
        self._set_data(alld[start])
        self.msg("Все игроки: переключайте камеру в CS2 — клавиатура пойдёт за ней. "
                 "Или выбирайте игрока здесь.")

    def pick_player(self, p):
        self.all_data = None
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
        self.pick_title.configure(text=tr("Читаю демо…").upper())
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
        self._fill_allp()
        self.playing = False
        self.tick = float(self._round_start(self.rounds[0])) if self.rounds else float(self.t0)
        self.show_play()
        self._ensure_overlay(rebuild=True)
        self._ensure_vpanel()
        self._paint_speed()
        self._paint_voice()
        self.msg("Загрузите демо в CS2, выберите раунд и нажмите ▶.")
        self._render(force=True)

    # ---------- режим «все игроки» ----------
    def _fill_allp(self):
        fr = getattr(self, "allp_fr", None)
        if fr is None:
            return
        for w in fr.winfo_children():
            w.destroy()
        alld = getattr(self, "all_data", None)
        if not alld or not self.info:
            fr.pack_forget()
            return
        fr.pack(fill="x", padx=14, pady=(2, 6), after=self._allp_after)
        cur = (self.data or {}).get("steamid")
        self._allp_btns, self._allp_cur = {}, cur
        first = self.info["rounds"][0]["teams"] if self.info.get("rounds") else {}
        rows = {3: [], 2: []}
        for p in self.info["players"]:
            if p["steamid"] in alld:
                rows.setdefault(first.get(p["steamid"], p["team"]), []).append(p)
        fr.grid_columnconfigure((0, 1), weight=1, uniform="allp")
        for ci, (side, col, title) in enumerate(((3, CT_COL, "Начали за КТ"), (2, T_COL, "Начали за Т"))):
            box = ctk.CTkFrame(fr, fg_color=mix(CARD, col, 0.07), corner_radius=2)
            box.grid(row=0, column=ci, sticky="nsew", padx=(0, 5) if ci == 0 else (5, 0))
            ctk.CTkFrame(box, height=3, fg_color=col, corner_radius=0).pack(fill="x")
            ctk.CTkLabel(box, text=tr(title).upper(), font=brand_font(12), text_color=col, height=22,
                         anchor="w").pack(fill="x", padx=10, pady=(4, 0))
            for p in sorted(rows.get(side, []), key=lambda p: p["name"].lower()):
                on = p["steamid"] == cur
                b = ctk.CTkButton(box, text=p["name"], height=26, anchor="w", corner_radius=2,
                                  fg_color=col if on else "transparent", hover_color=mix(CARD2, col, 0.35),
                                  text_color=ACC_TXT if on else TEXT, font=font(13, "bold"),
                                  command=lambda sid=p["steamid"]: self._switch_player(sid))
                b.pack(fill="x", padx=6, pady=1)
                self._allp_btns[p["steamid"]] = (b, col)
            ctk.CTkFrame(box, height=6, fg_color="transparent").pack()

    def _score_text(self, d):
        wins = sum(1 for r in self.rounds if r.get("won"))
        losses = sum(1 for r in self.rounds if r.get("won") is False)
        acc = tr("точные нажатия" if d.get("precise") else "приблизительные нажатия")
        self.player_lbl.configure(text=(d.get("player") or "").upper())
        self.demo_lbl2.configure(text=f"{d.get('map') or ''}   ·   {acc}".upper())
        self.score_us.configure(text=str(wins))
        self.score_them.configure(text=str(losses))
        self.cam_btn.configure(text=tr(f"Камера на {d['player']}"))

    def _after_switch(self, d):
        """Быстрое обновление после смены игрока: без пересоздания виджетов (это тормозило клавиатуру)."""
        self.timeline.set_rounds(self.rounds, self.t0, self.t1)
        self._cur_round = None
        self._score_text(d)
        btns = getattr(self, "_allp_btns", {})
        old = getattr(self, "_allp_cur", None)
        for sid, on in ((old, False), (d["steamid"], True)):
            if sid in btns:
                b, col = btns[sid]
                b.configure(fg_color=col if on else "transparent", text_color=ACC_TXT if on else TEXT)
        self._allp_cur = d["steamid"]
        self._ensure_overlay()

    def _fill_play(self, d):
        self.round_btns = []
        self.timeline.set_rounds(self.rounds, self.t0, self.t1)
        self._cur_round = None
        self._score_text(d)
        self._paint_speed()
        self._paint_voice()

    # ================= отрисовка =================
    def _mark_round(self, ri):
        self._cur_round = ri
        n = len(self.rounds or [])
        if self.rounds and 0 <= ri < n:
            self.round_lbl.configure(text=f"{tr('Раунд').upper()} {self.rounds[ri]['n']} / {n}")
        cs = tr("CS2 подключена" if getattr(self, "_cs_ok", False) else "CS2 не подключена")
        self.tick_lbl.configure(text=f"{tr('тик')} {int(self.tick)}   ·   {cs}")

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
                                      text=("" if busy else "▶  ") + tr("Запускаю…" if busy else "Запустить CS2 и демо").upper())
        self._cs_ok = ok
        self.dot_lbl.configure(text_color=OK if ok else LOSS)
        self.status_bar.configure(fg_color=OK if ok else LOSS)
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
