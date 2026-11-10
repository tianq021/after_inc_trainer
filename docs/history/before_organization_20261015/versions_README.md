# 修改器版本索引

按 AGENTS.md 第 3 条，每个版本都要留「版本号 + 功能 + 对应游戏号」。
本文件是索引，细节见各版本目录自己的 `README.md` 与 `下一步.txt`。

**统一的游戏号**：Steam App ID **3337140**。
修改器版本号规则：`<Steam 构建号>.<修改器序号>`，例如 `25936576.1`。

---

## 25936576.1 — 当前版本（已合并进项目根目录，实机验收通过）

- 版本目录（保留作版本记录与开发环境）：`versions/25936576.1_game25936576/`
- **项目根目录已是 25936576.1 的源码**（2026-10-15 按 AGENTS.md 第 2 条合并）
- 入口：`versions/25936576.1_game25936576/dist/build_25936576_1/AfterIncRevivalTrainer_CN.exe`
- 对应游戏：Steam App ID 3337140，构建 **25936576**（`game_build.py` 用 GameAssembly.dll 的精确 SHA-256 校验）
- 功能：资源 / 耐心 / 权威、战士快速移动、远征日期刷新、探索与建设队伍、随机任务扩展、队伍数量保持，
  以及本次重点 **战士升级**（"升级机会 +1"：调游戏原生升级事件，在所选战士所在区域生成可点击的原生升级图标；
  另有武器 +0.25、小队 +0.25 两个直接修改项）
- 界面：600×540，三个页签「资源 / 队伍与升级 / 远征与地图」
- 内置原生扩展 `AfterIncSoldierUpgrade.dll`：5,120 B，sha256 `c6f514f2fb9a0b1f40fe73a3c808c4ddf2a52016f3b7fe1e80e4ef021b9d70ef`
- 打包产物：22,016,304 B，sha256 `3ae1e5cec152a78835dc45c65b8237dc8a9aeee4b4dc4e1155f2fad88acd6063`
- 测试：在项目根目录 `python -m unittest discover -s tests` → 56 项通过
  （含 11 项原生用例，须用系统 Python 3.10）
- 验收：2026-10-15 实机通过，日志见 `%LOCALAPPDATA%/AfterIncTrainer/logs/soldier-result_*.json`

## 历史版本：3337140_任务扩展版_20261014（已归档）

- 目录：`versions/3337140_任务扩展版_20261014/`（从项目根目录整体归档，不是复制品）
- 对应游戏：Steam App ID **3337140**，支持构建 **25479909** 与 **25936576**
- 内部版本号：**无**，按「来源 + 构建号 + 文件哈希」登记，不编造版本号
- 功能：资源 / 耐心 / 权威、战士快速移动、远征日期刷新、探索与建设队伍、随机任务扩展、队伍数量保持；
  战士部分只有 `经验 +1`（只加经验，**不产生升级图标**）、`武器 +0.25`、`小队 +0.25`；界面 600×820
- 打包产物：`dist/build_25936576_tasks/AfterIncRevivalTrainer_CN.exe`（sha256 `6b3030c7b1ab4658`）
- 完整说明与全部文件哈希见该目录的 `README.md`

## 历史版本：soldier_upgrade_work（未编内部版本号）

- 目录：`soldier_upgrade_work/`
- 来源：2026-10-14 从「随机任务修复版」复制开发，**不替换**父目录中当时正在运行的程序
- 对应游戏：Steam App ID 3337140，构建 **25936576**
- 功能：三个战士升级项 `经验 +1`（调 `MovingSoldier.IncrementLevel`）/ `武器 +0.25` / `小队 +0.25`，
  以及队伍数量保持；窗口 600×820
- 已被 25936576.1 取代：`经验 +1` 只加经验、不会产生升级图标，25936576.1 已改为调用游戏原生升级事件
- 该版程序**没有写入内部版本号**，因此按来源 + 构建号 + 文件哈希登记，不为其编造版本号：
  - `soldier_upgrade_work/dist/AfterIncRevivalTrainer_CN.exe`：22,057,571 B，sha256 `bff69d6c1951bb2476c7c5d5586fc2b3ae530f5f1e5db014e36b322f79cd9bdb`
  - `soldier_upgrade_work/native/AfterIncSoldierUpgrade.dll`：3,584 B，sha256 `bdb1172c5cceec98ec903818691dbec9530d1264544fbfde24a6e26d7e1777f5`
  - `soldier_upgrade_work/trainer_gui.py`：49,990 B，sha256 `fad3d157565e7a8e2053b797ecdff156ccaff9159b4cbd7b69e8ec7c1a2f19fc`
- 25936576.1 里保留的同一份旧 DLL 备份：`native/AfterIncSoldierUpgrade.dll.bak-20261014-2342`（同一个哈希）

## 历史版本：更早的构建（根目录 `dist/`）

`dist/1`、`dist/2`、`dist/3`、`dist/4`、`dist/build_25936576`、`dist/build_25936576_tasks`
分别对应构建 24931318 / 25479909 / 25936576 的不同功能阶段。逐个 EXE 的取证表见根目录
`README.md` 末尾的附录。

## 合并状态

**已合并（2026-10-15）**：25936576.1 实机验收通过后，按 AGENTS.md 第 2 条执行了合并 ——
根目录原有源码（`trainer_gui.py`、`teams.py`、`task_extension.py`、`game_build.py`、
`memory_scan.py`、`expedition.py`、`AfterIncRevivalTrainer_CN.spec`、`native/`、`tests/`）
整体移入 `versions/3337140_任务扩展版_20261014/`，25936576.1 的对应文件复制到根目录。
合并后从根目录跑测试仍为 56 项通过。`dist/`、`il2cpp_dump/`、`scans/`、`tools/`、
`write_tests/`、`backups/`、`soldier_upgrade_work/`、`.git/` 未被改动。

回退方式见归档目录 README 的「如何回退」一节。
