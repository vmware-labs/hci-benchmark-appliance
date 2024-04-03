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
        Dir.entries(dir).select {|entry| File.directory? File.join(dir,entry) and !(entry =='.' || entry == '..') and entry =~ /iotest-/}.each do |ioFolder|#enter io folder
          jsonFile_list = `find "#{dir}/#{ioFolder}"/jsonstats/mem/ -type f -name 'system*' | grep -e "#{@cluster_hosts_map[cluster_name].join('\|')}"  | grep -v thumb`
          jsonFile_list = jsonFile_list.split("\n")
          server_resource_usage_arr = [] 
          jsonFile_list.each do |file|
            jsonFile = open(file)
            json = jsonFile.read
            parsed = JSON.parse(json)
            each_resource_usage_arr = []
            arr = parsed["stats"]["pctMemUsed"]["values"]
            avg_each_ram = arr.inject{ |sum, el| sum + el }.to_f / arr.size
            each_resource_usage_arr.push(avg_each_ram)
            avg_each_test_server = each_resource_usage_arr.inject{ |sum, el| sum + el }.to_f / each_resource_usage_arr.size
            server_resource_usage_arr.push(avg_each_test_server)
          end
          avg_test_case = (server_resource_usage_arr.inject{ |sum, el| sum + el }.to_f / server_resource_usage_arr.size).round(2)
          msg += "#{cluster_name}: #{avg_test_case}%; "
        end
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