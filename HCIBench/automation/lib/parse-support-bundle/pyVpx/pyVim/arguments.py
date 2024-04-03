## @file arguments.py
## @brief Arguments class for command-line parsing (use optparse instead!)
##
## Detailed description (for Doxygen goes here)
"""
Arguments class for command-line parsing (use optparse instead!).

Detailed description (for [e]pydoc goes here)
"""

import getopt
import sys
from six.moves import range


##
## @brief Arguments class for command-line parsing (use optparse
## instead!)
##
## No detailed description.
##
class Arguments:
    """
    Arguments class for command-line parsing (use optparse instead!)

    No detailed description.
    """

    (ARG_KBDINPUT, ARG_DEFAULTVAL, ARG_PROGRAMSET) = list(range(3))

    def __init__(self, argv, supportedArgs, supportedToggles):
        """
        Initialize an Arguments instance.
        """

        self.programName = argv[0]
        self.argList = argv[1:]
        self.keyValueMap = {}

        # Format for supported args, supported toggles:
        # ( [<Possible input options>], <Default>, <Help text>, <Key locator>)
        # Ex:
        #  supportedArgs =  [ (["h:", "host="], "localhost", "Host name", "host"),
        #                     (["u:", "user="], "root", "User name", "user"),
        #                     (["p:", "pwd="], "", "Password", "pwd")
        #                   ]
        #  supportedToggles = [ (["q", "quickcnx"], False, "Connect immediately on startup", "quickcnx"),
        #                       (["usage", "help"], False, "Show usage information", "usage")
        #                     ]
        self.supportedArgs = supportedArgs
        self.supportedToggles = supportedToggles
        self.simpleList = ""
        self.longList = []

        # Process defaults into the key-value map and create the arg list
        for argList in self.supportedArgs:
            argVals, default, help, name = argList
            for args in argVals:
                if str.endswith(args, ":") == True and len(args) == 2:
                    self.simpleList = self.simpleList + args
                    self.keyValueMap[name] = (default,
                                              Arguments.ARG_DEFAULTVAL,
                                              default, help)
                elif str.endswith(args, "=") == True:
                    self.longList.append(args)
                    self.keyValueMap[name] = (default,
                                              Arguments.ARG_DEFAULTVAL,
                                              default, help)
                else:
                    print("Internal argument parsing failure: " + args)
                    sys.exit(2)

        for argList in self.supportedToggles:
            argVals, default, help, name = argList
            for args in argVals:
                if str.endswith(args, ":") == False and len(args) == 1:
                    self.simpleList = self.simpleList + args
                    self.keyValueMap[name] = (default,
                                              Arguments.ARG_DEFAULTVAL,
                                              default, help)
                elif str.endswith(args, "=") == False:
                    self.longList.append(args)
                    self.keyValueMap[name] = (default,
                                              Arguments.ARG_DEFAULTVAL,
                                              default, help)
                else:
                    print("Internal argument parsing failed: " + args)
                    sys.exit(2)

        # Read user specified overrides for defaults
        try:
            opts, args = getopt.gnu_getopt(self.argList, self.simpleList,
                                           self.longList)
        except getopt.GetoptError:
            print("Error encountered processing arguments: ", argv)
            raise

        for opt, arg in opts:
            # I assume this entry exists for anything in the options list
            (val, help, name, argsNeeded) = self.FindTupleForOption(opt)

            if argsNeeded:
                self.keyValueMap[name] = (arg, Arguments.ARG_KBDINPUT, val,
                                          help)
            else:
                self.keyValueMap[name] = (not val, Arguments.ARG_KBDINPUT, val,
                                          help)

        self.unprocessedArgs = args

    # Search through supported args and supported toggles to find the data
    # for a given option
    # Returns (Default, help text, unique name)
    def FindTupleForOption(self, opt):
        for argList in self.supportedArgs:
            argVals, default, help, name = argList
            for args in argVals:
                if str.endswith(args, ":") == True and len(args) == 2:
                    argChoices = "-" + str.rstrip(args, ":")
                    if argChoices == opt:
                        return (default, help, name, True)
                elif str.endswith(args, "=") == True:
                    argChoices = "--" + str.rstrip(args, "=")
                    if argChoices == opt:
                        return (default, help, name, True)

        for argList in self.supportedToggles:
            argVals, default, help, name = argList
            for args in argVals:
                if str.endswith(args, ":") == False and len(args) == 1:
                    argChoices = "-" + args
                    if argChoices == opt:
                        return (default, help, name, False)
                else:
                    argChoices = "--" + args
                    if argChoices == opt:
                        return (default, help, name, False)

    # For a give name, retrieve the value
    def GetKeyValue(self, name):
        (val, source, default, help) = self.keyValueMap[name]
        return val

    # For a given name, retrieve the following:
    # (value, source of value, default, help)
    def GetKeyTuple(self, name):
        return self.keyValueMap[name]

    # For a given name, set the value.
    # Returns old value
    def SetKeyValue(self, name, val):
        if name in self.keyValueMap:
            (oldval, source, default, help) = self.keyValueMap[name]
        else:
            default = ""
            help = ""
            oldval = None
        self.keyValueMap[name] = (val, Arguments.ARG_PROGRAMSET, default, help)
        return oldval

    # Generate program usage instructions
    def Usage(self):
        print("Usage instructions: ")
        print(self.programName, " <options>")
        print("Options: \n")
        for argList in self.supportedArgs:
            argVals, default, help, name = argList
            argChoices = ""
            for args in argVals:
                if str.endswith(args, ":") == True and len(args) == 2:
                    argChoices = argChoices + "-" + str.rstrip(args, ":")
                    argChoices = argChoices + ","
                elif str.endswith(args, "=") == True:
                    argChoices = argChoices + "--" + str.rstrip(args, "=")
                    argChoices = argChoices + ","
            argChoices = str.rstrip(argChoices, ",")
            print("\t", argChoices, "\t\t: ", help, " (Default: ", default,
                  ")")

        for argList in self.supportedToggles:
            argVals, default, help, name = argList
            argChoices = ""
            for args in argVals:
                if str.endswith(args, ":") == False and len(args) == 1:
                    argChoices = argChoices + "-" + args
                    argChoices = argChoices + ","
                else:
                    argChoices = argChoices + "--" + args
                    argChoices = argChoices + ","
            argChoices = str.rstrip(argChoices, ",")
            print("\t", argChoices, "\t\t: ", help, " (Default: ", default,
                  ")")

    def GetProgramName(self):
        return self.programName

    def GetArgList(self):
        return self.argList

    def GetUnprocessedArgs(self):
        return self.unprocessedArgs

    def PrintDebugInfo(self):
        print("Program name      : ", self.GetProgramName())
        print("Arguments passed  : ", self.GetArgList())
        print("Unprocessed args  : ", self.GetUnprocessedArgs())
        print("Supported args    : ", self.supportedArgs)
        print("Supported toggles : ", self.supportedToggles)
        print("Key-value map     : ", self.keyValueMap)
        print("Getopt lists      : ", self.simpleList)
        print("Getopt lists (Ext): ", self.longList)

    def PrintCurrentArgList(self):
        print("Key value map    : ")
        print(self.keyValueMap)
