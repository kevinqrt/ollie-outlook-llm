# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
tcl_root = Path(sys.base_prefix) / "tcl"
dll_root = Path(sys.base_prefix) / "DLLs"

datas = []
datas += collect_data_files("customtkinter")
datas += collect_data_files("tkinter", include_py_files=True)
datas += [
    ("..\\.env.example", "."),
    ("..\\frontend\\dist", "frontend\\dist"),
]
if tcl_root.exists():
    for file_path in tcl_root.rglob("*"):
        if file_path.is_file():
            relative_dir = Path("tcl") / file_path.relative_to(tcl_root).parent
            datas.append((str(file_path), str(relative_dir)))

binaries = []
for binary_name in ("_tkinter.pyd", "tcl86t.dll", "tk86t.dll"):
    binary_path = dll_root / binary_name
    if binary_path.exists():
        binaries.append((str(binary_path), "."))

hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
]
hiddenimports += collect_submodules("tkinter")

a = Analysis(
    ["run_desktop_host.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="OllieDesktopHost",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
