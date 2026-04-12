#!/usr/bin/ruby
# deploy-k8s-pods.rb
# Creates namespace, PVCs, and fio pods in the target K8s cluster.
# Each pod gets $number_data_disk PVCs of $size_data_disk Gi mounted at /mnt/pvc0 … /mnt/pvcN-1.
# Mirrors the role of deploy-vms.rb for the VM path.

require_relative "rvc-util.rb"
require_relative "util.rb"
load File.expand_path("local-image-loader.rb", __dir__)
require 'fileutils'

@log_file = "#{$log_path}/deploy.log"
`rm -f #{@log_file}`

KUBECTL = "KUBECONFIG=#{Shellwords.escape($k8s_kubeconfig)} kubectl"

# If a bundled tar exists for this image, pre-load it onto every K8s node.
# Returns [image_ref, pull_policy] — pull_policy is Never when loaded locally.
POD_IMAGE, POD_PULL_POLICY = ensure_image_on_nodes($k8s_pod_image, KUBECTL, @log_file)

def k8s(cmd)
  out = `#{KUBECTL} #{cmd} 2>&1`
  rc  = $?.exitstatus
  [out.chomp, rc]
end

puts "Creating namespace #{$k8s_namespace}", @log_file
ns_yaml = <<~YAML
  apiVersion: v1
  kind: Namespace
  metadata:
    name: #{$k8s_namespace}
    labels:
      pod-security.kubernetes.io/enforce: baseline
      pod-security.kubernetes.io/warn: baseline
      pod-security.kubernetes.io/audit: baseline
YAML
ns_out = IO.popen("#{KUBECTL} apply -f -", "w+") { |io| io.write(ns_yaml); io.close_write; io.read }
puts ns_out, @log_file

def build_pvc_yaml(pvc_name, pod_name, group_label)
  labels = "    app: hcibench\n    pod: #{pod_name}"
  labels += "\n    hci-group: #{group_label}" unless group_label.empty?
  yaml = "apiVersion: v1\n"
  yaml += "kind: PersistentVolumeClaim\n"
  yaml += "metadata:\n"
  yaml += "  name: #{pvc_name}\n"
  yaml += "  namespace: #{$k8s_namespace}\n"
  yaml += "  labels:\n#{labels}\n"
  yaml += "spec:\n"
  yaml += "  volumeMode: Block\n"
  yaml += "  accessModes: [\"#{$k8s_access_mode}\"]\n"
  yaml += "  storageClassName: #{$k8s_storage_class}\n" unless $k8s_storage_class.empty?
  yaml += "  resources:\n"
  yaml += "    requests:\n"
  yaml += "      storage: #{$size_data_disk}Gi\n"
  yaml
end

def create_pod(pod_name, group_label, log_file)
  pvc_threads = (0...$number_data_disk).map do |disk_idx|
    Thread.new do
      pvc_name = "#{pod_name}-pvc-#{disk_idx}"
      pvc_yaml = build_pvc_yaml(pvc_name, pod_name, group_label)
      puts "Creating PVC #{pvc_name}", log_file
      pvc_out = IO.popen("#{KUBECTL} apply -f -", "w+") { |io| io.write(pvc_yaml); io.close_write; io.read }
      puts pvc_out, log_file
    end
  end
  pvc_threads.each(&:join)

  volume_devices = (0...$number_data_disk).map { |i|
    "        - name: pvc-#{i}\n          devicePath: /mnt/pvc#{i}"
  }.join("\n")
  volumes = (0...$number_data_disk).map { |i|
    "      - name: pvc-#{i}\n        persistentVolumeClaim:\n          claimName: #{pod_name}-pvc-#{i}"
  }.join("\n")

  extra_labels = group_label.empty? ? "" : "\n        hci-group: #{group_label}"
  pod_yaml = <<~YAML
    apiVersion: v1
    kind: Pod
    metadata:
      name: #{pod_name}
      namespace: #{$k8s_namespace}
      labels:
        app: hcibench#{extra_labels}
    spec:
      restartPolicy: Never
      containers:
      - name: fio
        image: #{POD_IMAGE}
        imagePullPolicy: #{POD_PULL_POLICY}
        command: ["sleep", "infinity"]
        volumeDevices:
#{volume_devices}
      volumes:
#{volumes}
  YAML

  puts "Creating pod #{pod_name}", log_file
  pod_out = IO.popen("#{KUBECTL} apply -f -", "w+") { |io| io.write(pod_yaml); io.close_write; io.read }
  puts pod_out, log_file
end

pod_threads = if !$vm_groups.empty?
  $vm_groups.each_with_index.flat_map do |grp, gi|
    group_label = "g#{gi}"
    grp["number_vm"].to_i.times.map do |pod_idx|
      Thread.new { create_pod("#{$k8s_pod_prefix}-g#{gi}-#{pod_idx}", group_label, @log_file) }
    end
  end
else
  $vm_num.times.map do |pod_idx|
    Thread.new { create_pod("#{$k8s_pod_prefix}-#{pod_idx}", "", @log_file) }
  end
end
pod_threads.each(&:join)

# Wait for all pods to reach Running state (up to 10 minutes)
puts "Waiting for pods to reach Running state...", @log_file
deadline = Time.now + 600
loop do
  out, _ = k8s("get pods -n #{Shellwords.escape($k8s_namespace)} -l app=hcibench --no-headers 2>/dev/null")
  lines = out.split("\n").reject(&:empty?)
  running = lines.count { |l| l.include?("Running") }
  puts "  #{running}/#{$vm_num} pods Running", @log_file
  break if running >= $vm_num
  if Time.now > deadline
    puts "Timed out waiting for pods to start", @log_file
    exit(253)
  end
  sleep(10)
end

puts "All #{$vm_num} pods are Running.", @log_file
exit(0)
