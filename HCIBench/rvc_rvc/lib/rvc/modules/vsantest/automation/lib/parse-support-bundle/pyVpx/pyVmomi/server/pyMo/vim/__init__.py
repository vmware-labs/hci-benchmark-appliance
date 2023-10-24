"""
Copyright 2008-2022 VMware, Inc.  All rights reserved. -- VMware Confidential
"""

try:
    __import__("DynamicTypeManager", globals(), locals(), [], 1)
except Exception:
    import sys
    import logging
    import traceback

    logging.error("Failed to import DynamicTypeManager")
    stackTrace = " ".join(traceback.format_exception(
                        sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2]))
    logging.error(stackTrace)
