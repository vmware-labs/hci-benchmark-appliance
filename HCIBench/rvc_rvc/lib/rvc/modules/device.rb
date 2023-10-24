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

require 'rvc/vim'
require 'rbvmomi/pbm'
VIM::Datastore

opts :connect do
  summary "Connect a virtual device"
  arg :device, nil, :lookup => VIM::VirtualDevice, :multi => true
end

def connect devs
  change_devices_connectivity devs, true
end


opts :disconnect do
  summary "Disconnect a virtual device"
  arg :device, nil, :lookup => VIM::VirtualDevice, :multi => true
end

def disconnect devs
  change_devices_connectivity devs, false
end


opts :remove do
  summary "Remove a virtual device"
  arg :device, nil, :lookup => VIM::VirtualDevice, :multi => true
  opt :no_destroy, "Do not delete backing files"
end

def remove devs, opts
  vm_devs = devs.group_by(&:rvc_vm)
  tasks = vm_devs.map do |vm,my_devs|
    device_changes = my_devs.map do |dev|
      fileOp = (dev.backing.is_a?(VIM::VirtualDeviceFileBackingInfo) && !opts[:no_destroy]) ? 'destroy' : nil
      { :operation => :remove, :fileOperation => fileOp, :device => dev }
    end
    spec = { :deviceChange => device_changes }
    vm.ReconfigVM_Task(:spec => spec)
  end

  progress tasks
end


opts :add_net do
  summary "Add a network adapter to a virtual machine"
  arg :vm, nil, :lookup => VIM::VirtualMachine
  arg :network, nil, :lookup => VIM::Network
  opt :type, "Adapter type", :default => 'e1000'
end

NET_DEVICE_CLASSES = {
  'e1000e' => VIM::VirtualE1000e,
  'e1000' => VIM::VirtualE1000,
  'vmxnet3' => VIM::VirtualVmxnet3,
}

def add_net vm, network, opts
  klass = NET_DEVICE_CLASSES[opts[:type]] or err "unknown network adapter type #{opts[:type].inspect}"

  case network
  when VIM::DistributedVirtualPortgroup
    switch, pg_key = network.collect 'config.distributedVirtualSwitch', 'key'
    port = VIM.DistributedVirtualSwitchPortConnection(
      :switchUuid => switch.uuid,
      :portgroupKey => pg_key)
    summary = network.name
    backing = VIM.VirtualEthernetCardDistributedVirtualPortBackingInfo(:port => port)
  when VIM::Network
    summary = network.name
    backing = VIM.VirtualEthernetCardNetworkBackingInfo(:deviceName => network.name)
  else fail
  end

  _add_device vm, nil, klass.new(
    :key => -1,
    :deviceInfo => {
      :summary => summary,
      :label => "",
    },
    :backing => backing,
    :addressType => 'generated'
  )
end


opts :reconfig_net do
  summary "Attach a network adapter to a different network"
  arg :device, nil, :lookup => VIM::VirtualDevice, :multi => true
  opt :network, "Network to attach to", :lookup => VIM::Network, :required => true
end

def reconfig_net devs, opts
  network = opts[:network]
  case network
  when VIM::DistributedVirtualPortgroup
    switch, pg_key = network.collect 'config.distributedVirtualSwitch', 'key'
    port = VIM.DistributedVirtualSwitchPortConnection(
      :switchUuid => switch.uuid,
      :portgroupKey => pg_key)
    summary = network.name
    backing = VIM.VirtualEthernetCardDistributedVirtualPortBackingInfo(:port => port)
  when VIM::Network
    summary = network.name
    backing = VIM.VirtualEthernetCardNetworkBackingInfo(:deviceName => network.name)
  else fail
  end

  vm_devs = devs.group_by(&:rvc_vm)
  tasks = vm_devs.map do |vm,my_devs|
    device_changes = my_devs.map do |dev|
      dev = dev.dup
      dev.backing = backing
      { :operation => :edit, :device => dev }
    end
    spec = { :deviceChange => device_changes }
    vm.ReconfigVM_Task(:spec => spec)
  end
  progress(tasks)
end

opts :add_disk do
  summary "Add a hard drive to a virtual machine"
  arg :vm, nil, :lookup => VIM::VirtualMachine
  arg :path, "Filename on the datastore", :lookup_parent => VIM::Datastore::FakeDatastoreFolder, :required => false
  opt :size, 'Size', :default => '10G'
  opt :controller, 'Virtual controller', :type => :string, :lookup => VIM::VirtualController
  opt :file_op, 'File operation (create|reuse|replace)', :default => 'create'
  opt :thick, "Use thick provisioning", :type => :boolean
  opt :profile, "Storage Profile", :lookup => RbVmomi::PBM::PbmCapabilityProfile
end

def add_disk vm, path, opts
  controller, unit_number = pick_controller vm, opts[:controller], [VIM::VirtualSCSIController, VIM::VirtualIDEController]
  id = "disk-#{controller.key}-#{unit_number}"

  if path
    dir, file = *path
    filename = "#{dir.datastore_path}/#{file}"
  else
    filename = "#{File.dirname(vm.summary.config.vmPathName)}/#{id}.vmdk"
  end

  opts[:file_op] = nil if opts[:file_op] == 'reuse'

  _add_device(
    vm, opts[:file_op],
    VIM::VirtualDisk(
      :key => -1,
      :backing => VIM.VirtualDiskFlatVer2BackingInfo(
        :fileName => filename,
        :diskMode => :persistent,
        :thinProvisioned => !(opts[:thick] == true),
      ),
      :capacityInKB => MetricNumber.parse(opts[:size]).to_i/1000,
      :controllerKey => controller.key,
      :unitNumber => unit_number
    ),
    :profile => opts[:profile],
  )
end


opts :add_cdrom do
  summary "Add a cdrom drive"
  arg :vm, nil, :lookup => VIM::VirtualMachine
  opt :controller, 'Virtual controller', :type => :string, :lookup => VIM::VirtualIDEController
end

def add_cdrom vm, opts
  controller, unit_number = pick_controller vm, opts[:controller], [VIM::VirtualIDEController]
  id = "cdrom-#{controller.key}-#{unit_number}"
  _add_device vm, nil, VIM.VirtualCdrom(
    :controllerKey => controller.key,
    :key => -1,
    :unitNumber => unit_number,
    :backing => VIM.VirtualCdromAtapiBackingInfo(
      :deviceName => id,
      :useAutoDetect => false
    ),
    :connectable => VIM.VirtualDeviceConnectInfo(
      :allowGuestControl => true,
      :connected => true,
      :startConnected => true
    )
  )
end


opts :insert_cdrom do
  summary "Put a disc in a virtual CDROM drive"
  arg :dev, nil, :lookup => VIM::VirtualDevice
  arg :iso, "Path to the ISO image on a datastore", :lookup => VIM::Datastore::FakeDatastoreFile
end

def insert_cdrom dev, iso
  vm = dev.rvc_vm
  backing = VIM.VirtualCdromIsoBackingInfo(:fileName => iso.datastore_path)

  spec = {
    :deviceChange => [
      {
        :operation => :edit,
        :device => dev.class.new(
          :key => dev.key,
          :controllerKey => dev.controllerKey,
          :backing => backing)
      }
    ]
  }

  progress [vm.ReconfigVM_Task(:spec => spec)]
end


SCSI_CONTROLLER_TYPES = {
  'pvscsi' => VIM::ParaVirtualSCSIController,
  'buslogic' => VIM::VirtualBusLogicController,
  'lsilogic' => VIM::VirtualLsiLogicController,
  'lsilogic-sas' => VIM::VirtualLsiLogicSASController,
}

SCSI_BUS_NUMBERS = [0, 1, 2, 3]

opts :add_scsi_controller do
  summary "Add a virtual SCSI controller to a VM"
  arg :vm, nil, :lookup => VIM::VirtualMachine
  opt :type, SCSI_CONTROLLER_TYPES.keys*'/', :default => 'lsilogic' # TODO tab complete
  opt :sharing, VIM::VirtualSCSISharing.values*'/', :default => 'noSharing' # TODO tab complete
  opt :hot_add, "Enable hot-add/remove", :default => nil
end

def add_scsi_controller vm, opts
  klass = SCSI_CONTROLLER_TYPES[opts[:type]] or err "invalid SCSI controller type #{opts[:type].inspect}"
  err "invalid value for --sharing" unless VIM::VirtualSCSISharing.values.member? opts[:sharing]

  existing_devices, = vm.collect 'config.hardware.device'
  used_bus_numbers = existing_devices.grep(VIM::VirtualSCSIController).map(&:busNumber)
  bus_number = (SCSI_BUS_NUMBERS - used_bus_numbers).min
  err "unable to allocate a bus number, too many SCSI controllers" unless bus_number

  controller = klass.new(
    :key => -1,
    :busNumber => bus_number,
    :sharedBus => opts[:sharing],
    :hotAddRemove => opts[:hot_add]
  )

  _add_device vm, nil, controller
end


opts :add_serial do
  summary "Add a virtual serial port to a VM"
  arg :vm, nil, :lookup => VIM::VirtualMachine
end

def add_serial vm
  # create an initial no-op backing
  backing = VIM::VirtualSerialPortURIBackingInfo(:direction => :client, :serviceURI => 'localhost:0')
  _add_device vm, nil, VIM::VirtualSerialPort(:yieldOnPoll => true, :key => -1, :backing => backing)
end


opts :connect_serial_uri do
  summary "Connect a virtual serial port to the given network URI"
  arg :dev, nil, :lookup => VIM::VirtualSerialPort
  arg :uri, "URI", :type => :string
  opt :client, "Connect to another machine", :short => 'c'
  opt :server, "Listen for incoming connections", :short => 's'
  conflicts :client, :server
end

def connect_serial_uri dev, uri, opts
  err "must specify --client or --server" unless opts[:client] || opts[:server]
  direction = opts[:client] ? 'client' : 'server'
  dev = dev.dup
  dev.backing = VIM::VirtualSerialPortURIBackingInfo(:direction => direction, :serviceURI => uri)
  spec = { :deviceChange => [ { :operation => :edit, :device => dev } ] }
  progress [dev.rvc_vm.ReconfigVM_Task(:spec => spec)]
end


def _add_device vm, fileOp, dev, opts = {}
  spec = {
    :deviceChange => [
      { :operation => :add, :fileOperation => fileOp, :device => dev },
    ]
  }
  if opts[:profile]
    profile = [VIM::VirtualMachineDefinedProfileSpec(
      :profileId => opts[:profile].profileId.uniqueId
    )]
    spec[:deviceChange][0][:profile] = profile
  end
  task = vm.ReconfigVM_Task(:spec => spec)
  result = progress([task])[task]
  if result == nil
    new_device = vm.collect('config.hardware.device')[0].grep(dev.class).last
    puts "Added device #{new_device.name}"
  else
    taskInfo = task.info
    if taskInfo.state == "error"
      err "Task failed"
    end
  end
  task
end

def change_devices_connectivity devs, connected
  if dev = devs.find { |dev| dev.connectable.nil? }
    err "#{dev.name} is not connectable."
  end

  vm_devs = devs.group_by(&:rvc_vm)
  tasks = vm_devs.map do |vm,my_devs|
    device_changes = my_devs.map do |dev|
      dev = dev.dup
      dev.connectable = dev.connectable.dup
      dev.connectable.connected = connected
      dev.connectable.startConnected = connected
      { :operation => :edit, :device => dev }
    end
    spec = { :deviceChange => device_changes }
    vm.ReconfigVM_Task(:spec => spec)
  end

  progress tasks
end

def pick_controller vm, controller, controller_classes
  existing_devices, = vm.collect 'config.hardware.device'

  controller ||= existing_devices.find do |dev|
    controller_classes.any? { |klass| dev.is_a? klass } &&
      dev.device.length < 2
  end
  err "no suitable controller found" unless controller

  used_unit_numbers = existing_devices.select { |dev| dev.controllerKey == controller.key }.map(&:unitNumber)
  unit_number = (used_unit_numbers.max||-1) + 1

  [controller, unit_number]
end
