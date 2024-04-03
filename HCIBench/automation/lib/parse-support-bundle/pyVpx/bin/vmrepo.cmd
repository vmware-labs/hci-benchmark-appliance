@echo off
REM WinXP/Win2k script to start vmrepo.py from
REM VMware Inc, 2006
if exist "%WROOT%" goto RunMe
if not exist "%VMTREE%" goto NeedEnv
if not exist %VMTREE%\bora-winroot goto NeedEnv
set WROOT=%VMTREE%\bora-winroot
echo INFO: WROOT has been set to: %WROOT% for the duration of this shell
:RunMe
set OLDPYPATH=%PYTHONPATH%
set OLDPATH=%PATH%
set PATH=%WROOT%\python\python-2.4.1-as;%WROOT%\bin;%PATH%
set PYTHONPATH=%WROOT%\python\python-2.4.1-as\lib
python vmrepo.py %1 %2 %3 %4 %5 %6 %7 %8 %9
set PATH=%OLDPATH%
set PYTHONPATH=%OLDPYPATH%
set OLDPATH=
set OLDPYPATH=
exit /B %ERRORLEVEL%
:NeedEnv
echo "ERROR: set WROOT variable to drive:\path\bora-winroot"
exit /B 1
