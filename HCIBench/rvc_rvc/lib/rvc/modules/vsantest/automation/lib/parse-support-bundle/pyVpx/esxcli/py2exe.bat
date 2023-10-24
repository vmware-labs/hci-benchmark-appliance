setlocal
@FOR %%i in (obj beta opt) DO (
   @if EXIST "..\..\..\build\build\LIBRARIES\vmodl\generic\%%i" (
      @set PYVMOMIPATH=..\..\..\build\build\LIBRARIES\vmodl\generic\%%i
   )
)
@if NOT EXIST "%PYVMOMIPATH%" (
   echo "Must build pyVmomi first"
   goto exit
)
echo "Using pyVmomi in %PYVMOMIPATH%"
set PYVIMPATH=..\
set PYTHONLIBPATH=%TCROOT%\win32\lxml-2.2.8\lib\python2.6\site-packages;%TCROOT%\win32\pyopenssl-0.13\Lib\python2.6\site-packages
@set PYTHONPATH=%PYTHONPATH%;%PYVMOMIPATH%;%PYVIMPATH%;%PYTHONLIBPATH%
@if "%TCROOT%"=="" (
   if NOT EXIST "c:\toolchain" (
      echo "Must have TCROOT defined"
      goto exit
   )
   set TCROOT=c:\toolchain
)
set PYTHONEXE=%TCROOT%\win32\python-2.6.1\python.exe
@if NOT EXIST "%PYTHONEXE%" (
   echo "Cannot find %PYTHONEXE%"
   goto exit
)
%PYTHONEXE% setup.py py2exe
echo n | comp dist package\win32
:exit
