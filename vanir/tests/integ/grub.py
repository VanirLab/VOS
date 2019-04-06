import os
import subprocess
import sys
import unittest

import vanir.tests

class GrubBase(object):
    virt_mode = None
    kernel = None

    def setUp(self):
        super(GrubBase, self).setUp()
        supported = False
        if self.template.startswith('fedora-'):
            supported = True
        elif self.template.startswith('debian-'):
            supported = True
        if not supported:
            self.skipTest("Template {} not supported by this test".format(
                self.template))

    def install_packages(self, vm):
        if self.template.startswith('fedora-'):
            cmd_install1 = 'dnf clean expire-cache && ' \
                'dnf install -y vanir-kernel-vm-support grub2-tools'
            cmd_install2 = 'dnf install -y kernel-core && ' \
                'KVER=$(rpm -q --qf ' \
                '\'%{VERSION}-%{RELEASE}.%{ARCH}\\n\' kernel-core|head -1) && ' \
                'dnf install --allowerasing  -y kernel-devel-$KVER && ' \
                'dkms autoinstall -k $KVER'
            cmd_update_grub = 'grub2-mkconfig -o /boot/grub2/grub.cfg'
        elif self.template.startswith('debian-'):
            cmd_install1 = 'apt-get update && apt-get install -y ' \
                           'vanir-kernel-vm-support grub2-common'
            cmd_install2 = 'apt-get install -y linux-image-amd64'
            cmd_update_grub = 'mkdir -p /boot/grub && update-grub2'
        else:
            assert False, "Unsupported template?!"

        for cmd in [cmd_install1, cmd_install2, cmd_update_grub]:
            try:
                self.loop.run_until_complete(vm.run_for_stdio(
                    cmd, user="root"))
            except subprocess.CalledProcessError as err:
                self.fail("Failed command: {}\nSTDOUT: {}\nSTDERR: {}"
                          .format(cmd, err.stdout, err.stderr))

    def get_kernel_version(self, vm):
        if self.template.startswith('fedora-'):
            cmd_get_kernel_version = 'rpm -q kernel-core|sort -V|tail -1|' \
                                     'cut -d - -f 3-'
        elif self.template.startswith('debian-'):
            cmd_get_kernel_version = \
                'dpkg-query --showformat=\'${Package}\\n\' --show ' \
                '\'linux-image-*-amd64\'|sort -n|tail -1|cut -d - -f 3-'
        else:
            raise RuntimeError("Unsupported template?!")

        kver, _ = self.loop.run_until_complete(vm.run_for_stdio(
            cmd_get_kernel_version, user="root"))
        return kver.strip()

    def assertXenScrubPagesEnabled(self, vm):
        enabled, _ = self.loop.run_until_complete(vm.run_for_stdio(
            'cat /sys/devices/system/xen_memory/xen_memory0/scrub_pages || '
            'echo 1'))
        enabled = enabled.decode().strip()
        self.assertEqual(enabled, '1',
            'Xen scrub pages not enabled in {}'.format(vm.name))

    def test_000_standalone_vm(self):
        self.testvm1 = self.app.add_new_vm('StandaloneVM',
            name=self.make_vm_name('vm1'),
            label='red')
        self.testvm1.virt_mode = self.virt_mode
        self.testvm1.features.update(self.app.domains[self.template].features)
        self.loop.run_until_complete(
            self.testvm1.clone_disk_files(self.app.domains[self.template]))
        self.loop.run_until_complete(self.testvm1.start())
        self.install_packages(self.testvm1)
        kver = self.get_kernel_version(self.testvm1)
        self.loop.run_until_complete(self.testvm1.shutdown(wait=True))

        self.testvm1.kernel = self.kernel
        self.loop.run_until_complete(self.testvm1.start())
        (actual_kver, _) = self.loop.run_until_complete(
            self.testvm1.run_for_stdio('uname -r'))
        self.assertEquals(actual_kver.strip(), kver)

        self.assertXenScrubPagesEnabled(self.testvm1)

    def test_010_template_based_vm(self):
        self.test_template = self.app.add_new_vm('TemplateVM',
            name=self.make_vm_name('template'), label='red')
        self.test_template.virt_mode = self.virt_mode
        self.test_template.features.update(self.app.domains[self.template].features)
        self.loop.run_until_complete(
            self.test_template.clone_disk_files(self.app.domains[self.template]))

        self.testvm1 = self.app.add_new_vm("AppVM",
                                     template=self.test_template,
                                     name=self.make_vm_name('vm1'),
                                     label='red')
        self.testvm1.virt_mode = self.virt_mode
        self.loop.run_until_complete(self.testvm1.create_on_disk())
        self.loop.run_until_complete(self.test_template.start())
        self.install_packages(self.test_template)
        kver = self.get_kernel_version(self.test_template)
        self.loop.run_until_complete(self.test_template.shutdown(wait=True))

        self.test_template.kernel = self.kernel
        self.testvm1.kernel = self.kernel

        # Check if TemplateBasedVM boots and has the right kernel
        self.loop.run_until_complete(
            self.testvm1.start())
        (actual_kver, _) = self.loop.run_until_complete(
            self.testvm1.run_for_stdio('uname -r'))
        self.assertEquals(actual_kver.strip(), kver)

        self.assertXenScrubPagesEnabled(self.testvm1)

        # And the same for the TemplateVM itself
        self.loop.run_until_complete(self.test_template.start())
        (actual_kver, _) = self.loop.run_until_complete(
            self.test_template.run_for_stdio('uname -r'))
        self.assertEquals(actual_kver.strip(), kver)

        self.assertXenScrubPagesEnabled(self.test_template)

@unittest.skipUnless(os.path.exists('/var/lib/vanir/vm-kernels/pvgrub2'),
                     'grub-xen package not installed')
class TC_40_PVGrub(GrubBase):
    virt_mode = 'pv'
    kernel = 'pvgrub2'

class TC_41_HVMGrub(GrubBase):
    virt_mode = 'hvm'
    kernel = None

def create_testcases_for_templates():
    yield from vanir.tests.create_testcases_for_templates('TC_40_PVGrub',
        TC_40_PVGrub, vanir.tests.SystemTestCase,
        module=sys.modules[__name__])
    yield from vanir.tests.create_testcases_for_templates('TC_41_HVMGrub',
        TC_41_HVMGrub, vanir.tests.SystemTestCase,
        module=sys.modules[__name__])

def load_tests(loader, tests, pattern):
    tests.addTests(loader.loadTestsFromNames(
        create_testcases_for_templates()))
    return tests

vanir.tests.maybe_create_testcases_on_import(create_testcases_for_templates)
