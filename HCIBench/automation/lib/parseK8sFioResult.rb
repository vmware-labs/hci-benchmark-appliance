#!/usr/bin/ruby
# parseK8sFioResult.rb
# Aggregates fio JSON results collected from K8s pods.
# Produces the same text summary format as parseFioResult.rb so that
# generate_report.rb and the UI can consume it unchanged.
#
# Usage: ruby parseK8sFioResult.rb <result_dir>

require_relative "rvc-util.rb"
require_relative "util.rb"
require "json"
require "pathname"

def puts_res(o, res_file)
  open(res_file, 'a') { |f| f << o + "\n" }
  $stdout.puts o
end

# Parse one or more concatenated JSON objects from a file (fio can emit them back-to-back)
def extract_fio_json(path)
  raw = File.read(path)
  # fio --output-format=json writes a single JSON object; handle concatenated runs
  depth  = 0
  start  = nil
  raw.each_char.with_index do |ch, i|
    if ch == '{'
      start = i if depth == 0
      depth += 1
    elsif ch == '}'
      depth -= 1
      return JSON.parse(raw[start..i]) if depth == 0 && start
    end
  end
  nil
rescue JSON::ParserError
  nil
end

if ARGV.empty?
  $stderr.puts "Usage: parseK8sFioResult.rb <result_dir>"
  exit(1)
end

ARGV.each do |dir|
  next unless File.directory?(dir)

  resfile = dir + "-res.txt"

  iops         = []
  throughput   = []
  r_lat        = []
  w_lat        = []
  r_lat_95     = []
  w_lat_95     = []
  job_names    = []
  max_num_jobs = 0
  num_vm       = 0
  vm_finish_early     = 0
  files_finished_early = []

  Dir.glob("#{dir}/*.json").sort.each do |file|
    parsed = extract_fio_json(file)
    num_jobs = 0
    num_vm  += 1
    if parsed && parsed['jobs']
      parsed['jobs'].each do |job|
        if iops[num_jobs].nil?
          iops[num_jobs]       = 0
          throughput[num_jobs] = 0
          r_lat[num_jobs]      = 0
          w_lat[num_jobs]      = 0
          r_lat_95[num_jobs]   = 0
          w_lat_95[num_jobs]   = 0
          job_names[num_jobs]  = job['jobname']
        end
        iops[num_jobs]       += job['read']['iops'].to_f  + job['write']['iops'].to_f
        throughput[num_jobs] += job['read']['bw'].to_f    + job['write']['bw'].to_f
        r_lat[num_jobs]      += job['read']['lat_ns']['mean'].to_f
        w_lat[num_jobs]      += job['write']['lat_ns']['mean'].to_f
        if job['read']['lat_ns']['percentile']
          r_lat_95[num_jobs] += job['read']['lat_ns']['percentile']['95.000000'].to_f
        end
        if job['write']['lat_ns']['percentile']
          w_lat_95[num_jobs] += job['write']['lat_ns']['percentile']['95.000000'].to_f
        end
        num_jobs += 1
      end
      max_num_jobs = num_jobs if num_jobs > max_num_jobs
    else
      vm_finish_early += 1
      files_finished_early << file
    end
  end

  sc_label = $k8s_storage_class.empty? ? "(default)" : $k8s_storage_class
  puts_res "StorageClass  = #{sc_label}", resfile
  puts_res "All pods finished testing early, no results summarized", resfile if max_num_jobs == 0

  active = num_vm - vm_finish_early
  active = 1 if active < 1

  (0...max_num_jobs).each do |i|
    throughput[i] = throughput[i] / 1024.0
    r_lat[i]      = r_lat[i]    / (active * 1_000_000.0)
    w_lat[i]      = w_lat[i]    / (active * 1_000_000.0)
    r_lat_95[i]   = r_lat_95[i] / (active * 1_000_000.0)
    w_lat_95[i]   = w_lat_95[i] / (active * 1_000_000.0)

    puts_res "There are #{vm_finish_early} pods that finished testing early, excluded from summary", resfile if vm_finish_early > 0
    puts_res "=============================", resfile
    puts_res "JOB_NAME\t= #{job_names[i]}", resfile
    puts_res "PODS\t\t= #{active}", resfile
    puts_res "IOPS\t\t= #{'%.2f' % iops[i]} IO/S", resfile
    puts_res "THROUGHPUT\t= #{'%.2f' % throughput[i]} MB/s", resfile
    puts_res "R_LATENCY\t= #{'%.4f' % r_lat[i]} ms", resfile
    puts_res "W_LATENCY\t= #{'%.4f' % w_lat[i]} ms", resfile
    puts_res "95%tile_R_LAT\t= #{'%.4f' % r_lat_95[i]} ms", resfile
    puts_res "95%tile_W_LAT\t= #{'%.4f' % w_lat_95[i]} ms", resfile
    puts_res "=============================", resfile
  end

  if files_finished_early.any?
    puts_res "Check the following result files that finished testing early:", resfile
    files_finished_early.each { |f| puts_res f, resfile }
  end

  hcibench_version = `cat /etc/hcibench_version 2>/dev/null`.chomp
  `cd "#{dir}"; cp -r "#{$log_path}" "#{dir}"/; tar zcfP HCIBench-#{hcibench_version}-logs.tar.gz -C logs . 2>/dev/null; rm -rf logs`
end
