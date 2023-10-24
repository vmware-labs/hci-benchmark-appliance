"""
Copyright 2010-2022 VMware, Inc.  All rights reserved. -- VMware Confidential
"""

import logging
import logging.handlers
import os.path
import sys
import six

class LoggingFactory:
   logFormat = "%(asctime)s [%(processName)s %(levelname)s '%(name)s' %(threadName)s] %(message)s"
   logSizeMB = 1
   numFiles = 2

   @staticmethod
   def AddOptions(parser, defaultLogFile=None, defaultLogLevel='debug',
                  defaultIdent=None, defaultSyslog=False):
      parser.add_option('-L', '--logfile', dest='logfile', default=defaultLogFile,
                        help='Log file name')
      parser.add_option('--loglevel', dest='loglevel', default=defaultLogLevel,
                        help='Log level')
      parser.add_option('-s', '--syslogident', dest='syslogident',
                        default=defaultIdent, help='Syslog Ident')

   @staticmethod
   def ParseOptions(options):
      logLevelMap = {'fatal': logging.CRITICAL,
                     'critical': logging.CRITICAL,
                     'error': logging.ERROR,
                     'warning': logging.WARNING,
                     'info': logging.INFO,
                     'debug': logging.DEBUG}
      logLevel = options.loglevel in logLevelMap and \
          logLevelMap[options.loglevel] or logging.DEBUG

      maxBytes = LoggingFactory.logSizeMB * 1024 * 1024
      backupCount = LoggingFactory.numFiles - 1

      # Set root logger config
      rootLogger = logging.getLogger()
      rootLogger.setLevel(logLevel)

      if options.syslogident:
         try:
            # Log to syslog
            defaultAddress = '/dev/log'
            fmt = '%(asctime)s ' + options.syslogident + '[%(process)d]: %(threadName)s: %(message)s'
            datefmt = "%b %d %H:%M:%S"
            syslogFormatter = logging.Formatter(fmt=fmt, datefmt=datefmt)
            syslogHandler = logging.handlers.SysLogHandler(defaultAddress)
            syslogHandler.setLevel(logLevel)
            syslogHandler.setFormatter(syslogFormatter)
            rootLogger.addHandler(syslogHandler)
         except:
            import traceback
            six.print_('Configuring logging to syslog failed: %s' \
                        % traceback.format_exc(), file=sys.stderr)
            # Since logging to syslog (as specified on the command-line) failed,
            # Just drop log message (see bug 650178).
            rootLogger.addHandler(NullHandler())

      handler = None

      if not options.logfile:
         if not options.syslogident:
            # No logfile specified: log to standard eror
            handler = logging.StreamHandler(sys.stderr)
      elif options.logfile == '-':
         # Log to standard output
         handler = logging.StreamHandler(sys.stdout)
      else:
         # Log to specified logfile
         logFile = os.path.normpath(options.logfile)
         handler = logging.handlers.RotatingFileHandler(filename=logFile,
                                                        maxBytes=maxBytes,
                                                        backupCount=backupCount)

      if handler:
         # Add handler only if logging to standard output or a specified logfile
         handler.setLevel(logLevel)
         formatter = logging.Formatter(LoggingFactory.logFormat)
         handler.setFormatter(formatter)
         rootLogger.addHandler(handler)

### The NullHandle class below was copied from Python-2.7.1/Lib/logging/__init__.py.
### We need it because we can't depend on Python 2.7 features (yet).

# Null handler

class NullHandler(logging.Handler):
    """
    This handler does nothing. It's intended to be used to avoid the
    "No handlers could be found for logger XXX" one-off warning. This is
    important for library code, which may contain code to log events. If a user
    of the library does not configure logging, the one-off warning might be
    produced; to avoid this, the library developer simply needs to instantiate
    a NullHandler and add it to the top-level logger of the library module or
    package.
    """
    def handle(self, record):
        pass

    def emit(self, record):
        pass

    def createLock(self):
        self.lock = None
