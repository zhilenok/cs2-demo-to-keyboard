# -*- coding: utf-8 -*-
"""Подключение к консоли CS2 (параметр запуска -netconport). Только локально."""
import collections, re, socket, threading, time

PROBLEMS = ("unknown command", "not playing", "no demo", "couldn't", "could not", "failed",
            "can't", "cannot", "not found")
NOISE = ("CSVCMsg_UserCommands", "SetConVar")
PAUSE_RE = re.compile(r"\b(un)?paused on tick (\d+)", re.I)
ACTION_RE = re.compile(r"CS2KEYS:(\w+)")
# CS2 пишет это в консоль, когда демо загрузилось и пошла картинка
INGAME_MARK = "-> CSGO_GAME_UI_STATE_INGAME"
MENU_MARK = "-> CSGO_GAME_UI_STATE_MAINMENU"
LOAD_TIMEOUT = 60.0          # если отметку не увидели — через минуту всё равно разрешаем команды
# пока демо грузится, можно только это: всё остальное (перемотка, камера, sv_cheats…) может уронить CS2
LOADING_OK = ("echo", "engine_no_focus_sleep", "tv_listen_voice_indices", "voice_", "snd_", "volume")


class DemoLoading(ConnectionError):
    """CS2 ещё загружает демо — команду не отправили, чтобы не уронить игру."""


class Netcon:
    def __init__(self, port=2121, host="127.0.0.1"):
        self.host, self.port = host, port
        self.sock = None
        self.lock = threading.Lock()
        self.cond = threading.Condition()
        self.lines = collections.deque(maxlen=500)
        self.seq = 0
        self.last_try = 0.0
        self.last_error = ""
        self.on_event = None      # вызывается при «paused/unpaused on tick N» из консоли CS2
        self.loading_until = 0.0  # пока time.time() < этого — демо грузится, лишние команды не шлём

    # ---- соединение ----
    def _connect(self):
        s = socket.create_connection((self.host, self.port), timeout=0.5)
        s.settimeout(None)
        self.sock = s
        self.last_error = ""
        threading.Thread(target=self._drain, args=(s,), daemon=True).start()
        s.sendall(b"engine_no_focus_sleep 0\n")

    def _drain(self, s):
        buf = b""
        try:
            while True:
                d = s.recv(65536)
                if not d:
                    break
                buf += d
                *parts, buf = buf.split(b"\n")
                for p in parts:
                    t = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", p.decode("utf-8", "replace")).strip()
                    if t:
                        if INGAME_MARK in t or MENU_MARK in t or PAUSE_RE.search(t):
                            # демо загрузилось (или загрузка отменилась) — через 2 с снова можно всё
                            if self.loading_until > time.time():
                                self.loading_until = time.time() + 2.0
                        ma = ACTION_RE.fullmatch(t)      # только чистый вывод echo, не ответ на запрос бинда
                        if ma and self.on_event:
                            try:
                                self.on_event("action", ma.group(1), time.perf_counter())
                            except Exception:
                                pass
                        mt = PAUSE_RE.search(t)
                        if mt and self.on_event:
                            try:
                                self.on_event("unpaused" if mt.group(1) else "paused", int(mt.group(2)),
                                              time.perf_counter())
                            except Exception:
                                pass
                        with self.cond:
                            self.seq += 1
                            self.lines.append((self.seq, t))
                            self.cond.notify_all()
        except OSError:
            pass
        if self.sock is s:
            self.sock = None

    @property
    def connected(self):
        if self.sock is not None:
            return True
        now = time.time()
        if now - self.last_try < 1.0:
            return False
        self.last_try = now
        try:
            self._connect()
            return True
        except ConnectionRefusedError:
            self.last_error = f"порт {self.port} закрыт: запустите CS2 через Workshop Tools с -netconport {self.port}"
        except socket.timeout:
            self.last_error = f"порт {self.port} не отвечает"
        except OSError as e:
            self.last_error = str(e)
        return False

    @property
    def loading(self):
        return time.time() < self.loading_until

    def send(self, *cmds):
        starts = any(c.strip().lower().startswith("playdemo") for c in cmds)
        if self.loading:
            if starts:
                raise DemoLoading("Демо уже загружается в CS2 — дождитесь картинки")
            if not all(c.strip().lower().startswith(LOADING_OK) for c in cmds):
                raise DemoLoading("CS2 ещё загружает демо — подождите, пока появится картинка")
        with self.lock:
            if not self.connected:
                raise ConnectionError(self.last_error or "нет соединения с CS2")
            data = "".join(c + "\n" for c in cmds).encode("utf-8")
            if starts:
                self.loading_until = time.time() + LOAD_TIMEOUT
            try:
                self.sock.sendall(data)
            except OSError:
                self.sock, self.last_try = None, 0
                if not self.connected:
                    raise ConnectionError("потеряно соединение с CS2")
                self.sock.sendall(data)

    # ---- чтение ответов ----
    def mark(self):
        with self.cond:
            return self.seq

    def since(self, seq):
        with self.cond:
            return [t for n, t in self.lines if n > seq]

    def wait_for(self, text, seq, timeout):
        end = time.time() + timeout
        with self.cond:
            while True:
                if any(text in t for n, t in self.lines if n > seq):
                    return True
                left = end - time.time()
                if left <= 0:
                    return False
                self.cond.wait(left)

    def ping(self, timeout=2.0):
        tag = "SYNC_PING_%d" % int(time.time() * 1000)
        seq = self.mark()
        self.send("echo " + tag)
        return self.wait_for(tag, seq, timeout)

    def problems(self, seq):
        return [t for t in self.since(seq) if any(p in t.lower() for p in PROBLEMS) and "sync_" not in t.lower()]

    def recent(self, n=80):
        with self.cond:
            out = [t for _, t in self.lines if not any(x in t for x in NOISE) and not t.startswith("SYNC_")]
        return out[-n:]
