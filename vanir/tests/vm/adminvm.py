import unittest
import unittest.mock

import vanir
import vanir.exc
import vanir.vm
import vanir.vm.adminvm

import vanir.tests

class TC_00_AdminVM(vanir.tests.VanirTestCase):
    def setUp(self):
        super().setUp()
        try:
            self.app = vanir.tests.vm.TestApp()
            with unittest.mock.patch.object(
                    vanir.vm.adminvm.AdminVM, 'start_qdb_watch') as mock_qdb:
                self.vm = vanir.vm.adminvm.AdminVM(self.app,
                    xml=None)
                mock_qdb.assert_called_once_with()
                self.addCleanup(self.cleanup_adminvm)
        except:  # pylint: disable=bare-except
            if self.id().endswith('.test_000_init'):
                raise
            self.skipTest('setup failed')

    def cleanup_adminvm(self):
        self.vm.close()
        del self.vm

    def test_000_init(self):
        pass

    def test_100_xid(self):
        self.assertEqual(self.vm.xid, 0)

    def test_101_libvirt_domain(self):
        with unittest.mock.patch.object(self.app, 'vmm') as mock_vmm:
            self.assertIsNotNone(self.vm.libvirt_domain)
            self.assertEqual(mock_vmm.mock_calls, [
                ('libvirt_conn.lookupByID', (0,), {}),
            ])

    def test_300_is_running(self):
        self.assertTrue(self.vm.is_running())

    def test_301_get_power_state(self):
        self.assertEqual(self.vm.get_power_state(), 'Running')

    def test_302_get_mem(self):
        self.assertGreater(self.vm.get_mem(), 0)

    @unittest.skip('mock object does not support this')
    def test_303_get_mem_static_max(self):
        self.assertGreater(self.vm.get_mem_static_max(), 0)

    def test_310_start(self):
        with self.assertRaises(vanir.exc.VanirException):
            self.vm.start()

    @unittest.skip('this functionality is undecided')
    def test_311_suspend(self):
        with self.assertRaises(vanir.exc.VanirException):
            self.vm.suspend()
