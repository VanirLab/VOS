''' Tests for the kernels storage backend '''

import os
import shutil

import asyncio

import vanir.storage
import vanir.tests.storage
from vanir.config import defaults

# :pylint: disable=invalid-name


class TestApp(vanir.Vanir):
    ''' A Mock App object '''
    def __init__(self, *args, **kwargs):  # pylint: disable=unused-argument
        super(TestApp, self).__init__('/tmp/vanir-test.xml', load=False,
                                      offline_mode=True, **kwargs)
        self.load_initial_values()
        self.pools['linux-kernel'].dir_path = '/tmp/vanir-test-kernel'
        dummy_kernel = os.path.join(self.pools['linux-kernel'].dir_path,
                                    'dummy')
        os.makedirs(dummy_kernel)
        open(os.path.join(dummy_kernel, 'vmlinuz'), 'w').close()
        open(os.path.join(dummy_kernel, 'modules.img'), 'w').close()
        open(os.path.join(dummy_kernel, 'initramfs'), 'w').close()
        self.default_kernel = 'dummy'

    def cleanup(self):
        ''' Remove temporary directories '''
        shutil.rmtree(self.pools['linux-kernel'].dir_path)

    def create_dummy_template(self):
        ''' Initalizes a dummy TemplateVM as the `default_template` '''
        template = self.add_new_vm(vanir.vm.templatevm.TemplateVM,
                                   name='test-template', label='red',
                                   memory=1024, maxmem=1024)
        self.default_template = template




class TC_01_KernelVolumes(vanir.tests.VanirTestCase):
    ''' Test correct handling of different types of volumes '''

    POOL_DIR = '/tmp/test-pool'
    POOL_NAME = 'test-pool'
    POOL_CONF = {'driver': 'linux-kernel', 'dir_path': POOL_DIR, 'name':
        POOL_NAME}

    def setUp(self):
        """ Add a test file based storage pool """
        super(TC_01_KernelVolumes, self).setUp()
        self.app = TestApp()
        self.app.create_dummy_template()
        self.loop.run_until_complete(self.app.add_pool(**self.POOL_CONF))
        os.makedirs(self.POOL_DIR + '/dummy', exist_ok=True)
        open('/tmp/test-pool/dummy/modules.img', 'w').close()

    def tearDown(self):
        """ Remove the file based storage pool after testing """
        self.loop.run_until_complete(self.app.remove_pool("test-pool"))
        self.app.cleanup()
        self.app.close()
        del self.app
        super(TC_01_KernelVolumes, self).tearDown()
        shutil.rmtree(self.POOL_DIR, ignore_errors=True)

    def test_000_reject_rw(self):
        config = {
            'name': 'root',
            'pool': self.POOL_NAME,
            'save_on_stop': True,
            'rw': True,
        }
        vm = vanir.tests.storage.TestVM(self)
        vm.kernel = 'dummy'
        with self.assertRaises(AssertionError):
            self.app.get_pool(self.POOL_NAME).init_volume(vm, config)

    def test_001_simple_volume(self):
        config = {
            'name': 'kernel',
            'pool': self.POOL_NAME,
            'rw': False,
        }

        template_vm = self.app.default_template
        vm = vanir.tests.storage.TestVM(self, template=template_vm)
        vm.kernel = 'dummy'
        volume = self.app.get_pool(self.POOL_NAME).init_volume(vm, config)
        self.assertEqual(volume.name, 'kernel')
        self.assertEqual(volume.pool, self.POOL_NAME)
        self.assertFalse(volume.snap_on_start)
        self.assertFalse(volume.save_on_stop)
        self.assertFalse(volume.rw)
        self.assertEqual(volume.usage, 0)
        expected_path = '/tmp/test-pool/dummy/modules.img'
        self.assertEqual(volume.path, expected_path)
        block_dev = volume.block_device()
        self.assertIsInstance(block_dev, vanir.storage.BlockDevice)
        self.assertEqual(block_dev.devtype, 'disk')
        self.assertEqual(block_dev.path, expected_path)
        self.assertEqual(block_dev.name, 'kernel')

    def test_002_follow_kernel_change(self):
        config = {
            'name': 'kernel',
            'pool': self.POOL_NAME,
            'rw': False,
        }

        template_vm = self.app.default_template
        vm = vanir.tests.storage.TestVM(self, template=template_vm)
        vm.kernel = 'dummy'
        volume = self.app.get_pool(self.POOL_NAME).init_volume(vm, config)
        self.assertEqual(volume.name, 'kernel')
        self.assertEqual(volume.pool, self.POOL_NAME)
        self.assertEqual(volume.path, '/tmp/test-pool/dummy/modules.img')
        vm.kernel = 'updated'
        self.assertEqual(volume.path, '/tmp/test-pool/updated/modules.img')

    def test_003_kernel_none(self):
        config = {
            'name': 'kernel',
            'pool': self.POOL_NAME,
            'rw': False,
        }

        template_vm = self.app.default_template
        vm = vanir.tests.storage.TestVM(self, template=template_vm)
        vm.kernel = None
        volume = self.app.get_pool(self.POOL_NAME).init_volume(vm, config)
        self.assertEqual(volume.name, 'kernel')
        self.assertEqual(volume.pool, self.POOL_NAME)
        self.assertFalse(volume.snap_on_start)
        self.assertFalse(volume.save_on_stop)
        self.assertFalse(volume.rw)
        self.assertEqual(volume.usage, 0)
        self.assertIsNone(volume.path)
        self.assertIsNone(volume.vid)
        block_dev = volume.block_device()
        self.assertIsNone(block_dev)

    def test_004_kernel_none_change(self):
        config = {
            'name': 'kernel',
            'pool': self.POOL_NAME,
            'rw': False,
        }

        template_vm = self.app.default_template
        vm = vanir.tests.storage.TestVM(self, template=template_vm)
        vm.kernel = None
        volume = self.app.get_pool(self.POOL_NAME).init_volume(vm, config)
        self.assertIsNone(volume.path)
        self.assertIsNone(volume.vid)
        block_dev = volume.block_device()
        self.assertIsNone(block_dev)
        vm.kernel = 'dummy'
        expected_path = '/tmp/test-pool/dummy/modules.img'
        self.assertEqual(volume.path, expected_path)
        block_dev = volume.block_device()
        self.assertIsInstance(block_dev, vanir.storage.BlockDevice)
        self.assertEqual(block_dev.devtype, 'disk')
        self.assertEqual(block_dev.path, expected_path)
        self.assertEqual(block_dev.name, 'kernel')

    def test_005_kernel_none_change(self):
        config = {
            'name': 'kernel',
            'pool': self.POOL_NAME,
            'rw': False,
        }

        template_vm = self.app.default_template
        vm = vanir.tests.storage.TestVM(self, template=template_vm)
        vm.kernel = 'dummy'
        volume = self.app.get_pool(self.POOL_NAME).init_volume(vm, config)
        expected_path = '/tmp/test-pool/dummy/modules.img'
        self.assertEqual(volume.path, expected_path)
        block_dev = volume.block_device()
        self.assertIsInstance(block_dev, vanir.storage.BlockDevice)
        self.assertEqual(block_dev.devtype, 'disk')
        self.assertEqual(block_dev.path, expected_path)
        self.assertEqual(block_dev.name, 'kernel')
        vm.kernel = None
        self.assertIsNone(volume.path)
        self.assertIsNone(volume.vid)
        block_dev = volume.block_device()
        self.assertIsNone(block_dev)


class TC_03_KernelPool(vanir.tests.VanirTestCase):
    """ Test the paths for the default file based pool (``FilePool``).
    """

    POOL_DIR = '/tmp/test-pool'
    POOL_NAME = 'test-pool'
    POOL_CONFIG = {'driver': 'linux-kernel', 'dir_path': POOL_DIR, 'name':
        POOL_NAME}

    def setUp(self):
        """ Add a test file based storage pool """
        super(TC_03_KernelPool, self).setUp()
        self.app = TestApp()
        self.app.create_dummy_template()
        dummy_kernel = os.path.join(self.POOL_DIR, 'dummy')
        os.makedirs(dummy_kernel)
        open(os.path.join(dummy_kernel, 'vmlinuz'), 'w').close()
        open(os.path.join(dummy_kernel, 'modules.img'), 'w').close()
        open(os.path.join(dummy_kernel, 'initramfs'), 'w').close()
        self.loop.run_until_complete(self.app.add_pool(**self.POOL_CONFIG))

    def tearDown(self):
        """ Remove the file based storage pool after testing """
        self.loop.run_until_complete(self.app.remove_pool("test-pool"))
        self.app.cleanup()
        self.app.close()
        del self.app
        super(TC_03_KernelPool, self).tearDown()
        shutil.rmtree(self.POOL_DIR, ignore_errors=True)
        if os.path.exists('/tmp/vanir-test'):
            shutil.rmtree('/tmp/vanir-test')

    def test_001_pool_exists(self):
        """ Check if the storage pool was added to the storage pool config """
        self.assertIn('test-pool', self.app.pools.keys())

    def test_002_pool_volumes(self):
        """ List volumes """
        volumes = self.app.pools[self.POOL_NAME].volumes
        self.assertEqual(len(volumes), 1)
        vol = volumes[0]
        self.assertEqual(vol.vid, 'dummy')
        self.assertEqual(vol.path, '/tmp/test-pool/dummy/modules.img')
