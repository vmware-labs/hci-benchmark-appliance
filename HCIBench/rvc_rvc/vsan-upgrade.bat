@echo off
setlocal
set RVC_ARGS=%*

pushd "%VMWARE_RVC_HOME%"
"%VMWARE_RUBY_BIN%" -Ilib -Igems\backports-3.1.1\lib -Igems\builder-3.2.0\lib -Igems\highline-1.6.15\lib -Igems\nokogiri-1.8.0-x86-mingw32\lib -Igems\rbvmomi-1.7.0\lib -Igems\terminal-table-1.4.5\lib -Igems\trollop-1.16\lib -Igems\zip-2.0.2\lib lib\rvc\lib\vsan-upgrade-standalone.rb %RVC_ARGS%
popd
