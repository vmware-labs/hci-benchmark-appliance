#!/bin/sh
#
# Copyright 2022 VMware, Inc.  All rights reserved. -- VMware Confidential
#
# py.sh
#

BLD=/build/apps/bin/bld
TCROOT=/build/toolchain
TMP_BLDINFO=/tmp/bldinfo.$$
IS_VISOR=`uname -a | grep "VMkernel"`
IS_MAC=`uname -a | grep "Darwin"`

Usage() {
    echo "Usage: $0 <script name> <scripts arguments>"
    echo "Program input: "
    echo "For running against a private hostd, location of source: derived from "
    echo " a) VMTREE variable b) pwd"
    echo "For running against an official hostd build: "
    echo "BLD_NUMBER=<bld number>"
    echo "VMBLD=obj|beta|release"
    echo "Debug tool: "
    echo " a) DEBUG_CMD b) none"
    echo "Python location: derived from "
    if [ "-n" "$IS_VISOR" ]; then
        echo " a) PYTHON b) which python3 c) toolchain"
    else
        echo " a) PYTHON b) toolchain c) which python3"
    fi
    echo "Debug mode: "
    echo " DEBUGMODE=1"
    exit 0
}


log() {
    if [ "-n" "$DEBUGMODE" ]; then
	echo $*
    fi
}

if [ "-n" "$BLD_NUMBER" ]; then
   $BLD info $BLD_NUMBER > $TMP_BLDINFO

   # Check for toolchain errors
   if [ "$?" -ne 0 ]; then
       cat $TMP_BLDINFO
       rm -f $TMP_BLDINFO > /dev/null 2>&1
       exit 1
   fi

   BLDTREE=`grep "Build Tree" $TMP_BLDINFO | awk -F ' ' '{print $3}'`
   TREELOC=$BLDTREE/bora
   VMBLD=`grep "Type" $TMP_BLDINFO | awk '{print $2}'`

   # Clean up tmp file
   rm -f $TMP_BLDINFO  > /dev/null 2>&1
elif [ "-n" "$VMTREE" ]; then
    TREELOC=$VMTREE
     if [ "-n" "$VMBLD" ]; then
	 VMBLD=$VMBLD
     else
	 VMBLD="obj"
     fi
    log "TREELOC is $VMTREE"
else
    # Try to guess the bora location from pwd
    CURRENTDIR=`pwd`
    TREELOC=`expr "$CURRENTDIR" : '\(.*bora\)'`
    if [ "-z" "$TREELOC" "-a" "-d" "bora" ]; then
        TREELOC="$CURRENTDIR/bora"
    fi
    log "TREELOC was found by match technique: $TREELOC"
    if [ "-z" "$TREELOC" ]; then
	Usage
    fi
    if [ "-n" "$VMBLD" ]; then
	 VMBLD=$VMBLD
     else
	 VMBLD="obj"
     fi
fi

if [ "-n" "$BLD_NUMBER" ]; then
   log "Using official build $BLD_NUMBER located at $TREELOC"
   BUILDLOC=$TREELOC/../build/linux64/bora/build
elif [ "-n" "$BUILDROOT" ]; then
    BUILDLOC=$BUILDROOT
    log "BUILDLOC from BUILDROOT: $BUILDLOC"
else
    BUILDLOC=$TREELOC/build
    log "BUILDLOC relative to TREELOC: $BUILDLOC"
fi
log "Using BUILDLOC $BUILDLOC"

# Make sure VMBLD does exists. Pick another one if needed
if [ "$IS_VISOR" -a ! "-d" "$BUILDLOC/esx/$VMBLD" ]; then
   for VMBLD in "obj" "beta" "release"; do
      if [ "-d" "$BUILDLOC/esx/$VMBLD" ]; then
         break
      fi
   done
fi
log "Using VMBLD $VMBLD"

if [ "-n" "$IS_VISOR" ]; then
   # UserWorlds are still 32-bit
   ARCH="32"
elif [ `uname -m` = "x86_64" ]; then
   ARCH="64"
else
   ARCH="32"
fi

if [ "-n" "$IS_MAC" ]; then
TC_PYTHON=$TCROOT/mac32/python-3.5.2-openssl1.0.2/bin/python
else
TC_PYTHON=$TCROOT/lin$ARCH/python-3.5.2-openssl1.0.2/bin/python
fi
LOCAL_PYTHON=`which python3`

if [ ! "-x" "$PYTHON" ]; then
    # Prefer local python when running on Visor hosts
    if [ "-n" "$IS_VISOR" ]; then
        if [ "-x" "$LOCAL_PYTHON" ]; then
            PYTHON=$LOCAL_PYTHON
        else
            PYTHON=$TC_PYTHON
        fi
    else
        if [ "-x" "$TC_PYTHON" ]; then
            PYTHON=$TC_PYTHON
        else
            PYTHON=$LOCAL_PYTHON
        fi
    fi
fi

if [ ! "-x" "$PYTHON" ]; then
    echo "Could not find Python executable"
    exit 1
fi

# Deal with the annoying fact that the build number is embedded in the
# path without requiring the user to explicitly specify it
ESXSTAGEDIR=$BUILDLOC/esx/$VMBLD
if [ "-n" "$BLD_NUMBER" ]; then
    BLDNUM=$BLD_NUMBER
    SCONSPKGLOC=$ESXSTAGEDIR/pyvmomi-$BLDNUM
else
    PYVMOMIPKGGLOB=$ESXSTAGEDIR/pyvmomi-*/
    N=`ls -dt1 $PYVMOMIPKGGGLOB 2>/dev/null | wc -l`
    if [ $N -eq 0 ]; then
        log "Can't find pyVmomi package under $BUILDLOC"
    elif [ $N -ne 1 ]; then
        log "Found multiple pyVmomi packages at $BUILDLOC; choosing the newest"
    fi
    SCONSPKGLOC=`ls -dt1 $PYVMOMIPKGGLOB 2>/dev/null | head -1`
fi
log "Using SCONSPKGLOC $SCONSPKGLOC"

# Figure out the location of pyVmomi in the build tree
MAKELOC=$BUILDLOC/vmodl
SCONSBLDLOC=$BUILDLOC/scons/build/LIBRARIES/vmodl/generic/$VMBLD
SCONSBLDLOC2=$BUILDLOC/build/LIBRARIES/vmodl/generic/$VMBLD
if [ -d "$SCONSBLDLOC" ]; then
    PYVMOMILOC=$SCONSBLDLOC
elif [ -d "$SCONSBLDLOC2" ]; then
    PYVMOMILOC=$SCONSBLDLOC2
elif [ -d "$MAKELOC" ]; then
    PYVMOMILOC=$MAKELOC
elif [ -d "$SCONSPKGLOC" ]; then
    PYVMOMILOC=$SCONSPKGLOC
fi
log "Using PYVMOMILOC $PYVMOMILOC"

MODULELOC=$TREELOC/vim/py/:$TREELOC/vim/py/pyJack/:$TREELOC/vim/py/stresstests/lib:$TREELOC/vim/py/stresstests/opLib:$TREELOC/vim:$TREELOC/vim/apps/dodo
export PYTHONPATH=$PYTHONPATH:$PYVMOMILOC:$MODULELOC:$TCROOT/noarch/six-1.9.0/lib/python2.7/site-packages
export PYLINTRC=$TREELOC/vim/py/pylintrc

log "Using python from: $PYTHON"
log "PYTHON_PATH: "
log "$PYTHONPATH"
# Get the script name, pull it out and pass the rest of the arguments over.
PYSCRIPT="$1"
if [ $# -ne 0 ]; then
   shift
fi

log "Executing command: "
[ -n "$DEBUGMODE" ] && set -x
if [ -z "$PYSCRIPT" ]; then
    exec $DEBUG_CMD $PYTHON -i $TREELOC/vim/py/pyVim/shell.py
else
    exec $DEBUG_CMD $PYTHON $PYSCRIPT "$@"
fi
