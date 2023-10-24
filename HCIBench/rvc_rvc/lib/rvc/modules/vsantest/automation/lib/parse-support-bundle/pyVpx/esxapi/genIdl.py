#
# Copyright 2011 VMware, Inc.  All rights reserved. -- VMware Confidential
#

__author__ = "VMware, Inc."

from vmidl.visitor import SimpleVisitor
from vmidl.types import Primitive, Struct, StringArray, StructArray

# PyVmomiVisitor: Class that creates PyVmomi data types for
# each VMIDL data type.
class IdlVisitor(SimpleVisitor):
   def __init__(self, fp, cmdIndent):
      self._fp = fp
      self._cmdIndent = cmdIndent

   def VisitEnum(self, t):
      print 'ignoring enum type ' , t.fqName

   def VisitStruct(self, t):
      pass

   def VisitStructArray(self, t):
      pass

   def VisitUnion(self, t):
      print 'ignoring union type ', t.fqName

   def VisitInterface(self, i):
      self._fp.write('interface %s {\n' % (i.fqName.replace('oms.EsxCLI.', '')))
      for c in i.cmdList:
         c.Visit(self)
      self._fp.write('}\n\n')

   def _GetTypeName(self, typ):
      if typ == None:
         return 'void'

      if isinstance(typ, Primitive):
         return typ.PyTypeName()
      if isinstance(typ, Struct):
         return typ.PyTypeName().rsplit('.', 1)[1]
      elif isinstance(typ, StructArray):
         return 'list[%s]' % (self._GetTypeName(typ.scalarType))
      elif isinstance(typ, StringArray):
         return 'list[string]'
      else:
         import pdb; pdb.set_trace()
         return 'UNKNOWN'

   def _GenType(self, t, indent=0):
      indentStr = indent * ' '
      if t == None:
         r = indentStr + 'void'
      elif isinstance(t, Struct):
         structName = self._GetTypeName(t)
         r = indentStr + 'struct {\n'
         r += '\n'.join('%s %s;' % (self._GenType(f.fieldType, indent + 3), f.fieldName)
                        for f in t.fieldList)
         r += '\n%s}' % (indentStr)
      elif isinstance(t, StructArray):
         r = indentStr + 'list [\n'
         r += self._GenType(t.scalarType, indent + 3)
         r += '\n%s]' % (indentStr)
      elif isinstance(t, StringArray):
         r = indentStr + 'list [string]'
      else:
         r = indentStr + t.PyTypeName()

      return r

class IdlVisitorOption1(IdlVisitor):
   def __init__(self, fp):
      IdlVisitor.__init__(self, fp, 3)

   def VisitInterface(self, i):
      self._fp.write('interface %s {\n' % (i.fqName.replace('oms.EsxCLI.', '')))
      structsVisited = []

      # Generate structs
      for c in i.cmdList:
         if isinstance(c.outType, Struct):
            self._GenerateStructs(c.outType, structsVisited)
         elif isinstance(c.outType, StructArray):
            self._GenerateStructs(c.outType.scalarType, structsVisited)

      # Generate methods
      for c in i.cmdList:
         c.Visit(self)

      self._fp.write('}\n\n')

   def VisitCommand(self, c):
      indentStr = ' ' * self._cmdIndent
      indent = self._cmdIndent
      methodName = c.fqName.rsplit('.', 1)[1]
      self._fp.write('%s%s %s(' % (indentStr, self._GetTypeName(c.outType), methodName))
      self._fp.write(', '.join(['%s %s' % (self._GenType(p.paramType), p.paramName)
                                for p in c.paramSpecList]))
      self._fp.write(');\n\n')

   def _GenerateStructs(self, typ, structsVisited):
      indent = self._cmdIndent
      if typ.PyTypeName() in structsVisited:
         return

      for f in typ.fieldList:
         if isinstance(f.fieldType, Struct):
            self._GenerateStructs(f.fieldType, structsVisited)
         elif isinstance(f.fieldType, StructArray):
            self._GenerateStructs(f.fieldType.scalarType, structsVisited)

      self._fp.write(self._GenType(typ, indent))
      self._fp.write('\n\n')
      structsVisited.append(typ.PyTypeName())

   def _GenType(self, t, indent=0):
      indentStr = indent * ' '
      if t == None:
         r = indentStr + 'void'
      elif isinstance(t, Struct):
         fieldIndentStr = ' ' * (indent + 3)
         structName = self._GetTypeName(t)
         r = indentStr + 'struct %s {\n' % (self._GetTypeName(t))
         r += '\n'.join('%s%s %s;' % (fieldIndentStr, self._GetTypeName(f.fieldType), f.fieldName)
                        for f in t.fieldList)
         r += '\n%s}' % (indentStr)
      elif isinstance(t, StructArray):
         r = indentStr + 'list [\n'
         r += self._GenType(t.scalarType, indent + 3)
         r += '\n%s]' % (indentStr)
      elif isinstance(t, StringArray):
         r = indentStr + 'list [string]'
      else:
         r = indentStr + t.PyTypeName()

      return r

class IdlVisitorOption3(IdlVisitor):
   def __init__(self, fp):
      IdlVisitor.__init__(self, fp, 3)

   def VisitCommand(self, c):
      indentStr = ' ' * self._cmdIndent
      indent = self._cmdIndent
      methodName = c.fqName.rsplit('.', 1)[1]
      self._fp.write('%s %s(' % (self._GenType(c.outType, indent), methodName))
      self._fp.write(', '.join(['%s %s' % (self._GenType(p.paramType), p.paramName)
                                for p in c.paramSpecList]))
      self._fp.write(');\n\n')

class IdlVisitorOption4(IdlVisitor):
   def __init__(self, fp):
      IdlVisitor.__init__(self, fp, 3)

   def _GenType(self, t, indent=0):
      indentStr = indent * ' '
      if t == None:
         r = indentStr + 'void'
      elif isinstance(t, Struct):
         structName = self._GetTypeName(t)
         r = indentStr + 'struct {\n'
         for f in t.fieldList:
            if isinstance(f.fieldType, Primitive) or isinstance(f.fieldType, StringArray):
               typeStr = self._GenType(f.fieldType, 0)
            else:
               typeStr = '\n' + self._GenType(f.fieldType, indent + 3)
            r += '%s%s : %s;\n' % (' ' * (indent + 3), f.fieldName, typeStr)

         r += '%s}' % (indentStr)
      elif isinstance(t, StructArray):
         r = indentStr + 'list [\n'
         r += self._GenType(t.scalarType, indent + 3)
         r += '\n%s]' % (indentStr)
      elif isinstance(t, StringArray):
         r = indentStr + 'list [string]'
      else:
         r = indentStr + t.PyTypeName()

      return r

   def VisitCommand(self, c):
      indentStr = ' ' * self._cmdIndent
      indent = self._cmdIndent
      methodName = c.fqName.rsplit('.', 1)[1]
      self._fp.write('%s function %s(' % (indentStr, methodName))
      self._fp.write(', '.join(['%s : %s' % (p.paramName, self._GenType(p.paramType))
                                for p in c.paramSpecList]))
      self._fp.write(') :')
      if isinstance(c.outType, StructArray) or isinstance(c.outType, Struct):
         self._fp.write('\n')
         outIndent = indent + 3
      else:
         self._fp.write(' ')
         outIndent = 0

      self._fp.write(self._GenType(c.outType, outIndent))
      self._fp.write('\n\n')


class IdlVisitorOption5(IdlVisitor):
   def __init__(self, fp):
      IdlVisitor.__init__(self, fp, 3)

   def VisitInterface(self, i):
      self._fp.write('interface %s {\n' % (i.fqName.replace('oms.EsxCLI.', '')))
      structsVisited = []

      # Generate structs
      for c in i.cmdList:
         if isinstance(c.outType, Struct):
            self._GenerateStructs(c.outType, structsVisited)
         elif isinstance(c.outType, StructArray):
            self._GenerateStructs(c.outType.scalarType, structsVisited)

      # Generate methods
      for c in i.cmdList:
         c.Visit(self)

      self._fp.write('}\n\n')

   def VisitCommand(self, c):
      indentStr = ' ' * self._cmdIndent
      indent = self._cmdIndent
      methodName = c.fqName.rsplit('.', 1)[1]
      self._fp.write('%sfunction %s(' % (indentStr, methodName))
      self._fp.write(', '.join(['%s : %s' % (p.paramName, self._GenType(p.paramType))
                                for p in c.paramSpecList]))
      self._fp.write(') : %s\n\n' % (self._GetTypeName(c.outType)))

   def _GenerateStructs(self, typ, structsVisited):
      indent = self._cmdIndent
      if typ.PyTypeName() in structsVisited:
         return

      for f in typ.fieldList:
         if isinstance(f.fieldType, Struct):
            self._GenerateStructs(f.fieldType, structsVisited)
         elif isinstance(f.fieldType, StructArray):
            self._GenerateStructs(f.fieldType.scalarType, structsVisited)

      self._fp.write(self._GenType(typ, indent))
      self._fp.write('\n\n')
      structsVisited.append(typ.PyTypeName())

   def _GenType(self, t, indent=0):
      indentStr = indent * ' '
      if t == None:
         r = indentStr + 'void'
      elif isinstance(t, Struct):
         structName = self._GetTypeName(t)
         r = '%sstruct %s {\n' % (indentStr, self._GetTypeName(t))
         for f in t.fieldList:
            r += '%s%s : %s;\n' % (' ' * (indent + 3), f.fieldName, self._GetTypeName(f.fieldType))

         r += '%s}' % (indentStr)
      elif isinstance(t, StructArray):
         r = indentStr + 'list[\n'
         r += self._GenType(t.scalarType, indent + 3)
         r += '\n%s]' % (indentStr)
      elif isinstance(t, StringArray):
         r = indentStr + 'list[string]'
      else:
         r = indentStr + t.PyTypeName()

      return r


class IdlVisitorOption6(IdlVisitor):
   def __init__(self, fp):
      IdlVisitor.__init__(self, fp, 3)

   def VisitInterface(self, i):
      self._fp.write('%s : interface {\n' % (i.fqName.replace('oms.EsxCLI.', '')))
      structsVisited = []

      # Generate structs
      for c in i.cmdList:
         if isinstance(c.outType, Struct):
            self._GenerateStructs(c.outType, structsVisited)
         elif isinstance(c.outType, StructArray):
            self._GenerateStructs(c.outType.scalarType, structsVisited)

      # Generate methods
      for c in i.cmdList:
         c.Visit(self)

      self._fp.write('}\n\n')

   def VisitCommand(self, c):
      indentStr = ' ' * self._cmdIndent
      indent = self._cmdIndent
      methodName = c.fqName.rsplit('.', 1)[1]
      self._fp.write('%s%s : function(' % (indentStr, methodName))
      self._fp.write(', '.join(['%s : %s' % (p.paramName, self._GenType(p.paramType))
                                for p in c.paramSpecList]))
      self._fp.write(') returns %s\n\n' % (self._GetTypeName(c.outType)))

   def _GenerateStructs(self, typ, structsVisited):
      indent = self._cmdIndent
      if typ.PyTypeName() in structsVisited:
         return

      for f in typ.fieldList:
         if isinstance(f.fieldType, Struct):
            self._GenerateStructs(f.fieldType, structsVisited)
         elif isinstance(f.fieldType, StructArray):
            self._GenerateStructs(f.fieldType.scalarType, structsVisited)

      self._fp.write(self._GenType(typ, indent))
      self._fp.write('\n\n')
      structsVisited.append(typ.PyTypeName())

   def _GenType(self, t, indent=0):
      indentStr = indent * ' '
      if t == None:
         r = indentStr + 'void'
      elif isinstance(t, Struct):
         structName = self._GetTypeName(t)
         r = '%s%s : struct {\n' % (indentStr, self._GetTypeName(t))
         for f in t.fieldList:
            r += '%s%s : %s;\n' % (' ' * (indent + 3), f.fieldName, self._GetTypeName(f.fieldType))

         r += '%s}' % (indentStr)
      elif isinstance(t, StructArray):
         r = indentStr + 'list[\n'
         r += self._GenType(t.scalarType, indent + 3)
         r += '\n%s]' % (indentStr)
      elif isinstance(t, StringArray):
         r = indentStr + 'list[string]'
      else:
         r = indentStr + t.PyTypeName()

      return r

def GenIdl(cls, pkg, fp):
   visitor = cls(fp)
   pkg.Visit(visitor)

def main():
   import esxcliVmidl
   pkg = esxcliVmidl.esxcliVmidlPackage
   #fp = open('/tmp/idl-1.txt', 'w')
   #GenIdl(IdlVisitorOption1, pkg, fp)
   #fp = open('/tmp/idl-3.txt', 'w')
   #GenIdl(IdlVisitorOption3, pkg, fp)
   #fp = open('/tmp/idl-4.txt', 'w')
   #GenIdl(IdlVisitorOption4, pkg, fp)
   fp = open('idl-5.txt', 'w')
   GenIdl(IdlVisitorOption5, pkg, fp)
   #fp = open('/tmp/idl-6.txt', 'w')
   #GenIdl(IdlVisitorOption6, pkg, fp)

if __name__ == "__main__":
   main()
