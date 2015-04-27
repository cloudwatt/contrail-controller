from cfgm_common import exceptions as vnc_exc
import json
import uuid as UUID


class MockVnc(object):
    def __init__(self):
        self.resources_collection = dict()

    def _break_method(self, method):
        rin = method.rindex('_')
        return (method[:rin], method[rin+1:])

    class Callables(object):
        def __init__(self, resource_type, resource, resource_collection):
            self._resource_type = resource_type.replace('_', '-')
            self._resource = resource
            self._resource_collection = resource_collection

    class ReadCallables(Callables):
        def __call__(self, **kwargs):
            if 'id' in kwargs:
                if kwargs['id'] in self._resource:
                    return self._resource[kwargs['id']]
            if 'fq_name_str' in kwargs or \
               'fq_name' in kwargs:
                fq_name_str = kwargs['fq_name_str'] \
                              if 'fq_name_str' in kwargs else \
                              ':'.join(kwargs['fq_name'])
                if fq_name_str in self._resource:
                    return self._resource[fq_name_str]

            # Not found yet
            raise vnc_exc.NoIdError(
                kwargs['id'] if 'id' in kwargs else None)

    class ListCallables(Callables):
        def __call__(self, parent_id=None, parent_fq_name=None,
                     back_ref_id=None, obj_uuids=None, fields=None,
                     detail=False, count=False):
            ret = []
            if parent_fq_name:
                for res in set(self._resource.values()):
                    if set(res.get_parent_fq_name()) == set(parent_fq_name):
                        ret.append(res)
            elif obj_uuids:
                for res in set(self._resource.values()):
                    if res.uuid in obj_uuids:
                        ret.append(res)
            else:
                for res in set(self._resource.values()):
                    ret.append(res)

            if count:
                return {"count": len(ret)}

            if not detail:
                sret = []
                for res in ret:
                    sret.append(res.serialize_to_json())
            return {self._resource_type + "s": sret}

    class CreateCallables(Callables):
        def __call__(self, obj):
            if not obj:
                raise ValueError("Create called with null object")

            uuid = getattr(obj, 'uuid', None)
            if not uuid:
                uuid = obj.uuid = str(UUID.uuid4())

            if hasattr(obj, 'parent_type'):
                rc = MockVnc.ReadCallables(
                    obj.parent_type,
                    self._resource_collection[obj.parent_type],
                    self._resource_collection)
                parent = rc(fq_name=obj.fq_name[:-1])
                obj.parent_uuid = parent.uuid

            fq_name_str = getattr(obj, 'fq_name_str', None)
            if not fq_name_str:
                fq_name_str = ":".join(obj.get_fq_name())

            self._resource[uuid] = obj

            if fq_name_str:
                if fq_name_str in self._resource:
                    raise ValueError(
                        "%s fq_name already exists, please use "
                        "a different name" % fq_name_str)

                self._resource[fq_name_str] = obj

    class UpdateCallables(Callables):
        def __call__(self, obj):
            if obj.uuid:
                cur_obj = self._resource[obj.uuid]
            else:
                cur_obj = self._resource[':'.join(obj.get_fq_name())]

            if obj._pending_ref_updates:
                for ref in obj._pending_ref_updates:
                    if ref.endswith("_refs"):
                        ref = ref[:-5].replace('_', '-')
                    obj_ref = cur_obj.getattr(ref)

                    obj_ref.append(getattr(obj, ref))

            if obj._pending_field_updates:
                for ref in obj._pending_field_updates:
                    if ref.endswith("_refs"):
                        ref = ref[:-5].replace('_', '-')
                    setattr(cur_obj, ref, getattr(obj, ref))

    class DeleteCallables(Callables):
        def __call__(self, **kwargs):
            obj = None
            if 'fq_name' in kwargs and kwargs['fq_name']:
                fq_name_str = ':'.join(kwargs['fq_name'])
                obj = self._resource[fq_name_str]

            if 'id' in kwargs:
                obj = self._resource[kwargs['id']]

            if not obj:
                raise vnc_exc.NoIdError(
                    kwargs['id'] if 'id' in kwargs else None)

            self._resource.pop(obj.uuid)
            self._resource.pop(':'.join(obj.get_fq_name()), None)

    def __getattr__(self, method):
        (resource, action) = self._break_method(method)

        if action not in ['list', 'read', 'create',
                          'update', 'delete']:
            raise ValueError("Unknown action %s received for %s method" %
                             (action, method))

        if action == 'list':
            # for 'list' action resource will be like resourceS
            resource = resource[:-1]
        callables_map = {'list': MockVnc.ListCallables,
                         'read': MockVnc.ReadCallables,
                         'create': MockVnc.CreateCallables,
                         'update': MockVnc.UpdateCallables,
                         'delete': MockVnc.DeleteCallables}

        if resource not in self.resources_collection:
            self.resources_collection[resource] = dict()

        return callables_map[action](
            resource, self.resources_collection[resource],
            self.resources_collection)

    def _obj_serializer_all(self, obj):
        if hasattr(obj, 'serialize_to_json'):
            return obj.serialize_to_json()
        else:
            return dict((k, v) for k, v in obj.__dict__.iteritems())

    def obj_to_json(self, obj):
        return json.dumps(obj, default=self._obj_serializer_all)

    def obj_to_dict(self, obj):
        return json.loads(self.obj_to_json(obj))
