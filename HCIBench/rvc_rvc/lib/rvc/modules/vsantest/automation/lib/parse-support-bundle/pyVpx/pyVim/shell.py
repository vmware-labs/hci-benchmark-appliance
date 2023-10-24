## @file shell.py
## @brief Provides niceties for working with pyVmomi in the Python shell.
"""
Provides niceties for working with pyVmomi in the Python shell.

To use it::

    $ python -i shell.py
"""

import atexit, os.path, sys
import pyVim

try:
    import readline
    pyVim.history_enabled = True
except ImportError:
    pyVim.history_enabled = False
else:
    import user


def find_src_root(working_dir=os.getcwd()):
    """
    Finds the top of a source tree given as an arg,
    or if no arg given, uses the current working directory.

    @type  working_dir: str
    @param working_dir: The directory to find the src_root of. If not
    supplied, defaults to the current working directory.
    @rtype: str
    @return: Path to top of source tree.
    """

    while (not os.path.exists(os.path.join(working_dir, "vim", "py"))):
        if (working_dir == os.path.sep
                or working_dir == os.path.dirname(working_dir)):
            return None
        working_dir = os.path.dirname(working_dir)

    return working_dir


def setup_sys_path():
    """
    Adds a few necessary directories to C{sys.path} so that later imports will
    find the needed modules.

    @rtype: None
    """

    src_root = find_src_root(os.path.abspath(sys.argv[0]))
    sys.path.append(os.path.join(src_root, "vim", "py"))
    sys.path.append(os.path.join(src_root, "build", "vmodl"))


setup_sys_path()

import pyVmomi
import pyVim.configSerialize, pyVim.connect, pyVim.folder
import pyVim.helpers, pyVim.host, pyVim.invt
import pyVim.moMapDefs, pyVim.task, pyVim.vc
import pyVim.vimhost, pyVim.vimutil, pyVim.vm, pyVim.vmconfig
# Optional component
try:
    import pyVim.integtest
except ImportError:
    pass

if pyVim.history_enabled:
    histfile = os.path.join(os.environ["HOME"], ".vimpython-history")

    try:
        readline.read_history_file(histfile)
    except IOError:
        pass

    atexit.register(readline.write_history_file, histfile)

del os, sys
