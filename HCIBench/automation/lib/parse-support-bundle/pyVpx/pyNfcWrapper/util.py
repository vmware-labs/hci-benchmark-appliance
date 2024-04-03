import logging

from cwrapper import *

# map NFC log levels to log levels for the python logging library
_logLevelMap = {
   NFC_LOGLEVEL_ERROR:   logging.ERROR,
   NFC_LOGLEVEL_WARNING: logging.WARNING,
   NFC_LOGLEVEL_INFO:    logging.INFO,
   NFC_LOGLEVEL_DEBUG:   logging.DEBUG
}

# default values for the buffer size and buffer count
# for NFC async IO
NFC_AIO_DEFAULT_BUF_SIZE = 65536
NFC_AIO_DEFAULT_BUF_COUNT = 4

def CreateLogFunc(logger):
   """Creates a callback function that forwards logs from the
   nfcWrapper library to the logging library.

   Note: you must hold on to this function while it is needed
   because ctypes won't and it might get garbage collected.
   """
   def LogFunc(level, message):
      logger.log(_logLevelMap[level], message.rstrip(" \n"))
   return NfcWrapperLogFunc(LogFunc)
