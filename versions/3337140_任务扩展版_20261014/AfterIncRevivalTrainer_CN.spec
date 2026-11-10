from pathlib import Path
root = Path(SPECPATH)
a = Analysis([str(root / 'trainer_gui.py')], pathex=[str(root)],
             binaries=[(str(root / 'native' / 'AfterIncTaskExtension.dll'), 'native')],
             datas=[], hiddenimports=[], hookspath=[], hooksconfig={},
             runtime_hooks=[], excludes=[], noarchive=False, optimize=0)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [],
          name='AfterIncRevivalTrainer_CN', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False,
          uac_admin=True)
