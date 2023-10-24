var dateFilterStart = null
var dateFilterEnd = null
var graphs = []

function setTimeFilter(start, end)
{
  dateFilterStart = new Date((start - 65) * 1000)
  dateFilterEnd = new Date((end + 65) * 1000)
}

// Refresh the vsansparse tab, because other tabs will remove it's SVG elements
function vsansparseTabRefresh()
{
  var scope = angular.element($("body")).scope();
  scope.$apply(function(){
      if (scope.forceVsanupdate){
        scope.forceVsanupdate();
      }
    });
}

function getParameterByName(name)
{
  name = name.replace(/[\[]/, "\\\[").replace(/[\]]/, "\\\]");
  var regexS = "[\\?&]" + name + "=([^&#]*)";
  var regex = new RegExp(regexS);
  var results = regex.exec(window.location.search);
  if(results == null)
    return "";
  else
    return decodeURIComponent(results[1].replace(/\+/g, " "));
}

function convertInputs(rawdata, stat, valueType, func) {
    var out = []
    var statsdata = rawdata[stat]
    for (var i = 0; i < statsdata['times'].length; i++) {
        val = func(statsdata[valueType][i])
        time = statsdata['times'][i] * 1000
        out.push({
            'value': val,
            'date': new Date(time),
            'y0': 0,
            'y': val,
        })
    }
    out.sort(function(a,b){
        return a.date - b.date
    })
    return out
}

function computeRcHitRate(readData, rcReadData) {
    var out = []
    for (var i = 0; i < readData.length; i++) {
        if (readData[i].value == 0) {
            val = 100
        } else {
            val = rcReadData[i].value * 100 / readData[i].value;
        }
        out.push({
            'value': val,
            'date': readData[i].date,
            'y0': 0,
            'y': val,
        })
    }
    return out
}

function computeLatency(totalTimeData, countData) {
    return computeRatio(totalTimeData, [ countData ], 0, false);
}

// Comput ratio of 2 data points, optionally adds them both together and convert
// into a percent if doPercentTotal is true.
function computeRatio(numeratorData, denominatorDatas, zeroValue, doPercentTotal) {
    var out = []
    for (var i = 0; i < numeratorData.length; i++) {
        denominator = 0;
        for (var d =0; d < denominatorDatas.length; d++) {
           denominator += denominatorDatas[d][i].value
        }
        if (doPercentTotal) {
           denominator /= 100;
        }

        if (denominator == 0) {
            val = zeroValue
        } else {
            val = numeratorData[i].value / denominator;
        }
        out.push({
            'value': val,
            'date': numeratorData[i].date,
            'y0': 0,
            'y': val,
        })
    }
    return out
}

function computeCbrcHitRate(readData, missReadData) {
    var out = []
    for (var i = 0; i < readData.length; i++) {
        if (readData[i].value == 0) {
            val = 100
        } else {
            val = 100 - (missReadData[i].value * 100 / readData[i].value);
        }
        out.push({
            'value': val,
            'date': readData[i].date,
            'y0': 0,
            'y': val,
        })
    }
    return out
}

function computeDataSum(datas) {
    var out = []
    for (var i = 0; i < datas[0].length; i++) {
        val = 0
        for (var j = 0; j < datas.length; j++) {
            val = val + datas[j][i].value
        }
        out.push({
            'value': val,
            'date': datas[0][i].date,
            'y0': 0,
            'y': val,
        })
    }
    return out
}

function compressTimeSeriesData(data, desiredDataPoints) {
    if (data.length <= desiredDataPoints) {
        return data
    }
    var batchSize = Math.ceil(data.length / desiredDataPoint)
    var out = []
    for (var i = 0; i < data.length; i++) {
        val = 0
        count = 0
        date = data[i].date
        while (count < batchSize && i < data.length) {
            val += data[i].value
            count++
            i++
        }
        val = val / count
        out.push({
            'value': val,
            'date': date,
            'y0': 0,
            'y': val,
        })
    }
    return out
}

function computeLatencyAvgs(latDatas, ioDatas) {
    var out = []
    for (var i = 0; i < latDatas[0].length; i++) {
        var ioSum = 0
        var latSum = 0
        for (var j = 0; j < latDatas.length; j++) {
            latSum = latSum + (latDatas[j][i].value * ioDatas[j][i].value)
            ioSum = ioSum + ioDatas[j][i].value
        }
        var val = 0
        if (ioSum > 0) {
            val = latSum / ioSum
        }
        out.push({
            'value': val,
            'date': latDatas[0][i].date,
            'y0': 0,
            'y': val,
        })
    }
    return out
}

function computeStdDeviation(avgs, sqAvgs) {
    var out = []
    for (var i = 0; i < avgs.length; i++) {
        var lat = avgs[i].value * 1000;
        var sq = sqAvgs[i].value * 1000;
        var diff = sq - lat * lat
        var val = Math.sqrt(diff) / 1000;
        if (isNaN(val)) {
          val = 0
        }
        out.push({
            'value': val,
            'date': avgs[i].date,
            'y0': 0,
            'y': val,
        })
    }
    return out
}

function findThresholdViolations(data, threshold) {
    var violations = []
    var start = null
    var last = null
    for (var key in data) {
        if (data[key].value > threshold) {
            if (start == null) {
                start = data[key].date;
            }
            last = data[key].date;
        } else {
            if (start != null && last - start >= 3 * 60 * 1000) {
                violations.push([start, last, last - start])
            }
            start = null;
            last = null;
        }
    }
    if (start != null && last - start >= 3 * 60 * 1000) {
        violations.push([start, last, last - start])
    }
    return violations;
}

function countThresholdViolations(data, threshold) {
    var violations = []
    var count = 0
    for (var key in data) {
        if (data[key].value > threshold) {
            count++
        }
    }
    return count * 100 / data.length;
}

function renderGraphs(rawdata, addControls, width, height, graphSpecs) {

    //boilderplate, set margins of graph
    var margin = {top: 20, right: 0, bottom: 20, left: 30};
    if (addControls) {
        margin.right += 160;
        margin.left += 10;
    }
    width = width - margin.left - margin.right,
    height = height - margin.top - margin.bottom;

    if (dateFilterStart && dateFilterEnd) {
      for (var key in graphSpecs) {
        for (var dataIdx in graphSpecs[key][3]) {
          var data = graphSpecs[key][3][dataIdx]
          var newdata = []
          for (var i in data) {
            if (data[i].date >= dateFilterStart &&
                data[i].date <= dateFilterEnd) {
               newdata.push(data[i])
            }
          }
          graphSpecs[key][3][dataIdx] = newdata
        }
      }
    }
//    console.log(rawdata)

    var healthtable = d3.select(".healthtable")
    healthtable.selectAll("tr").remove();

    function postHealth(label, unit, threshold, data) {
        var violations = findThresholdViolations(data, threshold)
        var healthTr = healthtable.append("tr")
        if (violations.length == 0) {
            healthTr.append("td").append("i")
                .attr("class", "icon-thumbs-up")
                .attr("style", "color: green")
            healthTr.append("td")
                .text(label)
        } else {
            txt = label + " above " + threshold + unit
            healthTr.append("td").append("i")
                .attr("class", "icon-thumbs-down")
                .attr("style", "color: #E60000")
            healthTr.append("td")
                .text(txt)
        }
    }

    //horizontal and vertical scales to map to svg area
    var x = d3.time.scale()
        .range([0, width]);
    var y = d3.scale.linear()
        .range([height, 0]);
    var z = d3.scale.category10();

    //set domain for the D3 interpolator
    ////d3 extent returs the min and max value of an array
    data = graphSpecs[0][3][0]
    x.domain(d3.extent(data, function(d) { return d.date; }));
    var xAxis = d3.svg.axis()
        .scale(x)
        .ticks(width / 50)
        .orient("bottom");
        //.ticks(d3.time.minutes,20); //where you should have tick marks


    var update_mousemove =  function(mouse_x){
        var selectedTime = x.invert(mouse_x - margin.left);
        var mappedIndex = 0
        var firstGraph = graphs[Object.keys(graphs)[0]]
        for (var v in firstGraph.datas[0]) {
            var d = firstGraph.datas[0][v].date
            if (d >= selectedTime) {
                break;
            }
            mappedIndex++;
        }

        //check to make sure that mouse on the the graph range
        if (mappedIndex < 0 || mappedIndex >= firstGraph.datas[0].length){
            for (var key in graphs) {
                var graph = graphs[key]
                graph.focus.attr("display","none");
            }
            return;
        }
        var mappedTime = firstGraph.datas[0][mappedIndex].date;
        for (var key in graphs) {
            var graph = graphs[key]
            mappedIndex = 0
            for (var v in graph.datas[0]) {
                var d = graph.datas[0][v].date
                if (d >= selectedTime) {
                    break;
                }
                mappedIndex++;
            }
            if (mappedIndex >= graph.datas[0].length) {
                mappedIndex = graph.datas[0].length - 1
            }
            var mappedTime = graph.datas[0][mappedIndex].date;

            var mappedHeight = 0

            //show draw line
            graph.focus.attr("display","show");

            for (var i in graph.datas) {
                mappedHeight = Math.max(
                    mappedHeight,
                    graph.datas[i][mappedIndex].value
                );

                graph.focus.select(".circle" + i)
                    .attr("cx", x(mappedTime))
                    .attr("cy", graph.y(graph.datas[i][mappedIndex].value));
                graph.legend.select(".label" + i)
                    .text(graph.datas[i][mappedIndex].value.toFixed(2))
            }
            graph.svg.select(".xLine")
                .attr("transform","translate(" + x(mappedTime)+",0)")
                .attr("y1", graph.y(mappedHeight));
         }
    }

    var mousemove = function(){
        //caculate the offset index
        update_mousemove(d3.mouse(this)[0])
    }

    function mouseover() {
      for (var key in graphs) {
        graph = graphs[key]
        if (graph != null) {
          graph.focus.attr("display", "show")
        }
      }
    }

    function mouseout() {
      for (var key in graphs) {
        graph = graphs[key]
        if (graph != null) {
          graph.focus.attr("display", "none")
        }
      }
    }

    function addGraph(key, title, aname,
                      divselect, width, height, datas,
                      labels, yMax, addControls,
                      violationPct, adjustLegendWidth)
    {
        var rootdiv = d3.select(escapeColon(divselect))
        if (rootdiv.length == 1 && rootdiv[0][0] == null) {
          console.log("Missing div '" + divselect + "' can't draw graph")
          return;
        }
        rootdiv.select("svg").remove();

        var legendYSpace = 22
        var legendLabelLengthPx = 140
        if (addControls && legendYSpace * labels.length > height) {
            height = legendYSpace * labels.length + 30
            rootheight = height + margin.top + margin.bottom
            rootdiv.attr("style", "height: "+rootheight+"px")
            var maxLabelLength = 0
            for (var i in labels) {
              maxLabelLength = Math.max(maxLabelLength, labels[i].length)
            }
            if (maxLabelLength > 15) {
              var additional = (maxLabelLength - 15) * 5
              width -= additional
              margin.right += additional
              legendLabelLengthPx += additional
            }
        } else if(adjustLegendWidth) {
          // Hack to adjust width for label names that are too long
          var maxLabelLength = 0
          for (var i in labels) {
            maxLabelLength = Math.max(maxLabelLength, labels[i].length)
          }
          if (maxLabelLength > 15) {
            var additional = (maxLabelLength - 15) * 5
            width -= additional
            margin.right += additional
            legendLabelLengthPx += additional
          }
       }

        if (yMax == null) {
            yMax = 0.0
            for (var i in datas) {
                yMax1 = d3.max(datas[i], function(d) { return d.y0 + d.y; });
                yMax = Math.max(yMax, yMax1);
            }
        }
        var y_graph = d3.scale.linear()
            .range([height, 0])
            .domain([0, yMax]);

        var yAxis_graph = d3.svg.axis()
            .scale(y_graph)
            .ticks(height / 20)
            .tickFormat(d3.format("s"))
            .orient("left");

        var area_graph = d3.svg.line()
            .interpolate("linear")
            .x(function(d) { return x(d.date); })
            .y(function(d) { return y_graph(d.value); });

        if (!addControls && violationPct != null) {
            var healthColor = "green"
            if (violationPct > 20.0) {
              healthColor = "red"
            }
            if (violationPct == -1) {
              healthColor = "unsure"
            }
            rootdiv.attr("class", rootdiv.attr("class") + " state " + healthColor)
        }

        rootdiv.append("a")
            .attr('name', aname)

        var svg_graph = rootdiv.append("svg")
            .attr("width", width + margin.left + margin.right)
            .attr("height", height + margin.top + margin.bottom)
            .on('mousemove', mousemove)
            .on('mouseover', function(){ mouseover(); })
            .on('mouseout', function(){ mouseout(); })
          .append("g")
            .attr("transform",
                  "translate(" + margin.left + "," + margin.top + ")")

        for (var i in datas) {
            svg_graph.selectAll(".layer")
                .data(i)
              .enter().append('path')
                .attr("class", "line")
                .attr("stroke", z("color" + i))
                .attr("d", function(d) { return area_graph(datas[i]); });
        }

        var focus_graph = svg_graph.append('g')
            .attr("class","focus");
        // XXX: classes
        focus_graph.append("line")
            .attr("class", "xLine")
            .attr("y1", 0)
            .attr("y2", height)
            .attr("opacity", 0.5)
            .attr("stroke", "#fff")
            .attr("stroke-width","1px");
        for (i in datas) {
            focus_graph.append("circle")
                .attr("class","circle" + i)
                .attr("r",2)
                .attr("fill", "none")
                .attr("stroke","white")
                .attr("opacity", 0.5)
                .attr("stroke-width", 2);
        }

        //draw x axis
        svg_graph.append("g")
          .attr("class", "x axis")
          .attr("transform", "translate(0," + height + ")")
          .call(xAxis);

        //draw yaxis
        svg_graph.append("g")
          .attr("class", "y axis")
          .call(yAxis_graph);

        var legend = svg_graph.append("g")
            .attr("class","legend")
            .attr("transform", "translate(" + (width + 10) + ",0)")

        if (addControls) {
            for (i in labels) {
                var legend_entry = legend.append("g")
                    .attr("transform", "translate(10," + (i * legendYSpace) + ")")
                legend_entry.append("rect")
                    .attr("width", 15)
                    .attr("height", 15)
                    .attr("fill", z("color" + i)); // XXX: disk
                legend_entry.append("text")
                    .attr("x",18)
                    .attr("y", 13)
                    .text(labels[i])
                    .attr("fill", "white")
                    .attr("font-weight", "100");

                legend_entry.append("text")
                    .attr("class", "label" + i)
                    .attr("fill", "white")
                    .attr("font-size", "20px")
                    .attr("font-weight", 200)
                    .attr("opacity", "0.8")
                    .attr("x", legendLabelLengthPx)
                    .attr("text-anchor","end")
                    .attr("y", 13)
                    .text("")
            }
        }

        var title_g = null
        if (addControls) {
          title_g = svg_graph.append("g")
              .attr("class", "title")
              .attr("transform", "translate(10,0)")
        } else {
          title_g = svg_graph.append("g")
              .attr("class", "title")
              .attr("transform", "translate(0,-7)")
        }
        title_g.append("text")
            .attr("fill", "white")
            .attr("font-size", "13px")
            .attr("font-weight", 200)
            .attr("opacity", ".8")
            .attr("x", 0)
            .attr("y", 0)
            .text(title)

        function promtForMaxY(x) {
            var res = prompt("Enter maximum value (empty means auto)", "");
            if (res == "") {
                res = null;
            }
            graphs[divselect] = addGraph(key, title, aname,
                divselect, width, height, datas,
                labels, res, addControls,
                violationPct
            );
        }

        if (addControls) {
            var resize_y = legend.append("g")
                .attr("class","overhead")
                .attr("transform", "translate(10," + (labels.length) * legendYSpace + " )")
                .on("click", promtForMaxY)
            resize_y.append("rect")
                .attr("width", 15)
                .attr("height", 15)
                .attr("fill", "white");
            resize_y.append("text")
                .attr("x",18)
                .attr("y", 13)
                .text("Set max y-Axis")
                .attr("fill", "white")
                .attr("font-weight", "100");
        }

        return {'svg': svg_graph, 'focus': focus_graph, 'legend': legend,
                'datas': datas,
                'y': y_graph,
                'divselect': divselect};
    }

    //postHealth("Read latency", "ms", 20, latencyData['read'])
    //postHealth("Write latency", "ms", 20, latencyData['write'])


    for (var key in graphSpecs) {
        var spec = graphSpecs[key]
        var datas = spec[3]
        //datas = compressTimeSeriesData(spec[3], width)
        var graphTmp = addGraph(key,
            spec[0], spec[1],
            spec[2], width, height,
            datas, spec[4],
            spec[5], addControls,
            spec[6], spec[7]
        )
        if (graphTmp) {
          graphs[graphTmp.divselect] = graphTmp
        }
    }
//    console.log(graphs)
}


function convertMemStatsInputs(rawdata) {
    var out = []
    var statsdata = rawdata
    for (var i = 0; i < statsdata['times'].length; i++) {
        val = statsdata['values'][i]
        time = statsdata['times'][i] * 1000
        out.push({
            'value': val,
            'date': new Date(time),
            'y0': 0,
            'y': val,
        })
    }
    out.sort(function(a,b){
        return a.date - b.date
    })
    return out
}

function computeMemGraphSpecs(rawdata, prefix) {
  var graphSpecs = []
  var names = Object.keys(rawdata['stats'])
  for (var i in names) {
    var name = names[i]
    slabs = Object.keys(rawdata['stats'][name])
    var lineDatas = []
    var labels = []
    var violations = -1
    for (var j in slabs) {
      slab = slabs[j]
      data = convertMemStatsInputs(rawdata['stats'][name][slab])

      lineDatas.push(data)
      labels.push(slab)

      if (name == "congestion") {
        violations = Math.max(
          violations,
          countThresholdViolations(data, 75)
        )
      }
    }

    graphSpecs.push([name, name,
      prefix + "-" + name,
      lineDatas, labels,
      100,
      violations]
    )
  }
  return graphSpecs
}

function computePcpuGraphSpecs(rawdata, prefix) {
    pcpus = Object.keys(rawdata['stats'])
    var pcpuData = []
    var labels = []
    for (var i in pcpus) {
        pcpu = pcpus[i]
        pcpuData.push(convertInputs(rawdata['stats'][pcpu],
            'usedPct', 'values',
            function(v) { return v }
        ))
        labels.push(pcpu)
    }
    var graphSpecs = [
        ["All PCPUs", "pcpus",
         prefix + "-pcpus",
         pcpuData,
         labels,
         100,
         0],
    ]
    return graphSpecs
}

function computeWdtGraphSpecs(rawdata, prefix) {
    return computeWdtGraphSpecsInt(rawdata, prefix, false);
}

function computeWdtGraphSpecsThumb(rawdata, prefix) {
    return computeWdtGraphSpecsInt(rawdata, prefix, true);
}

function computeWdtGraphSpecsInt(rawdata, prefix, thumb) {
    var keys = ['runTime', 'readyTime', 'overrunTime']
    var data = []
    var labels = []
    for (var i in keys) {
        key = keys[i]
        data.push(convertInputs(rawdata['stats'],
            key, 'avgs',
            function(v) { return v * 100 }
        ))
        labels.push(key)
    }
    var graphSpecs = []
    if (!thumb) {
        graphSpecs = [
            [rawdata['wdt'].replace("VSAN_", ""), "wdt",
             prefix,
             data,
             labels,
             100],
        ]
    } else {
        graphSpecs = [
            [rawdata['wdt'].replace("VSAN_", ""), "wdt",
             prefix,
             [data[0]],
             [labels[0]],
             100,
             countThresholdViolations(data[0], 80)],
        ]
    }
    return graphSpecs
}


function computeWdtSumGraphSpecs(rawdata, prefix) {
    return computeWdtSumGraphSpecsInt(rawdata, prefix, false);
}

function computeWdtSumGraphSpecsThumb(rawdata, prefix) {
    return computeWdtSumGraphSpecsInt(rawdata, prefix, true);
}

function computeWdtSumGraphSpecsInt(rawdata, prefix, thumb) {
    var keys = ['runTime', 'readyTime', 'overrunTime']
    var data = []
    var labels = []
    for (var i in keys) {
        key = keys[i]
        data.push(convertInputs(rawdata['stats'],
            key, 'avgs',
            function(v) { return v }
        ))
        labels.push(key)
    }
    var graphSpecs = []
    if (!thumb) {
        graphSpecs = [
            ["VSAN (num core)", "wdt",
             prefix + "-wdt",
             data,
             labels,
             null],
        ]
    } else {
        graphSpecs = [
            ["VSAN (num core)", "wdt",
             prefix + "-wdt",
             [data[0]],
             [labels[0]],
             null,
             0],
        ]
    }
    return graphSpecs
}


function computeHelperWorldGraphSpecs(rawdata, prefix) {
    return computeHelperWorldGraphSpecsInt(rawdata, prefix, false);
}

function computeHelperWorldGraphSpecsThumb(rawdata, prefix) {
    return computeHelperWorldGraphSpecsInt(rawdata, prefix, true);
}

function computeHelperWorldGraphSpecsInt(rawdata, prefix, thumb) {
    var keys = ['usedTime', 'readyTime']
    var data = []
    var labels = []
    for (var i in keys) {
        key = keys[i]
        data.push(convertInputs(rawdata['stats'],
            key, 'avgs',
            function(v) { return v * 100 }
        ))
        labels.push(key)
    }
    var graphSpecs = []
    if (!thumb) {
        graphSpecs = [
            [rawdata['helperworld'], "helperworld",
             prefix + "-helperworld",
             data,
             labels,
             100],
        ]
    } else {
        graphSpecs = [
            [rawdata['helperworld'], "helperworld",
             prefix + "-helperworld",
             [data[0]],
             [labels[0]],
             100,
             countThresholdViolations(data[0], 80)],
        ]
    }
    return graphSpecs
}


function computeHelperWorldSumGraphSpecs(rawdata, prefix) {
    return computeHelperWorldSumGraphSpecsInt(rawdata, prefix, false);
}

function computeHelperWorldSumGraphSpecsThumb(rawdata, prefix) {
    return computeHelperWorldSumGraphSpecsInt(rawdata, prefix, true);
}

function computeHelperWorldSumGraphSpecsInt(rawdata, prefix, thumb) {
    var keys = ['usedTime', 'readyTime']
    var data = []
    var labels = []
    for (i in keys) {
        key = keys[i]
        data.push(convertInputs(rawdata['stats'],
            key, 'avgs',
            function(v) { return v }
        ))
        labels.push(key)
    }
    var graphSpecs = []
    if (!thumb) {
        graphSpecs = [
            ["VSAN HW (num core)", "helperworld",
             prefix + "-helperworld",
             data,
             labels,
             null],
        ]
    } else {
        graphSpecs = [
            ["VSAN HW (num core)", "helperworld",
             prefix + "-helperworld",
             [data[0]],
             [labels[0]],
             null,
             0],
        ]
    }
    return graphSpecs
}

function computeVscsiGraphSpecs(rawdata, prefix) {
    return computeVscsiGraphSpecsInt(rawdata, prefix, false);
}

function computeVscsiGraphSpecsThumb(rawdata, prefix) {
    return computeVscsiGraphSpecsInt(rawdata, prefix, true);
}

function computeVscsiGraphSpecsInt(rawdata, prefix, thumb) {
    var data = {}
    data['latencyReads'] = convertInputs(rawdata['stats'],
      'latencyReads', 'avgs',
      function(v) { return v / 1000 }
    )
    data['latencyWrites'] = convertInputs(rawdata['stats'],
      'latencyWrites', 'avgs',
      function(v) { return v / 1000 }
    )
    data['numReads'] = convertInputs(rawdata['stats'],
      'numReads', 'avgs',
      function(v) { return v }
    )
    data['numWrites'] = convertInputs(rawdata['stats'],
      'numWrites', 'avgs',
      function(v) { return v }
    )
    data['bytesRead'] = convertInputs(rawdata['stats'],
      'bytesRead', 'avgs',
      function(v) { return v / 1024 }
    )
    data['bytesWrite'] = convertInputs(rawdata['stats'],
      'bytesWrite', 'avgs',
      function(v) { return v / 1024 }
    )
    var graphSpecs = []
    if (!thumb) {
        graphSpecs = [
            ["Latency", "latency",
             prefix + "-latency",
             [data['latencyReads'], data['latencyWrites']],
             ['Read Latency', 'Write Latency'],
             null,
             countThresholdViolations(data['latencyReads'], 30)],
            ["IOPS", "iops",
             prefix + "-iops",
             [data['numReads'], data['numWrites']],
             ['Read IOPS', 'Write IOPS'],
             null,
             0],
            ["Tput", "tput",
             prefix + "-tput",
             [data['bytesRead'], data['bytesWrite']],
             ['Read Tput', 'Write Tput'],
             null,
             0],
         ]
    } else {
      data["latency"] = computeLatencyAvgs(
        [
            data['latencyReads'],
            data['latencyWrites'],
        ],
        [
            data['numReads'],
            data['numWrites'],
        ]
      )
      data["iops"] = computeDataSum(
        [
            data['numReads'],
            data['numWrites'],
        ]
      )
      data["tput"] = computeDataSum(
        [
            data['bytesRead'],
            data['bytesWrite'],
        ]
      )
        graphSpecs = [
            ["Latency", "latency",
             prefix + "-latency",
             [data['latency']],
             ['Latency'],
             null,
             countThresholdViolations(data['latency'], 30)],
            ["IOPS", "iops",
             prefix + "-iops",
             [data['iops']],
             ['IOPS'],
             null,
             0],
            ["Tput", "tput",
             prefix + "-tput",
             [data['tput']],
             ['Tput'],
             null,
             0],
        ]
    }
    return graphSpecs
}


function computeIoAmpGraphSpecs(rawdata, prefix) {
    return computeIoAmpGraphSpecsInt(rawdata, prefix, false);
}

function computeIoAmpGraphSpecsThumb(rawdata, prefix) {
    return computeIoAmpGraphSpecsInt(rawdata, prefix, true);
}

function computeIoAmpGraphSpecsInt(rawdata, prefix, thumb) {
    var data = {}
    data['numReads'] = convertInputs(rawdata['stats'],
      'numReads', 'values',
      function(v) { return v }
    )
    data['numWrites'] = convertInputs(rawdata['stats'],
      'numWrites', 'values',
      function(v) { return v }
    )
    data['bytesRead'] = convertInputs(rawdata['stats'],
      'bytesRead', 'values',
      function(v) { return v }
    )
    data['bytesWrite'] = convertInputs(rawdata['stats'],
      'bytesWrite', 'values',
      function(v) { return v }
    )
    var graphSpecs = []
    if (!thumb) {
        graphSpecs = [
            ["IOPS Factor", "iops",
             prefix + "-iops",
             [data['numReads'], data['numWrites']],
             ['Read IOPS', 'Write IOPS'],
             null,
             0],
            ["Tput Factor", "tput",
             prefix + "-tput",
             [data['bytesRead'], data['bytesWrite']],
             ['Read Tput', 'Write Tput'],
             null,
             0],
         ]
    } else {
      // XXX
    }
    return graphSpecs
}

function computeSSDGraphSpecs(rawdata, prefix) {
  return computeSSDGraphSpecsInt(rawdata, prefix, false);
}

function computeSSDGraphSpecsThumb(rawdata, prefix) {
  return computeSSDGraphSpecsInt(rawdata, prefix, true);
}

function computeSSDGraphSpecsInt(rawdata, prefix, thumb) {
    var data = {}
    var datas = []
    var labels = []
    var types = {
      "wbFillPct": "WB Fill Pct",
      "llogLogSpace": "LLOG Log Space",
      "llogDataSpace": "LLOG Data Space",
      "plogLogSpace": "PLOG Log Space",
      "plogDataSpace": "PLOG Data Space",
    }
    for (var key in types) {
      labels.push(types[key])
      data[key] = convertInputs(rawdata['stats'],
          key, 'values',
          function(v) { return v }
      )
      datas.push(data[key])
    }
    var graphSpecs = null;
    if (!thumb) {
      graphSpecs = [
          ["WriteBuffer", "wbfill",
           prefix + "-wb",
           datas,
           labels,
           100,
           countThresholdViolations(data['wbFillPct'], 75)],
      ]
    } else {
      graphSpecs = [
          ["WriteBuffer Fill", "wbfill",
           prefix + "-wb",
           [data['wbFillPct']],
           ["WriteBuffer Fill Pct"],
           100,
           countThresholdViolations(data['wbFillPct'], 75)],
      ]
    }
    return graphSpecs
}

function computeVsansparseGraphSpecsThumb(rawdata, prefix) {
    return computeVsansparseGraphSpecsInt(rawdata, prefix, true)
}

function computeVsansparseGraphSpecs(rawdata, prefix) {
    return computeVsansparseGraphSpecsInt(rawdata, prefix, false)
}

function computeVsansparseGraphSpecsInt(rawdata, prefix, isThumb) {
    var data = {}
    var types = [
      //io stats
      "writes",
      "reads",
      "writeBytes",
      "readBytes",
      "lookups",
      "writeTimeUsec",
      "readTimeUsec",
      "cacheLookupTimeUsec",
      "cacheUpdateTimeUsec",
      "splitReads",
      "maxWriteTimeUsec",
      "splitLookupTimeUsec",
      "splitLookups",
      "maxReadTimeUsec",
      "lookupTimeUsec",
      "inserts",
      "hits",
      "evictions",
      "removes",
      "lruUpdates",
      "lruLockContentions",
      "lockContentions",
      "attemptedEvictions",
      "misses",
      "entries",
      "allocFailures"]

        for (var x in types) {
          var type = types[x]
            if (/Usec$/.test(type)) {
               data[type.replace("Usec", "Msec")] = convertInputs(rawdata['stats'],
                   type, 'avgs',
                   function(v) { return v / 1000 }
                   )
            } else if (/Bytes$/.test(type)) {
               data[type.replace("Bytes", "KBytes")] = convertInputs(rawdata['stats'],
                   type, 'avgs',
                   function(v) { return v / 1024 }
                   )
            } else {
               data[type] = convertInputs(rawdata['stats'],
                   type, 'avgs',
                   function(v) { return v }
                   )
            }

        }

    data['writeLatAvg'] = computeLatency(data['writeTimeMsec'], data['writes'])
    data['readLatAvg'] = computeLatency(data['readTimeMsec'], data['reads'])

    data['lookupLatAvg'] = computeLatency(data['lookupTimeMsec'], data['lookups'])
    data['cacheLookupTimeMsecAvg'] = computeLatency(data['cacheLookupTimeMsec'], data['reads'])
    data['cacheUpdateTimeMsecAvg'] = computeRatio(data['cacheUpdateTimeMsec'],
                                                  [
                                                     data['writes'], data['lookups']
                                                  ], 0, false)
    data['splitLookupLatAvg'] = computeLatency(data['splitLookupTimeMsec'], data['splitLookups'])

    data['fragmentation'] = computeRatio(data['splitReads'], [ data['reads'] ] , 1, false)
    data['cacheHitRate'] = computeRatio(data['hits'], [
                                                         data['misses'], data['hits']
                                                      ], 1, true)

    var graphSpecs = [
      ["IOps", "iocounts",
        prefix + "-iocounts",
        [data['reads'], data['writes'], data['lookups']],
        ["Reads", "Writes", "GWE"],
        null, -1],

      ["Read amplification", "layer",
        prefix + "-layer",
        [data['fragmentation']],
        ["Reads to layer"],
        null, -1],

      ["Cache", "cache",
        prefix + "-cache",
        [data['inserts'], data['removes'], data['entries'], data['allocFailures'], data['attemptedEvictions']],
        ["Inserts", "Removes", "Entries", "Allocation fail", "Eviction attempts" ],
        null, -1],
    ]

    nonThumbSpecs = [
      ["Latency (ms)", "iolatency",
        prefix + "-iolatency",
        [data['readLatAvg'], data['writeLatAvg'], data['lookupLatAvg'], data['cacheLookupTimeMsecAvg'], data['cacheUpdateTimeMsecAvg']],
        ["Read", "Write", "GWE", "Cache Lookup", "Cache Update" ],
        null, -1],

      ["Throughput (KB)", "iobytes",
        prefix + "-iobytes",
        [data['readKBytes'], data['writeKBytes']],
        ["Reads", "Writes"],
        null, -1],


      ["Cache Access", "cachehits",
        prefix + "-cachehits",
        [data['cacheHitRate']],
        ["Hit %"],
        null, -1],

      ["Lock Contentions", "locks",
        prefix + "-locks",
        [data['lruLockContentions'], data['lockContentions']],
        ["lru", "cache"],
        null, -1],
      ]

    if (!isThumb) {
      graphSpecs = graphSpecs.concat(nonThumbSpecs)
    }


    return graphSpecs
}

function computeVirstoGraphSpecs(rawdata, prefix) {
    var data = {}
    var types = [
      "mbValid",
      "mbInvalid",
      "mbDirty",
      "mbFree",
      "mbcHits",
      "mbcEvictions",
      "mbcMisses",
      "mfRuns",
      "mfPendingMetadata",
      "heapUtilization",
      "mfMetadataPerRun"
    ]

    for (var i in types) {
      var key = types[i]
      data[key] = convertInputs(rawdata['stats'],
          key, 'avgs',
          function(v) { return v }
      )
    }

    var graphSpecs = [
      ["Map Blocks", "mbcounters",
       prefix + "-mbcounters",
       [data['mbValid'], data['mbInvalid'], data['mbDirty'], data['mbFree']],
       ["Valid", "Invalid", "Dirty", "Free"],
       null, -1],

      ["Map Block Cache", "mbcache",
       prefix + "-mbcache",
       [data['mbcHits'], data['mbcMisses'], data['mbcEvictions']],
       ["Hits/sec", "Misses/sec", "Evictions/sec"],
       null, -1],

      ["Metadata Flusher", "mf",
       prefix + "-mf",
       [data['mfRuns'], data['mfMetadataPerRun'], data['mfPendingMetadata']],
       ["Runs/sec", "Flushed/Run (KB)", "Pending buffers (KB)"],
       null, -1],

      ["Virsto Instance", "vi",
       prefix + "-vi",
       [data['heapUtilization']],
       ["HeapUsed (KB)"],
       null, -1],

    ]
    return graphSpecs
}

function computeCFGraphSpecs(rawdata, prefix) {
    var data = {}
    var types = [
      "componentsToFlush",
      "extentsProcessed",
      "extentsSizeProcessed",
      "extentsPerRun"
    ]

    for (var i in types) {
      var key = types[i]
      data[key] = convertInputs(rawdata['stats'],
          key, 'avgs',
          function(v) { return v }
      )
    }

    var graphSpecs = [
      ["Components", "cfcomp",
       prefix + "-cfcomp",
       [data['componentsToFlush']],
       ["ComponentsToFlush"],
       null, -1],

      ["Extents", "cfext",
       prefix + "-cfext",
       [data['extentsProcessed'], data['extentsSizeProcessed'], data['extentsPerRun']],
       ["ExtentsCount", 'ExtentsSize (KB)', "Extents/Run"],
       null, -1],
    ]
    return graphSpecs
}

function computePlogGraphSpecs(rawdata, prefix) {
    var data = {}
    var keys = [
        "readQLatency", "readTLatency",
        "writeQLatency", "writeTLatency",
    ]
    for (i in keys) {
        key = keys[i]
        data[key] = convertInputs(rawdata['stats'],
            key, 'avgs',
            function(v) { return v / 1000 }
        )
    }
    keys = [
        "readIOs", "writeIOs",
        "numElevSSDReads", "numMDWrites",
        "numReads", "numMDReads",
        "numRCReads", "numVMFSReads",
        "numSSDReads",
    ]
    for (i in keys) {
        key = keys[i]
        data[key] = convertInputs(rawdata['stats'],
            key, 'avgs',
            function(v) { return v }
        )
    }
    keys = [
        "totalBytesRead", "totalBytesReadFromMD",
        "totalBytesReadFromSSD", "totalBytesReadByRC",
        "totalBytesReadByVMFS", "totalBytesDrained",
        "ssdBytesDrained", "zeroBytesDrained",
    ]
    for (i in keys) {
        key = keys[i]
        data[key] = convertInputs(rawdata['stats'],
            key, 'avgs',
            function(v) { return v / 1048576 }
        )
    }
    keys = [
        "numCFLogs", "numFSLogs", "elevRuns",
    ]
    for (i in keys) {
        key = keys[i]
        data[key] = convertInputs(rawdata['stats'],
            key, 'values',
            function(v) { return v}
        )
    }
    keys = [
        "plogDataUsage", "plogMDDataUsage",
        "plogNumCommitLogs", "plogNumWriteLogs",
        "plogNumFreedCommitLogs", "plogNumFreedWriteLogs",
        "totalFSBytes", "totalCFBytes"
    ]
    for (i in keys) {
        key = keys[i]
        data[key] = convertInputs(rawdata['stats'],
            key, 'values',
            function(v) { return v / 1048576 }
        )
    }
    data["readLatency"] = computeDataSum(
        [
            data['readQLatency'],
            data['readTLatency'],
        ]
    )
    data["writeLatency"] = computeDataSum(
        [
            data['writeQLatency'],
            data['writeTLatency'],
        ]
    )
    data["IOs"] = computeDataSum(
        [
            data['readIOs'],
            data['writeIOs'],
        ]
    )
    data["Latency"] = computeLatencyAvgs(
        [
            data['readLatency'],
            data['writeLatency'],
        ],
        [
            data['readIOs'],
            data['writeIOs'],
        ]
    )
    data['capacity'] = convertInputs(rawdata['stats'],
      'capacityUsed', 'avgs',
      function(v) { return v }
    )
    var graphSpecs = [
        ["PLOG Latency", "ploglatency",
         prefix + "-ploglatency",
         [
            data['readQLatency'], data['readTLatency'],
            data['writeQLatency'], data['writeTLatency']
         ],
         [
            "Read Queue", "Read Other",
            "Write Queue", "Write Other",
         ],
         null],
        ["Latency", "ploglatencysum",
         prefix + "-ploglatencysum",
         [
//            data['readLatency'], data['writeLatency'],
            data['Latency']
         ],
         [
            "Latency"
//            "Read latency", "Write latency",
         ],
         null,
         countThresholdViolations(data['Latency'], 30)],
        ["PLOG IORETRY IOPS", "plogiops",
         prefix + "-plogiops",
         [
            data['readIOs'], data['writeIOs'],
         ],
         [
            "Read IOPS", "Write IOPS",
         ],
         null, 0],
        ["PLOG Elev IOPS", "plogeleviops",
         prefix + "-plogeleviops",
         [
            data['numElevSSDReads'], data['numMDWrites'],
            data['elevRuns'],
         ],
         [
            "Elev SSDOPS", "Elev MDOPS", "Cycles",
         ],
         null, 0],
        ["PLOG Read Bytes (MB)", "plogreads",
         prefix + "-plogreads",
         [
            data['totalBytesRead'], data['totalBytesReadFromMD'],
            data['totalBytesReadFromSSD'], data['totalBytesReadByRC'],
            data['totalBytesReadByVMFS'],
         ],
         [
            "TotalBytes", "MDBytes",
            "SSDBytes", "RCBytes", "FSBytes",
         ],
         null, 0],
        ["PLOG ReadOPS", "plogreadops",
         prefix + "-plogreadops",
         [
            data['numReads'], data['numMDReads'],
            data['numSSDReads'], data['numRCReads'],
            data['numVMFSReads'],
         ],
         [
            "TotalReads", "MDReads", "SSDReads",
            "RCReads", "FSReads",
         ],
         null, 0],
        ["PLOG Elev Bytes (MB)", "plogelev",
         prefix + "-plogelev",
         [
            data['totalBytesDrained'], data['ssdBytesDrained'],
            data['zeroBytesDrained'],
         ],
         [
            "TotalDrained", "SSDDrained", "ZeroDrained",
         ],
         null, 0],
        ["PLOG Data Bytes (MB)", "plogdata",
         prefix + "-plogdata",
         [
            data['plogMDDataUsage'], data['plogDataUsage'],
            data['numCFLogs'], data['numFSLogs'],
            data['totalFSBytes'], data['totalCFBytes']
         ],
         [
            "MDData", "DGData",
            "numCF", "numFS",
            "fsBytes", "cfBytes",
         ],
         null, 0],
        ["PLOG Logs", "ploglogs",
         prefix + "-ploglogs",
         [
            data['plogNumWriteLogs'], data['plogNumCommitLogs'],
            data['plogNumFreedWriteLogs'], data['plogNumFreedCommitLogs'],
         ],
         [
            "WriteLogs", "CommitLogs",
            "WriteLogsFreed", "CommitLogsFreed",
         ],
         null, 0],
        ["IOPS", "plogiopssum",
         prefix + "-plogiopssum",
         [
            data['IOs'],
         ],
         [
            "IOPS"
         ],
         null, 0],
        ["Capacity", "plogcapacity",
         prefix + "-plogcapacity",
         [
            data['capacity']
         ],
         [
            "Capacity Used"
         ],
         100, 0],
    ]
    return graphSpecs
}

function computeDiskGraphSpecs(rawdata, prefix) {
    var data = {}
    var keys = [
        "rcRead", "wbRead",
        "wbWrite", "rcWrite"
    ]
    for (i in keys) {
        key = keys[i]
        data[key + "QLatency"] = convertInputs(rawdata['stats'],
            key + "QLatency", 'avgs',
            function(v) { return v / 1000 }
        )
        data[key + "TLatency"] = convertInputs(rawdata['stats'],
            key + "TLatency", 'avgs',
            function(v) { return v / 1000 }
        )
        data[key + "Latency"] = computeDataSum(
            [data[key + "QLatency"], data[key + "TLatency"]]
        )
        data[key + "IOs"] = convertInputs(rawdata['stats'],
            key + "IOs", 'avgs',
            function(v) { return v }
        )
    }
    data["readLatency"] = computeLatencyAvgs(
        [
            data['rcReadLatency'],
            data['wbReadLatency'],
        ],
        [
            data['rcReadIOs'],
            data['wbReadIOs'],
        ]
    )
    data["writeLatency"] = computeLatencyAvgs(
        [
            data['rcWriteLatency'],
            data['wbWriteLatency'],
        ],
        [
            data['rcWriteIOs'],
            data['wbWriteIOs'],
        ]
    )
    data["Latency"] = computeLatencyAvgs(
        [
            data['rcReadLatency'],
            data['wbReadLatency'],
            data['rcWriteLatency'],
            data['wbWriteLatency'],
        ],
        [
            data['rcReadIOs'],
            data['wbReadIOs'],
            data['rcWriteIOs'],
            data['wbWriteIOs'],
        ]
    )
    data["readIOs"] = computeDataSum(
        [
            data['rcReadIOs'],
            data['wbReadIOs'],
        ]
    )
    data["writeIOs"] = computeDataSum(
        [
            data['rcWriteIOs'],
            data['wbWriteIOs'],
        ]
    )
    data["IOs"] = computeDataSum(
        [
            data['rcReadIOs'],
            data['wbReadIOs'],
            data['rcWriteIOs'],
            data['wbWriteIOs'],
        ]
    )
    var graphSpecs = [
        ["LLOG Latency", "disklatency",
         prefix + "-disklatency",
         [
            data['rcReadQLatency'], data['rcReadTLatency'],
            data['rcWriteQLatency'], data['rcWriteTLatency'],
            data['wbReadQLatency'], data['wbReadTLatency'],
            data['wbWriteQLatency'], data['wbWriteTLatency'],
         ],
         [
            "RC Read Queue", "RC Read Other",
            "RC Write Queue", "RC Write Other",
            "WB Read Queue", "WB Read Other",
            "WB Write Queue", "WB Write Other",
         ],
         null],
        ["Latency", "disklatencysum",
         prefix + "-disklatencysum",
         [
//            data['readLatency'], data['writeLatency']
            data['Latency']
         ],
         [
//            "Read Latency", "Write Latency"
            "Latency"
         ],
         null,
         countThresholdViolations(data['Latency'], 30)],
        ["LLOG IOPS", "diskiops",
         prefix + "-diskiops",
         [
            data['rcReadIOs'], data['rcWriteIOs'],
            data['wbReadIOs'], data['wbWriteIOs'],
         ],
         [
            "RC Read", "RC Write",
            "WB Read", "WB Write",
         ],
         null],
        ["IOPS", "diskiopssum",
         prefix + "-diskiopssum",
         [
//            data['readIOs'], data['writeIOs']
            data['IOs']
         ],
         [
//            "Read", "Write"
            "IOPS"
         ],
         null,
         0],
    ]
    return graphSpecs
}

function computeLsomHostGraphSpecs(rawdata, prefix) {
    return computeLsomHostGraphSpecsInt(rawdata, prefix, false);
}

function computeLsomHostGraphSpecsThumb(rawdata, prefix) {
    return computeLsomHostGraphSpecsInt(rawdata, prefix, true);
}

function computeLsomHostGraphSpecsInt(rawdata, prefix, thumb) {
    var keys = ['read', 'payload', 'writeLe']
    var titles = ['Read', 'Write Data', 'Write LE']
    var data = {}
    var labels = []
    for (i in keys) {
        key = keys[i]
        data[key + "Latency"] = convertInputs(rawdata['stats'],
            key + "Latency", 'avgs',
            function(v) { return v / 1000 }
        )
        data[key + "IOPS"] = convertInputs(rawdata['stats'],
            key + "IOs", 'avgs',
            function(v) { return v }
        )
        data[key + "Bytes"] = convertInputs(rawdata['stats'],
            key + "Bytes", 'avgs',
            function(v) { return v / 1024}
        )
    }
    data["warEvictions"] = convertInputs(rawdata['stats'],
      "warEvictions", 'avgs',
      function(v) { return Math.round(v) }
    )
    data["quotaEvictions"] = convertInputs(rawdata['stats'],
      "quotaEvictions", 'avgs',
      function(v) { return Math.round(v) }
    )
    data["rawarIOPS"] = convertInputs(rawdata['stats'],
      "rawarIOs", 'avgs',
      function(v) { return Math.round(v) }
    )
    data["rawarBytes"] = convertInputs(rawdata['stats'],
      "rawarBytes", 'avgs',
      function(v) { return Math.round(v) }
    )
    data["patchedBytes"] = convertInputs(rawdata['stats'],
      "patchedBytes", 'avgs',
      function(v) { return Math.round(v) }
    )
    data["wastedPatchedBytes"] = convertInputs(rawdata['stats'],
      "wastedPatchedBytes", 'avgs',
      function(v) { return Math.round(v) }
    )
    data["plogCbSlotNotFound"] = convertInputs(rawdata['stats'],
      "plogCbSlotNotFound", 'avgs',
      function(v) { return Math.round(v) }
    )
    data["plogCbBitNotSet"] = convertInputs(rawdata['stats'],
      "plogCbBitNotSet", 'avgs',
      function(v) { return Math.round(v) }
    )
    data["plogCbInvalidated"] = convertInputs(rawdata['stats'],
      "plogCbInvalidated", 'avgs',
      function(v) { return Math.round(v) }
    )
    data["plogCbPatched"] = convertInputs(rawdata['stats'],
      "plogCbPatched", 'avgs',
      function(v) { return Math.round(v) }
    )
    if (rawdata['stats']['avgCapacityUsed']) {
      data["capacityUsed"] = convertInputs(rawdata['stats'],
        "avgCapacityUsed", 'avgs',
        function(v) { return v }
      )
      data["maxCapacityUsed"] = convertInputs(rawdata['stats'],
        "maxCapacityUsed", 'avgs',
        function(v) { return v }
      )
      data["minCapacityUsed"] = convertInputs(rawdata['stats'],
        "minCapacityUsed", 'avgs',
        function(v) { return v }
      )
    }
    data["rarReadIOPS"] = convertInputs(rawdata['stats'],
        "rarReadIOs", 'avgs',
        function(v) { return v }
    )
    data["rcHitRate"] = computeRcHitRate(data["readIOPS"], data["rarReadIOPS"])
    if (thumb) {
        data["Latency"] = computeLatencyAvgs(
            [
                data["readLatency"],
                data["payloadLatency"],
                data["writeLeLatency"],
            ],
            [
                data["readIOPS"],
                data["payloadIOPS"],
                data["writeLeIOPS"],
            ]
        )
        data["IOPS"] = computeDataSum([
            data["readIOPS"],
            data["payloadIOPS"],
            data["writeLeIOPS"],
        ])
        data["Tput"] = computeDataSum([
            data["readBytes"],
            data["payloadBytes"],
        ])
    } else {
      data["rcMemIOPS"] = convertInputs(rawdata['stats'],
          "rcMemIOs", 'avgs',
          function(v) { return v }
      )
      data["rcSsdIOPS"] = convertInputs(rawdata['stats'],
          "rcSsdIOs", 'avgs',
          function(v) { return v }
      )
      data["rarMissIOPS"] = convertInputs(rawdata['stats'],
           "rcMissIOs", 'avgs',
           function(v) { return v }
      )
      data["rarPartialMissIOPS"] = convertInputs(rawdata['stats'],
           "rcPartialMissIOs", 'avgs',
           function(v) { return v }
      )
      data["rcMissRate"] = computeRcHitRate(data["readIOPS"], data["rarMissIOPS"])
      data["rcPartialMissRate"] = computeRcHitRate(data["readIOPS"], data["rarPartialMissIOPS"])
    }
    var graphSpecs = null
    if (!thumb) {
      graphSpecs = []
      graphSpecs.push(
        ["Latency", "latency",
         prefix + "-latency",
         [data['readLatency'], data['payloadLatency'], data['writeLeLatency']],
         ["Read ", "Write Data ", "Write LE "],
         null])
      graphSpecs.push(
        ["IOPS", "iops",
         prefix + "-iops",
         [data['readIOPS'], data['payloadIOPS'], data['writeLeIOPS']],
         ["Read IOPS", "Write Data IOPS", "Write LE IOPS"],
         null])
      graphSpecs.push(
        ["Bandwidth", "tput",
         prefix + "-tput",
         [data['readBytes'], data['payloadBytes'], data['writeLeBytes']],
         ["Read KB/s", "Write KB/s", "Write LE KB/s"],
         null])
      if (rawdata['stats']['avgCapacityUsed']) {
        graphSpecs.push(
          ["Capacity", "capacity",
           prefix + "-capacity",
           [data['capacityUsed'], data['maxCapacityUsed'], data['minCapacityUsed']],
           ["Avg Capacity Used", "Max Capacity Used", "Min Capacity Used"],
           100,
           0])
      }
      graphSpecs.push(
        ["RC IOPS breakdown", "rciops",
         prefix + "-rciops",
         [data['readIOPS'], data['rcMemIOPS'], data['rcSsdIOPS'], data['rarReadIOPS'], data['rawarIOPS']],
         ["Total reads", "RC/Mem Reads", "RC/SSD Reads", "Total RC hits", "R-a-W-a-R"],
         null])
      graphSpecs.push(
        ["RC Hit Rate", "rc",
         prefix + "-rc",
         [data['rcHitRate'], data['rcMissRate'], data['rcPartialMissRate']],
         ["RC Hit Rate", "RC Miss Rate", "RC Partial Hit Rate"],
         100])
      graphSpecs.push(
        ["Evictions", "evictions",
         prefix + "-evictions",
         [data['warEvictions'], data['quotaEvictions']],
         ["Write after Read", "Quota"],
         null])
      graphSpecs.push(
        ["Bytes read from invalidated lines", "rawar",
         prefix + "-rawar",
         [data['rawarBytes'], data['patchedBytes'], data['wastedPatchedBytes']],
         ["R-W-R bytes", "Patched bytes", "Wasted patched bytes"],
         null])
      graphSpecs.push(
        ["Counters from the PLOG callback path to RC", "rc_plog_cb",
         prefix + "-rc_plog_cb",
         [data['plogCbSlotNotFound'], data['plogCbBitNotSet'], data['plogCbInvalidated'], data['plogCbPatched']],
         ["RCL not found", "Inv bit not set", "Invalidated", "Patched"],
         null])
    } else {
      graphSpecs = []
      graphSpecs.push(
        ["Latency", "latency",
         prefix + "-latency",
         [data['Latency']],
         ["Latency"],
         null,
         countThresholdViolations(data['Latency'], 30)])
      graphSpecs.push(
        ["IOPS", "iops",
         prefix + "-iops",
         [data['IOPS']],
         ["IOPS"],
         null,
         0])
      graphSpecs.push(
        ["Bandwidth", "tput",
         prefix + "-tput",
         [data['Tput']],
         ["Tput"],
         null,
         0])
      if (rawdata['stats']['avgCapacityUsed']) {
        graphSpecs.push(
          ["Capacity", "capacity",
           prefix + "-capacity",
           [data['capacityUsed']],
           ["Capacity Used"],
           100,
           0])
      }
      graphSpecs.push(
        ["RC Hit Rate", "rc",
         prefix + "-rc",
         [data['rcHitRate']],
         ["RC Hit Rate"],
         100,
         0])
      graphSpecs.push(
        ["Evictions", "evictions",
         prefix + "-evictions",
         [data['warEvictions'], data['quotaEvictions']],
         ["Write after Read", "Quota"],
         null,
         0])
    }
    return graphSpecs
}

function computeDomGraphSpecs(rawdata, prefix) {
    return computeDomGraphSpecsInt(rawdata, prefix, false)
}
function computeDomGraphSpecsThumb(rawdata, prefix) {
    return computeDomGraphSpecsInt(rawdata, prefix, true)
}

function computeDomGraphSpecsInt(rawdata, prefix, thumb) {
  var tputData = {};
  var iopsData = {};
  var latencyData = {};
  var congestionData = {};
  var latencySqData = {};
  var latencySdData = {};
  var types = ['read', 'write', 'recoveryWrite'];
  for (var x in types) {
    x = types[x];
    tputData[x] = convertInputs(rawdata['stats'],
      x + 'Bytes', 'avgs',
      function(v) { return v / 1024.0 }
    )
    iopsData[x] = convertInputs(rawdata['stats'],
      x + 'Count', 'avgs',
      function(v) { return v }
    )
    latencyData[x] = convertInputs(rawdata['stats'],
      x + 'Latency', 'avgs',
      function(v) { return v / 1000 }
    )
    latencySqData[x] = convertInputs(rawdata['stats'],
      x + 'LatencySq', 'avgs',
      function(v) { return v / 1000 }
    )
    congestionData[x] = convertInputs(rawdata['stats'],
      x + 'Congestion', 'avgs',
      function(v) { return v }
    )
    latencySdData[x] = computeStdDeviation(latencyData[x], latencySqData[x])
  }
  if (thumb) {
    latencyData["all"] = computeLatencyAvgs(
      [
        latencyData['read'],
        latencyData['write'],
        latencyData['recoveryWrite'],
      ],
      [
        iopsData['read'],
        iopsData['write'],
        iopsData['recoveryWrite'],
      ]
    )
    latencySdData["all"] = computeLatencyAvgs(
      [
        latencySdData['read'],
        latencySdData['write'],
        latencySdData['recoveryWrite'],
      ],
      [
        iopsData['read'],
        iopsData['write'],
        iopsData['recoveryWrite'],
      ]
    )
    iopsData["all"] = computeDataSum([
      iopsData['read'],
      iopsData['write'],
      iopsData['recoveryWrite'],
    ])
    tputData["all"] = computeDataSum([
      tputData['read'],
      tputData['write'],
      tputData['recoveryWrite'],
    ])
    congestionData["all"] = computeLatencyAvgs(
      [
        congestionData['read'],
        congestionData['write'],
        congestionData['recoveryWrite'],
      ],
      [
        iopsData['read'],
        iopsData['write'],
        iopsData['recoveryWrite'],
      ]
    )
  }

  var domClientCacheHitRate = convertInputs(rawdata['stats'],
    'domClientCacheHitRate', 'values',
    function(v) { return v }
  )

  var oioData = convertInputs(rawdata['stats'],
    'numOIO', 'avgs',
    function(v) { return v }
  )
  var graphSpecs = []
  if (!thumb) {
    graphSpecs = [
      ["Latencies", "latency",
       prefix + "-latency",
       [latencyData['read'], latencyData['write'], latencyData['recoveryWrite']],
       ["Read ", "Write ", "RecovWrite "],
       null],
      ["IOPS", "iops",
       prefix + "-iops",
       [iopsData['read'], iopsData['write'], iopsData['recoveryWrite']],
       ["Read ", "Write ", "RecovWrite "],
       null],
      ["Bandwidth", "tput",
       prefix + "-tput",
       [tputData['read'], tputData['write'], tputData['recoveryWrite']],
       ["Read KB/s", "Write KB/s", "RecovWrite KB/s"],
       null],
      ["Congestion", "congestion",
       prefix + "-cong",
       [congestionData['read'], congestionData['write'], congestionData['recoveryWrite']],
       ["Read Cong", "Write Cong", "RecovWrite Cong"],
       255],
      ["Outstanding IO", "oio",
       prefix + "-oio",
       [oioData],
       ["Num OIO"],
       null],
      ["Latency standard deviation", "latencySD",
       prefix + "-latencySD",
       [latencySdData['read'], latencySdData['write'], latencySdData['recoveryWrite']],
       ["Read Lat SD", "Write Lat SD", "RecovWrite Lat SD"],
       null],
      ["Client Cache Hit Rate", "domClientCacheHitRate",
       prefix + "-domClientCacheHitRate",
       [domClientCacheHitRate],
       ["Hit Rate"],
       null],
    ]
  } else {
    graphSpecs = [
      ["Latency", "latency",
       prefix + "-latency",
       [latencyData['all']],
       ["Latency"],
       null,
       countThresholdViolations(latencyData['all'], 30)],
      ["IOPS", "iops",
       prefix + "-iops",
       [iopsData['all']],
       ["IOPS"],
       null, -1],
      ["Bandwidth", "tput",
       prefix + "-tput",
       [tputData['all']],
       ["Tput KB/s"],
       null, -1],
      ["Congestion", "congestion",
       prefix + "-congestion",
       [congestionData['all']],
       ["Congestion"],
       255,
       countThresholdViolations(congestionData['all'], 20)],
      ["Outstanding IO", "oio",
       prefix + "-oio",
       [oioData],
       ["Num OIO"],
       null, -1],
      ["Latency stddev", "latencySD",
       prefix + "-latencySD",
       [latencySdData['all']],
       ["Lat SD"],
       null,
       countThresholdViolations(latencySdData['all'], 30)],
      ["CC Hit Rate", "domClientCacheHitRate",
       prefix + "-domClientCacheHitRate",
       [domClientCacheHitRate],
       ["Hit Rate"],
       null, -1],
    ]
  }
  return graphSpecs
}

function computeDistributionGraphSpecs(rawdata, prefix) {
  return computeDistributionGraphSpecsInt(rawdata, prefix, false);
}

function computeDistributionGraphSpecsThumb(rawdata, prefix) {
  return computeDistributionGraphSpecsInt(rawdata, prefix, true);
}

function computeDistributionGraphSpecsInt(rawdata, prefix, thumb) {
  var types = ['lsom.components', 'lsom.iocomponents', 'lsom.diskcapacity', 'dom.owners', 'dom.clients', 'dom.colocated']
  var labels = ['Components', 'IO Components', 'Disk Capacity', 'DOM owners', 'DOM Clients', 'DOM Colocated']
  var limits = [null, null, 100, null]
  var graphSpecs = []
  for (var i in types) {
    var type = types[i];
    var datas = []
    var hosts = []
    for (var host in rawdata['hosts']) {
      hosts.push(host)
      datas.push(convertInputs(rawdata['hosts'][host],
        type, 'total',
        function(v) { return v }
      ))
    }
    graphSpecs.push([
      labels[i], type,
      prefix + "-" + type.replace(/\./g, '-'),
      datas,
      hosts,
      null, -1
    ])
  }
  return graphSpecs;
}

function computeCbrcGraphSpecs(rawdata, prefix) {
  return computeCbrcGraphSpecsInt(rawdata, prefix, false);
}

function computeCbrcGraphSpecsThumb(rawdata, prefix) {
  return computeCbrcGraphSpecsInt(rawdata, prefix, true);
}

function computeCbrcGraphSpecsInt(rawdata, prefix, thumb) {
  var data = {}
  var graphSpecs = []

  data['reads'] = convertInputs(rawdata['stats'],
    'vmReadCount', 'avgs',
    function(v) { return v }
  )
  data['readMisses'] = convertInputs(rawdata['stats'],
    'dioReadCount', 'avgs',
    function(v) { return v }
  )
  data["cbrcHitRate"] = computeCbrcHitRate(data["reads"], data["readMisses"])

  graphSpecs.push([
    "CBRC Hit Rate", 'hitrate',
    prefix + "-hitrate",
    [data['cbrcHitRate']],
    ['Hit Rate'],
    100, -1
  ])
  if (!thumb) {
    graphSpecs.push([
      "CBRC IOPS", 'iops',
      prefix + "-iops",
      [data['reads'], data['readMisses']],
      ['Total Read', 'Read Misses'],
      null, -1
    ])
  }
  return graphSpecs;
}

function computeGenericGraphSpecs(rawdata, prefix) {
  return computeGenericGraphSpecsInt(rawdata, prefix, false)
}

function computeGenericGraphSpecsThumb(rawdata, prefix) {
  return computeGenericGraphSpecsInt(rawdata, prefix, true)
}

function computeGenericGraphSpecsInt(rawdata, prefix, thumb) {
  var data = {}
  var graphSpecs = []

  for (var statKey in rawdata['statsInfo']) {
    var info = rawdata['statsInfo'][statKey]
    data[statKey] = convertInputs(rawdata['stats'],
      statKey, info[0],
      function(v) {
        var val = v * info[1];
        if (info.length < 3 || info[2] == "round") {
          val = Math.round(val);
        }
        return val;
      }
    )
  }

  // XXX: Need to have thumb and non thumb specs
  for (var specIdx in rawdata['thumbSpecs']) {
    var spec = rawdata['thumbSpecs'][specIdx]
    var fields = []
    for (var fieldIdx in spec['fields']) {
      fields.push(data[spec['fields'][fieldIdx]])
    }
    graphSpecs.push([
      spec['label'], spec['key'],
      prefix + "-" + spec['key'],
      fields,
      spec['fieldLabels'],
      spec['max'],
      -1
    ])
  }

  return graphSpecs
}

function computeSysMemGraphSpecs(rawdata, prefix) {
  return computeSysMemGraphSpecsInt(rawdata, prefix, false);
}

function computeSysMemGraphSpecsThumb(rawdata, prefix) {
  return computeSysMemGraphSpecsInt(rawdata, prefix, true);
}

function computeSysMemGraphSpecsInt(rawdata, prefix, thumb) {
  var data = {}
  var graphSpecs = []

  data['totalGbMemUsed'] = convertInputs(rawdata['stats'],
    'totalMbMemUsed', 'values',
    function(v) { return v / 1024 }
  )
  data['pctMemUsed'] = convertInputs(rawdata['stats'],
    'pctMemUsed', 'values',
    function(v) { return v }
  )
  data['overcommitRatio'] = convertInputs(rawdata['stats'],
    'overcommitRatio', 'values',
    function(v) { return v / 100 }
  )

  if (!thumb) {
    graphSpecs.push([
      "Used mem GB", 'usedmemgb',
      prefix + "-usedmemgb",
      [data['totalGbMemUsed']],
      ['Used mem GB'],
      null, -1
    ])
  }

  graphSpecs.push([
    "Used mem %", 'usedmempct',
    prefix + "-usedmempct",
    [data['pctMemUsed']],
    ['Used mem %'],
    100,
    countThresholdViolations(data['pctMemUsed'], 85)
  ])
  graphSpecs.push([
    "Mem overcommit", 'overcommit',
    prefix + "-overcommit",
    [data['overcommitRatio']],
    ['Overcommit'],
    1.0, -1
  ])
  return graphSpecs
}


function computePnicsGraphSpecs(rawdata, prefix) {
  return computePnicsGraphSpecsInt(rawdata, prefix, false);
}

function computePnicsGraphSpecsThumb(rawdata, prefix) {
  return computePnicsGraphSpecsInt(rawdata, prefix, true);
}

function computePnicsGraphSpecsInt(rawdata, prefix, thumb) {
  var data = {}
  var graphSpecs = []

  if (thumb) {
    var pnics = []
    bytes2GbpsDiv = 1000 * 1000 * 1000 / 8
    data['rxbytes'] = []
    data['txbytes'] = []
    for (var pnic in rawdata['pnics']) {
      pnics.push(pnic)
      data['rxbytes'].push(convertInputs(rawdata['pnics'][pnic],
        'rxbytes', 'avgs',
        function(v) { return v / bytes2GbpsDiv }
      ))
      data['txbytes'].push(convertInputs(rawdata['pnics'][pnic],
        'txbytes', 'avgs',
        function(v) { return v / bytes2GbpsDiv }
      ))
    }

    graphSpecs.push([
      "Pnic RX Gbit/s", 'rxtput',
      prefix + "-rxtput",
      data['rxbytes'],
      pnics,
      10.0,
      -1
    ])
    graphSpecs.push([
      "Pnic TX Gbit/s", 'txtput',
      prefix + "-txtput",
      data['txbytes'],
      pnics,
      10.0,
      -1
    ])
    return graphSpecs
  }

  /* Full graphs. Return throughput and error graphs */
  bytes2MBpsDiv = 1024 * 1024
  pkts2KppsDiv = 1000

  var labels = []
  data['tput'] = []
  data['errs'] = []
  errLabels = []
  for (var pnic in rawdata['pnics']) {
    labels.push(pnic + '-RxMBps')
    labels.push(pnic + '-TxMBps')
    labels.push(pnic + '-RxKpps')
    labels.push(pnic + '-TxKpps')
    errLabels.push(pnic + '-TxErrs')
    errLabels.push(pnic + '-RxErrs')
    stats = rawdata['pnics'][pnic]
    data['tput'].push(convertInputs(stats,
      'rxbytes', 'avgs',
      function(v) { return v / bytes2MBpsDiv }
    ))
    data['tput'].push(convertInputs(stats,
      'txbytes', 'avgs',
      function(v) { return v / bytes2MBpsDiv }
    ))
    data['tput'].push(convertInputs(stats,
      'rxpkt', 'avgs',
      function(v) { return v / pkts2KppsDiv }
    ))
    data['tput'].push(convertInputs(stats,
      'txpkt', 'avgs',
      function(v) { return v / pkts2KppsDiv}
    ))
    data['errs'].push(computeDataSum([
                        convertInputs(stats,
                                      'txdrp', 'avgs',
                                      function(v) { return v}),
                        convertInputs(stats,
                                      'txerror', 'avgs',
                                      function(v) { return v})
                                    ])
                     )
    data['errs'].push(computeDataSum([
                        convertInputs(stats,
                                      'rxdrp', 'avgs',
                                      function(v) { return v}),
                        convertInputs(stats,
                                      'rxerror', 'avgs',
                                      function(v) { return v})
                                    ])
                     )

  }

  graphSpecs.push([
    "Pnic Tput", 'pnictput',
    prefix + "-pnictput",
    data['tput'],
    labels,
    null,
    -1
  ])

  graphSpecs.push([
    "Pnic Errors", 'pnicerrs',
    prefix + "-pnicerrs",
    data['errs'],
    errLabels,
    null,
    -1
  ])

  return graphSpecs
}

function computeTcpGraphSpecs(rawdata, prefix) {
  return computeTcpGraphSpecsInt(rawdata, prefix, false);
}

function computeTcpGraphSpecsThumb(rawdata, prefix) {
  return computeTcpGraphSpecsInt(rawdata, prefix, true);
}

function computeTcpGraphSpecsInt(rawdata, prefix, thumb) {
  var data = {}
  var graphSpecs = []

  tcpstats = rawdata['stats']['tcp']
  data = []

  rexmits = convertInputs(tcpstats, 'sndrexmitpack', 'avgs',
                          function(v) { return v })
  dupacks = convertInputs(tcpstats, 'rcvdupack', 'avgs',
                          function(v) { return v })
  rxdups = convertInputs(tcpstats, 'rcvduppack', 'avgs',
                         function(v) { return v })
  rxoops = convertInputs(tcpstats, 'rcvoopack', 'avgs',
                         function(v) { return v })
  if (thumb) { /* Only aggregate errors */
    txerrs = computeDataSum([rexmits, dupacks])
    rxerrs = computeDataSum([rxdups, rxoops])
    graphSpecs.push([
      "Tcp Errors", 'tcperrs',
      prefix + "-tcperrs",
      [txerrs, rxerrs],
      ['txerrs', 'rxerrs'],
      null,
      -1
    ])
    return graphSpecs;
  }

  /* Full graphs. Report throughput and errors in separate graphs */
  bytes2MBpsDiv = (1024 * 1024);
  txmbps = convertInputs(tcpstats, 'sndbyte', 'avgs',
                         function(v) { return v / bytes2MBpsDiv })
  rxmbps = convertInputs(tcpstats, 'rcvbyte', 'avgs',
                         function(v) { return v / bytes2MBpsDiv })
  pps2KppsDiv = 1000.0;
  txkpps = convertInputs(tcpstats, 'sndpack', 'avgs',
                         function(v) { return v / pps2KppsDiv})
  rxkpps = convertInputs(tcpstats, 'rcvpack', 'avgs',
                         function(v) { return v / pps2KppsDiv})
  graphSpecs.push([
    "vmknic throughput", 'vmktput',
    prefix + "-vmktput",
    [txmbps, rxmbps, txkpps, rxkpps],
    ['TxMBps', 'RxMBps', 'TxKpps', 'RxKpps'],
    null,
    0
  ])

  graphSpecs.push([
    "vmknic errors", 'vmkerrs',
    prefix + "-vmkerrs",
    [rexmits, dupacks, rxdups, rxoops],
    ['Rexmits', 'DupAckRx', 'DupDataRx', 'OutofOrderRx'],
    null,
    0
  ])

  return graphSpecs
}

function computeFitnessGraphSpecs(rawdata, prefix) {
  var graphSpecs = []
  var params = Object.keys(rawdata['fitness'])
  for (var i in params) {
    var param = params[i]
    disks = Object.keys(rawdata['fitness'][param])
    var lineDatas = []
    var labels = []
    var violations = -1
    for (var j in disks) {
      disk = disks[j]
      data = convertInputs(rawdata['fitness'][param], disk,
                           'values', function(v) {return v;})
      lineDatas.push(data)
      labels.push(disk)
    }
    graphSpecs.push([param, param,
      prefix + "-" + param,
      lineDatas, labels,
      null,
      violations]
    )
  }
  return graphSpecs
}

function computeCmmdsGraphSpecs(rawdata, prefix) {
  return computeCmmdsGraphSpecsInt(rawdata, prefix, false)
}

function computeCmmdsGraphSpecsThumb(rawdata, prefix) {
  return computeCmmdsGraphSpecsInt(rawdata, prefix, true)
}

function computeCmmdsGraphSpecsInt(rawdata, prefix, thumb) {
  var data = []
  var labels = []
  var graphSpecs = []

  masterStats = ['totalUpdates','droppedUpdatesToWitnessAgents',
                 'noPayloadUpdatesToWitnessAgents',
                 'fullUpdatesToWitnessAgents', 'updatesToRegAgents']

  deltadata = rawdata['stats']
  for (var j in masterStats) {
    d = convertInputs(deltadata['cmmds.master'],
                      masterStats[j], 'values', function(v){return v;})
    data.push(d)
    labels.push(masterStats[j])
  }
  graphSpecs.push([
    "Master Stats (count)", 'mstatsCount',
    prefix + "-" + "mstatsCount",
    data,
    labels,
    null,
    -1,
    !thumb
  ])

  data = []
  labels = []
  masterStats = ['bytesDroppedUpdatesToWitnessAgents', 'bytesNoPayloadUpdatesToWitnessAgents',
                 'bytesFullUpdatesToWitnessAgents', 'bytesUpdatesToRegAgents']
  for (var j in masterStats) {
    d = convertInputs(deltadata['cmmds.master'],
                      masterStats[j], 'values', function(v){return v;})
    data.push(d)
    labels.push(masterStats[j])
  }
  graphSpecs.push([
    "Master Stats (bytes)", 'mstatsBytes',
    prefix + "-" + "mstatsBytes",
    data,
    labels,
    null,
    -1,
    !thumb
  ])

  data = []
  labels = []
  ioStats = ['rdtRx', 'rdtTx']
  for (var j in ioStats) {
    d = convertInputs(deltadata['cmmdsnet.stats'],
                      ioStats[j], 'values', function(v){return v;})
    data.push(d)
    labels.push(ioStats[j])
  }
  graphSpecs.push([
    "IO Stats (count)", 'istatsCount',
    prefix + "-" + "istatsCount",
    data,
    labels,
    null,
    -1
  ])

  data = []
  labels = []
  ioStats = ['rdtRxBytes', 'rdtTxBytes']
  for (var j in ioStats) {
    d = convertInputs(deltadata['cmmdsnet.stats'],
                      ioStats[j], 'values', function(v){return v;})
    data.push(d)
    labels.push(ioStats[j])
  }
  graphSpecs.push([
    "IO Stats (bytes)", 'istatsBytes',
    prefix + "-" + "istatsBytes",
    data,
    labels,
    null,
    -1
  ])

  data = []
  labels = []
  for (var j in deltadata['cmmds.queues']) {
    d = convertInputs(deltadata['cmmds.queues'],
                      j, 'values', function(v){return v;})
    data.push(d)
    labels.push(j)
  }
  graphSpecs.push([
    "Queue Stats", 'qstats',
    prefix + "-" + "qstats",
    data,
    labels,
    null,
    -1,
    !thumb
  ])

  data = []
  labels = []
  workloadStats = ['rxMasterUpdate', 'rxSnapshot',
                   'txAgentUpdateRequest', 'txRetransmitRequest']
  for (var j in workloadStats) {
    d = convertInputs(deltadata['cmmds.workload'],
                      workloadStats[j], 'values', function(v){return v;})
    data.push(d)
    labels.push(workloadStats[j])
  }
  graphSpecs.push([
    "Workload Stats(1)", 'wstats1',
    prefix + "-" + "wstats1",
    data,
    labels,
    null,
    -1,
    !thumb
  ])

  data = []
  labels = []
  workloadStats = ['rxAgentUpdateRequest', 'rxAccept',
                   'txSnapshot', 'rxRetransmitRequest', 'rxLocalUpdate']
  for (var j in workloadStats) {
    d = convertInputs(deltadata['cmmds.workload'],
                      workloadStats[j], 'values', function(v){return v;})
    data.push(d)
    labels.push(workloadStats[j])
  }
  graphSpecs.push([
    "Workload Stats(2)", 'wstats2',
    prefix + "-" + "wstats2",
    data,
    labels,
    null,
    -1,
    !thumb
  ])

  return graphSpecs;
}

function computeElevatorGraphSpecs(rawdata, prefix) {
  return computeElevatorGraphSpecsInt(rawdata, prefix, false);
}

function computeElevatorGraphSpecsThumb(rawdata, prefix) {
  return computeElevatorGraphSpecsInt(rawdata, prefix, true);
}

function computeElevatorGraphSpecsInt(rawdata, prefix, thumb) {
  var data = {}
  var graphSpecs = []

  data['ssdWriteRate'] = convertInputs(rawdata['stats'],
    'readIOs', 'avgs',
    function(v) { return v }
  )
  // XXX: Not done yet
}

function computePhysDiskGraphSpecs(rawdata, prefix) {
  return computePhysDiskGraphSpecsInt(rawdata, prefix, false);
}

function computePhysDiskGraphSpecsThumb(rawdata, prefix) {
  return computePhysDiskGraphSpecsInt(rawdata, prefix, true);
}

function computePhysDiskGraphSpecsInt(rawdata, prefix, thumb) {
  var data = {}
  var graphSpecs = []

  data['readIOs'] = convertInputs(rawdata['stats'],
    'readIOs', 'avgs',
    function(v) { return v }
  )
  data['writeIOs'] = convertInputs(rawdata['stats'],
    'writeIOs', 'avgs',
    function(v) { return v }
  )
  data['dAvgLatency'] = convertInputs(rawdata['stats'],
    'dAvgLatency', 'avgs',
    function(v) { return v / 1000 }
  )
  data['gAvgLatency'] = convertInputs(rawdata['stats'],
    'gAvgLatency', 'avgs',
    function(v) { return v / 1000 }
  )
  data['kAvgLatency'] = convertInputs(rawdata['stats'],
    'kAvgLatency', 'avgs',
    function(v) { return v / 1000 }
  )
  data['readLatency'] = convertInputs(rawdata['stats'],
    'readLatency', 'avgs',
    function(v) { return v / 1000 }
  )
  data['writeLatency'] = convertInputs(rawdata['stats'],
    'writeLatency', 'avgs',
    function(v) { return v / 1000 }
  )
  data['read'] = convertInputs(rawdata['stats'],
    'read', 'avgs',
    // Divide by 2 because the values are in blocks/s, i.e. 512B/s
    function(v) { return v / 2 }
  )
  data['write'] = convertInputs(rawdata['stats'],
    'write', 'avgs',
    // Divide by 2 because the values are in blocks/s, i.e. 512B/s
    function(v) { return v / 2 }
  )

  if (thumb) {
    data["IOs"] = computeDataSum([
      data['readIOs'],
      data['writeIOs'],
    ])
    data["tput"] = computeDataSum([
      data['read'],
      data['write'],
    ])
    graphSpecs.push([
      "IOPS", 'iops',
      prefix + "-iops",
      [data['IOs']],
      ['IOPS'],
      null, -1
    ])
    graphSpecs.push([
      "Tput", 'tput',
      prefix + "-tput",
      [data['tput']],
      ['Total KB/s'],
      null, -1
    ])
    graphSpecs.push([
      "DevLatency (ms)", 'latency',
      prefix + "-latency",
      [data['dAvgLatency']],
      ['Device latency (ms)'],
      null, -1
    ])
  } else {
    graphSpecs.push([
      "IOPS", 'iops',
      prefix + "-iops",
      [data['readIOs'], data['writeIOs']],
      ['Read IOPS', 'Write IOPS'],
      null, -1
    ])
    graphSpecs.push([
      "Tput", 'tput',
      prefix + "-tput",
      [data['read'], data['write']],
      ['Read KB/s', 'Write KB/s'],
      null, -1
    ])
    graphSpecs.push([
      "DiskLatency (ms)", 'latency',
      prefix + "-latency",
      [data['dAvgLatency'], data['kAvgLatency'], data['gAvgLatency'],
       data['readLatency'], data['writeLatency']],
      ['DAVG', 'KAVG', 'GAVG', 'RDLAT', 'WRLAT'],
      null, -1
    ])
  }
  return graphSpecs;
}


function toggleVisibility(elementname, y) {
  var x = document.getElementById(elementname)
  if (x.style.display == "none") {
    x.style.display = y;
  } else {
    x.style.display = "none";
  }
}

function addGraphDivs(prefix, graphNames) {
    var hostDiv = d3.select("#" + escapeColon(prefix))
    for (var j in graphNames) {
      var hits = d3.select("." + escapeColon(prefix) + "-" + graphNames[j])
      if (hits[0].length == 1 && hits[0][0] != null) {
        continue
      }
      hostDiv.append("div")
        .attr("class", "mini-graph-container")
        .append("div")
          .attr("class", "graphmini " + prefix + "-" + graphNames[j])
      hostDiv.append("span").text(" ")
    }
}

function loadGraphsCommon(filename, func, prefix) {
  var query = jQuery.getJSON(
    filename,
    function(data){
      var graphSpecs = func(data, "." + prefix.replace(/\./g, '-'))
      renderGraphs(data, false, 150, 100, graphSpecs)
    }
  )
}

var graphTable = {}
function registerGraph(tabname, filename, func, prefix, needsDiv) {
  if (graphTable[tabname] == null) {
    graphTable[tabname] = []
  }
  graphTable[tabname].push({
    'filename': filename,
    'func': func,
    'prefix': prefix,
    'data': null,
    'graphSpecs': null,
    'needsDiv': needsDiv,
  })
}


function showTabGraphs(tabname) {
  if (tabname == "lsom-tab") {
    toggleLsomHostDiv()
  }

  function normalizeGraphSpecs() {
    var types = []
    for (var key in graphTable[tabname]) {
      var graphSpecs = graphTable[tabname][key].graphSpecs
      for (var i in graphSpecs) {
        if (graphSpecs[i][5] == null) {
          types.push(i)
        }
      }
      break
    }
    for (var t in types) {
      var yMax = 0
      for (var key in graphTable[tabname]) {
        var graphSpec = graphTable[tabname][key].graphSpecs[types[t]]
        for (var k in graphSpec[3]) {
          yMax1 = d3.max(graphSpec[3][k], function(d) { return d.y0 + d.y; });
          yMax = Math.max(yMax, yMax1);
        }
      }
      for (var key in graphTable[tabname]) {
        graphTable[tabname][key].graphSpecs[types[t]][5] = yMax
      }
    }
  }
  function drawTabGraphs() {
    var ready = true
    for (var key in graphTable[tabname]) {
      var graph = graphTable[tabname][key]
      if (graph.data == null) {
        ready = false
        break
      }
    }
    if (ready) {
      if (tabname == "vsan-client-host-tab" ||
         tabname == "vsan-domowner-host-tab" ||
         tabname == "vsan-disks-host-tab") {
        normalizeGraphSpecs()
      }
      for (var key in graphTable[tabname]) {
        var graph = graphTable[tabname][key]
        renderGraphs(graph.data, false, 150, 100, graph.graphSpecs)
      }
    }
  }
  function loadJsonForGraph(tabname, key) {
    jQuery.getJSON(
      graphTable[tabname][key].filename,
      function(data) {
        var prefix = graphTable[tabname][key].prefix.replace(/\./g, '-')
        graphTable[tabname][key].data = data;
        graphTable[tabname][key].graphSpecs = graphTable[tabname][key].func(
          graphTable[tabname][key].data,
          "." + prefix
        )
        if (graphTable[tabname][key].needsDiv) {
          var graphNames = []
          for (var i in graphTable[tabname][key].graphSpecs) {
            graphNames.push(graphTable[tabname][key].graphSpecs[i][1])
          }
          addGraphDivs(prefix, graphNames)
          console.log(graphTable[tabname][key].graphSpecs)
        }
        drawTabGraphs()
      }
    )
  }
  if (graphTable[tabname] == null) {
    graphTable[tabname] = []
  }
  d3.selectAll(".graphmini svg").remove()
  for (var key in graphTable[tabname]) {
    var graph = graphTable[tabname][key]
    graphTable[tabname][key].data = null
    graphTable[tabname][key].graphSpecs = null
    loadJsonForGraph(tabname, key)
  }
}

var app = angular.module('vsan', []);
var vmlist;

function extractFilenameFromDsPath(x) {
  var parts = x.split("/")
  return parts[parts.length - 1]
}
function escapeColon(x) {
  //escape colon to make IPv6 work
  return x.replace(/:/g, '\\:')
}
function convertToPrefix(x) {
  return x.replace(/(\.| )/g, '-')
}
app.filter('filterTimerange', function() {
  return function(items, scope) {
    var out = [];
    for (var key in scope.overview) {
      if (!scope.overviewDay) { out.push(key); }
      else {
        var firstTS = scope.overview[key]['firstTS'] * 1000;
        var filterStart = scope.overviewDay.getTime();
        var filterEnd = filterStart + 3600 * 24 * 1000;
        if (firstTS >= filterStart && firstTS <= filterEnd) {
          out.push(key);
        }
      }
    }
    out.sort(function(b, a) {
       return scope.overview[a]['firstTS'] - scope.overview[b]['firstTS'];
    });
    return out;
  }
});

app.factory('vsansparseSvc', function($http) {
  vsansparseList = {}; //openuuid->(filename)
  vsansparseHosts = [];
  vsansparseMaps = {};
  var isDataLoaded = false;
  $http.get('jsonstats/vsansparse/vsansparseList.json').success(function(data) {
    vsansparseList = data;
    $http.get('jsonstats/vsansparse/vsansparseHosts.json').success(function(data) {
      vsansparseHosts = data;
      $http.get('jsonstats/vsansparse/vsansparseMaps.json').success(function(data) {
        vsansparseMaps = data;
        isDataLoaded = true;
      });
    });
  });

  // Return a DOM object UUID from a vsansparse openuuid
  // Open UUIDs have an extra section at the front of the uuid which
  // must be removed to turn it into the DOM object UUID
  function openUuidToUuid(openUuid) {
    if (!isDataLoaded) {
      return false
    }

    uuid = openUuid.replace(/^[0-9a-fA-F]{1,8}-/, '');
    return uuid;
  }

  function getAllOpenUuidsOn(host) {
      results = [];
      for(key in vsansparseList) {
        if (host == vsansparseList[key]) {
          results.push(key);
        }
      }
      return results;
  }

  return {

    isVsanSparse: function(uuid) {

      for (key in vsansparseList) {
        if (openUuidToUuid(key) == uuid) {
          return true;
        }
      }
      return false;
    },


    //Return [hosts]
    getAllHosts: function() {
      return vsansparseHosts;
    },

    // Return {host -> [openUuuids]}
    getAllHostDisks: function() {
      result = {}
      for (key in vsansparseHosts) {
        host = vsansparseHosts[key]
        openUuids = getAllOpenUuidsOn(host);
        result[host] = openUuids;
      }
      return result;
    },

    // Return [openUuuids]
    getAllOpenUuidsOn: getAllOpenUuidsOn,

    // Get all {host -> [openuuids]} that have real uuid open
    getVsanSparseHosts: function(uuid) {
      results = {}
      for(key in vsansparseList) {
        if (openUuidToUuid(key) == uuid) {
          host = vsansparseList[key];
          results[host] = key;
        }
      }
      return results;
    },

    //Return a string of filename if found
    getVsanSparseFilename: function(uuid) {
      result = vsansparseMaps[uuid];
      return result;
    },

    getVsanSparseOpenUuidFilename: function(openuuid) {
      result = vsansparseMaps[openUuidToUuid(openuuid)];
      return result;
    },
  };
});



app.controller("VmListCtrl", function($scope, $http) {
  $scope.query = "";
  //Max number of vsansparse graph lines to show in the vsansparse tab
  $scope.maxVsanSparse = 200;
  $scope.showdisks = false;
  $scope.showVmTab = false;
  $scope.hosts = hosts;
  $scope.overviewKeys = overviewKeys;
  $scope.overview = overview;
  $scope.overviewDirs = overviewDirs;
  $scope.$watch("showVmTab", function(newVal) {
    if (newVal != true) {
      return;
    }
    $http.get('jsonstats/vm/list.json').success(function(data) {
      $scope.vmlist = data;
      $scope.vmvallist = []
      for (var key in $scope.vmlist) {
        $scope.vmlist[key]['show'] = {}
        $scope.vmlist[key]['showdisks'] = false
        $scope.vmvallist.push($scope.vmlist[key])
      }
      vmlist = $scope.vmlist
    });
  })
  $scope.$watch("timerangeOn", function(newVal) {
    if (newVal != true) {
      return;
    }
    $http.get('/timeranges.json').success(function(data) {
      $scope.overviewKeys = data['keys'];
      $scope.overview = data['label'];
      $scope.overviewDirs = data['url'];
    });
    $scope.overviewDay = new Date();
    $scope.overviewDay.setHours(0);
    $scope.overviewDay.setMinutes(0);
    $scope.overviewDay.setSeconds(0);
    $scope.overviewDay.setMilliseconds(0);
  })

  $scope.vsansparseShowHost = {}
  $scope.toggleVsanspaseHost = function(host) {
    $scope.vsansparseHostVisible[host] = !$scope.showVsansparse(host)
  }

  $scope.extractFilenameFromDsPath = function(x) {
    return extractFilenameFromDsPath(x)
  }
  $scope.toggleShow = function (vm, uuid) {
      vm.show[uuid] = !(vm.show[uuid] == true);
  }
  $scope.toggleAllVms = function() {
      $scope.showdisks = !$scope.showdisks
      for (var key in $scope.vmlist) {
          $scope.vmlist[key].showdisks = $scope.showdisks
      }
  }
  $scope.toggleVmShowDisks = function(vm) {
      vm.showdisks = !vm.showdisks
  }
  $scope.convertToPrefix = function(x) {
      return convertToPrefix(x)
  }
  $scope.resultFilter=function(x) {
     return function (task) {
        return (!$scope.showOnlyFailures) || task.result == 'failure';
     }
  }

  // Main filter for vsanSparse
  //
  // If there is a query, then only check the query against 3 properties of the disk
  //
  // Otherwise check if this is a host view or if the parent host is expanded
  $scope.vsansparseShouldShow=function(disk) {
    if ($scope.query) {
      regex = new RegExp($scope.query, "i");
      if (regex.test(disk.host) || regex.test(disk.filename) || regex.test(disk.openuuid))
        return true;
      return false;
    }
    if (!disk.openuuid) {
      return true;
    }
    if (typeof($scope.vsansparseShowHost[disk.host]) !== 'undefined') {
      return $scope.vsansparseShowHost[disk.host];
    }
    return false;
  }
  $scope.vsansparseToggleHost = function(host) {
    $scope.vsansparseShowHost[host] = ! $scope.vsansparseShowHost[host];
  }

});


// Directive to render virtual-disk attributes
app.directive('virtualDisk', function($http, $filter, $compile, vsansparseSvc) {
  return {
    restrict : "AC",
    // replace: true,
    // transclude: true,
    scope : {
      vm : '=virtualDiskVm',
      vdiskid : '@virtualDiskId',
    },
    link : function(scope, _element, attrs) {
      var element = d3.select(_element[0])

      scope.showdetails = {}
      scope.showbackings = false

      scope.$watch("vm", function(newVal, oldVal) {
        updateDom()
      })
      scope.$watch("vdiskid", function(newVal, oldVal) {
        updateDom()
      })
      scope.$watch("showdetails", function(newVal, oldVal) {
        updateDom()
      })
      scope.$watch("showbackings", function(newVal, oldVal) {
        updateDom()
      })
      scope.toggleShowBacking = function (uuid) {
        scope.showdetails[uuid] = !(scope.showdetails[uuid] == true)
        updateDom()
      }
      scope.toggleShowBackings = function () {
        scope.showbackings = !scope.showbackings
      }

      function updateDom() {
        if (scope.vm == null || scope.vdiskid == null) {
          return;
        }

        element.selectAll("div").remove()
        element.selectAll("span").remove()
        element.selectAll("ul").remove()

        var disk = scope.vm.disks[scope.vdiskid]
        if (disk == null) {
          return;
        }
        var backing = null
        element.append("div")
          .attr("class", "header clickable")
          .attr("ng-click", "toggleShowBackings()")
          .attr("ng-class", "{open:showbackings == true}")
          .html("<i ng-hide=\"showbackings == true\" class=\"icon-caret-right\"></i><i ng-show=\"showbackings == true\" class=\"icon-caret-down\"></i> Virtual Disk: " + scope.vdiskid +"<br>")
        if (scope.showbackings) {
            // XXX: Add VSCSI stats!
          var html = [
            "VSCSI device: " + scope.vdiskid,
            "",
            "VSCSI stats:",
            "<div vscsi-graph vscsi-graph-moid='"+scope.vm['moid']+"' vscsi-graph-vmname='"+scope.vm['name']+"' vscsi-graph-dev='"+scope.vdiskid+"'></div>",
          ]
          element.append("div")
            .attr("class", "objectDetails")
            .attr("style", "margin-left: 20px; margin-bottom: 20px")
            .html(html.join("<br>"))

          var ul = element.append("ul")
          backing = disk.backing
          while (backing != null) {
            drawBacking(ul, backing)
            backing = backing.parent
          }
        }
        $compile(_element.contents())(scope)
      }

      function drawBacking(element, backing) {
        var path = extractFilenameFromDsPath(backing.fileName)
        element.append("li")
          .attr("class", "clickable")
          .attr("ng-click", "toggleShowBacking('"+backing.uuid+"')")
          .attr("style", "margin-left: 20px")
          .html("<i ng-hide=\"showdetails[backing.uuid] == true\" class=\"icon-caret-right\"></i><i ng-show=\"showdetails[backing.uuid] == true\" class=\"icon-caret-down\"></i> Backing: " + path + "<br>")
        if (scope.showdetails[backing.uuid] == true) {
          var url = "graphs.html?json=jsonstats/dom/domobj-" + backing.uuid + ".json"
          var html = [
            "DOM Object UUID: " + backing.uuid + " <a href='"+url+"'>Full graphs</a>",
            "",
            "DOM owner:",
            "<div dom-graph dom-graph-uuid='"+backing.uuid+"'></div>",
            //"RAID tree:",
            //"<div raid-tree raid-tree-obj-uuid='"+backing.uuid+"'></div>",
          ]
          if (vsansparseSvc.isVsanSparse(backing.uuid)) {
            html.push("<vsansparse-disk backing=\"'"+ backing.uuid + "'\">");
          }
          element.append("div")
            .attr("class", "objectDetails")
            .attr("style", "margin-left: 20px; margin-bottom: 20px")
            .html(html.join("<br>"))
        }
      }

    }
  }
});

// Toggle directive  - Creates a toggleable div with @text displayed as the clickable
// Creates a new scope
//
// Eg <toggle text="Click to expand">Something that should be viewable via toggle</toggle>
app.directive('toggle', function() {
  return {
    restrict: "E",
    transclude: true,
    scope: {
      text: '=',
    },
    template: "<div class=\"header clickable\" ng-click=\"toggle()\">"
      + "<i ng-hide=\"show\" class=\"icon-caret-right\"></i>"
      + "<i ng-show=\"show\" class=\"icon-caret-down\"></i> {{text}}<br></div>"
      + "<div ng-transclude ng-show=\"show\" class='objectDetails'></div>",
    link: function(scope, element, attrs) {
      scope.show = false;
    },
    controller: function($scope) {
      $scope.toggle = function() {
        $scope.show = !$scope.show;
      };
    },
  }
});


//Replace the given element with minigraphs
function replaceElementWithMiniGraphs(http, element, prefix, dir, graphNames, graphSpecsFunc)
{
  element = d3.select(element[0]);
  var graphsDiv = element.append("div");
  for (i in graphNames) {
    var graph = graphNames[i];
    var klass = prefix;
    if (graph != "") {
      klass = prefix + "-" + graph;
    }
    klass = klass.replace(/(\.|\:)/g, '-');

    var graphDiv = graphsDiv.append("div")
      .attr("class", "mini-graph-container")
      .append("div")
      .attr("class", "graphmini " + klass);
  }

  http.get(dir + prefix + "_thumb.json").success(function(data) {
    var graphSpecs = graphSpecsFunc(data, "." + prefix.replace(/(\.|\:)/g, '-'));
    try {
      renderGraphs(data, false, 150, 100, graphSpecs);
    } catch (err) {
      console.log(["Bad data?", data]);
    }
  });
}

//Directive for <vsansparse-graphs> element
app.directive('vsansparseGraphs', function($http, vsansparseSvc) {
  return {
    restrict: "E",
    scope: {
      host: '=',
      openuuid: '=',
    },
    link: function(scope, element, attrs) {
      var graphTypes = ["iocounts", "layer", "cache"];
      var prefix = "vsansparse-" + scope.host;
      if (scope.openuuid) {
        prefix = prefix + "-" + scope.openuuid;
      }
      replaceElementWithMiniGraphs($http, element, prefix, "jsonstats/vsansparse/", graphTypes, computeVsansparseGraphSpecsThumb);
    },
  };
});


//Directive for <vsansparse-hosts> element
app.directive('vsansparseHosts',  function(vsansparseSvc) {
  return {
    restrict: "E",
    // Can use unsafe, link is providing the html
    template: ["<div ng-if='filteredDisks.length != limitedDisks.length'>",
              "   <b>Note</b> displayed items are limited to {{maxVsanSparse}}",
              "   {{filteredDisks.length - limitedDisks.length}} are hidden due to limit </div>",
              "<table class='graphgrid' style='text-algign: left;'>",
              "  <tbody>",
              "  <tr ng-repeat='disk in (limitedDisks = ((filteredDisks = (disks | filter:vsansparseShouldShow)) | limitTo: maxVsanSparse))' ng-class='disk.objClass' style='padding-bottom:5px'>",
              "    <td style='padding-right: 15px; width: 190px;' valign='top'>",
              "      <span ng-bind-html-unsafe='disk.description'></span><br>",
              "      <a vsansparse-full-graph host='disk.host' path='disk.filename' uuid='disk.openuuid'/>",
              "      <div class='header clickable' ng-if='disk.subitems' ng-click='vsansparseToggleHost(disk.host)'>",
              "        <i ng-hide=\"vsansparseHostVisible[disk.host]\" class=\"icon-caret-right\"></i>",
              "        <i ng-show=\"vsansparseHostVisible[disk.host]\" class=\"icon-caret-down\"></i>",
              "          {{disk.subitems}} open disks on host</div></td>",
              "    <td style='padding-right: 15px;' valign='top'>",
              "     <vsansparse-graphs host='disk.host' openuuid='disk.openuuid'></vsansparse-graphs>",
              "    </td>",
              "  </tr>",
              "  </tbody>",
              "</table>", ].join(""),
    link: function(scope, element, attrs) {
      function updateHosts() {
        hosts = vsansparseSvc.getAllHosts();
        hostDisks = vsansparseSvc.getAllHostDisks();
        results = [];
        for (key in hosts) {
          host = hosts[key];
          entry = {
            host: host,
            openuuid:"",
            description: host,
            subitems: hostDisks[host].length,
          };
          results.push(entry);
          for (disk in hostDisks[host]) {
            openuuid = hostDisks[host][disk]
            filename = escape(vsansparseSvc.getVsanSparseOpenUuidFilename(openuuid));
            entry = {
              host: host,
              openuuid: openuuid,
              description: filename.split('/').reverse()[0],
              objClass: 'objectDetails',
              filename: filename,
            }
            results.push(entry);
          }
        }
        scope.disks = results;
      }

      scope.forceVsanupdate = updateHosts;

      scope.$watch(function() {return vsansparseSvc.getAllHosts() }, function(list) {
        updateHosts();
      });
      updateHosts();
    },
  }
});
app.directive('vsansparseFullGraph', function() {
  return {
    restrict: "A",
    replace: true,
    scope: {
      host: '=',
      uuid: '=',
      path: '=',
    },
    template: "<a href='graphs.html?group=vsansparse&host={{host}}&uuid={{uuid}}&path={{path}}'> Full graphs </a>",
  };
});

// Matches <vsansparse-disk elements>
// Displays a disk based on a real UUID
app.directive('vsansparseDisk', function(vsansparseSvc) {
  return {
    restrict: "E",
    scope : {
      backing: '=',
      useFilename: '=',
    },
  template: [ "<toggle text=toggleText>",
  "<div ng-repeat='(host, openuuid) in hosts'>",
  " Opened on {{host}}",
  "<a  vsansparse-full-graph host='host' uuid='openuuid' path='filename'/>",
  "  <vsansparse-graphs uuid=backing host=host openuuid=openuuid>",
  " </div></toggle>",
  ].join(""),
    link: function(scope, element, attrs) {
      function updateVsansparse() {
        if (vsansparseSvc.isVsanSparse(scope.backing)) {
          hosts = vsansparseSvc.getVsanSparseHosts(scope.backing);
          scope.hosts = hosts;
          filename = escape(vsansparseSvc.getVsanSparseFilename(scope.backing));
          scope.filename = filename;
          if (scope.useFilename) {
            scope.toggleText = filename;
          } else {
            scope.toggleText = "vsanSparse backing";
          }
        }
      }
      scope.$watch(function() {return vsansparseSvc.isVsanSparse(scope.backing); }, function(list) {
        updateVsansparse();
      });

      updateVsansparse();
    },
  }
});


app.directive('vscsiGraph', function($http, $filter) {
  return {
    restrict : "EAC",
    //replace: true,
    //transclude: true,
    scope : {
      moid : '@vscsiGraphMoid',
      vmname : '@vscsiGraphVmname',
      dev : '@vscsiGraphDev',
    },
    link : function(scope, element, attrs) {
      element = d3.select(element[0])

      function updateGraphs() {
        element.selectAll("div").remove()

        var graphsDiv = element.append("div")
        var prefix = "vscsi-" + scope.moid + "-" + scope.dev
        var graphNames = ["latency", "iops", "tput"]
        for (i in graphNames) {
          var graph = graphNames[i]
          var klass = prefix
          if (graph != "") {
            klass = prefix+"-"+graph
          }
          klass = klass.replace(/(\.|\:)/g, '-')

          var graphDiv = graphsDiv.append("div")
            .attr("class", "mini-graph-container")
            .append("div")
                .attr("class", "graphmini "+klass)
        }
      }
      function updateDom() {
        if (scope.moid == null || scope.vmname == null || scope.dev == null) {
          return;
        }
        updateGraphs();
        var filename = 'jsonstats/vm/vscsi-' + scope.dev + '-' + scope.vmname + '_thumb.json'
        $http.get(escape(filename)).success(function(data) {
          scope.stats = data;
          var prefix = "vscsi-" + scope.moid + "-" + scope.dev
          var func = computeVscsiGraphSpecsThumb;
          var graphSpecs = func(data, "." + prefix.replace(/(\.|\:)/g, '-'))
          try {
            renderGraphs(data, false, 150, 100, graphSpecs)
          } catch (err) {
            console.log(["Bad data?", data])
          }

        });
      }
      scope.$watch("moid", function(newVal, oldVal) {
        updateDom()
      });
      scope.$watch("vmname", function(newVal, oldVal) {
        updateDom()
      });
      scope.$watch("dev", function(newVal, oldVal) {
        updateDom()
      });
    }
  }
});

app.directive('domGraph', function($http, $filter) {
  return {
    restrict : "EAC",
    //replace: true,
    //transclude: true,
    scope : {
      uuid : '@domGraphUuid',
    },
    link : function(scope, element, attrs) {
      element = d3.select(element[0])

      function updateGraphs() {
        element.selectAll("div").remove()

        var graphsDiv = element.append("div")
          // .attr("style", "display:inline-block;vertical-align:top;")
          // .attr("class", "graphs")
        var prefix = "domobj-" + scope.uuid
        var graphNames = ["latency", "iops", "tput", "congestion", "oio", "latencySD"]
        if (scope.uuid.indexOf("client") != -1) {
          graphNames.push("domClientCacheHitRate");
        }

        for (i in graphNames) {
          var graph = graphNames[i]
          var klass = prefix
          if (graph != "") {
            klass = prefix+"-"+graph
          }

          var graphDiv = graphsDiv.append("div")
            .attr("class", "mini-graph-container")
//            .attr("style", "margin-top: 0px")
            .append("div")
                .attr("class", "graphmini "+klass)
        }
      }
      scope.$watch("uuid", function(newVal, oldVal) {
          updateGraphs();
          $http.get('jsonstats/dom/domobj-' + scope.uuid + '_thumb.json').success(function(data) {
            scope.objstats = data;
            var prefix = "domobj-" + scope.uuid
            var func = computeDomGraphSpecsThumb;
            var graphSpecs = func(data, "." + prefix.replace(/\./g, '-'))
            try {
                renderGraphs(data, false, 150, 100, graphSpecs)
            } catch (err) {
                alert("foo");
                console.log(["Bad data?", data])
            }

          });
      });
    }
  }
});

app.directive('lsomCompGraph', function($http, $filter) {
  return {
    restrict : "EAC",
    //replace: true,
    //transclude: true,
    scope : {
      uuid : '@lsomCompGraphUuid',
    },
    link : function(scope, element, attrs) {
      element = d3.select(element[0])

      function updateGraphs() {
        element.selectAll("div").remove()

        var graphsDiv = element.append("div")
        var prefix = "lsomcomp-" + scope.uuid
        var graphNames = ["latency", "iops", "rc", "evictions", "rawar", "rc_plog_cb"]
        for (i in graphNames) {
          var graph = graphNames[i]
          var klass = prefix
          if (graph != "") {
            klass = prefix+"-"+graph
          }

          var graphDiv = graphsDiv.append("div")
            .attr("class", "mini-graph-container")
            .append("div")
                .attr("class", "graphmini "+klass)
        }
      }
      scope.$watch("uuid", function(newVal, oldVal) {
          updateGraphs();
          $http.get('jsonstats/lsom/lsomcomp-' + scope.uuid + '_thumb.json').success(function(data) {
            scope.objstats = data;
            var prefix = "lsomcomp-" + scope.uuid
            var func = computeLsomHostGraphSpecsThumb;
            var graphSpecs = func(data, "." + prefix.replace(/\./g, '-'))
            try {
                renderGraphs(data, false, 150, 100, graphSpecs)
            } catch (err) {
                console.log(["Bad data?", data])
            }

          });
      });
    }
  }
});

app.directive('raidTree', function($http, $filter, $compile) {
  return {
    restrict : "C",
    //replace: true,
    //transclude: true,
    scope : {
      uuid : '@raidTreeObjUuid',
    },
    link : function(scope, _element, attrs) {
      var element = d3.select(_element[0])

      $http.get('jsonstats/cmmds/disks.json').success(function(data) {
        scope.disks = data;
      });

      scope.$watch("uuid", function(newVal, oldVal) {
          $http.get('jsonstats/cmmds/cmmds-' + scope.uuid + '.json').success(function(data) {
            scope.cmmds = data;
          });
      });

      scope.$watch("cmmds", function(newVal, oldVal) {
        updateRaidTree();
      });
      scope.$watch("disks", function(newVal, oldVal) {
        updateRaidTree();
      });

      function updateRaidTree() {
        element.selectAll("div").remove()
        element.selectAll("table").remove()
        if (scope.disks == null || scope.cmmds == null) {
            return
        }
        disks = scope.disks
        obj = scope.cmmds['DOM_OBJECT'][0]['content']
        owner = scope.cmmds['DOM_OBJECT'][0]['owner']
        owner_host = disks['hostnames'][owner]
        if (!owner_host) {
          owner_host = owner
        }
        //element.append("div").text($filter('json')(obj))

        function componentsInDomConfig(config) {
            var out = {}
            if ($.inArray(config['type'], ["Witness", "Component"]) >= 0) {
                out[config['componentUuid']] = config
            } else {
                for (var key in config) {
                    var m = /child-\d+/.exec(key)
                    if (m != null) {
                        jQuery.extend(out, componentsInDomConfig(config[key]))
                    }
                }
            }
            return out
        }
        element.append("div").text("DOM Owner: " + owner_host)
        var table = element.append("table").attr("class", "raidTable")

        function printDomTreeInt(config, comps, indent) {
            var type = config['type']
            if ($.inArray(type, ["RAID_0", "RAID_1", "Concatenation"]) >= 0) {
              var tr = table.append("tr").attr("valign", "top")
              var td = tr.append("td")
                .text(type)
                .attr("style", "padding-left: " + (indent * 10) + "px")
            }
            if ($.inArray(type, ["Witness", "Component"]) >= 0) {
              var text = []
              var comp = comps[config['componentUuid']]
              if (comp && comp['props']) {
                  for (var key in comp['props']) {
                      var val = comp['props'][key]
                      text.push("<span class='label1'>" + key + ":</span> <span class='value1'>" + val + "</span>" )
                  }
              }
              text = text.join("<br>")
              var tr = table.append("tr").attr("valign", "top")
              var td = tr.append("td")
                .text(type)
                .attr("style", "padding-left: " + (indent * 10) + "px")
              tr.append("td").text(config['componentUuid'])
              tr.append("td").text(comp['state'])
              tr.append("td").html(text)

              if (type == "Component") {
                tr = table.append("tr").attr("valign", "top")
                tr.append("td").text("")
                tr.append("td")
                  .attr("colspan", "3")
                  .html("<div lsom-comp-graph lsom-comp-graph-uuid='"+config['componentUuid']+"'></div>")
              }
            }
            for (var key in config) {
                var m = /child-\d+/.exec(key)
                if (m != null) {
                    printDomTreeInt(config[key], comps, indent + 1)
                }
            }
        }

        var comps = componentsInDomConfig(obj)
        var csn = obj['attributes']['CSN']

        for (var key in comps) {
            var comp = comps[key]
            var attr = comp['attributes']
            var state = attr.componentState
            var compUuid = comp.componentUuid
            var stateNames = {
              "0": "FIRST",
              "1": "NONE",
              "2": "NEED_CONFIG",
              "3": "INITIALIZE",
              "4": "INITIALIZED",
              "5": "ACTIVE",
              "6": "ABSENT",
              "7": "STALE",
              "8": "RESYNCHING",
              "9": "DEGRADED",
              "10": "RECONFIGURING",
              "11": "CLEANUP",
              "12": "TRANSIENT",
              "13": "LAST",
            }
            var stateName = String(state)
            if (stateNames[stateName] != null) {
                stateName = stateNames[stateName]
            }
            comps[key]['state'] = stateName
            var props = {
            }
            if (stateName == "6" && attr['staleCsn']) {
                if (attr['staleCsn'] != csn) {
                    props['csn'] = "STALE (" + attr['staleCsn'] + "!=" +csn+ ")"
                }
            }
            if (attr['bytesToSync'] && String(attr['bytesToSync']) != "0") {
                // XXX: Format properly as %.2f GB
                props['bytesToSync'] = String(attr['bytesToSync'])
            }
            md = disks[comp.diskUuid]
            if (md && md['info'] && md['info']['diskName']) {
              props['HDD'] = md['info']['diskName']
            } else {
              props['HDD UUID'] = comp.diskUuid
            }
            ssd_uuid = md['content']['ssdUuid']
            ssd = disks[ssd_uuid]
            if (ssd && ssd['info'] && ssd['info']['diskName']) {
              props['SSD'] = ssd['info']['diskName']
            } else {
              props['SSD UUID'] = ssd_uuid
            }

            props['Host'] = md['hostname']

            comps[key]['props'] = props
        }

        printDomTreeInt(obj, comps, -1)
        $compile(_element.contents())(scope)
      };
    }
  }

});
