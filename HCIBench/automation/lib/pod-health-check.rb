#!/usr/bin/ruby
# pod-health-check.rb
# Validates that existing hcibench PVCs in the namespace are compatible with
# the current configuration before reusing them.  Pods are always recreated
# fresh (to avoid stale processes); only PVCs are reused since they are the
# expensive resource (bound to persistent volumes).
#
# Checks: namespace exists, total Bound PVC count matches, all PVCs have
# correct size and storageClass.
#
# Exit codes:
#   0   — PVCs are compatible, safe to reuse (pods will be recreated)
#   255 — PVCs are absent, insufficient, or incompatible; full redeploy needed

require_relative "rvc-util.rb"
require_relative "util.rb"
require 'shellwords'
require 'json'

@health_log  = "#{$log_path}/pod-health-check.log"
@status_log  = "#{$log_path}/test-status.log"

KUBECTL = "KUBECONFIG=#{Shellwords.escape($k8s_kubeconfig)} kubectl" unless defined?(KUBECTL)
NS      = Shellwords.escape($k8s_namespace) unless defined?(NS)

def k8s(cmd)
  out = `#{KUBECTL} #{cmd} 2>&1`
  rc  = $?.exitstatus
  [out.chomp, rc]
end

def failure_handler(reason)
  puts "[PVC CHECK] #{reason}", @health_log
  puts "[PVC CHECK] Existing PVCs not compatible — full redeploy needed", @health_log
  exit(255)
end

puts "Checking existing PVCs in namespace #{$k8s_namespace}...", @status_log

# ── 1. Namespace must exist ───────────────────────────────────────────────────
puts "Verifying namespace #{$k8s_namespace}...", @health_log
_, rc = k8s("get namespace #{NS} --no-headers 2>/dev/null")
failure_handler("Namespace #{$k8s_namespace} not found") unless rc == 0
puts "Namespace verified.", @health_log

# ── 2. Fetch all hcibench PVCs in one call ────────────────────────────────────
pvcs_json_out, _ = k8s("get pvc -n #{NS} -l app=hcibench -o json")
all_pvcs = (JSON.parse(pvcs_json_out)["items"] rescue [])
bound_pvcs = all_pvcs.select { |p| p.dig("status", "phase") == "Bound" }

expected_sc      = $k8s_storage_class   # empty string means "any"
expected_disks   = $number_data_disk
expected_size_gi = $size_data_disk.to_i
expected_total   = $vm_num * expected_disks

puts "Found #{bound_pvcs.size} Bound PVCs, expecting #{expected_total} (#{$vm_num} pods × #{expected_disks} disks, #{expected_size_gi}Gi each)", @health_log

# ── 3. Check total PVC count ─────────────────────────────────────────────────
unless bound_pvcs.size == expected_total
  failure_handler("Found #{bound_pvcs.size} Bound PVCs, want #{expected_total}")
end

# ── 4. Check each PVC's size and storageClass ─────────────────────────────────
bound_pvcs.each do |pvc|
  pvc_name = pvc.dig("metadata", "name")

  unless expected_sc.empty?
    sc = pvc.dig("spec", "storageClassName").to_s
    unless sc == expected_sc
      failure_handler("PVC #{pvc_name} storageClass mismatch: got '#{sc}', want '#{expected_sc}'")
    end
  end

  cap = pvc.dig("spec", "resources", "requests", "storage").to_s
  cap_gi = cap.gsub(/[^0-9]/, '').to_i
  unless cap_gi == expected_size_gi
    failure_handler("PVC #{pvc_name} size mismatch: got #{cap_gi}Gi, want #{expected_size_gi}Gi")
  end
end

puts "All PVCs validated: #{bound_pvcs.size} Bound, #{expected_size_gi}Gi#{expected_sc.empty? ? '' : ", SC=#{expected_sc}"}", @health_log
puts "DONE: PVCs are compatible — reusing PVCs, pods will be recreated fresh", @health_log
exit(0)
