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
Violin Memory 6000 Series All-Flash Array Common Driver for Openstack Cinder

Uses Violin REST API via XG-Tools to manage a standard V6000 series
flash array to provide network block-storage services.

by Ryan Lucio
Senior Software Engineer
Violin Memory
"""

import re
import time

from oslo.config import cfg

from cinder import context
from cinder import exception
from cinder.openstack.common import log as logging
from cinder import utils
from cinder.volume.drivers.san import san
from cinder.volume import volume_types

LOG = logging.getLogger(__name__)

# support vmos versions V6.3.0.4 or newer
# support vmos versions V6.3.1 or newer
VMOS_SUPPORTED_VERSION_PATTERNS = ['V6.3.0.[4-9]', 'V6.3.[1-9].?[0-9]?']

try:
    import vxg
except ImportError:
    LOG.exception(
        _("The Violin V6000 driver for Cinder requires the presence of "
          "the Violin 'XG-Tools', python libraries for facilitating "
          "communication between applications and the v6000 XML API. "
          "The libraries can be downloaded from the Violin Memory "
          "support website at http://www.violin-memory.com/support"))
    raise
else:
    LOG.info(_("Running with xg-tools version: %s"), vxg.__version__)

violin_opts = [
    cfg.StrOpt('gateway_vip',
               default='',
               help='IP address or hostname of the v6000 master VIP'),
    cfg.StrOpt('gateway_mga',
               default='',
               help='IP address or hostname of mg-a'),
    cfg.StrOpt('gateway_mgb',
               default='',
               help='IP address or hostname of mg-b'),
    cfg.StrOpt('gateway_user',
               default='admin',
               help='User name for connecting to the Memory Gateway'),
    cfg.StrOpt('gateway_password',
               default='',
               help='User name for connecting to the Memory Gateway',
               secret=True),
    cfg.BoolOpt('use_igroups',
                default=False,
                help='Use igroups to manage targets and initiators'),
    cfg.BoolOpt('use_thin_luns',
                default=False,
                help='Use thin luns instead of thick luns'), ]

CONF = cfg.CONF
CONF.register_opts(violin_opts)


class InvalidBackendConfig(exception.CinderException):
    message = _("Volume backend config is invalid: %(reason)s")


class RequestRetryTimeout(exception.CinderException):
    message = _("Backend service retry timeout hit: %(timeout)s sec")


class ViolinBackendErr(exception.CinderException):
    message = _("Backend reports: %(message)s")


class ViolinBackendErrExists(exception.CinderException):
    message = _("Backend reports: item already exists")


class ViolinBackendErrNotFound(exception.CinderException):
    message = _("Backend reports: item not found")


class V6000CommonDriver(san.SanDriver):
    """Executes commands relating to Violin Memory Arrays."""
    def __init__(self, *args, **kwargs):
        super(V6000CommonDriver, self).__init__(*args, **kwargs)
        self.request_timeout = 300
        self.vmem_vip = None
        self.vmem_mga = None
        self.vmem_mgb = None
        self.container = ""
        self.stats = {}
        self.config = kwargs.get('configuration', None)
        self.context = None
        self.lun_tracker = LunIdList(self.db)
        if self.config:
            self.config.append_config_values(violin_opts)

    def do_setup(self, context):
        """Any initialization the driver does while starting."""
        if not self.config.gateway_vip:
            raise exception.InvalidInput(
                reason=_('Gateway VIP is not set'))
        if not self.config.gateway_mga:
            raise exception.InvalidInput(
                reason=_('Gateway IP for mg-a is not set'))
        if not self.config.gateway_mgb:
            raise exception.InvalidInput(
                reason=_('Gateway IP for mg-b is not set'))

        self.vmem_vip = vxg.open(self.config.gateway_vip,
                                 self.config.gateway_user,
                                 self.config.gateway_password,
                                 keepalive=True)
        self.vmem_mga = vxg.open(self.config.gateway_mga,
                                 self.config.gateway_user,
                                 self.config.gateway_password,
                                 keepalive=True)
        self.vmem_mgb = vxg.open(self.config.gateway_mgb,
                                 self.config.gateway_user,
                                 self.config.gateway_password,
                                 keepalive=True)
        self.context = context

        vip = self.vmem_vip.basic

        ret_dict = vip.get_node_values("/vshare/state/local/container/*")
        if ret_dict:
            self.container = ret_dict.items()[0][1]

        ret_dict = vip.get_node_values(
            "/vshare/state/local/container/%s/lun/*"
            % self.container)
        if ret_dict:
            self.lun_tracker.update_from_volume_ids(ret_dict.values())

        ret_dict = vip.get_node_values(
            "/vshare/state/snapshot/container/%s/lun/*"
            % self.container)
        if ret_dict:
            for vol_id in ret_dict.values():
                snaps = vip.get_node_values(
                    "/vshare/state/snapshot/container/%s/lun/%s/snap/*"
                    % (self.container, vol_id))
                self.lun_tracker.update_from_snapshot_ids(snaps.values())

    def check_for_setup_error(self):
        """Returns an error if prerequisites aren't met."""
        vip = self.vmem_vip.basic

        if len(self.container) == 0:
            raise InvalidBackendConfig(reason=_('container is missing'))

        if not self._is_supported_vmos_version(self.vmem_vip.version):
            msg = _('VMOS version is not supported')
            raise InvalidBackendConfig(reason=msg)

        bn1 = ("/vshare/state/local/container/%s/threshold/usedspace"
               "/threshold_hard_val" % self.container)
        bn2 = ("/vshare/state/local/container/%s/threshold/provision"
               "/threshold_hard_val" % self.container)
        ret_dict = vip.get_node_values([bn1, bn2])

        for node in ret_dict:
            # The infrastructure does not support space reclamation so
            # ensure it is disabled.  When used space exceeds the hard
            # limit, snapshot space reclamation begins.  Default is 0
            # => no space reclamation.
            #
            if node.endswith('/usedspace/threshold_hard_val'):
                if ret_dict[node] != 0:
                    msg = _('space reclamation threshold is enabled')
                    raise InvalidBackendConfig(reason=msg)

            # The infrastructure does not support overprovisioning so
            # ensure it is disabled.  When provisioned space exceeds
            # the hard limit, further provisioning is stopped.
            # Default is 100 => provisioned space equals usable space.
            #
            elif node.endswith('/provision/threshold_hard_val'):
                if ret_dict[node] != 100:
                    msg = _('provisioned space threshold not equal to '
                           'usable space')
                    raise InvalidBackendConfig(reason=msg)

    def create_volume(self, volume):
        """Creates a volume."""
        self._create_lun(volume)

    def delete_volume(self, volume):
        """Deletes a volume."""
        self._delete_lun(volume)

    def create_snapshot(self, snapshot):
        """Creates a snapshot from an existing volume."""
        self._create_lun_snapshot(snapshot)

    def delete_snapshot(self, snapshot):
        """Deletes a snapshot."""
        self._delete_lun_snapshot(snapshot)

    def create_volume_from_snapshot(self, volume, snapshot):
        """Creates a volume from a snapshot."""
        snapshot['size'] = snapshot['volume']['size']
        self._create_lun(volume)
        self.copy_volume_data(self.context, snapshot, volume)

    def create_cloned_volume(self, volume, src_vref):
        """Creates a full clone of the specified volume."""
        self._create_lun(volume)
        self.copy_volume_data(self.context, src_vref, volume)

    def extend_volume(self, volume, new_size):
        """Extend an existing volume's size.

        The equivalent CLI command is "lun resize container
        <container_name> name <lun_name> size <gb>"

        Arguments:
            volume   -- volume object provided by the Manager
            new_size -- new (increased) size in GB to be applied
        """
        v = self.vmem_vip

        LOG.info(_("Extending lun %(id)s, from %(size)s to %(new_size)s GB") %
                 {'id': volume['id'], 'size': volume['size'],
                  'new_size': new_size})

        try:
            self._send_cmd(v.lun.resize_lun, 'Success',
                           self.container, volume['id'], new_size)

        except Exception:
            LOG.exception(_("LUN extend failed!"))
            raise

    @utils.synchronized('vmem-lun')
    def _create_lun(self, volume):
        """Creates a new lun.

        The equivalent CLI command is "lun create container
        <container_name> name <lun_name> size <gb>"

        Arguments:
            volume -- volume object provided by the Manager
        """
        lun_type = '0'
        v = self.vmem_vip

        LOG.info(_("Creating lun %(name)s, %(size)s GB") % volume)

        if self.config.use_thin_luns:
            lun_type = '1'

        # using the defaults for fields: quantity, nozero,
        # readonly, startnum, blksize, naca, alua, preferredport
        #
        try:
            self._send_cmd(v.lun.create_lun,
                           'LUN create: success!',
                           self.container, volume['id'],
                           volume['size'], 1, '0', lun_type, 'w',
                           1, 512, False, False, None)

        except ViolinBackendErrExists:
            LOG.info(_("Lun %s already exists, continuing"), volume['id'])

        except Exception:
            LOG.warn(_("Lun create failed!"))
            raise

    @utils.synchronized('vmem-lun')
    def _delete_lun(self, volume):
        """Deletes a lun.

        The equivalent CLI command is "no lun create container
        <container_name> name <lun_name>"

        Arguments:
            volume -- volume object provided by the Manager
        """
        v = self.vmem_vip
        success_msgs = ['lun deletion started', '']

        LOG.info(_("Deleting lun %s"), volume['id'])

        try:
            self._send_cmd(v.lun.bulk_delete_luns,
                           success_msgs,
                           self.container, volume['id'])

        except ViolinBackendErrNotFound:
            LOG.info(_("Lun %s already deleted, continuing"), volume['id'])

        except ViolinBackendErrExists:
            LOG.warn(_("Lun %s has dependent snapshots, skipping"),
                     volume['id'])
            raise exception.VolumeIsBusy(volume_name=volume['id'])

        except Exception:
            LOG.exception(_("Lun delete failed!"))
            raise

        self.lun_tracker.free_lun_id_for_volume(volume)

    @utils.synchronized('vmem-snap')
    def _create_lun_snapshot(self, snapshot):
        """Creates a new snapshot for a lun.

        The equivalent CLI command is "snapshot create container
        <container> lun <volume_name> name <snapshot_name>"

        Arguments:
            snapshot -- snapshot object provided by the Manager
        """
        v = self.vmem_vip

        LOG.info(_("Creating snapshot %s"), snapshot['id'])

        try:
            self._send_cmd(v.snapshot.create_lun_snapshot,
                           'Snapshot create: success!',
                           self.container, snapshot['volume_id'],
                           snapshot['id'])

        except ViolinBackendErrExists:
            LOG.info(_("Snapshot %s already exists, continuing"),
                     snapshot['id'])

        except Exception:
            LOG.exception(_("LUN snapshot create failed!"))
            raise

    @utils.synchronized('vmem-snap')
    def _delete_lun_snapshot(self, snapshot):
        """Deletes an existing snapshot for a lun.

        The equivalent CLI command is "no snapshot create container
        <container> lun <volume_name> name <snapshot_name>"

        Arguments:
            snapshot -- snapshot object provided by the Manager
        """
        v = self.vmem_vip

        LOG.info(_("Deleting snapshot %s"), snapshot['id'])

        try:
            self._send_cmd(v.snapshot.delete_lun_snapshot,
                           'Snapshot delete: success!',
                           self.container, snapshot['volume_id'],
                           snapshot['id'])

        except ViolinBackendErrNotFound:
            LOG.info(_("Snapshot %s already deleted, continuing"),
                     snapshot['id'])

        except Exception:
            LOG.exception(_("LUN snapshot delete failed!"))
            raise

        self.lun_tracker.free_lun_id_for_snapshot(snapshot)

    def _send_cmd(self, request_func, success_msgs, *args):
        """Run an XG request function, and retry until the request
        returns a success message, a failure message, or the global
        request timeout is hit.

        This wrapper is meant to deal with backend requests that can
        fail for any variety of reasons, for instance, when the system
        is already busy handling other LUN requests.  It is also smart
        enough to give up if clustering is down (eg no HA available),
        there is no space left, or other "fatal" errors are returned
        (see _fatal_error_code() for a list of all known error
        conditions).

        Arguments:
            request_func    -- XG api method to call
            success_msgs    -- Success messages expected from the backend
            *args           -- argument array to be passed to the request_func

        Returns:
            The response dict from the last XG call.
        """
        resp = {}
        start = time.time()
        done = False

        if isinstance(success_msgs, basestring):
            success_msgs = [success_msgs]

        while not done:
            if time.time() - start >= self.request_timeout:
                raise RequestRetryTimeout(timeout=self.request_timeout)

            resp = request_func(*args)

            if not resp['message']:
                # XG requests will return None for a message if no message
                # string is passed int the raw response
                resp['message'] = ''

            for msg in success_msgs:
                if not resp['code'] and msg in resp['message']:
                    done = True
                    break

            self._fatal_error_code(resp)

        return resp

    def _send_cmd_and_verify(self, request_func, verify_func,
                             request_success_msgs='', rargs=[], vargs=[]):
        """Run an XG request function, and verify success using an
        additional verify function.  If the verification fails, then
        retry the request/verify cycle until both functions are
        successful, the request function returns a failure message, or
        the global request timeout is hit.

        This wrapper is meant to deal with backend requests that can
        fail for any variety of reasons, for instance, when the system
        is already busy handling other LUN requests.  It is also smart
        enough to give up if clustering is down (eg no HA available),
        there is no space left, or other "fatal" errors are returned
        (see _fatal_error_code() for a list of all known error
        conditions).

        Arguments:
            request_func        -- XG api method to call
            verify_func         -- function to call to verify request was
                                   completed successfully (eg for export)
            request_success_msg -- Success message expected from the backend
                                   for the request_func
            *rargs              -- argument array to be passed to the
                                   request_func
            *vargs              -- argument array to be passed to the
                                   verify_func

        Returns:
            The response dict from the last XG call.
        """
        resp = {}
        start = time.time()
        request_needed = True
        verify_needed = True

        if isinstance(request_success_msgs, basestring):
            request_success_msgs = [request_success_msgs]

        while request_needed or verify_needed:
            if time.time() - start >= self.request_timeout:
                raise RequestRetryTimeout(timeout=self.request_timeout)

            if request_needed:
                resp = request_func(*rargs)
                if not resp['message']:
                    # XG requests will return None for a message if no message
                    # string is passed int the raw response
                    resp['message'] = ''
                    for msg in request_success_msgs:
                        if not resp['code'] and msg in resp['message']:
                            # XG request func was completed
                            request_needed = False
                            break
                self._fatal_error_code(resp)

            elif verify_needed:
                success = verify_func(*vargs)
                if success:
                    # XG verify func was completed
                    verify_needed = False
                else:
                    # try sending the request again
                    request_needed = True

        return resp

    def _get_igroup(self, volume, connector):
        """Gets the igroup that should be used when configuring a volume.

        Arguments:
            volume -- volume object used to determine the igroup name

        Returns:
            igroup_name -- name of igroup (for configuring targets &
                           initiators)
        """
        v = self.vmem_vip

        # Use the connector's primary hostname and use that as the
        # name of the igroup.  The name must follow syntax rules
        # required by the array: "must contain only alphanumeric
        # characters, dashes, and underscores.  The first character
        # must be alphanumeric".
        #
        igroup_name = re.sub(r'[\W]', '_', connector['host'])

        # verify that the igroup has been created on the backend, and
        # if it doesn't exist, create it!
        #
        bn = "/vshare/config/igroup/%s" % igroup_name
        resp = v.basic.get_node_values(bn)

        if not len(resp):
            v.igroup.create_igroup(igroup_name)

        return igroup_name

    def _get_volume_type_extra_spec(self, volume, spec_key):
        """Parse data stored in a volume_type's extra_specs table.

        Code adapted from examples in
        cinder/volume/drivers/solidfire.py and
        cinder/openstack/common/scheduler/filters/capabilities_filter.py.

        Arguments:
            volume   -- volume object containing volume_type to query
            spec_key -- the metadata key to search for

        Returns:
            spec_value -- string value associated with spec_key
        """
        spec_value = None
        ctxt = context.get_admin_context()
        typeid = volume['volume_type_id']
        if typeid:
            volume_type = volume_types.get_volume_type(ctxt, typeid)
            volume_specs = volume_type.get('extra_specs')
            for key, val in volume_specs.iteritems():

                # Havana release altered extra_specs to require a
                # prefix on all non-host-capability related extra
                # specs, so that prefix is stripped here before
                # checking the key.
                #
                if ':' in key:
                    scope = key.split(':')
                    key = scope[1]
                if key == spec_key:
                    spec_value = val
                    break

        return spec_value

    def _wait_for_exportstate(self, volume_name, state=False):
        """Polls backend to verify volume's export configuration.

        XG sets/queries following a request to create or delete a lun
        export may fail on the backend if vshared is still processing
        the export action (or times out).  We can check whether it is
        done by polling the export binding for a lun to ensure it is
        created or deleted.

        This function will try to verify the creation or removal of
        export state on both gateway nodes of the array every 5
        seconds for up to 30 seconds.

        Arguments:
            volume_name -- name of volume to be polled
            state       -- True to poll for existence, False for lack of

        Returns:
            True if the export state was correctly added or removed
            (depending on 'state' param)
        """
        status = [False, False]
        mg_conns = [self.vmem_mga.basic, self.vmem_mgb.basic]
        success = False

        bn = "/vshare/config/export/container/%s/lun/%s" \
            % (self.container, volume_name)

        for i in xrange(6):
            for node_id in xrange(2):
                if not status[node_id]:
                    resp = mg_conns[node_id].get_node_values(bn)
                    if state and len(resp.keys()):
                        status[node_id] = True
                    elif (not state) and (not len(resp.keys())):
                        status[node_id] = True

            if status[0] and status[1]:
                success = True
                break
            else:
                time.sleep(5)

        return success

    def _is_supported_vmos_version(self, version_string):
        """Check that the version of VMOS running on the gateways is
        valid for use with the OpenStack drivers."""
        for pattern in VMOS_SUPPORTED_VERSION_PATTERNS:
            if re.match(pattern, version_string):
                LOG.debug("Verified VMOS version %s is supported" %
                          version_string)
                return True
        return False

    def _fatal_error_code(self, response):
        """Check the error code in a XG response for a fatal error,
        and returns an appropriate exception.  Error codes extracted
        from vdmd_mgmt.c.

        Arguments:
            response -- a response dict result from an XG request
        """
        # known non-fatal response codes
        #
        retry_codes = {1024: 'lun deletion in progress, try again later',
                       14032: 'lc_err_lock_busy'}

        if response['code'] == 14000:
            # lc_generic_error
            raise ViolinBackendErr(message=response['message'])
        elif response['code'] == 14002:
            # lc_err_assertion_failed
            raise ViolinBackendErr(message=response['message'])
        elif response['code'] == 14004:
            # lc_err_not_found
            raise ViolinBackendErrNotFound()
        elif response['code'] == 14005:
            # lc_err_exists
            raise ViolinBackendErrExists()
        elif response['code'] == 14008:
            # lc_err_unexpected_arg
            raise ViolinBackendErr(message=response['message'])
        elif response['code'] == 14014:
            # lc_err_io_error
            raise ViolinBackendErr(message=response['message'])
        elif response['code'] == 14016:
            # lc_err_io_closed
            raise ViolinBackendErr(message=response['message'])
        elif response['code'] == 14017:
            # lc_err_io_timeout
            raise ViolinBackendErr(message=response['message'])
        elif response['code'] == 14021:
            # lc_err_unexpected_case
            raise ViolinBackendErr(message=response['message'])
        elif response['code'] == 14025:
            # lc_err_no_fs_space
            raise ViolinBackendErr(message=response['message'])
        elif response['code'] == 14035:
            # lc_err_range
            raise ViolinBackendErr(message=response['message'])
        elif response['code'] == 14036:
            # lc_err_invalid_param
            raise ViolinBackendErr(message=response['message'])
        elif response['code'] == 14121:
            # lc_err_cancelled_err
            raise ViolinBackendErr(message=response['message'])
        elif response['code'] == 512:
            # Not enough free space in container (vdmd bug)
            raise ViolinBackendErr(message=response['message'])
        elif response['code'] == 1 and 'LUN ID conflict' \
                in response['message']:
            # lun id conflict while attempting to export
            raise ViolinBackendErr(message=response['message'])


class LunIdList(object):
    """Tracks available lun_ids for use when exporting a new lun for the
    first time.  After instantiating a new LunIdList object, it should
    be updated (basically quiescing volumes/snapshot lun ID allocation
    between the array and the corresponding Openstack DB metadata).

    After that, the object can be queried to capture the next
    'available' lun ID for use with exporting a new volume or
    snapshot.  Only when the volume/snapshot is deleted entirely, the
    lun ID should be freed.

    Lun IDs are montonically increasing up to a max value of 16k,
    after which the selection will loop around to lun ID 1 and will
    continue to increment until an available ID is found.
    """
    def __init__(self, db, *args, **kwargs):
        self.max_lun_id = 16000
        self.lun_id_list = [0] * self.max_lun_id
        self.lun_id_list[0] = 1
        self.prev_index = 1
        self.free_index = 1
        self.context = context.get_admin_context()
        self.db = db

    def update_from_volume_ids(self, id_list=[]):
        """Walk a list of volumes collected that the array knows about and
        check for any saved lun_id metadata for each of those volumes to
        fully sync the list.  Note that the metadata keys are stored as
        strings.

        Arguments:
            id_list -- array containing names of volumes that exist on the
                       backend (volume 'names' are UUIDs if they were made
                       via the VMEM driver API)
        """
        for item in id_list:
            try:
                metadata = self.db.volume_metadata_get(self.context, item)
            except exception.VolumeNotFound:
                LOG.warn(_("No db state for lun %s, skipping lun_id update"),
                         item)
            else:
                if metadata and 'lun_id' in metadata:
                    index = int(metadata['lun_id'])
                    self.lun_id_list[index] = 1
                    LOG.debug("Set lun_id=%d for volume_id=%s" % (index, item))
                    self.update_free_index(index)

    def update_from_snapshot_ids(self, id_list=[]):
        """Walk a list of snapshots collected that the array knows about and
        check for any saved lun_id metadata for each of those snapshots to
        fully sync the list.  Note that the metadata keys are stored as
        strings.

        Arguments:
            id_list -- array containing names of snapshots that exist on the
                       backend (snapshot 'names' are UUIDs if they were made
                       via the VMEM driver API)
        """
        for item in id_list:
            try:
                metadata = self.db.snapshot_metadata_get(self.context, item)
            except exception.SnapshotNotFound:
                LOG.warn(_("No db state for snap %s, skipping lun_id update"),
                         item)
            else:
                if metadata and 'lun_id' in metadata:
                    index = int(metadata['lun_id'])
                    self.lun_id_list[index] = 1
                    LOG.debug("Set lun_id=%d for snapshot_id=%s" %
                              (index, item))
                    self.update_free_index(index)

    def get_lun_id_for_volume(self, volume):
        """Allocate a free a lun ID to a volume and create a lun_id tag
        in the volume's metadata.

        Arguments:
            volume -- the volume object to allocate a lun_id to
        """
        metadata = self.db.volume_metadata_get(self.context, volume['id'])
        if not metadata or 'lun_id' not in metadata:
            metadata = {}
            metadata['lun_id'] = self.get_next_lun_id_str()
            self.db.volume_metadata_update(self.context, volume['id'],
                                           metadata, False)
            LOG.debug("Assigned lun_id %s to volume %s" %
                      (metadata['lun_id'], volume['id']))
        return metadata['lun_id']

    def get_lun_id_for_snapshot(self, snapshot):
        """Allocate a free a lun ID to a snapshot and create a lun_id tag
        in the snapshot's metadata.

        Arguments:
            snapshot -- the snapshot object to allocate a lun_id to
        """
        metadata = self.db.snapshot_metadata_get(self.context, snapshot['id'])
        if not metadata or 'lun_id' not in metadata:
            metadata = {}
            metadata['lun_id'] = self.get_next_lun_id_str()
            self.db.snapshot_metadata_update(self.context, snapshot['id'],
                                             metadata, False)
            LOG.debug("Assigned lun_id %s to volume %s" %
                      (metadata['lun_id'], snapshot['id']))
        return metadata['lun_id']

    def free_lun_id_for_volume(self, volume):
        """Remove the lun_id tag saved in the volume's metadata and
        free the lun ID in the internal tracking array.

        Arguments:
            volume -- the volume object with a lun ID to be free'd
        """
        metadata = self.db.volume_metadata_get(self.context, volume['id'])
        if metadata and 'lun_id' in metadata:
            self.free_lun_id_str(metadata['lun_id'])

    def free_lun_id_for_snapshot(self, snapshot):
        """Remove the lun_id tag saved in the snapshot's metadata and
        free the lun ID in the internal tracking array.

        Arguments:
            snapshot -- the snapshot object with a lun ID to be free'd
        """
        metadata = self.db.snapshot_metadata_get(self.context, snapshot['id'])
        if metadata and 'lun_id' in metadata:
            self.free_lun_id_str(metadata['lun_id'])

    def get_next_lun_id_str(self):
        """Mark the next available lun_id as allocated and return
        it to the caller.

        Returns:
            next_id -- the lun ID that being allocated to the caller
        """
        next_id = self.free_index
        self.lun_id_list[next_id] = 1
        self.update_free_index()
        return str(next_id)

    def free_lun_id_str(self, value_str):
        """Mark a lun_id as now available, as if the lun was de-allocated.

        Arguments:
            value_str -- lun ID to free (in string format)
        """
        value = int(value_str)
        self.lun_id_list[value] = 0
        self.update_free_index()

    def update_free_index(self, index=None):
        """Update the free index, monotonically increasing, and
        looping back to 1 after the max lun ID value is hit.

        Arguments:
            index -- assume that all values below this number may be already
                     allocated, so start searching at that value if it is
                     higher than the free_index
        """
        i = 0
        count = 0
        max_size = len(self.lun_id_list)
        if index and index > self.free_index:
            i = index + 1
        else:
            i = self.free_index
        # avoid possibility of indexError
        if i >= max_size:
            i = 1
        while self.lun_id_list[i] == 1 and count < max_size:
            count += 1
            i += 1
            if i >= max_size:
                i = 1
        self.free_index = i
        if count == max_size:
            raise exception.Error("Cannot find free lun_id, giving up!")
