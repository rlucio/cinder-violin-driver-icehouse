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

"""
Violin Memory tests for iSCSI driver

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

from cinder.db.sqlalchemy import models

# TODO(rlucio): workaround for gettext '_' not defined bug, must be done before
# importing any cinder libraries.  This should be removed when the bug is
# fixed.
import gettext
gettext.install("cinder", unicode=1)

from cinder.volume.drivers.violin.vxg.core.session import XGSession
from cinder.volume.drivers.violin.vxg.vshare.igroup import IGroupManager
from cinder.volume.drivers.violin.vxg.vshare.iscsi import ISCSIManager
from cinder.volume.drivers.violin.vxg.vshare.lun import LUNManager
from cinder.volume.drivers.violin.vxg.vshare.snapshot import SnapshotManager
from cinder.volume.drivers.violin.vxg.vshare.vshare import VShare

from cinder.volume import configuration as conf
from cinder.volume.drivers.violin import v6000_common
from cinder.volume.drivers.violin import v6000_iscsi as violin


class testViolin(unittest.TestCase):
    """A test class for the violin driver module."""
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
        self.config.use_thin_luns = False
        self.config.use_igroups = False
        self.config.volume_backend_name = 'violin'
        self.config.gateway_iscsi_target_prefix = 'iqn.2004-02.com.vmem:'
        self.config.san_is_local = False
        self.driver = violin.V6000ISCSIDriver(configuration=self.config)
        self.driver.vmem_vip = self.m_conn
        self.driver.vmem_mga = self.m_conn
        self.driver.vmem_mgb = self.m_conn
        self.driver.container = 'myContainer'
        self.driver.gateway_iscsi_ip_addresses_mga = '1.2.3.4'
        self.driver.gateway_iscsi_ip_addresses_mgb = '1.2.3.4'
        self.driver.array_info = [{"node": 'hostname_mga',
                                   "addr": '1.2.3.4',
                                   "conn": self.driver.vmem_mga},
                                  {"node": 'hostname_mgb',
                                   "addr": '1.2.3.4',
                                   "conn": self.driver.vmem_mgb}]
        self.volume1 = mox.MockObject(models.Volume)
        self.volume1.id = '3d31af29-6d7d-443f-b451-6f0040d3c9a9'
        self.volume1.size = 1
        self.volume2 = mox.MockObject(models.Volume)
        self.volume2.id = '4c1af784-b328-43d2-84c8-db02158b922d'
        self.volume2.size = 2
        self.snapshot1 = mox.MockObject(models.Snapshot)
        self.snapshot1.snapshot_id = 'f8849c41-6d72-4f5a-8339-2cd6b52b5e5a'
        self.snapshot1.volume_id = 1
        self.snapshot2 = mox.MockObject(models.Snapshot)
        self.snapshot2.snapshot_id = '23e44fad-8840-46f1-99d3-5605a08fb289'
        self.snapshot2.volume_id = 2

    def tearDown(self):
        self.m.UnsetStubs()

    def testCheckForSetupError(self):
        bn_enable = {"/vshare/config/iscsi/enable": True}
        self.m.StubOutWithMock(v6000_common.V6000CommonDriver, 'check_for_setup_error')
        v6000_common.V6000CommonDriver.check_for_setup_error()
        self.m_conn.basic.get_node_values(mox.IsA(str)
                                          ).AndReturn(bn_enable)
        self.m.ReplayAll()
        self.assertTrue(self.driver.check_for_setup_error() is None)
        self.m.VerifyAll()

    def testCheckForSetupError_IscsiDisabled(self):
        '''iscsi is disabled.'''
        bn_enable = {"/vshare/config/iscsi/enable": False}
        self.m.StubOutWithMock(v6000_common.V6000CommonDriver, 'check_for_setup_error')
        v6000_common.V6000CommonDriver.check_for_setup_error()
        self.m_conn.basic.get_node_values(mox.IsA(str)
                                          ).AndReturn(bn_enable)
        self.m.ReplayAll()
        self.assertRaises(v6000_common.InvalidBackendConfig,
                          self.driver.check_for_setup_error)
        self.m.VerifyAll()

    def testCheckForSetupError_NoIscsiIPsMga(self):
        '''iscsi interface binding for mg-a is empty.'''
        self.driver.gateway_iscsi_ip_addresses_mga = ''
        bn_enable = {"/vshare/config/iscsi/enable": True}
        self.m.StubOutWithMock(v6000_common.V6000CommonDriver, 'check_for_setup_error')
        v6000_common.V6000CommonDriver.check_for_setup_error()
        self.m_conn.basic.get_node_values(mox.IsA(str)).AndReturn(bn_enable)
        self.m.ReplayAll()
        self.assertRaises(v6000_common.InvalidBackendConfig,
                          self.driver.check_for_setup_error)
        self.m.VerifyAll()

    def testCheckForSetupError_NoIscsiIPsMgb(self):
        '''iscsi interface binding for mg-a is empty.'''
        self.driver.gateway_iscsi_ip_addresses_mgb = ''
        bn_enable = {"/vshare/config/iscsi/enable": True}
        self.m.StubOutWithMock(v6000_common.V6000CommonDriver, 'check_for_setup_error')
        v6000_common.V6000CommonDriver.check_for_setup_error()
        self.m_conn.basic.get_node_values(mox.IsA(str)).AndReturn(bn_enable)
        self.m.ReplayAll()
        self.assertRaises(v6000_common.InvalidBackendConfig,
                          self.driver.check_for_setup_error)
        self.m.VerifyAll()

    def testInitializeConnection(self):
        igroup = None
        volume  = self.volume1;
        connector = {'initiator': 'iqn.1993-08.org.debian:8d3a79542d'}
        vol = volume['id']
        tgt = self.driver.array_info[0]
        lun = 1
        self.m.StubOutWithMock(self.driver, '_get_short_name')
        self.m.StubOutWithMock(self.driver, '_create_iscsi_target')
        self.m.StubOutWithMock(self.driver, '_export_lun')
        self.driver._get_short_name(volume['id']).AndReturn("3d31af29-6d7d-443f-b451-6f0040d3c9a9")
        self.driver._create_iscsi_target(volume).AndReturn(tgt)
        self.driver._export_lun(volume, connector, igroup).AndReturn(lun)
        self.m_conn.basic.save_config()
        self.m.ReplayAll()
        props = self.driver.initialize_connection(volume, connector)
        self.assertEqual(props['data']['target_portal'], "1.2.3.4:3260")

        #self.assertEqual(props['data']['target_iqn'],
        #                 "iqn.2004-02.com.vmem:hostname_mga:12345678901234567890123456789012")
        self.assertEqual(props['data']['target_lun'], lun)
        #self.assertEqual(props['data']['volume_id'], "3d31af29-6d7d-443f-b451-6f0040d3c9a9")
        self.m.VerifyAll()

    def testInitializeConnection_SnapshotObject(self):
        lun_id = 1
        igroup = None
        snap = self.snapshot1
        tgt = self.driver.array_info[0]
        connector = {'initiator': 'iqn.1993-08.org.debian:8d3a79542d'}
        self.m.StubOutWithMock(self.driver, '_get_short_name')
        self.m.StubOutWithMock(self.driver, '_create_iscsi_target')
        self.m.StubOutWithMock(self.driver, '_export_snapshot')
        self.driver._get_short_name(snap['id']).AndReturn("f8849c41-6d72-4f5a-8339-2cd6b52b5e5a")
        self.driver._create_iscsi_target(snap).AndReturn(tgt)
        self.driver._export_snapshot(snap, connector, igroup).AndReturn(lun_id)
        self.m_conn.basic.save_config()
        self.m.ReplayAll()
        props = self.driver.initialize_connection(snap, connector)
        self.assertEqual(props['data']['target_portal'], "1.2.3.4:3260")
        #self.assertEqual(props['data']['target_iqn'],
        #                 "iqn.2004-02.com.vmem:hostname_mga:12345")
        self.assertEqual(props['data']['target_lun'], lun_id)
        #self.assertEqual(props['data']['volume_id'], "12345")
        self.m.VerifyAll()


    def testInitializeConnection_WithIgroupsEnabled(self):
        self.config.use_igroups = True
        igroup = 'test-igroup-1'
        volume = self.volume1
        connector = {'initiator': 'iqn.1993-08.org.debian:8d3a79542d'}
        vol = volume['id']
        tgt = self.driver.array_info[0]
        lun = 1
        self.m.StubOutWithMock(self.driver, '_get_igroup')
        self.m.StubOutWithMock(self.driver, '_add_igroup_member')
        self.m.StubOutWithMock(self.driver, '_get_short_name')
        self.m.StubOutWithMock(self.driver, '_create_iscsi_target')
        self.m.StubOutWithMock(self.driver, '_export_lun')
        self.driver._get_igroup(volume, connector).AndReturn(igroup)
        self.driver._add_igroup_member(connector, igroup)
        self.driver._get_short_name(volume['id']).AndReturn("3d31af29-6d7d-443f-b451-6f0040d3c9a9")
        self.driver._create_iscsi_target(volume).AndReturn(tgt)
        self.driver._export_lun(volume, connector, igroup).AndReturn(lun)
        self.m_conn.basic.save_config()
        self.m.ReplayAll()
        props = self.driver.initialize_connection(volume, connector)
        self.assertEqual(props['data']['target_portal'], "1.2.3.4:3260")
        #self.assertEqual(props['data']['target_iqn'],
        #                 "iqn.2004-02.com.vmem:hostname_mga:12345")
        self.assertEqual(props['data']['target_lun'], lun)
        #self.assertEqual(props['data']['volume_id'], "12345")
        self.m.VerifyAll()

    def testTerminateConnection(self):
        volume = self.volume1
        connector = {'initiator': 'iqn.1993-08.org.debian:8d3a79542d'}
        self.m.StubOutWithMock(self.driver, '_unexport_lun')
        self.m.StubOutWithMock(self.driver, '_delete_iscsi_target')
        self.driver._unexport_lun(volume)
        self.driver._delete_iscsi_target(volume)
        self.m_conn.basic.save_config()
        self.m.ReplayAll()
        self.driver.terminate_connection(volume, connector)
        self.m.VerifyAll()


    def testTerminateConnection_SnapshotObject(self):
        snap = self.snapshot1
        connector = {'initiator': 'iqn.1993-08.org.debian:8d3a79542d'}
        self.m.StubOutWithMock(self.driver, '_unexport_snapshot')
        self.m.StubOutWithMock(self.driver, '_delete_iscsi_target')
        self.driver._delete_iscsi_target(snap)
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

    def testCreateIscsiTarget(self):
        volume = {'id': 'vol-01', 'size': '1'}
        target_name = volume['id']
        response = {'code': 0, 'message': 'success'}
        self.m.StubOutWithMock(self.driver, '_get_short_name')
        self.m.StubOutWithMock(self.driver, '_send_cmd')
        self.m.StubOutWithMock(self.driver, '_send_cmd_and_verify')
        self.driver._get_short_name(mox.IsA(str)).AndReturn(volume['id'])
        self.driver._send_cmd_and_verify(self.m_conn.iscsi.create_iscsi_target,
                                         self.driver._wait_for_targetstate,
                                         '', [target_name], [target_name]
                                         ).AndReturn(response)
        self.driver._send_cmd(self.m_conn.iscsi.bind_ip_to_target,
                              mox.IsA(str), mox.IsA(str),
                              mox.IsA(str)).AndReturn(response)
        self.driver._send_cmd(self.m_conn.iscsi.bind_ip_to_target,
                              mox.IsA(str), mox.IsA(str),
                              mox.IsA(str)).AndReturn(response)
        self.m.ReplayAll()
        self.assertTrue(self.driver._create_iscsi_target(volume) in
                        self.driver.array_info)
        self.m.VerifyAll()

    def testDeleteIscsiTarget(self):
        volume = {'id': 'vol-01', 'size': '1'}
        response = {'code': 0, 'message': 'success'}
        self.m.StubOutWithMock(self.driver, '_get_short_name')
        self.m.StubOutWithMock(self.driver, '_send_cmd')
        self.driver._get_short_name(mox.IsA(str)).AndReturn(volume['id'])
        self.driver._send_cmd(self.m_conn.iscsi.delete_iscsi_target,
                              mox.IsA(str), mox.IsA(str)).AndReturn(response)
        self.m.ReplayAll()
        self.assertTrue(self.driver._delete_iscsi_target(volume) is None)
        self.m.VerifyAll()

    def testDeleteIscsiTarget_TargetDeleteFailsWithException(self):
        volume = {'id': 'vol-01', 'size': '1'}
        response = {'code': 0, 'message': 'success'}
        exception = v6000_common.ViolinBackendErr
        self.m.StubOutWithMock(self.driver, '_get_short_name')
        self.m.StubOutWithMock(self.driver, '_send_cmd')
        self.driver._get_short_name(mox.IsA(str)).AndReturn(volume['id'])
        self.driver._send_cmd(self.m_conn.iscsi.delete_iscsi_target,
                              mox.IsA(str), mox.IsA(str)
                              ).AndRaise(exception('failed!'))
        self.m.ReplayAll()
        self.assertRaises(exception, self.driver._delete_iscsi_target, volume)
        self.m.VerifyAll()

    def testExportLun(self):
        volume = {'id': 'vol-01', 'size': '1'}
        igroup = 'test-igroup-1'
        lun_id = '1'
        response = {'code': 0, 'message': ''}
        connector = {'initiator': 'iqn.1993-08.org.debian:8d3a79542d'}
        self.m.StubOutWithMock(self.driver, '_get_short_name')
        self.m.StubOutWithMock(self.driver.lun_tracker, 'get_lun_id_for_volume')
        self.m.StubOutWithMock(self.driver, '_send_cmd_and_verify')
        self.driver._get_short_name(mox.IsA(str)).AndReturn(volume['id'])
        self.driver.lun_tracker.get_lun_id_for_volume(volume).AndReturn(lun_id)
        self.driver._send_cmd_and_verify(self.m_conn.lun.export_lun,
                                         self.driver._wait_for_exportstate,
                                         mox.IsA(str),
                                         [self.driver.container, volume['id'],
                                         volume['id'], igroup, lun_id],
                                         [volume['id'], True]
                                         ).AndReturn(lun_id)
        self.m.ReplayAll()
        self.assertEqual(self.driver._export_lun(volume, connector, igroup),lun_id)
        self.m.VerifyAll()

    def testExportLun_ExportFailsWithException(self):
        volume = {'id': 'vol-01', 'size': '1'}
        igroup = 'test-igroup-1'
        lun_id = '1'
        response = {'code': 0, 'message': ''}
        connector = {'initiator': 'iqn.1993-08.org.debian:8d3a79542d'}
        exception = v6000_common.ViolinBackendErr
        self.m.StubOutWithMock(self.driver, '_get_short_name')
        self.m.StubOutWithMock(self.driver, '_send_cmd_and_verify')
        self.m.StubOutWithMock(self.driver.lun_tracker,
                               'get_lun_id_for_volume')
        self.driver._get_short_name(mox.IsA(str)).AndReturn(volume['id'])
        self.driver.lun_tracker.get_lun_id_for_volume(volume).AndReturn(lun_id)
        self.driver._send_cmd_and_verify(self.m_conn.lun.export_lun,
                              self.driver._wait_for_exportstate,
                              mox.IsA(str),
                              [self.driver.container, volume['id'],
                              volume['id'], igroup, lun_id],
                              [volume['id'], True]
                              ).AndRaise(exception('failed!'))
        self.m.ReplayAll()
        self.assertRaises(exception, self.driver._export_lun, volume,
                          connector, igroup)
        self.m.VerifyAll()

    def testUnexportLun(self):
        volume = {'id': 'vol-01', 'size': '1'}
        lun_id = 1
        response = {'code': 0, 'message': ''}
        self.m.StubOutWithMock(self.driver, '_send_cmd_and_verify')
        self.driver._send_cmd_and_verify(self.m_conn.lun.unexport_lun,
                              self.driver._wait_for_exportstate,
                              mox.IsA(str),
                              [self.driver.container, volume['id'],
                              'all', 'all', 'auto'],
                              [volume['id'], False]).AndReturn(response)
        self.m.ReplayAll()
        self.assertTrue(self.driver._unexport_lun(volume) is None)
        self.m.VerifyAll()

    def testUnexportLun_UnexportFailsWithException(self):
        volume = {'id': 'vol-01', 'size': '1'}
        lun_id = 1
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

    def testAddIgroupMember(self):
        igroup = 'test-group-1'
        connector = {'initiator': 'foo'}
        response = {'code': 0, 'message': 'success'}
        self.m_conn.igroup.add_initiators(mox.IsA(str),
                                          mox.IsA(str)).AndReturn(response)
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

    def testGetLunID(self):
        volume = {'id': 'vol-01', 'size': '1'}
        bn = '/vshare/config/export/container/myContainer/lun/vol-01/target/**'
        resp = {'/vshare/config/export/container/myContainer/lun'
                '/vol-01/target/hba-a1/initiator/openstack/lun_id': 1}
        self.m_conn.basic.get_node_values(bn).AndReturn(resp)
        self.m.ReplayAll()
        self.assertEqual(self.driver._get_lun_id(volume['id']), 1)
        self.m.VerifyAll()

    def testGetLunID_NoLunConfig(self):
        volume = {'id': 'vol-01', 'size': '1'}
        bn = '/vshare/config/export/container/myContainer/lun/vol-01/target/**'
        resp = {}
        self.m_conn.basic.get_node_values(bn).AndReturn(resp)
        self.m.ReplayAll()
        self.assertEqual(self.driver._get_lun_id(volume['id']), -1)
        self.m.VerifyAll()

    def testWaitForTargetState(self):
        target = 'mytarget'
        bn = "/vshare/config/iscsi/target/%s" % target
        resp = {bn: target}
        self.m_conn.basic.get_node_values(bn).AndReturn(resp)
        self.m_conn.basic.get_node_values(bn).AndReturn(resp)
        self.m.ReplayAll()
        self.assertTrue(self.driver._wait_for_targetstate(target))
        self.m.VerifyAll()

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

    def testGetActiveIscsiIPs(self):
        request = ["/net/interface/state/eth4/addr/ipv4/1/ip",
                   "/net/interface/state/eth4/flags/link_up"]
        response1 = {"/net/interface/config/eth4": "eth4"}
        response2 = {"/net/interface/state/eth4/addr/ipv4/1/ip": "1.1.1.1",
                     "/net/interface/state/eth4/flags/link_up": True}
        self.m_conn.basic.get_node_values(mox.IsA(str)).AndReturn(response1)
        self.m_conn.basic.get_node_values(request).AndReturn(response2)
        self.m.ReplayAll()
        ips = self.driver._get_active_iscsi_ips(self.m_conn)
        self.assertEqual(len(ips), 1)
        self.assertEqual(ips[0], "1.1.1.1")
        self.m.VerifyAll()

    def testGetActiveIscsiIPs_InvalidIntfs(self):
        response = {"/net/interface/config/lo": "lo",
                    "/net/interface/config/vlan10": "vlan10",
                    "/net/interface/config/eth1": "eth1",
                    "/net/interface/config/eth2": "eth2",
                    "/net/interface/config/eth3": "eth3"}
        self.m_conn.basic.get_node_values(mox.IsA(str)).AndReturn(response)
        self.m.ReplayAll()
        ips = self.driver._get_active_iscsi_ips(self.m_conn)
        self.assertEqual(len(ips), 0)
        self.m.VerifyAll()

    def testGetActiveIscsiIps_NoIntfs(self):
        self.m_conn.basic.get_node_values(mox.IsA(str)).AndReturn({})
        self.m.ReplayAll()
        ips = self.driver._get_active_iscsi_ips(self.m_conn)
        self.assertEqual(len(ips), 0)
        self.m.VerifyAll()

    def testGetHostname(self):
        response = {"/system/hostname": "MYHOST"}
        self.m_conn.basic.get_node_values(mox.IsA(str)).AndReturn(response)
        self.m.ReplayAll()
        self.assertEqual(self.driver._get_hostname(None), "MYHOST")
        self.m.VerifyAll()

    def testGetHostname_QueryFails(self):
        self.m_conn.basic.get_node_values(mox.IsA(str)).AndReturn({})
        self.m.ReplayAll()
        self.assertEqual(self.driver._get_hostname(None),
                         self.driver.config.gateway_vip)
        self.m.VerifyAll()

    def testGetHostname_Mga(self):
        response = {"/system/hostname": "MYHOST"}
        self.m_conn.basic.get_node_values(mox.IsA(str)).AndReturn(response)
        self.m.ReplayAll()
        self.assertEqual(self.driver._get_hostname('mga'), "MYHOST")
        self.m.VerifyAll()

    def testGetHostName_MgaQueryFails(self):
        self.m_conn.basic.get_node_values(mox.IsA(str)).AndReturn({})
        self.m.ReplayAll()
        self.assertEqual(self.driver._get_hostname('mga'),
                         self.driver.config.gateway_mga)
        self.m.VerifyAll()

    def testGetHostname_Mgb(self):
        response = {"/system/hostname": "MYHOST"}
        self.m_conn.basic.get_node_values(mox.IsA(str)).AndReturn(response)
        self.m.ReplayAll()
        self.assertEqual(self.driver._get_hostname('mgb'), "MYHOST")
        self.m.VerifyAll()

    def testGetHostName_MgbQueryFails(self):
        self.m_conn.basic.get_node_values(mox.IsA(str)).AndReturn({})
        self.m.ReplayAll()
        self.assertEqual(self.driver._get_hostname('mgb'),
                         self.driver.config.gateway_mgb)
        self.m.VerifyAll()
