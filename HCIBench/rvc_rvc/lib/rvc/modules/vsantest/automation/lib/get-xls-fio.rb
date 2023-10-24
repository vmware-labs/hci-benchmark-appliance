#!/usr/bin/env ruby
#TBD: separate runs by datastore
require_relative "util.rb"
require_relative "rvc-util.rb"
require "rubygems"
require "pathname"
require 'spreadsheet'

ip = `ip a show dev eth0 | grep global | awk {'print $2'} | cut -d "/" -f1`.chomp
@empty = true

if ARGV.empty?
    p "Put all your test case folders into one test folder, for example:"
    p "-------------------------------------------------------------------"
    p "root@photon-HCIBench [ ~ ]# ls /opt/output/results/easy-run-1511824453"
    p "fio-8vmdk-100ws-4k-70rdpct-100randompct-4threads-1511829572          fio-8vmdk-100ws-4k-70rdpct-100randompct-4threads-1511918222          fio-8vmdk-100ws-4k-70rdpct-100randompct-4threads-1511992633
    fio-8vmdk-100ws-4k-70rdpct-100randompct-4threads-1511829572-res.txt  fio-8vmdk-100ws-4k-70rdpct-100randompct-4threads-1511918222-res.txt  fio-8vmdk-100ws-4k-70rdpct-100randompct-4threads-1511992633-res.txt"
    p "-------------------------------------------------------------------"
    p "Usage: ./get-xls-fio.rb TEST_FOLDER_FULL_PATH"
    p "e.g."
    p "/opt/automation/get-xls-fio.rb /opt/output/results/easy-run-1511824453"
    exit(1)
else
    for arg in ARGV
        folder_path = arg
        folder_name = File.basename(folder_path)
        xls_file = "/opt/output/results/#{folder_name}-fio.xls"
        book = Spreadsheet::Workbook.new
        format = Spreadsheet::Format.new({ :weight => :bold, :pattern => 1, :pattern_fg_color => :silver })
        sum_sheet = book.create_worksheet :name => 'Summary'
        if File.directory?(folder_path)
            subfolders = Pathname.new(folder_path).children.select { |c| c.directory? }.collect { |p| p.to_s }
            sum_sheet.row(0).concat %w{Sheet\ Number
                                    Case\ Name
                                    Job\ Name
                                    Number\ of\ VMs
                                    Number\ of\ VMs\ Finished\ Early
                                    IOPS
                                    Throughput(MB)
                                    Read\ Latency(ms)
                                    Write\ Latency(ms)
                                    Read\ 95tile\ Latency(ms)
                                    Write\ 95tile\ Latency(ms)
                                    Blocksize
                                    Read\ Percentage
                                    Total\ Outstanding\ IO
                                    vSAN\ CPU\ Usage}
                                    #Physical\ CPU\ Usage
                                    #Physical\ Memory\ Usage}

            resource_file = File.read("#{subfolders[0]}/#{$resource_json_file_name}")
            resource_hash = JSON.parse(resource_file)
            clusters = resource_hash.keys
            resource_hash[clusters[0]].keys.each do |metric|
                metric = metric.gsub(" ","\ ")
                sum_sheet.row(0).push metric.upcase
            end

            for col in 0..17
                sum_sheet.row(0).set_format(col, format)
            end
            row_num = 0
            subfolders.sort.each_with_index do |testcase,index|
                if Dir.glob("#{testcase}/iotest-fio-[0-9]*vm").size == 1
                    @empty = false
                    num_vm = 0
                    bs = []
                    rw = []
                    readpct = []
                    oio = []
                    iops = []
                    throughput = []
                    r_lat = []
                    w_lat = []
                    r_lat_95 = []
                    w_lat_95 = []
                    job_names = []
                    results_files = Dir["#{testcase}/*.json"]
                    global_jsons = []
                    vm_finish_early = 0
                    file_json_map = {}
                    max_num_jobs = 0
                    min_jsons = 0
                    #for one test case, prepare global for details, and get the sum in sum page
                    results_files.each do |file|
                        jsons = extractJsonsFromFile(file)
                        file_json_map[file] = jsons
                        if min_jsons == 0 or min_jsons > jsons.size
                            min_jsons = jsons.size
                        end
                    end

                    for file in file_json_map.keys
                    #for file in results_files
                        jsons = file_json_map[file] 
                        parsed = extractResultJson(jsons) #jsons[min_jsons - 1] 
                        global_jsons.push(jsons)
                        num_jobs = 0
                        num_vm += 1
                        if parsed != {}
                            parsed['jobs'].each do |job|
                                if iops[num_jobs] == nil
                                    iops[num_jobs] = 0
                                    throughput[num_jobs] = 0
                                    r_lat[num_jobs] = 0
                                    w_lat[num_jobs] = 0
                                    r_lat_95[num_jobs] = 0
                                    w_lat_95[num_jobs] = 0
                                    readpct[num_jobs] = 0
                                    oio[num_jobs] = 0
                                    job_names[num_jobs] = job['jobname']
                                end
                                bs[num_jobs] = parsed['global options']['bs']
                                rw[num_jobs] = job['job options']['rw'] || parsed['global options']['rw']
                                if rw[num_jobs].include? 'read'
                                    readpct[num_jobs] = 100
                                elsif rw[num_jobs].include? 'write'
                                    readpct[num_jobs] = 0
                                else
                                    readpct[num_jobs] = job['job options']['rwmixread'] || parsed['global options']['rwmixread']
                                end
                                if job['job options']['iodepth']
                                    oio[num_jobs] += job['job options']['iodepth'].to_i
                                else
                                    oio[num_jobs] += parsed['global options']['iodepth'].to_i
                                end
                                iops[num_jobs] += job['read']['iops'] + job['write']['iops']
                                throughput[num_jobs] += job['read']['bw'] + job['write']['bw']
                                r_lat[num_jobs] += job['read']['lat_ns']['mean']
                                w_lat[num_jobs] += job['write']['lat_ns']['mean']
                                r_lat_95[num_jobs] += job['read']['lat_ns']['percentile']['95.000000'] if job['read']['lat_ns']['percentile']
                                w_lat_95[num_jobs] += job['write']['lat_ns']['percentile']['95.000000'] if job['write']['lat_ns']['percentile']
                                num_jobs += 1
                            end
                            disks = parsed['disk_util'].size
                        max_num_jobs = num_jobs if num_jobs > max_num_jobs
                        else
                            vm_finish_early += 1
                        end
                    end
                    pcpu_usage = `/opt/automation/lib/getPCpuUsage.rb "#{testcase}"`.to_s
                    case_name = File.basename(testcase)
                    numofJsons = 0
                    global_jsons.each do |vm|
                        if vm.size > numofJsons
                            numofJsons = vm.size
                        end
                    end
                    resource_file = File.read("#{testcase}/#{$resource_json_file_name}")
                    resource_hash = JSON.parse(resource_file)
                    for i in 0..max_num_jobs-1
                        throughput[i] = throughput[i] / 1024
                        r_lat[i] = r_lat[i] / ((num_vm - vm_finish_early)* 1000000)
                        w_lat[i] = w_lat[i] / ((num_vm - vm_finish_early)* 1000000)
                        r_lat_95[i] = r_lat_95[i] / ((num_vm - vm_finish_early) * 1000000)
                        w_lat_95[i] = w_lat_95[i] / ((num_vm - vm_finish_early) * 1000000)
                        temp_hash = {}
                        resource_hash.each do |cluster_name,payload|
                            payload.each do |metric,value|
                                if temp_hash[metric]
                                    temp_hash[metric] += "#{cluster_name}: #{value}%; "
                                else
                                    temp_hash[metric] = "#{cluster_name}: #{value}%; "
                                end
                            end
                        end

                        sum_sheet.row(1+row_num).push "Sheet-#{1+i+index}", case_name, job_names[i], num_vm, vm_finish_early, iops[i].round(2), throughput[i].round(2),r_lat[i].round(2), w_lat[i].round(2), 
                        r_lat_95[i].round(2), w_lat_95[i].round(2), bs[i], readpct[i].to_s+"%",oio[i]*disks, pcpu_usage
                        temp_hash.each do |metric,value|
                            sum_sheet.row(1+row_num).push(value)
                        end
                        row_num = row_num + 1
                        details_sheet = book.create_worksheet :name => "Sheet-#{i+1+index}"
                        details_sheet.row(0).push case_name
                        details_sheet.row(0).concat %w{ Time Time\ Elasped IOPS  Throughput(MB) Read\ Latency(ms)  Write\ Latency(ms)  Read\ 95tile\ Latency(ms)  Write\ 95tile\ Latency(ms) }
                        for col in 0..8
                            details_sheet.row(0).set_format(col, format)
                        end
                        for j in 0..numofJsons - 2
                            finished_vm = 0
                            detail_iops = 0
                            detail_tput = 0
                            detail_rlat = 0
                            detail_wlat = 0
                            detail_r95l = 0
                            detail_w95l = 0
                            time = ""
                            elapsed = ""
                            global_jsons.each do |vm_jsons|
                                if vm_jsons.size > j
                                    json = vm_jsons[j]
                                    job = json['jobs'][i]
                                    detail_iops += job['read']['iops'] + job['write']['iops']
                                    detail_tput += job['read']['bw'] + job['write']['bw']
                                    detail_rlat += job['read']['lat_ns']['mean']
                                    detail_wlat += job['write']['lat_ns']['mean']
                                    detail_r95l += job['read']['lat_ns']['percentile']['95.000000'] if job['read']['lat_ns']['percentile']
                                    detail_w95l += job['write']['lat_ns']['percentile']['95.000000'] if job['write']['lat_ns']['percentile']
                                    time = json['time'] 
                                    elapsed = job['elapsed']
                                else
                                    finished_vm += 1
                                end
                            end
                            detail_tput = detail_tput / 1024
                            detail_rlat = detail_rlat / ((num_vm - finished_vm) * 1000000)
                            detail_wlat = detail_wlat / ((num_vm - finished_vm) * 1000000)
                            detail_r95l = detail_r95l / ((num_vm - finished_vm) * 1000000)
                            detail_w95l = detail_w95l / ((num_vm - finished_vm) * 1000000)
                            head = ""
                            if j == 0
                                head = job_names[i]   
                            end
                            details_sheet.row(j+1).push head, time, elapsed, detail_iops.round(2), detail_tput, detail_rlat.round(2), detail_wlat.round(2), detail_r95l.round(2), detail_w95l.round(2)
                        end
                    end
                end
            end
            if @empty
                p "No Fio workload results found in /output/results/#{folder_name}"
            else
                book.write xls_file
                p "======================================================================================"
                p "Summary XLS file generated: https://#{ip}:8443/output/results/#{folder_name}-fio.xls"
                p "======================================================================================"
            end
        else
            p "#{folder_path} is not a valid directory"
            exit(1)
        end
    end
end
