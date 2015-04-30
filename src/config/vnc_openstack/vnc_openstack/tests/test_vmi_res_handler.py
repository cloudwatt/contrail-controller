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

import contextlib
import mock
import uuid

import test_contrail_res_handler as test_res_handler

from cfgm_common import exceptions as vnc_exc
from neutron.common import constants as n_constants
from vnc_api import vnc_api
from vnc_openstack import vmi_res_handler as vmi_handler
from vnc_openstack import subnet_res_handler as subnet_handler

class TestVMInterfaceMixin(test_res_handler.TestContrailBase):

    def setUp(self):
        super(TestVMInterfaceMixin, self).setUp()
        self.vmi_mixin = vmi_handler.VMInterfaceMixin()
        self.vmi_mixin._vnc_lib = self.vnc_lib

    def test__port_fixed_ips_is_present(self):
        check = {'ip_address': ['10.0.0.3', '10.0.0.4', '10.0.0.5']}
        against = [{'ip_address': '10.0.0.4'}]
        self.assertTrue(self.vmi_mixin._port_fixed_ips_is_present(
            check, against))
        against = [{'ip_address': '20.0.0.32'}]
        self.assertFalse(self.vmi_mixin._port_fixed_ips_is_present(
            check, against))

    def test__get_vmi_memo_req_dict(self):
        vn_objs = [mock.Mock(), mock.Mock()]
        vn_objs[0].uuid = 'vn-1'
        vn_objs[1].uuid = 'vn-2'

        iip_obj = mock.Mock()
        iip_obj.uuid = 'iip-1'

        vm_objs = [mock.Mock(), mock.Mock(), mock.Mock()]
        vm_objs[0].uuid = 'vm-1'
        vm_objs[1].uuid = 'vm-2'
        vm_objs[2].uuid = 'vm-3'

        expected_memo_dict = {}
        expected_memo_dict['networks'] = {'vn-1': vn_objs[0],
                                          'vn-2': vn_objs[1]}
        expected_memo_dict['subnets'] = {'vn-1': [{'id': 'sn-1',
                                                   'cidr': '10.0.0.0/24'}],
                                         'vn-2': [{'id': 'sn-2',
                                                   'cidr': '20.0.0.0/24'}]}
        expected_memo_dict['instance-ips'] = {'iip-1': iip_obj}
        expected_memo_dict['virtual-machines'] = {'vm-1': vm_objs[0],
                                                  'vm-2': vm_objs[1],
                                                  'vm-3': vm_objs[2]}

        def _fake_get_vn_subnets(vn_obj):
            if vn_obj.uuid == 'vn-1':
                return [{'id': 'sn-1', 'cidr': '10.0.0.0/24'}]
            elif vn_obj.uuid == 'vn-2':
                return [{'id': 'sn-2', 'cidr': '20.0.0.0/24'}]

        with mock.patch.object(
            subnet_handler.SubnetHandler, 'get_vn_subnets') as mock_get_vns:
            mock_get_vns.side_effect = _fake_get_vn_subnets
            returned_memo_dict = self.vmi_mixin._get_vmi_memo_req_dict(
                vn_objs, [iip_obj], vm_objs)
            self.assertEqual(expected_memo_dict, returned_memo_dict)

    def test__get_extra_dhcp_opts_none(self):
        vmi_obj = mock.Mock()
        vmi_obj.get_virtual_machine_interface_dhcp_option_list.return_value = (
            None)
        self.assertIsNone(self.vmi_mixin._get_extra_dhcp_opts(vmi_obj))

    def test__get_extra_dhcp_opts(self):
        dhcp_opt_list = mock.Mock()
        dhcp_opts = [mock.Mock(), mock.Mock()]
        dhcp_opts[0].dhcp_option_value = 'value-1'
        dhcp_opts[0].dhcp_option_name = 'name-1'
        dhcp_opts[1].dhcp_option_value = 'value-2'
        dhcp_opts[1].dhcp_option_name = 'name-2'

        dhcp_opt_list.dhcp_option = dhcp_opts
        expected_dhcp_opt_list = [{'opt_value': 'value-1',
                                   'opt_name': 'name-1'},
                                  {'opt_value': 'value-2',
                                   'opt_name': 'name-2'}]

        vmi_obj = mock.Mock()
        vmi_obj.get_virtual_machine_interface_dhcp_option_list.return_value = (
            dhcp_opt_list)

        returned_dhcp_opt_list = self.vmi_mixin._get_extra_dhcp_opts(vmi_obj)
        self.assertEqual(expected_dhcp_opt_list, returned_dhcp_opt_list)

    def test__get_allowed_adress_pairs(self):
        allowed_addr_pairs = mock.Mock()
        allowed_addr_pair_list = [mock.MagicMock(), mock.MagicMock()]
        allowed_addr_pair_list[0].mac = 'mac-1'
        allowed_addr_pair_list[0].ip.get_ip_prefix_len.return_value = 32
        allowed_addr_pair_list[0].ip.get_ip_prefix.return_value = (
            '10.0.10.10')
        allowed_addr_pair_list[1].mac = 'mac-2'
        allowed_addr_pair_list[1].ip.get_ip_prefix_len.return_value = 24
        allowed_addr_pair_list[1].ip.get_ip_prefix.return_value = (
            '20.0.0.0')
        allowed_addr_pairs.allowed_address_pair = allowed_addr_pair_list
        expected_allowed_addr_paris = [{'mac_address': 'mac-1',
                                        'ip_address': '10.0.10.10'},
                                       {'mac_address': 'mac-2',
                                        'ip_address': '20.0.0.0/24'}]
        vmi_obj = mock.Mock()
        vmi_obj.get_virtual_machine_interface_allowed_address_pairs.return_value = allowed_addr_pairs

        returned_addr_pairs = self.vmi_mixin._get_allowed_adress_pairs(vmi_obj)
        self.assertEqual(expected_allowed_addr_paris, returned_addr_pairs)

    def test__get_allowed_adress_pairs_none(self):
        vmi_obj = mock.Mock()
        vmi_obj.get_virtual_machine_interface_allowed_address_pairs.return_value = (
            None)
        self.assertIsNone(self.vmi_mixin._get_allowed_adress_pairs(vmi_obj))

    def test__ip_address_to_subnet_id_none(self):
        memo_req = {'subnets': {}}
        vn_obj = mock.Mock()
        vn_obj.get_network_ipam_refs.return_value = []
        self.assertIsNone(self.vmi_mixin._ip_address_to_subnet_id('10.0.0.4',
                                                                  vn_obj,
                                                                  memo_req))

    def test__ip_address_to_subnet_id_from_memo_req(self):
        vn_obj = mock.Mock()
        vn_obj.uuid = 'vn-fake-id'
        memo_req = {'subnets': {'vn-fake-id':
                                [{'id': 'foo-id', 'cidr': '10.0.0.0/24'}]}}
        subnet_id = self.vmi_mixin._ip_address_to_subnet_id('10.0.0.5',
                                                            vn_obj,
                                                            memo_req)
        self.assertEqual('foo-id', subnet_id)

    def test__ip_address_to_subnet_id_from_vn_obj(self):
        memo_req = {'subnets': {}}
        fake_vn_obj = mock.Mock()
        
        fake_subnet_vnc = self._get_fake_subnet_vnc('10.0.0.0', '24', 'foo-id')
        fake_ipam_subnets = mock.Mock()
        fake_ipam_subnets.get_ipam_subnets.return_value = [fake_subnet_vnc]
        fake_ipam_refs = [{'attr': fake_ipam_subnets}]
        
        fake_vn_obj.get_network_ipam_refs.return_value = fake_ipam_refs
        subnet_id = self.vmi_mixin._ip_address_to_subnet_id('10.0.0.5',
                                                            fake_vn_obj,
                                                            memo_req)
        self.assertEqual('foo-id', subnet_id)
        self.assertIsNone(self.vmi_mixin._ip_address_to_subnet_id('20.0.0.5',
                                                                  fake_vn_obj,
                                                                  memo_req))

    def test_get_vmi_ip_dict_none(self):
        self.assertEqual([], self.vmi_mixin.get_vmi_ip_dict(mock.ANY,
                                                            mock.ANY,
                                                            mock.ANY))

    def test_get_vmi_ip_dict(self):
        fake_ip_back_refs = [{'uuid': 'fake-ip-1'}, {'uuid': 'fake-ip-2'}]
        fake_vmi_obj = mock.Mock()
        fake_vmi_obj.instance_ip_back_refs = fake_ip_back_refs

        fake_vn_obj = mock.Mock()
        fake_subnet_vnc1 = self._get_fake_subnet_vnc('10.0.0.0', '24',
                                                     'foo-id-1')
        fake_subnet_vnc2 = self._get_fake_subnet_vnc('12.0.0.0', '24',
                                                     'foo-id-2')
        fake_ipam_subnets = mock.Mock()
        fake_ipam_subnets.get_ipam_subnets.return_value = [fake_subnet_vnc1,
                                                           fake_subnet_vnc2]
        fake_ipam_refs = [{'attr': fake_ipam_subnets}]
        
        fake_vn_obj.get_network_ipam_refs.return_value = fake_ipam_refs

        fake_ip_obj1 = mock.Mock()
        fake_ip_obj1.get_instance_ip_address.return_value = '10.0.0.5'

        fake_ip_obj2 = mock.Mock()
        fake_ip_obj2.get_instance_ip_address.return_value = '12.0.0.25'

        self.vnc_lib.instance_ip_read.return_value = fake_ip_obj2

        fake_port_memo = {'instance-ips': {'fake-ip-1': fake_ip_obj1},
                          'subnets': {}}

        expected_ip_dict_list = [{'ip_address': '10.0.0.5',
                                  'subnet_id': 'foo-id-1'},
                                 {'ip_address': '12.0.0.25',
                                  'subnet_id': 'foo-id-2'}]

        returned_ip_dict_list = self.vmi_mixin.get_vmi_ip_dict(
            fake_vmi_obj, fake_vn_obj, fake_port_memo)
        self.assertEqual(expected_ip_dict_list, returned_ip_dict_list)

    def test_get_port_gw_id(self):
        fake_vmi_obj = mock.Mock()
        fake_vmi_obj.get_virtual_machine_refs.return_value = None
        self.assertIsNone(self.vmi_mixin.get_port_gw_id(fake_vmi_obj,
                                                        mock.ANY))

        fake_vm_refs = [{'uuid': 'fake-vm-1'}]
        fake_vmi_obj.get_virtual_machine_refs.return_value = fake_vm_refs
        fake_port_req_memo = {'virtual-machines': {}}

        self.vnc_lib.virtual_machine_read.side_effect = vnc_exc.NoIdError(
            mock.ANY)
        self.assertIsNone(self.vmi_mixin.get_port_gw_id(fake_vmi_obj,
                                                        fake_port_req_memo))

        fake_vm_obj = mock.Mock()
        fake_vm_obj.get_service_instance_refs.return_value = None
        self.vnc_lib.virtual_machine_read.side_effect = None
        self.vnc_lib.virtual_machine_read.return_value = fake_vm_obj
        self.assertIsNone(self.vmi_mixin.get_port_gw_id(fake_vmi_obj,
                                                        fake_port_req_memo))
        self.assertIn('fake-vm-1', fake_port_req_memo['virtual-machines'])

        fake_vm_obj.get_service_instance_refs.return_value = [{'uuid':
                                                               'fake-si'}]

        
        
        self.vnc_lib.service_instance_read.return_value = mock.ANY
        self.assertIsNone(self.vmi_mixin.get_port_gw_id(fake_vmi_obj,
                                                        fake_port_req_memo))
        self.vnc_lib.service_instance_read.assert_called_once_with(
            id='fake-si', fields=["logical_router_back_refs"])

        fake_si_obj = mock.Mock()
        fake_si_obj.logical_router_back_refs = [{'uuid': 'fake-router-id'}]
        self.vnc_lib.service_instance_read.return_value = fake_si_obj

        port_gw_id = self.vmi_mixin.get_port_gw_id(fake_vmi_obj,
                                                   fake_port_req_memo)
        self.assertEqual('fake-router-id', port_gw_id)

    def test__device_ids_from_vmi_objs(self):
        fake_vmi1 = mock.Mock()
        fake_vmi1.get_virtual_machine_refs.return_value = [{'uuid':
                                                         'vm1-device-id'}]

        fake_vmi2 = mock.Mock()
        fake_vmi2.get_virtual_machine_refs.return_value = None
        fake_vmi2.get_logical_router_back_refs.return_value = None

        fake_vmi3 = mock.Mock()
        fake_vmi3.get_virtual_machine_refs.return_value = None
        fake_vmi3.get_logical_router_back_refs.return_value = ([
            {'uuid': 'vm3-device-id'}])

        expected_device_ids = ['vm1-device-id', 'vm3-device-id']
        fake_vmi_objs = [fake_vmi1, fake_vmi2, fake_vmi3]
        returned_device_ids = self.vmi_mixin._device_ids_from_vmi_objs(
            fake_vmi_objs)
        self.assertEqual(expected_device_ids, returned_device_ids)

    def _test__vmi_to_neutron_port_helper(self, allowed_pairs=None,
                                          extensions_enabled=True):
        fake_vmi_obj =  mock.Mock()
        fake_vmi_obj.display_name = 'fake-port'
        fake_vmi_obj.uuid = 'fake-port-uuid'
        fake_vmi_obj.get_fq_name.return_value = ['fake-domain', 'fake-proj', 
                                                 'fake-net-id']

        fake_vmi_obj.get_virtual_network_refs.return_value = [{'uuid':
                                                               'fake-net-id'}]
        fake_vmi_obj.parent_type = ''
        parent_id = str(uuid.uuid4())
        fake_vmi_obj.parent_uuid = parent_id

        fake_mac_refs = mock.Mock()
        fake_mac_refs.mac_address = ['01:02:03:04:05:06']
        fake_vmi_obj.get_virtual_machine_interface_mac_addresses.return_value = (
            fake_mac_refs)

        fake_vmi_obj.get_security_group_refs.return_value = [{'uuid': 'sg-1'},
                                                             {'uuid': 'sg-2'}]
        fake_id_perms = mock.Mock()
        fake_id_perms.enable = True

        fake_vmi_obj.get_id_perms.return_value = fake_id_perms
        fake_vmi_obj.logical_router_back_refs = [{'uuid': 'fake-router-id'}]
        
        fake_vn_obj = mock.Mock()
        fake_vn_obj.parent_uuid = parent_id
        fake_subnet_vnc = self._get_fake_subnet_vnc('10.0.0.0', '24', 'foo-id')
        fake_ipam_subnets = mock.Mock()
        fake_ipam_subnets.get_ipam_subnets.return_value = [fake_subnet_vnc]
        fake_ipam_refs = [{'attr': fake_ipam_subnets}]
        
        fake_vn_obj.get_network_ipam_refs.return_value = fake_ipam_refs
        self.vnc_lib.virtual_network_read.return_value = fake_vn_obj

        expected_port_dict = {}
        expected_port_dict['name'] = 'fake-port'
        expected_port_dict['id'] = 'fake-port-uuid'
        expected_port_dict['tenant_id'] = parent_id.replace('-', '')
        expected_port_dict['network_id'] = 'fake-net-id'
        expected_port_dict['mac_address'] = '01:02:03:04:05:06'
        expected_port_dict['extra_dhcp_opts'] = 'extra-dhcp-opts'
        if allowed_pairs:
            expected_port_dict['allowed_address_pairs'] =  allowed_pairs
        expected_port_dict['fixed_ips'] = [{'ip_address': '10.0.0.4',
                                            'subnet_id': 'fake-subnet-id'}]
        expected_port_dict['security_groups'] = ['sg-1', 'sg-2']
        expected_port_dict['admin_state_up'] = True
        expected_port_dict['device_id'] = 'fake-device-id'
        expected_port_dict['device_owner'] = 'fake-owner'
        expected_port_dict['status'] = n_constants.PORT_STATUS_ACTIVE
        if extensions_enabled:
            expected_port_dict['contrail:fq_name'] = ['fake-domain',
                                                      'fake-proj', 
                                                      'fake-net-id']
            
        with contextlib.nested(
            mock.patch.object(self.vmi_mixin, '_get_extra_dhcp_opts'),
            mock.patch.object(self.vmi_mixin, '_get_allowed_adress_pairs'),
            mock.patch.object(self.vmi_mixin, 'get_vmi_ip_dict'),
            mock.patch.object(self.vmi_mixin, '_get_vmi_device_id_owner')
        ) as (fake_dhcp_opts, fake_addr_pairs, fake_get_vmi_ip_dict,
              fake_device_id_owner):
            fake_dhcp_opts.return_value = 'extra-dhcp-opts'
            fake_addr_pairs.return_value = allowed_pairs
            fake_get_vmi_ip_dict.return_value = (
                [{'ip_address': '10.0.0.4', 'subnet_id':'fake-subnet-id'}])
            fake_device_id_owner.return_value = ('fake-device-id',
                                                 'fake-owner')
            returned_port_dict = self.vmi_mixin._vmi_to_neutron_port(
                fake_vmi_obj, extensions_enabled=extensions_enabled)
            self.assertEqual(expected_port_dict, returned_port_dict)
        
    def test__vmi_to_neutron_port(self):
        self._test__vmi_to_neutron_port_helper()

    def test__vmi_to_neutron_port_allowed_addr_pairs(self):
        self._test__vmi_to_neutron_port_helper(
            allowed_pairs='fake-allowed-pairs')

    def test__vmi_to_neutron_port_extensions_disabled(self):
        self._test__vmi_to_neutron_port_helper(extensions_enabled=False)
