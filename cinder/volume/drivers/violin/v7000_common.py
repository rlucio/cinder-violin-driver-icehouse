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
Violin Memory 7000 Series All-Flash Array Common Driver for Openstack Cinder

Uses Violin REST API via XG-Tools to manage a standard V7000 series
flash array to provide network block-storage services.

by Ryan Lucio
Senior Software Engineer
Violin Memory
"""

from oslo.config import cfg

from cinder.openstack.common import log as logging
from cinder.volume.drivers.san import san

LOG = logging.getLogger(__name__)

violin_opts = [
    # gateway_vip replaced by san.py san_ip
    # gateway_user replaced by san.py san_login
    # gateway_password replaced by san.py san_password
    # use_thin_luns replaced by san.py san_thin_provision
    cfg.StrOpt('gateway_mga',
               default='',
               help='IP address or hostname of mg-a'),
    cfg.StrOpt('gateway_mgb',
               default='',
               help='IP address or hostname of mg-b'),
    cfg.BoolOpt('use_igroups',
                default=False,
                help='Use igroups to manage targets and initiators'),
]

CONF = cfg.CONF
CONF.register_opts(violin_opts)


class V7000CommonDriver(san.SanDriver):
    """Base class for 7000 Series All-Flash Arrays."""

    def __init__(self, *args, **kwargs):
        super(V7000CommonDriver, self).__init__(*args, **kwargs)
        self.stats = {}
        self.configuration.append_config_values(violin_opts)

    def do_setup(self):
        """Any initialization the driver does while starting."""
        pass

    def check_for_setup_error(self):
        """Returns an error if prerequisites aren't met."""
        pass

    def create_volume(self, volume):
        """Creates a volume. Can optionally return a Dictionary of
        changes to the volume object to be persisted.
        """
        raise NotImplementedError()

    def create_volume_from_snapshot(self, volume, snapshot):
        """Creates a volume from a snapshot."""
        raise NotImplementedError()

    def create_cloned_volume(self, volume, src_vref):
        """Creates a clone of the specified volume."""
        raise NotImplementedError()

    def delete_volume(self, volume):
        """Deletes a volume."""
        raise NotImplementedError()

    def create_snapshot(self, snapshot):
        """Creates a snapshot."""
        raise NotImplementedError()

    def delete_snapshot(self, snapshot):
        """Deletes a snapshot."""
        raise NotImplementedError()

    def initialize_connection(self, volume, connector):
        """Allow connection to connector and return connection info."""
        raise NotImplementedError()

    def terminate_connection(self, volume, connector, **kwargs):
        """Disallow connection from connector"""
        raise NotImplementedError()

    def get_volume_stats(self, refresh=False):
        """Get volume stats. If 'refresh' is True, update the stats first."""
        if refresh or not self.stats:
            self._update_volume_stats()
        return self.stats

    def extend_volume(self, volume, new_size):
        """Extend an existing volume's size."""
        raise NotImplementedError()

    def _update_volume_stats(self):
        """Gathers array stats from the backend and converts them to
        GB values.
        """
        data = {}
        total_gb = 'unknown'
        free_gb = 'unknown'
        protocol = 'unknown'
        backend_name = self.configuration.volume_backend_name
        data['volume_backend_name'] = backend_name or self.__class__.__name__
        data['vendor_name'] = 'Violin Memory, Inc.'
        data['driver_version'] = 'unknown'
        data['storage_protocol'] = protocol
        data['reserved_percentage'] = 0
        data['QoS_support'] = False
        data['total_capacity_gb'] = total_gb
        data['free_capacity_gb'] = free_gb
        self.stats = data
