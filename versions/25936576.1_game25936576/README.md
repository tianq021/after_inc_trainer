# 战士升级与队伍保持独立版本

修改器版本 **25936576.1**；Steam App ID **3337140**；游戏构建 **25936576**。

基于 2026-10-14 随机任务修复版复制开发，不替换父目录中正在运行的程序。
入口：`dist/build_25936576_1/AfterIncRevivalTrainer_CN.exe`。

## 默认目标值

人力 100、食物 7、水 7、木材 8、燃料 8、权威 100、目标耐心 365。
用户所称“体力”对应现有第一项；该字段经核对实际为人力，故保留人力名称。
这些是输入框默认值，启动不会自动设置资源或开启资源锁定。

## 队伍重新加载后保持

勾选“保持本次设置的队伍数量”，点“读取队伍”记住当前数量，或用探索/建设 +1 设置目标。
修改器运行期间每 1.5 秒重新验证当前关卡，数量不足时补回各自的目标；已有更多队伍不会被减掉。
读档、切关和游戏重启后都重新定位对象，不复用旧关卡地址；地图页或加载中等待重试。
取消勾选或“停止锁定”停止补回。记忆只保持到本次修改器退出，不改游戏存档格式。
探索和建设分别记录目标，未读取/设置的类别不会自动改动。

## 三个独立战士升级选项

仅支持精确构建 25936576。在关卡内点“读取战士”，下拉选择一个现存玩家战士：

- 升级机会 +1：调用游戏自身的战士升级事件，在所选战士所在区域生成一个可点击的原生升级图标；
  由玩家点击图标后自行选择全局战士加成。它不等于给单个战士加经验，也不替玩家做选择。
- 武器 +0.25：调用 ChangeWeaponStrength，武器强度 +0.25，武器升级次数 +1。
- 小队 +0.25：调用 ChangeSquadSize，小队规模 +0.25，小队升级次数 +1，并重建士兵标记。

操作提交后修改器会等游戏最多 8 秒把它执行完（窗口失焦时游戏会暂停，所以点完必须切回游戏窗口
让时间前进一下）；等到了就直接显示结果，超时则提示“请求还在等待游戏执行”。“取消等待”可清除
尚未执行的请求。只修改所选战士，不修改全部队伍或敌人。工具限制武器和小队升级次数各最多 20，
强度/规模最高 20（这是工具限制，不是宣称游戏原生上限）。

升级事件的原生拒绝码：-5 游戏已无可用升级奖励、-6 已有待处理升级、-7 升级事件未就绪或校验失败、
-8 游戏未确认生成一个升级事件、-9 升级事件执行异常。出现负值不会重试，连续点击也不会堆叠图标；
已有图标时必须先点掉再请求下一次。

### 关于 -5（没有可选的战士升级奖励）

游戏 `GameEvents.HasSoldierUpgradesLeft()` 的判据是：士兵升级科技里存在「可重复购买」或
「还没买过（`TechLite.timesEvolved` 为 0）」的一项。游戏自己的 `GameEvents.SoldierUpgrade`
用同一判据先数一遍可用选项，数量为 0 时会在创建图标之前就返回。所以这个存档一旦把
非重复的士兵升级科技全部买过，就不会再有升级图标 —— 修改器拒绝是如实反映游戏状态，
不是方向点错。诊断日志里的 `stage = 11 (left)` 就是这个分支。

### 诊断日志

每次点击都会在 `%LOCALAPPDATA%/AfterIncTrainer/logs` 写两份记录：

- `soldier_<时间戳>.json`：请求内容 + 提交时的 `hook_calls`。
- `soldier-result_<时间戳>.json`：游戏实际返回的 `status`、失败时的中文 `stage`、以及完整的
  `diag` 快照（`hook_calls` / `runs_started` / `identity_fails` / `stage` / `event_found` /
  `engaged_before` / `has_upgrades_left` / `opt_has_value` / `opt_is_object` / `created_count` /
  最后一次调用钩子时看到的 manager·game·global 指针）。

`hook_calls` 不增长就说明游戏线程一次都没进模拟函数（通常是游戏被暂停/失焦），
`hook_calls` 增长但 `runs_started` 不增长就说明请求已经在游戏早期就被比较交换挡掉了。

首次安装扩展前自动备份存档，位于 `%LOCALAPPDATA%/AfterIncTrainer/backups`，请求日志位于同级 logs。
扩展只加载到当前进程，不改游戏安装文件；通过 MovingSoldierManager 的 ISimulatable 虚表槽在游戏线程执行原函数。
关卡身份、列表成员、战士/设计回指与存活状态均重新校验；换关后旧选择和请求会拒绝执行。
修改器退出不卸载扩展；游戏退出释放扩展。更新 DLL 后若提示不一致，需要重启游戏。

## 开发验证

56 项自动测试通过（其中 11 项为原生用例），涵盖现有功能、队伍重置后恢复/不降低已有容量、
非法目标、战士扩展 ABI、旧关卡选择拒绝、未知版本拦截，以及战士升级请求在假对象图上的
全部拒绝码（-1/-2/-3/-4/-5/-6/-7/-8，含"事件标识长度写错"的回归用例）与武器/小队两条正常路径。
窗口 600×540，分为「资源 / 队伍与升级 / 远征与地图」三个页签。

### 实机验收：通过（2026-10-15）

`%LOCALAPPDATA%/AfterIncTrainer/logs/soldier-result_*.json` 连续多条记录一致：

| 字段 | 实测值 | 含义 |
| --- | --- | --- |
| `status` | 3 | 游戏确认生成了升级事件 |
| `stage` | 10 | 走到 `STAGE_OK` |
| `event_found` | 1 | 在 allEvents 里定位到 SoldierUpgrade |
| `has_upgrades_left` | 1 | 游戏判定仍有可用升级科技 |
| `engaged_before` | 0 / 1 | 待处理列表当时的状态 |
| `opt_has_value` | 1，`opt_is_object` 0 | `Optional<EngagedCluster>` 走 `value` 字段 |
| `created_count` | 1 | 生成的 cluster 里恰好 1 个 EngagedEvent |
| `identity_fails` | 0 | 管理器/关卡身份校验全部通过 |

选中的战士所在区域会出现可点击的原生升级图标，点开后可自选加成。
**用户观察**：一名战士把全部升级技能都点满之后，再升级时只剩「强化训练：提升战士战斗力」这一项
——这正是 `HasSoldierUpgradesLeft()` 判据里 `tech.repeatable` 为真的那条科技，所以升级机会仍然存在，
逻辑自洽。

### 历史排错记录（已修复）

- **-7「事件表里没有 SoldierUpgrade」**：`upgradeIdent()` 里把 `"SoldierUpgrade"` 的长度写成了 **13**，
  实际是 **14**（Soldier 7 + Upgrade 7），长度不等就直接判定不匹配，于是永远找不到事件。
  已改为从字面量推导长度，并在原生测试里加了"长度传 13 必须判为未找到"的回归用例。
- **-7 的另一处成因**：扫描 `engaged` 列表时原本是"任一元素判不了就整条中止"，
  列表变动期间会整次失败。现已改为跳过不匹配项继续找。
- **挂钩未触发导致的"已有升级等待执行"**：游戏窗口失焦时会暂停，请求会一直挂着。
  现在点完会等游戏最多 8 秒再回报，并在日志里给出 `hook_calls` 便于判断。

上一个 DLL（只加经验、没有升级事件，sha256 `bdb1172c...`）保留在
`native/AfterIncSoldierUpgrade.dll.bak-20261014-2342`。

实机 PID 2460（2026-10-14，旧接口）：soldier0 经验回调前后 1.029999→2.029999；武器强度 1→1.25、次数 0→1；
小队规模 1→1.25、次数 0→1。
队伍恢复已通过模拟重载测试；用户选择暂不重载、先打包，因此尚未进行实机关卡重载验收。

`python -m unittest discover -s tests -v`（须用系统 Python 3.10；3.13 环境无 tkinter）

`native/build_soldier.cmd`（发货用 DLL）

`native/build_native_test.cmd`（原生测试 DLL，仅供测试，不进打包）

`python -m PyInstaller --noconfirm --distpath dist/build_25936576_1 --workpath build/build_25936576_1 AfterIncRevivalTrainer_CN.spec`

### 原生构建的两个约束

本机没有安装 Windows SDK，`kernel32.lib` 等导入库不存在，因此：

1. `soldier_upgrade.cpp` 的升级事件路径使用 `__try/__except`，链接需要的 `__C_specific_handler`
   由 `build_soldier.cmd` 现场用 `ntdll.dll` 的导出表生成 `ntdll_seh.lib` 提供（ntdll 常驻目标进程）。
   DLL 仍保持 `/NODEFAULTLIB /ENTRY:DllMain` 的无 CRT 结构，只导入 ntdll。
2. 打包用的 `python -m PyInstaller` 必须用系统 Python 3.10（带 tkinter）；本机 Python 3.13 无 tkinter。

反汇编证据：`soldier_simulate.txt`、`upgrade_disassembly.txt`。
新增原生入口（25936576）：manager type=75878720，vtable=class+0x138+4*16，
Simulate=0x7CABB0，IncrementLevel=0x7BAE00，ChangeWeaponStrength=0x7B5110，ChangeSquadSize=0x7B9140，
升级事件 CanCreate=0x622BA0、Create=0x5D9DA0，Tech 标识 `SoldierUpgrade`。
