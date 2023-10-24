#!/usr/bin/env python

## @file vimApiGraph.py
## @brief Set of classes that describe the VIM API as a graph of managed objects.
##
## The implementation is data driven.
"""
Classes that describe the VIM API as a graph of managed
objects.

The implementation is data driven.
"""

from pyVmomi import types, Vmodl, Vim
import pyVim.vimApiTypeMatrix
import pyVim.moMapDefs
from functools import reduce

_LogLevel = 0


def Log(level, message):
    if level <= _LogLevel:
        print(message)


##
## @brief Description of constraints that might be placed on a managed
## object instance.
##
## Description of constraints that might be placed on a managed object instance.
## This constraint applies to a managed object instance of a specific type.  It
## describes a constraint for a property paths from a managed object indicating
## what other managed objects may be referred to by the property path.  The
## property path may either point at another constraint node or it may refer to
## a type of managed object.
##
## The lack of a constraint on a property path indicates that there are no
## constraints on what the path may be associated.  Setting the constraint on
## property path to indicate the empty set will effectively disable traversal
## of the path.  The list of constraints on a property path matches using logical
## 'or' semantics.  Property paths are ignored unless they satisfy one of the
## constraints.  Only the first one will be used to satsify the constraint, so
## this is not quite a fully featured constraint propagation system.
##
class NodeConstraint:
    ##
    ## @brief Constructs a constraint for a managed object instance node.
    ##
    ## The name of the node can be used by other NodeConstraint
    ## instances to refer to this node.
    ##
    def __init__(self, name, type, traverseConstraints):
        self._name = name
        self._type = type
        self._traverseConstraints = traverseConstraints

    ##
    ## @brief Get name of the node.
    ##
    ## This is either the the name of the class instance
    ## or it is the type name.
    ##
    def GetName(self):
        return self._name

    ## Get the type of the managed object.
    def GetType(self):
        return self._type

    ## Is there a constraint defined for a property path on the managed object?
    def IsConstrained(self, propPath):
        return propPath in self._traverseConstraints

    ##
    ## @brief List of constraints that apply to property path of managed object.
    ##
    ## Gets the list of constraints that apply to the property path of the
    ## managed object.
    ##
    def GetConstraints(self, propPath):
        traverseConstraints = self._traverseConstraints

        if propPath in traverseConstraints:
            return self._traverseConstraints[propPath]
        else:
            return []

    ## Dump the constraint data out to a string.
    def ToString(self):
        traverseConstraints = self._traverseConstraints

        s = "{ name='" + self._name + "' type='" + self._type + "' "
        constrings = [
            "'" + x + "': '" + str(', ').join(traverseConstraints[x]) + "'"
            for x in list(traverseConstraints.keys())
        ]
        s = s + "traverseConstraints=[" + str(', ').join(constrings) + "]"
        s = s + " }"

        return s


##
## @brief Traversal constraint with target that is another constraint node.
##
## Describes a traversal constraint that indicates that the target is another
## constraint node.  In order for the constraint to be satisifed, the target
## node of traversal specification must exist and the type of managed object
## must match that which is specified on the constraint node.
##
class TraversalConstraintNode:
    def __init__(self, nodeName):
        self._nodeName = nodeName

    def IsNodeConstraint(self):
        return True

    def IsTypeConstraint(self):
        return False

    def GetName(self):
        return self._nodeName


##
## @brief Traversal constraint with target that must be of a certain type.
##
## Describes a traversal constraint that indicates that the target must be of
## a certain type.  In order for the constraint to be satisifed, the target
## node of traversal specification must exist and the type of managed object
## must match that which is specified on the constraint node.
##
class TraversalConstraintType:
    def __init__(self, typeName):
        self._typeName = typeName

    def IsNodeConstraint(self):
        return False

    def IsTypeConstraint(self):
        return True

    def GetName(self):
        return self._typeName


#
# Description of the top level inventory structure of the VIM API.  This
# description of the structure is very concrete compared to the one that can
# derived from the VMODL types.
#

# Constraint on ServiceInstance that indicates that the root folder off the
# service instance contains only datacenters or other folders that themselves
# may on contain datacenters or other folders with datacenters.
_serviceInstanceNode = NodeConstraint(
    'serviceInstance', 'vim.ServiceInstance',
    {'content.rootFolder': [TraversalConstraintNode('datacenterFolder')]})

# Description of a folder that contains only datacenters or other folders that
# contani datacenters.
_datacenterFolderNode = NodeConstraint(
    'datacenterFolder', 'vim.Folder', {
        'childEntity': [
            TraversalConstraintNode('datacenterFolder'),
            TraversalConstraintNode('datacenter')
        ]
    })

# Description of a datacenter that contains four folders -- each one
# containing X or folders that contains X with X being one of
# {virtual machine, compute resource, datastore, network}
_datacenterNode = NodeConstraint(
    'datacenter', 'vim.Datacenter', {
        'vmFolder': [TraversalConstraintNode('virtualMachineFolder')],
        'datastoreFolder': [TraversalConstraintNode('datastoreFolder')],
        'networkFolder': [TraversalConstraintNode('networkFolder')],
        'hostFolder': [TraversalConstraintNode('computeResourceFolder')]
    })

# Description of folder that contains only virtual machines or other folders
# containing virtual machines.  Once the virtual machines are reached, no
# further contraints are specified.
_virtualMachineFolderNode = NodeConstraint(
    'virtualMachineFolder', 'vim.Folder', {
        'childEntity': [
            TraversalConstraintNode('virtualMachineFolder'),
            TraversalConstraintType('vim.VirtualMachine')
        ]
    })

# Description of folder that contains only compute resources or other folders
# containing compute resourcesd machines.  Once a compute resource is reached,
# no further contraints are specified.
_computeResourceFolderNode = NodeConstraint(
    'computeResourceFolder', 'vim.Folder', {
        'childEntity': [
            TraversalConstraintNode('computeResourceFolder'),
            TraversalConstraintType('vim.ComputeResource')
        ]
    })

# Description of folder that contains only datastores or other folders
# containing datastores.  Once the datastores are reached, no
# further contraints are specified.
_datastoreFolderNode = NodeConstraint(
    'datastoreFolder', 'vim.Folder', {
        'childEntity': [
            TraversalConstraintNode('datastoreFolder'),
            TraversalConstraintType('vim.Datastore')
        ]
    })

# Description of folder that contains only networks or other folders
# containing networks.  Once the networks are reached, no
# further contraints are specified.
_networkFolderNode = NodeConstraint(
    'networkFolder', 'vim.Folder', {
        'childEntity': [
            TraversalConstraintNode('networkFolder'),
            TraversalConstraintType('vim.Network')
        ]
    })

# Set of constraints that describe how the VIM API types are composed.
_defaultGraphConstraints = [
    _serviceInstanceNode, _datacenterFolderNode, _datacenterNode,
    _virtualMachineFolderNode, _datastoreFolderNode, _networkFolderNode,
    _computeResourceFolderNode
]

# XXX If it's useful, pull out the Graph, Edge, and GraphTraverser classes into
# a separate file where it can be used for general purposes.  Some of the
# traversal generation spec also needs to be teased out of the traverser.


##
## @brief Abstract interface that defines a graph of traversable nodes.
##
## This interface is relied upon by the traversal code to perform an
## exhaustive graph walk.
##
## Graph:
##    NodeName GetRootNode()
##    Edge[]   GetNodeEdges(node)
##
class Graph:
    def __init__(self):
        pass

    # Get the root node of the graph from which to begin traversal.
    def GetRootNode(self):
        raise Exception('Graph.GetRootNode must be implemented')

    # Get the edges of a node used to continue traversal.
    def GetNodeEdges(self, nodeName):
        raise Exception('Graph.GetNodeEdges must be implemented')


##
## @brief Defines a directional edge in the graph of traversable
## nodes.
##
## Edge:
##    string GetName()
##    string GetSourceNode()
##    string GetTargetNode()
##    string GetSourceType() - XXX User specific
##    string GetPropPath() - XXX User specific
##
class Edge:
    def __init__(self, sourceNode, targetNode, sourceType, propPath):
        self._sourceNode = sourceNode
        self._targetNode = targetNode
        self._sourceType = sourceType
        self._propertyPath = propPath

    # Get the name of the edge.  This property identifies the path and can be
    # used to determine duplicate edges.
    def GetName(self):
        return self._sourceNode + "::" + self._propertyPath + "->" + self._targetNode

    # Get the source node of the edge.
    def GetSourceNode(self):
        return self._sourceNode

    # Get the target node of the edge.
    def GetTargetNode(self):
        return self._targetNode

    # VIM API specific property describing the source type of the class
    # represented in the source node.
    def GetSourceType(self):
        return self._sourceType

    # VIM API specific property describing the name of the property from the
    # source type to the target type.
    def GetPropertyPath(self):
        return self._propertyPath


##
## @brief Class that traverses the graph.
##
class GraphTraverser:
    def __init__(self):
        pass

    # Helper function for breadth first traversal
    def DoesSelectionSpecExistForName(self, selectionSet, name):
        match = [x for x in selectionSet if x.GetName() == name]
        return len(match) > 0

    # Helper function to create a traversal spec
    def MakeTraversalSpec(self, name, type, propPath, moList):
        spec = Vmodl.Query.PropertyCollector.TraversalSpec()
        spec.SetName(name)
        spec.SetType(reduce(getattr, type.split('.'), types))
        spec.SetPath(propPath)
        spec.SetSkip(False)
        # Check if we want to capture the property or not.
        if moList is not None:
            flag = not (type in moList)
            spec.SetSkip(flag)
        newSelectSet = []
        spec.SetSelectSet(newSelectSet)
        return spec

    # Helper function to create a selection spec
    def MakeSelectionSpec(self, name, type, propPath):
        spec = Vmodl.Query.PropertyCollector.SelectionSpec()
        spec.SetName(name)
        return spec

    #
    # Build an exhaustive traversal spec from a constraint graph.  This traversal
    # algorithm uses a breadth first search as this heuristic will lead to traversal
    # specs of minimal depth, which should be most intuitive since the managed
    # object hierarchy is hiearchical in nature although it is technically more
    # like a graph.
    #
    # Exhaustive traversal algorithm:
    #
    # A node is a managed object class or instance.  An edge is directional and
    # consists of a property path used to access one managed object class or
    # instance node from another.
    #
    # From a node, enumerate over each edge adding traversal specs for each edge.
    # When a node is visited add either a TraversalSpec or a SelectionSpec for
    # each edge originating from that node if the edge is possible from the
    # constraints.  Add a TraversalSpec if the edge was never previously added.
    # Add a SelectionSpec if the edge was added.  Continue traversal for edges
    # that were not yet visited.
    #
    # @param graph - Mo Graph to traverse to generate the traversal specs
    # @param moList - Managed objects we are interested in for traversal.
    #                 if None we do not skip any object in the traversal.
    # @return rootselectionset - Selection set pivoted on the root managed
    #                            object.
    #
    def Traverse(self, graph, moList=None):
        rootNode = graph.GetRootNode()

        # Selection specs that already have a traversal spec
        existingSelectionSpecs = {}

        # Traversal specs that were traversed.  No need to traverse again.
        visitedEdges = {}

        # Root selection set that is to be returned
        rootSelectionSet = []

        # Queue of traversal context
        workingQueue = [{
            'node': rootNode,
            'currentSelectionSet': rootSelectionSet,
            'level': 0
        }]

        while len(workingQueue) > 0:
            # Remove work item from front of list
            work = workingQueue[0]
            node = work['node']
            currentSelectionSet = work['currentSelectionSet']
            level = work['level']
            workingQueue[0:1] = []

            Log(
                3, "------------------------ Start " + node +
                "-----------------------")
            Log(1, "==> Working on " + node + " at level " + str(level))
            Log(4, "====> Queue length is " + str(len(workingQueue)))

            edges = graph.GetNodeEdges(node)

            for edge in edges:
                propPath = edge.GetPropertyPath()
                nodeType = edge.GetSourceType()
                edgeName = edge.GetName()

                traverseSpecName = node + '::' + propPath

                Log(
                    3, "==> Examining " + edgeName + " (" + traverseSpecName +
                    ")")

                # Add spec only if one does not already exist for the property.
                # Traversal specs are not target type specific.
                if not self.DoesSelectionSpecExistForName(
                        currentSelectionSet, traverseSpecName):
                    spec = {}
                    if traverseSpecName not in existingSelectionSpecs:
                        Log(
                            2, "==> Adding traversal spec for path " +
                            traverseSpecName)
                        spec = self.MakeTraversalSpec(traverseSpecName,
                                                      nodeType, propPath,
                                                      moList)
                        newSelectSet = spec.GetSelectSet()

                        existingSelectionSpecs[traverseSpecName] = spec
                    else:
                        Log(
                            2, "==> Adding selection spec for name " +
                            traverseSpecName)
                        spec = self.MakeSelectionSpec(traverseSpecName,
                                                      nodeType, propPath)

                    currentSelectionSet.append(spec)

                    if (_LogLevel >= 5):
                        Log(5, rootSelectionSet)

                else:
                    Log(
                        4, "==> Skipping path " + propPath +
                        " because spec exists.")

                if edgeName not in visitedEdges:
                    visitedEdges[edgeName] = 1

                    Log(3, "==> Have not traversed edge " + edgeName)
                    newNode = edge.GetTargetNode()

                    # If we've had to add a traversal spec, then we haven't visited this
                    # node yet.
                    workingQueue.append({
                        'node': newNode,
                        'currentSelectionSet': newSelectSet,
                        'level': level + 1
                    })

                    Log(4, "====> Working queue length is " + str(len(workingQueue)) + ": " + \
                        str(', ').join([x['node'] for x in workingQueue]))
                else:
                    Log(3, "==> Already traversed edge " + edgeName)

            Log(
                3, "------------------------ End " + node +
                "-----------------------")

        return rootSelectionSet


##
## @brief Graph of managed objects.
##
## Uses the matrix VIM API types as well as some
## additional semantic constraints to construct a graph where the managed objects
## are nodes and the property paths between them are edges.  The graph represents
## not a specific instantiation of the managed objects but more like a schema
## that describes how the classes interact.
##
## The primary use case for this graph is to be able to generate property
## collector traversal specifications in a more general fashion using just
## constraints and the definition of the types.
##
## @param vimGraph a Matrix of managed objects see vimApiTypeMatrix
## @param nodeList set of constraintsfor the graph
## @param moList list of managed objects for which skip flag is unset.
##
class MoGraph(Graph):
    def __init__(self, vimGraph, nodeList):
        nodes = {}

        for node in nodeList:
            name = node.GetName()
            nodes[name] = node

        self._nodes = nodes
        self._vimGraph = vimGraph
        self._root = None
        if len(nodes) > 0:
            self._root = nodeList[0].GetName()

    # Gets node constraint object by the name of the node
    def GetNodeConstraint(self, nodeName):
        nodes = self._nodes

        if nodeName not in nodes:
            return None

        return nodes[nodeName]

    # Sets node constraint object by name of the node.  If node is None, node
    # constraint is effectively unset.
    def SetNodeConstraint(self, nodeName, node):
        if self._root == None:
            self._root = nodeName
        elif self._root == nodeName:
            self._root = None

        self._nodes[nodeName] = node

    # Sets the root node of the graph.  The root node is by default the first
    # node in the list.  This operation sets it explicitly.
    def SetRootNode(self, nodeName):
        nodes = self._nodes

        if nodeName not in nodes:
            raise Exception('Could not find node ' + nodeName)

        self._root = nodeName

    # Graph.GetRootNode
    #
    # Get the root node of the graph from which to begin traversal.
    def GetRootNode(self):
        if self._root == None:
            raise Exception('Root node in graph not defined')

        return self._root

    # Graph.GetNodeEdges
    #
    # Get the edges of a node used to continue traversal.
    def GetNodeEdges(self, nodeName):
        vimGraph = self._vimGraph
        nodes = self._nodes

        # Node name is either a managed object type or a node constraint node.
        # First see if it is the latter.  Otherwise, treat it as the former.
        node = None
        nodeType = nodeName
        if nodeName in nodes:
            node = nodes[nodeName]
            nodeType = node.GetType()

        # For a type, get the list of edges that are possible candidates.
        candidateEdges = vimGraph.GetEdgesForClass(nodeType)

        # Filter out edges that do not fit constraints specified by the node and
        # traversal constraints.  If the edge passes the filter, then box up the
        # edge in a format that fits the graph abstraction provided by this class.
        edges = []
        for ce in candidateEdges:
            source = ce['source']
            propPath = ce['propPath']
            target = ce['target']

            if node == None or not node.IsConstrained(propPath):
                # No node defined or node is defined but no constraints specified on
                # the property path.  There are no traversal constraints.
                Log(
                    5, "edge(" + source + ", " + propPath + ", " + target +
                    ") is not constrained")
                edges.append(Edge(nodeName, target, source, propPath))
                continue

            constraints = node.GetConstraints(propPath)

            # Constraints exist.  Check that the node matches one of the traversal
            # constraints.  Otherwise, it does not meet constraints.
            edge = None
            for constraint in constraints:
                if constraint.IsTypeConstraint():
                    if constraint.GetName() == target:
                        edge = Edge(nodeName, target, source, propPath)
                elif constraint.IsNodeConstraint():
                    newNodeName = constraint.GetName()
                    if newNodeName in nodes and nodes[newNodeName].GetType(
                    ) == target:
                        Log(
                            5, "edge(" + source + ", " + propPath + ", " +
                            target + ") meets constraints")
                        edge = Edge(nodeName, newNodeName, source, propPath)

            if edge != None:
                Log(
                    5, "edge(" + source + ", " + propPath + ", " + target +
                    ") meets constraints")
                edges.append(edge)
            else:
                Log(
                    5, "edge(" + source + ", " + propPath + ", " + target +
                    ") does not meets constraints")

        return edges


# Create a graph that represents the object model of the VIM API.
# @param moList If mo not in moList then the skip flag will be set.
def CreateMoGraph():
    vimGraph = pyVim.vimApiTypeMatrix.CreateMoTypeMatrix()
    graph = MoGraph(vimGraph, _defaultGraphConstraints)
    return graph


# Create a Molist that includes all inherited classes if the
# parent class is present.
# @param a list of managed objects
# @return a list of managed objects that include inherited
#         classes.
def GetCompleteMoList(moList, classHierarchy):
    newMoList = []
    for mo in moList:
        if mo in classHierarchy:
            newMoList.extend(classHierarchy[mo])
    newMoList.extend(moList)
    return newMoList


# Compute the selection spec that applies to the managed object graph.
def BuildMoGraphSelectionSpec(moList=None):
    if moList:
        moList = GetCompleteMoList(moList, pyVim.moMapDefs.ClassHierarchy)
    graph = CreateMoGraph()
    selectSet = GraphTraverser().Traverse(graph, moList)
    return selectSet


# Test function.
def main():
    vimGraph = pyVim.vimApiTypeMatrix.CreateMoTypeMatrix()
    print(vimGraph.ToString())
    moList = ["vim.ManagedEntity"]
    moList = GetCompleteMoList(moList, pyVim.moMapDefs.ClassHierarchy)
    graph = MoGraph(vimGraph, _defaultGraphConstraints)
    selectSet = GraphTraverser().Traverse(graph, moList)
    print("\nSelection Set:")
    #print selectSet


if __name__ == "__main__":
    main()
