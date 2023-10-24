#! /usr/bin/ruby

require 'fileutils'

require_relative 'ossl_wrapper'

# Key Generate
def key_generate(osw)
  if osw.key_exists
    unless osw.key_valid
      STDERR.puts("key path exist but not a valid file: #{key_path}")
      exit(1)
    end
  else
    FileUtils.mkpath(File.dirname(osw.get_key_path)) unless File.exist?(File.dirname(osw.get_key_path))
  end
  begin
    puts osw.key_generate
    exit(0)
  rescue StandardError => e
    STDERR.puts "openssl error: #{e}"
    puts false
    exit(1)
  end
end

# Key Delete
def key_delete(osw)
  begin
    puts osw.key_delete
    exit(0)
  rescue StandardError => e
    puts "openssl error: #{e}"
    exit(1)
  end
end

# Key Exists
def key_exists(osw)
  begin
    puts osw.key_exists && osw.key_valid
    exit(0)
  rescue StandardError => e
    puts "openssl error: #{e}"
    exit(1)
  end
end

# Encrypt
def encrypt(osw, plaintext)
  unless osw.key_exists
    STDERR.puts 'cannot encrypt because key does not exist; make sure to generate one beforehand'
    exit(1)
  end
  unless osw.key_valid
    STDERR.puts 'cannot encrypt because key is not valid; check key path or generate a valid key'
    exit(1)
  end
  begin
    puts osw.encrypt(plaintext)
    exit(0)
  rescue StandardError => e
    puts "openssl error: #{e}"
    exit(1)
  end
end

# Decrypt
def decrypt(osw, ciphertext)
  unless osw.key_exists
    STDERR.puts 'cannot decrypt because key does not exist'
    exit(1)
  end
  unless osw.key_valid
    STDERR.puts 'cannot decrypt because key is not valid; check key path or generate a valid key'
    exit(1)
  end
  begin
    puts osw.decrypt(ciphertext)
    exit(0)
  rescue StandardError => e
    puts "openssl error: #{e}"
    exit(1)
  end
end