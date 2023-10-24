#!/bin/env ruby
require 'yaml'
require 'time'
require 'net/ssh'
require 'net/scp'
require 'optparse'
require "/opt/automation/lib/util.rb"
require "/opt/automation/lib/rvc-util.rb"
require 'json'

if ARGV.empty? or ARGV.size < 1
  puts "Usage 'cmd + dirname'"
  exit(1)
else
  ARGV.each do |dir|
  	if File.directory?(dir)
  		kafka_results = File.join(dir, "kafka_results/")
  		res_33 = File.join(kafka_results, "automation-kafka")
  		res_34 = File.join(kafka_results, "automation-kafka-34")
  		for res in [res_33,res_34]
  			Dir.chdir(res)
  			producer_jsons = `find "$(pwd)" -type f -name 'producer_*.json'`.chomp.split("\n")
        consumer_jsons = `find "$(pwd)" -type f -name 'consumer_*.json'`.chomp.split("\n")
        if res.include? "34"
            ds = "vSAN-34"
          else
            ds = "vSAN-33"
          end
        if producer_jsons != []
          tput_arr = []
          avg_lat_arr = []
          max_lat_arr = []
          lat_50_arr = []
          lat_95_arr = []
          producer_jsons.each do |json_file|
            jsonFile = open(json_file)
            json = jsonFile.read
            json_content = JSON.parse(json)
            line = json_content["stdout_lines"][-1]
            tput_arr << `echo "#{line}" | cut -d '(' -f2 | cut -d ' ' -f1`.chomp.to_f
            avg_lat_arr << `echo "#{line}" | cut -d ',' -f3 | cut -d ' ' -f1-`.chomp.to_f
            max_lat_arr << `echo "#{line}" | cut -d ',' -f4 | cut -d ' ' -f1-`.chomp.to_f
            lat_50_arr << `echo "#{line}" | cut -d ',' -f5 | cut -d ' ' -f1-`.chomp.to_f
            lat_95_arr << `echo "#{line}" | cut -d ',' -f6 | cut -d ' ' -f1-`.chomp.to_f
          end
          sum_tput = tput_arr.inject{ |sum, el| sum + el }
          avg_lat = (avg_lat_arr.inject{ |sum, el| sum + el }.to_f / avg_lat_arr.size).round(2)
          max_lat = max_lat_arr.max()
          lat_50 = (lat_50_arr.inject{ |sum, el| sum + el }.to_f / lat_50_arr.size).round(2)
          lat_95 = (lat_95_arr.inject{ |sum, el| sum + el }.to_f / lat_95_arr.size).round(2)

          
          print "#{Pathname.new(dir).basename}-#{ds}, Aggregated Throughput, Average Latency, Max Latency, 50tile Latency, 95tile Latency\n"
          print " , #{sum_tput}, #{avg_lat}, #{max_lat}, #{lat_50}, #{lat_95}\n"
        else
          #consumer!
          max_duration = 0
          avg_dur_arr = []
          consumer_jsons.each do |json_file|
            jsonFile = open(json_file)
            json = jsonFile.read
            json_content = JSON.parse(json)
            line = json_content["delta"]
            duration = line.split(':').map(&:to_i).inject(0) { |a, b| a * 60 + b }.to_f + ("0." + line.split(".")[-1]).to_f
            avg_dur_arr << duration
            max_duration = duration if duration > max_duration
          end
          print "#{Pathname.new(dir).basename}-#{ds} avg, #{(avg_dur_arr.inject{ |sum, el| sum + el }/ avg_dur_arr.size).round(2)}\n"
          print "#{Pathname.new(dir).basename}-#{ds}, #{max_duration}\n"
        end
  		end
  	end
  end
end


