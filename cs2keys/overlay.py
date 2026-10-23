# -*- coding: utf-8 -*-
"""Прозрачное окно с клавиатурой и мышью поверх игры."""
import math
import os
import tkinter as tk

from .i18n import tr

IS_WIN = os.name == "nt"
KEY = "#ff00ff"            # цвет-ключ прозрачности (в дизайне не встречается)
CAP, CAP_EDGE, CAP_TEXT = "#2c3037", "#15171b", "#ece5d6"
DIM, DIM_EDGE, DIM_TEXT = "#4a4c50", "#2a2b2e", "#8d8f93"
GO, GO_EDGE, GO_TEXT = "#1fae52", "#0f6e32", "#ffffff"
PILL, PILL_TEXT, TAG = "#1b1d21", "#ece5d6", "#3ee07a"
# клавиши
K_FACE, K_EDGE, K_HI, K_BTN = "#262a31", "#121417", "#343942", "#2d3139"
K_TEXT, K_TEXT_DIM = "#dfe2e7", "#6f747d"
D_FACE, D_EDGE = "#34363a", "#1e1f22"               # игрок мёртв
G_FACE, G_EDGE, G_HI, G_RING = "#22c55e", "#15803d", "#6ee7a0", "#0e4f28"   # нажата
TAG_JUMP, TAG_WARN = "#f2f3f5", "#f0b429"
MOVE_BG = "#0f1f15"
MB = "#3b4049"             # кнопки мыши
APP_CAPTION = "CS2 Demo to Keyboard"
CAPTION = "#d2d5da"        # подпись над клавиатурой — неяркая, чтобы не отвлекать        # подложка в режиме перемещения

# (подпись, клавиша или None, ширина в ед., режим: always — видна всегда, pop — только при нажатии, ghost — пустое место)
ROWS = [
    [("Tab", "TAB", 1.5, "pop"), ("Q", None, 1, "ghost"), ("W", "W", 1, "always"), ("E", "E", 1, "pop"), ("R", "R", 1, "pop")],
    [("Caps", None, 1.75, "ghost"), ("A", "A", 1, "always"), ("S", "S", 1, "always"), ("D", "D", 1, "always"), ("F", "F", 1, "pop")],
    [("Shift", "SHIFT", 2.25, "always")],
    [("Ctrl", "CTRL", 1.5, "always"), ("Alt", None, 1.2, "ghost"), ("Пробел", "SPACE", 4.64, "always")],
]
GAP = 0.12


def rrect(c, x0, y0, x1, y1, r, **kw):
    r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
    pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1,
           x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
    return c.create_polygon(pts, smooth=True, **kw)


class Overlay(tk.Toplevel):
    KEY_COLOR = "#010101"      # почти чёрный ключ прозрачности: края текста дают тёмную тень, а не цветную кайму
    def __init__(self, master, keys, scale=1.0, alpha=0.95, pos=(80, 80), on_moved=None, transparent=True,
                 on_scaled=None):
        super().__init__(master)
        self.key = getattr(self, "KEY_COLOR", KEY)
        self.transparent = transparent
        self.on_scaled = on_scaled
        self.on_press = None
        self._resize = None
        self._rebuild_job = None
        self.keys = keys                     # порядок клавиш = биты маски
        self.scale, self.alpha, self.on_moved = scale, alpha, on_moved
        self.unlocked = False
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0)
        self.canvas.pack()
        self._apply_bg()
        self.attributes("-alpha", alpha)
        # не даём окну оказаться за пределами экрана
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = min(max(0, int(pos[0])), sw - 200)
        y = min(max(0, int(pos[1])), sh - 150)
        self.geometry(f"+{x}+{y}")
        self.canvas.bind("<ButtonPress-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)
        self._last = None
        self.build()
        self.after(300, self._apply_clickthrough)
        self.after(2000, self._keep_on_top)

    def _see_through(self):
        # в режиме перемещения фон сплошной: иначе клик между клавишами проваливается в игру
        return self.transparent and not self.unlocked

    def _apply_bg(self):
        bg = self.key if self._see_through() else (MOVE_BG if self.unlocked else "#101114")
        self.configure(bg=bg)
        self.canvas.configure(bg=bg)
        if IS_WIN:
            try:
                self.attributes("-transparentcolor", self.key if self._see_through() else "")
            except tk.TclError:
                pass

    def set_transparent(self, on):
        self.transparent = on
        self._apply_bg()
        self._apply_clickthrough()
        self._layered()

    def info(self):
        self.update_idletasks()
        return (f"окно {self.winfo_width()}×{self.winfo_height()} в точке {self.winfo_x()},{self.winfo_y()}, "
                f"видимо: {'да' if self.winfo_viewable() else 'нет'}")

    def center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"+{x}+{y}")
        self.deiconify()
        self.lift()
        if self.on_moved:
            self.on_moved(x, y)

    # ---------- построение ----------
    def build(self):
        """Прежний дизайн: плоские клавиши с тёмным «бортиком», без строки подписей снизу."""
        c = self.canvas
        c.delete("all")
        u = 46 * self.scale
        self.u = u
        pad = 0.25 * u
        fnt = ("Segoe UI", max(8, int(u * 0.34)), "bold")
        small = ("Segoe UI", max(7, int(u * 0.24)), "bold")
        self.items = {}
        # маленькая подпись над клавиатурой
        # «CS2 Demo to Keyboard», буквы D и K — в цветах логотипа; рисуем кусками подряд
        import tkinter.font as tkfont
        cap = tkfont.Font(family="Segoe UI", size=max(8, int(u * 0.25)), weight="bold")
        cx, cy = pad, pad + 0.14 * u
        for part, col in (("CS2 ", CAPTION), ("D", "#45d6e0"), ("emo to ", CAPTION), ("K", "#7ef0a6"),
                          ("eyboard", CAPTION)):
            c.create_text(cx, cy, text=part, fill=col, anchor="w", font=cap)
            cx += cap.measure(part)
        y = pad + 0.45 * u
        kbw = 0
        for row in ROWS:
            x = pad
            for label, key, w, mode in row:
                x0, x1 = x, x + w * u
                if mode != "ghost":
                    edge = rrect(c, x0, y + 0.08 * u, x1, y + u + 0.08 * u, 0.16 * u, fill=CAP_EDGE, outline="")
                    face = rrect(c, x0, y, x1, y + u, 0.16 * u, fill=CAP, outline="")
                    text = c.create_text((x0 + x1) / 2, y + u / 2, text=tr(label), fill=CAP_TEXT,
                                         font=fnt if len(label) == 1 else small)
                    self.items[key] = {"edge": edge, "face": face, "text": text, "mode": mode, "down": False}
                x = x1 + GAP * u
            kbw = max(kbw, x - GAP * u)
            y += (1 + GAP) * u
        kbh = y - GAP * u

        # мышь
        mx0 = kbw + 0.55 * u
        mw, mh, ht = 1.9 * u, 3.0 * u, 1.35 * u
        my0 = pad + 0.7 * u
        mx1, my1 = mx0 + mw, my0 + mh
        e = 0.08 * u
        self._mouse_body(c, mx0, my0 + e, mx1, my1 + e, ht, CAP_EDGE)
        self._mouse_body(c, mx0, my0, mx1, my1, ht, CAP)
        bb = (mx0, my0, mx1, my0 + 2 * ht)
        lmb = c.create_arc(*bb, start=90, extent=90, style=tk.PIESLICE, fill=MB, outline="")
        rmb = c.create_arc(*bb, start=0, extent=90, style=tk.PIESLICE, fill=MB, outline="")
        cx = (mx0 + mx1) / 2
        c.create_line(cx, my0, cx, my0 + ht, fill=CAP_EDGE, width=max(2, int(u * 0.05)))
        c.create_line(mx0, my0 + ht, mx1, my0 + ht, fill=CAP_EDGE, width=max(2, int(u * 0.05)))
        rrect(c, cx - 0.11 * u, my0 + 0.35 * u, cx + 0.11 * u, my0 + 0.8 * u, 0.1 * u, fill=CAP_EDGE, outline="")
        self.items["LMB"] = {"arc": lmb, "down": False, "mode": "always"}
        self.items["RMB"] = {"arc": rmb, "down": False, "mode": "always"}

        W = mx1 + pad
        # «прыжок» слева и «примерно» справа — просто текст с тенью на прозрачном фоне
        sy = max(kbh, my1 + e) + 0.4 * u
        tag_font = ("Segoe UI", max(8, int(u * 0.3)), "bold")
        self.tag_shadow = c.create_text(pad + 2, sy + 2, text="", fill="#0b0b0b", anchor="w", font=tag_font)
        self.tag_text = c.create_text(pad, sy, text="", fill=TAG_JUMP, anchor="w", font=tag_font)
        self.warn_shadow = c.create_text(W - pad + 2, sy + 2, text="", fill="#0b0b0b", anchor="e", font=tag_font)
        self.warn_text = c.create_text(W - pad, sy, text="", fill=TAG_WARN, anchor="e", font=tag_font)
        H = sy + 0.35 * u + pad
        # режим перемещения: рамка, подпись посередине и уголок для размера
        self.move_frame = c.create_rectangle(2, 2, W - 2, H - 2, outline=GO, width=3, dash=(8, 5), state="hidden")
        self.move_label_bg = rrect(c, W / 2 - 2.6 * u, H / 2 - 0.3 * u, W / 2 + 2.6 * u, H / 2 + 0.3 * u, 0.2 * u,
                                   fill=GO_EDGE, outline="", state="hidden")
        self.move_label = c.create_text(W / 2, H / 2, text=tr("Перетащите  •  уголок — размер"),
                                        fill="#ffffff", font=small, state="hidden")
        g = max(16, 0.55 * u)
        self.grip = c.create_polygon(W - 3, H - 3 - g, W - 3, H - 3, W - 3 - g, H - 3, fill=GO, outline="", state="hidden")
        self.W, self.H, self.g = W, H, g
        c.configure(width=int(W), height=int(H))
        self._state = None
        self._dead = None
        for k, it in self.items.items():
            if it["mode"] == "pop":
                for part in ("edge", "face", "text"):
                    c.itemconfigure(it[part], state="hidden")
        self.set_unlocked(self.unlocked)

    def _mouse_body(self, c, x0, y0, x1, y1, ht, color):
        r = (x1 - x0) / 2
        c.create_arc(x0, y0, x1, y0 + 2 * ht, start=0, extent=180, style=tk.CHORD, fill=color, outline="")
        c.create_rectangle(x0, y0 + ht, x1, y1 - r, fill=color, outline="")
        c.create_arc(x0, y1 - 2 * r, x1, y1, start=180, extent=180, style=tk.CHORD, fill=color, outline="")

    # ---------- состояние ----------
    def update_state(self, mask, weapon=None, tag=""):
        alive = bool(mask >> 14 & 1)
        c = self.canvas
        if alive != self._dead:
            self._dead = alive
            self._state = None
        state = (mask, tag or "")
        if state == self._state:
            return
        self._state = state
        d = 0.06 * self.u
        parts = [p for p in (tag or "").split("   ") if p]
        t1 = "   ".join(tr(p) for p in parts if p != "примерно") if alive else ""
        t2 = tr("примерно") if alive and "примерно" in parts else ""
        for a, b, t in ((self.tag_text, self.tag_shadow, t1), (self.warn_text, self.warn_shadow, t2)):
            c.itemconfigure(a, text=t)
            c.itemconfigure(b, text=t)
        for i, k in enumerate(self.keys):
            it = self.items.get(k)
            if not it:
                continue
            on = bool(mask >> i & 1)
            if "arc" in it:
                c.itemconfigure(it["arc"], fill=GO if on else (MB if alive else DIM))
                continue
            if it["mode"] == "pop":
                for part in ("edge", "face", "text"):
                    c.itemconfigure(it[part], state="normal" if on else "hidden")
            if on:
                c.itemconfigure(it["face"], fill=GO)
                c.itemconfigure(it["edge"], fill=GO_EDGE)
                c.itemconfigure(it["text"], fill=GO_TEXT)
            else:
                c.itemconfigure(it["face"], fill=CAP if alive else DIM)
                c.itemconfigure(it["edge"], fill=CAP_EDGE if alive else DIM_EDGE)
                c.itemconfigure(it["text"], fill=CAP_TEXT if alive else DIM_TEXT)
            if on != it["down"]:
                dy = d if on else -d
                c.move(it["face"], 0, dy)
                c.move(it["text"], 0, dy)
                it["down"] = on

    # ---------- настройки ----------
    def set_scale(self, scale):
        self.scale = scale
        st = self._state
        self.build()
        if st:
            self.update_state(st[0], None, st[1])

    def set_alpha(self, a):
        self.alpha = a
        self.attributes("-alpha", a)
        self._layered()

    def set_unlocked(self, on):
        self.unlocked = on
        st = "normal" if on else "hidden"
        for it in (self.move_frame, self.move_label_bg, self.move_label, self.grip):
            self.canvas.itemconfigure(it, state=st)
        self.canvas.tag_raise(self.move_label_bg)
        self.canvas.tag_raise(self.move_label)
        self.canvas.tag_raise(self.grip)
        self.canvas.configure(cursor="fleur" if on else "")
        self._apply_bg()
        self._apply_clickthrough()
        self._layered()

    # ---------- Windows: клики сквозь окно, без значка на панели задач ----------
    def _apply_clickthrough(self):
        if not IS_WIN:
            return
        try:
            import ctypes
            u32 = ctypes.windll.user32
            # настоящее окно верхнего уровня (у Tk холст лежит в дочернем окне;
            # если сделать «слоистым» дочернее окно, оно становится невидимым)
            hwnd = int(self.wm_frame(), 16)
            GWL_EXSTYLE, LAYERED, TRANSPARENT, TOOL, NOACT = -20, 0x80000, 0x20, 0x80, 0x08000000
            st = u32.GetWindowLongW(hwnd, GWL_EXSTYLE) | LAYERED | TOOL | NOACT
            # в режиме перемещения окно должно принимать мышь как обычное
            st = (st & ~TRANSPARENT & ~NOACT) if self.unlocked else (st | TRANSPARENT)
            u32.SetWindowLongW(hwnd, GWL_EXSTYLE, st)
            # после смены стиля прозрачность нужно задать заново напрямую через WinAPI
            # (Tk не переприменяет её, если значение не менялось)
            self._layered(hwnd)
            SWP = 0x0001 | 0x0002 | 0x0020 | 0x0040   # NOSIZE | NOMOVE | FRAMECHANGED | SHOWWINDOW
            u32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, SWP)   # -1 = поверх всех
        except Exception:
            pass

    def _layered(self, hwnd=None):
        if not IS_WIN:
            return
        try:
            import ctypes
            u32 = ctypes.windll.user32
            hwnd = hwnd or int(self.wm_frame(), 16)
            LWA_COLORKEY, LWA_ALPHA = 0x1, 0x2
            flags = LWA_ALPHA | (LWA_COLORKEY if self._see_through() else 0)
            r, g, b = (int(self.key[i:i + 2], 16) for i in (1, 3, 5))
            u32.SetLayeredWindowAttributes(hwnd, r | (g << 8) | (b << 16), int(max(0.05, min(1.0, self.alpha)) * 255), flags)
        except Exception:
            pass

    def _keep_on_top(self):
        try:
            self.attributes("-topmost", True)
            self.lift()
        except tk.TclError:
            return
        self.after(2000, self._keep_on_top)

    # ---------- перетаскивание, размер, прилипание к краям ----------
    def _in_grip(self, e):
        return e.x > self.W - self.g * 1.6 and e.y > self.H - self.g * 1.6

    def _drag_start(self, e):
        if not self.unlocked:
            return
        if self.on_press:
            self.on_press()
        if self._in_grip(e):
            self._resize = (e.x_root, self.W, self.scale)
            self._last = None
            return
        self._resize = None
        if IS_WIN and self._native_move():
            return
        self._last = (e.x_root, e.y_root, self.winfo_x(), self.winfo_y())

    def _native_move(self):
        """Перетаскивание средствами самой Windows — как за заголовок обычного окна."""
        try:
            import ctypes
            u32 = ctypes.windll.user32
            hwnd = int(self.wm_frame(), 16)
            u32.ReleaseCapture()
            u32.SendMessageW(hwnd, 0x00A1, 2, 0)      # WM_NCLBUTTONDOWN, HTCAPTION — цикл перемещения до отпускания
            self.update_idletasks()
            x, y = self._snap(self.winfo_x(), self.winfo_y())
            self.geometry(f"+{x}+{y}")
            if self.on_moved:
                self.on_moved(x, y)
            return True
        except Exception:
            return False

    def move_to(self, ax, ay, margin=12):
        """ax, ay: 0 — левый/верхний край, 0.5 — центр, 1 — правый/нижний."""
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = self.winfo_width(), self.winfo_height()
        x = int(margin + (sw - w - 2 * margin) * ax)
        y = int(margin + (sh - h - 2 * margin) * ay)
        self.geometry(f"+{x}+{y}")
        self.lift()
        if self.on_moved:
            self.on_moved(x, y)

    def nudge(self, dx, dy):
        x, y = self.winfo_x() + dx, self.winfo_y() + dy
        self.geometry(f"+{x}+{y}")
        if self.on_moved:
            self.on_moved(x, y)

    def _drag(self, e):
        if not self.unlocked:
            return
        if self._resize:
            x0, w0, s0 = self._resize
            ns = max(0.5, min(1.8, s0 * (w0 + e.x_root - x0) / w0))
            if abs(ns - self.scale) > 0.015:
                self.scale = ns
                if self._rebuild_job is None:         # перестраиваем не чаще раза в 40 мс
                    self._rebuild_job = self.after(40, self._rebuild_now)
            return
        if self._last:
            x0, y0, wx, wy = self._last
            x, y = self._snap(wx + e.x_root - x0, wy + e.y_root - y0)
            self.geometry(f"+{x}+{y}")

    def _rebuild_now(self):
        self._rebuild_job = None
        state = self._state
        self.build()
        if state:
            self.update_state(state[0], None, state[1])

    def _snap(self, x, y, dist=18, margin=8):
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = self.winfo_width(), self.winfo_height()
        if abs(x - margin) < dist:
            x = margin
        if abs(x + w - (sw - margin)) < dist:
            x = sw - margin - w
        if abs(y - margin) < dist:
            y = margin
        if abs(y + h - (sh - margin)) < dist:
            y = sh - margin - h
        cx = (sw - w) // 2
        if abs(x - cx) < dist:                         # и к центру по горизонтали
            x = cx
        return int(x), int(y)

    def _drag_end(self, e):
        if self._resize:
            self._resize = None
            if self._rebuild_job:
                self.after_cancel(self._rebuild_job)
                self._rebuild_now()
            if self.on_scaled:
                self.on_scaled(round(self.scale, 2))
        self._last = None
        if self.on_moved:
            self.on_moved(self.winfo_x(), self.winfo_y())


T_COL, CT_COL = "#e0a33a", "#5b9bd5"        # цвета сторон как в CS2


class VoicePanel(Overlay):
    """Панель «кто говорит» — отдельное прозрачное окно, двигается так же, как клавиатура."""
    ROWS = 5
    # почти чёрный цвет-ключ: сглаженные края текста смешиваются с ним в тёмную «тень», а не в розовую кайму
    KEY_COLOR = "#010101"

    def __init__(self, master, **kw):
        kw.setdefault("pos", (80, 400))
        super().__init__(master, keys=[], **kw)

    def build(self):
        c = self.canvas
        c.delete("all")
        u = 92 * self.scale          # в 2 раза крупнее, чем было; дальше — ползунок «Панель голоса»
        self.u = u
        pad = 0.2 * u
        W = 4.6 * u
        rh = 0.62 * u
        self.row_items = []
        small = ("Segoe UI", max(7, int(u * 0.26)), "bold")
        for i in range(self.ROWS):
            y = pad + i * (rh + 0.1 * u)
            bg = c.create_text(pad + 1.02 * u + 2, y + rh / 2 + 2, text="", fill="#0b0b0b", anchor="w",
                               font=small, state="hidden")             # тень под ником для читаемости
            bar = rrect(c, pad, y + 0.06 * u, pad + 0.14 * u, y + rh - 0.06 * u, 0.06 * u, fill=T_COL, outline="",
                        state="hidden")
            # значок динамика: корпус + две дуги
            sx, sy = pad + 0.42 * u, y + rh / 2
            spk = c.create_polygon(sx - 0.1 * u, sy - 0.08 * u, sx - 0.02 * u, sy - 0.08 * u, sx + 0.1 * u, sy - 0.18 * u,
                                   sx + 0.1 * u, sy + 0.18 * u, sx - 0.02 * u, sy + 0.08 * u, sx - 0.1 * u, sy + 0.08 * u,
                                   fill=GO, outline="", state="hidden")
            arc1 = c.create_arc(sx - 0.02 * u, sy - 0.2 * u, sx + 0.3 * u, sy + 0.2 * u, start=-45, extent=90,
                                style=tk.ARC, outline=GO, width=max(2, int(u * 0.045)), state="hidden")
            txt = c.create_text(pad + 1.02 * u, y + rh / 2, text="", fill=PILL_TEXT, anchor="w", font=small, state="hidden")
            self.row_items.append((bg, bar, spk, arc1, txt))
        H = pad + self.ROWS * (rh + 0.1 * u) - 0.1 * u + pad
        self.move_frame = c.create_rectangle(2, 2, W - 2, H - 2, outline=GO, width=3, dash=(8, 5), state="hidden")
        self.move_label_bg = rrect(c, pad, pad, W - pad, pad + rh, 0.18 * u, fill=GO_EDGE, outline="", state="hidden")
        self.move_label = c.create_text(W / 2, pad + rh / 2, text=tr("Панель голоса"), fill="#ffffff",
                                        font=small, state="hidden")
        g = max(16, 0.55 * u)
        self.grip = c.create_polygon(W - 3, H - 3 - g, W - 3, H - 3, W - 3 - g, H - 3, fill=GO, outline="", state="hidden")
        self.W, self.H, self.g = W, H, g
        c.configure(width=int(W), height=int(H))
        self._state = None
        self._dead = None
        self.set_unlocked(self.unlocked)

    def set_scale(self, scale):
        self.scale = scale
        st = self._state
        self.build()
        if st is not None:
            self.update_state(list(st))

    def _rebuild_now(self):
        self._rebuild_job = None
        st = self._state
        self.build()
        if st is not None:
            self.update_state(list(st))

    def update_state(self, speakers, *_):
        """speakers: список (имя, сторона 2/3/None, слышно ли, это выбранный игрок) — только те, кого слышно."""
        state = tuple(speakers)
        if state == self._state:
            return
        self._state = state
        c = self.canvas
        for i, items in enumerate(self.row_items):
            bg, bar, spk, arc1, txt = items
            if i < len(speakers):
                name, side, audible, me = speakers[i]
                for it in items:
                    c.itemconfigure(it, state="normal")
                col = T_COL if side == 2 else CT_COL if side == 3 else "#888888"
                c.itemconfigure(bar, fill=col)
                c.itemconfigure(txt, text=name, fill=TAG if me else PILL_TEXT)
                c.itemconfigure(bg, text=name)
                c.itemconfigure(spk, fill=GO)
                c.itemconfigure(arc1, outline=GO)
            else:
                for it in items:
                    c.itemconfigure(it, state="hidden")
        if self.unlocked:
            for it in (self.move_frame, self.move_label_bg, self.move_label, self.grip):
                c.tag_raise(it)
