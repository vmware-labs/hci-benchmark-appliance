__all__ = ["VibCommand", "VibCommandImpl", "Defs",
           "DbCommand", "DbCommandImpl", "DefsImpl",
           "ProfileCommand", "ProfileCommandImpl",
           "DepotCommand", "DepotCommandImpl"]

for name in __all__:
   try:
      __import__(name, globals(), locals(), [], 1)
   except Exception:
      import sys
      import logging
      import traceback

      logging.error("Failed to import " + name)
      stackTrace = " ".join(traceback.format_exception(
                            sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2]))
      logging.error(stackTrace)
