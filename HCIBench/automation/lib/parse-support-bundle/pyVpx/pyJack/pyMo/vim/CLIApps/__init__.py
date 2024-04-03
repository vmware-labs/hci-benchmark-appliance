#!/usr/bin/env python

# cliBase order is important
_cliBase = ["CLIInfo", "CLIInfoMgr", "CLIDecorators", "CLIInfoImpl"]
_cliSpec = []
_cliImpl = []
__all__ = _cliBase + _cliSpec + _cliImpl

# Import __all__
for name in __all__:
   __import__(name, globals(), locals(), [], 1)
