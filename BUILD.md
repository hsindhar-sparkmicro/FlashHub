# FlashHub Build Instructions

## Prerequisites

- Python 3.8+
- All dependencies from requirements.txt installed
- PyInstaller (`pip install pyinstaller`)

## Building

### Linux
```bash
chmod +x build.sh
./build.sh
```

### Windows
```cmd
build.bat
```

### Manual Build
```bash
pyinstaller FlashHub.spec
```

## Output

- Executable will be in `dist/` folder
- Linux: `dist/FlashHub`
- Windows: `dist\FlashHub.exe`

## Distribution

The executable is standalone and includes:
- Python runtime
- All dependencies (PyQt6, pyocd, etc.)
- Source code
- config.json and images folder

Users don't need Python installed to run it.

## Troubleshooting

### Missing modules
Add to `hiddenimports` in FlashHub.spec

### Missing data files
Add to `datas` in FlashHub.spec like:
```python
datas=[
    ('your_file.txt', '.'),
    ('your_folder', 'your_folder'),
]
```

### Large file size
- Use `--exclude-module` for unused packages
- Disable UPX: set `upx=False` in spec file

### Icon
Add icon file and update spec:
```python
icon='icon.ico'  # Windows
icon='icon.icns' # macOS
```

## Advanced: Creating Installers

### Windows Installer (NSIS)
1. Install NSIS from https://nsis.sourceforge.io/
2. Create installer script
3. Compile to setup.exe

### Linux AppImage
1. Install appimagetool
2. Create AppDir structure
3. Package: `appimagetool FlashHub.AppDir`

### Debian Package
```bash
pip install fpm
fpm -s dir -t deb -n flashhub -v 1.0.0 dist/FlashHub=/usr/bin/
```
