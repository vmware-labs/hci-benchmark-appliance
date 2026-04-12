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

KUBECTL = "KUBECONFIG=#{Shellwords.escape($k8s_kubeconfig)} kubectl" unless defined?(KUBECTL)
NS      = Shellwords.escape($k8s_namespace) unless defined?(NS)

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

$k8s_duration_var = ""
if $testing_duration && $testing_duration.is_a?(Integer)
  $k8s_duration_var = "--runtime=#{$testing_duration} --time_based=1"
end

K8S_FIO_GRAPHITE = "/opt/output/vm-template/graphites/k8s_fio_graphite.py" unless defined?(K8S_FIO_GRAPHITE)

def run_fio_on_pods(pods, adapted_param, param_name, res_dir, testname, testcase)
  graphite_pids = []
  gpid_mutex = Mutex.new
  pods.map do |pod|
    Thread.new do
      remote_param  = "/tmp/#{param_name}"
      result_remote = "/tmp/#{param_name}-result.json"
      result_local  = "#{res_dir}/#{pod}-k8s-0.json"
      system("#{KUBECTL} cp #{Shellwords.escape(adapted_param)} #{NS}/#{pod}:#{remote_param} >> #{@log_file} 2>&1")

      # Kill any leftover fio from a previous run, clear previous output, then start fio
      system("#{KUBECTL} exec -n #{NS} #{pod} -- sh -c 'killall fio 2>/dev/null; sleep 1' >> #{@log_file} 2>&1")
      bg_cmd = "> #{result_remote}; nohup fio #{remote_param} --output-format=json --output=#{result_remote} --status-interval=5"
      bg_cmd += " #{$k8s_duration_var}" unless $k8s_duration_var.empty?
      bg_cmd += " > /tmp/fio.log 2>&1 &"
      system("#{KUBECTL} exec -n #{NS} #{pod} -- sh -c #{Shellwords.escape(bg_cmd)} >> #{@log_file} 2>&1")

      # Launch local graphite reporter for this pod
      metric_prefix = "fio.#{testname}.#{testcase}.#{pod}"
      graphite_cmd = "python3 #{K8S_FIO_GRAPHITE} '#{KUBECTL}' #{NS} #{pod} #{result_remote} '#{metric_prefix}'"
      graphite_log = "#{res_dir}/#{pod}-graphite.log"
      gpid = spawn(graphite_cmd, [:out, :err] => [graphite_log, "a"])
      gpid_mutex.synchronize { graphite_pids << gpid }
      puts "  [#{pod}] fio started, graphite reporter pid=#{gpid}", @log_file

      # Wait for fio to finish in the pod (ignore zombie processes)
      loop do
        sleep(5)
        out, _ = k8s("exec -n #{NS} #{pod} -- sh -c 'for p in $(pgrep -x fio); do grep -q zombie /proc/$p/status 2>/dev/null || echo $p; done'")
        break if out.strip.empty?
      end
      puts "  [#{pod}] fio finished", @log_file

      # Collect final results
      system("#{KUBECTL} cp #{NS}/#{pod}:#{result_remote} #{Shellwords.escape(result_local)} >> #{@log_file} 2>&1")
      puts "  [#{pod}] Results collected to #{result_local}", @log_file
    end
  end.tap do |threads|
    # Store graphite pids for cleanup after all threads join
    threads.define_singleton_method(:graphite_pids) { graphite_pids }
  end
end

def stop_graphite_reporters(threads)
  return unless threads.respond_to?(:graphite_pids)
  threads.graphite_pids.each do |pid|
    begin
      Process.kill("TERM", pid)
      Process.wait(pid)
    rescue Errno::ESRCH, Errno::ECHILD
      # already exited
    end
  end
end

path_testname = Shellwords.escape($output_path.gsub(".","-").gsub(" ","_"))

if !$vm_groups.empty?
  # Mixed Workload Mode: run each group's param file in parallel against its labeled pods
  time = Time.now.to_i
  puts "Started Testing K8s Mixed Workload Mode (#{$vm_groups.size} groups in parallel)", @status_log

  # Grafana monitoring links for each group
  $vm_groups.each_with_index do |grp, gi|
    param_name = grp["param_file"].to_s
    path_testcase = Shellwords.escape("group#{gi}-#{param_name}".gsub(".","-").gsub(" ","_"))
    puts %{<a href="http://#{@ip_url}:3000/d/fio/hcibench-fio-monitoring?orgId=1&var-Testname=#{path_testname}&var-Testcase=#{path_testcase}-#{time}" \
    target="_blank">HERE TO MONITOR GROUP #{gi} FIO PERFORMANCE</a>},@status_log
  end

  group_threads = $vm_groups.each_with_index.map do |grp, gi|
    param_name = grp["param_file"].to_s
    src_param  = "#{$self_defined_param_file_path}/#{param_name}"
    item_label = "group#{gi}-#{param_name}-#{time}"
    res_dir    = "#{$output_path_dir}/#{item_label}"
    FileUtils.mkdir_p(res_dir)
    adapted_param = "#{res_dir}/#{param_name}-k8s.cfg"
    adapt_param_file(src_param, adapted_param)
    testcase = "group#{gi}-#{param_name}".gsub(".","-").gsub(" ","_")

    Thread.new do
      puts "Group #{gi} (#{param_name}): starting...", @status_log
      out, _ = k8s("get pods -n #{NS} -l app=hcibench,hci-group=g#{gi} --no-headers -o custom-columns=NAME:.metadata.name")
      group_pods = out.split("\n").map(&:strip).reject(&:empty?)
      if group_pods.empty?
        puts "[ERROR] No pods found for group #{gi} (label hci-group=g#{gi})", @status_log
        next
      end
      threads = run_fio_on_pods(group_pods, adapted_param, param_name, res_dir,
                                path_testname, "#{testcase}-#{time}")
      threads.each(&:join)
      stop_graphite_reporters(threads)

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
  cached_pods = pod_names
  Dir.entries($self_defined_param_file_path).sort.each do |item|
    next if item == '.' || item == '..' || File.directory?(item)

    time        = Time.now.to_i
    src_param   = "#{$self_defined_param_file_path}/#{item}"
    res_dir     = "#{$output_path_dir}/#{item}-#{time}"
    FileUtils.mkdir_p(res_dir)

    adapted_param = "#{res_dir}/#{item}-k8s.cfg"
    adapt_param_file(src_param, adapted_param)

    path_testcase = Shellwords.escape(item.gsub(".","-").gsub(" ","_"))

    puts "Started Testing #{item}", @status_log
    puts %{<a href="http://#{@ip_url}:3000/d/fio/hcibench-fio-monitoring?orgId=1&var-Testname=#{path_testname}&var-Testcase=#{path_testcase}-#{time}" \
    target="_blank">HERE TO MONITOR FIO PERFORMANCE</a>},@status_log

    pods = cached_pods
    if pods.empty?
      puts "[ERROR] No hcibench pods found in namespace #{$k8s_namespace}", @status_log
      next
    end

    threads = run_fio_on_pods(pods, adapted_param, item, res_dir,
                              path_testname, "#{path_testcase}-#{time}")
    threads.each(&:join)
    stop_graphite_reporters(threads)

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
