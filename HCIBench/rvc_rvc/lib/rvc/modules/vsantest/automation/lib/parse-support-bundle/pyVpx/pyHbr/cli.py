# Copyright (c) 2021-2022 VMware, Inc.  All rights reserved.
# -- VMware Confidential
#
# pyHbr.cli.py
#
# HBR sub-command command-line interface (cli) support.
#
# Usage:
#
#   # First create a CommandSet;
#   cmdSet = pyHbr.cli.CommandSet()
#
#   # Then add commands:
#   cmdSet.Add("fooness", MyFooness)
#   cmdSet.Add("bar", AddBar)
#
#   # Now this:
#   cmdSet.PrintUsage()
#   # Will print command line usage based on signature of callback functions
#

import optparse
import inspect
import textwrap

class SubCommand():
   """
   Encapsulate a single sub-command, its callback, the number of arguments
   it expects, and the list of optparse options (if any) it supports.

   The set of required/optional positional command line arguments is
   defined by the signature of the callback function.  The --help/help
   output for the command is generated from the signature too.

   The functions python doc is used as usage text.

   If any --foo -style options are supported, they'll be a
   """

   def __init__(self,
                mainCmd,
                name,         # string name of sub-command e.g. 'newtinyvm'
                callback,     # callback
                options=None, # optional optparse Options
                ):
      """
      Create a new subcommand with the given name that maps to the given
      callback.  Options is a list of optparse options the command can
      support.

      The mainCmd is the name of the main script.  Used for generating
      useful help strings.

      The command-line parser is generated from the signature of the given
      callback.
      """

      assert mainCmd != None
      assert name != None
      assert callback != None
      assert callable(callback)

      self._name = name
      self._mainCmd = mainCmd
      self._callback = callback

      # Figure out the expected options from the callback signature
      (args, vararg, kwarg, self.defaults) = inspect.getargspec(callback)
      assert vararg is None  # only simple command line args
      assert kwarg is None  # only simple command line args

      # Count number of parameters that have default values
      defaultCt = 0
      if self.defaults: defaultCt = len(self.defaults)

      self.args = args

      self.maxArgCt = len(self.args)
      self.requiredArgCt = self.maxArgCt - defaultCt

      # Deal with optparse style options (i.e., --file=bar).  Options are
      # passed to the 'options' parameter (which should be the first
      # parameter to the callback).
      if options:
         if args[0] != "options":
            raise RuntimeError("First parameter of callback must be 'options'" +
                               " if options are supported.")

         # Hide the "options" parameter from command-line converter
         self.args = args[1:]
         self.maxArgCt -= 1
         self.requiredArgCt -= 1

         # Generate the optparse option parser for this sub-command
         self.optionParser = optparse.OptionParser()
         for opt in options:
            self.optionParser.add_option(opt)

         # I don't like the way OptionParser prints/formats its help
         # strings.  So, override its help print routine with mine.
         self.optionParser.print_help = lambda: self.PrintUsage()
      else:
         self.optionParser = None

   def ParseOptions(self, args):
      """
      Parse the given array of (command-line) arguments.  Return an tuple
      of (options, args), where 'options' is an object with the options
      set, and 'args' are the remaining command-line arguments (if any).
      """

      assert self.optionParser
      return self.optionParser.parse_args(args)

   def Invoke(self, args):
      """
      Invoke this command with the given array of strings as its
      arguments.  (Presumably its sys.argv[2:] or something equivalent.)

      Makes sure a sufficient number of arguments are passed.  Parse out
      any optparse-style optional parameters in the 'options' parameter.

      optionParser will handle --help option, too.
      """

      options = None
      if self.optionParser:
         (options, args) = self.ParseOptions(args)
      else:
         # Always at least support --help
         if len(args) == 1 and args[0] == "--help":
            return self.PrintUsage()

      argCt = len(args)
      if argCt < self.requiredArgCt or argCt > self.maxArgCt:
         if argCt == 0:
            return self.PrintUsage()

         print("ERROR: Argument count mis-match (%s requires %u, got %u)" \
               % (self._name, self.requiredArgCt, len(args)))
         self.PrintUsage()
         return 126

      if self.optionParser:
         # Stick the 'options' object at the front (not counted in arg counts)
         args.insert(0, options)

      return self._callback(*args)

   def _GenCmdLineDesc(self):
      """
      Generate a description of the command line for this subcommand.
      Returns an array, something like:
          [ "<firstarg>", "<secondarg>", "[thirdarg]"]
      Uses the parameter names from the function declaration.

      Also generates the list of 'default' values for the optional
      positional arguments.

      Returns a tuple of the two lists (args, defaults)
      """

      strArgs = []
      strDefs = []

      if self.optionParser:
         strArgs.append("[Options]")

      # for i = [0 to requiredArgCt to maxArgCt]:
      i = 0
      while i < self.requiredArgCt:
         strArgs.append("<%s>" % self.args[i])
         i = i + 1
      while i < self.maxArgCt:
         a = self.args[i]
         strArgs.append("[%s]" % a)
         strDefs.append("%s default is '%s'" % (a, self.defaults[i - self.maxArgCt]))
         i = i + 1

      return (strArgs, strDefs)


   def _GenDocPara(self):
      """
      Generate a pleasantly formatted documentation for this command from
      the python function doc attached to it.

      Returned as a list of strings, one string per line out output.
      """

      pydoc = self._callback.__doc__
      if not pydoc:
         return ["Undocumented"]

      result = []

      # Strip leading whitespace, as each doc comments are often indented
      doc = textwrap.dedent(pydoc)

      # Split into paragraphs (textwrap would jam them together otherwise)
      for para in doc.split('\n\n'):
         # For each paragraph, re-format it to fit 80 columns nicely
         for l in textwrap.wrap(para, 72 - 8):
            result.append("\t" + l.strip())
         result.append("")

      return result


   def PrintUsage(self):
      """
      Print usage information for this particular command.  Use the python
      function doc text.  Include expected arguments and default values
      (if any).
      """

      (argsDesc, defaultsDesc) = self._GenCmdLineDesc()
      doc = self._GenDocPara();

      print("Usage: {} {} {}".format(self._mainCmd, self._name, ' '.join(argsDesc)))
      for l in self._GenDocPara():
         print(l)

      if defaultsDesc:
         print("Defaults:")
         for l in defaultsDesc:
            print("\t{}".format(l))
         print("")

      if self.optionParser:
         print(self.optionParser.format_option_help())

      return 0


class CommandSet():
   """
   A set of SubCommands.  New commands are added with Add(), and can be
   retrieved with Lookup().

   Supports printing a --help style usage dump of all the subcommands
   defined in this set.
   """

   def __init__(self, mainCmd):
      self._cmds = {}
      self._mainCmd = mainCmd

      # Put 'help' in the list ...
      self.Add("help", lambda: self.PrintUsage())

   def Add(self, name, callback, options=None):
      # Must be a novel command object
      assert name not in self._cmds
      self._cmds[name] = SubCommand(self._mainCmd, name, callback, options)

   def Lookup(self, name):
      return self._cmds.get(name, None)

   def Commands(self):
      """
      Return a list of all commands defined in this command set.
      """
      return self._cmds.keys()

   def PrintUsage(self):
      print("Usage %s <subcommand> [<subcommand options>]:" % (self._mainCmd))
      print("Subcommands:")
      for c in sorted(self._cmds):
         print("\t %s" % c)
         #print("\t %s" % c, ' '.join(self._cmds[c].args))
      return 1

   def PrintCommandHelp(self, args):
      if len(args) > 0:
         c = args[0]
         if not c in self._cmds:
            print("Unknown command: '{}'".format(c))
            return 1
         else:
            return self._cmds[c].PrintUsage()
      else:
         return self.PrintUsage()

#eof
