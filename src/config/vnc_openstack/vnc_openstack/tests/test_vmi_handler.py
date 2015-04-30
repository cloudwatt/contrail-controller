from neutron.common import constants as n_constants
from vnc_openstack import vmi_res_handler as vmi_handler
from vnc_openstack import subnet_res_handler as subnet_handler
from vnc_openstack import contrail_res_handler as res_handler
from vnc_openstack.tests import test_common
from vnc_api import vnc_api
import bottle
import uuid


class TestVmiHandlers(test_common.TestBase):
    def setUp(self):
        super(TestVmiHandlers, self).setUp()
        self._handler = vmi_handler.VMInterfaceHandler(self._test_vnc_lib)

    def test_create(self):
        context = {'is_admin': False,
                   'tenant_id': self._uuid_to_str(self.proj_obj.uuid)}

        # test with invalid network_id
        port_q_invalid_network_id = {
            'network_id': test_common.INVALID_UUID,
            'tenant_id': self._uuid_to_str(self.proj_obj.uuid)}
        entries = [{'input': {
            'context': context,
            'port_q': port_q_invalid_network_id},
            'output': bottle.HTTPError}]
        self._test_check_create(entries)

        # test with invalid tenant_id
        net_obj = vnc_api.VirtualNetwork('test-net', self.proj_obj)
        self._test_vnc_lib.virtual_network_create(net_obj)

        context['is_admin'] = True
        port_q_invalid_tenant_id = {
            'network_id': str(net_obj.uuid),
            'tenant_id': test_common.INVALID_UUID}
        entries = [{'input': {
            'context': context,
            'port_q': port_q_invalid_tenant_id},
            'output': bottle.HTTPError}]
        self._test_check_create(entries)

        # test with mismatching tenant_ids
        context['is_admin'] = False
        self._test_check_create(entries)

        # create one success entry
        proj_1 = self._project_create(name='proj-1')
        context['tenant_id'] = self._uuid_to_str(proj_1.uuid)
        port_q = {'name': 'test-port-1',
                  'network_id': str(net_obj.uuid),
                  'tenant_id': context['tenant_id']}
        entries = [{'input': {
            'context': context,
            'port_q': port_q},
            'output': {'name': 'test-port-1',
                       'network_id': str(net_obj.uuid),
                       'mac_address': self._generated()}}]
        self._test_check_create(entries)

        # create with the same mac id
        vmis = self._test_vnc_lib.virtual_machine_interfaces_list()['virtual-machine-interfaces']
        self.assertEqual(len(vmis), 1)
        mac = vmis[0]['virtual_machine_interface_mac_addresses'].mac_address[0]

        port_q['mac_address'] = mac
        port_q.pop('name')
        entries = [{'input': {
            'context': context,
            'port_q': port_q},
            'output': bottle.HTTPError}]
        self._test_check_create(entries)

        # create a test subnet
        subnet_uuid = self._create_test_subnet('test-subnet', net_obj)

        # check with a different mac and a fixed ip address
        port_q['mac_address'] = mac.replace('0', '1')
        port_q['fixed_ips'] = [{'subnet_id': subnet_uuid,
                               'ip_address': '192.168.1.3'}]
        entries = [{'input': {
            'context': context,
            'port_q': port_q},
            'output': {'mac_address': port_q['mac_address'],
                       'fixed_ips': [{'subnet_id': subnet_uuid,
                                      'ip_address': '192.168.1.3'}]}}]
        self._test_check_create(entries)

        # try creating a port with same fixed ip as before
        port_q['mac_address'] = mac.replace('0', '2')
        entries[0]['output'] = bottle.HTTPError
        self._test_check_create(entries)

    def _create_test_subnet(self, name, net_obj, cidr='192.168.1.0/24'):
        subnet_q = {'name': name,
                    'cidr': cidr,
                    'ip_version': 4,
                    'network_id': str(net_obj.uuid)}
        ret = subnet_handler.SubnetHandler(self._test_vnc_lib).resource_create(subnet_q)
        subnet_uuid = ret['id']
        return subnet_uuid

    def _create_test_port(self, name, net_obj, proj_obj,
                          with_fixed_ip=False, subnet_uuid=None,
                          ip_address='192.168.1.3'):
        context = {'tenant_id': self._uuid_to_str(proj_obj.uuid),
                   'is_admin': False}
        port_q = {'name': name,
                  'network_id': str(net_obj.uuid),
                  'tenant_id': context['tenant_id']}

        subnet_uuid = None
        exp_output = {'name': name,
                      'network_id': net_obj.uuid}
        if with_fixed_ip:
            port_q['fixed_ips'] = [{'subnet_id': subnet_uuid,
                                    'ip_address': ip_address}]
            exp_output['fixed_ips'] = [{'subnet_id': subnet_uuid,
                                        'ip_address': ip_address}]
        entries = [{'input': {
            'context': context,
            'port_q': port_q},
            'output': exp_output}]
        self._test_check_create(entries)

        context['tenant'] = context['tenant_id']
        res = self._handler.resource_list(context, filters={'name': name})
        self.assertEqual(len(res), 1)
        return res[0]['id']

    def _port_count_check(self, exp_count):
        entries = {'input': {'filters': None},
                   'output': exp_count}

        self._test_check_count([entries])

    def test_delete(self):
        self._test_failures_on_delete()

        net_obj = vnc_api.VirtualNetwork('test-net', self.proj_obj)
        self._test_vnc_lib.virtual_network_create(net_obj)
        subnet_uuid = self._create_test_subnet('test-subnet', net_obj)

        # create a port
        port_id_1 = self._create_test_port('test-port-1',
                                           net_obj=net_obj,
                                           proj_obj=self.proj_obj,
                                           with_fixed_ip=True,
                                           subnet_uuid=subnet_uuid)
        port_id_2 = self._create_test_port('test-port-2',
                                           net_obj=net_obj,
                                           proj_obj=self.proj_obj,
                                           with_fixed_ip=False)
        self._port_count_check(2)

        self._handler.resource_delete(port_id_1)

        self._port_count_check(1)

    def test_update(self):
        self._test_failures_on_update()

        net_obj = vnc_api.VirtualNetwork('test-net', self.proj_obj)
        self._test_vnc_lib.virtual_network_create(net_obj)
        subnet_uuid = self._create_test_subnet('test-subnet', net_obj)

        # create a port
        port_id_1 = self._create_test_port('test-port-1',
                                           net_obj=net_obj,
                                           proj_obj=self.proj_obj,
                                           with_fixed_ip=True,
                                           subnet_uuid=subnet_uuid)
        self._port_count_check(1)

        # update certain params and check
        entries = [{'input': {
            'port_q': {
                'name': 'test-port-updated',
                'admin_state_up': False,
                'security_groups': [],
                'device_owner': 'vm',
                'device_id': 'test-instance-1',
                'fixed_ips': [{'subnet_id': subnet_uuid, 
                               'ip_address': '192.168.1.10'}],
                'allowed_address_pairs': [{'ip_address': "10.0.0.0/24"},
                                          {'ip_address': "192.168.1.4"}],
                'extra_dhcp_opts': [{'opt_name': '4',
                                     'opt_value': '8.8.8.8'}]},
            'port_id': port_id_1},
            'output': {'name': 'test-port-updated',
                       'admin_state_up': False,
                       'id': port_id_1,
                       'security_groups': [self._generated()],
                       'extra_dhcp_opts': [{'opt_value': '8.8.8.8',
                                            'opt_name': '4'}],
                       'allowed_address_pairs': [
                            {'ip_address': '10.0.0.0/24'},
                            {'ip_address': '192.168.1.4'}]}}]
        self._test_check_update(entries)

        sg_rules = vnc_api.PolicyEntriesType()
        sg_obj = vnc_api.SecurityGroup(
            name='test-sec-group',
            parent_obj=self.proj_obj,
            security_group_entries=sg_rules)
        self._test_vnc_lib.security_group_create(sg_obj)
        entries[0]['input']['port_q']['security_groups'] = [sg_obj.uuid]
        entries[0]['input']['port_q']['device_id'] = 'test-instance-2'
        entries[0]['input']['port_q']['fixed_ips'][0]['ip_address'] = '192.168.1.11'
        entries[0]['output']['security_groups'] = [sg_obj.uuid]

        self._test_check_update(entries)

    def test_get(self):
        self._test_failures_on_get()

        net_obj = vnc_api.VirtualNetwork('test-net', self.proj_obj)
        self._test_vnc_lib.virtual_network_create(net_obj)
        subnet_uuid = self._create_test_subnet('test-subnet', net_obj)

        # create a port
        port_id_1 = self._create_test_port('test-port-1',
                                           net_obj=net_obj,
                                           proj_obj=self.proj_obj,
                                           with_fixed_ip=True,
                                           subnet_uuid=subnet_uuid)
        entries = [{'input': port_id_1,
                    'output': {
                        'mac_address': self._generated(),
                        'fixed_ips': [{'subnet_id': subnet_uuid,
                                       'ip_address': '192.168.1.3'}],
                        'name': 'test-port-1',
                        'admin_state_up': True}}]
        self._test_check_get(entries)

    def test_list(self):
        proj_1 = self._project_create('proj-1')
        net_obj_1 = vnc_api.VirtualNetwork('test-net-1', proj_1)
        self._test_vnc_lib.virtual_network_create(net_obj_1)
        subnet_uuid_1 = self._create_test_subnet('test-subnet-1', net_obj_1)
        port_id_1 = self._create_test_port('test-port-1',
                                           net_obj_1,
                                           proj_obj=proj_1,
                                           with_fixed_ip=True,
                                           subnet_uuid=subnet_uuid_1)

        proj_2 = self._project_create('proj_2')
        net_obj_2 = vnc_api.VirtualNetwork('test-net-2', proj_2)
        self._test_vnc_lib.virtual_network_create(net_obj_2)
        subnet_uuid_2 = self._create_test_subnet(
            'test-subnet-2', net_obj_2, '192.168.2.0/24')
        port_id_1 = self._create_test_port('test-port-2',
                                           net_obj_2,
                                           proj_obj=proj_2,
                                           with_fixed_ip=True,
                                           subnet_uuid=subnet_uuid_2,
                                           ip_address='192.168.2.3')

        entries = [
            # non admin context, with default tenant in context
            {'input': {
                'context': {
                    'tenant': self._uuid_to_str(self.proj_obj.uuid),
                    'is_admin': False},
                'filters': {
                    'tenant_id': [self._uuid_to_str(proj_1.uuid),
                                  self._uuid_to_str(proj_2.uuid)]}},
                'output': []},

            # admin context with default tenant in context
            {'input': {
                'context': {
                    'tenant': self._uuid_to_str(self.proj_obj.uuid),
                    'is_admin': True},
                'filters': {
                    'tenant_id': [self._uuid_to_str(proj_1.uuid),
                                  self._uuid_to_str(proj_2.uuid)]}},
                'output': [{'name': 'test-port-1'}, {'name': 'test-port-2'}]},

            # non-admin context with proj-1 and with filters of net-2 and proj_1
            {'input': {
                'context': {
                    'tenant': self._uuid_to_str(proj_1.uuid),
                    'is_admin': False},
                'filters': {
                    'tenant_id': [self._uuid_to_str(proj_1.uuid),
                                  self._uuid_to_str(proj_2.uuid)],
                    'network_id': [str(net_obj_2.uuid)]}},
                'output': []},

            # admin context with proj-1 and with filters of net-2 and proj_1
            {'input': {
                'context': {
                    'tenant': self._uuid_to_str(proj_1.uuid),
                    'is_admin': True},
                'filters': {
                    'tenant_id': [self._uuid_to_str(proj_1.uuid),
                                  self._uuid_to_str(proj_2.uuid)],
                    'network_id': [str(net_obj_2.uuid)]}},
                'output': [{'name': 'test-port-2'}]}]
        self._test_check_list(entries)
