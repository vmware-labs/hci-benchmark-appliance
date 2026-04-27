#!/usr/bin/ruby
# pre-validation-k8s.rb
# K8s-specific pre-validation checks.
# Loaded by pre-validation.rb when test_target == "k8s".
# Inherits: puts (timestamped+logged), err_msg, warning_msg, validate_subnets,
#            validate_testing_config, and all globals from rvc-util.rb.

require 'time'

KUBECTL_PRECHECK = "KUBECONFIG=#{Shellwords.escape($k8s_kubeconfig)} kubectl"

def validate_k8s_config_fields
  puts "Validating K8s configuration fields..."
  err_msg "k8s_kubeconfig_path is required" if $k8s_kubeconfig.to_s.strip.empty?
  err_msg "k8s_namespace is required"        if $k8s_namespace.to_s.strip.empty?
  err_msg "k8s_pod_image is required"        if $k8s_pod_image.to_s.strip.empty?
  valid_modes = %w[ReadWriteOnce ReadWriteMany ReadOnlyMany]
  err_msg "k8s_access_mode must be one of: #{valid_modes.join(', ')}" \
    unless valid_modes.include?($k8s_access_mode.to_s)
  err_msg "number_vm must be a positive integer" \
    unless $vm_num.is_a?(Integer) && $vm_num > 0
  err_msg "number_data_disk must be a positive integer" \
    unless $number_data_disk.is_a?(Integer) && $number_data_disk > 0
  err_msg "size_data_disk must be a positive integer" \
    unless $size_data_disk.is_a?(Integer) && $size_data_disk > 0
  puts "K8s configuration fields validated"
end

def validate_kubeconfig_file
  puts "Checking kubeconfig file at #{$k8s_kubeconfig}..."
  err_msg "kubeconfig file not found at #{$k8s_kubeconfig}" \
    unless File.exist?($k8s_kubeconfig)
  puts "kubeconfig file found"
end

def validate_k8s_connectivity
  puts "Validating K8s cluster connectivity..."

  # Check for certificate issues before general connectivity
  out = `#{KUBECTL_PRECHECK} get nodes --no-headers 2>&1`
  if $?.exitstatus != 0
    if out.include?("certificate has expired") || out.include?("x509:")
      # Extract server URL from kubeconfig for cert check
      server_url = `#{KUBECTL_PRECHECK} config view --minify -o jsonpath='{.clusters[0].cluster.server}' 2>/dev/null`.strip
      cert_details = ""
      if server_url =~ %r{https://([^:/]+):?(\d*)}
        host = $1
        port = $2.empty? ? "443" : $2
        cert_dates = `echo | openssl s_client -connect #{host}:#{port} -servername #{host} 2>/dev/null | openssl x509 -noout -dates 2>/dev/null`.strip
        cert_details = "\nServer certificate info (#{host}:#{port}):\n  #{cert_dates.gsub("\n", "\n  ")}" unless cert_dates.empty?
      end
      err_msg "K8s cluster certificate is expired or not yet valid. " \
              "Please renew the cluster certificates (e.g. 'kubeadm certs renew all' on the control plane).#{cert_details}\n" \
              "kubectl output: #{out.strip}"
    else
      err_msg "Cannot reach K8s cluster using kubeconfig #{$k8s_kubeconfig}:\n#{out.strip}"
    end
  end

  node_lines = out.strip.split("\n")
  puts "K8s cluster reachable. #{node_lines.size} node(s):"
  node_lines.each { |line| puts "  #{line}" }
  not_ready = node_lines.reject { |l| l.split[1] == "Ready" }
  warning_msg "The following nodes are not Ready and may affect test pod scheduling:\n#{not_ready.join("\n")}" \
    unless not_ready.empty?

  # Check worker node count vs requested pods
  worker_lines = node_lines.reject { |l| l.include?("control-plane") }
  ready_workers = worker_lines.select { |l| l.split[1] == "Ready" }
  if ready_workers.size < $vm_num
    warning_msg "Number of ready worker nodes (#{ready_workers.size}) is less than the number of pods (#{$vm_num}). " \
                "Multiple pods will be scheduled on the same node, which may not reflect realistic per-host performance. " \
                "Recommendation: set number of pods to #{ready_workers.size} or fewer for even distribution across worker nodes."
  end

  # Proactive certificate expiry warning
  server_url = `#{KUBECTL_PRECHECK} config view --minify -o jsonpath='{.clusters[0].cluster.server}' 2>/dev/null`.strip
  if server_url =~ %r{https://([^:/]+):?(\d*)}
    host = $1
    port = $2.empty? ? "443" : $2
    expiry_str = `echo | openssl s_client -connect #{host}:#{port} -servername #{host} 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null`.strip
    if expiry_str =~ /notAfter=(.*)/
      begin
        expiry_time = Time.parse($1)
        days_left = ((expiry_time - Time.now) / 86400).to_i
        if days_left < 0
          err_msg "K8s API server certificate expired #{-days_left} day(s) ago (#{expiry_time}). Please renew cluster certificates."
        elsif days_left < 30
          warning_msg "K8s API server certificate expires in #{days_left} day(s) (#{expiry_time}). Consider renewing soon."
        else
          puts "K8s API server certificate valid until #{expiry_time} (#{days_left} days remaining)"
        end
      rescue ArgumentError
        # Could not parse date, skip
      end
    end
  end
end

def validate_k8s_storage_class
  if $k8s_storage_class.to_s.strip.empty?
    puts "No StorageClass specified, checking for cluster default..."
    sc_out = `#{KUBECTL_PRECHECK} get storageclass --no-headers 2>&1`
    if $?.exitstatus != 0
      warning_msg "Could not list StorageClasses: #{sc_out.strip}. PVC provisioning may fail."
    else
      default_line = sc_out.split("\n").find { |l| l.include?("(default)") }
      if default_line
        default_sc = default_line.split.first
        puts "Default StorageClass: #{default_sc}"
      else
        err_msg "No default StorageClass found in the cluster. Please specify a StorageClass in HCIBench or set a default StorageClass in the cluster."
      end
    end
  else
    puts "Validating StorageClass '#{$k8s_storage_class}'..."
    out = `#{KUBECTL_PRECHECK} get storageclass #{Shellwords.escape($k8s_storage_class)} --no-headers 2>&1`
    err_msg "StorageClass '#{$k8s_storage_class}' not found in cluster: #{out.strip}" \
      if $?.exitstatus != 0
    puts "StorageClass '#{$k8s_storage_class}' validated"
  end
end

def validate_k8s_disk_space
  puts "Checking appliance disk space..."
  diskutil = `df /dev/sdb | grep sdb | awk '{print $5}' | cut -d "%" -f1`.to_i
  err_msg "Disk usage on /dev/sdb is #{diskutil}%, exceeding 85%. Please clear old results before running tests." \
    if diskutil > 85
  puts "Appliance disk space OK (#{diskutil}% used)"
end

def validate_k8s_fio_params
  puts "Validating fio workload profiles for K8s..."
  err_msg "The workload param directory #{$self_defined_param_file_path} is not valid!" \
    unless File.directory?($self_defined_param_file_path)
  err_msg "No workload param files found in #{$self_defined_param_file_path}!" \
    if _dir_empty?($self_defined_param_file_path)

  param_files_to_validate.each do |item|
    param_file = "#{$self_defined_param_file_path}/#{item}"
    disk_num = `grep -cE 'filename=/dev/sd[a-z]' #{param_file} 2>/dev/null`.to_i
    if disk_num > $number_data_disk
      err_msg "Workload profile '#{item}' references #{disk_num} disk(s) but number_data_disk is #{$number_data_disk}. " \
              "Reduce disk count in the profile or increase number_data_disk."
    end
    puts "  #{item}: #{disk_num} disk reference(s) — OK"
  end
  puts "Workload profiles validated"
end

# --- Execute K8s pre-validation ---
validate_k8s_config_fields
validate_kubeconfig_file
validate_k8s_connectivity
validate_k8s_storage_class
validate_subnets
validate_k8s_disk_space
validate_k8s_fio_params
validate_testing_config

puts "------------------------------------------------------------------------------"
puts "All K8s config has been validated, please go ahead to kick off testing"
puts "------------------------------------------------------------------------------"
