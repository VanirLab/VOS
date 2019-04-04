import asyncio
import functools
import itertools
import os
import string
import subprocess

import libvirt
import pkg_resources
import yaml

import vanir.api
import vanir.backup
import vanir.config
import vanir.devices
import vanir.firewall
import vanir.storage
import vanir.utils
import vanir.vm
import vanir.vm.adminvm
import vanir.vm.vanirvm


class VanirMgmtEventsDispatcher:
    def __init__(self, filters, send_event):
        self.filters = filters
        self.send_event = send_event

    def vm_handler(self, subject, event, **kwargs):
        # do not send internal events
        if event.startswith('admin-permission:'):
            return
        if event.startswith('device-get:'):
            return
        if event.startswith('device-list:'):
            return
        if event.startswith('device-list-attached:'):
            return
        if event in ('domain-is-fully-usable',):
            return

        if not list(vanir.api.apply_filters([(subject, event, kwargs)],
                self.filters)):
            return
        self.send_event(subject, event, **kwargs)

    def app_handler(self, subject, event, **kwargs):
        if not list(vanir.api.apply_filters([(subject, event, kwargs)],
                self.filters)):
            return
        self.send_event(subject, event, **kwargs)

    def on_domain_add(self, subject, event, vm):
        # pylint: disable=unused-argument
        vm.add_handler('*', self.vm_handler)

    def on_domain_delete(self, subject, event, vm):
        # pylint: disable=unused-argument
        vm.remove_handler('*', self.vm_handler)


class VanirAdminAPI(vanir.api.AbstractQubesAPI):
    '''Implementation of Vanir Management API calls
    This class contains all the methods available in the main API.
   
      
    '''

    SOCKNAME = '/var/run/vanirsd.sock'

    @vanir.api.method('admin.vmclass.List', no_payload=True,
        scope='global', read=True)
    @asyncio.coroutine
    def vmclass_list(self):
        '''List all VM classes'''
        self.enforce(not self.arg)
        self.enforce(self.dest.name == 'dom0')

        entrypoints = self.fire_event_for_filter(
            pkg_resources.iter_entry_points(vanir.vm.VM_ENTRY_POINT))

        return ''.join('{}\n'.format(ep.name)
            for ep in entrypoints)

    @vanir.api.method('admin.vm.List', no_payload=True,
        scope='global', read=True)
    @asyncio.coroutine
    def vm_list(self):
        '''List all the domains'''
        self.enforce(not self.arg)

        if self.dest.name == 'dom0':
            domains = self.fire_event_for_filter(self.app.domains)
        else:
            domains = self.fire_event_for_filter([self.dest])

        return ''.join('{} class={} state={}\n'.format(
                vm.name,
                vm.__class__.__name__,
                vm.get_power_state())
            for vm in sorted(domains))

    @vanir.api.method('admin.vm.property.List', no_payload=True,
        scope='local', read=True)
    @asyncio.coroutine
    def vm_property_list(self):
        '''List all properties on a qube'''
        return self._property_list(self.dest)

    @vanir.api.method('admin.property.List', no_payload=True,
        scope='global', read=True)
    @asyncio.coroutine
    def property_list(self):
        '''List all global properties'''
        self.enforce(self.dest.name == 'dom0')
        return self._property_list(self.app)

    def _property_list(self, dest):
        self.enforce(not self.arg)

        properties = self.fire_event_for_filter(dest.property_list())

        return ''.join('{}\n'.format(prop.__name__) for prop in properties)

    @vanir.api.method('admin.vm.property.Get', no_payload=True,
        scope='local', read=True)
    @asyncio.coroutine
    def vm_property_get(self):
        '''Get a value of one property'''
        return self._property_get(self.dest)

    @vanir.api.method('admin.property.Get', no_payload=True,
        scope='global', read=True)
    @asyncio.coroutine
    def property_get(self):
        '''Get a value of one global property'''
        self.enforce(self.dest.name == 'dom0')
        return self._property_get(self.app)

    def _property_get(self, dest):
        if self.arg not in dest.property_list():
            raise vanir.exc.VanirNoSuchPropertyError(dest, self.arg)

        self.fire_event_for_permission()

        property_def = dest.property_get_def(self.arg)
        # explicit list to be sure that it matches protocol spec
        if isinstance(property_def, vanir.vm.VMProperty):
            property_type = 'vm'
        elif property_def.type is int:
            property_type = 'int'
        elif property_def.type is bool:
            property_type = 'bool'
        elif self.arg == 'label':
            property_type = 'label'
        else:
            property_type = 'str'

        try:
            value = getattr(dest, self.arg)
        except AttributeError:
            return 'default=True type={} '.format(property_type)
        else:
            return 'default={} type={} {}'.format(
                str(dest.property_is_default(self.arg)),
                property_type,
                str(value) if value is not None else '')

    @vanir.api.method('admin.vm.property.GetDefault', no_payload=True,
        scope='local', read=True)
    @asyncio.coroutine
    def vm_property_get_default(self):
        '''Get a value of one property'''
        return self._property_get_default(self.dest)

    @vanir.api.method('admin.property.GetDefault', no_payload=True,
        scope='global', read=True)
    @asyncio.coroutine
    def property_get_default(self):
        '''Get a value of one global property'''
        self.enforce(self.dest.name == 'dom0')
        return self._property_get_default(self.app)

    def _property_get_default(self, dest):
        if self.arg not in dest.property_list():
            raise vanir.exc.VanirNoSuchPropertyError(dest, self.arg)

        self.fire_event_for_permission()

        property_def = dest.property_get_def(self.arg)
        # explicit list to be sure that it matches protocol spec
        if isinstance(property_def, vanir.vm.VMProperty):
            property_type = 'vm'
        elif property_def.type is int:
            property_type = 'int'
        elif property_def.type is bool:
            property_type = 'bool'
        elif self.arg == 'label':
            property_type = 'label'
        else:
            property_type = 'str'

        try:
            value = property_def.get_default(dest)
        except AttributeError:
            return None
        else:
            return 'type={} {}'.format(
                property_type,
                str(value) if value is not None else '')

    @vanir.api.method('admin.vm.property.Set',
        scope='local', write=True)
    @asyncio.coroutine
    def vm_property_set(self, untrusted_payload):
        '''Set property value'''
        return self._property_set(self.dest,
            untrusted_payload=untrusted_payload)

    @vanir.api.method('admin.property.Set',
        scope='global', write=True)
    @asyncio.coroutine
    def property_set(self, untrusted_payload):
        '''Set property value'''
        self.enforce(self.dest.name == 'dom0')
        return self._property_set(self.app,
            untrusted_payload=untrusted_payload)

    def _property_set(self, dest, untrusted_payload):
        if self.arg not in dest.property_list():
            raise vanir.exc.VanirNoSuchPropertyError(dest, self.arg)

        property_def = dest.property_get_def(self.arg)
        newvalue = property_def.sanitize(untrusted_newvalue=untrusted_payload)

        self.fire_event_for_permission(newvalue=newvalue)

        setattr(dest, self.arg, newvalue)
        self.app.save()

    @vanir.api.method('admin.vm.property.Help', no_payload=True,
        scope='local', read=True)
    @asyncio.coroutine
    def vm_property_help(self):
        '''Get help for one property'''
        return self._property_help(self.dest)

    @vanir.api.method('admin.property.Help', no_payload=True,
        scope='global', read=True)
    @asyncio.coroutine
    def property_help(self):
        '''Get help for one property'''
        self.enforce(self.dest.name == 'dom0')
        return self._property_help(self.app)

    def _property_help(self, dest):
        if self.arg not in dest.property_list():
            raise vanir.exc.VanirNoSuchPropertyError(dest, self.arg)

        self.fire_event_for_permission()

        try:
            doc = dest.property_get_def(self.arg).__doc__
        except AttributeError:
            return ''

        return vanir.utils.format_doc(doc)

    @vanir.api.method('admin.vm.property.Reset', no_payload=True,
        scope='local', write=True)
    @asyncio.coroutine
    def vm_property_reset(self):
        '''Reset a property to a default value'''
        return self._property_reset(self.dest)

    @vanir.api.method('admin.property.Reset', no_payload=True,
        scope='global', write=True)
    @asyncio.coroutine
    def property_reset(self):
        '''Reset a property to a default value'''
        self.enforce(self.dest.name == 'dom0')
        return self._property_reset(self.app)

    def _property_reset(self, dest):
        if self.arg not in dest.property_list():
            raise vanir.exc.VanirNoSuchPropertyError(dest, self.arg)

        self.fire_event_for_permission()

        delattr(dest, self.arg)
        self.app.save()

    @vanir.api.method('admin.vm.volume.List', no_payload=True,
        scope='local', read=True)
    @asyncio.coroutine
    def vm_volume_list(self):
        self.enforce(not self.arg)

        volume_names = self.fire_event_for_filter(self.dest.volumes.keys())
        return ''.join('{}\n'.format(name) for name in volume_names)

    @vanir.api.method('admin.vm.volume.Info', no_payload=True,
        scope='local', read=True)
    @asyncio.coroutine
    def vm_volume_info(self):
        self.enforce(self.arg in self.dest.volumes.keys())

        self.fire_event_for_permission()

        volume = self.dest.volumes[self.arg]
        # properties defined in API
        volume_properties = [
            'pool', 'vid', 'size', 'usage', 'rw', 'source', 'path',
            'save_on_stop', 'snap_on_start', 'revisions_to_keep']

        def _serialize(value):
            if callable(value):
                value = value()
            if value is None:
                value = ''
            return str(value)
        info = ''.join('{}={}\n'.format(key, _serialize(getattr(volume, key)))
            for key in volume_properties)
        try:
            info += 'is_outdated={}\n'.format(volume.is_outdated())
        except NotImplementedError:
            pass
        return info

    @vanir.api.method('admin.vm.volume.ListSnapshots', no_payload=True,
        scope='local', read=True)
    @asyncio.coroutine
    def vm_volume_listsnapshots(self):
        self.enforce(self.arg in self.dest.volumes.keys())

        volume = self.dest.volumes[self.arg]
        id_to_timestamp = volume.revisions
        revisions = sorted(id_to_timestamp, key=id_to_timestamp.__getitem__)
        revisions = self.fire_event_for_filter(revisions)

        return ''.join('{}\n'.format(revision) for revision in revisions)

    @vanir.api.method('admin.vm.volume.Revert',
        scope='local', write=True)
    @asyncio.coroutine
    def vm_volume_revert(self, untrusted_payload):
        self.enforce(self.arg in self.dest.volumes.keys())
        untrusted_revision = untrusted_payload.decode('ascii').strip()
        del untrusted_payload

        volume = self.dest.volumes[self.arg]
        snapshots = volume.revisions
        self.enforce(untrusted_revision in snapshots)
        revision = untrusted_revision

        self.fire_event_for_permission(volume=volume, revision=revision)

        ret = volume.revert(revision)
        if asyncio.iscoroutine(ret):
            yield from ret
        self.app.save()

    # write=True because this allow to clone VM - and most likely modify that
    # one - still having the same data
    @vanir.api.method('admin.vm.volume.CloneFrom', no_payload=True,
        scope='local', write=True)
    @asyncio.coroutine
    def vm_volume_clone_from(self):
        self.enforce(self.arg in self.dest.volumes.keys())

        volume = self.dest.volumes[self.arg]

        self.fire_event_for_permission(volume=volume)

        token = vanir.utils.random_string(32)
        # save token on self.app, as self is not persistent
        if not hasattr(self.app, 'api_admin_pending_clone'):
            self.app.api_admin_pending_clone = {}
        # don't handle collisions any better - if someone is so much out of
        # luck, can try again anyway
        self.enforce(token not in self.app.api_admin_pending_clone)

        self.app.api_admin_pending_clone[token] = volume
        return token

    @vanir.api.method('admin.vm.volume.CloneTo',
        scope='local', write=True)
    @asyncio.coroutine
    def vm_volume_clone_to(self, untrusted_payload):
        self.enforce(self.arg in self.dest.volumes.keys())
        untrusted_token = untrusted_payload.decode('ascii').strip()
        del untrusted_payload
        self.enforce(
            untrusted_token in getattr(self.app, 'api_admin_pending_clone', {}))
        token = untrusted_token
        del untrusted_token

        src_volume = self.app.api_admin_pending_clone[token]
        del self.app.api_admin_pending_clone[token]

        # make sure the volume still exists, but invalidate token anyway
        self.enforce(str(src_volume.pool) in self.app.pools)
        self.enforce(src_volume in self.app.pools[str(src_volume.pool)].volumes)

        dst_volume = self.dest.volumes[self.arg]

        self.fire_event_for_permission(src_volume=src_volume,
            dst_volume=dst_volume)

        op_retval = dst_volume.import_volume(src_volume)

        # clone/import functions may be either synchronous or asynchronous
        # in the later case, we need to wait for them to finish
        if asyncio.iscoroutine(op_retval):
            op_retval = yield from op_retval

        self.dest.volumes[self.arg] = op_retval
        self.app.save()

    @vanir.api.method('admin.vm.volume.Resize',
        scope='local', write=True)
    @asyncio.coroutine
    def vm_volume_resize(self, untrusted_payload):
        self.enforce(self.arg in self.dest.volumes.keys())
        untrusted_size = untrusted_payload.decode('ascii').strip()
        del untrusted_payload
        self.enforce(untrusted_size.isdigit())   # only digits, forbid '-' too
        self.enforce(len(untrusted_size) <= 20)  # limit to about 2^64

        size = int(untrusted_size)

        self.fire_event_for_permission(size=size)

        yield from self.dest.storage.resize(self.arg, size)
        self.app.save()

    @vanir.api.method('admin.vm.volume.Import', no_payload=True,
        scope='local', write=True)
    @asyncio.coroutine
    def vm_volume_import(self):
        '''Import volume data.
        Note that this function only returns a path to where data should be
        written, actual importing is done by a script in /etc/vanir-rpc
        When the script finish importing, it will trigger
        internal.vm.volume.ImportEnd (with either b'ok' or b'fail' as a
        payload) and response from that call will be actually send to the
        caller.
        '''
        self.enforce(self.arg in self.dest.volumes.keys())

        self.fire_event_for_permission()

        if not self.dest.is_halted():
            raise vanir.exc.VanirVMNotHaltedError(self.dest)

        path = yield from self.dest.storage.import_data(self.arg)
        self.enforce(' ' not in path)
        size = self.dest.volumes[self.arg].size

        # when we know the action is allowed, inform extensions that it will
        # be performed
        self.dest.fire_event('domain-volume-import-begin', volume=self.arg)

        return '{} {}'.format(size, path)

    @vanir.api.method('admin.vm.volume.Set.revisions_to_keep',
        scope='local', write=True)
    @asyncio.coroutine
    def vm_volume_set_revisions_to_keep(self, untrusted_payload):
        self.enforce(self.arg in self.dest.volumes.keys())
        try:
            untrusted_value = int(untrusted_payload.decode('ascii'))
        except (UnicodeDecodeError, ValueError):
            raise vanir.api.ProtocolError('Invalid value')
        del untrusted_payload
        self.enforce(untrusted_value >= 0)
        newvalue = untrusted_value
        del untrusted_value

        self.fire_event_for_permission(newvalue=newvalue)

        self.dest.volumes[self.arg].revisions_to_keep = newvalue
        self.app.save()

    @vanir.api.method('admin.vm.volume.Set.rw',
        scope='local', write=True)
    @asyncio.coroutine
    def vm_volume_set_rw(self, untrusted_payload):
        self.enforce(self.arg in self.dest.volumes.keys())
        try:
            newvalue = vanir.property.bool(None, None,
                untrusted_payload.decode('ascii'))
        except (UnicodeDecodeError, ValueError):
            raise vanir.api.ProtocolError('Invalid value')
        del untrusted_payload

        self.fire_event_for_permission(newvalue=newvalue)

        if not self.dest.is_halted():
            raise vanir.exc.VanirVMNotHaltedError(self.dest)

        self.dest.volumes[self.arg].rw = newvalue
        self.app.save()

    @vanir.api.method('admin.vm.tag.List', no_payload=True,
        scope='local', read=True)
    @asyncio.coroutine
    def vm_tag_list(self):
        self.enforce(not self.arg)

        tags = self.dest.tags

        tags = self.fire_event_for_filter(tags)

        return ''.join('{}\n'.format(tag) for tag in sorted(tags))

    @vanir.api.method('admin.vm.tag.Get', no_payload=True,
        scope='local', read=True)
    @asyncio.coroutine
    def vm_tag_get(self):
        vanir.vm.Tags.validate_tag(self.arg)

        self.fire_event_for_permission()

        return '1' if self.arg in self.dest.tags else '0'

    @vanir.api.method('admin.vm.tag.Set', no_payload=True,
        scope='local', write=True)
    @asyncio.coroutine
    def vm_tag_set(self):
        vanir.vm.Tags.validate_tag(self.arg)

        self.fire_event_for_permission()

        self.dest.tags.add(self.arg)
        self.app.save()

    @vanir.api.method('admin.vm.tag.Remove', no_payload=True,
        scope='local', write=True)
    @asyncio.coroutine
    def vm_tag_remove(self):
        vanir.vm.Tags.validate_tag(self.arg)

        self.fire_event_for_permission()

        try:
            self.dest.tags.remove(self.arg)
        except KeyError:
            raise vanir.exc.VanirTagNotFoundError(self.dest, self.arg)
        self.app.save()

    @vanir.api.method('admin.pool.List', no_payload=True,
        scope='global', read=True)
    @asyncio.coroutine
    def pool_list(self):
        self.enforce(not self.arg)
        self.enforce(self.dest.name == 'dom0')

        pools = self.fire_event_for_filter(self.app.pools)

        return ''.join('{}\n'.format(pool) for pool in pools)

    @vanir.api.method('admin.pool.ListDrivers', no_payload=True,
        scope='global', read=True)
    @asyncio.coroutine
    def pool_listdrivers(self):
        self.enforce(self.dest.name == 'dom0')
        self.enforce(not self.arg)

        drivers = self.fire_event_for_filter(vanir.storage.pool_drivers())

        return ''.join('{} {}\n'.format(
            driver,
            ' '.join(vanir.storage.driver_parameters(driver)))
            for driver in drivers)

    @vanir.api.method('admin.pool.Info', no_payload=True,
        scope='global', read=True)
    @asyncio.coroutine
    def pool_info(self):
        self.enforce(self.dest.name == 'dom0')
        self.enforce(self.arg in self.app.pools.keys())

        pool = self.app.pools[self.arg]

        self.fire_event_for_permission(pool=pool)

        other_info = ''
        pool_size = pool.size
        if pool_size is not None:
            other_info += 'size={}\n'.format(pool_size)

        pool_usage = pool.usage
        if pool_usage is not None:
            other_info += 'usage={}\n'.format(pool_usage)

        try:
            included_in = pool.included_in(self.app)
            if included_in:
                other_info += 'included_in={}\n'.format(str(included_in))
        except NotImplementedError:
            pass

        return ''.join('{}={}\n'.format(prop, val)
            for prop, val in sorted(pool.config.items())) + \
            other_info

    @vanir.api.method('admin.pool.Add',
        scope='global', write=True)
    @asyncio.coroutine
    def pool_add(self, untrusted_payload):
        self.enforce(self.dest.name == 'dom0')
        drivers = vanir.storage.pool_drivers()
        self.enforce(self.arg in drivers)
        untrusted_pool_config = untrusted_payload.decode('ascii').splitlines()
        del untrusted_payload
        self.enforce(all(('=' in line) for line in untrusted_pool_config))
        # pairs of (option, value)
        untrusted_pool_config = [line.split('=', 1)
            for line in untrusted_pool_config]
        # reject duplicated options
        self.enforce(
            len(set(x[0] for x in untrusted_pool_config)) ==
            len([x[0] for x in untrusted_pool_config]))
        # and convert to dict
        untrusted_pool_config = dict(untrusted_pool_config)

        self.enforce('name' in untrusted_pool_config)
        untrusted_pool_name = untrusted_pool_config.pop('name')
        allowed_chars = string.ascii_letters + string.digits + '-_.'
        self.enforce(all(c in allowed_chars for c in untrusted_pool_name))
        pool_name = untrusted_pool_name
        self.enforce(pool_name not in self.app.pools)

        driver_parameters = vanir.storage.driver_parameters(self.arg)
        self.enforce(
            all(key in driver_parameters for key in untrusted_pool_config))
        pool_config = untrusted_pool_config

        self.fire_event_for_permission(name=pool_name,
            pool_config=pool_config)

        yield from self.app.add_pool(name=pool_name, driver=self.arg,
            **pool_config)
        self.app.save()

    @vanir.api.method('admin.pool.Remove', no_payload=True,
        scope='global', write=True)
    @asyncio.coroutine
    def pool_remove(self):
        self.enforce(self.dest.name == 'dom0')
        self.enforce(self.arg in self.app.pools.keys())

        self.fire_event_for_permission()

        yield from self.app.remove_pool(self.arg)
        self.app.save()

    @vanir.api.method('admin.pool.Set.revisions_to_keep',
        scope='global', write=True)
    @asyncio.coroutine
    def pool_set_revisions_to_keep(self, untrusted_payload):
        self.enforce(self.dest.name == 'dom0')
        self.enforce(self.arg in self.app.pools.keys())
        pool = self.app.pools[self.arg]
        try:
            untrusted_value = int(untrusted_payload.decode('ascii'))
        except (UnicodeDecodeError, ValueError):
            raise vanir.api.ProtocolError('Invalid value')
        del untrusted_payload
        self.enforce(untrusted_value >= 0)
        newvalue = untrusted_value
        del untrusted_value

        self.fire_event_for_permission(newvalue=newvalue)

        pool.revisions_to_keep = newvalue
        self.app.save()

    @vanir.api.method('admin.label.List', no_payload=True,
        scope='global', read=True)
    @asyncio.coroutine
    def label_list(self):
        self.enforce(self.dest.name == 'dom0')
        self.enforce(not self.arg)

        labels = self.fire_event_for_filter(self.app.labels.values())

        return ''.join('{}\n'.format(label.name) for label in labels)

    @vanir.api.method('admin.label.Get', no_payload=True,
        scope='global', read=True)
    @asyncio.coroutine
    def label_get(self):
        self.enforce(self.dest.name == 'dom0')

        try:
            label = self.app.get_label(self.arg)
        except KeyError:
            raise vanir.exc.VanirValueError

        self.fire_event_for_permission(label=label)

        return label.color

    @vanir.api.method('admin.label.Index', no_payload=True,
        scope='global', read=True)
    @asyncio.coroutine
    def label_index(self):
        self.enforce(self.dest.name == 'dom0')

        try:
            label = self.app.get_label(self.arg)
        except KeyError:
            raise vanir.exc.VanirValueError

        self.fire_event_for_permission(label=label)

        return str(label.index)

    @vanir.api.method('admin.label.Create',
        scope='global', write=True)
    @asyncio.coroutine
    def label_create(self, untrusted_payload):
        self.enforce(self.dest.name == 'dom0')

        # don't confuse label name with label index
        self.enforce(not self.arg.isdigit())
        allowed_chars = string.ascii_letters + string.digits + '-_.'
        self.enforce(all(c in allowed_chars for c in self.arg))
        try:
            self.app.get_label(self.arg)
        except KeyError:
            # ok, no such label yet
            pass
        else:
            raise vanir.exc.VanirValueError('label already exists')

        untrusted_payload = untrusted_payload.decode('ascii').strip()
        self.enforce(len(untrusted_payload) == 8)
        self.enforce(untrusted_payload.startswith('0x'))
        # besides prefix, only hex digits are allowed
        self.enforce(all(x in string.hexdigits for x in untrusted_payload[2:]))

        # SEE: #2732
        color = untrusted_payload

        self.fire_event_for_permission(color=color)

        # allocate new index, but make sure it's outside of default labels set
        new_index = max(
            vanir.config.max_default_label, *self.app.labels.keys()) + 1

        label = vanir.Label(new_index, color, self.arg)
        self.app.labels[new_index] = label
        self.app.save()

    @vanir.api.method('admin.label.Remove', no_payload=True,
        scope='global', write=True)
    @asyncio.coroutine
    def label_remove(self):
        self.enforce(self.dest.name == 'dom0')

        try:
            label = self.app.get_label(self.arg)
        except KeyError:
            raise vanir.exc.VanirValueError
        # don't allow removing default labels
        self.enforce(label.index > vanir.config.max_default_label)

        # FIXME: this should be in app.add_label()
        for vm in self.app.domains:
            if vm.label == label:
                raise vanir.exc.VanirException('label still in use')

        self.fire_event_for_permission(label=label)

        del self.app.labels[label.index]
        self.app.save()

    @vanir.api.method('admin.vm.Start', no_payload=True,
        scope='local', execute=True)
    @asyncio.coroutine
    def vm_start(self):
        self.enforce(not self.arg)
        self.fire_event_for_permission()
        try:
            yield from self.dest.start()
        except libvirt.libvirtError as e:
            # change to VanirException, so will be reported to the user
            raise vanir.exc.VanirException('Start failed: ' + str(e) +
                ', see /var/log/libvirt/libxl/libxl-driver.log for details')


    @vanir.api.method('admin.vm.Shutdown', no_payload=True,
        scope='local', execute=True)
    @asyncio.coroutine
    def vm_shutdown(self):
        self.enforce(not self.arg)
        self.fire_event_for_permission()
        yield from self.dest.shutdown()

    @vanir.api.method('admin.vm.Pause', no_payload=True,
        scope='local', execute=True)
    @asyncio.coroutine
    def vm_pause(self):
        self.enforce(not self.arg)
        self.fire_event_for_permission()
        yield from self.dest.pause()

    @vanir.api.method('admin.vm.Unpause', no_payload=True,
        scope='local', execute=True)
    @asyncio.coroutine
    def vm_unpause(self):
        self.enforce(not self.arg)
        self.fire_event_for_permission()
        yield from self.dest.unpause()

    @vanir.api.method('admin.vm.Kill', no_payload=True,
        scope='local', execute=True)
    @asyncio.coroutine
    def vm_kill(self):
        self.enforce(not self.arg)
        self.fire_event_for_permission()
        yield from self.dest.kill()

    @vanir.api.method('admin.Events', no_payload=True,
        scope='global', read=True)
    @asyncio.coroutine
    def events(self):
        self.enforce(not self.arg)

        # run until client connection is terminated
        self.cancellable = True
        wait_for_cancel = asyncio.get_event_loop().create_future()

        # cache event filters, to not call an event each time an event arrives
        event_filters = self.fire_event_for_permission()

        dispatcher = VanirMgmtEventsDispatcher(event_filters, self.send_event)
        if self.dest.name == 'dom0':
            self.app.add_handler('*', dispatcher.app_handler)
            self.app.add_handler('domain-add', dispatcher.on_domain_add)
            self.app.add_handler('domain-delete', dispatcher.on_domain_delete)
            for vm in self.app.domains:
                vm.add_handler('*', dispatcher.vm_handler)
        else:
            self.dest.add_handler('*', dispatcher.vm_handler)

        # send artificial event as a confirmation that connection is established
        self.send_event(self.app, 'connection-established')

        try:
            yield from wait_for_cancel
        except asyncio.CancelledError:
            # the above waiting was already interrupted, this is all we need
            pass

        if self.dest.name == 'dom0':
            self.app.remove_handler('*', dispatcher.app_handler)
            self.app.remove_handler('domain-add', dispatcher.on_domain_add)
            self.app.remove_handler('domain-delete',
                dispatcher.on_domain_delete)
            for vm in self.app.domains:
                vm.remove_handler('*', dispatcher.vm_handler)
        else:
            self.dest.remove_handler('*', dispatcher.vm_handler)

    @vanir.api.method('admin.vm.feature.List', no_payload=True,
        scope='local', read=True)
    @asyncio.coroutine
    def vm_feature_list(self):
        self.enforce(not self.arg)
        features = self.fire_event_for_filter(self.dest.features.keys())
        return ''.join('{}\n'.format(feature) for feature in features)

    @vanir.api.method('admin.vm.feature.Get', no_payload=True,
        scope='local', read=True)
    @asyncio.coroutine
    def vm_feature_get(self):
        # validation of self.arg done by qrexec-policy is enough

        self.fire_event_for_permission()
        try:
            value = self.dest.features[self.arg]
        except KeyError:
            raise vanir.exc.VanirFeatureNotFoundError(self.dest, self.arg)
        return value

    @vanir.api.method('admin.vm.feature.CheckWithTemplate', no_payload=True,
        scope='local', read=True)
    @asyncio.coroutine
    def vm_feature_checkwithtemplate(self):
        # validation of self.arg done by qrexec-policy is enough

        self.fire_event_for_permission()
        try:
            value = self.dest.features.check_with_template(self.arg)
        except KeyError:
            raise vanir.exc.VanirFeatureNotFoundError(self.dest, self.arg)
        return value

    @vanir.api.method('admin.vm.feature.CheckWithNetvm', no_payload=True,
        scope='local', read=True)
    @asyncio.coroutine
    def vm_feature_checkwithnetvm(self):
        # validation of self.arg done by qrexec-policy is enough

        self.fire_event_for_permission()
        try:
            value = self.dest.features.check_with_netvm(self.arg)
        except KeyError:
            raise vanir.exc.VanirFeatureNotFoundError(self.dest, self.arg)
        return value

    @vanir.api.method('admin.vm.feature.CheckWithAdminVM', no_payload=True,
        scope='local', read=True)
    @asyncio.coroutine
    def vm_feature_checkwithadminvm(self):
        # validation of self.arg done by qrexec-policy is enough

        self.fire_event_for_permission()
        try:
            value = self.dest.features.check_with_adminvm(self.arg)
        except KeyError:
            raise vanir.exc.VanirFeatureNotFoundError(self.dest, self.arg)
        return value

    @vanir.api.method('admin.vm.feature.CheckWithTemplateAndAdminVM',
        no_payload=True, scope='local', read=True)
    @asyncio.coroutine
    def vm_feature_checkwithtpladminvm(self):
        # validation of self.arg done by qrexec-policy is enough

        self.fire_event_for_permission()
        try:
            value = self.dest.features.check_with_template_and_adminvm(self.arg)
        except KeyError:
            raise vanir.exc.VanirFeatureNotFoundError(self.dest, self.arg)
        return value

    @vanir.api.method('admin.vm.feature.Remove', no_payload=True,
        scope='local', write=True)
    @asyncio.coroutine
    def vm_feature_remove(self):
        # validation of self.arg done by qrexec-policy is enough

        self.fire_event_for_permission()
        try:
            del self.dest.features[self.arg]
        except KeyError:
            raise vanir.exc.VanirFeatureNotFoundError(self.dest, self.arg)
        self.app.save()

    @vanir.api.method('admin.vm.feature.Set',
        scope='local', write=True)
    @asyncio.coroutine
    def vm_feature_set(self, untrusted_payload):
        # validation of self.arg done by qrexec-policy is enough
        value = untrusted_payload.decode('ascii', errors='strict')
        del untrusted_payload

        self.fire_event_for_permission(value=value)
        self.dest.features[self.arg] = value
        self.app.save()

    @vanir.api.method('admin.vm.Create.{endpoint}', endpoints=(ep.name
            for ep in pkg_resources.iter_entry_points(vanir.vm.VM_ENTRY_POINT)),
        scope='global', write=True)
    @asyncio.coroutine
    def vm_create(self, endpoint, untrusted_payload=None):
        return self._vm_create(endpoint, allow_pool=False,
            untrusted_payload=untrusted_payload)

    @vanir.api.method('admin.vm.CreateInPool.{endpoint}', endpoints=(ep.name
            for ep in pkg_resources.iter_entry_points(vanir.vm.VM_ENTRY_POINT)),
        scope='global', write=True)
    @asyncio.coroutine
    def vm_create_in_pool(self, endpoint, untrusted_payload=None):
        return self._vm_create(endpoint, allow_pool=True,
            untrusted_payload=untrusted_payload)

    def _vm_create(self, vm_type, allow_pool=False, untrusted_payload=None):
        self.enforce(self.dest.name == 'dom0')

        kwargs = {}
        pool = None
        pools = {}

        # this will raise exception if none is found
        vm_class = vanir.utils.get_entry_point_one(vanir.vm.VM_ENTRY_POINT,
            vm_type)

        # if argument is given, it needs to be a valid template, and only
        # when given VM class do need a template
        if self.arg:
            if hasattr(vm_class, 'template'):
                if self.arg not in self.app.domains:
                    raise vanir.api.PermissionDenied(
                        'Template {} does not exist'.format(self.arg))
                kwargs['template'] = self.app.domains[self.arg]
            else:
                raise vanir.exc.VanirValueError(
                    '{} cannot be based on template'.format(vm_type))

        for untrusted_param in untrusted_payload.decode('ascii',
                errors='strict').split(' '):
            untrusted_key, untrusted_value = untrusted_param.split('=', 1)
            if untrusted_key in kwargs:
                raise vanir.api.ProtocolError('duplicated parameters')

            if untrusted_key == 'name':
                vanir.vm.validate_name(None, None, untrusted_value)
                kwargs['name'] = untrusted_value

            elif untrusted_key == 'label':
                # don't confuse label name with label index
                self.enforce(not untrusted_value.isdigit())
                allowed_chars = string.ascii_letters + string.digits + '-_.'
                self.enforce(all(c in allowed_chars for c in untrusted_value))
                try:
                    kwargs['label'] = self.app.get_label(untrusted_value)
                except KeyError:
                    raise vanir.exc.VanirValueError

            elif untrusted_key == 'pool' and allow_pool:
                if pool is not None:
                    raise vanir.api.ProtocolError('duplicated pool parameter')
                pool = self.app.get_pool(untrusted_value)
            elif untrusted_key.startswith('pool:') and allow_pool:
                untrusted_volume = untrusted_key.split(':', 1)[1]
                # kind of ugly, but actual list of volumes is available only
                # after creating a VM
                self.enforce(untrusted_volume in [
                    'root', 'private', 'volatile', 'kernel'])
                volume = untrusted_volume
                if volume in pools:
                    raise vanir.api.ProtocolError(
                        'duplicated pool:{} parameter'.format(volume))
                pools[volume] = self.app.get_pool(untrusted_value)

            else:
                raise vanir.api.ProtocolError('Invalid param name')
        del untrusted_payload

        if 'name' not in kwargs or 'label' not in kwargs:
            raise vanir.api.ProtocolError('Missing name or label')

        if pool and pools:
            raise vanir.api.ProtocolError(
                'Only one of \'pool=\' and \'pool:volume=\' can be used')

        if kwargs['name'] in self.app.domains:
            raise vanir.exc.VanirValueError(
                'VM {} already exists'.format(kwargs['name']))

        self.fire_event_for_permission(pool=pool, pools=pools, **kwargs)

        vm = self.app.add_new_vm(vm_class, **kwargs)
        # TODO: move this to extension (in race-free fashion)
        vm.tags.add('created-by-' + str(self.src))

        try:
            yield from vm.create_on_disk(pool=pool, pools=pools)
        except:
            del self.app.domains[vm]
            raise
        self.app.save()

    @vanir.api.method('admin.vm.CreateDisposable', no_payload=True,
        scope='global', write=True)
    @asyncio.coroutine
    def create_disposable(self):
        self.enforce(not self.arg)

        if self.dest.name == 'dom0':
            dispvm_template = self.src.default_dispvm
        else:
            dispvm_template = self.dest

        self.fire_event_for_permission(dispvm_template=dispvm_template)

        dispvm = yield from vanir.vm.dispvm.DispVM.from_appvm(dispvm_template)
        # TODO: move this to extension (in race-free fashion, better than here)
        dispvm.tags.add('disp-created-by-' + str(self.src))

        return dispvm.name

    @vanir.api.method('admin.vm.Remove', no_payload=True,
        scope='global', write=True)
    @asyncio.coroutine
    def vm_remove(self):
        self.enforce(not self.arg)

        self.fire_event_for_permission()

        if not self.dest.is_halted():
            raise vanir.exc.VanirVMNotHaltedError(self.dest)

        if self.dest.installed_by_rpm:
            raise vanir.exc.VanirVMInUseError(self.dest, \
                "VM installed by package manager: " + self.dest.name)

        del self.app.domains[self.dest]
        try:
            yield from self.dest.remove_from_disk()
        except:  # pylint: disable=bare-except
            self.app.log.exception('Error while removing VM \'%s\' files',
                self.dest.name)

        self.app.save()

    @vanir.api.method('admin.vm.device.{endpoint}.Available', endpoints=(ep.name
            for ep in pkg_resources.iter_entry_points('vanir.devices')),
            no_payload=True,
        scope='local', read=True)
    @asyncio.coroutine
    def vm_device_available(self, endpoint):
        devclass = endpoint
        devices = self.dest.devices[devclass].available()
        if self.arg:
            devices = [dev for dev in devices if dev.ident == self.arg]
            # no duplicated devices, but device may not exists, in which case
            #  the list is empty
            self.enforce(len(devices) <= 1)
        devices = self.fire_event_for_filter(devices, devclass=devclass)

        dev_info = {}
        for dev in devices:
            non_default_attrs = set(attr for attr in dir(dev) if
                not attr.startswith('_')).difference((
                    'backend_domain', 'ident', 'frontend_domain',
                    'description', 'options', 'regex'))
            properties_txt = ' '.join(
                '{}={!s}'.format(prop, value) for prop, value
                in itertools.chain(
                    ((key, getattr(dev, key)) for key in non_default_attrs),
                    # keep description as the last one, according to API
                    # specification
                    (('description', dev.description),)
                ))
            self.enforce('\n' not in properties_txt)
            dev_info[dev.ident] = properties_txt

        return ''.join('{} {}\n'.format(ident, dev_info[ident])
            for ident in sorted(dev_info))

    @vanir.api.method('admin.vm.device.{endpoint}.List', endpoints=(ep.name
            for ep in pkg_resources.iter_entry_points('vanir.devices')),
            no_payload=True,
        scope='local', read=True)
    @asyncio.coroutine
    def vm_device_list(self, endpoint):
        devclass = endpoint
        device_assignments = self.dest.devices[devclass].assignments()
        if self.arg:
            select_backend, select_ident = self.arg.split('+', 1)
            device_assignments = [dev for dev in device_assignments
                if (str(dev.backend_domain), dev.ident)
                   == (select_backend, select_ident)]
            # no duplicated devices, but device may not exists, in which case
            #  the list is empty
            self.enforce(len(device_assignments) <= 1)
        device_assignments = self.fire_event_for_filter(device_assignments,
            devclass=devclass)

        dev_info = {}
        for dev in device_assignments:
            properties_txt = ' '.join(
                '{}={!s}'.format(opt, value) for opt, value
                in itertools.chain(
                    dev.options.items(),
                    (('persistent', 'yes' if dev.persistent else 'no'),)
                ))
            self.enforce('\n' not in properties_txt)
            ident = '{!s}+{!s}'.format(dev.backend_domain, dev.ident)
            dev_info[ident] = properties_txt

        return ''.join('{} {}\n'.format(ident, dev_info[ident])
            for ident in sorted(dev_info))

    # Attach/Detach action can both modify persistent state (with
    # persistent=True) and volatile state of running VM (with persistent=False).
    # For this reason, write=True + execute=True
    @vanir.api.method('admin.vm.device.{endpoint}.Attach', endpoints=(ep.name
            for ep in pkg_resources.iter_entry_points('vanir.devices')),
        scope='local', write=True, execute=True)
    @asyncio.coroutine
    def vm_device_attach(self, endpoint, untrusted_payload):
        devclass = endpoint
        options = {}
        persistent = False
        for untrusted_option in untrusted_payload.decode('ascii').split():
            try:
                untrusted_key, untrusted_value = untrusted_option.split('=', 1)
            except ValueError:
                raise vanir.api.ProtocolError('Invalid options format')
            if untrusted_key == 'persistent':
                persistent = vanir.property.bool(None, None, untrusted_value)
            else:
                allowed_chars_key = string.digits + string.ascii_letters + '-_.'
                allowed_chars_value = allowed_chars_key + ',+:'
                if any(x not in allowed_chars_key for x in untrusted_key):
                    raise vanir.api.ProtocolError(
                        'Invalid chars in option name')
                if any(x not in allowed_chars_value for x in untrusted_value):
                    raise vanir.api.ProtocolError(
                        'Invalid chars in option value')
                options[untrusted_key] = untrusted_value

        # qrexec already verified that no strange characters are in self.arg
        backend_domain, ident = self.arg.split('+', 1)
        # may raise KeyError, either on domain or ident
        dev = self.app.domains[backend_domain].devices[devclass][ident]

        self.fire_event_for_permission(device=dev,
            devclass=devclass, persistent=persistent,
            options=options)

        assignment = vanir.devices.DeviceAssignment(
            dev.backend_domain, dev.ident,
            options=options, persistent=persistent)
        yield from self.dest.devices[devclass].attach(assignment)
        self.app.save()

    # Attach/Detach action can both modify persistent state (with
    # persistent=True) and volatile state of running VM (with persistent=False).
    # For this reason, write=True + execute=True
    @vanir.api.method('admin.vm.device.{endpoint}.Detach', endpoints=(ep.name
            for ep in pkg_resources.iter_entry_points('vanir.devices')),
            no_payload=True,
        scope='local', write=True, execute=True)
    @asyncio.coroutine
    def vm_device_detach(self, endpoint):
        devclass = endpoint

        # qrexec already verified that no strange characters are in self.arg
        backend_domain, ident = self.arg.split('+', 1)
        # may raise KeyError; if device isn't found, it will be UnknownDevice
        #  instance - but allow it, otherwise it will be impossible to detach
        #  already removed device
        dev = self.app.domains[backend_domain].devices[devclass][ident]

        self.fire_event_for_permission(device=dev,
            devclass=devclass)

        assignment = vanir.devices.DeviceAssignment(
            dev.backend_domain, dev.ident)
        yield from self.dest.devices[devclass].detach(assignment)
        self.app.save()

    # Attach/Detach action can both modify persistent state (with
    # persistent=True) and volatile state of running VM (with persistent=False).
    # For this reason, write=True + execute=True
    @vanir.api.method('admin.vm.device.{endpoint}.Set.persistent',
        endpoints=(ep.name
            for ep in pkg_resources.iter_entry_points('vanir.devices')),
        scope='local', write=True, execute=True)
    @asyncio.coroutine
    def vm_device_set_persistent(self, endpoint, untrusted_payload):
        devclass = endpoint

        self.enforce(untrusted_payload in (b'True', b'False'))
        persistent = untrusted_payload == b'True'
        del untrusted_payload

        # qrexec already verified that no strange characters are in self.arg
        backend_domain, ident = self.arg.split('+', 1)
        # device must be already attached
        matching_devices = [dev for dev
            in self.dest.devices[devclass].attached()
            if dev.backend_domain.name == backend_domain and dev.ident == ident]
        self.enforce(len(matching_devices) == 1)
        dev = matching_devices[0]

        self.fire_event_for_permission(device=dev,
            persistent=persistent)

        self.dest.devices[devclass].update_persistent(dev, persistent)
        self.app.save()

    @vanir.api.method('admin.vm.firewall.Get', no_payload=True,
            scope='local', read=True)
    @asyncio.coroutine
    def vm_firewall_get(self):
        self.enforce(not self.arg)

        self.fire_event_for_permission()

        return ''.join('{}\n'.format(rule.api_rule)
            for rule in self.dest.firewall.rules
            if rule.api_rule is not None)

    @vanir.api.method('admin.vm.firewall.Set',
            scope='local', write=True)
    @asyncio.coroutine
    def vm_firewall_set(self, untrusted_payload):
        self.enforce(not self.arg)
        rules = []
        for untrusted_line in untrusted_payload.decode('ascii',
                errors='strict').splitlines():
            rule = vanir.firewall.Rule.from_api_string(
                untrusted_rule=untrusted_line)
            rules.append(rule)

        self.fire_event_for_permission(rules=rules)

        self.dest.firewall.rules = rules
        self.dest.firewall.save()

    @vanir.api.method('admin.vm.firewall.Reload', no_payload=True,
            scope='local', execute=True)
    @asyncio.coroutine
    def vm_firewall_reload(self):
        self.enforce(not self.arg)

        self.fire_event_for_permission()

        self.dest.fire_event('firewall-changed')

    @asyncio.coroutine
    def _load_backup_profile(self, profile_name, skip_passphrase=False):
        '''Load backup profile and return :py:class:`vanir.backup.Backup`
        instance
        :param profile_name: name of the profile
        :param skip_passphrase: do not load passphrase - only backup summary
            can be retrieved when this option is in use
        '''
        profile_path = os.path.join(
            vanir.config.backup_profile_dir, profile_name + '.conf')

        with open(profile_path) as profile_file:
            profile_data = yaml.safe_load(profile_file)

        try:
            dest_vm = profile_data['destination_vm']
            dest_path = profile_data['destination_path']
            include_vms = profile_data['include']
            if include_vms is not None:
                # convert old keywords to new keywords
                include_vms = [vm.replace('$', '@') for vm in include_vms]
            exclude_vms = profile_data.get('exclude', [])
            # convert old keywords to new keywords
            exclude_vms = [vm.replace('$', '@') for vm in exclude_vms]
            compression = profile_data.get('compression', True)
        except KeyError as err:
            raise vanir.exc.VanirException(
                'Invalid backup profile - missing {}'.format(err))

        try:
            dest_vm = self.app.domains[dest_vm]
        except KeyError:
            raise vanir.exc.VanirException(
                'Invalid destination_vm specified in backup profile')

        if isinstance(dest_vm, vanir.vm.adminvm.AdminVM):
            dest_vm = None

        if skip_passphrase:
            passphrase = None
        elif 'passphrase_text' in profile_data:
            passphrase = profile_data['passphrase_text']
        elif 'passphrase_vm' in profile_data:
            passphrase_vm_name = profile_data['passphrase_vm']
            try:
                passphrase_vm = self.app.domains[passphrase_vm_name]
            except KeyError:
                raise vanir.exc.VanirException(
                    'Invalid backup profile - invalid passphrase_vm')
            try:
                passphrase, _ = yield from passphrase_vm.run_service_for_stdio(
                    'vanir.BackupPassphrase+' + self.arg)
                # make it foolproof against "echo passphrase" implementation
                passphrase = passphrase.strip()
                self.enforce(b'\n' not in passphrase)
            except subprocess.CalledProcessError:
                raise vanir.exc.VanirException(
                    'Failed to retrieve passphrase from \'{}\' VM'.format(
                        passphrase_vm_name))
        else:
            raise vanir.exc.VanirException(
                'Invalid backup profile - you need to '
                'specify passphrase_text or passphrase_vm')

        # handle include
        if include_vms is None:
            vms_to_backup = None
        else:
            vms_to_backup = set(vm for vm in self.app.domains
                if any(vanir.utils.match_vm_name_with_special(vm, name)
                    for name in include_vms))

        # handle exclude
        vms_to_exclude = set(vm.name for vm in self.app.domains
            if any(vanir.utils.match_vm_name_with_special(vm, name)
                for name in exclude_vms))

        kwargs = {
            'target_vm': dest_vm,
            'target_dir': dest_path,
            'compressed': bool(compression),
            'passphrase': passphrase,
        }
        if isinstance(compression, str):
            kwargs['compression_filter'] = compression
        backup = vanir.backup.Backup(self.app, vms_to_backup, vms_to_exclude,
                                     **kwargs)
        return backup

    def _backup_progress_callback(self, profile_name, progress):
        self.app.fire_event('backup-progress', backup_profile=profile_name,
            progress=progress)

    @vanir.api.method('admin.backup.Execute', no_payload=True,
        scope='global', read=True, execute=True)
    @asyncio.coroutine
    def backup_execute(self):
        self.enforce(self.dest.name == 'dom0')
        self.enforce(self.arg)
        self.enforce('/' not in self.arg)

        self.fire_event_for_permission()

        profile_path = os.path.join(vanir.config.backup_profile_dir,
            self.arg + '.conf')
        if not os.path.exists(profile_path):
            raise vanir.api.PermissionDenied(
                'Backup profile {} does not exist'.format(self.arg))

        if not hasattr(self.app, 'api_admin_running_backups'):
            self.app.api_admin_running_backups = {}

        backup = yield from self._load_backup_profile(self.arg)
        backup.progress_callback = functools.partial(
            self._backup_progress_callback, self.arg)

        # forbid running the same backup operation twice at the time
        self.enforce(self.arg not in self.app.api_admin_running_backups)

        backup_task = asyncio.ensure_future(backup.backup_do())
        self.app.api_admin_running_backups[self.arg] = backup_task
        try:
            yield from backup_task
        except asyncio.CancelledError:
            raise vanir.exc.VanirException('Backup cancelled')
        finally:
            del self.app.api_admin_running_backups[self.arg]

    @vanir.api.method('admin.backup.Cancel', no_payload=True,
        scope='global', execute=True)
    @asyncio.coroutine
    def backup_cancel(self):
        self.enforce(self.dest.name == 'dom0')
        self.enforce(self.arg)
        self.enforce('/' not in self.arg)

        self.fire_event_for_permission()

        if not hasattr(self.app, 'api_admin_running_backups'):
            self.app.api_admin_running_backups = {}

        if self.arg not in self.app.api_admin_running_backups:
            raise vanir.exc.VanirException('Backup operation not running')

        self.app.api_admin_running_backups[self.arg].cancel()

    @vanir.api.method('admin.backup.Info', no_payload=True,
        scope='local', read=True)
    @asyncio.coroutine
    def backup_info(self):
        self.enforce(self.dest.name == 'dom0')
        self.enforce(self.arg)
        self.enforce('/' not in self.arg)

        self.fire_event_for_permission()

        profile_path = os.path.join(vanir.config.backup_profile_dir,
            self.arg + '.conf')
        if not os.path.exists(profile_path):
            raise vanir.api.PermissionDenied(
                'Backup profile {} does not exist'.format(self.arg))

        backup = yield from self._load_backup_profile(self.arg,
            skip_passphrase=True)
        return backup.get_backup_summary()

    def _send_stats_single(self, info_time, info, only_vm, filters,
            id_to_name_map):
        '''A single iteration of sending VM stats
        :param info_time: time of previous iteration
        :param info: information retrieved in previous iteration
        :param only_vm: send information only about this VM
        :param filters: filters to apply on stats before sending
        :param id_to_name_map: ID->VM name map, may be modified
        :return: tuple(info_time, info) - new information (to be passed to
        the next iteration)
        '''

        (info_time, info) = self.app.host.get_vm_stats(info_time, info,
            only_vm=only_vm)
        for vm_id, vm_info in info.items():
            if vm_id not in id_to_name_map:
                try:
                    name = \
                        self.app.vmm.libvirt_conn.lookupByID(vm_id).name()
                except libvirt.libvirtError as err:
                    if err.get_error_code() == libvirt.VIR_ERR_NO_DOMAIN:
                        # stubdomain or so
                        name = None
                    else:
                        raise
                id_to_name_map[vm_id] = name
            else:
                name = id_to_name_map[vm_id]

            # skip VMs with unknown name
            if name is None:
                continue

            if not list(vanir.api.apply_filters([name], filters)):
                continue

            self.send_event(name, 'vm-stats',
                memory_kb=int(vm_info['memory_kb']),
                cpu_time=int(vm_info['cpu_time'] / 1000000),
                cpu_usage=int(vm_info['cpu_usage']))

        return info_time, info

    @vanir.api.method('admin.vm.Stats', no_payload=True,
        scope='global', read=True)
    @asyncio.coroutine
    def vm_stats(self):
        self.enforce(not self.arg)

        # run until client connection is terminated
        self.cancellable = True

        # cache event filters, to not call an event each time an event arrives
        stats_filters = self.fire_event_for_permission()

        only_vm = None
        if self.dest.name != 'dom0':
            only_vm = self.dest

        self.send_event(self.app, 'connection-established')

        info_time = None
        info = None
        id_to_name_map = {0: 'dom0'}
        try:
            while True:
                info_time, info = self._send_stats_single(info_time, info,
                    only_vm, stats_filters, id_to_name_map)
                yield from asyncio.sleep(self.app.stats_interval)
        except asyncio.CancelledError:
            # valid method to terminate this loop
            pass