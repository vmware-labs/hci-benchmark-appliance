README for e2
Prototype tool to remap esxcli namespaces.

Components :
1. The binary to run : e2
2. Sample file for remapping namespaces : ns.txt
3. README file

About the tool :

The tool allows you to remap esxcli commands into a different namespace hierarchy.
The intent is for people to propose the namespace hierarchy desired for the commands.
Since the remapping takes quite a few seconds, I've enabled a simple shell like interaction with the commands.

Things to note about the prototype :
1. Namespaces are dot separated.
   In esxcli if you type "network vswitch list", here you have to type "network.vswitch.list"
2. No help text for namespaces

Steps :
1. tar -xzvf esxcliNamespaces.tar.gz
2. Run binary e2 
   e2 -H <esxHost> -u <username> -p <password> -n <namespace rules>
3. This will bring you to a shell. Just hitting <enter> will give you the top level namespaces available.

Format of namespace rules file :
Two types of entries can be present in the file :
1. Import a namespace from esxcli.
IMPORT_NAMESPACE <destinationNamespace> <sourceNamespace>

You can either specify namespace or namespace.app as the second parameter here
Examples : 
a. IMPORT_NAMESPACE storage.core corestorage
The above statement imports the contents under corestorage to storage.core

b. IMPORT_NAMESPACE vm vms.vm
The above statement imports the contents under vms.vm to vm

2. IMPORT_CMD <destinationCmd> <sourceCmd>

Examples :
a. IMPORT_CMD unixcompat.ping network.diagnose.ping
b. IMPORT_CMD vib.listInDepot imagex.depot.listvibs
   
Sample usage :
kunnatur@kunnatur-lx2:>e2 --host 10.20.104.190 -u root -p '' -n ns.txt

esxcli>
Namespace 

Available Namespaces : 
network.
reflect.
storage.
system.
unixcompat.
vib.
vm.

Available Commands : 

esxcli>unixcompat.
Namespace unixcompat.

Available Namespaces : 

Available Commands : 
lspci
ping
traceroute

esxcli>network.vswitch.list
vSwitch0
  Name: vSwitch0
  Class: etherswitch
  Num Ports: 128
  Used Ports: 3
  Configured Ports: 128
  MTU: 1500
  CPD Status: listen
  Beacon Enabled: false
  Beacon Interval: 1
  Beacon Threshold: 3
  Beacon Required By: []
  Uplinks: vmnic0
  Portgroups: VM Network, Management Network

