#!/usr/bin/ruby
# cleanup-k8s-pods.rb
# Deletes all hcibench pods and their PVCs from the K8s namespace.
# Mirrors the role of cleanup-vm.rb for the VM path.

require_relative "rvc-util.rb"
require_relative "util.rb"

@log_file = "#{$log_path}/cleanup-k8s.log"

KUBECTL = "KUBECONFIG=#{Shellwords.escape($k8s_kubeconfig)} kubectl"

def k8s(cmd)
  out = `#{KUBECTL} #{cmd} 2>&1`
  [out.chomp, $?.exitstatus]
end

puts "Deleting hcibench pods in namespace #{$k8s_namespace}...", @log_file
k8s("delete pods -n #{Shellwords.escape($k8s_namespace)} -l app=hcibench --ignore-not-found=true --wait=true")

puts "Deleting hcibench PVCs in namespace #{$k8s_namespace}...", @log_file
k8s("delete pvc -n #{Shellwords.escape($k8s_namespace)} -l app=hcibench --ignore-not-found=true --wait=true")

puts "Deleting namespace #{$k8s_namespace}...", @log_file
k8s("delete namespace #{Shellwords.escape($k8s_namespace)} --ignore-not-found=true")

k8s("delete ds hcibench-image-loader -n kube-system --ignore-not-found=true 2>/dev/null")
File.delete($k8s_warmup_done_file) if File.exist?($k8s_warmup_done_file)
puts "Cleanup complete.", @log_file
exit(0)
