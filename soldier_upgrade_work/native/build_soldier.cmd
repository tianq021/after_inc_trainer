@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b 1
cd /d "%~dp0"
cl /nologo /LD /O2 /GS- /Zl /W4 soldier_upgrade.cpp /link /NODEFAULTLIB /ENTRY:DllMain /OUT:AfterIncSoldierUpgrade.dll
