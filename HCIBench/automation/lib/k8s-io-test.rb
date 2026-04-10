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

def run_fio_on_pods(pods, adapted_param, param_name, res_dir)
  pods.map do |pod|
    Thread.new do
      remote_param  = "/tmp/#{param_name}"
      result_remote = "/tmp/#{param_name}-result.json"
      result_local  = "#{res_dir}/#{pod}-k8s-0.json"
      system("#{KUBECTL} cp #{Shellwords.escape(adapted_param)} #{NS}/#{pod}:#{remote_param} >> #{@log_file} 2>&1")
      fio_cmd = "fio #{remote_param} --output-format=json --output=#{result_remote}"
      fio_cmd += " #{duration_var}" unless duration_var.empty?
      puts "  [#{pod}] Running: #{fio_cmd}", @log_file
      system("#{KUBECTL} exec -n #{NS} #{pod} -- sh -c #{Shellwords.escape(fio_cmd)} >> #{@log_file} 2>&1")
      system("#{KUBECTL} cp #{NS}/#{pod}:#{result_remote} #{Shellwords.escape(result_local)} >> #{@log_file} 2>&1")
      puts "  [#{pod}] Results collected to #{result_local}", @log_file
    end
  end
end

if !$vm_groups.empty?
  # Mixed Workload Mode: run each group's param file in parallel against its labeled pods
  time = Time.now.to_i
  puts "Started Testing K8s Mixed Workload Mode (#{$vm_groups.size} groups in parallel)", @status_log

  group_threads = $vm_groups.each_with_index.map do |grp, gi|
    param_name = grp["param_file"].to_s
    src_param  = "#{$self_defined_param_file_path}/#{param_name}"
    item_label = "#{time}-group#{gi}-#{param_name}"
    res_dir    = "#{$output_path_dir}/#{item_label}"
    FileUtils.mkdir_p(res_dir)
    adapted_param = "#{res_dir}/#{param_name}-k8s.cfg"
    adapt_param_file(src_param, adapted_param)

    Thread.new do
      puts "Group #{gi} (#{param_name}): starting...", @status_log
      out, _ = k8s("get pods -n #{NS} -l app=hcibench,hci-group=g#{gi} --no-headers -o custom-columns=NAME:.metadata.name")
      group_pods = out.split("\n").map(&:strip).reject(&:empty?)
      if group_pods.empty?
        puts "[ERROR] No pods found for group #{gi} (label hci-group=g#{gi})", @status_log
        next
      end
      threads = run_fio_on_pods(group_pods, adapted_param, param_name, res_dir)
      threads.each(&:join)

      FileUtils.cp(src_param, "#{res_dir}/fio.cfg")
      `cp #{$basedir}/../conf/k8s-conf.yaml #{res_dir}/hcibench.cfg`
      `sed -i '/username/d;/password/d;/k8s_kubeconfig_content/d;/k8s_kubeconfig_path/d' #{res_dir}/hcibench.cfg`
      resfile = "#{@http_place}/#{$output_path}/#{item_label}-res.txt"
      `ruby #{$k8s_parse_fio_file} '#{res_dir}' > '#{$output_path_dir}'/'#{item_label}-res.txt' | tee -a #{@log_file}`
      puts "Group #{gi} done. Click <a href=\"#{resfile}\" target=\"_blank\">HERE</a> to view the result", @status_log
    end
  end
  group_threads.each(&:join)
  puts "All K8s Group Tests Finished.", @status_log
end

if $vm_groups.empty?
  Dir.entries($self_defined_param_file_path).sort.each do |item|
    next if item == '.' || item == '..' || File.directory?(item)

    time        = Time.now.to_i
    src_param   = "#{$self_defined_param_file_path}/#{item}"
    res_dir     = "#{$output_path_dir}/#{item}-#{time}"
    FileUtils.mkdir_p(res_dir)

    adapted_param = "#{res_dir}/#{item}-k8s.cfg"
    adapt_param_file(src_param, adapted_param)

    puts "Started Testing #{item}", @status_log

    pods = pod_names
    if pods.empty?
      puts "[ERROR] No hcibench pods found in namespace #{$k8s_namespace}", @status_log
      next
    end

    threads = run_fio_on_pods(pods, adapted_param, item, res_dir)
    threads.each(&:join)

    puts "Workload #{item} finished, preparing the results...", @status_log

    FileUtils.cp(src_param, "#{res_dir}/fio.cfg")
    `cp #{$basedir}/../conf/k8s-conf.yaml #{res_dir}/hcibench.cfg`
    `sed -i '/username/d;/password/d;/k8s_kubeconfig_content/d;/k8s_kubeconfig_path/d' #{res_dir}/hcibench.cfg`

    resfile = "#{@http_place}/#{$output_path}/#{item}-#{time}-res.txt"
    cal_result_exe = "ruby #{$k8s_parse_fio_file} '#{res_dir}' > '#{$output_path_dir}'/'#{item}-#{time}-res.txt'"
    `#{cal_result_exe} | tee -a #{@log_file}`

    puts "Done Testing #{item}, Click <a href=\"#{resfile}\" target=\"_blank\">HERE</a> to view the result", @status_log
  end
end
