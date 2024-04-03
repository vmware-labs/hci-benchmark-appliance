"""
Copyright 2021 VMware, Inc.  All rights reserved. -- VMware Confidential

A pyVmomi helper for features states mapping
"""
from pyVmomi import Feature
import featureState


def import_vsphere_feature_states(enable_logging=True):
    featureState.init(enable_logging)

    vsphere_features = featureState.featureNameList
    pyvmomi_features = Feature.get_feature_names()
    matching_features = set(vsphere_features).intersection(pyvmomi_features)

    for feature in matching_features:
        state = vars(featureState)[feature]
        Feature.set_feature_state(feature, state)