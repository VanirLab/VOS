import unittest.mock as mock

import asyncio

import vanir.vm.dispvm
import vanir.vm.appvm
import vanir.vm.templatevm
import vanir.tests
import vanir.tests.vm
import vanir.tests.vm.appvm

class TestApp(vanir.tests.vm.TestApp):
    def __init__(self):
        super(TestApp, self).__init__()
        self.qid_counter = 1

    def add_new_vm(self, cls, **kwargs):
        qid = self.qid_counter
        self.qid_counter += 1
        vm = cls(self, None, qid=qid, **kwargs)
        self.domains[vm.name] = vm
        self.domains[vm] = vm
        return vm

class TC_00_DispVM(vanir.tests.VanirTestCase):
    def setUp(self):
        super(TC_00_DispVM, self).setUp()
        self.app = TestApp()
        self.app.save = mock.Mock()
        self.app.pools['default'] = vanir.tests.vm.appvm.TestPool('default')
        self.app.pools['linux-kernel'] = mock.Mock(**{
            'init_volume.return_value.pool': 'linux-kernel'})
        self.app.vmm.offline_mode = True
        self.template = self.app.add_new_vm(vanir.vm.templatevm.TemplateVM,
            name='test-template', label='red')
        self.appvm = self.app.add_new_vm(vanir.vm.appvm.AppVM,
            name='test-vm', template=self.template, label='red')
        self.app.domains[self.appvm.name] = self.appvm
        self.app.domains[self.appvm] = self.appvm
        self.addCleanup(self.cleanup_dispvm)

    def cleanup_dispvm(self):
        self.template.close()
        self.appvm.close()
        del self.template
        del self.appvm
        self.app.domains.clear()
        self.app.pools.clear()

    @asyncio.coroutine
    def mock_coro(self, *args, **kwargs):
        pass

    @mock.patch('os.symlink')
    @mock.patch('os.makedirs')
    @mock.patch('vanir.storage.Storage')
    def test_000_from_appvm(self, mock_storage, mock_makedirs, mock_symlink):
        mock_storage.return_value.create.side_effect = self.mock_coro
        self.appvm.template_for_dispvms = True
        orig_getitem = self.app.domains.__getitem__
        with mock.patch.object(self.app, 'domains', wraps=self.app.domains) \
                as mock_domains:
            mock_domains.configure_mock(**{
                'get_new_unused_dispid': mock.Mock(return_value=42),
                '__getitem__.side_effect': orig_getitem
            })
            dispvm = self.loop.run_until_complete(
                vanir.vm.dispvm.DispVM.from_appvm(self.appvm))
            mock_domains.get_new_unused_dispid.assert_called_once_with()
        self.assertEqual(dispvm.name, 'disp42')
        self.assertEqual(dispvm.template, self.appvm)
        self.assertEqual(dispvm.label, self.appvm.label)
        self.assertEqual(dispvm.label, self.appvm.label)
        self.assertEqual(dispvm.auto_cleanup, True)
        mock_makedirs.assert_called_once_with(
            '/var/lib/vanir/appvms/' + dispvm.name, mode=0o775, exist_ok=True)
        mock_symlink.assert_called_once_with(
            '/usr/share/icons/hicolor/128x128/devices/appvm-red.png',
            '/var/lib/vanir/appvms/{}/icon.png'.format(dispvm.name))

    def test_001_from_appvm_reject_not_allowed(self):
        with self.assertRaises(vanir.exc.VanirException):
            dispvm = self.loop.run_until_complete(
                vanir.vm.dispvm.DispVM.from_appvm(self.appvm))

    def test_002_template_change(self):
        self.appvm.template_for_dispvms = True
        orig_getitem = self.app.domains.__getitem__
        with mock.patch.object(self.app, 'domains', wraps=self.app.domains) \
                as mock_domains:
            mock_domains.configure_mock(**{
                'get_new_unused_dispid': mock.Mock(return_value=42),
                '__getitem__.side_effect': orig_getitem
            })
            dispvm = self.app.add_new_vm(vanir.vm.dispvm.DispVM,
                name='test-dispvm', template=self.appvm)

            with self.assertRaises(vanir.exc.VanirValueError):
                dispvm.template = self.appvm
            with self.assertRaises(vanir.exc.VanirValueError):
                dispvm.template = vanir.property.DEFAULT


    def test_010_create_direct(self):
        self.appvm.template_for_dispvms = True
        orig_getitem = self.app.domains.__getitem__
        with mock.patch.object(self.app, 'domains', wraps=self.app.domains) \
                as mock_domains:
            mock_domains.configure_mock(**{
                'get_new_unused_dispid': mock.Mock(return_value=42),
                '__getitem__.side_effect': orig_getitem
            })
            dispvm = self.app.add_new_vm(vanir.vm.dispvm.DispVM,
                name='test-dispvm', template=self.appvm)
            mock_domains.get_new_unused_dispid.assert_called_once_with()
        self.assertEqual(dispvm.name, 'test-dispvm')
        self.assertEqual(dispvm.template, self.appvm)
        self.assertEqual(dispvm.label, self.appvm.label)
        self.assertEqual(dispvm.label, self.appvm.label)
        self.assertEqual(dispvm.auto_cleanup, False)

    def test_011_create_direct_generate_name(self):
        self.appvm.template_for_dispvms = True
        orig_getitem = self.app.domains.__getitem__
        with mock.patch.object(self.app, 'domains', wraps=self.app.domains) \
                as mock_domains:
            mock_domains.configure_mock(**{
                'get_new_unused_dispid': mock.Mock(return_value=42),
                '__getitem__.side_effect': orig_getitem
            })
            dispvm = self.app.add_new_vm(vanir.vm.dispvm.DispVM,
                template=self.appvm)
            mock_domains.get_new_unused_dispid.assert_called_once_with()
        self.assertEqual(dispvm.name, 'disp42')
        self.assertEqual(dispvm.template, self.appvm)
        self.assertEqual(dispvm.label, self.appvm.label)
        self.assertEqual(dispvm.auto_cleanup, False)

    def test_011_create_direct_reject(self):
        orig_getitem = self.app.domains.__getitem__
        with mock.patch.object(self.app, 'domains', wraps=self.app.domains) \
                as mock_domains:
            mock_domains.configure_mock(**{
                'get_new_unused_dispid': mock.Mock(return_value=42),
                '__getitem__.side_effect': orig_getitem
            })
            with self.assertRaises(vanir.exc.VanirException):
                self.app.add_new_vm(vanir.vm.dispvm.DispVM,
                    name='test-dispvm', template=self.appvm)
            self.assertFalse(mock_domains.get_new_unused_dispid.called)
