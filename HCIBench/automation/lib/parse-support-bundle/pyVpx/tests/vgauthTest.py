#!/usr/bin/python

#
# Basic tests for Vim::Vm::Guest::AliasManager
#
# These require the latest tools on a VM with a supported guest
# (linux or Windows).  Until there's a way to get one from
# a standard place, its hardcoded a VM name.
#

from pyVmomi import Vim, Vmodl
from pyVim.helpers import Log
from guestOpsUtils import *


def init_certs():
   global caCert
   caCert = "-----BEGIN CERTIFICATE-----\n"\
"MIIDaTCCAlGgAwIBAgIJAP2wwtxh1P4OMA0GCSqGSIb3DQEBBQUAMGsxEzARBgNV\n"\
"BAMTCkV4YW1wbGUgQ0ExFTATBgNVBAgTDFBhbG8gQWx0byBDQTELMAkGA1UEBhMC\n"\
"VVMxHzAdBgkqhkiG9w0BCQEWEGxlbWtlQHZtd2FyZS5jb20xDzANBgNVBAoTBlZN\n"\
"d2FyZTAeFw0xMTA4MTAyMzE0NDlaFw0xMTA5MDkyMzE0NDlaMGsxEzARBgNVBAMT\n"\
"CkV4YW1wbGUgQ0ExFTATBgNVBAgTDFBhbG8gQWx0byBDQTELMAkGA1UEBhMCVVMx\n"\
"HzAdBgkqhkiG9w0BCQEWEGxlbWtlQHZtd2FyZS5jb20xDzANBgNVBAoTBlZNd2Fy\n"\
"ZTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAKEzJaO0nna1+tIwof8F\n"\
"p40EVMJJ30WSiNrdqzG9CiuEacDgFt0XpRR3uxIZao6OVAA/OdykQSFp0pOxD3dW\n"\
"jPqTJ4CUkqD71ensyB2nObSsV9GwlvP/MfYMcMHFsv1hguQBOuXken+TYJhCYW/9\n"\
"z6NxLpWEH3akbBBuKhdph41+45VBV9kgncrG9zbdClPh4VExjETlggajlxczHwfa\n"\
"KPDy3UxfEwMF/BrA9LJdTihVqXxWCxqJohfF53KcUsgtusB4i5SP3i58JA+frn/p\n"\
"r65o9Cft+mdxdG/gmJJShQqgS16y9ejAj/yEEAKWOlTeuG2V8FWP+7f7SJswz+K3\n"\
"FJcCAwEAAaMQMA4wDAYDVR0TBAUwAwEB/zANBgkqhkiG9w0BAQUFAAOCAQEAAER2\n"\
"UoSFeq/klehDW0MJsv3Lt3yn+cPDrK1QeUQmbLA8xY1twGAMzzcyvObjLAs4Csys\n"\
"lMcqCaCF0LjDfnMNfIrnZpGb0SjmGS77POrXOOT79Qz5bjsy0ZEZbX7+HuqCwnlP\n"\
"WynYIzVU124dNpqkWHdRZ3faLY1IEsEsIkoyi/WDSsorV7Hqx8uAGVXFUn6CORM4\n"\
"XmLp59mIy+2zMNzI4ZXs4uoP7KJMu+eXzV7zcd0nZbLVJcXWk3jdo9qIeIR1rTNh\n"\
"qMcYenV6XyF5QGB5Tz7GpRVBwOcvaThvFYO5lar/quH+yQWOd4arq+EElwGWQSzu\n"\
"e4qBCuYxFN60Ajp1/w==\n"\
"-----END CERTIFICATE-----"

   global cert2
   cert2 = "-----BEGIN CERTIFICATE-----\n"\
"MIIDFTCCAf0CAQAwDQYJKoZIhvcNAQEEBQAwazETMBEGA1UEAxMKRXhhbXBsZSBD\n"\
"QTEVMBMGA1UECBMMUGFsbyBBbHRvIENBMQswCQYDVQQGEwJVUzEfMB0GCSqGSIb3\n"\
"DQEJARYQbGVta2VAdm13YXJlLmNvbTEPMA0GA1UEChMGVk13YXJlMB4XDTExMDgx\n"\
"MDIzMjQxMVoXDTIxMDgwNzIzMjQxMVowNjETMBEGA1UEAxMKRXhhbXBsZSBDQTEf\n"\
"MB0GCSqGSIb3DQEJARYQbGVta2VAdm13YXJlLmNvbTCCASIwDQYJKoZIhvcNAQEB\n"\
"BQADggEPADCCAQoCggEBALtBcjmNWqhQfe65jU83Jn1SSBdOjsIJsYhIMEpxwNck\n"\
"5/31F5UytHFxXrKEaL4J6wg2Xg21cwAk6sFlulavGN8sbRBiOCnmoMEvD9XuI/1z\n"\
"gOKNhXUIIO3woYam1CoubdbVmEvW+zdNTaDKKHnabnS6AFAYB+FcCdwrB8JTAyQl\n"\
"GtjdKbcHOvvla+SyYBwXECRjnPlSxrX9W2FmBSCtQO2cJDH5H++pZX7sSXiOtgir\n"\
"Ztf6ZYCK7w2GcL9p3mO/HCOPBZDc96/qmEv4WfeVP3cMcC11gqBsqvNw0tiWG9Vl\n"\
"HcCCwc5TadhelIEBBdwT8PNpg7CBgNxc9HDTzV9JczMCAwEAATANBgkqhkiG9w0B\n"\
"AQQFAAOCAQEAkNGcdjkpkGK9h1LN847qWex705W5eXa3TWqiSgGNBHff8HlqMLUe\n"\
"gu5WVcMp/PlORjUg6FoBpeB3jcqmkg3VSEU745KXjxx9+W/NG8axaYwZit+wXZcl\n"\
"8JeW+Z9MTKcpXnO8rZPmF/Sq63kfNwmz8zYzZarnXWvtb04Mu+CeBRf4KcYQVq8F\n"\
"GzlB22kt54ZJwJsoFIy7VobGD45Z8GMa4tBTjlmPSpdI1jpcLYM2xd6eKrTw+myL\n"\
"NQRr9WThkZGs57Yb/Is82WfIhP2OGgXLc7GE9pqYFeD+R9lBNL1jHNGh6S79CLIH\n"\
"O1kJqdZCGymaF8+KxyToWjyXa2xfnSAijw==\n"\
"-----END CERTIFICATE-----"

   global cert3
   cert3 = "-----BEGIN CERTIFICATE-----\n"\
"MIIDGzCCAgMCAQIwDQYJKoZIhvcNAQEEBQAwazETMBEGA1UEAxMKRXhhbXBsZSBD\n"\
"QTEVMBMGA1UECBMMUGFsbyBBbHRvIENBMQswCQYDVQQGEwJVUzEfMB0GCSqGSIb3\n"\
"DQEJARYQbGVta2VAdm13YXJlLmNvbTEPMA0GA1UEChMGVk13YXJlMB4XDTExMDgx\n"\
"NjIxNDE0N1oXDTIxMDgxMzIxNDE0N1owPDENMAsGA1UECxMETGVhZjENMAsGA1UE\n"\
"AxMEbGVhZjEcMBoGCSqGSIb3DQEJARYNbGVhZkBsZWFmLmNvbTCCASIwDQYJKoZI\n"\
"hvcNAQEBBQADggEPADCCAQoCggEBALtBcjmNWqhQfe65jU83Jn1SSBdOjsIJsYhI\n"\
"MEpxwNck5/31F5UytHFxXrKEaL4J6wg2Xg21cwAk6sFlulavGN8sbRBiOCnmoMEv\n"\
"D9XuI/1zgOKNhXUIIO3woYam1CoubdbVmEvW+zdNTaDKKHnabnS6AFAYB+FcCdwr\n"\
"B8JTAyQlGtjdKbcHOvvla+SyYBwXECRjnPlSxrX9W2FmBSCtQO2cJDH5H++pZX7s\n"\
"SXiOtgirZtf6ZYCK7w2GcL9p3mO/HCOPBZDc96/qmEv4WfeVP3cMcC11gqBsqvNw\n"\
"0tiWG9VlHcCCwc5TadhelIEBBdwT8PNpg7CBgNxc9HDTzV9JczMCAwEAATANBgkq\n"\
"hkiG9w0BAQQFAAOCAQEACosVSdqywfWj+0/kOj/AjKtIKB/X7tgHDLAI8+4pda2s\n"\
"xjWjJNW12IFeTR26CJ9XNZdRUisQNInS0pHu+qT4Q6tyK5VGWxT4pqlkrtoTWaex\n"\
"QkcuVa+cHC8iaf5bBKZzFJ4WMiJV2E4dLS/nrQbMYAWKWLJAQiJWSEZ1YuysS3ji\n"\
"Rk+9LC65Sioz8e8pSaM2mkUgSIs+xVpwUHHgtqNIzjZsjr7tTbayO2YoZ2RoSRW3\n"\
"DhjqloAgn4t7EfllEqXirZXIgNksogDJY2ftexNX3MJEH7Qr3IZA0N6Ld1Ipt37p\n"\
"lyAZgwOet+CIcBDiN9dACzxgTXz7YQDuQSLl/JTsdQ==\n"\
"-----END CERTIFICATE-----"


def cleanMapFile():
   Log("Clearing mapfile")
   result = aliasMgr.ListMappedAliases(virtualMachine, guestAuth)

   for a in result:
      try:
         Log("Clearing cert %s" % a.base64Cert)
         aliasMgr.RemoveAliasByCert(virtualMachine, guestAuth, gUser, a.base64Cert)
      except Exception:
         pass

def cleanUserFile(user):
   Log("Clearing alias store for user %s" % user)
   result = aliasMgr.ListAliases(virtualMachine, guestAuth, user)

   for a in result:
      try:
         Log("Clearing cert %s" % a.base64Cert)
         aliasMgr.RemoveAliasByCert(virtualMachine, guestAuth, user, a.base64Cert)
      except Exception:
         pass

def addMappedAliases():
   Log("adding some mapped aliases for listing")
   nSubj = aliasDef.GuestAuthNamedSubject(name="subjectName")
   aInfo = aliasDef.GuestAuthAliasInfo(subject=nSubj, comment="This is a test comment")
   nSubj2 = aliasDef.GuestAuthNamedSubject(name="subjectName2")
   aInfo2 = aliasDef.GuestAuthAliasInfo(subject=nSubj2, comment="This is a test comment2")
   nSubj3 = aliasDef.GuestAuthAnySubject()
   aInfo3 = aliasDef.GuestAuthAliasInfo(subject=nSubj3, comment="This is a test comment3 for an ANY")

   result = aliasMgr.AddAlias(virtualMachine, guestAuth, gUser, True, caCert, aInfo)
   result = aliasMgr.AddAlias(virtualMachine, guestAuth, gUser, True, caCert, aInfo2)
   result = aliasMgr.AddAlias(virtualMachine, guestAuth, gUser, True, caCert, aInfo3)

   result = aliasMgr.AddAlias(virtualMachine, guestAuth, gUser, True, cert2, aInfo2)

def addUnmappedAliases():
   Log("adding some unmapped aliases for listing")
   nSubj = aliasDef.GuestAuthNamedSubject(name="unMappedSubjectName")
   aInfo = aliasDef.GuestAuthAliasInfo(subject=nSubj, comment="This is a unmapped test comment")
   nSubj2 = aliasDef.GuestAuthNamedSubject(name="unMappedSubjectName2")
   aInfo2 = aliasDef.GuestAuthAliasInfo(subject=nSubj2, comment="This is a unmapped test comment2")
   nSubj3 = aliasDef.GuestAuthAnySubject()
   aInfo3 = aliasDef.GuestAuthAliasInfo(subject=nSubj3, comment="This is a unmapped test comment3 for an ANY")

   result = aliasMgr.AddAlias(virtualMachine, guestAuth, gUser, False, caCert, aInfo)
   result = aliasMgr.AddAlias(virtualMachine, guestAuth, gUser, False, caCert, aInfo2)
   result = aliasMgr.AddAlias(virtualMachine, guestAuth, gUser, False, caCert, aInfo3)

   result = aliasMgr.AddAlias(virtualMachine, guestAuth, gUser, False, cert2, aInfo2)

def addAlias():
   Log("Adding a basic alias")
   nSubj = aliasDef.GuestAuthNamedSubject(name="subjectName")
   aInfo = aliasDef.GuestAuthAliasInfo(subject=nSubj, comment="This is a test comment")
   result = aliasMgr.AddAlias(virtualMachine, guestAuth, gUser, True, caCert, aInfo)

def removeAlias():
   Log("Adding and removing a basic alias")
   nSubj = aliasDef.GuestAuthNamedSubject(name="removeSubject")
   aInfo = aliasDef.GuestAuthAliasInfo(subject=nSubj, comment="This is a test comment for remove")
   result = aliasMgr.AddAlias(virtualMachine, guestAuth, gUser, True, caCert, aInfo)
   result = aliasMgr.RemoveAlias(virtualMachine, guestAuth, gUser, caCert, nSubj)

def removeAll():
   Log("Adding 2 aliases and removing by cert")
   nSubj = aliasDef.GuestAuthNamedSubject(name="removeAllSubject")
   nSubj2 = aliasDef.GuestAuthNamedSubject(name="removeAllSubject2")
   aInfo = aliasDef.GuestAuthAliasInfo(subject=nSubj, comment="This is a test comment for removeAll")
   aInfo2 = aliasDef.GuestAuthAliasInfo(subject=nSubj2, comment="This is a test comment for removeAll")
   result = aliasMgr.AddAlias(virtualMachine, guestAuth, gUser, True, caCert, aInfo)
   result = aliasMgr.AddAlias(virtualMachine, guestAuth, gUser, True, caCert, aInfo2)
   result = aliasMgr.RemoveAliasByCert(virtualMachine, guestAuth, gUser, caCert)

def listMapped():
   Log("ListMapped test")
   cleanMapFile()
   addMappedAliases()
   result = aliasMgr.ListMappedAliases(virtualMachine, guestAuth)
   Log("All mapped aliases: %s" % result)
   cleanMapFile()

def listAliases():
   Log("List test for user %s" % gUser)
   cleanUserFile(gUser)
   addUnmappedAliases()
   result = aliasMgr.ListAliases(virtualMachine, guestAuth, gUser)
   Log("Aliases for user %s" % gUser)
   Log("Result %s" % result)
   cleanUserFile(gUser)

def negTests():
   Log("Some negative test cases")

   nSubj = aliasDef.GuestAuthNamedSubject(name="subjectName")
   aInfo = aliasDef.GuestAuthAliasInfo(subject=nSubj, comment="This is a test comment")
   result = aliasMgr.AddAlias(virtualMachine, guestAuth, gUser, True, caCert, aInfo)

   try:
      # second try should fail w/ MultipleMappings fault
      result = aliasMgr.AddAlias(virtualMachine, guestAuth, gUser, True, caCert, aInfo)
   except Vim.Fault.GuestMultipleMappings as il:
      Log("Got the expected multiple mapping fault")


def main():

   # Process command line
   options = get_options()

   global svcInst
   global virtualMachine
   global guestAdminAuth
   global guestAuth
   global guestAuthBad
   [svcInst, virtualMachine, guestAdminAuth,
    guestAuth, guestAuthBad] = init(options.host, options.user, options.password,
                                    options.vmname, options.vmxpath, options.guestuser,
                                    options.guestpassword, options.guestrootuser,
                                    options.guestrootpassword)

   init_certs()

   # get the processManager object
   global procMgr
   procMgr = svcInst.content.guestOperationsManager.processManager

   # get the AliasManager object
   global aliasMgr
   aliasMgr = svcInst.content.guestOperationsManager.aliasManager
   global aliasDef
   aliasDef = Vim.Vm.Guest.AliasManager

   # use the cmdline username for the vgauth API tests
   global gUser
   gUser=options.guestuser

   testNotReady(procMgr, virtualMachine, guestAuth)
   waitForTools(virtualMachine)

   cleanMapFile()
   cleanUserFile(gUser)
   addAlias()
   removeAlias()
   removeAll()
   negTests()
   listMapped()
   listAliases()

   cleanMapFile()
   cleanUserFile(gUser)


# Start program
if __name__ == "__main__":
   main()
   Log("AliasMgr tests completed")
