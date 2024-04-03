# Copyright 2009, Peter A. Bigot
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain a
# copy of the License at:
#
#            http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Classes and global objects related to archiving U{XML
Namespaces<http://www.w3.org/TR/2006/REC-xml-names-20060816/index.html>}."""

import pyxb
import os
import fnmatch
import pyxb.utils.utility
import utility

PathEnvironmentVariable = 'PYXB_ARCHIVE_PATH'
"""Environment variable from which default path to pre-loaded namespaces is
read.  The value should be a colon-separated list of absolute paths.  The
character C{&} at the start of a member of the list is replaced by the path to
the directory where the %{pyxb} modules are found, including a trailing C{/}.
For example, use C{&pyxb/bundles//} to enable search of any archive bundled
with PyXB.

@note: If you put a path separater between C{&} and the following path, this
will cause the substitution to be ignored."""

import os.path
import stat

DefaultArchivePrefix = os.path.realpath(os.path.join(os.path.dirname( __file__), '../..'))
"""The default archive prefix, substituted for C{&} in C{PYXB_ARCHIVE_PATH}."""

def GetArchivePath ():
    """Return the archive path as defined by the L{PathEnvironmentVariable},
    or C{None} if that variable is not defined."""
    import os
    return os.environ.get(PathEnvironmentVariable)

# Stuff required for pickling
import cPickle as pickle
#import pyxb.utils.pickle_trace as pickle

import re

class NamespaceArchive (object):
    """Represent a file from which one or more namespaces can be read, or to
    which they will be written."""

    # A code used to identify the format of the archive, so we don't
    # mis-interpret its contents.
    # YYYYMMDDHHMM
    __PickleFormat = '200907190858'

    @classmethod
    def _AnonymousCategory (cls):
        """The category name to use when storing references to anonymous type
        definitions.  For example, attribute definitions defined within an
        attribute use in a model group definition.that can be referenced frojm
        ax different namespace."""
        return cls.__AnonymousCategory
    __AnonymousCategory = '_anonymousTypeDefinition'

    @classmethod
    def PicklingArchive (cls):
        """Return a reference to a set specifying the namespace instances that
        are being archived.

        This is needed to determine whether a component must be serialized as
        aa reference."""
        # NB: Use root class explicitly.  If we use cls, when this is invoked
        # by subclasses it gets mangled using the subclass name so the one
        # defined in this class is not found
        return NamespaceArchive.__PicklingArchive
    # Class variable recording the namespace that is currently being
    # pickled.  Used to prevent storing components that belong to
    # other namespaces.  Should be None unless within an invocation of
    # SaveToFile.
    __PicklingArchive = None

    __NamespaceArchives = None
    """A mapping from generation UID to NamespaceArchive instances."""

    def discard (self):
        """Remove this archive from the set of available archives.

        This is invoked when an archive contains a namespace that the user has
        specified should not be loaded."""
        del self.__NamespaceArchives[self.generationUID()]
        for ns in self.__namespaces:
            ns._removeArchive(self)

    @classmethod
    def __GetArchiveInstance (cls, archive_file, stage=None):
        """Return a L{NamespaceArchive} instance associated with the given file.

        To the extent possible, the same file accessed through different paths
        returns the same L{NamespaceArchive} instance.
        """
        
        nsa = NamespaceArchive(archive_path=archive_file, stage=cls._STAGE_uid)
        rv = cls.__NamespaceArchives.get(nsa.generationUID(), nsa)
        if rv == nsa:
            cls.__NamespaceArchives[rv.generationUID()] = rv
        rv._readToStage(stage)
        return rv

    __ArchivePattern_re = re.compile('\.wxs$')

    @classmethod
    def PreLoadArchives (cls, archive_path=None, required_archive_files=None, reset=False):
        """Scan for available archives, associating them with namespaces.

        This only validates potential archive contents; it does not load
        namespace data from the archives.  If invoked with no arguments, 

        @keyword archive_path: A colon-separated list of files or directories in
        which namespace archives can be found; see L{PathEnvironmentVariable}.
        Defaults to L{GetArchivePath()}.  If not defaulted, C{reset} will be
        forced to C{True}.  For any directory in the path, all files ending with
        C{.wxs} are examined.

        @keyword required_archive_files: A list of paths to files that must
        resolve to valid namespace archives.

        @keyword reset: If C{False} (default), the most recently read set of
        archives is returned; if C{True}, the archive path is re-scanned and the
        namespace associations validated.

        @return: A list of L{NamespaceArchive} instances corresponding to the
        members of C{required_archive_files}, in order.  If
        C{required_archive_files} was not provided, returns an empty list.

        @raise pickle.UnpicklingError: a C{required_archive_files} member does not
        contain a valid namespace archive.
        """
        
        import builtin
        
        reset = reset or (archive_path is not None) or (required_archive_files is not None) or (cls.__NamespaceArchives is None)
        required_archives = []
        if reset:
            # Get a list of pre-existing archives, initializing the map if
            # this is the first time through.
            if cls.__NamespaceArchives is None:
                cls.__NamespaceArchives = { }
            existing_archives = set(cls.__NamespaceArchives.values())
            archive_set = set(required_archives)

            # Get archives for all required files
            if required_archive_files is not None:
                for afn in required_archive_files:
                    required_archives.append(cls.__GetArchiveInstance(afn, stage=cls._STAGE_readModules))

            # Ensure we have an archive path.  If not, don't do anything.
            if archive_path is None:
                archive_path = GetArchivePath()
            if archive_path is not None:
    
                # Get archive instances for everything in the archive path
                candidate_files = pyxb.utils.utility.GetMatchingFiles(archive_path, cls.__ArchivePattern_re, prefix_pattern='&', prefix_substituend=DefaultArchivePrefix)
                for afn in candidate_files:
                    #print 'Considering %s' % (afn,)
                    try:
                        nsa = cls.__GetArchiveInstance(afn, stage=cls._STAGE_readModules)
                        archive_set.add(nsa)
                    except pickle.UnpicklingError, e:
                        print 'Cannot use archive %s: %s' % (afn, e)
                    except pyxb.NamespaceArchiveError, e:
                        print 'Cannot use archive %s: %s' % (afn, e)
                
                # Do this for two reasons: first, to get an iterable that won't
                # cause problems when we remove unresolvable archives from
                # archive_set; and second to aid with forced dependency inversion
                # testing
                ordered_archives = sorted(list(archive_set), lambda _a,_b: cmp(_a.archivePath(), _b.archivePath()))
                ordered_archives.reverse()
    
                # Create a graph that identifies dependencies between the archives
                archive_map = { }
                for a in archive_set:
                    archive_map[a.generationUID()] = a
                archive_graph = pyxb.utils.utility.Graph()
                for a in ordered_archives:
                    prereqs = a._unsatisfiedModulePrerequisites()
                    if 0 < len(prereqs):
                        for p in prereqs:
                            if builtin.BuiltInObjectUID == p:
                                continue
                            da = archive_map.get(p)
                            if da is None:
                                print 'WARNING: %s depends on unavailable archive %s' % (a, p)
                                archive_set.remove(a)
                            else:
                                #print '%s depends on %s' % (a, da)
                                archive_graph.addEdge(a, da)
                    else:
                        #print '%s has no dependencies' % (a,)
                        archive_graph.addRoot(a)
    
                # Verify that there are no dependency loops.
                archive_scc = archive_graph.sccOrder()
                for scc in archive_scc:
                    if 1 < len(scc):
                        raise pyxb.LogicError("Cycle in archive dependencies.  How'd you do that?\n  " + "\n  ".join([ _a.archivePath() for _a in scc ]))
                    archive = scc[0]
                    if not (archive in archive_set):
                        #print 'Discarding unresolvable %s' % (archive,)
                        archive.discard()
                        existing_archives.remove(archive)
                        continue
                    #print 'Completing load of %s' % (archive,)
                    #archive._readToStage(cls._STAGE_COMPLETE)

            # Discard any archives that we used to know about but now aren't
            # supposed to.  @todo make this friendlier in the case of archives
            # we've already incorporated.
            for archive in existing_archives.difference(archive_set):
                print 'Discarding excluded archive %s' % (archive,)
                archive.discard()

        return required_archives

    def archivePath (self):
        """Path to the file in which this namespace archive is stored."""
        return self.__archivePath
    __archivePath = None

    def generationUID (self):
        """The unique identifier for the generation that produced this archive."""
        return self.__generationUID
    __generationUID = None

    def isLoadable (self):
        """Return C{True} iff it is permissible to load the archive.
        Archives created for output cannot be loaded."""
        return self.__isLoadable
    __isLoadable = None

    def __locateModuleRecords (self):
        self.__moduleRecords = set()
        namespaces = set()
        for ns in pyxb.namespace.utility.AvailableNamespaces():
            # @todo allow these; right now it's usually the XML
            # namespace and we're not prepared to reconcile
            # redefinitions of those components.
            if ns.isUndeclaredNamespace():
                continue
            mr = ns.lookupModuleRecordByUID(self.generationUID())
            if mr is not None:
                namespaces.add(ns)
                mr.prepareForArchive(self)
                self.__moduleRecords.add(mr)
        self.__namespaces.update(namespaces)
    def moduleRecords (self):
        """Return the set of L{module records <ModuleRecord>} stored in this
        archive.

        Each module record represents"""
        return self.__moduleRecords
    __moduleRecords = None
                
    @classmethod
    def ForPath (cls, archive_file):
        """Return the L{NamespaceArchive} instance that can be found at the
        given path."""
        return cls.__GetArchiveInstance(archive_file)

    # States in the finite automaton that is used to read archive contents.
    _STAGE_UNOPENED = 0         # Haven't even checked for existence
    _STAGE_uid = 1              # Verified archive exists, obtained generation UID from it
    _STAGE_readModules = 2      # Read module records from archive, which includes UID dependences
    _STAGE_validateModules = 3  # Verified pre-requisites for module loading
    _STAGE_readComponents = 4   # Extracted components from archive and integrated into namespaces
    _STAGE_COMPLETE = _STAGE_readComponents

    def _stage (self):
        return self.__stage
    __stage = None

    def __init__ (self, archive_path=None, generation_uid=None, loadable=True, stage=None):
        """Create a new namespace archive.

        If C{namespaces} is given, this is an output archive.

        If C{namespaces} is absent, this is an input archive.

        @raise IOError: error attempting to read the archive file
        @raise pickle.UnpicklingError: something is wrong with the format of the library
        """
        self.__namespaces = set()
        if generation_uid is not None:
            if archive_path:
                raise pyxb.LogicError('NamespaceArchive: cannot define both namespaces and archive_path')
            self.__generationUID = generation_uid
            self.__locateModuleRecords()
        elif archive_path is not None:
            if generation_uid is not None:
                raise pyxb.LogicError('NamespaceArchive: cannot provide generation_uid with archive_path')
            self.__archivePath = archive_path
            self.__stage = self._STAGE_UNOPENED
            self.__isLoadable = loadable
            if self.__isLoadable:
                if stage is None:
                    stage = self._STAGE_moduleRecords
                self._readToStage(stage)
        else:
            pass

    def add (self, namespace):
        """Add the given namespace to the set that is to be stored in this archive."""
        if namespace.isAbsentNamespace():
            raise pyxb.NamespaceArchiveError('Cannot archive absent namespace')
        self.__namespaces.add(namespace)

    def update (self, namespace_set):
        """Add the given namespaces to the set that is to be stored in this archive."""
        [ self.add(_ns) for _ns in namespace_set ]

    def namespaces (self):
        """Set of namespaces that can be read from this archive."""
        return self.__namespaces
    __namespaces = None

    def __createPickler (self, output):
        # @todo: support StringIO instances?
        if not isinstance(output, file):
            output = open(output, 'wb')
        pickler = pickle.Pickler(output, -1)
    
        # The format of the archive
        pickler.dump(NamespaceArchive.__PickleFormat)
    
        # The UID for the set
        assert self.generationUID() is not None
        pickler.dump(self.generationUID())

        return pickler

    def __createUnpickler (self):
        unpickler = pickle.Unpickler(open(self.__archivePath, 'rb'))

        format = unpickler.load()
        if self.__PickleFormat != format:
            raise pyxb.NamespaceArchiveError('Archive format is %s, require %s' % (format, self.__PickleFormat))

        self.__generationUID = unpickler.load()

        return unpickler

    def __readModules (self, unpickler):
        #print 'RM %x %s' % (id(self), self)
        mrs = unpickler.load()
        assert isinstance(mrs, set), 'Expected set got %s from %s' % (type(mrs), self.archivePath())
        if self.__moduleRecords is None:
            for mr in mrs.copy():
                mr2 = mr.namespace().lookupModuleRecordByUID(mr.generationUID())
                if mr2 is not None:
                    mr2._setFromOther(mr, self)
                    #print 'Replaced locally defined %s with archive data' % (mr2,)
                    mrs.remove(mr)
            self.__moduleRecords = set()
            assert 0 == len(self.__namespaces)
            for mr in mrs:
                mr._setArchive(self)
                ns = mr.namespace()
                ns.addModuleRecord(mr)
                self.__namespaces.add(ns)
                self.__moduleRecords.add(mr)
        else:
            # Verify the archive still has what was in it when we created this.
            for mr in mrs:
                mr2 = mr.namespace().lookupModuleRecordByUID(mr.generationUID())
                if not (mr2 in self.__moduleRecords):
                    raise pyxb.NamespaceArchiveError('Lost module record %s %s from %s' % (mr.namespace(), mr.generationUID(), self.archivePath()))

    def _unsatisfiedModulePrerequisites (self):
        prereq_uids = set()
        for mr in self.__moduleRecords:
            ns = mr.namespace()
            #print 'Namespace %s records:' % (ns,)
            #for xmr in ns.moduleRecords():
            #    print ' %s' % (xmr,)
            prereq_uids.update(mr.dependsOnExternal())
        return prereq_uids

    def __validatePrerequisites (self, stage):
        import builtin
        prereq_uids = self._unsatisfiedModulePrerequisites()
        #print '%s depends on %d prerequisites' % (self, len(prereq_uids))
        for uid in prereq_uids:
            if builtin.BuiltInObjectUID == uid:
                continue
            depends_on = self.__NamespaceArchives.get(uid)
            if depends_on is None:
                raise pyxb.NamespaceArchiveError('%s: archive depends on unavailable archive %s' % (self.archivePath(), uid))
            #print '%s stage %s depends on %s at %s going to %s' % (self, self._stage(), depends_on, depends_on._stage(), stage)
            depends_on._readToStage(stage)

    def __validateModules (self):
        self.__validatePrerequisites(self._STAGE_validateModules)
        for mr in self.__moduleRecords:
            ns = mr.namespace()
            #print 'Namespace %s records:' % (ns,)
            #for xmr in ns.moduleRecords():
            #    print ' %s' % (xmr,)
            for base_uid in mr.dependsOnExternal():
                xmr = ns.lookupModuleRecordByUID(base_uid)
                if xmr is None:
                    raise pyxb.NamespaceArchiveError('Module %s depends on external module %s, not available in archive path' % (mr.generationUID(), base_uid))
                if not xmr.isIncorporated():
                    print 'Need to incorporate data from %s' % (xmr,)
                else:
                    print 'Have required base data %s' % (xmr,)

            for origin in mr.origins():
                #print 'mr %s origin %s' % (mr, origin)
                for (cat, names) in origin.categoryMembers().iteritems():
                    if not (cat in ns.categories()):
                        continue
                    cross_objects = names.intersection(ns.categoryMap(cat).keys())
                    if 0 < len(cross_objects):
                        raise pyxb.NamespaceArchiveError('Archive %s namespace %s module %s origin %s archive/active conflict on category %s: %s' % (self.__archivePath, ns, mr, origin, cat, " ".join(cross_objects)))
                    print '%s no conflicts on %d names' % (cat, len(names))

    def __readComponentSet (self, unpickler):
        self.__validatePrerequisites(self._STAGE_readComponents)
        print 'RCS %s' % (self,)
        for n in range(len(self.__moduleRecords)):
            ns = unpickler.load()
            mr = ns.lookupModuleRecordByUID(self.generationUID())
            assert mr in self.__moduleRecords
            assert not mr.isIncorporated()
            objects = unpickler.load()
            mr._loadCategoryObjects(objects)

    __unpickler = None
    def _readToStage (self, stage):
        if self.__stage is None:
            raise pyxb.NamespaceArchiveError('Attempt to read from invalid archive %s' % (self,))
        try:
            while self.__stage < stage:
                #print 'RTS %s want %s' % (self.__stage, stage)
                if self.__stage < self._STAGE_uid:
                    self.__unpickler = self.__createUnpickler()
                    self.__stage = self._STAGE_uid
                    continue
                if self.__stage < self._STAGE_readModules:
                    assert self.__unpickler is not None
                    self.__readModules(self.__unpickler)
                    self.__stage = self._STAGE_readModules
                    continue
                if self.__stage < self._STAGE_validateModules:
                    self.__validateModules()
                    self.__stage = self._STAGE_validateModules
                    continue
                if self.__stage < self._STAGE_readComponents:
                    assert self.__unpickler is not None
                    self.__stage = self._STAGE_readComponents
                    self.__readComponentSet(self.__unpickler)
                    self.__unpickler = None
                    continue
                raise pyxb.LogicError('Too many stages (at %s, want %s)' % (self.__stage, stage))
        except:
            self.__stage = None
            self.__unpickler = None
            raise

    def readNamespaces (self):
        """Read all the components from this archive, integrating them into
        their respective namespaces."""
        self._readToStage(self._STAGE_COMPLETE)

    def writeNamespaces (self, output):
        """Store the namespaces into the archive.

        @param output: An instance substitutable for a writable file, or the
        name of a file to write to.
        """
        import sys
        
        assert NamespaceArchive.__PicklingArchive is None
        NamespaceArchive.__PicklingArchive = self
        assert self.__moduleRecords is not None

        # Recalculate the record/object associations: we didn't assign
        # anonymous names to the indeterminate scope objects because they
        # weren't needed for bindings, but they are needed in the archive.
        for mr in self.__moduleRecords:
            mr.namespace()._associateOrigins(mr)

        try:
            # See http://bugs.python.org/issue3338
            recursion_limit = sys.getrecursionlimit()
            sys.setrecursionlimit(10 * recursion_limit)
    
            pickler = self.__createPickler(output)

            assert isinstance(self.__moduleRecords, set)
            print "\n".join([ str(_mr) for _mr in self.__moduleRecords ])
            pickler.dump(self.__moduleRecords)

            for mr in self.__moduleRecords:
                pickler.dump(mr.namespace())
                pickler.dump(mr.categoryObjects())
        finally:
            sys.setrecursionlimit(recursion_limit)
        NamespaceArchive.__PicklingArchive = None

    def __str__ (self):
        archive_path = self.__archivePath
        if archive_path is None:
            archive_path = '??'
        return 'NSArchive@%s' % (archive_path,)

class _ArchivableObject_mixin (pyxb.cscRoot):
    """Mix-in to any object that can be stored in a namespace within an archive."""
    
    # Need to set this per category item
    __objectOrigin = None
    def _objectOrigin (self):
        return self.__objectOrigin
    def _setObjectOrigin (self, object_origin, override=False):
        if (self.__objectOrigin is not None) and (not override):
            if  self.__objectOrigin != object_origin:
                raise pyxb.LogicError('Inconsistent origins for object %s: %s %s' % (self, self.__objectOrigin, object_origin))
        else:
            self.__objectOrigin = object_origin

    def _prepareForArchive (self, archive):
        #assert self.__objectOrigin is not None
        if self._objectOrigin() is not None:
            return getattr(super(_ArchivableObject_mixin, self), '_prepareForArchive_csc', lambda *_args,**_kw: self)(self._objectOrigin().moduleRecord())
        assert not isinstance(self, pyxb.xmlschema.structures._NamedComponent_mixin)

    def _updateFromOther_csc (self, other):
        return getattr(super(_ArchivableObject_mixin, self), '_updateFromOther_csc', lambda *_args,**_kw: self)(other)

    def _updateFromOther (self, other):
        """Update this instance with additional information provided by the other instance.

        This is used, for example, when a built-in type is already registered
        in the namespace, but we've processed the corresponding schema and
        have obtained more details."""
        assert self != other
        return self._updateFromOther_csc(other)

    def _allowUpdateFromOther (self, other):
        import builtin
        assert self._objectOrigin()
        return builtin.BuiltInObjectUID == self._objectOrigin().generationUID()

class _NamespaceArchivable_mixin (pyxb.cscRoot):
    """Encapsulate the operations and data relevant to archiving namespaces.

    This class mixes-in to L{pyxb.namespace.Namespace}"""

    def _reset (self):
        """CSC extension to reset fields of a Namespace.

        This one handles category-related data."""
        getattr(super(_NamespaceArchivable_mixin, self), '_reset', lambda *args, **kw: None)()
        self.__loadedFromArchive = None
        self.__wroteToArchive = None
        self.__active = False
        self.__moduleRecordMap = {}

    def _loadedFromArchive (self):
        return self.__loadedFromArchive
    
    __wroteToArchive = None
    __loadedFromArchive = None

    def isActive (self, empty_inactive=False):
        if self.__isActive and empty_inactive:
            for (ct, cm) in self._categoryMap().items():
                if 0 < len(cm):
                    print '%s: %d %s -- activated' % (self, len(cm), ct)
                    return True
            return False
        return self.__isActive

    def _activate (self):
        #if not self.__isActive:
        #    print 'Activating %s' % (self,)
        self.__isActive = True
    __isActive = None

    def __init__ (self, *args, **kw):
        super(_NamespaceArchivable_mixin, self).__init__(*args, **kw)
        
    def _setLoadedFromArchive (self, archive):
        self.__loadedFromArchive = archive
        self._activate()
    def _setWroteToArchive (self, archive):
        self.__wroteToArchive = archive

    def _removeArchive (self, archive):
        # Yes, I do want this to raise KeyError if the archive is not present
        mr = self.__moduleRecordMap[archive.generationUID()]
        assert not mr.isIncorporated(), 'Removing archive %s after incorporation' % (archive.archivePath(),)
        # print 'removing %s' % (mr,)
        del self.__moduleRecordMap[archive.generationUID()]
        
    def isLoadable (self):
        """Return C{True} iff the component model for this namespace can be
        loaded from a namespace archive."""
        for mr in self.moduleRecords():
            if mr.isLoadable():
                return True
        return False

    def loadableFrom (self):
        """Return the list of archives from which components for this
        namespace can be loaded."""
        rv = []
        for mr in self.moduleRecords():
            if mr.isLoadable():
                rv.append(mr.archive())
        return rv

    def moduleRecords (self):
        return self.__moduleRecordMap.values()
    __moduleRecordMap = None

    def addModuleRecord (self, module_record):
        assert isinstance(module_record, ModuleRecord)
        # This assertion will fail if the binding is loaded before its archive
        # is scanned.
        assert not (module_record.generationUID() in self.__moduleRecordMap)
        self.__moduleRecordMap[module_record.generationUID()] = module_record
        return module_record
    def lookupModuleRecordByUID (self, generation_uid, create_if_missing=False, *args, **kw):
        rv = self.__moduleRecordMap.get(generation_uid)
        if (rv is None) and create_if_missing:
            rv = self.addModuleRecord(ModuleRecord(self, generation_uid, *args, **kw))
        return rv

    def _setState_csc (self, kw):
        #assert not self.__isActive, 'ERROR: State set for active namespace %s' % (self,)
        return getattr(super(_NamespaceArchivable_mixin, self), '_getState_csc', lambda _kw: _kw)(kw)
    
    def markNotLoadable (self):
        """Prevent loading this namespace from an archive.

        This marks all archives in which the namespace appears, whether
        publically or privately, as not loadable."""
        if self._loadedFromArchive():
            raise pyxb.NamespaceError(self, 'cannot mark not loadable when already loaded')
        for mr in self.moduleRecords():
            mr._setIsLoadable(False)

class ModuleRecord (pyxb.utils.utility.PrivateTransient_mixin):
    __PrivateTransient = set()
    
    def namespace (self):
        return self.__namespace
    __namespace = None

    def archive (self):
        return self.__archive
    def _setArchive (self, archive):
        self.__archive = archive
        return self
    __archive = None
    __PrivateTransient.add('archive')

    def isPublic (self):
        return self.__isPublic
    def _setIsPublic (self, is_public):
        self.__isPublic = is_public
        return self
    __isPublic = None

    def isIncorporated (self):
        return self.__isIncorporated or (self.archive() is None)
    def markIncorporated (self):
        assert self.__isLoadable
        self.__isIncorporated = True
        self.__isLoadable = False
        return self
    __isIncorporated = None
    __PrivateTransient.add('isIncorporated')

    def isLoadable (self):
        return self.__isLoadable and (self.archive() is not None)
    def _setIsLoadable (self, is_loadable):
        self.__isLoadable = is_loadable
        return self
    __isLoadable = None

    def generationUID (self):
        return self.__generationUID
    __generationUID = None

    def origins (self):
        return self.__originMap.values()
    def addOrigin (self, origin):
        assert isinstance(origin, _ObjectOrigin)
        assert not (origin.signature() in self.__originMap)
        self.__originMap[origin.signature()] = origin
        return origin
    def lookupOriginBySignature (self, signature):
        return self.__originMap.get(signature)
    def _setOrigins (self, origins):
        if self.__originMap is None:
            self.__originMap = {}
        else:
            self.__originMap.clear()
        [ self.addOrigin(_o) for _o in origins ]
        return self
    __originMap = None

    def hasMatchingOrigin (self, **kw):
        for origin in self.origins():
            if origin.match(**kw):
                return True
        return False

    def modulePath (self):
        return self.__modulePath
    def setModulePath (self, module_path):
        assert (module_path is None) or isinstance(module_path, basestring)
        self.__modulePath = module_path
        return self
    __modulePath = None

    def module (self):
        return self.__module
    def _setModule (self, module):
        self.__module = module
        # This is a nice idea, but screws up the unit tests that already have
        # ns1 and the like logged as expected prefixes.  Only causes a problem
        # when the tests are run individually; dunno why.
        #ns = self.namespace()
        #if (ns.prefix() is None) and (module is not None):
        #    try:
        #        ns.setPrefix(os.path.basename(os.path.normpath(module.__file__)).split('.')[0])
        #    except AttributeError:
        #        pass
        return self
    __module = None
    __PrivateTransient.add('module')

    def referencedNamespaces (self):
        return self.__referencedNamespaces
    def _setReferencedNamespaces (self, referenced_namespaces):
        self.__referencedNamespaces.update(referenced_namespaces)
        return self
    def referenceNamespace (self, namespace):
        self.__referencedNamespaces.add(namespace)
        return namespace
    __referencedNamespaces = None

    __constructedLocally = False
    __PrivateTransient.add('constructedLocally')

    def __init__ (self, namespace, generation_uid, **kw):
        import builtin

        super(ModuleRecord, self).__init__()
        self.__namespace = namespace
        #print 'Created MR for %s gen %s' % (namespace, generation_uid)
        assert (generation_uid != builtin.BuiltInObjectUID) or namespace.isBuiltinNamespace()
        self.__isPublic = kw.get('is_public', False)
        self.__isIncoporated = kw.get('is_incorporated', False)
        self.__isLoadable = kw.get('is_loadable', True)
        assert isinstance(generation_uid, pyxb.utils.utility.UniqueIdentifier)
        self.__generationUID = generation_uid
        self.__modulePath = kw.get('module_path')
        self.__module = kw.get('module')
        self.__originMap = {}
        self.__referencedNamespaces = set()
        self.__categoryObjects = { }
        self.__constructedLocally = True
        self.__dependsOnExternal = set()

    def _setFromOther (self, other, archive):
        if (not self.__constructedLocally) or other.__constructedLocally:
            raise pyxb.ImplementationError('Module record update requires local to be updated from archive')
        assert self.__generationUID == other.__generationUID
        assert self.__archive is None
        self.__isPublic = other.__isPublic
        assert not self.__isIncorporated
        self.__isLoadable = other.__isLoadable
        self.__modulePath = other.__modulePath
        # self.__module already set correctly
        self.__originMap.update(other.__originMap)
        self.__referencedNamespaces.update(other.__referencedNamespaces)
        if not (other.__categoryObjects is None):
            self.__categoryObjects.update(other.__categoryObjects)
        self.__dependsOnExternal.update(other.__dependsOnExternal)
        self._setArchive(archive)

    def categoryObjects (self):
        return self.__categoryObjects
    def resetCategoryObjects (self):
        self.__categoryObjects.clear()
        for origin in self.origins():
            origin.resetCategoryMembers()
    def _addCategoryObject (self, category, name, obj):
        obj._prepareForArchive(self)
        self.__categoryObjects.setdefault(category, {})[name] = obj
    def _loadCategoryObjects (self, category_objects):
        assert self.__categoryObjects is None
        assert not self.__constructedLocally
        ns = self.namespace()
        ns.configureCategories(category_objects.keys())
        for (cat, obj_map) in category_objects.iteritems():
            current_map = ns.categoryMap(cat)
            for (local_name, component) in obj_map.iteritems():
                existing_component = current_map.get(local_name)
                if existing_component is None:
                    current_map[local_name] = component
                elif existing_component._allowUpdateFromOther(component):
                    existing_component._updateFromOther(component)
                else:
                    raise pyxb.NamespaceError(self, 'Load attempted to override %s %s in %s' % (cat, local_name, self.namespace()))
        self.markIncorporated()
    __categoryObjects = None
    __PrivateTransient.add('categoryObjects')

    def dependsOnExternal (self):
        return self.__dependsOnExternal
    __dependsOnExternal = None

    def prepareForArchive (self, archive):
        assert self.archive() is None
        self._setArchive(archive)
        ns = self.namespace()
        self.__dependsOnExternal.clear()
        for mr in ns.moduleRecords():
            if mr != self:
                print 'This gen depends on %s' % (mr,)
                self.__dependsOnExternal.add(mr.generationUID())
        for obj in ns._namedObjects().union(ns.components()):
            if isinstance(obj, _ArchivableObject_mixin):
                if obj._objectOrigin():
                    obj._prepareForArchive(self)
        #print 'Archive %s ns %s module %s has %d origins' % (self.archive(), self.namespace(), self, len(self.origins()))

    def completeGenerationAssociations (self):
        self.namespace()._transferReferencedNamespaces(self)
        self.namespace()._associateOrigins(self)

    def __str__ (self):
        return 'MR[%s]@%s' % (self.generationUID(), self.namespace())

class _ObjectOrigin (pyxb.utils.utility.PrivateTransient_mixin, pyxb.cscRoot):
    """Marker class for objects that can serve as an origin for an object in a
    namespace."""
    __PrivateTransient = set()

    def signature (self):
        return self.__signature
    __signature = None

    def moduleRecord (self):
        return self.__moduleRecord
    __moduleRecord = None

    def namespace (self):
        return self.moduleRecord().namespace()

    def generationUID (self):
        return self.moduleRecord().generationUID()

    def __init__ (self, namespace, generation_uid, **kw):
        self.__signature = kw.pop('signature', None)
        super(_ObjectOrigin, self).__init__(**kw)
        self.__moduleRecord = namespace.lookupModuleRecordByUID(generation_uid, create_if_missing=True, **kw)
        self.__moduleRecord.addOrigin(self)
        self.__categoryMembers = { }
        self.__categoryObjectMap = { }

    def resetCategoryMembers (self):
        self.__categoryMembers.clear()
        self.__categoryObjectMap.clear()
        self.__originatedComponents = None
    def addCategoryMember (self, category, name, obj):
        self.__categoryMembers.setdefault(category, set()).add(name)
        self.__categoryObjectMap.setdefault(category, {})[name] = obj
        self.__moduleRecord._addCategoryObject(category, name, obj)
    def categoryMembers (self):
        return self.__categoryMembers
    def originatedObjects (self):
        if self.__originatedObjects is None:
            components = set()
            [ components.update(_v.values()) for _v in self.__categoryObjectMap.itervalues() ]
            self.__originatedObjects = frozenset(components)
        return self.__originatedObjects

    # The set of category names associated with objects.  Don't throw this
    # away and use categoryObjectMap.keys() instead: that's transient, and we
    # need this to have a value when read from an archive.
    __categoryMembers = None

    # Map from category name to a map from an object name to the object
    __categoryObjectMap = None
    __PrivateTransient.add('categoryObjectMap')

    # The set of objects that originated at this origin
    __originatedObjects = None
    __PrivateTransient.add('originatedObjects')

class _SchemaOrigin (_ObjectOrigin):
    """Holds the data regarding components derived from a single schema.

    Coupled to a particular namespace through the
    L{_NamespaceComponentAssociation_mixin}.
    """

    __PrivateTransient = set()

    def __setDefaultKW (self, kw):
        schema = kw.get('schema')
        if schema is not None:
            assert not ('location' in kw)
            kw['location'] = schema.location()
            assert not ('signature' in kw)
            kw['signature'] = schema.signature()
            assert not ('generation_uid' in kw)
            kw['generation_uid'] = schema.generationUID()
            assert not ('namespace' in kw)
            kw['namespace'] = schema.targetNamespace()
            assert not ('version' in kw)
            kw['version'] = schema.schemaAttribute('version')

    def match (self, **kw):
        """Determine whether this record matches the parameters.

        @keyword schema: a L{pyxb.xmlschema.structures.Schema} instance from
        which the other parameters are obtained.
        @keyword location: a schema location (URI)
        @keyword signature: a schema signature
        @return: C{True} iff I{either} C{location} or C{signature} matches."""
        self.__setDefaultKW(kw)
        location = kw.get('location')
        if (location is not None) and (self.location() == location):
            return True
        signature = kw.get('signature')
        if (signature is not None) and (self.signature() == signature):
            return True
        return False

    def location (self):
        return self.__location
    __location = None

    def schema (self):
        return self.__schema
    __schema = None
    __PrivateTransient.add('schema')

    def version (self):
        return self.__version
    __version = None

    def __init__ (self, **kw):
        self.__setDefaultKW(kw)
        self.__schema = kw.pop('schema', None)
        self.__location = kw.pop('location', None)
        self.__version = kw.pop('version', None)
        super(_SchemaOrigin, self).__init__(kw.pop('namespace'), kw.pop('generation_uid'), **kw)

    def __str__ (self):
        rv = [ '_SchemaOrigin(%s@%s' % (self.namespace(), self.location()) ]
        if self.version() is not None:
            rv.append(',version=%s' % (self.version(),))
        rv.append(')')
        return ''.join(rv)

def AvailableForLoad ():
    """Return a list of namespace URIs for which we may be able to load the
    namespace contents from a pre-parsed file.  The corresponding L{Namespace}
    can be retrieved using L{NamespaceForURI}, and the declared objects in
    that namespace loaded with L{Namespace.validateComponentModel}.

    Note that success of the load is not guaranteed if the packed file
    is not compatible with the schema class being used."""
    # Invoke this to ensure we have searched for loadable namespaces
    return _LoadableNamespaceMap().keys()

class NamespaceDependencies (object):

    def rootNamespaces (self):
        return self.__rootNamespaces
    __rootNamespaces = None

    def namespaceGraph (self, reset=False):
        if reset or (self.__namespaceGraph is None):
            self.__namespaceGraph = pyxb.utils.utility.Graph()
            map(self.__namespaceGraph.addRoot, self.rootNamespaces())

            # Make sure all referenced namespaces have valid components
            need_check = self.__rootNamespaces.copy()
            done_check = set()
            while 0 < len(need_check):
                ns = need_check.pop()
                ns.validateComponentModel()
                self.__namespaceGraph.addNode(ns)
                for rns in ns.referencedNamespaces().union(ns.importedNamespaces()):
                    self.__namespaceGraph.addEdge(ns, rns)
                    if not rns in done_check:
                        need_check.add(rns)
                if not ns.hasSchemaComponents():
                    print 'WARNING: Referenced %s has no schema components' % (ns.uri(),)
                done_check.add(ns)
            assert done_check == self.__namespaceGraph.nodes()

        return self.__namespaceGraph
    __namespaceGraph = None

    def namespaceOrder (self, reset=False):
        return self.namespaceGraph(reset).sccOrder()

    def siblingsFromGraph (self, reset=False):
        siblings = set()
        ns_graph = self.namespaceGraph(reset)
        for ns in self.__rootNamespaces:
            ns_siblings = ns_graph.sccMap().get(ns)
            if ns_siblings is not None:
                siblings.update(ns_siblings)
            else:
                siblings.add(ns)
        return siblings

    def siblingNamespaces (self):
        if self.__siblingNamespaces is None:
            self.__siblingNamespaces = self.siblingsFromGraph()
        return self.__siblingNamespaces

    def setSiblingNamespaces (self, sibling_namespaces):
        self.__siblingNamespaces = sibling_namespaces

    __siblingNamespaces = None

    def dependentNamespaces (self, reset=False):
        return self.namespaceGraph(reset).nodes()

    def componentGraph (self, reset=False):
        if reset or (self.__componentGraph is None):
            self.__componentGraph = pyxb.utils.utility.Graph()
            all_components = set()
            for ns in self.siblingNamespaces():
                [ all_components.add(_c) for _c in ns.components() if _c.hasBinding() ]
                
            need_visit = all_components.copy()
            while 0 < len(need_visit):
                c = need_visit.pop()
                self.__componentGraph.addNode(c)
                for cd in c.bindingRequires(include_lax=True):
                    if cd in all_components:
                        self.__componentGraph.addEdge(c, cd)
        return self.__componentGraph
    __componentGraph = None

    def componentOrder (self, reset=False):
        return self.componentGraph(reset).sccOrder()

    def __init__ (self, **kw):
        namespace_set = set(kw.get('namespace_set', []))
        namespace = kw.get('namespace')
        if namespace is not None:
            namespace_set.add(namespace)
        if 0 == len(namespace_set):
            raise pyxb.LogicError('NamespaceDependencies requires at least one root namespace')
        self.__rootNamespaces = namespace_set


## Local Variables:
## fill-column:78
## End:
