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

from vnc_api import vnc_api

from vnc_openstack import router_res_handler as router_handler
from vnc_openstack.tests import test_common
from vnc_openstack import vn_res_handler as vn_handler


class TestLogicalRouterHandler(test_common.TestBase):
    def setUp(self):
        super(TestLogicalRouterHandler, self).setUp()
        self._handler = router_handler.LogicalRouterHandler(self._test_vnc_lib)

    def _create_external_net(self):
        net_q = {'tenant_id': self._uuid_to_str(self.proj_obj.uuid),
                 'router:external': True,
                 'shared': True,
                 'name': 'public'
                 }

        net_res_q = (vn_handler.VNetworkHandler(
            self._test_vnc_lib).resource_create(net_q))

        # create service instance template
        svc_obj = vnc_api.ServiceTemplate()
        svc_obj.fq_name = router_handler.SNAT_SERVICE_TEMPLATE_FQ_NAME

        self._test_vnc_lib.service_template_create(svc_obj)
        return net_res_q['id']

    def _create_test_router(self, name, admin_state_up=True, tenant_id=None):
        if not tenant_id:
            tenant_id = self._uuid_to_str(self.proj_obj.uuid)

        router_q = {'name': name,
                    'admin_state_up': admin_state_up,
                    'tenant_id': tenant_id}
        return self._handler.resource_create(router_q)['id']

    def _router_count_check(self, exp_count, context=None):
        entries = {'input': {'filters': None},
                   'output': exp_count}
        if context:
            entries['input']['context'] = context

        self._test_check_count([entries])

    def test_create(self):
        tenant_id = self._uuid_to_str(self.proj_obj.uuid)
        external_net_id = self._create_external_net()

        entries = [{'input': {'router_q': {'name': 'test-router-1',
                                           'admin_state_up': True,
                                           'tenant_id': tenant_id}},
                    'output': {'name': 'test-router-1', 'admin_state_up': True,
                               'tenant_id': tenant_id, 'status': 'ACTIVE'}},
                   {'input': {'router_q': {'name': 'test-router-2',
                                           'admin_state_up': False,
                                           'tenant_id': tenant_id}},
                    'output': {'name': 'test-router-2',
                               'admin_state_up': False,
                               'tenant_id': tenant_id, 'status': 'ACTIVE'}},
                   {'input': {'router_q': {'name': 'test-router-3',
                                           'admin_state_up': True,
                                           'tenant_id': tenant_id,
                                           'external_gateway_info':
                                           {'network_id': external_net_id}}},
                    'output': {'name': 'test-router-3',
                               'admin_state_up': True,
                               'tenant_id': tenant_id, 'status': 'ACTIVE',
                               'external_gateway_info': {'network_id':
                                                         external_net_id}}}]
        self._test_check_create(entries)

    def test_delete(self):
        rtr_1 = self._create_test_router('router-1')
        rtr_2 = self._create_test_router('router-2', admin_state_up=False)
        self._router_count_check(2)
        self._handler.resource_delete(rtr_1)
        self._router_count_check(1)
        self._handler.resource_delete(rtr_2)
        self._router_count_check(0)

    def test_update(self):
        rtr_id = self._create_test_router('router-1')
        router_q = {'name': 'new-router'}
        entries = [{'input': {'router_q': router_q, 'rtr_id': rtr_id},
                    'output': {'name': 'new-router'}}]
        self._test_check_update(entries)

        # set the gw
        ext_net_id = self._create_external_net()
        router_q['external_gateway_info'] = {'network_id': ext_net_id}
        entries = [{'input': {'router_q': router_q, 'rtr_id': rtr_id},
                    'output': {'name': 'new-router',
                               'external_gateway_info': {'network_id':
                                                         ext_net_id}}}]
        self._test_check_update(entries)

        # clear the gw
        self._test_check_update(entries)
        router_q = {'name': 'new-router'}
        entries = [{'input': {'router_q': router_q, 'rtr_id': rtr_id},
                    'output': {'name': 'new-router',
                               'external_gateway_info': None}}]
        self._test_check_update(entries)

    def test_get(self):
        rtr_id = self._create_test_router('router-1')
        entries = [{'input': rtr_id,
                   'output': {'name': 'router-1',
                              'external_gateway_info': None,
                              'admin_state_up': True,
                              'status': 'ACTIVE',
                              'tenant_id':
                              self._uuid_to_str(self.proj_obj.uuid)}}]
        self._test_check_get(entries)

    def test_list(self):
        proj_1 = self._project_create('proj-1')
        proj_2 = self._project_create('proj-2')
        self._create_test_router('p1-router-1', tenant_id=proj_1.uuid)
        self._create_test_router('p1-router-2', tenant_id=proj_1.uuid)
        self._create_test_router('p2-router-1', tenant_id=proj_2.uuid)

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
             'output': [{'name': 'p1-router-1'},
                        {'name': 'p1-router-2'},
                        {'name': 'p2-router-1'}]},

            # non-admin context with proj-1 and with filters of proj-2
            {'input': {
                'context': {
                    'tenant': self._uuid_to_str(proj_1.uuid),
                    'is_admin': False},
                'filters': {
                    'tenant_id': [self._uuid_to_str(proj_2.uuid)]}},
                'output': [{'name': 'p1-router-1'},
                           {'name': 'p1-router-2'}]},

            # admin context with proj-1 and with filters of proj-2
            {'input': {
                'context': {
                    'tenant': self._uuid_to_str(proj_1.uuid),
                    'is_admin': True},
                'filters': {
                    'tenant_id': [self._uuid_to_str(proj_2.uuid)]}},
                'output': [{'name': 'p2-router-1'}]}]

        self._test_check_list(entries)
