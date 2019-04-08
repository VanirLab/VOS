import asyncio
import vanir.api.internal
import vanir.tests
import vanir.vm.adminvm
from unittest import mock

def mock_coro(f):
    @asyncio.coroutine
    def coro_f(*args, **kwargs):
        return f(*args, **kwargs)

    return coro_f

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

    def create_mockvm(self, features=None):
        if features is None:
            features = {}
        vm = mock.Mock()
        vm.features.check_with_template.side_effect = features.get
        vm.run_service.return_value.wait = mock_coro(
            vm.run_service.return_value.wait)
        vm.run_service = mock_coro(vm.run_service)
        vm.suspend = mock_coro(vm.suspend)
        vm.resume = mock_coro(vm.resume)
        return vm

    def call_mgmt_func(self, method, arg=b'', payload=b''):
        mgmt_obj = vanir.api.internal.VanirInternalAPI(self.app,
            b'dom0', method, b'dom0', arg)

        loop = asyncio.get_event_loop()
        response = loop.run_until_complete(
            mgmt_obj.execute(untrusted_payload=payload))
        return response

    def test_000_suspend_pre(self):
        dom0 = mock.NonCallableMock(spec=vanir.vm.adminvm.AdminVM)

        running_vm = self.create_mockvm(features={'qrexec': True})
        running_vm.is_running.return_value = True

        not_running_vm = self.create_mockvm(features={'qrexec': True})
        not_running_vm.is_running.return_value = False

        no_qrexec_vm = self.create_mockvm()
        no_qrexec_vm.is_running.return_value = True

        domains_dict = {
            'dom0': dom0,
            'running': running_vm,
            'not-running': not_running_vm,
            'no-qrexec': no_qrexec_vm,
        }
        self.addCleanup(domains_dict.clear)
        self.app.domains = mock.MagicMock(**{
            '__iter__': lambda _: iter(domains_dict.values()),
            '__getitem__': domains_dict.get,
        })

        ret = self.call_mgmt_func(b'internal.SuspendPre')
        self.assertIsNone(ret)
        self.assertFalse(dom0.called)

        self.assertNotIn(('run_service', ('vanir.SuspendPreAll',), mock.ANY),
            not_running_vm.mock_calls)
        self.assertNotIn(('suspend', (), {}),
            not_running_vm.mock_calls)

        self.assertIn(('run_service', ('vanir.SuspendPreAll',), mock.ANY),
            running_vm.mock_calls)
        self.assertIn(('suspend', (), {}),
            running_vm.mock_calls)

        self.assertNotIn(('run_service', ('vanir.SuspendPreAll',), mock.ANY),
            no_qrexec_vm.mock_calls)
        self.assertIn(('suspend', (), {}),
            no_qrexec_vm.mock_calls)

    def test_001_suspend_post(self):
        dom0 = mock.NonCallableMock(spec=vanir.vm.adminvm.AdminVM)

        running_vm = self.create_mockvm(features={'qrexec': True})
        running_vm.is_running.return_value = True
        running_vm.get_power_state.return_value = 'Suspended'

        not_running_vm = self.create_mockvm(features={'qrexec': True})
        not_running_vm.is_running.return_value = False
        not_running_vm.get_power_state.return_value = 'Halted'

        no_qrexec_vm = self.create_mockvm()
        no_qrexec_vm.is_running.return_value = True
        no_qrexec_vm.get_power_state.return_value = 'Suspended'

        domains_dict = {
            'dom0': dom0,
            'running': running_vm,
            'not-running': not_running_vm,
            'no-qrexec': no_qrexec_vm,
        }
        self.addCleanup(domains_dict.clear)
        self.app.domains = mock.MagicMock(**{
            '__iter__': lambda _: iter(domains_dict.values()),
            '__getitem__': domains_dict.get,
        })

        ret = self.call_mgmt_func(b'internal.SuspendPost')
        self.assertIsNone(ret)
        self.assertFalse(dom0.called)

        self.assertNotIn(('run_service', ('vanir.SuspendPostAll',), mock.ANY),
            not_running_vm.mock_calls)
        self.assertNotIn(('resume', (), {}),
            not_running_vm.mock_calls)

        self.assertIn(('run_service', ('vanir.SuspendPostAll',), mock.ANY),
            running_vm.mock_calls)
        self.assertIn(('resume', (), {}),
            running_vm.mock_calls)

        self.assertNotIn(('run_service', ('vanir.SuspendPostAll',), mock.ANY),
            no_qrexec_vm.mock_calls)
        self.assertIn(('resume', (), {}),
            no_qrexec_vm.mock_calls)
#2019 Vanir-lab.
