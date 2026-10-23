# -*- coding: utf-8 -*-
"""Функция GSI убрана. Модуль оставлен только чтобы удалить её файл из папки CS2, если он остался."""
import os

FILE = "gamestate_integration_cs2dtk.cfg"
PORT = 3125


def cfg_dir(cs2_exe):
    """...\\game\\bin\\win64\\cs2.exe -> ...\\game\\csgo\\cfg"""
    if not cs2_exe:
        return None
    game = os.path.dirname(os.path.dirname(os.path.dirname(cs2_exe)))
    d = os.path.join(game, "csgo", "cfg")
    return d if os.path.isdir(d) else None


def remove_cfg(directory):
    try:
        if directory:
            os.remove(os.path.join(directory, FILE))
            return True
    except OSError:
        pass
    return False
