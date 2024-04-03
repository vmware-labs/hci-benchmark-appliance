#!/usr/bin/env python

## @file vimApiTypeMatrix.py
## @brief File containing utilities to access and view the VIM API.
##
## Detailed description (for Doxygen goes here)
"""
File containing utilities to access and view the VIM API.

Detailed description (for [e]pydoc goes here)
"""

import pyVim.moMapDefs
from six.moves import range


# Take a field and format it appropriated into a fixed width field
def ToPrintableField(field, fieldWidth):
    if len(field) > fieldWidth:
        field = field[0:fieldWidth]
    else:
        field = field + (' ' * (fieldWidth - len(field)))
    return field


# Get rid of redundant information "vim." prefix
def StripVimPrefix(cls):
    if cls[0:4] == "vim.":
        cls = cls[4:]
    return cls


# Assumes that array is rectangular and has at least one row.
def From2DArrayToString(a):
    numRows = len(a)
    numCols = len(a[0])

    # Compute width for each column
    columnWidths = [0] * numCols
    for row in range(numRows):
        for col in range(numCols):
            if a[row][col] != None:
                w = len(a[row][col])
                if w > columnWidths[col]:
                    columnWidths[col] = w

    # Print out the table
    for row in range(numRows):
        for col in range(numCols):
            s = a[row][col]
            if s == None:
                s = ""
            a[row][col] = ToPrintableField(s, columnWidths[col])

    lines = [[]] * numRows
    for row in range(numRows):
        lines[row] = str(" | ").join(a[row])

    return str("\n").join(lines)


def AddClassIfNew(classes, cls):
    if cls not in classes:
        classes[cls] = len(classes)


##
## @brief Matrix containing the valid set of managed object classes
## and associations in the VIM API model.
##
## This class is a utility class that makes it simple to enumerate
## over all the managed object classes and associations.  It also
## takes into consideration inheritance relationships between managed
## objects.
##
class MoTypeMatrix:
    def __init__(self, references, classHierarchy):
        # Map of references from classes to other classes
        self.references = references

        # Relevant class hierarchy mapping base class to derived classes
        self.classHierarchy = classHierarchy

        # Listing from class name to class id
        self.classes = self.BuildClasses(references, classHierarchy)

    # Build the full list of classes
    def BuildClasses(self, references, classHierarchy):
        classes = {}

        for cls in list(references.keys()):
            AddClassIfNew(classes, cls)

            clsRefs = references[cls]
            for propPath in list(clsRefs.keys()):
                clsReferee = clsRefs[propPath]
                AddClassIfNew(classes, clsReferee)

        for cls in classHierarchy:
            AddClassIfNew(classes, cls)

            for derivedCls in classHierarchy[cls]:
                AddClassIfNew(classes, derivedCls)

        return classes

    # Produce stringified version of the table.
    def ToString(self):
        classList = self.GetClassNames()
        classList.sort()

        a = []

        # Initialize class name index
        classIndex = {}
        for cls in classList:
            classIndex[cls] = len(classIndex)

        # Initialize 2D matrix
        a = [[]] * (len(classList) + 1)
        for col in range(len(a)):
            a[col] = [None] * len(a)

        # Fill in the metadata row and column
        a[0][0] = ""
        for cls in classList:
            idx = classIndex[cls] + 1
            cls = StripVimPrefix(cls)
            a[0][idx] = cls
            a[idx][0] = cls

        # Fill in table entries
        for cls1 in classList:
            row = classIndex[cls1] + 1
            for cls2 in classList:
                col = classIndex[cls2] + 1
                edges = self.GetEdgesBetweenClasses(cls1, cls2)
                a[row][col] = str(', ').join(edges)

        return From2DArrayToString(a)

    # Get the list of property paths from the source class that directly
    # references the target class.
    def GetEdgesBetweenClasses(self, source, target):
        references = self.references
        classHierarchy = self.classHierarchy

        if source not in references:
            return []

        clsRefs = references[source]

        propPaths = []
        for propPath in clsRefs:
            clsReferee = clsRefs[propPath]

            # Look for direct references to target class as well as derived classes
            # of target
            if (clsReferee == target) or \
               (clsReferee in classHierarchy and \
                len([x for x in classHierarchy[clsReferee] if x == target]) > 0):
                propPaths.append(propPath)

        return propPaths

    # Gets the list of edges from a source node.
    def GetEdgesForClass(self, source):
        references = self.references
        classHierarchy = self.classHierarchy

        if source not in references:
            return []

        clsRefs = references[source]

        edges = []
        for propPath in list(clsRefs.keys()):
            clsReferee = clsRefs[propPath]
            edges.append({
                'source': source,
                'target': clsReferee,
                'propPath': propPath
            })

            # Append edges to derived classes if applicable
            if clsReferee in classHierarchy:
                for derivedCls in classHierarchy[clsReferee]:
                    edges.append({
                        'source': source,
                        'target': derivedCls,
                        'propPath': propPath
                    })

        return edges

    # Get all classes
    def GetClassNames(self):
        return list(self.classes.keys())

    # Is the class valid?
    def IsValidClass(self, cls):
        return cls in self.classes


# Create a logically immutable object representing the valid paths through the
# managed object hierarchy.
def CreateMoTypeMatrix():
    return MoTypeMatrix(pyVim.moMapDefs.ValidReferences,
                        pyVim.moMapDefs.ClassHierarchy)


def main():
    matrix = CreateMatrix()
    print(matrix.ToString())


if __name__ == "__main__":
    main()
