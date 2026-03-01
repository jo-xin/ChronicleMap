# ChronicleMap

[![Release](https://img.shields.io/github/v/release/yourusername/ChronicleMap)](https://github.com/yourusername/ChronicleMap/releases)
[![Python](https://img.shields.io/badge/python-3.11-blue)](https://www.python.org/)
[![Poetry](https://img.shields.io/badge/poetry-managed-blueviolet)](https://python-poetry.org/)

> 一个基于 Python 和 PySide6 的桌面应用，用于时间线地图可视化。

## 目录

- [快速开始](#快速开始)
- [环境准备](#环境准备)
- [开发指南](#开发指南)
- [构建与打包](#构建与打包)
  - [本地打包](#本地打包)
  - [自动发布](#自动发布)
- [OCR 依赖说明](#ocr-依赖说明)
- [版本管理](#版本管理)

---

## 快速开始

```powershell
# 1. 克隆项目
git clone <repository-url>
cd ChronicleMap

# 2. 安装依赖（使用 Poetry）
poetry install

# 3. 运行应用
poetry run python -m chroniclemap.gui
```

---

## 环境准备

### 必需工具

- **Python 3.11+**
- **Poetry**（依赖管理）：`pip install poetry`
- **Tesseract OCR**（可选但推荐，用于日期识别）

### 项目结构

```
ChronicleMap/
├── chroniclemap/          # 主代码目录
│   ├── __init__.py       # 版本号定义处
│   └── gui/              # GUI 入口
├── assets/icons/         # 应用图标
├── tests/                # 测试文件
├── pyproject.toml        # 项目配置与版本号
└── dist/                 # 构建输出（自动生成）
```

---

## 开发指南

### 日常开发流程

```powershell
# 进入项目目录
cd D:\desktop\study\language\python\project\ChronicleMap

# 安装/更新依赖
poetry install

# 运行测试
poetry run pytest -q

# 运行特定测试文件
poetry run pytest tests/test_campaign_manager.py -q

# 启动应用（开发模式）
poetry run python -m chroniclemap.gui
```

### 调试

在代码中插入断点：

```python
import pdb; pdb.set_trace()  # 程序运行到这里会进入交互式调试
```

或使用 VS Code 的调试功能（已配置 `.vscode/launch.json`）。

### 添加新依赖

```powershell
# 生产依赖
poetry add <package-name>

# 开发依赖（如 pytest, black 等）
poetry add --group dev <package-name>

# 运行临时命令（无需进入虚拟环境）
poetry run <command>
```

---

## 构建与打包

### 资源路径

- **应用图标**：`assets/icons/chroniclemap.ico`

### 本地打包

#### 方案 A：单文件模式（OneFile）
适合分发，启动稍慢，只有一个 `.exe` 文件。

```powershell
poetry run python -m PyInstaller `
  --noconfirm --clean --windowed --onefile `
  --name ChronicleMap `
  --icon assets/icons/chroniclemap.ico `
  --hidden-import PySide6.QtCore `
  --hidden-import PySide6.QtGui `
  --hidden-import PySide6.QtWidgets `
  --add-data "chroniclemap/gui/locales;chroniclemap/gui/locales" `
  chroniclemap/gui/__main__.py
```

**输出**：`dist/ChronicleMap.exe`

#### 方案 B：目录模式（OneDir）
启动更快，但是一个文件夹，适合频繁测试。

```powershell
poetry run python -m PyInstaller `
  --noconfirm --clean --windowed --onedir `
  --name ChronicleMap `
  --icon assets/icons/chroniclemap.ico `
  --hidden-import PySide6.QtCore `
  --hidden-import PySide6.QtGui `
  --hidden-import PySide6.QtWidgets `
  --add-data "chroniclemap/gui/locales;chroniclemap/gui/locales" `
  chroniclemap/gui/__main__.py
```

**输出**：`dist/ChronicleMap/`（文件夹）

### 自动发布（推荐）

项目已配置 GitHub Actions（`.github/workflows/release.yml`）。

**发布步骤**：

1. **统一版本号**（见下节[版本管理](#版本管理)）
2. **提交并打标签**：
   ```powershell
   git add .
   git commit -m "release: v0.1.0"
   git tag v0.1.0
   git push origin main
   git push origin v0.1.0  # 触发 GitHub Actions
   ```
3. **等待构建**：GitHub Actions 会自动：
   - 构建单文件 EXE
   - 构建目录版并压缩为 ZIP
   - 创建 Release 并上传两个附件

---

## OCR 依赖说明

⚠️ **重要**：OCR 功能需要系统级依赖。

- Python 依赖 `pytesseract` 已通过 Poetry 安装
- **但必须单独安装 Tesseract OCR 引擎**：
  - **Windows**: 下载安装包并确保 `tesseract.exe` 在系统 PATH 中
  - **macOS**: `brew install tesseract`
  - **Linux**: `sudo apt-get install tesseract-ocr`

**行为说明**：
- 若未安装 Tesseract，应用仍可运行，但 OCR 日期提取会失败，自动回退到手动输入/预测日期模式。

---

## 版本管理

发布前必须确保以下两处版本号一致：

| 文件 | 字段 | 示例 |
|------|------|------|
| `pyproject.toml` | `[project].version` | `"0.1.0"` |
| `chroniclemap/__init__.py` | `__version__` | `"0.1.0"` |

**自动化检查**：GitHub Actions 会在发布时校验 `git tag` 与代码内版本号是否一致，不一致将自动失败。

**版本 bump 快捷方式**：
```powershell
# 使用 poetry 自动更新版本号（会自动修改 pyproject.toml）
poetry version patch   # 0.1.0 -> 0.1.1
poetry version minor   # 0.1.0 -> 0.2.0
poetry version major   # 0.1.0 -> 1.0.0

# 然后记得同步修改 __init__.py 中的 __version__
```

---

## 故障排除

**Q: 打包后图标不显示？**  
A: 确保 `--icon` 路径正确，且为 `.ico` 格式（Windows）。

**Q: 运行时提示缺少 DLL？**  
A: 尝试添加 `--hidden-import` 对应缺失的库。

**Q: GitHub Actions 发布失败？**  
A: 检查版本号是否三处一致（tag、pyproject.toml、__init__.py）。

---

## 许可证

[MIT](LICENSE)
```
