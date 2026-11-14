# -*- coding: utf-8 -*-
"""Game State Integration: CS2 сама сообщает программе, на какого игрока смотрит камера.

Перед запуском CS2 программа кладёт в её папку cfg файл gamestate_integration_cs2dtk.cfg. CS2 читает его
при старте и при каждом изменении шлёт короткий JSON на http://127.0.0.1:PORT — только внутри компьютера.
Из JSON берём лишь SteamID и ник наблюдаемого игрока. Чужие запросы без нашего токена игнорируются."""
import json
import os
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

FILE = "gamestate_integration_cs2dtk.cfg"
PORT = 3125


def cfg_dir(cs2_exe):
    """...\\game\\bin\\win64\\cs2.exe -> ...\\game\\csgo\\cfg"""
    if not cs2_exe:
        return None
    game = os.path.dirname(os.path.dirname(os.path.dirname(cs2_exe)))
    d = os.path.join(game, "csgo", "cfg")
    return d if os.path.isdir(d) else None


def write_cfg(directory, port, token):
    if not directory:
        return False
    text = ('"CS2 Demo to Keyboard"\n{\n'
            f'\t"uri"\t\t"http://127.0.0.1:{int(port)}"\n'
            '\t"timeout"\t"1.0"\n\t"buffer"\t"0.0"\n\t"throttle"\t"0.05"\n\t"heartbeat"\t"1.0"\n'
            f'\t"auth"\n\t{{\n\t\t"token"\t"{token}"\n\t}}\n'
            '\t"data"\n\t{\n\t\t"provider"\t"1"\n\t\t"player_id"\t"1"\n\t\t"player_state"\t"1"\n\t}\n}\n')
    try:
        with open(os.path.join(directory, FILE), "w", encoding="utf-8") as f:
            f.write(text)
        return True
    except OSError:
        return False


def remove_cfg(directory):
    try:
        if directory:
            os.remove(os.path.join(directory, FILE))
            return True
    except OSError:
        pass
    return False


class Listener:
    """Маленький HTTP-сервер на 127.0.0.1: принимает сообщения CS2 и вызывает on_player(steamid, name)."""

    def __init__(self, on_player, port=PORT):
        self.on_player = on_player
        self.port = port
        self.token = secrets.token_hex(12)
        self.last = None
        self.srv = None

    def start(self):
        owner = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                try:
                    n = int(self.headers.get("Content-Length") or 0)
                    data = json.loads(self.rfile.read(min(n, 1 << 20)) or b"{}")
                except Exception:
                    data = {}
                self.send_response(200)
                self.end_headers()
                if (data.get("auth") or {}).get("token") != owner.token:
                    return
                pl = data.get("player") or {}
                sid = str(pl.get("steamid") or "")
                if sid:
                    # каждое сообщение (и «пульс» раз в секунду) передаём дальше: программа сама сверит,
                    # совпадает ли камера с клавиатурой, — так ловим и автопереключение камеры CS2
                    owner.last = sid
                    try:
                        owner.on_player(sid, str(pl.get("name") or ""))
                    except Exception:
                        pass

            def log_message(self, *a):
                pass

        try:
            self.srv = ThreadingHTTPServer(("127.0.0.1", self.port), H)
        except OSError:
            self.srv = None                      # порт занят — работаем без слежения за камерой
            return False
        self.srv.daemon_threads = True
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        return True

    def stop(self):
        if self.srv:
            try:
                self.srv.shutdown()
            except Exception:
                pass
