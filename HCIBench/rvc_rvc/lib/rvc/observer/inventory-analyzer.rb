require_relative 'vsan.rb'

require 'digest/md5'
require 'pathname'
include ERB::Util

def _normalize_uuid uuid
  uuid = uuid.gsub("-", "")
  uuid = "%s-%s-%s-%s-%s" % [
    uuid[0..7], uuid[8..11], uuid[12..15],
    uuid[16..19], uuid[20..31]
  ]
  uuid
end

def _normalize_ts ts
  t = Time.at(ts)
  t -= t.sec
  t.to_i.to_f
end

def _compressAvg data, points
  if data.length <= points
    return data
  end
  batchSize = (data.length / points).to_i
  i = 0
  out = []
  while i < data.length
    val = 0
    count = 0
    while (count < batchSize && i < data.length)
      val += (data[i] || 0)
      count += 1
      i += 1
    end
    val = val / count.to_f
    out << val
    i += 1
  end
  out
end

def _compressFirst data, points
  if data.length <= points
    return data
  end
  batchSize = (data.length / points).to_i
  i = 0
  out = []
  while i < data.length
    count = 0
    val = data[i]
    while (count < batchSize && i < data.length)
      count += 1
      i += 1
    end
    out << val
    i += 1
  end
  out
end

def _sumInventoryStats stats
  timesList = stats.map{|x| x.times}
  times = timesList.uniq.flatten.uniq.sort

  out = InventoryStat.new
  times.each do |ts|
    value = 0
    avg = 0
    stats.each do |s|
      value += s.values[ts] || 0
      avg += s.avgs[ts] || 0
    end
    out.addCustom(ts, value, avg)
  end
  out
end

def _vsanSparseUuid uuid
  uuid.gsub /^[0-9a-fA-F]{1,8}-/, ''
end

class InventoryStat
  attr_reader :times
  attr_reader :values, :avgs, :total, :divs

  def initialize requiredFields = nil
    @total = []
    @values = {}
    @avgs = {}
    @prev = nil
    @prevTs = 0
    @times = []
    @divs = []

    @requiredFields = requiredFields
  end

  def addCustom ts, value, avg
    @total << value
    @divs << nil
    @values[ts] = value
    @avgs[ts] = avg
    @prev = value
    @prevTs = ts
    @times << ts
  end

  def addStatic ts, value
    @total << value
    @divs << nil
    @values[ts] = value
    @avgs[ts] = value
    @prev = value
    @prevTs = ts
    @times << ts
  end

  def add ts, value, div = nil
    @total << value
    @divs << div

    prev = @prev
    if !prev || !value || prev > value
      val = 0
    else
      val = value - prev
    end
    @values[ts] = val
    avg = 0
    if !div
      deltaT = ts - @prevTs
      if deltaT != 0
        avg = val / deltaT
      end
    else
      if div != 0
        avg = val / div
      end
    end
    @avgs[ts] = avg

    @prev = value
    @prevTs = ts
    @times << ts
  end

  def lastvalue
    @values[@prevTs]
  end


  def to_json opts = {}
    out = {
      'avgs' => @avgs.values,
      'times' => @times,
      'prev' => @prev,
      'prevTs' => @prevTs,
      'values' => @values.values,
      'total' => @total,
    }

    if opts[:points]
      points = opts[:points]
      out['avgs'] = _compressAvg(out['avgs'], points)
      out['values'] = _compressAvg(out['values'], points)
      out.delete('prev')
      out.delete('prevTs')
      out['times'] = _compressFirst(out['times'], points)
      out['total'] = _compressFirst(out['total'], points)
    end

    if @requiredFields &&
      out = out.select{|k,v| @requiredFields.member?(k)}
    end

    out
  end

  def normalized_totals
    _normalized(self.total)
  end

  def normalized_divs
    if divs.uniq == [nil]
      return nil
    else
      _normalized(self.total)
    end
  end

  def _normalized vals
    out = {}
    if self.times.length < 2
      return out
    end
    prevTs = self.times[0]
    i = 1
    nextTs = self.times[i]
    ts = _normalize_ts(nextTs)
    while ts < self.times.last
      a = vals[i - 1]
      b = vals[i]
      factor = (ts - prevTs) / (nextTs - prevTs)
      out[ts] = a + factor * (b - a)

      # Move ahead
      ts += 60
      if ts > nextTs && ts < self.times.last
        i += 1
        prevTs = nextTs
        nextTs = self.times[i]
      end
    end
    out
  end

  #
  # Staticly merge 2 or more InventoryStats together
  # Totals in the return value are not adjusted
  #
  def self.mergeStatic list
    out = InventoryStat.new

    all_values = {}

    list.each do |x|
      all_values.merge! x.values
    end

    all_values.keys.sort.each do |ts|
      out.addStatic(ts, all_values[ts])
    end

    out
  end

  def self.merge list
    out = InventoryStat.new

    all_totals = {}
    all_divs = {}

    list.each do |x|
      totals = x.normalized_totals
      totals.each do |ts, total|
        all_totals[ts] ||= 0
        all_totals[ts] += total
      end
      divs = x.normalized_divs
      if divs
        divs.each do |ts, div|
          all_divs[ts] ||= 0
          all_divs[ts] += div
        end
      end
    end

    all_totals.keys.sort.each do |ts|
      out.add(ts, all_totals[ts], all_divs[ts])
    end

    out
  end

  def findCloseTime time
    margin = 10
    times = @times.select{|x| (time - x).abs <= margin}
    times = times.sort_by{|x| (time - x).abs}
    hit = times.first
    if !hit
      return {
        'avg' => 0.0,
        'value' => 0.0,
        'total' => 0.0,
      }
    end
    idx = @times.index(hit)
    {
      'avg' => @avgs[hit],
      'value' => @values[hit],
      'total' => @total[idx],
    }
  end

  def rebaseTime times
    out = InventoryStat.new
    times.each do |time|
      hit = findCloseTime(time)
      out.addCustom(time, hit['value'], hit['avg'])
    end
    out
  end
end

class StatsMerger
  def dom
    keys = {}
    [
      'readCount', 'writeCount', 'recoveryWriteCount',
      'readBytes', 'writeBytes', 'receiveryWriteBytes',
      'numOIO', 'totalCount', 'domClientCacheHitRate'
    ].each do |key|
      keys[key] = nil
    end
    ['read', 'write'].each do |type|
      ['Latency', 'LatencySq', 'Congestion'].each do |suffix|
        key = "#{type}#{suffix}"
        countKey = "#{type}Count"
        keys[key] = countKey
      end
    end

    keys
  end

  def mergeStats out, statsDBs, keys
    statsObjects = []
    statsDBs.each do |statsDB|
      statsObjects += statsDB.stats.values
    end
    statsList = statsObjects.map{|x| x[keys.keys.first]}.compact
    times = statsList.map{|x| x.times}.sort_by{|x| x.length}.last

    statsListDict = {}
    keys.each do |key, divKey|
      statsList = statsObjects.map{|x| x[key]}.compact
      statsListDict[key] = statsList.map{|x| x.rebaseTime(times).to_json}
    end

    keys.select{|k,d| d == nil}.each do |key, divKey|
      mergedStats = InventoryStat.new
      (times || []).each_with_index do |time, i|
        avg = statsListDict[key].map{|stats| stats['avgs'][i]}.sum
        value = statsListDict[key].map{|stats| stats['values'][i]}.sum
        mergedStats.addCustom(time, value, avg)
      end
      out[key] = mergedStats
    end

    keys.select{|k,d| d != nil}.each do |key, divKey|
      mergedStats = InventoryStat.new
      (times || []).each_with_index do |time, i|
        primarySum = 0
        divSum = 0
        statsListDict[key].each_with_index do |stats, j|
          if divKey.is_a?(Integer)
            divVal = divKey
          else
            divVal = statsListDict[divKey][j]['avgs'][i]
          end
          primarySum += stats['avgs'][i] * divVal
          divSum += divVal
        end
        avg = 0
        if divSum > 0
          avg = primarySum / divSum
        end

        primarySum = 0
        divSum = 0
        statsListDict[key].each_with_index do |stats, j|
          if divKey.is_a?(Integer)
            divVal = divKey
          else
            divVal = statsListDict[divKey][j]['values'][i]
          end
          primarySum += stats['values'][i] * divVal
          divSum += divVal
        end
        value = 0
        if divSum > 0
          value = primarySum / divSum
        end

        mergedStats.addCustom(time, value, avg)
      end
      out[key] = mergedStats
    end

    out
  end

end

class StatsDB
  attr_reader :stats, :files, :keyInfos, :extraInfos

  def invFiles
    files.invert
  end

  def initialize
    @stats = {}
    @keyInfos = {}
    @files = {}
    @extraInfos = {}
  end

  def registerKey keyInfo
    key = keyInfo.values
    if !@keyInfos[key]
      extraInfo = yield
      @extraInfos[key] = extraInfo
      @files[[extraInfo['group'], extraInfo['file']]] = key
      @keyInfos[key] = keyInfo
      @stats[key] ||= {}
    end
    key
  end

  def get key
    @stats[key]
  end

  def package key, opts = {}
    out = Hash[@keyInfos[key].map{|k,v| [k.to_s, v]}]
    stats = @stats[key]
    out = out.merge(@extraInfos[key]).merge(
      'stats' => Hash[stats.map do |key, value|
        [key.to_s, value.to_json(opts)]
      end])
    out
  end

  def merge! other, filterKeys = nil
    other.keyInfos.each do |key, keyInfo|
      if filterKeys != nil && !filterKeys.member?(key)
        next
      end
      self.registerKey(keyInfo) do
        other.extraInfos[key]
      end
      self.get(key).merge!(other.get(key))
    end
  end

  def trim!
    @stats = Hash[@stats.map do |key, stats|
      stats = Hash[stats.keys.map{|x| [x, nil]}]
      [key, stats]
    end]
  end

end

class InventoryAnalyzer
  attr_reader :vmInfoHistory
  attr_reader :cmmdsHistory
  attr_reader :vcInfo
  attr_reader :hostsProps

  attr_reader :vms
  attr_reader :counts
  attr_reader :v3DomStats
  attr_reader :ssds
  attr_reader :diskStats
  attr_reader :virstoStats
  attr_reader :CFStats
  attr_reader :physDiskStats
  attr_reader :plogDeviceInfo
  attr_reader :plogStats
  attr_reader :physDisk2uuid
  attr_reader :physDisk2dg
  attr_reader :hostElevStats
  attr_reader :lsomHostStats
  attr_reader :lsomStats
  attr_reader :systemMem
  attr_reader :pnics
  attr_reader :vmknicStats
  attr_reader :worldletStats
  attr_reader :pcpuStats
  attr_reader :slabs
  attr_reader :heaps
  attr_reader :osfsMntLatestHisto
  attr_reader :cbrcStats
  attr_reader :vscsiStats
  attr_reader :rdtAssocsetHistos
  attr_reader :rdtAssocsetStats
  attr_reader :nfsStats
  attr_reader :lsomCongestion
  attr_reader :vscsiHostStats
  attr_reader :vsansparse
  attr_reader :vsansparseList
  attr_reader :vsansparseHosts
  attr_reader :vsansparseOpenChain
  attr_reader :vsansparsePathmap

  attr_reader :cmmdsClusterInfos
  attr_reader :cmmdsHistory
  attr_reader :hostnames
  attr_reader :cmmdsDisks
  attr_reader :cmmdsStats

  attr_reader :vsanIscsiTargetList
  attr_reader :vsanIscsiTargetHostStats
  attr_reader :vsanIscsiTargetTargetStats
  attr_reader :vsanIscsiTargetLunStats

  attr_reader :vms
  attr_reader :vmInfoHistory

  attr_reader :fitnessStats

  def hosts
    @counts.keys
  end

  def initialize
    # uuid -> timeStamp -> all Stats
    @v3DomStats = StatsDB.new

    @vsanObjUuids = {}
    @osfsMntLatestHisto = {}
    @ssds = StatsDB.new
    @slabs = {}
    @heaps = {}
    @gaps = []

    @systemMem = {}
    @pnics = {}
    @vmknicStats = {}
    @vmInfoHistory = {}

    @cmmdsHistory = {}
    @cmmdsClusterInfos = {}

    @lsomStats = {}

    @worldletStats = {}
    @helperWorldStats = {}
    @helperWorldNames = {}

    @pcpuStats = {}

    @plogDeviceInfo = {}
    @plogStats = {}
    @diskStats = {}
    @virstoStats = {}
    @CFStats = {}
    @physDiskStats = StatsDB.new
    @hostElevStats = {}

    @lsomHostStats = StatsDB.new

    @cbrcStats = {}
    @vscsiStats = {}
    @vscsiHostStats = StatsDB.new
    @ioAmplification = {}
    @nfsStats = StatsDB.new
    @lsomCongestion = StatsDB.new

    @counts = {}


    @rdtAssocsetHistos = {}
    @rdtAssocsetStats = {}

    @hostnames = {}
    @cmmdsDisks = {}
    @vcInfo = {}

    @hostsProps = {}
    @vms = {}

    @vsansparse = {}
    @vsansparseOpenChain = {}
    @vsansparseList = {}
    @vsansparseHosts = {}
    @vsansparsePathmap = {}
    @fitnessStats = {}
    @cmmdsStats = {}
    @vsanIscsiTargetList = {}
    @vsanIscsiTargetHostStats = {}
    @vsanIscsiTargetTargetStats = {}
    @vsanIscsiTargetLunStats = {}
  end

  def json_dump out
    if $useOj
      Oj.dump(out)
    else
      JSON.dump(out)
    end
  end

  def dumpByFilename group, file, opts = {}
    if group == "lsom"
      if file =~ /^cong-(.*)$/
        return dumpGenericStatsDB(@lsomCongestion, [group, file], nil, opts)
      end
      if file =~ /^ssd-(.*)$/
        return dumpGenericStatsDB(@ssds, [group, file], nil, opts)
      end
      if file =~ /^physdisk-(.*)$/
        return dumpGenericStatsDB(@physDiskStats, [group, file], nil, opts)
      end
      if file =~ /^lsomhost-(.*)$/
        return dumpGenericStatsDB(@lsomHostStats, [group, file], nil, opts)
      end
      if file =~ /^lsomsum$/
        statsDB = StatsDB.new
        key = statsDB.registerKey({:scope => "all"}) do
          {
            'group' => group,
            'file' => file,
            'statsInfo' => {
                "rcHitRate" => ['avgs', 1, 'round'],
                "warEvictions" => ['avgs', 1, 'round'],
                "quotaEvictions" => ['avgs', 1, 'round'],
              }.merge(
              ['read', 'payload', 'writeLe'].map do |ioType|
                {
                  "#{ioType}IOs" => ['avgs', 1, 'round'],
                  "#{ioType}Bytes" => ['avgs', 1 / 1024.0, 'round'],
                  "#{ioType}Latency" => ['avgs', 1 / 1000.0, 'round'],
                }
              end.inject({}, :merge)),
            'thumbSpecs' => [
              {
                'label' => 'IOPS',
                'key' => 'iops',
                'fields' => ['readIOs', 'payloadIOs'],
                'fieldLabels' => ['Read IOPS', 'Write IOPS'],
                'max' => nil,
                'threshold' => 'XXX'
              },
              {
                'label' => 'Tput KB/s',
                'key' => 'tput',
                'fields' => ['readBytes', 'payloadBytes'],
                'fieldLabels' => ['Read KB/s', 'Write KB/s'],
                'max' => nil,
                'threshold' => 'XXX'
              },
              {
                'label' => 'Latency ms',
                'key' => 'latency',
                'fields' => ['readLatency', 'payloadLatency', 'writeLeLatency'],
                'fieldLabels' => ['Read Latency', 'Payload Latency', 'WriteLe Latency'],
                'max' => nil,
                'threshold' => 'XXX'
              },
              {
                'label' => 'RC Hit Rate (pct)',
                'key' => 'rchitrate',
                'fields' => ['rcHitRate'],
                'fieldLabels' => ['RC Hit Rate'],
                'max' => 100,
                'threshold' => 'XXX'
              },
              {
                'label' => 'Evictions (count)',
                'key' => 'evictions',
                'fields' => ['warEvictions', 'quotaEvictions'],
                'fieldLabels' => ['Write-After-Read', 'Quota'],
                'max' => nil,
                'threshold' => 'XXX'
              },
            ]
          }
        end
        statsObj = statsDB.get(key)
        merger = StatsMerger.new
        merger.mergeStats(statsObj, [@lsomHostStats],
          'readIOs' => nil,
          'payloadIOs' => nil,
          'writeLeIOs' => nil,
          'readBytes' => nil,
          'payloadBytes' => nil,
          'writeLeBytes' => nil,
          'readLatency' => "readIOs",
          'payloadLatency' => "payloadIOs",
          'writeLeLatency' => "writeLeIOs",
          'rcHitRate' => "readIOs",
          'warEvictions' => nil,
          'quotaEvictions' => nil,
        )
        return dumpGenericStatsDB(statsDB, [group, file], nil, opts)
      end
      if file =~ /^ssdsum$/
        statsDB = StatsDB.new
        key = statsDB.registerKey({:scope => "all"}) do
          {
            'group' => "lsom",
            'file' => file,
            'statsInfo' => {
              "wbFillPct" => ['avgs', 1, 'round'],
              # "llogLogSpace" => ['avgs', 1, 'round'],
              # "llogDataSpace" => ['avgs', 1, 'round'],
              # "plogLogSpace" => ['avgs', 1, 'round'],
              # "plogDataSpace" => ['avgs', 1, 'round'],
            },
            'thumbSpecs' => [
              {
                'label' => 'WB Fill (pct)',
                'key' => 'wbfill',
                'fields' => ['wbFillPct'],
                'fieldLabels' => ['WriteBuffer Fill pct'],
                'max' => 100,
                'threshold' => 'XXX'
              },
            ]
          }
        end
        statsObj = statsDB.get(key)
        merger = StatsMerger.new
        merger.mergeStats(statsObj, [@ssds],
          'wbFillPct' => 1,
        )
        return dumpGenericStatsDB(statsDB, [group, file], nil, opts)
      end
      if file =~ /^(physdiskcachesum|physdiskcapacitysum)$/
        statsDB = StatsDB.new
        key = statsDB.registerKey({:scope => "all"}) do
          {
            'group' => "lsom",
            'file' => file,
            'statsInfo' =>
              {
                "readIOs" => ['avgs', 1, 'round'],
                "writeIOs" => ['avgs', 1, 'round'],
                "read" => ['avgs', 1 / 2.0, 'round'], # measured in blocks
                "write" => ['avgs', 1 / 2.0, 'round'],
                "readLatency" => ['avgs', 1 / 1000.0, 'round'],
                "writeLatency" => ['avgs', 1 / 1000.0, 'round'],
              },
            'thumbSpecs' => [
              {
                'label' => 'IOPS',
                'key' => 'iops',
                'fields' => ['readIOs', 'writeIOs'],
                'fieldLabels' => ['Read IOPS', 'Write IOPS'],
                'max' => nil,
                'threshold' => 'XXX'
              },
              {
                'label' => 'Tput KB/s',
                'key' => 'tput',
                'fields' => ['read', 'write'],
                'fieldLabels' => ['Read KB/s', 'Write KB/s'],
                'max' => nil,
                'threshold' => 'XXX'
              },
              {
                'label' => 'Latency ms',
                'key' => 'latency',
                'fields' => ['readLatency', 'writeLatency'],
                'fieldLabels' => ['Read Latency', 'Write Latency'],
                'max' => nil,
                'threshold' => 'XXX'
              }
            ]
          }
        end
        statsObj = statsDB.get(key)
        merger = StatsMerger.new
        filteredDB = StatsDB.new
        isSsd = (file == 'physdiskcachesum') ? 1 : 0
        filteredDB.merge!(@physDiskStats,
          @physDiskStats.keyInfos.values.select{|x| x[:isSsd] == isSsd}.map{|x| x.values}
        )
        merger.mergeStats(statsObj, [filteredDB],
          'readIOs' => nil,
          'payloadIOs' => nil,
          'writeIOs' => nil,
          'read' => nil,
          'write' => nil,
          'readLatency' => "readIOs",
          'writeLatency' => "writeIOs",
        )
        return dumpGenericStatsDB(statsDB, [group, file], nil, opts)
      end
    end
    if group == "dom"
      if file =~ /^(domclientsum|domownersum|domcompmgrsum|domvmhomesum|domvmdiskssum)$/
        statsDB = StatsDB.new
        key = statsDB.registerKey({:scope => "all"}) do
          {
            'group' => group,
            'file' => file,
            'statsInfo' => ['read', 'write', 'recoveryWrite'].map do |ioType|
              {
                "#{ioType}Count" => ['avgs', 1, 'round'],
                "#{ioType}Bytes" => ['avgs', 1 / 1024.0, 'round'],
                "#{ioType}Latency" => ['avgs', 1 / 1000.0, 'round'],
                "#{ioType}LatencySq" => ['avgs', 1 / 1000.0, 'round'],
                "#{ioType}Congestion" => ['avgs', 1, 'round'],
              }
            end.inject({}, :merge),
            'thumbSpecs' => [
              {
                'label' => 'IOPS',
                'key' => 'iops',
                'fields' => ['readCount', 'writeCount'],
                'fieldLabels' => ['Read IOPS', 'Write IOPS'],
                'max' => nil,
                'threshold' => 'XXX'
              },
              {
                'label' => 'Tput KB/s',
                'key' => 'tput',
                'fields' => ['readBytes', 'writeBytes'],
                'fieldLabels' => ['Read KB/s', 'Write KB/s'],
                'max' => nil,
                'threshold' => 'XXX'
              },
              {
                'label' => 'Latency ms',
                'key' => 'latency',
                'fields' => ['readLatency', 'writeLatency'],
                'fieldLabels' => ['Read Latency', 'Write Latency'],
                'max' => nil,
                'threshold' => 'XXX'
              }
            ]
          }
        end
        statsObj = statsDB.get(key)
        merger = StatsMerger.new
        filteredDB = StatsDB.new
        if file == "domvmhomesum"
          uuids = dumpVmList.values.map{|x| x['vsan_vm_home'].keys}.flatten

          filteredDB.merge!(@v3DomStats,
            @v3DomStats.stats.keys.select{|x| uuids.member?(x[0])}
          )
        elsif file == "domvmdiskssum"
          uuids = dumpVmList.values.map{|x| x['vsan_disks'].keys}.flatten

          filteredDB.merge!(@v3DomStats,
            @v3DomStats.stats.keys.select{|x| uuids.member?(x[0])}
          )
        else
          labelMap = {
            'domownersum' => 'total',
            'domclientsum' => 'client',
            'domcompmgrsum' => 'compmgr',
          }
          label = labelMap[file]
          filteredDB.merge!(@v3DomStats,
            @v3DomStats.stats.keys.select{|x| x[0] =~ /#{label}/}
          )
        end
        merger.mergeStats(statsObj, [filteredDB],
          'readCount' => nil,
          'writeCount' => nil,
          'recoveryWriteCount' => nil,
          'readBytes' => nil,
          'writeBytes' => nil,
          'recoveryWriteBytes' => nil,
          'readLatency' => "readCount",
          'writeLatency' => "writeCount",
          'recoveryWriteLatency' => "recoveryWriteCount",
          'readLatencySq' => "readCount",
          'writeLatencySq' => "writeCount",
          'recoveryWriteLatencySq' => "recoveryWriteCount",
          'readCongestion' => nil,
          'writeCongestion' => nil,
          'recoveryWriteCongestion' => nil,
        )
        return dumpGenericStatsDB(statsDB, [group, file], nil, opts)
      end
    end
    if group == "nfs"
      if file =~ /^nfsmnt-(.*)$/
        return dumpGenericStatsDB(@nfsStats, [group, file], nil, opts)
      end
      if file =~ /^nfssum$/
        statsDB = StatsDB.new
        key = statsDB.registerKey({:scope => "all"}) do
          {
            'group' => "nfs",
            'file' => "nfssum",
            'statsInfo' => {
              'reads' => ['avgs', 1, 'round'],
              'writes' => ['avgs', 1, 'round'],
              'readBytes' => ['avgs', 1 / 1024.0, 'round'],
              'writeBytes' => ['avgs', 1 / 1024.0, 'round'],
              'readTime' => ['avgs', 1 / 1000.0, 'round'], # us -> ms
              'writeTime' => ['avgs', 1 / 1000.0, 'round'], # us -> ms
            },
            'thumbSpecs' => [
              {
                'label' => 'IOPS',
                'key' => 'iops',
                'fields' => ['reads', 'writes'],
                'fieldLabels' => ['Read IOPS', 'Write IOPS'],
                'max' => nil,
                'threshold' => 'XXX'
              },
              {
                'label' => 'Tput KB/s',
                'key' => 'tput',
                'fields' => ['readBytes', 'writeBytes'],
                'fieldLabels' => ['Read KB/s', 'Write KB/s'],
                'max' => nil,
                'threshold' => 'XXX'
              },
              {
                'label' => 'Latency ms',
                'key' => 'latency',
                'fields' => ['readTime', 'writeTime'],
                'fieldLabels' => ['Read Latency', 'Write Latency'],
                'max' => nil,
                'threshold' => 'XXX'
              }
            ]
          }
        end
        statsObj = statsDB.get(key)
        merger = StatsMerger.new
        merger.mergeStats(statsObj, [@nfsStats],
          'reads' => nil,
          'writes' => nil,
          'readBytes' => nil,
          'writeBytes' => nil,
          'readTime' => "reads",
          'writeTime' => "writes",
        )
        return dumpGenericStatsDB(statsDB, [group, file], nil, opts)
      end
    end
    if group == "misc"
      if file =~ /^vscsihost-(.*)$/
        return dumpGenericStatsDB(@vscsiHostStats, [group, file], nil, opts)
      end
      if file =~ /^vscsisum$/
        statsDB = StatsDB.new
        key = statsDB.registerKey({:scope => "all"}) do
          {
            'group' => "misc",
            'file' => "vscsisum",
            'statsInfo' => {
              'numReads' => ['avgs', 1, 'round'],
              'numWrites' => ['avgs', 1, 'round'],
              'bytesRead' => ['avgs', 1 / 1024.0, 'round'],
              'bytesWrite' => ['avgs', 1 / 1024.0, 'round'],
              'latencyReads' => ['avgs', 1 / 1000.0, 'round'], # us -> ms
              'latencyWrites' => ['avgs', 1 / 1000.0, 'round'], # us -> ms
            },
            'thumbSpecs' => [
              {
                'label' => 'IOPS',
                'key' => 'iops',
                'fields' => ['numReads', 'numWrites'],
                'fieldLabels' => ['Read IOPS', 'Write IOPS'],
                'max' => nil,
                'threshold' => 'XXX'
              },
              {
                'label' => 'Tput KB/s',
                'key' => 'tput',
                'fields' => ['bytesRead', 'bytesWrite'],
                'fieldLabels' => ['Read KB/s', 'Write KB/s'],
                'max' => nil,
                'threshold' => 'XXX'
              },
              {
                'label' => 'Latency ms',
                'key' => 'latency',
                'fields' => ['latencyReads', 'latencyWrites'],
                'fieldLabels' => ['Read Latency', 'Write Latency'],
                'max' => nil,
                'threshold' => 'XXX'
              }
            ]
          }
        end
        statsObj = statsDB.get(key)
        merger = StatsMerger.new
        merger.mergeStats(statsObj, [@vscsiHostStats],
          'numReads' => nil,
          'numWrites' => nil,
          'bytesRead' => nil,
          'bytesWrite' => nil,
          'latencyReads' => "numReads",
          'latencyWrites' => "numWrites",
        )
        return dumpGenericStatsDB(statsDB, [group, file], nil, opts)
      end
    end
  end

  def dumpDom uuid, stats = nil, opts = {}
    if !stats
      stats = @v3DomStats.get([uuid])
    end
    out = {
      'uuid' => uuid,
      'stats' => Hash[stats.map do |key, value|
        [key.to_s, value.to_json(opts)]
      end]
    }
    if uuid !~ /(total-|client-|compmgr-)/
      begin
        entries = @cmmdsHistory[['DOM_OBJECT', uuid]]
        if entries && entries.length > 0
          if entries.length > 1
            $stderr.puts "Warning: DOM object #{uuid} has a history and we ignore it"
          end
          entry = entries.last
          comps = _components_in_dom_config(entry['content'])
          compStats = comps.map{|x| @lsomStats[x['componentUuid']]}.compact
          keys = compStats.map{|x| x.keys}.flatten.uniq
          compStats = Hash[keys.map do |key|
            list = compStats.map{|x| x[key]}.compact
            [key.to_s, InventoryStat.merge(list)]
          end]
          out['lsomstats'] = Hash[compStats.map do |key, value|
            [key.to_s, value.to_json(opts)]
          end]
        end
      rescue Exception => ex
        pp ex.message
        pp ex.backtrace
      end

    end

    out
  end

  def dumpVsansparseHosts
    out = @vsansparse.keys
    return out
  end

  def dumpVsansparseList
    @vsansparseOpenChain.each do |hostname, chains|
      chains.each do | openUuid, stats|
        @vsansparseList[openUuid] = hostname
      end
    end

    out = @vsansparseList
    return out
  end

  def dumpVsansparse hostname, uuid, stats = nil, opts = {}
    if !stats
      stats = (uuid == nil ? @vsansparse[hostname] : @vsansparseOpenChain[hostname][uuid])
    end
    out = {
      'hostname' => hostname,
      'uuid' => uuid,
      'stats' => Hash[stats.map do |key, value|
        [key.to_s, value.to_json(opts)]
      end]
    }
  end

  def dumpPcpu host, opts = {}
    pcpus = Hash[@pcpuStats.select{|k,v| k[0] == host}.map do |k,v|
      [k[1], v]
    end]
    out = {
      'hostname' => host,
      'stats' => Hash[pcpus.map do |pcpu, stats|
        [pcpu, Hash[stats.map do |key, value|
          [key.to_s, value.to_json(opts)]
        end]]
      end]
    }
  end

  def dumpWdt hostname, wdt, stats = nil, opts = {}
    if !stats
      stats = @worldletStats[[hostname, wdt]]
    end
    out = {
      'hostname' => hostname,
      'wdt' => wdt,
      'stats' => Hash[stats.map do |key, value|
        [key.to_s, value.to_json(opts)]
      end]
    }
  end

  def dumpWdtSum hostname, opts = {}
    statsList = @worldletStats.select{|k,v| k[0] == hostname}.values
    stats = {}
    statsList.first.each do |k,v|
      stats[k] = _sumInventoryStats(statsList.map{|x| x[k]})
    end
    out = {
      'hostname' => hostname,
      'stats' => Hash[stats.map do |key, value|
        [key.to_s, value.to_json(opts)]
      end]
    }
  end

  def dumpHelperWorld hostname, wdt, stats = nil, opts = {}
    key = [hostname, wdt]
    if !stats
      stats = @helperWorldStats[key]
    end
    out = {
      'hostname' => hostname,
      'helperworld' => @helperWorldNames[key],
      'stats' => Hash[stats.map do |key, value|
        [key.to_s, value.to_json(opts)]
      end]
    }
  end

  def dumpHelperWorldSum hostname, opts = {}
    statsList = @helperWorldStats.select{|k,v| k[0] == hostname}.values
    stats = {}
    statsList.first.each do |k,v|
      stats[k] = _sumInventoryStats(statsList.map{|x| x[k]})
    end
    out = {
      'hostname' => hostname,
      'stats' => Hash[stats.map do |key, value|
        [key.to_s, value.to_json(opts)]
      end]
    }
  end

  def dumpHeaps hostname, heaps = nil, opts = {}
    if !heaps
      heaps = @heaps[hostname]
    end
    out = {
      'hostname' => hostname,
      'stats' => {},
    }

    {
      'cmmds' => /^(CMMDS)/,
      'slabs' => /(Slab)/,
      'other' => nil
    }.each do |name, pattern|
      if pattern
        selected_heaps = heaps.select{|k, v| k =~ pattern}
        heaps = heaps.reject{|k, v| k =~ pattern}
      else
        selected_heaps = heaps
      end

      out['stats'][name] = Hash[selected_heaps.map do |heap, _stats|
        stats = {
          'times' => _stats.keys,
          'values' => _stats.values.map{|x| x[:pctFreeOfMax] },
        }
        if opts[:points]
          stats['times'] = _compressFirst(stats['times'], opts[:points])
          stats['values'] = _compressAvg(stats['values'], opts[:points])
        end
        [heap, stats]
      end]
    end

    out
  end

  def dumpSlabs hostname, slabs = nil, opts = {}
    if !slabs
      slabs = @slabs[hostname]
    end

    out = {
      'hostname' => hostname,
      'stats' => {},
    }

    {
      'congestion' => /^(Task|PLOG_Task|LSOM_Task|BL_NodeSlab|BL_CB|LSOM_LsnEntry|dom-[^-]*-opsSlab)/,
      'lsom' => /^(RC|Rc|PLOG|SSD|LSOM|BL_)/,
      'dom' => nil
    }.each do |name, pattern|
      if pattern
        selected_slabs = slabs.select{|k, v| k =~ pattern}
        slabs = slabs.reject{|k, v| k =~ pattern}
      else
        selected_slabs = slabs
      end

      out['stats'][name] = Hash[selected_slabs.map do |slab, _stats|
        stats = {
          'times' => _stats.keys,
          'values' => _stats.values.map{|x| x[:usedObjs] },
        }
        if opts[:points]
          stats['times'] = _compressFirst(stats['times'], opts[:points])
          stats['values'] = _compressAvg(stats['values'], opts[:points])
        end
        [slab, stats]
      end]
    end

    out
  end

  def dumpLsomComp uuid, stats = nil, opts = {}
    if !stats
      stats = @lsomStats[uuid]
    end
    out = {
      'uuid' => uuid,
      'stats' => Hash[stats.map do |key, value|
        [key.to_s, value.to_json(opts)]
      end]
    }
  end

  def dumpPlog dev, hostname = nil, devinfo = nil, stats = nil, opts = {}
    if !stats
      key = [hostname, dev, devinfo]
      if !hostname
        key = @plogStats.keys.find{|x| x[1] == dev}
        hostname, dev, devinfo = key
      end
      stats = @plogStats[key]
    end
    out = {
      'hostname' => hostname,
      'dev' => dev,
      'devtype' => (devinfo['isSSD'] == 1) ? "SSD" : "MD",
      'stats' => Hash[stats.map do |key, value|
        [key.to_s, value.to_json(opts)]
      end]
    }
  end

  def dumpDisk dev, hostname = nil, stats = nil, opts = {}
    if !stats
      key = [hostname, dev]
      if !hostname
        key = @diskStats.keys.find{|x| x[1] == dev}
        hostname, dev = key
      end
      stats = @diskStats[key]
    end
    out = {
      'hostname' => hostname,
      'dev' => dev,
      'stats' => Hash[stats.map do |key, value|
        [key.to_s, value.to_json(opts)]
      end]
    }
  end

  def dumpVmList
    out = Hash[(@vms || {}).map do |moid, vmInfo|
      fields = ['name', 'vsan-obj-uuids', 'disks']
      vmInfo = vmInfo.select{|k,v| fields.member?(k)}
      vmInfo['moid'] = moid
      objs = vmInfo['vsan-obj-uuids']
      vmInfo['vsan_vm_home'] = Hash[objs.select do |k, x|
        x =~ /(\.vmx|\.vmtx)$/
      end.map{|k, x| [k, "VM Home"]}]
      vmInfo['vsan_disks'] = Hash[objs.select do |k, x|
        x =~ /\.vmdk$/
      end]
      vmInfo['disks'] = Hash[(vmInfo['disks'] || []).map do |disk|
        name = "scsi%d:%d" % [
          (disk['controllerKey'] || 1000) - 1000,
          disk['unitNumber']
        ]
        [name, disk]
      end]
      [moid, vmInfo]
    end]
  end

  def dumpGenericStatsDB stats, fileInfo, key = nil, opts = {}
    key ||= stats.files[fileInfo]
    if !key
      pp stats.files
      return nil
    end
    out = stats.package(key, opts)
    out
  end

  def dumpVscsi vm, disk, stats = nil, opts = {}
    if !stats
      key = [vm, disk]
      stats = @vscsiStats[key]
    end
    out = {
      'vm' => vm,
      'disk' => disk,
      'stats' => Hash[stats.map do |key, value|
        [key.to_s, value.to_json(opts)]
      end]
    }
  end

  def dumpIoAmplification hostname, stats = nil, opts = {}
    if !stats
      stats = @ioAmplification[hostname]
    end
    out = {
      'hostname' => hostname,
      'stats' => Hash[stats.map do |key, value|
        [key.to_s, value.to_json(opts)]
      end]
    }
  end

  def dumpDistribution opts = {}
    out = {
      'hosts' => Hash[@counts.map do |hostname, stats|
        [
          hostname,
          Hash[stats.map do |key, value|
            [key.to_s, value.to_json(opts)]
          end]
        ]
      end]
    }
  end

  def dumpPnics hostname, stats = nil, opts = {}
    if !stats
      stats = @pnics[hostname]
    end
    out = {
      'pnics' => Hash[stats.map do |pnic, stats|
        [
          pnic,
          Hash[stats.map do |key, value|
            [key.to_s, value.to_json(opts)]
          end]
        ]
      end]
    }
  end

  def dumpVmknicStats hostname, stats = nil, opts = {}
    if !stats
      stats = @vmknicStats[hostname]
    end
    out = {
      'stats' => Hash[stats.map do |layer, layerStats|
        [
          layer,
          Hash[layerStats.map do |key, value|
            [key.to_s, value.to_json(opts)]
          end]
        ]
      end]
    }
  end

  def dumpFitnessStats hostname, stats = nil, opts = {}
    if !stats
      stats = @fitnessStats[hostname]
    end
    out = {
      'hostname' => hostname,
      'fitness' => Hash[stats.map do |param, stats|
        [
          param,
          Hash[stats.map do |key, value|
            [key.to_s, value.to_json(opts)]
          end]
        ]
      end]
    }
  end

  def dumpCmmdsStats hostname, stats = nil, opts = {}
    if !stats
      stats = @cmmdsStats[hostname]
    end
    out = {
      'hostname' => hostname,
      'stats' => Hash[stats.map do |param, stats|
        [
          param,
          Hash[stats.map do |key, value|
            [key.to_s, value.to_json(opts)]
          end]
        ]
      end]
    }
  end

  def dumpIscsiTargetList
    out = Hash[(@vsanIscsiTargetList || {}).map do |targetAlias, targetInfo|
      [targetAlias, targetInfo]
    end]
  end

  def dumpIscsiTargetHostStats hostname, stats = nil, opts = {}
    if !stats
      stats = @vsanIscsiTargetHostStats[hostname]
    end
    out = {
      'hostname' => hostname,
      'stats' => Hash[stats.map do |param, stats|
        [
          param,
          Hash[stats.map do |key, value|
            [key.to_s, value.to_json(opts)]
          end]
        ]
      end]
    }
  end

  def dumpIscsiTargetTargetStats targetAlias, stats = nil, opts = {}
    # for external observer servejson method in vsan.rb
    if !stats
      if @vsanIscsiTargetList.has_key?(targetAlias) and
        @vsanIscsiTargetTargetStats.has_key?(targetAlias)
          stats = @vsanIscsiTargetTargetStats[targetAlias]
      end
    end
    out = {
      'targetAlias' => targetAlias,
      'stats' => Hash[stats.map do |key, value|
        [key.to_s, value.to_json(opts)]
      end]
    }
  end

  def dumpIscsiTargetLunStats lunUuid, stats = nil, opts = {}
    # for external observer servejson method in vsan.rb
    if !stats
      @vsanIscsiTargetLunStats.each do |targetAlias, targetLuns|
        targetLuns.map do |lunId, lunStatsGroups|
          if @vsanIscsiTargetList.has_key?(targetAlias) and
            @vsanIscsiTargetList[targetAlias]['luns'].has_key?(lunId)
            if lunUuid ==
              @vsanIscsiTargetList[targetAlias]['luns'][lunId]['lun-uuid']
              stats = lunStatsGroups
              break
            end
          end
        end
        if stats
          break
        end
      end
    end
    out = {
      'lunUuid' => lunUuid,
      'stats' => Hash[stats.map do |lunStatsGroup, lunStats|
        [
          lunStatsGroup,
          Hash[lunStats.map do |key, value|
            [key.to_s, value.to_json(opts)]
          end]
        ]
      end]
    }
  end

  def dumpCbrc hostname, stats = nil, opts = {}
    if !stats
      stats = @cbrcStats[hostname]
    end
    out = {
      'hostname' => hostname,
      'stats' => Hash[stats.map do |key, value|
        [key.to_s, value.to_json(opts)]
      end]
    }
  end

  def dumpSystemMem host, stats = nil, opts = {}
    if !stats
      stats = @systemMem[host]
    end
    out = {
      'host' => host,
      'stats' => Hash[stats.map do |key, value|
        [key.to_s, value.to_json(opts)]
      end]
    }
  end

  def dumpCmmdsDisks
    out = @cmmdsDisks.merge({'hostnames' => @hostnames})
    @plogDeviceInfo.each do |uuid, info|
      out[uuid] ||= {}
      out[uuid]['info'] = info
    end
    out
  end

  def dumpCmmdsUuid uuid
    @cmmdsHistory[uuid]
  end

  def dumpToFile(group, filename, content)
    path = File.join("jsonstats", group, filename)
    FileUtils.mkdir_p(File.join("jsonstats", group))
    open(path, 'w') do |io|
      io.write(json_dump(content))
    end
  end

  def dumpToTar(tar, group, filename, content)
    path = File.join("jsonstats", group, filename)
    tar.add_file(path, 0644) do |io|
      io.write(json_dump(content))
    end
  end

  def dump(dumpOpts = {})
    if dumpOpts[:tar]
      dumpOpts[:tar].mkdir('jsonstats', 0777)
    end
    ['vm', 'dom', 'lsom', 'cmmds', 'pcpu', 'mem', 'misc', 'nfs', 'clom', 'vsansparse', 'vit'].each do |x|
      if dumpOpts[:tar]
        dumpOpts[:tar].mkdir(File.join('jsonstats', x), 0777)
      else
        FileUtils.mkdir_p(File.join('jsonstats', x))
      end
    end

    toFileProc = Proc.new do |group, filename, content|
      if dumpOpts[:tar]
        dumpToTar(dumpOpts[:tar], group, filename, content)
      else
        dumpToFile(group, filename, content)
      end
    end

    thumbPoints = 60
    thumbOpts = {:points => thumbPoints}
    puts "#{Time.now}: Writing statsdump for system mem ..."
    @systemMem.each do |hostname, stats|
      toFileProc.call("mem", "system-#{hostname}.json",
        dumpSystemMem(hostname, stats)
      )
      toFileProc.call("mem", "system-#{hostname}_thumb.json",
        dumpSystemMem(hostname, stats, thumbOpts)
      )
    end

    puts "#{Time.now}: Writing statsdump for pnics ..."
    @pnics.each do |hostname, stats|
      toFileProc.call("misc", "pnics-#{hostname}.json",
        dumpPnics(hostname, stats)
      )
      toFileProc.call("misc", "pnics-#{hostname}_thumb.json",
        dumpPnics(hostname, stats, thumbOpts)
      )
    end

    puts "#{Time.now}: Writing statsdump for vmktcpip stack ..."
    @vmknicStats.each do |hostname, stats|
      toFileProc.call("misc", "vmknic-#{hostname}.json",
        dumpVmknicStats(hostname, stats)
      )
      toFileProc.call("misc", "vmknic-#{hostname}_thumb.json",
        dumpVmknicStats(hostname, stats, thumbOpts)
      )
    end

    puts "#{Time.now}: Writing statsdump for slabs ..."
    @slabs.each do |hostname, slabs|
      toFileProc.call("mem", "slabs-#{hostname}.json",
        dumpSlabs(hostname, slabs)
      )
      toFileProc.call("mem", "slabs-#{hostname}_thumb.json",
        dumpSlabs(hostname, slabs, thumbOpts)
      )
    end

    puts "#{Time.now}: Writing statsdump for heaps ..."
    @heaps.each do |hostname, heaps|
      toFileProc.call("mem", "heaps-#{hostname}.json",
        dumpHeaps(hostname, heaps)
      )
      toFileProc.call("mem", "heaps-#{hostname}_thumb.json",
        dumpHeaps(hostname, heaps, thumbOpts)
      )
    end

    puts "#{Time.now}: Writing statsdump for fitness stats ..."
    @fitnessStats.each do |hostname, stats|
      toFileProc.call("clom", "fitness-#{hostname}.json",
        dumpFitnessStats(hostname, stats)
      )
      toFileProc.call("clom", "fitness-#{hostname}_thumb.json",
        dumpFitnessStats(hostname, stats, thumbOpts)
      )
    end

    puts "#{Time.now}: Writing statsdump for cmmds stats ..."
    @cmmdsStats.each do |hostname, stats|
      toFileProc.call("cmmds", "cmmds-vsi-#{hostname}.json",
        dumpCmmdsStats(hostname, stats)
      )
      toFileProc.call("cmmds", "cmmds-vsi-#{hostname}_thumb.json",
        dumpCmmdsStats(hostname, stats, thumbOpts)
      )
    end

    puts "#{Time.now}: Writing statsdump for vSAN iSCSI Target host stats ..."
    @vsanIscsiTargetHostStats.each do |hostname, stats|
      toFileProc.call("vit", "vit-vsi-#{hostname}.json",
        dumpIscsiTargetHostStats(hostname, stats)
      )
      toFileProc.call("vit", "vit-vsi-#{hostname}_thumb.json",
        dumpIscsiTargetHostStats(hostname, stats, thumbOpts)
      )
    end

    puts "#{Time.now}: Writing statsdump for pcpus ..."
    hosts = @pcpuStats.keys.map{|x| x[0]}.uniq
    hosts.each do |host|
      toFileProc.call("pcpu", "pcpu-#{host}.json",
        dumpPcpu(host)
      )
      toFileProc.call("pcpu", "pcpu-#{host}_thumb.json",
        dumpPcpu(host, thumbOpts)
      )
    end

    puts "#{Time.now}: Writing statsdump for worldlets ..."
    @worldletStats.each do |_wdt, stats|
      hostname, wdt = _wdt

      toFileProc.call("pcpu", "wdt-#{hostname}-#{wdt}.json",
        dumpWdt(hostname, wdt, stats)
      )
      toFileProc.call("pcpu", "wdt-#{hostname}-#{wdt}_thumb.json",
        dumpWdt(hostname, wdt, stats, thumbOpts)
      )
    end
    @worldletStats.keys.map{|x| x[0]}.uniq.each do |hostname|
      toFileProc.call("pcpu", "wdtsum-#{hostname}.json",
        dumpWdtSum(hostname)
      )
      toFileProc.call("pcpu", "wdtsum-#{hostname}_thumb.json",
        dumpWdtSum(hostname, thumbOpts)
      )
    end

    puts "#{Time.now}: Writing statsdump for helper worlds ..."
    @helperWorldStats.each do |_key, stats|
      hostname, helper = _key

      toFileProc.call("pcpu", "helperworld-#{hostname}-#{helper}.json",
        dumpHelperWorld(hostname, helper, stats)
      )
      toFileProc.call("pcpu", "helperworld-#{hostname}-#{helper}_thumb.json",
        dumpHelperWorld(hostname, helper, stats, thumbOpts)
      )
    end
    @helperWorldStats.keys.map{|x| x[0]}.uniq.each do |hostname|
      toFileProc.call("pcpu", "helperworldsum-#{hostname}.json",
        dumpHelperWorldSum(hostname)
      )
      toFileProc.call("pcpu", "helperworldsum-#{hostname}_thumb.json",
        dumpHelperWorldSum(hostname, thumbOpts)
      )
    end


    puts "#{Time.now}: Writing statsdump for DOM ..."
    @v3DomStats.stats.each do |key, stats|
      uuid = key[0]
      toFileProc.call("dom", "domobj-#{uuid}.json",
        dumpDom(uuid, stats)
      )
      toFileProc.call("dom", "domobj-#{uuid}_thumb.json",
        dumpDom(uuid, stats, thumbOpts)
      )
    end

    if !$observer_skip_components
      puts "#{Time.now}: Writing statsdump for LSOM components ..."
      @lsomStats.each do |uuid, stats|
        toFileProc.call("lsom", "lsomcomp-#{uuid}.json",
          dumpLsomComp(uuid, stats)
        )
        toFileProc.call("lsom", "lsomcomp-#{uuid}_thumb.json",
          dumpLsomComp(uuid, stats, thumbOpts)
        )
      end
    end

    puts "#{Time.now}: Writing statsdump for PLOG disks ..."
    @plogStats.each do |_dev, stats|
      hostname, dev, devinfo = _dev
      toFileProc.call("lsom", "plog-#{dev}.json",
        dumpPlog(dev, hostname, devinfo, stats)
      )
      toFileProc.call("lsom", "plog-#{dev}_thumb.json",
        dumpPlog(dev, hostname, devinfo, stats, thumbOpts)
      )
    end

    puts "#{Time.now}: Writing statsdump for LSOM disks ..."
    @diskStats.each do |_dev, stats|
      hostname, dev = _dev
      toFileProc.call("lsom", "disk-#{dev}.json",
        dumpDisk(dev, hostname, stats)
      )
      toFileProc.call("lsom", "disk-#{dev}_thumb.json",
        dumpDisk(dev, hostname, stats, thumbOpts)
      )
    end

    puts "#{Time.now}: Writing virstoStats for LSOM disks ..."
    @virstoStats.each do |_dev, stats|
      hostname, dev = _dev
      toFileProc.call("lsom", "virsto-#{dev}.json",
         dumpDisk(dev, hostname, stats)
      )
    end

    puts "#{Time.now}: Writing CFStats for LSOM disks ..."
    @CFStats.each do |_dev, stats|
      hostname, dev = _dev
      toFileProc.call("lsom", "CF-#{dev}.json",
         dumpDisk(dev, hostname, stats)
      )
    end

    #Output the host only stats
    puts "#{Time.now}: Writing vsansparse ..."
    @vsansparse.each do |hostname, stats|
      @vsansparseHosts[hostname] = true
      toFileProc.call("vsansparse", "vsansparse-#{hostname}.json",
         dumpVsansparse(hostname, nil, stats)
      )
      toFileProc.call("vsansparse", "vsansparse-#{hostname}_thumb.json",
         dumpVsansparse(hostname, nil, stats, thumbOpts)
      )
    end

    puts "#{Time.now}: Writing vsansparse Open Chains ..."
    @vsansparseOpenChain.each do |hostname, chains|
      chains.each do | openUuid, stats|
        @vsansparseList[openUuid] = hostname
        toFileProc.call("vsansparse", "vsansparse-#{hostname}-#{openUuid}.json",
                        dumpVsansparse(hostname, openUuid, stats)
                       )
        toFileProc.call("vsansparse", "vsansparse-#{hostname}-#{openUuid}_thumb.json",
                        dumpVsansparse(hostname, openUuid, stats, thumbOpts)
                       )
      end
    end

    puts "#{Time.now}: Writing statsdump for CBRC ..."
    @cbrcStats.each do |hostname, stats|
      toFileProc.call("misc", "cbrc-#{hostname}.json",
        dumpCbrc(hostname, stats)
      )
      toFileProc.call("misc", "cbrc-#{hostname}_thumb.json",
        dumpCbrc(hostname, stats, thumbOpts)
      )
    end

    puts "#{Time.now}: Writing statsdump for VSCSI ..."
    @vscsiStats.each do |_dev, stats|
      vm, disk = _dev
      if vm.include?("/")
        vm = vm.split("/").last
      end
      toFileProc.call("vm", "vscsi-#{disk}-#{vm}.json",
        dumpVscsi(vm, disk, stats)
      )
      toFileProc.call("vm", "vscsi-#{disk}-#{vm}_thumb.json",
        dumpVscsi(vm, disk, stats, thumbOpts)
      )
    end
    @ioAmplification.each do |hostname, stats|
      toFileProc.call("misc", "ioamp-#{hostname}.json",
        dumpIoAmplification(hostname, stats)
      )
      toFileProc.call("misc", "ioamp-#{hostname}_thumb.json",
        dumpIoAmplification(hostname, stats, thumbOpts)
      )
    end

    {
      'NFS' => @nfsStats,
      'VSCSI-host' => @vscsiHostStats,
      'LSOM Congestion' => @lsomCongestion,
      'LSOM Host' => @lsomHostStats,
      'PhysDisk' => @physDiskStats,
      'SSDs WB' => @ssds,
    }.each do |title, stats|
      puts "#{Time.now}: Writing statsdump for #{title} ..."
      stats.files.each do |fileInfo, key|
        toFileProc.call(fileInfo[0], "#{fileInfo[1]}.json",
          dumpGenericStatsDB(stats, fileInfo, key)
        )
        toFileProc.call(fileInfo[0], "#{fileInfo[1]}_thumb.json",
          dumpGenericStatsDB(stats, fileInfo, key, thumbOpts)
        )
      end
    end
    if $observer_include_aggregates
      [
        ['misc', 'vscsisum'],
        ['nfs', 'nfssum'],
        ['dom', 'domclientsum'],
        ['dom', 'domownersum'],
        ['dom', 'domcompmgrsum'],
        ['dom', 'domvmhomesum'],
        ['dom', 'domvmdiskssum'],
        ['lsom', 'lsomsum'],
        ['lsom', 'physdiskcachesum'],
        ['lsom', 'physdiskcapacitysum'],
        ['lsom', 'ssdsum'],
      ].each do |group, file|
        puts "#{Time.now}: Writing statsdump for sums: #{group}/#{file} ..."
        toFileProc.call(group, "#{file}.json",
          dumpByFilename(group, file)
        )
        toFileProc.call(group, "#{file}_thumb.json",
          dumpByFilename(group, file, thumbOpts)
        )
      end
    end

    if !$observer_skip_cmmds_history
      puts "#{Time.now}: Writing out CMMDS history ..."
      @cmmdsHistory.keys.each do |uuid|
        toFileProc.call("cmmds", "cmmds-#{uuid}.json",
          dumpCmmdsUuid(uuid)
        )
      end
    end

    toFileProc.call("misc", "timerange.json", dumpTimerange())

    puts "#{Time.now}: Done dumping time series stats"
  end

  def dumpTimerange
    firstTs = nil
    lastTs = nil
    @pnics.each do |hostname, stats|
      next if stats.empty?
      stats[stats.keys.first].values.each do |val|
        times = val.times
        if !firstTs || times.first < firstTs
          firstTs = times.first
        end
        if !lastTs || times.last < lastTs
          lastTs = times.last
        end
        break
      end
    end
    {
      'firstTS' => firstTs,
      'lastTS' => lastTs,
    }
  end

  def dumpAggregates(dumpOpts = {})
    toFileProc = Proc.new do |group, filename, content|
      if dumpOpts[:tar]
        dumpToTar(dumpOpts[:tar], group, filename, content)
      else
        dumpToFile(group, filename, content)
      end
    end

    thumbPoints = 60
    thumbOpts = {:points => thumbPoints}

    puts "#{Time.now}: Writing statsdump for VMs ..."
    toFileProc.call("vm", "list.json",
      dumpVmList()
    )

    puts "#{Time.now}: Writing out vSAN iSCSI Target list ..."
    # group "vit" (vSAN iSCSI Target) under jsonstats
    toFileProc.call("vit", "vit-list.json",
      dumpIscsiTargetList()
    )

    puts "#{Time.now}: Writing statsdump for vSAN iSCSI Target target stats ..."
    @vsanIscsiTargetTargetStats.each do |targetAlias, targetStats|
      if @vsanIscsiTargetList.has_key?(targetAlias)
        toFileProc.call("vit", "vit-vsi-target-#{targetAlias}.json",
          dumpIscsiTargetTargetStats(targetAlias, targetStats)
        )
        toFileProc.call("vit", "vit-vsi-target-#{targetAlias}_thumb.json",
          dumpIscsiTargetTargetStats(targetAlias, targetStats, thumbOpts)
        )
      end
    end

    # dump iSCSI LUN stats here since we rely on aggregated vsanIscsiTargetList
    # for targetAlias/lunId => lunUuid mapping
    puts "#{Time.now}: Writing statsdump for vSAN iSCSI Target LUN stats ..."
    @vsanIscsiTargetLunStats.each do |targetAlias, targetLuns|
      targetLuns.map do |lunId, lunStatsGroups|
        if @vsanIscsiTargetList.has_key?(targetAlias) and
          @vsanIscsiTargetList[targetAlias]['luns'].has_key?(lunId)
          lunUuid = @vsanIscsiTargetList[targetAlias]['luns'][lunId]['lun-uuid']
          toFileProc.call("vit", "vit-vsi-lun-#{lunUuid}.json",
            dumpIscsiTargetLunStats(lunUuid, lunStatsGroups)
          )
          toFileProc.call("vit", "vit-vsi-lun-#{lunUuid}_thumb.json",
            dumpIscsiTargetLunStats(lunUuid, lunStatsGroups, thumbOpts)
          )
        end
      end
    end

    puts "#{Time.now}: Writing out CMMDS Disk info ..."
    toFileProc.call("cmmds", "disks.json",
      dumpCmmdsDisks()
    )

    puts "#{Time.now}: Writing out Distribution info ..."
    toFileProc.call("misc", "distribution.json",
      dumpDistribution()
    )
    toFileProc.call("misc", "distribution_thumb.json",
      dumpDistribution(thumbOpts)
    )
    #output the openuuids -> host structure
    toFileProc.call("vsansparse", "vsansparseList.json", @vsansparseList)
    # output [hosts]
    toFileProc.call("vsansparse", "vsansparseHosts.json", @vsansparseHosts.keys)
    #output uuid-> filename
    toFileProc.call("vsansparse", "vsansparseMaps.json", @vsansparsePathmap)
  end

  def processInventorySnapshot j
    if !j.has_key?('snapshot')
      return
    end
    @fixedDomTotals = false

    if j['snapshot'].has_key? 'cmmds'
      processCmmds j
    end
    if j['snapshot'].has_key? 'vsi'
      processVsi j
    end
    if j['snapshot'].has_key? 'inventory'
      processInventory j
    end
    if j['snapshot'].has_key? 'vcinfo'
      @vcInfo.update(j['snapshot']['vcinfo'])
    end
  end

  def processCmmds j
    j['snapshot']['cmmds']['clusterInfos'].each do |host, info|
      @cmmdsClusterInfos[host] = info
    end

    # This is not really correct. It doesn't deal with partitions
    dir = j['snapshot']['cmmds']['clusterDirs'].values.first
    if !dir
      return
    end
    dir.each do |entry|
      types = [
        'DOM_OBJECT', 'LSOM_OBJECT', 'POLICY', 'CONFIG_STATUS',
        'DISK', 'HOSTNAME',
      ]
      if !types.member?(entry['type'])
        next
      end

      @cmmdsHistory[entry['uuid']] ||= {}
      @cmmdsHistory[entry['uuid']][entry['type']] ||= []
      existing = @cmmdsHistory[entry['uuid']][entry['type']].last
      if (!existing) || existing['md5sum'] != entry['md5sum']
        entry['ts'] = j['timestamp']
        if !entry['content'] || entry['content'].empty? || entry['content'] == 'null'
          $stderr.puts "#{entry['ts']}: WARNING: Ignoring: #{entry['type']} UUID: #{entry['uuid']} with empty content. Please check the health of this object."
          next
        end
        if entry['content'].is_a?(String)
          entry['content'] = JSON.load(entry['content'])
        end

        if entry['type'] == 'HOSTNAME'
          @hostnames ||= {}
          @hostnames[entry['uuid']] = entry['content']['hostname']
        end
        if entry['type'] == 'DISK'
          if !@hostnames[entry['owner']]
            # Do not add this entry to the history so it gets revisited
            next
          end
          entry['hostname'] = @hostnames[entry['owner']]
          @cmmdsDisks ||= {}
          @cmmdsDisks[entry['uuid']] = entry
        end

        @cmmdsHistory[entry['uuid']][entry['type']] << entry
      end
    end
  end

  def processInventory j
    if !j['snapshot'] || !j['snapshot']['inventory']
      return
    end
    inventory = j['snapshot']['inventory']

    (inventory['vms'] || {}).each do |vm, vmInfo|
      @vms ||= {}
      @vms[vm] ||= {}
      @vms[vm]['name'] = vmInfo['name']
      @vms[vm]['vsan-obj-uuids'] ||= {}
      if vmInfo.has_key? 'vsan-obj-uuids'
        @vsanObjUuids.merge!(vmInfo['vsan-obj-uuids'])
        @vms[vm]['vsan-obj-uuids'].merge!(vmInfo['vsan-obj-uuids'])
      end
      @vms[vm]['disks'] = vmInfo['disks']

      @vmInfoHistory[vm] ||= []
      if vmInfo.has_key? 'runtime.connectionState'
        existing = @vmInfoHistory[vm].last
        if (!existing) || existing['runtime.connectionState'] != vmInfo['runtime.connectionState']
          vmInfo['ts'] = j['timestamp']
          @vmInfoHistory[vm] << vmInfo
        end
      end
    end

    (inventory['hosts'] || {}).each do |host, hostInfo|
      @hostsProps[host] ||= hostInfo
    end
  end

  def processVsansparse(ts, dest, ioSource, allocSource, expectAll)
    if ioSource.nil? or allocSource.nil?
      #puts "#{Time.now}: Missing iostats or allocstats"
      return
    end
    [
      "minLookupTimeUsec",
      "maxGWETimeUsec",
      "maxLookupTimeUsec",
      "minWriteTimeUsec",
      "maxWriteTimeUsec",
      "minGWETimeUsec",
      "maxReadTimeUsec",
      "minReadTimeUsec",
    ].each do |stat|
      if ioSource.has_key?(stat)
        dest[stat] ||= InventoryStat.new
        dest[stat].addStatic(ts, ioSource[stat])
      #else
      #  puts "#{Time.now}: Missing vsansparse stat #{stat} skipping"
      end

    end
    [
      "writeBytes",
      "writeTimeUsec",
      "writes",
      "readTimeUsec",
      "cacheLookupTimeUsec",
      "cacheUpdateTimeUsec",
      "lookups",
      "reads",
      "splitReads",
      "readBytes",
      "splitLookupTimeUsec",
      "splitLookups",
      "lookupTimeUsec",
    ].each do |stat|
      if ioSource.has_key?(stat)
        dest[stat] ||= InventoryStat.new
        dest[stat].add(ts, ioSource[stat])
      #else
      #  puts "#{Time.now}: Missing vsansparse stat #{stat} skipping"
      end
    end
    [
     "inserts",
     "hits",
     "evictions",
     "removes",
     "lruUpdates",
     "lruLockContentions",
     "attemptedEvictions",
     "misses",
     "extentHits",
     "lockContentions",
     "allocFailures",].each do |stat|
       if allocSource.has_key?(stat)
         dest[stat] ||= InventoryStat.new
         dest[stat].add(ts, allocSource[stat])
       #else
       #  puts "#{Time.now}: Missing vsansparse stat #{stat} skipping"
       end
     end
     ["entries"].each do |stat|
       if allocSource.has_key?(stat)
         dest[stat] ||= InventoryStat.new
         dest[stat].addStatic(ts, allocSource[stat])
       #else
       #  puts "#{Time.now}: Missing vsansparse stat #{stat} skipping"
       end
     end
  end

  def processVsi j
    allHost = j['snapshot']['vsi']
    allHost.each do |hostname, host|
      @counts[hostname] ||= {}
      @counts[hostname]['dom.owners'] ||= InventoryStat.new
      @counts[hostname]['lsom.iocomponents'] ||= InventoryStat.new
      @counts[hostname]['lsom.components'] ||= InventoryStat.new
      @counts[hostname]['lsom.diskcapacity'] ||= InventoryStat.new
      @counts[hostname]['dom.clients'] ||= InventoryStat.new
      @counts[hostname]['dom.colocated'] ||= InventoryStat.new

      uuids = {}
      if host['fitness-stats']
        fields = {}
        ts = host['fitness-stats']['taken']
        @fitnessStats[hostname] ||= {}
        host['fitness-stats']['data'].each do |disk|
          diskid = disk['diskid'];
          disk.delete('diskid');
          disk.each do |paramName, paramValue|
            @fitnessStats[hostname][paramName] ||= {}
            @fitnessStats[hostname][paramName][diskid] ||= InventoryStat.new
            @fitnessStats[hostname][paramName][diskid].addStatic(ts, paramValue)
          end
        end
      end

      @cmmdsStats[hostname] ||= {}
      # Backwards compatability check, if one of these is present, everything
      # should be present!
      if host['cmmds.vsi-taken']
        ts = host['cmmds.vsi-taken']
        vsi = ['cmmds.master', 'cmmds.queues', 'cmmds.workload', 'cmmdsnet.stats']

        # Some computation of params not in vsi
        host['cmmds.workload']['rxLocalUpdate'] = (
          host['cmmds.workload']['rxAccept'] -
          host['cmmds.workload']['rxAgentUpdateRequest']
        )
        host['cmmds.master']['totalUpdates'] = (
          host['cmmds.master']['droppedUpdatesToWitnessAgents'] +
          host['cmmds.master']['seqNumUpdatesToWitnessAgents'] +
          host['cmmds.master']['updatesToRegAgents'] +
          host['cmmds.master']['seqNumUpdatesToRegAgents'] +
          host['cmmds.master']['noPayloadUpdatesToWitnessAgents'] +
          host['cmmds.master']['fullUpdatesToWitnessAgents']
        )

        vsi.each do |param|
          @cmmdsStats[hostname][param] ||= {}
          host[param].each do |p, pv|
            @cmmdsStats[hostname][param][p] ||= InventoryStat.new
            # Special handling of queues (which is a list)
            if param == 'cmmds.queues'
              @cmmdsStats[hostname][param][p].add(
                ts,
                pv['depthHisto']['count']
              )
            else
              @cmmdsStats[hostname][param][p].add(ts, pv)
            end
          end
        end
      end

      if host['vit.targetList']
        # empty @vsanIscsiTargetList since we only use the latest trace record
        @vsanIscsiTargetList = {}
        host['vit.targetList'].each do |targetAlias, targetInfo|
          @vsanIscsiTargetList[targetAlias] = targetInfo
        end
      end

      if host['vit.vsi-taken']
        ts = host['vit.vsi-taken']

        @vsanIscsiTargetHostStats[hostname] ||= {}
        # per host stats
        hostStatsNodes = ['vit.vitdRestartCount']
        hostStatsNodes.each do |param|
          @vsanIscsiTargetHostStats[hostname][param] ||= {}
          (host[param] || {}).map do |p, pv|
            @vsanIscsiTargetHostStats[hostname][param][p] ||= InventoryStat.new
            @vsanIscsiTargetHostStats[hostname][param][p].add(ts, pv)
          end
        end

        # must match target stats VSI node
        targetStats = [
          "numLoginAttempt",
          "numLoginFailure",
        ]

        # per target stats
        (host['vit.targetStats'] || {}).map do |targetAlias, targetStats|
          if targetStats.instance_of?(Hash)
            @vsanIscsiTargetTargetStats[targetAlias] ||= {}
            targetStats.each do |p, pv|
              if targetStats.include?(p)
                @vsanIscsiTargetTargetStats[targetAlias][p] ||= InventoryStat.new
                @vsanIscsiTargetTargetStats[targetAlias][p].add(ts, pv)
              end
            end
          end
        end

        # must match LUN stats VSI node
        lunStatsNodes = {
          "prstats" => [
            "isReserved",
            "numActiveRegistrants",
          ],
        }

        # per LUN stats
        (host['vit.lunStats'] || {}).map do |targetAlias, targetLuns|
          if targetLuns.instance_of?(Hash)
            @vsanIscsiTargetLunStats[targetAlias] ||= {}
            targetLuns.map do |lunId, lunStatsGroups|
              if lunStatsGroups.instance_of?(Hash)
                @vsanIscsiTargetLunStats[targetAlias][lunId] ||= {}
                lunStatsGroups.map do |lunStatsGroup, lunStats|
                  if lunStatsNodes.has_key?(lunStatsGroup) and lunStats.instance_of?(Hash)
                    @vsanIscsiTargetLunStats[targetAlias][lunId][lunStatsGroup] ||= {}
                    lunStats.each do |p, pv|
                      if lunStatsNodes[lunStatsGroup].include?(p)
                        @vsanIscsiTargetLunStats[targetAlias][lunId][lunStatsGroup][p] ||= InventoryStat.new
                        @vsanIscsiTargetLunStats[targetAlias][lunId][lunStatsGroup][p].add(ts, pv)
                      end
                    end
                  end
                end
              end
            end
          end
        end
      end

      if host['dom.owners.stats-taken']
        domTs = host['dom.owners.stats-taken']
        uuids = Hash[(host['dom.owners.stats'] || {}).map do |k,v|
          [k, [domTs, v]]
        end]

        @counts[hostname]['dom.owners'].add(domTs, uuids.keys.length)
      end

      if host['dom.owner.stats']
        uuids["total-#{hostname}"] = [
          host['dom.owner.stats-taken'] || domTs,
          host['dom.owner.stats']
        ]
      end
      if host['dom.client.stats']
        uuids["client-#{hostname}"] = [
          host['dom.client.stats-taken'] || domTs,
          host['dom.client.stats']
        ]
      end
      clientUuids = {}
      if host['dom.clients']
        domClientTs = host['dom.client.stats-taken']
        clientUuids = host['dom.clients']
        @counts[hostname]['dom.clients'].add(domClientTs,
                                             clientUuids.keys.length)
      end

      if host['dom.owner.stats'] && host['dom.clients']
        domClientTs = host['dom.client.stats-taken']
        colocatedUuids = [uuids.keys, clientUuids.keys].inject(&:&)
        @counts[hostname]['dom.colocated'].add(domClientTs,
                                               colocatedUuids.length)
      end
      if host['dom.compmgr.stats']
        uuids["compmgr-#{hostname}"] = [
          host['dom.compmgr.stats-taken'] || domTs,
          host['dom.compmgr.stats']
        ]
      end
      uuids.each do |uuid, domInfo|
        domTs, stats = domInfo
        if uuid !~ /(total|client|compmgr)/
          uuid = _normalize_uuid uuid.to_s
        end

        key = @v3DomStats.registerKey(
          {:uuid => uuid}
        ) do
          {
            'group' => "dom",
            'file' => "domobj-#{uuid}",
            'statsInfo' =>
              ['read', 'write', 'recoveryWrite'].map do |ioType|
                {
                  "#{ioType}Count" => ['avgs', 1, 'round'],
                  "#{ioType}Bytes" => ['avgs', 1 / 1024.0, 'round'],
                  "#{ioType}Latency" => ['avgs', 1 / 1000.0, 'round'],
                  "#{ioType}LatencySq" => ['avgs', 1 / 1000.0, 'round'],
                  "#{ioType}Congestion" => ['avgs', 1, 'round'],
                }
              end.inject({}, :merge),
            'thumbSpecs' => [
              {
                'label' => 'IOPS',
                'key' => 'iops',
                'fields' => ['readCount', 'writeCount'],
                'fieldLabels' => ['Read IOPS', 'Write IOPS'],
                'max' => nil,
                'threshold' => 'XXX'
              },
              {
                'label' => 'Tput KB/s',
                'key' => 'tput',
                'fields' => ['readBytes', 'writeBytes'],
                'fieldLabels' => ['Read KB/s', 'Write KB/s'],
                'max' => nil,
                'threshold' => 'XXX'
              },
              {
                'label' => 'Latency ms',
                'key' => 'latency',
                'fields' => ['readLatency', 'writeLatency'],
                'fieldLabels' => ['Read Latency', 'Write Latency'],
                'max' => nil,
                'threshold' => 'XXX'
              }
            ]
          }
        end
        statsObj = @v3DomStats.get(key)
        ['read', 'write', 'recoveryWrite'].each do |ioType|
          statsObj["#{ioType}Count"] ||=
            InventoryStat.new(['times', 'avgs'])
          statsObj["#{ioType}Bytes"] ||=
            InventoryStat.new(['times', 'avgs'])
          statsObj["#{ioType}Latency"] ||=
            InventoryStat.new(['times', 'avgs'])
          statsObj["#{ioType}LatencySq"] ||=
            InventoryStat.new(['times', 'avgs'])
          statsObj["#{ioType}Congestion"] ||=
            InventoryStat.new(['times', 'avgs'])

          statsObj["#{ioType}Count"].add(domTs,
            stats["#{ioType}Count"])
          statsObj["#{ioType}Congestion"].add(domTs,
            stats["#{ioType}CongestionSum"],
            statsObj["#{ioType}Count"].lastvalue)
          statsObj["#{ioType}Bytes"].add(domTs,
            stats["#{ioType}Bytes"])
          statsObj["#{ioType}Latency"].add(domTs,
            stats["#{ioType}LatencySumUs"],
            statsObj["#{ioType}Count"].lastvalue)
          statsObj["#{ioType}LatencySq"].add(domTs,
            stats["#{ioType}LatencySqSumUs"],
            statsObj["#{ioType}Count"].lastvalue)
        end

        statsObj["totalCount"] ||=
          InventoryStat.new
        statsObj["numOIO"] ||=
          InventoryStat.new
        statsObj["totalCount"].add(domTs,
          stats["ioCount"])
        statsObj["numOIO"].add(domTs,
          stats["numOIOSum"],
          statsObj["totalCount"].lastvalue)

        statsObj["domClientCacheHits"] ||=
          InventoryStat.new
        statsObj["domClientCacheLookups"] ||=
          InventoryStat.new
        statsObj["domClientCacheHitRate"] ||=
          InventoryStat.new
        cacheHitRate = 0
        if host['dom.client.cachestats']
          # check cache stats if cache is enabled
          prevLookups = statsObj["domClientCacheLookups"].lastvalue != nil ? statsObj["domClientCacheLookups"].lastvalue : 0
          prevHits = statsObj["domClientCacheHits"].lastvalue != nil ? statsObj["domClientCacheHits"].lastvalue : 0
          if host['dom.client.cachestats']['lookups'] == prevLookups
            cacheHitRate = 0
          else
            cacheHitRate = 100 * (host['dom.client.cachestats']['hits'] - prevHits) / (host['dom.client.cachestats']['lookups'] - prevLookups)
          end
          statsObj["domClientCacheLookups"].addStatic(domTs, host['dom.client.cachestats']['lookups'])
          statsObj["domClientCacheHits"].addStatic(domTs, host['dom.client.cachestats']['hits'])
        end
        statsObj["domClientCacheHitRate"].addStatic(domTs, cacheHitRate)
      end


      lsomTs = host['lsom.disks-taken']
      if lsomTs
      (host['lsom.disks'] || {}).each do |uuid, stats|
        #pp stats
        info = stats['info']
        device = [hostname, uuid]
        if info && info['type'] == 'cache'
          key = @ssds.registerKey(
            {:hostname => hostname, :uuid => uuid}
          ) do
            {
              'group' => "lsom",
              'file' => "ssd-#{uuid}",
              'statsInfo' => {
                "wbFillPct" => ['avgs', 1, 'round'],
                "llogLogSpace" => ['avgs', 1, 'round'],
                "llogDataSpace" => ['avgs', 1, 'round'],
                "plogLogSpace" => ['avgs', 1, 'round'],
                "plogDataSpace" => ['avgs', 1, 'round'],
              },
              'thumbSpecs' => [
                {
                  'label' => 'WB Fill (pct)',
                  'key' => 'wbfill',
                  'fields' => ['wbFillPct'],
                  'fieldLabels' => ['WriteBuffer Fill pct'],
                  'max' => 100,
                  'threshold' => 'XXX'
                },
              ]
            }
          end
          statsObj = @ssds.get(key)
          freePct = info['wbFreeSpace'].to_f * 100.0 / info['wbSize']
          statsObj['wbFillPct'] ||= InventoryStat.new
          statsObj['llogLogSpace'] ||= InventoryStat.new
          statsObj['llogDataSpace'] ||= InventoryStat.new
          statsObj['plogLogSpace'] ||= InventoryStat.new
          statsObj['plogDataSpace'] ||= InventoryStat.new

          statsObj['wbFillPct'].addStatic(lsomTs,
            100 - (freePct.to_i))
          statsObj['llogLogSpace'].addStatic(lsomTs,
            info['llogLogSpace'].to_f * 100.0 / info['wbSize'])
          statsObj['llogDataSpace'].addStatic(lsomTs,
            info['llogDataSpace'].to_f * 100.0 / info['wbSize'])
          statsObj['plogLogSpace'].addStatic(lsomTs,
            info['plogLogSpace'].to_f * 100.0 / info['wbSize'])
          statsObj['plogDataSpace'].addStatic(lsomTs,
            info['plogDataSpace'].to_f * 100.0 / info['wbSize'])
        end

        vs = stats['virstoStats']
        if vs && info && info['type'] == 'data'
           @virstoStats[device] ||= {}
           @virstoStats[device]['mbcHits'] ||= InventoryStat.new
           @virstoStats[device]['mbcEvictions'] ||= InventoryStat.new
           @virstoStats[device]['mbcMisses'] ||= InventoryStat.new
           @virstoStats[device]['mbFree'] ||= InventoryStat.new
           @virstoStats[device]['mbDirty'] ||= InventoryStat.new
           @virstoStats[device]['mbValid'] ||= InventoryStat.new
           @virstoStats[device]['mbInvalid'] ||= InventoryStat.new
           @virstoStats[device]['mfRuns'] ||= InventoryStat.new
           @virstoStats[device]['heapUtilization'] ||= InventoryStat.new
           @virstoStats[device]['mfMetadataPerSec'] ||= InventoryStat.new
           @virstoStats[device]['mfMetadataPerRun'] ||= InventoryStat.new
           @virstoStats[device]['mfPendingMetadata'] ||= InventoryStat.new

           @virstoStats[device]['mbcHits'].add(lsomTs, vs['mbcHits'])
           @virstoStats[device]['mbcEvictions'].add(lsomTs, vs['mbcEvictions'])
           @virstoStats[device]['mbcMisses'].add(lsomTs, vs['mbcMisses'])

           @virstoStats[device]['mbFree'].addStatic(lsomTs, vs['mbFree'])
           @virstoStats[device]['mbDirty'].addStatic(lsomTs, vs['mbDirty'])
           @virstoStats[device]['mbValid'].addStatic(lsomTs, vs['mbValid'])
           @virstoStats[device]['mbInvalid'].addStatic(lsomTs, vs['mbInvalid'])

           @virstoStats[device]['mfRuns'].add(lsomTs, vs['mfRuns'])
           @virstoStats[device]['heapUtilization'].addStatic(lsomTs, vs['heapUtilization'] / 1024)
           @virstoStats[device]['mfMetadataPerSec'].add(lsomTs, vs['mfTotalMetadata'] / 1024)
           @virstoStats[device]['mfPendingMetadata'].addStatic(lsomTs, vs['mfPendingMetadata'] / 1024)

           if @virstoStats[device]['mfRuns'].lastvalue == 0
            @virstoStats[device]['mfMetadataPerRun'].addStatic(lsomTs, 0)
           else
            @virstoStats[device]['mfMetadataPerRun'].addStatic(lsomTs, 1.0 * @virstoStats[device]['mfMetadataPerSec'].lastvalue / @virstoStats[device]['mfRuns'].lastvalue)
           end
        end

        cfs = stats['CFStats']
        if cfs && info && info['type'] == 'data'
           @CFStats[device] ||= {}
           @CFStats[device]['componentsToFlush'] ||= InventoryStat.new
           @CFStats[device]['extentsProcessed'] ||= InventoryStat.new
           @CFStats[device]['extentsSizeProcessed'] ||= InventoryStat.new
           @CFStats[device]['extentsPerSec'] ||= InventoryStat.new
           @CFStats[device]['extentsPerRun'] ||= InventoryStat.new

           @CFStats[device]['componentsToFlush'].addStatic(lsomTs, cfs['componentsToFlush'])
           @CFStats[device]['extentsProcessed'].addStatic(lsomTs, cfs['extentsProcessed'])
           if cfs['numVirstoBarriers'] || cfs['numVirstoBarriers'] == 0
             @CFStats[device]['extentsSizeProcessed'].addStatic(lsomTs, 0)
           else
             @CFStats[device]['extentsSizeProcessed'].addStatic(lsomTs, 1.0 * cfs['totalExtentSizeProcessed'] / (cfs['numVirstoBarriers'] * 1024))
           end
           @CFStats[device]['extentsPerSec'].add(lsomTs, cfs['totalExtentsProcessed'])

           if @virstoStats[device]['mfRuns'].lastvalue == 0
            @CFStats[device]['extentsPerRun'].addStatic(lsomTs, 0)
           else
            @CFStats[device]['extentsPerRun'].addStatic(lsomTs, 1.0 * @CFStats[device]['extentsPerSec'].lastvalue / @virstoStats[device]['mfRuns'].lastvalue)
           end
        end

        if info && info['type'] == 'cache'
          key = @lsomCongestion.registerKey(
            {:hostname => hostname, :dev => uuid}
          ) do
            {
              'group' => "lsom",
              'file' => "cong-#{hostname}-#{uuid}",
              'statsInfo' => {
                'memCongestion' => ['total', 1, 'round'],
                'slabCongestion' => ['total', 1, 'round'],
                'ssdCongestion' => ['total', 1, 'round'],
                'iopsCongestion' => ['total', 1, 'round'],
                'logCongestion' => ['total', 1, 'round'],
                'compCongestion' => ['total', 1, 'round'],
              },
              'thumbSpecs' => [
                {
                  'label' => 'Congestion',
                  'key' => 'congestion',
                  'fields' => [
                    'memCongestion', 'slabCongestion', 'ssdCongestion',
                    'iopsCongestion', 'logCongestion', 'compCongestion'
                  ],
                  'fieldLabels' => [
                    'memCongestion', 'slabCongestion', 'ssdCongestion',
                    'iopsCongestion', 'logCongestion', 'compCongestion'
                  ],
                  'max' => 255,
                  'threshold' => 'XXX'
                },
              ]
            }
          end
          statsObj = @lsomCongestion.get(key)
          [
            'memCongestion', 'slabCongestion', 'ssdCongestion',
            'iopsCongestion', 'logCongestion', 'compCongestion'
          ].each do |type|
            statsObj[type] ||= InventoryStat.new
            statsObj[type].addStatic(lsomTs, info[type])
          end
        end

        begin
          info = stats
          if !info['info'] || info['info']['type'] != 'cache'
            next
          end
          @diskStats[device] ||= {}
          [
            [:rcRead, stats['rcReadQStats']['rcIOStats']],
            [:rcWrite, stats['rcWriteQStats']['rcIOStats']],
            [:wbRead, stats['WBQStats']['wbReadIOStats']],
            [:wbWrite, stats['WBQStats']['wbWriteIOStats']],
          ].each do |type, values|
            @diskStats[device]["#{type}IOs".to_sym] ||=
              InventoryStat.new
            @diskStats[device]["#{type}QLatency".to_sym] ||=
              InventoryStat.new
            @diskStats[device]["#{type}TLatency".to_sym] ||=
              InventoryStat.new

            @diskStats[device]["#{type}IOs".to_sym].add(lsomTs,
              values['nrIOs'])
            @diskStats[device]["#{type}QLatency".to_sym].add(lsomTs,
              values['totalQTime'],
              @diskStats[device]["#{type}IOs".to_sym].lastvalue)
            @diskStats[device]["#{type}TLatency".to_sym].add(lsomTs,
              values['totalLatency'],
              @diskStats[device]["#{type}IOs".to_sym].lastvalue)
          end
        rescue
          raise
        end
      end
      end

      plogTs = host['plog.devices-taken']
      if plogTs
      (host['plog.devices'] || {}).each do |dev, info|
        begin
          if !info || !info['stats'] || !info['stats']['stats'] ||
                      !info['elevStats'] || !info['info']
            next
          end
          stats = info['stats']['stats']
          oobstats = info['stats']['oobStats']
          elevStats = info['elevStats']
          device = [hostname, info['info']['deviceUUID'], info['info']]
          @plogDeviceInfo[info['info']['deviceUUID']] = info['info']
          @plogStats[device] ||= {}
          @plogStats[device][:writeIOs] ||= InventoryStat.new
          @plogStats[device][:writeQLatency] ||= InventoryStat.new
          @plogStats[device][:writeTLatency] ||= InventoryStat.new
          @plogStats[device][:readIOs] ||= InventoryStat.new
          @plogStats[device][:readQLatency] ||= InventoryStat.new
          @plogStats[device][:readTLatency] ||= InventoryStat.new
          @plogStats[device][:capacityUsed] ||= InventoryStat.new
          @plogStats[device][:totalBytesDrained] ||= InventoryStat.new
          @plogStats[device][:ssdBytesDrained] ||= InventoryStat.new
          @plogStats[device][:zeroBytesDrained] ||= InventoryStat.new
          @plogStats[device][:numElevSSDReads] ||= InventoryStat.new
          @plogStats[device][:numMDWrites] ||= InventoryStat.new
          @plogStats[device][:totalBytesRead] ||= InventoryStat.new
          @plogStats[device][:totalBytesReadFromMD] ||= InventoryStat.new
          @plogStats[device][:totalBytesReadFromSSD] ||= InventoryStat.new
          @plogStats[device][:totalBytesReadByRC] ||= InventoryStat.new
          @plogStats[device][:totalBytesReadByVMFS] ||= InventoryStat.new
          @plogStats[device][:numReads] ||= InventoryStat.new
          @plogStats[device][:numRCReads] ||= InventoryStat.new
          @plogStats[device][:numVMFSReads] ||= InventoryStat.new
          @plogStats[device][:numMDReads] ||= InventoryStat.new
          @plogStats[device][:numSSDReads] ||= InventoryStat.new
          @plogStats[device][:plogNumCommitLogs] ||= InventoryStat.new
          @plogStats[device][:plogNumWriteLogs] ||= InventoryStat.new
          @plogStats[device][:plogNumFreedCommitLogs] ||= InventoryStat.new
          @plogStats[device][:plogNumFreedWriteLogs] ||= InventoryStat.new
          @plogStats[device][:plogMDDataUsage] ||= InventoryStat.new
          @plogStats[device][:plogDataUsage] ||= InventoryStat.new
          @plogStats[device][:numCFWrites] ||= InventoryStat.new
          @plogStats[device][:cfWriteBytes] ||= InventoryStat.new
          @plogStats[device][:elevRuns] ||= InventoryStat.new
          @plogStats[device][:numCFLogs] ||= InventoryStat.new
          @plogStats[device][:numFSLogs] ||= InventoryStat.new
          @plogStats[device][:totalCFBytes] ||= InventoryStat.new
          @plogStats[device][:totalFSBytes] ||= InventoryStat.new

          @physDisk2uuid ||= {}
          @physDisk2dg ||= {}
          @physDiskIsSsd ||= {}
          devName = hostname, dev
          @physDisk2uuid[devName] = info['info']['deviceUUID']
          @physDisk2dg[devName] = info['info']['mappedUUID']
          @physDiskIsSsd[devName] = info['info']['isSSD']

          if not @hostElevStats[hostname]
            @hostElevStats[hostname] ||= {}
          end
          @hostElevStats[hostname][dev] ||= {}
          @hostElevStats[hostname][dev][:ssdWriteRate] ||= InventoryStat.new
          @hostElevStats[hostname][dev][:mdDrainRate] ||= InventoryStat.new
          writeStats = stats['writeIOStats']
          readStats = stats['readIOStats']
          writeOOBStats = oobstats['writeIOStats']
          readOOBStats = oobstats['readIOStats']

          if info['info']['isSSD'] != 1
            writeStats['totalQTime'] ||= 0
            writeStats['totalQTime'] +=
              (writeStats['totalQTimeOrdered'] || 0) +
              (writeStats['totalQTimeUnOrdered'] || 0)
            readStats['totalQTime'] ||= 0
            readStats['totalQTime'] +=
              (readStats['totalQTimeOrdered'] || 0) +
              (readStats['totalQTimeUnOrdered'] || 0)
          end

          @plogStats[device][:writeIOs].add(plogTs,
            (writeStats['nrIOs'] + writeOOBStats['nrIOs']))
          @plogStats[device][:writeQLatency].add(plogTs,
            writeStats['totalQTime'],
            @plogStats[device][:writeIOs].lastvalue)
          @plogStats[device][:writeTLatency].add(plogTs,
            writeStats['totalLatency'],
            @plogStats[device][:writeIOs].lastvalue)

          @plogStats[device][:readIOs].add(plogTs,  readStats['nrIOs'])
          @plogStats[device][:readQLatency].add(plogTs,
            readStats['totalQTime'],
            @plogStats[device][:readIOs].lastvalue)
          @plogStats[device][:readTLatency].add(plogTs,
            readStats['totalLatency'],
            @plogStats[device][:readIOs].lastvalue)

          addArray = ['totalBytesDrained','ssdBytesDrained',
                      'zeroBytesDrained','numElevSSDReads',
                      'numMDWrites','totalBytesRead',
                      'totalBytesReadFromMD','totalBytesReadFromSSD',
                      'totalBytesReadByRC','totalBytesReadByVMFS',
                      'numSSDReads','numMDReads',
                      'numReads','numRCReads','numVMFSReads']

          addArray.each do |stat|
             @plogStats[device][stat.to_sym].add(plogTs,
                                                 elevStats[stat])
          end

          addStaticArray = ['numCFLogs','numFSLogs',
                            'totalFSBytes','totalCFBytes',
                            'plogNumCommitLogs','plogNumWriteLogs',
                            'plogNumFreedCommitLogs',
                            'plogNumFreedWriteLogs',
                            'plogMDDataUsage','plogDataUsage',
                            'numCFWrites', 'elevRuns']

          addStaticArray.each do |stat|
             @plogStats[device][stat.to_sym].addStatic(plogTs,
                                                       elevStats[stat])
          end


          (host['lsom.disks'] || {}).each do |uuid, stats|
            diskInfo = stats['info']
            if diskInfo && uuid == info['info']['deviceUUID']
              @plogStats[device][:capacityUsed].addStatic(plogTs,
                 diskInfo['capacityUsed'].to_f * 100.0 / diskInfo['capacity'].to_f)
            end
          end

          @hostElevStats[hostname][dev][:ssdWriteRate].times << plogTs
          @hostElevStats[hostname][dev][:ssdWriteRate].values[plogTs] =
              elevStats['b1FillRate']
          @hostElevStats[hostname][dev][:mdDrainRate].times << plogTs
          @hostElevStats[hostname][dev][:mdDrainRate].values[plogTs] = elevStats['b0DrainRate']
        rescue
          raise
        end
      end
      end

      diskTs = host['disks-taken']
      if host['disks.stats'] && diskTs
        (host['disks.stats'] || {}).each do |_device, info|
          begin
            dev = _device
            device = hostname, _device
            uuid = @physDisk2uuid[device]
            diskGroup = @physDisk2dg[device]
            key = @physDiskStats.registerKey(
              {
                :hostname => hostname,
                :dev => dev,
                :uuid => uuid,
                :diskgroup => diskGroup,
                :isSsd => @physDiskIsSsd[device]
              }
            ) do
              {
                'group' => "lsom",
                'file' => "physdisk-#{hostname}-#{Digest::MD5.hexdigest(dev)}",
                'statsInfo' =>
                  {
                    "readIOs" => ['avgs', 1, 'round'],
                    "writeIOs" => ['avgs', 1, 'round'],
                    "read" => ['avgs', 1 / 2.0, 'round'], # measured in blocks
                    "write" => ['avgs', 1 / 2.0, 'round'],
                    "readLatency" => ['avgs', 1 / 1000.0, 'round'],
                    "writeLatency" => ['avgs', 1 / 1000.0, 'round'],
                    "dAvgLatency" => ['avgs', 1 / 1000.0, 'round'],
                    "gAvgLatency" => ['avgs', 1 / 1000.0, 'round'],
                    "kAvgLatency" => ['avgs', 1 / 1000.0, 'round'],
                  },
                'thumbSpecs' => [
                  {
                    'label' => 'IOPS',
                    'key' => 'iops',
                    'fields' => ['readIOs', 'writeIOs'],
                    'fieldLabels' => ['Read IOPS', 'Write IOPS'],
                    'max' => nil,
                    'threshold' => 'XXX'
                  },
                  {
                    'label' => 'Tput KB/s',
                    'key' => 'tput',
                    'fields' => ['read', 'write'],
                    'fieldLabels' => ['Read KB/s', 'Write KB/s'],
                    'max' => nil,
                    'threshold' => 'XXX'
                  },
                  {
                    'label' => 'Latency ms',
                    'key' => 'latency',
                    'fields' => ['readLatency', 'writeLatency'],
                    'fieldLabels' => ['Read Latency', 'Write Latency'],
                    'max' => nil,
                    'threshold' => 'XXX'
                  }
                ]
              }
            end
            statsObj = @physDiskStats.get(key)

            statsObj['readIOs'] ||= InventoryStat.new
            statsObj['writeIOs'] ||= InventoryStat.new
            statsObj['dAvgLatency'] ||= InventoryStat.new
            statsObj['gAvgLatency'] ||= InventoryStat.new
            statsObj['kAvgLatency'] ||= InventoryStat.new
            statsObj['readLatency'] ||= InventoryStat.new
            statsObj['writeLatency'] ||= InventoryStat.new
            statsObj['read'] ||= InventoryStat.new
            statsObj['write'] ||= InventoryStat.new

            statsObj['readIOs'].add(diskTs, info['readOps'])
            statsObj['writeIOs'].add(diskTs, info['writeOps'])

            # Commands in the last interval
            rdcmds = statsObj['readIOs'].lastvalue
            wrcmds = statsObj['writeIOs'].lastvalue
            cmds = rdcmds + wrcmds

            dAvg = info['latency']['issueTime'] + info['latency']['queueTime']
            dAvg = dAvg - info['latency']['layerTime']
            statsObj['dAvgLatency'].add(diskTs, dAvg, cmds)

            gAvg= info['latency']['totalTime']
            statsObj['gAvgLatency'].add(diskTs, gAvg, cmds)

            kAvg = gAvg - dAvg
            statsObj['kAvgLatency'].add(diskTs, kAvg, cmds)

            statsObj['read'].add(diskTs, info['blocksRead'])
            statsObj['write'].add(diskTs, info['blocksWritten'])

            statsObj['readLatency'].add(diskTs,
                                        info['latency']['totalTimeReads'],
                                        rdcmds)
            statsObj['writeLatency'].add(diskTs,
                                         info['latency']['totalTimeWrites'],
                                         wrcmds)
          rescue
            raise
          end
        end
      end


      lsomTs = host['lsom.disks-taken']
      key = @lsomHostStats.registerKey(
        {:hostname => hostname}
      ) do
        {
          'group' => "lsom",
          'file' => "lsomhost-#{hostname}",
          'statsInfo' =>
            ['read', 'payload', 'writeLe'].map do |ioType|
              {
                "#{ioType}IOs" => ['avgs', 1, 'round'],
                "#{ioType}Bytes" => ['avgs', 1 / 1024.0, 'round'],
                "#{ioType}Latency" => ['avgs', 1 / 1000.0, 'round'],
              }
            end.inject({}, :merge),
          'thumbSpecs' => [
            {
              'label' => 'IOPS',
              'key' => 'iops',
              'fields' => ['readIOs', 'payloadIOs'],
              'fieldLabels' => ['Read IOPS', 'Write IOPS'],
              'max' => nil,
              'threshold' => 'XXX'
            },
            {
              'label' => 'Tput KB/s',
              'key' => 'tput',
              'fields' => ['readBytes', 'payloadBytes'],
              'fieldLabels' => ['Read KB/s', 'Write KB/s'],
              'max' => nil,
              'threshold' => 'XXX'
            },
            {
              'label' => 'Latency ms',
              'key' => 'latency',
              'fields' => ['readLatency', 'payloadLatency', 'writeLeLatency'],
              'fieldLabels' => ['Read Latency', 'Payload Latency', 'WriteLe Latency'],
              'max' => nil,
              'threshold' => 'XXX'
            }
          ]
        }
      end
      lsomHostStatsObj = @lsomHostStats.get(key)
      [
        :readIOs, :readLatency, :readBytes,
        :payloadIOs, :payloadLatency, :payloadBytes,
        :writeLeIOs, :writeLeLatency, :writeLeBytes,
        :rcMemIOs, :rcSsdIOs, :rarReadIOs,
        :avgCapacityUsed, :maxCapacityUsed, :minCapacityUsed,
        :rcMissIOs, :rcPartialMissIOs,
        :warEvictions, :quotaEvictions,
        :rawarIOs, :rawarBytes, :patchedBytes, :wastedPatchedBytes,
        :plogCbSlotNotFound, :plogCbBitNotSet, :plogCbInvalidated,
        :plogCbPatched,
        :rcHitRate
      ].each do |x|
        lsomHostStatsObj[x.to_s] ||= InventoryStat.new
      end
      lsomSumStats = {}
      if lsomTs
        (host['lsom.disks'] || {}).each do |uuid, stats|
          # Only add tier1 disk stats since tier2 data
          # is already aggregated under tier 1 disk stats.
          if stats['info']['type'] != "data"
            allStats = stats['info']['aggStats'] || {}
            if allStats && allStats.values.length > 0
              # wbcfcount not included rar
              [
                :rar, :readIoCount, :rarMem, :rarRCSsd, :readIoTime, :bytesRead,
                :payloadIoTime, :payloadIoCount, :payloadDataBytes,
                :writeLeIoTime, :writeLeIoCount, :writeLeDataBytes,
                :miss, :partialMiss,
                :warEvictions, :quotaEvictions,
                :rawar, :rawarBytes, :patchedBytes, :wastedPatchedBytes,
                :plogCbSlotNotFound, :plogCbBitNotSet, :plogCbInvalidated,
               :plogCbPatched,
              ].each do |key|
                lsomSumStats[key] ||= 0
                if allStats[key.to_s]
                  lsomSumStats[key] += allStats[key.to_s]
                end
              end

              @lsomStats[uuid] ||= Hash[
                [:readIOs, :readLatency, :readBytes,
                 :payloadIOs, :payloadLatency, :payloadBytes,
                 :writeLeIOs, :writeLeLatency, :writeLeBytes,
                 :rcMemIOs, :rcSsdIOs, :rarReadIOs,
                 :rcMissIOs, :rcPartialMissIOs,
                 :warEvictions, :quotaEvictions,
                 :rawarIOs, :rawarBytes, :patchedBytes, :wastedPatchedBytes,
                 :plogCbSlotNotFound, :plogCbBitNotSet, :plogCbInvalidated,
                 :plogCbPatched,
                 ].map do |x|
                  [x, InventoryStat.new(['times', 'avgs'])]
                end
              ]
              @lsomStats[uuid][:readIOs].add(lsomTs,
                allStats['readIoCount'] || 0)
              @lsomStats[uuid][:readLatency].add(lsomTs,
                allStats['readIoTime'] || 0,
                @lsomStats[uuid][:readIOs].lastvalue)
              @lsomStats[uuid][:readBytes].add(lsomTs,
                allStats['bytesRead'] || 0)

              @lsomStats[uuid][:payloadIOs].add(lsomTs,
                allStats['payloadIoCount'] || 0)
              @lsomStats[uuid][:payloadLatency].add(lsomTs,
                allStats['payloadIoTime'] || 0,
                @lsomStats[uuid][:payloadIOs].lastvalue)
              @lsomStats[uuid][:payloadBytes].add(lsomTs,
                allStats['payloadDataBytes'] || 0)

              @lsomStats[uuid][:writeLeIOs].add(lsomTs,
                allStats['writeLeIoCount'] || 0)
              @lsomStats[uuid][:writeLeLatency].add(lsomTs,
                allStats['writeLeIoTime'] || 0,
                @lsomStats[uuid][:writeLeIOs].lastvalue)
              @lsomStats[uuid][:writeLeBytes].add(lsomTs,
                allStats['writeLeDataBytes'] || 0)

              @lsomStats[uuid][:rcMemIOs].add(lsomTs,
                allStats['rarMem'] || 0)
              @lsomStats[uuid][:rcSsdIOs].add(lsomTs,
                allStats['rarRCSsd'] || 0)
              @lsomStats[uuid][:rarReadIOs].add(lsomTs,
                allStats['rar'] || 0)

              @lsomStats[uuid][:rcMissIOs].add(lsomTs,
                allStats['miss'] || 0)
              @lsomStats[uuid][:rcPartialMissIOs].add(lsomTs,
                allStats['partialMiss'] || 0)

              @lsomStats[uuid][:warEvictions].add(lsomTs,
                allStats['warEvictions'] || 0)
              @lsomStats[uuid][:quotaEvictions].add(lsomTs,
                allStats['quotaEvictions'] || 0)

              @lsomStats[uuid][:rawarIOs].add(lsomTs,
                allStats['rawar'] || 0)
              @lsomStats[uuid][:rawarBytes].add(lsomTs,
                allStats['rawarBytes'] || 0)
              @lsomStats[uuid][:patchedBytes].add(lsomTs,
                allStats['patchedBytes'] || 0)
              @lsomStats[uuid][:wastedPatchedBytes].add(lsomTs,
                allStats[':wastedPatchedBytes'] || 0)

              @lsomStats[uuid][:plogCbSlotNotFound].add(lsomTs,
                allStats['plogCbSlotNotFound'] || 0)
              @lsomStats[uuid][:plogCbBitNotSet].add(lsomTs,
                allStats['plogCbBitNotSet'] || 0)
              @lsomStats[uuid][:plogCbInvalidated].add(lsomTs,
                allStats['plogCbInvalidated'] || 0)
              @lsomStats[uuid][:plogCbPatched].add(lsomTs,
                allStats['plogCbPatched'] || 0)
            end
          end
        end

        host['lsom.node'] ||= {}
        host['lsom.node']['numDataComponents'] ||= 0
        host['lsom.node']['numOpenedComponents'] ||= 0
        @counts[hostname]['lsom.iocomponents'].add(lsomTs,
          host['lsom.node']['numDataComponents'])
        @counts[hostname]['lsom.components'].add(lsomTs,
          host['lsom.node']['numOpenedComponents'])

        lsomHostStatsObj['readIOs'].add(lsomTs,
          lsomSumStats[:readIoCount] || 0)
        lsomHostStatsObj['readLatency'].add(lsomTs,
          lsomSumStats[:readIoTime] || 0,
          lsomHostStatsObj['readIOs'].lastvalue)
        lsomHostStatsObj['readBytes'].add(lsomTs,
          lsomSumStats[:bytesRead] || 0)

        lsomHostStatsObj['payloadIOs'].add(lsomTs,
          lsomSumStats[:payloadIoCount] || 0)
        lsomHostStatsObj['payloadLatency'].add(lsomTs,
          lsomSumStats[:payloadIoTime] || 0,
          lsomHostStatsObj['payloadIOs'].lastvalue)
        lsomHostStatsObj['payloadBytes'].add(lsomTs,
          lsomSumStats[:payloadDataBytes] || 0)

        lsomHostStatsObj['writeLeIOs'].add(lsomTs,
          lsomSumStats[:writeLeIoCount] || 0)
        lsomHostStatsObj['writeLeLatency'].add(lsomTs,
          lsomSumStats[:writeLeIoTime] || 0,
          lsomHostStatsObj['writeLeIOs'].lastvalue)
        lsomHostStatsObj['writeLeBytes'].add(lsomTs,
          lsomSumStats[:writeLeDataBytes] || 0)

        lsomHostStatsObj['rcMemIOs'].add(lsomTs,
          lsomSumStats[:rarMem] || 0)
        lsomHostStatsObj['rcSsdIOs'].add(lsomTs,
          lsomSumStats[:rarRCSsd] || 0)
        lsomHostStatsObj['rarReadIOs'].add(lsomTs,
          lsomSumStats[:rar] || 0)

        hitRate = 0
        if lsomSumStats[:rar] && lsomSumStats[:rar] != 0
          hitRate = lsomSumStats[:rar] * 100 / lsomSumStats[:readIoCount]
        end
        lsomHostStatsObj['rcHitRate'].addStatic(lsomTs,
          hitRate)

        lsomHostStatsObj['rcMissIOs'].add(lsomTs,
          lsomSumStats[:miss] || 0)
        lsomHostStatsObj['rcPartialMissIOs'].add(lsomTs,
          lsomSumStats[:partialMiss] || 0)

        lsomHostStatsObj['warEvictions'].add(lsomTs,
          lsomSumStats[:warEvictions] || 0)
        lsomHostStatsObj['quotaEvictions'].add(lsomTs,
          lsomSumStats[:quotaEvictions] || 0)

        lsomHostStatsObj['rawarIOs'].add(lsomTs,
          lsomSumStats[:rawar] || 0)
        lsomHostStatsObj['rawarBytes'].add(lsomTs,
          lsomSumStats[:rawarBytes] || 0)
        lsomHostStatsObj['patchedBytes'].add(lsomTs,
          lsomSumStats[:patchedBytes] || 0)
        lsomHostStatsObj['wastedPatchedBytes'].add(lsomTs,
          lsomSumStats[:wastedPatchedBytes] || 0)

        lsomHostStatsObj['plogCbSlotNotFound'].add(lsomTs,
          lsomSumStats[:plogCbSlotNotFound] || 0)
        lsomHostStatsObj['plogCbBitNotSet'].add(lsomTs,
          lsomSumStats[:plogCbBitNotSet] || 0)
        lsomHostStatsObj['plogCbInvalidated'].add(lsomTs,
          lsomSumStats[:plogCbInvalidated] || 0)
        lsomHostStatsObj['plogCbPatched'].add(lsomTs,
          lsomSumStats[:plogCbPatched] || 0)

        # Host wide disk stats
        maxCapacityUsedPct = 0
        minCapacityUsedPct = 100
        sumCapacityUsed = 0
        sumCapacity = 0
        (host['lsom.disks'] || {}).each do |uuid, stats|
          info = stats['info']
          if info && info['type'] != 'cache'
            sumCapacityUsed += info['capacityUsed']
            sumCapacity += info['capacity']
            usedPct = info['capacityUsed'].to_f * 100.0 / info['capacity'].to_f
            if usedPct > maxCapacityUsedPct
              maxCapacityUsedPct = usedPct
            end
            if usedPct < minCapacityUsedPct
              minCapacityUsedPct = usedPct
            end
          end
        end
        if sumCapacity == 0
          avgCapacityUsedPct = 0
        else
          avgCapacityUsedPct = sumCapacityUsed.to_f * 100.0 / sumCapacity.to_f
        end
        lsomHostStatsObj['avgCapacityUsed'].addStatic(lsomTs,
          avgCapacityUsedPct)
        lsomHostStatsObj['maxCapacityUsed'].addStatic(lsomTs,
          maxCapacityUsedPct)
        lsomHostStatsObj['minCapacityUsed'].addStatic(lsomTs,
          minCapacityUsedPct)
        @counts[hostname]['lsom.diskcapacity'].addStatic(lsomTs,
          avgCapacityUsedPct)
      end

      if host['system.mem']
        # We don't build deltas and average over time delta, so
        # timestamps can be approximate
        ts = host['lsom.disks-taken']
        ts ||= host['worldlets-taken']
        stats = host['system.mem']

        @systemMem[hostname] ||= {}
        @systemMem[hostname]['totalMbMemUsed'] ||= InventoryStat.new
        @systemMem[hostname]['pctMemUsed'] ||= InventoryStat.new
        @systemMem[hostname]['overcommitRatio'] ||= InventoryStat.new

        free = stats['comprehensive']['free']
        total = stats['comprehensive']['kernel']
        @systemMem[hostname]['totalMbMemUsed'].addStatic(ts,
          (total - free) / 1024)
        @systemMem[hostname]['pctMemUsed'].addStatic(ts,
          100 - (free * 100 / total))
        @systemMem[hostname]['overcommitRatio'].addStatic(ts,
          stats['overcommit']['avg1min'])
      end

      vsansparseTs = host['vsansparse-taken']
      ioStats = host['vsansparse.ioStats']
      allocStats = host['vsansparse.allocStats']
      openChains = host['vsansparse.openChains'] || {}
      pathMapping = host['vsansparse.pathlookup'] || {}
      if vsansparseTs.nil? or ioStats.nil? or allocStats.nil? or openChains.nil?
        @vsanSparseWarningCount ||= 0
        if @vsanSparseWarningCount % 30 == 0
          puts "#{Time.now}: Missing vsansparse stats skipping"
        end
        @vsanSparseWarningCount += 1
      else
        @vsansparse[hostname] ||= {}
        processVsansparse(vsansparseTs, @vsansparse[hostname], ioStats, allocStats, false)

        @vsansparseOpenChain[hostname] ||= {}

        openChains.keys.each do |uuid|
          @vsansparseOpenChain[hostname][uuid] ||= {}
          processVsansparse(vsansparseTs, @vsansparseOpenChain[hostname][uuid], openChains[uuid]['iostats'], openChains[uuid]['allocinfo'], true)
        end
        pathMapping.each do |uuid, path|
          if not path.nil?
            @vsansparsePathmap[uuid] = path
          end
        end
      end

      if host['pnics']
        ts = host['pnics-taken']

        @pnics[hostname] ||= {}
        host['pnics'].each do |pnic, stats|
          @pnics[hostname][pnic] ||= {}
          ['rxbytes',
            'rxpkt',
            'rxdrp',
            'rxerror',
            'txbytes',
            'txpkt',
            'txdrp',
            'txerror',].each do |type|
            @pnics[hostname][pnic][type] ||= InventoryStat.new
            @pnics[hostname][pnic][type].add(ts,
              stats['stats'][type])
          end
        end
      end

      if host['tcpip.stats.tcp']
        ts = host['tcpip.stats-taken']
        stats = host['tcpip.stats.tcp']
        @vmknicStats[hostname] ||= {}
        @vmknicStats[hostname]['tcp'] ||= {}
        ['conndrops',
          'rcvackpack',
          'rcvbyte',
          'rcvdupack',
          'rcvduppack',
          'rcvoopack',
          'rcvpack',
          'rcvwinprobe',
          'rcvwinupd',
          'sack_recovery_episode',
          'sndacks',
          'sndbyte',
          'sndpack',
          'sndrexmitpack',
          'sndwinup',].each do |type|
          @vmknicStats[hostname]['tcp'][type] ||= InventoryStat.new
          @vmknicStats[hostname]['tcp'][type].add(ts, stats[type])
        end
      end

      if host['tcpip.stats.ip']
        ts = host['tcpip.stats-taken']
        stats = host['tcpip.stats.ip']
        @vmknicStats[hostname] ||= {}
        @vmknicStats[hostname]['ip'] ||= {}
        ['total',
         'delivered',
         'localout',
         'notmember',].each do |type|
          @vmknicStats[hostname]['ip'][type] ||= InventoryStat.new
          @vmknicStats[hostname]['ip'][type].add(ts, stats[type])
        end
      end

      if host['tcpip.stats.igmp']
        ts = host['tcpip.stats-taken']
        stats = host['tcpip.stats.igmp']
        @vmknicStats[hostname] ||= {}
        @vmknicStats[hostname]['igmp'] ||= {}
        ['rcv_total',
         'rcv_reports',
         'rcv_ourreports',
         'snd_reports',].each do |type|
          @vmknicStats[hostname]['igmp'][type] ||= InventoryStat.new
          @vmknicStats[hostname]['igmp'][type].add(ts, stats[type])
        end
      end

      if host['worldlets-taken']
        wdtTs = host['worldlets-taken']
        (host['worldlets'] || {}).each do |wdt, stats|
          if wdt =~ /(\d+)\.VSAN_0x([\da-f]*)_(.*)/
            if ['Owner', 'Client', 'LSOMLLOG', 'PLOG', 'CompServer'].member?($3)
              wdt = "VSAN_#{$3}#{$1}"
            else
              wdt = "VSAN_#{$3}"
            end
          # match vSAN iSCSI Target worlds
          elsif wdt =~ /(\d+)\.((tq:)?vit.*)/
            wdt = "#{$2}_#{$1}"
            # workaround for world tq:vit-timer-q
            wdt.sub!(/^tq:vit(.*)/, "tq-vit\\1")
          elsif wdt =~ /(\d+)\.(.*)/
            wdt = "#{$2}_#{$1}"
          end
          wdt = [hostname, wdt]
          @worldletStats[wdt] ||= {}

          [:waitTime, :runTime, :overrunTime, :readyTime].each do |key|
            @worldletStats[wdt][key.to_s] ||= InventoryStat.new
            # stats are in ns, but deltaT is in s, so convert stats to seconds
            @worldletStats[wdt][key.to_s].add(wdtTs,
              stats[key.to_s] ? (stats[key.to_s].to_f / 1000**3) : 0)
          end
        end
      end

      if host['worlds.helper-taken']
        whTs = host['worlds.helper-taken']
        (host['worlds.helper'] || {}).each do |helperId, helperInfo|
          helperInfo['worlds'].each do |wid, stats|
            hwid = [hostname, "#{helperId}-#{wid}"]
            @helperWorldStats[hwid] ||= {}
            @helperWorldNames[hwid] = "#{helperId}-#{wid}"
            if helperInfo['info']
              @helperWorldNames[hwid] = "%s-%s" % [
                helperInfo['info']['qName'],
                wid
              ]
            end

            [:waitTime, :runTime, :usedTime, :readyTime].each do |key|
              @helperWorldStats[hwid][key.to_s] ||= InventoryStat.new
              # stats are in us, but deltaT is in s, so convert stats to seconds
              @helperWorldStats[hwid][key.to_s].add(whTs,
                stats[key.to_s] ? (stats[key.to_s].to_f / 1000**2) : 0)
            end
          end
        end
      end
      if host['pcpus-taken']
        pcpuTs = host['pcpus-taken']
        (host['pcpus'] || {}).each do |pcpu, stats|
          pcpu = [hostname, pcpu]
          @pcpuStats[pcpu] ||= {}
          [:wdtTime, :idleTime, :haltTime, :usedTime,
           :busyWaitTime, :coreHaltTime, :elapsedTime].each do |key|
             cur = stats[key.to_s]

             @pcpuStats[pcpu][key.to_s] ||= InventoryStat.new
             @pcpuStats[pcpu][key.to_s].add(pcpuTs,
               stats[key.to_s] || 0)
          end

          @pcpuStats[pcpu][:usedPct] ||= InventoryStat.new
          elapsed = @pcpuStats[pcpu]['elapsedTime'].lastvalue
          coreHalt = @pcpuStats[pcpu]['coreHaltTime'].lastvalue
          usedPct = 0
          if elapsed > 0
            usedPct = 100 - (coreHalt * 100 / elapsed)
          end
          @pcpuStats[pcpu][:usedPct].addStatic(pcpuTs, usedPct)
        end
      end

      ts = host['lsom.disks-taken']
      ts ||= host['worldlets-taken']

      (host['vsanslabs'] || {}).each do |slab, stats|
        info = stats['stats']
        if !info
          next
        end
        @slabs[hostname] ||= {}
        @slabs[hostname][slab] ||= {}
        @slabs[hostname][slab][ts] = {
          :usedObjs => info['allocCount'].to_f * 100.0 / info['maxObjs']
        }
      end

      if host['mem-heap-stats']
        fields = {}
        host['mem-heap-stats'][0].split(",").each_with_index{|x, i| fields[x] = i}
        @heaps[hostname] ||= {}
        host['mem-heap-stats'][1..-1].each do |heap|
          heap = heap.split(",")
          heapname = heap[fields['name']]
          @heaps[hostname][heapname] ||= {}
          @heaps[hostname][heapname][ts] = {
            :pctFreeOfMax => 100 - heap[fields['pctFreeOfMax']].to_f,
            :lowPctFreeOfMax => 100 - heap[fields['lowPctFreeOfMax']].to_f,
          }
        end
      end

      @osfsMntLatestHisto[hostname] ||= {}
      @osfsMntLatestHisto[hostname] = host['osfs.mnt']

      @cbrcStats[hostname] ||= {}
      cbrcTs = host['cbrc-taken']
      if cbrcTs && host['cbrc'] && host['cbrc']['dcacheStats']
        stats = host['cbrc']['dcacheStats']
        ['vmReadCount', 'evictCount', 'bufferInvalidations',
         'digestNotFoundCount', 'cacheEligibleReadCount',
         'dioReadCount'
        ].each do |type|
          @cbrcStats[hostname][type] ||= InventoryStat.new
          @cbrcStats[hostname][type].add(cbrcTs, stats['counters'][type])
        end
      end

      nfsTs = host['nfsclient-taken']
      if nfsTs && host['nfsclient']
        host['nfsclient'].each do |mnt, mntStats|
          key = @nfsStats.registerKey(
            {:hostname => hostname, :mnt => mnt}
          ) do
            {
              'group' => "nfs",
              'file' => "nfsmnt-#{hostname}-#{mnt.gsub('-', '')}",
              'statsInfo' => {
                'reads' => ['avgs', 1, 'round'],
                'writes' => ['avgs', 1, 'round'],
                'readBytes' => ['avgs', 1 / 1024.0, 'round'],
                'writeBytes' => ['avgs', 1 / 1024.0, 'round'],
                'readTime' => ['avgs', 1 / 1000.0, 'round'], # us -> ms
                'writeTime' => ['avgs', 1 / 1000.0, 'round'], # us -> ms
              },
              'thumbSpecs' => [
                {
                  'label' => 'IOPS',
                  'key' => 'iops',
                  'fields' => ['reads', 'writes'],
                  'fieldLabels' => ['Read IOPS', 'Write IOPS'],
                  'max' => nil,
                  'threshold' => 'XXX'
                },
                {
                  'label' => 'Tput KB/s',
                  'key' => 'tput',
                  'fields' => ['readBytes', 'writeBytes'],
                  'fieldLabels' => ['Read KB/s', 'Write KB/s'],
                  'max' => nil,
                  'threshold' => 'XXX'
                },
                {
                  'label' => 'Latency ms',
                  'key' => 'latency',
                  'fields' => ['readTime', 'writeTime'],
                  'fieldLabels' => ['Read Latency', 'Write Latency'],
                  'max' => nil,
                  'threshold' => 'XXX'
                }
              ]
            }
          end
          statsObj = @nfsStats.get(key)
          [
            'reads', 'readBytes',
            'writes', 'writeBytes',
          ].each do |type|
            statsObj[type] ||= InventoryStat.new
            statsObj[type].add(nfsTs, mntStats[type])
          end
          ['IssueTime', 'Time'].each do |timeType|
            ['read', 'write'].each do |ioType|
              typeKey = "#{ioType}#{timeType}"
              statsObj[typeKey] ||= InventoryStat.new
              statsObj[typeKey].add(nfsTs,
                mntStats[typeKey],
                statsObj["#{ioType}s"].lastvalue)
            end
          end
        end
      end

      if host['vm.vscsi']
        hostSum = {}
        ['numReads', 'numWrites',
         'bytesRead', 'bytesWrite',
         'latencyReads', 'latencyWrites'
        ].each do |type|
          hostSum[type] = 0
        end

        host['vm.vscsi'].values.each do |vmInfo|
          vscsiTs = vmInfo['taken']
          vm = vmInfo['vmmGroupInfo']['displayName']
          vmInfo['vscsi'].each do |disk, _stats|
            stats = _stats['ioStats']
            dev = [vm, disk]
            @vscsiStats[dev] ||= {}

            ['numReads', 'numWrites',
             'bytesRead', 'bytesWrite',
             'latencyReads', 'latencyWrites'
            ].each do |type|
              @vscsiStats[dev][type] ||= InventoryStat.new
              hostSum[type] += stats[type]
            end

            ['numReads', 'numWrites', 'bytesRead', 'bytesWrite'].each do |type|
              @vscsiStats[dev][type].add(vscsiTs, stats[type])
            end

            @vscsiStats[dev]['latencyReads'].add(vscsiTs,
              stats['latencyReads'],
              @vscsiStats[dev]['numReads'].lastvalue)
            @vscsiStats[dev]['latencyWrites'].add(vscsiTs,
              stats['latencyWrites'],
              @vscsiStats[dev]['numWrites'].lastvalue)
          end
        end

        if host['vm.vscsi'].length > 0
          vscsiTs = host['vm.vscsi'].values[0]['taken']
          stats = hostSum

          key = @vscsiHostStats.registerKey(
            {:hostname => hostname}
          ) do
            {
              'group' => "misc",
              'file' => "vscsihost-#{hostname}",
              'statsInfo' => {
                'numReads' => ['avgs', 1, 'round'],
                'numWrites' => ['avgs', 1, 'round'],
                'bytesRead' => ['avgs', 1 / 1024.0, 'round'],
                'bytesWrite' => ['avgs', 1 / 1024.0, 'round'],
                'latencyReads' => ['avgs', 1 / 1000.0, 'round'], # us -> ms
                'latencyWrites' => ['avgs', 1 / 1000.0, 'round'], # us -> ms
              },
              'thumbSpecs' => [
                {
                  'label' => 'IOPS',
                  'key' => 'iops',
                  'fields' => ['numReads', 'numWrites'],
                  'fieldLabels' => ['Read IOPS', 'Write IOPS'],
                  'max' => nil,
                  'threshold' => 'XXX'
                },
                {
                  'label' => 'Tput KB/s',
                  'key' => 'tput',
                  'fields' => ['bytesRead', 'bytesWrite'],
                  'fieldLabels' => ['Read KB/s', 'Write KB/s'],
                  'max' => nil,
                  'threshold' => 'XXX'
                },
                {
                  'label' => 'Latency ms',
                  'key' => 'latency',
                  'fields' => ['latencyReads', 'latencyWrites'],
                  'fieldLabels' => ['Read Latency', 'Write Latency'],
                  'max' => nil,
                  'threshold' => 'XXX'
                }
              ]
            }
          end
          statsObj = @vscsiHostStats.get(key)
          ['numReads', 'numWrites',
           'bytesRead', 'bytesWrite',
           'latencyReads', 'latencyWrites'
          ]. each do |type|
            statsObj[type] ||= InventoryStat.new
          end

          ['numReads', 'numWrites', 'bytesRead', 'bytesWrite'].each do |type|
            statsObj[type].add(vscsiTs, hostSum[type])
          end

          statsObj['latencyReads'].add(vscsiTs,
            hostSum['latencyReads'],
            statsObj['numReads'].lastvalue)
          statsObj['latencyWrites'].add(vscsiTs,
            hostSum['latencyWrites'],
            statsObj['numWrites'].lastvalue)

          @ioAmplification[hostname] ||= {}
          ['numReads', 'numWrites', 'bytesRead', 'bytesWrite'].each do |type|
            @ioAmplification[hostname][type] ||= InventoryStat.new
          end
          {
            'numReads' => 'readCount',
            'numWrites' => 'writeCount',
            'bytesRead' => 'readBytes',
            'bytesWrite' => 'writeBytes',
          }.each do |vscsiType, domType|
            vscsiValue = statsObj[vscsiType].lastvalue
            domUuid = "client-#{hostname}"
            if @v3DomStats
              domStats = @v3DomStats.get([domUuid])
              domValue = nil
              if domStats
                domValue = domStats[domType].lastvalue
              end
              if domValue && domValue != 0 && vscsiValue && vscsiValue != 0
                @ioAmplification[hostname][vscsiType].addStatic(vscsiTs,
                  domValue.to_f / vscsiValue.to_f
                )
              end
            end
          end
        end
      end

      if host['rdt.assocsets']
        rdtTs = host['rdt.assocsets-taken']
        @rdtAssocsetHistos[hostname] ||= {}
        @rdtAssocsetStats[hostname] ||= {}
        host['rdt.assocsets'].each do |endpoint, epStats|
          epStats.each do |assocset, stats|
            key = [endpoint, assocset]
            @rdtAssocsetHistos[hostname][key] ||= {}
            @rdtAssocsetStats[hostname][key] ||= {}
            buckets = stats['stats']['residenceHisto']['buckets']
            resSum = 0
            resCount = 0
            buckets.each do |bucket|
              limit = bucket['limit']
              @rdtAssocsetHistos[hostname][key][limit] ||= InventoryStat.new
              @rdtAssocsetHistos[hostname][key][limit].add(rdtTs,
                bucket['count'], 1)
              resSum += (bucket['count'] * limit)
              resCount += bucket['count']
            end
            @rdtAssocsetStats[hostname][key]['count'] ||= InventoryStat.new
            @rdtAssocsetStats[hostname][key]['count'].add(rdtTs,
              resCount)
            @rdtAssocsetStats[hostname][key]['avgReady'] ||= InventoryStat.new
            @rdtAssocsetStats[hostname][key]['avgReady'].add(rdtTs,
              resSum,
              @rdtAssocsetStats[hostname][key]['count'].lastvalue || 0)
          end
        end
      end
    end
  end

  # Copies over only required inventoryAnalyzer attributes needed for HTML generation.
  # Include only attributes required for HTML generation or for dumping aggregate info.
  def trim inventoryAnalyzer
    @v3DomStats = inventoryAnalyzer.v3DomStats
    @v3DomStats.trim!
    @lsomHostStats = inventoryAnalyzer.lsomHostStats
    @lsomHostStats.trim!
    @physDiskStats = inventoryAnalyzer.physDiskStats
    @physDiskStats.trim!
    @ssds = inventoryAnalyzer.ssds
    @ssds.trim!
    @plogStats = Hash[inventoryAnalyzer.plogStats.keys.map {|x| [x,{}]}]
    @diskStats = Hash[inventoryAnalyzer.diskStats.keys.map {|x| [x,{}]}]
    @virstoStats = Hash[inventoryAnalyzer.virstoStats.keys.map {|x| [x,{}]}]
    @CFStats = Hash[inventoryAnalyzer.CFStats.keys.map {|x| [x,{}]}]
    @vsansparse = inventoryAnalyzer.vsansparse
    @vsansparseOpenChain = inventoryAnalyzer.vsansparseOpenChain
    @plogDeviceInfo = inventoryAnalyzer.plogDeviceInfo
    @cmmdsDisks = inventoryAnalyzer.cmmdsDisks
    @worldletStats = Hash[inventoryAnalyzer.worldletStats.keys.map {|x| [x,{}]}]
    @rdtAssocsetHistos = Hash[inventoryAnalyzer.rdtAssocsetHistos.keys.map do |x|
          [x,Hash[inventoryAnalyzer.rdtAssocsetHistos[x].keys.map {|x| [x,{}]}]]
          end ]

    @slabs = Hash[inventoryAnalyzer.slabs.keys.map {|x| [x,{}]}]
    @heaps = Hash[inventoryAnalyzer.heaps.keys.map {|x| [x,{}]}]
    @cbrcStats = Hash[inventoryAnalyzer.cbrcStats.keys.map do |x|
          [x,Hash[inventoryAnalyzer.cbrcStats[x].keys.map {|x| [x,{}]}]]
          end ]
    @vmInfoHistory = inventoryAnalyzer.vmInfoHistory
    @cmmdsHistory = inventoryAnalyzer.cmmdsHistory
    @vms = inventoryAnalyzer.vms
    @vcInfo = inventoryAnalyzer.vcInfo
    @hostsProps = inventoryAnalyzer.hostsProps
    @counts = inventoryAnalyzer.counts
    @rdtAssocsetStats = inventoryAnalyzer.rdtAssocsetStats

    @vscsiHostStats = inventoryAnalyzer.vscsiHostStats
    @vscsiHostStats.trim!
    @nfsStats = inventoryAnalyzer.nfsStats
    @nfsStats.trim!
    @lsomCongestion = inventoryAnalyzer.lsomCongestion
    @lsomCongestion.trim!
    @vsansparseHosts = inventoryAnalyzer.vsansparseHosts
    @vsansparseList = inventoryAnalyzer.vsansparseList
    @vsansparsePathmap = inventoryAnalyzer.vsansparsePathmap
    @fitnessStats = Hash[inventoryAnalyzer.fitnessStats.keys.map do |x|
          [x, Hash[inventoryAnalyzer.fitnessStats[x].keys.map {|x| [x, {}]}]]
          end ]
    @cmmdsStats = inventoryAnalyzer.cmmdsStats
    @vsanIscsiTargetList= inventoryAnalyzer.vsanIscsiTargetList
    @vsanIscsiTargetHostStats= inventoryAnalyzer.vsanIscsiTargetHostStats
    @vsanIscsiTargetTargetStats= inventoryAnalyzer.vsanIscsiTargetTargetStats
    @vsanIscsiTargetLunStats= inventoryAnalyzer.vsanIscsiTargetLunStats
  end

  # Merge required attributes needed for HTML generation
  # Include only attributes required for HTML generation or for dumping aggregate info.
  def merge! inventoryAnalyzer
    @v3DomStats.merge! inventoryAnalyzer.v3DomStats
    @lsomHostStats.merge! inventoryAnalyzer.lsomHostStats
    @plogStats.merge! inventoryAnalyzer.plogStats
    @ssds.merge! inventoryAnalyzer.ssds
    @diskStats.merge! inventoryAnalyzer.diskStats
    @virstoStats.merge! inventoryAnalyzer.virstoStats
    @CFStats.merge! inventoryAnalyzer.CFStats
    @vsansparse.merge! inventoryAnalyzer.vsansparse
    @vsansparseOpenChain.merge! inventoryAnalyzer.vsansparseOpenChain
    @plogDeviceInfo.merge! inventoryAnalyzer.plogDeviceInfo
    @cmmdsDisks.merge! inventoryAnalyzer.cmmdsDisks
    @physDiskStats.merge! inventoryAnalyzer.physDiskStats
    @worldletStats.merge! inventoryAnalyzer.worldletStats
    @rdtAssocsetHistos.merge! inventoryAnalyzer.rdtAssocsetHistos
    @slabs.merge! inventoryAnalyzer.slabs
    @heaps.merge! inventoryAnalyzer.heaps
    @cbrcStats.merge! inventoryAnalyzer.cbrcStats
    @vmInfoHistory.merge! inventoryAnalyzer.vmInfoHistory
    @cmmdsHistory.merge! inventoryAnalyzer.cmmdsHistory
    @vcInfo.merge! inventoryAnalyzer.vcInfo
    @hostsProps.merge! inventoryAnalyzer.hostsProps
    @vms.merge! inventoryAnalyzer.vms
    @rdtAssocsetStats.merge! inventoryAnalyzer.rdtAssocsetStats
    @counts.merge! inventoryAnalyzer.counts

    @vscsiHostStats.merge! inventoryAnalyzer.vscsiHostStats
    @nfsStats.merge! inventoryAnalyzer.nfsStats
    @lsomCongestion.merge! inventoryAnalyzer.lsomCongestion
    @vsansparseList.merge! inventoryAnalyzer.vsansparseList
    @vsansparseHosts.merge! inventoryAnalyzer.vsansparseHosts
    @vsansparsePathmap.merge! inventoryAnalyzer.vsansparsePathmap
    @fitnessStats.merge! inventoryAnalyzer.fitnessStats
    @cmmdsStats.merge! inventoryAnalyzer.cmmdsStats
    @vsanIscsiTargetList.merge! inventoryAnalyzer.vsanIscsiTargetList
    @vsanIscsiTargetHostStats.merge! inventoryAnalyzer.vsanIscsiTargetHostStats
    @vsanIscsiTargetTargetStats.merge! inventoryAnalyzer.vsanIscsiTargetTargetStats
    @vsanIscsiTargetLunStats.merge! inventoryAnalyzer.vsanIscsiTargetLunStats
  end

  def _generateRdtGraphs
    $stderr.puts "#{Time.now}: Generating RDT graphs"
    @rdtAssocsetHistos.each do |host, hostStats|
      hostStats.each do |ep, stats|
        fileName = "stats/rdtassocset-#{host}-#{ep[0]}-#{ep[1]}"
        Gnuplot.open do |gp|
          Gnuplot::Plot.new( gp ) do |plot|
            plot.output fileName + "-histo.png"
            plot.terminal 'png size 1024,3000'
            plot.title "RDT Assocset readytimes on #{host}/#{ep[0]}/#{ep[1]}"
            plot.ylabel "Count"
            #plot.xlabel "uptime"
            #plot.autoscale "true"
            plot.xlabel "time"
            plot.multiplot ''
            plot.xdata "time"
            plot.timefmt '"%m-%d-%H:%M:%S"'
            plot.format 'x "%m-%d-%H:%M:%S"'
            plot.xtics 'rotate'
            plot.data = stats.keys.sort.map do |key|
              Gnuplot::DataSet.new( [
                stats[key].times.map do |time|
                  Time.at(time).strftime("%m-%d-%H:%M:%S")
                end,
                stats[key].values.values
              ] ) do |ds|
                ds.with = "linespoints"
                ds.title = "<= #{key} us"
                ds.using = "1:2"
              end
            end
          end
        end

        stats = @rdtAssocsetStats[host][ep]
        Gnuplot.open do |gp|
          Gnuplot::Plot.new( gp ) do |plot|
            plot.output fileName + "-avg.png"
            plot.terminal 'png size 1024,800'
            plot.title "RDT Assocset readytimes on #{host}/#{ep[0]}/#{ep[1]}"
            plot.ylabel "<= us"
            #plot.xlabel "uptime"
            #plot.autoscale "true"
            plot.xlabel "time"
            plot.multiplot ''
            plot.xdata "time"
            plot.timefmt '"%m-%d-%H:%M:%S"'
            plot.format 'x "%m-%d-%H:%M:%S"'
            plot.xtics 'rotate'
            plot.data = [
              Gnuplot::DataSet.new( [
                stats['avgReady'].times.map do |time|
                  Time.at(time).strftime("%m-%d-%H:%M:%S")
                end,
                stats['avgReady'].avgs.values
              ] ) do |ds|
                ds.with = "linespoints"
                ds.title = "ready time upper bound avg (us)"
                ds.using = "1:2"
              end
            ]
          end
        end
      end
    end
  end

  def generateSummaryGraphs(useJsGraphs)
    threads = []
    maxthreads = 20

    t1 = Time.now
    _generateRdtGraphs
    t2 = Time.now
    (t2 - t1)
  end

  def generateGraphs
    time = 0
    time += generateSummaryGraphs
    time
  end

  def _processCmmdsEntries entries
    obj_infos = {
       'dom_objects' => {},
       'lsom_objects' => {},
       'disk_objects' => {},
       'vsan_disk_uuids' => {},
       'host_vsan_uuids' => {},
       'host_props' => {},
    }
    entries.each do |e|
      if e['type'] == 'DOM_OBJECT'
        obj_infos['dom_objects'][e['uuid']] ||= {}
        obj_infos['dom_objects'][e['uuid']]['config'] = e
      end
      if e['type'] == 'POLICY'
        obj_infos['dom_objects'][e['uuid']] ||= {}
        obj_infos['dom_objects'][e['uuid']]['policy'] = e['content']
      end
      if e['type'] == 'LSOM_OBJECT'
        obj_infos['lsom_objects'][e['uuid']] = e
      end
      if ['DISK', 'DISK_STATUS', 'DISK_USAGE'].member?(e['type'])
        edup = e.dup
        edup.delete('content')
        obj_infos['disk_objects'][e['uuid']] ||= edup
        obj_infos['disk_objects'][e['uuid']].merge!(e['content'])
      end
    end
    @cmmdsClusterInfos.map do |host, info|
      obj_infos['host_vsan_uuids'][info["Local Node UUID"]] = host
      obj_infos['host_props'][host] = {'name' => host}
    end


    obj_infos
  end

  def generateDomPerHostHtml
    puts "#{Time.now}: Generating DOM per-host HTML tabs ..."
    out = {}
    allUuids = @v3DomStats.stats.keys.map{|x| x[0]}

    tabs = []

    tab = ""
    #tab << "<h3>What am I looking at?</h3>"
    tab << "<h3 onclick='javascript: $(\"#client-tab-help\").toggle(\"fast\")'>"
    tab << "<i class=\"icon-question-sign\"></i> What am I looking at </h3>"
    tab << "<div class='tabhelp' id='client-tab-help'>"
    tab << "<p>This view shows vSAN statistics from the view point of the "
    tab << "vSAN client running on each host. In other words, this view "
    tab << "represents the vSAN performance as seen by VMs running on the "
    tab << "hosts for which statistics are shown.</p><p>If this view shows any "
    tab << "unexpected performance, one needs to drill down further to "
    tab << "understand where performance issues may be coming from. "
    tab << "It is important to understand that due to the distributed "
    tab << "nature of vSAN each host accesses data from all hosts, "
    tab << "so any performance issue seen on this view may be caused by "
    tab << "any host in the vSAN cluster. Check the 'vSAN disks' "
    tab << "view to learn more about any bottlenecks the disks (HDD and SSD) "
    tab << "may be causing, or navigate to the 'VM' centric view to see "
    tab << "how individual disks/hosts are contributing to the VMs performance."
    tab << "</p>"
    tab << "</div>"
    tabs << {
      'text' => tab,
      'uuids' => allUuids.select{|x| x =~ /(client)-/}.sort,
      'title' => 'vSAN Client',
      'tabname' => 'vsan-client-host-tab',
      'visibility' => 1,
      'label' => 'vSAN Client',
    }


    tab = ""
    tab << "<h3 onclick='javascript: $(\"#disks-tab-help\").toggle(\"fast\")'>"
    tab << "<i class=\"icon-question-sign\"></i> What am I looking at </h3>"
    tab << "<div class='tabhelp' id='disks-tab-help'>"
    tab << "<pr>This view shows vSAN statistics of the physical disk layer of "
    tab << "each host. In other words, this view allows to determine if there "
    tab << "is any contention on any of the disk groups that make up the overall "
    tab << "vSAN cluster. Note that the statistics shown are purely the "
    tab << "physical disk layer and do not include any other vSAN overhead "
    tab << "(e.g. networking or vSAN RAID). Also remember that due to the "
    tab << "distributed nature of vSAN the physical disks of one host are "
    tab << "accessed by VMs on all hosts in the vSAN cluster.</p><p>"
    tab << "If this view shows physical disk contention across a majority "
    tab << "of hosts then this likely indicates that the workload run by "
    tab << "VMs is collectively higher than the vSAN cluster can handle. "
    tab << "In that case, either reduce the storage workload, or check the "
    tab << "detailed physical device view to determine if you need more HDDs "
    tab << "or SSDs.</p><p>"
    tab << "If however only a single host's physical disks are contended, "
    tab << "while other hosts are operating fine, then you may have an "
    tab << "imbalance, e.g. caused by particularly noisy VMs. We would like "
    tab << "to learn about such cases in order to further tune our balancing "
    tab << "algorithms, but unfortunately do not offer any user actions to "
    tab << "remediate at this point."
    tab << "</p></div>"
    tabs << {
      'text' => tab,
      'uuids' => allUuids.select{|x| x =~ /(compmgr)-/}.sort,
      'title' => 'vSAN Disks',
      'tabname' => 'vsan-disks-host-tab',
      'visibility' => 2,
      'label' => 'vSAN Disks',
    }

    tab = ""
    tab << "<h3 onclick='javascript: $(\"#domowner-tab-help\").toggle(\"fast\")'>"
    tab << "<i class=\"icon-question-sign\"></i> What am I looking at </h3>"
    tab << "<div class='tabhelp' id='domowner-tab-help'>"
    tab << "<p>For VMware Support: DOM Owner.</p>"
    tab << "<p>The DOM owner is a vSAN internal layer. For every vSAN object "
    tab << "vSAN elects one host to be the 'owner'. The owner performance all "
    tab << "RAID functionality and ensures correctness, even under concurrent "
    tab << "access by multiple clients. All IO flows from the vSAN client to "
    tab << "to the owner and then to the disk layer. vSAN tries to "
    tab << "co-locate the owner and the client to not incur an additional "
    tab << "network hop. However, the user can't influence where the owner "
    tab << "for a given object is located, so reading the below graphs and "
    tab << "correlating them with the client and disks graphs can be "
    tab << "very difficult. We expect only VMware Support to be able to "
    tab << "read much out of these graphs.</p>"
    tab << "</div>"
    tabs << {
      'text' => tab,
      'uuids' => allUuids.select{|x| x =~ /(total)-/}.sort,
      'title' => 'DOM Owner',
      'tabname' => 'vsan-domowner-host-tab',
      'visibility' => 1000,
      'label' => 'DOM Owner',
    }

    tabs.each do |tabInfo|
      tab = tabInfo['text']
      table = TableEmitter.new(
        tabInfo['label'], "IO Graphs",
      ) do |table|
        uuids = tabInfo['uuids']
        uuids.each do |uuid|
          title = uuid
          if uuid =~ /(total|client|compmgr)-(.*)/
            title = $2
          end

          graphs = "<span id='dom-#{uuid.gsub(".", "-")}'></span>"

          graphUrl = "graphs.html?json=jsonstats/dom/domobj-#{uuid}.json"
          row = [
            [
              title,
              "<a href=\"#{graphUrl}\">Full size graphs</a>"
            ].join("<br>"),
            graphs
          ]
          table.row(row)
        end
      end
      tab << table.generate(false)
      tab << "<script>registerDomGraphs('#{tabInfo['tabname']}', #{JSON.dump(tabInfo['uuids'])}, 'dom')</script>"
      out[[tabInfo['title'], tabInfo['tabname'], tabInfo['visibility']]] = tab
    end

    out
  end

  def generateLsomHtml(skipExpert = false)
    puts "#{Time.now}: Generating LSOM per-host HTML tabs ..."
    tab = ""
    tab << "<h3 onclick='javascript: $(\"#lsom-tab-help\").toggle(\"fast\")'>"
    tab << "<i class=\"icon-question-sign\"></i> What am I looking at </h3>"
    tab << "<div class='tabhelp' id='lsom-tab-help'>"
    tab << "<p>This view offers a deep view into the physical disk layer of a vSAN "
    tab << "host. It offers an aggregate view across all disks and disk groups "
    tab << "as well as details about every physical disk. </p><p>"
    tab << "Using this view one can get insight into how vSAN is splitting "
    tab << "the IO work between the SSDs and HDDs. In particular, a low "
    tab << "ReadCache (RC) hit ratio means that the size of the SSD is not "
    tab << "large enough to keep the 'working set' of the workload in cache. "
    tab << "Typically that in turn leads to the HDDs (also refered to as "
    tab << "Magnetic Disk, MD) seeing a lot of IOPS and high IO latencies. "
    tab << "In such cases a cache analysis should be done to determine how "
    tab << "much cache would be sufficient for the workload to potentially "
    tab << "buy additional SSDs. Alternatively, additional HDDs may be able "
    tab << "to absorb the higher cache miss load.</p><p>"
    tab << "If the RC hit ratio is high, and HDD low in IOPS and latency, but "
    tab << "the SSD seeing very high IOPS beyond the SSDs capabilities or "
    tab << "high SSD latency, then vSAN is using the "
    tab << "cache very effectively, but either the SSD is no longer performing "
    tab << "according to its speficiation or even the SSD with its superior "
    tab << "performance is not able to keep up with the workload. Using more "
    tab << "SSDs would improve the latter case. The former case should be "
    tab << "looked at with the SSD vendor.</p><p>"
    tab << "Note: The IOPS of SSD and HDD will be higher than the aggregate "
    tab << "IOPS shown. This is because of vSAN consuming IOPS for internal "
    tab << "purposes in order to provide the caching and availability features. "
    tab << "</p></div>"

    tab << "Host to show: "
    tab << "<select onchange='toggleLsomHostDiv()' id='lsom-host-dropdown'>"
    tab << "<option>None</option>"
    hostnames = @lsomHostStats.stats.keys.map{|x| x[0]}.sort
    hostnames.each do |hostname|
      tab << "<option>#{hostname}</option>"
    end
    tab << "</select>"
    tab << "<br>"

    hostnames.each do |hostname|
      tab << "<div style='display: none' id='lsom-host-#{hostname.gsub(".", "_")}' class='lsom-host-div'>"
      graphUrl = "graphs.html?json=jsonstats/lsom/lsomhost-#{hostname}.json&group=lsomhost"
      graphLink = "<a style=\"font-weight: normal;\" href=\"#{graphUrl}\">Full graphs</a>"
      table = TableEmitter.new(
        "Host disk-layer aggregate stats: #{graphLink}",
      ) do |table|
        prefix = "lsom-#{hostname.gsub(".", "-")}"
        graphs = ""
        ['latency', 'iops', 'tput', 'rc', 'evictions'].each do |type|
          graphs += "<div class=\"mini-graph-container\">"
          graphs += "<div class=\"graphmini #{prefix}-#{type}\"></div>"
          graphs += "</div>\n"
        end
        graphs += "<script>registerGraph('lsom-host-#{hostname}', 'jsonstats/lsom/lsomhost-#{hostname}_thumb.json', computeLsomHostGraphSpecsThumb, '#{prefix}')</script>"

        row = [
          graphs,
        ]
        table.row(row, :no_left_heading => true)
      end
      tab << table.generate
      tab << "<br>"

      plogMds = @plogStats.keys.select{|x| x[2]['isSSD'] != 1}.map{|x| x.first(2)}
      plogMds = plogMds.uniq.sort_by{|x| x[0]}
      plogMds = plogMds.select{|h, uuid| h == hostname}

      table = TableEmitter.new(
        "Device-level stats",
      ) do |table|
        plogSsds = @plogStats.keys.select{|x| x[2]['isSSD'] == 1}.map{|x| x.first(2)}
        ssdsKeys = @ssds.stats.keys
        devs = (ssdsKeys + @diskStats.keys + plogSsds).uniq.sort_by{|x| x[0]}
        devs = devs.select{|h, uuid| h == hostname}
        devs.each do |hostname, uuid|
          registers = ""
          graphs = ""

          if false
            # Do not show PLOG latencies at SSD layer in summary, because
            # these latencies are not relevant to the user
            prefix = "plog-#{uuid}"
            graphs += "<div class=\"mini-graph-container\">"
            graphs += "<div class=\"graphmini #{prefix}-ploglatencysum\"></div>"
            graphs += "</div>\n"
            graphs += "<div class=\"mini-graph-container\">"
            graphs += "<div class=\"graphmini #{prefix}-plogiopssum\"></div>"
            graphs += "</div>\n"
            registers += "<script>registerGraph('lsom-host-#{hostname}', 'jsonstats/lsom/plog-#{uuid}_thumb.json',computePlogGraphSpecs, '#{prefix}')</script>"
          end

          prefix = "disk-#{uuid}"
          graphs += "<div class=\"mini-graph-container\">"
          graphs += "<div class=\"graphmini #{prefix}-disklatencysum\"></div>"
          graphs += "</div>\n"
          graphs += "<div class=\"mini-graph-container\">"
          graphs += "<div class=\"graphmini #{prefix}-diskiopssum\"></div>"
          graphs += "</div>\n"
          registers += "<script>registerGraph('lsom-host-#{hostname}', 'jsonstats/lsom/disk-#{uuid}_thumb.json',computeDiskGraphSpecs, '#{prefix}')</script>"

          prefix = "ssd-#{uuid}"
          graphs += "<div class=\"mini-graph-container\">"
          graphs += "<div class=\"graphmini #{prefix}-wb\"></div>"
          graphs += "</div>\n"
          registers += "<script>registerGraph('lsom-host-#{hostname}', 'jsonstats/lsom/ssd-#{uuid}_thumb.json', computeSSDGraphSpecsThumb, '#{prefix}')</script>"

          graphs += registers

          ssd = uuid
          if @plogDeviceInfo[uuid] && @plogDeviceInfo[uuid]['diskName']
            ssd += "<br>" + @plogDeviceInfo[uuid]['diskName']
          end
          row = [
            [
              "SSD",
              ssd,
              "<a href=\"graphs.html?uuid=#{uuid}&group=ssd\">Full graphs</a>",
              "<a href=\"graphs.html?group=physdisk&host=#{hostname}&dev=#{ @plogDeviceInfo[uuid]['diskName']}&md5=#{Digest::MD5.hexdigest(@plogDeviceInfo[uuid]['diskName'])}\">PhysDisk</a>",
            ].join("<br>"),
            [
              graphs,
            ].join("<br>")
          ]
          table.row row

          ssdMds = plogMds.map{|x| x[1]}.select do |x|
            mdInfo = @cmmdsDisks[x]
            mdInfo && mdInfo['content']['ssdUuid'] == uuid
          end

          ssdMds.each do |uuid|
            prefix = "plog-#{uuid}"
            ploggraphs = ""
            ploggraphs += "<div class=\"mini-graph-container\">"
            ploggraphs += "<div class=\"graphmini #{prefix}-ploglatencysum\"></div>"
            ploggraphs += "</div>\n"
            ploggraphs += "<div class=\"mini-graph-container\">"
            ploggraphs += "<div class=\"graphmini #{prefix}-plogiopssum\"></div>"
            ploggraphs += "</div>\n"
            ploggraphs += "<script>registerGraph('lsom-host-#{hostname}', 'jsonstats/lsom/plog-#{uuid}_thumb.json', computePlogGraphSpecs, '#{prefix}')</script>"

            hdd = uuid
            if @plogDeviceInfo[uuid] && @plogDeviceInfo[uuid]['diskName']
              hdd += "<br>" + @plogDeviceInfo[uuid]['diskName']
            end
            row = [
              [
                "HDD",
                hdd,
                "<a href=\"graphs.html?uuid=#{uuid}&group=md\">Full graphs</a>",
                "<a href=\"graphs.html?group=physdisk&host=#{hostname}&dev=#{@plogDeviceInfo[uuid]['diskName']}&md5=#{Digest::MD5.hexdigest(@plogDeviceInfo[uuid]['diskName'])}\">PhysDisk</a>",
              ].join("<br>"),
              [
                ploggraphs,
                ""
              ].join("<br>")
            ]
            table.row row
          end
        end
      end
      tab << table.generate(true)
      tab << "<br><br>"

      tab << "</div>" # Host-Div
      tab << "<br>"
    end
    tab << "<br><br>"

    if !skipExpert
    tab << "<h5 onclick='javascript: $(\"#lsom-tab-expert\").toggle(\"fast\")'>"
    tab << "<i class=\"icon-bar-chart\"></i> Expert graphs </h5>"
    tab << "<div class='expertinfo' id='lsom-tab-expert'>"
    diskKeys = []
    table = TableEmitter.new(
      "Hostname", "Physical-Disk-Stats"
    ) do |table|
      @physDiskStats.stats.keys.each do |key|
        hostname = key[0]
        dev = key[1]
        md5Dev = Digest::MD5.hexdigest(key[1])
        diskKeys << [key[0], key[1], md5Dev]
        row = [
          [
            hostname,
            dev,
            [
              "<a href=\"graphs.html?group=physdisk&host=#{hostname}&dev=#{dev}&md5=#{md5Dev}\">PhysDisk</a>",
            ].join(' - '),
          ].join("<br>"),
          "<span id='lsom-physdisk-#{hostname.gsub(/(\.|:)/, "-")}-#{dev.gsub(/(\.|:)/, "-")}'></span>"
        ]
        table.row row
      end
    end
    tab << table.generate
    tab << "<script>registerPhysDiskGraphs('lsom-tab', #{JSON.dump(diskKeys)})</script>"
    tab << "</div>"
    end

    {['vSAN Disks (deep-dive)', 'lsom-tab', 3] => tab}
  end

  def generateCpuHtml(skipRdtAsso = false)
    puts "#{Time.now}: Generating CPU per-host HTML tabs ..."
    tab = ""
    tab << "<h3 onclick='javascript: $(\"#cpu-tab-help\").toggle(\"fast\")'>"
    tab << "<i class=\"icon-question-sign\"></i> What am I looking at </h3>"
    tab << "<div class='tabhelp' id='cpu-tab-help'>"
    tab << "<p>This view shows CPU usage statistics, both from a overall host "
    tab << "perspective, as well as specifically of vSAN and networking "
    tab << "worldlets.</p><p>"
    tab << "A worldlet can at most occupy a single physical CPU core. The "
    tab << "100% mark in the graphs refer to percentage of that limit. If "
    tab << "the utilization of a vSAN worldlet is getting close to 100% then "
    tab << "CPU is likely a bottleneck for vSAN performance. However, even "
    tab << "when the utilization (called runTime) is not maxed out yet, a "
    tab << "significant utilization (>10%) of readyTime indicates CPU "
    tab << "contention between vSAN and other uses of physical CPUs on "
    tab << "the host (e.g. running VMs). Looking at overall CPU consumption "
    tab << "of the host should confirm this picture.</p><p>"
    tab << "In case of contention (high ready time) turning off other users "
    tab << "of the CPU may improve vSAN performance, especially latencies. "
    tab << "In case of maxed out utilization, the workload is too demanding "
    tab << "in terms of IOPS for the current version of vSAN."
    tab << "</p></div>"

    table = TableEmitter.new(
      "Hostname", "PCPU graphs", "Worldlet graphs"
    ) do |table|
      hostnames = @worldletStats.keys.map{|x| x[0]}.uniq.sort
      hostnames.each do |hostname|
        key = [hostname]
        wdts = @worldletStats.keys.select{|x| x[0] == hostname}.map{|x| x[1]}
        helperworlds = @helperWorldStats.keys.select{|x| x[0] == hostname}.map{|x| x[1]}

        wdtsGroups = {
          'DOM' => wdts.grep(/(VSAN)/) - wdts.grep(/(CMMDS|PLOG|LSOM)/),
          'LSOM' => wdts.grep(/(LSOM|PLOG)/),
          'CMMDS' => wdts.grep(/(CMMDS)/),
          'vmnic' => wdts.grep(/vmnic/),
          'vmknic' => wdts.grep(/vmk\d+/),
          'iSCSI' => wdts.grep(/(vit)/),
        }

        prefix = "pcpu-#{hostname.gsub(".", "-")}"
        cpugraphs = ""
        cpugraphs += "<div class=\"mini-graph-container\"><div class=\"graphmini #{prefix}-pcpus\"></div></div>\n"
        cpugraphs += "<script>registerGraph('cpu-tab', 'jsonstats/pcpu/pcpu-#{hostname}_thumb.json', computePcpuGraphSpecs, '#{prefix}')</script>"

        row = [
          [
            "#{hostname}",
          ].compact.join("<br>"),
          [
            "PCPU: <a href=\"graphs.html?group=pcpu&host=#{hostname}\">Full graphs</a>",
            cpugraphs,
          ].join("<br>"),
          wdtsGroups.map do |group, wdts|
            next if wdts.length == 0
            url = "graphs.html?host=#{hostname}&group=wdts&wdts=#{wdts.sort.join(',')}"
            "#{group}: <a href=\"#{url}\">Full graphs</a>"
          end.compact.join(" - ") +
        ###  " - Helper-worlds: <a href=\"graphs.html?host=#{hostname}&group=helperworlds&helperworlds=#{helperworlds.join(',')}\">Full graphs</a>" +
          "<br>" +
          wdtsGroups.map do |group, wdts|
            if !['DOM', 'LSOM'].member?(group)
              next
            end
            list = wdts.sort.map do |wdt|
              label = wdt.gsub("VSAN_", "")

              prefix = "pcpu-#{hostname.gsub(".", "-")}-#{wdt}"
              graphs = ""
              graphs += "<div class=\"mini-graph-container\">"
              graphs += "<div class=\"graphmini #{prefix}\"></div>"
              graphs += "</div>\n"
              graphs += "<script>registerGraph('cpu-tab', 'jsonstats/pcpu/wdt-#{hostname}-#{wdt}_thumb.json', computeWdtGraphSpecsThumb, '#{prefix}')</script>"
              graphs
            end.join("  ")
          end.join(" ")
        ]
        table.row row
      end
    end
    tab << table.generate(false)

    tab << "<br><br>"

    if !skipRdtAsso
    tab << "<b>RDT AssociationSets</b>: Charts and stats:<br><br>"
    table = TableEmitter.new(
      "Host", "Association Set", "Ready times"
    ) do |table|
      @rdtAssocsetHistos.keys.sort.each do |hostname|
        @rdtAssocsetHistos[hostname].keys.sort.each do |assocset|
          ep, assocset = assocset
          imgprefix = "rdtassocset-#{hostname}-#{ep}-#{assocset}"
          row = [
            hostname,
            "#{ep} - #{assocset}",
            [
              "<a href=\"stats/#{imgprefix}-histo.png\">Histo</a>",
              "<a href=\"stats/#{imgprefix}-avg.png\">Average</a>",
            ].join("  "),
          ]
          table.row row
        end
      end
    end
    tab << table.generate
    end

    {['PCPU', 'cpu-tab', 6] => tab}
  end

  def generateMemoryHtml
    puts "#{Time.now}: Generating Memory per-host HTML tabs ..."
    # LSOM* heaps are congestion influencing

    tab = ""
    tab << "<h3 onclick='javascript: $(\"#mem-tab-help\").toggle(\"fast\")'>"
    tab << "<i class=\"icon-question-sign\"></i> What am I looking at </h3>"
    tab << "<div class='tabhelp' id='mem-tab-help'>"
    tab << "<p>Disclaimer: "
    tab << "This view is primarily meant for VMware Support. Users may "
    tab << "or may not be able to spot problems in the shown values. "
    tab << "But VMware "
    tab << "Support may be able to suggest changes of advanced config "
    tab << "options to tune the sizes of the shown memory pools if "
    tab << "a problem is found.</p><p>"
    tab << "This view shows consumption of various vSAN memory pools. "
    tab << "The pools tracked under <i>congestion</i> directly impact "
    tab << "IO performance if they are above ~75% utilization. Such a "
    tab << "high utilization triggers vSAN's congestion mechanism, which "
    tab << "imposes IO delays (additional latencies) at the vSAN client. "
    tab << "Congestion values can be seen in the various IO views in this "
    tab << "tool.</p>"
    tab << "<p>Other memory pools are expected to be fully utilized "
    tab << "based on vSAN system limits (like number of SSDs, HDDs, disk "
    tab << "groups, components, etc) being reached. High utilization then "
    tab << "means a configuration limit is reached, but shouldn't result in any "
    tab << "IO path performance implications."
    tab << "</p><p>"
    tab << "If sizing of the memory pools is found to be a problem, it is "
    tab << "often possible to adjust ESX advanced config options to tune "
    tab << "the sizes of the pools. VMware Support may suggest such changes "
    tab << "based on analysis of the data shown here."
    tab << "</p></div>"

    table = TableEmitter.new(
      "Host", "Slabs", "Heaps"
    ) do |table|
      (@slabs.keys + @heaps.keys).uniq.sort.each do |hostname|
        prefix = "slab-#{hostname.gsub(".", "-")}"
        graphs = ""
        slabs = ['congestion', 'lsom', 'dom']
        slabs.each do |i|
          graphs += "<div class=\"mini-graph-container\"><div class=\"graphmini #{prefix}-#{i}\"></div></div>\n"
        end
        graphs += "<script>registerGraph('mem-tab', 'jsonstats/mem/slabs-#{hostname}_thumb.json', computeMemGraphSpecs, '#{prefix}')</script>"

        graphs2 = ""
        prefix = "heap-#{hostname.gsub(".", "-")}"
        heaps = ['cmmds', 'other']
        heaps.each do |i|
          graphs2 += "<div class=\"mini-graph-container\"><div class=\"graphmini #{prefix}-#{i}\"></div></div>\n"
        end
        graphs2 += "<script>registerGraph('mem-tab', 'jsonstats/mem/heaps-#{hostname}_thumb.json', computeMemGraphSpecs, '#{prefix}')</script>"

        url = "graphs.html?group=mem&host=#{hostname}"
        url += "&slabs=#{slabs.join(',')}"
        url += "&heaps=#{heaps.join(',')}"
        row = [
          hostname + "<br>" + "<a href=\"#{url}\">Full graphs</a>",
          graphs +
          graphs2,
        ]
        table.row row
      end
    end
    tab << table.generate(false)

    {['Memory', 'mem-tab', 7] => tab}
  end

  def generateVscsiHtml
    cbrcEnabled = @cbrcStats.find do |host, stats|
      stats['vmReadCount'] && stats['dioReadCount']
    end
    if !cbrcEnabled
      puts "#{Time.now}: CBRC wasn't enabled, skipping ..."
      return {}
    end

    puts "#{Time.now}: Generating CBRC per-host HTML tabs ..."
    tab = ""
    table = TableEmitter.new(
      "Host", "CBRC Graphs", "Links"
    ) do |table|
      @cbrcStats.keys.sort.each do |hostname|
        prefix = "cbrc-#{hostname.gsub(".", "-")}"
        graphs = ""
        groups = ['hitrate']
        groups.each do |i|
          graphs += "<div class=\"mini-graph-container\"><div class=\"graphmini #{prefix}-#{i}\"></div></div>\n"
        end
        graphs += "<script>registerGraph('cbrc-tab', 'jsonstats/misc/cbrc-#{hostname}_thumb.json', computeCbrcGraphSpecsThumb, '#{prefix}')</script>"

        row = [
          "#{hostname}",
          graphs,
          "<a href=\"graphs.html?group=cbrc&host=#{hostname}\">Full graphs</a>",
        ]
        table.row row
      end
    end
    tab << table.generate

    {['CBRC', 'cbrc-tab', 10] => tab}
  end

  def generateDistributionHtml
    puts "#{Time.now}: Generating Distribution HTML tabs ..."
    tab = ""
    tab << "<h3 onclick='javascript: $(\"#dist-tab-help\").toggle(\"fast\")'>"
    tab << "<i class=\"icon-question-sign\"></i> What am I looking at </h3>"
    tab << "<div class='tabhelp' id='dist-tab-help'>"
    tab << "<p>This view shows how various physical and in-memory objects "
    tab << "are distributed across the vSAN cluster.</p><p>"
    tab << "Components are the slices/pieces of vSAN objects stored on "
    tab << "HDDs. They include IO components and witnesses. Balancing "
    tab << "components across the cluster is an important sideeffect of "
    tab << "balancing for performance and space. But in addition, in v1 "
    tab << "of vSAN there is 3000 components per host limit.</p><p>"
    tab << "DOM owners are in-memory state inside vSAN that the user "
    tab << "can't control. The information is shown here for the benefit "
    tab << "of VMware Support."

    tab << "</p></div>"
    graphs = ""
    prefix = "distribution"
    types = ['lsom-components', 'lsom-iocomponents', 'dom-owners', 'dom-clients', 'dom-colocated']
    types.each do |i|
      graphs += "<div class=\"mini-graph-container\"><div class=\"graphmini #{prefix}-#{i}\"></div></div>\n"
    end
    graphs += "<script>registerGraph('distribution-tab', 'jsonstats/misc/distribution_thumb.json', computeDistributionGraphSpecsThumb, '#{prefix}')</script>"
    url = "graphs.html?group=distribution"
    tab << "<b>Distributions across hosts:</b> <a href=\"#{url}\">Full graphs</a><br>"
    tab << graphs

    {['Distribution', 'distribution-tab', 11] => tab}
  end

  def generateVmStateHtml
    tab = ""
    if @vmInfoHistory.length != 0
      table = TableEmitter.new(
        "VM Name", "Events" , "Options"

      ) do |table|
        vms =  @vmInfoHistory.each do |vm, history|
          if history.length <= 1
           next
          end
          name = history[0]['name']
          state = history[0]['runtime.connectionState']
          row = [
            name,
            history[1..-1].map do |entry|
              msg = "#{Time.at(entry['ts'])}: VM state changed #{state} -> #{entry['runtime.connectionState']}"
              state = entry['runtime.connectionState']
              msg
            end.compact.join("<br>"),
            "<a href='vmInfoHistory/#{name}.txt'>Full history</a>"
          ]
          table.row row
        end
      end
      tab << table.generate
    end

    FileUtils.mkdir_p 'vmInfoHistory'

    @vmInfoHistory.each do |vm, vmInfo|
      if vmInfo && ! vmInfo.empty?
        name = vmInfo[0]['name']
        open("vmInfoHistory/#{name}.txt", 'w') do |io|
          io.write "VM Name: #{name}\n\n"
          vmInfo.each do |entry|
            io.write "#{Time.at(entry['ts'])}:\n"
            io.write PP.pp(entry, "")
            io.write "\n"
          end
        end
      end
    end

    {['VM States', 'vmstate-tab', 12] => tab}
  end

  def generateLivenessHtml
    puts "#{Time.now}: Generating Liveness HTML tabs ..."
    configHistory = Hash[@cmmdsHistory.map do |k,v|
      history = v['CONFIG_STATUS']
      history ? [k, history] : nil
    end.compact]
    uuids = configHistory.select do |uuid, history|
      history = history.map do |entry|
        entry['live'] = _isLiveByState(entry['content']['state'])
        entry
      end
      if history.map{|x| x['live']}.uniq.length == 1
        next
      end
      true
    end.keys

    tab = ""
    if uuids.length != 0
      table = TableEmitter.new(
        "DOM object UUID", "Events"
      ) do |table|
        uuids = uuids.map do |uuid|
          history = configHistory[uuid]
          liveness = history[0]['live']
          row = [
            uuid,
            history[1..-1].map do |entry|
              if entry['live'] != liveness
                next
              end
              if !entry['live']
                msg = "#{entry['ts']}: Object lost liveness"
              else
                msg = "#{entry['ts']}: Object gained liveness"
              end
              liveness = entry['live']
              msg
            end.compact.join("<br>"),
          ]
          table.row row
        end
      end
      tab << table.generate
    end

    FileUtils.mkdir_p 'cmmdsHistory'

    objHistory = Hash[@cmmdsHistory.map do |k,v|
      history = v['DOM_OBJECT']
      history ? [k, history] : nil
    end.compact]
    objHistory.each do |uuid, object|
      next if !object || object.empty?
      uuid = object[0]['uuid']
      open("cmmdsHistory/#{uuid}.txt", 'w') do |io|
        io.write "Object UUID: #{uuid}\n\n"
        object.each do |entry|
          io.write "#{Time.at(entry['ts'])}:\n"
          io.write PP.pp(entry, "")
          io.write "\n"
        end
      end
    end

    table = TableEmitter.new(
      "DOM object UUID", "Component state changes", "Options"
    ) do |newTable|
      objHistory.each do |uuid, entries|
        prevStates = nil
        stateHistory = entries.map do |entry|
          comps = _components_in_dom_config(entry['content'])
          states = comps.map{|x| x['attributes']['componentState']}
          res = (prevStates != states) ? [entry, states] : nil
          prevStates = states
          res
        end.compact
        if stateHistory.length <= 1
          next
        end
        events = stateHistory.map do |change|
          entry, states = change
          states = states.map{|x| _componentStateName(x)}
          ts = Time.at(entry['ts'])
          "#{ts}: States: #{states}"
        end.join("<br>")
        uuid = entries[0]['uuid']
        newTable.row([
          uuid,
          events,
          "<a href='cmmdsHistory/#{uuid}.txt'>Full history</a>"
        ])
      end
    end
    tab << table.generate

    {['Liveness', 'livenesstab', 12] => tab}
  end

  def generateHtmlTabs useJsGraphs, opts = {}
    out = {}
    out.merge!(generateDomPerHostHtml())
    out.merge!(generateLsomHtml(opts[:skipLsomExpert]))
    out.merge!(generateCpuHtml(opts[:skipRdtAsso]))
    out.merge!(generateMemoryHtml())
    out.merge!(generateVscsiHtml())
#    out.merge!(generateDistributionHtml())
    if !opts[:skipLivenessTab]
      out.merge!(generateLivenessHtml())
      out.merge!(generateVmStateHtml())
    end

    # html << "<pre>"
    # html << "\n\nGaps:\n\n\n"
    # @gaps.each do |gap|
      # html << "#{gap}<br>"
    # end
    # html << "</pre>"

    out
  end

  def _assessAvailabilityByStatus state
    mask = {
      'DATA_AVAILABLE' => (1 << 0),
      'QUORUM' => (1 << 1),
      'PERF_COMPLIANT' => (1 << 2),
      'INCOMPLETE' => (1 << 3),
    }
    Hash[mask.map{|k,v| [k, (state & v) != 0]}]
  end

  def _isLiveByState state
    state = _assessAvailabilityByStatus(state)
    state['DATA_AVAILABLE'] && state['QUORUM']
  end

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

  def _componentStateName state
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
    state_name
  end
end
