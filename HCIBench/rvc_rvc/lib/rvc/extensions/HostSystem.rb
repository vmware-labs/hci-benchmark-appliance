# Copyright (c) 2011 VMware, Inc.  All Rights Reserved.
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

class RbVmomi::VIM::HostSystem
  def self.ls_properties
    %w(name summary.hardware.memorySize summary.hardware.cpuModel
       summary.hardware.cpuMhz summary.hardware.numCpuPkgs
       summary.hardware.numCpuCores summary.hardware.numCpuThreads)
  end

  def ls_text r
    memorySize, cpuModel, cpuMhz, numCpuPkgs, numCpuCores =
      %w(memorySize cpuModel cpuMhz numCpuPkgs numCpuCores).map { |x| r["summary.hardware.#{x}"] }
    " (host): cpu #{numCpuPkgs}*#{numCpuCores/numCpuPkgs}*#{"%.2f" % (cpuMhz.to_f/1000)} GHz, memory #{"%.2f" % (memorySize/10**9)} GB"
  end

  field 'state.connection' do
    summary "State of connection to VC."
    property 'runtime.connectionState'
  end

  field 'state.power' do
    summary "Host power state."
    property 'runtime.powerState'
  end

  field 'state.maintenancemode' do
    summary "Host maintenance mode."
    property 'runtime.inMaintenanceMode'
  end

  field 'build' do
    summary "ESX build number."
    property 'summary.config.product.build'
  end

  field 'productname' do
    summary "ESX product name."
    property 'summary.config.product.fullName'
  end

  field 'uptime' do
    summary "Host's uptime in days"
    properties %w(runtime.bootTime)
    block { |t| t ? MetricNumber.new(((Time.now-t) / (24 * 60 * 60)), 'd') : nil }
  end

  field 'num.vms' do
    summary "Number of VMs on the host"
    properties %w(vm)
    block { |t| t ? t.length : nil }
  end

  field 'num.poweredonvms' do
    summary "Number of VMs on the host"
    properties %w(vm)
    block do |vms|
      if vms && vms.length > 0
        conn = vms.first._connection
        pc = conn.propertyCollector
        vmsProps = pc.collectMultiple(vms, 'runtime.powerState')
        vmsProps.select{|vm, p| p['runtime.powerState'] == 'poweredOn'}.length 
      end 
    end
  end

  field 'cpuusage' do
    summary "Realtime CPU usage in percent"
    properties %w(summary.hardware.numCpuCores summary.hardware.cpuMhz summary.quickStats)
    block do |cores, mhz, stats|
      if cores && mhz && stats
        value = stats.overallCpuUsage.to_f * 100 / (cores * mhz)
        MetricNumber.new(value, '%')
      end 
    end
  end

  field 'memusage' do
    summary "Realtime Mem usage in percent"
    properties %w(summary.hardware.memorySize summary.quickStats)
    block do |mem, stats|
      if mem && stats
        value = stats.overallMemoryUsage.to_f * 100 / (mem / 1024.0 / 1024.0)
        MetricNumber.new(value, '%')
      end 
    end
  end

  field 'vms' do
    summary "VirtualMachine status"
    properties %w(vm)
    block do |vms|
      if vms && vms.length > 0
        conn = vms.first._connection
        pc = conn.propertyCollector
        vmsProps = pc.collectMultiple(vms,
          'name',
          'runtime.connectionState',
          'runtime.powerState')
        vmsProps.values.map do |x|
          "#{x['name']}: #{x['runtime.powerState']}(#{x['runtime.connectionState']})"
        end.join("\n")
      end
    end
  end

  [['.realtime', 1], ['.5min', 5 * 3], ['.10min', 10 * 3]].each do |label, max_samples|
    field "cpuusage#{label}" do
      summary "CPU Usage in Percent"
      perfmetrics %w(cpu.usage)
      perfmetric_settings :max_samples => max_samples
      block do |value|
        if value
          value = value.sum.to_f / value.length / 100
          MetricNumber.new(value, '%')
        else
          nil
        end
      end
    end
  end
  
  [['.realtime', 1], ['.5min', 5 * 3], ['.10min', 10 * 3]].each do |label, max_samples|
    field "memusage#{label}" do
      summary "Mem Usage in Percent"
      perfmetrics %w(mem.usage)
      perfmetric_settings :max_samples => max_samples
      block do |value|
        if value
          value = value.sum.to_f / value.length / 100
          MetricNumber.new(value, '%')
        else
          nil
        end
      end
    end
  end

  def display_info
    super
    summary = self.summary
    runtime = summary.runtime
    stats = summary.quickStats
    hw = summary.hardware
    puts "connection state: #{runtime.connectionState}"
    puts "power state: #{runtime.powerState}"
    puts "uptime: #{"%0.2f" % ((Time.now - runtime.bootTime)/(24*3600))} days" if runtime.bootTime
    puts "in maintenance mode: #{runtime.inMaintenanceMode}"
    puts "standby mode: #{runtime.standbyMode}" if runtime.standbyMode
    if about = summary.config.product
      puts "product: #{about.fullName}"
      puts "license: #{about.licenseProductName} #{about.licenseProductVersion}" if about.licenseProductName
    end
    if runtime.connectionState == 'connected' and runtime.powerState == 'poweredOn'
      overallCpu = hw.numCpuCores * hw.cpuMhz
      puts "cpu: %d*%d*%.2f GHz = %.2f GHz" % [hw.numCpuPkgs, (hw.numCpuCores / hw.numCpuPkgs), hw.cpuMhz/1e3, overallCpu/1e3]
      puts "cpu usage: %.2f GHz (%.1f%%)" % [stats.overallCpuUsage/1e3, 100*stats.overallCpuUsage/overallCpu]
      puts "memory: %.2f GB" % [hw.memorySize/1e9]
      puts "memory usage: %.2f GB (%.1f%%)" % [stats.overallMemoryUsage/1e3, 100*1e6*stats.overallMemoryUsage/hw.memorySize]
    end
  end

  def children
    {
      'vms' => RVC::FakeFolder.new(self, :ls_vms),
      'datastores' => RVC::FakeFolder.new(self, :ls_datastores),
      'networks' => RVC::FakeFolder.new(self, :ls_networks),
    }
  end

  def ls_vms
    RVC::Util.collect_children self, :vm
  end

  def ls_datastores
    RVC::Util.collect_children self, :datastore
  end

  def ls_networks
    RVC::Util.collect_children self, :network
  end
end

class VIM::EsxcliCommand
  def option_parser
    parser = Trollop::Parser.new
    parser.text cli_info.help
    cli_info.param.each do |cli_param|
      vmodl_param = type_info.paramTypeInfo.find { |x| x.name == cli_param.name }
      opts = trollop_type(vmodl_param.type)
      opts[:required] = vmodl_param.annotation.find { |a| a.name == "optional"} ? false : true
      opts[:long] = cli_param.displayName
      #pp opts.merge(:name => cli_param.name)
      # XXX correct short options
      parser.opt cli_param.name, cli_param.help, opts
    end
    parser
  end

  def trollop_type t
    if t[-2..-1] == '[]'
      multi = true
      t = t[0...-2]
    else
      multi = false
    end
    type = case t
    when 'string', 'boolean' then t.to_sym
    when 'long' then :int
    else fail "unexpected esxcli type #{t.inspect}"
    end
    { :type => type, :multi => multi }
  end
end
