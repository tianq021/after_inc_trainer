# After Inc: Revival 简易修改器项目——进度与续作手册

最后更新：2026-09-06

> 本文档用于在对话上下文压缩、游戏重启或工作中断后恢复进度。继续工作时应先阅读本文，再查看同目录下的 `memory_scan.py` 和各次扫描的 `snapshot.json`。

## 1. 项目目标

为 Steam 版 **After Inc: Revival** 制作一个简陋、离线、无账号、无使用时长限制的 Windows 修改器。

目标功能：

1. 耐力；
2. 食物；
3. 水；
4. 木材；
5. 燃料；
6. 权威；
7. 士兵快速移动。

可附带研究但不作为第一版重点：人力。

第一版建议只做资源和耐力相关功能。士兵快速移动需要定位游戏逻辑函数，复杂度高于资源数值修改，应在基础资源地址确认后处理。

## 2. 安全边界与当前状态

只读扫描阶段截至第七轮结束时：

- 扫描器只申请 `PROCESS_QUERY_INFORMATION` 和 `PROCESS_VM_READ` 权限；
- 没有修改游戏安装目录中的文件；
- 没有注入 DLL；
- 没有安装 Cheat Engine；
- 所有候选地址和扫描记录都保存在工作区内。

第七轮只读验证结束后，项目进入首次受控写入测试：

- 已先备份 Steam 存档、缓存清单、本地设置和 Steam App 清单；
- 新增了单地址 `write-float32` 命令；
- 命令只有在当前值与 `--expected` 完全一致、并提供精确确认短语时才写入；
- 第一个人力候选 `0x00000232EA35AA18` 曾从 `0.0` 临时改为 `1.0`，但暂停状态下左上角人力仍显示 `0`；
- 随后已把第一个候选安全恢复为 `0.0`，并把第二个人力候选 `0x00000232EA35ABE0` 从 `0.0` 临时改为 `1.0`；
- 尚未冻结任何值，也没有批量写入；
- 已用 IL2CPP 元数据恢复出真实类和字段布局，并唯一定位当前 `WorldSettlementSimulator` 对象；
- 第二个人力候选已经确认是 `StandaloneProduction._total`（对象偏移 `0x280`），第一个候选是同一资源对象中的计算缓存；
- 当前已把结构确认的人力主字段从 `3.0` 改为 `10.0`，正在等待界面刷新验证。

除上述已经经过多轮变化验证的人力候选外，不应向其他候选地址写入数值。

## 3. 本机游戏信息

游戏安装位置：

```text
F:\SteamLibrary\steamapps\common\After Inc
```

关键文件：

```text
F:\SteamLibrary\steamapps\common\After Inc\After Inc. Revival.exe
F:\SteamLibrary\steamapps\common\After Inc\GameAssembly.dll
F:\SteamLibrary\steamapps\common\After Inc\UnityPlayer.dll
F:\SteamLibrary\steamapps\common\After Inc\After Inc. Revival_Data\il2cpp_data\Metadata\global-metadata.dat
```

当前已确认的构建信息：

| 项目 | 值 |
|---|---|
| Steam App ID | `3337140` |
| Steam Build ID | `24931318` |
| Unity 版本 | `6000.0.62f1` |
| 平台 | Windows 64 位 |
| 脚本后端 | Unity IL2CPP |
| `GameAssembly.dll` SHA-256 | `81ded46998713b8e79d877dca14e0d50791603e9a7d3a407b59365883942b6b8` |

Steam 清单位置：

```text
F:\SteamLibrary\steamapps\appmanifest_3337140.acf
```

扫描时的游戏进程 PID 为 `30376`。PID 仅对当次运行有效，游戏重启后会变化。

## 4. 为什么可以自己制作

游戏是标准的 Unity IL2CPP 构建，`GameAssembly.dll` 和未隐藏的 `global-metadata.dat` 均存在。元数据中可以看到与资源相关的类和方法名称，例如：

```text
ResourceList
GetResourceCount
SpendResource
GenericResourceChange
ChangeAuthority
ResourceCount
stamina_cost
foodGainAmount
waterScavengeDistrictAmount
woodScavengeDistrictAmount
fuelScavengeDistrictAmount
```

因此有两条可行路线：

1. 先用内存数值变化找到资源对象和字段；
2. 后续用 IL2CPP 元数据和 `GameAssembly.dll` 中的代码定位稳定方法或特征码。

第一条路线更适合快速做出原型；第二条路线用于减少游戏重启或小版本更新造成的地址失效。

## 5. 截图数值记录

### 5.1 第一次截图：初始状态

第一次截图确认的实际含义：

| 项目 | 值 | 备注 |
|---|---:|---|
| 人力 | 0 | 左上角锤子/工具图标，最初曾被误认为耐力，现已更正 |
| 民心 | 27% | 当前不在目标功能内 |
| 权威 | 51 | 皇冠图标 |
| 食物 | 1/6 | 当前量为 1，容量为 6 |
| 水 | 1/6 | 当前量为 1，容量为 6 |
| 木材 | 2/8 | 当前量为 2，容量为 8 |
| 燃料 | 4/8 | 当前量为 4，容量为 8 |
| 科技等级 | 1 | 左下角烧瓶图标 |
| 房屋 | 1 | 左下角房屋图标 |
| 耐心 | 高 | 左下角月桂图标 |

耐力没有在这张截图中显示，因此没有把人力 `0` 当作耐力继续处理。

### 5.2 第二次截图：数值变化后

第二次截图确认：

| 项目 | 旧值 | 新值 | 是否适合筛选 |
|---|---:|---:|---|
| 人力 | 0 | 1 | 首次零值未扫描，已用新值 1 补做一份首次扫描 |
| 民心 | 27% | 31% | 暂不处理 |
| 权威 | 51 | 51 | 未变化，可用于“未变化”过滤，但精确值候选仍较多 |
| 食物 | 1 | 1 | 未变化 |
| 水 | 1 | 0 | 已执行第二次精确筛选 |
| 木材 | 2 | 2 | 未变化 |
| 燃料 | 4 | 5 | 已执行第二次精确筛选，结果非常好 |

第二次截图中游戏处于暂停状态，这是正确做法。扫描期间数值应尽量保持不变。

## 6. 扫描器文件与用法

扫描器源码：

```text
G:\Codex_mmx\after_inc_trainer\memory_scan.py
```

说明文件：

```text
G:\Codex_mmx\after_inc_trainer\README.md
```

使用的 Python：

```text
G:\Codex_mmx\2026-08-17\.venv\Scripts\python.exe
```

扫描器目前支持三个子命令：

### 6.1 `initial`

扫描当前进程中与指定非零数值相等、并且按 4 字节对齐的 `int32` 和 `float32` 候选。

示例：

```powershell
& 'G:\Codex_mmx\2026-08-17\.venv\Scripts\python.exe' `
  'G:\Codex_mmx\after_inc_trainer\memory_scan.py' initial `
  --process 'After Inc. Revival.exe' `
  --value 'food=1' `
  --value 'water=1' `
  --value 'wood=2' `
  --value 'fuel=4' `
  --value 'authority=51' `
  --output 'G:\Codex_mmx\after_inc_trainer\scans\build_24931318_initial' `
  --game-build '24931318' `
  --game-assembly 'F:\SteamLibrary\steamapps\common\After Inc\GameAssembly.dll'
```

零值初扫会产生大量误匹配，因此扫描器会跳过初始值为 0 的项目。

### 6.2 `refine`

从上一次候选地址中筛选当前等于新精确值的地址。

示例：

```powershell
& 'G:\Codex_mmx\2026-08-17\.venv\Scripts\python.exe' `
  'G:\Codex_mmx\after_inc_trainer\memory_scan.py' refine `
  --snapshot 'G:\Codex_mmx\after_inc_trainer\scans\build_24931318_initial\snapshot.json' `
  --value 'water=0' `
  --value 'fuel=5' `
  --output 'G:\Codex_mmx\after_inc_trainer\scans\build_24931318_refine_01'
```

### 6.3 `inspect`

只读查看某个候选地址附近按 4 字节解释的整数和浮点数。

示例：

```powershell
& 'G:\Codex_mmx\2026-08-17\.venv\Scripts\python.exe' `
  'G:\Codex_mmx\after_inc_trainer\memory_scan.py' inspect `
  --process 'After Inc. Revival.exe' `
  --address '0x000002332264CAD8' `
  --before 128 `
  --after 192
```

## 7. 已完成的扫描及结果

### 7.1 初始资源扫描

扫描记录：

```text
G:\Codex_mmx\after_inc_trainer\scans\build_24931318_initial\snapshot.json
```

扫描统计：

| 项目 | 值 |
|---|---:|
| 已扫描私有内存 | 2,861,461,504 字节，约 2.66 GiB |
| 读取失败 | 0 |
| 扫描耗时 | 50.449 秒 |

候选数量：

| 项目 | 类型 | 初始值 | 候选数 |
|---|---|---:|---:|
| 食物、水 | `int32` | 1 | 6,363,323 |
| 食物、水 | `float32` | 1.0 | 7,181,711 |
| 木材 | `int32` | 2 | 1,463,783 |
| 木材 | `float32` | 2.0 | 267,819 |
| 燃料 | `int32` | 4 | 1,090,390 |
| 燃料 | `float32` | 4.0 | 20,597 |
| 权威 | `int32` | 51 | 47,089 |
| 权威 | `float32` | 51.0 | 3,197 |

食物和水首次值相同，因此共享第一批候选。后续两者数值不同时可以分别筛选。

### 7.2 水和燃料第二次筛选

扫描记录：

```text
G:\Codex_mmx\after_inc_trainer\scans\build_24931318_refine_01\snapshot.json
```

筛选结果：

| 项目 | 类型 | 变化 | 筛选前 | 筛选后 |
|---|---|---:|---:|---:|
| 水 | `int32` | 1 → 0 | 6,363,323 | 71,192 |
| 水 | `float32` | 1.0 → 0.0 | 7,181,711 | 519,123 |
| 燃料 | `int32` | 4 → 5 | 1,090,390 | 2,363 |
| 燃料 | `float32` | 4.0 → 5.0 | 20,597 | **1** |

燃料的唯一 `float32` 候选：

```text
地址：0x000002332264CAD8
扫描时的值：5.0
候选文件：G:\Codex_mmx\after_inc_trainer\scans\build_24931318_refine_01\fuel_float32_5.bin
```

这个地址非常有希望，但**尚未确认**。必须等燃料再次变化后，检查这个地址是否同步变化。只有同步变化后，才可以认为它是燃料值或燃料值的有效缓存。

附近内存中还出现了 `2.05`、`2.0`、`22.0`、`20.0`、`0.4` 等浮点数，但目前没有证据证明它们属于其他资源，不应猜测或写入。

### 7.3 人力补充初扫

由于第一次截图中人力为 0，而零值没有初扫，第二次截图人力变为 1 后补做了初始扫描。

扫描记录：

```text
G:\Codex_mmx\after_inc_trainer\scans\build_24931318_manpower_initial_01\snapshot.json
```

候选数量：

| 类型 | 当前值 | 候选数 |
|---|---:|---:|
| `int32` | 1 | 6,350,900 |
| `float32` | 1.0 | 7,376,053 |

需要人力再次变化才能有效缩小候选。

### 7.4 第三次截图与第三轮筛选

第三次截图确认的状态：

| 项目 | 上一状态 | 当前状态 | 处理结果 |
|---|---:|---:|---|
| 人力 | 1 | 0 | 已从人力补充初扫继续筛选 |
| 民心 | 31% | 44% | 暂不处理 |
| 权威 | 51 | 51 | 未变化 |
| 食物 | 1 | 1 | 未变化 |
| 水 | 0 | 1 | 已从水、燃料第二次筛选继续筛选 |
| 木材 | 2 | 1 | 已从最初资源快照执行第二次筛选 |
| 燃料 | 5 | 5 | 未变化，用于检查唯一候选是否仍保持稳定 |

水和燃料第三轮记录：

```text
G:\Codex_mmx\after_inc_trainer\scans\build_24931318_refine_02\snapshot.json
```

结果：

| 项目 | 类型 | 筛选前 | 筛选后 |
|---|---|---:|---:|
| 水 | `int32` | 71,192 | 6,859 |
| 水 | `float32` | 519,123 | 92,858 |
| 燃料 | `int32` | 2,363 | 131 |
| 燃料 | `float32` | 1 | **1** |

燃料唯一浮点候选在经过一轮游戏状态变化后仍为 `5.0`，没有被排除。这说明候选较稳定，但由于屏幕燃料也没有变化，仍不足以最终证明它就是燃料字段。

木材筛选记录：

```text
G:\Codex_mmx\after_inc_trainer\scans\build_24931318_wood_refine_01\snapshot.json
```

结果：

| 类型 | 变化 | 筛选前 | 筛选后 |
|---|---:|---:|---:|
| `int32` | 2 → 1 | 1,463,783 | 4,210 |
| `float32` | 2.0 → 1.0 | 267,819 | 9,397 |

人力筛选记录：

```text
G:\Codex_mmx\after_inc_trainer\scans\build_24931318_manpower_refine_01\snapshot.json
```

结果：

| 类型 | 变化 | 筛选前 | 筛选后 |
|---|---:|---:|---:|
| `int32` | 1 → 0 | 6,350,900 | 67,748 |
| `float32` | 1.0 → 0.0 | 7,376,053 | 695,053 |

木材、水和人力都需要再变化至少一次。下一轮应分别从各自最新的 `snapshot.json` 继续，而不能退回最初快照，否则已经排除的候选会重新出现。

### 7.5 第四次截图与第四轮筛选

第四次截图状态：

| 项目 | 上一状态 | 当前状态 | 变化情况 |
|---|---:|---:|---|
| 人力 | 0 | 1 | 发生变化，继续筛选 |
| 民心 | 44% | 58% | 暂不处理 |
| 权威 | 51 | 51 | 未变化 |
| 食物 | 1 | 1 | 未变化 |
| 水 | 1 | 1 | 未变化，但可排除期间发生变化的临时候选 |
| 木材 | 1 | 1 | 未变化，但可排除期间发生变化的临时候选 |
| 燃料 | 5 | 5 | 未变化，继续验证候选稳定性 |

人力最新记录：

```text
G:\Codex_mmx\after_inc_trainer\scans\build_24931318_manpower_refine_02\snapshot.json
```

| 类型 | 变化 | 筛选前 | 筛选后 |
|---|---:|---:|---:|
| `int32` | 0 → 1 | 67,748 | 6,849 |
| `float32` | 0.0 → 1.0 | 695,053 | 77,098 |

水和燃料最新记录：

```text
G:\Codex_mmx\after_inc_trainer\scans\build_24931318_refine_03\snapshot.json
```

| 项目 | 类型 | 当前值 | 筛选前 | 筛选后 |
|---|---|---:|---:|---:|
| 水 | `int32` | 1 | 6,859 | 3,574 |
| 水 | `float32` | 1.0 | 92,858 | 27,083 |
| 燃料 | `int32` | 5 | 131 | 14 |
| 燃料 | `float32` | 5.0 | 1 | **1** |

木材最新记录：

```text
G:\Codex_mmx\after_inc_trainer\scans\build_24931318_wood_refine_02\snapshot.json
```

| 类型 | 当前值 | 筛选前 | 筛选后 |
|---|---:|---:|---:|
| `int32` | 1 | 4,210 | 629 |
| `float32` | 1.0 | 9,397 | 921 |

食物和权威第一次“保持不变”筛选记录：

```text
G:\Codex_mmx\after_inc_trainer\scans\build_24931318_food_authority_refine_01\snapshot.json
```

| 项目 | 类型 | 当前值 | 筛选前 | 筛选后 |
|---|---|---:|---:|---:|
| 食物 | `int32` | 1 | 6,363,323 | 6,126,794 |
| 食物 | `float32` | 1.0 | 7,181,711 | 5,801,700 |
| 权威 | `int32` | 51 | 47,089 | 42,023 |
| 权威 | `float32` | 51.0 | 3,197 | 2,121 |

食物和权威因为从首次扫描开始始终没有发生变化，单靠“保持不变”只能缓慢排除候选。两者都需要至少一次实际数值变化。

### 7.6 第五次截图与第五轮筛选

第五次截图中，人力从 1 变为 3；食物、水、木材、燃料和权威保持不变。民心变为 82%，不在当前目标内。

人力最新记录：

```text
G:\Codex_mmx\after_inc_trainer\scans\build_24931318_manpower_refine_03\snapshot.json
```

| 类型 | 变化 | 筛选前 | 筛选后 |
|---|---:|---:|---:|
| `int32` | 1 → 3 | 6,849 | **29** |
| `float32` | 1.0 → 3.0 | 77,098 | **28** |

人力已经非常接近定位，再发生一次不同数值变化通常就能降到个位数或唯一候选。

水和燃料最新记录：

```text
G:\Codex_mmx\after_inc_trainer\scans\build_24931318_refine_04\snapshot.json
```

| 项目 | 类型 | 当前值 | 筛选前 | 筛选后 |
|---|---|---:|---:|---:|
| 水 | `int32` | 1 | 3,574 | 2,933 |
| 水 | `float32` | 1.0 | 27,083 | 12,373 |
| 燃料 | `int32` | 5 | 14 | **9** |
| 燃料 | `float32` | 5.0 | 1 | **1** |

木材最新记录：

```text
G:\Codex_mmx\after_inc_trainer\scans\build_24931318_wood_refine_03\snapshot.json
```

| 类型 | 当前值 | 筛选前 | 筛选后 |
|---|---:|---:|---:|
| `int32` | 1 | 629 | 281 |
| `float32` | 1.0 | 921 | **65** |

食物和权威最新记录：

```text
G:\Codex_mmx\after_inc_trainer\scans\build_24931318_food_authority_refine_02\snapshot.json
```

| 项目 | 类型 | 当前值 | 筛选前 | 筛选后 |
|---|---|---:|---:|---:|
| 食物 | `int32` | 1 | 6,126,794 | 6,104,370 |
| 食物 | `float32` | 1.0 | 5,801,700 | 5,627,860 |
| 权威 | `int32` | 51 | 42,023 | 41,926 |
| 权威 | `float32` | 51.0 | 2,121 | 2,121 |

食物和权威的“保持不变”筛选已经基本失去继续缩小候选的作用，后续不要反复浪费时间扫描相同值，应等待真实变化。

### 7.7 第六次截图与第六轮筛选

第六次截图状态：

| 项目 | 上一状态 | 当前状态 | 变化情况 |
|---|---:|---:|---|
| 人力 | 3 | 2 | 发生变化 |
| 民心 | 82% | 60% | 暂不处理 |
| 权威 | 51 | 51 | 未变化，本轮不再重复扫描 |
| 食物 | 1 | 0 | 首次发生变化 |
| 水 | 1 | 2 | 发生变化 |
| 木材 | 1 | 1 | 未变化，继续稳定性过滤 |
| 燃料 | 5 | 5 | 未变化，继续稳定性过滤 |

人力最新记录：

```text
G:\Codex_mmx\after_inc_trainer\scans\build_24931318_manpower_refine_04\snapshot.json
```

| 类型 | 变化 | 筛选前 | 筛选后 |
|---|---:|---:|---:|
| `int32` | 3 → 2 | 29 | **0** |
| `float32` | 3.0 → 2.0 | 28 | **2** |

由此可判断人力不是当前扫描路径中的普通 `int32`，更可能是 `float32`，剩余两个候选：

```text
0x00000232EA35AA18
0x00000232EA35ABE0
```

两个地址相距较近，可能分别是游戏状态值与 UI/计算缓存。人力再变化一次即可区分，或者两者可能始终同步，需要后续通过引用关系判断主值。

水和燃料最新记录：

```text
G:\Codex_mmx\after_inc_trainer\scans\build_24931318_refine_05\snapshot.json
```

| 项目 | 类型 | 变化/当前值 | 筛选前 | 筛选后 |
|---|---|---:|---:|---:|
| 水 | `int32` | 1 → 2 | 2,933 | **1** |
| 水 | `float32` | 1.0 → 2.0 | 12,373 | **1** |
| 燃料 | `int32` | 保持 5 | 9 | 7 |
| 燃料 | `float32` | 保持 5.0 | 1 | **1** |

水的两个唯一候选：

```text
int32   0x00000230E34C97C4
float32 0x00000231A0A1A428
```

需要水再次变化才能判断实际类型。燃料唯一浮点候选仍是：

```text
float32 0x000002332264CAD8
```

食物最新记录：

```text
G:\Codex_mmx\after_inc_trainer\scans\build_24931318_food_refine_01\snapshot.json
```

| 类型 | 变化 | 筛选前 | 筛选后 |
|---|---:|---:|---:|
| `int32` | 1 → 0 | 6,104,370 | 5,570 |
| `float32` | 1.0 → 0.0 | 5,627,860 | 26,118 |

木材最新记录：

```text
G:\Codex_mmx\after_inc_trainer\scans\build_24931318_wood_refine_04\snapshot.json
```

| 类型 | 当前值 | 筛选前 | 筛选后 |
|---|---:|---:|---:|
| `int32` | 1 | 281 | 186 |
| `float32` | 1.0 | 65 | 23 |

第六轮之后，人力和水已经进入“下一次变化即可确认”的阶段；燃料仍需首次从 5 变化；食物和木材还需继续变化筛选。

### 7.8 第七次截图、第七轮筛选与策略调整

第七次截图状态：

| 项目 | 上一状态 | 当前状态 | 变化情况 |
|---|---:|---:|---|
| 人力 | 2 | 0 | 发生变化 |
| 民心 | 60% | 59% | 暂不处理 |
| 权威 | 51 | 51 | 未变化 |
| 食物 | 0 | 0 | 未变化 |
| 水 | 2 | 1 | 发生变化 |
| 木材 | 1 | 1 | 未变化 |
| 燃料 | 5 | 5 | 未变化 |

人力最新记录：

```text
G:\Codex_mmx\after_inc_trainer\scans\build_24931318_manpower_refine_05\snapshot.json
```

| 类型 | 变化 | 筛选前 | 筛选后 |
|---|---:|---:|---:|
| `int32` | 2 → 0 | 0 | 0 |
| `float32` | 2.0 → 0.0 | 2 | **2** |

两个浮点候选再次同步跟随人力变化：

```text
0x00000232EA35AA18
0x00000232EA35ABE0
```

它们已经连续跟随多轮 `1 → 0 → 1 → 3 → 2 → 0`，可信度很高。两个地址可能分别是实际状态与 UI/计算缓存，也可能是两个需要同步的字段。只读筛选无法继续区分，下一步应在备份存档后做一次可逆的小范围写入测试：只把其中一个地址从 0 写成 1，观察顶部人力是否变化，然后立即决定保留还是恢复。

对两个候选附近进行了只读检查。它们位于相近的堆区域，相距 `0x1C8` 字节，附近存在多个对象指针、浮点参数和容量样数值，但仅凭布局还无法可靠判定哪个是主值，不能直接假定。

水和燃料最新记录：

```text
G:\Codex_mmx\after_inc_trainer\scans\build_24931318_refine_06\snapshot.json
```

| 项目 | 类型 | 变化/当前值 | 筛选前 | 筛选后 |
|---|---|---:|---:|---:|
| 水 | `int32` | 2 → 1 | 1 | **0** |
| 水 | `float32` | 2.0 → 1.0 | 1 | **0** |
| 燃料 | `int32` | 保持 5 | 7 | 7 |
| 燃料 | `float32` | 保持 5.0 | 1 | **1** |

水之前的两个“唯一候选”这次全部被排除，说明它们是临时缓存、对象在回合更新时被重建，或者显示水量不是一个长期固定的原始整数/浮点字段。结论是：**不能再依赖水的旧绝对地址**。水以及可能采用同一资源系统的食物、木材、燃料，后续应转向：

1. 定位 `ResourceList`、`GetResourceCount`、`SpendResource` 或 `GenericResourceChange`；
2. 找到资源管理器实例或资源对象的稳定根指针；
3. 定位写入资源值的 `GameAssembly.dll` 指令；
4. 使用字段偏移或 AOB 特征码，而不是跨回合复用堆绝对地址。

燃料唯一浮点候选仍保持为 `0x000002332264CAD8`，但由于燃料一直没有再次离开 5，仍不能排除它只是长期保持 5 的无关字段。

食物最新记录：

```text
G:\Codex_mmx\after_inc_trainer\scans\build_24931318_food_refine_02\snapshot.json
```

| 类型 | 当前值 | 筛选前 | 筛选后 |
|---|---:|---:|---:|
| `int32` | 0 | 5,570 | 2,450 |
| `float32` | 0.0 | 26,118 | 14,200 |

木材最新记录：

```text
G:\Codex_mmx\after_inc_trainer\scans\build_24931318_wood_refine_05\snapshot.json
```

| 类型 | 当前值 | 筛选前 | 筛选后 |
|---|---:|---:|---:|
| `int32` | 1 | 186 | 165 |
| `float32` | 1.0 | 23 | 17 |

第七轮后的优先级发生变化：先通过可逆写入确认人力两个候选，再对资源系统做函数/对象级定位。继续仅靠绝对地址精确值筛选，可能会重复得到临时缓存。

### 7.9 首次受控写入测试

写入前备份目录：

```text
G:\Codex_mmx\after_inc_trainer\backups\2026-08-30_before_first_write
```

备份内容：

```text
gamesettingsv2.bin
pcnosyncsettings.bin
remotecache.vdf
appmanifest_3337140.acf
```

扫描器新增 `write-float32` 子命令。该命令具备以下保护：

1. 需要显式确认短语 `WRITE-ONE-FLOAT32`；
2. 写入前读取当前值；
3. 当前值与 `--expected` 不完全一致时拒绝写入；
4. 每次只写 4 字节；
5. 写入后立即读回验证；
6. 保存旧值、新值和恢复命令。

首次写入：

```text
地址：0x00000232EA35AA18
旧值：0.0
新值：1.0
结果：写入与读回验证成功
```

写入日志：

```text
G:\Codex_mmx\after_inc_trainer\write_tests\manpower_candidate_1_0_to_1.json
```

写入后只读复核：

```text
0x00000232EA35AA18 = 1.0
0x00000232EA35ABE0 = 0.0
```

当前游戏仍保持暂停。第一次观察时，左上角人力仍为 `0`。这说明在不推进游戏时间的条件下，第一个候选没有直接改变可见数字；仍不能完全排除它是等待逻辑刷新后才生效的状态缓存。

### 7.10 第二个人力候选交换测试

为避免两个候选同时为 `1.0` 而无法区分，先恢复第一个候选，再测试第二个候选。

恢复第一个候选：

```text
地址：0x00000232EA35AA18
旧值：1.0
新值：0.0
结果：写入与读回验证成功
日志：G:\Codex_mmx\after_inc_trainer\write_tests\manpower_candidate_1_restore_1_to_0.json
```

测试第二个候选：

```text
地址：0x00000232EA35ABE0
旧值：0.0
新值：1.0
结果：写入与读回验证成功
日志：G:\Codex_mmx\after_inc_trainer\write_tests\manpower_candidate_2_0_to_1.json
```

交换后只读复核：

```text
0x00000232EA35AA18 = 0.0
0x00000232EA35ABE0 = 1.0
```

现在应在保持暂停的情况下观察左上角人力：

- 若显示变成 `1`，第二个候选至少是有效显示值或主值；
- 若仍显示 `0`，应先把第二个候选恢复为 `0.0`，然后再研究无时间推进的 UI 刷新方式；
- 在得到观察结果前不要解除暂停，以免游戏逻辑覆盖测试值。

### 7.11 IL2CPP 结构定位与人力主字段确认

用户短暂解除暂停后，界面人力自然变为 `3`。只读复核发现两个旧候选都被游戏更新成了 `3.0`：

```text
0x00000232EA35AA18 = 3.0
0x00000232EA35ABE0 = 3.0
```

随后使用官方开源 Il2CppDumper `v6.7.46` 对以下两个游戏文件做离线只读分析：

```text
F:\SteamLibrary\steamapps\common\After Inc\GameAssembly.dll
F:\SteamLibrary\steamapps\common\After Inc\After Inc. Revival_Data\il2cpp_data\Metadata\global-metadata.dat
```

解析成功：

```text
Metadata Version: 31
Il2Cpp Version: 31
CodeRegistration: 0x1831AE120
MetadataRegistration: 0x183833A90
```

生成结果位于：

```text
G:\Codex_mmx\after_inc_trainer\il2cpp_dump\build_24931318
```

Il2CppDumper 在完成全部输出后尝试执行 `Console.ReadKey`，由于当前没有交互控制台而弹出 `.NET 0xe0434352` 即时调试错误。该错误发生在分析工作完成后的退出阶段，不属于游戏错误，不影响游戏、存档或已生成文件；残留分析器进程随后已经退出。

恢复出的关键字段：

```text
WorldSettlementSimulator.manpowerProd   +0x38
WorldSettlementSimulator.foodProd       +0x40
WorldSettlementSimulator.fuelProd       +0x80
WorldSettlementSimulator.waterProd      +0x98
WorldSettlementSimulator.constructionProd +0xA0
WorldSettlementSimulator.woodProd       +0xB0
WorldSettlementSimulator.authorityProd  +0x200
StandaloneProduction._total             +0x280
BaseProduction.resource                 +0x10
```

扫描器新增只读 `locate-settlement` 命令，按照上述对象字段间距，并同时核对每个生产对象的 `ResourceType` 枚举值。它扫描约 `2.87 GB` 私有内存后只找到一个完全匹配的对象：

```text
WorldSettlementSimulator = 0x00000232EA058000
候选数 = 1
```

结构报告：

```text
G:\Codex_mmx\after_inc_trainer\structure_scans\build_24931318_settlement.json
```

定位当时的真实库存：

| 项目 | 主字段地址 | 原始 float | 界面显示/说明 |
|---|---|---:|---|
| 人力 | `0x00000232EA35ABE0` | `3.0` | `3` |
| 水 | `0x00000232EA2048C0` | `2.9884255` | `2`，界面向下取整或截断 |
| 木材 | `0x00000232EA0E4BE0` | `1.0` | `1` |
| 柴火 | `0x00000232EA0B3280` | `2.8702617` | 与煤合并显示燃料 |
| 煤 | `0x00000232EA0C8BE0` | `2.4000001` | 与柴火合计约 `5.27`，界面显示 `5` |

这也解释了旧候选：

```text
0x00000232EA35A960  = manpowerProd 对象
对象 + 0x0B8       = 0x00000232EA35AA18（计算/服务调制缓存）
对象 + 0x280       = 0x00000232EA35ABE0（真实 _total）
```

结构确认后的醒目写入测试：

```text
地址：0x00000232EA35ABE0
旧值：3.0
新值：10.0
结果：写入与读回验证成功
日志：G:\Codex_mmx\after_inc_trainer\write_tests\manpower_struct_verified_3_to_10.json
```

写后复核：主字段为 `10.0`，计算缓存仍为 `3.0`。如果暂停状态下顶部仍显示 `3`，需要短暂解除暂停以触发资源的视觉更新；此时由于写入目标已由类结构确认，不再是盲猜候选地址。

### 7.12 基础资源、目标耐心与权威结构测试

人力从 `3.0` 改为 `10.0` 后，经一次视觉刷新，顶部人力准确显示 `10`，确认 `StandaloneProduction._total` 为有效主字段。

随后新增 `write-float32-batch`：写入前先核对批次内全部旧值；只有全部匹配才开始写入；写入或验证过程中任何一项失败，程序会把已经写过的项目自动回滚。首次资源批次：

```text
食物子资源 forage：0.0 -> 5.0
水：2.9884255 -> 5.0
木材：1.0 -> 7.0
燃料子资源 firewood：2.8702617 -> 5.0
煤保持：2.4000001
日志：G:\Codex_mmx\after_inc_trainer\write_tests\resources_struct_verified_batch_01.json
```

短暂推进游戏刷新后，界面显示：

```text
食物 4/6
水   4/6
木材 7/8
燃料 7/8
```

食物和水从写入值 `5` 变成 `4`，是推进时发生正常生产/消耗；木材和燃料的组合计算也与结构推断一致，因此四类资源地址均确认有效。

目标耐心相关字段：

```text
WorldSettlementSimulator.objectiveAuthorityTimer    +0x340
WorldSettlementSimulator.objectivePatienceMulti     +0x344
WorldSettlementSimulator.objectiveExpectedGameTurns +0x348
WorldSettlementSimulator.objectiveAuthorityTimerMax +0x34C
```

当界面显示“目标耐心：中”和“距离因缺乏目标进展而损失权威的天数 56”时，内存值为：

```text
objectiveAuthorityTimer = 56
objectiveExpectedGameTurns = 117
objectiveAuthorityTimerMax = 117
```

这证明当前剩余天数就是 `objectiveAuthorityTimer`。扫描器新增受保护的 `write-int32` 后，执行：

```text
地址：0x00000232EA058340
旧值：56
新值：117
日志：G:\Codex_mmx\after_inc_trainer\write_tests\objective_patience_timer_56_to_117.json
```

权威不是 `authorityProd._total`。当前界面权威 `51` 对应定居点对象中的比例字段：

```text
maxAuthority  +0x2F8 = 0.51
baseAuthority +0x2FC = 0.50
gameStartAuthority +0x300 = 0.51
```

受控测试已同时把权威上限和基础值设为 `0.80`：

```text
0x00000232EA0582F8：0.51 -> 0.80
0x00000232EA0582FC：0.50 -> 0.80
日志：G:\Codex_mmx\after_inc_trainer\write_tests\authority_base_max_to_080.json
```

当前读回状态为“目标耐心 `117/117`、权威上限 `0.80`、权威基础值 `0.80`”。下一步需要一次短暂视觉刷新，验证耐心显示“高”以及顶部权威显示 `80`；若权威仍为 `51`，继续分析 `WorldSettlementSimulator.get_Authority()`（RVA `0x78C150`）及 `AuthoritySource.value`（对象偏移 `0x10`）。

### 7.13 自动连接、读档与切关重定位

原 GUI 只在手动扫描时保存一次绝对地址，`_ensure_attached()` 只检查 PID。读档或切换关卡通常不会改变 PID，但会重新创建 `GlobalSimulation` 或 `WorldSettlementSimulator`，因此旧版会继续持有失效地址。

2026-08-31 已完成自动重定位改造。依据 IL2CPP 字段布局验证以下活动对象闭环：

```text
WorldSettlementSimulator +0x10 -> GameController
WorldSettlementSimulator +0x18 -> GlobalSimulation
GameController +0x48             -> GlobalSimulation
GlobalSimulation +0x50           -> WorldSettlementSimulator
GlobalSimulation +0xE8           -> GameController
GameController +0x10             -> Unity 原生对象 m_CachedPtr（必须非零）
GameController +0x100            -> hasSetup（必须为 true）
```

处理流程：

1. 修改器启动后自动连接，不要求先点“扫描并连接”；
2. 每 `0.5` 秒只读验证活动对象和全部资源类型；
3. 同一 `GameController` 下读档或切关时，沿对象闭环直接取得新的定居点和资源地址；
4. 游戏重启或旧 `GameController` 销毁时，沿 `GameAssembly.dll` 中确认的稳定静态根取得新对象；
5. 完整扫描不再自动执行，只保留为“完整扫描重新定位”按钮的人工诊断兜底；
6. 重新定位期间，读取、设置和持续锁定都在同一个互斥锁后等待，不会向旧地址写入；
7. 临时未找到关卡时保留持续锁定选项，后台重连成功后继续，而不是要求用户手动扫描。

2026-09-06 进一步反汇编当前 `GameAssembly.dll` 后，确认可使用以下跨场景稳定链：

```text
GameAssembly.dll + 0x3D13B90 -> SteamManager Il2CppClass
Il2CppClass + 0xB8            -> static_fields
static_fields + 0x8           -> SteamManager.s_instance
SteamManager + 0x50           -> SteamLaunchHandler
SteamLaunchHandler + 0x28     -> scenarioLauncher / 当前 GameController
GameController + 0x48         -> GlobalSimulation
GlobalSimulation + 0x50       -> WorldSettlementSimulator
```

`SteamManager.Awake()` 会把单例对象设为 `DontDestroyOnLoad`；`GameController.SetUpGame()` 在
每次关卡完成初始化时把当前 `GameController` 写入 `scenarioLauncher`。修改器因此不再等待
8 秒或自动搜索附近/全部内存，而是每 `0.5` 秒直接读取这条链。根指针尚未发布时只等待下一
次轮询，发布后通常在 `0–0.5` 秒内重连。取得候选后仍完整核对活动对象闭环、`hasSetup`、
Unity 原生对象指针和全部资源类型，重新定位期间仍不向旧地址写入。

相关文件：

```text
G:\Codex_mmx\after_inc_trainer\memory_scan.py
G:\Codex_mmx\after_inc_trainer\trainer_gui.py
G:\Codex_mmx\after_inc_trainer\tests\test_auto_rebind.py
G:\Codex_mmx\after_inc_trainer\tests\test_trainer_connection.py
```

自动连接相关测试现覆盖活动结构验证、稳定静态根解析、销毁对象拒绝、同进程新关卡跟随、
切关等待、稳定根快速重绑定、进程重启和人工完整扫描兜底，全部通过。最终测试数与打包校验见下一节。

```text
G:\Codex_mmx\after_inc_trainer\dist\AfterIncRevivalTrainer_CN.exe
SHA-256: 见 7.14 节的最新构建
```

本轮修改时游戏进程未运行，因此尚需一次实际“读档”和一次“切换关卡”验收；自动重定位路径已通过模拟对象替换测试，验收时不应手动点击重新定位。

### 7.14 玩家战士快速移动

2026-08-31 已完成“战士快速移动”。IL2CPP 元数据与原生代码确认：

```text
GlobalSimulation.soldiers                    +0x20 -> MovingSoldierManager
MovingSoldierManager.soldiers                +0x10 -> List<MovingSoldier>
MovingSoldier.currentZone                    +0x30
MovingSoldier.fromZone                       +0x38
MovingSoldier.turnsToArrival                 +0x78
MovingSoldier.maxTurnsToArrival              +0x84
MovingSoldier.isDead                         +0x8C
MovingSoldier.currentState                   +0xAC
MovingSoldier.design                         +0xB8
MovingSoldierDesign.soldier                  +0x10
```

`MovingSoldierDesign.Simulate()` 对移动计时器每次减 `1.0`，并且只在结果恰好等于
`0.0` 时调用 `MovingSoldier.OnArrival()`。因此实现没有把计时器直接写成 `0`，而是只把
大于一回合的有效行程缩短为 `1.0`，让下一次正常推进负责触发完整到达流程。

安全限制：

1. 只沿活动 `GlobalSimulation.soldiers` 读取玩家战士管理器，不扫描所有战士对象，也不访问敌军集合；
2. 校验管理器对活动 `GlobalSimulation` 和 `GameController` 的反向引用；
3. 校验 IL2CPP `List<T>` 大小、容量、对象对齐、类指针及 `design -> soldier` 反向引用；
4. 只选择未死亡、起点与终点不同、计时器为有限整数且 `turnsToArrival > 1` 的对象；
5. 写入前再次核对计时器、区域、死亡标志和设计对象，状态变化时取消整批并自动重试；
6. 每次只写 `turnsToArrival` 的 4 字节 `float32`，逐项读回验证；失败时回滚本批已经写过的项目；
7. GUI 开关每 `800 ms` 检查一次，因此勾选后新发起的后续移动也会自动缩短。

自动测试现共 `8` 项，新增覆盖玩家列表选择、非移动/死亡/可疑计时器拒绝，以及受检写入
`5.0 -> 1.0`。本轮游戏进程未运行，必须实机进行最后验收：发起一次两回合以上的玩家
战士移动，勾选功能并推进一次，确认正常触发到达；同时观察敌军没有被加速。

最新打包产物：

```text
G:\Codex_mmx\after_inc_trainer\dist\AfterIncRevivalTrainer_CN.exe
大小：21,628,307 字节
SHA-256：280B6530263C0B7F1ED52848198CABEFD4B0FCED480BF1C1811F88F213594783
```

打包使用 `G:\Codex_mmx\2026-08-17\.venv`，并已确认分析清单包含 `numpy`；不要用缺少
`numpy` 的系统 Python 重打包，否则完整结构扫描会在游戏重启后的兜底路径中失效。

## 8. 用户难以精确控制资源时怎么办

不需要事先控制资源一定变成某个指定数值。扫描真正需要的是：

1. 变化前的准确显示值；
2. 变化后的准确显示值；
3. 两次读数之间游戏进程没有重启；
4. 在执行扫描时暂停游戏，让数值稳定。

资源自然变化也完全可以用于筛选。例如：

- 燃料自然从 5 变为 4；
- 水自然从 0 变为 1；
- 多种资源在同一个月同时变化；
- 建筑消耗使木材从 2 变为 0；
- 事件使权威从 51 变为其他值。

只要变化后截一张能看清全部资源的图，就可以按最终显示值分别筛选。多项资源同时变化不会让候选混在一起，因为每个项目使用独立的候选集合。

### 8.1 最推荐的操作方式

1. 保持游戏当前进程不关闭；
2. 完成一次正常行动或让时间推进；
3. 不要求控制最终数值；
4. 数值变化后立刻暂停；
5. 打开资源概览；
6. 截图全部资源、顶部人力和权威；
7. 根据截图中的最终值执行下一次精确筛选。

### 8.2 如果变化太快

如果数值在扫描的几十秒内还会继续变化，应先暂停游戏再启动扫描。首次全内存扫描大约需要 20–50 秒；候选筛选通常只需要数秒到十几秒。

### 8.3 如果不知道准确值

当前扫描器主要支持“等于新精确值”筛选。后续可增加以下关系筛选模式：

```text
changed      当前值与上次不同
unchanged    当前值与上次相同
increased    当前值比上次大
decreased    当前值比上次小
```

但关系筛选需要在每轮保存候选地址对应的原始数值，而当前候选文件只保存了地址。若截图可以看清新值，继续使用精确值筛选更可靠，也更容易排除误匹配。

## 9. 历史分析顺序与当前实机验收

步骤 A 到 E 保留为早期定位过程记录；相关资源已由 IL2CPP 对象结构确认，不再按绝对地址
继续筛选。当前仍需执行的是步骤 F 的实机验收。

### 步骤 A：确认燃料唯一候选

第三次截图中燃料仍为 5，唯一浮点候选继续保持，没有被排除。下一步仍需等待燃料从 5 自然变成任何其他值。变化后暂停并截图，然后：

1. 从 `build_24931318_refine_01/snapshot.json` 继续筛选燃料；
2. 检查唯一地址 `0x000002332264CAD8` 是否变成截图中的新燃料值；
3. 若同步变化，将其标记为“已确认一次”；
4. 最好再经历第三次变化确认，避免它只是显示缓存。

### 步骤 B：继续筛选水

水已经经历 `1 → 0 → 1 → 1 → 1 → 2 → 1`。之前整数和浮点各一个的候选在最后一次变化时全部归零，已证实不是稳定主值。不要再从旧水快照继续精确筛选，应转向资源管理器、字段偏移或写入函数定位。

### 步骤 C：筛选人力

人力已经经历 `0 → 1 → 0 → 1 → 3 → 2 → 0`，整数候选归零，两个浮点候选持续同步。下一步不再继续数值筛选，而是备份存档后进行可逆的单地址写入测试，以区分主值和缓存。

### 步骤 D：食物、木材、权威

食物和权威目前还没有发生可用于第二轮筛选的变化；木材已经完成一次变化筛选：

- 食物：已经从 1 变为 0 并保持一轮，当前剩 2,450 个整数候选和 14,200 个浮点候选；可以继续观察变化，但应警惕资源对象重建；
- 木材：已经从 2 变为 1 并保持多轮，当前还剩 165 个整数候选和 17 个浮点候选；可以继续观察变化，但稳定实现仍应依赖资源管理器或特征码；
- 权威：仍为 51，当前仍有 41,926 个整数候选和 2,121 个浮点候选；实际变化后从 `build_24931318_food_authority_refine_02/snapshot.json` 继续。

只要发生自然变化并能从截图中读取准确新值即可，不必刻意控制。

### 步骤 E：耐力

当前两张截图都没有显示耐力。需要进入会显示或消耗耐力的界面，例如行动、探索或其他明确显示耐力成本和剩余值的界面，再进行：

1. 非零耐力首次扫描；
2. 消耗一次耐力；
3. 暂停并按新值筛选；
4. 重复一次确认。

不要再把左上角的人力当作耐力。

### 步骤 F：士兵快速移动

该功能已按 7.14 节实现。当前不再进行数值搜索，也不把剩余回合写成 0。下一步仅做实机验收：

1. 启动游戏并进入有玩家战士的关卡；
2. 发起一次至少需要 2 回合的移动；
3. 勾选 GUI 中的“战士快速移动”；
4. 等状态显示“已加速 1 名”，然后正常推进一次；
5. 确认玩家战士正常到达并触发目标地点逻辑；
6. 同时观察敌军没有被加速；
7. 再发起一次移动，确认开关无需重复勾选即可继续生效。

## 10. 从候选地址到稳定修改器

即使确认了燃料绝对地址，直接把该地址硬编码进修改器仍然不可靠。游戏重启后堆地址通常会改变。

正确流程：

1. 确认真实数值地址；
2. 找到引用该地址的对象；
3. 识别对象的字段偏移；
4. 找到稳定的根对象指针、静态字段或管理器实例；
5. 如果指针链仍不稳定，定位写入该字段的 `GameAssembly.dll` 指令；
6. 对指令附近生成 AOB 特征码；
7. 每次启动时扫描特征码并计算字段地址；
8. 校验游戏 Build ID 或 `GameAssembly.dll` 哈希；
9. 校验失败时拒绝写入，避免更新后破坏游戏状态。

游戏重启以后：

- PID 会变化；
- `0x000002332264CAD8` 这类绝对地址大概率会失效；
- 现有候选快照通常不能直接跨进程继续筛选；
- 已发现的字段偏移、指针链和特征码才是可复用成果。

## 11. 修改器界面设计基线（已实现）

第一版可用 Windows 自带的 64 位 .NET Framework C# 编译器生成，无需安装完整 .NET SDK。

本机可用编译器：

```text
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe
```

建议界面：

```text
After Inc: Revival 简易修改器

游戏状态：已连接 / 未连接
游戏构建：24931318 / 不支持

[ ] 锁定耐力

食物  [  数值  ] [设置]
水    [  数值  ] [设置]
木材  [  数值  ] [设置]
燃料  [  数值  ] [设置]
权威  [  数值  ] [设置]

[ ] 士兵快速移动

提示：仅支持单机，修改前请备份存档。
```

实现原则：

- 64 位进程；
- 自动寻找 `After Inc. Revival.exe`；
- 默认只读连接；
- 只有用户点击设置或勾选功能后才申请写权限；
- 不联网；
- 不加壳；
- 不混淆；
- 保留源码；
- 显示支持的 Build ID 和 DLL 哈希；
- 地址或特征码校验失败时停止操作。

## 12. 可能的误区

1. **左上角 0/1 是人力，不是耐力。**
2. 资源卡片中的 `1/6` 表示当前量 1、容量 6；搜索当前量，不搜索容量。
3. 显示为整数不代表内部一定是整数，因此同时搜索 `int32` 和 `float32`。
4. 某地址只匹配一次变化仍可能是 UI 缓存，需要第二次或第三次变化确认。
5. 不要因为燃料只有一个浮点候选就立即写入。
6. 游戏更新或重启后不要继续使用旧绝对地址。
7. “瞬间建造”“无负面事件”等逻辑修改容易破坏任务，不属于第一版目标。
8. 扫描时暂停游戏；变化过程可以不受控制，但变化后的准确读数必须可见。

## 13. 恢复工作时的检查清单

继续项目前按顺序检查：

1. 阅读本文档；
2. 检查游戏是否仍为 Build `24931318`；
3. 计算或核对 `GameAssembly.dll` SHA-256；
4. 运行 `python -m unittest discover -s tests -v`，应通过 13 项；
5. 启动最新 `dist\AfterIncRevivalTrainer_CN.exe`，不要先手动定位；
6. 实测一次读档和一次切关，确认自动重新连接；
7. 按 7.14 节实测战士快速移动，并确认敌军不受影响；
8. 游戏更新后先停止写入，重新核对 IL2CPP 字段和原生逻辑；
9. 在任何新的写入测试前备份存档。

## 14. 当前结论

基础资源、权威、目标耐心、自动重定位和玩家战士快速移动均已进入 GUI。实现使用
IL2CPP 活动对象闭环与字段布局，不再依赖某次进程中的绝对地址。战士移动功能只处理玩家
`MovingSoldierManager.soldiers`，把大于 1 的有效行程缩短到 1 回合，并保留游戏原生
`OnArrival()` 到达路径。

代码级验证现有 13 项自动测试全部通过。由于本轮游戏进程未运行，当前唯一剩余工作是实机
验收：读档、切关、玩家战士到达、后续移动持续生效，以及敌军不受影响。验收通过后即可把
Steam Build `24931318` 的这一版标记为完成；任何游戏更新都必须重新验证后再写内存。
