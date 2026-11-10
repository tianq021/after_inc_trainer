# 修改器 26049821.3

Steam App ID 3337140；游戏构建 26049821（1.0.2.2）。

保留资源、队伍、战士升级与远征功能，以及 26049821.2 的远征重载修复。
新增每次启动独立日志与自动进程/游戏日志监控。正常关闭会停止监控并等待修改线程完成，避免截断游戏恢复步骤。

65 项测试和隐藏 GUI 生命周期检查通过。游戏内结算/存读档仍待实机验收。
启动 dist/AfterIncRevivalTrainer_CN.exe；详细说明见 日志与自动监控说明.md。
构建：python -m PyInstaller --noconfirm --distpath dist --workpath build/package AfterIncRevivalTrainer_CN.spec。
测试：python -m unittest discover -s tests。

EXE SHA-256：fd20a71e500cec0288bcf2354b3eec647358c54c74aa9c6ca0313644320c5893。
