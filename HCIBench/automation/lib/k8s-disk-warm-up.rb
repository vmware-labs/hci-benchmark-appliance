#!/usr/bin/ruby
# k8s-disk-warm-up.rb
# Fills all PVC block devices across all hcibench pods before testing.
# Runs fio sequentially per-PVC within each pod, all pods in parallel.
# Mirrors disk-warm-up.rb for the VM path.

require_relative "rvc-util.rb"
require_relative "util.rb"
require 'shellwords'

KUBECTL = "KUBECONFIG=#{Shellwords.escape($k8s_kubeconfig)} kubectl"
NS      = Shellwords.escape($k8s_namespace)

@status_log = "#{$log_path}/test-status.log"
@log_file   = "#{$log_path}/k8s-disk-warm-up.log"

# Mirror the method/thread mapping from disk-warm-up.rb (VM path):
#   ZERO   -> fio_zero          2 threads  (sequential write, zero-filled buffers)
#   RANDOM -> dd_openssl equiv  4 threads  (incompressible/random data)
#   FIO    -> fio_random_dedupe 2 threads  (dedupe-pattern data)
case $warm_up_disk_before_testing
when 'ZERO'
  fio_extra  = "--zero_buffers=1"
  nb_threads = 2
when 'RANDOM'
  fio_extra  = "--refill_buffers=1 --buffer_compress_percentage=0"
  nb_threads = 4
when 'FIO'
  fio_extra  = "--dedupe_percentage=50 --refill_buffers=1"
  nb_threads = 2
else
  exit(0)
end

def k8s_exec(pod, cmd)
  system("#{KUBECTL} exec -n #{NS} #{pod} -- sh -c #{Shellwords.escape(cmd)} >> #{@log_file} 2>&1")
end

def pod_names
  out = `#{KUBECTL} get pods -n #{NS} -l app=hcibench --no-headers \
    -o custom-columns=NAME:.metadata.name 2>&1`
  out.split("\n").map(&:strip).reject(&:empty?)
end

pods = pod_names
total = pods.size * $number_data_disk
done  = 0

puts "Disk Preparation Started: 0/#{total} PVCs", @status_log

threads = pods.map do |pod|
  Thread.new do
    (0...$number_data_disk).each do |i|
      dev = "/mnt/pvc#{i}"
      fio_cmd = "fio --name=warmup --filename=#{dev} --rw=write " \
                "--bs=4M --iodepth=8 --direct=1 --numjobs=#{nb_threads} --loops=1 #{fio_extra}"
      puts "  [#{pod}] Filling #{dev} (#{$warm_up_disk_before_testing})", @log_file
      k8s_exec(pod, fio_cmd)
      done += 1
      puts "Disk Preparation Progress: #{done}/#{total} PVCs", @status_log
    end
  end
end

threads.each(&:join)
puts "Disk Preparation Finished: #{total}/#{total} PVCs", @status_log
