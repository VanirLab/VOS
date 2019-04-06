import os

import sys

import vanir
import vanir.tests
import subprocess

# the same class for both dom0 and VMs
class TC_00_List(vanir.tests.SystemTestCase):
    template = None

    def setUp(self):
        super().setUp()
        self.img_path = '/tmp/test.img'
        self.mount_point = '/tmp/test-dir'
        if self.template is not None:
            self.vm = self.app.add_new_vm(
                "AppVM",
                label='red',
                name=self.make_vm_name("vm"))
            self.loop.run_until_complete(
                self.vm.create_on_disk())
            self.app.save()
            self.loop.run_until_complete(self.vm.start())
        else:
            self.vm = self.app.domains[0]

    def tearDown(self):
        super().tearDown()
        if self.template is None:
            if os.path.exists(self.mount_point):
                subprocess.call(['sudo', 'umount', self.mount_point])
                subprocess.call(['sudo', 'rmdir', self.mount_point])
            if os.path.exists('/dev/mapper/test-dm'):
                subprocess.call(['sudo', 'dmsetup', 'remove', 'test-dm'])
            if os.path.exists(self.img_path):
                loopdev = subprocess.check_output(['losetup', '-j',
                    self.img_path])
                for dev in loopdev.decode().splitlines():
                    subprocess.call(
                        ['sudo', 'losetup', '-d', dev.split(':')[0]])
                subprocess.call(['sudo', 'rm', '-f', self.img_path])

    def run_script(self, script, user="user"):
        if self.template is None:
            if user == "user":
                subprocess.check_call(script, shell=True)
            elif user == "root":
                subprocess.check_call(['sudo', 'sh', '-c', script])
        else:
            self.loop.run_until_complete(
                self.vm.run_for_stdio(script, user=user))

    def test_000_list_loop(self):
        if self.template is None:
            self.skipTest('loop devices excluded in dom0')
        self.run_script(
            "set -e;"
            "truncate -s 128M {path}; "
            "losetup -f {path}; "
            "udevadm settle".format(path=self.img_path), user="root")

        dev_list = list(self.vm.devices['block'])
        found = False
        for dev in dev_list:
            if dev.description == self.img_path:
                self.assertTrue(dev.ident.startswith('loop'))
                self.assertEquals(dev.mode, 'w')
                self.assertEquals(dev.size, 1024 * 1024 * 128)
                found = True

        if not found:
            self.fail("Device {} not found in {!r}".format(
                self.img_path, dev_list))

    def test_001_list_loop_mounted(self):
        if self.template is None:
            self.skipTest('loop devices excluded in dom0')
        self.run_script(
            "set -e;"
            "truncate -s 128M {path}; "
            "mkfs.ext4 -q -F {path}; "
            "mkdir -p {mntdir}; "
            "mount {path} {mntdir} -o loop; "
            "udevadm settle".format(
                path=self.img_path,
                mntdir=self.mount_point),
            user="root")

        dev_list = list(self.vm.devices['block'])
        for dev in dev_list:
            if dev.description == self.img_path:
                self.fail(
                    'Device {} ({}) should not be listed because is mounted'
                    .format(dev, self.img_path))

    def test_010_list_dm(self):
        self.run_script(
            "set -e;"
            "truncate -s 128M {path}; "
            "loopdev=`losetup -f`; "
            "losetup $loopdev {path}; "
            "dmsetup create test-dm --table \"0 262144 linear $(cat "
            "/sys/block/$(basename $loopdev)/dev) 0\";"
            "udevadm settle".format(path=self.img_path), user="root")

        dev_list = list(self.vm.devices['block'])
        found = False
        for dev in dev_list:
            if dev.ident.startswith('loop'):
                self.assertNotEquals(dev.description, self.img_path,
                    "Device {} ({}) should not be listed as it is used in "
                    "device-mapper".format(dev, self.img_path)
                )
            elif dev.description == 'test-dm':
                self.assertEquals(dev.mode, 'w')
                self.assertEquals(dev.size, 1024 * 1024 * 128)
                found = True

        if not found:
            self.fail("Device {} not found in {!r}".format('test-dm', dev_list))

    def test_011_list_dm_mounted(self):
        self.run_script(
            "set -e;"
            "truncate -s 128M {path}; "
            "loopdev=`losetup -f`; "
            "losetup $loopdev {path}; "
            "dmsetup create test-dm --table \"0 262144 linear $(cat "
            "/sys/block/$(basename $loopdev)/dev) 0\";"
            "mkfs.ext4 -q -F /dev/mapper/test-dm;"
            "mkdir -p {mntdir};"
            "mount /dev/mapper/test-dm {mntdir};"
            "udevadm settle".format(
                path=self.img_path,
                mntdir=self.mount_point),
            user="root")

        dev_list = list(self.vm.devices['block'])
        for dev in dev_list:
            if dev.ident.startswith('loop'):
                self.assertNotEquals(dev.description, self.img_path,
                    "Device {} ({}) should not be listed as it is used in "
                    "device-mapper".format(dev, self.img_path)
                )
            else:
                self.assertNotEquals(dev.description, 'test-dm',
                    "Device {} ({}) should not be listed as it is "
                    "mounted".format(dev, 'test-dm')
                )

    def test_012_list_dm_delayed(self):
        self.run_script(
            "set -e;"
            "truncate -s 128M {path}; "
            "loopdev=`losetup -f`; "
            "losetup $loopdev {path}; "
            "udevadm settle; "
            "dmsetup create test-dm --table \"0 262144 linear $(cat "
            "/sys/block/$(basename $loopdev)/dev) 0\";"
            "udevadm settle".format(path=self.img_path), user="root")

        dev_list = list(self.vm.devices['block'])
        found = False
        for dev in dev_list:
            if dev.ident.startswith('loop'):
                self.assertNotEquals(dev.description, self.img_path,
                    "Device {} ({}) should not be listed as it is used in "
                    "device-mapper".format(dev, self.img_path)
                )
            elif dev.description == 'test-dm':
                self.assertEquals(dev.mode, 'w')
                self.assertEquals(dev.size, 1024 * 1024 * 128)
                found = True

        if not found:
            self.fail("Device {} not found in {!r}".format('test-dm', dev_list))

    def test_013_list_dm_removed(self):
        if self.template is None:
            self.skipTest('test not supported in dom0 - loop devices excluded '
                          'in dom0')
        self.run_script(
            "set -e;"
            "truncate -s 128M {path}; "
            "loopdev=`losetup -f`; "
            "losetup $loopdev {path}; "
            "dmsetup create test-dm --table \"0 262144 linear $(cat "
            "/sys/block/$(basename $loopdev)/dev) 0\";"
            "udevadm settle;"
            "dmsetup remove test-dm;"
            "udevadm settle".format(path=self.img_path), user="root")

        dev_list = list(self.vm.devices['block'])
        found = False
        for dev in dev_list:
            if dev.description == self.img_path:
                self.assertTrue(dev.ident.startswith('loop'))
                self.assertEquals(dev.mode, 'w')
                self.assertEquals(dev.size, 1024 * 1024 * 128)
                found = True

        if not found:
            self.fail("Device {} not found in {!r}".format(self.img_path, dev_list))

    def test_020_list_loop_partition(self):
        if self.template is None:
            self.skipTest('loop devices excluded in dom0')
        self.run_script(
            "set -e;"
            "truncate -s 128M {path}; "
            "echo ,,L | sfdisk {path};"
            "loopdev=`losetup -f`; "
            "losetup -P $loopdev {path}; "
            "blockdev --rereadpt $loopdev; "
            "udevadm settle".format(path=self.img_path), user="root")

        dev_list = list(self.vm.devices['block'])
        found = False
        for dev in dev_list:
            if dev.description == self.img_path:
                self.assertTrue(dev.ident.startswith('loop'))
                self.assertEquals(dev.mode, 'w')
                self.assertEquals(dev.size, 1024 * 1024 * 128)
                self.assertIn(dev.ident + 'p1', [d.ident for d in dev_list])
                found = True

        if not found:
            self.fail("Device {} not found in {!r}".format(self.img_path, dev_list))

    def test_021_list_loop_partition_mounted(self):
        if self.template is None:
            self.skipTest('loop devices excluded in dom0')
        self.run_script(
            "set -e;"
            "truncate -s 128M {path}; "
            "echo ,,L | sfdisk {path};"
            "loopdev=`losetup -f`; "
            "losetup -P $loopdev {path}; "
            "blockdev --rereadpt $loopdev; "
            "mkfs.ext4 -q -F ${{loopdev}}p1; "
            "mkdir -p {mntdir}; "
            "mount ${{loopdev}}p1 {mntdir}; "
            "udevadm settle".format(
                path=self.img_path, mntdir=self.mount_point),
            user="root")

        dev_list = list(self.vm.devices['block'])
        for dev in dev_list:
            if dev.description == self.img_path:
                self.fail(
                    'Device {} ({}) should not be listed because its '
                    'partition is mounted'
                    .format(dev, self.img_path))
            elif dev.ident.startswith('loop') and dev.ident.endswith('p1'):
                # FIXME: risky assumption that only tests create partitioned
                # loop devices
                self.fail(
                    'Device {} ({}) should not be listed because is mounted'
                    .format(dev, self.img_path))


def create_testcases_for_templates():
    return vanir.tests.create_testcases_for_templates('TC_00_List',
        TC_00_List,
        module=sys.modules[__name__])

def load_tests(loader, tests, pattern):
    tests.addTests(loader.loadTestsFromNames(
        create_testcases_for_templates()))
    return tests

vanir.tests.maybe_create_testcases_on_import(create_testcases_for_templates)
