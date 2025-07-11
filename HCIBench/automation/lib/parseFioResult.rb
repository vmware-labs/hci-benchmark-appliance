#!/usr/bin/ruby
require_relative "rvc-util.rb"
require_relative "util.rb"
require "rubygems"
require "pathname"
require 'spreadsheet'
require 'json'

def puts(o,res_file)
  open(res_file, 'a') do |f|
    f << o + "\n"
  end
  super(o)
end

if ARGV.empty?
  p "Usage"
  exit(1)
else
  ARGV.each do |dir|
    if File.directory?(dir)
      startTime = File.basename(dir).split("-")[-1]
      endTime = Time.now.to_i
      res_usage = _get_res_usage(startTime, endTime, dir)
      file = File.open("#{dir}/#{$resource_json_file_name}", 'w')
      file.puts _get_res_avg_usage(startTime, endTime).to_json
      for datastore in $datastore_names
        ds_prefix = _get_ds_id_by_name(datastore)
        num_vm = 0
        iops = []
        throughput = []
        r_lat = []
        w_lat = []
        r_lat_95 = []
        w_lat_95 = []
        job_names = []
        max_num_jobs = 0
        vm_finish_early = 0
        files_finished_early = []
        file_arr = `ls #{dir}/*-'#{ds_prefix}'-*.json`.split("\n")
        file_arr.each do |file|
          jsons = extractJsonsFromFile(file)
          parsed = extractResultJson(jsons)  
          num_jobs = 0
          num_vm += 1
          if parsed != {}
            parsed['jobs'].each do |job|
              if (iops[num_jobs] == nil)
                iops[num_jobs] = 0
                throughput[num_jobs] = 0
                r_lat[num_jobs] = 0
                w_lat[num_jobs] = 0
                r_lat_95[num_jobs] = 0
                w_lat_95[num_jobs] = 0
                job_names[num_jobs] = job['jobname']
              end
              iops[num_jobs] += job['read']['iops'] + job['write']['iops']
              throughput[num_jobs] += job['read']['bw'] + job['write']['bw']
              r_lat[num_jobs] += job['read']['lat_ns']['mean']
              w_lat[num_jobs] += job['write']['lat_ns']['mean']
              r_lat_95[num_jobs] += job['read']['lat_ns']['percentile']['95.000000'] if job['read']['lat_ns']['percentile'] 
              w_lat_95[num_jobs] += job['write']['lat_ns']['percentile']['95.000000'] if job['write']['lat_ns']['percentile']
              num_jobs += 1
            end
            max_num_jobs = num_jobs if num_jobs > max_num_jobs
          else
            vm_finish_early += 1
            files_finished_early.append(file)
          end
        end
        resfile = dir + "-res.txt"
        puts "Datastore     = #{datastore}", resfile
        puts "All the VMs finished testing early, no results summarized", resfile if max_num_jobs == 0
        for i in 0..max_num_jobs-1
          throughput[i] = throughput[i] / 1024
          r_lat[i] = r_lat[i] / ((num_vm - vm_finish_early) * 1000000)
          w_lat[i] = w_lat[i] / ((num_vm - vm_finish_early) * 1000000)
          r_lat_95[i] = r_lat_95[i] / ((num_vm - vm_finish_early) * 1000000.0)
          w_lat_95[i] = w_lat_95[i] / ((num_vm - vm_finish_early) * 1000000.0)
          puts "There are #{vm_finish_early} VMs finished testing early, those VMs are not used for summarizing results", resfile if vm_finish_early > 0
          puts "=============================", resfile
          puts "JOB_NAME\t= #{job_names[i]}", resfile
          puts "VMs\t\t= #{num_vm-vm_finish_early}", resfile
          puts "IOPS\t\t= #{'%.2f'% iops[i]} IO/S", resfile
          puts "THROUGHPUT\t= #{'%.2f'% throughput[i]} MB/s", resfile
          puts "R_LATENCY\t= #{'%.4f'% r_lat[i]} ms", resfile
          puts "W_LATENCY\t= #{'%.4f'% w_lat[i]} ms", resfile
          puts "95%tile_R_LAT\t= #{'%.4f'% r_lat_95[i]} ms", resfile
          puts "95%tile_W_LAT\t= #{'%.4f'% w_lat_95[i]} ms", resfile
          puts "=============================", resfile
        end
      end
      puts "Resource Usage:", resfile
      puts res_usage, resfile
    else
      puts "#{dir} doesn't exist!"
    end
    if files_finished_early != []
      puts "Check the following results files that finished testing early:", resfile
      files_finished_early.each do |file|
        puts file, resfile
      end
    end
    hcibench_version=`cat /etc/hcibench_version`.chomp
    `cd "#{dir}"; cp -r #{$log_path} "#{dir}"/; tar zcfP HCIBench-#{hcibench_version}-logs.tar.gz -C logs .; rm -rf logs`
  end
end
