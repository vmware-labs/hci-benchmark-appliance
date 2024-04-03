@echo on
setlocal

if "%TCROOT%" == "" set TCROOT=\\build-toolchain\toolchain
if "%BUILDTYPE%" == "" set BUILDTYPE=obj
if "%VMTREE%" == "" set VMTREE=%CD%

set BLDLOC=%VMTREE%\build\build\LIBRARIES\vmodl\generic\%BUILDTYPE%;%VMTREE%\build\scons\build\vmodl\%BUILDTYPE%\generic
set MODULELOC=%VMTREE%\vim\py;%VMTREE%\vim\py\pyJack;%VMTREE%\vim\py\stresstests\lib;%VMTREE%\vim\py\stresstests\opLib;%VMTREE%\vim
set PYTHONPATH=%PYTHONPATH%;%BLDLOC%;%MODULELOC%
set PYLINTRC=%VMTREE%\vim\py\pylintrc

%TCROOT%\win32\python-2.5\python.exe %*
