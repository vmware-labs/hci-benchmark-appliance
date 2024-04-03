
from esxcli import CLIHandler, ArgStream
from esxcli import CLIParseException, CLIExecuteException, LogException
from optparse import OptionParser, Values
from Session import Session, SessionOptions

import logging
import operator
import shlex
import sys
import cmd
from pyVmomi import VmomiSupport, Vim

NS_DELIM = '.'

class NamespaceError(Exception):
   _errType = "Namespace error"

class Namespace:
   def __init__(self, name):
      self._name = name
      self._subnamespaces = {}
      self._commands = {}

   def _AddSubNamespace(self, ns):
      if ns not in self._subnamespaces:
         if ns in self._commands:
            raise NamespaceError('AddSubnamespace: Name collision')
         self._subnamespaces[ns] = Namespace(ns)

      return self._subnamespaces[ns]

   def AddCommand(self, cmdName, cmdObj):
      if cmdName in self._commands:
         raise NamespaceError('Command %1 already present in ns' % cmd.name)

      if cmdName in self._subnamespaces:
         raise NamespaceError('AddCommand : Name collision')

      self._commands[cmdName] = cmdObj

   def AddNamespace(self, namespace):
      if namespace == '':
         return self
      nsComponents = namespace.split(NS_DELIM, 1)
      ns = self._AddSubNamespace(nsComponents[0])
      if len(nsComponents) == 2:
         ns = ns.AddNamespace(nsComponents[1])

      return ns

   def GetSubnamespace(self, subns):
      if subns == '':
         return self
      return self._subnamespaces[subns]

   def GetCommand(self, cmd):
      return self._commands[cmd]

class NamespaceHandler:
   def __init__(self, esxcliUtil):
      self._rootNamespace = Namespace('')
      self._esxcliUtil = esxcliUtil

   def ImportNamespace(self, destNs, sourceNs):
      if isinstance(destNs, str):
         ns = self._rootNamespace.AddNamespace(destNs)
      else:
         ns = destNs

      (nsComp, app, providerCmds) = self._esxcliUtil.GetCmdsInNamespace(sourceNs)
      for cmdName,methodObj in providerCmds.items():
         ns.AddCommand(methodObj.displayName, (nsComp, app, methodObj))

      subnamespaces = self._esxcliUtil.GetSubnamespaces(sourceNs)
      for s in subnamespaces:
         self.ImportNamespace(ns.AddNamespace(s), sourceNs + NS_DELIM + s)

   def ImportCmd(self, destCmd, srcCmd):
      destNs,cmdName = destCmd.rsplit(NS_DELIM, 1)
      ns = self._rootNamespace.AddNamespace(destNs)
      ns.AddCommand(cmdName, self._esxcliUtil.GetCmd(srcCmd))

   def GetRootNamespace(self):
      return _rootNamespace

   def PrintNsTree(self, ns=None, prefix=''):
      if ns == None:
         ns = self._rootNamespace
      nsName = prefix + ns._name + NS_DELIM
      print(nsName)
      for k,v in sorted(ns._subnamespaces.items(), key=operator.itemgetter(0)):
         self.PrintNsTree(v, nsName)
      for j in sorted(ns._commands.keys()):
         print(nsName + j)

   def PrintNamespaceInfo(self, nsName, ns):
      print('Namespace %s' % nsName)
      print('\nAvailable Namespaces : ')
      for k in sorted(ns._subnamespaces.keys()):
         print(k + NS_DELIM)
      print('\nAvailable Commands : ')
      for c in sorted(ns._commands.keys()):
         print(c)


   def Execute(self, cmd, args):
      cmdComps = cmd.split(NS_DELIM)
      nsComps = cmdComps[:-1]
      cmdName = cmdComps[-1]

      ns = self._rootNamespace
      try:
         for n in nsComps:
            ns = ns.GetSubnamespace(n)
      except KeyError:
         print('Cmd %s not found' % cmd)
         return

      try:
         (sourceNs, app, method) = ns.GetCommand(cmdName)
         params = self._esxcliUtil._handler.ParseArgs(method, args)
         result = self._esxcliUtil._handler._Execute(app, method, params)
         if result:
            message = self._esxcliUtil._handler._FormatResult(method, result)
            print(message)
      except KeyError:
         try:
            ns = ns.GetSubnamespace(cmdName)
            self.PrintNamespaceInfo(cmd, ns)
         except KeyError:
            print('Cmd %s not found' % cmd)
            return
      except CLIParseException as err:
         # Parse error
         try:
            message = self._esxcliUtil._handler._FormatHelp(sourceNs, app, method, err.message)
            print(message)
         except Vim.Fault.NotAuthenticated as err:
            LogException(err)
            message = err.msg
         except Exception as err:
            LogException(err)
            message = "Runtime error"
      except CLIExecuteException as err:
         # Execution exception
         message = err.message
         LogException(err)

   def ProcessRules(self, rulesFile):
      f = open(rulesFile)
      for line in f:
         args = line.split()
         if len(args) == 0 or line[0] == '#':
            continue

         c = args[0]
         if c == 'IMPORT_NAMESPACE':
            self.ImportNamespace(args[1], args[2])
         elif c == 'IMPORT_CMD':
            self.ImportCmd(args[1], args[2])
         else:
            print('Ignoring line %s' % line)


class DummyHandler(CLIHandler):
   def __init__(self, host, username, pwd):
      CLIHandler.__init__(self)
      opts = Values({
            'server' : host,
            'portnumber' : 443,
            'username' : username,
            'password' : pwd
            })
      sessionOptions = SessionOptions(opts)
      self.session = Session(sessionOptions)
      self.session.Login()

   def ParseArgs(self, method, args):
      argStream = ArgStream(args)
      parameters = {}
      while not argStream.Empty():
         arg = argStream.Pop()
         if self._IsOption(arg) and (not arg == "-" or arg == "--"):
            # Split "="
            splitOption = arg.split('=', 1)
            if len(splitOption) > 1 and splitOption[1]:
               argStream.Push(splitOption[1])
            option = splitOption[0]
            (param, val) = self._ParseCLIParameter(method, option, argStream)

            # Store parameters. Only array type can be duplicated
            valSet = parameters.setdefault(param.name, val)
            if valSet is not val:
               if issubclass(param.vmomiInfo.type, VmomiSupport.Array):
                  valSet += val
               else:
                  message = "Duplicated option " + option
                  raise NamespaceError(message)
         else:
            # Got  leftover option
            # For this version, do not allow leftover options
            message = "Invalid option " + arg
            raise NamespaceError(message)

      return parameters


class EsxcliUtil:
   def __init__(self, host, username, pwd):
      self._handler = DummyHandler(host, username, pwd)

   def GetCmdsInNamespace(self, ns):
      nsComps = ns.split(NS_DELIM)
      if len(nsComps) != 2:
         return ('', None, {})
      apps = self._handler._GetApps(nsComps[0], nsComps[1])
      if len(apps) == 0:
         raise NamespaceError('Namespace %s not found' % ns)
      if len(apps) > 1:
         raise NamespaceError('Ambiguous specification : Impl error')

      return (nsComps[0], apps[0], apps[0].methods)

   def GetCmd(self, cmd):
      nsComps = cmd.split(NS_DELIM)
      if len(nsComps) != 3:
         raise KeyError

      apps = self._handler._GetApps(nsComps[0], nsComps[1])
      if len(apps) == 0:
         raise NamespaceError('Command %s not found' % cmd)

      return (nsComps[0], apps[0], apps[0].methods.get(VmomiSupport.Capitalize(nsComps[2])))

   def GetSubnamespaces(self, ns):
      nsComps = ns.split(NS_DELIM)
      if ns == '':
         return [n.name for n in self._handler._GetNamespaces()]
      elif len(nsComps) == 1:
         return [app.name for app in self._handler._GetApps(nsComps[0])]
      else:
         return []

class EsxcliCmd(cmd.Cmd):
   def __init__(self, nsHandler):
      cmd.Cmd.__init__(self)
      self._nsHandler = nsHandler
      self.prompt = 'esxcli>'

   def emptyline(self):
      self._nsHandler.Execute('', [])

   def default(self, line):
      #TODO: error handling
      args = shlex.split(line)
      self._nsHandler.Execute(args[0], args[1:])

   def do_EOF(self, line):
      return True

   def do_printTree(self, line):
      self._nsHandler.PrintNsTree()

   def do_quit(self, line):
      sys.exit(0)


def AddOptions(parser):
   parser.add_option("-H", "--host",
                      default="localhost",
                      help="host to get esxcli information from")
   parser.add_option("-u", "--user",
                     default="root",
                     help="User name to use when connecting to hostd")
   parser.add_option("-p", "--password",
                     default="",
                     help="Password to use when connecting to hostd")
   parser.add_option("-n", "--namespaceFile", default=None,
                     help="Rules specifying the namespace organization")

def main():
   parser = OptionParser()
   AddOptions(parser)
   (options, args) = parser.parse_args()
   if options.namespaceFile == None:
      print('Namespace rules file needs to be specified')
      return

   nsHandler = NamespaceHandler(EsxcliUtil(options.host, options.user, options.password))
   nsHandler.ProcessRules(options.namespaceFile)
   EsxcliCmd(nsHandler).cmdloop()


#TODO: exception handling, import cmd, rename/remove cmd
if __name__ == '__main__':
   main()


