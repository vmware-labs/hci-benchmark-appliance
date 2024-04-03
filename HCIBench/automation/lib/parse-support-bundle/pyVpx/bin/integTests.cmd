@REM WinXP/Win2k script to start integDriver.py from
@REM VMware Inc, 2006

@if exist "%WROOT%" goto RunMe
@if not exist "%VMTREE%" goto NeedEnv
@if not exist %VMTREE%\bora-winroot goto NeedEnv
@set WROOT=%VMTREE%\bora-winroot
@echo INFO: WROOT has been set to: %WROOT% for the duration of this shell
:RunMe
@set DLOC=integtests.d
@set DRIVER=%DLOC%/integDriver.py
@set OLDPATH=%PATH%
@set PATH=%WROOT%\bin;%WROOT%\python\python-2.4.1-as;%PATH%
python %DRIVER% %1 %2 %3 %4 %5 %6 %7 %8 %9
@set PATH=%OLDPATH%
@set OLDPATH=
@set DRIVER=
@set DLOC=
@exit /B %ERRORLEVEL%
:NeedEnv
@echo "ERROR: set WROOT variable to drive:\need-path-to\bora-winroot"
@exit /B 1
