#!/usr/bin/env ruby
#TBD: separate runs by datastore
require_relative "util.rb"
require_relative "rvc-util.rb"
require "rubygems"
require "pathname"
require 'spreadsheet'

version = "vdbench50406"
stddev_offset = 0
@empty = true
ip = `ip a show dev eth0 | grep global | awk {'print $2'} | cut -d "/" -f1`.chomp

if ARGV.empty?
    p "Put all your test case folders into one test folder, for example:"
    p "-------------------------------------------------------------------"
    p "root@photon-HCIBench [ ~ ]# ls /opt/output/results/easy-run-1511824453"
    p "vdb-8vmdk-100ws-4k-70rdpct-100randompct-4threads-1511829572          vdb-8vmdk-100ws-4k-70rdpct-100randompct-4threads-1511918222          vdb-8vmdk-100ws-4k-70rdpct-100randompct-4threads-1511992633
    vdb-8vmdk-100ws-4k-70rdpct-100randompct-4threads-1511829572-res.txt  vdb-8vmdk-100ws-4k-70rdpct-100randompct-4threads-1511918222-res.txt  vdb-8vmdk-100ws-4k-70rdpct-100randompct-4threads-1511992633-res.txt"
    p "-------------------------------------------------------------------"
    p "Usage: ./get-xls-vdbench.rb TEST_FOLDER_FULL_PATH"
    p "e.g."
    p "/opt/automation/lib/get-xls-vdbench.rb /opt/output/results/easy-run-1511824453"
    exit(1)
else
    for arg in ARGV
        folder_path = arg
        folder_name = File.basename(folder_path)
        xls_file = "/opt/output/results/#{folder_name}-vdbench.xls"
        book = Spreadsheet::Workbook.new
        format = Spreadsheet::Format.new({ :weight => :bold, :pattern => 1, :pattern_fg_color => :silver })
        sum_sheet = book.create_worksheet :name => 'Summary'
        if File.directory?(folder_path)
            subfolders = Pathname.new(folder_path).children.select { |c| c.directory? }.collect { |p| p.to_s }
            sum_sheet.row(0).concat %w{Sheet\ Number Case\ Name Run\ Definition Number\ of\ VMs 
            IOPS Throughput Latency Read\ Latency Write\ Latency Latency\ Standard\ Deviation 
            Blocksize Read\ Percentage Total\ Outstanding\ IO vSAN\ CPU\ Usage}

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
                if Dir.glob("#{testcase}/*.txt").size >= 1
                    @empty = false
                    results_files = Dir["#{testcase}/*.txt"]
                    files_map = {}
                    max_rd = 0
                    #extract all the content into files_map
                    for file in results_files
                        rds = []
                        avgs = []
                        intervals = []
                        file_name = File.basename(file)
                        text = File.open(file).read
                        text.gsub!(/\r\n?/, "\n")
                        text.each_line do |line|
                            version = line.split(' ')[2] if line =~ /^.*Vdbench distribution:.*$/
                            #RD lines
                            if line =~ /^.*RD=.*$/
                                rd = line.split(" ")[2..-1].join(" ")                          
                                rds.push(rd)
                            end
                            #interval lines
                            if line =~ /^[0-9\:\.\ ]+$/ and line.size > 40
                                interval = line.split(" ")
                                intervals.push([]) if intervals.empty? or intervals[-1][1].to_i > interval[1].to_i
                                intervals.push(interval)
                            end
    
                            #result lines
                            if line =~ /^.* avg.*$/
                                avg = line.split(" ")[2..-1]
                                avgs.push(avg)
                            elsif line =~ /^.*avg.*$/
                                avg = line.split(" ")[1..-1]
                                avgs.push(avg)
                            end
                        end
                        max_rd = rds.size if max_rd < rds.size
                        files_map[file_name] = [rds,intervals,avgs]
                    end

                    if version == "vdbench50407"
                      stddev_offset = 1
                    else
                      stddev_offset = 0
                    end
    
                    #deal with avg of each case
                    #cpu_usage = `/opt/automation/lib/getCpuUsage.rb "#{testcase}"`.to_s
                    #ram_usage = `/opt/automation/lib/getRamUsage.rb "#{testcase}"`.to_s
                    pcpu_usage = `/opt/automation/lib/getPCpuUsage.rb "#{testcase}"`.to_s
                    case_name = File.basename(testcase)
                    resource_file = File.read("#{testcase}/#{$resource_json_file_name}")
                    resource_hash = JSON.parse(resource_file)
                    for sub_index in 0...max_rd
                        rd = ""
                        vm_num = 0
                        iops_arr = []
                        tput_arr = []
                        blocksize = 0
                        readpct = ""
                        avg_lat_arr = []
                        rd_lat_arr = []
                        wt_lat_arr = []
                        stddev_lat_arr = []
                        qd = 0
                        badfile_num = 0
    
                        for file in files_map.keys
                            if files_map[file][2][sub_index]
                                rd = files_map[file][0][sub_index]
                                metric = files_map[file][2][sub_index]
                                iops = metric[0].to_f
                                iops_arr.push(iops)
                                tput = metric[1].to_f
                                tput_arr.push(tput)
                                blocksize = metric[2]
                                readpct = metric[3].to_f.round.to_s
                                avg_lat = metric[4].to_f
                                avg_lat_arr.push(avg_lat)
                                rd_lat = metric[5].to_f
                                rd_lat_arr.push(rd_lat)
                                wt_lat = metric[6].to_f
                                wt_lat_arr.push(wt_lat)
                                stddev_lat = metric[8 + stddev_offset].to_f
                                stddev_lat_arr.push(stddev_lat)
                                qd = qd + metric[9 + stddev_offset].to_f
                                vm_num = vm_num + 1
                            else
                                badfile_num = badfile_num + 1
                            end
                        end
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
                        sum_sheet.row(1+row_num).push "Sheet-#{1+index}", case_name, rd, vm_num, iops_arr.inject(0){|sum,x| sum + x}.round(2), tput_arr.inject(0){|sum,x| sum + x}.round(2), 
                        (avg_lat_arr.inject(0){|sum,x| (sum + x)}.to_f/avg_lat_arr.size).round(4),(rd_lat_arr.inject(0){|sum,x| (sum + x)}.to_f/rd_lat_arr.size).round(4), 
                        (wt_lat_arr.inject(0){|sum,x| (sum + x)}.to_f/wt_lat_arr.size).round(4), (stddev_lat_arr.inject(0){|sum,x| (sum + x)}.to_f/stddev_lat_arr.size).round(2), (blocksize.to_f/1024).round.to_s+"KB", 
                        readpct+"%", qd, pcpu_usage
                        temp_hash.each do |metric,value|
                            sum_sheet.row(1+row_num).push(value)
                        end
                        row_num = row_num + 1
                    end
    
                    details_sheet = book.create_worksheet :name => "Sheet-#{index+1}"
                    details_sheet.row(0).push case_name
                    details_sheet.row(0).concat %w{ Interval IOPS Throughput Latency Read\ Latency Write\ Latency Latency\ Standard\ Deviation}
                    for col in 0..7
                        details_sheet.row(0).set_format(col, format)
                    end
                    success_run = 0
                    for file in files_map.keys
                        success_run = files_map[file][2].size if files_map[file][0].size == max_rd and success_run <= files_map[file][2].size
                    end
    
                    detail_row_num = 1
                    for sub_index in 0...success_run
                        interval_arr = []
                        files_num = files_map.keys.size
                        for file in files_map.keys
                            if files_map[file][2][sub_index] #can use the interval
                                endpoint = 0
                                for i in 0...files_map[file][1].size
                                    if files_map[file][1][i].empty? and i != 0
                                        endpoint = i
                                        break
                                    end
                                    if i == 0
                                        interval_arr[i] = [files_map[file][0][0]]
                                        next
                                    end                   
                                    key = files_map[file][1][i][1].to_i
                                    iops = files_map[file][1][i][2].to_f.round(2)
                                    tput = files_map[file][1][i][3].to_f.round(2)
                                    lat = files_map[file][1][i][6].to_f.round(2)
                                    r_lat = files_map[file][1][i][7].to_f.round(2)
                                    w_lat = files_map[file][1][i][8].to_f.round(2)
                                    stddev_lat = files_map[file][1][i][10 + stddev_offset].to_f.round(2)
                                    if interval_arr[key]
                                        interval_arr[key] = [interval_arr[key],[iops, tput, lat, r_lat, w_lat, stddev_lat]].transpose.map { |e| e.reduce(:+) }
                                    else
                                        interval_arr[key] = [iops, tput, lat, r_lat, w_lat, stddev_lat]
                                    end                                   
                                end
                                files_map[file][1].slice!(0...endpoint)
                                files_map[file][0].slice!(0)
                            else
                                files_num = files_num - 1
                                next
                            end
                        end
                        interval_arr.each_with_index do |value, interval|
                            unless value.nil?
                                if interval == 0
                                    details_sheet.row(detail_row_num).push value[0]
                                elsif interval == 1
                                    details_sheet.row(detail_row_num).push interval,value[0],value[1],(value[2]/files_num).round(4),(value[3]/files_num).round(4),(value[4]/files_num).round(4),(value[5]/files_num).round(4)
                                    detail_row_num = detail_row_num + 1
                                else
                                    details_sheet.row(detail_row_num).push "",interval,value[0],value[1],(value[2]/files_num).round(4),(value[3]/files_num).round(4),(value[4]/files_num).round(4),(value[5]/files_num).round(4)
                                    detail_row_num = detail_row_num + 1
                                end
                            end
                        end
                        detail_row_num = detail_row_num + 1
                    end
                end
            end
            if @empty
                p "No Vdbench workload results found in /output/results/#{folder_name}"
            else
                book.write xls_file    
                p "======================================================================================"
                p "Summary XLS file generated: https://#{ip}:443/output/results/#{folder_name}-vdbench.xls"
                p "======================================================================================"
            end
        else
            p "#{folder_path} is not a valid directory"
            exit(1)
        end
    end
end
