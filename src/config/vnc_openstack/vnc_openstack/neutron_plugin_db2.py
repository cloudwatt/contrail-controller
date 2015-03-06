import gevent
try:
    import ujson as json
except ImportError:
    import json
import uuid

import bottle

from cfgm_common import exceptions
from neutron_plugin_db import DBInterface


class DBInterfaceV2(DBInterface):

    def __init__(self, *args, **kwargs):
        super(DBInterfaceV2, self).__init__(*args, **kwargs)

    def _resource_create(self, resource_type, obj):
        create_method = getattr(self._vnc_lib, resource_type + '_create')
        try:
            obj_uuid = create_method(obj)
        except exceptions.RefsExistError:
            obj.uuid = str(uuid.uuid4())
            obj.name += '-' + obj.uuid
            obj.fq_name[-1] += '-' + obj.uuid
            obj_uuid = create_method(obj)
        except (exceptions.PermissionDenied, exceptions.BadRequest) as e:
            DBInterfaceV2._raise_contrail_exception('BadRequest',
                                                    resource=resource_type,
                                                    msg=str(e))
        return obj_uuid

    def _resource_list(self, resource_type, parent_id=None, back_ref_id=None,
                       obj_uuids=None, fields=None, back_ref_fields=None,
                       detail=True):
        fields = list(set((fields or []) + (back_ref_fields or [])))

        list_method = getattr(self._vnc_lib, resource_type + 's_list')
        return list_method(parent_id=parent_id, back_ref_id=back_ref_id,
                           obj_uuids=obj_uuids, detail=detail, fields=fields)

    def _virtual_machine_interfaces_list(self, **kwargs):
        kwargs['back_ref_fields'] = ['logical_router_back_refs',
                                     'instance_ip_back_refs',
                                     'floating_ip_back_refs']
        return self._resource_list('virtual_machine_interface', **kwargs)

    # Encode and send an excption information to neutron. exc must be a
    # valid exception class name in neutron, kwargs must contain all
    # necessary arguments to create that exception
    @staticmethod
    def _raise_contrail_exception(self, exc, **kwargs):
        exc_info = {'exception': exc}
        exc_info.update(kwargs)
        bottle.abort(400, json.dumps(exc_info))

    @staticmethod
    def _validate_project_ids(project_ids):
        ids = []
        for project_id in project_ids:
            try:
                ids.append(str(uuid.UUID(project_id)))
            except ValueError:
                pass
        return ids

    @staticmethod
    def _device_ids_from_vmi_objs(vmi_objs):
        device_ids = []
        for vmi_obj in vmi_objs:
            vm_ref = vmi_obj.get_virtual_machine_refs()
            if vm_ref:
                device_ids.append(vm_ref[0]['uuid'])
            else:
                lg_back_ref = vmi_obj.get_logical_router_back_refs()
                if lg_back_ref:
                    device_ids.append(lg_back_ref[0]['uuid'])
        return device_ids

    # returns port objects, net objects, and instance ip objects
    def _get_ports_nets_ips(self, context, project_ids=None,
                            device_ids=None):
        vm_objs_gevent = gevent.spawn(self._vnc_lib.virtual_machines_list,
                                      back_ref_id=device_ids, detail=True)
        net_objs_gevent = gevent.spawn(self._vnc_lib.virtual_networks_list,
                                       parent_id=project_ids, detail=True)
        gevents = [vm_objs_gevent, net_objs_gevent]

        # if admin no need to filter we can retrieve all the ips object
        # with only one call
        if context['is_admin']:
            iip_objs_gevent = gevent.spawn(self._vnc_lib.instance_ips_list,
                                           detail=True)
            gevents.append(iip_objs_gevent)

        gevent.joinall(gevents)

        vm_objs = vm_objs_gevent.value
        net_objs = net_objs_gevent.value
        if context['is_admin']:
            iips_objs = iip_objs_gevent.value
        else:
            net_ids = [net_obj.uuid for net_obj in net_objs]
            iips_objs = self._vnc_lib.instance_ips_list(back_ref_id=net_ids,
                                                        detail=True)

        return vm_objs, net_objs, iips_objs

    # Returns a list of dicts of subnet-id:cidr for a VN
    @staticmethod
    def _virtual_network_to_subnets(net_obj):
        ret_subnets = []

        for ipam_ref in net_obj.get_network_ipam_refs() or []:
            for subnet in ipam_ref['attr'].get_ipam_subnets():
                subnet_id = subnet.subnet_uuid
                cidr = '%s/%s' % (subnet.subnet.get_ip_prefix(),
                                  subnet.subnet.get_ip_prefix_len())
                ret_subnets.append({'id': subnet_id, 'cidr': cidr})

        return ret_subnets

    def _vmi_resources_to_neutron_ports(self, vmi_objs, net_objs, iip_objs,
                                        vm_objs):
        ret_ports = []

        memo_req = {'networks': {},
                    'subnets': {},
                    'virtual-machines': {},
                    'instance-ips': {}}

        for net_obj in net_objs:
            memo_req['networks'][net_obj.uuid] = net_obj
            memo_req['subnets'][net_obj.uuid] = (
                DBInterfaceV2._virtual_network_to_subnets(net_obj))

        for iip_obj in iip_objs:
            memo_req['instance-ips'][iip_obj.uuid] = iip_obj

        for vm_obj in vm_objs:
            memo_req['virtual-machines'][vm_obj.uuid] = vm_obj

        for vmi_obj in vmi_objs:
            try:
                # TODO(safchain) to refactor, rename it to vmi_to_neutron_port
                port_info = self._port_vnc_to_neutron(vmi_obj, memo_req)
            except exceptions.NoIdError:
                continue
            ret_ports.append(port_info)

        return ret_ports

    # get vmi related resources filtered by project_ids
    def _get_vmi_resources(self, context, project_ids=None, ids=None,
                           device_ids=None):
        if not context['is_admin']:
            project_ids = [str(uuid.UUID(context['tenant']))]

        # XXX(safchain) what about the schema version < 1.06, see the version 1
        # of this class about a comment around back_ref and parent id ????
        vmi_objs = self._virtual_machine_interfaces_list(
            parent_id=project_ids, back_ref_id=device_ids)

        if not context['is_admin'] and not device_ids:
            device_ids = DBInterfaceV2._device_ids_from_vmi_objs(vmi_objs)

        vm_objs, net_objs, iip_objs = self._get_ports_nets_ips(context,
                                                               project_ids,
                                                               device_ids)
        return vmi_objs, vm_objs, net_objs, iip_objs

    def port_list(self, context, filters=None):
        # TODO(???) used to find dhcp server field. support later...
        if 'network:dhcp' in filters.get('device_owner', []):
            return []

        project_ids = []
        if not context['is_admin']:
            project_ids = [str(uuid.UUID(context['tenant']))]
        elif 'tenant_id' in filters:
            project_ids = DBInterfaceV2._validate_project_ids(
                filters['tenant_id'])
        elif 'network_id':
            # TODO(safchain)
            pass

        # choose the most appropriate way of retrieving ports
        # before pruning by other filters
        if 'device_id' in filters:
            vmi_objs, vm_objs, net_objs, iip_objs = self._get_vmi_resources(
                context, project_ids, device_ids=filters['device_id'])
        else:
            vmi_objs, vm_objs, net_objs, iip_objs = self._get_vmi_resources(
                context, project_ids, ids=filters.get('id'))

        ports = self._vmi_resources_to_neutron_ports(vmi_objs, net_objs,
                                                     iip_objs, vm_objs)

        # prune phase
        ret_ports = []
        for port in ports:
            # TODO(safchain) revisit these filters if necessary
            if not self._filters_is_present(filters, 'name',
                                            port['name']):
                continue
            if not self._filters_is_present(filters, 'device_owner',
                                            port['device_owner']):
                continue
            if 'fixed_ips' in filters and not self._port_fixed_ips_is_present(
                    filters['fixed_ips'], port['fixed_ips']):
                continue

            ret_ports.append(port)

        return ret_ports
