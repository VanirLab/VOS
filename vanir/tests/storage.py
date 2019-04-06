import shutil
import unittest.mock
import vanir.log
import vanir.storage
from vanir.exc import VanirException
from vanir.storage import pool_drivers
from vanir.storage.file import FilePool
from vanir.storage.reflink import ReflinkPool
from vanir.tests import SystemTestCase, VanirTestCase

# :pylint: disable=invalid-name


class TestPool(unittest.mock.Mock):
    def __init__(self, *args, **kwargs):
        super(TestPool, self).__init__(*args, spec=vanir.storage.Pool, **kwargs)
        try:
            self.name = kwargs['name']
        except KeyError:
            pass

    def __str__(self):
        return 'test'

    def init_volume(self, vm, volume_config):
        vol = unittest.mock.Mock(spec=vanir.storage.Volume)
        vol.configure_mock(**volume_config)
        vol.pool = self
        vol.import_data.return_value = '/tmp/test-' + vm.name
        return vol


class TestVM(object):
    def __init__(self, test, template=None):
        self.app = test.app
        self.name = test.make_vm_name('appvm')
        self.dir_path = '/var/lib/vanir/appvms/' + self.name
        self.log = vanir.log.get_vm_logger(self.name)

        if template:
            self.template = template

    def is_template(self):
        # :pylint: disable=no-self-use
        return False

    def is_disposablevm(self):
        # :pylint: disable=no-self-use
        return False


class TestTemplateVM(TestVM):
    dir_path_prefix = vanir.config.system_path['vanir_templates_dir']

    def __init__(self, test, template=None):
        super(TestTemplateVM, self).__init__(test, template)
        self.dir_path = '/var/lib/vanir/vm-templates/' + self.name

    def is_template(self):
        return True


class TestDisposableVM(TestVM):
    def is_disposablevm(self):
        return True

class TestApp(vanir.Qubes):
    def __init__(self, *args, **kwargs):  # pylint: disable=unused-argument
        super(TestApp, self).__init__('/tmp/vanir-test.xml',
            load=False, offline_mode=True, **kwargs)
        self.load_initial_values()
        self.default_pool = self.pools['varlibqubes']

class TC_00_Pool(VanirTestCase):
    """ This class tests the utility methods from :mod:``vanir.storage`` """

    def setUp(self):
        super(TC_00_Pool, self).setUp()
        self.basedir_patch = unittest.mock.patch('vanir.config.vanir_base_dir',
            '/tmp/vanir-test-basedir')
        self.basedir_patch.start()
        self.app = TestApp()

    def tearDown(self):
        self.basedir_patch.stop()
        self.app.close()
        del self.app
        shutil.rmtree('/tmp/vanir-test-basedir', ignore_errors=True)
        super().tearDown()

    def test_000_unknown_pool_driver(self):
        # :pylint: disable=protected-access
        """ Expect an exception when unknown pool is requested"""
        with self.assertRaises(VanirException):
            self.app.get_pool('foo-bar')

    def test_001_all_pool_drivers(self):
        """ Expect all our pool drivers (and only them) """
        self.assertCountEqual(
            ['linux-kernel', 'lvm_thin', 'file', 'file-reflink'],
            pool_drivers())

    def test_002_get_pool_klass(self):
        """ Expect the default pool to be `FilePool` or `ReflinkPool` """
        # :pylint: disable=protected-access
        result = self.app.get_pool('varlibqubes')
        self.assertTrue(isinstance(result, FilePool)
                        or isinstance(result, ReflinkPool))

    def test_003_pool_exists_default(self):
        """ Expect the default pool to exists """
        self.assertPoolExists('varlibqubes')

    def test_004_add_remove_pool(self):
        """ Tries to adding and removing a pool. """
        pool_name = 'asdjhrp89132'

        # make sure it's really does not exist
        self.loop.run_until_complete(self.app.remove_pool(pool_name))
        self.assertFalse(self.assertPoolExists(pool_name))

        self.loop.run_until_complete(
            self.app.add_pool(name=pool_name,
                          driver='file',
                          dir_path='/tmp/asdjhrp89132'))
        self.assertTrue(self.assertPoolExists(pool_name))

        self.loop.run_until_complete(self.app.remove_pool(pool_name))
        self.assertFalse(self.assertPoolExists(pool_name))

    def assertPoolExists(self, pool):
        """ Check if specified pool exists """
        return pool in self.app.pools.keys()

    def test_005_remove_used(self):
        pool_name = 'test-pool-asdf'

        dir_path = '/tmp/{}'.format(pool_name)
        pool = self.loop.run_until_complete(
            self.app.add_pool(name=pool_name,
                driver='file',
                dir_path=dir_path))
        self.addCleanup(shutil.rmtree, dir_path)
        vm = self.app.add_new_vm('StandaloneVM', label='red',
            name=self.make_vm_name('vm'))
        self.loop.run_until_complete(vm.create_on_disk(pool=pool))
        with self.assertRaises(vanir.exc.VanirPoolInUseError):
            self.loop.run_until_complete(self.app.remove_pool(pool_name))
