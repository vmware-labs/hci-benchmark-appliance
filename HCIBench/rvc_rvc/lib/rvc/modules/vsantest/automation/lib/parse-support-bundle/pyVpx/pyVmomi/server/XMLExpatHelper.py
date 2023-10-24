#!/usr/bin/env python
"""
Copyright 2008-2022 VMware, Inc.  All rights reserved. -- VMware Confidential

This module is a helper class for XML parsing with expat
"""
__author__ = "VMware, Inc"


# A helper class for XML Expact parser user. It helps to simplify Expat
# handlers store / restore when working with sub parser
class XMLExpatHelper:
    """A helper class for XML Expact parser user. It helps to simplify Expat
    handlers store / restore when working with sub parser
    """

    # Constructor
    #
    # @param  parser the expat parser
    def __init__(self, parser):
        self.parser = parser
        self.subHandlersStack = []
        self.BypassTagHeight = None
        self.currTag = None

    # Push an expat handler (to handlers stack) and take over subsequent xml
    # elements handling.  The sub-handler will be popped off when the xml tag
    # start/stop is balanced.
    #
    # @param   subHandler the subhandler to use
    # @return  the input subHandler
    def SubHandler(self, subHandler):
        """Push an expat handler to take over xml handling"""
        # Set new subhandler
        self._PushHandler(subHandler)

        # Override subHandler's StartElementHandler & EndElementHandler with
        # our tag balancing handler
        self.parser.StartElementHandler = self._StartElementHandler
        self.parser.EndElementHandler = self._EndElementHandler
        return subHandler

    # Get the current expat parser
    #
    # @return  the expat parser
    def GetParser(self):
        """Get the current expat parser"""
        return self.parser

    # Skip all tags until the end tag is encountered
    # Must be called from StartElementHandler
    #
    # @param tag the end tag
    def SkipUntilEndTag(self):
        """Skip all tags until the end tag is encountered"""
        if self.currTag is not None:
            subHandler, tagStack, origParserHandlers, origSubHandlers = \
                                                       self.subHandlersStack[-1]
            # Start bypass handler mode
            self.BypassTagHeight = len(tagStack) - 1
            assert (self.BypassTagHeight >= 0)
        else:
            # Must be called from StartElementHandler
            assert (False)

    # My StartElementHandler to keep track of xml tag start
    #
    # @param  tag the XML tag
    # @param  attr the XML attribute
    def _StartElementHandler(self, tag, attr):
        """Start XML element"""
        # Get current tagStack
        subHandler, tagStack, origParserHandlers, origSubHandlers = \
                                                      self.subHandlersStack[-1]
        tagStack.append(tag)

        if self.BypassTagHeight is None:
            # Call sub handler's start element handler
            self.currTag = tag
            subHandler.StartElementHandler(tag, attr)
            self.currTag = None
        else:
            # Bypass handler mode
            pass

    # My StartElementHandler to keep track of xml tag stop
    # Pop parser when tag stack is empty
    #
    # @param  tag the XML tag
    def _EndElementHandler(self, tag):
        """End XML element"""
        subHandler, tagStack, origParserHandlers, origSubHandlers = \
                                                      self.subHandlersStack[-1]
        if not tagStack:
            # Pop handler when tag stack is empty
            self._PopHandler()
            subHandler, tagStack, origParserHandlers, origSubHandlers = \
                                                       self.subHandlersStack[-1]

        # Get current end tag
        currTag = tagStack.pop()
        # Expact parser should detect tag mismatch problem
        assert (currTag == tag)
        del currTag

        if self.BypassTagHeight is None or self.BypassTagHeight == len(
                tagStack):
            self.BypassTagHeight = None
            # Call sub handler's end element handler
            subHandler.EndElementHandler(tag)
        else:
            # Bypass handler mode
            pass

    # Save subhandler states onto parser stack
    #
    # @param subHandler the XML sub handler to push onto stack
    def _PushHandler(self, subHandler):
        """Save subhandler states onto parser stack"""
        origParserHandlers = subHandler.ExpatHandlers(self.parser, subHandler)
        origSubHandlers = (subHandler.StartElementHandler,
                           subHandler.EndElementHandler)
        self.subHandlersStack.append(
            (subHandler, [], origParserHandlers, origSubHandlers))

    def _PopHandler(self):
        """Restore subhandler states from parser stack"""
        subHandler, tagStack, origParserHandlers, origSubHandlers = \
                                                      self.subHandlersStack.pop()
        # Override Start/End ElementHandler
        (subHandler.StartElementHandler,
         subHandler.EndElementHandler) = origSubHandlers
        subHandler.ExpatHandlers(self.parser, origParserHandlers)
