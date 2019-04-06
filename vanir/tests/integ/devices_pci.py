import os
import subprocess
import time
import unittest

import vanir.devices
import vanir.ext.pci
import vanir.tests


@vanir.tests.skipUnlessEnv('VANIR_TEST_PCIDEV')
class TC_00_Devices_PCI(vanir.tests.SystemTestCase):
    def setUp(self):
        super(TC_00_Devices_PCI, self).setUp()
        if self._testMethodName not in ['test_000_list']:
            pcidev = os.environ['VANIR_TEST_PCIDEV']
            self.dev = self.app.domains[0].devices['pci'][pcidev]
            self.assignment = vanir.devices.DeviceAssignment(
                backend_domain=self.dev.backend_domain,
                ident=self.dev.ident,
                persistent=True)
            if isinstance(self.dev, vanir.devices.UnknownDevice):
                self.skipTest('Specified device {} does not exists'.format(pcidev))
            self.init_default_template()
            self.vm = self.app.add_new_vm(vanir.vm.appvm.AppVM,
                name=self.make_vm_name('vm'),
                label='red',
            )
            self.vm.virt_mode = 'hvm'
            self.loop.run_until_complete(
                self.vm.create_on_disk())
            self.vm.features['pci-no-strict-reset/' + pcidev] = True
            self.app.save()

    @unittest.expectedFailure
    def test_000_list(self):
        p = subprocess.Popen(['lspci'], stdout=subprocess.PIPE)
        # get a dict: BDF -> description
        actual_devices = dict(
            l.split(' (')[0].split(' ', 1)
                for l in p.communicate()[0].decode().splitlines())
        for dev in self.app.domains[0].devices['pci']:
            lspci_ident = dev.ident.replace('_', ':')
            self.assertIsInstance(dev, vanir.ext.pci.PCIDevice)
            self.assertEqual(dev.backend_domain, self.app.domains[0])
            self.assertIn(lspci_ident, actual_devices)
            self.assertEqual(dev.description, actual_devices[lspci_ident])
            actual_devices.pop(lspci_ident)

        if actual_devices:
            self.fail('Not all devices listed, missing: {}'.format(
                actual_devices))

    def assertDeviceNotInCollection(self, dev, dev_col):
        self.assertNotIn(dev, dev_col.attached())
        self.assertNotIn(dev, dev_col.persistent())
        self.assertNotIn(dev, dev_col.assignments())
        self.assertNotIn(dev, dev_col.assignments(persistent=True))

    def test_010_attach_offline_persistent(self):
        dev_col = self.vm.devices['pci']
        self.assertDeviceNotInCollection(self.dev, dev_col)
        self.loop.run_until_complete(
            dev_col.attach(self.assignment))
        self.app.save()
        self.assertNotIn(self.dev, dev_col.attached())
        self.assertIn(self.dev, dev_col.persistent())
        self.assertIn(self.dev, dev_col.assignments())
        self.assertIn(self.dev, dev_col.assignments(persistent=True))
        self.assertNotIn(self.dev, dev_col.assignments(persistent=False))

        self.loop.run_until_complete(self.vm.start())

        self.assertIn(self.dev, dev_col.attached())
        (stdout, _) = self.loop.run_until_complete(
            self.vm.run_for_stdio('lspci'))
        self.assertIn(self.dev.description, stdout.decode())


    def test_011_attach_offline_temp_fail(self):
        dev_col = self.vm.devices['pci']
        self.assertDeviceNotInCollection(self.dev, dev_col)
        self.assignment.persistent = False
        with self.assertRaises(vanir.exc.VanirVMNotRunningError):
            self.loop.run_until_complete(
                dev_col.attach(self.assignment))


    def test_020_attach_online_persistent(self):
        self.loop.run_until_complete(
            self.vm.start())
        dev_col = self.vm.devices['pci']
        self.assertDeviceNotInCollection(self.dev, dev_col)
        self.loop.run_until_complete(
            dev_col.attach(self.assignment))

        self.assertIn(self.dev, dev_col.attached())
        self.assertIn(self.dev, dev_col.persistent())
        self.assertIn(self.dev, dev_col.assignments())
        self.assertIn(self.dev, dev_col.assignments(persistent=True))
        self.assertNotIn(self.dev, dev_col.assignments(persistent=False))

        # give VM kernel some time to discover new device
        time.sleep(1)
        (stdout, _) = self.loop.run_until_complete(
            self.vm.run_for_stdio('lspci'))
        self.assertIn(self.dev.description, stdout.decode())


    def test_021_persist_detach_online_fail(self):
        dev_col = self.vm.devices['pci']
        self.assertDeviceNotInCollection(self.dev, dev_col)
        self.loop.run_until_complete(
            dev_col.attach(self.assignment))
        self.app.save()
        self.loop.run_until_complete(
            self.vm.start())
        with self.assertRaises(vanir.exc.VanirVMNotHaltedError):
            self.loop.run_until_complete(
                self.vm.devices['pci'].detach(self.assignment))

    def test_030_persist_attach_detach_offline(self):
        dev_col = self.vm.devices['pci']
        self.assertDeviceNotInCollection(self.dev, dev_col)
        self.loop.run_until_complete(
            dev_col.attach(self.assignment))
        self.app.save()
        self.assertNotIn(self.dev, dev_col.attached())
        self.assertIn(self.dev, dev_col.persistent())
        self.assertIn(self.dev, dev_col.assignments())
        self.assertIn(self.dev, dev_col.assignments(persistent=True))
        self.assertNotIn(self.dev, dev_col.assignments(persistent=False))
        self.loop.run_until_complete(
            dev_col.detach(self.assignment))
        self.assertDeviceNotInCollection(self.dev, dev_col)

    def test_031_attach_detach_online_temp(self):
        dev_col = self.vm.devices['pci']
        self.loop.run_until_complete(
            self.vm.start())
        self.assignment.persistent = False
        self.assertDeviceNotInCollection(self.dev, dev_col)
        self.loop.run_until_complete(
            dev_col.attach(self.assignment))

        self.assertIn(self.dev, dev_col.attached())
        self.assertNotIn(self.dev, dev_col.persistent())
        self.assertIn(self.dev, dev_col.assignments())
        self.assertIn(self.dev, dev_col.assignments(persistent=False))
        self.assertNotIn(self.dev, dev_col.assignments(persistent=True))
        self.assertIn(self.dev, dev_col.assignments(persistent=False))


        # give VM kernel some time to discover new device
        time.sleep(1)
        (stdout, _) = self.loop.run_until_complete(
            self.vm.run_for_stdio('lspci'))

        self.assertIn(self.dev.description, stdout.decode())
        self.loop.run_until_complete(
            dev_col.detach(self.assignment))
        self.assertDeviceNotInCollection(self.dev, dev_col)

        (stdout, _) = self.loop.run_until_complete(
            self.vm.run_for_stdio('lspci'))
        self.assertNotIn(self.dev.description, stdout.decode())
