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
Violin Memory tests for Violin Memory 6000 Series All-Flash Array Drivers

by Ryan Lucio
Senior Software Engineer
Violin Memory
"""

import mock

from cinder.db.sqlalchemy import models
from cinder import test
from cinder.volume import configuration as conf

from cinder.tests import fake_vmem_xgtools_client as vxg
from cinder.volume.drivers.violin import v6000_common
from cinder.volume.drivers.violin import v6000_iscsi

VOLUME_ID = "abcdabcd-1234-abcd-1234-abcdeffedcba"
VOLUME = {
    "name": "volume-" + VOLUME_ID,
    "id": VOLUME_ID,
    "display_name": "fake_volume",
    "size": 2,
    "host": "irrelevant",
    "volume_type": None,
    "volume_type_id": None,
}
SNAPSHOT_ID = "abcdabcd-1234-abcd-1234-abcdeffedcbb"
SNAPSHOT = {
    "name": "snapshot-" + SNAPSHOT_ID,
    "id": SNAPSHOT_ID,
    "volume_id": VOLUME_ID,
    "volume_name": "volume-" + VOLUME_ID,
    "volume_size": 2,
    "display_name": "fake_snapshot",
    "volume": VOLUME,
}
SRC_VOL_ID = "abcdabcd-1234-abcd-1234-abcdeffedcbc"
SRC_VOL = {
    "name": "volume-" + SRC_VOL_ID,
    "id": SRC_VOL_ID,
    "display_name": "fake_src_vol",
    "size": 2,
    "host": "irrelevant",
    "volume_type": None,
    "volume_type_id": None,
}
INITIATOR_IQN = "iqn.1111-22.org.debian:11:222"
CONNECTOR = {
    "initiator": INITIATOR_IQN,
    "host": "irrelevant"
}

mock_client_conf = [
    'basic',
    'basic.login',
    'basic.get_node_values',
    'basic.save_config',
    'lun',
    'lun.export_lun',
    'lun.unexport_lun',
    'snapshot',
    'snapshot.export_lun_snapshot',
    'snapshot.unexport_lun_snapshot',
    'iscsi',
    'iscsi.bind_ip_to_target',
    'iscsi.create_iscsi_target',
    'iscsi.delete_iscsi_target',
    'igroup',
]


class V6000ISCSIDriverTestCase(test.TestCase):
    """Test case for VMEM FCP driver."""
    def setUp(self):
        super(V6000ISCSIDriverTestCase, self).setUp()
        self.conf = self.setup_configuration()
        self.driver = v6000_iscsi.V6000ISCSIDriver(configuration=self.conf)
        self.driver.container = 'myContainer'
        self.driver.device_id = 'ata-VIOLIN_MEMORY_ARRAY_23109R00000022'
        self.driver.gateway_iscsi_ip_addresses_mga = '1.2.3.4'
        self.driver.gateway_iscsi_ip_addresses_mgb = '1.2.3.4'
        self.driver.array_info = [{"node": 'hostname_mga',
                                   "addr": '1.2.3.4',
                                   "conn": self.driver.vmem_mga},
                                  {"node": 'hostname_mgb',
                                   "addr": '1.2.3.4',
                                   "conn": self.driver.vmem_mgb}]
        self.stats = {}
        self.driver.set_initialized()

    def tearDown(self):
        super(V6000ISCSIDriverTestCase, self).tearDown()

    def setup_configuration(self):
        config = mock.Mock(spec=conf.Configuration)
        config.volume_backend_name = 'v6000_iscsi'
        config.san_is_local = False
        config.san_ip = '1.1.1.1'
        config.san_login = 'admin'
        config.san_password = ''
        config.san_thin_provision = False
        config.gateway_user = 'admin'
        config.gateway_password = ''
        config.gateway_vip = '1.1.1.1'
        config.gateway_mga = '2.2.2.2'
        config.gateway_mgb = '3.3.3.3'
        config.use_igroups = False
        config.container = 'myContainer'
        config.use_igroups = False
        config.use_thin_luns = False
        config.san_is_local = False
        config.gateway_iscsi_target_prefix = 'iqn.2004-02.com.vmem:'
        return config

    def setup_mock_vshare(self, m_conf=None):
        # function adapted from cinder/tests/test_hp3par.py
        #
        _m_vshare = mock.Mock(name='VShare',
                              version='1.1.1',
                              spec=mock_client_conf)

        if m_conf:
            _m_vshare.configure_mock(**m_conf)

        return _m_vshare

    @mock.patch.object(v6000_common.V6000CommonDriver, 'check_for_setup_error')
    def test_check_for_setup_error(self, m_setup_func):
        bn = "/vshare/config/iscsi/enable"
        response = {bn: True}

        conf = {
            'basic.get_node_values.return_value': response,
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)

        result = self.driver.check_for_setup_error()

        m_setup_func.assert_called_with()
        self.driver.vmem_vip.basic.get_node_values.assert_called_with(bn)
        self.assertTrue(result is None)

    @mock.patch.object(v6000_common.V6000CommonDriver, 'check_for_setup_error')
    def test_check_for_setup_error_iscsi_is_disabled(self, m_setup_func):
        bn = "/vshare/config/iscsi/enable"
        response = {bn: False}

        conf = {
            'basic.get_node_values.return_value': response,
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)

        self.assertRaises(v6000_common.InvalidBackendConfig,
                          self.driver.check_for_setup_error)

    @mock.patch.object(v6000_common.V6000CommonDriver, 'check_for_setup_error')
    def test_check_for_setup_error_no_iscsi_ips_for_mga(self, m_setup_func):
        bn = "/vshare/config/iscsi/enable"
        response = {bn: True}
        self.driver.gateway_iscsi_ip_addresses_mga = ''

        conf = {
            'basic.get_node_values.return_value': response,
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)

        self.assertRaises(v6000_common.InvalidBackendConfig,
                          self.driver.check_for_setup_error)

    @mock.patch.object(v6000_common.V6000CommonDriver, 'check_for_setup_error')
    def test_check_for_setup_error_no_iscsi_ips_for_mgb(self, m_setup_func):
        bn = "/vshare/config/iscsi/enable"
        response = {bn: True}
        self.driver.gateway_iscsi_ip_addresses_mgb = ''

        conf = {
            'basic.get_node_values.return_value': response,
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)

        self.assertRaises(v6000_common.InvalidBackendConfig,
                          self.driver.check_for_setup_error)

    def test_initialize_connection(self):
        lun_id = 1
        igroup = None
        tgt = self.driver.array_info[0]
        iqn = "%s%s:%s" % (self.conf.gateway_iscsi_target_prefix,
                           tgt['node'], VOLUME['id'])
        volume = mock.MagicMock(spec=models.Volume)

        def getitem(name):
            return VOLUME[name]

        volume.__getitem__.side_effect = getitem

        self.driver.vmem_vip = self.setup_mock_vshare()
        self.driver._get_short_name = mock.Mock(return_value=VOLUME['id'])
        self.driver._create_iscsi_target = mock.Mock(return_value=tgt)
        self.driver._export_lun = mock.Mock(return_value=lun_id)

        props = self.driver.initialize_connection(volume, CONNECTOR)

        self.driver._get_short_name.assert_called_with(volume['id'])
        self.driver._create_iscsi_target.assert_called_with(volume)
        self.driver._export_lun.assert_called_with(volume, CONNECTOR, igroup)
        self.driver.vmem_vip.basic.save_config.assert_called_with()
        self.assertEqual(props['data']['target_portal'], "1.2.3.4:3260")
        self.assertEqual(props['data']['target_iqn'], iqn)
        self.assertEqual(props['data']['target_lun'], lun_id)
        self.assertEqual(props['data']['volume_id'], volume['id'])

    def test_initialize_connection_with_snapshot_object(self):
        lun_id = 1
        igroup = None
        tgt = self.driver.array_info[0]
        iqn = "%s%s:%s" % (self.conf.gateway_iscsi_target_prefix,
                           tgt['node'], SNAPSHOT['id'])
        snapshot = mock.MagicMock(spec=models.Snapshot)

        def getitem(name):
            return SNAPSHOT[name]

        snapshot.__getitem__.side_effect = getitem

        self.driver.vmem_vip = self.setup_mock_vshare()
        self.driver._get_short_name = mock.Mock(return_value=SNAPSHOT['id'])
        self.driver._create_iscsi_target = mock.Mock(return_value=tgt)
        self.driver._export_snapshot = mock.Mock(return_value=lun_id)

        props = self.driver.initialize_connection(snapshot, CONNECTOR)

        self.driver._get_short_name.assert_called_with(snapshot['id'])
        self.driver._create_iscsi_target.assert_called_with(snapshot)
        self.driver._export_snapshot.assert_called_with(snapshot, CONNECTOR,
                                                        igroup)
        self.driver.vmem_vip.basic.save_config.assert_called_with()
        self.assertEqual(props['data']['target_portal'], "1.2.3.4:3260")
        self.assertEqual(props['data']['target_iqn'], iqn)
        self.assertEqual(props['data']['target_lun'], lun_id)
        self.assertEqual(props['data']['volume_id'], snapshot['id'])

    def test_initialize_connection_with_igroups_enabled(self):
        self.conf.use_igroups = True
        lun_id = 1
        igroup = 'test-igroup-1'
        tgt = self.driver.array_info[0]
        iqn = "%s%s:%s" % (self.conf.gateway_iscsi_target_prefix,
                           tgt['node'], VOLUME['id'])
        volume = mock.MagicMock(spec=models.Volume)

        def getitem(name):
            return VOLUME[name]

        volume.__getitem__.side_effect = getitem

        self.driver.vmem_vip = self.setup_mock_vshare()
        self.driver._get_igroup = mock.Mock(return_value=igroup)
        self.driver._add_igroup_member = mock.Mock()
        self.driver._get_short_name = mock.Mock(return_value=VOLUME['id'])
        self.driver._create_iscsi_target = mock.Mock(return_value=tgt)
        self.driver._export_lun = mock.Mock(return_value=lun_id)

        props = self.driver.initialize_connection(volume, CONNECTOR)

        self.driver._get_igroup.assert_called_with(volume, CONNECTOR)
        self.driver._add_igroup_member.assert_called_with(CONNECTOR, igroup)
        self.driver._get_short_name.assert_called_with(volume['id'])
        self.driver._create_iscsi_target.assert_called_with(volume)
        self.driver._export_lun.assert_called_with(volume, CONNECTOR, igroup)
        self.driver.vmem_vip.basic.save_config.assert_called_with()
        self.assertEqual(props['data']['target_portal'], "1.2.3.4:3260")
        self.assertEqual(props['data']['target_iqn'], iqn)
        self.assertEqual(props['data']['target_lun'], lun_id)
        self.assertEqual(props['data']['volume_id'], volume['id'])

    def test_terminate_connection(self):
        volume = mock.MagicMock(spec=models.Volume)

        self.driver.vmem_vip = self.setup_mock_vshare()
        self.driver._unexport_lun = mock.Mock()
        self.driver._delete_iscsi_target = mock.Mock()

        result = self.driver.terminate_connection(volume, CONNECTOR)

        self.driver._unexport_lun.assert_called_with(volume)
        self.driver._delete_iscsi_target.assert_called_with(volume)
        self.driver.vmem_vip.basic.save_config.assert_called_with()
        self.assertTrue(result is None)

    def test_terminate_connection_with_snapshot_object(self):
        snapshot = mock.MagicMock(spec=models.Snapshot)

        self.driver.vmem_vip = self.setup_mock_vshare()
        self.driver._unexport_snapshot = mock.Mock()
        self.driver._delete_iscsi_target = mock.Mock()

        result = self.driver.terminate_connection(snapshot, CONNECTOR)

        self.driver._unexport_snapshot.assert_called_with(snapshot)
        self.driver._delete_iscsi_target.assert_called_with(snapshot)
        self.driver.vmem_vip.basic.save_config.assert_called_with()
        self.assertTrue(result is None)

    def test_get_volume_stats(self):
        self.driver._update_stats = mock.Mock()
        self.driver._update_stats()

        result = self.driver.get_volume_stats(True)

        self.driver._update_stats.assert_called_with()
        self.assertEqual(result, self.driver.stats)

    def test_create_iscsi_target(self):
        target_name = VOLUME['id']
        response = {'code': 0, 'message': 'success'}

        m_vshare = self.setup_mock_vshare()

        self.driver.vmem_vip = m_vshare
        self.driver.vmem_mga = m_vshare
        self.driver.vmem_mgb = m_vshare
        self.driver._get_short_name = mock.Mock(return_value=VOLUME['id'])
        self.driver._send_cmd_and_verify = mock.Mock(return_value=response)
        self.driver._send_cmd = mock.Mock(return_value=response)

        calls = [mock.call(self.driver.vmem_mga.iscsi.bind_ip_to_target, '',
                           VOLUME['id'],
                           self.driver.gateway_iscsi_ip_addresses_mga),
                 mock.call(self.driver.vmem_mgb.iscsi.bind_ip_to_target, '',
                           VOLUME['id'],
                           self.driver.gateway_iscsi_ip_addresses_mgb)]

        result = self.driver._create_iscsi_target(VOLUME)

        self.driver._get_short_name.assert_called_with(VOLUME['id'])
        self.driver._send_cmd_and_verify.assert_called_with(
            self.driver.vmem_vip.iscsi.create_iscsi_target,
            self.driver._wait_for_targetstate, '',
            [target_name], [target_name])
        self.driver._send_cmd.assert_has_calls(calls)
        self.assertTrue(result in self.driver.array_info)

    def test_delete_iscsi_target(self):
        response = {'code': 0, 'message': 'success'}

        self.driver.vmem_vip = self.setup_mock_vshare()
        self.driver._get_short_name = mock.Mock(return_value=VOLUME['id'])
        self.driver._send_cmd = mock.Mock(return_value=response)

        result = self.driver._delete_iscsi_target(VOLUME)

        self.driver._get_short_name.assert_called_with(VOLUME['id'])
        self.driver._send_cmd(self.driver.vmem_vip.iscsi.delete_iscsi_target,
                              '', VOLUME['id'])
        self.assertTrue(result is None)

    def test_delete_iscsi_target_fails_with_exception(self):
        response = {'code': 14000, 'message': 'Generic error'}
        exception = v6000_common.ViolinBackendErr

        self.driver.vmem_vip = self.setup_mock_vshare()
        self.driver._get_short_name = mock.Mock(return_value=VOLUME['id'])
        self.driver._send_cmd = mock.Mock(
            side_effect=exception(response['message']))

        self.assertRaises(exception, self.driver._delete_iscsi_target, VOLUME)

    @mock.patch.object(v6000_common.LunIdList, 'get_lun_id_for_volume')
    def test_export_lun(self, m_get_lun_id_func):
        igroup = 'test-igroup-1'
        lun_id = '1'
        response = {'code': 0, 'message': ''}

        self.driver.vmem_vip = self.setup_mock_vshare()
        m_get_lun_id_func.return_value = lun_id
        self.driver._get_short_name = mock.Mock(return_value=VOLUME['id'])
        self.driver._send_cmd_and_verify = mock.Mock(return_value=response)

        result = self.driver._export_lun(VOLUME, CONNECTOR, igroup)

        m_get_lun_id_func.assert_called_with(VOLUME)
        self.driver._get_short_name.assert_called_with(VOLUME['id'])
        self.driver._send_cmd_and_verify.assert_called_with(
            self.driver.vmem_vip.lun.export_lun,
            self.driver._wait_for_exportstate, '',
            [self.driver.container, VOLUME['id'], VOLUME['id'],
             igroup, lun_id], [VOLUME['id'], True])
        self.assertEqual(result, lun_id)

    @mock.patch.object(v6000_common.LunIdList, 'get_lun_id_for_volume')
    def test_export_lun_fails_with_exception(self, m_get_lun_id_func):
        igroup = 'test-igroup-1'
        lun_id = '1'
        response = {'code': 14000, 'message': 'Generic error'}
        exception = v6000_common.ViolinBackendErr

        self.driver.vmem_vip = self.setup_mock_vshare()
        m_get_lun_id_func.return_value = lun_id
        self.driver._get_short_name = mock.Mock(return_value=VOLUME['id'])
        self.driver._send_cmd_and_verify = mock.Mock(
            side_effect=exception(response['message']))

        self.assertRaises(v6000_common.ViolinBackendErr,
                          self.driver._export_lun,
                          VOLUME, CONNECTOR, igroup)

    def test_unexport_lun(self):
        response = {'code': 0, 'message': ''}

        self.driver.vmem_vip = self.setup_mock_vshare()
        self.driver._send_cmd_and_verify = mock.Mock(
            return_value=response)

        result = self.driver._unexport_lun(VOLUME)

        self.driver._send_cmd_and_verify.assert_called_with(
            self.driver.vmem_vip.lun.unexport_lun,
            self.driver._wait_for_exportstate, '',
            [self.driver.container, VOLUME['id'], 'all', 'all', 'auto'],
            [VOLUME['id'], False])
        self.assertTrue(result is None)

    def test_unexport_lun_fails_with_exception(self):
        response = {'code': 14000, 'message': 'Generic error'}

        self.driver.vmem_vip = self.setup_mock_vshare()
        self.driver._send_cmd_and_verify = mock.Mock(
            side_effect=v6000_common.ViolinBackendErr(response['message']))

        self.assertRaises(v6000_common.ViolinBackendErr,
                          self.driver._unexport_lun, VOLUME)

    @mock.patch.object(v6000_common.LunIdList, 'get_lun_id_for_snapshot')
    def test_export_snapshot(self, m_get_lun_id_func):
        lun_id = '1'
        igroup = 'test-igroup-1'
        response = {'code': 0, 'message': ''}

        self.driver.vmem_vip = self.setup_mock_vshare()
        m_get_lun_id_func.return_value = lun_id
        self.driver._get_short_name = mock.Mock(return_value=SNAPSHOT['id'])
        self.driver._send_cmd = mock.Mock(return_value=response)
        self.driver._wait_for_exportstate = mock.Mock()

        result = self.driver._export_snapshot(SNAPSHOT, CONNECTOR, igroup)

        m_get_lun_id_func.assert_called_with(SNAPSHOT)
        self.driver._get_short_name.assert_called_with(SNAPSHOT['id'])
        self.driver._send_cmd.assert_called_with(
            self.driver.vmem_vip.snapshot.export_lun_snapshot, '',
            self.driver.container, SNAPSHOT['volume_id'], SNAPSHOT['id'],
            igroup, SNAPSHOT['id'], lun_id)
        self.driver._wait_for_exportstate.assert_called_with(SNAPSHOT['id'],
                                                             True)
        self.assertEqual(result, lun_id)

    def test_unexport_snapshot(self):
        response = {'code': 0, 'message': ''}

        self.driver.vmem_vip = self.setup_mock_vshare()
        self.driver._send_cmd = mock.Mock(return_value=response)
        self.driver._wait_for_exportstate = mock.Mock()

        result = self.driver._unexport_snapshot(SNAPSHOT)

        self.driver._send_cmd.assert_called_with(
            self.driver.vmem_vip.snapshot.unexport_lun_snapshot, '',
            self.driver.container, SNAPSHOT['volume_id'], SNAPSHOT['id'],
            'all', 'all', 'auto', False)
        self.driver._wait_for_exportstate.assert_called_with(SNAPSHOT['id'],
                                                             False)
        self.assertTrue(result is None)

    def test_add_igroup_member(self):
        igroup = 'test-group-1'
        response = {'code': 0, 'message': 'success'}

        conf = {
            'igroup.add_initiators.return_value': response,
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)

        result = self.driver._add_igroup_member(CONNECTOR, igroup)

        self.driver.vmem_vip.igroup.add_initiators.assert_called_with(
            igroup, CONNECTOR['initiator'])
        self.assertTrue(result is None)

    def test_update_stats(self):
        backend_name = self.conf.volume_backend_name
        vendor_name = "Violin Memory, Inc."
        tot_bytes = 100 * 1024 * 1024 * 1024
        free_bytes = 50 * 1024 * 1024 * 1024
        bn0 = '/cluster/state/master_id'
        bn1 = "/vshare/state/global/1/container/myContainer/total_bytes"
        bn2 = "/vshare/state/global/1/container/myContainer/free_bytes"
        response1 = {bn0: '1'}
        response2 = {bn1: tot_bytes, bn2: free_bytes}

        conf = {
            'basic.get_node_values.side_effect': [response1, response2],
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)

        result = self.driver._update_stats()

        calls = [mock.call(bn0), mock.call([bn1, bn2])]
        self.driver.vmem_vip.basic.get_node_values.assert_has_calls(calls)
        self.assertEqual(self.driver.stats['total_capacity_gb'], 100)
        self.assertEqual(self.driver.stats['free_capacity_gb'], 50)
        self.assertEqual(self.driver.stats['volume_backend_name'],
                         backend_name)
        self.assertEqual(self.driver.stats['vendor_name'], vendor_name)
        self.assertTrue(result is None)

    def test_update_stats_fails_data_query(self):
        backend_name = self.conf.volume_backend_name
        vendor_name = "Violin Memory, Inc."
        bn0 = '/cluster/state/master_id'
        bn1 = "/vshare/state/global/1/container/myContainer/total_bytes"
        bn2 = "/vshare/state/global/1/container/myContainer/free_bytes"
        response1 = {bn0: '1'}
        response2 = {}

        conf = {
            'basic.get_node_values.side_effect': [response1, response2],
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)

        self.assertTrue(self.driver._update_stats() is None)
        self.assertEqual(self.driver.stats['total_capacity_gb'], "unknown")
        self.assertEqual(self.driver.stats['free_capacity_gb'], "unknown")
        self.assertEqual(self.driver.stats['volume_backend_name'],
                         backend_name)
        self.assertEqual(self.driver.stats['vendor_name'], vendor_name)

    def testGetShortName_LongName(self):
        long_name = "abcdefghijklmnopqrstuvwxyz1234567890"
        short_name = "abcdefghijklmnopqrstuvwxyz123456"
        self.assertEqual(self.driver._get_short_name(long_name), short_name)

    def testGetShortName_ShortName(self):
        long_name = "abcdef"
        short_name = "abcdef"
        self.assertEqual(self.driver._get_short_name(long_name), short_name)

    def testGetShortName_EmptyName(self):
        long_name = ""
        short_name = ""
        self.assertEqual(self.driver._get_short_name(long_name), short_name)

    def test_get_active_iscsi_ips(self):
        bn0 = "/net/interface/config/*"
        bn1 = ["/net/interface/state/eth4/addr/ipv4/1/ip",
               "/net/interface/state/eth4/flags/link_up"]
        response1 = {"/net/interface/config/eth4": "eth4"}
        response2 = {"/net/interface/state/eth4/addr/ipv4/1/ip": "1.1.1.1",
                     "/net/interface/state/eth4/flags/link_up": True}

        conf = {
            'basic.get_node_values.side_effect': [response1, response2],
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)

        results = self.driver._get_active_iscsi_ips(self.driver.vmem_vip)

        calls = [mock.call(bn0), mock.call(bn1)]
        self.driver.vmem_vip.basic.get_node_values.assert_has_calls(calls)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], "1.1.1.1")

    def test_get_active_iscsi_ips_with_invalid_interfaces(self):
        response = {"/net/interface/config/lo": "lo",
                    "/net/interface/config/vlan10": "vlan10",
                    "/net/interface/config/eth1": "eth1",
                    "/net/interface/config/eth2": "eth2",
                    "/net/interface/config/eth3": "eth3"}

        conf = {
            'basic.get_node_values.return_value': response,
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)

        result = self.driver._get_active_iscsi_ips(self.driver.vmem_vip)

        self.assertEqual(len(result), 0)

    def test_get_active_iscsi_ips_with_no_interfaces(self):
        response = {}

        conf = {
            'basic.get_node_values.return_value': response,
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)

        result = self.driver._get_active_iscsi_ips(self.driver.vmem_vip)

        self.assertEqual(len(result), 0)

    def test_get_hostname(self):
        bn = '/system/hostname'
        response = {bn: 'MYHOST'}

        conf = {
            'basic.get_node_values.return_value': response,
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)

        result = self.driver._get_hostname()

        self.driver.vmem_vip.basic.get_node_values.assert_called_with(bn)
        self.assertEqual(result, "MYHOST")

    def test_get_hostname_mga(self):
        bn = '/system/hostname'
        response = {bn: 'MYHOST'}

        conf = {
            'basic.get_node_values.return_value': response,
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)
        self.driver.vmem_mga = self.setup_mock_vshare(m_conf=conf)
        self.assertEqual(self.driver._get_hostname('mga'), "MYHOST")

    def test_get_hostname_mgb(self):
        response = {"/system/hostname": "MYHOST"}
        bn = '/system/hostname'
        response = {bn: 'MYHOST'}

        conf = {
            'basic.get_node_values.return_value': response,
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)
        self.driver.vmem_mgb = self.setup_mock_vshare(m_conf=conf)
        self.assertEqual(self.driver._get_hostname('mgb'), "MYHOST")

    def test_get_hostname_query_fails(self):
        response = {}

        conf = {
            'basic.get_node_values.return_value': response,
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)

        self.assertEqual(self.driver._get_hostname(), self.conf.gateway_vip)

    def test_get_lun_id(self):
        bn = "/vshare/config/export/container/myContainer/lun/%s/target/**" \
            % VOLUME['id']
        response = {("/vshare/config/export/container/myContainer/lun"
                     "/%s/target/hba-a1/initiator/openstack/lun_id"
                     % VOLUME['id']): 1}

        conf = {
            'basic.get_node_values.return_value': response,
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)

        result = self.driver._get_lun_id(VOLUME['id'])

        self.driver.vmem_vip.basic.get_node_values.assert_called_with(bn)
        self.assertEqual(result, 1)

    def test_get_lun_id_with_no_lun_config(self):
        bn = '/vshare/config/export/container/myContainer/lun/vol-01/target/**'
        response = {}

        conf = {
            'basic.get_node_values.return_value': response,
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)

        self.assertEqual(self.driver._get_lun_id(VOLUME['id']), -1)

    def test_wait_for_targetstate(self):
        target = 'mytarget'
        bn = "/vshare/config/iscsi/target/%s" % target
        response = {bn: target}

        conf = {
            'basic.get_node_values.return_value': response,
        }
        self.driver.vmem_mga = self.setup_mock_vshare(m_conf=conf)
        self.driver.vmem_mgb = self.setup_mock_vshare(m_conf=conf)

        result = self.driver._wait_for_targetstate(target)

        self.driver.vmem_mga.basic.get_node_values.assert_called_with(bn)
        self.driver.vmem_mgb.basic.get_node_values.assert_called_with(bn)
        self.assertTrue(result)
