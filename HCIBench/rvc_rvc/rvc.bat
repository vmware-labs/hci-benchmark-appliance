@echo off
setlocal
if "%1"=="" (
  echo Try "--help" or "-h" to view more information about RVC usage.
  echo No argument is specified, connecting to localhost as administrator@vsphere.local
  set RVC_ARGS="administrator@vsphere.local@localhost"
) else (
  set RVC_ARGS=%*
)
if "%VMWARE_RUBY_HOME%"=="" set VMWARE_RUBY_HOME="..\\ruby-2.1.6-p336-x64-mingw32-with-gems"
if "%VMWARE_RUBY_BIN%"=="" set VMWARE_RUBY_BIN="%VMWARE_RUBY_HOME%\\bin\\ruby.exe"
if not "%VMWARE_RVC_HOME%"=="" pushd "%VMWARE_RVC_HOME%"
set GEMS="%VMWARE_RUBY_HOME%\\gems"
<<<<<<< HEAD
"%VMWARE_RUBY_BIN%" -Ilib -I%GEMS%\backports-3.6.5\lib -I%GEMS%\builder-3.2.2\lib -I%GEMS%\highline-1.7.2\lib -I%GEMS%\libxml-ruby-2.8.0\lib -I%GEMS%\mini_portile-0.6.2\lib -I%GEMS%\nokogiri-1.8.0-x64-mingw32\lib -I%GEMS%\terminal-table-1.5.2\lib -I%GEMS%\trollop-2.1.2\lib -I%GEMS%\zip-2.0.2\lib -Igems\rbvmomi-1.7.0\lib bin\rvc %RVC_ARGS%
=======
"%VMWARE_RUBY_BIN%" -Ilib -I%GEMS%\backports-3.11.1\lib -I%GEMS%\builder-3.2.3\lib -I%GEMS%\highline-1.7.8\lib -I%GEMS%\mini_portile2-2.3.0\lib -I%GEMS%\nokogiri-1.8.2-x64-mingw32\lib -I%GEMS%\terminal-table-1.8.0\lib -I%GEMS%\unicode-display_width-1.5.0\lib -I%GEMS%\trollop-2.1.2\lib -I%GEMS%\zip-2.0.2\lib -I%GEMS%\ffi-1.9.10-x64-mingw32\lib -Igems\rbvmomi-1.7.0\lib bin\rvc %RVC_ARGS%
>>>>>>> f21ea97... Add RubyGem dependency unicode/display_width
popd
