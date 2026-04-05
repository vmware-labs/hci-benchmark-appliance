#!/usr/bin/ruby
# pod-health-check.rb
# Validates that existing hcibench pods in the namespace are compatible with
# the current configuration before reusing them.  Mirrors the role of
# vm-health-check.rb for the K8s path.
#
# Exit codes:
#   0   — pods are healthy and compatible, safe to reuse
#   255 — pods are absent, insufficient, or incompatible; caller should redeploy

require_relative "rvc-util.rb"
require_relative "util.rb"
load File.expand_path("local-image-loader.rb", __dir__)
require 'shellwords'

@health_log  = "#{$log_path}/pod-health-check.log"
@status_log  = "#{$log_path}/test-status.log"

KUBECTL = "KUBECONFIG=#{Shellwords.escape($k8s_kubeconfig)} kubectl"
NS      = Shellwords.escape($k8s_namespace)

def k8s(cmd)
  out = `#{KUBECTL} #{cmd} 2>&1`
  rc  = $?.exitstatus
  [out.chomp, rc]
end

def failure_handler(reason)
  puts "[ERROR] #{reason}", @health_log
  puts "[ERROR] Existing pods not compatible — will redeploy", @health_log
  puts "ABORT: Pods are absent or incompatible with current configuration", @health_log
  exit(255)
end

puts "Checking existing pods in namespace #{$k8s_namespace}...", @status_log

# ── 1. Namespace must exist ───────────────────────────────────────────────────
puts "Verifying namespace #{$k8s_namespace}...", @health_log
_, rc = k8s("get namespace #{NS} --no-headers 2>/dev/null")
failure_handler("Namespace #{$k8s_namespace} not found") unless rc == 0
puts "Namespace verified.", @health_log

# ── 2. Enough Running pods ────────────────────────────────────────────────────
puts "Checking pod count (need #{$vm_num})...", @health_log
pods_out, _ = k8s("get pods -n #{NS} -l app=hcibench --no-headers 2>/dev/null")
pod_lines = pods_out.split("\n").reject(&:empty?)
running_pods = pod_lines.select { |l| l.split[2] == "Running" }

if running_pods.size < $vm_num
  failure_handler("Only #{running_pods.size}/#{$vm_num} pods Running")
end
puts "#{running_pods.size} pods Running (need #{$vm_num}) — OK", @health_log

# ── 3. Per-pod validation ─────────────────────────────────────────────────────
# Collect pod names of the ones we will use
pod_names = running_pods.first($vm_num).map { |l| l.split[0] }

expected_image, _ = ensure_image_on_nodes($k8s_pod_image, KUBECTL, @health_log)
expected_sc     = $k8s_storage_class   # empty string means "any"
expected_disks  = $number_data_disk
expected_size_gi = $size_data_disk.to_i

pod_names.each do |pod|
  puts "Verifying pod #{pod}...", @health_log

  # --- image ---
  image_out, _ = k8s("get pod #{pod} -n #{NS} -o jsonpath='{.spec.containers[0].image}'")
  unless image_out == expected_image
    failure_handler("Pod #{pod} image mismatch: got '#{image_out}', want '#{expected_image}'")
  end

  # --- PVC count ---
  pvcs_out, _ = k8s("get pvc -n #{NS} -l pod=#{pod} --no-headers 2>/dev/null")
  pvc_lines = pvcs_out.split("\n").reject(&:empty?)
  unless pvc_lines.size == expected_disks
    failure_handler("Pod #{pod} has #{pvc_lines.size} PVCs, want #{expected_disks}")
  end

  # --- Per-PVC: storage class and capacity ---
  pvc_lines.each do |pvc_line|
    pvc_name = pvc_line.split[0]

    unless expected_sc.empty?
      sc_out, _ = k8s("get pvc #{pvc_name} -n #{NS} -o jsonpath='{.spec.storageClassName}'")
      unless sc_out == expected_sc
        failure_handler("PVC #{pvc_name} storageClass mismatch: got '#{sc_out}', want '#{expected_sc}'")
      end
    end

    cap_out, _ = k8s("get pvc #{pvc_name} -n #{NS} -o jsonpath='{.spec.resources.requests.storage}'")
    # Kubernetes reports capacity as e.g. "10Gi" — strip the "Gi" suffix for numeric comparison
    cap_gi = cap_out.gsub(/[^0-9]/, '').to_i
    unless cap_gi == expected_size_gi
      failure_handler("PVC #{pvc_name} size mismatch: got #{cap_gi}Gi, want #{expected_size_gi}Gi")
    end
  end

  puts "Pod #{pod} verified.", @health_log
end

puts "DONE: Pods are healthy and compatible — reusing for I/O testing", @health_log
exit(0)
