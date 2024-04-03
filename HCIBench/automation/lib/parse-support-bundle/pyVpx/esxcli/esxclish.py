"""
Copyright 2011-2014 VMware, Inc.  All rights reserved. -- VMware Confidential

Shell interface to esxcli.py
"""
__author__ = "VMware, Inc"

import cmd
import sys
import shlex

from optparse  import OptionParser, make_option, SUPPRESS_HELP, Values

from esxcli import *
from Session import Session, SessionOptions

class ShellHandler(CLIHandler):
    def __init__(self):
      CLIHandler.__init__(self)

    def ProcessArgs(self, args):
       cmdOptionsList = SessionOptions.GetOptParseOptions()
       cmdOptionsList.append(make_option("--context", dest="context",
                                         default='', help=SUPPRESS_HELP))
       _STR_USAGE = "%prog [options]"
       cmdParser = OptionParser(option_list=cmdOptionsList, usage=_STR_USAGE,
                                add_help_option=False)

       # Get command line options
       (options, remainingArgs) = cmdParser.parse_args(args)
       sessionOptions = SessionOptions(options)
       self.session = Session(sessionOptions)
       self._ParseContext(options)

    def ClearCmdState(self):
       self.cmdNamespace = None
       self.app = None
       self.method = None
       self.options = Values()
       self.options._update_loose({'formatter' : None, 'debug' : False})
       self.usage = ''

    def ExecuteCommand(self, args):
       try:
          self.ClearCmdState()
          result, message = self._HandleOneCmd(args)
          if message:
             self.Print(message)
             message = ''
       except CLIParseException as err:
          # Parse error
         if err.message:
            logging.error(err.message)

         message = self._FormatHelpNoRaise(self.cmdNamespace,
                                           self.app, self.method, err)
       except CLIExecuteException as err:
          # Execution exception
          message = err.message
       except SessionException as err:
          message = err.message
       except vmodl.MethodFault as err:
          message = "Runtime error: " + err.msg
       except Exception as err:
          LogException(err)
          message = "Runtime error"

       # Print message
       self.Print(message)

class EsxcliCmd(cmd.Cmd):
   def __init__(self, shellHandler):
      cmd.Cmd.__init__(self)
      self._shellHandler = shellHandler
      self.prompt = 'esxcli>'

   def emptyline(self):
      self._shellHandler.ExecuteCommand([])

   def default(self, line):
      #TODO: error handling
      args = shlex.split(line)
      self._shellHandler.ExecuteCommand(args)

   def do_EOF(self, line):
      return True

   def do_quit(self, line):
      sys.exit(0)


def main():
   SetupLogging('esxclish.py')
   argv = sys.argv[1:]
   shellHandler = ShellHandler()
   shellHandler.ProcessArgs(argv)

   EsxcliCmd(shellHandler).cmdloop()


if __name__ == '__main__':
   main()
