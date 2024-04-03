## @file moMapDefs.py
## @brief Definition of the map that is the VIM API.
"""
Definition of the map that is the VIM API.

The map consists of a list of definitions that describe how classes
refer to other classes through property paths as well as a managed
object class hierarchy.

Relevant managed object class hierarchy::

    <class name>: [ <derived class0> <derived class1> ... ]
"""

ClassHierarchy = {}
ClassHierarchy['vim.ManagedEntity'] = [
    'vim.Folder', 'vim.Datacenter', 'vim.ComputeResource', 'vim.HostSystem',
    'vim.VirtualMachine', 'vim.ResourcePool'
]

ClassHierarchy['vim.ComputeResource'] = ['vim.ClusterComputeResource']

#
# Exhaustive list of managed object references
#
#   <referrer class>: { <property path0>: <referee class0>,
#                       <property path1>: <referee class1>,
#                       ... }
#
ValidReferences = {}
ValidReferences['vim.ComputeResource'] = {
    'resourcePool': 'vim.ResourcePool',
    'host': 'vim.HostSystem',
    'datastore': 'vim.Datastore',
    'network': 'vim.Network',
    'environmentBrowser': 'vim.EnvironmentBrowser'
}

ValidReferences['vim.Datacenter'] = {
    'hostFolder': 'vim.Folder',
    'vmFolder': 'vim.Folder',
    'datastoreFolder': 'vim.Folder',
    'networkFolder': 'vim.Folder',
    'datastore': 'vim.Datastore',
    'network': 'vim.Network'
}

ValidReferences['vim.Folder'] = {
    'childEntity': 'vim.ManagedEntity',
}

ValidReferences['vim.HostSystem'] = {
    'datastore': 'vim.Datastore',
    'datastoreBrowser': 'vim.host.DatastoreBrowser',
    'network': 'vim.Network',
    'vm': 'vim.VirtualMachine',
    'configManager.advancedOption': 'vim.option.OptionManager',
    'configManager.cpuScheduler': 'vim.host.CpuSchedulerSystem',
    'configManager.datastoreSystem': 'vim.host.DatastoreSystem',
    'configManager.memoryManager': 'vim.host.MemoryManagerSystem',
    'configManager.storageSystem': 'vim.host.StorageSystem',
    'configManager.networkSystem': 'vim.host.NetworkSystem',
    'configManager.vmotionSystem': 'vim.host.VMotionSystem',
    'configManager.serviceSystem': 'vim.host.ServiceSystem',
    'configManager.firewallSystem': 'vim.host.FirewallSystem',
    'configManager.diagnosticSystem': 'vim.host.DiagnosticSystem',
    'configManager.autoStartManager': 'vim.host.AutoStartManager',
    'configManager.snmpSystem': 'vim.host.SnmpSystem',
    'configManager.graphicsManager': 'vim.host.GraphicsManager'
}

ValidReferences['vim.ServiceInstance'] = {
    'content.rootFolder': 'vim.Folder',
    'content.taskManager': 'vim.TaskManager',
    'content.setting': 'vim.option.OptionManager',
    'content.userDirectory': 'vim.UserDirectory',
    'content.sessionManager': 'vim.SessionManager',
    'content.accountManager': 'vim.host.LocalAccountManager',
    'content.alarmManager': 'vim.alarm.AlarmManager',
    'content.authorizationManager': 'vim.AuthorizationManager',
    'content.customFieldsManager': 'vim.CustomFieldsManager',
    'content.diagnosticManager': 'vim.DiagnosticManager',
    'content.eventManager': 'vim.event.EventManager',
    'content.licenseManager': 'vim.LicenseManager',
    'content.perfManager': 'vim.PerformanceManager',
    'content.propertyCollector': 'vmodl.query.PropertyCollector',
    'content.scheduledTaskManager': 'vim.scheduler.ScheduledTaskManager',
    'content.searchIndex': 'vim.SearchIndex',
    'content.customizationSpecManager': 'vim.CustomizationSpecManager'
}

ValidReferences['vim.VirtualMachine'] = {
    'environmentBrowser': 'vim.EnvironmentBrowser',
    'resourcePool': 'vim.ResourcePool',
    'datastore': 'vim.Datastore',
    'network': 'vim.Network',
    'snapshot.currentSnapshot': 'vim.vm.Snapshot',
}

ValidReferences['vim.TaskManager'] = {
    'recentTask': 'vim.Task',
}

ValidReferences['vim.scheduler.ScheduledTaskManager'] = {
    'scheduledTask': 'vim.scheduler.ScheduledTask'
}
