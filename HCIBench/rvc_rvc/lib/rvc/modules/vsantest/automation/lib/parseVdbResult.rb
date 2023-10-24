#!/usr/bin/ruby
#TBD to replace BASH SCRIPT
require_relative "rvc-util.rb"
require 'shellwords'
require 'json'

@version = "vdbench50406"
@stddevoffset = 0
@short = false

def puts(o,res_file)
  open(res_file, 'a') do |f|
    f << o + "\n"
  end
  super(o)
end

if ARGV.empty? or ARGV.size < 1
  puts "Usage 'cmd + dirname'"
  exit(1)
else
  ARGV.each do |dir|
    if File.directory?(dir)
      startTime = File.basename(dir).split("-")[-1]
      endTime = Time.now.to_i
      file = File.open("#{dir}/#{$resource_json_file_name}", 'w')
      file.puts _get_res_avg_usage(startTime, endTime).to_json
      res_usage = _get_res_usage(startTime, endTime, dir)
      resfile = dir + "-res.txt"
      $datastore_names.each do |datastore|
        puts "Datastore     = #{datastore}", resfile
        puts "=============================", resfile
        #ds_prefix = datastore
        ds_prefix = _get_ds_id_by_name(datastore)
        file_list = `ls #{dir}/#{$vm_prefix}-*#{ds_prefix}-*.txt`.encode('UTF-8', :invalid => :replace).split("\n")
        files_map = {}
        max_rd = 0
        max_rd_file = ""
        file_list.each do |result_file|
          rds = []
          avgs = []
          File.open(result_file).each do |line|
            case
            when line =~ /^.*Vdbench distribution:.*$/
              @version = line.split(' ')[2]
            when line =~ /^.*RD=.*$/
              rd = line.split(" ")[2..-1].join(" ")
              rds.push(rd)
            when line =~ /^.* avg.*$/
              avg = line.split(" ")[2..-1]
              avgs.push(avg)
            when line =~ /^.*avg.*$/
              avg = line.split(" ")[1..-1]
              avgs.push(avg)
            end
          end
          if max_rd < rds.size
            max_rd = rds.size
            max_rd_file = result_file
          end
          files_map[result_file] = [rds,avgs]
        end
        @stddevoffset = 1 if @version == "vdbench50407"
        for sub_index in 0...max_rd
          rd = ""
          vm_num = 0
          iops_arr = []
          tput_arr = []
          avg_lat_arr = []
          rd_lat_arr = []
          wt_lat_arr = []
          stddev_lat_arr = []
          badfiles = []
          files_map.keys.each do |file|
            rd = files_map[file][0][sub_index] if file == max_rd_file
            if files_map[file][1][sub_index] #has that many avg
              metric = files_map[file][1][sub_index]
              iops = metric[0].to_f
              iops_arr.push(iops)
              tput = metric[1].to_f
              tput_arr.push(tput)
              avg_lat = metric[4].to_f
              avg_lat_arr.push(avg_lat)
              rd_lat = metric[5].to_f
              rd_lat_arr.push(rd_lat)
              wt_lat = metric[6].to_f
              wt_lat_arr.push(wt_lat)
              stddev_lat = metric[8 + @stddevoffset].to_f
              stddev_lat_arr.push(stddev_lat)
              vm_num += 1
            else
              badfiles << file
            end
          end
          iops_sum = iops_arr.inject(0){|sum,x| sum + x }
          tput_sum = tput_arr.inject(0){|sum,x| sum + x }
          if avg_lat_arr.size > 0
            avg_lat = avg_lat_arr.inject(0){|sum,x| sum + x }/avg_lat_arr.size
            avg_rlat = rd_lat_arr.inject(0){|sum,x| sum + x }/rd_lat_arr.size
            avg_wlat = wt_lat_arr.inject(0){|sum,x| sum + x }/wt_lat_arr.size
            stddev_lat = stddev_lat_arr.inject(0){|sum,x| sum + x }/stddev_lat_arr.size
          else
            avg_lat = 0
            avg_rlat = 0
            avg_wlat = 0
            stddev_lat = 0
          end
          puts "Version:\t#{@version}", resfile
          puts "Run Def:\t#{rd}", resfile
          puts "VMs\t\t= #{vm_num}", resfile
          puts "IOPS\t\t= #{iops_sum.round(2)} IO/S", resfile
          puts "THROUGHPUT\t= #{tput_sum.round(2)} MB/s", resfile
          puts "LATENCY\t\t= #{avg_lat.round(2)} ms", resfile
          puts "R_LATENCY\t= #{avg_rlat.round(2)} ms", resfile
          puts "W_LATENCY\t= #{avg_wlat.round(2)} ms", resfile
          puts "95%tile_LAT\t= #{(stddev_lat * 1.645 + avg_lat).round(2)} ms", resfile
          puts "=============================", resfile
          if badfiles.size > 0
            puts "Testing is done, #{vm_num} out of #{vm_num + badfiles.size} VMs finished test successfully. Please check following files for details:\n#{badfiles.join(%{\n})}", resfile
            puts "=============================", resfile
          end
        end
      end
      puts "Resource Usage:", resfile
      #cpu_usage = _get_cpu_usage(startTime).chomp
      #ram_usage = _get_ram_usage(startTime).chomp
      vsan_pcpu_usage = _get_vsan_cpu_usage(dir).chomp
      #puts "CPU USAGE\t= #{cpu_usage}", resfile
      #puts "RAM USAGE\t= #{ram_usage}", resfile
      puts "vSAN PCPU USAGE\t= #{vsan_pcpu_usage.to_s}", resfile if vsan_pcpu_usage != ""
      puts res_usage, resfile
      hcibench_version = `cat /etc/hcibench_version`.chomp
      `cd "#{dir}"; cp -r #{$log_path} "#{dir}"/; tar zcfP HCIBench-#{hcibench_version}-logs.tar.gz -C logs .; rm -rf logs`
    else
      puts "#{dir} doesn't exist!"    
    end
  end
end
