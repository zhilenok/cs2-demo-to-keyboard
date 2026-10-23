# Точка входа: двойной клик запускает программу без консоли.
import multiprocessing
from cs2keys.main import run

if __name__ == "__main__":
    multiprocessing.freeze_support()
    run()
