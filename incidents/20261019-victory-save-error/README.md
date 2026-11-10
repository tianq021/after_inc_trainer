# 2026-10-19 胜利气泡后存档错误

用户操作：锁定人力、增加队伍、添加 5 个远征地图，点击最终胜利气泡后提示存档损坏。当前仅授权监控及诊断；未修改游戏、修改器或恢复存档。

## 已确认
- 修改器 26049821.1 的 task_extension.cpp 新构建映射存在两个错误重载：
  - ObjectiveChain 无参构造应为 0x985060，当前错误使用复制构造 0x9850E0。
  - ObjectiveChain.Add(Generator) 应为 0x984900，当前错误使用 Add(IEnumerable<Generator>) 0x984700。
- 来自同名方法按 Name 建字典造成的重载覆盖，之前 56 项模拟测试未覆盖实际调用签名。
- Player-prev.log 第 30259 行首次 NullReferenceException：ObjectiveChain 复制构造 -> Campaign.CalculateXpEarned -> LevelBuilder.CalculateXpGains -> ScoreCard -> EndGame -> ObjectiveCompleteGameEnd。
- 后续 FindBuilderForIdentAndCampaign -> SaveMeta.Serialize -> TryCreateNamedSave 报 quicksave.afterincsave 的 SaveMeta 损坏。
- 此证据强烈指向远征扩展，但尚未复现隔离、修复验证，也未判定所有存档均损坏。人力/队伍未有对应因果证据。

## 现场
- 游戏 PID 41108，2026-10-19 21:57:47 启动；修改器 PID 11120 / 32156（父子进程），均有响应。
- 沙箱内进程枚举不可见；监控已在沙箱外执行只读查询。
- 添加地图记录 tasks-1792417903642251800.json：count=5，原游戏 PID 23952，构建 26049821。
- 添加前备份 C:/Users/hp/AppData/Local/AfterIncTrainer/backups/20261019-215143-before-tasks。未验证其可恢复性。
- 本目录 Player.log、Player-prev.log、trainer_logs、steam_snapshot 为采集现场副本，复制正在运行的存档非原子快照。
- monitor.py 后台只读监控进程 CPU/内存及增量 Player.log，运行 30 分钟，monitor.jsonl / live_player.log 为输出。创建 STOP 文件可提前停止。后台记录不会自动触发聊天通知。

后续修复须按用户指示进行，先保留当前存档与备份，修复重载匹配并补充签名验证，再在隔离存档中验证结算和存读档。
