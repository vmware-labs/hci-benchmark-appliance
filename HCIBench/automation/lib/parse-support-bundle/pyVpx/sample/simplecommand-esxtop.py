#!/usr/bin/python

## @file simplecommand-esxtop.py
## @brief Internal sample application to fetch esxtop values using the SimpleCommand interface
##
## Sample application that tests the range of the SimpleCommand interface for esxtop.

import sys
from pyVim import pp, arguments
import pyVim.connect
import pyVmomi


class Object:
    ## Constructor
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


# ------------------------------------------------------------------
# Start of Parse ==NUM-OF-OBJ== section of FetchStats Query
# ------------------------------------------------------------------


# Relation Visitors
def Int(ins, d, prop):
    def ConvertInt():
        d[prop] = int(d[prop])

    return ConvertInt


def OptionalInt(ins, d, prop):
    def ConvertOptionalInt():
        if d.has_key(prop):
            d[prop] = int(d[prop])
        else:
            d[prop] = -1

    return ConvertOptionalInt


def Bool(ins, d, prop):
    def ConvertBool():
        d[prop] = bool(int(d[prop]))

    return ConvertBool


def Relation(ins, d, prop):
    def ConvertRelation():
        global relations
        n = int(d[prop])
        d[prop] = []
        for i in xrange(n):
            d[prop].append(Parse(ins, prop))

    return ConvertRelation


def Str(ins, d, prop):
    def ConvertStr():
        d[prop] = str(d[prop])

    return ConvertStr


##
## The following relations describes the hierarchical structure used by esxtop
## to rollup entities.  The hierarchy is not self-describing unlike the counters
## themselves so we describe the hierarchy here.
##
## The hierarchy is version-specific so we've encoded some of the version
## differences here.
##
relations = {
    'Server': [('COS', Int), ('PCPU', Int), ('PMem', Int), ('Sched', Int),
               ('SCSI', Int), ('Net', Int)],
    'PCPU': [('LCPU', Int), ('Core', Int), ('Package', Int)],
    'PMem': [('NUMANode', Bool)],
    'Sched': [('SchedGroup', Relation)],
    'SchedGroup': [('GroupID', Int), ('VMNUMANodeMem', Int),
                   ('GroupName', Str), ('MemClientID', OptionalInt),
                   ('CPUClient', Relation)],
    'CPUClient': [('CPUClientID', Int), ('VCPUName', Str)],
    'SCSI': [('Path', Relation), ('SCSIDevice', Relation),
             ('Adapter', Relation)],
    'Path': [('DeviceName', Str), ('PathName', Str)],
    'SCSIDevice': [('DeviceName', Str), ('DisplayName', Str),
                   ('WorldPerDev', Relation), ('Partition', Relation)],
    'Partition': [('PartitionID', Int)],
    'WorldPerDev': [('WorldID', Str)],
    'Adapter': [('AdapterName', Str), ('Channel', Relation)],
    'Channel': [('ChannelID', Int), ('Target', Relation)],
    'Target': [('TargetID', Int), ('Lun', Relation)],
    'Lun': [('LunID', Int)],
    'Net': [('TotalPorts', Int), ('PNIC', Int), ('NetPortset', Relation)],
    'NetPortset': [('NetPort', Relation)],
    'NetPort': [('PortID', Int), ('PortsetName', Str)],
}
versionedRelations = {}
versionedRelations["vim25/5.5"] = {
    'SchedGroup': [('GroupID', Int), ('VMNUMANodeMem', Int),
                   ('GroupName', Str), ('MemClientID', OptionalInt),
                   ('CPUClient', Relation), ('HiddenWorld', Relation)],
    'HiddenWorld': [('HiddenWorldID', Int), ('HiddenWorldName', Str)],
    'Interrupt': [('InterruptVector', Relation)],
    'InterruptVector': [('VectorID', Int), ('InterruptPerCPU', Int)],
    'Power': [('CState', Int), ('PState', Int), ('TState', Int),
              ('LCPU', Int)],
}

# Top level relations in the hierarchy
toplevelRelations = ('Server', 'PCPU', 'PMem', 'Sched', 'SCSI', 'Net')
versionedToplevelRelations = {}
versionedToplevelRelations["vim25/5.5"] = ('Interrupt', 'Power')


def ParseProps(ins, d, properties):
    for (prop, typ) in properties:
        convertFn = typ(ins, d, prop)
        convertFn()


def Parse(ins, relationName):
    obj = ParseNumObjLine(ins, relationName)
    ParseProps(ins, obj, relations[relationName])
    return obj


def ParseNumObjLine(ins, expectedName):
    line = ins.readline()
    fields = line.split("|")[1:-1]

    name = fields[0]

    if name != expectedName:
        raise Exception("Type mismatch: Expected '%s'.  Got '%s'." %
                        (name, expectedName))

    keyvalues = [["_type", name]] + [field.split(",") for field in fields[1:]]
    #   print "%s: " % name + str(dict(keyvalues))
    return dict(keyvalues)


def ParseEsxtopFetchStats(counterDefs, ins):
    # Parse FetchStats data
    line = ins.readline()
    #   print line
    if line != "==NUM-OF-OBJ==\n":
        raise Exception(
            "Bad start of FetchStats data.  Expecting NUM-OF-OBJ marker.  Got '%s'"
            % line)

    global toplevelRelations
    numObjs = {}
    for relationName in toplevelRelations:
        numObjs[relationName] = Parse(ins, relationName)

    line = ins.readline()
    if line != "==COUNTER-VALUE==\n":
        raise Exception(
            "Bad start of CounterValue data.  Expecting COUNTER-VALUE marker.  Got '%s'"
            % line)

    counters = []
    for line in ins:
        #      print line
        fields = line.split("|")[1:-1]
        typeName = fields[0]
        values = fields[1:]

        counterDef = counterDefs.GetCounter(typeName)
        if not counterDef:
            raise Exception("Counter type '%s'." % typeName)

        # Process the counter by type
        values2 = []
        for (t, v) in zip([t[0] for t in counterDef], values):
            if t == "B":
                values2.append(bool(int(v)))
            elif t == "STR" or t == "CSTR":
                values2.append(v)
            else:
                values2.append(int(v))


#      print zip([t[1] for t in counterDef], values2)
        obj = (typeName, dict(zip([t[1] for t in counterDef], values2)))
        counters.append(obj)

    return (numObjs, counters)


def DumpObj(obj, indent=0):
    out = ""
    if isinstance(obj, dict):
        out += "{\n"
        indent += 1
        for k in obj.keys():
            if k == "_type":
                continue
            out += "   " * indent
            out += k + " "
            out += DumpObj(obj[k], indent)
        indent -= 1
        out += "   " * indent
        out += "}\n"
    elif isinstance(obj, list):
        if len(obj) == 0:
            out += "[]\n"
        else:
            out += "[\n"
            indent += 1
            for o in obj:
                out += "   " * indent
                out += DumpObj(o, indent)
            indent -= 1
            out += "   " * indent
            out += "]\n"
    else:
        out += " = " + str(obj) + "\n"
    return out


def MakeObjTableArray(table, relationName, obj, propStack):
    #   print "MakeObjTableArray(%s)" % relationName
    #   print "Stack: " + str(propStack)
    #   print table
    global relations
    primitiveFields = [
        relation[0] for relation in relations[relationName]
        if relation[1] != Relation
    ]
    relationFields = [
        relation[0] for relation in relations[relationName]
        if relation[1] == Relation
    ]

    for o in obj:
        props = [(f, o[f]) for f in primitiveFields]
        # Prepend all properties from the stack.  The stack contains properties that
        # are considered context for the data
        allprops = reduce(lambda x, y: x + y, propStack, []) + props
        if len(allprops) > 0:
            #         print "Appending: " + str(allprops)
            table[relationName].append(dict(allprops))

    for o in obj:
        for f in relationFields:
            propStack.append([(pf, o[pf]) for pf in primitiveFields])
            MakeObjTableArray(table, f, o[f], propStack)
            propStack.pop()


def MakeObjTable(obj):
    global relations
    table = dict(
        zip(relations.keys(), [[] for i in xrange(len(relations.keys()))]))

    for relationName in toplevelRelations:
        MakeObjTableArray(table, relationName, [obj[relationName]], [])

    return table


# ------------------------------------------------------------------
# End of Parse ==NUM-OF-OBJ== section of FetchStats Query
# ------------------------------------------------------------------


# ------------------------------------------------------------------
# Start of Parse CounterInfo Query
# ------------------------------------------------------------------
class CounterDefs:
    def __init__(self, countersStr):
        self._types = None
        self._types = dict([(g[0], [(c.split(",")[1], c.split(",")[0])
                                    for c in g[1:]])
                            for g in [[cs for cs in css.split("|")][1:-1]
                                      for css in countersStr.split()]])

    def GetTypes(self):
        return self._types.keys()

    def GetCounter(self, typeName):
        if self._types.has_key(typeName):
            return self._types[typeName]
        return None

    def __str__(self):
        return str(self._types)


# ------------------------------------------------------------------
# End of Parse CounterInfo Query
# ------------------------------------------------------------------

# ------------------------------------------------------------------
# Start of Table Printing Utilities
# ------------------------------------------------------------------


# Stringify the table before printing
def PrintTable(table, hasHeader=False):
    print pp.indent(table, hasHeader=hasHeader, wrapfunc=str)


# XXX Support sorting for hidden fields
def SortTable(table, fieldNames, sortFields):
    if fieldNames == None or sortFields == None or len(sortFields) == 0:
        return table

    # Handle inverse sorting by looking for "!" at the beginning of the field name
    sortIndexInvert = []
    for (i, field) in zip(range(len(sortFields)), sortFields):
        if field and len(field) > 1 and field[0] == "!":
            sortIndexInvert.append(True)
            sortFields[i] = field[1:]
        else:
            sortIndexInvert.append(False)

    fieldNameMap = dict(zip(fieldNames, range(len(fieldNames))))
    sortIndexFields = [fieldNameMap[field] for field in sortFields]

    def SortTableFunc(x, y):
        for (i, invert) in zip(sortIndexFields, sortIndexInvert):
            c = cmp(x[i], y[i])
            if c != 0:
                return invert and -c or c
        return 0

    return table.sort(SortTableFunc)


def LimitTable(table, kwargs):
    max = kwargs.has_key('limit') and kwargs['limit'] or None
    if max != None:
        del table[max:]


def ShowTables(data, kwargs):
    global tableDefs
    table = [[
        tk, ", ".join(tableDefs[tk].required),
        ", ".join(tableDefs[tk].optional)
    ] for tk in tableDefs.keys()]

    fields = ["Table", "Required", "Optional"]
    sortFields = kwargs['sort'] and kwargs['sort'] or ["Table"]
    SortTable(table, fields, sortFields)
    LimitTable(table, kwargs)
    PrintTable([fields] + table, hasHeader=True)


# User callable commands
def ShowCounters(data, kwargs):
    #   table = [[t, len(data.defs.GetCounter(t)), ", ".join([f[1] for f in data.defs.GetCounter(t)])] for t in data.defs.GetTypes()]
    table = [[t, len(data.defs.GetCounter(t))] for t in data.defs.GetTypes()]

    #   fields = ["CounterName", "NumFields", "FieldNames"]
    fields = ["Counter", "NumFields"]
    sortFields = kwargs['sort']
    SortTable(table, fields, sortFields)
    LimitTable(table, kwargs)
    PrintTable([fields] + table, hasHeader=True)


def ShowCounter(data, kwargs):
    counter = kwargs['counter']
    if data.defs.GetCounter(counter) == None:
        raise Exception("Invalid counter '%s' specified." % counter)
    table = [[f[0], f[1]] for f in data.defs.GetCounter(counter)]

    fields = ["Type", "Name"]
    sortFields = kwargs['sort']
    SortTable(table, fields, sortFields)
    LimitTable(table, kwargs)
    PrintTable([fields] + table, hasHeader=True)


def SelectCounter(data, kwargs):
    counter = kwargs['counter']
    fields = kwargs['fields']
    if fields == None or len(fields) == 0:
        if data.defs.GetCounter(counter) == None:
            raise Exception("Invalid counter '%s' specified." % counter)
        fields = [f[1] for f in data.defs.GetCounter(counter)]
    if data.valueMap.has_key(counter):
        table = [[c[f] for f in fields] for c in data.valueMap[counter]]
    else:
        table = []

    sortFields = kwargs['sort']
    SortTable(table, fields, sortFields)
    LimitTable(table, kwargs)
    PrintTable([fields] + table, hasHeader=True)


def ShowTopologies(data, kwargs):
    table = [[t, len(data.topologyTable[t])]
             for t in data.topologyTable.keys()]

    fields = ["Topology", "NumEntries"]
    sortFields = kwargs['sort']
    SortTable(table, fields, sortFields)
    LimitTable(table, kwargs)
    PrintTable([fields] + table, hasHeader=True)


def SelectTopology(data, kwargs):
    topology = kwargs['topology']
    fields = kwargs['fields']
    if not data.topologyTable.has_key(topology) or len(
            data.topologyTable[topology]) < 1:
        # Guard needed since we look at the first row to find the schema
        return
    if fields == None or len(fields) == 0:
        # XXX Have the schema available in some way that does not depend on the data
        # and is less susceptible to dictionary ordering issues
        fields = data.topologyTable[topology][0].keys()
    table = [[row[col] for col in fields]
             for row in data.topologyTable[topology]]

    sortFields = kwargs['sort']
    SortTable(table, fields, sortFields)
    LimitTable(table, kwargs)
    PrintTable([fields] + table, hasHeader=True)


optionalAll = ["sort", "limit"]

tableDefs = {
    "tables":
    Object(required=[], optional=optionalAll, func=ShowTables),
    "counters":
    Object(required=[], optional=optionalAll, func=ShowCounters),
    "counter":
    Object(required=["counter"], optional=optionalAll, func=ShowCounter),
    "values":
    Object(required=["counter"],
           optional=["fields"] + optionalAll,
           func=SelectCounter),
    "topologies":
    Object(required=[], optional=optionalAll, func=ShowTopologies),
    "topology":
    Object(required=["topology"],
           optional=["fields"] + optionalAll,
           func=SelectTopology),
}


def Select(data, kwargs):
    table = kwargs.has_key('table') and kwargs['table'] or 'tables'

    for k in tableDefs[table].required:
        if not kwargs.has_key(k):
            raise Exception("Required parameter '%s' not specified." % k)

    # Optional parameters need not be specified.  Make sure they are defined.
    for k in tableDefs[table].optional:
        if not kwargs.has_key(k):
            kwargs[k] = None

    tableDefs[table].func(data, kwargs)

    # XXX Support group-bys
    # XXX Support joins


# ------------------------------------------------------------------
# End of Table Printing Utilities
# ------------------------------------------------------------------

# ------------------------------------------------------------------
# Start of EsxtopReader Utility
# ------------------------------------------------------------------


# Iterator to make a string simulate a file
class StringLineReader:
    def __init__(self, s):
        self._s = s.splitlines()
        self._i = 0

    def readline(self):
        if self._i < len(self._s):
            line = self._s[self._i]
            self._i += 1
            return line + "\n"
        return None

    def close(self):
        self._s = []
        self._i
        return True

    def next(self):
        line = self.readline()
        if line == None:
            raise StopIteration
        return line

    def __iter__(self):
        return self


# The main class that users interact with
# XXX Eliminate the needs to access the internal member variables directly.
class EsxtopReader(object):
    def __init__(self, si=None):
        self._si = si

        self._lastCounterInfo = None
        self._lastFetchStatsStr = None

        self._data = None

    def SetSi(self, si):
        self._si = si

    def SetData(self, countersStr, fetchStatsStr):
        if countersStr != None and fetchStatsStr != None:
            self._data = self.ProcessEsxtopStats(countersStr, fetchStatsStr)

    def Fetch(self):
        self._data = self.FetchEsxtopStats()

    def FetchEsxtopStats(self):
        si = self._si
        esxtop = si.RetrieveInternalContent().serviceManager.service[0].service
        countersStr = esxtop.Execute("CounterInfo")
        fetchStatsStr = esxtop.Execute("FetchStats")
        esxtop.Execute("FreeStats")

        return self.ProcessEsxtopStats(countersStr, fetchStatsStr)

    def ProcessEsxtopStats(self, countersStr, fetchStatsStr):
        self._lastCounterInfo = countersStr
        self._lastFetchStats = fetchStatsStr

        counterDefs = CounterDefs(countersStr)

        lr = StringLineReader(fetchStatsStr)
        (obj, counters) = ParseEsxtopFetchStats(counterDefs, lr)
        lr.close()

        counterMap = {}
        for counter in counters:
            typeName = counter[0]
            if not counterMap.has_key(typeName):
                counterMap[typeName] = []
            counterMap[typeName].append(counter[1])

        topologyTable = MakeObjTable(obj)

        return Object(defs=counterDefs,
                      objs=obj,
                      valueMap=counterMap,
                      topologyTable=topologyTable)

    def Select(self, table=None, **kwargs):
        if self._data == None:
            if self._si:
                self.Fetch()
            else:
                raise Exception("No esxtop data source.")
        kwargs['table'] = table
        Select(self._data, kwargs)


# ------------------------------------------------------------------
# End of EsxtopReader Utility
# ------------------------------------------------------------------


# Test main function
def main():
    # Argument mgmt
    supportedArgs = [
        (["h:", "host="], "", "Host name", "host"),
        (["u:", "user="], "root", "User name", "user"),
        (["p:", "pwd="], "", "Password", "pwd"),
        (["n:", "namespace="], "vim25", "Namespace", "namespace"),
        (["c:",
          "counterinfofile="], "", "CounterInfo File", "counterinfofile"),
        (["f:", "fetchstatsfile="], "", "FetchStats File", "fetchstatsfile"),
    ]
    supportedToggles = [
        (["i", "interactive"], False, "Interactive Mode", "interactive"),
        (["H", "help"], False, "Help", "help"),
    ]
    args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
    host = args.GetKeyValue("host")
    user = args.GetKeyValue("user")
    pwd = args.GetKeyValue("pwd")
    namespace = args.GetKeyValue("namespace")
    counterinfofile = args.GetKeyValue("counterinfofile")
    fetchstatsfile = args.GetKeyValue("fetchstatsfile")
    interact = args.GetKeyValue("interactive")
    help = args.GetKeyValue("help")

    if help:
        args.Usage()
        return None

    # XXX Only handles 1 level of versioning
    global versionedRelations
    if versionedRelations.has_key(namespace):
        global relations
        relations.update(versionedRelations[namespace])

    # XXX Only handles 1 level of versioning
    global versionedToplevelRelations
    if versionedToplevelRelations.has_key(namespace):
        global toplevelRelations
        toplevelRelations += versionedToplevelRelations[namespace]

    si = None
    if host:
        si = pyVim.connect.Connect(host,
                                   user=user,
                                   pwd=pwd,
                                   namespace=namespace)

    countersStr = None
    if counterinfofile:
        ins = open(counterinfofile, "r")
        countersStr = ins.read()
        ins.close()

    fetchStatsStr = None
    if fetchstatsfile:
        ins = open(fetchstatsfile, "r")
        fetchStatsStr = ins.read()
        ins.close()

    esxtop = EsxtopReader(si)
    esxtop.SetData(countersStr, fetchStatsStr)

    if interact:
        interactive(esxtop)
    else:
        testwalk(esxtop)

    return esxtop


def testwalk(esxtop):
    print '==================== esxtop.Select() ===================='
    esxtop.Select()

    print '==================== esxtop.Select("counters") ===================='
    esxtop.Select("counters")

    # Iterate each counter definition followed by the values
    for t in esxtop._data.defs.GetTypes():
        print '==================== esxtop.Select("counter", counter="%s") ====================' % t
        esxtop.Select("counter", counter=t)

        print '==================== esxtop.Select("values", counter="%s") ====================' % t
        esxtop.Select("values", counter=t)

    print '==================== esxtop.Select("topologies") ===================='
    esxtop.Select("topologies")

    # Iterate each topology
    for t in esxtop._data.topologyTable.keys():
        print '==================== esxtop.Select("topology", topology="%s") ====================' % t
        esxtop.Select("topology", topology=t)

    print '==================== DumpObj(esxtop._data.objs) ===================='
    print DumpObj(esxtop._data.objs)

    print '==================== esxtop.Execute("CounterInfo") ===================='
    print esxtop._lastCounterInfo

    print '==================== esxtop.Execute("FetchStats") ===================='
    print esxtop._lastFetchStats


# Run interactive mode in the python interpreter
def interactive(e):
    global esxtop
    esxtop = e

    esxtop.Select()

    # Examples
    # esxtop.Select(table="counters", sort=["!NumFields", "Counter"])
    # esxtop.Select(table="counter", counter="VCPU")
    # esxtop.Select(table="values", counter="VCPU", fields=["VCPUID", "WorldName", "UsedTimeInUsec", "SysTimeInUsec"])
    # esxtop.Select(table="values", counter="VCPU", fields=["VCPUID", "WorldName", "UsedTimeInUsec", "SysTimeInUsec"], sort=["!UsedTimeInUsec"])

    # Example of fetching data from the server
    # esxtop.Fetch()
    # esxtop.Select(table="values", counter="VCPU", fields=["VCPUID", "WorldName", "UsedTimeInUsec", "SysTimeInUsec"], sort=["!UsedTimeInUsec"])

    # Example of fetching some data periodically
    # import time
    # for i in xrange(10): esxtop.Fetch() or (esxtop.Select(table="values", counter="VCPU", fields=["VCPUID", "WorldName", "UsedTimeInUsec", "SysTimeInUsec"], sort=["!UsedTimeInUsec"]) or time.sleep(2))
    # for i in xrange(10): esxtop.Fetch() or esxtop.Select(table="values", counter="NetPort", sort=["!NumOfSendPackets", "!NumOfRecvPackets"]) or time.sleep(2)

    # View the topology
    # esxtop.Select("topology", topology="CPUClient")


if __name__ == "__main__":
    main()
