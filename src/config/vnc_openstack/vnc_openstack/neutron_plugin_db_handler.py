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
        vn_create_handler = vn_handler.VNetworkCreateHandler(self._vnc_lib)
        return vn_create_handler.resource_create(
            network_q=network_q,
            contrail_extensions_enabled=self._contrail_extensions_enabled)


    def network_update(self, net_id, network_q):
        vn_update_handler = vn_handler.VNetworkUpdateHandler(self._vnc_lib)
        return vn_update_handler.resource_update(net_id=net_id,
                                                 network_q=network_q)

    def network_delete(self, net_id):
        vn_delete_handler = vn_handler.VNetworkDeleteHandler(self._vnc_lib)
        vn_delete_handler.resource_delete(net_id=net_id)

    def network_read(self, net_uuid, fields=None):
        vn_get_handler = vn_handler.VNetworkGetHandler(self._vnc_lib)
        return vn_get_handler.resource_get(net_uuid=net_uuid, fields=fields)

    def network_list(self, context=None, filters=None):
        """
        vn_get_handler = vn_handler.VNetworkGetHandler(self._vnc_lib)
        return vn_get_handler.resource_list(context=context, filters=filters)
        """
        return super(DBInterfaceV2, self).network_list(context=context,
                                                       filters=filters)

    def network_count(self, filters=None):
        return super(DBInterfaceV2, self).network_count(filters=filters)


    def port_create(self, context, port_q):
        vmi_create_handler = vmi_handler.VMInterfaceCreateHandler(
            self._vnc_lib)
        return vmi_create_handler.resource_create(context=context,
                                                  port_q=port_q)

    def port_delete(self, port_id):
        vmi_delete_handler = vmi_handler.VMInterfaceDeleteHandler(
            self._vnc_lib)
        vmi_delete_handler.resource_delete(port_id=port_id)

    def port_update(self, port_id, port_q):
        vmi_update_handler = vmi_handler.VMInterfaceUpdateHandler(
            self._vnc_lib)
        return vmi_update_handler.resource_update(port_id=port_id,
                                                  port_q=port_q)

    def port_read(self, port_id):
        vmi_list_handler = vmi_handler.VMInterfaceGetHandler(self._vnc_lib)
        return vmi_list_handler.resource_list(port_id=port_id)

    def port_count(self, filters=None):
        return super(DBInterfaceV2, self).port_count(filters=filters)

    def subnet_create(self, subnet_q):
        sn_create_handler = subnet_handler.SubnetCreateHandler(self._vnc_lib)
        return sn_create_handler.resource_create(subnet_q=subnet_q)

    def subnet_update(self, subnet_id, subnet_q):
        sn_update_handler = subnet_handler.SubnetUpdateHandler(self._vnc_lib)
        return sn_update_handler.resource_update(subnet_id=subnet_id,
                                                 subnet_q=subnet_q)

    def subnet_delete(self, subnet_id):
        sn_delete_handler = subnet_handler.SubnetDeleteHandler(self._vnc_lib)
        sn_delete_handler.resource_delete(subnet_id=subnet_id)

    def subnet_read(self, subnet_id):
        sn_get_handler = subnet_handler.SubnetGetHandler(self._vnc_lib)
        return sn_get_handler.resource_get(subnet_id=subnet_id)

    def subnets_list(self, context, filters=None):
        sn_get_handler = subnet_handler.SubnetGetHandler(self._vnc_lib)
        return sn_get_handler.resource_list(context=context,
                                            filters=filters)

    def subnets_count(self, context, filters=None):
        sn_get_handler = subnet_handler.SubnetGetHandler(self._vnc_lib)
        return sn_get_handler.resource_count(context=context,
                                             filters=filters)

    def floatingip_create(self, context, fip_q):
        fip_create_handler = fip_handler.FloatingIpCreateHandler(self._vnc_lib)
        return fip_create_handler.resource_create(context=context,
                                                  fip_q=fip_q)

    def floatingip_delete(self, fip_id):
        fip_delete_handler = fip_handler.FloatingIpDeleteHandler(self._vnc_lib)
        fip_delete_handler.resource_delete(fip_id=fip_id)

    def floatingip_update(self, context, fip_id, fip_q):
        fip_update_handler = fip_handler.FloatingIpUpdateHandler(self._vnc_lib)
        return fip_update_handler.resource_update(context=context,
                                                  fip_id=fip_id,
                                                  fip_q=fip_q)

    def floatingip_read(self, fip_uuid):
        fip_get_handler = fip_handler.FloatingIpGetHandler(self._vnc_lib)
        return fip_get_handler.resource_get(fip_uuid=fip_uuid)

    def floatingip_list(self, context, filters=None):
        fip_get_handler = fip_handler.FloatingIpGetHandler(self._vnc_lib)
        return fip_get_handler.resource_list(context=context,
                                             filters=filters)

    def floatingip_count(self, context, filters=None):
        fip_get_handler = fip_handler.FloatingIpGetHandler(self._vnc_lib)
        return fip_get_handler.resource_count(context=context,
                                              filters=filters)

    def router_create(self, router_q):
        rtr_create_handler = rtr_handler.LogicalRouterCreateHandler(
            self._vnc_lib)
        return rtr_create_handler.resource_create(router_q=router_q)

    def router_delete(self, rtr_id):
        rtr_delete_handler = rtr_handler.LogicalRouterDeleteHandler(
            self._vnc_lib)
        return rtr_delete_handler.resource_delete(rtr_id=rtr_id)

    def router_update(self, rtr_id, router_q):
        rtr_update_handler = rtr_handler.LogicalRouterUpdateHandler(
            self._vnc_lib)
        return rtr_update_handler.resource_update(rtr_id=rtr_id,
                                                  router_q=router_q)

    def router_read(self, rtr_uuid, fields=None):
        rtr_get_handler = rtr_handler.LogicalRouterGetHandler(self._vnc_lib)
        return rtr_get_handler.resource_get(rtr_uuid=rtr_uuid, fields=fields)

    def router_list(self, context=None, filters=None):
        rtr_get_handler = rtr_handler.LogicalRouterGetHandler(self._vnc_lib)
        return rtr_get_handler.resource_get(context=context, filters=filters)

    def router_count(self, filters=None):
        rtr_get_handler = rtr_handler.LogicalRouterGetHandler(self._vnc_lib)
        return rtr_get_handler.resource_get(filters=filters)


