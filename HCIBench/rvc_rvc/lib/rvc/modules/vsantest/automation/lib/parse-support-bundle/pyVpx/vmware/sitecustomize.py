"""
sitecustomize.py
"""

#
# Add to sys.path so that we can find the vmware.misc module.
#
import os, sys

if os.getenv("VMTREE"):
   sys.path.append("%s/vim/py" % os.getenv("VMTREE"))

from vmware.misc import DebugPrint, ModuleDirList

DebugPrint("\n# sitecustomize.py")

#
# Add some directories to sys.path so that we can find modules like
# pyVim and pyVmomi.
#
ModuleDirList("""
   $VMTREE/vim/py
   $VMTREE/build/scons/package/devel/linux32/$BLDTYPE/esx/rpm/hostd/stage/usr/lib/python2.2
   $VMTREE/build/vmodl
   """)

DebugPrint()
