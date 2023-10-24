require 'time'
require 'fileutils'

module RVC

class ScreenLogger
  attr_accessor :log_file

  def log text
    if @log_file
      @log_file.write(text)
      @log_file.flush
    end
  end

  def log_input input
    log("#{Time.now}: " + input + "\n")
  end

  def disable
    if @log_file
      puts "#{Time.now}: Done disable screen logging for file #{@log_file.path}"
      @log_file.close
      @log_file = nil
    end
  end

  def enable file_path = nil
    if @log_file
      puts "Screen logging has already been enabled, log file #{@log_file.path}"
    else
      if !file_path
        home_path = OS.windows? ? ENV['HOMEPATH'] : ENV['HOME']
        file_path = "#{home_path}/rvc-screen-#{Time.now.to_i}.log"
        puts "#{Time.now}: Starting to enable screen logging"
      end
      begin
        file_dir = File.dirname(file_path)
        if !File.directory?(file_dir)
          FileUtils.mkdir_p file_dir
        end
        @log_file = File.new(file_path, 'w')
      rescue Exception
        puts "Cannot create log file #{file_path}"
        @log_file = nil
        return
      end
      puts "#{Time.now}: Done start screen logging, log file #{file_path}"
    end
  end
end
end
