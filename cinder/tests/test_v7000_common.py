# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2014 Violin Memory, Inc.
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

"""
Violin Memory tests for 7.x storage drivers

by Ryan Lucio
Senior Software Engineer
Violin Memory

Python-related documentation for unit testing with unittest and mock
can be found at:
* http://docs.python.org/2/library/unittest.html
* https://pypi.python.org/pypi/mock
* http://www.voidspace.org.uk/python/mock/

Cinder testing/development howto can be found at:
* http://docs.openstack.org/developer/cinder/devref/
  development.environment.html
"""

import mock

from cinder import test
from cinder.volume import configuration as conf
from cinder.volume.drivers.violin import v7000_common as violin

VOLUME_ID = "abcdabcd-1234-abcd-1234-abcdeffedcba"
VOLUME = {"name": "volume-" + VOLUME_ID,
          "id": VOLUME_ID,
          "display_name": "fake_volume",
          "size": 2,
          "host": "irrelevant",
          "volume_type": None,
          "volume_type_id": None,
          }
SNAPSHOT_ID = "abcdabcd-1234-abcd-1234-abcdeffedcbb"
SNAPSHOT = {"name": "snapshot-" + SNAPSHOT_ID,
            "id": SNAPSHOT_ID,
            "volume_id": VOLUME_ID,
            "volume_name": "volume-" + VOLUME_ID,
            "volume_size": 2,
            "display_name": "fake_snapshot",
            }
SRC_VOL_ID = "abcdabcd-1234-abcd-1234-abcdeffedcbc"
SRC_VOL = {"name": "volume-" + SRC_VOL_ID,
           "id": SRC_VOL_ID,
           "display_name": "fake_src_vol",
           "size": 2,
           "host": "irrelevant",
           "volume_type": None,
           "volume_type_id": None,
           }
INITIATOR_IQN = "iqn.1111-22.org.debian:11:222"
CONNECTOR = {"initiator": INITIATOR_IQN}


class V7000CommonDriverTestCase(test.TestCase):
    """Test case for Violin drivers."""
    def setUp(self):
        super(V7000CommonDriverTestCase, self).setUp()
        self.config = mock.Mock(spec=conf.Configuration)
        self.config.volume_backend_name = 'V7000_common'
        self.config.san_is_local = False
        self.config.san_ip = '1.1.1.1'
        self.config.san_login = 'admin'
        self.config.san_password = ''
        self.config.san_thin_provision = False
        self.config.gateway_mga = '2.2.2.2'
        self.config.gateway_mgb = '3.3.3.3'
        self.config.use_igroups = False
        self.driver = violin.V7000CommonDriver(configuration=self.config)
        self.driver.set_initialized()

    def tearDown(self):
        super(V7000CommonDriverTestCase, self).tearDown()

    def test_do_setup(self):
        pass

    def check_for_setup_error(self):
        pass

    def test_create_volume(self):
        volume = VOLUME
        self.assertRaises(NotImplementedError,
                          self.driver.create_volume, volume)

    def test_create_volume_from_snapshot(self):
        volume = VOLUME
        snapshot = SNAPSHOT
        self.assertRaises(NotImplementedError,
                          self.driver.create_volume_from_snapshot,
                          volume, snapshot)

    def test_create_cloned_volume(self):
        volume = VOLUME
        src_vref = SRC_VOL
        self.assertRaises(NotImplementedError,
                          self.driver.create_cloned_volume, volume, src_vref)

    def test_delete_volume(self):
        volume = VOLUME
        self.assertRaises(NotImplementedError,
                          self.driver.delete_volume, volume)

    def test_create_snapshot(self):
        snapshot = SNAPSHOT
        self.assertRaises(NotImplementedError,
                          self.driver.create_snapshot, snapshot)

    def test_delete_snapshot(self):
        snapshot = SNAPSHOT
        self.assertRaises(NotImplementedError,
                          self.driver.delete_snapshot, snapshot)

    def test_initialize_connection(self):
        volume = VOLUME
        connector = CONNECTOR
        self.assertRaises(NotImplementedError,
                          self.driver.initialize_connection, volume, connector)

    def test_terminate_connection(self):
        volume = VOLUME
        connector = CONNECTOR
        self.assertRaises(NotImplementedError,
                          self.driver.terminate_connection, volume, connector)

    def test_get_volume_stats(self):
        self.driver._update_volume_stats = mock.Mock(return_value=None)
        result = self.driver.get_volume_stats(refresh=True)
        self.driver._update_volume_stats.assert_called_once_with()
        assert result == self.driver.stats

    def test_extend_volume(self):
        size = 1
        volume = VOLUME
        self.assertRaises(NotImplementedError,
                          self.driver.extend_volume, volume, size)

    def test_update_volume_stats(self):
        expected = {'volume_backend_name': self.config.volume_backend_name,
                    'vendor_name': 'Violin Memory, Inc.',
                    'driver_version': 'unknown',
                    'storage_protocol': 'unknown',
                    'reserved_percentage': 0,
                    'QoS_support': False,
                    'total_capacity_gb': 'unknown',
                    'free_capacity_gb': 'unknown',
                    }
        assert self.driver._update_volume_stats() == None
        self.assertDictMatch(expected, self.driver.stats)
