# GameAssembly.dll 稳定根指针分析

分析日期：2026-09-06

## 目标与样本

- 游戏：After Inc: Revival，Steam Build `24931318`
- `GameAssembly.dll` 大小：`70,436,352` 字节
- SHA-256：`81DED46998713B8E79D877DCA14E0D50791603E9A7D3A407B59365883942B6B8`
- IL2CPP metadata 版本：`31`

目标是避免切关或游戏重启后扫描约 `2.6 GiB` 私有内存。

## 原生代码证据

### SteamManager 是跨场景单例

`SteamManager.get_Instance`（RVA `0xA88E70`）在 RVA `0xA88EC2` 读取：

```text
mov rax, [GameAssembly + 0x3D13B90]
mov rcx, [rax + 0xB8]
mov rbx, [rcx + 0x8]
```

对应 `SteamManager Il2CppClass -> static_fields -> s_instance`。`SteamManager.Awake`
（RVA `0xA882C0`）会写入该静态字段，并调用 `UnityEngine.Object.DontDestroyOnLoad`。

### SteamManager 保存当前场景启动器

`SteamManager.GetLaunchHandler<object>`（RVA `0xDD5980`）把取得的启动器写到：

```text
mov [SteamManager + 0x50], rax
```

metadata 对应字段 `SteamManager.launch`。`SteamLaunchHandler.set_scenarioLauncher`
（RVA `0x4D14E0`）把参数写到：

```text
mov [SteamLaunchHandler + 0x28], rdi
```

metadata 对应字段 `_scenarioLauncher`。

### 每次关卡初始化都会发布当前 GameController

`GameController.SetUpGame`（RVA `0x757640`）末尾 RVA `0x75822B–0x758254` 依次：

1. 调用 `SteamManager.get_Instance`；
2. 调用 `SteamManager.GetLaunchHandler<object>`；
3. 将当前 `GameController`（`r15`）作为参数；
4. 调用 `SteamLaunchHandler.set_scenarioLauncher`。

因此 `scenarioLauncher` 是由游戏自身在每次关卡初始化后更新的活动根，而不是修改器猜测
或缓存的临时绝对地址。

## 最终读取链

```text
GameAssembly.dll + 0x3D13B90
  -> SteamManager Il2CppClass
  +0xB8 -> static_fields
  +0x08 -> SteamManager.s_instance
  +0x50 -> SteamLaunchHandler
  +0x28 -> 当前 GameController
  +0x48 -> 当前 GlobalSimulation
  +0x50 -> 当前 WorldSettlementSimulator
```

## 安全验证

解析链后仍执行以下检查，任一失败都暂停读写并等待下一次 `0.5` 秒轮询：

1. `SteamManager` 对象的类指针必须等于静态根中的 `SteamManager Il2CppClass`；
2. `SteamManager` 和 `GameController` 的 Unity `m_CachedPtr` 必须非零；
3. `GameController.hasSetup` 必须为 `true`；
4. `GameController / GlobalSimulation / WorldSettlementSimulator` 必须形成双向闭环；
5. 全部生产对象指针必须有效，`ResourceType` 必须逐项匹配 metadata 布局；
6. 只有完整验证通过的地址才允许进入读取或写入流程。

完整内存定位器仍保留在“完整扫描重新定位”按钮中，但不再由切关或启动过程自动触发。
这些 RVA 仅适用于上述 DLL 哈希；游戏更新后必须重新验证。
