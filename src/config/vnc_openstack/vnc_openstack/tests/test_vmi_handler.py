from vnc_openstack import vmi_res_handler as vmi_handler
from vnc_openstack import subnet_res_handler as subnet_handler
from vnc_openstack.tests import test_common
from vnc_api import vnc_api
import bottle


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
        subnet_q = {'name': 'test-subnet',
                    'cidr': '192.168.1.0/24',
                    'ip_version': 4,
                    'network_id': str(net_obj.uuid)}
        ret = subnet_handler.SubnetHandler(self._test_vnc_lib).resource_create(subnet_q)
        subnet_uuid = ret['id']

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


