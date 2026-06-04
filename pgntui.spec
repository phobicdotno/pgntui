# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import copy_metadata

a = Analysis(
    ["src/pgntui/__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        ("src/pgntui/decode/pgns.json", "pgntui/decode"),
        ("src/pgntui/themes/builtin", "pgntui/themes/builtin"),
        ("src/pgntui/examples", "pgntui/examples"),
    ] + copy_metadata("pgntui"),
    hiddenimports=["pgntui.drivers.actisense", "pgntui.drivers.replay", "pgntui.examples"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="pgntui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
