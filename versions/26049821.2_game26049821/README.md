# 修改器 26049821.2 — 远征扩展重载修复

Steam App ID：3337140；游戏构建：26049821；游戏版本：1.0.2.2；2026-10-19。
启动 dist/AfterIncRevivalTrainer_CN.exe。保留资源锁定、队伍、战士升级、远征日期与添加地图等原有功能。

修复 26049821.1 将两个同名方法匹配到错误重载的问题：
- ObjectiveChain 无参构造：0x9850E0（错误复制构造）改为 0x985060。
- ObjectiveChain.Add(Generator)：0x984700（错误集合重载）改为 0x984900。

用户报告点击胜利气泡后存档报错；现场首次异常在结算经验时复制目标链，随后 SaveMeta 读取失败。现场保存在 ../../incidents/20261019-victory-save-error。
本次修正地址，不自动修复已经生成的问题地图或存档。先退出旧修改器并重启游戏，确保旧 DLL 已卸载。使用独立测试档验证新增 1 张地图、保存读取、胜利结算、重启后的读取，再验证 5 张地图。

验证：59 项自动测试全部通过。新增测试加载实际编译的映射 DLL，对 3 个构建、6 个原生方法逐一比较完整函数签名；回填旧版两个错误地址时准确产生 2 个测试失败。测试 DLL 不打包。PyInstaller 构建成功。仍待游戏内结算和存读档验收，不把自动测试视为实机验收。

原生构建：native/build.cmd；签名测试 DLL：native/build_task_test.cmd。
测试：python -m unittest discover -s tests -v。签名测试依赖项目 il2cpp_dump 中现有三个构建的 script.json。
打包：python -m PyInstaller --noconfirm --distpath dist --workpath build AfterIncRevivalTrainer_CN.spec。
EXE SHA-256：73990d848f989d3e85696ae34d878b53d8b91e20133a826b13866ff5b6dcb9fd。
