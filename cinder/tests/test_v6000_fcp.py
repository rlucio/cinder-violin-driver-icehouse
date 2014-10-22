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
Violin Memory tests for FCP driver

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
from cinder.db.sqlalchemy import models

from cinder.volume.drivers.violin.vxg.core.session import XGSession
from cinder.volume.drivers.violin.vxg.vshare.igroup import IGroupManager
from cinder.volume.drivers.violin.vxg.vshare.iscsi import ISCSIManager
from cinder.volume.drivers.violin.vxg.vshare.lun import LUNManager
from cinder.volume.drivers.violin.vxg.vshare.snapshot import SnapshotManager
from cinder.volume.drivers.violin.vxg.vshare.vshare import VShare

from cinder.volume import configuration as conf
from cinder.volume.drivers.violin import v6000_common
from cinder.volume.drivers.violin import v6000_fcp as violin


class testV6000FC(unittest.TestCase):
    """A test class for the violin Fibrechannel driver module."""
    def setUp(self):
        self.m = mox.Mox()
        self.m_conn = self.m.CreateMock(VShare)
        self.m_conn.basic = self.m.CreateMock(XGSession)
        self.m_conn.lun = self.m.CreateMock(LUNManager)
        self.m_conn.iscsi = self.m.CreateMock(ISCSIManager)
        self.m_conn.igroup = self.m.CreateMock(IGroupManager)
        self.m_conn.snapshot = self.m.CreateMock(SnapshotManager)
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
        self.driver = violin.V6000FCDriver(configuration=self.config)
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
        self.m.StubOutWithMock(v6000_common.V6000CommonDriver, 'check_for_setup_error')
        v6000_common.V6000CommonDriver.check_for_setup_error()
        self.m.ReplayAll()
        self.assertTrue(self.driver.check_for_setup_error() is None)
        self.m.VerifyAll()

    def testCheckForSetupError_NoWWNConfig(self):
        '''No wwns were found during setup.'''
        self.driver.gateway_fc_wwns = []
        self.m.StubOutWithMock(v6000_common.V6000CommonDriver, 'check_for_setup_error')
        v6000_common.V6000CommonDriver.check_for_setup_error()
        self.m.ReplayAll()
        self.assertRaises(v6000_common.InvalidBackendConfig,
                          self.driver.check_for_setup_error)
        self.m.VerifyAll()

    def testEnsureExport(self):
        # nothing to test here
        #
        pass

    def testCreateExport(self):
        # nothing to test here
        #
        pass

    def testRemoveExport(self):
        # nothing to test here
        #
        pass

    def testInitializeConnection(self):
        lun_id = 1
        vol = self.volume1
        igroup = None
        connector = {'host': 'h1',
                     'wwpns': [u'50014380186b3f65', u'50014380186b3f67']}
        self.m.StubOutWithMock(self.driver, '_export_lun')
        self.driver._export_lun(vol, connector, igroup).AndReturn(lun_id)
        self.m_conn.basic.save_config()
        self.m.ReplayAll()
        props = self.driver.initialize_connection(vol, connector)
        self.assertEqual(props['driver_volume_type'], "fibre_channel")
        self.assertEqual(props['data']['target_discovered'], True)
        self.assertEqual(props['data']['target_wwn'],
                         self.driver.gateway_fc_wwns)
        self.assertEqual(props['data']['target_lun'], lun_id)
        self.m.VerifyAll()

    def testInitializeConnection_SnapshotObject(self):
        lun_id = 1
        igroup = None
        snap = self.snapshot1
        connector = {'host': 'h1',
                     'wwpns': [u'50014380186b3f65', u'50014380186b3f67']}
        self.m.StubOutWithMock(self.driver, '_export_snapshot')
        self.driver._export_snapshot(snap, connector, igroup).AndReturn(lun_id)
        self.m_conn.basic.save_config()
        self.m.ReplayAll()
        props = self.driver.initialize_connection(snap, connector)
        self.assertEqual(props['driver_volume_type'], "fibre_channel")
        self.assertEqual(props['data']['target_discovered'], True)
        self.assertEqual(props['data']['target_wwn'],
                         self.driver.gateway_fc_wwns)
        self.assertEqual(props['data']['target_lun'], lun_id)
        self.m.VerifyAll()

    def testTerminateConnection(self):
        volume = self.volume1
        connector = {'wwpns': [u'50014380186b3f65', u'50014380186b3f67']}
        self.m.StubOutWithMock(self.driver, '_unexport_lun')
        self.driver._unexport_lun(volume)
        self.m_conn.basic.save_config()
        self.m.ReplayAll()
        self.driver.terminate_connection(volume, connector)
        self.m.VerifyAll()

    def testTerminateConnection_SnapshotObject(self):
        snap = self.snapshot1
        connector = {'wwpns': [u'50014380186b3f65', u'50014380186b3f67']}
        self.m.StubOutWithMock(self.driver, '_unexport_snapshot')
        self.driver._unexport_snapshot(snap)
        self.m_conn.basic.save_config()
        self.m.ReplayAll()
        self.driver.terminate_connection(snap, connector)
        self.m.VerifyAll()

    def testGetVolumeStats(self):
        self.m.StubOutWithMock(self.driver, '_update_stats')
        self.driver._update_stats()
        self.m.ReplayAll()
        self.assertEqual(self.driver.get_volume_stats(True), self.driver.stats)
        self.m.VerifyAll()

    def testExportLun(self):
        volume = self.volume1
        lun_id = '1'
        igroup = 'test-igroup-1'
        connector = {'wwpns': [u'50014380186b3f65', u'50014380186b3f67']}
        response = {'code': 0, 'message': ''}
        self.m.StubOutWithMock(self.driver.lun_tracker,
                               'get_lun_id_for_volume')
        self.m.StubOutWithMock(self.driver, '_send_cmd_and_verify')
        self.driver.lun_tracker.get_lun_id_for_volume(volume).AndReturn(lun_id)
        self.driver._send_cmd_and_verify(self.m_conn.lun.export_lun,
                                         self.driver._wait_for_exportstate,
                                         mox.IsA(str),
                                         [self.driver.container, volume['id'],
                                          'all', igroup, lun_id],
                                         [volume['id'], True]
                                         ).AndReturn(response)
        self.m.ReplayAll()
        self.assertEqual(self.driver._export_lun(volume, connector, igroup),
                         lun_id)
        self.m.VerifyAll()

    def testExportLun_ExportFailsWithException(self):
        volume = self.volume1
        lun_id = '1'
        igroup = 'test-igroup-1'
        connector = {'wwpns': [u'50014380186b3f65', u'50014380186b3f67']}
        response = {'code': 0, 'message': ''}
        exception = v6000_common.ViolinBackendErr
        self.m.StubOutWithMock(self.driver.lun_tracker,
                               'get_lun_id_for_volume')
        self.m.StubOutWithMock(self.driver, '_send_cmd_and_verify')
        self.driver.lun_tracker.get_lun_id_for_volume(volume).AndReturn(lun_id)
        self.driver._send_cmd_and_verify(self.m_conn.lun.export_lun,
                                         self.driver._wait_for_exportstate,
                                         mox.IsA(str),
                                         [self.driver.container, volume['id'],
                                          'all', igroup, lun_id],
                                         [volume['id'], True]
                                         ).AndRaise(exception('failed!'))
        self.m.ReplayAll()
        self.assertRaises(exception, self.driver._export_lun, volume,
                          connector, igroup)
        self.m.VerifyAll()

    def testUnexportLun(self):
        volume = self.volume1
        response = {'code': 0, 'message': ''}
        self.m.StubOutWithMock(self.driver, '_send_cmd_and_verify')
        self.driver._send_cmd_and_verify(
            self.m_conn.lun.unexport_lun,
            self.driver._wait_for_exportstate,
            mox.IsA(str),
            [self.driver.container, volume['id'],
             'all', 'all', 'auto'],
            [volume['id'], False]).AndReturn(response)
        self.m.ReplayAll()
        self.assertTrue(self.driver._unexport_lun(volume) is None)
        self.m.VerifyAll()

    def testUnexportLun_UnexportFailsWithException(self):
        volume = self.volume1
        response = {'code': 0, 'message': ''}
        exception = v6000_common.ViolinBackendErr
        self.m.StubOutWithMock(self.driver, '_send_cmd_and_verify')
        self.driver._send_cmd_and_verify(self.m_conn.lun.unexport_lun,
                                         self.driver._wait_for_exportstate,
                                         mox.IsA(str),
                                         [self.driver.container, volume['id'],
                                          'all', 'all', 'auto'],
                                         [volume['id'], False]
                                         ).AndRaise(exception('failed!'))
        self.m.ReplayAll()
        self.assertRaises(exception, self.driver._unexport_lun, volume)
        self.m.VerifyAll()

    # TODO(rdl) missing tests
    #def testExportSnapshot(self):
    #def testUnExportSnapshot(self):

    def testAddIgroupMember(self):
        volume = self.volume1
        igroup = 'test-group-1'
        connector = {'wwpns': [u'50014380186b3f65', u'50014380186b3f67']}
        wwpns = ['wwn.50:01:43:80:18:6b:3f:65', 'wwn.50:01:43:80:18:6b:3f:67']
        response = {'code': 0, 'message': 'success'}
        self.m.StubOutWithMock(self.driver, '_convert_wwns_openstack_to_vmem')
        self.driver._convert_wwns_openstack_to_vmem(
            connector['wwpns']).AndReturn(wwpns)
        self.m_conn.igroup.add_initiators(igroup,
                                          wwpns).AndReturn(response)
        self.m.ReplayAll()
        self.assertTrue(self.driver._add_igroup_member(connector, igroup)
                        is None)
        self.m.VerifyAll()

    def testUpdateStats(self):
        backend_name = self.config.volume_backend_name
        vendor_name = "Violin Memory, Inc."
        tot_bytes = 100 * 1024 * 1024 * 1024
        free_bytes = 50 * 1024 * 1024 * 1024
        bn0 = '/cluster/state/master_id'
        resp0 = {'/cluster/state/master_id': '1'}
        bn1 = "/vshare/state/global/1/container/myContainer/total_bytes"
        bn2 = "/vshare/state/global/1/container/myContainer/free_bytes"
        response = {bn1: tot_bytes, bn2: free_bytes}
        self.m_conn.basic.get_node_values(bn0).AndReturn(resp0)
        self.m_conn.basic.get_node_values([bn1, bn2]).AndReturn(response)
        self.m.ReplayAll()
        self.assertTrue(self.driver._update_stats() is None)
        self.assertEqual(self.driver.stats['total_capacity_gb'], 100)
        self.assertEqual(self.driver.stats['free_capacity_gb'], 50)
        self.assertEqual(self.driver.stats['volume_backend_name'],
                         backend_name)
        self.assertEqual(self.driver.stats['vendor_name'], vendor_name)
        self.m.VerifyAll()

    def testUpdateStats_DataQueryFails(self):
        backend_name = self.config.volume_backend_name
        vendor_name = "Violin Memory, Inc."
        bn0 = '/cluster/state/master_id'
        resp0 = {'/cluster/state/master_id': '1'}
        bn1 = "/vshare/state/global/1/container/myContainer/total_bytes"
        bn2 = "/vshare/state/global/1/container/myContainer/free_bytes"
        self.m_conn.basic.get_node_values(bn0).AndReturn(resp0)
        self.m_conn.basic.get_node_values([bn1, bn2]).AndReturn({})
        self.m.ReplayAll()
        self.assertTrue(self.driver._update_stats() is None)
        self.assertEqual(self.driver.stats['total_capacity_gb'], "unknown")
        self.assertEqual(self.driver.stats['free_capacity_gb'], "unknown")
        self.assertEqual(self.driver.stats['volume_backend_name'],
                         backend_name)
        self.assertEqual(self.driver.stats['vendor_name'], vendor_name)
        self.m.VerifyAll()

    def testGetActiveFcTargets(self):
        bn0 = '/vshare/state/global/*'
        resp0 = {'/vshare/state/global/1': 1,
                 '/vshare/state/global/2': 2}
        bn1 = '/vshare/state/global/1/target/fc/**'
        resp1 = {'/vshare/state/global/1/target/fc/hba-a1/wwn':
                 'wwn.21:00:00:24:ff:45:fb:22'}
        bn2 = '/vshare/state/global/2/target/fc/**'
        resp2 = {'/vshare/state/global/2/target/fc/hba-a1/wwn':
                 'wwn.21:00:00:24:ff:45:e2:30'}
        self.m_conn.basic.get_node_values(bn0).AndReturn(resp0)
        self.m_conn.basic.get_node_values(bn2).AndReturn(resp2)
        self.m_conn.basic.get_node_values(bn1).AndReturn(resp1)
        result = ['21000024ff45e230', '21000024ff45fb22']
        self.m.ReplayAll()
        self.assertEqual(self.driver._get_active_fc_targets(), result)
        self.m.VerifyAll()

    def testConvertWWNsOpenstackToVMEM(self):
        vmem_wwns = ['wwn.50:01:43:80:18:6b:3f:65']
        openstack_wwns = ['50014380186b3f65']
        result = self.driver._convert_wwns_openstack_to_vmem(openstack_wwns)
        self.assertEqual(result, vmem_wwns)

    def testsConvertWWNsVMEMToOpenstack(self):
        vmem_wwns = ['wwn.50:01:43:80:18:6b:3f:65']
        openstack_wwns = ['50014380186b3f65']
        result = self.driver._convert_wwns_vmem_to_openstack(vmem_wwns)
        self.assertEqual(result, openstack_wwns)
