import unittest
import uuid
from cfgm_common import exceptions as vnc_exc
from vnc_api import vnc_api
from vnc_openstack.tests.vnc_mock import MockVnc


class TestBase(unittest.TestCase):
    def setUp(self):
        self._test_vnc_lib = MockVnc()

        domain_obj = vnc_api.Domain()
        self._test_vnc_lib.domain_create(domain_obj)

        self.proj_obj = vnc_api.Project(parent_obj=domain_obj)
        self._test_vnc_lib.project_create(self.proj_obj)

    def tearDown(self):
        pass

    def _generated(self):
        return 0xFF

    def _compare(self, verify, against):
        if type(verify) != type(against):
            return False

        if isinstance(verify, dict):
            return self._compare_dict(verify, against)
        elif isinstance(verify, list):
            return self._compare_list(verify, against)
        else:
            return verify in [against, self._generated()]

    def _compare_list(self, verify, against):
        for v in verify:
            for index, a in enumerate(against):
                if self._compare(v, a):
                    break
            if index < len(against):
                against.pop(index)
            else:
                return False

        return True

    def _compare_dict(self, verify, against):
        if not verify and not against:
            return True

        for k, v in against.iteritems():
            if (k in verify):
                if not self._compare(v, verify[k]):
                    return False
            else:
                return False

        return True

    def test_create(self, test_entries):
        # test with empty dict
        with self.assertRaises(Exception):
            self._handler.resource_create({})

        # put some invalid tenant id and check for exception
        _q = {}
        _q['tenant_id'] = uuid.UUID('00000000000000000000000000000000')
        with self.assertRaises(Exception):
            self._handler.resource_create(_q)

        for entry in test_entries:

            if type(entry['output']) == type and issubclass(entry['output'], Exception):
                with assertRaises(entry['output']):
                    self._handler._resource_create(entry['input'])
            else:
                ret = self._handler.resource_create(entry['input'])
                self.assertTrue(self._compare(ret, entry['input']))
