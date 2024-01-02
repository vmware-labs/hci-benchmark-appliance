#!/usr/bin/ruby
require_relative "/opt/automation/lib/rvc-util.rb"
require_relative "/opt/automation/lib/util.rb"
vms = []
snapshots = ARGV[0].to_i
waittime = ARGV[1].to_i
puts snapshots
puts waittime

@folder_path_escape = _get_folder_path_escape[0]
 `rvc #{$vc_rvc} --path #{@folder_path_escape} -c "vm.ip #{$vm_prefix}-*" -c 'exit' -q`.split("\n").each do |vm|
 vms << vm.split(":")[0]
end

threads = []
for i in 1..snapshots
  vms.each do |vm|
    threads << Thread.new{`rvc #{$vc_rvc} --path #{@folder_path_escape} -c "snapshot.create --no-memory #{vm}" -c "exit"`}
  end

  threads.each(&:join)
  sleep(waittime)
end
