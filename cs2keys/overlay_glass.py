# -*- coding: utf-8 -*-
"""Клавиатура «Стекло»: компактная раскладка, полупрозрачные клавиши, нажатые светятся зелёным.

Картинка рисуется через Pillow с настоящей попиксельной прозрачностью и выводится на экран
функцией Windows UpdateLayeredWindow (сквозь стекло видно игру). Перетаскивание, размер,
клики сквозь окно и прилипание к краям — как у классической клавиатуры (класс Overlay)."""
import os
import sys
import tkinter as tk

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .i18n import tr
from .overlay import Overlay, VoicePanel, IS_WIN

# (подпись, клавиша, x, y, ширина, режим) — в единицах «u» (размер клавиши); pop — видна только при нажатии
LAYOUT = [
    ("Tab", "TAB", 0.00, 0.00, 1.90, "always"),
    ("W", "W", 2.24, 0.00, 1.00, "always"),          # как на клавиатуре: на четверть клавиши левее S
    ("E", "E", 3.36, 0.00, 1.00, "pop"),
    ("Shift", "SHIFT", 0.00, 1.12, 1.25, "always"),
    ("A", "A", 1.37, 1.12, 1.00, "always"),
    ("S", "S", 2.49, 1.12, 1.00, "always"),
    ("D", "D", 3.61, 1.12, 1.00, "always"),
    ("Ctrl", "CTRL", 0.00, 2.24, 1.25, "always"),
    ("Пробел", "SPACE", 1.37, 2.24, 3.24, "always"),
]
KB_W, KB_H = 4.61, 3.24
MOUSE = (4.81, 0.25, 1.5, 2.6)          # x, y, ширина, высота
BADGES = ("R", "F")                       # редкие клавиши — плашками в нижней строке
BASE_U = 40

WHITE = (255, 255, 255)
GREEN_TOP, GREEN_BOT = (110, 231, 160), (34, 197, 94)
GREEN_EDGE = (190, 255, 215)
CAP_HI = (141, 255, 187)
TAG_WARN = (240, 180, 41)
MOVE_BG = (15, 31, 21)
GO = (31, 174, 82)


def _font_path(bold=True):
    """Шрифт для надписей: Segoe UI на Windows, иначе — что найдётся."""
    cands = []
    if IS_WIN:
        win = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        cands += [os.path.join(win, "seguisb.ttf" if bold else "segoeui.ttf"), os.path.join(win, "segoeuib.ttf"),
                  os.path.join(win, "arialbd.ttf")]
    base = getattr(sys, "_MEIPASS", None)
    here = os.path.join(base, "cs2keys", "fonts") if base else os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
    cands += [os.path.join(here, "Exo2CS2K-Bold.ttf"), "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    for p in cands:
        if os.path.exists(p):
            return p
    return None


_FONTS = {}


def _font(size, bold=True):
    size = max(6, int(round(size)))
    k = (size, bold)
    if k not in _FONTS:
        p = _font_path(bold)
        try:
            _FONTS[k] = ImageFont.truetype(p, size) if p else ImageFont.load_default()
        except Exception:
            _FONTS[k] = ImageFont.load_default()
    return _FONTS[k]


def _vgrad(w, h, top, bot):
    """Вертикальный градиент RGBA (top, bot — кортежи из 4 чисел)."""
    col = Image.new("RGBA", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        col.putpixel((0, y), tuple(int(a + (b - a) * t) for a, b in zip(top, bot)))
    return col.resize((w, h))


def _rounded_mask(w, h, r, ss=4):
    m = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), radius=r * ss, fill=255)
    return m.resize((w, h), Image.LANCZOS)


def _outline(w, h, r, color, width=1, ss=4):
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), radius=r * ss, outline=color,
                                         width=max(1, int(width * ss)))
    return im.resize((w, h), Image.LANCZOS)


def _text(img, xy, s, fnt, fill, anchor="mm", shadow=True):
    d = ImageDraw.Draw(img)
    if shadow:
        d.text((xy[0], xy[1] + 1), s, font=fnt, fill=(0, 0, 0, 110), anchor=anchor)
    d.text(xy, s, font=fnt, fill=fill, anchor=anchor)


def _glass_face(w, h, r, state, glow_pad):
    """Спрайт клавиши (с полями под свечение). state: off / on / dead."""
    W, H = w + 2 * glow_pad, h + 2 * glow_pad
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    mask = _rounded_mask(w, h, r)
    if state == "on":
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        g = Image.new("RGBA", (w, h), GREEN_BOT + (200,))
        glow.paste(g, (glow_pad, glow_pad), mask)
        glow = glow.filter(ImageFilter.GaussianBlur(glow_pad * 0.45))
        out.alpha_composite(glow)
        face = _vgrad(w, h, GREEN_TOP + (195,), GREEN_BOT + (150,))
        edge = GREEN_EDGE + (235,)
        hi = (255, 255, 255, 170)
    else:
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sh.paste(Image.new("RGBA", (w, h), (0, 0, 0, 60)), (glow_pad, glow_pad + max(1, h // 14)), mask)
        out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(max(1, h // 10))))
        if state == "dead":
            face = _vgrad(w, h, (255, 255, 255, 26), (255, 255, 255, 10))
            edge, hi = (255, 255, 255, 50), (255, 255, 255, 40)
        else:
            face = _vgrad(w, h, (255, 255, 255, 58), (255, 255, 255, 16))
            edge, hi = (255, 255, 255, 92), (255, 255, 255, 115)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    layer.paste(face, (0, 0), mask)
    layer.alpha_composite(_outline(w, h, r, edge, 1))
    # блик по верхней кромке
    d = ImageDraw.Draw(layer)
    d.line((r, 1, w - r, 1), fill=hi, width=1)
    out.alpha_composite(layer, (glow_pad, glow_pad))
    return out


class LayeredMixin:
    """Вывод готовой картинки Pillow на экран с попиксельной прозрачностью (UpdateLayeredWindow).
    Если не получилось — запасной путь: картинка на холсте и прозрачность по цвету-ключу."""

    def _init_layered(self):
        self._mode = "wait"           # wait → ulw (стекло) или fallback (по цвету-ключу)
        self._fails = 0
        self.diag = None
        self._img = None
        self._tk_img = None

    # ---------- фон и прозрачность: всё делает картинка ----------
    def _apply_bg(self):
        bg = "#101114"
        self.configure(bg=bg)
        self.canvas.configure(bg=bg)

    def set_alpha(self, a):
        self.alpha = a
        self._present()

    def set_transparent(self, on):
        self.transparent = on
        self._apply_clickthrough()
        self._present()

    def _layered(self, hwnd=None):
        self._present()

    # ---------- вывод на экран ----------
    def info(self):
        base = super().info()
        return f"{base}, стекло: {self.diag or self._mode}"

    def _present(self):
        img = self._img
        if img is None:
            return
        if IS_WIN and self._mode != "fallback":
            try:
                mapped = self.winfo_ismapped() and self.winfo_viewable()
            except tk.TclError:
                return
            if not mapped:
                # пока окно не показано, у Tk ещё нет настоящего окна верхнего уровня — ждём
                self._retry_present(80)
                return
            if self._update_layered(img):
                self._mode, self._fails = "ulw", 0
                return
            # Tk мог снова включить у окна SetLayeredWindowAttributes — сбрасываем стиль и пробуем ещё раз
            self._toggle_layered()
            if self._update_layered(img):
                self._mode, self._fails = "ulw", 0
                return
            self._fails += 1
            if self._fails < 4:
                self._retry_present(150)
                return
            # не вышло — запасной путь: картинка на холсте и прозрачность по цвету-ключу
            self._mode = "fallback"
            self._toggle_layered()
        self._show_on_canvas(img)
        if IS_WIN:
            try:
                self.attributes("-transparentcolor", self.key if self._see_through() else "")
            except tk.TclError:
                pass
            Overlay._layered(self)

    def _retry_present(self, ms):
        if not getattr(self, "_retry_job", None):
            def retry():
                self._retry_job = None
                self._present()
            self._retry_job = self.after(ms, retry)

    def _toggle_layered(self):
        try:
            import ctypes
            u32 = ctypes.windll.user32
            hwnd = int(self.wm_frame(), 16)
            GWL_EXSTYLE, LAYERED = -20, 0x80000
            st = u32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            u32.SetWindowLongW(hwnd, GWL_EXSTYLE, st & ~LAYERED)
            u32.SetWindowLongW(hwnd, GWL_EXSTYLE, st | LAYERED)
        except Exception:
            pass

    def _show_on_canvas(self, img):
        """Без UpdateLayeredWindow (не Windows или ошибка): картинка на холсте поверх тёмного фона."""
        from PIL import ImageTk
        bg = Image.new("RGBA", img.size, (16, 17, 20, 255))
        if IS_WIN and self._see_through():
            # пиксели почти без заливки уходят в цвет-ключ — клавиши остаются, фон пропадает
            key = tuple(int(self.key[i:i + 2], 16) for i in (1, 3, 5)) + (255,)
            bg = Image.new("RGBA", img.size, key)
            a = img.getchannel("A").point(lambda v: 255 if v > 40 else 0)
            flat = Image.alpha_composite(Image.new("RGBA", img.size, (40, 44, 50, 255)), img)
            bg.paste(flat, (0, 0), a)
        else:
            bg.alpha_composite(img)
        self._tk_img = ImageTk.PhotoImage(bg.convert("RGB"))
        c = self.canvas
        if not getattr(self, "_img_item", None) or not c.find_withtag(self._img_item):
            c.delete("all")
            self._img_item = c.create_image(0, 0, anchor="nw", image=self._tk_img)
        else:
            c.itemconfigure(self._img_item, image=self._tk_img)

    def _update_layered(self, img):
        try:
            import ctypes
            from ctypes import wintypes
            u32 = ctypes.WinDLL("user32", use_last_error=True)
            gdi = ctypes.WinDLL("gdi32", use_last_error=True)
            hwnd = int(self.wm_frame(), 16)
            GWL_EXSTYLE, LAYERED = -20, 0x80000
            u32.GetWindowLongW.restype = ctypes.c_long
            st = u32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if not st & LAYERED:
                u32.SetWindowLongW(hwnd, GWL_EXSTYLE, st | LAYERED)
            w, h = img.size
            data = img.convert("RGBa").tobytes("raw", "BGRa")

            class BITMAPINFOHEADER(ctypes.Structure):
                _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                            ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD),
                            ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
                            ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                            ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

            class BLENDFUNCTION(ctypes.Structure):
                _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                            ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]

            bmi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
            gdi.CreateDIBSection.restype = wintypes.HBITMAP
            gdi.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT,
                                             ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD]
            gdi.CreateCompatibleDC.restype = wintypes.HDC
            gdi.CreateCompatibleDC.argtypes = [wintypes.HDC]
            gdi.SelectObject.restype = wintypes.HGDIOBJ
            gdi.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
            gdi.DeleteObject.argtypes = [wintypes.HGDIOBJ]
            gdi.DeleteDC.argtypes = [wintypes.HDC]
            u32.GetDC.restype = wintypes.HDC
            u32.GetDC.argtypes = [wintypes.HWND]
            u32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
            u32.UpdateLayeredWindow.argtypes = [wintypes.HWND, wintypes.HDC, ctypes.c_void_p, ctypes.c_void_p,
                                                wintypes.HDC, ctypes.c_void_p, wintypes.COLORREF, ctypes.c_void_p,
                                                wintypes.DWORD]
            screen = u32.GetDC(None)
            mem = gdi.CreateCompatibleDC(screen)
            bits = ctypes.c_void_p()
            hbmp = gdi.CreateDIBSection(screen, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
            ok = False
            if hbmp and bits.value:
                ctypes.memmove(bits, data, len(data))
                old = gdi.SelectObject(mem, hbmp)
                size = wintypes.SIZE(w, h)
                src = wintypes.POINT(0, 0)
                blend = BLENDFUNCTION(0, 0, int(max(0.05, min(1.0, self.alpha)) * 255), 1)   # AC_SRC_ALPHA
                ok = bool(u32.UpdateLayeredWindow(hwnd, screen, None, ctypes.byref(size), mem, ctypes.byref(src), 0,
                                                  ctypes.byref(blend), 2))                        # ULW_ALPHA
                gdi.SelectObject(mem, old)
                gdi.DeleteObject(hbmp)
            gdi.DeleteDC(mem)
            u32.ReleaseDC(None, screen)
            self.diag = None if ok else f"UpdateLayeredWindow ошибка {ctypes.get_last_error()}, окно {hwnd:#x}"
            return ok
        except Exception as e:
            self.diag = f"UpdateLayeredWindow: {e}"
            return False


class GlassOverlay(LayeredMixin, Overlay):
    """Компактная «стеклянная» клавиатура. Публичный интерфейс — как у Overlay."""

    def __init__(self, *a, **kw):
        self._init_layered()
        self._sprites = {}
        self._txt_cache = {}
        self.player, self.speed = "", ""
        self._mask, self._tag = 0, ""
        super().__init__(*a, **kw)

    # ---------- построение ----------
    def build(self):
        u = BASE_U * self.scale
        self.u = u
        pad = int(round(0.3 * u))                  # поле вокруг — под свечение
        self.pad = pad
        self.cap_h = int(round(0.5 * u))
        self.foot_h = int(round(0.62 * u))
        kb_top = pad + self.cap_h
        W = int(round(pad * 2 + (MOUSE[0] + MOUSE[2]) * u))
        H = int(round(kb_top + KB_H * u + self.foot_h + pad))
        self.kb_top = kb_top
        self.W, self.H = W, H
        self.g = max(16, 0.45 * u)
        r = max(3, int(round(0.2 * u)))
        gp = max(4, int(round(0.28 * u)))
        self.gp = gp
        self._sprites = {}
        self._txt_cache = {}
        self._base_cache = {}
        self.keys_geo = []
        for label, key, x, y, w, mode in LAYOUT:
            px, py = int(round(pad + x * u)), int(round(kb_top + y * u))
            pw, ph = int(round(w * u)), int(round(u))
            name = tr(label)
            fsz = 0.34 * u if len(name) == 1 else 0.26 * u
            sprites = {}
            for st in ("off", "on", "dead"):
                spr = _glass_face(pw, ph, r, st, gp)
                col = (255, 255, 255, 235) if st != "dead" else (255, 255, 255, 110)
                _text(spr, (gp + pw / 2, gp + ph / 2), name, _font(fsz), col, shadow=st != "dead")
                sprites[st] = spr
            self.keys_geo.append((key, px - gp, py - gp, mode, sprites))
        self._build_mouse(u, pad, kb_top)
        # плашки R / F
        bh = int(round(0.42 * u))
        bw = int(round(0.5 * u))
        self.badge_sprites = {}
        for b in BADGES:
            spr = _glass_face(bw, bh, max(2, int(0.12 * u)), "on", gp)
            _text(spr, (gp + bw / 2, gp + bh / 2), b, _font(0.26 * u), (255, 255, 255, 240))
            self.badge_sprites[b] = spr
        self.badge_w, self.badge_h = bw, bh
        self.canvas.configure(width=W, height=H)
        self.geometry(f"{W}x{H}")
        self._state = None
        self._dead = None
        self._render()

    def _build_mouse(self, u, pad, kb_top):
        mx, my, mw, mh = MOUSE
        x, y = int(round(pad + mx * u)), int(round(kb_top + my * u))
        w, h = int(round(mw * u)), int(round(mh * u))
        ht = int(round(h * 0.45))
        r = w // 2
        gp = self.gp
        body_mask = _rounded_mask(w, h, r)
        self.mouse_pos = (x - gp, y - gp)
        sprites = {}
        for st in ("off", "dead"):
            sprites["body_" + st] = _glass_face(w, h, r, st, gp)
        # кнопки: левая/правая половина верхней части, обрезанные по корпусу
        for side in ("L", "R"):
            half = Image.new("L", (w, h), 0)
            ImageDraw.Draw(half).rectangle((0, 0, w // 2 - 1, ht) if side == "L" else (w // 2, 0, w, ht), fill=255)
            from PIL import ImageChops
            m = ImageChops.multiply(half, body_mask)
            on = Image.new("RGBA", (w + 2 * gp, h + 2 * gp), (0, 0, 0, 0))
            glow = Image.new("RGBA", (w + 2 * gp, h + 2 * gp), (0, 0, 0, 0))
            glow.paste(Image.new("RGBA", (w, h), GREEN_BOT + (190,)), (gp, gp), m)
            on.alpha_composite(glow.filter(ImageFilter.GaussianBlur(gp * 0.45)))
            fill = _vgrad(w, h, GREEN_TOP + (205,), GREEN_BOT + (165,))
            layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            layer.paste(fill, (0, 0), m)
            on.alpha_composite(layer, (gp, gp))
            sprites["btn_" + side] = on
        # линии раздела и колёсико — поверх
        lines = Image.new("RGBA", (w + 2 * gp, h + 2 * gp), (0, 0, 0, 0))
        d = ImageDraw.Draw(lines)
        d.line((gp + w // 2, gp + 1, gp + w // 2, gp + ht), fill=(255, 255, 255, 80), width=1)
        d.line((gp + 1, gp + ht, gp + w - 2, gp + ht), fill=(255, 255, 255, 80), width=1)
        ww, wh = max(3, int(0.12 * w)), max(6, int(0.15 * h))
        d.rounded_rectangle((gp + w // 2 - ww // 2, gp + int(0.12 * h), gp + w // 2 + ww // 2, gp + int(0.12 * h) + wh),
                            radius=ww // 2, fill=(0, 0, 0, 120))
        sprites["lines"] = lines
        self.mouse_sprites = sprites

    # ---------- состояние ----------
    def update_state(self, mask, weapon=None, tag=""):
        state = (mask, tag or "")
        if state == self._state:
            return
        self._state = state
        self._mask, self._tag = mask, tag or ""
        self._render()

    def set_speed(self, text):
        """Скорость меняется почти каждый тик — перерисовываем её не чаще раза в 100 мс."""
        if text == self.speed:
            return
        self.speed = text
        if not text:
            return self._render()
        if getattr(self, "_speed_job", None) is None:
            def go():
                self._speed_job = None
                self._render(footer_only=True)
            self._speed_job = self.after(100, go)

    def set_player(self, name):
        self.player = name or ""
        self._render()

    def set_unlocked(self, on):
        self.unlocked = on
        try:
            self.canvas.configure(cursor="fleur" if on else "")
        except tk.TclError:
            pass
        self._apply_clickthrough()
        self._render()

    # ---------- рисование ----------
    def _cached_text(self, s, size, fill, bold=True):
        k = (s, size, fill, bold)
        im = self._txt_cache.get(k)
        if im is None:
            fnt = _font(size, bold)
            l, t, r, b = fnt.getbbox(s) if s else (0, 0, 1, 1)
            im = Image.new("RGBA", (r - l + 4, b - t + 5), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            d.text((2 - l, 3 - t), s, font=fnt, fill=(0, 0, 0, 150))
            d.text((2 - l, 2 - t), s, font=fnt, fill=fill)
            if len(self._txt_cache) > 600:
                self._txt_cache.clear()
            self._txt_cache[k] = im
        return im

    def _caption(self, img):
        """«CS2 Demo to Keyboard»: заглавные (CS2, D, K) светятся зелёным."""
        size = 0.27 * self.u
        x, y = self.pad, self.pad
        for part, hi in (("CS2", True), (" ", False), ("D", True), ("emo to ", False), ("K", True), ("eyboard", False)):
            if part == " ":
                x += int(_font(size).getlength(" "))
                continue
            im = self._cached_text(part, size, CAP_HI + (255,) if hi else (255, 255, 255, 180))
            img.alpha_composite(im, (int(x), int(y)))
            x += int(_font(size).getlength(part))

    def _base(self):
        """Всё, кроме нижней строки: фон, подпись/метки, клавиши, мышь. Кэшируется по состоянию."""
        W, H, u = self.W, self.H, self.u
        mask = self._mask
        alive = bool(mask >> 14 & 1)
        parts = [p for p in self._tag.split("   ") if p] if alive else []
        idx = {k: i for i, k in enumerate(self.keys)}
        key = (mask & 0x7FFF, tuple(parts), self.unlocked, self.transparent)
        cache = self.__dict__.setdefault("_base_cache", {})
        img = cache.get(key)
        if img is not None:
            return img, idx
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        if self.unlocked:
            d.rounded_rectangle((0, 0, W - 1, H - 1), radius=int(0.2 * u), fill=MOVE_BG + (190,))
        elif not self.transparent:
            d.rounded_rectangle((0, 0, W - 1, H - 1), radius=int(0.2 * u), fill=(16, 17, 20, 255))
        # верхняя строка: подпись программы, а в прыжке — метки «прыжок» / «примерно» на её месте
        t1 = "   ".join(tr(p) for p in parts if p != "примерно")
        t2 = tr("примерно") if "примерно" in parts else ""
        if t1 or t2:
            x = self.pad
            for s_, col in ((t1, (255, 255, 255, 240)), (t2, TAG_WARN + (255,))):
                if s_:
                    im = self._cached_text(s_, 0.27 * u, col)
                    img.alpha_composite(im, (int(x), self.pad))
                    x += im.width + int(0.25 * u)
        else:
            self._caption(img)
        for k, x0, y0, mode, spr in self.keys_geo:
            on = k in idx and bool(mask >> idx[k] & 1)
            if mode == "pop" and not on:
                continue
            img.alpha_composite(spr["on" if on else ("off" if alive else "dead")], (x0, y0))
        ms = self.mouse_sprites
        img.alpha_composite(ms["body_off" if alive else "body_dead"], self.mouse_pos)
        for side, k in (("L", "LMB"), ("R", "RMB")):
            if k in idx and mask >> idx[k] & 1:
                img.alpha_composite(ms["btn_" + side], self.mouse_pos)
        img.alpha_composite(ms["lines"], self.mouse_pos)
        if self.unlocked:
            self._draw_move(img)
        if len(cache) > 96:
            cache.clear()
        cache[key] = img
        return img, idx

    def _render(self, footer_only=False):
        if not hasattr(self, "keys_geo"):
            return
        W, u = self.W, self.u
        base, idx = self._base()
        img = base.copy()
        mask = self._mask
        # нижняя строка: ник · R F · скорость
        fy = int(self.kb_top + KB_H * u + 0.18 * u)
        size = 0.27 * u
        if self.player:
            img.alpha_composite(self._cached_text(self.player, size, (255, 255, 255, 220)), (self.pad, fy))
        if self.speed:
            im = self._cached_text(self.speed, size, (255, 255, 255, 220))
            img.alpha_composite(im, (W - self.pad - im.width, fy))
        shown = [b for b in BADGES if b in idx and mask >> idx[b] & 1]
        if shown:
            gap = int(0.12 * u)
            total = len(shown) * self.badge_w + (len(shown) - 1) * gap
            bx = int(W / 2 - total / 2)
            for b in shown:
                img.alpha_composite(self.badge_sprites[b], (bx - self.gp, fy - self.gp - 1))
                bx += self.badge_w + gap
        self._img = img
        self._present()

    def _draw_move(self, img):
        W, H, u = self.W, self.H, self.u
        d = ImageDraw.Draw(img)
        step, dash = 13, 8
        for x in range(2, W - 2, step):
            d.line((x, 2, min(x + dash, W - 3), 2), fill=GO + (255,), width=3)
            d.line((x, H - 3, min(x + dash, W - 3), H - 3), fill=GO + (255,), width=3)
        for y in range(2, H - 2, step):
            d.line((2, y, 2, min(y + dash, H - 3)), fill=GO + (255,), width=3)
            d.line((W - 3, y, W - 3, min(y + dash, H - 3)), fill=GO + (255,), width=3)
        s = tr("Перетащите  •  уголок — размер")
        im = self._cached_text(s, max(9, 0.24 * u), (255, 255, 255, 255))
        if im.width > W - 0.6 * u:
            im = self._cached_text(tr("Перетащите"), max(9, 0.24 * u), (255, 255, 255, 255))
        bw, bh = im.width + int(0.4 * u), im.height + int(0.16 * u)
        bx, by = (W - bw) // 2, (H - bh) // 2
        d.rounded_rectangle((bx, by, bx + bw, by + bh), radius=bh // 2, fill=(15, 110, 50, 235))
        img.alpha_composite(im, (bx + (bw - im.width) // 2, by + (bh - im.height) // 2))
        g = int(self.g)
        d.polygon([(W - 3, H - 3 - g), (W - 3, H - 3), (W - 3 - g, H - 3)], fill=GO + (255,))



# ---------------- панель «кто говорит» в стиле «Стекло» ----------------
# цвета игроков, как в CS2 (CCSPlayerController.m_iCompTeammateColor): жёлтый, фиолетовый, зелёный, синий, оранжевый
PLAYER_COLORS = {0: (242, 227, 59), 1: (168, 85, 247), 2: (47, 210, 122), 3: (74, 163, 255), 4: (255, 154, 46)}
SIDE_COLORS = {2: (224, 176, 80), 3: (91, 155, 213)}


def _name_font(size):
    """Ник — шрифтом Exo 2 (в папке fonts), если его нет — обычным."""
    base = getattr(sys, "_MEIPASS", None)
    here = os.path.join(base, "cs2keys", "fonts") if base else os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
    size = max(7, int(round(size)))
    k = ("exo", size)
    if k not in _FONTS:
        p = os.path.join(here, "Exo2CS2K-Bold.ttf")
        try:
            _FONTS[k] = ImageFont.truetype(p, size) if os.path.exists(p) else _font(size)
        except Exception:
            _FONTS[k] = _font(size)
    return _FONTS[k]


def _circle_avatar(im, d, ring):
    """Круглая аватарка диаметром d с тонкой светлой обводкой."""
    ss = 4
    big = im.resize((d * ss, d * ss), Image.LANCZOS)
    m = Image.new("L", (d * ss, d * ss), 0)
    ImageDraw.Draw(m).ellipse((0, 0, d * ss - 1, d * ss - 1), fill=255)
    out = Image.new("RGBA", (d * ss, d * ss), (0, 0, 0, 0))
    out.paste(big, (0, 0), m)
    ImageDraw.Draw(out).ellipse((1, 1, d * ss - 2, d * ss - 2), outline=ring, width=int(1.5 * ss))
    return out.resize((d, d), Image.LANCZOS)


def _letter_avatar(name, d, col):
    ss = 4
    out = Image.new("RGBA", (d * ss, d * ss), (0, 0, 0, 0))
    dr = ImageDraw.Draw(out)
    dr.ellipse((0, 0, d * ss - 1, d * ss - 1), fill=tuple(int(c * 0.45) for c in col) + (235,),
               outline=col + (255,), width=int(1.5 * ss))
    ch = (name.strip()[:1] or "?").upper()
    dr.text((d * ss / 2, d * ss / 2 + ss), ch, font=_name_font(d * 0.55 * ss), fill=(255, 255, 255, 240), anchor="mm")
    return out.resize((d, d), Image.LANCZOS)


def _speaker_icon(size, col):
    """Зелёный динамик с волнами и мягким свечением."""
    ss = 4
    n = size * ss
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = col + (255,)
    cy = n / 2
    d.polygon([(n * 0.08, cy - n * 0.12), (n * 0.24, cy - n * 0.12), (n * 0.44, cy - n * 0.3),
               (n * 0.44, cy + n * 0.3), (n * 0.24, cy + n * 0.12), (n * 0.08, cy + n * 0.12)], fill=c)
    w = int(n * 0.07)
    d.arc((n * 0.3, cy - n * 0.22, n * 0.66, cy + n * 0.22), -50, 50, fill=c, width=w)
    d.arc((n * 0.3, cy - n * 0.38, n * 0.86, cy + n * 0.38), -50, 50, fill=c, width=w)
    im = im.resize((size, size), Image.LANCZOS)
    pad = max(2, size // 4)
    out = Image.new("RGBA", (size + 2 * pad, size + 2 * pad), (0, 0, 0, 0))
    glow = Image.new("RGBA", out.size, (0, 0, 0, 0))
    glow.paste(Image.new("RGBA", im.size, col + (170,)), (pad, pad), im.getchannel("A"))
    out.alpha_composite(glow.filter(ImageFilter.GaussianBlur(pad * 0.6)))
    out.alpha_composite(im, (pad, pad))
    return out, pad


class GlassVoicePanel(LayeredMixin, VoicePanel):
    """«Кто говорит» в стиле стеклянной клавиатуры: полоска цвета игрока, аватарка Steam, ник шрифтом Exo 2."""
    BASE_U = 56

    def __init__(self, *a, **kw):
        self._init_layered()
        self._txt_cache = {}
        self._rows_cache = {}
        self._speakers = []
        self._poll_job = None
        super().__init__(*a, **kw)

    _cached_text = GlassOverlay._cached_text
    _draw_move = GlassOverlay._draw_move

    def build(self):
        u = self.BASE_U * self.scale
        self.u = u
        self.pad = pad = int(round(0.3 * u))
        self.rw, self.rh = int(round(5.4 * u)), int(round(0.92 * u))
        self.gap = int(round(0.14 * u))
        self.W = W = 2 * pad + self.rw
        self.H = H = 2 * pad + self.ROWS * self.rh + (self.ROWS - 1) * self.gap
        self.g = max(16, 0.45 * u)
        self.gp = max(4, int(round(0.28 * u)))
        self._txt_cache, self._rows_cache = {}, {}
        self._face = _glass_face(self.rw, self.rh, max(3, int(0.22 * u)), "off", self.gp)
        self._spk, self._spk_pad = _speaker_icon(max(10, int(0.44 * u)), GREEN_BOT)
        self.canvas.configure(width=W, height=H)
        self.geometry(f"{W}x{H}")
        self._state = None
        self._dead = None
        self.row_items = []
        self._render()

    def update_state(self, speakers, *_):
        state = tuple(tuple(s) for s in speakers)
        if state == self._state:
            return
        self._state = state
        self._speakers = list(state)
        self._render()

    def set_unlocked(self, on):
        self.unlocked = on
        try:
            self.canvas.configure(cursor="fleur" if on else "")
        except tk.TclError:
            pass
        self._apply_clickthrough()
        self._render()

    def _row(self, sp):
        from . import avatars
        name, side, audible, me = sp[:4]
        sid = sp[4] if len(sp) > 4 else None
        color = sp[5] if len(sp) > 5 else None
        av = avatars.get(sid) if sid else None
        key = (name, side, me, sid, color, av is not None)
        img = self._rows_cache.get(key)
        if img is not None:
            return img
        u, rw, rh, gp = self.u, self.rw, self.rh, self.gp
        col = PLAYER_COLORS.get(color) if isinstance(color, int) else None
        col = col or SIDE_COLORS.get(side, (150, 156, 168))
        img = self._face.copy()
        # полоска цвета игрока слева — по форме скруглённого края
        r = max(3, int(0.22 * u))
        sm = Image.new("L", (rw, rh), 0)
        ImageDraw.Draw(sm).rounded_rectangle((0, 0, rw - 1, rh - 1), radius=r, fill=255)
        cut = Image.new("L", (rw, rh), 0)
        ImageDraw.Draw(cut).rectangle((0, 0, max(3, int(0.1 * u)), rh), fill=255)
        from PIL import ImageChops
        stripe = ImageChops.multiply(sm, cut)
        glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        glow.paste(Image.new("RGBA", (rw, rh), col + (200,)), (gp, gp), stripe)
        img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(max(2, gp * 0.35))))
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        lay.paste(Image.new("RGBA", (rw, rh), col + (255,)), (gp, gp), stripe)
        img.alpha_composite(lay)
        # аватарка
        d = int(round(0.66 * u))
        ax, ay = gp + int(0.26 * u), gp + (rh - d) // 2
        ava = _circle_avatar(av, d, col + (230,)) if av is not None else _letter_avatar(name, d, col)
        img.alpha_composite(ava, (ax, ay))
        # ник
        fnt = _name_font(0.36 * u)
        nx = ax + d + int(0.2 * u)
        maxw = gp + rw - nx - int(0.85 * u)
        s = name
        while s and fnt.getlength(s) > maxw:
            s = s[:-1]
        if s != name and s:
            s = s[:-1] + "…"
        dr = ImageDraw.Draw(img)
        fill = CAP_HI + (255,) if me else (255, 255, 255, 240)
        dr.text((nx, gp + rh / 2 + 1), s, font=fnt, fill=(0, 0, 0, 140), anchor="lm")
        dr.text((nx, gp + rh / 2), s, font=fnt, fill=fill, anchor="lm")
        # динамик справа
        sw = self._spk.width
        img.alpha_composite(self._spk, (gp + rw - int(0.2 * u) - sw + self._spk_pad, gp + (rh - sw) // 2))
        if len(self._rows_cache) > 64:
            self._rows_cache.clear()
        self._rows_cache[key] = img
        return img

    def _render(self, footer_only=False):
        if not hasattr(self, "rw"):
            return
        from . import avatars
        W, H, u = self.W, self.H, self.u
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(img)
        if self.unlocked:
            dr.rounded_rectangle((0, 0, W - 1, H - 1), radius=int(0.2 * u), fill=MOVE_BG + (190,))
        elif not self.transparent and self._speakers:
            dr.rounded_rectangle((0, 0, W - 1, H - 1), radius=int(0.2 * u), fill=(16, 17, 20, 255))
        rows = self._speakers
        if self.unlocked and not rows:        # в режиме перемещения показываем пример строки
            rows = [(tr("Панель голоса"), 2, True, False, None, 0)]
        for i, sp in enumerate(rows[:self.ROWS]):
            y = self.pad + i * (self.rh + self.gap)
            img.alpha_composite(self._row(sp), (self.pad - self.gp, y - self.gp))
        if self.unlocked:
            self._draw_move(img)
        self._img = img
        self._present()
        # аватарки ещё качаются — перерисуем, когда придут
        if avatars.pending() and self._poll_job is None:
            def poll():
                self._poll_job = None
                self._rows_cache.clear()
                self._render()
            self._poll_job = self.after(700, poll)
