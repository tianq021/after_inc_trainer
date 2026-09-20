# After Inc: Revival memory analysis helper

## 2026-09-19: 远征任务刷新

新版程序：`dist/expedition_update/AfterIncRevivalTrainer_CN.exe`（原版 EXE 保留）。
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
