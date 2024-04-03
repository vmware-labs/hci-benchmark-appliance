#!/usr/bin/python

from __future__ import print_function

import sys
import atexit
from pyVmomi import Vim
from pyVmomi import VmomiSupport
from pyVim.connect import SmartConnect, Disconnect
from optparse import OptionParser

#
perfCountersOld = {
0 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 0,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Usage',
      summary = 'CPU usage as a percentage during the interval',
      key = 'usage'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'none',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) [
      1,
      2,
      3
   ]
}
''',
1 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 1,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Usage',
      summary = 'CPU usage as a percentage during the interval',
      key = 'usage'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
2 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 2,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Usage',
      summary = 'CPU usage as a percentage during the interval',
      key = 'usage'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'maximum',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
3 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 3,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Usage',
      summary = 'CPU usage as a percentage during the interval',
      key = 'usage'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'minimum',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
4 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 4,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Usage in MHz',
      summary = 'CPU usage, as measured in megahertz, during the interval',
      key = 'usagemhz'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'MHz',
      summary = 'Megahertz',
      key = 'megaHertz'
   },
   rollupType = 'none',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) [
      5,
      6,
      7
   ]
}
''',
5 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 5,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Usage in MHz',
      summary = 'CPU usage, as measured in megahertz, during the interval',
      key = 'usagemhz'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'MHz',
      summary = 'Megahertz',
      key = 'megaHertz'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
6 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 6,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Usage in MHz',
      summary = 'CPU usage, as measured in megahertz, during the interval',
      key = 'usagemhz'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'MHz',
      summary = 'Megahertz',
      key = 'megaHertz'
   },
   rollupType = 'maximum',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
7 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 7,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Usage in MHz',
      summary = 'CPU usage, as measured in megahertz, during the interval',
      key = 'usagemhz'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'MHz',
      summary = 'Megahertz',
      key = 'megaHertz'
   },
   rollupType = 'minimum',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
8 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 8,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Reserved capacity',
      summary = 'Total CPU capacity reserved by virtual machines',
      key = 'reservedCapacity'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'MHz',
      summary = 'Megahertz',
      key = 'megaHertz'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
9 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 9,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'System',
      summary = 'Amount of time spent on system processes on each virtual CPU in the virtual machine',
      key = 'system'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'summation',
   statsType = 'delta',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
10 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 10,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Wait',
      summary = 'Total CPU time spent in wait state',
      key = 'wait'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'summation',
   statsType = 'delta',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
11 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 11,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Ready',
      summary = 'Percentage of time that the virtual machine was ready, but could not get scheduled to run on the physical CPU',
      key = 'ready'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'summation',
   statsType = 'delta',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
12 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 12,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Used',
      summary = 'Total CPU usage',
      key = 'used'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'summation',
   statsType = 'delta',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
13 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 13,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Idle',
      summary = 'Total time that the CPU spent in an idle state',
      key = 'idle'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'summation',
   statsType = 'delta',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
14 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 14,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Swap wait',
      summary = 'CPU time spent waiting for swap-in',
      key = 'swapwait'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'summation',
   statsType = 'delta',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
15 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 15,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Utilization',
      summary = 'CPU utilization as a percentage during the interval (CPU usage and CPU utilization may be different due to power management technologies or hyper-threading)',
      key = 'utilization'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'none',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) [
      16,
      17,
      18
   ]
}
''',
16 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 16,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Utilization',
      summary = 'CPU utilization as a percentage during the interval (CPU usage and CPU utilization may be different due to power management technologies or hyper-threading)',
      key = 'utilization'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
17 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 17,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Utilization',
      summary = 'CPU utilization as a percentage during the interval (CPU usage and CPU utilization may be different due to power management technologies or hyper-threading)',
      key = 'utilization'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'maximum',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
18 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 18,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Utilization',
      summary = 'CPU utilization as a percentage during the interval (CPU usage and CPU utilization may be different due to power management technologies or hyper-threading)',
      key = 'utilization'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'minimum',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
19 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 19,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Core utilization',
      summary = 'CPU utilization of the corresponding core (if hyper-threading is enabled) as a percentage during the interval (A core is utilized, if either or both of its logical CPUs are utilized)',
      key = 'coreUtilization'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'none',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) [
      20,
      21,
      22
   ]
}
''',
20 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 20,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Core utilization',
      summary = 'CPU utilization of the corresponding core (if hyper-threading is enabled) as a percentage during the interval (A core is utilized, if either or both of its logical CPUs are utilized)',
      key = 'coreUtilization'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
21 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 21,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Core utilization',
      summary = 'CPU utilization of the corresponding core (if hyper-threading is enabled) as a percentage during the interval (A core is utilized, if either or both of its logical CPUs are utilized)',
      key = 'coreUtilization'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'maximum',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
22 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 22,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Core utilization',
      summary = 'CPU utilization of the corresponding core (if hyper-threading is enabled) as a percentage during the interval (A core is utilized, if either or both of its logical CPUs are utilized)',
      key = 'coreUtilization'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'minimum',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
23 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 23,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Total capacity',
      summary = 'Total CPU capacity reserved by and available for virtual machines',
      key = 'totalCapacity'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'MHz',
      summary = 'Megahertz',
      key = 'megaHertz'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
24 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 24,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Latency',
      summary = 'Percent of time the VM is unable to run because it is contending for access to the physical CPU(s)',
      key = 'latency'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
25 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 25,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Entitlement',
      summary = 'CPU resources devoted by the ESX scheduler',
      key = 'entitlement'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'MHz',
      summary = 'Megahertz',
      key = 'megaHertz'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
26 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 26,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Demand',
      summary = 'The amount of CPU resources a VM would use if there were no CPU contention or CPU limit',
      key = 'demand'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'MHz',
      summary = 'Megahertz',
      key = 'megaHertz'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
27 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 27,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Co-stop',
      summary = 'Time the VM is ready to run, but is unable to due to co-scheduling constraints',
      key = 'costop'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'summation',
   statsType = 'delta',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
28 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 28,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Max limited',
      summary = 'Time the VM is ready to run, but is not run due to maxing out its CPU limit setting',
      key = 'maxlimited'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'summation',
   statsType = 'delta',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
29 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 29,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Overlap',
      summary = 'Time the VM was interrupted to perform system services on behalf of that VM or other VMs',
      key = 'overlap'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'summation',
   statsType = 'delta',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
30 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 30,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Run',
      summary = 'Time the VM is scheduled to run',
      key = 'run'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU',
      summary = 'CPU',
      key = 'cpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'summation',
   statsType = 'delta',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65536 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65536,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Usage',
      summary = 'Memory usage as percentage of total configured or available memory',
      key = 'usage'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'none',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) [
      65537,
      65538,
      65539
   ]
}
''',
65537 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65537,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Usage',
      summary = 'Memory usage as percentage of total configured or available memory',
      key = 'usage'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65538 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65538,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Usage',
      summary = 'Memory usage as percentage of total configured or available memory',
      key = 'usage'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'maximum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65539 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65539,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Usage',
      summary = 'Memory usage as percentage of total configured or available memory',
      key = 'usage'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'minimum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65540 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65540,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Granted',
      summary = 'Amount of machine memory or physical memory that is mapped for a virtual machine or a host',
      key = 'granted'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'none',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) [
      65541,
      65542,
      65543
   ]
}
''',
65541 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65541,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Granted',
      summary = 'Amount of machine memory or physical memory that is mapped for a virtual machine or a host',
      key = 'granted'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65542 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65542,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Granted',
      summary = 'Amount of machine memory or physical memory that is mapped for a virtual machine or a host',
      key = 'granted'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'maximum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65543 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65543,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Granted',
      summary = 'Amount of machine memory or physical memory that is mapped for a virtual machine or a host',
      key = 'granted'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'minimum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65544 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65544,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Active',
      summary = 'Amount of memory that is actively used, as estimated by VMkernel based on recently touched memory pages',
      key = 'active'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'none',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) [
      65545,
      65546,
      65547
   ]
}
''',
65545 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65545,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Active',
      summary = 'Amount of memory that is actively used, as estimated by VMkernel based on recently touched memory pages',
      key = 'active'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65546 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65546,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Active',
      summary = 'Amount of memory that is actively used, as estimated by VMkernel based on recently touched memory pages',
      key = 'active'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'maximum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65547 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65547,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Active',
      summary = 'Amount of memory that is actively used, as estimated by VMkernel based on recently touched memory pages',
      key = 'active'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'minimum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65548 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65548,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Shared',
      summary = 'Amount of guest memory that is shared with other virtual machines, relative to a single virtual machine or to all powered-on virtual machines on a host',
      key = 'shared'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'none',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) [
      65549,
      65550,
      65551
   ]
}
''',
65549 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65549,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Shared',
      summary = 'Amount of guest memory that is shared with other virtual machines, relative to a single virtual machine or to all powered-on virtual machines on a host',
      key = 'shared'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65550 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65550,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Shared',
      summary = 'Amount of guest memory that is shared with other virtual machines, relative to a single virtual machine or to all powered-on virtual machines on a host',
      key = 'shared'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'maximum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65551 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65551,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Shared',
      summary = 'Amount of guest memory that is shared with other virtual machines, relative to a single virtual machine or to all powered-on virtual machines on a host',
      key = 'shared'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'minimum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65552 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65552,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Zero',
      summary = 'Memory that contains 0s only',
      key = 'zero'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'none',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) [
      65553,
      65554,
      65555
   ]
}
''',
65553 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65553,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Zero',
      summary = 'Memory that contains 0s only',
      key = 'zero'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65554 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65554,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Zero',
      summary = 'Memory that contains 0s only',
      key = 'zero'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'maximum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65555 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65555,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Zero',
      summary = 'Memory that contains 0s only',
      key = 'zero'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'minimum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65556 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65556,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Unreserved',
      summary = 'Amount of memory that is unreserved',
      key = 'unreserved'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'none',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) [
      65557,
      65558,
      65559
   ]
}
''',
65557 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65557,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Unreserved',
      summary = 'Amount of memory that is unreserved',
      key = 'unreserved'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65558 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65558,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Unreserved',
      summary = 'Amount of memory that is unreserved',
      key = 'unreserved'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'maximum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65559 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65559,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Unreserved',
      summary = 'Amount of memory that is unreserved',
      key = 'unreserved'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'minimum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65560 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65560,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Swap used',
      summary = 'Amount of memory that is used by swap',
      key = 'swapused'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'none',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) [
      65561,
      65562,
      65563
   ]
}
''',
65561 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65561,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Swap used',
      summary = 'Amount of memory that is used by swap',
      key = 'swapused'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65562 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65562,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Swap used',
      summary = 'Amount of memory that is used by swap',
      key = 'swapused'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'maximum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65563 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65563,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Swap used',
      summary = 'Amount of memory that is used by swap',
      key = 'swapused'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'minimum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65568 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65568,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Shared common',
      summary = 'Amount of machine memory that is shared by all powered-on virtual machines and vSphere services on the host',
      key = 'sharedcommon'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'none',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) [
      65569,
      65570,
      65571
   ]
}
''',
65569 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65569,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Shared common',
      summary = 'Amount of machine memory that is shared by all powered-on virtual machines and vSphere services on the host',
      key = 'sharedcommon'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65570 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65570,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Shared common',
      summary = 'Amount of machine memory that is shared by all powered-on virtual machines and vSphere services on the host',
      key = 'sharedcommon'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'maximum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65571 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65571,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Shared common',
      summary = 'Amount of machine memory that is shared by all powered-on virtual machines and vSphere services on the host',
      key = 'sharedcommon'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'minimum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65572 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65572,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Heap',
      summary = 'VMkernel virtual address space dedicated to VMkernel main heap and related data',
      key = 'heap'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'none',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) [
      65573,
      65574,
      65575
   ]
}
''',
65573 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65573,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Heap',
      summary = 'VMkernel virtual address space dedicated to VMkernel main heap and related data',
      key = 'heap'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65574 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65574,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Heap',
      summary = 'VMkernel virtual address space dedicated to VMkernel main heap and related data',
      key = 'heap'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'maximum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65575 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65575,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Heap',
      summary = 'VMkernel virtual address space dedicated to VMkernel main heap and related data',
      key = 'heap'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'minimum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65576 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65576,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Heap free',
      summary = "Free address space in the VMkernel's main heap",
      key = 'heapfree'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'none',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) [
      65577,
      65578,
      65579
   ]
}
''',
65577 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65577,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Heap free',
      summary = "Free address space in the VMkernel's main heap",
      key = 'heapfree'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65578 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65578,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Heap free',
      summary = "Free address space in the VMkernel's main heap",
      key = 'heapfree'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'maximum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65579 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65579,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Heap free',
      summary = "Free address space in the VMkernel's main heap",
      key = 'heapfree'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'minimum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65580 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65580,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'State',
      summary = 'One of four threshold levels representing the percentage of free memory on the host. The counter value determines swapping and ballooning behavior for memory reclamation.',
      key = 'state'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65581 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65581,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Balloon',
      summary = 'Amount of memory allocated by the virtual machine memory control driver (vmmemctl), which is installed with VMware Tools',
      key = 'vmmemctl'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'none',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) [
      65582,
      65583,
      65584
   ]
}
''',
65582 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65582,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Balloon',
      summary = 'Amount of memory allocated by the virtual machine memory control driver (vmmemctl), which is installed with VMware Tools',
      key = 'vmmemctl'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65583 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65583,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Balloon',
      summary = 'Amount of memory allocated by the virtual machine memory control driver (vmmemctl), which is installed with VMware Tools',
      key = 'vmmemctl'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'maximum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65584 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65584,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Balloon',
      summary = 'Amount of memory allocated by the virtual machine memory control driver (vmmemctl), which is installed with VMware Tools',
      key = 'vmmemctl'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'minimum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65585 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65585,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Overhead',
      summary = 'Memory (KB) consumed by the virtualization infrastructure for running the VM',
      key = 'overhead'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'none',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) [
      65586,
      65587,
      65588
   ]
}
''',
65586 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65586,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Overhead',
      summary = 'Memory (KB) consumed by the virtualization infrastructure for running the VM',
      key = 'overhead'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65587 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65587,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Overhead',
      summary = 'Memory (KB) consumed by the virtualization infrastructure for running the VM',
      key = 'overhead'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'maximum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65588 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65588,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Overhead',
      summary = 'Memory (KB) consumed by the virtualization infrastructure for running the VM',
      key = 'overhead'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'minimum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65589 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65589,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Reserved capacity',
      summary = 'Total amount of memory reservation used by powered-on virtual machines and vSphere services on the host',
      key = 'reservedCapacity'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'MB',
      summary = 'Megabytes',
      key = 'megaBytes'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65590 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65590,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Swapped',
      summary = "Current amount of guest physical memory swapped out to the virtual machine's swap file by the VMkernel",
      key = 'swapped'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'none',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) [
      65591,
      65592,
      65593
   ]
}
''',
65591 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65591,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Swapped',
      summary = "Current amount of guest physical memory swapped out to the virtual machine's swap file by the VMkernel",
      key = 'swapped'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65592 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65592,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Swapped',
      summary = "Current amount of guest physical memory swapped out to the virtual machine's swap file by the VMkernel",
      key = 'swapped'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'maximum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65593 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65593,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Swapped',
      summary = "Current amount of guest physical memory swapped out to the virtual machine's swap file by the VMkernel",
      key = 'swapped'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'minimum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65594 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65594,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Swap target',
      summary = 'Target size for the virtual machine swap file',
      key = 'swaptarget'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'none',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) [
      65595,
      65596,
      65597
   ]
}
''',
65595 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65595,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Swap target',
      summary = 'Target size for the virtual machine swap file',
      key = 'swaptarget'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65596 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65596,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Swap target',
      summary = 'Target size for the virtual machine swap file',
      key = 'swaptarget'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'maximum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65597 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65597,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Swap target',
      summary = 'Target size for the virtual machine swap file',
      key = 'swaptarget'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'minimum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65598 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65598,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Swap in',
      summary = 'Amount swapped-in to memory from disk',
      key = 'swapin'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'none',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) [
      65599,
      65600,
      65601
   ]
}
''',
65599 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65599,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Swap in',
      summary = 'Amount swapped-in to memory from disk',
      key = 'swapin'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65600 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65600,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Swap in',
      summary = 'Amount swapped-in to memory from disk',
      key = 'swapin'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'maximum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65601 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65601,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Swap in',
      summary = 'Amount swapped-in to memory from disk',
      key = 'swapin'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'minimum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65602 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65602,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Swap out',
      summary = 'Amount of memory swapped-out to disk',
      key = 'swapout'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'none',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) [
      65603,
      65604,
      65605
   ]
}
''',
65603 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65603,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Swap out',
      summary = 'Amount of memory swapped-out to disk',
      key = 'swapout'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65604 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65604,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Swap out',
      summary = 'Amount of memory swapped-out to disk',
      key = 'swapout'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'maximum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65605 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65605,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Swap out',
      summary = 'Amount of memory swapped-out to disk',
      key = 'swapout'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'minimum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65606 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65606,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Balloon target',
      summary = "Target value set by VMkernal for the virtual machine's memory balloon size",
      key = 'vmmemctltarget'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'none',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) [
      65607,
      65608,
      65609
   ]
}
''',
65607 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65607,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Balloon target',
      summary = "Target value set by VMkernal for the virtual machine's memory balloon size",
      key = 'vmmemctltarget'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65608 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65608,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Balloon target',
      summary = "Target value set by VMkernal for the virtual machine's memory balloon size",
      key = 'vmmemctltarget'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'maximum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65609 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65609,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Balloon target',
      summary = "Target value set by VMkernal for the virtual machine's memory balloon size",
      key = 'vmmemctltarget'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'minimum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65610 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65610,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Consumed',
      summary = 'Amount of memory consumed by a virtual machine, host, or cluster',
      key = 'consumed'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'none',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) [
      65611,
      65612,
      65613
   ]
}
''',
65611 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65611,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Consumed',
      summary = 'Amount of memory consumed by a virtual machine, host, or cluster',
      key = 'consumed'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65612 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65612,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Consumed',
      summary = 'Amount of memory consumed by a virtual machine, host, or cluster',
      key = 'consumed'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'maximum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65613 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65613,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Consumed',
      summary = 'Amount of memory consumed by a virtual machine, host, or cluster',
      key = 'consumed'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'minimum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65614 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65614,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Used by VMkernel',
      summary = 'Amount of machine memory used by VMkernel for core functionality, such as device drivers and other internal uses',
      key = 'sysUsage'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'none',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) [
      65615,
      65616,
      65617
   ]
}
''',
65615 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65615,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Used by VMkernel',
      summary = 'Amount of machine memory used by VMkernel for core functionality, such as device drivers and other internal uses',
      key = 'sysUsage'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65616 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65616,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Used by VMkernel',
      summary = 'Amount of machine memory used by VMkernel for core functionality, such as device drivers and other internal uses',
      key = 'sysUsage'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'maximum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65617 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65617,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Used by VMkernel',
      summary = 'Amount of machine memory used by VMkernel for core functionality, such as device drivers and other internal uses',
      key = 'sysUsage'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'minimum',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65618 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65618,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Swap in rate',
      summary = 'Rate at which memory is swapped from disk into active memory during the interval',
      key = 'swapinRate'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65619 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65619,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Swap out rate',
      summary = 'Rate at which memory is being swapped from active memory to disk during the current interval',
      key = 'swapoutRate'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65620 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65620,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Active write',
      summary = 'Amount of memory actively being written to by the VM',
      key = 'activewrite'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65621 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65621,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Compressed',
      summary = 'Amount of memory compressed by ESX',
      key = 'compressed'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65622 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65622,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Compression rate',
      summary = 'Rate of memory compression for the VM',
      key = 'compressionRate'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65623 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65623,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Decompression rate',
      summary = 'Rate of memory decompression for the VM',
      key = 'decompressionRate'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65624 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65624,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Reserved overhead',
      summary = 'Memory (KB) reserved for use as the virtualization overhead for the VM',
      key = 'overheadMax'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65625 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65625,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Total capacity',
      summary = 'Total amount of memory reservation used by and available for powered-on virtual machines and vSphere services on the host',
      key = 'totalCapacity'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'MB',
      summary = 'Megabytes',
      key = 'megaBytes'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65626 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65626,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Zipped memory',
      summary = 'Memory (KB) zipped',
      key = 'zipped'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65627 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65627,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory saved by zipping',
      summary = 'Memory (KB) saved due to memory zipping',
      key = 'zipSaved'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65628 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65628,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Latency',
      summary = 'Percentage of time the VM is waiting to access swapped or compressed memory',
      key = 'latency'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65629 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65629,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Entitlement',
      summary = 'Amount of host physical memory VM is entitled to, as determined by the ESX scheduler',
      key = 'entitlement'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65630 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65630,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Low free threshold',
      summary = 'Threshold of free host physical memory below which ESX will begin reclaiming memory from VMs through ballooning and swapping',
      key = 'lowfreethreshold'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65631 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65631,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Host swap cache used',
      summary = 'Space used for caching swapped pages of a VM in the low latency host cache',
      key = 'llSwapUsed'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65632 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65632,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Swap in rate from host cache',
      summary = 'Rate at which memory is beeing swapped from low latency host cache into active memory',
      key = 'llSwapInRate'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
65633 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 65633,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Swap out rate to host cache',
      summary = 'Rate at which memory is being swapped from active memory to low latency host cache',
      key = 'llSwapOutRate'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory',
      summary = 'Memory',
      key = 'mem'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
131072 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 131072,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Usage',
      summary = 'Aggregated disk I/O rate. For hosts, this metric includes the rates for all virtual machines running on the host during the collection interval.',
      key = 'usage'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Disk',
      summary = 'Disk',
      key = 'disk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'none',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) [
      131073,
      131074,
      131075
   ]
}
''',
131073 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 131073,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Usage',
      summary = 'Aggregated disk I/O rate. For hosts, this metric includes the rates for all virtual machines running on the host during the collection interval.',
      key = 'usage'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Disk',
      summary = 'Disk',
      key = 'disk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
131074 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 131074,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Usage',
      summary = 'Aggregated disk I/O rate. For hosts, this metric includes the rates for all virtual machines running on the host during the collection interval.',
      key = 'usage'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Disk',
      summary = 'Disk',
      key = 'disk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'maximum',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
131075 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 131075,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Usage',
      summary = 'Aggregated disk I/O rate. For hosts, this metric includes the rates for all virtual machines running on the host during the collection interval.',
      key = 'usage'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Disk',
      summary = 'Disk',
      key = 'disk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'minimum',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
131076 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 131076,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Read requests',
      summary = 'Number of disk reads during the collection interval',
      key = 'numberRead'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Disk',
      summary = 'Disk',
      key = 'disk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'summation',
   statsType = 'delta',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
131077 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 131077,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Write requests',
      summary = 'Number of disk writes during the collection interval',
      key = 'numberWrite'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Disk',
      summary = 'Disk',
      key = 'disk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'summation',
   statsType = 'delta',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
131078 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 131078,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Read rate',
      summary = 'Average number of kilobytes read from the disk each second during the collection interval',
      key = 'read'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Disk',
      summary = 'Disk',
      key = 'disk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
131079 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 131079,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Write rate',
      summary = 'Average number of kilobytes written to disk each second during the collection interval',
      key = 'write'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Disk',
      summary = 'Disk',
      key = 'disk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
131080 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 131080,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Commands issued',
      summary = 'Number of SCSI commands issued during the collection interval',
      key = 'commands'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Disk',
      summary = 'Disk',
      key = 'disk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'summation',
   statsType = 'delta',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
131081 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 131081,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Command aborts',
      summary = 'Number of SCSI commands aborted during the collection interval',
      key = 'commandsAborted'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Disk',
      summary = 'Disk',
      key = 'disk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'summation',
   statsType = 'delta',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
131082 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 131082,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Bus resets',
      summary = 'Number of SCSI-bus reset commands issued during the collection interval',
      key = 'busResets'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Disk',
      summary = 'Disk',
      key = 'disk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'summation',
   statsType = 'delta',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
131083 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 131083,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Physical device read latency',
      summary = 'Average amount of time, in milliseconds, to complete read from the physical device',
      key = 'deviceReadLatency'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Disk',
      summary = 'Disk',
      key = 'disk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
131084 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 131084,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Kernel read latency',
      summary = 'Average amount of time, in milliseconds, spent by VMKernel processing each SCSI read command',
      key = 'kernelReadLatency'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Disk',
      summary = 'Disk',
      key = 'disk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
131085 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 131085,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Read latency',
      summary = 'Average amount of time taken during the collection interval to process a SCSI read command issued from the Guest OS to the virtual machine',
      key = 'totalReadLatency'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Disk',
      summary = 'Disk',
      key = 'disk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
131086 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 131086,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Queue read latency',
      summary = 'Average amount of time taken during the collection interval per SCSI read command in the VMKernel queue',
      key = 'queueReadLatency'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Disk',
      summary = 'Disk',
      key = 'disk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
131087 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 131087,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Physical device write latency',
      summary = 'Average amount of time, in milliseconds, to write to the physical device',
      key = 'deviceWriteLatency'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Disk',
      summary = 'Disk',
      key = 'disk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
131088 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 131088,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Kernel write latency',
      summary = 'Average amount of time, in milliseconds, spent by VMKernel processing each SCSI write command',
      key = 'kernelWriteLatency'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Disk',
      summary = 'Disk',
      key = 'disk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
131089 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 131089,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Write latency',
      summary = 'Average amount of time taken during the collection interval to process a SCSI write command issued by the Guest OS to the virtual machine',
      key = 'totalWriteLatency'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Disk',
      summary = 'Disk',
      key = 'disk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
131090 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 131090,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Queue write latency',
      summary = 'Average amount time taken during the collection interval per SCSI write command in the VMKernel queue',
      key = 'queueWriteLatency'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Disk',
      summary = 'Disk',
      key = 'disk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
131091 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 131091,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Physical device command latency',
      summary = 'Average amount of time, in milliseconds, to complete a SCSI command from the physical device',
      key = 'deviceLatency'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Disk',
      summary = 'Disk',
      key = 'disk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
131092 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 131092,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Kernel command latency',
      summary = 'Average amount of time, in milliseconds, spent by VMkernel processing each SCSI command',
      key = 'kernelLatency'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Disk',
      summary = 'Disk',
      key = 'disk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
131093 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 131093,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Command latency',
      summary = 'Average amount of time taken during the collection interval to process a SCSI command issued by the Guest OS to the virtual machine',
      key = 'totalLatency'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Disk',
      summary = 'Disk',
      key = 'disk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
131094 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 131094,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Queue command latency',
      summary = 'Average amount of time spent in the VMkernel queue, per SCSI command, during the collection interval',
      key = 'queueLatency'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Disk',
      summary = 'Disk',
      key = 'disk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
131095 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 131095,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Highest latency',
      summary = 'Highest latency value across all disks used by the host',
      key = 'maxTotalLatency'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Disk',
      summary = 'Disk',
      key = 'disk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
131096 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 131096,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Maximum queue depth',
      summary = 'Maximum queue depth',
      key = 'maxQueueDepth'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Disk',
      summary = 'Disk',
      key = 'disk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
131097 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 131097,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Average read requests per second',
      summary = 'Average number of disk reads per second during the collection interval',
      key = 'numberReadAveraged'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Disk',
      summary = 'Disk',
      key = 'disk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
131098 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 131098,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Average write requests per second',
      summary = 'Average number of disk writes per second during the collection interval',
      key = 'numberWriteAveraged'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Disk',
      summary = 'Disk',
      key = 'disk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
131099 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 131099,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Average commands issued per second',
      summary = 'Average number of SCSI commands issued per second during the collection interval',
      key = 'commandsAveraged'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Disk',
      summary = 'Disk',
      key = 'disk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
196608 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 196608,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Usage',
      summary = 'Network utilization (combined transmit- and receive-rates) during the interval',
      key = 'usage'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Network',
      summary = 'Network',
      key = 'net'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'none',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) [
      196609,
      196610,
      196611
   ]
}
''',
196609 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 196609,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Usage',
      summary = 'Network utilization (combined transmit- and receive-rates) during the interval',
      key = 'usage'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Network',
      summary = 'Network',
      key = 'net'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
196610 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 196610,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Usage',
      summary = 'Network utilization (combined transmit- and receive-rates) during the interval',
      key = 'usage'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Network',
      summary = 'Network',
      key = 'net'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'maximum',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
196611 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 196611,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Usage',
      summary = 'Network utilization (combined transmit- and receive-rates) during the interval',
      key = 'usage'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Network',
      summary = 'Network',
      key = 'net'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'minimum',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
196612 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 196612,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Packets received',
      summary = 'Number of packets received during the interval',
      key = 'packetsRx'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Network',
      summary = 'Network',
      key = 'net'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'summation',
   statsType = 'delta',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
196613 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 196613,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Packets transmitted',
      summary = 'Number of packets transmitted during the interval',
      key = 'packetsTx'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Network',
      summary = 'Network',
      key = 'net'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'summation',
   statsType = 'delta',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
196614 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 196614,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Data receive rate',
      summary = 'Average rate at which data was received during the interval',
      key = 'received'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Network',
      summary = 'Network',
      key = 'net'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
196615 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 196615,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Data transmit rate',
      summary = 'Average rate at which data was transmitted during the interval',
      key = 'transmitted'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Network',
      summary = 'Network',
      key = 'net'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
196616 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 196616,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Receive packets dropped',
      summary = 'Number of receives dropped',
      key = 'droppedRx'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Network',
      summary = 'Network',
      key = 'net'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'summation',
   statsType = 'delta',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
196617 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 196617,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Transmit packets dropped',
      summary = 'Number of transmits dropped',
      key = 'droppedTx'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Network',
      summary = 'Network',
      key = 'net'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'summation',
   statsType = 'delta',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
196618 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 196618,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Data receive rate',
      summary = 'Average amount of data received per second',
      key = 'bytesRx'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Network',
      summary = 'Network',
      key = 'net'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
196619 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 196619,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Data transmit rate',
      summary = 'Average amount of data transmitted per second',
      key = 'bytesTx'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Network',
      summary = 'Network',
      key = 'net'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
196620 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 196620,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Broadcast receives',
      summary = 'Number of broadcast packets received during the sampling interval',
      key = 'broadcastRx'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Network',
      summary = 'Network',
      key = 'net'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'summation',
   statsType = 'delta',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
196621 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 196621,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Broadcast transmits',
      summary = 'Number of broadcast packets transmitted during the sampling interval',
      key = 'broadcastTx'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Network',
      summary = 'Network',
      key = 'net'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'summation',
   statsType = 'delta',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
196622 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 196622,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Multicast receives',
      summary = 'Number of multicast packets received during the sampling interval',
      key = 'multicastRx'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Network',
      summary = 'Network',
      key = 'net'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'summation',
   statsType = 'delta',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
196623 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 196623,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Multicast transmits',
      summary = 'Number of multicast packets transmitted during the sampling interval',
      key = 'multicastTx'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Network',
      summary = 'Network',
      key = 'net'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'summation',
   statsType = 'delta',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
196624 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 196624,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Packet receive errors',
      summary = 'Number of packets with errors received during the sampling interval',
      key = 'errorsRx'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Network',
      summary = 'Network',
      key = 'net'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'summation',
   statsType = 'delta',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
196625 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 196625,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Packet transmit errors',
      summary = 'Number of packets with errors transmitted during the sampling interval',
      key = 'errorsTx'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Network',
      summary = 'Network',
      key = 'net'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'summation',
   statsType = 'delta',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
196626 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 196626,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Unknown protocol frames',
      summary = 'Number of frames with unknown protocol received during the sampling interval',
      key = 'unknownProtos'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Network',
      summary = 'Network',
      key = 'net'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'summation',
   statsType = 'delta',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
262144 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 262144,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Uptime',
      summary = 'Total time elapsed, in seconds, since last system startup',
      key = 'uptime'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'System',
      summary = 'System',
      key = 'sys'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Second',
      summary = 'Second',
      key = 'second'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
262145 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 262145,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Heartbeat',
      summary = 'Number of heartbeats issued per virtual machine during the interval',
      key = 'heartbeat'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'System',
      summary = 'System',
      key = 'sys'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'summation',
   statsType = 'delta',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
262146 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 262146,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Disk usage',
      summary = 'Amount of disk space usage for each mount point',
      key = 'diskUsage'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'System',
      summary = 'System',
      key = 'sys'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
262147 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 262147,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource CPU usage (None)',
      summary = 'Amount of CPU used during the interval by the Service Console and other applications',
      key = 'resourceCpuUsage'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'System',
      summary = 'System',
      key = 'sys'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'MHz',
      summary = 'Megahertz',
      key = 'megaHertz'
   },
   rollupType = 'none',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) [
      262148,
      262149,
      262150
   ]
}
''',
262148 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 262148,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource CPU usage (Average)',
      summary = 'Amount of CPU used during the interval by the Service Console and other applications',
      key = 'resourceCpuUsage'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'System',
      summary = 'System',
      key = 'sys'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'MHz',
      summary = 'Megahertz',
      key = 'megaHertz'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
262149 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 262149,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource CPU usage (Maximum)',
      summary = 'Amount of CPU used during the interval by the Service Console and other applications',
      key = 'resourceCpuUsage'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'System',
      summary = 'System',
      key = 'sys'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'MHz',
      summary = 'Megahertz',
      key = 'megaHertz'
   },
   rollupType = 'maximum',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
262150 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 262150,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource CPU usage (Minimum)',
      summary = 'Amount of CPU used during the interval by the Service Console and other applications',
      key = 'resourceCpuUsage'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'System',
      summary = 'System',
      key = 'sys'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'MHz',
      summary = 'Megahertz',
      key = 'megaHertz'
   },
   rollupType = 'minimum',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
262151 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 262151,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource memory touched',
      summary = 'Memory touched by the system resource group',
      key = 'resourceMemTouched'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'System',
      summary = 'System',
      key = 'sys'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
262152 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 262152,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource memory mapped',
      summary = 'Memory mapped by the system resource group',
      key = 'resourceMemMapped'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'System',
      summary = 'System',
      key = 'sys'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
262153 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 262153,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource memory share saved',
      summary = 'Memory saved due to sharing by the system resource group',
      key = 'resourceMemShared'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'System',
      summary = 'System',
      key = 'sys'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
262154 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 262154,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource memory swapped',
      summary = 'Memory swapped out by the system resource group',
      key = 'resourceMemSwapped'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'System',
      summary = 'System',
      key = 'sys'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
262155 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 262155,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource memory overhead',
      summary = 'Overhead memory consumed by the system resource group',
      key = 'resourceMemOverhead'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'System',
      summary = 'System',
      key = 'sys'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
262156 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 262156,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource memory shared',
      summary = 'Memory shared by the system resource group',
      key = 'resourceMemCow'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'System',
      summary = 'System',
      key = 'sys'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
262157 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 262157,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource memory zero',
      summary = 'Zero filled memory used by the system resource group',
      key = 'resourceMemZero'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'System',
      summary = 'System',
      key = 'sys'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
262158 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 262158,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource CPU running (1 min. average)',
      summary = 'CPU running average over 1 minute of the system resource group',
      key = 'resourceCpuRun1'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'System',
      summary = 'System',
      key = 'sys'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
262159 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 262159,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource CPU active (1 min. average)',
      summary = 'CPU active average over 1 minute of the system resource group',
      key = 'resourceCpuAct1'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'System',
      summary = 'System',
      key = 'sys'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
262160 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 262160,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource CPU maximum limited (1 min.)',
      summary = 'CPU maximum limited over 1 minute of the system resource group',
      key = 'resourceCpuMaxLimited1'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'System',
      summary = 'System',
      key = 'sys'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
262161 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 262161,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource CPU running (5 min. average)',
      summary = 'CPU running average over 5 minutes of the system resource group',
      key = 'resourceCpuRun5'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'System',
      summary = 'System',
      key = 'sys'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
262162 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 262162,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource CPU active (5 min. average)',
      summary = 'CPU active average over 5 minutes of the system resource group',
      key = 'resourceCpuAct5'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'System',
      summary = 'System',
      key = 'sys'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
262163 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 262163,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource CPU maximum limited (5 min.)',
      summary = 'CPU maximum limited over 5 minutes of the system resource group',
      key = 'resourceCpuMaxLimited5'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'System',
      summary = 'System',
      key = 'sys'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
262164 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 262164,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource CPU allocation minimum (in MHZ)',
      summary = 'CPU allocation reservation (in MHZ) of the system resource group',
      key = 'resourceCpuAllocMin'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'System',
      summary = 'System',
      key = 'sys'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'MHz',
      summary = 'Megahertz',
      key = 'megaHertz'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
262165 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 262165,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource CPU allocation maximum (in MHZ)',
      summary = 'CPU allocation limit (in MHZ) of the system resource group',
      key = 'resourceCpuAllocMax'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'System',
      summary = 'System',
      key = 'sys'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'MHz',
      summary = 'Megahertz',
      key = 'megaHertz'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
262166 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 262166,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource CPU allocation shares',
      summary = 'CPU allocation shares of the system resource group',
      key = 'resourceCpuAllocShares'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'System',
      summary = 'System',
      key = 'sys'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
262167 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 262167,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource memory allocation minimum (in KB)',
      summary = 'Memory allocation reservation (in KB) of the system resource group',
      key = 'resourceMemAllocMin'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'System',
      summary = 'System',
      key = 'sys'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
262168 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 262168,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource memory allocation maximum (in KB)',
      summary = 'Memory allocation limit (in KB) of the system resource group',
      key = 'resourceMemAllocMax'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'System',
      summary = 'System',
      key = 'sys'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
262169 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 262169,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource memory allocation shares',
      summary = 'Memory allocation shares of the system resource group',
      key = 'resourceMemAllocShares'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'System',
      summary = 'System',
      key = 'sys'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
327680 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 327680,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Active (1 min. average)',
      summary = 'CPU active average over 1 minute',
      key = 'actav1'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource group CPU',
      summary = 'Resource group CPU',
      key = 'rescpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
327681 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 327681,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Active (1 min. peak)',
      summary = 'CPU active peak over 1 minute',
      key = 'actpk1'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource group CPU',
      summary = 'Resource group CPU',
      key = 'rescpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
327682 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 327682,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Running (1 min. average)',
      summary = 'CPU running average over 1 minute',
      key = 'runav1'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource group CPU',
      summary = 'Resource group CPU',
      key = 'rescpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
327683 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 327683,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Active (5 min. average)',
      summary = 'CPU active average over 5 minutes',
      key = 'actav5'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource group CPU',
      summary = 'Resource group CPU',
      key = 'rescpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
327684 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 327684,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Active (5 min. peak)',
      summary = 'CPU active peak over 5 minutes',
      key = 'actpk5'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource group CPU',
      summary = 'Resource group CPU',
      key = 'rescpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
327685 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 327685,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Running (5 min. average)',
      summary = 'CPU running average over 5 minutes',
      key = 'runav5'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource group CPU',
      summary = 'Resource group CPU',
      key = 'rescpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
327686 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 327686,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Active (15 min. average)',
      summary = 'CPU active average over 15 minutes',
      key = 'actav15'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource group CPU',
      summary = 'Resource group CPU',
      key = 'rescpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
327687 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 327687,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Active (15 min. peak)',
      summary = 'CPU active peak over 15 minutes',
      key = 'actpk15'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource group CPU',
      summary = 'Resource group CPU',
      key = 'rescpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
327688 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 327688,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Running (15 min. average)',
      summary = 'CPU running average over 15 minutes',
      key = 'runav15'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource group CPU',
      summary = 'Resource group CPU',
      key = 'rescpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
327689 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 327689,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Running (1 min. peak)',
      summary = 'CPU running peak over 1 minute',
      key = 'runpk1'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource group CPU',
      summary = 'Resource group CPU',
      key = 'rescpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
327690 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 327690,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Throttled (1 min. average)',
      summary = 'Amount of CPU resources over the limit that were refused, average over 1 minute',
      key = 'maxLimited1'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource group CPU',
      summary = 'Resource group CPU',
      key = 'rescpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
327691 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 327691,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Running (5 min. peak)',
      summary = 'CPU running peak over 5 minutes',
      key = 'runpk5'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource group CPU',
      summary = 'Resource group CPU',
      key = 'rescpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
327692 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 327692,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Throttled (5 min. average)',
      summary = 'Amount of CPU resources over the limit that were refused, average over 5 minutes',
      key = 'maxLimited5'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource group CPU',
      summary = 'Resource group CPU',
      key = 'rescpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
327693 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 327693,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Running (15 min. peak)',
      summary = 'CPU running peak over 15 minutes',
      key = 'runpk15'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource group CPU',
      summary = 'Resource group CPU',
      key = 'rescpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
327694 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 327694,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Throttled (15 min. average)',
      summary = 'Amount of CPU resources over the limit that were refused, average over 15 minutes',
      key = 'maxLimited15'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource group CPU',
      summary = 'Resource group CPU',
      key = 'rescpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Percent',
      summary = 'Percentages',
      key = 'percent'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
327695 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 327695,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Group CPU sample count',
      summary = 'Group CPU sample count',
      key = 'sampleCount'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource group CPU',
      summary = 'Resource group CPU',
      key = 'rescpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
327696 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 327696,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Group CPU sample period',
      summary = 'Group CPU sample period',
      key = 'samplePeriod'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Resource group CPU',
      summary = 'Resource group CPU',
      key = 'rescpu'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
393216 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 393216,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory used',
      summary = 'Amount of total configured memory that is available for use',
      key = 'memUsed'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Management agent',
      summary = 'Management agent',
      key = 'managementAgent'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
393217 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 393217,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory swap used',
      summary = 'Sum of the memory swapped by all powered-on virtual machines on the host',
      key = 'swapUsed'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Management agent',
      summary = 'Management agent',
      key = 'managementAgent'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KB',
      summary = 'Kilobytes',
      key = 'kiloBytes'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
393218 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 393218,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory swap in',
      summary = 'Amount of memory that is swapped in for the Service Console',
      key = 'swapIn'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Management agent',
      summary = 'Management agent',
      key = 'managementAgent'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
393219 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 393219,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Memory swap out',
      summary = 'Amount of memory that is swapped out for the Service Console',
      key = 'swapOut'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Management agent',
      summary = 'Management agent',
      key = 'managementAgent'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
393220 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 393220,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'CPU usage',
      summary = 'Amount of Service Console CPU usage',
      key = 'cpuUsage'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Management agent',
      summary = 'Management agent',
      key = 'managementAgent'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'MHz',
      summary = 'Megahertz',
      key = 'megaHertz'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
458752 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 458752,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Average commands issued per second',
      summary = 'Average number of commands issued per second by the storage adapter during the collection interval',
      key = 'commandsAveraged'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Storage adapter',
      summary = 'Storage adapter',
      key = 'storageAdapter'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
458753 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 458753,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Average read requests per second',
      summary = 'Average number of read commands issued per second by the storage adapter during the collection interval',
      key = 'numberReadAveraged'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Storage adapter',
      summary = 'Storage adapter',
      key = 'storageAdapter'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
458754 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 458754,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Average write requests per second',
      summary = 'Average number of write commands issued per second by the storage adapter during the collection interval',
      key = 'numberWriteAveraged'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Storage adapter',
      summary = 'Storage adapter',
      key = 'storageAdapter'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
458755 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 458755,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Read rate',
      summary = 'Rate of reading data by the storage adapter',
      key = 'read'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Storage adapter',
      summary = 'Storage adapter',
      key = 'storageAdapter'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
458756 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 458756,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Write rate',
      summary = 'Rate of writing data by the storage adapter',
      key = 'write'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Storage adapter',
      summary = 'Storage adapter',
      key = 'storageAdapter'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
458757 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 458757,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Read latency',
      summary = 'The average time a read by the storage adapter takes',
      key = 'totalReadLatency'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Storage adapter',
      summary = 'Storage adapter',
      key = 'storageAdapter'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
458758 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 458758,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Write latency',
      summary = 'The average time a write by the storage adapter takes',
      key = 'totalWriteLatency'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Storage adapter',
      summary = 'Storage adapter',
      key = 'storageAdapter'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
524288 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 524288,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Average commands issued per second',
      summary = 'Average number of commands issued per second on the storage path during the collection interval',
      key = 'commandsAveraged'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Storage path',
      summary = 'Storage path',
      key = 'storagePath'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
524289 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 524289,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Average read requests per second',
      summary = 'Average number of read commands issued per second on the storage path during the collection interval',
      key = 'numberReadAveraged'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Storage path',
      summary = 'Storage path',
      key = 'storagePath'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
524290 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 524290,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Average write requests per second',
      summary = 'Average number of write commands issued per second on the storage path during the collection interval',
      key = 'numberWriteAveraged'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Storage path',
      summary = 'Storage path',
      key = 'storagePath'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
524291 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 524291,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Read rate',
      summary = 'Rate of reading data on the storage path',
      key = 'read'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Storage path',
      summary = 'Storage path',
      key = 'storagePath'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
524292 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 524292,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Write rate',
      summary = 'Rate of writing data on the storage path',
      key = 'write'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Storage path',
      summary = 'Storage path',
      key = 'storagePath'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
524293 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 524293,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Read latency',
      summary = 'The average time a read issued on the storage path takes',
      key = 'totalReadLatency'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Storage path',
      summary = 'Storage path',
      key = 'storagePath'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
524294 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 524294,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Write latency',
      summary = 'The average time a write issued on the storage path takes',
      key = 'totalWriteLatency'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Storage path',
      summary = 'Storage path',
      key = 'storagePath'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
589824 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 589824,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Average read requests per second',
      summary = 'Average number of read commands issued per second to the virtual disk during the collection interval',
      key = 'numberReadAveraged'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Virtual disk',
      summary = 'Virtual disk',
      key = 'virtualDisk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
589825 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 589825,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Average write requests per second',
      summary = 'Average number of write commands issued per second to the virtual disk during the collection interval',
      key = 'numberWriteAveraged'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Virtual disk',
      summary = 'Virtual disk',
      key = 'virtualDisk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
589826 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 589826,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Read rate',
      summary = 'Rate of reading data from the virtual disk',
      key = 'read'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Virtual disk',
      summary = 'Virtual disk',
      key = 'virtualDisk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
589827 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 589827,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Write rate',
      summary = 'Rate of writing data to the virtual disk',
      key = 'write'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Virtual disk',
      summary = 'Virtual disk',
      key = 'virtualDisk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
589828 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 589828,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Read latency',
      summary = 'The average time a read from the virtual disk takes.',
      key = 'totalReadLatency'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Virtual disk',
      summary = 'Virtual disk',
      key = 'virtualDisk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
589829 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 589829,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Write latency',
      summary = 'The average time a write to the virtual disk takes',
      key = 'totalWriteLatency'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Virtual disk',
      summary = 'Virtual disk',
      key = 'virtualDisk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
589830 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 589830,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Average number of outstanding read requests',
      summary = 'Average number of outstanding read requests to the virtual disk during the collection interval',
      key = 'readOIO'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Virtual disk',
      summary = 'Virtual disk',
      key = 'virtualDisk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
589831 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 589831,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Average number of outstanding write requests',
      summary = 'Average number of outstanding write requests to the virtual disk during the collection interval',
      key = 'writeOIO'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Virtual disk',
      summary = 'Virtual disk',
      key = 'virtualDisk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
589832 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 589832,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Read workload metric',
      summary = 'Storage DRS virtual disk metric for the read workload model',
      key = 'readLoadMetric'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Virtual disk',
      summary = 'Virtual disk',
      key = 'virtualDisk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
589833 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 589833,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Write workload metric',
      summary = '** FIXME counter.virtualDisk.writeLoadMetric.summary (perf.vmsg) - writeLoadMetric',
      key = 'writeLoadMetric'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Virtual disk',
      summary = 'Virtual disk',
      key = 'virtualDisk'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
655360 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 655360,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Average read requests per second',
      summary = 'Average number of read commands issued per second to the datastore during the collection interval',
      key = 'numberReadAveraged'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Datastore',
      summary = 'Datastore',
      key = 'datastore'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
655361 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 655361,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Average write requests per second',
      summary = 'Average number of write commands issued per second to the datastore during the collection interval',
      key = 'numberWriteAveraged'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Datastore',
      summary = 'Datastore',
      key = 'datastore'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
655362 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 655362,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Read rate',
      summary = 'Rate of reading data from the datastore',
      key = 'read'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Datastore',
      summary = 'Datastore',
      key = 'datastore'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
655363 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 655363,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Write rate',
      summary = 'Rate of writing data to the datastore',
      key = 'write'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Datastore',
      summary = 'Datastore',
      key = 'datastore'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'KBps',
      summary = 'Kilobytes per second',
      key = 'kiloBytesPerSecond'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
655364 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 655364,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Read latency',
      summary = 'The average time a read from the datastore takes',
      key = 'totalReadLatency'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Datastore',
      summary = 'Datastore',
      key = 'datastore'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
655365 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 655365,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Write latency',
      summary = 'The average time a write to the datastore takes',
      key = 'totalWriteLatency'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Datastore',
      summary = 'Datastore',
      key = 'datastore'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Millisecond',
      summary = 'Millisecond',
      key = 'millisecond'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
655366 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 655366,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Storage I/O Control normalized latency',
      summary = 'Storage I/O Control size-normalized I/O latency',
      key = 'sizeNormalizedDatastoreLatency'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Datastore',
      summary = 'Datastore',
      key = 'datastore'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Microsecond',
      summary = 'Microsecond',
      key = 'microsecond'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
655367 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 655367,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Storage I/O Control aggregated IOPS',
      summary = 'Storage I/O Control aggregated IOPS',
      key = 'datastoreIops'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Datastore',
      summary = 'Datastore',
      key = 'datastore'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
655368 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 655368,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Storage DRS datastore bytes read',
      summary = 'Storage DRS datastore bytes read',
      key = 'datastoreReadBytes'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Datastore',
      summary = 'Datastore',
      key = 'datastore'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
655369 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 655369,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Storage DRS datastore bytes written',
      summary = 'Storage DRS datastore bytes written',
      key = 'datastoreWriteBytes'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Datastore',
      summary = 'Datastore',
      key = 'datastore'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
655370 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 655370,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Storage DRS datastore read I/O rate',
      summary = 'Storage DRS datastore read I/O rate',
      key = 'datastoreReadIops'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Datastore',
      summary = 'Datastore',
      key = 'datastore'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
655371 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 655371,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Storage DRS datastore write I/O rate',
      summary = 'Storage DRS datastore write I/O rate',
      key = 'datastoreWriteIops'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Datastore',
      summary = 'Datastore',
      key = 'datastore'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
655372 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 655372,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Storage DRS datastore normalized read latency',
      summary = 'Storage DRS datastore normalized read latency',
      key = 'datastoreNormalReadLatency'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Datastore',
      summary = 'Datastore',
      key = 'datastore'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
655373 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 655373,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Storage DRS datastore normalized write latency',
      summary = 'Storage DRS datastore normalized write latency',
      key = 'datastoreNormalWriteLatency'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Datastore',
      summary = 'Datastore',
      key = 'datastore'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
655374 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 655374,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Storage DRS datastore outstanding read requests',
      summary = 'Storage DRS datastore outstanding read requests',
      key = 'datastoreReadOIO'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Datastore',
      summary = 'Datastore',
      key = 'datastore'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
655375 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 655375,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Storage DRS datastore outstanding write requests',
      summary = 'Storage DRS datastore outstanding write requests',
      key = 'datastoreWriteOIO'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Datastore',
      summary = 'Datastore',
      key = 'datastore'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Number',
      summary = 'Number',
      key = 'number'
   },
   rollupType = 'latest',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
720896 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 720896,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Usage',
      summary = 'Current power usage',
      key = 'power'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Power',
      summary = 'Power',
      key = 'power'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Watt',
      summary = 'Watt',
      key = 'watt'
   },
   rollupType = 'average',
   statsType = 'rate',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
720897 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 720897,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Cap',
      summary = 'Maximum allowed power usage',
      key = 'powerCap'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Power',
      summary = 'Power',
      key = 'power'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Watt',
      summary = 'Watt',
      key = 'watt'
   },
   rollupType = 'average',
   statsType = 'absolute',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
720898 : '''
(vim.PerformanceManager.CounterInfo) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   key = 720898,
   nameInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Energy usage',
      summary = 'Total energy used since last stats reset',
      key = 'energy'
   },
   groupInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Power',
      summary = 'Power',
      key = 'power'
   },
   unitInfo = (vim.ElementDescription) {
      dynamicType = <unset>,
      dynamicProperty = (vmodl.DynamicProperty) [],
      label = 'Joule',
      summary = 'Joule',
      key = 'joule'
   },
   rollupType = 'summation',
   statsType = 'delta',
   level = <unset>,
   perDeviceLevel = <unset>,
   associatedCounterId = (int) []
}
''',
}

def GetOptions():
    """
    Supports the command-line arguments listed below
    """
    parser = OptionParser()
    parser.add_option("-H", "--host",
                      default="localhost",
                      help="Remote host to connect to.")
    parser.add_option("-u", "--user",
                      default="root",
                      help="User name to use when connecting to hostd.")
    parser.add_option("-p", "--password",
                      default="",
                      help="Password to use when connecting to hostd.")
    (options, _) = parser.parse_args()
    return options

def Main():
   # Process command line
   options = GetOptions()

   si = SmartConnect(host = options.host,
                     user = options.user,
                     pwd = options.password)
   atexit.register(Disconnect, si)
   content = si.RetrieveContent()
   prfrmncMngr = content.perfManager

   perfCountersNew = {}

   perfCounters = prfrmncMngr.perfCounter
   for i in range(len(perfCounters)):
      perfCountersNew[perfCounters[i].key] = "\n%s\n" % (perfCounters[i])

   #
   # Check whether all old counters are the same in the new vim.PerformanceManager.perfCounter property
   # We are not expecting that some of the counters are going to be removed
   #
   for oldCntrId, oldCntr in perfCountersOld.iteritems():
      newCntr = perfCountersNew[oldCntrId]
      if newCntr is None:
         print("ERROR: Old counter with ID:%d is not present in the new "
               "vim.PerformanceManager.perfCounter property" % oldCntrId)
         exit(1)
      if oldCntr != newCntr:
         print("ERROR: Counter with ID:%d is different in the new "
               "vim.PerformanceManager.perfCounter property" % oldCntrId)
         exit(1)

   print("SUCCESS!")


# Start program
if __name__ == "__main__":
    Main()
