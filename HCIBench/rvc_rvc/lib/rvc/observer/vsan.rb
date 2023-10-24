#
# VSAN-specific stuff.
#

require 'json'

def _components_in_dom_config dom_config
  out = []
  if ['Component', 'Witness'].member?(dom_config['type'])
    out << dom_config
  else
    dom_config.select{|k,v| k =~ /child-\d+/}.each do |k, v|
      out += _components_in_dom_config v
    end
  end
  out
end

def _print_dom_config_tree_int dom_config, dom_components_str, indent = 0
  out = ""

  pre = "  " * indent
  type = dom_config['type']
  children = dom_config.select{|k,v| k =~ /child-\d+/}.values
  if ['RAID_0', 'RAID_1', 'Concatenation'].member?(type)
    out += "#{pre}#{type}\n"
    children.each do |child|
      out += _print_dom_config_tree_int child, dom_components_str, indent + 1
    end
  elsif ['Configuration'].member?(type)
#    puts "#{pre}#{type}"
    children.each do |child|
      out += _print_dom_config_tree_int child, dom_components_str, indent + 1
    end
  elsif ['Witness', 'Component'].member?(type)
    comp_uuid = dom_config['componentUuid']
    info = dom_components_str[comp_uuid]
    line = "#{pre}#{type}: #{info[0]}"
    if info[2].length > 0
      out += "#{line} (#{info[1]}, #{info[2]})\n"
    else
      out += "#{line} (#{info[1]})\n"
    end
  end
  out
end

def _print_dom_config_tree dom_obj_uuid, obj_infos, indent = 0, opts = {}
  pre = "  " * indent
  dom_obj_infos = obj_infos['dom_objects'][dom_obj_uuid]
  if !dom_obj_infos
    raise "#{pre}Couldn't find info about DOM object '#{dom_obj_uuid}'"
  end
  dom_obj = dom_obj_infos['config']
  policy = dom_obj_infos['policy']

  dom_components = _components_in_dom_config(dom_obj['content'])

  dom_components_str = Hash[dom_components.map do |dom_comp|
    attr = dom_comp['attributes']
    state = attr['componentState']
    comp_uuid = dom_comp['componentUuid']
    state_names = {
      '0' => 'FIRST',
      '1' => 'NONE',
      '2' => 'NEED_CONFIG',
      '3' => 'INITIALIZE',
      '4' => 'INITIALIZED',
      '5' => 'ACTIVE',
      '6' => 'ABSENT',
      '7' => 'STALE',
      '8' => 'RESYNCHING',
      '9' => 'DEGRADED',
      '10' => 'RECONFIGURING',
      '11' => 'CLEANUP',
      '12' => 'TRANSIENT',
      '13' => 'LAST',
    }
    state_name = state.to_s
    if state_names[state.to_s]
      state_name = "#{state_names[state.to_s]} (#{state})"
    end
    props = {
      'state' => state_name,
    }

    comp_policy = {}
    ['readOPS', 'writeOPS'].select{|x| attr[x]}.each do |x|
      comp_policy[x] = attr[x]
    end
    if attr['readCacheReservation'] && attr['readCacheHitRate']
      comp_policy['rc size/hitrate'] = "%.2fGB/%d%%" % [
        attr['readCacheReservation'].to_f / 1024**3,
        attr['readCacheHitRate'],
      ]
    end
    if attr['bytesToSync']
      comp_policy['dataToSync'] = "%.2f GB" % [
        attr['bytesToSync'].to_f / 1024**3
      ]
    end

    lsom_object = obj_infos['lsom_objects'][comp_uuid]
    if lsom_object
      host_uuid = lsom_object['owner']
      host = obj_infos['host_vsan_uuids'][host_uuid]
      hostName = host ? obj_infos['host_props'][host]['name'] : nil
      md_uuid = dom_comp['diskUuid']
      md = obj_infos['vsan_disk_uuids'][md_uuid]
      if md_uuid
        ssd_uuid = (obj_infos['disk_objects'][md_uuid] || {})['ssdUuid']
        #pp ssd_uuid
        ssd = obj_infos['vsan_disk_uuids'][ssd_uuid]
      else
        ssd = nil
        ssd_uuid = nil
      end      
      #pp ssd
      props.merge!({
        'host' => hostName || host_uuid,
        'md' => md ? md.DisplayName : md_uuid,
        'ssd' => ssd ? ssd.DisplayName : ssd_uuid,
      })
      if opts[:highlight_disk] && md_uuid == opts[:highlight_disk]
        props['md'] = "**#{props['md']}**"
      end
    else
      props.merge!({
        'host' => "LSOM object not found"
      })
    end
    propsStr = props.map{|k,v| "#{k}: #{v}"}.join(", ")
    comp_policy_str = comp_policy.map{|k,v| "#{k}: #{v}"}.join(", ")
    [comp_uuid, [comp_uuid, propsStr, comp_policy_str]]
  end]

  if policy
    policy = policy.map{|k,v| "#{k} = #{v}"}.join(", ")
  else
    policy = "No POLICY entry found in CMMDS"
  end
  owner_uuid = dom_obj['owner']
  host = obj_infos['host_vsan_uuids'][owner_uuid]
  owner = host ? obj_infos['host_props'][host]['name'] : 'unknown'

  out = ""
  out += "#{pre}DOM Object: #{dom_obj['uuid']} (owner: #{owner}, policy: #{policy})\n"
  if opts[:context]
    out += "#{pre}  Context: #{opts[:context]}\n"
  end
  out += _print_dom_config_tree_int dom_obj['content'], dom_components_str, indent
end



class CmmdsDump

  def initialize(cmmds_dump_path)
    @dump = JSON.load(IO.read(cmmds_dump_path))
  end
  
end
