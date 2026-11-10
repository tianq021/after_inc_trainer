@echo off
rem Build the native upgrade test DLL. Same /NODEFAULTLIB layout as the shipped
rem extension, plus /DTRAINER_TEST so soldier_upgrade.cpp routes every game
rem address through testResolve() in native_upgrade_test.cpp.
rem
rem The test DLL is a development artifact only: AfterIncRevivalTrainer_CN.spec
rem lists the shipped binaries explicitly, so it is never bundled into the EXE.
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b 1
cd /d "%~dp0"

rem See build_soldier.cmd: this machine has no Windows SDK, and SEH needs
rem __C_specific_handler, which ntdll.dll exports.
> ntdll_seh.def echo LIBRARY ntdll.dll
>>ntdll_seh.def echo EXPORTS
>>ntdll_seh.def echo     __C_specific_handler
lib /nologo /def:ntdll_seh.def /out:ntdll_seh.lib /machine:x64
if errorlevel 1 exit /b 1

cl /nologo /LD /O2 /GS- /Zl /W4 /DTRAINER_TEST soldier_upgrade.cpp native_upgrade_test.cpp /link /NODEFAULTLIB /ENTRY:DllMain /OUT:AfterIncSoldierUpgradeTest.dll "%~dp0ntdll_seh.lib"
