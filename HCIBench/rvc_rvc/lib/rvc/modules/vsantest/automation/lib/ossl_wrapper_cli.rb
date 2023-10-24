#! /usr/bin/ruby

require_relative 'ossl_wrapper'
require_relative 'ossl_wrapper_cli_parser'
require_relative 'ossl_wrapper_cli_commands'
require_relative 'ossl_wrapper_util'

# Get CLI arguments
opts = OSSLCliParser.parse ARGV

# Create object
osw = OSSLWrapper.new(set_options(opts))

# Run command
case decode_command(opts)
when Command::ENCRYPT
  encrypt(osw, opts.encrypt)

when Command::DECRYPT
  decrypt(osw, opts.decrypt)

when Command::KEYGENERATE
  key_generate(osw)

when Command::KEYEXISTS
  key_exists(osw)

when Command::KEYDELETE
  key_delete(osw)

else
  # Invalid number of operations
  STDERR.puts 'only one operation permitted at a time: encrypt, decrypt, key-generate, or key-exists, or key-delete'
  exit(1)
end