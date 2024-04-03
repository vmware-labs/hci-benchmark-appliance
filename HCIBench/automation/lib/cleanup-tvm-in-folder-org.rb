#!/usr/bin/ruby
require_relative "rvc-util.rb"
require_relative "util.rb"

@tvm_folder_path_escape = _get_tvm_folder_path_escape[0]
@tvm_cleanup_log = "#{$log_path}/prevalidation/tvm-cleanup.log"
begin
	puts `rvc #{$vc_rvc} --path #{@tvm_folder_path_escape} -c "kill *" -c 'exit' -q`,@tvm_cleanup_log
	puts `rvc #{$vc_rvc} --path #{@tvm_folder_path_escape} -c "destroy ." -c 'exit' -q 2> /dev/null`,@tvm_cleanup_log
rescue Exception => e
	puts "dont worry, nothing critical",@tvm_cleanup_log
	puts "#{e.class}: #{e.message}",@tvm_cleanup_log
end