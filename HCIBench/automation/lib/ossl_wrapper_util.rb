
require 'fileutils'

# Function to temporarily suppress STDOUT and STDERR by redirecting them
# to /dev/null
#
# Ref. https://gist.github.com/moertel/11091573
#
def suppress_output
  original_stdout, original_stderr = $stdout.clone, $stderr.clone
  $stderr.reopen File.new('/dev/null', 'w')
  $stdout.reopen File.new('/dev/null', 'w')
  yield
ensure
  $stdout.reopen original_stdout
  $stderr.reopen original_stderr
end

# Enum of commands
module Command
  ENCRYPT = 1
  DECRYPT = 2
  KEYGENERATE = 4
  KEYEXISTS = 8
  KEYDELETE = 16
end

# Decode command from optparse output
def decode_command(opts)
  operation = 0
  operation += Command::ENCRYPT unless opts.encrypt.nil?
  operation += Command::DECRYPT unless opts.decrypt.nil?
  operation += Command::KEYGENERATE unless opts.keygenerate.nil?
  operation += Command::KEYEXISTS unless opts.keyexists.nil?
  operation += Command::KEYDELETE unless opts.keydelete.nil?
  operation
end

# Convert optparse output into OSSLWrapper constructor input
def set_options(opts)
  # Set the key path
  if !opts.key.nil?
    key_path = File.expand_path(opts.key.chomp)
  else
    key_path = 'key.bin'
  end

  # Set the openssl path
  if !opts.openssl.nil?
    openssl_path = File.expand_path(opts.openssl.chomp)
  else
    openssl_path = '/usr/bin/openssl'
  end

  # Set the openssl path
  if !opts.cipher.nil?
    cipher = File.expand_path(opts.cipher.chomp)
  else
    cipher = 'aes-256-cbc'
  end

  { keyfile: key_path, openssl: openssl_path, cipher: cipher }
end