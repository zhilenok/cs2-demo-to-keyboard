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
    # polars 2.x держит свою часть в отдельном модуле (_polars_runtime_32 …) — добавляем тот, что установлен
    import importlib.util
    for mod in ("_polars_runtime_32", "_polars_runtime_64", "_polars_runtime_compat", "polars_runtime_32"):
        if importlib.util.find_spec(mod) is not None:
            args[args.index("--workpath"):args.index("--workpath")] = ["--collect-all", mod]
    PyInstaller.__main__.run(args)
    exe = os.path.join(ROOT, "dist", NAME + (".exe" if os.name == "nt" else ""))
    if not os.path.exists(exe):
        sys.exit("build failed: no " + exe)
    print("built:", exe)


if __name__ == "__main__":
    main()
