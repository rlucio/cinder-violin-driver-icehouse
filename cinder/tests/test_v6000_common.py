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
Violin Memory tests for common driver functions

by Ryan Lucio
Senior Software Engineer
Violin Memory

Note: python documentation for unit testing can be found at
http://docs.python.org/2/library/unittest.html

Note: cinder documentation for development can be found at
http://docs.openstack.org/developer/cinder/devref/development.environment.html
"""


import mox
import unittest

# TODO(rdl): import and use test utils (cinder.tests.utils)
from cinder import context
from cinder.db.sqlalchemy import models
from cinder.volume import volume_types

from cinder.volume.drivers.violin.vxg.core.session import XGSession
from cinder.volume.drivers.violin.vxg.vshare.igroup import IGroupManager
from cinder.volume.drivers.violin.vxg.vshare.iscsi import ISCSIManager
from cinder.volume.drivers.violin.vxg.vshare.lun import LUNManager_3 as LUNManager
from cinder.volume.drivers.violin.vxg.vshare.snapshot import SnapshotManager
from cinder.volume.drivers.violin.vxg.vshare.vshare import VShare

from cinder.volume import configuration as conf
from cinder.volume.drivers.violin import v6000_common


class testV6000Common(unittest.TestCase):
    """A test class for the VMEM V6000 common driver module."""
    def setUp(self):
        self.m = mox.Mox()
        self.m_conn = self.m.CreateMock(VShare)
        self.m_conn.basic = self.m.CreateMock(XGSession)
        self.m_conn.lun = self.m.CreateMock(LUNManager)
        self.m_conn.iscsi = self.m.CreateMock(ISCSIManager)
        self.m_conn.igroup = self.m.CreateMock(IGroupManager)
        self.m_conn.snapshot = self.m.CreateMock(SnapshotManager)
        self.m_conn.version = '1.1.1'
        self.config = mox.MockObject(conf.Configuration)
        self.config.append_config_values(mox.IgnoreArg())
        self.config.gateway_vip = '1.1.1.1'
        self.config.gateway_mga = '2.2.2.2'
        self.config.gateway_mgb = '3.3.3.3'
        self.config.gateway_user = 'admin'
        self.config.gateway_password = ''
        self.config.volume_backend_name = 'violin'
        self.config.use_igroups = False
        self.config.use_thin_luns = False
        self.config.san_is_local = False
        self.driver = v6000_common.V6000CommonDriver(configuration=self.config)
        self.driver.vmem_vip = self.m_conn
        self.driver.vmem_mga = self.m_conn
        self.driver.vmem_mgb = self.m_conn
        self.driver.container = 'myContainer'
        self.driver.device_id = 'ata-VIOLIN_MEMORY_ARRAY_23109R00000022'
        self.stats = {}
        self.driver.gateway_fc_wwns = ['wwn.21:00:00:24:ff:45:fb:22',
                                       'wwn.21:00:00:24:ff:45:fb:23',
                                       'wwn.21:00:00:24:ff:45:f1:be',
                                       'wwn.21:00:00:24:ff:45:f1:bf',
                                       'wwn.21:00:00:24:ff:45:e2:30',
                                       'wwn.21:00:00:24:ff:45:e2:31',
                                       'wwn.21:00:00:24:ff:45:e2:5e',
                                       'wwn.21:00:00:24:ff:45:e2:5f']
        self.volume1 = mox.MockObject(models.Volume)
        self.volume1.id = '3d31af29-6d7d-443f-b451-6f0040d3c9a9'
        self.volume1.size = 1
        self.volume2 = mox.MockObject(models.Volume)
        self.volume2.id = '4c1af784-b328-43d2-84c8-db02158b922d'
        self.volume2.size = 2
        self.snapshot1 = mox.MockObject(models.Snapshot)
        self.snapshot1.name = 'snap-01'
        self.snapshot1.snapshot_id = 'f8849c41-6d72-4f5a-8339-2cd6b52b5e5a'
        self.snapshot1.volume_id = 1
        self.snapshot1.volume_name = 'vol-01'
        self.snapshot2 = mox.MockObject(models.Snapshot)
        self.snapshot2.name = 'snap-02'
        self.snapshot2.snapshot_id = '23e44fad-8840-46f1-99d3-5605a08fb289'
        self.snapshot2.volume_id = 2
        self.snapshot2.volume_name = 'vol-02'

    def tearDown(self):
        self.m.UnsetStubs()

    def testCheckForSetupError(self):
        bn1 = ("/vshare/state/local/container/%s/threshold/usedspace"
               "/threshold_hard_val" % self.driver.container)
        bn2 = ("/vshare/state/local/container/%s/threshold/provision"
               "/threshold_hard_val" % self.driver.container)
        bn_thresholds = {bn1: 0, bn2: 100}
        self.m.StubOutWithMock(self.driver, '_is_supported_vmos_version')
        self.driver._is_supported_vmos_version(mox.IsA(str)).AndReturn(True)
        self.m_conn.basic.get_node_values([bn1, bn2]).AndReturn(bn_thresholds)
        self.m.ReplayAll()
        self.assertTrue(self.driver.check_for_setup_error() is None)
        self.m.VerifyAll()

    def testCheckForSetupError_NoContainer(self):
        '''Container name is empty.'''
        self.driver.container = ""
        self.assertRaises(v6000_common.InvalidBackendConfig,
                          self.driver.check_for_setup_error)

    def testCheckForSetupError_InvalidUsedSpaceThreshold(self):
        bn1 = ("/vshare/state/local/container/%s/threshold/usedspace"
               "/threshold_hard_val" % self.driver.container)
        bn2 = ("/vshare/state/local/container/%s/threshold/provision"
               "/threshold_hard_val" % self.driver.container)
        bn_thresholds = {bn1: 99, bn2: 100}
        self.m.StubOutWithMock(self.driver, '_is_supported_vmos_version')
        self.driver._is_supported_vmos_version(mox.IsA(str)).AndReturn(True)
        self.m_conn.basic.get_node_values([bn1, bn2]).AndReturn(bn_thresholds)
        self.m.ReplayAll()
        self.assertRaises(v6000_common.InvalidBackendConfig,
                          self.driver.check_for_setup_error)
        self.m.VerifyAll()

    def testCheckForSetupError_InvalidProvisionedSpaceThreshold(self):
        bn1 = ("/vshare/state/local/container/%s/threshold/usedspace"
               "/threshold_hard_val" % self.driver.container)
        bn2 = ("/vshare/state/local/container/%s/threshold/provision"
               "/threshold_hard_val" % self.driver.container)
        bn_thresholds = {bn1: 0, bn2: 99}
        self.m.StubOutWithMock(self.driver, '_is_supported_vmos_version')
        self.driver._is_supported_vmos_version(mox.IsA(str)).AndReturn(True)
        self.m_conn.basic.get_node_values([bn1, bn2]).AndReturn(bn_thresholds)
        self.m.ReplayAll()
        self.assertRaises(v6000_common.InvalidBackendConfig,
                          self.driver.check_for_setup_error)
        self.m.VerifyAll()

    def testCreateVolume(self):
        volume = self.volume1
        self.m.StubOutWithMock(self.driver, '_create_lun')
        self.driver._create_lun(volume)
        self.m.ReplayAll()
        self.assertTrue(self.driver.create_volume(volume) is None)
        self.m.VerifyAll()

    def testDeleteVolume(self):
        volume = self.volume1
        self.m.StubOutWithMock(self.driver, '_delete_lun')
        self.driver._delete_lun(volume)
        self.m.ReplayAll()
        self.assertTrue(self.driver.delete_volume(volume) is None)
        self.m.VerifyAll()

    def testCreateSnapshot(self):
        snapshot = self.snapshot1
        self.m.StubOutWithMock(self.driver, '_create_lun_snapshot')
        self.driver._create_lun_snapshot(snapshot)
        self.m.ReplayAll()
        self.assertTrue(self.driver.create_snapshot(snapshot) is None)
        self.m.VerifyAll()

    def testDeleteSnapshot(self):
        snapshot = self.snapshot1
        self.m.StubOutWithMock(self.driver, '_delete_lun_snapshot')
        self.driver._delete_lun_snapshot(snapshot)
        self.m.ReplayAll()
        self.assertTrue(self.driver.delete_snapshot(snapshot) is None)
        self.m.VerifyAll()

    #def testCreateVolumeFromSnapshot(self):
    #    src_snap = self.snapshot1
    #    dest_vol = self.volume2
    #    self.m.StubOutWithMock(self.driver, '_create_lun')
    #    self.m.StubOutWithMock(self.driver, 'copy_volume_data')
    #    self.driver._create_lun(dest_vol)
    #    self.driver.copy_volume_data(self.driver.context, dest_vol, src_snap)
    #    self.m.ReplayAll()
    #    self.assertTrue(self.driver.create_volume_from_snapshot
    #                    (dest_vol, src_snap) is None)
    #    self.m.VerifyAll()

    def testCreateClonedVolume(self):
        src_vol = self.volume1
        dest_vol = self.volume2
        self.m.StubOutWithMock(self.driver, '_create_lun')
        self.m.StubOutWithMock(self.driver, 'copy_volume_data')
        self.driver._create_lun(dest_vol)
        self.driver.copy_volume_data(self.driver.context, src_vol, dest_vol)
        self.m.ReplayAll()
        self.assertTrue(self.driver.create_cloned_volume
                        (src_vol, dest_vol) is None)
        self.m.VerifyAll()

    def testExtendVolume(self):
        volume = self.volume1
        new_volume_size = 10
        response = {'code': 0, 'message': 'Success '}
        self.m.StubOutWithMock(self.driver, '_send_cmd')
        self.driver._send_cmd(self.m_conn.lun.resize_lun,
                              mox.IsA(str),
                              self.driver.container, volume['id'],
                              new_volume_size).AndReturn(response)
        self.m.ReplayAll()
        self.assertTrue(self.driver.extend_volume(volume, new_volume_size)
                        is None)
        self.m.VerifyAll()

    def testExtendVolume_NewSizeIsTooSmall(self):
        volume = self.volume1
        new_volume_size = 0
        response = {'code': 14036, 'message': 'Failure'}
        self.m.StubOutWithMock(self.driver, '_send_cmd')
        self.driver._send_cmd(self.m_conn.lun.resize_lun,
                              mox.IsA(str),
                              self.driver.container, volume['id'],
                              new_volume_size
                              ).AndRaise(v6000_common.ViolinBackendErr())
        self.m.ReplayAll()
        self.assertRaises(v6000_common.ViolinBackendErr,
                          self.driver.extend_volume, volume, new_volume_size)
        self.m.VerifyAll()

    def testCreateLun(self):
        volume = self.volume1
        response = {'code': 0, 'message': 'LUN create: success!'}
        self.m.StubOutWithMock(self.driver, '_send_cmd')
        self.driver._send_cmd(self.m_conn.lun.create_lun,
                              mox.IsA(str),
                              self.driver.container, volume['id'],
                              volume['size'], 1, "0", "0", "w", 1,
                              512, False, False, None).AndReturn(response)
        self.m.ReplayAll()
        self.assertTrue(self.driver._create_lun(volume) is None)
        self.m.VerifyAll()

    def testCreateLun_LunAlreadyExists(self):
        volume = self.volume1
        response = {'code': 0, 'message': 'LUN create: success!'}
        self.m.StubOutWithMock(self.driver, '_send_cmd')
        self.driver._send_cmd(self.m_conn.lun.create_lun,
                              mox.IsA(str),
                              self.driver.container, volume['id'],
                              volume['size'], 1, "0", "0", "w", 1,
                              512, False, False, None
                              ).AndRaise(v6000_common.ViolinBackendErrExists())
        self.m.ReplayAll()
        self.assertTrue(self.driver._create_lun(volume) is None)
        self.m.VerifyAll()

    def testCreateLun_CreateFailsWithException(self):
        volume = self.volume1
        response = {'code': 0, 'message': 'LUN create: success!'}
        exception = v6000_common.ViolinBackendErr
        self.m.StubOutWithMock(self.driver, '_send_cmd')
        self.driver._send_cmd(self.m_conn.lun.create_lun, mox.IsA(str),
                              self.driver.container, volume['id'],
                              volume['size'], 1, "0", "0", "w", 1,
                              512, False, False, None
                              ).AndRaise(exception('failed'))
        self.m.ReplayAll()
        self.assertRaises(exception, self.driver._create_lun, volume)
        self.m.VerifyAll()

    def testDeleteLun(self):
        volume = self.volume1
        response = {'code': 0, 'message': 'lun deletion started'}
        success_msgs = ['lun deletion started', '']
        self.m.StubOutWithMock(self.driver, '_send_cmd')
        self.m.StubOutWithMock(self.driver.lun_tracker,
                               'free_lun_id_for_volume')
        self.driver._send_cmd(self.m_conn.lun.bulk_delete_luns,
                              success_msgs,
                              self.driver.container,
                              volume['id']).AndReturn(response)
        self.driver.lun_tracker.free_lun_id_for_volume(volume)
        self.m.ReplayAll()
        self.assertTrue(self.driver._delete_lun(volume) is None)
        self.m.VerifyAll()

    def testDeleteLun_EmptyResponseMessage(self):
        volume = self.volume1
        response = {'code': 0, 'message': ''}
        success_msgs = ['lun deletion started', '']
        self.m.StubOutWithMock(self.driver, '_send_cmd')
        self.m.StubOutWithMock(self.driver.lun_tracker,
                               'free_lun_id_for_volume')
        self.driver._send_cmd(self.m_conn.lun.bulk_delete_luns,
                              success_msgs,
                              self.driver.container,
                              volume['id']).AndReturn(response)
        self.driver.lun_tracker.free_lun_id_for_volume(volume)
        self.m.ReplayAll()
        self.assertTrue(self.driver._delete_lun(volume) is None)
        self.m.VerifyAll()

    def testDeleteLun_LunAlreadyDeleted(self):
        volume = self.volume1
        response = {'code': 0, 'message': 'lun deletion started'}
        success_msgs = ['lun deletion started', '']
        self.m.StubOutWithMock(self.driver, '_send_cmd')
        self.m.StubOutWithMock(self.driver.lun_tracker,
                               'free_lun_id_for_volume')
        self.driver._send_cmd(self.m_conn.lun.bulk_delete_luns,
                              success_msgs,
                              self.driver.container,
                              volume['id']
                              ).AndRaise(v6000_common.ViolinBackendErrNotFound)
        self.driver.lun_tracker.free_lun_id_for_volume(volume)
        self.m.ReplayAll()
        self.assertTrue(self.driver._delete_lun(volume) is None)
        self.m.VerifyAll()

    def testDeleteLun_DeleteFailsWithException(self):
        volume = self.volume1
        response = {'code': 0, 'message': 'lun deletion started'}
        success_msgs = ['lun deletion started', '']
        exception = v6000_common.ViolinBackendErr
        self.m.StubOutWithMock(self.driver, '_send_cmd')
        self.driver._send_cmd(self.m_conn.lun.bulk_delete_luns,
                              success_msgs,
                              self.driver.container, volume['id']
                              ).AndRaise(exception('failed!'))
        self.m.ReplayAll()
        self.assertRaises(exception, self.driver._delete_lun, volume)
        self.m.VerifyAll()

    def testCreateLunSnapshot(self):
        snapshot = self.snapshot1
        response = {'code': 0, 'message': 'success'}
        self.m.StubOutWithMock(self.driver, '_send_cmd')
        self.driver._send_cmd(self.m_conn.snapshot.create_lun_snapshot,
                              mox.IsA(str),
                              self.driver.container,
                              snapshot['volume_id'],
                              snapshot['id']).AndReturn(response)
        self.m.ReplayAll()
        self.assertTrue(self.driver._create_lun_snapshot(snapshot) is None)
        self.m.VerifyAll()

    def testDeleteLunSnapshot(self):
        snapshot = self.snapshot1
        response = {'code': 0, 'message': 'success'}
        self.m.StubOutWithMock(self.driver, '_send_cmd')
        self.m.StubOutWithMock(self.driver.lun_tracker,
                               'free_lun_id_for_snapshot')
        self.driver._send_cmd(self.m_conn.snapshot.delete_lun_snapshot,
                              mox.IsA(str),
                              self.driver.container,
                              snapshot['volume_id'],
                              snapshot['id']).AndReturn(response)
        self.driver.lun_tracker.free_lun_id_for_snapshot(snapshot)
        self.m.ReplayAll()
        self.assertTrue(self.driver._delete_lun_snapshot(snapshot) is None)
        self.m.VerifyAll()

    def testSendCmd(self):
        request_func = self.m.CreateMockAnything()
        success_msg = 'success'
        request_args = ['arg1', 'arg2', 'arg3']
        response = {'code': 0, 'message': 'success'}
        request_func(request_args).AndReturn(response)
        self.m.ReplayAll()
        self.assertEqual(self.driver._send_cmd
                         (request_func, success_msg, request_args),
                         response)
        self.m.VerifyAll()

    def testSendCmd_RequestTimedout(self):
        '''The retry timeout is hit.'''
        request_func = self.m.CreateMockAnything()
        success_msg = 'success'
        request_args = ['arg1', 'arg2', 'arg3']
        self.driver.request_timeout = 0
        self.m.ReplayAll()
        self.assertRaises(v6000_common.RequestRetryTimeout,
                          self.driver._send_cmd,
                          request_func, success_msg, request_args)
        self.m.VerifyAll()

    def testSendCmd_ResponseHasNoMessage(self):
        '''The callback response dict has a NULL message field.'''
        request_func = self.m.CreateMockAnything()
        success_msg = 'success'
        request_args = ['arg1', 'arg2', 'arg3']
        response1 = {'code': 0, 'message': None}
        response2 = {'code': 0, 'message': 'success'}
        request_func(request_args).AndReturn(response1)
        request_func(request_args).AndReturn(response2)
        self.m.ReplayAll()
        self.assertEqual(self.driver._send_cmd
                         (request_func, success_msg, request_args),
                         response2)
        self.m.VerifyAll()

    def testSendCmd_ResponseHasFatalError(self):
        '''The callback response dict contains a fatal error code.'''
        request_func = self.m.CreateMockAnything()
        success_msg = 'success'
        request_args = ['arg1', 'arg2', 'arg3']
        response = {'code': 14000, 'message': 'try again later.'}
        request_func(request_args).AndReturn(response)
        self.m.ReplayAll()
        self.assertRaises(v6000_common.ViolinBackendErr,
                          self.driver._send_cmd,
                          request_func, success_msg, request_args)
        self.m.VerifyAll()

    def testGetIgroup(self):
        volume = self.volume1
        connector = {'host': 'h1',
                     'wwpns': [u'50014380186b3f65', u'50014380186b3f67']}
        bn = '/vshare/config/igroup/%s' % connector['host']
        resp = {bn: connector['host']}
        self.m_conn.basic.get_node_values(bn).AndReturn(resp)
        self.m.ReplayAll()
        self.assertEqual(self.driver._get_igroup(volume, connector),
                         connector['host'])
        self.m.VerifyAll()

    def testGetIgroup_WithNewName(self):
        volume = self.volume1
        connector = {'host': 'h1',
                     'wwpns': [u'50014380186b3f65', u'50014380186b3f67']}
        bn = '/vshare/config/igroup/%s' % connector['host']
        resp = {}
        self.m_conn.basic.get_node_values(bn).AndReturn(resp)
        self.m_conn.igroup.create_igroup(connector['host'])
        self.m.ReplayAll()
        self.assertEqual(self.driver._get_igroup(volume, connector),
                         connector['host'])
        self.m.VerifyAll()

    def testGetVolumeTypeExtraSpec(self):
        volume = {'volume_type_id': 1}
        volume_type = {'extra_specs': {'override:test_key': 'test_value'}}
        self.m.StubOutWithMock(context, 'get_admin_context')
        self.m.StubOutWithMock(volume_types, 'get_volume_type')
        context.get_admin_context().AndReturn(None)
        volume_types.get_volume_type(None, 1).AndReturn(volume_type)
        self.m.ReplayAll()
        result = self.driver._get_volume_type_extra_spec(volume, 'test_key')
        self.assertEqual(result, 'test_value')
        self.m.VerifyAll()

    def testGetVolumeTypeExtraSpec_NoVolumeType(self):
        volume = {'volume_type_id': None}
        self.m.StubOutWithMock(context, 'get_admin_context')
        context.get_admin_context().AndReturn(None)
        self.m.ReplayAll()
        result = self.driver._get_volume_type_extra_spec(volume, 'test_key')
        self.assertEqual(result, None)
        self.m.VerifyAll()

    def testGetVolumeTypeExtraSpec_NoExtraSpecs(self):
        volume = {'volume_type_id': 1}
        volume_type = {'extra_specs': {}}
        self.m.StubOutWithMock(context, 'get_admin_context')
        self.m.StubOutWithMock(volume_types, 'get_volume_type')
        context.get_admin_context().AndReturn(None)
        volume_types.get_volume_type(None, 1).AndReturn(volume_type)
        self.m.ReplayAll()
        result = self.driver._get_volume_type_extra_spec(volume, 'test_key')
        self.assertEqual(result, None)
        self.m.VerifyAll()

    def testGetVolumeTypeExtraSpec_NoOverridePrefixInExtraSpecKey(self):
        volume = {'volume_type_id': 1}
        volume_type = {'extra_specs': {'test_key': 'test_value'}}
        self.m.StubOutWithMock(context, 'get_admin_context')
        self.m.StubOutWithMock(volume_types, 'get_volume_type')
        context.get_admin_context().AndReturn(None)
        volume_types.get_volume_type(None, 1).AndReturn(volume_type)
        self.m.ReplayAll()
        result = self.driver._get_volume_type_extra_spec(volume, 'test_key')
        self.assertEqual(result, 'test_value')
        self.m.VerifyAll()

    def testWaitForExportState(self):
        bn = '/vshare/config/export/container/myContainer/lun/vol-01'
        resp = {'/vshare/config/export/container/myContainer/lun/vol-01':
                'vol-01'}
        self.m_conn.basic.get_node_values(bn).AndReturn(resp)
        self.m_conn.basic.get_node_values(bn).AndReturn(resp)
        self.m.ReplayAll()
        self.assertTrue(self.driver._wait_for_exportstate('vol-01', True))
        self.m.VerifyAll()

    def testWaitForExportState_NoState(self):
        self.m_conn.basic.get_node_values(mox.IsA(str)).AndReturn({})
        self.m_conn.basic.get_node_values(mox.IsA(str)).AndReturn({})
        self.m.ReplayAll()
        self.assertTrue(self.driver._wait_for_exportstate("vol-01", False))
        self.m.VerifyAll()

    def test_is_supported_vmos_version(self):
        version = 'V6.3.1'
        self.assertTrue(self.driver._is_supported_vmos_version(version))

    def testIsSupportedVMOSVersion_SupportedFutureVersion(self):
        version = 'V6.3.7'
        self.assertTrue(self.driver._is_supported_vmos_version(version))

    def testIsSupportedVmosVersion_UnsupportedPastVMOSVersion(self):
        version = 'G5.5.2'
        self.assertFalse(self.driver._is_supported_vmos_version(version))

    def testIsSupportedVMOSVersion_UnsupportedFutureVersion(self):
        version = 'V7.0.0'
        self.assertFalse(self.driver._is_supported_vmos_version(version))

    def testFatalErrorCode(self):
        # NYI
        #
        pass
