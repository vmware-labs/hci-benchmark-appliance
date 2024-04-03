require 'fileutils'
require "json"
require 'timeout'
require 'shellwords'
require 'resolv'
require 'net/ssh'
require 'net/scp'
require_relative "rvc-util.rb"

def puts(o,f=nil)
  o = "#{Time.now}: " + o.to_s
  super(o)
  if not f.nil?
    open(f, 'a') do |file|
      file.puts o
    end
  end
end

def ssh_valid(host, user ,pass)
  begin
    session = Net::SSH.start( host.to_s, user.to_s, :password => pass.to_s, :number_of_password_prompts => 0, :non_interactive => true)
    session.close
    return true
  rescue Net::SSH::ConnectionTimeout
    p "Timed out"
  rescue Timeout::Error
    p "Timed out"
  rescue Errno::EHOSTUNREACH
    p "Host unreachable"
  rescue Errno::ECONNREFUSED
    p "Connection refused"
  rescue Net::SSH::AuthenticationFailed
    p "Authentication failure"
  rescue Exception => e
    p "#{e.class}: #{e.message}"
  end
  return false
end

def ssh_cmd_with_return(host, user, pass, cmd)
  return_stdout = ""
  begin
    Net::SSH.start( host.to_s, user.to_s, :password => pass.to_s, :number_of_password_prompts => 0 ) do |ssh|
      return_stdout = ssh.exec!(cmd.to_s)
      ssh.close
    end
  rescue Net::SSH::ConnectionTimeout
    p "Timed out"
  rescue Timeout::Error
    p "Timed out"
  rescue Errno::EHOSTUNREACH
    p "Host unreachable"
  rescue Errno::ECONNREFUSED
    p "Connection refused"
  rescue Net::SSH::AuthenticationFailed
    p "Authentication failure"
  rescue Exception => e
    p "#{e.class}: #{e.message}"
  end
  return return_stdout
end

def ssh_cmd(host, user, pass, cmd)
  return_value = ""
  begin
    Net::SSH.start( host.to_s, user.to_s, :password => pass.to_s, :number_of_password_prompts => 0 ) do |ssh|
      return_value = ssh.exec!(cmd.to_s)
      ssh.close
    end
  rescue Net::SSH::ConnectionTimeout
    p "Timed out"
  rescue Timeout::Error
    p "Timed out"
  rescue Errno::EHOSTUNREACH
    p "Host unreachable"
  rescue Errno::ECONNREFUSED
    p "Connection refused"
  rescue Net::SSH::AuthenticationFailed
    p "Authentication failure"
  rescue Exception => e
    p "#{e.class}: #{e.message}"
  end
  return return_value
end

def scp_item(host, user, pass, source, dest)
  begin 
    Net::SCP.start( host.to_s, user.to_s, :password => pass.to_s, :number_of_password_prompts => 0 ) do |scp|
      scp.upload!(source, dest)
    end
    p "#{source} upload to #{host}:#{dest} success"
    return true
  rescue Net::SSH::ConnectionTimeout
    p "Timed out"
  rescue Timeout::Error
    p "Timed out"
  rescue Errno::EHOSTUNREACH
    p "Host unreachable"
  rescue Errno::ECONNREFUSED
    p "Connection refused"
  rescue Net::SSH::AuthenticationFailed
    p "Authentication failure"
  rescue Exception => e
    p "#{e.class}: #{e.message}"
  end
  p "#{source} upload to #{host}:#{dest} failed"
  return false
end

def download_item(host, user, pass, source, dest, opt={})
  begin
    Net::SCP.start( host.to_s, user.to_s, :password => pass.to_s, :number_of_password_prompts => 0 ) do |scp|
      scp.download!(source, dest, opt)
    end
    p "#{host}:#{source} download to local #{dest} success"
    return
  rescue Net::SSH::ConnectionTimeout
    p "Timed out"
  rescue Timeout::Error
    p "Timed out"
  rescue Errno::EHOSTUNREACH
    p "Host unreachable"
  rescue Errno::ECONNREFUSED
    p "Connection refused"
  rescue Net::SSH::AuthenticationFailed
    p "Authentication failure"
  rescue Exception => e
    p "#{e.class}: #{e.message}"
  end
  p "#{host}:#{source} download to local #{dest} failed"
end

def extractJsonsFromFile(file)
  count = 0
  fullText = ''
  jsons = []
  no_brace = true
  File.readlines(file).each do |line|
    no_brace = false if line.lstrip[0] == "{"
    next if no_brace
    count += (line.count('{') - line.count('}'))
    fullText += line
    if count == 0
      no_brace = true
      if fullText.count('{') > 0
        jsonPiece = JSON.parse(fullText)
        jsons << jsonPiece
      end
      fullText = ''
    end
  end
  return jsons
end

def extractResultJson(jsons)
  parsed = {}
  jsons.each do |json|
    if json['jobs'][0]['eta'] == 0
      parsed = json
      break
    end
  end
  return parsed
end
