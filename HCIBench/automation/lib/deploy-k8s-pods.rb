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

(0...$vm_num).each do |pod_idx|
  pod_name = "#{$k8s_pod_prefix}-#{pod_idx}"

  # --- PVCs ---
  (0...$number_data_disk).each do |disk_idx|
    pvc_name = "#{pod_name}-pvc-#{disk_idx}"
    sc_line = $k8s_storage_class.empty? ? "" : "        storageClassName: #{$k8s_storage_class}\n"
    pvc_yaml = <<~YAML
      apiVersion: v1
      kind: PersistentVolumeClaim
      metadata:
        name: #{pvc_name}
        namespace: #{$k8s_namespace}
        labels:
          app: hcibench
          pod: #{pod_name}
      spec:
        volumeMode: Block
        accessModes: ["#{$k8s_access_mode}"]
#{sc_line}        resources:
          requests:
            storage: #{$size_data_disk}Gi
    YAML
    puts "Creating PVC #{pvc_name}", @log_file
    IO.popen("#{KUBECTL} apply -f -", "w") { |io| io.write(pvc_yaml) }
  end

  # --- Pod ---
  volume_devices = (0...$number_data_disk).map { |i|
    "        - name: pvc-#{i}\n          devicePath: /mnt/pvc#{i}"
  }.join("\n")

  volumes = (0...$number_data_disk).map { |i|
    "      - name: pvc-#{i}\n        persistentVolumeClaim:\n          claimName: #{pod_name}-pvc-#{i}"
  }.join("\n")

  pod_yaml = <<~YAML
    apiVersion: v1
    kind: Pod
    metadata:
      name: #{pod_name}
      namespace: #{$k8s_namespace}
      labels:
        app: hcibench
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

  puts "Creating pod #{pod_name}", @log_file
  pod_out = IO.popen("#{KUBECTL} apply -f -", "w+") { |io| io.write(pod_yaml); io.close_write; io.read }
  puts pod_out, @log_file
end

# Wait for all pods to reach Running state (up to 10 minutes)
puts "Waiting for pods to reach Running state...", @log_file
deadline = Time.now + 600
loop do
  out, _ = k8s("get pods -n #{Shellwords.escape($k8s_namespace)} -l app=hcibench --no-headers 2>/dev/null")
  lines = out.split("\n").reject(&:empty?)
  total    = lines.size
  running  = lines.count { |l| l.include?("Running") }
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
