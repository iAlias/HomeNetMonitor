# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for HomeNetMonitor

import os
from pathlib import Path

block_cipher = None

# Resolve resource paths relative to spec file location
SPEC_DIR = Path(SPECPATH)
RESOURCES_DIR = SPEC_DIR / "resources"

a = Analysis(
    [str(SPEC_DIR / "src" / "main.py")],
    pathex=[str(SPEC_DIR)],
    binaries=[],
    datas=[
        (str(RESOURCES_DIR / "mac_oui.json"), "resources"),
        (str(RESOURCES_DIR / "icon.ico"), "resources"),
    ],
    hiddenimports=[
        "scapy.layers.all",
        "scapy.arch.windows",
        "scapy.arch.windows.native",
        "scapy.layers.inet",
        "scapy.layers.l2",
        "scapy.layers.dns",
        "scapy.sendrecv",
        "netifaces",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "pyqtgraph",
        "psutil",
        "requests",
        "sqlite3",
        "win10toast",
        "src.ui.main_window",
        "src.ui.dashboard_tab",
        "src.ui.devices_tab",
        "src.ui.connections_tab",
        "src.ui.alerts_tab",
        "src.ui.settings_dialog",
        "src.core.packet_sniffer",
        "src.core.device_scanner",
        "src.core.dns_resolver",
        "src.core.geo_lookup",
        "src.core.data_store",
        "src.models.device",
        "src.models.connection",
        "src.utils.mac_vendor",
        "src.utils.constants",
    ],
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
    name="HomeNetMonitor",
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
    icon=str(RESOURCES_DIR / "icon.ico"),
    uac_admin=True,
    onefile=True,
)
