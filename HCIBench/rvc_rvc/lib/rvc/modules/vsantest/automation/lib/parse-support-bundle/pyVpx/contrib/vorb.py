# Copyright 2009-2021 VMware, Inc. All rights reserved.
# VMware Confidential

# vorb.py: a Python VMOMI object request broker
#
from optparse import OptionParser, Values
import PyVmomiServer
from MoManager import GetMoManager
from .logUtils import LoggingFactory

class VmomiOrb:
   def __init__(self):
      pass

   @staticmethod
   def AddOptions(parser, defaultSoapPort=8088):
      parser.add_option('-P', '--port', dest='port', type='int', default=defaultSoapPort,
                        help='Web server port')
      parser.add_option('-H', '--host', dest='host', default="",
                        help='Server Address or hostname')
      parser.add_option('-W', '--workers', dest='max_workers', type='int', default=8,
                        help='The size of the worker thread pool. Use 0 for infinity.')
      parser.add_option('-S', '--stdin', dest='stdin', default=False,
                        action='store_true', help='Enable stdin/stdout mode')
      parser.add_option("-g", "--cgi", dest="cgi", action="store_true",
                         help="CGI mode: process a single SOAP request as a CGI script")
   @staticmethod
   def ProcessOptions(options, args):
      return { 'soapPort': options.port,
               'soapHost': options.host,
               'stdin': options.stdin,
               'cgi': options.cgi,
               'max_workers': options.max_workers
             }

   def InitializeServer(self, vorbOptions, defaultToCgiMode=False):
      self._soapPort = vorbOptions['soapPort']
      # Initialize the PyVmomi server
      pyVmomiServerOptions = Values()

      if vorbOptions['stdin']:
         pyVmomiServerOptions.interactive = True
      elif vorbOptions['cgi'] or defaultToCgiMode:
         pyVmomiServerOptions.cgi = True
      else:
         pyVmomiServerOptions.port = vorbOptions['soapPort']
         pyVmomiServerOptions.host = vorbOptions['soapHost']

      pyVmomiServerOptions.max_workers = vorbOptions['max_workers']
      pyVmomiServerOptions.ignorePyMo = True
      PyVmomiServer.Initialize(options=pyVmomiServerOptions)

   def GetSoapPort(self):
      return self._soapPort

   @staticmethod
   def RegisterObject(obj, moId=None, serverGuid=None):
      GetMoManager().RegisterObject(obj, moId, serverGuid)

   ## Register a python managed object factory
   #
   # @param  moType Managed object type for which the factory
   #         is being registered
   # @param  serverGuid the serverGuid of the managed object
   # @param  moFactory Factory instance that can create objects of type moType
   @staticmethod
   def RegisterMoFactory(moFactory, moType, serverGuid=None):
      GetMoManager().RegisterMoFactory(moFactory, moType, serverGuid)

   def RunServer(self, authChecker = None):
      PyVmomiServer.Run(authChecker)

def RunVmomiOrb(registerFunc, optionHandler=None, defaultToCgiMode=False,
                authChecker = None):
   parser = OptionParser()
   LoggingFactory.AddOptions(parser)
   VmomiOrb.AddOptions(parser)
   if optionHandler:
      optionHandler.AddOptions(parser)
   (options, args) = parser.parse_args()
   LoggingFactory.ParseOptions(options)
   vorbOptions = VmomiOrb.ProcessOptions(options, args)
   if optionHandler:
      optionHandler.ProcessOptions(options, args)
   vorb = VmomiOrb()
   vorb.InitializeServer(vorbOptions, defaultToCgiMode)
   registerFunc(vorb)
   vorb.RunServer(authChecker)

