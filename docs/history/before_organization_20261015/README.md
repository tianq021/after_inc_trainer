# 2026-10-15：战士升级（修改器版本 25936576.1）

**项目根目录现在就是 25936576.1 的源码**（2026-10-15 按 AGENTS.md 第 2 条完成合并）。
- 可直接运行：在项目根目录 `python -m unittest discover -s tests` → 56 项通过（须用系统 Python 3.10）
- 打包：`python -m PyInstaller --noconfirm --distpath dist/build_25936576_1 --workpath build/build_25936576_1 AfterIncRevivalTrainer_CN.spec`
- 已经验证过的可执行文件在 `versions/25936576.1_game25936576/dist/build_25936576_1/AfterIncRevivalTrainer_CN.exe`
- 版本目录 `versions/25936576.1_game25936576/` 保留作版本记录与开发环境（含原生测试 DLL、反汇编证据）
- 修改器版本 25936576.1；Steam App ID 3337140；游戏构建 25936576
- 功能与验收数据见 `versions/25936576.1_game25936576/README.md`；
  版本索引见 `versions/README.md`；进度与遗留项见 `下一步.txt`

被它取代的旧源码（任务扩展版，支持构建 25479909 / 25936576）已整体归档到
`versions/3337140_任务扩展版_20261014/`，该目录的 README 里有全部文件哈希与回退方法。

# 2026-10-14：适配构建 25936576

新版入口：`dist/build_25936576_tasks/AfterIncRevivalTrainer_CN.exe`，旧版入口保留。

已适配资源、耐心、权威、战士快速移动、远征日期刷新及探索/建设队伍。
使用新版 GameAssembly.dll 的精确 SHA-256 校验，更新单例、设置、远征种子和队伍类型地址。
与 25479909 的元数据对比确认上述功能涉及的字段布局一致，保留原有对象、范围和回读检查。

随机任务实验功能现已适配 25936576：更新原生函数、类型、列表追加、委托调用及地图排布地址，
保留 25479909 支持。首次添加备份时排除游戏占用的 Sentry 诊断锁文件，继续完整备份存档。

已在 25936576 地图页验证入口并配置 1 个测试任务；实际生成与关卡验收见
`build_25936576_compatibility.md`。自动测试覆盖两个构建的添加、读取、清除及写入失败回滚。

# 2026-09-30：探索与建设队伍

队伍功能新版入口：`dist/3/AfterIncRevivalTrainer_CN.exe`（旧路径 `dist/teams_update/` 已不存在；
`dist` 下各目录的真实身份见文末表格）。
进入关卡后在“探索与建设队伍”区域点击“读取数量”，分别点击“探索队伍 +1”或“建设队伍 +1”。
显示的是包含工作中队伍的总容量，每次增加一队，上限 20；暂停时可短暂继续游戏刷新显示。
本功能仅支持精确匹配的构建 25479909。每次操作重新定位当前关卡、校验管理器类型和容量表，
保存原值后写入单个整数并回读验证；不修改其他任务队列。日志保存在原日志目录。
存档、重启后的保留情况尚未验证；切关后请重新读取数量。

本次实机内存验证：探索 1→2、建设 2→3，均即时回读成功；稍后连续读取为探索 2、建设 2。
建设队伍随后减少的原因尚未确认；当时临时队伍计时器均为 0，未重复补加。
35 项自动测试通过。
实际同时执行多项探索/建设仍需在游戏中验收。旧版正在运行，故新程序单独打包，未替换旧入口。

# 2026-09-24：添加随机任务实验版

新版入口：dist/AfterIncRevivalTrainer_CN.exe。新增数量输入、添加任务、读取状态和清除本次添加。最多保留 5 个；添加后切换赛季或重新进入地图。精确支持构建 25479909，不推进日期。说明与已知限制见《随机任务实验版说明.md》。

本次三个工作目录已统一归入此项目。新版分析在 il2cpp_dump/build_25479909，工作归档在 build/task_feature_work。旧版程序保留为 `dist/1/AfterIncRevivalTrainer_CN_before_tasks.exe`。

# After Inc: Revival memory analysis helper

## 2026-09-19: 远征任务刷新

新版程序：`dist/1/AfterIncRevivalTrainer_CN_before_tasks.exe`（旧路径 `dist/expedition_update/` 已不存在）。
在“远征任务”区域点击“读取状态”，然后点击“刷新任务（推进1天）”。
每次操作将游戏远征系统的虚拟日期增加一天；返回世界地图并重新进入选关界面，
必要时切换赛季，让游戏重新生成任务卡片。“恢复真实日期”将日期偏移设回零，
不会撤销已经完成的任务或奖励。此功能不依赖关卡资源扫描，未进入定居点也能使用。

实现只修改 `GameSettings.randLevelSeeding.manualDebugFutureDays`，不修改系统时间。
每次操作均验证已加载模块对应文件的 SHA-256、两级对象类型及字段范围；
操作期间按钮禁用，写入前后复核对象状态。日志保存在原日志目录。
权限不足时使用与游戏相同的权限运行修改器。

已验证：19 项自动测试通过，当前游戏进程只读连接成功，初始日期偏移为 0。
待实机验收：推进后的任务卡片重建、进入关卡、完成记录及重启后的偏移状态。
本次没有自动改变正在运行的游戏日期；首次使用请在选关界面操作。

This folder contains build-specific memory analysis helpers used to locate the
values needed by a small offline trainer.

The GUI now connects through a native, process-stable root recovered from the
supported `GameAssembly.dll`.  Every 500 ms it follows `SteamManager.s_instance
-> launch -> scenarioLauncher -> GameController -> GlobalSimulation ->
WorldSettlementSimulator`, then validates the complete bidirectional world
cycle and every production type before reading or writing.  `SetUpGame()`
publishes the current `GameController` to that root after each scene load, so a
save reload, level change, or process restart normally requires only a handful
of pointer reads and no private-memory search.

The slow full structural locator is no longer started automatically during a
scene transition.  While the stable root is temporarily unpublished, the GUI
waits and retries; reads, writes, and continuous locks remain paused.  The
**完整扫描重新定位** button retains the full locator as a manual diagnostic
fallback for the exact supported build.

The GUI also provides **战士快速移动** for player-controlled soldiers.  It
follows the active world's `MovingSoldierManager`, validates the managed list
and each soldier/design back-reference, then reduces only an active journey
whose timer is greater than one to exactly `1.0`.  The next normal game step
still executes the game's own arrival callback.  It does not enumerate or
write enemy-unit collections, and it never writes `0` to bypass arrival logic.

For the complete project state, scan results, continuation procedure, and the
correction that the top-left value is manpower rather than stamina, read
`After_Inc_修改器项目进度与续作手册.md` first.

The `initial`, `refine`, `inspect`, and `locate-settlement` commands request only
`PROCESS_QUERY_INFORMATION` and `PROCESS_VM_READ`.

The separate `write-float32` command performs one checked float write only when
the current value exactly matches `--expected` and the exact confirmation phrase
is supplied. It logs the old/new value and a restore command. It does not modify
game files.

`write-int32` provides the same old-value check and logging for one integer.
`write-float32-batch` preflights every item before writing and rolls back already
written items if a later write or verification fails.

For Steam build `24931318`, IL2CPP metadata version 31 identifies
`WorldSettlementSimulator` and `StandaloneProduction._total`. The following
command performs a read-only structural search and verifies all production
objects by their `ResourceType` values:

```powershell
python memory_scan.py locate-settlement `
  --process "After Inc. Revival.exe" `
  --output structure_scans\build_24931318_settlement.json
```

The first successful run found exactly one settlement object. Absolute object
addresses remain valid only for the current game process; the packaged GUI does
not reuse them and instead resolves the current object from the stable native
root after every restart.  The command above remains useful for diagnostics.
The current automated rebind and soldier-movement tests can be run with:

```powershell
python -m unittest discover -s tests -v
```

Initial screenshot values for Steam build `24931318`:

- manpower: 0 (not scanned because zero has too many false matches)
- food: 1
- water: 1
- wood: 2
- fuel: 4
- authority: 51

Stamina was not visible in the supplied screenshot and must be scanned from a
screen where its exact value is shown or can be changed.

`food` and `water` intentionally share the first candidate set because their
initial values are identical. A later exact-value change separates them.

## 附录：dist 下各程序的实际身份（2026-10-15 从 EXE 内部取证）

上面的历史条目里出现过 `dist/teams_update/`、`dist/expedition_update/` 这类路径，它们**并不存在**。
下表是直接读每个 EXE 内置的 `trainer_gui` / `game_build` 常量得到的真实对应关系
（建档方式：解出 PyInstaller 归档里的 PYZ，反序列化模块后提取字符串常量）：

| 目录 | 内置支持构建号 | 界面/功能指纹 | sha256 前 16 位 |
| --- | --- | --- | --- |
| `dist/1/…_before_tasks.exe` | 24931318 | 远征任务、刷新任务 | `7a75557637be34cc` |
| `dist/2/AfterIncRevivalTrainer_CN.exe` | （PYZ 为旧 Python 版本，无法反序列化；指纹含随机任务） | 远征任务、刷新任务、随机任务 | `9229f1f4db0ab0de` |
| `dist/3/AfterIncRevivalTrainer_CN.exe` | 同上 | 远征任务、刷新任务、随机任务、探索与建设队伍 | `f45e293fcbee972b` |
| `dist/4/AfterIncRevivalTrainer_CN.exe` | 同上 | 上述 + 远征与随机任务、队伍与战士、战士快移 | `77f33f6ddf7b8918` |
| `dist/build_25936576/AfterIncRevivalTrainer_CN.exe` | 25936576 | 与 4 相同的紧凑布局 | `5415ee4b04e5f5d1` |
| `dist/build_25936576_tasks/AfterIncRevivalTrainer_CN.exe` | 25936576 | 与 4 相同 | `6b3030c7b1ab4658` |
| `dist/AfterIncRevivalTrainer_CN.exe` | 25936576 | 与 `build_25936576_tasks` 是同一个文件 | `6b3030c7b1ab4658` |

`dist/2`、`3`、`4` 的 `game_build` 模块是用旧版 Python 打包的，当前环境（3.10）无法反序列化其 code object，
因此构建号一栏留空；功能指纹仍可从内置 `trainer_gui` 常量读出。
`dist/1`、`2` 的 `expedition` 模块同样存在 `TypeError: code object` 的问题。

按 AGENTS.md「历史修改器文件夹应该以 steam 的号码命名」，这些目录尚未改名（`dist` 与
`after_inc_trainer` 的所有者是旧沙箱账户 `CodexSandboxOffline`，改名需要先取回目录所有者身份）。
