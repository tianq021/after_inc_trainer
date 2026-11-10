# 构建 25936576 兼容性核对（2026-10-14）

本机 Steam appmanifest_3337140.acf 确认已安装构建 25936576。
GameAssembly.dll SHA-256：`c99f927e5590681f3a3790cb81dc6808fc519ac8d0e5486cdf1376578fc8f169`。
使用项目已有 Il2CppDumper 6.7.46 读取游戏 DLL 与 global-metadata.dat，
输出位于 `il2cpp_dump/build_25936576`；元数据版本 31。

对比 build_25479909/dump.cs，忽略 TypeDefIndex 后，以下类型字段声明和偏移一致：
SteamManager、SteamLaunchHandler、GameController、GlobalSimulation、WorldSimBase、
WorldSettlementSimulator、StandaloneProduction、BaseProduction、GameSettings、
RandomLevelSeeding、UnifiedConstructionZoneJobManager、MovingSoldierManager、
MovingSoldier、MovingSoldierDesign；ResourceType 枚举和 ResourceSource 接口也一致。

从新版 script.json 按完整类型名定位的 RVA（十进制）：

| 类型 | RVA |
| --- | ---: |
| SteamManager | 76270776 |
| GameSettings | 76112208 |
| RandomLevelSeeding | 76049200 |
| UnifiedConstructionZoneJobManager | 76461704 |

反汇编确认 SteamManager.get_Instance（0xB4C160）从 0x48BCCB8 读取类型指针，
继续使用类 +0xB8 静态字段及 +0x8 单例。
UnifiedConstructionZoneJobManager.SetBuilderCapacity（0x8F2AF0）继续更新 +0x10 字典，
非负容量分支无额外状态写入。队伍解析现在使用对应构建的类型槽。

## 随机任务扩展补充适配

复核新版生成函数的实际调用链，映射如下（RVA）：

| 用途 | 25936576 |
| --- | --- |
| Campaigns 类型槽 | 0x48F4420 |
| GetRandomCampaignLevels | 0x766D50 |
| RandomLevel | 0x792490 |
| 对象分配 | 0x4708C0 |
| ObjectiveChain 类型槽 | 0x4868B20 |
| ObjectiveChain 构造 / Add | 0x985000 / 0x9848A0 |
| ObjectiveLoader.Randomised | 0x9A1B50 |
| LevelBuilder.SetObjectiveChain | 0x6B0970 |
| List.Add / MethodInfo 槽 | 0x2F80 / 0x48F2390 |
| 静态委托调用跳板 | 0x3170 |
| 地图选点 mov r9d, 6 | 0x6E030F |

Campaigns.Campaign 和 ObjectiveChain 字段布局保持不变。
LevelBuilder 有字段变动，扩展不直接写其字段，而是调用新版游戏函数。
88 字节 TaskState 最末的保留整数现为构建号，Python 与 DLL 同步选择地址。
未知构建拒绝操作，未配置的原生回调也拒绝调用游戏函数。

实机 PID 28016 通过精确哈希、委托跳板、原生成入口及地图指令检查。
首次备份因 Sentry 诊断锁文件失败，未加载扩展；排除诊断锁后备份成功并配置
1 个任务（种子 57976），回读 count=1、active=true、build=25936576。
备份：`C:/Users/hp/AppData/Local/AfterIncTrainer/backups/20261014-231731-before-tasks`。
用户刷新地图后实机回读：generated=1、calls=158、error=0、activity=0、active=true。
确认实际任务生成成功，测试任务保留供用户查看或清除；进入与结算仍需实机验收。
39 项自动测试通过，新版 EXE 已打包。

验证命令：`python -m unittest discover -s tests -v`。
打包命令：`python -m PyInstaller --noconfirm --distpath dist/build_25936576_tasks --workpath build/build_25936576_tasks AfterIncRevivalTrainer_CN.spec`。
