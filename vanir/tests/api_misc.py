import asyncio
from unittest import mock
import vanir.tests
import vanir.api.misc


class TC_00_API_Misc(vanir.tests.VanirTestCase):
    def setUp(self):
        super(TC_00_API_Misc, self).setUp()
        self.tpl = mock.NonCallableMagicMock(name='template')
        del self.tpl.template
        self.src = mock.NonCallableMagicMock(name='appvm',
            template=self.tpl)
        self.app = mock.NonCallableMock()
        self.dest = mock.NonCallableMock()
        self.dest.name = 'dom0'
        self.app.configure_mock(domains={
            'dom0': self.dest,
            'test-vm': self.src,
        })

    def configure_qdb(self, entries):
        self.src.configure_mock(**{
            'untrusted_qdb.read.side_effect': (
                lambda path: entries.get(path, None)),
            'untrusted_qdb.list.side_effect': (
                lambda path: sorted(entries.keys())),
        })

    def call_mgmt_func(self, method, arg=b'', payload=b''):
        mgmt_obj = vanir.api.misc.QubesMiscAPI(self.app,
            b'test-vm', method, b'dom0', arg)

        loop = asyncio.get_event_loop()
        response = loop.run_until_complete(
            mgmt_obj.execute(untrusted_payload=payload))
        return response

    def test_000_features_request(self):
        qdb_entries = {
            '/features-request/feature1': b'1',
            '/features-request/feature2': b'',
            '/features-request/feature3': b'other',
        }
        self.configure_qdb(qdb_entries)
        response = self.call_mgmt_func(b'vanir.FeaturesRequest')
        self.assertIsNone(response)
        self.assertEqual(self.app.mock_calls, [
            mock.call.save()
        ])
        self.assertEqual(self.src.mock_calls, [
            mock.call.untrusted_qdb.list('/features-request/'),
            mock.call.untrusted_qdb.read('/features-request/feature1'),
            mock.call.untrusted_qdb.read('/features-request/feature2'),
            mock.call.untrusted_qdb.read('/features-request/feature3'),
            mock.call.fire_event_async('features-request', untrusted_features={
                'feature1': '1', 'feature2': '', 'feature3': 'other'}),
            ('fire_event_async().__iter__', (), {}),
        ])

    def test_001_features_request_empty(self):
        self.configure_qdb({})
        response = self.call_mgmt_func(b'vanir.FeaturesRequest')
        self.assertIsNone(response)
        self.assertEqual(self.app.mock_calls, [
            mock.call.save()
        ])
        self.assertEqual(self.src.mock_calls, [
            mock.call.untrusted_qdb.list('/features-request/'),
            mock.call.fire_event_async('features-request',
                untrusted_features={}),
            ('fire_event_async().__iter__', (), {}),
        ])

    def test_002_features_request_invalid1(self):
        qdb_entries = {
            '/features-request/feature1': b'test spaces',
        }
        self.configure_qdb(qdb_entries)
        with self.assertRaises(vanir.api.PermissionDenied):
            self.call_mgmt_func(b'vanir.FeaturesRequest')
        self.assertEqual(self.app.mock_calls, [])
        self.assertEqual(self.src.mock_calls, [
            mock.call.untrusted_qdb.list('/features-request/'),
            mock.call.untrusted_qdb.read('/features-request/feature1'),
        ])

    def test_003_features_request_invalid2(self):
        qdb_entries = {
            '/features-request/feature1': b'\xfe\x01',
        }
        self.configure_qdb(qdb_entries)
        with self.assertRaises(UnicodeDecodeError):
            self.call_mgmt_func(b'vanir.FeaturesRequest')
        self.assertEqual(self.app.mock_calls, [])
        self.assertEqual(self.src.mock_calls, [
            mock.call.untrusted_qdb.list('/features-request/'),
            mock.call.untrusted_qdb.read('/features-request/feature1'),
        ])

    def test_010_notify_tools(self):
        qdb_entries = {
            '/vanir-tools/version': b'1',
            '/vanir-tools/qrexec': b'1',
            '/vanir-tools/gui': b'1',
            '/vanir-tools/os': b'Linux',
            '/vanir-tools/default-user': b'user',
        }
        self.configure_qdb(qdb_entries)
        response = self.call_mgmt_func(b'vanir.NotifyTools')
        self.assertIsNone(response)
        self.assertEqual(self.app.mock_calls, [
            mock.call.save()
        ])
        self.assertEqual(self.src.mock_calls, [
            mock.call.untrusted_qdb.read('/vanir-tools/qrexec'),
            mock.call.untrusted_qdb.read('/vanir-tools/gui'),
            mock.call.untrusted_qdb.read('/vanir-tools/gui-emulated'),
            mock.call.untrusted_qdb.read('/vanir-tools/default-user'),
            mock.call.untrusted_qdb.read('/vanir-tools/os'),
            mock.call.fire_event_async('features-request', untrusted_features={
                'gui': '1',
                'default-user': 'user',
                'qrexec': '1',
                'os': 'Linux'}),
            ('fire_event_async().__iter__', (), {}),
        ])
        self.assertEqual(self.app.mock_calls, [mock.call.save()])

    def test_013_notify_tools_no_version(self):
        qdb_entries = {
            '/vanir-tools/qrexec': b'1',
            '/vanir-tools/gui': b'1',
            '/vanir-tools/os': b'Linux',
            '/vanir-tools/default-user': b'user',
        }
        self.configure_qdb(qdb_entries)
        response = self.call_mgmt_func(b'vanir.NotifyTools')
        self.assertIsNone(response)
        self.assertEqual(self.src.mock_calls, [
            mock.call.untrusted_qdb.read('/vanir-tools/qrexec'),
            mock.call.untrusted_qdb.read('/vanir-tools/gui'),
            mock.call.untrusted_qdb.read('/vanir-tools/gui-emulated'),
            mock.call.untrusted_qdb.read('/vanir-tools/default-user'),
            mock.call.untrusted_qdb.read('/vanir-tools/os'),
            mock.call.fire_event_async('features-request', untrusted_features={
                'gui': '1',
                'default-user': 'user',
                'qrexec': '1',
                'os': 'Linux'}),
            ('fire_event_async().__iter__', (), {}),
        ])
        self.assertEqual(self.app.mock_calls, [mock.call.save()])

    def test_015_notify_tools_invalid_value_qrexec(self):
        qdb_entries = {
            '/vanir-tools/version': b'1',
            '/vanir-tools/qrexec': b'invalid value',
            '/vanir-tools/gui': b'0',
            '/vanir-tools/os': b'Linux',
            '/vanir-tools/default-user': b'user',
        }
        self.configure_qdb(qdb_entries)
        with self.assertRaises(vanir.api.PermissionDenied):
            self.call_mgmt_func(b'vanir.NotifyTools')
        self.assertEqual(self.app.mock_calls, [])
        self.assertEqual(self.src.mock_calls, [
            mock.call.untrusted_qdb.read('/vanir-tools/qrexec'),
        ])

    def test_016_notify_tools_invalid_value_gui(self):
        qdb_entries = {
            '/vanir-tools/version': b'1',
            '/vanir-tools/qrexec': b'1',
            '/vanir-tools/gui': b'invalid value',
            '/vanir-tools/os': b'Linux',
            '/vanir-tools/default-user': b'user',
        }
        self.configure_qdb(qdb_entries)
        with self.assertRaises(vanir.api.PermissionDenied):
            self.call_mgmt_func(b'vanir.NotifyTools')
        self.assertEqual(self.app.mock_calls, [])
        self.assertEqual(self.src.mock_calls, [
            mock.call.untrusted_qdb.read('/vanir-tools/qrexec'),
            mock.call.untrusted_qdb.read('/vanir-tools/gui'),
        ])

    def test_020_notify_updates_standalone(self):
        del self.src.template
        response = self.call_mgmt_func(b'vanir.NotifyUpdates', payload=b'1\n')
        self.assertIsNone(response)
        self.assertEqual(self.src.mock_calls, [
            mock.call.updateable.__bool__(),
            mock.call.features.__setitem__('updates-available', True),
        ])
        self.assertEqual(self.app.mock_calls, [mock.call.save()])

    def test_021_notify_updates_standalone2(self):
        del self.src.template
        response = self.call_mgmt_func(b'vanir.NotifyUpdates', payload=b'0\n')
        self.assertIsNone(response)
        self.assertEqual(self.src.mock_calls, [
            mock.call.updateable.__bool__(),
            mock.call.features.__setitem__('updates-available', False),
        ])
        self.assertEqual(self.app.mock_calls, [
            mock.call.save()
        ])

    def test_022_notify_updates_invalid(self):
        del self.src.template
        with self.assertRaises(vanir.api.PermissionDenied):
            self.call_mgmt_func(b'vanir.NotifyUpdates', payload=b'')
        self.assertEqual(self.src.mock_calls, [])
        self.assertEqual(self.tpl.mock_calls, [])
        self.assertEqual(self.app.mock_calls, [])

    def test_023_notify_updates_invalid2(self):
        del self.src.template
        with self.assertRaises(vanir.api.PermissionDenied):
            self.call_mgmt_func(b'vanir.NotifyUpdates', payload=b'no updates')
        self.assertEqual(self.src.mock_calls, [])
        self.assertEqual(self.tpl.mock_calls, [])
        self.assertEqual(self.app.mock_calls, [])

    def test_024_notify_updates_template_based_no_updates(self):
        '''No updates on template-based VM, should not reset state'''
        self.src.updateable = False
        self.src.template.is_running.return_value = False
        response = self.call_mgmt_func(b'vanir.NotifyUpdates', payload=b'0\n')
        self.assertIsNone(response)
        self.assertEqual(self.tpl.mock_calls, [
            mock.call.updateable.__bool__(),
            mock.call.is_running(),
        ])
        self.assertEqual(self.app.mock_calls, [])

    def test_025_notify_updates_template_based(self):
        '''Some updates on template-based VM, should save flag'''
        self.src.updateable = False
        self.tpl.is_running.return_value = False
        self.src.storage.outdated_volumes = []
        response = self.call_mgmt_func(b'vanir.NotifyUpdates', payload=b'1\n')
        self.assertIsNone(response)
        self.assertEqual(self.src.mock_calls, [])
        self.assertEqual(self.tpl.mock_calls, [
            mock.call.updateable.__bool__(),
            mock.call.is_running(),
            mock.call.features.__setitem__('updates-available', True),
        ])
        self.assertEqual(self.app.mock_calls, [
            mock.call.save()
        ])

    def test_026_notify_updates_template_based_outdated(self):
        self.src.updateable = False
        self.src.template.is_running.return_value = False
        self.src.storage.outdated_volumes = ['root']
        response = self.call_mgmt_func(b'vanir.NotifyUpdates', payload=b'1\n')
        self.assertIsNone(response)
        self.assertEqual(self.src.mock_calls, [])
        self.assertEqual(self.tpl.mock_calls, [
            mock.call.updateable.__bool__(),
            mock.call.is_running(),
        ])
        self.assertIsInstance(self.tpl.updates_available, mock.Mock)
        self.assertEqual(self.app.mock_calls, [])

    def test_027_notify_updates_template_based_template_running(self):
        self.src.updateable = False
        self.src.template.is_running.return_value = True
        self.src.storage.outdated_volumes = []
        response = self.call_mgmt_func(b'vanir.NotifyUpdates', payload=b'1\n')
        self.assertIsNone(response)
        self.assertEqual(self.src.mock_calls, [])
        self.assertEqual(self.tpl.mock_calls, [
            mock.call.updateable.__bool__(),
            mock.call.is_running(),
        ])
        self.assertIsInstance(self.src.updates_available, mock.Mock)
        self.assertEqual(self.app.mock_calls, [])

    def test_028_notify_updates_template_based_dispvm(self):
        self.dvm = self.src
        self.dvm.updateable = False
        self.srv = mock.NonCallableMagicMock(template=self.dvm)
        self.src.updateable = False
        self.src.template.is_running.return_value = False
        self.src.storage.outdated_volumes = []
        response = self.call_mgmt_func(b'vanir.NotifyUpdates', payload=b'1\n')
        self.assertIsNone(response)
        self.assertEqual(self.src.mock_calls, [])
        self.assertEqual(self.dvm.mock_calls, [])
        self.assertEqual(self.tpl.mock_calls, [
            mock.call.updateable.__bool__(),
            mock.call.is_running(),
            mock.call.features.__setitem__('updates-available', True),
        ])
        self.assertIsInstance(self.src.updates_available, mock.Mock)
        self.assertEqual(self.app.mock_calls, [
            mock.call.save()
        ])