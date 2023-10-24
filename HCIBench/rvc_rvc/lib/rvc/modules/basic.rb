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

require 'terminal-table'
require 'time'

opts :type do
  summary "Display information about a VMODL type"
  arg :name, "VMODL type name"
end

rvc_alias :type

def type name
  klass = RbVmomi::VIM.type(name) rescue err("#{name.inspect} is not a VMODL type.")
  shell.introspect_class klass
  nil
end


opts :help do
  summary "Display this text"
  arg :cmd, "Command or namespace to display help for", :required => false
end

rvc_alias :help

def help input
  if input
    cmdpath, args = Shell.parse_input input
    o = shell.cmds.lookup(cmdpath, Namespace) || shell.cmds.lookup(cmdpath)
    RVC::Util.err "invalid command or namespace" unless o
  else
    o = shell.cmds
  end

  case o
  when Command
    o.parser.educate
  when Namespace
    help_namespace o
  end

  # TODO apropos
  puts (<<-EOS)

To see commands in a namespace: help namespace_name
To see detailed help for a command: help namespace_name.command_name
  EOS

  unless input
    puts (<<-EOS)
To drop to Ruby console use '//', in Ruby console you can use vSphere API against managed objects.
For executing Ruby without dropping to console, prefix command with '/'
    EOS
  end
end

# TODO namespace summaries
def help_namespace ns
  unless ns.namespaces.empty?
    puts "Namespaces:"
    ns.namespaces.sort.each do |child_name,child|
      puts child_name
    end
  end

  puts unless ns.namespaces.empty? or ns.commands.empty?

  unless ns.commands.empty?
    puts "Commands:"
    ns.commands.sort.each do |cmd_name,cmd|
      help_summary cmd
    end
  end
end

def help_summary cmd
  aliases = shell.cmds.aliases.select { |k,v| shell.cmds.lookup(v) == cmd }.map(&:first)
  aliases_text = aliases.empty? ? '' : " (#{aliases*', '})"
  puts "#{cmd.name}#{aliases_text}: #{cmd.summary}"
end


opts :debug do
  summary "Toggle VMOMI logging to stderr"
end

rvc_alias :debug

def debug
  debug = shell.debug = !shell.debug
  shell.connections.each do |name,conn|
    conn.debug = debug if conn.respond_to? :debug
  end
  puts "debug mode #{debug ? 'en' : 'dis'}abled"
end


opts :cd do
  summary "Change directory"
  arg :obj, "Directory to change to", :lookup => Object
end

rvc_alias :cd

def cd obj
  shell.fs.cd(obj)
  shell.fs.marks[''] = [find_ancestor(RbVmomi::VIM::Datacenter)].compact
  shell.fs.marks['@'] = [find_ancestor(RbVmomi::VIM)].compact
  shell.fs.delete_numeric_marks
end

def find_ancestor klass
  shell.fs.cur.rvc_path.map { |k,v| v }.reverse.find { |x| x.is_a? klass }
end


opts :ls do
  summary "List objects in a directory"
  arg :obj, "Directory to list", :required => false, :default => '.', :lookup => Object
end

rvc_alias :ls
rvc_alias :ls, :l

def ls obj
  if obj.respond_to?(:rvc_ls)
    return obj.rvc_ls
  end

  children = obj.rvc_children
  name_map = children.invert
  children, fake_children = children.partition { |k,v| v.is_a? VIM::ManagedEntity }
  i = 0

  fake_children.each do |name,child|
    puts "#{i} #{name}#{child.ls_text(nil)}"
    child.rvc_link obj, name
    shell.cmds.mark.mark i.to_s, [child]
    i += 1
  end

  return if children.empty?

  filterSpec = VIM.PropertyFilterSpec(:objectSet => [], :propSet => [])
  filteredTypes = Set.new

  children.each do |name,child|
    filterSpec.objectSet << { :obj => child }
    filteredTypes << child.class
  end

  filteredTypes.each do |x|
    filterSpec.propSet << {
      :type => x.wsdl_name,
      :pathSet => x.ls_properties+%w(name overallStatus),
    }
  end

  connection = single_connection(children.map { |k,v| v })
  pc = connection.propertyCollector
  rv = pc.RetrievePropertiesEx(:specSet => [filterSpec], :options => {})
  if !rv.nil?
    results = rv.objects
    token = rv.token
    while token
      continueProps = pc.ContinueRetrievePropertiesEx(:token => token)
      results += continueProps.objects
      token = continueProps.token
    end
  else
    results = []
  end

  results.each do |r|
    name = name_map[r.obj]
    text = r.obj.ls_text(r) rescue " (error)"
    realname = r['name'] if name != r['name']
    colored_name = status_color name, r['overallStatus']
    puts "#{i} #{colored_name}#{realname && " [#{realname}]"}#{text}"
    r.obj.rvc_link obj, name
    shell.cmds.mark.mark i.to_s, [r.obj]
    i += 1
  end
end

opts :info do
  summary "Display information about an object"
  arg :path, nil, :lookup => Object
end

rvc_alias :info
rvc_alias :info, :i

opts :show do
  summary "Display information about an object"
  arg :arg0, nil, :type => :string
  arg :arg1, nil, :type => :string, :required => false
end

rvc_alias :show

rvc_completor :show do |word, args|
  choices = shell.completion.fs_candidates word
  obj = lookup_single '.'
  if args.length == 1
    if obj.class == VIM::Datacenter || obj.class == VIM
      choices << ['portgroups', ' ']
      choices << ['vds', ' ']
    end
    if obj.class < VIM::DistributedVirtualSwitch
      choices << ['running-config', ' ']
      choices << ['interface', ' ']
      #choices << ['vlan', ' ']
      #choices << ['lldp', ' ']
      #choices << ['cdp', ' ']
    end
  #elsif index == 1
  #  if args[0] == 'vlan'
  #    choices << ['summary', ' ']
  #  end
  end
  choices
end

def show arg0, arg1
  arg1 ||= '.'
  begin
    obj = lookup_single arg1
  rescue
    obj = nil
  end

  case arg0
  when 'running-config'
    if obj.class < VIM::DistributedVirtualSwitch
      shell.cmds.vds.show_running_config obj
    else
      if arg1 != '.'
        err "'#{arg1}' is not a vDS!"
      else
        err "you need to be inside a vDS"
      end
    end
  when 'portgroups'
    shell.cmds.vds.show_all_portgroups [obj]
  when 'vds'
    shell.cmds.vds.show_all_vds [obj]
  when 'interface'
    shell.cmds.vds.show_all_ports [obj]
  #when 'vlan'
  else
    path = lookup_single arg0
    info path
  end
end

def info obj
  puts "path: #{obj.rvc_path_str}"
  if obj.respond_to? :display_info
    obj.display_info
    obj.methods.grep(/rvc_display_info_/).sort.each do |method|
      obj.send(method)
    end
  else
    puts "class: #{obj.class.name}"
  end
end


opts :destroy do
  summary "Destroy managed entities"
  arg :obj, nil, :lookup => VIM::ManagedEntity, :multi => true
end

rvc_alias :destroy

def destroy objs
  tasks objs, :Destroy
end


opts :reload_entity do
  summary "Synchronize management server state"
  arg :obj, nil, :lookup => VIM::ManagedEntity, :multi => true
end

rvc_alias :reload_entity

def reload_entity objs
  objs.each(&:Reload)
end


opts :what do
  summary "Basic information about the given objects"
  arg :obj, nil, :multi => true, :required => false, :lookup => Object
end

rvc_alias :what
rvc_alias :what, :w

def what objs
  objs.each do |obj|
    puts "#{obj.rvc_path_str}: #{obj.class}"
  end
end


opts :mv do
  summary "Move entities to another folder"
  text "The entities' names are unchanged."
  arg :objs, "Entities to move", :lookup => VIM::ManagedEntity, :multi => true
end

rvc_alias :mv

def mv objs
  err "Destination entity missing" unless objs.size > 1
  dst = objs.pop
  progress [dst.MoveIntoFolder_Task(:list => objs)]
end


opts :rename do
  summary "Rename an entity"
  arg :objs, "Entity to rename", :lookup => VIM::ManagedEntity
  arg :name, "New name"
end

rvc_alias :rename

def rename obj, name
  progress [obj.Rename_Task(:newName => name)]
end


opts :disconnect do
  summary "Disconnect from a server"
  arg :connection, nil, :type => :string, :lookup => RbVmomi::VIM
end

rvc_alias :disconnect

def disconnect connection
  k, = shell.connections.find { |k,v| v == connection }
  shell.connections.delete k
end


opts :mkdir do
  summary "Create a folder"
  arg :path, "Folder to create", :type => :string
end

rvc_alias :mkdir

# TODO dispatch to datastore.mkdir if path is in a datastore
def mkdir path
  parent = lookup_single! File.dirname(path), RbVmomi::VIM::Folder
  parent.CreateFolder(:name => File.basename(path))
end


opts :events do
  summary "Show recent events"
  arg :obj, nil, :required => false, :default => '.', :lookup => Object
  opt :lines, "Output the last N events", :short => 'n', :type => :int, :default => 10
  opt :show_id, "Show event ID", :type => :boolean
end

rvc_alias :events

def events obj, opts
  err "'events' not supported at this level" unless obj.respond_to?(:_connection)
  manager = obj._connection.serviceContent.eventManager
  @event_details ||= Hash[manager.collect("description.eventInfo").first.collect { |d| [d.key, d] }]

  spec = VIM::EventFilterSpec(:entity => VIM::EventFilterSpecByEntity(:entity => obj, :recursion => "all"))

  collector = manager.CreateCollectorForEvents(:filter => spec)
  collector.SetCollectorPageSize(:maxCount => opts[:lines])
  collector.latestPage.reverse.each do |event|
    time = event.createdTime.localtime.strftime("%m/%d/%Y %I:%M %p")
    category = @event_details[event.class.to_s].category
    prefix = "[#{time}] [#{category}]"
    if opts[:show_id] && event.is_a?(VIM::EventEx)
      prefix = "#{prefix} [#{event.eventTypeId}]"
    end
    puts "#{prefix} #{event.fullFormattedMessage.strip}"
  end
ensure
  collector.DestroyCollector if collector
end


opts :fields do
  summary "Show available fields on an object"
  arg :obj, nil, :required => false, :default => '.', :lookup => RVC::InventoryObject
end

def fields obj
  obj.class.ancestors.select { |x| x.respond_to? :fields }.each do |klass|
    fields = klass.fields false
    next if fields.empty?
    puts "Fields on #{klass}:"
    fields.each do |name,field|
      puts " #{name}: #{field.summary}"
    end
  end
end

rvc_alias :fields


opts :table do
  summary "Display a table with the selected fields"

  text <<-EOS

You may specify the fields to display using multiple -f options, or
separate them with ':'. The available fields for an object are
shown by the "fields" command.
  EOS
  text ""

  arg :obj, nil, :multi => true, :lookup => RVC::InventoryObject
  opt :field, "Field to display", :multi => true, :type => :string
  opt :sort, "Field to sort by", :type => :string
  opt :reverse, "Reverse sort order"
end

rvc_completor :table do |word, args|
  if args[-2] == '-f'
    RVC::Field::ALL_FIELD_NAMES.map { |x| [x, ' '] }
  else
    shell.completion.fs_candidates word
  end
end

def table objs, opts
  if opts[:field_given]
    fields = opts[:field].map { |x| x.split ':' }.flatten(1)
  else
    fields = objs.map(&:class).uniq.
                  map { |x| x.fields.select { |k,v| v.default? } }.
                  map(&:keys).flatten(1).uniq
  end

  data = retrieve_fields(objs, fields).values

  if f = opts[:sort]
    data.sort! { |a,b| table_sort_compare a[f], b[f] }
    data.reverse! if opts[:reverse]
  end

  # Invert field components to get an array of header rows
  field_components = fields.map { |x| x.split '.' }
  header_rows = []
  field_components.each_with_index do |cs,i|
    cs.each_with_index do |c,j|
      header_rows[j] ||= [nil]*field_components.length
      header_rows[j][i] = c
    end
  end

  table = Terminal::Table.new
  header_rows.each { |row| table.add_row row }
  table.add_separator
  data.each do |h|
    table.add_row(fields.map { |f| h[f] == nil ? 'N/A' : h[f] })
  end
  puts table
end

def table_sort_compare a, b
  return a <=> b if a != nil and b != nil
  return 0 if a == nil and b == nil
  return -1 if a == nil
  return 1 if b == nil
  fail
end

opts :screenlog do
  summary "Configure screen logging"
  opt :enable, "Enable screen logging", :type => :boolean
  opt :file_path, "Customized log file path, only be valid during enable screen logging", :type => :string
  opt :disable, "Disable screen logging", :type => :boolean
end

def screenlog opts = {}
  if opts[:enable]
    $screen_log.enable(opts[:file_path])
  elsif opts[:disable]
    $screen_log.disable
  else
    RVC::Util.err "Please make a choice to enable or disable screen logging"
  end
end

rvc_alias :table
