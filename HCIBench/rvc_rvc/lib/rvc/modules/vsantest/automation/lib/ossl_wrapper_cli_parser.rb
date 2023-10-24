
require 'optparse'

# This class  parses the CLI input for the OSSL Wrapper CLI
class OSSLCliParser

  Options = Struct.new(:encrypt, :decrypt, :key, :openssl, :cipher, :keygenerate, :keyexists, :keydelete)
  @opts = ''

  def self.parse(options)
    options = ['-h'] if options.empty?
    args = Options.new
    opt_parser = OptionParser.new do |opts|
      opts.banner = "Usage: example.rb [options]"

      opts.on("-e TEXT", "--encrypt PLAINTEXT", String, "Encrypt the plaintext using OpenSSL") do |n|
        args.encrypt = n
      end

      opts.on("-d TEXT", "--decrypt TEXT", String, "Decrypt the plaintext using OpenSSL") do |n|
        args.decrypt = n
      end

      opts.on("-k TEXT", "--key TEXT", String, "File containing the pass for OpenSSL") do |n|
        args.key = n
      end

      opts.on("-o TEXT", "--openssl TEXT", String, "Path to OpenSSL binary") do |n|
        args.openssl = n
      end

      opts.on("-c TEXT", "--cipher TEXT", String, "Cipher to use for encryption and decryption") do |n|
        args.cipher = n
      end

      opts.on("--key-generate", "Generate a new key file") do
        args.keygenerate = true
      end

      opts.on("--key-delete", "Delete key file if it exists") do
        args.keydelete = true
      end

      opts.on("--key-exists", "Checks if the key file exists") do
        args.keyexists = true
      end

      opts.on("-h", "--help", "Prints this help") do
        puts opts
        exit(0)
      end

      @opts = opts
    end

    begin
      opt_parser.parse!(options)
    rescue OptionParser::InvalidOption => e
      STDERR.puts("CLI parsing error: #{e}")
      puts @opts
      exit(1)
    end

    return args
  end
end