#!/usr/bin/ruby
require_relative "rvc-util.rb"
require_relative "util.rb"
vms = []

@folder_path_escape = _get_folder_path_escape[0]
 `rvc #{$vc_rvc} --path #{@folder_path_escape} -c "vm.ip #{$vm_prefix}-*" -c 'exit' -q`.split("\n").each do |vm|
 vms << vm.split(":")[0]
end

threads = []
vms.each do |vm|
  threads << Thread.new{`rvc #{$vc_rvc} --path #{@folder_path_escape} -c "snapshot.remove -r #{vm}/snapshots/*" -c "exit"`}
end

threads.each(&:join)
