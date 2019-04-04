import asyncio
import json
import subprocess

import vanir.api
import vanir.api.admin
import vanir.vm.adminvm
import vanir.vm.dispvm


class VanirInternalAPI(vanir.api.AbstractVanirAPI):
    ''' Communication interface for dom0 components,
    by design the input here is trusted.'''

    SOCKNAME = '/var/run/vanirsd.internal.sock'

    @vanir.api.method('internal.GetSystemInfo', no_payload=True)
    @asyncio.coroutine
    def getsysteminfo(self):
        self.enforce(self.dest.name == 'dom0')
        self.enforce(not self.arg)

        system_info = {'domains': {
            domain.name: {
                'tags': list(domain.tags),
                'type': domain.__class__.__name__,
                'template_for_dispvms':
                    getattr(domain, 'template_for_dispvms', False),
                'default_dispvm': (str(domain.default_dispvm) if
                    getattr(domain, 'default_dispvm', None) else None),
                'icon': str(domain.label.icon),
            } for domain in self.app.domains
        }}

        return json.dumps(system_info)

    @vanir.api.method('internal.vm.volume.ImportEnd')
    @asyncio.coroutine
    def vm_volume_import_end(self, untrusted_payload):
        '''
        This is second half of admin.vm.volume.Import handling. It is called
        when actual import is finished. Response from this method is sent do
        the client (as a response for admin.vm.volume.Import call).
        '''
        self.enforce(self.arg in self.dest.volumes.keys())
        success = untrusted_payload == b'ok'

        try:
            yield from self.dest.storage.import_data_end(self.arg,
                success=success)
        except:
            self.dest.fire_event('domain-volume-import-end', volume=self.arg,
                success=False)
            raise

        self.dest.fire_event('domain-volume-import-end', volume=self.arg,
            success=success)

        if not success:
            raise vanir.exc.VanirException('Data import failed')

    @vanir.api.method('internal.SuspendPre', no_payload=True)
    @asyncio.coroutine
    def suspend_pre(self):
        '''
        Method called before host system goes to sleep.
        :return:
        '''

        # first notify all VMs
        processes = []
        for vm in self.app.domains:
            if isinstance(vm, vanir.vm.adminvm.AdminVM):
                continue
            if not vm.is_running():
                continue
            if not vm.features.check_with_template('qrexec', False):
                continue
            try:
                proc = yield from vm.run_service(
                    'vanir.SuspendPreAll', user='root',
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL)
                processes.append(proc)
            except vanir.exc.VanirException as e:
                vm.log.warning('Failed to run vanir.SuspendPreAll: %s', str(e))

        # FIXME: some timeout?
        if processes:
            yield from asyncio.wait([p.wait() for p in processes])

        coros = []
        # then suspend/pause VMs
        for vm in self.app.domains:
            if isinstance(vm, vanir.vm.adminvm.AdminVM):
                continue
            if vm.is_running():
                coros.append(vm.suspend())
        if coros:
            yield from asyncio.wait(coros)

    @vanir.api.method('internal.SuspendPost', no_payload=True)
    @asyncio.coroutine
    def suspend_post(self):
        '''
        Method called after host system wake up from sleep.
        :return:
        '''

        coros = []
        # first resume/unpause VMs
        for vm in self.app.domains:
            if isinstance(vm, vanir.vm.adminvm.AdminVM):
                continue
            if vm.get_power_state() in ["Paused", "Suspended"]:
                coros.append(vm.resume())
        if coros:
            yield from asyncio.wait(coros)

        # then notify all VMs
        processes = []
        for vm in self.app.domains:
            if isinstance(vm, vanir.vm.adminvm.AdminVM):
                continue
            if not vm.is_running():
                continue
            if not vm.features.check_with_template('qrexec', False):
                continue
            try:
                proc = yield from vm.run_service(
                    'vanir.SuspendPostAll', user='root',
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL)
                processes.append(proc)
            except vanir.exc.VanirException as e:
                vm.log.warning('Failed to run vanir.SuspendPostAll: %s', str(e))

        # FIXME: some timeout?
        if processes:
            yield from asyncio.wait([p.wait() for p in processes])