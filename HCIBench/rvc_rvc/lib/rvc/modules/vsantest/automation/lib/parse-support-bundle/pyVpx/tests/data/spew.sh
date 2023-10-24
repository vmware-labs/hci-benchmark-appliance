#!/bin/sh

# Script that spews just over 4kB worth of data to stdout and stderr.

# Binary was signed via the following command:
# /build/toolchain/noarch/vmware/signserver/signc --signmethod=vibsign-1.0 \
#    --keyid=elfsign_test --input=spew.sh --output=spew.sig
#
# Official builds may reject the elfsign_test key, unless they were booted from
# the VMware-VMvisor-Installer-With-Test-Certs-...iso or have
# vib-test-certs-....i386.vib installed.

DATA="A quick brown fox jumped over the lazy dogs.  A QUICK BROWN FOX JUMPED OVER \
THE LAZY DOGS.  One hundred twenty eight characters."

i=0
while [ "$i" -lt 50 ]; do
  # Spew to stdout and stderr
  echo $DATA
  echo >&2 $DATA
  i=`expr $i + 1`
done

