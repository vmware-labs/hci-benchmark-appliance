class TasksAnalyzer
  attr_accessor :uptime
  attr_reader :taskTotal
  attr_reader :taskSuccess
  attr_reader :taskFailure
  attr_reader :taskStats
  attr_reader :uptime
  attr_reader :exceptionHisto
  attr_reader :allTasks
  
  def initialize opts
    @opts = opts
    @taskTotal = Hash.new(0)
    @taskSuccess = Hash.new(0)
    @taskFailure = Hash.new(0)
    @exceptionHisto = Hash.new(0)

    @startTimestamp = nil
    @lastTimestamp = nil
    @waitStart = nil
    @uptime = 0
    
    # fault_cycles state machine
    #    :ACC_STATS - normal mode, accumulate stats
    # :ACC_NEXT_ONLY - accumulate next trace then transition to :NO_ACC
    # :ACC_NEXT_WAIT - accumulate next trace then transition to :ACC_WAIT
    #       :NO_ACC - don't accumulate stats
    #     :ACC_WAIT - collect stats after waitTime
    @accumulate = :ACC_STATS
    # how long to wait after fault stop before collecting stats
    @waitTime = 600
    
    # workload+taskId -> start time
    @runningTasks = {}
    
    @taskStats = Hash.new(0)
    @allTasks = []                                   
  end

  def taskStatsInit op
    if !@taskStats.has_key? op
      @taskStats[op] = {:success => Stats.new(op),
                        :failure => Stats.new("#{op}.fail"),
                       # fault msg -> number of occurences
                        :faults => Hash.new(0)}
    end
  end

  def processTrace j
    if j.has_key? 'timestamp'
      @startTimestamp ||= j['timestamp']
      @lastTimestamp = j['timestamp']
      @uptime = @lastTimestamp - @startTimestamp
    end

    if j.has_key? 'op' and j['op'].has_key? 'op'
      op = j['op']['op']
      if op == 'RelocateVM'
        hostChange = j['op']['newHost'] != j['op']['oldHost']
        dsChange = j['op']['newDs'] != j['op']['oldDs']
        hot = "Cold-Hot"
        if j['op'].has_key?('isHot')
          hot = j['op']['isHot'] ? "Hot" : "Cold"
        end
        if hostChange && dsChange
          op = "#{hot}-XvMotion"
        elsif dsChange
          op = "#{hot}-SvMotion"
        elsif 
          op = "#{hot}-vMotion"
        end
      end
      taskIdentifier = "#{j['workload']}--#{j['taskId']}" # taskId alone is not unique!
      stateNames = ['vim-task-begin', 'vim-task-success', 'vim-task-exception']
      if op == 'CreateSnapshot' && j['type'] == 'vim-task-exception'
        if j['exception'] && j['exception']['msg'] == "Snapshot not taken since the state of the virtual machine has not changed since the last snapshot operation."
          # This is actually not a bug. This exception is expected, hence rewriting it
          # to make it a success
          $stderr.puts "Rewriting #{op} at #{@lastTimestamp} from exception to success"
          j['type'] = 'vim-task-success'
        end
      elsif op == 'ReconfigVM' && j['type'] == 'vim-task-exception'
        if j['op']['profileEnabled'] && j['op']['profileEnabled'] == true && j['op']['dsType'] && j['op']['dsType'] != 'vsan'
          # This is actually not a bug. This exception is expected, hence rewriting it
          # to make it a success
          $stderr.puts "Rewriting #{op} at #{@lastTimestamp} from exception to success"
          j['type'] = 'vim-task-success'
        end
      end
    elsif j['type'] =~ /vm-wait-for-boot/
      op = 'vm-boot'
      taskIdentifier = "#{j['workload']}" # This is actually not quite unique, which is bad
      stateNames = ['vm-wait-for-boot-begin', 'vm-wait-for-boot-success', 'vm-wait-for-boot-exception']
    elsif j['type'] =~ /vim-ovfdeploy/
      op = 'vim-ovfdeploy'
      taskIdentifier = "#{j['workload']}" # This is actually not quite unique, which is bad
      stateNames = ['vim-ovfdeploy-begin', 'vim-ovfdeploy-success', 'vim-ovfdeploy-exception']
    elsif j['type'] =~ /fault-cycles-run/
      op = 'fault-cycles-run'
      taskIdentifier = "#{j['workload']}" # This is actually not quite unique, which is bad
      stateNames = ['fault-cycles-run-begin', 'fault-cycles-run-success', 'fault-cycles-run-exception']
      if @opts[:faultCycles] == true
        @accumulate = :ACC_NEXT_ONLY
      end
    elsif j['type'] =~ /fault-cycles-sleep/
      op = 'fault-cycles-sleep'
      taskIdentifier = "#{j['workload']}" # This is actually not quite unique, which is bad
      stateNames = ['fault-cycles-sleep-begin', 'fault-cycles-sleep-success', 'fault-cycles-sleep-exception']
      if @opts[:faultCycles] == true && @accumulate == :NO_ACC
        if j['type'] == 'fault-cycles-sleep-begin' 
          @accumulate = :ACC_NEXT_WAIT
          @waitStart = @lastTimestamp
        elsif j['type'] == 'fault-cycles-sleep-exception' 
          @accumulate = :ACC_STATS
        end
      end
    else
      return
    end

    if !op.is_a?(String)
      op = 'undefined'
    end

    if [:ACC_NEXT_ONLY, :ACC_STATS, :ACC_NEXT_WAIT].include?(@accumulate)
      beginState, successState, exceptionState = stateNames
      if j['type'] == beginState
        @taskTotal[op] += 1
        @runningTasks[taskIdentifier] = @lastTimestamp
      elsif j['type'] == successState
        @taskSuccess[op] += 1

        if @runningTasks[taskIdentifier] != nil
          taskStartTime = @runningTasks[taskIdentifier]
          taskDuration = @lastTimestamp - taskStartTime
          taskStatsInit(op)
          @taskStats[op][:success].add(@uptime, taskDuration)

          @allTasks << {
            :duration => taskDuration,
            :startTime => taskStartTime,
            :endTime => @lastTimestamp,
            :op => op,
            :result => "success",
            :id => taskIdentifier
          }
        end
        @runningTasks.delete(taskIdentifier)
      elsif j['type'] == exceptionState
        @taskFailure[op] += 1
        exceptionMsg = nil
        if j['exception']
          exceptionMsg = j['exception']['msg']
          @exceptionHisto[exceptionMsg] += 1
          taskStatsInit(op)
          @taskStats[op][:faults][exceptionMsg] += 1
        elsif j['ex']
          exceptionMsg = j['ex']['class']
          @exceptionHisto[exceptionMsg] += 1
          taskStatsInit(op)
          @taskStats[op][:faults][exceptionMsg] += 1
        end

        if @runningTasks[taskIdentifier] != nil
          taskStartTime = @runningTasks[taskIdentifier]
          taskDuration = @lastTimestamp - taskStartTime
          @runningTasks.delete(taskIdentifier)
          taskStatsInit(op)
          @taskStats[op][:failure].add(@uptime, taskDuration)
          
          @allTasks << {
            :duration => taskDuration,
            :startTime => taskStartTime,
            :endTime => @lastTimestamp,
            :op => op,
            :id => taskIdentifier,
            :result => "fail",
            :exceptionMsg => exceptionMsg,
          }
        end
      end
    end

    if @accumulate == :ACC_NEXT_ONLY
      @accumulate = :NO_ACC
    elsif @accumulate == :ACC_NEXT_WAIT
      @accumulate = :ACC_WAIT
    end
    if @accumulate == :ACC_WAIT
      if (@lastTimestamp - @waitStart) >= @waitTime
        @accumulate = :ACC_STATS
      end
    end
  end

  def empty?
    return @taskTotal.empty?
  end

end
