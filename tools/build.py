# -*- coding: utf-8 -*-
"""Сборка одного файла "CS2 Demo to Keyboard.exe" (PyInstaller). Используется build.bat и GitHub Actions."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = "CS2 Demo to Keyboard"


def main():
    import PyInstaller.__main__
    sep = os.pathsep                       # ";" в Windows
    pkg = os.path.join(ROOT, "cs2keys")
    args = [
        os.path.join(ROOT, "CS2Keys.pyw"),
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", NAME,
        "--icon", os.path.join(pkg, "assets", "app.ico"),
        "--add-data", f"{os.path.join(pkg, 'fonts')}{sep}cs2keys/fonts",
        "--add-data", f"{os.path.join(pkg, 'assets')}{sep}cs2keys/assets",
        "--collect-all", "customtkinter",
        "--collect-all", "tkinterdnd2",
        "--collect-all", "demoparser2",
        "--hidden-import", "pyarrow", "--hidden-import", "polars", "--hidden-import", "pandas",
        "--hidden-import", "PIL.ImageTk",
        "--exclude-module", "scipy", "--exclude-module", "matplotlib", "--exclude-module", "IPython",
        "--exclude-module", "pytest", "--exclude-module", "sympy",
        "--workpath", os.path.join(ROOT, "build"),
        "--distpath", os.path.join(ROOT, "dist"),
        "--specpath", os.path.join(ROOT, "build"),
    ]
    PyInstaller.__main__.run(args)
    exe = os.path.join(ROOT, "dist", NAME + (".exe" if os.name == "nt" else ""))
    if not os.path.exists(exe):
        sys.exit("build failed: no " + exe)
    print("built:", exe)


if __name__ == "__main__":
    main()
