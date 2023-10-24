# Patch in some last minute additions to the API
db = RbVmomi::VIM.loader.instance_variable_get(:@db)
db['HostVsanInternalSystem']['methods']["QuerySyncingVsanObjects"] =
  {"params"=>
    [{"name"=>"uuids",
      "is-array"=>true,
      "is-optional"=>true,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:string"}],
   "result"=>
    {"is-array"=>false,
     "is-optional"=>false,
     "is-task"=>false,
     "version-id-ref"=>nil,
     "wsdl_type"=>"xsd:string"}}
db['HostVsanInternalSystem']['methods']["GetVsanObjExtAttrs"] =
  {"params"=>
    [{"name"=>"uuids",
      "is-array"=>true,
      "is-optional"=>true,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:string"}],
   "result"=>
    {"is-array"=>false,
     "is-optional"=>false,
     "is-task"=>false,
     "version-id-ref"=>nil,
     "wsdl_type"=>"xsd:string"}}
db['VsanPolicyChangeBatch'] =
  {"kind"=>"data",
   "props"=>
    [{"name"=>"uuid",
      "is-optional"=>true,
      "is-array"=>true,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:string"},
     {"name"=>"policy",
      "is-optional"=>true,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:string"}],
  "wsdl_base"=>"DynamicData",
  "wsdl_name"=>'VsanPolicyChangeBatch'}
db['VsanPolicyCost'] =
  {"kind"=>"data",
   "props"=>
    [{"name"=>"changeDataSize",
      "is-optional"=>true,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:long"},
     {"name"=>"currentDataSize",
      "is-optional"=>true,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:long"},
     {"name"=>"tempDataSize",
      "is-optional"=>true,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:long"},
     {"name"=>"copyDataSize",
      "is-optional"=>true,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:long"},
     {"name"=>"changeFlashReadCacheSize",
      "is-optional"=>true,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:long"},
     {"name"=>"currentFlashReadCacheSize",
      "is-optional"=>true,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:long"},
     {"name"=>"diskSpaceToAddressSpaceRatio",
      "is-optional"=>true,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:float"}],
  "wsdl_base"=>"DynamicData",
  "wsdl_name"=>"VsanPolicyCost"}
db['VsanPolicySatisfiability'] =
  {"kind"=>"data",
   "props"=>
    [{"name"=>"uuid",
      "is-optional"=>true,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:string"},
     {"name"=>"isSatisfiable",
      "is-optional"=>false,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:boolean"},
     {"name"=>"reason",
      "is-optional"=>true,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"LocalizableMessage"},
     {"name"=>"cost",
      "is-optional"=>true,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"VsanPolicyCost"}],
  "wsdl_base"=>"DynamicData",
  "wsdl_name"=>"VsanPolicySatisfiability"}
db['HostVsanInternalSystem']['methods']["ReconfigurationSatisfiable"] =
  {"params"=>
    [{"name"=>"pcbs",
      "is-array"=>true,
      "is-optional"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"VsanPolicyChangeBatch"}],
   "result"=>
    {"is-array"=>true,
     "is-optional"=>false,
     "is-task"=>false,
     "version-id-ref"=>nil,
     "wsdl_type"=>"VsanPolicySatisfiability"}}
db['VsanHostFaultDomainInfo'] =
  {"kind"=>"data",
   "props"=>
    [{"name"=>"name",
      "is-optional"=>false,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:string"}],
   "wsdl_base"=>"DynamicData"}
if !db['VsanHostConfigInfo']['props'].find{|x| x["name"] == "faultDomainInfo"}
  db['VsanHostConfigInfo']['props'] <<
    {"name"=>"faultDomainInfo",
     "is-optional"=>true,
     "is-array"=>false,
     "version-id-ref"=>nil,
     "wsdl_type"=>"VsanHostFaultDomainInfo"}
end
if !db['HostScsiDisk']['props'].find{|x| x["name"] == "emulatedDIXDIFEnabled"}
  db['HostScsiDisk']['props'] <<
    {"name"=>"emulatedDIXDIFEnabled",
     "is-optional"=>true,
     "is-array"=>false,
     "version-id-ref"=>nil,
     "wsdl_type"=>"xsd:boolean"}
end
db['FileInfo']['props'] =
 [{"name"=>"path",
   "is-optional"=>false,
   "is-array"=>false,
   "version-id-ref"=>nil,
   "wsdl_type"=>"xsd:string"},
  {"name"=>"friendlyName",
   "is-optional"=>true,
   "is-array"=>false,
   "version-id-ref"=>"vim.version.version11",
   "wsdl_type"=>"xsd:string"},
  {"name"=>"fileSize",
   "is-optional"=>true,
   "is-array"=>false,
   "version-id-ref"=>nil,
   "wsdl_type"=>"xsd:long"},
  {"name"=>"modification",
   "is-optional"=>true,
   "is-array"=>false,
   "version-id-ref"=>nil,
   "wsdl_type"=>"xsd:dateTime"},
  {"name"=>"owner",
   "is-optional"=>true,
   "is-array"=>false,
   "version-id-ref"=>"vim.version.version5",
   "wsdl_type"=>"xsd:string"}]
db['HostVsanSystem']['methods']['RemoveDiskMapping_Task'] =
{"params"=>
  [{"name"=>"mapping",
    "is-array"=>true,
    "is-optional"=>false,
    "version-id-ref"=>nil,
    "wsdl_type"=>"VsanHostDiskMapping"},
   {"name"=>"maintenanceSpec",
    "is-array"=>false,
    "is-optional"=>true,
    "version-id-ref"=>"vim.version.r14i18",
    "wsdl_type"=>"HostMaintenanceSpec"}],
 "result"=>
  {"is-array"=>true,
   "is-optional"=>true,
   "is-task"=>true,
   "version-id-ref"=>nil,
   "wsdl_type"=>"VsanHostDiskMapResult"}}
db['HostVsanInternalSystem']['methods']["QueryVsanObjectUuidsByFilter"] =
  {"params"=>
    [{"name"=>"uuids",
      "is-array"=>true,
      "is-optional"=>true,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:string"},
     {"name"=>"limit",
      "is-array"=>false,
      "is-optional"=>true,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:int"},
     {"name"=>"version",
      "is-array"=>false,
      "is-optional"=>true,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:int"}],
   "result"=>
    {"is-array"=>true,
     "is-optional"=>false,
     "is-task"=>false,
     "version-id-ref"=>nil,
     "wsdl_type"=>"xsd:string"}}
db['VsanObjectOperationResult'] =
  {"kind"=>"data",
   "props"=>
    [{"name"=>"uuid",
      "is-optional"=>false,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:string"},
     {"name"=>"failureReason",
      "is-optional"=>true,
      "is-array"=>true,
      "version-id-ref"=>nil,
      "wsdl_type"=>"LocalizableMessage"}],
   "wsdl_base"=>"DynamicData"}
db['HostVsanInternalSystem']['methods']["UpgradeVsanObjects"] =
  {"params"=>
    [{"name"=>"uuids",
      "is-array"=>true,
      "is-optional"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:string"},
     {"name"=>"newVersion",
      "is-array"=>false,
      "is-optional"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:int"}],
   "result"=>
    {"is-array"=>true,
     "is-optional"=>true,
     "is-task"=>false,
     "version-id-ref"=>nil,
     "wsdl_type"=>"VsanObjectOperationResult"}}
db['HostVsanSystem']['methods']['EvacuateVsanNode_Task'] =
{"params"=>
   [{"name"=>"maintenanceSpec",
     "is-array"=>false,
     "is-optional"=>false,
     "version-id-ref"=>nil,
     "wsdl_type"=>"HostMaintenanceSpec"},
    {"name"=>"timeout",
     "is_array"=>false,
     "is_optional"=>false,
     "version-id-ref"=>nil,
     "wsdl_type"=>"xsd:int"}],
 "result"=>
  {"is-array"=>false,
   "is-optional"=>false,
   "is-task"=>true,
   "version-id-ref"=>nil,
   "wsdl_type"=>nil}}
db['HostVsanSystem']['methods']['RecommissionVsanNode_Task'] =
{"params"=>[],
 "result"=>
  {"is-array"=>false,
   "is-optional"=>false,
   "is-task"=>true,
   "version-id-ref"=>nil,
   "wsdl_type"=>nil}}
db['HostVsanInternalSystemDeleteVsanObjectsResult'] =
  {"kind"=>"data",
   "props"=>
    [{"name"=>"uuid",
      "is-optional"=>false,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:string"},
     {"name"=>"success",
      "is-optional"=>false,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:boolean"},
     {"name"=>"failureReason",
      "is-optional"=>true,
      "is-array"=>true,
      "version-id-ref"=>nil,
      "wsdl_type"=>"LocalizableMessage"}],
   "wsdl_base"=>"DynamicData"}
db['HostVsanInternalSystem']['methods']["DeleteVsanObjects"] =
{"params"=>
  [{"name"=>"uuids",
    "is-array"=>true,
    "is-optional"=>false,
    "version-id-ref"=>nil,
    "wsdl_type"=>"xsd:string"},
   {"name"=>"force",
    "is-array"=>false,
    "is-optional"=>true,
    "version-id-ref"=>nil,
    "wsdl_type"=>"xsd:boolean"}],
  "result"=>
    {"is-array"=>true,
     "is-optional"=>false,
     "is-task"=>false,
     "version-id-ref"=>nil,
     "wsdl_type"=>"HostVsanInternalSystemDeleteVsanObjectsResult"}}
db['VsanHostDiskMapInfo'] =
  {"kind"=>"data",
   "props"=>
    [{"name"=>"mapping",
      "is-optional"=>false,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"VsanHostDiskMapping"},
    {"name"=>"mounted",
      "is-optional"=>false,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:boolean"}],
    "wsdl_base"=>"DynamicData"}
if !db['VsanHostConfigInfoStorageInfo']['props'].find{|x| x["name"] == "diskMapInfo"}
  db['VsanHostConfigInfoStorageInfo']['props'] <<
    {"name"=>"diskMapInfo",
     "is-optional"=>true,
     "is-array"=>true,
     "version-id-ref"=>nil,
     "wsdl_type"=>"VsanHostDiskMapInfo"}
end
db['VsanHostVsanDiskInfo'] =
  {"kind"=>"data",
   "props"=>
    [{"name"=>"vsanUuid",
      "is-optional"=>false,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:string"},
    {"name"=>"formatVersion",
      "is-optional"=>false,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:int"}],
    "wsdl_base"=>"DynamicData"}
if !db['HostScsiDisk']['props'].find{|x| x["name"] == "vsanDiskInfo"}
  db['HostScsiDisk']['props'] <<
    {"name"=>"vsanDiskInfo",
     "is-optional"=>true,
     "is-array"=>false,
     "version-id-ref"=>nil,
     "wsdl_type"=>"VsanHostVsanDiskInfo"}
end

db['VimEsxCLICLIFault'] =
  {"kind"=>"data",
   "props"=>
    [{"name"=>"errMsg",
      "is-array"=>true,
      "is-optional"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:string"}],
   "wsdl_base"=>"DynamicData",
   "wsdl_name"=>'VimEsxCLICLIFault'}

db['VirtualMachineFileLayoutExFileInfo']['props'] <<
  {"name"=>"backingObjectId",
   "is-optional"=>true,
   "is-array"=>false,
   "version-id-ref"=>"vim.version.version10",
   "wsdl_type"=>"xsd:string"}

db['VirtualNVMEController'] =
  {
    "kind"=>"data",
    "props"=>[],
    "wsdl_base"=>"VirtualController"
  }
db = nil

RbVmomi::VIM.loader.add_types(
{"VsanUpgradeSystemUpgradeHistoryDiskGroupOpType"=>
  {"kind"=>"enum", "values"=>["add", "remove"]},
 "VsanUpgradeSystem"=>
  {"kind"=>"managed",
   "props"=>[],
   "methods"=>
    {"PerformVsanUpgradePreflightCheck"=>
      {"params"=>
        [{"name"=>"cluster",
          "is-array"=>false,
          "is-optional"=>false,
          "version-id-ref"=>nil,
          "wsdl_type"=>"ClusterComputeResource"},
         {"name"=>"downgradeFormat",
          "is-array"=>false,
          "is-optional"=>true,
          "version-id-ref"=>nil,
          "wsdl_type"=>"xsd:boolean"}],
       "result"=>
        {"is-array"=>false,
         "is-optional"=>false,
         "is-task"=>false,
         "version-id-ref"=>nil,
         "wsdl_type"=>"VsanUpgradeSystemPreflightCheckResult"}},
     "QueryVsanUpgradeStatus"=>
      {"params"=>
        [{"name"=>"cluster",
          "is-array"=>false,
          "is-optional"=>false,
          "version-id-ref"=>nil,
          "wsdl_type"=>"ClusterComputeResource"}],
       "result"=>
        {"is-array"=>false,
         "is-optional"=>false,
         "is-task"=>false,
         "version-id-ref"=>nil,
         "wsdl_type"=>"VsanUpgradeSystemUpgradeStatus"}},
     "PerformVsanUpgrade_Task"=>
      {"params"=>
        [{"name"=>"cluster",
          "is-array"=>false,
          "is-optional"=>false,
          "version-id-ref"=>nil,
          "wsdl_type"=>"ClusterComputeResource"},
         {"name"=>"performObjectUpgrade",
          "is-array"=>false,
          "is-optional"=>true,
          "version-id-ref"=>nil,
          "wsdl_type"=>"xsd:boolean"},
         {"name"=>"downgradeFormat",
          "is-array"=>false,
          "is-optional"=>true,
          "version-id-ref"=>nil,
          "wsdl_type"=>"xsd:boolean"},
         {"name"=>"allowReducedRedundancy",
          "is-array"=>false,
          "is-optional"=>true,
          "version-id-ref"=>nil,
          "wsdl_type"=>"xsd:boolean"},
         {"name"=>"excludeHosts",
          "is-array"=>true,
          "is-optional"=>true,
          "version-id-ref"=>nil,
          "wsdl_type"=>"HostSystem"}],
       "result"=>
        {"is-array"=>false,
         "is-optional"=>false,
         "is-task"=>true,
         "version-id-ref"=>nil,
         "wsdl_type"=>"VsanUpgradeSystemUpgradeStatus"}}},
   "wsdl_base"=>"ManagedObject"},
 "VsanUpgradeSystemAPIBrokenIssue"=>
  {"kind"=>"data",
   "props"=>
    [{"name"=>"hosts",
      "is-optional"=>false,
      "is-array"=>true,
      "version-id-ref"=>nil,
      "wsdl_type"=>"HostSystem"}],
   "wsdl_base"=>"VsanUpgradeSystemPreflightCheckIssue"},
 "VsanUpgradeSystemAutoClaimEnabledOnHostsIssue"=>
  {"kind"=>"data",
   "props"=>
    [{"name"=>"hosts",
      "is-optional"=>false,
      "is-array"=>true,
      "version-id-ref"=>nil,
      "wsdl_type"=>"HostSystem"}],
   "wsdl_base"=>"VsanUpgradeSystemPreflightCheckIssue"},
 "VsanUpgradeSystemHostsDisconnectedIssue"=>
  {"kind"=>"data",
   "props"=>
    [{"name"=>"hosts",
      "is-optional"=>false,
      "is-array"=>true,
      "version-id-ref"=>nil,
      "wsdl_type"=>"HostSystem"}],
   "wsdl_base"=>"VsanUpgradeSystemPreflightCheckIssue"},
 "VsanUpgradeSystemMissingHostsInClusterIssue"=>
  {"kind"=>"data",
   "props"=>
    [{"name"=>"hosts",
      "is-optional"=>false,
      "is-array"=>true,
      "version-id-ref"=>nil,
      "wsdl_type"=>"HostSystem"}],
   "wsdl_base"=>"VsanUpgradeSystemPreflightCheckIssue"},
 "VsanUpgradeSystemNetworkPartitionInfo"=>
  {"kind"=>"data",
   "props"=>
    [{"name"=>"hosts",
      "is-optional"=>false,
      "is-array"=>true,
      "version-id-ref"=>nil,
      "wsdl_type"=>"HostSystem"}],
   "wsdl_base"=>"DynamicData"},
 "VsanUpgradeSystemNetworkPartitionIssue"=>
  {"kind"=>"data",
   "props"=>
    [{"name"=>"partitions",
      "is-optional"=>false,
      "is-array"=>true,
      "version-id-ref"=>nil,
      "wsdl_type"=>"VsanUpgradeSystemNetworkPartitionInfo"}],
   "wsdl_base"=>"VsanUpgradeSystemPreflightCheckIssue"},
 "VsanUpgradeSystemPreflightCheckIssue"=>
  {"kind"=>"data",
   "props"=>
    [{"name"=>"msg",
      "is-optional"=>false,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:string"}],
   "wsdl_base"=>"DynamicData"},
 "VsanUpgradeSystemPreflightCheckResult"=>
  {"kind"=>"data",
   "props"=>
    [{"name"=>"issues",
      "is-optional"=>true,
      "is-array"=>true,
      "version-id-ref"=>nil,
      "wsdl_type"=>"VsanUpgradeSystemPreflightCheckIssue"},
     {"name"=>"diskMappingToRestore",
      "is-optional"=>true,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"VsanHostDiskMapping"}],
   "wsdl_base"=>"DynamicData"},
 "VsanUpgradeSystemRogueHostsInClusterIssue"=>
  {"kind"=>"data",
   "props"=>
    [{"name"=>"uuids",
      "is-optional"=>false,
      "is-array"=>true,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:string"}],
   "wsdl_base"=>"VsanUpgradeSystemPreflightCheckIssue"},
 "VsanUpgradeSystemUpgradeHistoryDiskGroupOp"=>
  {"kind"=>"data",
   "props"=>
    [{"name"=>"operation",
      "is-optional"=>false,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:string"},
     {"name"=>"diskMapping",
      "is-optional"=>false,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"VsanHostDiskMapping"}],
   "wsdl_base"=>"VsanUpgradeSystemUpgradeHistoryItem"},
 "VsanUpgradeSystemUpgradeHistoryItem"=>
  {"kind"=>"data",
   "props"=>
    [{"name"=>"timestamp",
      "is-optional"=>false,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:dateTime"},
     {"name"=>"host",
      "is-optional"=>true,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"HostSystem"},
     {"name"=>"message",
      "is-optional"=>false,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:string"},
     {"name"=>"task",
      "is-optional"=>true,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"Task"}],
   "wsdl_base"=>"DynamicData"},
 "VsanUpgradeSystemUpgradeHistoryPreflightFail"=>
  {"kind"=>"data",
   "props"=>
    [{"name"=>"preflightResult",
      "is-optional"=>false,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"VsanUpgradeSystemPreflightCheckResult"}],
   "wsdl_base"=>"VsanUpgradeSystemUpgradeHistoryItem"},
 "VsanUpgradeSystemUpgradeStatus"=>
  {"kind"=>"data",
   "props"=>
    [{"name"=>"inProgress",
      "is-optional"=>false,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:boolean"},
     {"name"=>"history",
      "is-optional"=>true,
      "is-array"=>true,
      "version-id-ref"=>nil,
      "wsdl_type"=>"VsanUpgradeSystemUpgradeHistoryItem"},
     {"name"=>"aborted",
      "is-optional"=>true,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:boolean"},
     {"name"=>"completed",
      "is-optional"=>true,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:boolean"},
     {"name"=>"progress",
      "is-optional"=>true,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:int"}],
   "wsdl_base"=>"DynamicData"},
 "VsanUpgradeSystemV2ObjectsPresentDuringDowngradeIssue"=>
  {"kind"=>"data",
   "props"=>
    [{"name"=>"uuids",
      "is-optional"=>false,
      "is-array"=>true,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:string"}],
   "wsdl_base"=>"VsanUpgradeSystemPreflightCheckIssue"},
 "VsanUpgradeSystemWrongEsxVersionIssue"=>
  {"kind"=>"data",
   "props"=>
    [{"name"=>"hosts",
      "is-optional"=>false,
      "is-array"=>true,
      "version-id-ref"=>nil,
      "wsdl_type"=>"HostSystem"}],
   "wsdl_base"=>"VsanUpgradeSystemPreflightCheckIssue"},
  "VimHostVsanAsyncSystem"=>
  {"kind"=>"managed",
   "props"=>[],
   "methods"=>
    {"StartProactiveRebalance"=>
      {"params"=>
        [{"name"=>"timeSpan",
          "is-array"=>false,
          "is-optional"=>true,
          "version-id-ref"=>nil,
          "wsdl_type"=>"xsd:int"},
         {"name"=>"varianceThreshold",
          "is-array"=>false,
          "is-optional"=>true,
          "version-id-ref"=>nil,
          "wsdl_type"=>"xsd:float"},
         {"name"=>"timeThreshold",
          "is-array"=>false,
          "is-optional"=>true,
          "version-id-ref"=>nil,
          "wsdl_type"=>"xsd:int"},
         {"name"=>"rateThreshold",
          "is-array"=>false,
          "is-optional"=>true,
          "version-id-ref"=>nil,
          "wsdl_type"=>"xsd:int"}],
       "result"=>
         {"is-array"=>false,
          "is-optional"=>false,
          "is-task"=>false,
          "version-id-ref"=>nil,
          "wsdl_type"=>'xsd:boolean'}},
     "StopProactiveRebalance"=>
      {"params"=>[],
       "result"=>
         {"is-array"=>false,
          "is-optional"=>false,
          "is-task"=>false,
          "version-id-ref"=>nil,
          "wsdl_type"=>'xsd:boolean'}},
     "GetProactiveRebalanceInfo"=>
      {"params"=>[],
       "result"=>
         {"is-array"=>false,
          "is-optional"=>false,
          "is-task"=>false,
          "version-id-ref"=>nil,
          "wsdl_type"=>"VimHostVsanProactiveRebalanceInfo"}}},
    "wsdl_base"=>"ManagedObject"},
  "VimHostVsanProactiveRebalanceInfo"=>
  {"kind"=>"data",
   "props"=>
    [{"name"=>"running",
      "is-optional"=>false,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:boolean"},
     {"name"=>"startTs",
      "is-optional"=>true,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:dateTime"},
     {"name"=>"stopTs",
      "is-optional"=>true,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:dateTime"},
     {"name"=>"varianceThreshold",
      "is-optional"=>true,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:float"},
     {"name"=>"timeThreshold",
      "is-optional"=>true,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:int"},
     {"name"=>"rateThreshold",
      "is-optional"=>true,
      "is-array"=>false,
      "version-id-ref"=>nil,
      "wsdl_type"=>"xsd:int"}],
    "wsdl_base"=>"DynamicData"
  },
}
)

db = nil


class RbVmomi::VIM
  def initialize opts
    super opts
  end

  def spawn_additional_connection
    c1 = RbVmomi::VIM.new(@opts)
    c1.cookie = self.cookie
    c1.rev = self.rev
    c1
  end
end

RbVmomi::VIM::ManagedObject
class RbVmomi::VIM::ManagedObject
  def dup_on_conn conn
    self.class.new(conn, self._ref)
  end
end

RbVmomi::VIM::ReflectManagedMethodExecuter
class RbVmomi::VIM::ReflectManagedMethodExecuter
  def execute moid, method, args
    soap_args = args.map do |k,v|
      VIM::ReflectManagedMethodExecuterSoapArgument.new.tap do |soap_arg|
        soap_arg.name = k
        xml = Builder::XmlMarkup.new :indent => 0
        _connection.obj2xml xml, k, :anyType, false, v
        soap_arg.val = xml.target!
      end
    end
    result = ExecuteSoap(:moid => moid, :version => 'urn:vim25/5.0',
                         :method => method, :argument => soap_args)
    if result
      # If esxcli command was executed successfully, we should have response,
      # bug if the command met error, we should have fault
      if result.response
        _connection.deserializer.deserialize Nokogiri(result.response).root, nil
      elsif result.fault
        # With a fault, we should raise it
        # With VimEsxCLICLIFault, its actual error message which user is aware of,
        # is inside field errMsg
        fault = _connection.deserializer.deserialize Nokogiri(result.fault.faultDetail).root, nil
        if fault.fault &&
          (fault.fault.instance_of? RbVmomi::VIM::VimEsxCLICLIFault)
          raise RbVmomi::Fault.new(fault.fault.errMsg, fault.fault)
        else
          raise fault
        end
      else
        nil
      end
    else
      nil
    end
  end
end

RbVmomi::Connection
class RbVmomi::Connection
  def parse_response resp, desc
    if resp.at('faultcode')
      detail = resp.at('detail')
      fault = detail && @deserializer.deserialize(detail.children.first, 'MethodFault')
      msg = resp.at('faultstring').text
      if fault
        # As we know, in esxcli implementation,
        # the fault message is set to errMsg in the way:
        # output->AddErrorMessage(ex.GetMessage());
        # so we have to use errMsg to overwrite faultstring in response,
        # otherwise we cannot represent real error.
        if fault.instance_of? RbVmomi::VIM::VimEsxCLICLIFault
          msg = fault.errMsg
        end
        raise RbVmomi::Fault.new(msg, fault)
      else
        fail "#{resp.at('faultcode').text}: #{msg}"
      end
    else
      if desc
        type = desc['is-task'] ? 'Task' : desc['wsdl_type']
        returnvals = resp.children.select(&:element?).map { |c| @deserializer.deserialize c, type }
        (desc['is-array'] && !desc['is-task']) ? returnvals : returnvals.first
      else
        nil
      end
    end
  end

end

class RbVmomi::VIM
  def _latestVersion
    body = http.get('/sdk/vimServiceVersions.xml').body
    xml = Nokogiri(body)
    xml.xpath('//namespace[name="urn:vim25"]/version').text
  end

  def latestVersion
    @latestVersion ||= _latestVersion
  end
end

def _run_with_latest_rev conn
  _run_with_rev(conn, conn.latestVersion) do
    yield
  end
end

def _run_with_rev conn, rev
  old_rev = conn.rev
  begin
    conn.rev = rev
    yield
  ensure
    conn.rev = old_rev
  end
end


RbVmomi::VIM::HostSystem
class RbVmomi::VIM::HostSystem
  def filtered_disks_for_vsan opts = {}
    vsan = opts[:vsanSystem] || self.configManager.vsanSystem
    stateFilter = opts[:state_filter] || /^eligible$/
    disks = vsan.QueryDisksForVsan()

    disks = disks.select do |disk|
      disk.state =~ stateFilter
    end

    if opts[:filter_ssd_by_model] || opts[:filter_hdd_by_model]
      disks = disks.select do |disk|
        model = [
          disk.disk.vendor,
          disk.disk.model
        ].compact.map{|x| x.strip}.join(" ")
        ssd_model_match = true
        hdd_model_match = true
        if opts[:filter_ssd_by_model]
          ssd_model_match = (model =~ opts[:filter_ssd_by_model])
        end
        if opts[:filter_hdd_by_model]
          hdd_model_match = (model =~ opts[:filter_hdd_by_model])
        end
        isSsd = disk.disk.ssd
        (!isSsd && hdd_model_match) || (isSsd && ssd_model_match)
      end
    end

    disks = disks.map{|x| x.disk}

    disks
  end

  def consume_disks_for_vsan opts = {}
    vsan = opts[:vsanSystem] || self.configManager.vsanSystem
    disks = filtered_disks_for_vsan(opts.merge(
      :state_filter => /^eligible$/,
      :vsanSystem => vsan
    ))
    if disks.length > 0
      vsan.AddDisks_Task(:disk => disks)
    end
  end
end

RbVmomi::VIM::HostVsanInternalSystem
class RbVmomi::VIM::HostVsanInternalSystem
  def rvc_load_json x
    if $rvc_json_use_oj
      Oj.load(x)
    else
      JSON.load(x)
    end
  end

  def _parseJson json
    if json == "BAD"
      return nil
    end
    begin
      json = rvc_load_json(json)
    rescue
      nil
    end
  end

  def query_cmmds queries
    useGzip = $vsanUseGzipApis
    if useGzip
      queries = queries + [{:type => "GZIP"}]
    end
    json = self.QueryCmmds(:queries => queries)
    if useGzip
      require 'base64'
      begin
        gzip = Base64.decode64(json)
        gz = Zlib::GzipReader.new(StringIO.new(gzip))
        json = gz.read
      rescue Zlib::GzipFile::Error
        raise "Server failed to gather CMMDS entries: RESULT = '#{json}'"
      end
    end
    objects = _parseJson json
    if !objects
      raise "Server failed to gather CMMDS entries: JSON = '#{json}'"
#      open('/tmp/badjson.json', 'w'){|io| io.write json}
#      raise "Server failed to gather CMMDS entries: JSON = #{json.length}"
    end
    objects = objects['result']
    objects
  end

  def query_vsan_obj_extattrs(opts)
    json = self.GetVsanObjExtAttrs(opts)
    objects = _parseJson json
    if !objects
      raise "Server failed to gather vSAN obj ext attr info for #{opts[:uuids]}: JSON = '#{json}'"
    end
    objects
  end


  def query_vsan_objects(opts)
    json = self.QueryVsanObjects(opts)
    objects = _parseJson json
    if !objects
      raise "Server failed to gather vSAN object info for #{opts[:uuids]}: JSON = '#{json}'"
    end
    objects
  end

  def query_syncing_vsan_objects(opts = {})
    json = self.QuerySyncingVsanObjects(opts)
    objects = _parseJson json
    if !objects
      raise "Server failed to query syncing objects: JSON = '#{json}'"
    end
    objects
  end

  def query_vsan_statistics(opts = {})
    json = self.QueryVsanStatistics(opts)
    objects = _parseJson json
    if !objects
      raise "Server failed to query vsan stats: JSON = '#{json}'"
    end
    objects
  end

  def query_physical_vsan_disks(opts)
    json = self.QueryPhysicalVsanDisks(opts)
    objects = _parseJson json
    if !objects
      raise "Server failed to query vsan disks: JSON = '#{json}'"
    end
    objects
  end

  def query_objects_on_physical_vsan_disk(opts)
    json = self.QueryObjectsOnPhysicalVsanDisk(opts)
    objects = _parseJson json
    if !objects
      raise "Server failed to query objects on vsan disks: JSON = '#{json}'"
    end
    objects
  end
end


def _vsan_disk_results_handler logger, results, fault_msg
  has_error = false
  results.values.each do |r|
    if r.is_a?(VIM::LocalizedMethodFault)
      logger.info fault_msg
      logger.info r.localizedMessage
      has_error = true
    else
      if !r.is_a?(Array)
        # Assertion, must be an Array, leave this to see what happened
        # XXX, if this happens, we should file a bug.
        logger.info PP.pp(r, "")
        has_error = true
      else
        r.each do |dr|
          if dr.error
            logger.info fault_msg
            msg = _marshal_disk_mapping_error(dr)
            logger.info _marshal_disk_mapping_error(dr)
            if msg.include? 'Out of resources'
              logger.info "Please try again with option 'allow-reduced-redundancy'"
            end
            has_error = true
          end
        end
      end
    end
  end
  return has_error
end

def _ondisk_upgrade_get_hosts_props conn, pc, hosts
  _run_with_rev(conn, 'dev') do
    if conn.serviceContent.about.build.to_i < "1996141".to_i
      raise "Vpx is too old, please pick a new one after official build 1996141"
    end
    all_hosts_props = pc.collectMultiple(hosts,
      'name',
      'runtime.connectionState',
      'configManager.vsanSystem',
      'configManager.vsanInternalSystem',
      'configManager.advancedOption',
      'config.product',
      'runtime.inMaintenanceMode',
    )

    disconnected_hosts = all_hosts_props.select do |k,v|
      v['runtime.connectionState'] != 'connected'
    end.keys

    # Only consider hosts that are connected
    hosts_props = all_hosts_props.select{|h,p| !disconnected_hosts.member?(h)}
    host = hosts_props.keys.first
    if !host
       RVC::Util::err "Couldn't find any connected hosts"
    end

    vsanSysList = Hash[hosts_props.map{|h, p| [h, p['configManager.vsanSystem']]}]
    vsansys_props = pc.collectMultiple(vsanSysList.values,
      'config.clusterInfo',
      'config.storageInfo.autoClaimStorage',
      'config.storageInfo.diskMapping',
    )
    hosts_props.each do |host, props|
      vsanSys = vsanSysList[host]
      clusterInfo = vsansys_props[vsanSys]['config.clusterInfo']
      props['nodeUuid'] = clusterInfo.nodeUuid
      autoClaim = vsansys_props[vsanSys]['config.storageInfo.autoClaimStorage']
      props['vsan.autoClaimStorage'] = autoClaim
      props['vsandisks'] = []
      diskMappings = vsansys_props[vsanSys]['config.storageInfo.diskMapping'] || []
      diskMappings.each do |group|
        disk = {}
        detail = group.ssd.vsanDiskInfo
        disk['deviceName'] = group.ssd.deviceName
        if !detail && props['config.product'].version >= "6.0.0"
          raise "ESX server #{props['name']} is too old, please pick a new one after official build 1994142"
        end
        # 55u1 node doesn't have valid VsanDiskInfo, and formatVersion is 0
        disk['formatVersion'] = detail ? detail.formatVersion : 0
        props['vsandisks'] << disk
      end
    end

    return all_hosts_props
  end
end
