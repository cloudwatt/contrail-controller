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

import bottle
import mock

import test_contrail_res_handler as test_res_handler
from cfgm_common import exceptions as vnc_exc
from vnc_openstack import ipam_res_handler as ipam_handler
from vnc_openstack import vmi_res_handler as vmi_handler
from vnc_openstack import subnet_res_handler as subnet_handler
from vnc_openstack.tests import test_common
from vnc_api import vnc_api


class TestSubnetMixin(test_res_handler.TestContrailBase):

    def setUp(self):
        super(TestSubnetMixin, self).setUp()
        self._subnet_mixin = subnet_handler.SubnetMixin()
        self._subnet_mixin._vnc_lib = self.vnc_lib

    def test__subnet_vnc_read_mapping_id(self):
        self.vnc_lib.kv_retrieve.return_value = 'foo-key'
        self.assertEqual('foo-key',
                         self._subnet_mixin._subnet_vnc_read_mapping(
                            id='foo-id')) 

    def test__subnet_vnc_read_mapping_id_not_exist(self):
        self.vnc_lib.kv_retrieve.side_effect = vnc_exc.NoIdError(mock.ANY)
        vn_objs = [mock.Mock(), mock.Mock()]
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
        fake_vn_obj.uuid = 'foo-net-id'
        self._subnet_mixin._resource_list = mock.Mock()
        self._subnet_mixin._resource_list.return_value = [fake_vn_obj]
        self.assertEqual('foo-net-id 10.0.0.0/24',
                         self._subnet_mixin._subnet_vnc_read_mapping(
                            id='foo-id-1'))
        self.assertRaises(bottle.HTTPError,
                          self._subnet_mixin._subnet_vnc_read_mapping, id='id') 

    def test__subnet_vnc_read_mapping_key(self):
        self.vnc_lib.kv_retrieve.return_value = 'foo-id'
        self.assertEqual('foo-id',
                         self._subnet_mixin._subnet_vnc_read_mapping(
                            key='foo-key')) 

    def test__subnet_vnc_read_mapping_key_not_exists(self):
        self.vnc_lib.kv_retrieve.side_effect = vnc_exc.NoIdError(mock.ANY)
        vn_objs = [mock.Mock(), mock.Mock()]
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
        fake_vn_obj.uuid = 'foo-net-id'

        self._subnet_mixin._resource_get = mock.Mock()
        self._subnet_mixin._resource_get.return_value = fake_vn_obj
        self.assertEqual('foo-id-1',
                         self._subnet_mixin._subnet_vnc_read_mapping(
                            key='foo-net-id 10.0.0.0/24'))
        


class TestSubnetHandlers(test_common.TestBase):
    def setUp(self):
        super(TestSubnetHandlers, self).setUp()
        self._handler = subnet_handler.SubnetHandler(self._test_vnc_lib)

    def test_create(self):
        net_obj = vnc_api.VirtualNetwork('test-net', self.proj_obj)
        self._test_vnc_lib.virtual_network_create(net_obj)

        subnet_q = {'name': 'test-subnet',
                    'cidr': '192.168.1.0/24',
                    'ip_version': '4',
                    'network_id': str(net_obj.uuid)}
        output = {'name': 'test-subnet',
                  'network_id': net_obj.uuid,
                  'allocation_pools ': [{'start': '192.168.1.2',
                                        'end': '192.168.1.254'}],
                  'gateway_ip': '192.168.1.1',
                  'ip_version': 4,
                  'cidr': '192.168.1.0/24',
                  'tenant_id': self.proj_obj.uuid.replace('-', '')}
        entries = [{'input': {
            'subnet_q': subnet_q},
            'output': output}]
        self._test_check_create(entries)
        
        # create a subnet which already exists.
        entries[0]['output'] = bottle.HTTPError
        self._test_check_create(entries)

    def test_create_dhcp_disabled(self):
        net_obj = vnc_api.VirtualNetwork('test-net', self.proj_obj)
        self._test_vnc_lib.virtual_network_create(net_obj)

        subnet_q = {'name': 'test-subnet',
                    'cidr': '192.168.1.0/24',
                    'ip_version': '4',
                    'enable_dhcp': False,
                    'network_id': str(net_obj.uuid)}
        output = {'name': 'test-subnet',
                  'network_id': net_obj.uuid,
                  'allocation_pools ': [{'start': '192.168.1.2',
                                        'end': '192.168.1.254'}],
                  'gateway_ip': '192.168.1.1',
                  'enable_dhcp': False,
                  'ip_version': 4,
                  'cidr': '192.168.1.0/24',
                  'tenant_id': self.proj_obj.uuid.replace('-', '')}
        entries = [{'input': {
            'subnet_q': subnet_q},
            'output': output}]
        self._test_check_create(entries)

    def test_create_allocation_pool(self):
        net_obj = vnc_api.VirtualNetwork('test-net', self.proj_obj)
        self._test_vnc_lib.virtual_network_create(net_obj)

        subnet_q = {'name': 'test-subnet',
                    'cidr': '192.168.1.0/24',
                    'ip_version': '4',
                    'enable_dhcp': True,
                    'network_id': str(net_obj.uuid),
                    'allocation_pools': [{'start': '192.168.1.100',
                                          'end': '192.168.1.1.130'}],
                    'gateway_ip': '192.168.1.4'}
        output = {'name': 'test-subnet',
                  'network_id': net_obj.uuid,
                  'allocation_pools ': [{'start': '192.168.1.100',
                                        'end': '192.168.1.130'}],
                  'gateway_ip': '192.168.1.4',
                  'enable_dhcp': True,
                  'ip_version': 4,
                  'cidr': '192.168.1.0/24',
                  'tenant_id': self.proj_obj.uuid.replace('-', '')}
        entries = [{'input': {
            'subnet_q': subnet_q},
            'output': output}]
        self._test_check_create(entries)

    def _create_test_ipam(self, tenant_id):
        ipam_q = {'name': 'fake-ipam',
                  'tenant_id':  tenant_id}
        ipam_dict = ipam_handler.IPamCreateHandler().resource_create(ipam_q)
        return ipam_handler._resource_get(id=ipam_dict['id'])

    def test_create_ipam_exists(self):
        net_obj = vnc_api.VirtualNetwork('test-net', self.proj_obj)
        self._test_vnc_lib.virtual_network_create(net_obj)
        subnet_q = {'name': 'test-subnet',
                    'cidr': '192.168.1.0/24',
                    'ip_version': '4',
                    'enable_dhcp': True,
                    'network_id': str(net_obj.uuid),
                    'contrail:ipam_fq_name': ['default-domain',
                                              'default-project',
                                              'fake-ipam']}
        output = {'name': 'test-subnet',
                  'network_id': net_obj.uuid,
                  'allocation_pools ': [{'start': '192.168.1.2',
                                        'end': '192.168.1.254'}],
                  'gateway_ip': '192.168.1.1',
                  'ip_version': 4,
                  'cidr': '192.168.1.0/24',
                  'tenant_id': self.proj_obj.uuid.replace('-', '')}
        entries = [{'input': {
            'subnet_q': subnet_q},
            'output': output}]
        self._test_check_create(entries)

