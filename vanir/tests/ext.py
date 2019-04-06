from unittest import mock

import vanir.ext.core_features
import vanir.ext.services
import vanir.ext.windows
import vanir.tests


class TC_00_CoreFeatures(vanir.tests.VanirTestCase):
    def setUp(self):
        super().setUp()
        self.ext = vanir.ext.core_features.CoreFeatures()
        self.vm = mock.MagicMock()
        self.features = {}
        self.vm.configure_mock(**{
            'features.get.side_effect': self.features.get,
            'features.__contains__.side_effect': self.features.__contains__,
            'features.__setitem__.side_effect': self.features.__setitem__,
            })

    def test_010_notify_tools(self):
        del self.vm.template
        self.loop.run_until_complete(
            self.ext.vanir_features_request(self.vm, 'features-request',
                untrusted_features={
                    'gui': '1',
                    'version': '1',
                    'default-user': 'user',
                    'qrexec': '1'}))
        self.assertEqual(self.vm.mock_calls, [
            ('features.get', ('qrexec', False), {}),
            ('features.__contains__', ('qrexec',), {}),
            ('features.__setitem__', ('qrexec', True), {}),
            ('features.__contains__', ('gui',), {}),
            ('features.__setitem__', ('gui', True), {}),
            ('features.get', ('qrexec', False), {}),
            ('fire_event_async', ('template-postinstall',), {}),
            ('fire_event_async().__iter__', (), {}),
        ])

    def test_011_notify_tools_uninstall(self):
        del self.vm.template
        self.loop.run_until_complete(
            self.ext.vanir_features_request(self.vm, 'features-request',
                untrusted_features={
                    'gui': '0',
                    'version': '1',
                    'default-user': 'user',
                    'qrexec': '0'}))
        self.assertEqual(self.vm.mock_calls, [
            ('features.get', ('qrexec', False), {}),
            ('features.__contains__', ('qrexec',), {}),
            ('features.__setitem__', ('qrexec', False), {}),
            ('features.__contains__', ('gui',), {}),
            ('features.__setitem__', ('gui', False), {}),
            ('features.get', ('qrexec', False), {}),
        ])

    def test_012_notify_tools_uninstall2(self):
        del self.vm.template
        self.loop.run_until_complete(
            self.ext.vanir_features_request(self.vm, 'features-request',
                untrusted_features={
                    'version': '1',
                    'default-user': 'user',
                }))
        self.assertEqual(self.vm.mock_calls, [
            ('features.get', ('qrexec', False), {}),
            ('features.get', ('qrexec', False), {}),
        ])

    def test_013_notify_tools_no_version(self):
        del self.vm.template
        self.loop.run_until_complete(
            self.ext.vanir_features_request(self.vm, 'features-request',
                untrusted_features={
                    'qrexec': '1',
                    'gui': '1',
                    'default-user': 'user',
                }))
        self.assertEqual(self.vm.mock_calls, [
            ('features.get', ('qrexec', False), {}),
            ('features.__contains__', ('qrexec',), {}),
            ('features.__setitem__', ('qrexec', True), {}),
            ('features.__contains__', ('gui',), {}),
            ('features.__setitem__', ('gui', True), {}),
            ('features.get', ('qrexec', False), {}),
            ('fire_event_async', ('template-postinstall',), {}),
            ('fire_event_async().__iter__', (), {}),
        ])

    def test_015_notify_tools_invalid_value_qrexec(self):
        del self.vm.template
        self.loop.run_until_complete(
            self.ext.vanir_features_request(self.vm, 'features-request',
                untrusted_features={
                    'version': '1',
                    'qrexec': 'invalid',
                    'gui': '1',
                    'default-user': 'user',
                }))
        self.assertEqual(self.vm.mock_calls, [
            ('features.get', ('qrexec', False), {}),
            ('features.__contains__', ('gui',), {}),
            ('features.__setitem__', ('gui', True), {}),
            ('features.get', ('qrexec', False), {}),
        ])

    def test_016_notify_tools_invalid_value_gui(self):
        del self.vm.template
        self.loop.run_until_complete(
            self.ext.vanir_features_request(self.vm, 'features-request',
                untrusted_features={
                    'version': '1',
                    'qrexec': '1',
                    'gui': 'invalid',
                    'default-user': 'user',
                }))
        self.assertEqual(self.vm.mock_calls, [
            ('features.get', ('qrexec', False), {}),
            ('features.__contains__', ('qrexec',), {}),
            ('features.__setitem__', ('qrexec', True), {}),
            ('features.get', ('qrexec', False), {}),
            ('fire_event_async', ('template-postinstall',), {}),
            ('fire_event_async().__iter__', (), {}),
        ])

    def test_017_notify_tools_template_based(self):
        self.loop.run_until_complete(
            self.ext.vanir_features_request(self.vm, 'features-request',
                untrusted_features={
                    'version': '1',
                    'qrexec': '1',
                    'gui': '1',
                    'default-user': 'user',
                }))
        self.assertEqual(self.vm.mock_calls, [
            ('template.__bool__', (), {}),
            ('log.warning', ('Ignoring vanir.NotifyTools for template-based '
                             'VM',), {})
        ])

    def test_018_notify_tools_already_installed(self):
        self.features['qrexec'] = True
        self.features['gui'] = True
        del self.vm.template
        self.loop.run_until_complete(
            self.ext.vanir_features_request(self.vm, 'features-request',
                untrusted_features={
                    'gui': '1',
                    'version': '1',
                    'default-user': 'user',
                    'qrexec': '1'}))
        self.assertEqual(self.vm.mock_calls, [
            ('features.get', ('qrexec', False), {}),
            ('features.__contains__', ('qrexec',), {}),
            ('features.__contains__', ('gui',), {}),
        ])

class TC_10_WindowsFeatures(vanir.tests.VanirTestCase):
    def setUp(self):
        super().setUp()
        self.ext = vanir.ext.windows.WindowsFeatures()
        self.vm = mock.MagicMock()
        self.features = {}
        self.vm.configure_mock(**{
            'features.get.side_effect': self.features.get,
            'features.__contains__.side_effect': self.features.__contains__,
            'features.__setitem__.side_effect': self.features.__setitem__,
            })

    def test_000_notify_tools_full(self):
        del self.vm.template
        self.ext.vanir_features_request(self.vm, 'features-request',
            untrusted_features={
                'gui': '1',
                'version': '1',
                'default-user': 'user',
                'qrexec': '1',
                'os': 'Windows'})
        self.assertEqual(self.vm.mock_calls, [
            ('features.__setitem__', ('os', 'Windows'), {}),
            ('features.__setitem__', ('rpc-clipboard', True), {}),
        ])

    def test_001_notify_tools_no_qrexec(self):
        del self.vm.template
        self.ext.vanir_features_request(self.vm, 'features-request',
            untrusted_features={
                'gui': '1',
                'version': '1',
                'default-user': 'user',
                'qrexec': '0',
                'os': 'Windows'})
        self.assertEqual(self.vm.mock_calls, [
            ('features.__setitem__', ('os', 'Windows'), {}),
        ])

    def test_002_notify_tools_other_os(self):
        del self.vm.template
        self.ext.vanir_features_request(self.vm, 'features-request',
            untrusted_features={
                'gui': '1',
                'version': '1',
                'default-user': 'user',
                'qrexec': '1',
                'os': 'other'})
        self.assertEqual(self.vm.mock_calls, [])

class TC_20_Services(vanir.tests.VanirTestCase):
    def setUp(self):
        super().setUp()
        self.ext = vanir.ext.services.ServicesExtension()
        self.vm = mock.MagicMock()
        self.features = {}
        self.vm.configure_mock(**{
            'template': None,
            'maxmem': 1024,
            'is_running.return_value': True,
            'features.get.side_effect': self.features.get,
            'features.items.side_effect': self.features.items,
            'features.__iter__.side_effect': self.features.__iter__,
            'features.__contains__.side_effect': self.features.__contains__,
            'features.__setitem__.side_effect': self.features.__setitem__,
            'features.__delitem__.side_effect': self.features.__delitem__,
            })

    def test_000_write_to_qdb(self):
        self.features['service.test1'] = '1'
        self.features['service.test2'] = ''

        self.ext.on_domain_qdb_create(self.vm, 'domain-qdb-create')
        self.assertEqual(sorted(self.vm.untrusted_qdb.mock_calls), [
            ('write', ('/vanir-service/meminfo-writer', '1'), {}),
            ('write', ('/vanir-service/test1', '1'), {}),
            ('write', ('/vanir-service/test2', '0'), {}),
        ])

    def test_001_feature_set(self):
        self.ext.on_domain_feature_set(self.vm,
            'feature-set:service.test_no_oldvalue',
            'service.test_no_oldvalue', '1')
        self.ext.on_domain_feature_set(self.vm,
            'feature-set:service.test_oldvalue',
            'service.test_oldvalue', '1', '')
        self.ext.on_domain_feature_set(self.vm,
            'feature-set:service.test_disable',
            'service.test_disable', '', '1')
        self.ext.on_domain_feature_set(self.vm,
            'feature-set:service.test_disable_no_oldvalue',
            'service.test_disable_no_oldvalue', '')

        self.assertEqual(sorted(self.vm.untrusted_qdb.mock_calls), sorted([
            ('write', ('/vanir-service/test_no_oldvalue', '1'), {}),
            ('write', ('/vanir-service/test_oldvalue', '1'), {}),
            ('write', ('/vanir-service/test_disable', '0'), {}),
            ('write', ('/vanir-service/test_disable_no_oldvalue', '0'), {}),
        ]))

    def test_002_feature_delete(self):
        self.ext.on_domain_feature_delete(self.vm,
            'feature-delete:service.test3', 'service.test3')
        self.assertEqual(sorted(self.vm.untrusted_qdb.mock_calls), [
            ('rm', ('/vanir-service/test3',), {}),
        ])

    def test_010_supported_services(self):
        self.ext.supported_services(self.vm, 'features-request',
            untrusted_features={
                'supported-service.test1': '1',  # ok
                'supported-service.test2': '0',  # ignored
                'supported-service.test3': 'some text',  # ignored
                'no-service': '1',  # ignored
            })
        self.assertEqual(self.features, {
            'supported-service.test1': True,
        })

    def test_011_supported_services_add(self):
        self.features['supported-service.test1'] = '1'
        self.ext.supported_services(self.vm, 'features-request',
            untrusted_features={
                'supported-service.test1': '1',  # ok
                'supported-service.test2': '1',  # ok
            })
        # also check if existing one is untouched
        self.assertEqual(self.features, {
            'supported-service.test1': '1',
            'supported-service.test2': True,
        })

    def test_012_supported_services_remove(self):
        self.features['supported-service.test1'] = '1'
        self.ext.supported_services(self.vm, 'features-request',
            untrusted_features={
                'supported-service.test2': '1',  # ok
            })
        self.assertEqual(self.features, {
            'supported-service.test2': True,
        })
