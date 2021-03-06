import os
import unittest.mock as mock

import lxml.etree

import vanir
import vanir.events

import vanir.tests
import vanir.tests.init
import vanir.tests.storage_reflink

class TestApp(vanir.tests.TestEmitter):
    pass


class TC_20_VanirHost(vanir.tests.VanirTestCase):
    sample_xc_domain_getinfo = [
        {'paused': 0, 'cpu_time': 243951379111104, 'ssidref': 0,
            'hvm': 0, 'shutdown_reason': 255, 'dying': 0,
            'mem_kb': 3733212, 'domid': 0, 'max_vcpu_id': 7,
            'crashed': 0, 'running': 1, 'maxmem_kb': 3734236,
            'shutdown': 0, 'online_vcpus': 8,
            'handle': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            'cpupool': 0, 'blocked': 0},
        {'paused': 0, 'cpu_time': 2849496569205, 'ssidref': 0,
            'hvm': 0, 'shutdown_reason': 255, 'dying': 0,
            'mem_kb': 303916, 'domid': 1, 'max_vcpu_id': 0,
            'crashed': 0, 'running': 0, 'maxmem_kb': 308224,
            'shutdown': 0, 'online_vcpus': 1,
            'handle': [116, 174, 229, 207, 17, 1, 79, 39, 191, 37, 41,
                186, 205, 158, 219, 8],
            'cpupool': 0, 'blocked': 1},
        {'paused': 0, 'cpu_time': 249658663079978, 'ssidref': 0,
            'hvm': 0, 'shutdown_reason': 255, 'dying': 0,
            'mem_kb': 3782668, 'domid': 11, 'max_vcpu_id': 7,
            'crashed': 0, 'running': 0, 'maxmem_kb': 3783692,
            'shutdown': 0, 'online_vcpus': 8,
            'handle': [169, 95, 55, 127, 140, 94, 79, 220, 186, 210,
                117, 5, 148, 11, 185, 206],
            'cpupool': 0, 'blocked': 1}]

    def setUp(self):
        super(TC_20_VanirHost, self).setUp()
        self.app = TestApp()
        self.app.vmm = mock.Mock()
        self.vanir_host  = vanir.app.VanirHost(self.app)

    def test_000_get_vm_stats_single(self):
        self.app.vmm.configure_mock(**{
            'xc.domain_getinfo.return_value': self.sample_xc_domain_getinfo
        })

        info_time, info = self.vanir_host .get_vm_stats()
        self.assertEqual(self.app.vmm.mock_calls, [
            ('xc.domain_getinfo', (0, 1024), {}),
        ])
        self.assertIsNotNone(info_time)
        expected_info = {
            0: {
                'cpu_time': 243951379111104//8,
                'cpu_usage': 0,
                'memory_kb': 3733212,
            },
            1: {
                'cpu_time': 2849496569205,
                'cpu_usage': 0,
                'memory_kb': 303916,
            },
            11: {
                'cpu_time': 249658663079978//8,
                'cpu_usage': 0,
                'memory_kb': 3782668,
            },
        }
        self.assertEqual(info, expected_info)

    def test_001_get_vm_stats_twice(self):
        self.app.vmm.configure_mock(**{
            'xc.domain_getinfo.return_value': self.sample_xc_domain_getinfo
        })

        prev_time, prev_info = self.vanir_host .get_vm_stats()
        prev_time -= 1
        prev_info[0]['cpu_time'] -= 10**8
        prev_info[1]['cpu_time'] -= 10**9
        prev_info[11]['cpu_time'] -= 125 * 10**6
        info_time, info = self.vanir_host .get_vm_stats(prev_time, prev_info)
        self.assertIsNotNone(info_time)
        expected_info = {
            0: {
                'cpu_time': 243951379111104//8,
                'cpu_usage': 9,
                'memory_kb': 3733212,
            },
            1: {
                'cpu_time': 2849496569205,
                'cpu_usage': 99,
                'memory_kb': 303916,
            },
            11: {
                'cpu_time': 249658663079978//8,
                'cpu_usage': 12,
                'memory_kb': 3782668,
            },
        }
        self.assertEqual(info, expected_info)
        self.assertEqual(self.app.vmm.mock_calls, [
            ('xc.domain_getinfo', (0, 1024), {}),
            ('xc.domain_getinfo', (0, 1024), {}),
        ])

    def test_002_get_vm_stats_one_vm(self):
        self.app.vmm.configure_mock(**{
            'xc.domain_getinfo.return_value': [self.sample_xc_domain_getinfo[1]]
        })

        vm = mock.Mock
        vm.xid = 1
        vm.name = 'somevm'

        info_time, info = self.vanir_host .get_vm_stats(only_vm=vm)
        self.assertIsNotNone(info_time)
        self.assertEqual(self.app.vmm.mock_calls, [
            ('xc.domain_getinfo', (1, 1), {}),
        ])



class TC_30_VMCollection(vanir.tests.VanirTestCase):
    def setUp(self):
        super().setUp()
        self.app = TestApp()
        self.vms = vanir.app.VMCollection(self.app)

        self.testvm1 = vanir.tests.init.TestVM(
            None, None, qid=1, name='testvm1')
        self.testvm2 = vanir.tests.init.TestVM(
            None, None, qid=2, name='testvm2')

        self.addCleanup(self.cleanup_vmcollection)

    def cleanup_vmcollection(self):
        self.testvm1.close()
        self.testvm2.close()
        self.vms.close()
        del self.testvm1
        del self.testvm2
        del self.vms
        del self.app

    def test_000_contains(self):
        self.vms._dict = {1: self.testvm1}

        self.assertIn(1, self.vms)
        self.assertIn('testvm1', self.vms)
        self.assertIn(self.testvm1, self.vms)

        self.assertNotIn(2, self.vms)
        self.assertNotIn('testvm2', self.vms)
        self.assertNotIn(self.testvm2, self.vms)

    def test_001_getitem(self):
        self.vms._dict = {1: self.testvm1}

        self.assertIs(self.vms[1], self.testvm1)
        self.assertIs(self.vms['testvm1'], self.testvm1)
        self.assertIs(self.vms[self.testvm1], self.testvm1)

    def test_002_add(self):
        self.vms.add(self.testvm1)
        self.assertIn(1, self.vms)

        self.assertEventFired(self.app, 'domain-add',
            kwargs={'vm': self.testvm1})

        with self.assertRaises(TypeError):
            self.vms.add(object())

        testvm_qid_collision = vanir.tests.init.TestVM(
            None, None, name='testvm2', qid=1)
        testvm_name_collision = vanir.tests.init.TestVM(
            None, None, name='testvm1', qid=2)

        with self.assertRaises(ValueError):
            self.vms.add(testvm_qid_collision)
        with self.assertRaises(ValueError):
            self.vms.add(testvm_name_collision)

    def test_003_qids(self):
        self.vms.add(self.testvm1)
        self.vms.add(self.testvm2)

        self.assertCountEqual(self.vms.qids(), [1, 2])
        self.assertCountEqual(self.vms.keys(), [1, 2])

    def test_004_names(self):
        self.vms.add(self.testvm1)
        self.vms.add(self.testvm2)

        self.assertCountEqual(self.vms.names(), ['testvm1', 'testvm2'])

    def test_005_vms(self):
        self.vms.add(self.testvm1)
        self.vms.add(self.testvm2)

        self.assertCountEqual(self.vms.vms(), [self.testvm1, self.testvm2])
        self.assertCountEqual(self.vms.values(), [self.testvm1, self.testvm2])

    def test_006_items(self):
        self.vms.add(self.testvm1)
        self.vms.add(self.testvm2)

        self.assertCountEqual(self.vms.items(),
            [(1, self.testvm1), (2, self.testvm2)])

    def test_007_len(self):
        self.vms.add(self.testvm1)
        self.vms.add(self.testvm2)

        self.assertEqual(len(self.vms), 2)

    def test_008_delitem(self):
        self.vms.add(self.testvm1)
        self.vms.add(self.testvm2)

        del self.vms['testvm2']

        self.assertCountEqual(self.vms.vms(), [self.testvm1])
        self.assertEventFired(self.app, 'domain-delete',
            kwargs={'vm': self.testvm2})

    def test_100_get_new_unused_qid(self):
        self.vms.add(self.testvm1)
        self.vms.add(self.testvm2)

        self.vms.get_new_unused_qid()

#   def test_200_get_vms_based_on(self):
#       pass

#   def test_201_get_vms_connected_to(self):
#       pass


class TC_80_VanirInitialPools(vanir.tests.VanirTestCase):
    def setUp(self):
        super().setUp()
        self.app = vanir.Vanir('/tmp/vanirtest.xml', load=False,
            offline_mode=True)
        self.test_dir = '/var/tmp/test-varlibqubes'
        self.test_patch = mock.patch.dict(
            vanir.config.defaults['pool_configs']['varlibqubes'],
            {'dir_path': self.test_dir})
        self.test_patch.start()

    def tearDown(self):
        self.test_patch.stop()
        self.app.close()
        del self.app

    def get_driver(self, fs_type, accessible):
        vanir.tests.storage_reflink.mkdir_fs(self.test_dir, fs_type,
            accessible=accessible, cleanup_via=self.addCleanup)
        self.app.load_initial_values()

        varlibqubes = self.app.pools['varlibqubes']
        self.assertEqual(varlibqubes.dir_path, self.test_dir)
        return varlibqubes.driver

    def test_100_varlibqubes_btrfs_accessible(self):
        self.assertEqual(self.get_driver('btrfs', True), 'file-reflink')

    def test_101_varlibqubes_btrfs_inaccessible(self):
        self.assertEqual(self.get_driver('btrfs', False), 'file')

    def test_102_varlibqubes_ext4_accessible(self):
        self.assertEqual(self.get_driver('ext4', True), 'file')

    def test_103_varlibqubes_ext4_inaccessible(self):
        self.assertEqual(self.get_driver('ext4', False), 'file')


class TC_89_VanirEmpty(vanir.tests.VanirTestCase):
    def tearDown(self):
        try:
            os.unlink('/tmp/vanirtest.xml')
        except:
            pass
        try:
            self.app.close()
            del self.app
        except AttributeError:
            pass
        super().tearDown()

    @vanir.tests.skipUnlessDom0
    def test_000_init_empty(self):
        # pylint: disable=no-self-use,unused-variable,bare-except
        try:
            os.unlink('/tmp/vanirtest.xml')
        except FileNotFoundError:
            pass
        vanir.Vanir.create_empty_store('/tmp/vanirtest.xml').close()

    def test_100_property_migrate_default_fw_netvm(self):
        xml_template = '''<?xml version="1.0" encoding="utf-8" ?>
        <vanir version="3.0">
            <properties>
                <property name="default_netvm">{default_netvm}</property>
                <property name="default_fw_netvm">{default_fw_netvm}</property>
            </properties>
            <labels>
                <label id="label-1" color="#cc0000">red</label>
            </labels>
            <pools>
              <pool driver="file" dir_path="/tmp/vanir-test" name="default"/>
            </pools>
            <domains>
                <domain class="StandaloneVM" id="domain-1">
                    <properties>
                        <property name="qid">1</property>
                        <property name="name">sys-net</property>
                        <property name="provides_network">True</property>
                        <property name="label" ref="label-1" />
                        <property name="netvm"></property>
                        <property name="uuid">2fcfc1f4-b2fe-4361-931a-c5294b35edfa</property>
                    </properties>
                    <features/>
                    <devices class="pci"/>
                </domain>

                <domain class="StandaloneVM" id="domain-2">
                    <properties>
                        <property name="qid">2</property>
                        <property name="name">sys-firewall</property>
                        <property name="provides_network">True</property>
                        <property name="label" ref="label-1" />
                        <property name="uuid">9a6d9689-25f7-48c9-a15f-8205d6c5b7c6</property>
                    </properties>
                </domain>

                <domain class="StandaloneVM" id="domain-3">
                    <properties>
                        <property name="qid">3</property>
                        <property name="name">appvm</property>
                        <property name="label" ref="label-1" />
                        <property name="uuid">1d6aab41-3262-400a-b3d3-21aae8fdbec8</property>
                    </properties>
                </domain>
            </domains>
        </vanir>
        '''
        with self.subTest('default_setup'):
            with open('/tmp/vanirtest.xml', 'w') as xml_file:
                xml_file.write(xml_template.format(
                    default_netvm='sys-firewall',
                    default_fw_netvm='sys-net'))
            self.app = vanir.Vanir('/tmp/vanirtest.xml', offline_mode=True)
            self.assertEqual(
                self.app.domains['sys-net'].netvm, None)
            self.assertEqual(
                self.app.domains['sys-firewall'].netvm, self.app.domains['sys-net'])
            # property is no longer "default"
            self.assertFalse(
                self.app.domains['sys-firewall'].property_is_default('netvm'))
            # verify that appvm.netvm is unaffected
            self.assertTrue(
                self.app.domains['appvm'].property_is_default('netvm'))
            self.assertEqual(
                self.app.domains['appvm'].netvm,
                self.app.domains['sys-firewall'])
            with self.assertRaises(AttributeError):
                self.app.default_fw_netvm

            self.app.close()
            del self.app

        with self.subTest('same'):
            with open('/tmp/vanirtest.xml', 'w') as xml_file:
                xml_file.write(xml_template.format(
                    default_netvm='sys-net',
                    default_fw_netvm='sys-net'))
            self.app = vanir.Vanir('/tmp/vanirtest.xml', offline_mode=True)
            self.assertEqual(
                self.app.domains['sys-net'].netvm, None)
            self.assertEqual(
                self.app.domains['sys-firewall'].netvm,
                self.app.domains['sys-net'])
            self.assertTrue(
                self.app.domains['sys-firewall'].property_is_default('netvm'))
            # verify that appvm.netvm is unaffected
            self.assertTrue(
                self.app.domains['appvm'].property_is_default('netvm'))
            self.assertEqual(
                self.app.domains['appvm'].netvm,
                self.app.domains['sys-net'])
            with self.assertRaises(AttributeError):
                self.app.default_fw_netvm

        with self.subTest('loop'):
            with open('/tmp/vanirtest.xml', 'w') as xml_file:
                xml_file.write(xml_template.format(
                    default_netvm='sys-firewall',
                    default_fw_netvm='sys-firewall'))
            self.app = vanir.Vanir('/tmp/vanirtest.xml', offline_mode=True)
            self.assertEqual(
                self.app.domains['sys-net'].netvm, None)
            # this was netvm loop, better set to none, to not crash qubesd
            self.assertEqual(
                self.app.domains['sys-firewall'].netvm, None)
            self.assertFalse(
                self.app.domains['sys-firewall'].property_is_default('netvm'))
            # verify that appvm.netvm is unaffected
            self.assertTrue(
                self.app.domains['appvm'].property_is_default('netvm'))
            self.assertEqual(
                self.app.domains['appvm'].netvm,
                self.app.domains['sys-firewall'])
            with self.assertRaises(AttributeError):
                self.app.default_fw_netvm


class TC_90_Vanir(vanir.tests.VanirTestCase):
    def tearDown(self):
        try:
            os.unlink('/tmp/vanirtest.xml')
        except:
            pass
        super().tearDown()

    def setUp(self):
        super(TC_90_Vanir, self).setUp()
        self.app = vanir.Vanir('/tmp/vanirtest.xml', load=False,
            offline_mode=True)
        self.addCleanup(self.cleanup_vanir)
        self.app.load_initial_values()
        self.template = self.app.add_new_vm('TemplateVM', name='test-template',
            label='green')

    def cleanup_vanir(self):
        self.app.close()
        del self.app
        try:
            del self.template
        except AttributeError:
            pass

    def test_100_clockvm(self):
        appvm = self.app.add_new_vm('AppVM', name='test-vm', template=self.template,
            label='red')
        self.assertIsNone(self.app.clockvm)
        self.assertNotIn('service.clocksync', appvm.features)
        self.assertNotIn('service.clocksync', self.template.features)
        self.app.clockvm = appvm
        self.assertIn('service.clocksync', appvm.features)
        self.assertTrue(appvm.features['service.clocksync'])
        self.app.clockvm = self.template
        self.assertNotIn('service.clocksync', appvm.features)
        self.assertIn('service.clocksync', self.template.features)
        self.assertTrue(self.template.features['service.clocksync'])

    def test_110_netvm_loop(self):
        '''Netvm loop through default_netvm'''
        netvm = self.app.add_new_vm('AppVM', name='test-net',
            template=self.template, label='red')
        try:
            self.app.default_netvm = None
            netvm.netvm = vanir.property.DEFAULT
            with self.assertRaises(ValueError):
                self.app.default_netvm = netvm
        finally:
            del netvm

    def test_111_netvm_loop(self):
        '''Netvm loop through default_netvm'''
        netvm = self.app.add_new_vm('AppVM', name='test-net',
            template=self.template, label='red')
        try:
            netvm.netvm = None
            self.app.default_netvm = netvm
            with self.assertRaises(ValueError):
                netvm.netvm = vanir.property.DEFAULT
        finally:
            del netvm

    def test_200_remove_template(self):
        appvm = self.app.add_new_vm('AppVM', name='test-vm',
            template=self.template,
            label='red')
        with mock.patch.object(self.app, 'vmm'):
            with self.assertRaises(vanir.exc.VanirException):
                del self.app.domains[self.template]

    def test_201_remove_netvm(self):
        netvm = self.app.add_new_vm('AppVM', name='test-netvm',
            template=self.template, provides_network=True,
            label='red')
        appvm = self.app.add_new_vm('AppVM', name='test-vm',
            template=self.template,
            label='red')
        appvm.netvm = netvm
        with mock.patch.object(self.app, 'vmm'):
            with self.assertRaises(vanir.exc.VanirVMInUseError):
                del self.app.domains[netvm]

    def test_202_remove_default_netvm(self):
        netvm = self.app.add_new_vm('AppVM', name='test-netvm',
            template=self.template, provides_network=True,
            label='red')
        netvm.netvm = None
        self.app.default_netvm = netvm
        with mock.patch.object(self.app, 'vmm'):
            with self.assertRaises(vanir.exc.VanirVMInUseError):
                del self.app.domains[netvm]

    def test_203_remove_default_dispvm(self):
        appvm = self.app.add_new_vm('AppVM', name='test-appvm',
            template=self.template,
            label='red')
        self.app.default_dispvm = appvm
        with mock.patch.object(self.app, 'vmm'):
            with self.assertRaises(vanir.exc.VanirVMInUseError):
                del self.app.domains[appvm]

    def test_204_remove_appvm_dispvm(self):
        dispvm = self.app.add_new_vm('AppVM', name='test-appvm',
            template=self.template,
            label='red')
        appvm = self.app.add_new_vm('AppVM', name='test-appvm2',
            template=self.template, default_dispvm=dispvm,
            label='red')
        with mock.patch.object(self.app, 'vmm'):
            with self.assertRaises(vanir.exc.VanirVMInUseError):
                del self.app.domains[dispvm]

    def test_205_remove_appvm_dispvm(self):
        appvm = self.app.add_new_vm('AppVM', name='test-appvm',
            template=self.template, template_for_dispvms=True,
            label='red')
        dispvm = self.app.add_new_vm('DispVM', name='test-dispvm',
            template=appvm,
            label='red')
        with mock.patch.object(self.app, 'vmm'):
            with self.assertRaises(vanir.exc.VanirVMInUseError):
                del self.app.domains[appvm]

    @vanir.tests.skipUnlessGit
    def test_900_example_xml_in_doc(self):
        self.assertXMLIsValid(
            lxml.etree.parse(open(
                os.path.join(vanir.tests.in_git, 'doc/example.xml'), 'rb')),
            'vanir.rng')
