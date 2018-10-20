# -*- mode: python -*-

block_cipher = None


a = Analysis(['__test.py'],
             pathex=['C:\\Users\\kevin\\Documents\\GitHub\\- Desktop App Infrastructure\\Eel2'],
             binaries=[],
             datas=[('C:\\Users\\kevin\\Anaconda3\\lib\\site-packages\\eel\\eel.js', 'eel'), ('Web', 'Web')],
             hiddenimports=['bottle_websocket'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='__test',
          debug=False,
          strip=False,
          upx=True,
          console=True )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='__test')
