#!/usr/bin/python
"""
Python program for creating a user on a host on which hostd is running

Requirements:
 * pyVmomi, pyVim
 * Needs to be invoked with py.sh rather than regular python executable
 * The target host needs to be running hostd
"""

import sys
from pyVim.connect import Connect
from optparse import OptionParser
from pyVmomi import Vim


def get_options():
    """
    Supports the command-line arguments listed below
    """

    parser = OptionParser()
    parser.add_option("--host", help="remote host to connect to")
    parser.add_option("-u",
                      "--user",
                      default="root",
                      help="User name to use when connecting to hostd")
    parser.add_option("-p",
                      "--password",
                      default="ca$hc0w",
                      help="Password to use when connecting to hostd")
    parser.add_option("-n",
                      "--user-name-to-create",
                      help="User name of user to create")
    parser.add_option("-i",
                      "--posix-id-to-create",
                      help="Numeric POSIX id of user to create")
    parser.add_option("-d",
                      "--description",
                      default="User created by createuser.py",
                      help="Description of user to create")
    parser.add_option("--with-password",
                      default="password",
                      help="Password of user to create")
    parser.add_option("--enable-shell-access",
                      action="store_true",
                      help="Grant shell access to new user")
    (options, _) = parser.parse_args()
    return options


def main():
    """
    Simple command-line program for creating a new user on a system
    managed by hostd.
    """

    options = get_options()

    service_instance = Connect(host=options.host,
                               user=options.user,
                               pwd=options.password)

    user_name_to_create = options.user_name_to_create
    posix_id_to_create = int(options.posix_id_to_create)

    print("Creating user name \"%s\" with POSIX id %d..." %
          (user_name_to_create, posix_id_to_create)),
    sys.__stdout__.flush()

    service_instance.content.accountManager.CreateUser(
        Vim.Host.LocalAccountManager.PosixAccountSpecification(
            id=user_name_to_create,
            password=options.with_password,
            description=options.description,
            posixId=posix_id_to_create,
            shellAccess=options.enable_shell_access))

    print("DONE.")


# Start program
if __name__ == "__main__":
    main()
