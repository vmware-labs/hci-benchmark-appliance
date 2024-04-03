## @file account.py --
## @brief helper code for user account, permissions and roles management
##
## Allows for creation/editing/deleting of user accounts,
## Manipulating roles and permissions.
"""
Helper code for user account, permissions and roles management
Requires that a connection is established with the host with the
rights to perform account management.
"""

__author__ = 'VMware, Inc'

from pyVmomi import Vmodl, Vim
from .connect import GetSi


def CreatePosixUser(name,
                    password='',
                    description="user created by account.py",
                    posixId=None,
                    allowShellAccess=None):
    """
    Creates a user account.

    @param name   the user name of the account to be created
    @param password   the password for the account
    @param description   the description of the account
    @param posixId   the posix numeric id to use for the account
    @param allowShellAccess   whether shell access is enabled for the account
    """

    si = GetSi()
    si.content.accountManager.CreateUser(
        Vim.Host.LocalAccountManager.PosixAccountSpecification(
            id=name,
            password=password,
            description=description,
            posixId=posixId,
            shellAccess=allowShellAccess))


def CreateUser(name, password='', description="user created by account.py"):
    """
    Creates a user account.

    @param name   the user name of the account to be created
    @param password   the password for the account
    @param description   the description of the account
    """

    si = GetSi()
    si.content.accountManager.CreateUser(
        Vim.Host.LocalAccountManager.AccountSpecification(
            id=name, password=password, description=description))


def RemoveUser(name):
    """
    Deletes a user account.

    @param name   the user name of the account to be removed
    """

    si = GetSi()
    si.content.accountManager.RemoveUser(name)


def GetRoleId(name):
    """
    Returns the role id given a role name

    @param name   the name of the role
    @return   the role id for the name
    """

    si = GetSi()
    roles = si.content.authorizationManager.roleList
    for role in roles:
        if role.name == name:
            return role.roleId

    raise Exception("Role with name " + name + " not found")


def CreateRole(name, basedOnRoleName=None, privsToAdd=[], privsToRemove=[]):
    """
    Creates a new role based on the set of privileges of an existing role (or
    empty set if existing role name is not specified), with differences in
    privileges specified optional to-add and to-remove lists.

    @param name   the user name of the account to be removed
    @param basedOnRoleName   the name of the role to based this role's privileges on
    @param privsToAdd   the additional list of privileges to assign to this role
    @param privsToRemove   the list of privileges to remove from this role
    """

    si = GetSi()
    privileges = []
    if basedOnRoleName != None:
        roles = si.content.authorizationManager.roleList
        for role in roles:
            if role.name == basedOnRoleName:
                privileges = role.privilege
                break

    privileges = privileges + [p for p in privsToAdd if p not in privileges]
    privileges = [p for p in privileges if p not in privsToRemove]

    return si.content.authorizationManager.AddRole(name, privileges)


def RemoveRole(roleId, failIfUsed):
    """
    Deletes a role

    @param roleId   the id of the role
    @param failIfUsed   if true prevents the role from being removed if it is being used.
    """

    si = GetSi()
    si.content.authorizationManager.RemoveRole(roleId, failIfUsed)


def GetAuthorizationManager(si=None):
    """
    Retrieves the authorization manager

    @param si   the service instance
    @return     the authorization manager
    """
    if not si:
        si = GetSi()

    return si.content.authorizationManager
