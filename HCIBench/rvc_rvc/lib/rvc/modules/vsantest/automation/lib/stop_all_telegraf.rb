#!/usr/bin/ruby
require_relative "rvc-util.rb"
require "logger"
#Get the container id by name

logfilepath = "#{$log_path}telegraf.log"
log = Logger.new(logfilepath)
log.level = Logger::INFO

begin
    `kill -9 \`ps -ef | grep [t]elegraf | awk '{print $2}'\`` if `ps -ef | grep [t]elegraf | wc -l`.chomp != 0
    `rm -rf /opt/automation/conf/telegraf.conf`
    telegraf_running = `ps -ef | grep [t]elegraf | wc -l`
    if telegraf_running == "0"
      log.info "telegraf stopped"
    else
      _retry = 0
      while _retry < 5
        if `ps -ef | grep [t]elegraf | wc -l` == "1"
          log.info "telegraf still running, retry in 3 seconds"
          sleep(3)
          _retry += 1
        else
          log.info "telegraf stopped"
          break
        end
      end
    end
rescue Exception => e
    log.error "Exception happened: #{e.message}"
end
