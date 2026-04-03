#!/usr/bin/ruby
# k8s-io-test.rb
# Drives fio tests on K8s pods.  Mirrors the role of io-test.rb for the VM path.
#
# For each fio param file:
#   1. Adapt the param file: replace raw block device paths (/dev/sda …) with
#      filesystem paths (/mnt/pvc0/fiotest …) suitable for PVC-mounted volumes.
#   2. Copy the adapted param file to every pod via `kubectl cp`.
#   3. Execute fio on every pod in parallel; collect JSON output.
#   4. Parse results with parseK8sFioResult.rb.

require 'yaml'
require 'fileutils'
require 'shellwords'
require_relative "rvc-util.rb"
require_relative "util.rb"

KUBECTL = "KUBECONFIG=#{Shellwords.escape($k8s_kubeconfig)} kubectl"
NS      = Shellwords.escape($k8s_namespace)

@status_log = "#{$log_path}/test-status.log"
@log_file   = "#{$log_path}/k8s-io-test.log"
@ip_Address = _get_ip_addr
@ip_url     = @ip_Address
@ip_url     = "[#{@ip_Address}]" if defined?(IPAddress) && IPAddress.valid_ipv6?(@ip_Address)
@http_place = "https://#{@ip_url}:443/output/results"

def k8s(cmd)
  out = `#{KUBECTL} #{cmd} 2>&1`
  [out.chomp, $?.exitstatus]
end

# Build the list of running hcibench pods
def pod_names
  out, _ = k8s("get pods -n #{NS} -l app=hcibench --no-headers -o custom-columns=NAME:.metadata.name")
  out.split("\n").map(&:strip).reject(&:empty?)
end

# Rewrite a fio param file so that raw block devices become filesystem paths.
# HCIBench param files use sda as the first data disk (block device convention).
# For K8s, PVCs are exposed as raw block devices at /mnt/pvc0, /mnt/pvc1, etc.
# via volumeDevices, so fio targets them directly as block devices.
# /dev/sda  → /mnt/pvc0
# /dev/sdb  → /mnt/pvc1
# etc.
def adapt_param_file(src_path, dst_path)
  content = File.read(src_path)
  ('a'..'z').each_with_index do |letter, idx|
    content = content.gsub("/dev/sd#{letter}", "/mnt/pvc#{idx}")
    content = content.gsub("/dev/vd#{letter}", "/mnt/pvc#{idx}")
  end
  # Also handle /dev/sda1 … patterns
  (0..45).each do |idx|
    content = content.gsub("/dev/disk#{idx}", "/mnt/pvc#{idx}/fiotest")
  end
  File.write(dst_path, content)
end

if !$self_defined_param_file_path || !File.directory?($self_defined_param_file_path)
  $self_defined_param_file_path = "/opt/automation/fio-param-files"
end

duration_var = ""
if $testing_duration && $testing_duration.is_a?(Integer)
  duration_var = "--runtime=#{$testing_duration} --time_based=1"
end

Dir.entries($self_defined_param_file_path).sort.each do |item|
  next if item == '.' || item == '..' || File.directory?(item)

  time        = Time.now.to_i
  src_param   = "#{$self_defined_param_file_path}/#{item}"
  res_dir     = "#{$output_path_dir}/#{item}-#{time}"
  FileUtils.mkdir_p(res_dir)

  # Adapt param file for filesystem-based PVC paths
  adapted_param = "#{res_dir}/#{item}-k8s.cfg"
  adapt_param_file(src_param, adapted_param)

  puts "Started Testing #{item}", @status_log

  pods = pod_names
  if pods.empty?
    puts "[ERROR] No hcibench pods found in namespace #{$k8s_namespace}", @status_log
    next
  end

  # --- Run fio on every pod in parallel ---
  threads = pods.map do |pod|
    Thread.new do
      remote_param = "/tmp/#{item}"
      result_remote = "/tmp/#{item}-result.json"
      result_local  = "#{res_dir}/#{pod}-k8s-0.json"

      # Copy adapted param file into the pod
      system("#{KUBECTL} cp #{Shellwords.escape(adapted_param)} #{NS}/#{pod}:#{remote_param} >> #{@log_file} 2>&1")

      # Run fio
      fio_cmd = "fio #{remote_param} --output-format=json --output=#{result_remote}"
      fio_cmd += " #{duration_var}" unless duration_var.empty?
      puts "  [#{pod}] Running: #{fio_cmd}", @log_file
      system("#{KUBECTL} exec -n #{NS} #{pod} -- sh -c #{Shellwords.escape(fio_cmd)} >> #{@log_file} 2>&1")

      # Collect results
      system("#{KUBECTL} cp #{NS}/#{pod}:#{result_remote} #{Shellwords.escape(result_local)} >> #{@log_file} 2>&1")
      puts "  [#{pod}] Results collected to #{result_local}", @log_file
    end
  end
  threads.each(&:join)

  puts "Workload #{item} finished, preparing the results...", @status_log

  # Copy original (unadapted) param file as the canonical config record
  FileUtils.cp(src_param, "#{res_dir}/fio.cfg")
  `cp #{$basedir}/../conf/k8s-conf.yaml #{res_dir}/hcibench.cfg`
  `sed -i '/username/d' #{res_dir}/hcibench.cfg`
  `sed -i '/password/d' #{res_dir}/hcibench.cfg`

  resfile = "#{@http_place}/#{$output_path}/#{item}-#{time}-res.txt"
  cal_result_exe = "ruby #{$k8s_parse_fio_file} '#{res_dir}' > '#{$output_path_dir}'/'#{item}-#{time}-res.txt'"

  threads2 = []
  threads2 << Thread.new { `#{cal_result_exe} | tee -a #{@log_file}` }
  threads2.each(&:join)

  puts "Done Testing #{item}, Click <a href=\"#{resfile}\" target=\"_blank\">HERE</a> to view the result", @status_log
end
