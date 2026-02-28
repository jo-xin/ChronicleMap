下面是两次对话历史的拼接
【【【【【【【【【【【【【【【【【【【【【【

项目回顾（到目前为止）

已完成的核心能力

核心模型与时间系统
GameDate（支持广泛年份、无闰年模式）
Campaign / Snapshot / Ruler / RankPeriod 等模型完善，含序列化反序列化
TemporalEngine 支持播放、跳转、按滤镜取快照
参考：models.py、engine.py
存储与导入
Campaign 建立、加载、保存
导入截图写入 maps、生成 thumbnails、写 metadata
OCR 识别日期（可选）已在导入链路打通
新增截图删除：删 metadata + 删 maps/thumbnails 文件
参考：manager.py、import_widget.py
GUI 主流程
Campaign 管理页、详情页、导入页、播放器页都可用
播放页支持手动输入日期跳转
右侧 campaign note 编辑并保存
默认导入间隔即时保存
参考：campaign_manager.py、campaign_detail.py、player_window.py
帝王系统（已进入可用阶段）
帝王创建/编辑/复制/删除
生卒、在位、玩家扮演时期、rank periods 可编辑
排序规则按玩家扮演开始时间（空值在前），操作后自动重排+保存
肖像支持：本地选择、剪贴板粘贴、移除、替换
肖像无引用自动清理（替换/删除头像/删 ruler）
肖像边框颜色按最高 rank
ruler timeline（不可拖动）已绘制：显示“谁在扮演 + rank 颜色段 + 当前时间竖线”
参考：player_window.py
质量状态
测试持续通过，当前 36 passed
当前阶段判断
你现在已经不再是“架构草案”阶段，而是可运行的 GUI MVP + 叙事层初版。
换句话说：主工作流可跑通，核心数据模型稳定，正在从“能用”走向“好用”。


# 高层回顾（从需求到现在 — 摘要）

你最初的需求（我已完整理解并记录）是做一个 *ChronicleMap（编年史地图）* 应用，用于保存并回放 Paradox 风格大地图随时间变化的截图（多滤镜、多存档、日精度时间轴、OCR 自动识别截图日期、图像对齐以减少抖动、叙事性元数据如帝王/谥号/传记等）。你希望：

* 每张截图关联游戏内日期（**日级 YYYY-MM-DD**）和 **滤镜类型**（比如政治/宗教/文化/realms/faith 等）。
* 存档按目录组织：`Campaign/maps/<Filter>/<YYYY-MM-DD>.png`，并配有 `metadata.json` 索引。
* 支持剪贴板粘贴、批量导入、默认上传周期（可配置）、以及 OCR 自动解析截图内的日期（可配置 ROI、模组/分辨率模板）。
* 播放器要有可缩放的时间轴、滤镜热切换、记忆播放速度与上次位置、以及帝王分段轨与等级配色（叙事层）。
* 后期可导出 MP4/GIF、打包为 exe（Windows），并在 CI 中做检查与构建。

我们把这套需求分阶段实现：先做需求分析 → 架构设计 → 再分模块实现（core models → storage → vision OCR → temporal engine → GUI → 打包）。目前已经实现并验证了以下内容。

# 我们现已实现 / 验证的核心功能（按模块）

**基础与工具链**

* 使用 Poetry 管理虚拟环境与依赖；项目可用 `poetry install`，用 `poetry run` 执行。
* 本地代码风格钩子：`.pre-commit-config.yaml`（black/isort/ruff）已配置并启用。
* CI：`.github/workflows/ci.yml`（GitHub Actions）已配置，在远端自动运行 pre-commit + pytest 并已通过一次 run。实体： GitHub

**核心数据模型**

* `chroniclemap/core/models.py`：完整 dataclass 实现，包括 `Campaign`、`Snapshot`、`Ruler`、`RankPeriod`、`AlignInfo`、`CampaignConfig`，并包含序列化/反序列化方法与日期解析工具。
* 单元测试 `tests/test_models.py` 通过。

**存储（Storage）**

* `chroniclemap/storage/manager.py`：实现原子写入 metadata、创建 campaign 文件夹结构、导入图片（按 filter + date 命名、避免覆盖）、生成缩略图（Pillow）。
* 新增 `StorageManager` 类，封装基础函数，方便 UI/测试注入与 mock。
* 单元测试 `tests/test_storage.py`、`tests/test_storage_ocr.py` 通过。

**时间轴引擎（Temporal）**

* `chroniclemap/temporal/engine.py`：headless 的 `TemporalEngine`，支持 play/pause/seek/tick（以 `days/sec` 为单位），并提供 `get_snapshot_for`、`next_snapshot_after` 与 `step_to_next_snapshot`。
* 已加入 CK3 风格的“**无闰年**”开关（`ignore_leap_years=True` 默认），并实现专门的无闰年 ordinal 算法。
* 单元测试 `tests/test_temporal.py` 通过。

**OCR（Vision）**

* `chroniclemap/vision/ocr.py`：实现了可插拔的 OCR Provider 框架：

  * `MockOCRProvider`（先尝试从文件名提取日期；在可用时回退到 pytesseract）
  * `TesseractOCRProvider`（基于 `pytesseract`，包含 ROI 计算、预处理（灰度/放大/滤波））
  * `compute_roi()`：支持 absolute ROI、relative(比例) ROI、模板（按分辨率匹配），并设有“右下四分之一”回退策略。
* OCR 集成：`import_image_into_campaign` 现在接受可选 `ocr_provider`、`ocr_roi_spec` 与 `ocr_template_key` 参数；若未给出 `date_str`，会优先尝试 OCR 自动解析日期。
* 测试覆盖：`tests/test_ocr_roi.py`、`tests/test_ocr_tesseract_integration.py`（如果环境中安装了 tesseract + pytesseract 则运行）、以及 `tests/test_storage_ocr.py`（Mock OCR）通过。

**其他**

* basic tests 与 CI 流程在 GitHub Actions 中成功运行（pre-commit + pytest）。
* 你已在本地用 VSCode / PyCharm 开发并使用 pre-commit 钩子（commit 时自动格式化/检查），行为正常。

# 已新增/修改的关键文件（当前项目中）

```
pyproject.toml
README.md
.gitignore
.pre-commit-config.yaml
.github/workflows/ci.yml

chroniclemap/
  __init__.py
  core/
    __init__.py
    models.py
  storage/
    manager.py        # 包含 StorageManager 与导入/保存函数
  temporal/
    engine.py         # TemporalEngine（含 ignore_leap_years 支持）
  vision/
    ocr.py            # OCR providers (Mock, Tesseract), compute_roi
  # 未来：vision/align.py, gui/* 等

tests/
  test_models.py
  test_storage.py
  test_temporal.py
  test_ocr.py
  test_ocr_roi.py
  test_storage_ocr.py
  test_ocr_tesseract_integration.py  # skip unless pytesseract available
```

# 如何运行（常用命令）

（假设你在项目根并已用 `poetry install` 安装依赖）

* 进入 poetry shell 或用 `poetry run`：

  ```powershell
  poetry shell
  # 或者
  poetry run python -V
  ```

* 运行全部测试：

  ```powershell
  poetry run pytest -q
  ```

* 把本地变更 commit（pre-commit 会自动触发）：

  ```powershell
  git add .
  git commit -m "feat: ... "
  git push
  ```

* 运行程序（将来当你实现了入口脚本 `run_app.py`）：

  ```powershell
  poetry run python run_app.py
  ```

  （注：目前我们尚未完成 GUI 程序入口；这是将来约定的运行方式）

# 技术栈（已使用 / 推荐）

* 语言：Python 3.11（推荐）
* 依赖管理：Poetry（`pyproject.toml`）
* GUI（后期推荐）：PySide6 或 PyQt（二选一）
* 图像处理：Pillow（缩略图、预处理）；OpenCV（更高级的对齐和特征匹配）
* OCR：Tesseract OCR engine + `pytesseract` Python 绑定
* 打包（后期）：PyInstaller（可在 GitHub Actions 上构建 exe）
* 编辑器 / IDE：Visual Studio Code、PyCharm
* 代码质量：`black` / `isort` / `ruff` 通过 `.pre-commit-config.yaml` 管理（pre-commit）
* CI：GitHub Actions（`.github/workflows/ci.yml`）

> 说明：上面实体名只在首次提及时用 entity 包裹（便于点击查看如 GitHub、Poetry 等），之后以普通文本引用。

# 已完成到的里程碑（对应我之前给你的分步计划）

* [x] 项目脚手架与依赖配置（pyproject, poetry）
* [x] Core 数据模型（Campaign/Snapshot/Ruler）与序列化
* [x] Storage manager（导入图片、写 metadata、缩略图）
* [x] Temporal 引擎（含 CK3 无闰年模式）
* [x] OCR 架构（Mock + TesseractProvider + ROI 模板）
* [x] 单元测试覆盖（models/storage/temporal/ocr）
* [x] pre-commit + CI 集成（GitHub Actions）

# 下一步建议（短期 / 中期 / 长期）

**短期（现在可马上做）**

1. 把 OCR pipeline 的 CK3 默认 ROI 与预处理参数加入 `Global_Settings.json` 并在 UI/StorageManager 中暴露（方便用户在 GUI 里微调模板）。
2. 把 StorageManager 的 `import_image` 在导入后自动运行 alignment（简单 translation）并把结果写入 `Snapshot.align`。
3. 开始实现 GUI 原型（PySide6）：最小化界面能创建/加载 campaign、导入图片（可粘贴）、播放/暂停/seek、滤镜按钮、帝王轨显示。

**中期**
4. 完善 alignment（ORB/SIFT 特征匹配 + 仿射校正），降低播放时画面抖动；支持对图像裁剪掉 UI 边框。
5. Timeline 高级交互：缩放刻度、帝王分段样式、hover 显示 tooltip（谥号/全名）。
6. 增强 OCR：模板管理 UI、多语言支持（自动选择 `chi_sim+eng` 等），低置信度时弹出人工确认对话。

**长期**
7. 导出 MP4/GIF（基于渲染帧把图片合成为视频）
8. 打包为 Windows exe（`PyInstaller`），并在 GitHub Actions 编写 `release.yml` 构建 workflow，上传为 Release Artifact。
9. 性能优化（大量图片时的缓存、缩略图索引、内存管理）。



































你好，我接下来要设计一个复杂的python项目，需要你的帮助。以下是我之前的对话记录，请你阅读理解，谢谢你！《《《《《《我在玩一些p社游戏，涉及到大地图的变化，可惜没有什么机制可以保存下来。我现在需要一个机制，我会上传游戏内某一时刻地图截图，可能一年一次，或者更频繁，甚至不按照周期但是指明了日期。系统需要即时保留这些截图，并有组织的管理在本地，我可以随时像播放视频一样看这些截图，把这些截图按照恒定但是可以设置的时间流速播放。我说的不清楚，只要你明白就好，你当然可以有别的组织表述语言的方式。此外，游戏内有不同的滤镜，比如说一个滤镜显示国界，一个显示信仰地图之类的。只要我之前同时给这些滤镜上传了截图，系统就允许我在播放时随时切换滤镜。我知道这是个很复杂的项目，所以我们按照软件系统设计的传统流程，先进行需求分析，需求整理的差不多之后再设计架构，架构设计清楚了之后再具体开始编程，目前我们只要分析、整理需求就好。我知道给你的只是必要的需求，当然还有很多其他的需求也是需要的，但是我没有说全。比如说条理清晰的本地文件管理，比如说允许保存多个存档，比如说允许直接从我的剪切板获得截图作为上传并保存，允许设置不同的播放速度并记忆等等。 

你好！这个想法非常棒。作为一名 P 社（Paradox Interactive）玩家，我完全理解这种需求。无论是《欧陆风云4》、《十字军之王3》还是《群星》，看着自己的领土像墨水一样在地图上扩张，确实是游戏最有成就感的时刻之一。

你提出的这个“历史地图回放器（History Map Replayer）”项目，核心难点不在于单一的技术，而在于多维度的同步（时间 + 滤镜）以及大量图片资产的高效组织。

按照软件工程的传统流程，我们先进行需求分析（Requirement Analysis）。我将你的想法整理并扩展为以下几个维度：

1. 核心功能需求 (Functional Requirements)
A. 数据录入与管理
多存档支持 (Multi-Campaign Support)： 系统可以创建不同的“项目”或“存档”，例如“大明-1444”或“瑞典-成就局”。

灵活上传： * 支持从剪贴板直接粘贴（Ctrl+V）。

支持批量导入本地文件夹中的截图。

元数据标注： 每一张图片需要关联两个核心属性：游戏内日期 (Date) 和 地图滤镜类型 (Filter Type，如：政治、宗教、文化)。

文件系统自动化： 在本地建立清晰的目录结构（例如：Campaign_Name/Date/Filter_Type.png），确保数据透明且易于迁移。

B. 播放与渲染引擎
时间轴同步播放： 这是最核心的功能。系统需要将离散日期的截图线性化。如果 1450 年有截图，1452 年也有，系统要在播放时自动计算它们在时间轴上的位置。

多滤镜实时切换： 播放过程中，用户点击“宗教”按钮，画面立即切换到对应日期的宗教地图，但播放进度（时间点）保持不变。

动态流速控制： 允许设置每秒跳过多少天/月/年，或者简单的设置 FPS（每秒帧数）。

C. 交互与 UI
时间轴进度条： 允许用户拖动进度条跳转到特定年份。

记忆功能： 系统记录每个存档最后一次播放到的位置和用户偏好的播放速度。

2. 逻辑挑战与待解决细节 (Business Logic Challenges)
在需求分析阶段，我们需要预判一些“坑”：

数据缺失处理： 如果 1450 年我存了“政治地图”和“宗教地图”，但 1451 年我只存了“政治地图”。当用户在播放 1451 年时切换到“宗教”滤镜，系统该显示什么？（建议：显示最近的一张历史截图或留白）。

日期解析： P 社游戏的日期格式各异（如：1444.11.11）。系统需要一个强大的解析器，将这些字符串转化为可计算的时间戳。

图像对齐： 如果玩家在截图时缩放程度不一，播放时会产生严重的“晃动”。我们是否需要考虑基础的图像裁剪或对齐功能？

3. 需求整理表 (SRS Outline)
为了方便后续设计架构，我将需求汇总如下：

模块	关键功能点	优先级
项目管理	存档新建/删除、路径自定义、配置记忆	高
数据采集	剪贴板监听、日期手动/自动输入、滤镜标签分类	高
播放控制	播放/暂停、倍速调节、时间轴跳转、滤镜热切换	极高
存储策略	自动命名、目录分级、缩略图生成（优化加载速度）	中
导出功能	将某段历史导出为 MP4 或 GIF 视频	低（后期）
4. 下一步：架构设想 (Preview)
在进入正式架构设计前，我建议采用 Python + PyQt/PySide (GUI) + SQLite/JSON (Metadata) 的技术栈。

存储： 既然你要求“条理清晰的本地管理”，我们可以直接利用文件夹层级作为数据库的一部分，再配合一个轻量级的 metadata.json 来记录时间轴顺序。

渲染： 使用 OpenCV 或 Pillow 处理图像，通过 QTimer 来驱动播放循环。

这是我目前基于你的描述整理的需求分析。你看一下是否有遗漏？或者有哪些细节（比如某个特定滤镜的特殊需求）需要补充？

如果你觉得这份分析已经勾勒出了你想要的系统原型，我们可以开始讨论架构设计（包括文件夹结构设计和核心类的定义）。你想先聊聊数据怎么存，还是 UI 怎么画？

谢谢你，我又想到了下面这些需求，请你理解、分析、整理。详细点好，不怕字多，但是要条例，踏实：



“”“

日期精确到日，不管是记录还是播放。进度条要可以缩放。比如说当前进度条涵盖10年，或者10个月。比如说进度条分10个刻度，或者怎样的。



本地目录结构最好是一个存档一个文件夹，存档下每个滤镜一个文件夹，滤镜下直接放图片即可，图片名字就是日期



至于上传，我可以随时约定默认上传周期，比如说一个月一上传，或者半年或者一年，可以具体写。这样当我点击一个专门的过渡到下一个时间点的按钮后，下次默认上传的图片就是上次上传加上周期得到的时间。当然时间也可以手动设置，手动选择输入。之前我是这么想的，但既然你提到了解析日期，也许确实，我们可以通过OCR自动识别截图中的日期信息。这也是相当大胆的设计。



以及你提到的，截图的处理。我能保证截图时缩放比例一致，但是可能会存在平移。以及画面的外边框在现实时的裁剪。所以系统还要能对图片的主体地图进行识别，并且在呈现时平移确保主体位置不变。当然这些是相当细节的设计了。



其他的，也是一个核心功能：涉及到文本。



我希望有地方，能让我写一些属于全局的文本，当然可以有多个；也可以具体的为每个存档写文本；甚至能为每个帝王写。



这就涉及到另一个新的功能，按帝王的分段。我的国家根据不同的国家，应当分不同的阶段。这些可以在播放时体现在进度条下面的一个新的条，每一个帝王之间是分开的，代表不同的统治。十字军之王为不同的统治者设置了不同的等级：“霸权，帝国，王国，公国，伯国，以及无地统治者。”我希望不同的等级也体现在那个条上面，或许是颜色变化，或许是花纹，或许是边框装饰之类的。或者说自定义设置条的颜色之类的。也要考虑到一个帝王可能统治的前半期是国王，后面是皇帝这样的。当然，不同的分段下面要有标识是谁在统治。我希望在每次加入一个帝王的记录之后，给他写传记，这个自然可以放在前面我们说的给帝王的文本那里；此外，我还可以起谥号。我希望显示在帝王进度条下面的就是谥号，鼠标悬浮在进度条上面会全名之类的。当然，这些属于较为后期、细节的机制了

”“”

太棒了！你的这些补充不仅极大地丰富了系统的人文深度（叙事性），还对UI交互和算法处理提出了非常具体且专业的要求。

现在的需求已经从一个简单的“图片查看器”进化为了一个**“高度定制化的历史档案库”**。针对你补充的细节，我重新整理并深化了需求分析方案。

1. 时间轴与精密进度控制 (Temporal Precision)
全精度时间轴： 系统内部逻辑以“天”为最小时间单位（YYYY-MM-DD）。

缩放式进度条 (Zoomable Timeline)：

动态视口： 用户可以通过鼠标滚轮或UI滑块，在“世纪/十年/年/月”不同精度间切换。

刻度算法： 进度条需要根据当前缩放级别动态生成刻度线（例如：缩放到“月”级别时，显示每一天的细分刻度）。

步进机制：

支持“跳转至下一张截图”和“按照设定周期跳转”。

智能日期预测： 当用户设定了“半年上传一次”，点击“下一个时间点”按钮时，系统自动填充 LastDate + 180 Days，用户只需确认或微调。

2. 多维度数据存储结构 (Storage & Data Architecture)
为了保证你要求的“条理清晰”，我们将采用**“文件目录 + 索引元数据”**的双重结构：

物理路径：

Plaintext
/Root
  /Campaign_1 (存档名)
    /metadata.json (核心索引：记录所有图片路径、日期、滤镜、帝王信息)
    /Political_Map (政治地图滤镜文件夹)
       /1444-11-11.png
       /1450-01-01.png
    /Religous_Map (宗教地图滤镜文件夹)
       /1444-11-11.png
    /Biographies (存放文本说明，或整合进json)
OCR 自动识别 (可选/进阶)：

集成轻量级 OCR（如 Tesseract 或 PaddleOCR）。

针对不同游戏（EU4, CK3, HOI4）预设日期坐标框。

逻辑： 截图粘贴后，系统扫描右上角/左上角区域，尝试解析日期字符串，若解析成功则自动填充日期，减少手动输入。

3. 图像对齐与视觉稳定性 (CV & Alignment)
这是提升“大片感”的关键。即使缩放一致，平移偏差也会导致播放时画面跳动。

特征点匹配 (Feature Matching)： 利用 OpenCV 算法（如 SIFT 或 ORB）识别地图上的固定地理特征（如海岸线、不动的山脉）。

自动平移修正： 以第一张截图或“底图”为基准，后续图片自动计算偏移量（Offset），并在显示时进行补偿平移。

智能裁剪： 自动识别并裁剪掉游戏的 UI 边框（如顶栏、小地图框），仅保留纯净的地图主体。

4. 叙事与文本管理系统 (Narrative & Lore)
这是你最核心的新增需求，我们需要构建一个**“层次化文本系统”**：

三级文本结构：

全局笔记 (Global)： 软件层面的通用备注。

存档笔记 (Campaign-level)： 记录本局游戏的大背景、目标（如“这次我要重建罗马”）。

阶段/帝王传记 (Ruler-level)： 与特定时间段绑定的深度文本。

帝王/阶段分段条 (Ruler Segmented Bar)：

可视化呈现： 在主时间轴下方增加一个平行的轨道。

等级视觉化： * 颜色编码： 皇帝（紫/金）、国王（红）、公爵（蓝）等。

装饰元素： 比如皇帝级别有精美的金色边框，伯爵则是简单的细线。

身份变迁： 允许在同一个帝王的时间轴内标记“头衔提升”事件，反映从国王到皇帝的变化。

命名与谥号机制：

全名 (Full Name)： 记录在后台，悬浮查看。

展示名 (Display Name)： 优先显示“谥号”（如“伟大的”、“长弓王”），显示在进度条分段的中心。

5. 逻辑整合：帝王与地图的关联
这是实现你想法的算法逻辑：

用户定义一个帝王的 [开始日期, 结束日期]。

系统自动在主时间轴上切分出这段区间。

播放器在运行到该区间时，UI 自动弹框显示该帝王的传记预览，或者在侧边栏刷新他的资料。

需求整理总结表 (Updated SRS)
维度	功能点	详细描述
时间控制	全精度/可缩放时间轴	日级精度，支持世纪到月份的视口缩放
智能采集	OCR与步进预测	自动识别截图日期，支持按固定周期自动推算下次日期
视觉优化	图像对齐与去边框	基于特征点匹配的平移修正，确保地图播放不晃动
存储管理	滤镜目录结构	存档 -> 滤镜 -> 日期命名的图片，物理结构极其透明
叙事逻辑	帝王/阶段轨道	独立于时间轴的视觉条，支持等级、花纹、谥号、传记
文本交互	多级富文本	全局、存档、帝王三级文本，支持悬浮显示全名
下一步建议
既然需求已经非常清晰且具有挑战性，我建议我们进入架构设计阶段。

在架构设计中，我们需要重点讨论以下两个模型：

数据模型 (Data Model)： 如何在 Python 中定义 Campaign, Ruler, Snapshot 这几个类，以及它们如何互相引用。

视图模型 (View Model)： 如何设计那个复杂的、带有多条轨道（时间刻度轨道、帝王轨道、事件轨道）的 UI 界面。

你是希望先看一眼这个系统的“数据逻辑蓝图”（代码怎么组织），还是先聊聊“界面布局草图”（UI 怎么长）？

谢谢你，接下来让我们进入架构设计阶段。我们要从大到小的逻辑清晰的讨论。首先我们使用pyqt或者其他的库实现的程序。首先有全局都用到的，比如说公共常量，各种对象的类之类的；要有storage模块，负责文件和类的互相转换，包括截图、元数据，以及通用、习惯配置的存储【这里要插入介绍一下，之前没介绍，比如说播放速度，比如说头衔等级的配色之类的。这个也要有层级，比如说全局配置，存档配置，两者都有的配置自然是存档配置优先】；要有图像模块，从图像的输入就开始负责。比如说输入图像，根据推断以及OCR识别图像时间【这里也插入一下，可能输入的图像里面显示的是年号纪年，这个机制也要有，具体的之后再扩展】，并标明图像的滤镜之类的信息创建图片类，图像处理包括识别对其，并保存到本地，并且妥善管理组装；还有元数据模块，负责所有的元数据，包括全局的文本，存档文本，以及每个帝王都有自己的元数据，包括玩家扮演其游玩的期间，其作为不同头衔等级的时间段，名字、谥号、年号、传记、笔记之类的；然后需要一个类似编年史的，或者模拟世界播放的模块，根据现在播放到不同时间可以知道要不要获取新的一张图片，以及不同滤镜的处理，以及其他的元数据等的详细信息。总之，其将一张张静态的图片和元数据变成动态的可播放的“视频”（我不太会表达，要麻烦你总结、起名字了）。以及之后我们说可以一边播放一边上传，就不搞了现在要不就上传截图，要不就播放。当然元数据可以随时编辑；还有GUI模块，就不多说了；还有总的，或者启动的模块，比如说启动程序，选择创建不同的存档之类的。我只是大概说个思想，具体如何设定什么的就靠你了，谢谢你。越详细越好。

你好！这个架构思路非常扎实。你已经跳出了单纯“写代码”的层面，开始从模块化和数据流的角度思考一个复杂系统的运作。

我将这个项目命名为 “ChronicleMap (编年史地图)”。为了实现你描述的功能，我们将采用典型的分层架构，并引入一个**“配置覆盖机制”**来处理全局与存档配置的关系。

以下是详细的架构设计：

1. 系统逻辑架构图
2. 核心模块详细设计
A. Core (核心基础模块)
这是项目的地基，定义了所有模块通用的语言。

Constants (constants.py): 定义支持的滤镜类型、颜色常量、默认播放速度、OCR 预设坐标等。

Data Models (models.py):

Snapshot: 包含日期、图片路径、滤镜类型、对齐偏移量。

Ruler: 包含统治区间、全名、谥号、年号、头衔等级变化历史、传记、笔记。

Campaign: 存档实体，包含快照列表、帝王列表、存档级文本。

B. Storage (存储与序列化模块)
负责将 Python 对象转化为磁盘上的文件，反之亦然。

Config Manager: 采用 “层级覆盖机制”。

读取顺序：Default Config -> Global Config (user_settings.json) -> Campaign Config (campaign_settings.json)。

如果存档配置中定义了 playback_speed，则忽略全局配置。

Asset Serializer: 负责将 Campaign 类保存为 metadata.json，并管理图片的物理路径。

C. Vision (图像与 OCR 模块)
负责把原始截图变成“合格”的数据。

Date Extractor: * 集成 OCR（如 PaddleOCR）。

纪年转换器 (Calendar Converter): 这是一个亮点功能。如果识别到“贞观三年”，系统通过一个映射表或逻辑算法将其转换为 ISO 日期 0629-01-01。

Aligner (图像对齐器): * 利用 OpenCV 的特征匹配算法（如 ORB），寻找地图中不动的地理标志。

计算出相对于“基准图”的偏移量

(Δx,Δy)
并记录在 Snapshot 的元数据中。

Clipper (裁剪器): 根据预设的模板剔除游戏 UI 边框。

D. Narrative (元数据与叙事模块)
管理文字和历史逻辑。

Text Store: 管理全局、存档、帝王三级文本。

Timeline Logic: 处理帝王在不同时间点头衔的变化（例如：1444-1450 为国王，1450-1460 为皇帝）。

Epithet Manager: 专门负责全名与谥号的切换逻辑。

E. Temporal Engine (时间轴播放引擎)
这是你说的“模拟世界播放”的核心。

Ticker (计时器): 一个高精度的虚拟时钟，根据 playback_speed 推进当前时间。

State Resolver: * 根据“当前时间”和“当前滤镜”，从 Snapshot 库中检索最匹配的图片。

补帧策略： 如果当前日期没有对应滤镜的图，它负责决定是显示上一张还是留白。

元数据同步： 告诉 UI 层：现在是哪个帝王在位，应该显示什么背景音乐或文本。

F. GUI (用户界面模块)
Main Window: 整合播放控制栏、滤镜切换栏、时间轴轨道。

Canvas: 使用 QGraphicsView 高效渲染图像，并应用对齐偏移量。

Timeline Widget: 一个高度定制的控件，支持滚轮缩放，包含时间刻度轨和帝王勋章轨。

3. 本地存储结构预览
为了实现你要求的“条例、踏实”，文件夹结构建议如下：

Plaintext
/ChronicleMap_Data
  /Global_Settings.json         <-- 全局配置、配色方案、OCR 模板
  /Global_Notes.md              <-- 全局文本内容
  /Campaigns
    /My_Rome_Run
      /metadata.json            <-- 存档核心元数据（帝王信息、图片索引）
      /campaign_settings.json   <-- 存档独有配置（覆盖全局）
      /notes.md                 <-- 存档感言
      /maps
        /Political
          /1444-11-11.png
          /1453-05-29.png
        /Religous
          /1444-11-11.png
      /thumbnails               <-- 自动生成的缩略图，加速 UI 加载
4. 关键技术方案：如何把图片变成“视频”
你担心的“表达不清楚”其实在架构上很明确。我们不需要真正生成一个 .mp4，而是在 GUI 中实现 “即时合成渲染”：

逻辑帧： 引擎每秒计算 N 个逻辑日期。

渲染帧： * 找到最接近该日期的图片。

在内存中应用 Aligner 计算出的偏移。

如果是切换滤镜，使用平滑的渐变（Opacity Animation）来实现图片重叠切换。

UI 联动： 当逻辑日期跳过帝王更替点时，下方的帝王进度条高亮更新。

5. 补充设计：头衔配色方案
在全局配置中，我们会定义一个 RankTheme 对象：

JSON
{
  "RankTheme": {
    "Empire":  {"color": "#FFD700", "border": "golden_double", "z_index": 5},
    "Kingdom": {"color": "#FF0000", "border": "silver_bold", "z_index": 4},
    "Duchy":   {"color": "#1E90FF", "border": "simple", "z_index": 3}
  }
}
这样你在 UI 的进度条上，就能根据头衔等级自动渲染出你想要的“繁复花纹”或颜色。

这是初步的架构方案。它涵盖了从底层存储、图像处理到顶层渲染的完整链路。

这个架构最吸引我的部分是它的扩展性：即便未来你想加入“导出 MP4”的功能，我们也只需要在引擎层增加一个视频编码模块，而不必改动底层逻辑。》》》》》》
】】】】】】】】】】】】】】】】】】】】】