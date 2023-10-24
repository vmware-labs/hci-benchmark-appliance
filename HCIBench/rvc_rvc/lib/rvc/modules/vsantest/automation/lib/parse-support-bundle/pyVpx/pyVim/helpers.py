## @file helpers.py
## @brief Miscellaneous helper functions
##
## Detailed description (for Doxygen goes here)
"""
Miscellaneous helper functions

Detailed description (for [e]pydoc goes here)
"""
import os
import os.path
import datetime
import re
import subprocess


def Log(msg):
    """
    Prints a formatted log message to stdout.

    @type  msg   : str
    @param msg   : Message to log
    @rtype       : None
    """

    print("[ " + str(datetime.datetime.now()) + " ]" + msg)


##
## @brief Measures elapsed time between two points.
##
class StopWatch:
    """ Measures elapsed time between two points. """
    def __init__(self):
        self.start = datetime.datetime.now()

    def finish(self, msg):
        self.end = datetime.datetime.now()
        self.timeTaken = self.end - self.start
        Log("Time taken for " + msg + " : " + str(self.timeTaken))


def RunCmd(command):
    """ Function to run commands on host. """
    returncode = 0
    std_out = ''

    try:
        std_out = subprocess.check_output(command,
                                          stderr=subprocess.STDOUT,
                                          shell=True)
    except subprocess.CalledProcessError as ex:
        returncode = ex.returncode

    if type(std_out) is str:
        return (std_out, returncode)
    else:
        return (std_out.decode("utf-8"), returncode)


def GetDatastorePath():
    """ Function that returns path to a VMFS datastore. """
    dataStore, rc = RunCmd(
        "esxcli storage vmfs extent list | head -3 | tail -1" +
        "| awk -F '  +' '{print $1}'")

    if rc != 0:
        destDir = None
    else:
        destDir = "\'" + '/vmfs/volumes/' + dataStore.strip() + "\'"

    return destDir


def AddEscapeCharactersToPath(path):
    """ Function to add escape sequences for special characters in path string. """
    return path.replace("(", "\\(").replace(" ", "\\ ").replace(")", "\\)")


def IsEncryptedCoredump(path):
    """ Function to find if the coredump is encrypted or not. """
    if not os.path.exists('/bin/vmkdump_extract'):
        raise Exception('vmkdump_extract not present.')

    result, rc = RunCmd("/bin/vmkdump_extract -E {0}".format(path))

    if rc != 0:
        raise Exception(
            'RunCmd failed when trying to check for encrypted coredump')

    return result.strip() == "YES"


def DecryptCoredump(path, tempDir):
    """
    Function to decrypt an encrypted core dump. The decrypted coredump is
    stored in the temporary directory passed to it.
    """
    destinationPath = '{0}/zdump-decrypted'.format(tempDir)
    _, rc = RunCmd('crypto-util envelope extract --offset 4096 {0} {1}'.format(
        path, destinationPath))

    if rc != 0:
        raise Exception(
            'RunCmd failed when trying to decrypt an encrypted coredump.')

    return destinationPath


class MemoryLeakChecker:
    def __init__(self):
        self.ah64Result = ''
        self.resultDirectory = ''

    def HasMemoryLeak(self, processName, removePrevTempDir=False):
        """ Function to check if there is a memory leak in binary. """
        vmkdumpExtractPath = '/build/apps/bin/esx/vmkdump_extract_wrapper.py'

        if not os.path.exists(vmkdumpExtractPath):
            raise Exception(
                'vmkdump_extract_wrapper.py not present. Mount build directory.'
            )

        destDir = GetDatastorePath()
        if destDir is None:
            raise Exception('Failed to get datastore path')

        processNameEscaped = AddEscapeCharactersToPath(processName)
        if removePrevTempDir:
            _, rc = RunCmd('rm -rf {0}/{1}Leak*'.format(
                destDir, processNameEscaped))
            if rc != 0:
                raise Exception(
                    'Could not clear previous {0}Leak temp directories.'.
                    format(processNameEscaped))

        # Create temp directory #
        tempDirUnstripped, rc = RunCmd('mktemp -d {0}/{1}LeakXXXXXX'.format(
            destDir, processNameEscaped))
        if rc != 0:
            raise Exception('Could not create temporary directory. ')

        tempDir = AddEscapeCharactersToPath(tempDirUnstripped.strip())
        # Download ah64 binary #
        ah64Url = 'http://engweb.eng.vmware.com/~tim/ah64'
        _, rc = RunCmd('wget {0} -O {1}/ah64'.format(ah64Url, tempDir))
        if rc != 0:
            raise Exception('Could not download ah64.')

        # Generate live core. A zdump file will be generated. #
        out, rc = RunCmd('vmkbacktrace -n {0} -w'.format(processNameEscaped))
        if rc != 0:
            raise Exception('Could not generate live core.')
        zdumpStripped = out.strip().split(",")[-1]

        # Decrypt if zdump is encrypted #
        zdump = ""
        try:
            if IsEncryptedCoredump(zdumpStripped):
                zdump = DecryptCoredump(zdumpStripped, tempDir)
            else:
                zdump = zdumpStripped
        except Exception as ex:
            raise

        # Extract  #
        elfCore = "\'" + '{0}/test-{1}.elf'.format(tempDir,
                                                   processNameEscaped) + "\'"
        _, rc = RunCmd('{0} -X {1} {2}'.format(vmkdumpExtractPath, elfCore,
                                               zdump))
        if rc != 0:
            raise Exception('Failed to extract elf core.')

        # Find if there are any memory chunks leaked #
        out, rc = RunCmd(
            'cd {0} && chmod +x ./ah64 && echo "show leaked" | ./ah64 test-{1}.elf'
            .format(tempDir, processNameEscaped))
        if rc != 0:
            raise Exception('ah64 failed to run.')

        pattern = re.compile(
            r'([0-9,]+) chunks take 0x[0-9a-hA-H]+ \([0-9,]+\) bytes\.')
        match = pattern.search(out)

        if match is not None:
            leakedChunks = int(match.group(1))
            self.ah64Result = out
            self.resultDirectory = tempDir
            return leakedChunks

        raise Exception('Could not find the requested pattern.')

    def GetMemleakCheckOutput(self):
        return self.ah64Result

    def GetMemleakCheckDirectory(self):
        return self.resultDirectory
