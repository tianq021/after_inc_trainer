# After Inc: Revival 修改器

当前修改器版本 **26049821.4**，Steam App ID **3337140**，主要对应游戏构建 **26049821**。

本版只改“写入后校验”的容错：写入被游戏抢占时自动重写重读（最多 3 次），持续锁定遇到抢占改为瞬时错误，不再一次失败就停掉全部锁定并弹窗；手动设置只有在连续重试仍失败时才提示暂停后再试。详见 [版本说明](versions/26049821.4_game26049821/README.md)。

## 自动日志

启动即监控，关闭即停止；每次运行在 EXE 旁 logs 中生成独立目录。正常关闭等待正在进行的修改完成。详见 [日志与自动监控说明](docs/日志与自动监控说明.md)。

## 启动

直接运行 [dist/AfterIncRevivalTrainer_CN.exe](dist/AfterIncRevivalTrainer_CN.exe)。默认入口已统一为 26049821.4，文件与版本存档逐字节一致。

经验问题沿用 26049821.3 的修复：通过“升级机会 +1”生成游戏原生升级图标，再由玩家在游戏里选择奖励。详细操作、拒绝码及限制见[当前版本说明](versions/26049821.4_game26049821/README.md)。

## 文件校验

成品 EXE 的 SHA-256 记录在 [SHA256SUMS.txt](SHA256SUMS.txt)：`9f402ca959783f41e986ab37cdd0a016c9fb98508f7628602c580f5029171756`。PowerShell 校验：`Get-FileHash .\dist\AfterIncRevivalTrainer_CN.exe -Algorithm SHA256`。

## 当前功能

- 资源、耐心、权威修改与锁定，战士快速移动。
- 探索与建设队伍增量、队伍数量保持。
- 战士升级机会、武器 +0.25、小队 +0.25。
- 远征日期刷新、随机任务扩展。
- 600×540 三页签界面：资源、队伍与升级、远征与地图。

各功能依照 GameAssembly.dll 精确哈希校验支持范围；战士升级仅支持 26049821。Steam App ID、游戏构建号和修改器版本号是不同概念。

## 文件布局

| 位置 | 用途 |
| --- | --- |
| 根目录 Python 文件、native/、tests/ | 已合并的 26049821.4 当前源码与测试 |
| dist/ | 当前默认应用 |
| versions/26049821.4_game26049821/ | 当前版原始源码、程序及验证资料快照 |
| versions/26049821.3_game26049821/ | 上一版快照，保留原样 |
| versions/history/ | 早期历史应用，每版附功能、游戏号和 SHA-256 |
| versions/3337140_任务扩展版_20261014/ | 先前合并时保留的旧源码，原名称保留 |
| soldier_upgrade_work/ | 经验修复前开发版源码与应用，保留原位置供追溯 |
| docs/history/before_organization_20261015/ | 整理前文档、应用清单和整理后清单 |
| build/、il2cpp_dump/、tools/、scans/、structure_scans/、write_tests/、backups/ | 构建、分析及备份资料，保留原位置 |

完整版本登记见 [versions/README.md](versions/README.md)。根目录其他技术说明及历史复盘保留作背景资料；其中旧路径按版本索引查找，当前状态以本文件及“下一步.txt”为准。

## 开发与打包

使用系统 Python 3.10，在项目根目录执行：

```powershell
python -m unittest discover -s tests
python -m PyInstaller --noconfirm --distpath dist --workpath build/build_26049821_4 AfterIncRevivalTrainer_CN.spec
```

2026-10-24：26049821.4 修正写入后校验的容错（重试 + 抢占归为瞬时错误），74 项测试通过、打包成功。上一版实机验收记录见 [26049821.3 版本说明](versions/26049821.3_game26049821/README.md)；本版仍需在运行中的游戏里复验人力锁定。旧版 25936576.1 完整保留。
