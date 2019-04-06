import vanir.devices

import vanir.tests

class TestDevice(vanir.devices.DeviceInfo):
    # pylint: disable=too-few-public-methods
    pass


class TestVMCollection(dict):
    def __iter__(self):
        return iter(set(self.values()))


class TestApp(object):
    # pylint: disable=too-few-public-methods
    def __init__(self):
        self.domains = TestVMCollection()


class TestVM(vanir.tests.TestEmitter):
    def __init__(self, app, name, *args, **kwargs):
        super(TestVM, self).__init__(*args, **kwargs)
        self.app = app
        self.name = name
        self.device = TestDevice(self, 'testdev', 'Description')
        self.events_enabled = True
        self.devices = {
            'testclass': vanir.devices.DeviceCollection(self, 'testclass')
        }
        self.app.domains[name] = self
        self.app.domains[self] = self
        self.running = False

    def __str__(self):
        return self.name

    @vanir.events.handler('device-list-attached:testclass')
    def dev_testclass_list_attached(self, event, persistent = False):
        for vm in self.app.domains:
            if vm.device.frontend_domain == self:
                yield (vm.device, {})

    @vanir.events.handler('device-list:testclass')
    def dev_testclass_list(self, event):
        yield self.device

    def is_halted(self):
        return not self.running

    def is_running(self):
        return self.running



class TC_00_DeviceCollection(vanir.tests.VanirTestCase):
    def setUp(self):
        super().setUp()
        self.app = TestApp()
        self.emitter = TestVM(self.app, 'vm')
        self.app.domains['vm'] = self.emitter
        self.device = self.emitter.device
        self.collection = self.emitter.devices['testclass']
        self.assignment = vanir.devices.DeviceAssignment(
            backend_domain=self.device.backend_domain,
            ident=self.device.ident,
            persistent=True
        )

    def test_000_init(self):
        self.assertFalse(self.collection._set)

    def test_001_attach(self):
        self.loop.run_until_complete(self.collection.attach(self.assignment))
        self.assertEventFired(self.emitter, 'device-pre-attach:testclass')
        self.assertEventFired(self.emitter, 'device-attach:testclass')
        self.assertEventNotFired(self.emitter, 'device-pre-detach:testclass')
        self.assertEventNotFired(self.emitter, 'device-detach:testclass')

    def test_002_detach(self):
        self.loop.run_until_complete(self.collection.attach(self.assignment))
        self.loop.run_until_complete(self.collection.detach(self.assignment))
        self.assertEventFired(self.emitter, 'device-pre-attach:testclass')
        self.assertEventFired(self.emitter, 'device-attach:testclass')
        self.assertEventFired(self.emitter, 'device-pre-detach:testclass')
        self.assertEventFired(self.emitter, 'device-detach:testclass')

    def test_010_empty_detach(self):
        with self.assertRaises(LookupError):
            self.loop.run_until_complete(
                self.collection.detach(self.assignment))

    def test_011_double_attach(self):
        self.loop.run_until_complete(self.collection.attach(self.assignment))

        with self.assertRaises(vanir.devices.DeviceAlreadyAttached):
            self.loop.run_until_complete(
                self.collection.attach(self.assignment))

    def test_012_double_detach(self):
        self.loop.run_until_complete(self.collection.attach(self.assignment))
        self.loop.run_until_complete(self.collection.detach(self.assignment))

        with self.assertRaises(vanir.devices.DeviceNotAttached):
            self.loop.run_until_complete(
                self.collection.detach(self.assignment))

    def test_013_list_attached_persistent(self):
        self.assertEqual(set([]), set(self.collection.persistent()))
        self.loop.run_until_complete(self.collection.attach(self.assignment))
        self.assertEventFired(self.emitter, 'device-list-attached:testclass')
        self.assertEqual({self.device}, set(self.collection.persistent()))
        self.assertEqual(set([]),
            set(self.collection.attached()))

    def test_014_list_attached_non_persistent(self):
        self.assignment.persistent = False
        self.emitter.running = True
        self.loop.run_until_complete(self.collection.attach(self.assignment))
        # device-attach event not implemented, so manipulate object manually
        self.device.frontend_domain = self.emitter
        self.assertEqual({self.device},
            set(self.collection.attached()))
        self.assertEqual(set([]),
            set(self.collection.persistent()))
        self.assertEqual({self.device},
            set(self.collection.attached()))
        self.assertEventFired(self.emitter, 'device-list-attached:testclass')

    def test_015_list_available(self):
        self.assertEqual({self.device}, set(self.collection))
        self.assertEventFired(self.emitter, 'device-list:testclass')

    def test_020_update_persistent_to_false(self):
        self.emitter.running = True
        self.assertEqual(set([]), set(self.collection.persistent()))
        self.loop.run_until_complete(self.collection.attach(self.assignment))
        # device-attach event not implemented, so manipulate object manually
        self.device.frontend_domain = self.emitter
        self.assertEqual({self.device}, set(self.collection.persistent()))
        self.assertEqual({self.device}, set(self.collection.attached()))
        self.assertEqual({self.device}, set(self.collection.persistent()))
        self.assertEqual({self.device}, set(self.collection.attached()))
        self.collection.update_persistent(self.device, False)
        self.assertEqual(set(), set(self.collection.persistent()))
        self.assertEqual({self.device}, set(self.collection.attached()))

    def test_021_update_persistent_to_true(self):
        self.assignment.persistent = False
        self.emitter.running = True
        self.assertEqual(set([]), set(self.collection.persistent()))
        self.loop.run_until_complete(self.collection.attach(self.assignment))
        # device-attach event not implemented, so manipulate object manually
        self.device.frontend_domain = self.emitter
        self.assertEqual(set(), set(self.collection.persistent()))
        self.assertEqual({self.device}, set(self.collection.attached()))
        self.assertEqual(set(), set(self.collection.persistent()))
        self.assertEqual({self.device}, set(self.collection.attached()))
        self.collection.update_persistent(self.device, True)
        self.assertEqual({self.device}, set(self.collection.persistent()))
        self.assertEqual({self.device}, set(self.collection.attached()))

    def test_022_update_persistent_reject_not_running(self):
        self.assertEqual(set([]), set(self.collection.persistent()))
        self.loop.run_until_complete(self.collection.attach(self.assignment))
        self.assertEqual({self.device}, set(self.collection.persistent()))
        self.assertEqual(set(), set(self.collection.attached()))
        with self.assertRaises(vanir.exc.QubesVMNotStartedError):
            self.collection.update_persistent(self.device, False)

    def test_023_update_persistent_reject_not_attached(self):
        self.assertEqual(set(), set(self.collection.persistent()))
        self.assertEqual(set(), set(self.collection.attached()))
        self.emitter.running = True
        with self.assertRaises(vanir.exc.QubesValueError):
            self.collection.update_persistent(self.device, True)
        with self.assertRaises(vanir.exc.QubesValueError):
            self.collection.update_persistent(self.device, False)


class TC_01_DeviceManager(vanir.tests.VanirTestCase):
    def setUp(self):
        super().setUp()
        self.app = TestApp()
        self.emitter = TestVM(self.app, 'vm')
        self.manager = vanir.devices.DeviceManager(self.emitter)

    def test_000_init(self):
        self.assertEqual(self.manager, {})

    def test_001_missing(self):
        device = TestDevice(self.emitter.app.domains['vm'], 'testdev')
        assignment = vanir.devices.DeviceAssignment(
            backend_domain=device.backend_domain,
            ident=device.ident,
            persistent=True)
        self.loop.run_until_complete(
            self.manager['testclass'].attach(assignment))
        self.assertEventFired(self.emitter, 'device-attach:testclass')

