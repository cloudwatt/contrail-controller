#    Copyright
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


import gevent
try:
    import ujson as json
except ImportError:
    import json
import uuid

import bottle

from cfgm_common import exceptions
from vnc_api import vnc_api
from neutron_plugin_db import DBInterface

import contrail_res_handler as res_handler
import fip_res_handler as fip_handler
import router_res_handler as rtr_handler
import subnet_res_handler as subnet_handler
import vn_res_handler as vn_handler
import vmi_res_handler as vmi_handler

class DBInterfaceV2(DBInterface):

    def __init__(self, *args, **kwargs):
        super(DBInterfaceV2, self).__init__(*args, **kwargs)

    # Encode and send an excption information to neutron. exc must be a
    # valid exception class name in neutron, kwargs must contain all
    # necessary arguments to create that exception
    @staticmethod
    def _raise_contrail_exception(exc, **kwargs):
        exc_info = {'exception': exc}
        exc_info.update(kwargs)
        bottle.abort(400, json.dumps(exc_info))

    @staticmethod
    def _validate_project_ids(project_ids, context=None):
        if context and not context['is_admin']:
            return [context['tenant']]

        ids = []
        for project_id in project_ids:
            try:
                ids.append(str(uuid.UUID(project_id)))
            except ValueError:
                pass
        return ids


    @staticmethod
    def _filters_is_present(filters, key_name, match_value):
        if filters:
            if key_name in filters:
                try:
                    if key_name == 'tenant_id':
                        filter_value = [str(uuid.UUID(t_id)) \
                                        for t_id in filters[key_name]]
                    else:
                        filter_value = filters[key_name]
                    idx = filter_value.index(match_value)
                except ValueError:  # not in requested list
                    return False
        return True

    def network_create(self, network_q):
        handler = vn_handler.VNetworkHandler(self._vnc_lib)
        return handler.resource_create(
            network_q=network_q,
            contrail_extensions_enabled=self._contrail_extensions_enabled)


    def network_update(self, net_id, network_q):
        handler = vn_handler.VNetworkHandler(self._vnc_lib)
        return handler.resource_update(net_id=net_id,
                                       network_q=network_q)

    def network_delete(self, net_id):
        handler = vn_handler.VNetworkHandler(self._vnc_lib)
        handler.resource_delete(net_id=net_id)

    def network_read(self, net_uuid, fields=None):
        handler = vn_handler.VNetworkHandler(self._vnc_lib)
        return handler.resource_get(net_uuid=net_uuid, fields=fields)

    def network_list(self, context=None, filters=None):
        handler = vn_handler.VNetworkHandler(self._vnc_lib)
        return handler.resource_list(
            context=context, filters=filters,
            contrail_extensions_enabled=self._contrail_extensions_enabled)

    def network_count(self, filters=None):
        handler = vn_handler.VNetworkHandler(self._vnc_lib)
        return handler.resource_count(filters=filters)

    def port_create(self, context, port_q):
        handler = vmi_handler.VMInterfaceHandler(
            self._vnc_lib)
        return handler.resource_create(context=context,
                                       port_q=port_q)

    def port_delete(self, port_id):
        handler = vmi_handler.VMInterfaceHandler(
            self._vnc_lib)
        handler.resource_delete(port_id=port_id)

    def port_update(self, port_id, port_q):
        handler = vmi_handler.VMInterfaceHandler(
            self._vnc_lib)
        return handler.resource_update(port_id=port_id,
                                       port_q=port_q)

    def port_read(self, port_id):
        handler = vmi_handler.VMInterfaceHandler(self._vnc_lib)
        return handler.resource_get(port_id=port_id)

    def port_list(self, context=None, filters=None):
        handler = vmi_handler.VMInterfaceHandler(self._vnc_lib)
        return handler.resource_list(context=context, filters=filters)

    def port_count(self, filters=None):
        handler = vmi_handler.VMInterfaceHandler(self._vnc_lib)
        return handler.resource_count(filters=filters)

    def subnet_create(self, subnet_q):
        handler = subnet_handler.SubnetHandler(self._vnc_lib)
        return handler.resource_create(subnet_q=subnet_q)

    def subnet_update(self, subnet_id, subnet_q):
        handler = subnet_handler.SubnetHandler(self._vnc_lib)
        return handler.resource_update(subnet_id=subnet_id,
                                       subnet_q=subnet_q)

    def subnet_delete(self, subnet_id):
        sn_delete_handler = subnet_handler.SubnetHandler(self._vnc_lib)
        sn_delete_handler.resource_delete(subnet_id=subnet_id)

    def subnet_read(self, subnet_id):
        handler = subnet_handler.SubnetHandler(self._vnc_lib)
        return handler.resource_get(subnet_id=subnet_id)

    def subnets_list(self, context, filters=None):
        handler = subnet_handler.SubnetHandler(self._vnc_lib)
        return handler.resource_list(context=context,
                                     filters=filters)

    def subnets_count(self, context, filters=None):
        handler = subnet_handler.SubnetHandler(self._vnc_lib)
        return handler.resource_count(context=context,
                                      filters=filters)

    def floatingip_create(self, context, fip_q):
        handler = fip_handler.FloatingIpHandler(self._vnc_lib)
        return handler.resource_create(context=context,
                                       fip_q=fip_q)

    def floatingip_delete(self, fip_id):
        handler = fip_handler.FloatingIpHandler(self._vnc_lib)
        handler.resource_delete(fip_id=fip_id)

    def floatingip_update(self, context, fip_id, fip_q):
        handler = fip_handler.FloatingIpHandler(self._vnc_lib)
        return handler.resource_update(context=context,
                                       fip_id=fip_id,
                                       fip_q=fip_q)

    def floatingip_read(self, fip_uuid):
        handler = fip_handler.FloatingIpHandler(self._vnc_lib)
        return handler.resource_get(fip_uuid=fip_uuid)

    def floatingip_list(self, context, filters=None):
        handler = fip_handler.FloatingIpHandler(self._vnc_lib)
        return handler.resource_list(context=context,
                                     filters=filters)

    def floatingip_count(self, context, filters=None):
        handler = fip_handler.FloatingIpHandler(self._vnc_lib)
        return handler.resource_count(context=context,
                                      filters=filters)

    def router_create(self, router_q):
        handler = rtr_handler.LogicalRouterHandler(
            self._vnc_lib)
        return handler.resource_create(router_q=router_q)

    def router_delete(self, rtr_id):
        handler = rtr_handler.LogicalRouterHandler(
            self._vnc_lib)
        return handler.resource_delete(rtr_id=rtr_id)

    def router_update(self, rtr_id, router_q):
        handler = rtr_handler.LogicalRouterHandler(
            self._vnc_lib)
        return handler.resource_update(rtr_id=rtr_id,
                                       router_q=router_q)

    def router_read(self, rtr_uuid, fields=None):
        handler = rtr_handler.LogicalRouterHandler(self._vnc_lib)
        return handler.resource_get(rtr_uuid=rtr_uuid, fields=fields)

    def router_list(self, context=None, filters=None):
        handler = rtr_handler.LogicalRouterHandler(self._vnc_lib)
        return handler.resource_list(context=context, filters=filters)

    def router_count(self, filters=None):
        handler = rtr_handler.LogicalRouterHandler(self._vnc_lib)
        return handler.resource_count(filters=filters)
