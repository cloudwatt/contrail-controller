from vnc_openstack import policy_res_handler as policy_handler
from vnc_openstack.tests import test_common


class TestPolicyHandlers(test_common.TestBase):
    def setUp(self):
        super(TestPolicyHandlers, self).setUp()
        self._handler = policy_handler.PolicyHandler(self._test_vnc_lib)

    def test_create(self):
        entries = [
            {'input': {'tenant_id': self.proj_obj.uuid.replace('-', ''),
                       'entries': {'policy_rule': []}},
             'output': {'id': self._generated(),
                        'fq_name': ['default-domain', 'default-project']}}]
        super(TestPolicyHandlers, self).test_create(entries)
