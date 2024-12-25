# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('core', 'core'),
        ('ui', 'ui'),
        ('utils', 'utils')
    ],
    hiddenimports=[
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtUiTools',
        'PySide6.QtNetwork',
        'PySide6.QtPrintSupport',
        'PySide6.QtSvg',
        'PySide6.QtXml',
        'cv2',
        'numpy',
        'numpy.core._methods',
        'numpy.lib.format',
        'PIL',
        'PIL.Image',
        'PIL.ImageFilter',
        'PIL._imaging',
        'PIL.ImageQt',
        'PIL.ImageOps',
        'PIL.ImageEnhance',
        'ffmpeg',
        'ffmpeg-python',
        'utils',
        'utils.file_handler'
    ],
    hookspath=[],
    hooksconfig={
        "PIL": {
            "include_all": True
        }
    },
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='批量去水印工具_v2.0',
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
    icon='icon.ico'
) 