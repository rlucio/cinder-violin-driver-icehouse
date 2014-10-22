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


class RestObject(object):
    """This class is the parent class for objects returned from cinder.volume.drivers.violin.vxg.open().

    """
    def __init__(self, session, version_info):
        self.basic = session
        self.close = self.basic.close
        self.open = self.basic.open
        self._version_info = version_info

    def __del__(self):
        """Close connections on object deletion.

        """
        try:
            self.basic.close()
        except Exception:
            pass

    def __enter__(self):
        """Implements "with cinder.volume.drivers.violin.vxg.open(...) as foo:" for vxg.

        """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Handles connection cleanup for "with cinder.volume.drivers.violin.vxg.open(...) as foo" for vxg.

        """
        self.__del__()

    @property
    def debug(self):
        '''If debug messages are turned on or not.'''
        return self.basic.debug

    @debug.setter
    def debug(self, value):
        '''Update the debug setting.'''
        self.basic.debug = bool(value)

    @property
    def closed(self):
        '''If the connection is believed open or not.'''
        return self.basic.closed

    def __repr__(self):
        values = ['<{0}'.format(self.__class__.__name__),
                  'host:{0}'.format(self.basic.host),
                  'user:{0}'.format(self.basic.user),
                  'password:{0}'.format(self.basic.password),
                  'proto:{0}'.format(self.basic.proto),
                  ]
        return ' '.join(values)


class RestNamespace(object):
    """Stores the parent object such that children namespaces can access it.

    """
    def __init__(self, basic):
        self._basic = basic
