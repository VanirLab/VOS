import asyncio
import re
import string
import uuid

import lxml.etree

import vanir
import vanir.devices
import vanir.events
import vanir.features
import vanir.log

VM_ENTRY_POINT = 'vanir.vm'

def validate_name(holder, prop, value):
    ''' Check if value is syntactically correct VM name '''
    if not isinstance(value, str):
        raise TypeError('VM name must be string, {!r} found'.format(
            type(value).__name__))
    if len(value) > 31:
        if holder is not None and prop is not None:
            raise vanir.exc.VanirPropertyValueError(holder, prop, value,
                '{} value must be shorter than 32 characters'.format(
                    prop.__name__))
        raise vanir.exc.VanirValueError(
            'VM name must be shorter than 32 characters')

    # this regexp does not contain '+'; if it had it, we should specifically
    # disallow 'lost+found' #1440
    if re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*$", value) is None:
        if holder is not None and prop is not None:
            raise vanir.exc.VanirPropertyValueError(holder, prop, value,
                '{} value contains illegal characters'.format(prop.__name__))
        raise vanir.exc.VanirValueError(
            'VM name contains illegal characters')
    if value in ('none', 'default'):
        raise vanir.exc.VanirValueError(
            'VM name cannot be \'none\' nor \'default\'')

def setter_label(self, prop, value):
    ''' Helper for setting the domain label '''
    # pylint: disable=unused-argument
    if isinstance(value, vanir.Label):
        return value
    if isinstance(value, str) and value.startswith('label-'):
        return self.app.labels[int(value.split('-', 1)[1])]

    return self.app.get_label(value)


def _setter_qid(self, prop, value):
    ''' Helper for setting the domain qid '''
    # pylint: disable=unused-argument
    value = int(value)
    if not 0 <= value <= vanir.config.max_qid:
        raise ValueError(
            '{} value must be between 0 and vanir.config.max_qid'.format(
                prop.__name__))
    return value


class Tags(set):
    '''Manager of the tags.
    Tags are simple: tag either can be present on qube or not. Tag is a
    simple string consisting of ASCII alphanumeric characters, plus `_` and
    `-`.
    This class inherits from set, but has most of the methods that manipulate
    the item disarmed (they raise NotImplementedError). The ones that are left
    fire appropriate events on the qube that owns an instance of this class.
    '''

    #
    # Those are the methods that affect contents. Either disarm them or make
    # them report appropriate events. Good approach is to rewrite them carefully
    # using official documentation, but use only our (overloaded) methods.
    #
    def __init__(self, vm, seq=()):
        super(Tags, self).__init__()
        self.vm = vm
        self.update(seq)

    def clear(self):
        '''Remove all tags'''
        for item in tuple(self):
            self.remove(item)

    def symmetric_difference_update(self, *args, **kwargs):
        '''Not implemented
        :raises: NotImplementedError
        '''
        raise NotImplementedError()

    def intersection_update(self, *args, **kwargs):
        '''Not implemented
        :raises: NotImplementedError
        '''
        raise NotImplementedError()

    def pop(self):
        '''Not implemented
        :raises: NotImplementedError
        '''
        raise NotImplementedError()

    def discard(self, elem):
        '''Remove a tag if present'''
        if elem in self:
            self.remove(elem)

    def update(self, *others):
        '''Add tags from iterable(s)'''
        for other in others:
            for elem in other:
                self.add(elem)

    def add(self, elem):
        '''Add a tag'''
        allowed_chars = string.ascii_letters + string.digits + '_-'
        if any(i not in allowed_chars for i in elem):
            raise ValueError('Invalid character in tag')
        if elem in self:
            return
        super(Tags, self).add(elem)
        self.vm.fire_event('domain-tag-add:' + elem, tag=elem)

    def remove(self, elem):
        '''Remove a tag'''
        super(Tags, self).remove(elem)
        self.vm.fire_event('domain-tag-delete:' + elem, tag=elem)

    #
    # end of overriding
    #

    @staticmethod
    def validate_tag(tag):
        safe_set = string.ascii_letters + string.digits + '-_'
        if not all((x in safe_set) for x in tag):
            raise ValueError('disallowed characters')


class BaseVM(vanir.PropertyHolder):
    '''Base class for all VMs
    :param app: vanir application context
    :type app: :py:class:`vanir.vanir`
    :param xml: xml node from which to deserialise
    :type xml: :py:class:`lxml.etree._Element` or :py:obj:`None`
    This class is responsible for serializing and deserialising machines and
    provides basic framework. It contains no management logic. For that, see
    :py:class:`vanir.vm.vanirvm.VanirVM`.
    '''
    # pylint: disable=no-member

    uuid = vanir.property('uuid', type=uuid.UUID, write_once=True,
        clone=False,
        doc='UUID from libvirt.')

    name = vanir.property('name', type=str, write_once=True,
        clone=False,
        doc='User-specified name of the domain.')

    qid = vanir.property('qid', type=int, write_once=True,
        setter=_setter_qid,
        clone=False,
        doc='''Internal, persistent identificator of particular domain. Note
            this is different from Xen domid.''')

    label = vanir.property('label',
        setter=setter_label,
        doc='''Colourful label assigned to VM. This is where the colour of the
            padlock is set.''')

    def __init__(self, app, xml, features=None, devices=None, tags=None,
            **kwargs):
        # pylint: disable=redefined-outer-name

        self._qdb_watch_paths = set()
        self._qdb_connection_watch = None

        # self.app must be set before super().__init__, because some property
        # setters need working .app attribute
        #: mother :py:class:`vanir.vanir` object
        self.app = app

        super(BaseVM, self).__init__(xml, **kwargs)

        #: dictionary of features of this qube
        self.features = vanir.features.Features(self, features)

        #: :py:class:`DeviceManager` object keeping devices that are attached to
        #: this domain
        self.devices = devices or vanir.devices.DeviceManager(self)

        #: user-specified tags
        self.tags = Tags(self, tags or ())

        #: logger instance for logging messages related to this VM
        self.log = None

        #: storage volumes
        self.volumes = {}

        #: storage manager
        self.storage = None

        if hasattr(self, 'name'):
            self.init_log()

    def close(self):
        super().close()

        if self._qdb_connection_watch is not None:
            asyncio.get_event_loop().remove_reader(
                self._qdb_connection_watch.watch_fd())
            self._qdb_connection_watch.close()
            del self._qdb_connection_watch

        del self.app
        del self.features
        del self.storage
        # TODO storage may have circ references, but it doesn't leak fds
        del self.devices
        del self.tags

    def load_extras(self):
        if self.xml is None:
            return

        # features
        for node in self.xml.xpath('./features/feature'):
            self.features[node.get('name')] = node.text

        # devices (pci, usb, ...)
        for parent in self.xml.xpath('./devices'):
            devclass = parent.get('class')
            for node in parent.xpath('./device'):
                options = {}
                for option in node.xpath('./option'):
                    options[option.get('name')] = option.text

                device_assignment = vanir.devices.DeviceAssignment(
                    self.app.domains[node.get('backend-domain')],
                    node.get('id'),
                    options,
                    persistent=True
                )
                self.devices[devclass].load_persistent(device_assignment)

        # tags
        for node in self.xml.xpath('./tags/tag'):
            self.tags.add(node.get('name'))

        # SEE:1815 firewall, policy.

    def init_log(self):
        '''Initialise logger for this domain.'''
        self.log = vanir.log.get_vm_logger(self.name)

    def __xml__(self):
        element = lxml.etree.Element('domain')
        element.set('id', 'domain-' + str(self.qid))
        element.set('class', self.__class__.__name__)

        element.append(self.xml_properties())

        features = lxml.etree.Element('features')
        for feature in self.features:
            node = lxml.etree.Element('feature', name=feature)
            node.text = self.features[feature]
            features.append(node)
        element.append(features)

        for devclass in self.devices:
            devices = lxml.etree.Element('devices')
            devices.set('class', devclass)
            for device in self.devices[devclass].assignments(persistent=True):
                node = lxml.etree.Element('device')
                node.set('backend-domain', device.backend_domain.name)
                node.set('id', device.ident)
                for key, val in device.options.items():
                    option_node = lxml.etree.Element('option')
                    option_node.set('name', key)
                    option_node.text = val
                    node.append(option_node)
                devices.append(node)
            element.append(devices)

        tags = lxml.etree.Element('tags')
        for tag in self.tags:
            node = lxml.etree.Element('tag', name=tag)
            tags.append(node)
        element.append(tags)

        return element

    def __repr__(self):
        proprepr = []
        for prop in self.property_list():
            if prop.__name__ in ('name', 'qid'):
                continue
            try:
                proprepr.append('{}={!s}'.format(
                    prop.__name__, getattr(self, prop.__name__)))
            except AttributeError:
                continue

        return '<{} at {:#x} name={!r} qid={!r} {}>'.format(type(self).__name__,
            id(self), self.name, self.qid, ' '.join(proprepr))

    #
    # xml serialising methods
    #

    def create_config_file(self):
        '''Create libvirt's XML domain config file
        '''
        domain_config = self.app.env.select_template([
                'libvirt/xen/by-name/{}.xml'.format(self.name),
                'libvirt/xen-user.xml',
                'libvirt/xen-dist.xml',
                'libvirt/xen.xml',
            ]).render(vm=self)
        return domain_config

    def watch_qdb_path(self, path):
        '''Add a VanirDB path to be watched.
        Each change to the path will cause `domain-qdb-change:path` event to be
        fired.
        You can call this method for example in response to
        `domain-init` and `domain-load` events.
        '''

        if path not in self._qdb_watch_paths:
            self._qdb_watch_paths.add(path)
            if self._qdb_connection_watch:
                self._qdb_connection_watch.watch(path)

    def _qdb_watch_reader(self, loop):
        '''Callback when self._qdb_connection_watch.watch_fd() FD is
        readable.
        Read reported event (watched path change) and fire appropriate event.
        '''
        import VanirDB  # pylint: disable=import-error
        try:
            path = self._qdb_connection_watch.read_watch()
            for watched_path in self._qdb_watch_paths:
                if watched_path == path or (
                            watched_path.endswith('/') and
                            path.startswith(watched_path)):
                    self.fire_event('domain-qdb-change:' + watched_path,
                        path=path)
        except VanirDB.DisconnectedError:
            loop.remove_reader(self._qdb_connection_watch.watch_fd())
            self._qdb_connection_watch.close()
            self._qdb_connection_watch = None

    def start_qdb_watch(self, loop=None):
        '''Start watching VanirDB
        Calling this method in appropriate time is responsibility of child
        class.
        '''
        # cleanup old watch connection first, if any
        if self._qdb_connection_watch is not None:
            asyncio.get_event_loop().remove_reader(
                self._qdb_connection_watch.watch_fd())
            self._qdb_connection_watch.close()

        import VanirDB  # pylint: disable=import-error
        self._qdb_connection_watch = VanirDB.VanirDB(self.name)
        if loop is None:
            loop = asyncio.get_event_loop()
        loop.add_reader(self._qdb_connection_watch.watch_fd(),
            self._qdb_watch_reader, loop)
        for path in self._qdb_watch_paths:
            self._qdb_connection_watch.watch(path)

    @vanir.stateless_property
    def klass(self):
        '''Domain class name'''
        return type(self).__name__

class VMProperty(vanir.property):
    '''Property that is referring to a VM
    :param type vmclass: class that returned VM is supposed to be instance of
    and all supported by :py:class:`property` with the exception of ``type`` \
        and ``setter``
    '''

    _none_value = ''

    def __init__(self, name, vmclass=BaseVM, allow_none=False,
            **kwargs):
        if 'type' in kwargs:
            raise TypeError(
                "'type' keyword parameter is unsupported in {}".format(
                    self.__class__.__name__))
        if not issubclass(vmclass, BaseVM):
            raise TypeError(
                "'vmclass' should specify a subclass of vanir.vm.BaseVM")

        super(VMProperty, self).__init__(name,
            saver=(lambda self_, prop, value:
                self._none_value if value is None else value.name),
            **kwargs)
        self.vmclass = vmclass
        self.allow_none = allow_none

    def __set__(self, instance, value):
        if value is self.__class__.DEFAULT:
            self.__delete__(instance)
            return

        if value == self._none_value:
            value = None
        if value is None:
            if self.allow_none:
                super(VMProperty, self).__set__(instance, value)
                return
            raise ValueError(
                'Property {!r} does not allow setting to {!r}'.format(
                    self.__name__, value))

        app = instance if isinstance(instance, vanir.vanir) else instance.app

        try:
            vm = app.domains[value]
        except KeyError:
            raise vanir.exc.VanirVMNotFoundError(value)

        if not isinstance(vm, self.vmclass):
            raise TypeError('wrong VM class: domains[{!r}] is of type {!s} '
                'and not {!s}'.format(value,
                    vm.__class__.__name__,
                    self.vmclass.__name__))

        super(VMProperty, self).__set__(instance, vm)

    def sanitize(self, *, untrusted_newvalue):
        try:
            untrusted_vmname = untrusted_newvalue.decode('ascii')
        except UnicodeDecodeError:
            raise vanir.exc.VanirValueError
        if untrusted_vmname == '':
            # allow empty VM name for setting VMProperty value, because it's
            # string representation of None (see self._none_value)
            return untrusted_vmname
        validate_name(None, self, untrusted_vmname)
        return untrusted_vmname