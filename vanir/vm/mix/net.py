''' This module contains the NetVMMixin '''
import ipaddress
import os
import re

import libvirt  # pylint: disable=import-error
import vanir
import vanir.config
import vanir.events
import vanir.firewall
import vanir.exc

def _setter_mac(self, prop, value):
    ''' Helper for setting the MAC address '''
    # pylint: disable=unused-argument
    if not isinstance(value, str):
        raise ValueError('MAC address must be a string')
    value = value.lower()
    if re.match(r"^([0-9a-f][0-9a-f]:){5}[0-9a-f][0-9a-f]$", value) is None:
        raise ValueError('Invalid MAC address value')
    return value


def _default_ip(self):
    if not self.is_networked():
        return None
    if self.netvm is not None:
        return self.netvm.get_ip_for_vm(self)  # pylint: disable=no-member

    return self.get_ip_for_vm(self)


def _default_ip6(self):
    if not self.is_networked():
        return None
    if not self.features.check_with_netvm('ipv6', False):
        return None
    if self.netvm is not None:
        return self.netvm.get_ip6_for_vm(self)  # pylint: disable=no-member

    return self.get_ip6_for_vm(self)


def _setter_netvm(self, prop, value):
    # pylint: disable=unused-argument
    if value is None:
        return None
    if not value.provides_network:
        raise vanir.exc.QubesValueError(
            'The {!s} qube does not provide network'.format(value))

    # skip check for netvm loops during vanir.xml loading, to avoid tricky
    # loading order
    if self.events_enabled:
        if value is self \
                or value in self.app.domains.get_vms_connected_to(self):
            raise vanir.exc.QubesValueError(
                'Loops in network are unsupported')
    return value

def _setter_provides_network(self, prop, value):
    value = vanir.property.bool(self, prop, value)
    if not value:
        if list(self.connected_vms):
            raise vanir.exc.QubesValueError(
                'The qube is still used by other vanir, change theirs '
                '\'netvm\' first')

    return value


class NetVMMixin(vanir.events.Emitter):
    ''' Mixin containing network functionality '''
    mac = vanir.property('mac', type=str,
        default='00:16:3E:5E:6C:00',
        setter=_setter_mac,
        doc='MAC address of the NIC emulated inside VM')

    ip = vanir.property('ip', type=ipaddress.IPv4Address,
        default=_default_ip,
        doc='IP address of this domain.')

    ip6 = vanir.property('ip6', type=ipaddress.IPv6Address,
        default=_default_ip6,
        doc='IPv6 address of this domain.')

    # CORE2: swallowed uses_default_netvm
    netvm = vanir.VMProperty('netvm', load_stage=4, allow_none=True,
        default=(lambda self: self.app.default_netvm),
        setter=_setter_netvm,
        doc='''VM that provides network connection to this domain. When
            `None`, machine is disconnected. When absent, domain uses default
            NetVM.''')

    provides_network = vanir.property('provides_network', default=False,
        type=bool, setter=_setter_provides_network,
        doc='''If this domain can act as network provider (formerly known as
            NetVM or ProxyVM)''')


    @property
    def firewall_conf(self):
        return 'firewall.xml'

    #
    # used in networked appvms or proxyvms (netvm is not None)
    #


    @vanir.stateless_property
    def visible_ip(self):
        '''IP address of this domain as seen by the domain.'''
        return self.features.check_with_template('net.fake-ip', None) or \
            self.ip

    @vanir.stateless_property
    def visible_ip6(self):
        '''IPv6 address of this domain as seen by the domain.'''
        return self.ip6

    @vanir.stateless_property
    def visible_gateway(self):
        '''Default gateway of this domain as seen by the domain.'''
        return self.features.check_with_template('net.fake-gateway', None) or \
            (self.netvm.gateway if self.netvm else None)

    @vanir.stateless_property
    def visible_gateway6(self):
        '''Default (IPv6) gateway of this domain as seen by the domain.'''
        if self.features.check_with_netvm('ipv6', False):
            return self.netvm.gateway6 if self.netvm else None
        return None

    @vanir.stateless_property
    def visible_netmask(self):
        '''Netmask as seen by the domain.'''
        return self.features.check_with_template('net.fake-netmask', None) or \
            (self.netvm.netmask if self.netvm else None)

    #
    # used in netvms (provides_network=True)
    # those properties and methods are most likely accessed as vm.netvm.<prop>
    #

    @staticmethod
    def get_ip_for_vm(vm):
        '''Get IP address for (appvm) domain connected to this (netvm) domain.
        '''
        import vanir.vm.dispvm  # pylint: disable=redefined-outer-name
        if isinstance(vm, vanir.vm.dispvm.DispVM):
            return ipaddress.IPv4Address('10.138.{}.{}'.format(
                (vm.dispid >> 8) & 0xff, vm.dispid & 0xff))

        # VM technically can get address which ends in '.0'. This currently
        # does not happen, because qid < 253, but may happen in the future.
        return ipaddress.IPv4Address('10.137.{}.{}'.format(
            (vm.qid >> 8) & 0xff, vm.qid & 0xff))

    @staticmethod
    def get_ip6_for_vm(vm):
        '''Get IPv6 address for (appvm) domain connected to this (netvm) domain.
        Default address is constructed with vanir-specific site-local prefix,
        and IPv4 suffix (0xa89 is 10.137.).
        '''
        import vanir.vm.dispvm  # pylint: disable=redefined-outer-name
        if isinstance(vm, vanir.vm.dispvm.DispVM):
            return ipaddress.IPv6Address('{}::a8a:{:x}'.format(
                vanir.config.qubes_ipv6_prefix, vm.dispid))

        return ipaddress.IPv6Address('{}::a89:{:x}'.format(
            vanir.config.qubes_ipv6_prefix, vm.qid))

    @vanir.stateless_property
    def gateway(self):
        '''Gateway for other domains that use this domain as netvm.'''
        return self.visible_ip if self.provides_network else None

    @vanir.stateless_property
    def gateway6(self):
        '''Gateway (IPv6) for other domains that use this domain as netvm.'''
        if self.features.check_with_netvm('ipv6', False):
            return self.visible_ip6 if self.provides_network else \
                None
        return None

    @property
    def netmask(self):
        '''Netmask for gateway address.'''
        return '255.255.255.255' if self.is_networked() else None

    @property
    def connected_vms(self):
        ''' Return a generator containing all domains connected to the current
            NetVM.
        '''
        for vm in self.app.domains:
            if getattr(vm, 'netvm', None) is self:
                yield vm

    #
    # used in both
    #

    @property
    def dns(self):
        '''Secondary DNS server set up for this domain.'''
        if self.netvm is not None or self.provides_network:
            return (
                '10.139.1.0',
                '10.139.1.1',
				'10.139.1.2',
				'10.139.1.3',
				'10.139.1.4',
				'10.139.1.5',
            )

        return None

    def __init__(self, *args, **kwargs):
        self._firewall = None
        super(NetVMMixin, self).__init__(*args, **kwargs)

    @vanir.events.handler('domain-load')
    def on_domain_load_netvm_loop_check(self, event):
        # pylint: disable=unused-argument
        # make sure there are no netvm loops - which could cause qubesd
        # looping infinitely
        if self is self.netvm:
            self.log.error(
                'vm \'%s\' network-connected to itself, breaking the '
                'connection', self.name)
            self.netvm = None
        elif self.netvm in self.app.domains.get_vms_connected_to(self):
            self.log.error(
                'netvm loop detected on \'%s\', breaking the connection',
                self.name)
            self.netvm = None

    @vanir.events.handler('domain-shutdown')
    def on_domain_shutdown(self, event, **kwargs):
        '''Cleanup network interfaces of connected, running VMs.
        This will allow re-reconnecting them cleanly later.
        '''
        # pylint: disable=unused-argument
        for vm in self.connected_vms:
            if not vm.is_running():
                continue
            try:
                vm.detach_network()
            except (vanir.exc.VanirException, libvirt.libvirtError):
                # ignore errors
                pass

    @vanir.events.handler('domain-start')
    def on_domain_started(self, event, **kwargs):
        '''Connect this domain to its downstream domains. Also reload firewall
        in its netvm.
        This is needed when starting netvm *after* its connected domains.
        '''  # pylint: disable=unused-argument

        if self.netvm:
            self.netvm.reload_firewall_for_vm(self)  # pylint: disable=no-member

        for vm in self.connected_vms:
            if not vm.is_running():
                continue
            vm.log.info('Attaching network')
            try:
                vm.attach_network()
            except (vanir.exc.VanirException, libvirt.libvirtError):
                vm.log.warning('Cannot attach network', exc_info=1)

    @vanir.events.handler('domain-pre-shutdown')
    def on_domain_pre_shutdown(self, event, force=False):
        ''' Checks before NetVM shutdown if any connected domains are running.
            If `force` is `True` tries to detach network interfaces of connected
            vms
        '''  # pylint: disable=unused-argument

        connected_vms = [vm for vm in self.connected_vms if vm.is_running()]
        if connected_vms and not force:
            raise vanir.exc.QubesVMError(self,
                'There are other VMs connected to this VM: {}'.format(
                    ', '.join(vm.name for vm in connected_vms)))


    def attach_network(self):
        '''Attach network in this machine to it's netvm.'''

        if not self.is_running():
            raise vanir.exc.QubesVMNotRunningError(self)
        if self.netvm is None:
            raise vanir.exc.QubesVMError(self,
                'netvm should not be {}'.format(self.netvm))

        if not self.netvm.is_running():  # pylint: disable=no-member
            # pylint: disable=no-member
            self.log.info('Starting NetVM ({0})'.format(self.netvm.name))
            self.netvm.start()

        self.netvm.set_mapped_ip_info_for_vm(self)
        self.libvirt_domain.attachDevice(
            self.app.env.get_template('libvirt/devices/net.xml').render(
                vm=self))

    def detach_network(self):
        '''Detach machine from it's netvm'''

        if not self.is_running():
            raise vanir.exc.QubesVMNotRunningError(self)
        if self.netvm is None:
            raise vanir.exc.QubesVMError(self,
                'netvm should not be {}'.format(self.netvm))

        self.libvirt_domain.detachDevice(
            self.app.env.get_template('libvirt/devices/net.xml').render(
                vm=self))

    def is_networked(self):
        '''Check whether this VM can reach network (firewall notwithstanding).
        :returns: :py:obj:`True` if is machine can reach network, \
            :py:obj:`False` otherwise.
        :rtype: bool
        '''

        if self.provides_network:
            return True

        return self.netvm is not None

    def reload_firewall_for_vm(self, vm):
        ''' Reload the firewall rules for the vm '''
        if not self.is_running():
            return

        for addr_family in (4, 6):
            ip = vm.ip6 if addr_family == 6 else vm.ip
            if ip is None:
                continue
            base_dir = '/vanir-firewall/{}/'.format(ip)
            # remove old entries if any (but don't touch base empty entry - it
            # would trigger reload right away
            self.untrusted_qdb.rm(base_dir)
            # write new rules
            for key, value in vm.firewall.qdb_entries(
                    addr_family=addr_family).items():
                self.untrusted_qdb.write(base_dir + key, value)
            # signal its done
            self.untrusted_qdb.write(base_dir[:-1], '')

    def set_mapped_ip_info_for_vm(self, vm):
        '''
        Set configuration to possibly hide real IP from the VM.
        This needs to be done before executing 'script'
        (`/etc/xen/scripts/vif-route-vanir`) in network providing VM
        '''
        # add info about remapped IPs (VM IP hidden from the VM itself)
        mapped_ip_base = '/mapped-ip/{}'.format(vm.ip)
        if vm.visible_ip:
            self.untrusted_qdb.write(mapped_ip_base + '/visible-ip',
                str(vm.visible_ip))
        else:
            self.untrusted_qdb.rm(mapped_ip_base + '/visible-ip')
        if vm.visible_gateway:
            self.untrusted_qdb.write(mapped_ip_base + '/visible-gateway',
                str(vm.visible_gateway))
        else:
            self.untrusted_qdb.rm(mapped_ip_base + '/visible-gateway')

    @vanir.events.handler('property-pre-del:netvm')
    def on_property_pre_del_netvm(self, event, name, oldvalue=None):
        ''' Sets the the NetVM to default NetVM '''
        # pylint: disable=unused-argument
        # we are changing to default netvm
        newvalue = type(self).netvm.get_default(self)
        # check for netvm loop
        _setter_netvm(self, type(self).netvm, newvalue)
        if newvalue == oldvalue:
            return
        self.fire_event('property-pre-set:netvm', pre_event=True,
            name='netvm', newvalue=newvalue, oldvalue=oldvalue)

    @vanir.events.handler('property-del:netvm')
    def on_property_del_netvm(self, event, name, oldvalue=None):
        ''' Sets the the NetVM to default NetVM '''
        # pylint: disable=unused-argument
        # we are changing to default netvm
        newvalue = self.netvm
        if newvalue == oldvalue:
            return
        self.fire_event('property-set:netvm',
            name='netvm', newvalue=newvalue, oldvalue=oldvalue)

    @vanir.events.handler('property-pre-set:netvm')
    def on_property_pre_set_netvm(self, event, name, newvalue, oldvalue=None):
        ''' Run sanity checks before setting a new NetVM '''
        # pylint: disable=unused-argument
        if newvalue is not None:
            if not self.app.vmm.offline_mode \
                    and self.is_running() and not newvalue.is_running():
                raise vanir.exc.VanirVMNotStartedError(newvalue,
                    'Cannot dynamically attach to stopped NetVM: {!r}'.format(
                        newvalue))

        # don't check oldvalue, because it's missing if it was default
        if self.netvm is not None:
            if self.is_running():
                self.detach_network()

    @vanir.events.handler('property-set:netvm')
    def on_property_set_netvm(self, event, name, newvalue, oldvalue=None):
        ''' Replaces the current NetVM with a new one and fires
            net-domain-connect event
        '''
        # pylint: disable=unused-argument

        if newvalue is None:
            return

        if self.is_running():
            # refresh IP, DNS etc
            self.create_qdb_entries()
            self.attach_network()

            newvalue.fire_event('net-domain-connect', vm=self)

    @vanir.events.handler('net-domain-connect')
    def on_net_domain_connect(self, event, vm):
        ''' Reloads the firewall config for vm '''
        # pylint: disable=unused-argument
        self.reload_firewall_for_vm(vm)

    @vanir.events.handler('domain-qdb-create')
    def on_domain_qdb_create(self, event):
        ''' Fills the VanirDB with firewall entries. '''
        # pylint: disable=unused-argument
        for vm in self.connected_vms:
            if vm.is_running():
                # keep in sync with on_firewall_changed
                self.set_mapped_ip_info_for_vm(vm)
                self.reload_firewall_for_vm(vm)

    @vanir.events.handler('firewall-changed', 'domain-spawn')
    def on_firewall_changed(self, event, **kwargs):
        ''' Reloads the firewall if vm is running and has a NetVM assigned '''
        # pylint: disable=unused-argument
        if self.is_running() and self.netvm:
            self.netvm.set_mapped_ip_info_for_vm(self)
            self.netvm.reload_firewall_for_vm(self)  # pylint: disable=no-member

    # CORE2: swallowed get_firewall_conf, write_firewall_conf,
    # get_firewall_defaults
    @property
    def firewall(self):
        if self._firewall is None:
            self._firewall = vanir.firewall.Firewall(self)
        return self._firewall

    def has_firewall(self):
        ''' Return `True` if there are some vm specific firewall rules set '''
        return os.path.exists(os.path.join(self.dir_path, self.firewall_conf))