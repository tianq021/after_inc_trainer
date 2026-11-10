@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b 1
cd /d "%~dp0"

rem action==1 now calls the game's native upgrade event, so the source needs SEH
rem (__try/__except). MSVC emits a call to __C_specific_handler for that. This
rem machine has no Windows SDK, so the handler is imported straight from ntdll.dll
rem (which exports it) through an import library generated here. The DLL keeps its
rem /NODEFAULTLIB layout: no CRT, and ntdll is always present in the target.
> ntdll_seh.def echo LIBRARY ntdll.dll
>>ntdll_seh.def echo EXPORTS
>>ntdll_seh.def echo     __C_specific_handler
lib /nologo /def:ntdll_seh.def /out:ntdll_seh.lib /machine:x64
if errorlevel 1 exit /b 1

cl /nologo /LD /O2 /GS- /Zl /W4 soldier_upgrade.cpp /link /NODEFAULTLIB /ENTRY:DllMain /OUT:AfterIncSoldierUpgrade.dll "%~dp0ntdll_seh.lib"
