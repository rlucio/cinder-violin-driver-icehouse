#!/usr/bin/env python

# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 Violin Memory, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from cinder.volume.drivers.violin.vxg.core.restobject import RestObject
from cinder.volume.drivers.violin.vxg.vshare import igroup as IGROUP
from cinder.volume.drivers.violin.vxg.vshare import iscsi as ISCSI
from cinder.volume.drivers.violin.vxg.vshare import lun as LUN
from cinder.volume.drivers.violin.vxg.vshare import snapshot as SNAPSHOT

CLASS_NAMES = 'VShare'

"""
Adding new classes to this module:

All new classes should be added at the bottom of this file (you can't inherit
from a class that hasn't been defined yet).  Keep the most up-to-date class
named "VShare".  When adding a new VShare class, rename the current VShare
to "VShare_x", where x is +1 of the highest named class in this file.  This
will typically be +1 of whatever class the old "VShare" class is inheriting
from).

Here's an example snippit of old code before updating:

class VShare(VShare_5):
    def __init__(self, session):
        super(VShare, self).__init__(session)
        ...

Here's what this would change to (two updates):

class VShare_6(VShare_5):
    def __init__(self, session):
        super(VShare_6, self).__init__(session)
        ...

"""


class VShare_1(RestObject):
    object_type = 'tallmaple-mg'
    _versions = '5.0.2'

    def __init__(self, session, version_info):
        super(VShare_1, self).__init__(session, version_info)
        self.basic = session
        self.lun = LUN.LUNManager(self.basic)

    @property
    def version(self):
        return self._version_info['type'] + self._version_info['version']


class VShare_2(VShare_1):
    _versions = '5.1.0'

    def __init__(self, session, version_info):
        super(VShare_2, self).__init__(session, version_info)
        self.lun = LUN.LUNManager_1(self.basic)


class VShare_3(VShare_2):
    _versions = '5.2.0'

    def __init__(self, session, version_info):
        super(VShare_3, self).__init__(session, version_info)
        self.lun = LUN.LUNManager_2(self.basic)
        self.igroup = IGROUP.IGroupManager(self.basic)
        self.iscsi = ISCSI.ISCSIManager(self.basic)


class VShare(VShare_3):
    _versions = '6.0.0'

    def __init__(self, session, version_info):
        super(VShare, self).__init__(session, version_info)
        self.lun = LUN.LUNManager_3(self.basic)
        self.igroup = IGROUP.IGroupManager_1(self.basic)
        self.snapshot = SNAPSHOT.SnapshotManager(self.basic)
