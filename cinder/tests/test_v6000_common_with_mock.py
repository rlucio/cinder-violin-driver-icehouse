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

from cinder import context
from cinder import test
from cinder.volume import configuration as conf
from cinder.volume import volume_types

from cinder.tests import fake_vmem_xgtools_client as vxg
from cinder.volume.drivers.violin import v6000_common

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
    'lun',
    'igroup',
    'snapshot',
]


class V6000CommonDriverTestCase(test.TestCase):
    """Test case for Violin drivers."""
    def setUp(self):
        super(V6000CommonDriverTestCase, self).setUp()
        self.conf = self.setup_configuration()
        self.driver = v6000_common.V6000CommonDriver(configuration=self.conf)
        self.driver.container = 'myContainer'
        self.driver.device_id = 'ata-VIOLIN_MEMORY_ARRAY_23109R00000022'
        self.stats = {}
        self.driver.set_initialized()

    def tearDown(self):
        super(V6000CommonDriverTestCase, self).tearDown()

    def setup_configuration(self):
        # code inspired by cinder/tests/test_hp3par.py
        #
        config = mock.Mock(spec=conf.Configuration)
        config.volume_backend_name = 'v6000_common'
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

    @mock.patch('vxg.open')
    def setup_mock_client(self, _m_client, m_conf=None):
        # code inspired by cinder/tests/test_hp3par.py
        #

        # configure the vshare object mock with defaults
        _m_vshare = mock.Mock(name='VShare',
                              version='1.1.1',
                              spec=mock_client_conf)

        # if m_conf, clobber the defaults with it
        if m_conf:
            _m_vshare.configure_mock(**m_conf)

        # set calls to vxg.open() to return this mocked vshare object
        _m_client.return_value = _m_vshare

        return _m_client

    def setup_mock_vshare(self, m_conf=None):
        # function adapted from cinder/tests/test_hp3par.py
        #
        _m_vshare = mock.Mock(name='VShare',
                              version='1.1.1',
                              spec=mock_client_conf)

        if m_conf:
            _m_vshare.configure_mock(**m_conf)

        return _m_vshare

    def test_check_for_setup_error(self):
        '''No setup errors are found.'''
        bn1 = ("/vshare/state/local/container/%s/threshold/usedspace"
               "/threshold_hard_val" % self.driver.container)
        bn2 = ("/vshare/state/local/container/%s/threshold/provision"
               "/threshold_hard_val" % self.driver.container)
        bn_thresholds = {bn1: 0, bn2: 100}

        conf = {
            'basic.get_node_values.return_value': bn_thresholds,
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)
        self.driver._is_supported_vmos_version = mock.Mock(return_value=True)

        result = self.driver.check_for_setup_error()

        self.driver._is_supported_vmos_version.assert_called_with(
            self.driver.vmem_vip.version)
        self.driver.vmem_vip.basic.get_node_values.assert_called_with(
            [bn1, bn2])
        self.assertEqual(result, None)

    def test_check_for_setup_error_no_container(self):
        '''No container was configured.'''
        self.driver.vmem_vip = self.setup_mock_vshare()
        self.driver.container = ''
        self.assertRaises(v6000_common.InvalidBackendConfig,
                          self.driver.check_for_setup_error)

    def test_check_for_setup_error_invalid_usedspace_threshold(self):
        '''The array's usedspace threshold was altered (not supported).'''
        bn1 = ("/vshare/state/local/container/%s/threshold/usedspace"
               "/threshold_hard_val" % self.driver.container)
        bn2 = ("/vshare/state/local/container/%s/threshold/provision"
               "/threshold_hard_val" % self.driver.container)
        bn_thresholds = {bn1: 99, bn2: 100}

        conf = {
            'basic.get_node_values.return_value': bn_thresholds,
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)
        self.driver._is_supported_vmos_version = mock.Mock(return_value=True)

        self.assertRaises(v6000_common.InvalidBackendConfig,
                          self.driver.check_for_setup_error)

    def test_check_for_setup_error_invalid_provisionedspace_threshold(self):
        '''The array's provisioned threshold was altered (not supported).'''
        bn1 = ("/vshare/state/local/container/%s/threshold/usedspace"
               "/threshold_hard_val" % self.driver.container)
        bn2 = ("/vshare/state/local/container/%s/threshold/provision"
               "/threshold_hard_val" % self.driver.container)
        bn_thresholds = {bn1: 0, bn2: 99}

        conf = {
            'basic.get_node_values.return_value': bn_thresholds,
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)
        self.driver._is_supported_vmos_version = mock.Mock(return_value=True)

        self.assertRaises(v6000_common.InvalidBackendConfig,
                          self.driver.check_for_setup_error)

    def test_create_volume(self):
        '''Volume created successfully.'''
        self.driver._create_lun = mock.Mock()

        result = self.driver.create_volume(VOLUME)

        self.driver._create_lun.assert_called_with(VOLUME)
        self.assertTrue(result is None)

    def test_delete_volume(self):
        '''Volume deleted successfully.'''
        self.driver._delete_lun = mock.Mock()

        result = self.driver.delete_volume(VOLUME)

        self.driver._delete_lun.assert_called_with(VOLUME)
        self.assertTrue(result is None)

    def test_create_snapshot(self):
        '''Snapshot created successfully.'''
        self.driver._create_lun_snapshot = mock.Mock()

        result = self.driver.create_snapshot(SNAPSHOT)

        self.driver._create_lun_snapshot.assert_called_with(SNAPSHOT)
        self.assertTrue(result is None)

    def test_delete_snapshot(self):
        '''Snapshot deleted successfully.'''
        self.driver._delete_lun_snapshot = mock.Mock()

        result = self.driver.delete_snapshot(SNAPSHOT)

        self.driver._delete_lun_snapshot.assert_called_with(SNAPSHOT)
        self.assertTrue(result is None)

    def test_create_volume_from_snapshot(self):
        '''Volume created from a snapshot successfully.'''
        self.driver.context = None
        self.driver._create_lun = mock.Mock()
        self.driver.copy_volume_data = mock.Mock()

        result = self.driver.create_volume_from_snapshot(VOLUME, SNAPSHOT)

        self.driver._create_lun.assert_called_with(VOLUME)
        self.driver.copy_volume_data.assert_called_with(None, SNAPSHOT, VOLUME)
        self.assertTrue(result is None)

    def test_create_cloned_volume(self):
        '''Volume clone created successfully.'''
        self.driver.context = None
        self.driver._create_lun = mock.Mock()
        self.driver.copy_volume_data = mock.Mock()

        result = self.driver.create_cloned_volume(VOLUME, SRC_VOL)

        self.driver._create_lun.assert_called_with(VOLUME)
        self.driver.copy_volume_data.assert_called_with(None, SRC_VOL, VOLUME)
        self.assertTrue(result is None)

    def test_extend_volume(self):
        '''Volume extend completes successfully.'''
        new_volume_size = 10
        response = {'code': 0, 'message': 'Success '}

        conf = {
            'lun.resize_lun.return_value': response,
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)
        self.driver._send_cmd = mock.Mock(return_value=response)

        result = self.driver.extend_volume(VOLUME, new_volume_size)
        self.driver._send_cmd.assert_called_with(
            self.driver.vmem_vip.lun.resize_lun,
            'Success', self.driver.container,
            VOLUME['id'], new_volume_size)
        self.assertTrue(result is None)

    def test_extend_volume_new_size_is_too_small(self):
        '''Volume extend fails when new size would shrink the volume.'''
        new_volume_size = 0
        response = {'code': 14036, 'message': 'Failure'}

        conf = {
            'lun.resize_lun.return_value': response,
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)
        self.driver._send_cmd = mock.Mock(
            side_effect=v6000_common.ViolinBackendErr(message='fail'))

        self.assertRaises(v6000_common.ViolinBackendErr,
                          self.driver.extend_volume, VOLUME, new_volume_size)

    def test_create_lun(self):
        '''Lun is successfully created.'''
        response = {'code': 0, 'message': 'LUN create: success!'}

        conf = {
            'lun.create_lun.return_value': response,
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)
        self.driver._send_cmd = mock.Mock(return_value=response)

        result = self.driver._create_lun(VOLUME)

        self.driver._send_cmd.assert_called_with(
            self.driver.vmem_vip.lun.create_lun, 'LUN create: success!',
            self.driver.container, VOLUME['id'], VOLUME['size'], 1, "0",
            "0", "w", 1, 512, False, False, None)
        self.assertTrue(result is None)

    def test_create_lun_lun_already_exists(self):
        '''Array returns error that the lun already exists.'''
        response = {'code': 14005,
                    'message': 'LUN with name ... already exists'}

        conf = {
            'lun.create_lun.return_value': response,
        }
        self.driver.vmem_vip = self.setup_mock_client(m_conf=conf)
        self.driver._send_cmd = mock.Mock(
            side_effect=v6000_common.ViolinBackendErrExists(
                response['message']))

        self.assertTrue(self.driver._create_lun(VOLUME) is None)

    def test_create_lun_create_fails_with_exception(self):
        '''Array returns a out of space error.'''
        response = {'code': 512, 'message': 'Not enough space available'}

        conf = {
            'lun.create_lun.return_value': response,
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)
        self.driver._send_cmd = mock.Mock(
            side_effect=v6000_common.ViolinBackendErr(response['message']))

        self.assertRaises(v6000_common.ViolinBackendErr,
                          self.driver._create_lun, VOLUME)

    def test_delete_lun(self):
        '''Lun is deleted successfully.'''
        response = {'code': 0, 'message': 'lun deletion started'}
        success_msgs = ['lun deletion started', '']

        conf = {
            'lun.delete_lun.return_value': response,
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)
        self.driver._send_cmd = mock.Mock(return_value=response)
        self.driver.lun_tracker.free_lun_id_for_volume = mock.Mock()

        result = self.driver._delete_lun(VOLUME)

        self.driver._send_cmd.assert_called_with(
            self.driver.vmem_vip.lun.bulk_delete_luns,
            success_msgs, self.driver.container, VOLUME['id'])
        self.driver.lun_tracker.free_lun_id_for_volume.assert_called_with(
            VOLUME)
        self.assertTrue(result is None)

    def test_delete_lun_empty_response_message(self):
        '''Array bug where delete action returns no message.'''
        response = {'code': 0, 'message': ''}
        success_msgs = ['lun deletion started', '']

        conf = {
            'lun.delete_lun.return_value': response,
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)
        self.driver._send_cmd = mock.Mock(return_value=response)
        self.driver.lun_tracker.free_lun_id_for_volume = mock.Mock()

        self.assertTrue(self.driver._delete_lun(VOLUME) is None)

    def test_delete_lun_lun_already_deleted(self):
        '''Array fails to delete a lun that doesn't exist.'''
        response = {'code': 14005, 'message': 'LUN ... does not exist.'}
        success_msgs = ['lun deletion started', '']

        conf = {
            'lun.delete_lun.return_value': response,
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)
        self.driver._send_cmd = mock.Mock(
            side_effect=v6000_common.ViolinBackendErrNotFound(
                response['message']))
        self.driver.lun_tracker.free_lun_id_for_volume = mock.Mock()

        self.assertTrue(self.driver._delete_lun(VOLUME) is None)

    def test_delete_lun_delete_fails_with_exception(self):
        '''Array returns a generic error.'''
        response = {'code': 14000, 'message': 'Generic error'}
        success_msgs = ['lun deletion started', '']

        conf = {
            'lun.delete_lun.return_value': response
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)
        self.driver._send_cmd = mock.Mock(
            side_effect=v6000_common.ViolinBackendErr(response['message']))
        self.driver.lun_tracker.free_lun_id_for_volume = mock.Mock()

        self.assertRaises(v6000_common.ViolinBackendErr,
                          self.driver._delete_lun, VOLUME)

    def test_create_lun_snapshot(self):
        '''Snapshot creation completes successfully.'''
        response = {'code': 0, 'message': 'success'}
        success_msg = 'Snapshot create: success!'

        conf = {
            'snapshot.create_lun_snapshot.return_value': response
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)
        self.driver._send_cmd = mock.Mock(return_value=response)

        result = self.driver._create_lun_snapshot(SNAPSHOT)

        self.driver._send_cmd.assert_called_with(
            self.driver.vmem_vip.snapshot.create_lun_snapshot, success_msg,
            self.driver.container, SNAPSHOT['volume_id'], SNAPSHOT['id'])
        self.assertTrue(result is None)

    def test_delete_lun_snapshot(self):
        '''Snapshot deletion completes successfully.'''
        response = {'code': 0, 'message': 'success'}
        success_msg = 'Snapshot delete: success!'

        conf = {
            'snapshot.delete_lun_snapshot.return_value': response,
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)
        self.driver._send_cmd = mock.Mock(return_value=response)
        self.driver.lun_tracker.free_lun_id_for_snapshot = mock.Mock()

        result = self.driver._delete_lun_snapshot(SNAPSHOT)

        self.driver._send_cmd.assert_called_with(
            self.driver.vmem_vip.snapshot.delete_lun_snapshot, success_msg,
            self.driver.container, SNAPSHOT['volume_id'], SNAPSHOT['id'])
        self.driver.lun_tracker.free_lun_id_for_snapshot.assert_called_with(
            SNAPSHOT)
        self.assertTrue(result is None)

    def test_send_cmd(self):
        '''Command callback completes successfully.'''
        success_msg = 'success'
        request_args = ['arg1', 'arg2', 'arg3']
        response = {'code': 0, 'message': 'success'}

        request_func = mock.Mock(return_value=response)
        self.driver._fatal_error_code = mock.Mock(return_value=None)

        result = self.driver._send_cmd(request_func, success_msg, request_args)

        self.driver._fatal_error_code.assert_called_with(response)
        self.assertEqual(result, response)

    def test_send_cmd_request_timed_out(self):
        '''The callback retry timeout hits immediately.'''
        success_msg = 'success'
        request_args = ['arg1', 'arg2', 'arg3']
        self.driver.request_timeout = 0

        request_func = mock.Mock()

        self.assertRaises(v6000_common.RequestRetryTimeout,
                          self.driver._send_cmd,
                          request_func, success_msg, request_args)

    def test_send_cmd_response_has_no_message(self):
        '''The callback returns no message on the first call.'''
        success_msg = 'success'
        request_args = ['arg1', 'arg2', 'arg3']
        response1 = {'code': 0, 'message': None}
        response2 = {'code': 0, 'message': 'success'}

        request_func = mock.Mock(side_effect=[response1, response2])
        self.driver._fatal_error_code = mock.Mock(return_value=None)

        self.assertEqual(self.driver._send_cmd
                         (request_func, success_msg, request_args),
                         response2)

    def test_send_cmd_response_has_fatal_error(self):
        '''The callback response contains a fatal error code.'''
        success_msg = 'success'
        request_args = ['arg1', 'arg2', 'arg3']
        response = {'code': 14000, 'message': 'try again later.'}

        request_func = mock.Mock(return_value=response)
        self.driver._fatal_error_code = mock.Mock(
            side_effect=v6000_common.ViolinBackendErr(message='fail'))
        self.assertRaises(v6000_common.ViolinBackendErr,
                          self.driver._send_cmd,
                          request_func, success_msg, request_args)

    def test_get_igroup(self):
        '''The igroup is verified and already exists.'''
        bn = '/vshare/config/igroup/%s' % CONNECTOR['host']
        response = {bn: CONNECTOR['host']}

        conf = {
            'basic.get_node_values.return_value': response,
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)

        result = self.driver._get_igroup(VOLUME, CONNECTOR)

        self.driver.vmem_vip.basic.get_node_values.assert_called_with(bn)
        self.assertEqual(result, CONNECTOR['host'])

    def test_get_igroup_with_new_name(self):
        '''The igroup is verified but must be created on the backend.'''
        bn = '/vshare/config/igroup/%s' % CONNECTOR['host']
        response = {}

        conf = {
            'basic.get_node_values.return_value': response,
        }
        self.driver.vmem_vip = self.setup_mock_vshare(m_conf=conf)

        self.assertEqual(self.driver._get_igroup(VOLUME, CONNECTOR),
                         CONNECTOR['host'])

    @mock.patch.object(context, 'get_admin_context')
    @mock.patch.object(volume_types, 'get_volume_type')
    def test_get_volume_type_extra_spec(self, m_get_vol_type, m_get_context):
        '''Volume_type extra specs are found successfully.'''
        vol = VOLUME.copy()
        vol['volume_type_id'] = 1
        volume_type = {'extra_specs': {'override:test_key': 'test_value'}}

        m_get_context.return_value = None
        m_get_vol_type.return_value = volume_type

        result = self.driver._get_volume_type_extra_spec(vol, 'test_key')

        m_get_context.assert_called_with()
        m_get_vol_type.assert_called_with(None, vol['volume_type_id'])
        self.assertEqual(result, 'test_value')

    @mock.patch.object(context, 'get_admin_context')
    @mock.patch.object(volume_types, 'get_volume_type')
    def test_get_volume_type_extra_spec_with_no_volume_type(self,
                                                            m_get_vol_type,
                                                            m_get_context):
        '''No volume_type is set for the volume.'''
        vol = VOLUME.copy()
        vol['volume_type_id'] = 0
        result = self.driver._get_volume_type_extra_spec(vol, 'test_key')
        self.assertEqual(result, None)

    @mock.patch.object(context, 'get_admin_context')
    @mock.patch.object(volume_types, 'get_volume_type')
    def test_get_volume_type_extra_spec_with_no_extra_specs(self,
                                                            m_get_vol_type,
                                                            m_get_context):
        '''No extra specs exist for the volume type.'''
        vol = VOLUME.copy()
        vol['volume_type_id'] = 1
        volume_type = {'extra_specs': {}}

        m_get_context.return_value = None
        m_get_vol_type.return_value = volume_type
        result = self.driver._get_volume_type_extra_spec(vol, 'test_key')
        self.assertEqual(result, None)

    @mock.patch.object(context, 'get_admin_context')
    @mock.patch.object(volume_types, 'get_volume_type')
    def test_get_volume_type_extra_spec_with_no_override_prefix(self,
                                                                m_get_vol_type,
                                                                m_get_context):
        '''The extra specs key does not have the proper 'override' prefix.'''
        vol = VOLUME.copy()
        vol['volume_type_id'] = 1
        volume_type = {'extra_specs': {'test_key': 'test_value'}}

        m_get_context.return_value = None
        m_get_vol_type.return_value = volume_type
        result = self.driver._get_volume_type_extra_spec(vol, 'test_key')
        self.assertEqual(result, 'test_value')

    def test_wait_for_export_state(self):
        '''Queries to cluster nodes verify export state.'''
        vol = VOLUME.copy()
        bn = "/vshare/config/export/container/myContainer/lun/%s" \
            % vol['name']
        response = {'/vshare/config/export/container/myContainer/lun/vol-01':
                    vol['name']}

        conf = {
            'basic.get_node_values.return_value': response,
        }
        self.driver.vmem_mga = self.setup_mock_vshare(m_conf=conf)
        self.driver.vmem_mgb = self.setup_mock_vshare(m_conf=conf)

        result = self.driver._wait_for_exportstate(vol['name'], True)

        self.driver.vmem_mga.basic.get_node_values.assert_called_with(bn)
        self.driver.vmem_mgb.basic.get_node_values.assert_called_with(bn)
        self.assertTrue(result)

    def test_wait_for_export_state_with_no_state(self):
        '''Queries to cluster nodes verify *no* export state.'''
        vol = VOLUME.copy()
        response = {}

        conf = {
            'basic.get_node_values.return_value': response,
        }
        self.driver.vmem_mga = self.setup_mock_vshare(m_conf=conf)
        self.driver.vmem_mgb = self.setup_mock_vshare(m_conf=conf)

        self.assertTrue(self.driver._wait_for_exportstate(vol['name'], False))

    def test_is_supported_vmos_version(self):
        '''Currently supported VMOS version.'''
        version = 'V6.3.1'
        self.assertTrue(self.driver._is_supported_vmos_version(version))

    def test_is_supported_vmos_version_supported_future_version(self):
        '''Potential future supported VMOS version.'''
        version = 'V6.3.7'
        self.assertTrue(self.driver._is_supported_vmos_version(version))

    def test_is_supported_vmos_version_unsupported_past_version(self):
        '''Currently unsupported VMOS version.'''
        version = 'G5.5.2'
        self.assertFalse(self.driver._is_supported_vmos_version(version))

    def test_is_supported_vmos_version_unsupported_future_version(self):
        '''Future incompatible VMOS version.'''
        version = 'V7.0.0'
        self.assertFalse(self.driver._is_supported_vmos_version(version))

    def test_fatal_error_code(self):
        '''Return an exception for a valid fatal error code.'''
        response = {'code': 14000, 'message': 'fail city'}
        self.assertRaises(v6000_common.ViolinBackendErr,
                          self.driver._fatal_error_code,
                          response)

    def test_fatal_error_code_non_fatal_error(self):
        '''Returns no exception for a non-fatal error code.'''
        response = {'code': 1024, 'message': 'try again!'}
        self.assertEqual(self.driver._fatal_error_code(response), None)
