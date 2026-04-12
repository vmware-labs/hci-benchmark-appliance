#!/usr/bin/ruby
# all-in-one-k8s-testing.rb
# K8s storage testing orchestrator.  Mirrors all-in-one-testing.rb for the VM
# path but replaces vSphere/RVC operations with kubectl-based pod management.
#
# Flow:
#   1. Pre-flight checks
#   2. Deploy pods (unless reuse_vm is set and pods already exist)
#   3. Run fio workloads via k8s-io-test.rb
#   4. Optionally clean up pods

require_relative "util.rb"
require_relative "rvc-util.rb"
require 'fileutils'
require 'timeout'

@test_status_log = "#{$log_path}/test-status.log"
`cp -f #{$basedir}/../conf/k8s-conf.yaml #{$basedir}/../logs/hcibench.cfg`
`sed -i '/username/d;/password/d;/k8s_kubeconfig_content/d;/k8s_kubeconfig_path/d' #{$basedir}/../logs/hcibench.cfg`

`mkdir -m 755 -p #{$output_path_dir}` unless File.directory?($output_path_dir)

KUBECTL = "KUBECONFIG=#{Shellwords.escape($k8s_kubeconfig)} kubectl"
NS      = Shellwords.escape($k8s_namespace)

def k8s_failure_handler(what_failed)
  puts "[ERROR] #{what_failed} Failed.", @test_status_log
  if $cleanup_vm
    puts "Cleaning up K8s pods...", @test_status_log
    load $k8s_cleanup_file
    puts "K8s pods cleaned up.", @test_status_log
  else
    puts "K8s pods preserved for debugging. Run /opt/automation/cleanup-k8s-pods.sh to delete them.", @test_status_log
  end
  puts "Testing Failed. For details see logs in /opt/automation/logs", @test_status_log
  puts "Please cancel and re-run the testing.", @test_status_log
  loop { sleep(600) }
end

# --- Pre-flight: disk space ---
diskutil = `df /dev/sdb | grep sdb | awk '{print $5}' | cut -d "%" -f1`.to_i
if diskutil > 85
  puts "Your /dev/sdb usage is more than 85%, please clear old results.", @test_status_log
  k8s_failure_handler("Disk space")
end

# --- Pre-flight: kubeconfig ---
unless File.exist?($k8s_kubeconfig)
  puts "[ERROR] kubeconfig not found at #{$k8s_kubeconfig}", @test_status_log
  k8s_failure_handler("kubeconfig missing")
end

# --- Pre-flight: kubectl connectivity ---
out = `#{KUBECTL} get nodes --no-headers 2>&1`
if $?.exitstatus != 0
  puts "[ERROR] Cannot reach K8s cluster: #{out}", @test_status_log
  k8s_failure_handler("K8s cluster connectivity")
end
puts "K8s cluster reachable. Nodes:\n#{out}", @test_status_log

# --- Deploy or reuse PVCs ---
pvcs_reused = false
if $reuse_pod
  puts "Checking existing PVCs for compatibility...", @test_status_log
  system("ruby #{$k8s_health_file}")
  if $?.exitstatus == 0
    puts "Reusing existing PVCs in namespace #{$k8s_namespace}.", @test_status_log
    pvcs_reused = true
    # Delete old pods (they may have stale processes) — PVCs are kept
    puts "Deleting old pods (PVCs preserved)...", @test_status_log
    `#{KUBECTL} delete pods -n #{NS} -l app=hcibench --ignore-not-found=true --wait=true 2>/dev/null`
  else
    puts "Existing PVCs are absent or incompatible — full redeploy.", @test_status_log
  end
end

unless pvcs_reused
  # Fresh deploy — clear warmup flag so prep runs on new PVCs
  File.delete($k8s_warmup_done_file) if File.exist?($k8s_warmup_done_file)

  # Clean up any stale pods and PVCs before deploying fresh ones
  `#{KUBECTL} delete pods -n #{NS} -l app=hcibench --ignore-not-found=true --wait=true 2>/dev/null`
  `#{KUBECTL} delete pvc   -n #{NS} -l app=hcibench --ignore-not-found=true 2>/dev/null`
end

# Always deploy pods (fresh pods bind to existing or new PVCs via kubectl apply)
puts "Deploying #{$vm_num} pods with #{$number_data_disk} PVCs each (#{$size_data_disk} Gi, StorageClass: #{$k8s_storage_class.empty? ? '(default)' : $k8s_storage_class})#{pvcs_reused ? ' — reusing existing PVCs' : ''}...", @test_status_log
`ruby #{$k8s_deploy_k8s_file}`
rc = $?.exitstatus
if rc == 253
  k8s_failure_handler("Pod deployment timed out")
elsif rc != 0
  k8s_failure_handler("Pod deployment")
end
puts "Deployment finished.", @test_status_log

# --- Disk warm-up ---
if $warm_up_disk_before_testing != "NONE"
  if pods_reused && File.exist?($k8s_warmup_done_file)
    puts "Disk Preparation Skipped — PVCs were already prepped in a previous run.", @test_status_log
  else
    puts "Disk Preparation Started (#{$warm_up_disk_before_testing}).", @test_status_log
    load $k8s_warmup_file
    FileUtils.touch($k8s_warmup_done_file)
    puts "Disk Preparation Finished.", @test_status_log
  end
else
  puts "Disk Preparation Skipped (NONE).", @test_status_log
end

# --- Run I/O tests ---
puts "I/O Test Started.", @test_status_log
load $k8s_io_test_file
puts "I/O Test Finished.", @test_status_log

# --- Generate XLS ---
puts "Generating XLS file for this run...", @test_status_log
ARGV = [$output_path_dir]
load $getxlsfiofile

# --- Cleanup ---
if $cleanup_vm
  puts "Cleaning up K8s pods and PVCs...", @test_status_log
  load $k8s_cleanup_file
  puts "Cleanup complete.", @test_status_log
else
  puts "K8s pods preserved. Run /opt/automation/cleanup-k8s-pods.sh to delete them.", @test_status_log
end
