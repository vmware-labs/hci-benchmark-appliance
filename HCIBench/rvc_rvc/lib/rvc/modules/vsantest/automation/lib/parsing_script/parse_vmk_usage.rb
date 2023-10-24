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
          jsonFile_list = `find "#{dir}/#{ioFolder}"/jsonstats/misc/ -type f -name 'vmknic-*' |grep -v thumb `
          jsonFile_list=jsonFile_list.split("\n")
	  file_arr = []
          rcv_bytes_arr = [] #each element should be the avg of each server receive bytes
          rcv_bytes_95th = []
          snd_bytes_arr = [] #each element should be the avg of each server receive bytes
          snd_bytes_95th = []
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
            arr_rcv = parsed["stats"]["tcp"]["rcvbyte"]["avgs"]
            arr_snd = parsed["stats"]["tcp"]["sndbyte"]["avgs"]

            arr_rcv_avg = (arr_rcv.inject { |sum, el| sum + el }.to_f / (arr_rcv.size * 1024 * 1024)).round(2)
            rcv_bytes_95th << percentile_by_value(arr_rcv, 0.95)

            arr_snd_avg = (arr_snd.inject { |sum, el| sum + el }.to_f / (arr_snd.size * 1024 * 1024)).round(2)
            snd_bytes_95th << percentile_by_value(arr_snd, 0.95)

            rcv_bytes_arr << arr_rcv_avg
            snd_bytes_arr << arr_snd_avg
          end
#          puts file_arr
          puts "Rx average Bandwidth: #{rcv_bytes_arr}"
          puts "Rx 95tile Bandwidth: #{rcv_bytes_95th}"

          puts "Tx average Bandwidth: #{snd_bytes_arr}"
          puts "Tx 95tile Bandwidth: #{snd_bytes_95th}"

        end
    else
      puts "#{dir} doesn't exist!"
      exit(1)
    end
  end
end
