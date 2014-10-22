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
from cinder.volume.drivers.violin import v6000_fcp

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
    "host": "irrelevant",
    'wwpns': [u'50014380186b3f65', u'50014380186b3f67'],
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
    'igroup',
]


class V6000FCPDriverTestCase(test.TestCase):
    """Test case for VMEM FCP driver."""
    def setUp(self):
        super(V6000FCPDriverTestCase, self).setUp()
        self.conf = self.setup_configuration()
        self.driver = v6000_fcp.V6000FCDriver(configuration=self.conf)
        self.driver.container = 'myContainer'
        self.driver.device_id = 'ata-VIOLIN_MEMORY_ARRAY_23109R00000022'
        self.driver.gateway_fc_wwns = ['wwn.21:00:00:24:ff:45:fb:22',
                                       'wwn.21:00:00:24:ff:45:fb:23',
                                       'wwn.21:00:00:24:ff:45:f1:be',
                                       'wwn.21:00:00:24:ff:45:f1:bf',
                                       'wwn.21:00:00:24:ff:45:e2:30',
                                       'wwn.21:00:00:24:ff:45:e2:31',
                                       'wwn.21:00:00:24:ff:45:e2:5e',
                                       'wwn.21:00:00:24:ff:45:e2:5f']
        self.stats = {}
        self.driver.set_initialized()

    def tearDown(self):
        super(V6000FCPDriverTestCase, self).tearDown()

    def setup_configuration(self):
        config = mock.Mock(spec=conf.Configuration)
        config.volume_backend_name = 'v6000_fcp'
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
        '''No setup errors are found.'''
        result = self.driver.check_for_setup_error()
        m_setup_func.assert_called_with()
        self.assertTrue(result is None)

    @mock.patch.object(v6000_common.V6000CommonDriver, 'check_for_setup_error')
    def test_check_for_setup_error_no_wwn_config(self, m_setup_func):
        '''No wwns were found during setup.'''
        self.driver.gateway_fc_wwns = []
        self.assertRaises(v6000_common.InvalidBackendConfig,
                          self.driver.check_for_setup_error)

    def test_initialize_connection(self):
        lun_id = 1
        igroup = None
        volume = mock.Mock(spec=models.Volume)

        self.driver.vmem_vip = self.setup_mock_vshare()
        self.driver._export_lun = mock.Mock(return_value=lun_id)

        props = self.driver.initialize_connection(volume, CONNECTOR)

        self.driver._export_lun.assert_called_with(volume, CONNECTOR, igroup)
        self.driver.vmem_vip.basic.save_config.assert_called_with()
        self.assertEqual(props['driver_volume_type'], "fibre_channel")
        self.assertEqual(props['data']['target_discovered'], True)
        self.assertEqual(props['data']['target_wwn'],
                         self.driver.gateway_fc_wwns)
        self.assertEqual(props['data']['target_lun'], lun_id)

    def test_initialize_connection_with_snapshot_object(self):
        lun_id = 1
        igroup = None
        snapshot = mock.Mock(spec=models.Snapshot)

        self.driver.vmem_vip = self.setup_mock_vshare()
        self.driver._export_snapshot = mock.Mock(return_value=lun_id)

        props = self.driver.initialize_connection(snapshot, CONNECTOR)

        self.driver._export_snapshot.assert_called_with(snapshot, CONNECTOR,
                                                        igroup)
        self.driver.vmem_vip.basic.save_config.assert_called_with()
        self.assertEqual(props['driver_volume_type'], "fibre_channel")
        self.assertEqual(props['data']['target_discovered'], True)
        self.assertEqual(props['data']['target_wwn'],
                         self.driver.gateway_fc_wwns)
        self.assertEqual(props['data']['target_lun'], lun_id)

    def test_terminate_connection(self):
        volume = mock.Mock(spec=models.Volume)

        self.driver.vmem_vip = self.setup_mock_vshare()
        self.driver._unexport_lun = mock.Mock()

        result = self.driver.terminate_connection(volume, CONNECTOR)

        self.driver._unexport_lun.assert_called_with(volume)
        self.driver.vmem_vip.basic.save_config.assert_called_with()
        self.assertEqual(result, None)

    def test_terminate_connection_snapshot_object(self):
        snapshot = mock.Mock(spec=models.Snapshot)

        self.driver.vmem_vip = self.setup_mock_vshare()
        self.driver._unexport_snapshot = mock.Mock()

        result = self.driver.terminate_connection(snapshot, CONNECTOR)

        self.driver._unexport_snapshot.assert_called_with(snapshot)
        self.driver.vmem_vip.basic.save_config.assert_called_with()
        self.assertEqual(result, None)

    def test_get_volume_stats(self):
        self.driver._update_stats = mock.Mock()
        self.driver._update_stats()

        result = self.driver.get_volume_stats(True)

        self.driver._update_stats.assert_called_with()
        self.assertEqual(result, self.driver.stats)

    @mock.patch.object(v6000_common.LunIdList, 'get_lun_id_for_volume')
    def test_export_lun(self, m_get_lun_id_func):
        lun_id = '1'
        igroup = 'test-igroup-1'
        response = {'code': 0, 'message': ''}

        self.driver.vmem_vip = self.setup_mock_vshare()
        m_get_lun_id_func.return_value = lun_id
        self.driver._send_cmd_and_verify = mock.Mock(
            return_value=response)

        result = self.driver._export_lun(VOLUME, CONNECTOR, igroup)

        m_get_lun_id_func.assert_called_with(VOLUME)
        self.driver._send_cmd_and_verify.assert_called_with(
            self.driver.vmem_vip.lun.export_lun,
            self.driver._wait_for_exportstate, '',
            [self.driver.container, VOLUME['id'], 'all', igroup, lun_id],
            [VOLUME['id'], True])
        self.assertEqual(result, lun_id)

    @mock.patch.object(v6000_common.LunIdList, 'get_lun_id_for_volume')
    def test_export_lun_fails_with_exception(self, m_get_lun_id_func):
        lun_id = '1'
        igroup = 'test-igroup-1'
        response = {'code': 14000, 'message': 'Generic error'}

        self.driver.vmem_vip = self.setup_mock_vshare()
        m_get_lun_id_func.return_value = lun_id
        self.driver._send_cmd_and_verify = mock.Mock(
            side_effect=v6000_common.ViolinBackendErr(response['message']))

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
        self.driver._send_cmd = mock.Mock(return_value=response)
        self.driver._wait_for_exportstate = mock.Mock()

        result = self.driver._export_snapshot(SNAPSHOT, CONNECTOR, igroup)

        m_get_lun_id_func.assert_called_with(SNAPSHOT)
        self.driver._send_cmd.assert_called_with(
            self.driver.vmem_vip.snapshot.export_lun_snapshot, '',
            self.driver.container, SNAPSHOT['volume_id'], SNAPSHOT['id'],
            igroup, 'all', lun_id)
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
        wwpns = ['wwn.50:01:43:80:18:6b:3f:65', 'wwn.50:01:43:80:18:6b:3f:67']

        conf = {
            'igroup.add_initiators.return_value': response,
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)

        self.driver._convert_wwns_openstack_to_vmem = mock.Mock(
            return_value=wwpns)

        result = self.driver._add_igroup_member(CONNECTOR, igroup)

        self.driver._convert_wwns_openstack_to_vmem.assert_called_with(
            CONNECTOR['wwpns'])
        self.driver.vmem_vip.igroup.add_initiators.assert_called_with(
            igroup, wwpns)
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

    def test_get_active_fc_targets(self):
        bn0 = '/vshare/state/global/*'
        response0 = {'/vshare/state/global/1': 1,
                     '/vshare/state/global/2': 2}
        bn1 = '/vshare/state/global/1/target/fc/**'
        response1 = {'/vshare/state/global/1/target/fc/hba-a1/wwn':
                     'wwn.21:00:00:24:ff:45:fb:22'}
        bn2 = '/vshare/state/global/2/target/fc/**'
        response2 = {'/vshare/state/global/2/target/fc/hba-a1/wwn':
                     'wwn.21:00:00:24:ff:45:e2:30'}
        wwpns = ['21000024ff45fb22', '21000024ff45e230']

        conf = {
            'basic.get_node_values.side_effect':
            [response0, response1, response2],
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)

        result = self.driver._get_active_fc_targets()

        calls = [mock.call(bn0), mock.call(bn1), mock.call(bn2)]
        self.driver.vmem_vip.basic.get_node_values.assert_has_calls(
            calls, any_order=True)
        self.assertEqual(result, wwpns)

    def test_convert_wwns_openstack_to_vmem(self):
        vmem_wwns = ['wwn.50:01:43:80:18:6b:3f:65']
        openstack_wwns = ['50014380186b3f65']
        result = self.driver._convert_wwns_openstack_to_vmem(openstack_wwns)
        self.assertEqual(result, vmem_wwns)

    def test_convert_wwns_vmem_to_openstack(self):
        vmem_wwns = ['wwn.50:01:43:80:18:6b:3f:65']
        openstack_wwns = ['50014380186b3f65']
        result = self.driver._convert_wwns_vmem_to_openstack(vmem_wwns)
        self.assertEqual(result, openstack_wwns)
