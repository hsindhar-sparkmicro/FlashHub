# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

pyocd_datas = collect_data_files('pyocd')
pyocd_hiddenimports = collect_submodules('pyocd')
cmsis_pack_manager_datas = collect_data_files('cmsis_pack_manager')
cmsis_pack_manager_lib = Path('vnev/lib/python3.12/site-packages/cmsis_pack_manager/cmsis_pack_manager/libcmsis_pack_manager.so')

extra_datas = []
if cmsis_pack_manager_lib.exists():
    extra_datas.append(
        (str(cmsis_pack_manager_lib), 'cmsis_pack_manager/cmsis_pack_manager')
    )

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config.json', '.'),
        ('images', 'images'),
    ] + pyocd_datas + cmsis_pack_manager_datas + extra_datas,
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtNetwork',
        'src.gui.main_window',
        'src.gui.flow_layout',
        'src.gui.pack_dialog',
        'src.gui.project_dialog',
        'src.gui.target_selector_dialog',
        'src.gui.tool_settings_dialog',
        'src.gui.workers',
        'src.backend.openocd_wrapper',
        'src.backend.pyocd_wrapper',
        'src.backend.stm32cubeprogrammer_wrapper',
        'src.utils.config_manager',
    ] + pyocd_hiddenimports,
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
    name='FlashHub',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window for GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add 'icon.ico' or 'icon.icns' if you have an icon
)
