# 修改器版本索引

Steam App ID：**3337140**。当前修改器版本：**26049821.4**；游戏构建：**26049821**。
有内部版本号的版本以版本号和游戏构建命名；早期 EXE 没有内部版本号，以 unversioned、已知游戏构建和哈希区分，不把 Steam App ID 当作修改器版本。

## 当前版 26049821.4

- 默认入口：[../dist/AfterIncRevivalTrainer_CN.exe](../dist/AfterIncRevivalTrainer_CN.exe)。
- [版本说明](26049821.4_game26049821/README.md)：写入校验改为重试 + 抢占归类，消除一次抢占就停全部锁定并弹窗的问题。74 项测试及 GUI 生命周期检查通过。

## 历史版 26049821.3

- 历史入口：26049821.3_game26049821/dist/AfterIncRevivalTrainer_CN.exe。
- [版本说明](26049821.3_game26049821/README.md)：启动日志与自动监控，正常关闭等待后台修改完成。65 项测试及 GUI 生命周期检查通过。

## 历史版 26049821.2

- 历史入口：26049821.2_game26049821/dist/AfterIncRevivalTrainer_CN.exe。
- [修复版说明](26049821.2_game26049821/README.md)：修正远征目标链的两个错误函数重载，59 项测试通过。游戏内结算和存读档仍待验收。

## 历史版 26049821.1（远征扩展存在已知故障，请勿使用）

- 历史入口：26049821.1_game26049821/dist/AfterIncRevivalTrainer_CN.exe。
- [完整版本与适配说明](26049821.1_game26049821/README.md)。
- 原有功能适配游戏 1.0.2.2，56 项测试通过；GUI 构造检查及打包成功。
- 新版实机验证状态见版本说明。

## 历史版 25936576.1

- 历史入口：25936576.1_game25936576/dist/AfterIncRevivalTrainer_CN.exe。
- 原始快照及说明：[25936576.1_game25936576](25936576.1_game25936576/README.md)。
- 已包含资源、耐心、权威、快速移动、队伍及数量保持、远征、随机任务、战士升级机会、武器及小队增强。
- 经验修复已合并；根目录代码与版本快照一致。本次复跑 56 项测试通过。
- EXE SHA-256：`3ae1e5cec152a78835dc45c65b8237dc8a9aeee4b4dc4e1155f2fad88acd6063`。

## 历史应用

以下版本均未写入内部版本号；功能说明沿用整理前记录，未重新实机验证。未知构建继续标为未知。

| 目录 | 游戏构建 | 功能阶段 |
| --- | --- | --- |
| [unversioned_game-unknown_77f33f6d](history/unversioned_game-unknown_77f33f6d/README.md) | -unknown | 随机任务、队伍与战士、紧凑布局（历史功能指纹）。 |
| [unversioned_game-unknown_9229f1f4](history/unversioned_game-unknown_9229f1f4/README.md) | -unknown | 远征刷新、随机任务（历史功能指纹）。 |
| [unversioned_game-unknown_f45e293f](history/unversioned_game-unknown_f45e293f/README.md) | -unknown | 远征刷新、随机任务、探索与建设队伍（历史功能指纹）。 |
| [unversioned_game24931318_7a755576](history/unversioned_game24931318_7a755576/README.md) | 24931318 | 资源、耐心、权威、战士快速移动、远征刷新（历史记录）。 |
| [unversioned_game25936576_5415ee4b](history/unversioned_game25936576_5415ee4b/README.md) | 25936576 | 游戏构建 25936576 适配版；早于随机任务适配修订。 |
| [unversioned_game25936576_6b3030c7](history/unversioned_game25936576_6b3030c7/README.md) | 25936576 | 游戏构建 25936576 随机任务适配版；不含本次原生升级事件修复。 |

原 dist 根入口与 build_25936576_tasks 的 EXE 哈希相同；两份原文件均保留在对应历史目录，根入口副本加 `_default_copy` 后缀。

## 历史源码与开发版

- [3337140_任务扩展版_20261014](3337140_任务扩展版_20261014/README.md)：先前归档的源码，支持构建 25479909 / 25936576。没有内部版本号，保留原目录名。
- [soldier_upgrade_work](../soldier_upgrade_work/README.md)：经验修复前独立开发版，游戏构建 25936576，包含经验 +1、武器、小队、队伍保持；没有内部版本号。源码与 EXE 原位置保留，已由 25936576.1 取代。

整理前后的完整应用 SHA-256 清单在 [docs/history](../docs/history/before_organization_20261015/)。旧说明里的 dist/1..4、build_25936576、build_25936576_tasks 路径均按各历史目录 README 的“原位置”映射查找。
