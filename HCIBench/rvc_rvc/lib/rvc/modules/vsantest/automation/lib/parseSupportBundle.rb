#!/usr/bin/ruby
require_relative "util.rb"
require_relative "rvc-util.rb"
require 'fileutils'

@parse_support_bundle_log = "#{$log_path}/supportBundleParse.log"

def parseSupportBundle bundle_path, test_case_name
  if not File.exist?(bundle_path)
    puts "File #{bundle_path} not exist"
    exit(255)
  end

  dest_folder = File.dirname(bundle_path)
  bundle_file_name = File.basename(bundle_path)
  bundle_dir_name = bundle_file_name.gsub('.', '_')
  FileUtils.mkdir_p("#{dest_folder}/#{bundle_dir_name}")

  puts "Unzipping support bundle...", @parse_support_bundle_log
  `tar -zxvf "#{bundle_path}" -C "#{dest_folder}/#{bundle_dir_name}" --strip-components=1`

  puts "Combining stats and cmmd files...", @parse_support_bundle_log
  `cat #{dest_folder}/#{bundle_dir_name}/commands/python_*vsan-perfsvc-statuspy* > "#{dest_folder}/#{bundle_dir_name}/perf-stats.txt"`
  `cat #{dest_folder}/#{bundle_dir_name}/commands/cmmds-tool_find--f-python.txt* > "#{dest_folder}/#{bundle_dir_name}/cmmds-tool_find--f-python.txt"`

  puts "Ingest into InfluxDB...", @parse_support_bundle_log
  humbug_link = `python2 /opt/automation/lib/parse-support-bundle/scripts/perf_analysis.py -f "#{dest_folder}/#{bundle_dir_name}/perf-stats.txt" -p SoapParser -n #{test_case_name} -e #{$ip_Address} -i 172.17.0.1`.chomp
  puts humbug_link, @parse_support_bundle_log
  return humbug_link
end

if ARGV[0]
  bundle_path = ARGV[0]
  test_case_name = ARGV[1] || bundle_path.split("/")[-3]
  link = parseSupportBundle(bundle_path, test_case_name)
  `echo "#{link}" > #{$humbug_link_file}`
end
