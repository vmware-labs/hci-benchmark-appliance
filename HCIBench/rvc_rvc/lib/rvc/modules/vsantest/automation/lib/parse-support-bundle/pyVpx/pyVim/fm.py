## @file fm.py
## @brief Synchronous FileManager functions
##
## Detailed description (for Doxygen goes here)
"""
Synchronous FileManager functions.

Detailed description (for pydoc goes here)
"""


def Move(host, srcDatacenter, srcFile, dstDatacenter, dstFile, force,
         fileType):
    """
    Move a file from (srcDatacenter, srcFile) to (dstDatacenter, dstFile).

    @type  host:           [in] C{L{pyVim.vimhost.Host}}
    @param host:
    @type  srcDatacenter:  [in] str
    @param srcDatacenter:  The datacenter of the source path
    @type  srcFile:        [in] str
    @param srcFile:        The datastore path for the source.
    @type  dstDatacenter:  [in] str
    @param dstDatacenter:  The datacenter of the destination path.
    @type  dstFile:        [in] str
    @param dstFile:        The datastore path for the destination.
    @type  force:          [in] bool
    @param force:          If True, overwrite any identically
                            named file or disk at the destination.
    @type  fileType:       [in] str
    @param fileType:       The type of file to be considered
                            for the operation.
    """
    PrintDebugInfo(functionName="pyVim.fm.Move",
                   srcDatacenter=srcDatacenter,
                   srcFile=srcFile,
                   dstDatacenter=dstDatacenter,
                   dstFile=dstFile,
                   force=force,
                   fileType=fileType)
    host.InvokeAndTrack(host.GetFileManager().Move, srcDatacenter, srcFile,
                        dstDatacenter, dstFile, force, fileType)


def PrintDebugInfo(functionName, **kwargs):
    """
    Debug function that prints a list of key/value pairs.

    """

    if False:
        for k, v in list(kwargs.items()):
            print("*** %s: %s = '%s'" % (functionName, k, v))


def Copy(host, srcDatacenter, srcFile, dstDatacenter, dstFile, force,
         fileType):
    """
    Copy a file from (srcDatacenter, srcFile) to (dstDatacenter, dstFile).

    @type  host:           [in] C{L{pyVim.vimhost.Host}}
    @param host:
    @type  srcDatacenter:  [in] str
    @param srcDatacenter:  The datacenter of the source path
    @type  srcFile:        [in] str
    @param srcFile:        The datastore path for the source.
    @type  dstDatacenter:  [in] str
    @param dstDatacenter:  The datacenter of the destination path.
    @type  dstFile:        [in] str
    @param dstFile:        The datastore path for the destination.
    @type  force:          [in] bool
    @param force:          If True, overwrite any identically
                            named file or disk at the destination.
    @type  fileType:       [in] str
    @param fileType:       The type of file to be considered
                            for the operation.
    """
    PrintDebugInfo(functionName="pyVim.fm.Copy",
                   srcDatacenter=srcDatacenter,
                   srcFile=srcFile,
                   dstDatacenter=dstDatacenter,
                   dstFile=dstFile,
                   force=force,
                   fileType=fileType)
    host.InvokeAndTrack(host.GetFileManager().Copy, srcDatacenter, srcFile,
                        dstDatacenter, dstFile, force, fileType)


def Delete(host, srcDatacenter, srcFile, force, fileType):
    """
    Delete a file from (srcDatacenter, srcFile).

    @type  host:           [in] C{L{pyVim.vimhost.Host}}
    @param host:
    @type  srcDatacenter:  [in] str
    @param srcDatacenter:  The datacenter of the source path
    @type  srcFile:        [in] str
    @param srcFile:        The datastore path for the source.
    @type  force:          [in] bool
    @param force:          If True, overwrite any identically
                            named file or disk at the destination.
    @type  fileType:       [in] str
    @param fileType:       The type of file to be considered
                            for the operation.
    """
    PrintDebugInfo(functionName="pyVim.fm.Delete",
                   srcDatacenter=srcDatacenter,
                   srcFile=srcFile,
                   force=force,
                   fileType=fileType)
    host.InvokeAndTrack(host.GetFileManager().Delete, srcDatacenter, srcFile,
                        force, fileType)


def ChangeOwner(host, srcFile, srcDatacenter, owner):
    """
    Change the owner of file (srcDatacenter, srcFile).

    @type  host:           [in] C{L{pyVim.vimhost.Host}}
    @param host:
    @type  srcDatacenter:  [in] str
    @param srcDatacenter:  The datacenter of the source path
    @type  srcFile:        [in] str
    @param srcFile:        The datastore path for the source.
    @type  owner:          [in] str
    @param owner:          [in] User name to set as owner of file/folder.
    """
    PrintDebugInfo(functionName="pyVim.fm.ChangeOwner",
                   srcFile=srcFile,
                   srcDatacenter=srcDatacenter,
                   owner=owner)
    return host.GetFileManager().ChangeOwner(srcFile, srcDatacenter, owner)
