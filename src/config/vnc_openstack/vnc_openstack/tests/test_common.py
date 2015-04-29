import unittest
import uuid
import bottle
from vnc_api import vnc_api
from vnc_openstack.tests.vnc_mock import MockVnc


class TestBase(unittest.TestCase):
    def setUp(self):
        self._test_vnc_lib = MockVnc()

        self.domain_obj = vnc_api.Domain()
        self._test_vnc_lib.domain_create(self.domain_obj)

        self.proj_obj = self._project_create()

    def tearDown(self):
        pass

    def _project_create(self, name=None):
        proj_obj = vnc_api.Project(parent_obj=self.domain_obj, name=name)
        self._test_vnc_lib.project_create(proj_obj)
        return proj_obj

    def _generated(self):
        return 0xFF

    def _uuid_to_str(self, uuid):
        return str(uuid).replace('-', '')

    def _compare(self, verify, against):
        print " -- Checking %s *** against *** %s" % (verify, against)
        if (isinstance(verify, dict) or isinstance(verify, list)) and \
                type(verify) != type(against):
            return False

        if isinstance(verify, dict):
            return self._compare_dict(verify, against)
        elif isinstance(verify, list):
            return self._compare_list(verify, against)
        else:
            return verify in [against, self._generated()]

    def _compare_list(self, verify, against):
        _against = list(against)
        for v in verify:
            for index, a in enumerate(_against):
                if self._compare(v, a):
                    break
            if index < len(_against):
                _against.pop(index)
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

    def _test_check(self, _handler_method, test_entries):
        for entry in test_entries:
            if type(entry['output']) == type and \
                    issubclass(entry['output'], Exception):
                with self.assertRaises(entry['output']):
                    _handler_method(entry['input'])
            else:
                ret = _handler_method(entry['input'])
                self.assertTrue(self._compare(ret, entry['output']))

    def _test_failures_on_create(self, null_entry=False,
                                 invalid_tenant=False):
        if null_entry:
            # test with empty dict
            with self.assertRaises(bottle.HTTPError):
                self._handler.resource_create({})

        if invalid_tenant:
            # put some invalid tenant id and check for exception
            _q = {}
            _q['tenant_id'] = '00000000000000000000000000000000'
            with self.assertRaises(bottle.HTTPError):
                self._handler.resource_create(_q)

    def _test_check_create(self, entries):
        return self._test_check(self._handler.resource_create, entries)

    def _test_check_update(self, entries):
        def _pre_handler(inp):
            return self._handler.resource_update(**inp)
        return self._test_check(_pre_handler, entries)

    def _test_failures_on_list(self, invalid_tenant=False):
        filters = {'tenant_id': '00000000000000000000000000000000'}
        ret = self._handler.resource_list(context=None, filters=filters)
        self.assertEqual(ret, [])

    def _test_check_list(self, entries):
        def _pre_handler(inp):
            return self._handler.resource_list(**inp)
        return self._test_check(_pre_handler, entries)

    def _test_check_count(self, entries):
        def _pre_handler(inp):
            return self._handler.resource_count(**inp)
        return self._test_check(_pre_handler, entries)

    def _test_failures_on_get(self):
        # input a invalid uuid and check for exception
        with self.assertRaises(bottle.HTTPError):
            self._handler.resource_get(
                str(uuid.UUID('00000000000000000000000000000000')))

    def _test_failures_on_update(self):
        # input a invalid uuid and check for exception
        with self.assertRaises(bottle.HTTPError):
            self._handler.resource_update(
                str(uuid.UUID('00000000000000000000000000000000')), {})

    def _test_failures_on_delete(self, id=None):
        # input a invalid uuid and check for exception
        id = str(uuid.UUID('00000000000000000000000000000000')) \
            if not id else id
        with self.assertRaises(bottle.HTTPError):
            self._handler.resource_delete(id)

    def _test_check_get(self, entries):
        return self._test_check(self._handler.resource_get, entries)

    def _test_check_delete(self, entries):
        return self._test_check(self._handler.resource_delete, entries)
