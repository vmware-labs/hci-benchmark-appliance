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
VIM::Datastore

require 'terminal-table'

opts :download do
  summary "Download a file from a datastore"
  arg 'datastore-path', "Filename on the datastore", :lookup => VIM::Datastore::FakeDatastoreFile
  arg 'local-path', "Filename on the local machine"
end

def download file, local_path
  download_path = http_path file.datastore.send(:datacenter).name, file.datastore.name, file.path

  http_download file.datastore._connection, download_path, local_path
end


opts :upload do
  summary "Upload a file to a datastore"
  arg 'local-path', "Filename on the local machine"
  arg 'datastore-path', "Filename on the datastore", :lookup_parent => VIM::Datastore::FakeDatastoreFolder
end

def upload local_path, dest
  dir, datastore_filename = *dest
  err "local file does not exist" unless File.exists? local_path
  real_datastore_path = "#{dir.path}/#{datastore_filename}"

  upload_path = http_path dir.datastore.send(:datacenter).name, dir.datastore.name, real_datastore_path

  http_upload dir.datastore._connection, local_path, upload_path
end


opts :mkdir do
  summary "Create a directory on a datastore"
  arg 'path', "Directory to create on the datastore"
end

def mkdir datastore_path
  datastore_dir_path = File.dirname datastore_path
  dir = lookup_single(datastore_dir_path)
  err "datastore directory does not exist" unless dir.is_a? RbVmomi::VIM::Datastore::FakeDatastoreFolder
  ds = dir.datastore
  dc = ds.path.find { |o,x| o.is_a? RbVmomi::VIM::Datacenter }[0]
  name = "#{dir.datastore_path}/#{File.basename(datastore_path)}"
  dc._connection.serviceContent.fileManager.MakeDirectory :name => name,
                                                          :datacenter => dc,
                                                          :createParentDirectories => false
end


opts :edit do
  summary "Edit a file"
  arg "file", nil, :lookup => VIM::Datastore::FakeDatastoreFile
end

rvc_alias :edit, :vi

def edit file
  editor = ENV['VISUAL'] || ENV['EDITOR'] || 'vi'
  filename = File.join(Dir.tmpdir, "rvc.#{Time.now.to_i}.#{rand(65536)}")
  download file, filename
  begin
    pre_stat = File.stat filename
    system("#{editor} #{filename}")
    post_stat = File.stat filename
    if pre_stat != post_stat
      upload filename, [file.parent, File.basename(file.path)]
    end
  ensure
    File.unlink filename
  end
end


def http_path dc_name, ds_name, path
  "/folder/#{URI.escape path}?dcPath=#{URI.escape dc_name}&dsName=#{URI.escape ds_name}"
end


opts :find_orphans do
  summary "Finds directories on the datastore that don't belong to any registered VM"
  arg :datastore, nil, :lookup => VIM::Datastore
  opt :mark, "Name of the mark to save results in", :required => false, :type => :string
end

def find_orphans ds, opts
  pc = ds._connection.serviceContent.propertyCollector
  vms = ds.vm
  
  puts "Collecting file information about #{vms.length} VMs ... (this may take a while)"
  dsName = ds.name
  vmFiles = pc.collectMultiple vms, 'layoutEx.file'
  
  puts "Collecting file information on datastore '#{dsName}' ..."
  dsBrowser = ds.browser
  result = dsBrowser.SearchDatastore_Task(
    :datastorePath => "[#{dsName}] ",
    :searchSpec => {
      :details => {
        :fileType => true,
        :fileSize => false,
        :fileOwner => false,
        :modification => false
      }
    }
  ).wait_for_completion
  dsDirectories = result.file.grep(RbVmomi::VIM::FolderFileInfo).map(&:path)
  
  puts "Checking for any VMs that got added inbetween ..."
  addedVms = ds.vm - vms
  if addedVms.length > 0
    puts "Processing #{addedVms.length} new VMs ..."
    vmFiles.merge!(pc.collectMultiple addedVms, 'layoutEx.file')
  end
  
  begin 
    perDSUsage = pc.collectMultiple vms, 'storage.perDatastoreUsage'
  rescue RbVmomi::Fault => ex
    if ex.fault.is_a?(RbVmomi::VIM::ManagedObjectNotFound)
      vms = vms - [ex.fault.obj]
      retry
    end
    perDSUsage = []
    raise
  end

  puts "Cross-referencing VM files with files on datastore '#{dsName}' ..."
  vmFilenameHash = Hash[vmFiles.map do |vm, info| 
    [
      vm, 
      info["layoutEx.file"].map{|x| x.name}.select{|x| x =~ /^\[#{dsName}\] /}.map{|x| x.gsub(/^\[#{dsName}\] /, '')}
    ]
  end]
  filenames = vmFilenameHash.values.flatten(1)
  vmDirectories = filenames.map{ |x| x.split('/').first }.uniq
  orphanDirectories = (dsDirectories - vmDirectories).reject { |x| x =~ /^\./ }
  puts "Found #{orphanDirectories.length} potentially orphaned directories"
  
  puts "Composing list of potentially orphaned files ... (this may take a while)"
  data = orphanDirectories.map do |dir|
    begin 
      result = dsBrowser.SearchDatastoreSubFolders_Task(
        :datastorePath => "[#{dsName}] #{dir}/",
        :searchSpec => {
          :details => {
            :fileType => false,
            :fileSize => true,
            :fileOwner => false,
            :modification => false
          }
        }
      ).wait_for_completion
      files = result.map(&:file).flatten
      dirSize = files.map(&:fileSize).sum
      $stdout.write "."
      $stdout.flush
      [dir, dirSize, files.length]
    rescue 
      puts "failed to search #{dir.inspect}: #{$!.message}"
      nil
    end
  end.compact
  puts
  puts
  
  if data.empty?
    puts "No orphans found"
  else
    puts(Terminal::Table.new do
      data.sort_by { |a| a[1] }.each do |x|
        dir, dirSize, numFiles = x
        self.headings = 'Directory', 'Space Used', '# Files'
        add_row [dir, "#{dirSize.metric}B", numFiles]
      end
    end)
  end

  puts

  totalSize = data.map{|x| x[1]}.sum
  dsSummary = ds.summary
  vmDsUsage = perDSUsage.map{|vm, x| x['storage.perDatastoreUsage'].find{|y| y.datastore == ds}}.reject{|x| x == nil}
  committed = vmDsUsage.map{|x| x.committed}.sum
  unshared = vmDsUsage.map{|x| x.unshared}.sum
  otherSpace = (dsSummary.capacity - dsSummary.freeSpace) - unshared
  puts "Provisioned on Datastore:  #{dsSummary.uncommitted.metric}B"
  puts "Capacity of Datastore: #{dsSummary.capacity.metric}B"
  puts "Free Space on Datastore: #{dsSummary.freeSpace.metric}B"
  puts "VMs Provisioned on Datastore: #{vmDsUsage.map(&:uncommitted).sum.metric}B"
  puts "VMs Used on Datastore: #{committed.metric}B"
  puts "VMs Unshared on Datastore: #{vmDsUsage.map(&:unshared).sum.metric}B"
  puts "Unaccounted space: #{otherSpace.metric}B"
  puts "Total size of detected potential orphans: #{totalSize.metric}B"
  puts

  results = data.map do |dirInfo|
    RbVmomi::VIM::Datastore::FakeDatastoreFolder.new(ds, "#{dirInfo[0]}")
  end
  opts[:mark] ||= "#{dsName}_orphans"
  shell.cmds.mark.mark opts[:mark], results
  puts "Saved results to mark '#{opts[:mark]}'"

  i = 0
  results.each do |r|
    display_path = r.path
    puts "#{i} #{display_path}"
    shell.cmds.mark.mark i.to_s, [r]
    i += 1
  end
end


opts :delete do
  summary "Deletes the specified files or folders from the datastore"
  arg :objs, nil, :multi => true, :lookup => RVC::InventoryObject
end

def delete objs
  fm = nil
  tasks = objs.map do |obj|
    isFolder = obj.is_a?(RbVmomi::VIM::Datastore::FakeDatastoreFolder) 
    isFile = obj.is_a?(RbVmomi::VIM::Datastore::FakeDatastoreFile)
    err "Parameter is neither file nor folder" if !isFolder && !isFile
     
    ds = obj.datastore
    dc = ds.path.find{|x| x[0].is_a? RbVmomi::VIM::Datacenter}[0]
    fm ||= ds._connection.serviceContent.fileManager
    dsPath = "[#{ds.name}] #{obj.path}"
    puts "Deleting #{dsPath}"
    fm.DeleteDatastoreFile_Task(:name => dsPath, :datacenter => dc)
  end
  progress(tasks)
end


opts :du do
  summary "Estimate disk space consumption"
  arg :objs, nil, :multi => true, :lookup => RVC::InventoryObject
end

def du objs
  fm = nil
  tasks = Hash[objs.map do |obj|
    isFolder = obj.is_a?(RbVmomi::VIM::Datastore::FakeDatastoreFolder) 
    isFile = obj.is_a?(RbVmomi::VIM::Datastore::FakeDatastoreFile)
    err "Parameter is neither file nor folder" if !isFolder && !isFile
     
    ds = obj.datastore

    task = ds.browser.SearchDatastore_Task(
      :datastorePath => obj.datastore_path,
      :searchSpec => {
        :details => {
          :fileType => true,
          :fileSize => true,
          :fileOwner => false,
          :modification => false
        }
      }
    )
    [obj, task]
  end]
  results = progress(tasks.values)
  t = Terminal::Table.new()
  t << [
    'Path', 
    'Space consumption', 
  ]
  t.add_separator
  objs.each do |obj|
    task = tasks[obj]
    result = results[task]
    sum = result.file.map{|x| x.fileSize}.sum
    t << [obj.datastore_path, "%.2f GB" % [sum.to_f / 1024 ** 3]]
  end
  puts t
end
