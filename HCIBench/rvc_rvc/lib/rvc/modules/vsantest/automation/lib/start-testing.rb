#!/usr/bin/ruby
require_relative "rvc-util.rb"

`rm -f #{$log_path}/*.log`

if $easy_run
  load $easyrunfile
else
  load $allinonetestingfile
end
