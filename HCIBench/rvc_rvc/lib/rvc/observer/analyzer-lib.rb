begin
  require 'gnuplot'
rescue LoadError
  $stderr.puts "Couldn't load gnuplot lib"
end

def analyser_lib_dirname
  File.dirname(__FILE__)
end

class Array
  def sum
    inject(0, &:+)
  end
  
  def avg
    l = length
    if l == 0
      0
    else 
      sum / length
    end
  end
end

class Stats
  def initialize(name)
    @total = 0
    @n = 0
    @min = -1
    @max = 0
    @vals = []

    @name = name

    FileUtils.mkdir_p 'stats'
    @filename = "stats/#{name}.stats"
  end

  def write(str)
    f = open(@filename, 'a')
    f.write (str)
    f.close
  end

  def add(x,y)
    @total += y
    @n += 1
    @vals.push(y)
    @min = y if (@min < 0) or (y < @min)
    @max = y if y > @max
    write("#{x}\t#{y}\n")
  end

  def mean
    1.0 * @total / @n
  end

  def to_s
    if @n > 0
      "%.02f" % mean
    else
      "(no data)"
    end
  end

  def close
    @vals.sort! { |a,b| a <=> b }
    @stats = open("stats/#{name}-extra.stats", 'w')
    size = @vals.size - 1
    @stats.write("1\t#{@vals[0]}\t#{@vals[size/10]}\t#{@vals[(size*9)/10]}\t#{@vals[size]}\t#{1.0 * @total / @n}\n")
    @stats.close
    return if (@n == 0)
    gnuplotCmds = "
binwidth=3
bin(x,width)=width*floor(x/width)

set term png size 1024,768
set ylabel 'Number of tasks'
set xlabel 'Task duration (sec)'

set output '#{histofile}'
plot 'stats/#{name}.stats' using (bin(\$2,binwidth)):(1.0) smooth freq with boxes title '#{name}'

set ylabel 'Task duration (sec)'
set xlabel 'Uptime (sec)'

set output '#{scatterfile}'
set size 0.9, 1.0
set origin 0.0, 0.0
set multiplot
plot 'stats/#{name}.stats' using 1:2 w points title '#{name}'
set size 0.15, 0.95
set origin 0.85, 0.05
#set yrange [0:#{@vals.last}]
unset ylabel
unset xlabel
#unset ytics
unset xtics
set boxwidth 0.0025
plot 'stats/#{name}-extra.stats' using 1:3:2:5:4 w candlesticks lt 1 lw 2 notitle whiskerbars, \
     '' using 1:6:6:6:6 w candlesticks lt -1 lw 2 notitle
unset multiplot
"
    IO.popen('gnuplot', 'w') { |f| f.write(gnuplotCmds) }
  end

  def histofile
    "stats/#{name}.histogram.png"
  end

  def scatterfile
    "stats/#{name}.scatter.png"    
  end

  attr_reader :total, :n, :min, :max, :name
end


class TableEmitter
  def initialize(*headings)
    @headings = headings
    @numColumns = headings.length
    @html = ""
    yield self
    
  end

  def row(cells, opts = {})
    @html << "<tr"
    if opts[:id]
      @html << " id=\"#{opts[:id]}\""
    end
    if opts[:ngshow]
      @html << " ng-show=\"#{opts[:ngshow]}\""
    end
    @html << " style=\"padding-bottom: 5px "
    if opts[:hide]
      @html << "; display: none"
    end
    @html << "\">"

    cells.each_with_index do |c, i|
      x = ""
      s = ""
      if i == 0 && !opts[:no_left_heading]
        s = "#{s}width: 190px;"
      end
      if cells.length < @numColumns && i == cells.length - 1
        x = "#{x}colspan=\"#{@numColumns - cells.length}\" "
      end
      @html << "<td style=\"padding-right: 15px; #{s}\" valign=\"top\" #{x}>#{c}</td>"
    end
    @html << "</tr>"
  end
  
  def generate(showheadings = true)
    html = @html
    @html = ""
    @html << "<table class=\"graphgrid\" style=\"text-align: left;\">"
    if showheadings
      @html << "<tr>"
      @headings.each do |h|
        @html << "<th style=\"padding-right: 15px;\">#{h}</th>"
      end
      @html << "</tr>"
    end
    @html << html
    
    @html << "</table>"  
  end
end

def var(k)
  k.gsub('-','_')
end
