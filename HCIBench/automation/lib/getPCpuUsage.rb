#!/usr/bin/ruby
require "rubygems"
require "json"
require_relative "rvc-util.rb"

msg = ""
if ARGV.empty?
  puts "Usage"
  exit(1)
else
  ARGV.each do |dir|
    @cluster_hosts_map = _get_cluster_hosts_map_from_file(dir)
    @cluster_hosts_map.keys.each do |cluster_name|
      if File.directory?(dir)
        pcpu_usage=
        total_pcpu=
        dirName = File.basename(dir)
        Dir.entries(dir).select {|entry| File.directory? File.join(dir,entry) and !(entry =='.' || entry == '..') and entry =~ /iotest-/}.each do |ioFolder|#enter io folder
          jsonFile_list = `find "#{dir}/#{ioFolder}"/jsonstats/pcpu/ -type f -name 'wdtsum-*' | grep -e "#{@cluster_hosts_map[cluster_name].join('\|')}" | grep -v thumb `
          jsonFile_list = jsonFile_list.split("\n")
          file_cpu_usage_arr = [] #each element should be the avg of each server cpu_usage number
          jsonFile_list.each do |file| # get each server's cpu_usage number
            jsonFile = open(file)
            json = jsonFile.read
            begin
              parsed = JSON.parse(json)
            rescue JSON::ParserError => e
              p e
              exit 1
            end
            arr = parsed["stats"]["runTime"]["avgs"]
            avg_of_file = arr.inject { |sum, el| sum + el }.to_f / arr.size * 100
            file_cpu_usage_arr.push(avg_of_file)
          end
          pcpu_usage=file_cpu_usage_arr.inject{ |sum, el| sum + el }.to_f
        end
        Dir.entries(dir).select {|entry| File.directory? File.join(dir,entry) and !(entry =='.' || entry == '..') and entry =~ /iotest-/}.each do |ioFolder|#enter io folder
          jsonFile_list = `find "#{dir}/#{ioFolder}"/jsonstats/pcpu/ -type f -name 'pcpu*' | grep -e "#{@cluster_hosts_map[cluster_name].join('\|')}" | grep -v thumb`
          jsonFile_list=jsonFile_list.split("\n")
          total_num_of_pcpu = [] #each element should be the avg of each server cpu_usage number
          jsonFile_list.each do |file| # get each server's cpu_usage number
            jsonFile = open(file)
            json = jsonFile.read
            parsed = JSON.parse(json)
            total_num_of_pcpu.push(parsed["stats"].size)
          end
          total_pcpu = total_num_of_pcpu.inject{ |sum, el| sum + el }
        end
        msg += "#{cluster_name}: #{(pcpu_usage/total_pcpu).round(2)}%; " if pcpu_usage != 0.0
      else
        puts "#{dir} doesn't exist!"
        exit(1)
      end
    end
  end
end

if msg.count(";") == 1
  print msg.scan(/[0-9]*.[0-9]*%/).join 
else
  print msg
end
