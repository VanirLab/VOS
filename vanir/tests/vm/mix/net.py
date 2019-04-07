import ipaddress
import unittest

import vanir
import vanir.vm.vanirvm

import vanir.tests
import vanir.tests.vm.vanirvm

class TC_00_NetVMMixin(
        vanir.tests.vm.vanirvm.VanirVMTestsMixin, vanir.tests.VanirTestCase):
    def setUp(self):
        super(TC_00_NetVMMixin, self).setUp()
        self.app = vanir.tests.vm.TestApp()
        self.app.vmm.offline_mode = True

    def setup_netvms(self, vm):
        # usage of VanirVM here means that those tests should be after
        # testing properties used here
        self.netvm1 = vanir.vm.vanirvm.VanirVM(self.app, None, qid=2,
            name=vanir.tests.VMPREFIX + 'netvm1',
            provides_network=True, netvm=None)
        self.netvm2 = vanir.vm.vanirvm.VanirVM(self.app, None, qid=3,
            name=vanir.tests.VMPREFIX + 'netvm2',
            provides_network=True, netvm=None)
        self.nonetvm = vanir.vm.vanirvm.VanirVM(self.app, None, qid=4,
            name=vanir.tests.VMPREFIX + 'nonet')
        self.app.domains = vanir.app.VMCollection(self.app)
        for domain in (vm, self.netvm1, self.netvm2, self.nonetvm):
            self.app.domains._dict[domain.qid] = domain
        self.app.default_netvm = self.netvm1
        self.app.default_fw_netvm = self.netvm1
        self.addCleanup(self.cleanup_netvms)

    def cleanup_netvms(self):
        self.netvm1.close()
        self.netvm2.close()
        self.nonetvm.close()
        try:
            self.app.domains.close()
        except AttributeError:
            pass
        del self.netvm1
        del self.netvm2
        del self.nonetvm
        del self.app.default_netvm
        del self.app.default_fw_netvm


    @vanir.tests.skipUnlessDom0
    def test_140_netvm(self):
        vm = self.get_vm()
        self.setup_netvms(vm)
        self.assertPropertyDefaultValue(vm, 'netvm', self.app.default_netvm)
        self.assertPropertyValue(vm, 'netvm', self.netvm2, self.netvm2,
            self.netvm2.name)
        del vm.netvm
        self.assertPropertyDefaultValue(vm, 'netvm', self.app.default_netvm)
        self.assertPropertyValue(vm, 'netvm', self.netvm2.name, self.netvm2,
            self.netvm2.name)
        self.assertPropertyValue(vm, 'netvm', None, None, '')

    def test_141_netvm_invalid(self):
        vm = self.get_vm()
        self.setup_netvms(vm)
        self.assertPropertyInvalidValue(vm, 'netvm', 'invalid')
        self.assertPropertyInvalidValue(vm, 'netvm', 123)

    def test_142_netvm_netvm(self):
        vm = self.get_vm()
        self.setup_netvms(vm)
        self.assertPropertyInvalidValue(vm, 'netvm', self.nonetvm)

    def test_143_netvm_loopback(self):
        vm = self.get_vm()
        self.app.domains = {1: vm, vm: vm}
        self.addCleanup(self.app.domains.clear)
        self.assertPropertyInvalidValue(vm, 'netvm', vm)

    def test_144_netvm_loopback2(self):
        vm = self.get_vm()
        self.setup_netvms(vm)
        vm.netvm = None
        self.netvm2.netvm = self.netvm1
        vm.provides_network = True
        self.netvm1.netvm = vm
        self.assertPropertyInvalidValue(vm, 'netvm', self.netvm2)

    def test_150_ip(self):
        vm = self.get_vm()
        self.setup_netvms(vm)
        self.assertPropertyDefaultValue(vm, 'ip',
            ipaddress.IPv4Address('10.137.0.' + str(vm.qid)))
        vm.ip = '192.168.1.1'
        self.assertEqual(vm.ip, ipaddress.IPv4Address('192.168.1.1'))

    def test_151_ip_invalid(self):
        vm = self.get_vm()
        self.setup_netvms(vm)
        self.assertPropertyInvalidValue(vm, 'ip', 'abcd')
        self.assertPropertyInvalidValue(vm, 'ip', 'a.b.c.d')
        self.assertPropertyInvalidValue(vm, 'ip', '1111.2222.3333.4444')
        # TODO: implement and add here: 0.0.0.0, 333.333.333.333

    def test_160_ip6(self):
        vm = self.get_vm()
        self.setup_netvms(vm)
        self.assertPropertyDefaultValue(vm, 'ip6', None)
        vm.netvm.features['ipv6'] = True
        self.assertPropertyDefaultValue(vm, 'ip6',
            ipaddress.IPv6Address('{}::a89:{:x}'.format(
                vanir.config.vanir_ipv6_prefix, vm.qid)))
        vm.ip6 = 'abcd:efff::1'
        self.assertEqual(vm.ip6, ipaddress.IPv6Address('abcd:efff::1'))

    def test_161_ip6_invalid(self):
        vm = self.get_vm()
        self.setup_netvms(vm)
        vm.netvm.features['ipv6'] = True
        self.assertPropertyInvalidValue(vm, 'ip', 'zzzz')
        self.assertPropertyInvalidValue(vm, 'ip',
            '1:2:3:4:5:6:7:8:0:a:b:c:d:e:f:0')

    def test_170_provides_network_netvm(self):
        vm = self.get_vm()
        vm2 = self.get_vm('test2', qid=3)
        self.assertPropertyDefaultValue(vm, 'provides_network', False)
        self.assertPropertyInvalidValue(vm2, 'netvm', vm)
        self.assertPropertyValue(vm, 'provides_network', True, True, 'True')
        self.assertPropertyValue(vm2, 'netvm', vm, vm, 'test-inst-test')
        # used by other vm
        self.assertPropertyInvalidValue(vm, 'provides_network', False)
        self.assertPropertyValue(vm2, 'netvm', None, None, '')
        self.assertPropertyValue(vm2, 'netvm', '', None, '')
        self.assertPropertyValue(vm, 'provides_network', False, False, 'False')
