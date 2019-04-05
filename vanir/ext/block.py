import re
import string
import lxml.etree

import Vanir.devices
import Vanir.ext

name_re = re.compile(r"^[a-z0-9-]{1,12}$")
device_re = re.compile(r"^[a-z0-9/-]{1,64}$")
# FIXME: any better idea of desc_re?
desc_re = re.compile(r"^.{1,255}$")
mode_re = re.compile(r"^[rw]$")

# all frontends, prefer xvdi
# TODO: get this from libvirt driver?
AVAILABLE_FRONTENDS = ['xvd'+c for c in
                       string.ascii_lowercase[8:]+string.ascii_lowercase[:8]]

SYSTEM_DISKS = ('xvda', 'xvdb', 'xvdc', 'xvdd')


class BlockDevice(Vanir.devices.DeviceInfo):
    def __init__(self, backend_domain, ident):
        super(BlockDevice, self).__init__(backend_domain=backend_domain,
            ident=ident)
        self._description = None
        self._mode = None
        self._size = None

    @property
    def description(self):
        '''Human readable device description'''
        if self._description is None:
            if not self.backend_domain.is_running():
                return self.ident
            safe_set = {ord(c) for c in
                string.ascii_letters + string.digits + '()+,-.:=_/ '}
            untrusted_desc = self.backend_domain.untrusted_qdb.read(
                '/Vanir-block-devices/{}/desc'.format(self.ident))
            if not untrusted_desc:
                return ''
            desc = ''.join((chr(c) if c in safe_set else '_')
                for c in untrusted_desc)
            self._description = desc
        return self._description

    @property
    def mode(self):
        '''Device mode, either 'w' for read-write, or 'r' for read-only'''
        if self._mode is None:
            if not self.backend_domain.is_running():
                return 'w'
            untrusted_mode = self.backend_domain.untrusted_qdb.read(
                '/Vanir-block-devices/{}/mode'.format(self.ident))
            if untrusted_mode is None:
                self._mode = 'w'
            elif untrusted_mode not in (b'w', b'r'):
                self.backend_domain.log.warning(
                    'Device {} has invalid mode'.format(self.ident))
                self._mode = 'w'
            else:
                self._mode = untrusted_mode.decode()
        return self._mode

    @property
    def size(self):
        '''Device size in bytes'''
        if self._size is None:
            if not self.backend_domain.is_running():
                return None
            untrusted_size = self.backend_domain.untrusted_qdb.read(
                '/Vanir-block-devices/{}/size'.format(self.ident))
            if untrusted_size is None:
                self._size = 0
            elif not untrusted_size.isdigit():
                self.backend_domain.log.warning(
                    'Device {} has invalid size'.format(self.ident))
                self._size = 0
            else:
                self._size = int(untrusted_size)
        return self._size

    @property
    def device_node(self):
        '''Device node in backend domain'''
        return '/dev/' + self.ident.replace('_', '/')


class BlockDeviceExtension(Vanir.ext.Extension):
    @Vanir.ext.handler('domain-init', 'domain-load')
    def on_domain_init_load(self, vm, event):
        '''Initialize watching for changes'''
        # pylint: disable=unused-argument,no-self-use
        vm.watch_qdb_path('/Vanir-block-devices')

    @Vanir.ext.handler('domain-qdb-change:/Vanir-block-devices')
    def on_qdb_change(self, vm, event, path):
        '''A change in VanirDB means a change in device list'''
        # pylint: disable=unused-argument,no-self-use
        vm.fire_event('device-list-change:block')

    def device_get(self, vm, ident):
        # pylint: disable=no-self-use
        '''Read information about device from VanirDB
        :param vm: backend VM object
        :param ident: device identifier
        :returns BlockDevice'''

        untrusted_vanir_device_attrs = vm.untrusted_qdb.list(
            '/Vanir-block-devices/{}/'.format(ident))
        if not untrusted_vanir_device_attrs:
            return None
        return BlockDevice(vm, ident)

    @Vanir.ext.handler('device-list:block')
    def on_device_list_block(self, vm, event):
        # pylint: disable=unused-argument,no-self-use

        if not vm.is_running():
            return
        untrusted_vanir_devices = vm.untrusted_qdb.list('/Vanir-block-devices/')
        untrusted_idents = set(untrusted_path.split('/', 3)[2]
            for untrusted_path in untrusted_vanir_devices)
        for untrusted_ident in untrusted_idents:
            if not name_re.match(untrusted_ident):
                msg = ("%s vm's device path name contains unsafe characters. "
                       "Skipping it.")
                vm.log.warning(msg % vm.name)
                continue

            ident = untrusted_ident

            device_info = self.device_get(vm, ident)
            if device_info:
                yield device_info

    @Vanir.ext.handler('device-get:block')
    def on_device_get_block(self, vm, event, ident):
        # pylint: disable=unused-argument,no-self-use
        if not vm.is_running():
            return
        if not vm.app.vmm.offline_mode:
            device_info = self.device_get(vm, ident)
            if device_info:
                yield device_info

    @Vanir.ext.handler('device-list-attached:block')
    def on_device_list_attached(self, vm, event, **kwargs):
        # pylint: disable=unused-argument,no-self-use
        if not vm.is_running():
            return

        xml_desc = lxml.etree.fromstring(vm.libvirt_domain.XMLDesc())

        for disk in xml_desc.findall('devices/disk'):
            if disk.get('type') != 'block':
                continue
            dev_path_node = disk.find('source')
            if dev_path_node is None:
                continue
            dev_path = dev_path_node.get('dev')

            target_node = disk.find('target')
            if target_node is not None:
                frontend_dev = target_node.get('dev')
                if not frontend_dev:
                    continue
                if frontend_dev in SYSTEM_DISKS:
                    continue
            else:
                continue

            backend_domain_node = disk.find('backenddomain')
            if backend_domain_node is not None:
                backend_domain = vm.app.domains[backend_domain_node.get('name')]
            else:
                backend_domain = vm.app.domains[0]

            options = {}
            read_only_node = disk.find('readonly')
            if read_only_node is not None:
                options['read-only'] = 'yes'
            else:
                options['read-only'] = 'no'
            options['frontend-dev'] = frontend_dev
            if disk.get('device') != 'disk':
                options['devtype'] = disk.get('device')

            if dev_path.startswith('/dev/'):
                ident = dev_path[len('/dev/'):]
            else:
                ident = dev_path

            ident = ident.replace('/', '_')

            yield (BlockDevice(backend_domain, ident), options)

    def find_unused_frontend(self, vm):
        # pylint: disable=no-self-use
        '''Find unused block frontend device node for <target dev=.../>
        parameter'''
        assert vm.is_running()

        xml = vm.libvirt_domain.XMLDesc()
        parsed_xml = lxml.etree.fromstring(xml)
        used = [target.get('dev', None) for target in
            parsed_xml.xpath("//domain/devices/disk/target")]
        for dev in AVAILABLE_FRONTENDS:
            if dev not in used:
                return dev
        return None

    @Vanir.ext.handler('device-pre-attach:block')
    def on_device_pre_attached_block(self, vm, event, device, options):
        # pylint: disable=unused-argument

        # validate options
        for option, value in options.items():
            if option == 'frontend-dev':
                if not value.startswith('xvd') and not value.startswith('sd'):
                    raise Vanir.exc.VanirValueError(
                        'Invalid frontend-dev option value: ' + value)
            elif option == 'read-only':
                options[option] = (
                    'yes' if Vanir.property.bool(None, None, value) else 'no')
            elif option == 'devtype':
                if value not in ('disk', 'cdrom'):
                    raise Vanir.exc.VanirValueError(
                        'devtype option can only have '
                        '\'disk\' or \'cdrom\' value')
            else:
                raise Vanir.exc.VanirValueError(
                    'Unsupported option {}'.format(option))

        if 'read-only' not in options:
            options['read-only'] = 'yes' if device.mode == 'r' else 'no'
        if options.get('read-only', 'no') == 'no' and device.mode == 'r':
            raise Vanir.exc.VanirValueError(
                'This device can be attached only read-only')

        if not vm.is_running():
            return

        if not device.backend_domain.is_running():
            raise Vanir.exc.VanirVMNotRunningError(device.backend_domain,
                'Domain {} needs to be running to attach device from '
                'it'.format(device.backend_domain.name))

        if 'frontend-dev' not in options:
            options['frontend-dev'] = self.find_unused_frontend(vm)

        vm.libvirt_domain.attachDevice(
            vm.app.env.get_template('libvirt/devices/block.xml').render(
                device=device, vm=vm, options=options))

    @Vanir.ext.handler('device-pre-detach:block')
    def on_device_pre_detached_block(self, vm, event, device):
        # pylint: disable=unused-argument,no-self-use
        if not vm.is_running():
            return

        # need to enumerate attached device to find frontend_dev option (at
        # least)
        for attached_device, options in self.on_device_list_attached(vm, event):
            if attached_device == device:
                vm.libvirt_domain.detachDevice(
                    vm.app.env.get_template('libvirt/devices/block.xml').render(
                        device=device, vm=vm, options=options))
                break