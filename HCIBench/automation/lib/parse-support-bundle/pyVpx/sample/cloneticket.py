#!/usr/bin/python

import sys
from pyVmomi import Vim, SoapStubAdapter
from pyVmomi import VmomiSupport
from pyVim.connect import Connect
from pyVim import arguments


def loginWithTicket(host, port, ticket):
    stub = SoapStubAdapter(host=host,
                           port=port,
                           version="vim.version.version9")
    si = Vim.ServiceInstance("ServiceInstance", stub)
    sm = si.GetContent().GetSessionManager().CloneSession(ticket)


def main():
    supportedArgs = [(["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "", "Password", "pwd")]

    supportedToggles = [(["burn", "use"], False, "Burn the ticket", "burn"),
                        (["usage",
                          "help"], False, "Show usage information", "usage")]

    args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
    if args.GetKeyValue("usage") == True:
        args.Usage()
        return

    # Connect
    si = Connect(host=args.GetKeyValue("host"),
                 user=args.GetKeyValue("user"),
                 pwd=args.GetKeyValue("pwd"),
                 version="vim.version.version9")

    # Obtain a ticket
    sm = si.GetContent().GetSessionManager()
    ticket = sm.AcquireCloneTicket()
    print "Clone Ticket: " + ticket

    if not args.GetKeyValue("burn") == True:
        return

    # Use the ticket
    try:
        (host, port) = args.GetKeyValue("host").split(":", 1)
        port = int(port)
    except ValueError, ve:
        host = args.GetKeyValue("host")
        port = 902

    print "first attempt to clone session..."
    loginWithTicket(host, port, ticket)
    print "successfully cloned session"

    # Make sure it only works once
    try:
        print "second attempt to clone session..."
        loginWithTicket(host, port, ticket)
    except Vim.Fault.InvalidLogin:
        print "second clone attempt failed (as expected)"


# Start program
if __name__ == "__main__":
    main()
