from unittest import mock

import lxml.etree

import vanir.storage
import vanir.tests
import vanir.tests.vm.vanirvm
import vanir.vm.appvm
import vanir.vm.templatevm

class TestApp(object):
    labels = {1: vanir.Label(1, '0xcc0000', 'red')}

    def __init__(self):
        self.domains = {}

class TestProp(object):
    # pylint: disable=too-few-public-methods
    __name__ = 'testprop'

class TestVM(object):
    # pylint: disable=too-few-public-methods
    app = TestApp()

    def __init__(self, **kwargs):
        self.running = False
        self.installed_by_rpm = False
        for k, v in kwargs.items():
            setattr(self, k, v)

    def is_running(self):
        return self.running

class TestPool(vanir.storage.Pool):
    def init_volume(self, vm, volume_config):
        vid = '{}/{}'.format(vm.name, volume_config['name'])
        assert volume_config.pop('pool', None) == self
        return vanir.storage.Volume(vid=vid, pool=self, **volume_config)


class TC_90_AppVM(vanir.tests.vm.qubesvm.VanirVMTestsMixin,
        vanir.tests.VanirTestCase):
    def setUp(self):
        super().setUp()
        self.app.pools['default'] = TestPool('default')
        self.app.pools['linux-kernel'] = mock.Mock(**{
            'init_volume.return_value.pool': 'linux-kernel'})
        self.template = vanir.vm.templatevm.TemplateVM(self.app, None,
            qid=1, name=vanir.tests.VMPREFIX + 'template')
        self.app.domains[self.template.name] = self.template
        self.app.domains[self.template] = self.template
        self.addCleanup(self.cleanup_appvm)

    def cleanup_appvm(self):
        self.template.close()
        del self.template
        self.app.domains.clear()
        self.app.pools.clear()

    def get_vm(self, **kwargs):
        vm = vanir.vm.appvm.AppVM(self.app, None,
            qid=2, name=vanir.tests.VMPREFIX + 'test',
            template=self.template,
            **kwargs)
        self.addCleanup(vm.close)
        return vm

    def test_000_init(self):
        self.get_vm()

    def test_001_storage_init(self):
        vm = self.get_vm()
        self.assertTrue(vm.volume_config['private']['save_on_stop'])
        self.assertFalse(vm.volume_config['private']['snap_on_start'])
        self.assertIsNone(vm.volume_config['private'].get('source', None))

        self.assertFalse(vm.volume_config['root']['save_on_stop'])
        self.assertTrue(vm.volume_config['root']['snap_on_start'])
        self.assertEqual(vm.volume_config['root'].get('source', None),
            self.template.volumes['root'])

        self.assertFalse(
            vm.volume_config['volatile'].get('save_on_stop', False))
        self.assertFalse(
            vm.volume_config['volatile'].get('snap_on_start', False))
        self.assertIsNone(vm.volume_config['volatile'].get('source', None))

    def test_002_storage_template_change(self):
        vm = self.get_vm()
        # create new mock, so new template will get different volumes
        self.app.pools['default'] = mock.Mock(**{
            'init_volume.return_value.pool': 'default'})
        template2 = vanir.vm.templatevm.TemplateVM(self.app, None,
            qid=3, name=vanir.tests.VMPREFIX + 'template2')
        self.app.domains[template2.name] = template2
        self.app.domains[template2] = template2

        vm.template = template2
        self.assertFalse(vm.volume_config['root']['save_on_stop'])
        self.assertTrue(vm.volume_config['root']['snap_on_start'])
        self.assertNotEqual(vm.volume_config['root'].get('source', None),
            self.template.volumes['root'].source)
        self.assertEqual(vm.volume_config['root'].get('source', None),
            template2.volumes['root'])

    def test_003_template_change_running(self):
        vm = self.get_vm()
        with mock.patch.object(vm, 'get_power_state') as mock_power:
            mock_power.return_value = 'Running'
            with self.assertRaises(vanir.exc.VanirVMNotHaltedError):
                vm.template = self.template

    def test_004_template_reset(self):
        vm = self.get_vm()
        with self.assertRaises(vanir.exc.VanirValueError):
            vm.template = vanir.property.DEFAULT

    def test_500_property_migrate_template_for_dispvms(self):
        xml_template = '''
        <domain class="AppVM" id="domain-1">
            <properties>
                <property name="qid">1</property>
                <property name="name">testvm</property>
                <property name="label" ref="label-1" />
                <property name="dispvm_allowed">{value}</property>
            </properties>
        </domain>
        '''
        xml = lxml.etree.XML(xml_template.format(value='True'))
        vm = vanir.vm.appvm.AppVM(self.app, xml)
        self.assertEqual(vm.template_for_dispvms, True)
        with self.assertRaises(AttributeError):
            vm.dispvm_allowed

        xml = lxml.etree.XML(xml_template.format(value='False'))
        vm = vanir.vm.appvm.AppVM(self.app, xml)
        self.assertEqual(vm.template_for_dispvms, False)
        with self.assertRaises(AttributeError):
            vm.dispvm_allowed
