require "/opt/automation/lib/rvc-util.rb"
require "/opt/automation/lib/util.rb"
require "cgi"
require "yaml"
require "json"

# Name the result path and template path.
# template_path might need to be changed based on code deployment.
# result_path = "/opt/output/results/Just-A-Test/vdb-2vmdk-100ws-4k-70rdpct-100randompct-2threads-1567721576"
result_path = ARGV[0]
result_path = result_path[0..-2] if result_path and result_path[-1] == "/"

@pdf_generate_log = "#{$log_path}/pdfGenerate.log"

def genReport(result_path)
  humbug_link = ""
  humbug_link = File.read($humbug_link_file) if File.exist?($humbug_link_file)
  
  pdf_path = result_path + "-report.pdf"

  path_testname = Shellwords.escape(result_path.split("/")[-2].gsub(".","-").gsub(" ","_"))
  path_testcase = Shellwords.escape(result_path.split("/")[-1].gsub(".","-").gsub(" ","_"))

  vsan_cfg_file = result_path + "/vsan.cfg"

  template_path = "/opt/automation/lib/report"
  timezone = `timedatectl show | grep -i timezone | cut -d "=" -f2`.chomp.gsub("/","%2F").gsub("_","%5F")
  #Get the start time and stop time of tests, and scale them correctly.
  puts "Get the start time and stop time of tests, and scale them correctly", @pdf_generate_log
  from_time = result_path.split('-')[-1].to_i
  to_time = File.mtime("#{result_path}-res.txt").to_i
  from_time = from_time*1000
  to_time = to_time*1000
  #Download the screenshots to the images/fio or images/vdbench directories.
  puts "Download the screenshots to the images/fio or images/vdbench directories", @pdf_generate_log
  `mkdir -p /opt/automation/lib/report/images/#{$tool}`
  if $tool == "fio"
    fio_small_imgs = Array.[](2,3,13,14,23,25,10,26,6,12)
    fio_large_imgs = Array.[](5,7,8,11,22,9,21)
    for i in fio_small_imgs
      `curl 'http://#{$docker_ip}:3000/render/d-solo/fio/hcibench-fio-monitoring?orgId=1&var-Testname=#{path_testname}&var-Testcase=#{path_testcase}&from=#{from_time}&to=#{to_time}&panelId=#{i}&width=300&height=150&tz=#{timezone}'>#{template_path}/images/fio/#{i}.png`
    end
    for i in fio_large_imgs
      `curl 'http://#{$docker_ip}:3000/render/d-solo/fio/hcibench-fio-monitoring?orgId=1&var-Testname=#{path_testname}&var-Testcase=#{path_testcase}&from=#{from_time}&to=#{to_time}&panelId=#{i}&width=610&height=435&tz=#{timezone}'>#{template_path}/images/fio/#{i}.png`
    end
  else
    vdbench_small_imgs = Array.[](2,3,4,17,13,14,23,25,10,26,6,12)
    vdbench_large_imgs = Array.[](5,7,8,11,22,9,21,20)
    for i in vdbench_small_imgs
      `curl 'http://#{$docker_ip}:3000/render/d-solo/vdbench/hcibench-vdbench-monitoring?orgId=1&var-Testname=#{path_testname}&var-Testcase=#{path_testcase}&from=#{from_time}&to=#{to_time}&panelId=#{i}&width=300&height=135&tz=#{timezone}'>#{template_path}/images/vdbench/#{i}.png`
    end
    for i in vdbench_large_imgs
      `curl 'http://#{$docker_ip}:3000/render/d-solo/vdbench/hcibench-vdbench-monitoring?orgId=1&var-Testname=#{path_testname}&var-Testcase=#{path_testcase}&from=#{from_time}&to=#{to_time}&panelId=#{i}&width=610&height=435&tz=#{timezone}'>#{template_path}/images/vdbench/#{i}.png`
    end
  end
  # Read the templates
  puts "Read the templates", @pdf_generate_log
  template = "#{template_path}/#{$tool}_report_template.html"
  html = File.read(template)

  #Replate the hcitags in the template with the actual data
  puts "Replate the hcitags in the template with the actual data", @pdf_generate_log
  html = html.gsub(/<hcitag:ip_address>/, CGI.escape(_get_ip_addr))
  html = html.gsub(/<hcitag:from_time>/, from_time.to_s)
  html = html.gsub(/<hcitag:to_time>/, to_time.to_s)
  html = html.gsub(/<hcitag:path_testname>/, path_testname)
  html = html.gsub(/<hcitag:path_testcase>/, path_testcase)

  #Handle the special chars in the url
  puts "Handle the special chars in the url", @pdf_generate_log
  cluster_name_url=CGI.escape($cluster_name)
  html = html.gsub(/<hcitag:cluster_name>/, cluster_name_url)

  stats_path = Dir["#{result_path}/**/stats.html"]
  stats_path = stats_path[0]
  stats_path = stats_path.gsub("/opt/output", "http://" + _get_ip_addr)
  html = html.gsub(/<hcitag:stats_addr>/, stats_path)

  if $vsan_debug and humbug_link != ""
    html = html.gsub(/<hcitag:humbug>/, humbug_link)
  else
    html = html.gsub('<a href="<hcitag:humbug>" target="_blank" rel="noopener noreferrer">vSAN Performance Stats in Grafana</a><br/>','')
  end

  html = html.gsub(/<hcitag:test_name>/, result_path.split('/')[-1])
  html = html.gsub(/<hcitag:report_time>/, Time.now.localtime.to_s)
  #Read the HCIBench version
  hcib_v = " HCIBench_#{`cat /etc/hcibench_version`}"
  html = html.gsub(/ HCIBench/, hcib_v)
  html = html.gsub(/<hcitag:vsan_support_url>/,_get_vsan_support_url($cluster_name))

  if File.exist?(vsan_cfg_file)
    File.readlines(vsan_cfg_file).each do |line|
      $vsan_version = 2 if line.include? "vSAN ESA Enabled: True"
      $vsan_version = 1 if line.include? "vSAN ESA Enabled: False"
    end
  end

  if $vsan_version == 1
    html = html.gsub(/class="vsan2"/, "hidden")
  else
    html = html.gsub(/class="vsan1"/, "hidden")
  end

  #Read the result content and replace the hcitag in the html template.
  puts "Read the result content and replace the hcitag in the html template", @pdf_generate_log
  result_file = ""
  File.read("#{result_path}-res.txt").each_line do |line|
    if line.match(/Resource Usage:/)
      break
    end
    result_file += line
  end
  result_file = result_file.gsub("VMs", "Number of VMs")
  result_file = result_file.gsub("IOPS", "I/O per Second")
  result_file = result_file.gsub("THROUGHPUT", "Throughput")
  result_file = result_file.gsub("R_LATENCY", "Read Latency")
  result_file = result_file.gsub("W_LATENCY", "Write Latency")
  result_file = result_file.gsub("LATENCY", "Latency")
  result_file = result_file.gsub("95%tile_R_LAT", "95th Percentile Read Latency")
  result_file = result_file.gsub("95%tile_W_LAT", "95th Percentile Write Latency")
  result_file = result_file.gsub("95%tile_LAT", "95th Percentile Latency")
  result_file = result_file.gsub(/=============================\n/,"<b>\\0</b>")
  result_file = result_file.gsub(/[\s|\t]*= /, ":\t")
  #result_file = result_file.gsub(/[^\w:,]\s.*/, '<b>\\0</b>')
  result_file = result_file + "<h2>Resource Usage</h2>"
  resource_file = File.read("#{result_path}/#{$resource_json_file_name}")
  resource_hash = JSON.parse(resource_file)

  res_table = "<table style='width:100%'><tr><th>Cluster</th>"
  clusters = resource_hash.keys
  resource_hash[clusters[0]].keys.each do |metric|
    res_table += "<th>#{metric}</th>"
  end
  res_table += "</tr>"
  clusters.each do |cluster|
    res_table += "<tr><td align=center>#{cluster}</td>"
    resource_hash[cluster].values.each do |value|
      res_table += "<td align=center>#{value}%</td>"
    end
    res_table += "</tr>"
  end
  res_table += "</table>"

  result_file += res_table
  result_file = result_file.gsub(/[\s|\t]*= /, ":\t")

  result_file = result_file.gsub("\n", "<br/>")
  html = html.gsub(/<hcitag:perf_result>/, result_file)
  #Read HCIBench cfg
  result_file = ""
  entry = YAML.load_file("#{result_path}/hcibench.cfg")
  if not entry["static_enabled"]
    entry.delete("static_ip_prefix")
  end

  if not entry["easy_run"]
    entry.delete("workloads")
  end

  if not entry["deploy_on_hosts"]
    entry.delete("hosts")
  end

  if not entry["network_name"] or entry["network_name"] == ""
    entry["network_name"] = "VM Network"
  end

  if not entry["storage_policy"] or entry["storage_policy"] == ""
    entry["storage_policy"] = "Datastore Default Policy"
  end

  entry.delete("hosts_credential")

  entry.each do |key|
    next if key[1] == ""
    result_file += (key.join(', ') + "\n").sub(',',':') if key[1] != nil
  end

  result_file = result_file.gsub(", ", "\n")
  result_file = result_file.gsub("\n", "<br/>")
  result_file = result_file.gsub("vc:", "vCenter IP/Hostname:")
  result_file = result_file.gsub("datacenter_name:", "Datacenter Name:")
  result_file = result_file.gsub("cluster_name:", "Cluster Name:")
  result_file = result_file.gsub("resource_pool_name:", "Resource Pool Name:")
  result_file = result_file.gsub("vm_folder_name:", "VM Folder Name:")
  result_file = result_file.gsub("network_name:", "Network Name:")
  result_file = result_file.gsub("static_ip_prefix:", "Internal Static IP Prefix:")
  result_file = result_file.gsub("static_enabled:", "Use Internal Static IP:")
  result_file = result_file.gsub("reuse_vm:", "Reuse Existing VMs:")
  result_file = result_file.gsub("datastore_name:", "Datastore Name:")
  result_file = result_file.gsub("deploy_on_hosts:", "Directly Deploy on Hosts:")
  result_file = result_file.gsub("hosts:", "Host List:")
  result_file = result_file.gsub("easy_run:", "Easy Run:")
  result_file = result_file.gsub("workloads:", "Easy Run Workloads:")
  result_file = result_file.gsub("storage_policy:", "Storage Policy Name:")
  result_file = result_file.gsub("vm_prefix:", "Guest VM Name Prefix:")
  result_file = result_file.gsub("multi_writer:", "Multi-Write VMDK:")
  result_file = result_file.gsub("clear_cache:", "Clear Read/Write Cache/Buffer Before Test:")
  result_file = result_file.gsub("vsan_debug:", "vSAN Debug Mode:")
  result_file = result_file.gsub("number_vm:", "Number of Guest VMs:")
  result_file = result_file.gsub("number_cpu:", "Number of vCPU per VM:")
  result_file = result_file.gsub("size_ram:", "Size(GB) of RAM per VM:")
  result_file = result_file.gsub("number_data_disk:", "Number of Data Disk per VM:")
  result_file = result_file.gsub("size_data_disk:", "Size of Data Disk in GB:")
  result_file = result_file.gsub("self_defined_param_file_path:", "Workload Parameter File Source:")
  result_file = result_file.gsub("output_path:", "Test Name:")
  result_file = result_file.gsub("warm_up_disk_before_testing:", "Virtual Disk Preparation Method:")
  result_file = result_file.gsub("tool:", "Tool to Use:")
  result_file = result_file.gsub("testing_duration:", "Testing Time:")
  result_file = result_file.gsub("cleanup_vm:", "Delete Guest VMs after Testing:")

  html = html.gsub(/<hcitag:HCIBench_config>/, result_file)

  result_file = File.read("#{result_path}/#{$tool}.cfg")
  result_file = result_file.gsub("\n", "<br/>")
  html = html.gsub(/<hcitag:fio_vdbench_config>/, result_file)

  vsan_cfg_path = Dir["#{result_path}/**/vsan.cfg"]
  if vsan_cfg_path.length == 1
    result_file = File.read(vsan_cfg_path[0])
    result_file = result_file.gsub("\n", "<br/>")
    html = html.gsub(/<hcitag:vSAN_config>/, result_file)
  else
    html = html.gsub(/<hcitag:vSAN_config>/, "Not applicable to this test.<br/>")
  end

  #Generate html file from the template.
  puts "Generate html file from the template", @pdf_generate_log
  File.open("#{template_path}/report.html", "w") {|file| file.puts html}

  html = File.open("#{template_path}/report.html",'r')

  #Generate the pdf file using weasyprint
  puts "Generate the pdf file using weasyprint", @pdf_generate_log
  `weasyprint #{template_path}/report.html #{pdf_path}`

  #Clean the contents in the template folder.
  puts "Clean the contents in the template folder", @pdf_generate_log
  `rm -f #{template_path}/report.html`
  `rm -f #{template_path}/images/#{$tool}/*`
end

genReport(result_path) if result_path
