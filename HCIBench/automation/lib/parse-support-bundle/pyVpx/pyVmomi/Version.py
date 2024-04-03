from .VmomiSupport import CreateVersion, parentMap, _MaturitySet

_internal = "internal"


# Version-specific initialization
def Init():
    # Extend self.Add(version) with support for internal versions
    _MaturitySet._AddCommon = _MaturitySet.Add
    _MaturitySet.Add = _Add
    # Add internal versions-specific method(s)
    _MaturitySet.GetInternalWireId = _GetInternalWireId
    _MaturitySet.GetInternalWireIdW = _GetInternalWireIdW
    # Backward compatibility alias(es)
    _MaturitySet.GetInternalNamespace = _MaturitySet.GetInternalWireId


def _Add(self, version):
    wireId, wireNs = self._AddCommon(version)
    internalWireNs = _internal + wireNs

    # Allow e.g. GetNameW('internalvim25') -> 'vim.version.version12'
    self._verNameMapW[internalWireNs] = version

    # Allow e.g. GetWireIdW('internalvim25') -> 'internalvim25/6.7'
    self._wireIdMapW[internalWireNs] = _internal + wireId


def _GetInternalWireId(self, vmodlNs):
    """
    VMODL namespace to registered version wire-id mapping, e.g.
    'vim' -> 'internalvim25/6.7'
    """
    return _internal + self.GetWireId(vmodlNs)


def _GetInternalWireIdW(self, wireNs):
    """
    Wire namespace to registered version wire-id mapping, e.g.
    'vim25' -> 'internalvim25/6.7'
    Supports internal wireNs as well, e.g.
    'internalvim25' -> internalvim25/6.7'
    """
    wireId = self.GetWireIdW(wireNs)
    return wireId if wireNs.startswith(_internal) else _internal + wireId


# Add an API version
def AddVersion(version,
               ns,
               versionId='',
               isLegacy=0,
               serviceNs=''):
    CreateVersion(version, ns, versionId, isLegacy, serviceNs)
    internalVersion = _GetInternalVersion(version)
    internalServiceNs = _internal + serviceNs if serviceNs else ''
    internalNs = _internal + ns if ns else ''
    CreateVersion(internalVersion, internalNs, versionId, isLegacy,
                  internalServiceNs)


# Check if a version is a child of another
def IsChildVersion(child, parent):
    return child == parent or \
        _GetPublicVersion(parent) in parentMap[_GetPublicVersion(child)]


# Get internal version string from the public version string
# vim.version.version7 --> vim.version.internalversion7
def _GetInternalVersion(version):
    verParts = version.rsplit(".", 1)
    versionName = verParts[1]
    return version if versionName.startswith(_internal) \
        else verParts[0] + '.' + _internal + versionName


# Returns public version from an internal version. In case of public version,
#  it returns the same string
def _GetPublicVersion(version):
    return "".join(version.split(_internal))
