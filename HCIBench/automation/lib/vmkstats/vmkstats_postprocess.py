"""VMKstats Parser"""
import argparse
import json
import os
import subprocess
import re

from vmkflames import VmkstatsFlames

_JAVA = "java"
_ROOT_MAP = {
    "LSOMLLOG": "VSANServerMainLoop",
    "PLOG": "VSANServerMainLoop",
}
_FLAMEGRAPH_PL = "flamegraph.pl"


class VmkstatsParser(object):
    """VMKstats output parser"""

    def __init__(self, outputDir, java, jar):
        """Initialize the vmkstats parser object"""
        self._odir = outputDir
        self._java = java
        self._jar = jar
        self._parse_cmd = " ".join(
            [self._java, "-jar", self._jar, "--text", "-tag", "k"]
        )
        self._flamegraph_cmd = " "
        os.chdir(self._odir)

    def updateOdir(self, odir):
        """Update the output dir"""
        self._odir = odir

    def parse(
        self,
        ctx,
        rootAt=None,
        cpuids=None,
        caller=True,
        maxDepth=None,
        percent=False,
    ):
        """Parse the vmkstats"""
        cmd = self._parse_cmd
        oFileName = ctx
        if rootAt:
            cmd += " --rootAt %s" % (rootAt)

        if caller:
            cmd += " --caller"
            oFileName += "_caller"
        else:
            cmd += " --callee"
            oFileName += "_callee"

        if maxDepth:
            cmd += " --maxdepth %d" % (maxDepth)
            oFileName += "_depth%d" % (maxDepth)

        if percent:
            oFileName += "_percent"
        else:
            cmd += " --samples"

        if cpuids:
            cmd += " --world %s" % (",".join(cpuids))
        oFileName = oFileName.lstrip("_")
        oFileName += ".txt"
        eFileName = oFileName + ".err"
        oFilePath = os.path.join(self._odir, oFileName)
        eFilePath = os.path.join(self._odir, eFileName)
        #print(cmd)
        openf = open(oFilePath, "w")
        opene = open(eFilePath, "w")
        try:
            subprocess.call(cmd, stdout=openf, stderr=opene, cwd=self._odir, shell=True)
            #Execute(cmd, wait=True, cwd=self._odir, ofName=oFilePath)
            self.demangle_funcnames(oFilePath)
        except:
            print(cmd + " Falied!")
            # Continue even if processing for one of the layers fails
            pass

    @staticmethod
    def demangle_funcnames(filepath):
        """Demangle C++ function names"""
        try:
            # Might not be available on all hosts
            import cxxfilt
        except:
            return

        processed_file = []
        file_modified = False
        with open(filepath) as fh:
            for line in fh:
                line = line.strip()
                try:
                    match = re.match(
                        r"(?P<prefix>.*) (?P<funcname>.*) (?P<fsamples>.*)",
                        line,
                    ).groupdict()
                    match["funcname"] = cxxfilt.demangle(
                        match["funcname"], external_only=False
                    )
                    processed_file.append(
                        " ".join(
                            [
                                match["prefix"],
                                match["funcname"],
                                match["fsamples"],
                            ]
                        )
                    )
                    file_modified = True
                except:
                    processed_file.append(line)

        if file_modified:
            with open(filepath, "w") as fh:
                fh.write("\n".join(processed_file))

    def generateFlamegraph(self, vsanworldsfile, scriptDir):
        """
        Generate flamegraphs for the ctx with cpuids

        :param vsanworldsfile: vsanworlds.json file
        :param scriptDir: Perfcloud directory
        """
        flamesObj = VmkstatsFlames(self._odir, vsanworldsfile)
        outputFiles = flamesObj.processStats()
        os.mkdir(os.path.join(self._odir, "flFiles"))
        for outputFile in outputFiles:
            if os.stat(outputFile).st_size:
                outputSVG = outputFile.replace(".fl", ".svg")
                cmd = "%s --minwidth 0 %s" % (
                    os.path.join(scriptDir, _FLAMEGRAPH_PL),
                    outputFile,
                )
                print(cmd)
                f = open(outputSVG, "w")
                subprocess.call(cmd, stdout=f, shell=True)
                #Execute(cmd, wait=True, ofName=outputSVG)
                cmd = "mv %s %s" % (
                    outputFile,
                    os.path.join(self._odir, "flFiles"),
                )
                subprocess.call(cmd,shell=True)
                #Execute(cmd, wait=True)


def main():
    """Main function"""
    args = argparse.ArgumentParser()
    args.add_argument(
        "--outputdir", "-o", action="store", help="vmkstats output directory"
    )
    args.add_argument(
        "--scriptdir",
        action="store",
        default=None,
        help="perfcloud directory path",
    )
    args.add_argument(
        "--flamegraph", action="store_true", help="Generate flamegraphs",
    )
    args.add_argument(
        "--java", action="store", default=_JAVA, help="java path"
    )
    args.add_argument(
        "--jar", action="store", help="vmcallstackview.jar file path"
    )
    opts = args.parse_args()

    parser = VmkstatsParser(opts.outputdir, opts.java, opts.jar)

    # Generate global caller/callee files
    parser.parse(ctx="")
    parser.parse(ctx="", percent=True)
    parser.parse(ctx="", caller=False)
    parser.parse(ctx="", caller=False, percent=True)
    parser.parse(ctx="", caller=False, maxDepth=1)

    # Module wise parsing
    vsanworldsfile = os.path.join(opts.outputdir, "vsanworlds.json")
    modWorlds = json.load(open(vsanworldsfile))
    for mod in sorted(modWorlds, key=lambda k: len(modWorlds[k])):
        root = _ROOT_MAP.get(mod)
        parser.parse(mod, rootAt=root, cpuids=modWorlds[mod])
        parser.parse(mod, rootAt=root, cpuids=modWorlds[mod], percent=True)

    if opts.scriptdir and opts.flamegraph:
        parser.generateFlamegraph(vsanworldsfile, opts.scriptdir)

    # Delete zero size files
    cmd = "find %s -type f -empty -delete" % (opts.outputdir)
    subprocess.call(cmd,shell=True)
    #Execute(cmd, wait=True)


if __name__ == "__main__":
    main()
