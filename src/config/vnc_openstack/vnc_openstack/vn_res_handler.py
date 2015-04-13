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

import uuid
try:
    import ujson as json
except ImportError:
    import json

from cfgm_common import exceptions as vnc_exc
from neutron.common import constants as n_constants
from vnc_api import vnc_api

import contrail_res_handler as res_handler
import neutron_plugin_db_handler as db_handler
import subnet_res_handler as subnet_hanler


class VNetworkHandler(res_handler.ResourceGetHandler,
                      res_handler.ResourceCreateHandler,
                      res_handler.ResourceDeleteHandler):
    resource_create_method = 'virtual_network_create'
    resource_list_method = 'virtual_networks_list'
    resource_get_method = 'virtual_network_read'
    resource_delete_method = 'virtual_network_delete'
    detail = False


class VNetworkMixin(object):

    def create_or_get_vn_obj(self, network_q):
        return VNetworkGetHandler(self._vnc_lib)._resource_get(
            id=network_q['id'])

    def neutron_dict_to_vn(self, network_q):
        vn_obj = self.create_or_get_vn_obj(network_q)
        if not vn_obj:
            return

        external_attr = network_q.get('router:external')
        net_name = network_q.get('name')
        if net_name:
            vn_obj.display_name = net_name

        id_perms = vn_obj.get_id_perms()
        if 'admin_state_up' in network_q:
            id_perms.enable = network_q['admin_state_up']
            vn_obj.set_id_perms(id_perms)
        
        if 'contrail:policys' in network_q:
            policy_fq_names = network_q['contrail:policys']
            # reset and add with newly specified list
            vn_obj.set_network_policy_list([], [])
            seq = 0
            for p_fq_name in policy_fq_names:
                domain_name, project_name, policy_name = p_fq_name

                domain_obj = vnc_api.Domain(domain_name)
                project_obj = vnc_api.Project(project_name, domain_obj)
                policy_obj = vnc_api.NetworkPolicy(policy_name, project_obj)

                vn_obj.add_network_policy(policy_obj,
                                           VirtualNetworkPolicyType(
                                           sequence=SequenceType(seq, 0)))
                seq = seq + 1

        if 'contrail:route_table' in network_q:
            rt_fq_name = network_q['contrail:route_table']
            if rt_fq_name:
                try:
                    rt_obj = self._vnc_lib.route_table_read(fq_name=rt_fq_name)
                    vn_obj.set_route_table(rt_obj)
                except vnc_api.NoIdError:
                    # TODO add route table specific exception
                    db_handler.DBInterfaceV2._raise_contrail_exception(
                        'NetworkNotFound', net_id=vn_obj.uuid)

        return vn_obj

    def _get_vn_extra_dict(self, vn_obj):
        extra_dict = {}
        extra_dict['contrail:fq_name'] = vn_obj.get_fq_name()
        extra_dict['contrail:instance_count'] = 0

        net_policy_refs = vn_obj.get_network_policy_refs()
        if net_policy_refs:
            sorted_refs = sorted(
                net_policy_refs,
                key=lambda t:(t['attr'].sequence.major,
                              t['attr'].sequence.minor))
            extra_dict['contrail:policys'] = [np_ref['to'] for np_ref in
                                              sorted_refs]

        rt_refs = vn_obj.get_route_table_refs()
        if rt_refs:
            extra_dict['contrail:route_table'] = [rt_ref['to'] for rt_ref in
                                                  rt_refs]

        return extra_dict

    def _add_vn_subnet_info(self, vn_obj, net_q_dict, extra_dict=None):
        ipam_refs = vn_obj.get_network_ipam_refs()
        net_q_dict['subnets'] = []
        if not ipam_refs:
            return

        if extra_dict:
            extra_dict['contrail:subnet_ipam'] = []

        sn_handler = subnet_handler.ContrailSubnetHandler(self._vnc_lib)
        for ipam_ref in ipam_refs:
            subnets = ipam_ref['attr'].get_ipam_subnets()
            for subnet in subnets:
                sn_id, sn_cidr = sn_handler.get_subnet_id_cidr(subnet, vn_obj)
                net_q_dict['subnets'].append(sn_id)

                if not extra_dict:
                    continue

                sn_ipam = {}
                sn_ipam['subnet_cidr'] = sn_cidr
                sn_ipam['ipam_fq_name'] = ipam_ref['to']
                extra_dict['contrail:subnet_ipam'].append(sn_ipam)


    def vn_to_neutron_dict(self, vn_obj, contrail_extensions_enabled=False):
        net_q_dict = {}
        extra_dict = None

        id_perms = vn_obj.get_id_perms()
        net_q_dict['id'] = vn_obj.uuid

        if not vn_obj.display_name:
            # for nets created directly via vnc_api
            net_q_dict['name'] = vn_obj.get_fq_name()[-1]
        else:
            net_q_dict['name'] = vn_obj.display_name

        net_q_dict['tenant_id'] = vn_obj.parent_uuid.replace('-', '')
        net_q_dict['admin_state_up'] = id_perms.enable
        net_q_dict['shared'] = True if vn_obj.is_shared else False
        net_q_dict['status'] = (n_constants.NET_STATUS_ACTIVE if id_perms.enable
                                else n_constants.NET_STATUS_DOWN)
        net_q_dict['router:external'] = (True if vn_obj.router_external
                                         else False)
        
        if contrail_extensions_enabled:
            extra_dict = self._get_vn_extra_dict(vn_obj)

        self._add_vn_subnet_info(vn_obj, net_q_dict, extra_dict)

        if contrail_extensions_enabled:
            net_q_dict.update(extra_dict)

        return net_q_dict

    def get_vn_tenant_id(self, vn_obj):
        return vn_obj.parent_uuid.replace('-', '')


class VNetworkCreateHandler(VNetworkHandler, VNetworkMixin):
    
    def create_or_get_vn_obj(self, network_q):
        net_name = network_q.get('name', None)
        project_id = str(uuid.UUID(network_q['tenant_id']))
        proj_obj = self._project_read(proj_id=project_id)
        id_perms = vnc_api.IdPermsType(enable=True)
        vn_obj = vnc_api.VirtualNetwork(net_name, proj_obj,
                                        id_perms=id_perms)
        external_attr = network_q.get('router:external')
        if external_attr is not None:
            vn_obj.router_external = external_attr
        else:
            vn_obj.router_external = False

        is_shared = network_q.get('shared')
        if is_shared is not None:
            vn_obj.is_shared = is_shared
        else:
            vn_obj.is_shared = False

        return vn_obj

    def resource_create(self, **kwargs):
        network_q = kwargs.get('network_q')
        contrail_extensions_enabled = kwargs.get('contrail_extensions_enabled',
                                                 False)
        vn_obj = self.neutron_dict_to_vn(network_q)
        net_uuid =  self._resource_create(vn_obj)

        if vn_obj.router_external:
            fip_pool_obj = vnc_api.FloatingIpPool('floating-ip-pool', vn_obj)
            res_handler.FloatingIpPoolHandler(self._vnc_lib)._resource_create(
                fip_pool_obj)
            
        ret_network_q = self.vn_to_neutron_dict(
            vn_obj, contrail_extensions_enabled=contrail_extensions_enabled)

        return ret_network_q


class VNetworkUpdateHandler(VNetworkHandler, VNetworkMixin):

    def _update_external_router_attr(self, router_external, vn_obj):
        if router_external and not vn_obj.router_external:
            fip_pool_obj = vnc_api.FloatingIpPool('floating-ip-pool',
                                                  vn_obj)
            res_handler.FloatingIpPoolHandler(self._vnc_lib)._resource_create(
                fip_pool_obj)
        else:
            fip_pools = vn_obj.get_floating_ip_pools()
            for fip_pool in fip_pools or []:
                try:
                    (res_handler.FloatingIpPoolHandler(
                        self._vnc_lib)._resource_delete(id=fip_pool['uuid']))
                except vnc_api.RefsExistError:
                    db_handler.DBInterfaceV2._raise_contrail_exception(
                        'NetworkInUse', net_id=net_id)

    def _validate_shared_attr(self, is_shared, vn_obj):
        if is_shared and not vn_obj.is_shared:
            for vmi in vn_obj.get_virtual_machine_interface_back_refs() or []:
                vmi_obj = VMInterfaceGetHandler(self._vnc_lib)._resource_get(
                    id=vmi['uuid'])
                if (vmi_obj.parent_type == 'project' and
                    vmi_obj.parent_uuid != vn_obj.parent_uuid):
                    db_handler.DBInterfaceV2._raise_contrail_exception(
                        'InvalidSharedSetting',
                        network=vn_obj.display_name)

    def create_or_get_vn_obj(self, network_q):
        vn_obj = self._resource_get(id=network_q['id'])
        router_external = network_q.get('router:external')
        if router_external is not None:
            if router_external != vn_obj.router_external:
                self._update_external_router_attr(router_external, vn_obj)
                vn_obj.router_external = external_attr

        is_shared = network_q.get('shared')
        if is_shared is not None:
            if is_shared != vn_obj.is_shared:
                self._validate_shared_attr(is_shared, vn_obj)
                vn_obj.is_shared = is_shared

        return vn_obj

    def resource_update(self, **kwargs):
        net_id = kwargs.get('net_id')
        network_q = kwargs.get('network_q')
        contrail_extensions_enabled = kwargs.get('contrail_extensions_enabled',
                                                 True)

        network_q['id'] = net_id
        vn_obj = self.neutron_dict_to_vn(network_q)
        self._resource_update(vn_obj)

        ret_network_q = self.vn_to_neutron_dict(
            vn_obj, contrail_extensions_enabled=contrail_extensions_enabled)

        return ret_network_q


class VNetworkGetHandler(VNetworkHandler, VNetworkMixin):

    def resource_list(self, **kwargs):
        context = kwargs.get('context')
        filters= kwargs.get('filters')
        

    def resource_get(self, **kwargs):
        net_uuid = kwargs.get('net_uuid')
        try:
            vn_obj = self._resource_get(id=net_uuid)
        except vnc_exc.NoIdError:
            db_handler.DBInterfaceV2._raise_contrail_exception(
                'NetworkNotFound', net_id=net_uuid)

        return self.vn_to_neutron_dict(
            vn_obj, kwargs.get('contrail_extensions_enabled', True))


    def resource_count(self, **kwargs):
        filters = kwargs.get('filters')
        count = self._resource_count_optimized(filters)
        if count is not None:
            return count

        nets_info = self.resource_list(filters=filters)
        return len(nets_info)

    def get_vn_list_project(self, project_id, count=False):
        if project_id:
            try:
                project_uuid = str(uuid.UUID(project_id))
            except ValueError:
                project_uuid = None
        else:
            project_uuid = None

        if count:
            ret_val = self._resource_list(parent_id=project_uuid,
                                          count=True)
        else:
            ret_val = self._resource_list(parent_id=project_uuid,
                                          detail=True)

        return ret_val

    def vn_list_shared(self):
        ret_list = []
        nets = self.get_vn_list_project(project_id=None)
        for net in nets:
            if not net.get_is_shared():
                continue
            ret_list.append(net)
        return ret_list


class VNetworkDeleteHandler(VNetworkHandler):

    def resource_delete(self, **kwargs):
        net_id = kwargs.get('net_id')
        try:
            vn_obj = self._resource_get(id=net_id)
        except vnc_api.NoIdError:
            return

        try:
            fip_pools = vn_obj.get_floating_ip_pools()
            for fip_pool in fip_pools or []:
                self._vnc_lib.floating_ip_pool_delete(id=fip_pool['uuid'])

            self._resource_delete(id=net_id)
        except vnc_api.RefsExistError:
            db_handler.DBInterfaceV2._raise_contrail_exception('NetworkInUse',
                                                               net_id=net_id)
