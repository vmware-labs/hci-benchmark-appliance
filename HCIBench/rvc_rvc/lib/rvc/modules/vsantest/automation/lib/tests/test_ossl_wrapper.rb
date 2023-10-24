#! /usr/bin/ruby

require 'test/unit'

require_relative '../ossl_wrapper'

class TestOsslWrapper < Test::Unit::TestCase

  def initialize(arg)
    super(arg)

    all_lowercase = ('a'..'z').to_a
    all_uppercase = ('A'..'Z').to_a
    all_symbols = %w(! @ # $ % ^ & * \( \) [ ] { } ' " : ; , . / \\ - = _ +)
    all = all_lowercase + all_uppercase + all_symbols

    # Create some random test strings
    @test_strings = ['my cat is named mittens', 'P@ssw0rd', 'VMware!23']
    (1..100).each do
      @test_strings.push((1..1 + rand(31)).map {all.to_a[rand(all.length)]}.join)
    end

  end

  # Called before every test method runs. Can be used
  # to set up fixture information.
  def setup
    @ob = OSSLWrapper.new
  end

  # Called after every test method runs. Can be used to tear
  # down fixture information.
  def teardown
    @ob.key_delete
  end

  def test_001
    @ob.key_delete
    assert(!@ob.key_exists, 'key exists')
  end

  def test_002
    @ob.key_delete
    @ob.key_generate
    assert(@ob.key_exists, 'key does not exist')
  end

  def test_003
    @ob.key_generate
    @test_strings.each do |test|
      c1 = @ob.encrypt(test)
      assert(c1 != test, 'plaintext not encrypted on input: [' + test + ']')
    end
  end

  def test_004
    @ob.key_generate
    @test_strings.each do |test|
      c1 = @ob.encrypt(test)
      p1 = @ob.decrypt(c1)
      assert(test == p1, 'plaintext does not match on input: [' + test + ']')
    end
  end

  def test_005
    @ob.key_generate
    @test_strings.each do |test|
      c1 = @ob.encrypt(test)
      c2 = @ob.encrypt(test)
      assert(c1 != c2, 'ciphertext was identical on input: [' + test + ']')
    end
  end

  def test_006
    @ob.key_generate
    @test_strings.each do |test|
      c1 = @ob.encrypt(test)
      c2 = @ob.encrypt(test)
      p1 = @ob.decrypt(c1)
      p2 = @ob.decrypt(c2)
      assert(c1 != c2, 'ciphertext was the same on input: [' + test + ']')
      assert(test == p1 && p1 == p2, 'plaintext does not match on input: [' + test + ']')
    end
  end

  def test_007
    OSSLWrapper.new(keyfile: '../key.bin', openssl: "openssl", cipher: 'aes-256-cbc')
  end
end