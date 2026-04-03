#!/usr/bin/ruby
# local-image-loader.rb
#
# Loads bundled container image tars onto every K8s node — no internet required.
#
# Approach:
#   1. Serve /opt/automation/images/ via a temporary Python HTTP server on the appliance
#   2. For each node, bootstrap busybox by exec-ing into an already-running privileged
#      CNI/network pod that mounts the host root filesystem (antrea-agent, calico-node,
#      cilium, flannel, weave-net).  No separate bootstrap pod needed, so there is no
#      chicken-and-egg dependency on busybox being pre-cached.
#      Falls back to a privileged bootstrap pod if no suitable existing pod is found
#      (works once busybox has been cached by a previous run).
#   3. Deploy a privileged busybox DaemonSet (imagePullPolicy: Never) that downloads
#      and imports the main image tar on every node in parallel.
#   4. Tear down the DaemonSet and HTTP server.
#
# Returns [image_ref, pull_policy]:
#   - [image_ref, "Never"]        when the tar was loaded onto all nodes
#   - [image_ref, "IfNotPresent"] when no tar found (falls back to remote pull)

require 'shellwords'
require 'json'

IMAGES_DIR  = "/opt/automation/images"
HTTP_PORT   = 8889
DS_NAME     = "hcibench-image-loader"
DS_NS       = "kube-system"
BUSYBOX_REF = "busybox:1.36"
BUSYBOX_TAR = File.join(IMAGES_DIR, "busybox-1.36.tar")

def _image_tar_name(image_ref)
  image_ref.gsub(/[\/:]/, '-') + ".tar"
end

def _image_tar_path(image_ref)
  File.join(IMAGES_DIR, _image_tar_name(image_ref))
end

def _appliance_ip
  `ip -4 addr show eth0 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' | head -1`.strip
end

# Find an already-running pod on `node` that mounts the host root filesystem.
# Privileged CNI/network DaemonSet pods typically have a hostPath volume for "/"
# mounted at /host, /rootfs, etc., which we can use to write to the host's /tmp
# and chroot into to run ctr/docker.
#
# Returns [namespace, pod_name, host_root_mountpath] or nil.
def _find_host_root_pod(node, kubectl)
  # Ordered by likelihood — add more CNI labels here if needed
  candidates = [
    ["kube-system", "k8s-app=antrea-agent"],
    ["kube-system", "app=antrea-agent"],
    ["kube-system", "k8s-app=calico-node"],
    ["kube-system", "app=calico-node"],
    ["kube-system", "k8s-app=cilium"],
    ["kube-system", "app=cilium"],
    ["kube-system", "app=flannel"],
    ["kube-system", "k8s-app=flannel"],
    ["kube-system", "k8s-app=weave-net"],
  ]

  candidates.each do |ns, label|
    json_str = `#{kubectl} get pods -n #{ns} -l #{label} \
      --field-selector spec.nodeName=#{node} \
      -o json 2>/dev/null`
    pods = JSON.parse(json_str) rescue next
    items = (pods["items"] || []).select { |p| p.dig("status", "phase") == "Running" }
    next if items.empty?

    pod      = items.first
    pod_name = pod.dig("metadata", "name")
    volumes  = pod.dig("spec", "volumes") || []

    # Find a volume whose hostPath.path is exactly "/"
    host_vol = volumes.find { |v| v.dig("hostPath", "path") == "/" }
    next unless host_vol

    vol_name = host_vol["name"]

    # Resolve the mountPath for that volume in any container
    mount_path = nil
    (pod.dig("spec", "containers") || []).each do |c|
      vm = (c["volumeMounts"] || []).find { |m| m["name"] == vol_name }
      if vm
        mount_path = vm["mountPath"]
        break
      end
    end
    next unless mount_path

    return [ns, pod_name, mount_path]
  end
  nil
end

# Import a tar on a node by exec-ing into an existing privileged pod that has
# the host root filesystem mounted at host_root.
# Returns true on success, false on failure.
def _import_via_host_pod(ns, pod, host_root, tar_name, tar_url, kubectl, log_file)
  # Try wget first, fall back to curl
  cmd = "{ wget -q -O #{host_root}/tmp/#{tar_name} #{tar_url} 2>/dev/null || " \
        "  curl -fsSL -o #{host_root}/tmp/#{tar_name} #{tar_url}; } " \
        "|| { echo 'ERROR: download failed'; exit 1; }; " \
        "if test -S #{host_root}/run/containerd/containerd.sock 2>/dev/null; then " \
        "  chroot #{host_root} ctr --address /run/containerd/containerd.sock " \
        "    -n k8s.io images import /tmp/#{tar_name}; " \
        "elif test -S #{host_root}/var/run/docker.sock 2>/dev/null; then " \
        "  chroot #{host_root} docker load -i /tmp/#{tar_name}; " \
        "else echo 'ERROR: no supported container runtime socket'; exit 1; fi; " \
        "rm -f #{host_root}/tmp/#{tar_name}"
  result = `#{kubectl} exec -n #{ns} #{pod} -- sh -c #{Shellwords.escape(cmd)} 2>&1`
  puts result, log_file
  $?.exitstatus == 0
end

# Fallback bootstrap: import a tar via a temporary privileged pod.
# Requires busybox:1.36 to already be cached on the node (imagePullPolicy: Never),
# so this only works reliably after a prior successful bootstrap.
def _import_via_bootstrap_pod(node, tar_name, tar_url, kubectl, log_file)
  pod_name  = "hcibench-bootstrap-#{node.gsub(/[^a-z0-9]/, '-')}"
  pod_yaml  = <<~YAML
    apiVersion: v1
    kind: Pod
    metadata:
      name: #{pod_name}
      namespace: #{DS_NS}
    spec:
      nodeName: #{node}
      tolerations:
      - operator: Exists
      restartPolicy: Never
      hostPID: true
      containers:
      - name: loader
        image: #{BUSYBOX_REF}
        imagePullPolicy: Never
        securityContext:
          privileged: true
        command:
        - sh
        - -c
        - |
          wget -q -O /host-tmp/#{tar_name} #{tar_url} \
            || { echo "ERROR: download failed"; exit 1; }
          if chroot /host test -S /run/containerd/containerd.sock 2>/dev/null; then
            chroot /host ctr --address /run/containerd/containerd.sock \
              -n k8s.io images import /tmp/#{tar_name}
          elif chroot /host test -S /var/run/docker.sock 2>/dev/null; then
            chroot /host docker load -i /tmp/#{tar_name}
          else
            echo "ERROR: no supported container runtime socket"; exit 1
          fi
          rm -f /host-tmp/#{tar_name}
        volumeMounts:
        - name: host-root
          mountPath: /host
        - name: host-tmp
          mountPath: /host-tmp
      volumes:
      - name: host-root
        hostPath:
          path: /
      - name: host-tmp
        hostPath:
          path: /tmp
  YAML

  IO.popen("#{kubectl} apply -f - 2>&1", "w+") { |io| io.write(pod_yaml); io.close_write; puts io.read, log_file }

  deadline = Time.now + 300
  loop do
    phase = `#{kubectl} get pod #{pod_name} -n #{DS_NS} \
      -o jsonpath='{.status.phase}' 2>/dev/null`.strip
    break if %w[Succeeded Failed].include?(phase)
    break if Time.now > deadline
    sleep(3)
  end

  `#{kubectl} delete pod #{pod_name} -n #{DS_NS} --ignore-not-found=true 2>/dev/null`
end

# Bootstrap a single image tar onto a single node.
# Prefers exec-ing into an existing privileged host-root pod; falls back to a
# temporary bootstrap pod if none is available.
def _bootstrap_on_node(node, tar_name, tar_url, kubectl, log_file)
  host_pod = _find_host_root_pod(node, kubectl)
  if host_pod
    ns, pod, host_root = host_pod
    puts "    Using #{ns}/#{pod} (host_root=#{host_root}) for bootstrap", log_file
    ok = _import_via_host_pod(ns, pod, host_root, tar_name, tar_url, kubectl, log_file)
    return if ok
    puts "    [WARN] exec-based import failed — falling back to bootstrap pod", log_file
  else
    puts "    No existing host-root pod found on #{node} — trying bootstrap pod", log_file
  end
  _import_via_bootstrap_pod(node, tar_name, tar_url, kubectl, log_file)
end

# Ensures image_ref is available on every K8s node.
# Returns [image_ref, pull_policy].
def ensure_image_on_nodes(image_ref, kubectl, log_file)
  tar = _image_tar_path(image_ref)
  unless File.exist?(tar)
    puts "No bundled tar for #{image_ref} — pods will pull from remote.", log_file
    return [image_ref, "IfNotPresent"]
  end

  appliance_ip = _appliance_ip
  tar_name     = _image_tar_name(image_ref)
  tar_url      = "http://#{appliance_ip}:#{HTTP_PORT}/#{tar_name}"
  busybox_url  = "http://#{appliance_ip}:#{HTTP_PORT}/#{_image_tar_name(BUSYBOX_REF)}"

  puts "Bundled tar found — loading #{image_ref} onto K8s nodes (no internet required)", log_file

  http_pid = spawn("python3 -m http.server #{HTTP_PORT} --directory #{Shellwords.escape(IMAGES_DIR)}",
                   [:out, :err] => "/dev/null")
  sleep(1)

  begin
    nodes = `#{kubectl} get nodes --no-headers -o custom-columns=NAME:.metadata.name 2>/dev/null`
              .split("\n").map(&:strip).reject(&:empty?)

    # Step 1 — bootstrap busybox onto every node via an existing privileged CNI pod
    if File.exist?(BUSYBOX_TAR)
      puts "Bootstrapping busybox on #{nodes.size} nodes...", log_file
      nodes.each do |node|
        puts "  Loading busybox on #{node}", log_file
        _bootstrap_on_node(node, _image_tar_name(BUSYBOX_REF), busybox_url, kubectl, log_file)
      end
      puts "Busybox bootstrap complete.", log_file
    end

    # Step 2 — busybox DaemonSet loads the main image on all nodes in parallel
    ds_yaml = <<~YAML
      apiVersion: apps/v1
      kind: DaemonSet
      metadata:
        name: #{DS_NAME}
        namespace: #{DS_NS}
      spec:
        selector:
          matchLabels:
            app: #{DS_NAME}
        template:
          metadata:
            labels:
              app: #{DS_NAME}
          spec:
            tolerations:
            - operator: Exists
            hostPID: true
            initContainers:
            - name: load
              image: #{BUSYBOX_REF}
              imagePullPolicy: Never
              securityContext:
                privileged: true
              command:
              - sh
              - -c
              - |
                wget -q -O /host-tmp/#{tar_name} #{tar_url} \
                  || { echo "ERROR: failed to download #{tar_url}"; exit 1; }
                if chroot /host test -S /run/containerd/containerd.sock 2>/dev/null; then
                  chroot /host ctr --address /run/containerd/containerd.sock \
                    -n k8s.io images import /tmp/#{tar_name}
                elif chroot /host test -S /var/run/docker.sock 2>/dev/null; then
                  chroot /host docker load -i /tmp/#{tar_name}
                else
                  echo "ERROR: no supported container runtime socket"; exit 1
                fi
                rm -f /host-tmp/#{tar_name}
              volumeMounts:
              - name: host-root
                mountPath: /host
              - name: host-tmp
                mountPath: /host-tmp
            containers:
            - name: done
              image: #{BUSYBOX_REF}
              imagePullPolicy: Never
              command: ["sh", "-c", "sleep infinity"]
            volumes:
            - name: host-root
              hostPath:
                path: /
            - name: host-tmp
              hostPath:
                path: /tmp
    YAML

    IO.popen("#{kubectl} apply -f - 2>&1", "w+") { |io| io.write(ds_yaml); io.close_write; puts io.read, log_file }

    puts "Waiting for #{image_ref} to load on all #{nodes.size} nodes...", log_file
    deadline = Time.now + 600
    loop do
      ready = `#{kubectl} get ds #{DS_NAME} -n #{DS_NS} \
        -o jsonpath='{.status.numberReady}' 2>/dev/null`.strip.to_i
      puts "  #{ready}/#{nodes.size} nodes ready", log_file
      break if ready >= nodes.size
      if Time.now > deadline
        puts "[WARN] Timed out waiting for image load — pods may fail to start.", log_file
        break
      end
      sleep(5)
    end

    `#{kubectl} delete ds #{DS_NAME} -n #{DS_NS} --ignore-not-found=true 2>/dev/null`
    puts "Image #{image_ref} loaded on all nodes. Using imagePullPolicy: Never.", log_file
    return [image_ref, "Never"]

  ensure
    Process.kill("TERM", http_pid) rescue nil
    Process.wait(http_pid)         rescue nil
  end
end
