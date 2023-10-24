#! /usr/bin/ruby

require 'base64'
require 'pathname'
require 'open3'
require 'fileutils'

class OSSLWrapper

  def initialize(keyfile: 'key.bin', openssl: '/usr/bin/openssl', cipher: 'aes-256-cbc', **kargs)
    @keyfile = keyfile
    @openssl = openssl
    @cipher = cipher
  end

  def encrypt(plaintext)
    raise "openssl path is invalid: #{File.expand_path(@openssl)}"  unless File.exist?(@openssl)
    raise "key does not exist: #{File.join(File.dirname(__FILE__), @keyfile)}"  unless File.exist?(@keyfile)
    cmd = "echo \"#{Base64.encode64(plaintext)}\" | #{@openssl} enc -#{@cipher} -a -A -pass file:\"#{@keyfile}\""
    stdout, stderr, status = popen_wrapper cmd
    raise 'error encrypting plaintext:' + stderr unless status == 0 and stderr.empty?
    stdout.chomp
  end

  def decrypt(ciphertext)
    raise "openssl path is invalid: #{File.expand_path(@openssl)}"  unless File.exist?(@openssl)
    raise "key does not exist: #{File.expand_path(@keyfile)}" unless File.exist?(@keyfile)
    cmd = "echo \"#{ciphertext}\" | #{@openssl}  enc -#{@cipher} -a -A -d -pass file:\"#{@keyfile}\""
    stdout, stderr, status = popen_wrapper cmd
    raise stderr unless status == 0 and stderr.empty?
    Base64.decode64(stdout).chomp
  end

  def key_generate(length: 128)
    raise "openssl path is invalid: #{File.expand_path(@openssl)}"  unless File.exist?(@openssl)
    cmd = "export RANDFILE=/dev/urandom; #{@openssl} rand -base64 #{length}"
    stdout, stderr, status = popen_wrapper cmd
    raise stderr unless status == 0 and stderr.empty?
    open(@keyfile, 'w', 0644) {|f| f.write(stdout.chomp)}
    true
  end

  def key_exists
    File.exist?(@keyfile)
  end

  def key_valid
    File.file?(@keyfile)
  end

  def key_delete
    return (File.delete(@keyfile) == 1) if File.exist?(@keyfile)
    false
  end

  def get_key_path
    @keyfile
  end

  private

  # noinspection RubyUnusedLocalVariable
  def popen_wrapper(cmd)
    Open3.popen3(cmd) do |stdin, stdout, stderr, wait_thr|
      stdout = stdout.read
      stderr = stderr.read
      exitstatus = wait_thr.value.exitstatus
      return stdout, stderr, exitstatus
    end
  end
end

