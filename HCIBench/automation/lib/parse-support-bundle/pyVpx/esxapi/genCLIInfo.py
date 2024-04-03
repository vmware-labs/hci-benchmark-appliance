from optparse import OptionParser, Values

from pyVmomi import vim, vmodl
from pyVmomi.VmomiSupport import newestVersions
from pyVim.connect import Connect, Disconnect

from pyJack import pyMo
import json

def ParseOptions():
   parser = OptionParser()
   parser.add_option('-H', '--host', dest='host', type='string',
                     help='Host name of service provider')
   parser.add_option('-P', '--port', dest='port', type='int', default = 443,
                     help='Port at which service provider is running')
   parser.add_option('-u', '--user', dest='user', type='string', default='root',
                     help='user name')
   parser.add_option('-p', '--passwd', dest='passwd', type='string', default='',
                     help='password')
   parser.add_option('-F', '--filename', dest='filename', type='string',
                     help='file name to write the cli info to')
   (options, args) = parser.parse_args()
   return options

def GetCLIInfoInstances(stub):
   dtm = vmodl.reflect.DynamicTypeManager('ha-dynamic-type-manager', stub)
   ret = []
   for mo in dtm.QueryMoInstances():
      if mo.moType == 'vim.CLIInfo':
         ret.append(vim.CLIInfo(mo.id, stub))
   return ret

def FetchCliInfo(cliInfoSet, moType):
   for cliInfo in cliInfoSet:
      try :
         return cliInfo.FetchCLIInfo(moType)
      except Exception:
         pass

class CliMetadata:
   def __init__(self, commandName, apiFunction, shortOptions, defaultFormatter):
      self.commandName = commandName
      self.apiFunction = apiFunction
      self.shortOptions = shortOptions
      self.defaultFormatter = defaultFormatter

   def SerializeToJson(self, fp):
      obj = dict(commandName = self.commandName,
                 apiFunction = self.apiFunction)
      # Add short options only if there are values in the dictionary
      if self.shortOptions:
         obj['shortOptions'] = self.shortOptions
      obj['defaultFormatter'] = self.defaultFormatter
      json.dump(obj, fp, indent=3)
      fp.write('\n\n')

def GetHint(hintList, hintName):
   for hint in hintList:
      if hint.key == hintName:
         return hint.value

   return None

def main():
   options = ParseOptions()
   if options.host == None or options.filename == None:
      print 'Please specify host and fileName'
      return

   si = Connect(host=options.host, port=options.port,
                user=options.user, pwd=options.passwd,
                namespace=newestVersions.GetWireId('vim'))
   dtm = vmodl.Reflect.DynamicTypeManager('ha-dynamic-type-manager', si._stub)
   cliInfoSet = GetCLIInfoInstances(si._stub)

   fp = open(options.filename, 'w' )

   for moType in dtm.QueryTypeInfo().managedTypeInfo:
      print "Generating cliInfo for %s" % (moType.name)
      prefix = moType.name.replace('vim.EsxCLI.', '')
      cliInfo = FetchCliInfo(cliInfoSet, moType.name)
      if cliInfo == None:
         continue
      for method in cliInfo.method:
         cmdName = '%s %s' % (prefix.replace('.', ' '), method.displayName)
         apiFunc = '.'.join([prefix, method.name])
         shortOptions = {}
         for param in method.param:
            for alias in param.aliases:
               if alias.startswith('-') and not alias.startswith('--') :
                  shortOptions[param.name] = alias
                  break
         defaultFormatter = GetHint(method.hints, 'formatter')
         if defaultFormatter == '':
            defaultFormatter = 'none'
         cliMetadata = CliMetadata(cmdName, apiFunc, shortOptions, defaultFormatter)
         cliMetadata.SerializeToJson(fp)
         break


if __name__=='__main__':
   main()
