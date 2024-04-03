#!/usr/bin/ruby

require "rubygems"
require "json"

def percentile_by_value(values, percentile)
  values_sorted = values.sort
  k = (percentile*(values_sorted.length-1)+1).floor - 1
  f = (percentile*(values_sorted.length-1)+1).modulo(1)
  return ((values_sorted[k] + (f * (values_sorted[k+1] - values_sorted[k])))/(1024*1024)).round(2)
end

if ARGV.empty?
  puts "Usage"
  exit(1)
else
  ARGV.each do |dir|
    if File.directory?(dir)
      file = ""
      pcpu_usage=
      total_pcpu=
      dirName = File.basename(dir)
      parentDirName = File.basename(File.dirname(dir))
        Dir.entries(dir).select {|entry| File.directory? File.join(dir,entry) and !(entry =='.' || entry == '..') and entry =~ /observerData/}.each do |ioFolder|#enter io folder
          jsonFile_list = `find "#{dir}/#{ioFolder}"/jsonstats/dom/ -type f -name 'domobj-client-*' |grep -v thumb `
          jsonFile_list=jsonFile_list.split("\n").sort
	  file_arr = []
          w_bytes_arr = [] 
          r_bytes_arr = [] 
          jsonFile_list.sort.each do |file| # get each server's cpu_usage number
            file_arr << file
            jsonFile = open(file)
            json = jsonFile.read
            begin
              parsed = JSON.parse(json)
            rescue JSON::ParserError => e
              p "N/A" 
              exit 1
            end
            arr_r = parsed["stats"]["readLatency"]["avgs"][1..-1]
            arr_w = parsed["stats"]["writeLatency"]["avgs"][1..-1]

            arr_r_avg = (arr_r.inject { |sum, el| sum + el }.to_f / (arr_r.size * 1000)).round(2)

            arr_w_avg = (arr_w.inject { |sum, el| sum + el }.to_f / (arr_w.size * 1000)).round(2)

            r_bytes_arr << arr_r_avg
            w_bytes_arr << arr_w_avg
          end
          puts "Read Latency: #{r_bytes_arr}, Avg: #{(r_bytes_arr.inject{ |sum, el| sum + el }.to_f/r_bytes_arr.size).round(2)}"
          puts "Write Latency: #{w_bytes_arr}, Avg: #{(w_bytes_arr.inject{ |sum, el| sum + el }.to_f/r_bytes_arr.size).round(2)}"
        end
    else
      puts "#{dir} doesn't exist!"
      exit(1)
    end
  end
end
