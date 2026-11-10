# 历史版本：任务扩展版（2026-10-14）

本目录是从项目根目录**整体归档**下来的旧源码，不是复制品 —— 根目录里那些文件已经被
25936576.1 取代，原件都搬到了这里，没有被删除。

- 归档日期：2026-10-15（按 AGENTS.md 第 2 条「测试通过后再合并文件夹」执行）
- 目录名按 AGENTS.md 第 5 条以 Steam 号码开头：**3337140**
- 对应游戏：Steam App ID **3337140**，支持构建 **25479909** 与 **25936576**
- 内部版本号：**无**。这一版程序没有写入内部版本号，因此按「来源 + 构建号 + 文件哈希」登记，
  不为其编造版本号。

## 功能

资源 / 耐心 / 权威修改、战士快速移动、远征日期刷新、探索与建设队伍、随机任务扩展
（原生 `AfterIncTaskExtension.dll` 挂 `LevelBuilder` 生成链）、队伍数量保持。
战士部分只有 `经验 +1`（调 `MovingSoldier.IncrementLevel`）、`武器 +0.25`、`小队 +0.25`；
界面为 600×820 单页长列表。

**与 25936576.1 的关键差别**：这一版的「经验 +1」只增加经验值，**不会产生游戏里的升级图标**。
25936576.1 已改为调用游戏原生升级事件（`BaseGameEvents.TryFire` + `GameEvents.SoldierUpgrade`），
点击后在所选战士所在区域生成可点击的原生升级图标。

## 归档文件哈希（sha256 前 16 位）

| 文件 | 大小 | sha256[:16] |
| --- | --- | --- |
| `trainer_gui.py` | 51,794 B | `8fe76945f2fcfd3d` |
| `teams.py` | 6,532 B | `5c0f7ab5073402d4` |
| `task_extension.py` | 14,973 B | `b3e6a9889a13bd7c` |
| `game_build.py` | 2,062 B | `36a6237c31765c27` |
| `memory_scan.py` | 52,386 B | `70317b55ef064c8b` |
| `expedition.py` | 4,182 B | `e23c1f4151138a22` |
| `AfterIncRevivalTrainer_CN.spec` | 442 B | `2c49cc3647806809` |
| `native/AfterIncTaskExtension.dll` | 3,584 B | `05ded15f756f13f6` |
| `native/task_extension.cpp` | 3,741 B | `5c8582748e2f571a` |
| `native/build.cmd` | 265 B | `3f6d958f371a79a1` |
| `tests/test_auto_rebind.py` | — | `f82b4e7acd506d2e` |
| `tests/test_expedition.py` | — | `6c5f059d167beb92` |
| `tests/test_task_builds.py` | — | `2d7f2b53609d7b2a` |
| `tests/test_task_extension.py` | — | `39e73ac8d15456cd` |
| `tests/test_teams.py` | — | `d9a6def32b40039c` |
| `tests/test_trainer_connection.py` | — | `fd1d8ed1d53fc91a` |
| `tests/test_trainer_fast_move.py` | — | `f340994680752805` |

（`game_build.py`、`memory_scan.py`、`expedition.py` 与 25936576.1 的完全相同，属于未改动的公共文件。）

## 对应的打包产物

这一版打出来的 EXE 在 `dist/` 下，没有一起归档（`dist` 未被 git 跟踪，且需要保留运行中的程序）：

| 位置 | 说明 | sha256[:16] |
| --- | --- | --- |
| `dist/build_25936576_tasks/AfterIncRevivalTrainer_CN.exe` | 本版本的 25936576 打包 | `6b3030c7b1ab4658` |
| `dist/AfterIncRevivalTrainer_CN.exe` | 同一个文件 | `6b3030c7b1ab4658` |
| `dist/build_25936576/AfterIncRevivalTrainer_CN.exe` | 25936576 适配过程中的中间包 | `5415ee4b04e5f5d1` |
| `dist/1` ~ `dist/4` | 更早的 24931318 / 25479909 各功能阶段 | 见根 `README.md` 末尾附录 |

另外 `soldier_upgrade_work/` 是 2026-10-14 从本版本复制出的**战士升级专项开发版**（也未编内部版本号），
它同样已被 25936576.1 取代，登记见 `versions/README.md`。

## 如何回退

把本目录的 `*.py`、`AfterIncRevivalTrainer_CN.spec`、`native/`、`tests/` 复制回项目根目录即可，
覆盖根目录的同名文件。打包产物无需回退（`dist/` 里的旧 EXE 一直都在）。
