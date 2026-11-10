> 已知问题：本版远征扩展存在错误函数重载，会影响胜利结算及存档读取。仅供历史追溯，请使用 26049821.2；下文为原始发布记录。

# 修改器 26049821.1 — 游戏构建 26049821

Steam App ID：3337140；游戏内部版本：1.0.2.2；日期：2026-10-19。
启动：dist/AfterIncRevivalTrainer_CN.exe。

功能：资源/耐心/权威修改及锁定、快速移动、探索与建设队伍及数量保持、战士升级机会/武器/小队增强、远征日期、随机任务扩展。
战士功能在本版仅接受 26049821；旧游戏 25936576 使用保留的 25936576.1 完整版本。其他功能保留先前支持的构建。

验证：56 项自动测试通过，重新编译生产 DLL 和原生测试 DLL，PyInstaller 打包成功。尚未进行新版游戏内实机功能验收。
GameAssembly SHA-256：08719a4423f94c5563cec3d82bdc647ff44a09345bc2c9e88f222cdd5eae782a。
EXE SHA-256：cb7133b7b98d9fb685a72931f837875d43c0af71021fbc17db6016a9d9969222。

## 适配依据

已有 Il2CppDumper 6.7.46 解析本机 DLL 与元数据（版本 31），结果保存在 ../../il2cpp_dump/build_26049821。
21 个相关类型的字段布局与上一构建一致，见 layout_verification.json。
GameEvents 新增 numTricksInARow（0xF8），原 soh9DestroyBridgeCheckedThisRun 移至 0xFC；本修改器不读写这两个字段。其父类 BaseGameEvents、事件列表和升级标记布局不变。
类型槽沿用旧值，但函数必须使用新版 RVA。未知哈希继续拒绝操作。

| 调用 | 新 RVA |
| --- | --- |
| GetRandomCampaignLevels | 0x766DB0 |
| RandomLevel | 0x7924F0 |
| ObjectiveChain 构造 / Add | 0x9850E0 / 0x984700 |
| ObjectiveLoader.Randomised | 0x9A1BB0 |
| SetObjectiveChain | 0x6B0A50 |
| HasSoldierUpgradesLeft | 0x622C80 |
| BaseGameEvents.TryFire | 0x5D9DA0 |
| MovingSoldierManager.Simulate | 0x7CAC10 |
| ChangeWeaponStrength / ChangeSquadSize | 0x7B5170 / 0x7B91A0 |
| 地图选点指令 | 0x6E036F |

反汇编确认原任务生成器调用 0x4708C0 对象分配、0x2F80 List.Add；委托跳板仍为 0x3170。地图补丁原字节为 41 b9 06 00 00 00，运行时仍校验。

构建：native/build.cmd、native/build_soldier.cmd、native/build_native_test.cmd。
测试：python -m unittest discover -s tests -v。
打包：python -m PyInstaller --noconfirm --distpath dist --workpath build AfterIncRevivalTrainer_CN.spec。
