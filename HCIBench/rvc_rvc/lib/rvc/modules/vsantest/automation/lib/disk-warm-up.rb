#! /usr/bin/ruby

require_relative "util.rb"
require_relative "rvc-util.rb"

@vm_size = 0
@test_status_log = "#{$log_path}/test-status.log"

def check_status
  while true
    vms_finish = `grep ^Time /opt/automation/logs/*diskinit.log | wc -l`.to_i
    if vms_finish < @vm_size
      `sed -i '$d' #{@test_status_log}`
      puts "Disk Preparation Finished: #{vms_finish}/#{@vm_size} VMs", @test_status_log
      sleep 60
    else
      `sed -i '$d' #{@test_status_log}`
      puts "Disk Preparation Finished: #{vms_finish}/#{@vm_size} VMs", @test_status_log
      sleep 5
      break
    end
  end
  abort "Exiting checking"
end

def run_cmd(vm, method, nb_threads)
  # Warm up disks concurrently
  # By default diskinit will run 1 thread per CPU which is reasonably optimal for most cases.
  # This can v
  # diskinit <method> [--result FILE] [--logfile FILE] [--threads COUNT]A
  #
  #   method: The initialization method (zero, random, openssl, fio)
  #
  #   result: Path for output yaml file that will contain the results of the initialization. This file is
  #           updated as the initialization processes the disks.
  #
  #   logfile: Path to output log file.
  #
  #   threads: Number of concurrent threads. Defaults to 1 per VM vCPU.
  #
  #`$SSHPASS_COMMAND ssh $IDENTIFY_ARG $IDENTIFY_FILE #{vm} 'diskinit #{method} --result diskinit.yaml --logfile diskinit.log' > #{$log_path}/#{vm}-diskinit.log`
  `$SSHPASS_COMMAND ssh $IDENTIFY_ARG $IDENTIFY_FILE #{vm} 'diskinit #{method} --threads=#{nb_threads} --result diskinit.yaml --logfile diskinit.log' > #{$log_path}/#{vm}-diskinit.log`
end

case (ARGV[0] || $warm_up_disk_before_testing)
when 'ZERO'
  method = 'fio_zero'
  nb_threads = 2
when 'RANDOM'
  method = 'dd_openssl'
  nb_threads = 4
when 'FIO'
  method = 'fio_random_dedupe'
  nb_threads = 2
else
  p 'Need to specify a valid disk initialization method: ZERO, RANDOM, or FIO'
  exit(255)
end

threads = []
vms = _ssh_to_vm
@vm_size = vms.size

puts "Disk Preparation Finished: 0/#{@vm_size} VMs", @test_status_log
Thread.start { check_status }
vms.each do |s|
  s.strip!
  threads << Thread.new{run_cmd(s, method, nb_threads)}
  break if $multiwriter 
end
threads.each(&:join)
`sed -i '$d' #{@test_status_log}`
puts "Disk Preparation Finished: #{@vm_size}/#{@vm_size} VMs", @test_status_log
