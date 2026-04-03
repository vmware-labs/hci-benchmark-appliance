#!/usr/bin/ruby
require_relative "rvc-util.rb"

`rm -f #{$log_path}/*.log`

if $test_target == "k8s"
  load "#{$basedir}/all-in-one-k8s-testing.rb"
elsif $easy_run
  load $easyrunfile
else
  load $allinonetestingfile
end
