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

TIMEFMT = '%Y-%m-%dT%H:%M:%SZ'

DISPLAY_TIMEFMT = {
  :realtime => '%H:%M',
  1 => '%H:%M',
  2 => '%m/%d',
  3 => '%m/%d',
  4 => '%Y/%m/%d',
}

def require_gnuplot
  begin
    require 'gnuplot'
  rescue LoadError
    Gem::Specification.reset
    begin
      require 'gnuplot'
    rescue LoadError
      err "The gnuplot gem is not installed"
    end
  end
end

def find_interval pm, start
  now = Time.now
  ago = now - start

  if ago < 3600
    #puts "Using realtime interval, period = 20 seconds."
    interval_id = 20
    display_timefmt = DISPLAY_TIMEFMT[:realtime]
  else
    intervals = pm.historicalInterval
    interval = intervals.find { |x| now - x.length < start }
    err "start time is too long ago" unless interval
    #puts "Using historical interval #{interval.name.inspect}, period = #{interval.samplingPeriod} seconds."
    interval_id = interval.samplingPeriod
    display_timefmt = DISPLAY_TIMEFMT[interval.key]
  end

  return interval_id, display_timefmt
end

opts :plot do
  summary "Plot a graph of the given performance counters"
  arg :counter, "Counter name"
  arg :obj, "", :lookup => VIM::ManagedEntity, :multi => true
  opt :terminal, "Display plot on terminal", :default => ENV['DISPLAY'].nil?
  opt :start, "Start time", :type => :date, :short => 's'
  opt :end, "End time", :type => :date, :short => 'e'
  summary <<-EOS

Example:
  perf.plot cpu.usagemhz myvm myvm2 --start '20 minutes ago'

See perf.counters to determine which performance counters are available.
  EOS
end

def plot counter_name, objs, opts
  vim = single_connection objs
  pm = vim.serviceContent.perfManager
  group_key, counter_key, rollup_type = counter_name.split('.', 3)

  now = Time.now
  opts[:end] ||= now
  opts[:start] ||= opts[:end] - 1800

  err "end time is in the future" unless opts[:end] <= Time.now

  interval_id, display_timefmt = find_interval pm, opts[:start]

  all_counters = Hash[pm.perfCounter.map { |x| [x.key, x] }]

  metrics = pm.QueryAvailablePerfMetric(
    :entity => objs.first,
    :intervalId => interval_id)

  metric = metrics.find do |metric|
    counter = all_counters[metric.counterId]
    counter.groupInfo.key == group_key &&
      counter.nameInfo.key == counter_key
  end or err "counter #{group_key}.#{counter_key} was not found in the #{interval_id}s interval"
  counter = all_counters[metric.counterId]

  specs = objs.map do |obj|
    {
      :entity => obj,
      :metricId => [metric],
      :intervalId => interval_id,
      :startTime => opts[:start],
      :endTime => opts[:end],
      :format => 'csv',
    }
  end

  with_gnuplot(true) do |gp|
    plot = Gnuplot::Plot.new(gp) do |plot|
      if objs.size == 1
        plot.title "#{counter_name} on #{objs[0].name}"
      else
        plot.title counter_name
      end

      plot.ylabel counter.unitInfo.label
      plot.xlabel "Time"
      plot.terminal 'dumb' if opts[:terminal]

      plot.set 'xdata', 'time'
      plot.set 'format', "x '#{display_timefmt}'"
      plot.set 'timefmt', TIMEFMT.inspect

      if counter.unitInfo.key == 'percent'
        plot.set 'yrange', '[0:100]'
      end

      plot.data = retrieve_datasets pm, counter, specs
    end
    gp.puts
  end
end

def retrieve_datasets pm, counter, specs
  results = pm.QueryPerf(:querySpec => specs)
  datasets = results.map do |result|
    times = result.sampleInfoCSV.split(',').select { |x| x['T']  }
    if result.value.empty?
      puts "No data for #{result.entity.name} #{counter.name}"
      next
    end
    data = result.value[0].value.split(',').map(&:to_i)

    if counter.unitInfo.key == 'percent'
      times.length.times do |i|
        times[i] = data[i] = nil if data[i] < 0
      end

      times.compact!
      data.compact!
      data.map! { |x| x/100.0 }
    end

    Gnuplot::DataSet.new([times, data]) do |ds|
      ds.notitle if specs.size == 1
      ds.with = "lines"
      ds.using = '1:2'
      ds.title = result.entity.name
    end
  end.compact
end

def with_gnuplot persist
  if $rvc_gnuplot
    yield $rvc_gnuplot
  else
    cmd = Gnuplot.gnuplot(persist) or err 'gnuplot not found'
    $rvc_gnuplot = IO::popen(cmd, "w")
    begin
      yield $rvc_gnuplot
    ensure
      gp = $rvc_gnuplot
      $rvc_gnuplot = nil
      gp.close
    end
  end
end


opts :watch do
  summary "Watch a graph of the given performance counters"
  arg :counter, "Counter name"
  arg :objs, "", :lookup => VIM::ManagedEntity, :multi => true
  opt :interval, "Seconds between updates", :short => 'i', :default => 10
  opt :terminal, "Display plot on terminal", :default => ENV['DISPLAY'].nil?
end

def watch counter_name, objs, opts
  require_gnuplot
  with_gnuplot false do |gp|
    puts "Press Ctrl-C to stop."
    while true
      plot counter_name, objs, :terminal => opts[:terminal]
      sleep opts[:interval]
      if opts[:terminal]
        $stdout.write "\e[25A"
        $stdout.flush
      end
    end
  end
rescue Interrupt
end


opts :counters do
  summary "Display available perf counters"
  arg :obj, nil, :lookup => VIM::ManagedEntity
end

def counters obj
  pm = obj._connection.serviceContent.perfManager
  interval = pm.provider_summary(obj).refreshRate
  if interval == -1
    # Object does not support real time stats
    interval = nil
  end

  active_intervals = pm.active_intervals
  active_intervals_text = lambda do |level|
    return '' unless level
    xs = active_intervals[level]
    return 'none' if xs.empty?
    xs.map { |x| x.name.match(/Past (\w+)/)[1] } * ','
  end

  metrics = pm.QueryAvailablePerfMetric(
    :entity => obj,
    :intervalId => interval)
  available_counters = metrics.map(&:counterId).uniq.
                               map { |id| pm.perfcounter_idhash[id] }

  groups = available_counters.group_by { |counter| counter.groupInfo }

  table = Terminal::Table.new
  table.add_row ["Name", "Description", "Unit", "Level", "Per-Dev", "Active Intervals"]
  groups.sort_by { |group,counters| group.key }.each do |group,counters|
    table.add_separator
    table.add_row [{ :value => group.label, :colspan => 5}]
    table.add_separator
    counters.sort_by(&:name).each do |counter|
      pp counter
      table.add_row [counter.name, counter.nameInfo.label, counter.unitInfo.label,
                     counter.level, counter.perDeviceLevel,
                     active_intervals_text[counter.level]]
    end
  end
  puts(table)
end


opts :counter do
  summary "Retrieve detailed information about a perf counter"
  arg :metric, nil, :type => :string
  arg :obj, nil, :lookup => VIM::ManagedEntity, :required => false
end

def counter counter_name, obj
  vim = obj ? obj._connection : lookup_single('~@')
  pm = vim.serviceContent.perfManager
  counter = pm.perfcounter_hash[counter_name] or err "no such counter #{counter_name.inspect}"

  active_intervals = pm.active_intervals
  active_intervals_text = lambda do |level|
    xs = active_intervals[level]
    xs.empty? ? 'none' : xs.map(&:name).map(&:inspect) * ', '
  end

  puts "Label: #{counter.nameInfo.label}"
  puts "Summary: #{counter.nameInfo.summary}"
  puts "Unit label: #{counter.unitInfo.label}"
  puts "Unit summary: #{counter.unitInfo.summary}"
  puts "Rollup type: #{counter.rollupType}"
  puts "Stats type: #{counter.statsType}"
  puts "Level: #{counter.level}"
  puts " Enabled in intervals: #{active_intervals_text[counter.level]}"
  puts "Per-device level: #{counter.perDeviceLevel}"
  puts " Enabled in intervals: #{active_intervals_text[counter.perDeviceLevel]}"

  if obj
    interval = pm.provider_summary(obj).refreshRate
    if interval == -1
      # Object does not support real time stats
      interval = nil
    end
    puts "Real time interval: #{interval || 'N/A'}"
    metrics = pm.QueryAvailablePerfMetric(:entity => obj, :intervalId => interval)
    metrics.select! { |x| x.counterId == counter.key }
    instances = metrics.map(&:instance).reject(&:empty?)
    unless instances.empty?
      puts "Instances:"
      instances.map do |x|
        puts "  #{x}"
      end
    end
  end
end


opts :modify_counters do
  summary "Modify perf counter settings"
  arg :metrics, nil, :type => :string, :multi => true
  opt :aggregate_level, nil, :type => :int
  opt :per_device_level, nil, :type => :int
end

def modify_counters counter_names, opts
  vim = lookup_single('~@')
  pm = vim.serviceContent.perfManager
  pm.UpdateCounterLevelMapping(
    :counterLevelMap => counter_names.map do |counter_name|
      counter = pm.perfcounter_hash[counter_name]
      if !counter
        err "no such counter #{counter_name.inspect}"
      end

      aggregateLevel = opts[:aggregate_level] || counter.level
      perDeviceLevel = opts[:per_device_level] || counter.perDeviceLevel
      {
        :counterId => counter.key,
        :aggregateLevel => aggregateLevel,
        :perDeviceLevel => perDeviceLevel,
      }
    end
  )
end

opts :stats do
  summary "Retrieve performance stats for given object"
  arg :metrics, nil, :type => :string
  arg :obj, nil, :multi => true, :lookup => VIM::ManagedEntity
  opt :samples, "Number of samples to retrieve", :type => :int
  opt :instance, "Specify a particular insance instead of *", :type => :string, :multi => true
end

def stats metrics, objs, opts
  metrics = metrics.split(",")

  vim = single_connection objs
  pm = vim.serviceContent.perfManager
  pc = vim.propertyCollector

  metrics.each do |x|
    err "no such metric #{x}" unless pm.perfcounter_hash.member? x
  end

  interval = pm.provider_summary(objs.first).refreshRate
  start_time = nil
  if interval == -1
    # Object does not support real time stats
    interval = 300
    start_time = Time.now - 300 * 5
  end
  instances = opts[:instance] || ['*']
  if instances.length == 0
    instances << '*'
  end
  stat_opts = {
    :interval => interval,
    :start_time => start_time,
    :instance => instances,
    :multi_instance => true,
  }
  stat_opts[:max_samples] = opts[:samples] if opts[:samples]
  res = pm.retrieve_stats objs, metrics, stat_opts

  table = Terminal::Table.new
  table.add_row ['Object', 'Instance', 'Metric', 'Values', 'Unit']
  table.add_separator
  objs_props = pc.collectMultiple(objs, 'name')
  objs.sort_by{|obj| objs_props[obj]['name']}.each do |obj|
    if !res[obj]
      next
    end
    metrics.each do |metric|
      matches = res[obj][:metrics].select{|k, v| k[0] == metric}
      matches.each do |key, stat|
        key, instance = key
        metric_info = pm.perfcounter_hash[metric]
        table.add_row([objs_props[obj]['name'], instance, metric, stat.join(','), metric_info.unitInfo.label])
      end
    end
  end
  puts table
end

opts :stats_with_timerange do
  summary "Retrieve performance stats for given object"
  arg :metrics, nil, :type => :string
  arg :obj, nil, :multi => true, :lookup => VIM::ManagedEntity
  opt :starttime, "Starting time", :type => :int
  opt :endtime, "Ending tiem", :type => :int
  opt :samples, "Number of samples to retrieve", :type => :int
  opt :instance, "Specify a particular insance instead of *", :type => :string, :multi => true
  opt :outputformat, "specify output format, table or [avgs]", :type => :string
end

def stats_with_timerange metrics, objs, opts
  metrics = metrics.split(",")

  vim = single_connection objs
  pm = vim.serviceContent.perfManager
  pc = vim.propertyCollector
  
  cluster = objs[0].parent
  while not cluster.is_a?(VIM::ClusterComputeResource)
    cluster = cluster.parent
  end
  arr = [cluster.name]
  metrics.each do |x|
    err "no such metric #{x}" unless pm.perfcounter_hash.member? x
    arr << x + "%"
  end

  interval = pm.provider_summary(objs.first).refreshRate
  start_time = Time.at(opts[:starttime]) || nil
  end_time = Time.at(opts[:endtime]) || nil
  if interval == -1
    # Object does not support real time stats
    interval = 300
    start_time = Time.now - 300 * 5
  end
  instances = opts[:instance] || ['*']
  if instances.length == 0
    instances << '*'
  end
  stat_opts = {
    :interval => interval,
    :start_time => start_time,
    :end_time => end_time,
    :instance => instances,
    :multi_instance => true,
  }
  if opts[:samples]
    stat_opts[:max_samples] = opts[:samples] 
  end
  res = pm.retrieve_stats objs, metrics, stat_opts

  table = Terminal::Table.new :title => "Resource Utilization", :headings => arr
  objs_props = pc.collectMultiple(objs, 'name')
  hosts_avg_array = []
  avg_hash = {}
  objs.sort_by{|obj| objs_props[obj]['name']}.each do |obj|
    if !res[obj]
      next
    end
    avg_of_host = 0
    host_arr = [objs_props[obj]['name']]
    metrics.each do |metric|
      matches = res[obj][:metrics].select{|k, v| k[0] == metric}
      matches.each do |key, stat|
        hosts_avg_array << avg_of_host = ((stat.inject(0.0) { |sum, el| sum + el } / stat.size)/100).round(2)
        key, instance = key
        if avg_hash.has_key?(key)
          avg_hash[key] += avg_of_host 
        else
          avg_hash[key] = avg_of_host
        end
        metric_info = pm.perfcounter_hash[metric]
        host_arr << avg_of_host
        #table.add_row([objs_props[obj]['name'], instance, metric, stat.join(','), metric_info.unitInfo.label])
      end
    end
    table.add_row(host_arr)
  end
  avg_row = ['Average']
  arr[1..-1].each do |mtx|
    mtx = mtx[0..-2]
    avg_num = (avg_hash[mtx].to_f/objs.size).round(2)
    avg_row << avg_num
    avg_hash[mtx] = avg_num
  end
  table.add_separator
  table.add_row(avg_row)

  puts table if opts[:outputformat] == "table" or opts[:outputformat] == "both"
  puts avg_hash if opts[:outputformat] == "avgs" or opts[:outputformat] == "both"
end