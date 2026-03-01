# ChronicleMap

## Local Development

```powershell
cd D:\desktop\study\language\python\project\ChronicleMap
poetry install
poetry run pytest -q
```

## Local Packaging (Windows EXE)

Icon path:

- `assets/icons/chroniclemap.ico`

Build command:

```powershell
poetry install
poetry run python -m PyInstaller --noconfirm --clean --windowed --onefile --name ChronicleMap --icon assets/icons/chroniclemap.ico --collect-all PySide6 --collect-submodules PySide6 --collect-data chroniclemap chroniclemap/gui/__main__.py
```

Output:

- `dist/ChronicleMap.exe`

## GitHub Auto Release Packaging

This repository now includes:

- `/.github/workflows/release.yml`

When you push a tag like `v0.1.0`, GitHub Actions will:

1. Build Windows EXE with PyInstaller
2. Upload artifact
3. Create a GitHub Release and attach the EXE

## Versioning Rule (Important)

Before creating a release tag, keep these two versions consistent:

- `pyproject.toml` -> `[project].version`
- `chroniclemap/__init__.py` -> `__version__`

Then create and push tag:

```powershell
git add .
git commit -m "release: v0.1.0"
git tag v0.1.0
git push origin main
git push origin v0.1.0
```



# American Indian

cd D:\desktop\study\language\python\project\chroniclemap\

### poetry

poetry add xxx

poetry run xxx


### test

poetry run pytest -q

poetry run pytest tests/test_campaign_manager.py -q



import pdb; pdb.set_trace()  # ← 在这里设置断点
