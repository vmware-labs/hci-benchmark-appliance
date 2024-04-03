#! /usr/bin/ruby

require 'test/unit'

require_relative '../ossl_wrapper'
require_relative '../ossl_wrapper_cli_parser'
require_relative  "../ossl_wrapper_util"

class Flag
  def initialize(short, long, key, has_arg)
    @short = short
    @long = long
    @arg = has_arg
    @key = key
  end

  def get_short
    @short
  end

  def get_long
    @long
  end

  def get_key
    @key
  end

  def has_arg
    @arg
  end
end

class TestOsslWrapperCliParser < Test::Unit::TestCase

  def initialize(arg)
    super(arg)

    all_lowercase, all_uppercase = ('a'..'z').to_a, ('A'..'Z').to_a
    all_symbols = %w(! @ # $ % ^ & * \( \) [ ] { } ' " : ; , . / \\ - _ +)
    all = all_lowercase + all_uppercase + all_symbols

    # All valid flags
    @flags = Array.new
    @flags.push(Flag.new('e', 'encrypt', "encrypt", true ))
    @flags.push(Flag.new('d', 'decrypt', "decrypt", true ))
    @flags.push(Flag.new('k', 'key', "key", true ))
    @flags.push(Flag.new('o', 'openssl', "openssl", true ))
    @flags.push(Flag.new('c', 'cipher', "cipher", true ))
    @flags.push(Flag.new(nil, 'key-generate', "keygenerate", false ))
    @flags.push(Flag.new(nil, 'key-delete', "keydelete", false ))
    @flags.push(Flag.new(nil, 'key-exists', "keyexists", false ))

    # Create a list of all short flags
    @invalid_flags_short = all_lowercase + all_uppercase

    # Create a list of random long flags
    @invalid_flags_long = Array.new
    (1..100).each do @invalid_flags_long.push((1..3+rand(18)).map {all.to_a[rand(all.length)]}.join) end

    # Remove valid from invalids
    @flags.each do |flag|
      @invalid_flags_short.delete(flag.get_short) if flag.get_short
      @invalid_flags_long.delete(flag.get_long)
    end

    # Delete help flags
    @invalid_flags_short.delete('h')
    @invalid_flags_long.delete('help')
  end

  # Called before every test method runs. Can be used
  # to set up fixture information.
  def setup
    # Nothing
  end

  # Called after every test method runs. Can be used to tear
  # down fixture information.
  def teardown
    # Nothing
  end

  # Flags: short valid
  def test_001
    @flags.each do |test|
      next unless test.get_short
      cmd = Array.new
      cmd.push("-#{test.get_short}")
      cmd.push('foo') if test.has_arg
      opts = OSSLCliParser.parse cmd
      expected = 'foo'
      expected = true unless test.has_arg
      assert(opts[test.get_long] == expected, 'short flag value did not match')
    end
  end

  # Flags: long valid
  def test_002
    @flags.each do |test|
      cmd = Array.new
      cmd.push("--#{test.get_long}")
      cmd.push('foo') if test.has_arg
      opts = OSSLCliParser.parse cmd
      expected = 'foo'
      expected = true unless test.has_arg
      assert(opts[test.get_key] == expected, 'long flag value did not match')
    end
  end

  # Flags: None
  def test_003
    assert_raise SystemExit, 'exception SystemExit was not raised on no arguments' do
      cmd = Array.new
      suppress_output { OSSLCliParser.parse cmd }
    end
  end

  # Flags: -h
  def test_004
    assert_raise SystemExit, 'exception SystemExit was not raised on flag: -h' do
      cmd = Array.new
      cmd.push('-h')
      suppress_output { OSSLCliParser.parse cmd }
    end
  end

  # Flags: --help
  def test_005
    assert_raise SystemExit, 'exception SystemExit was not raised on flag: --help' do
      cmd = Array.new
      cmd.push('--help')
      suppress_output { OSSLCliParser.parse cmd }
    end
  end

  # Flags: invalid short flags
  def test_006
    @invalid_flags_short.each do |test|
      assert_raise SystemExit, "exception SystemExit was not raised on flag: -#{test}" do
        cmd = Array.new
        cmd.push("-#{test}")
        suppress_output {OSSLCliParser.parse cmd}
      end
    end
  end

  # Flags: invalid short flags with argument
  def test_007
    @invalid_flags_short.each do |test|
      assert_raise SystemExit, "exception SystemExit was not raised on flag: -#{test}" do
        cmd = Array.new
        cmd.push("-#{test}")
        cmd.push('foo')
        suppress_output {OSSLCliParser.parse cmd}
      end
    end
  end

  # Argument: invalid long flags
  def test_008
    @invalid_flags_long.each do |test|
      assert_raise SystemExit, "exception SystemExit was not raised on flag: -#{test}" do
        cmd = Array.new
        cmd.push("--#{test}")
        suppress_output {OSSLCliParser.parse cmd}
      end
    end
  end

  # Argument: invalid long flag with argument
  def test_009
    @invalid_flags_long.each do |test|
      assert_raise SystemExit, "exception SystemExit was not raised on flag: -#{test}" do
        cmd = Array.new
        cmd.push("--#{test}")
        cmd.push('foo')
        suppress_output {OSSLCliParser.parse cmd}
      end
    end
  end

  # Argument: one short valid, one short invalid
  def test_010
    @flags.each do |test1|
      @invalid_flags_short.each do |test2|
        next unless test1.get_short
        cmd = Array.new
        cmd.push("-#{test1.get_short}")
        cmd.push('foo') if test1.has_arg
        cmd.push("-#{test2}")
        assert_raise SystemExit, "exception SystemExit was not raised on flags: -#{test1.get_short} -#{test2}" do
          suppress_output {OSSLCliParser.parse cmd}
        end
      end
    end
  end

  # Argument: one short valid, one short invalid with argument
  def test_011
    @flags.each do |test1|
      @invalid_flags_short.each do |test2|
        next unless test1.get_short
        cmd = Array.new
        cmd.push("-#{test1.get_short}")
        cmd.push('foo') if test1.has_arg
        cmd.push("-#{test2}")
        cmd.push('foo')
        assert_raise SystemExit, "exception SystemExit was not raised on flags: -#{test1.get_short} -#{test2}" do
          suppress_output {OSSLCliParser.parse cmd}
        end
      end
    end
  end

  # Argument: one short invalid, one short valid
  def test_012
    @flags.each do |test1|
      @invalid_flags_short.each do |test2|
        next unless test1.get_short
        cmd = Array.new
        cmd.push("-#{test2}")
        cmd.push("-#{test1.get_short}")
        cmd.push('foo') if test1.has_arg
        assert_raise SystemExit, "exception SystemExit was not raised on flags: -#{test2} -#{test1.get_short} " do
          suppress_output {OSSLCliParser.parse cmd}
        end
      end
    end
  end

  # Argument: one short invalid with argument, one short valid
  def test_013
    @flags.each do |test1|
      @invalid_flags_short.each do |test2|
        next unless test1.get_short
        cmd = Array.new
        cmd.push("-#{test2}")
        cmd.push('foo')
        cmd.push("-#{test1.get_short}")
        cmd.push('foo') if test1.has_arg
        assert_raise SystemExit, "exception SystemExit was not raised on flags: -#{test2} -#{test1.get_short} " do
          suppress_output {OSSLCliParser.parse cmd}
        end
      end
    end
  end

  # Argument: one long valid, one long invalid
  def test_014
    @flags.each do |test1|
      @invalid_flags_long.each do |test2|
        next unless test1.get_short
        cmd = Array.new
        cmd.push("--#{test1.get_long}")
        cmd.push('foo') if test1.has_arg
        cmd.push("--#{test2}")
        assert_raise SystemExit, "exception SystemExit was not raised on flags: -#{test1.get_long} -#{test2}" do
          suppress_output {OSSLCliParser.parse cmd}
        end
      end
    end
  end

  # Argument: one long valid, one long invalid with argument
  def test_015
    @flags.each do |test1|
      @invalid_flags_long.each do |test2|
        cmd = Array.new
        cmd.push("--#{test1.get_long}")
        cmd.push('foo') if test1.has_arg
        cmd.push("--#{test2}")
        cmd.push('foo')
        assert_raise SystemExit, "exception SystemExit was not raised on flags: -#{test1.get_long} -#{test2}" do
          suppress_output {OSSLCliParser.parse cmd}
        end
      end
    end
  end

  # Argument: one long invalid, one long valid
  def test_016
    @flags.each do |test1|
      @invalid_flags_long.each do |test2|
        cmd = Array.new
        cmd.push("--#{test2}")
        cmd.push("--#{test1.get_long}")
        cmd.push('foo') if test1.has_arg
        assert_raise SystemExit, "exception SystemExit was not raised on flags: -#{test1.get_long} -#{test2}" do
          suppress_output {OSSLCliParser.parse cmd}
        end
      end
    end
  end

  # Argument: one long invalid with argument, one long valid
  def test_017
    @flags.each do |test1|
      @invalid_flags_long.each do |test2|
        cmd = Array.new
        cmd.push("--#{test2}")
        cmd.push('foo')
        cmd.push("--#{test1.get_long}")
        cmd.push('foo') if test1.has_arg
        assert_raise SystemExit, "exception SystemExit was not raised on flags: -#{test1.get_long} -#{test2}" do
          suppress_output {OSSLCliParser.parse cmd}
        end
      end
    end
  end

end
