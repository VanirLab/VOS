import libvirt
import vanir
import vanir.exc
import vanir.vm


class AdminVM(vanir.vm.BaseVM):
    '''Dom0'''

    dir_path = None

    name = vanir.property('name',
        default='dom0', setter=vanir.property.forbidden)

    qid = vanir.property('qid',
        default=0, type=int, setter=vanir.property.forbidden)

    uuid = vanir.property('uuid',
        default='00000000-0000-0000-0000-000000000000',
        setter=vanir.property.forbidden)

    default_dispvm = vanir.VMProperty('default_dispvm',
        load_stage=4,
        allow_none=True,
        default=(lambda self: self.app.default_dispvm),
        doc='Default VM to be used as Disposable VM for service calls.')

    include_in_backups = vanir.property('include_in_backups',
        default=True, type=bool,
        doc='If this domain is to be included in default backup.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._qdb_connection = None
        self._libvirt_domain = None

        if not self.app.vmm.offline_mode:
            self.start_qdb_watch()

    def __str__(self):
        return self.name

    def __lt__(self, other):
        # order dom0 before anything
        return self.name != other.name

    @property
    def attached_volumes(self):
        return []

    @property
    def xid(self):
        '''Always ``0``.
        .. seealso:
           :py:attr:`vanir.vm.vanirvm.VanirVM.xid`
        '''
        return 0

    @property
    def libvirt_domain(self):
        '''Libvirt object for dom0.
        .. seealso:
           :py:attr:`vanir.vm.vanirvm.VanirVM.libvirt_domain`
        '''
        if self._libvirt_domain is None:
            self._libvirt_domain = self.app.vmm.libvirt_conn.lookupByID(0)
        return self._libvirt_domain

    @staticmethod
    def is_running():
        '''Always :py:obj:`True`.
        .. seealso:
           :py:meth:`vanir.vm.vanirvm.VanirVM.is_running`
        '''
        return True

    @staticmethod
    def is_halted():
        '''Always :py:obj:`False`.
        .. seealso:
           :py:meth:`vanir.vm.vanirvm.VanirVM.is_halted`
        '''
        return False

    @staticmethod
    def get_power_state():
        '''Always ``'Running'``.
        .. seealso:
           :py:meth:`vanir.vm.vanirvm.VanirVM.get_power_state`
        '''
        return 'Running'

    @staticmethod
    def get_mem():
        '''Get current memory usage of Dom0.
        Unit is KiB.
        .. seealso:
           :py:meth:`vanir.vm.vanirvm.VanirVM.get_mem`
        '''

        # return psutil.virtual_memory().total/1024
        with open('/proc/meminfo') as file:
            for line in file:
                if line.startswith('MemTotal:'):
                    return int(line.split(':')[1].strip().split()[0])
        raise NotImplementedError()

    def get_mem_static_max(self):
        '''Get maximum memory available to Dom0.
        .. seealso:
           :py:meth:`vanir.vm.vanirvm.VanirVM.get_mem_static_max`
        '''
        if self.app.vmm.offline_mode:
            # default value passed on xen cmdline
            return 4096
        try:
            return self.app.vmm.libvirt_conn.getInfo()[1]
        except libvirt.libvirtError as e:
            self.log.warning('Failed to get memory limit for dom0: %s', e)
            return 4096

    def verify_files(self):
        '''Always :py:obj:`True`
        .. seealso:
           :py:meth:`vanir.vm.vanirvm.VanirVM.verify_files`
        '''  # pylint: disable=no-self-use
        return True

    def start(self, start_guid=True, notify_function=None,
            mem_required=None):
        '''Always raises an exception.
        .. seealso:
           :py:meth:`vanir.vm.vanirvm.VanirVM.start`
        '''  # pylint: disable=unused-argument,arguments-differ
        raise vanir.exc.VanirVMError(self, 'Cannot start Dom0 fake domain!')

    def suspend(self):
        '''Does nothing.
        .. seealso:
           :py:meth:`vanir.vm.vanirvm.VanirVM.suspend`
        '''
        raise vanir.exc.VanirVMError(self, 'Cannot suspend Dom0 fake domain!')

    def shutdown(self):
        '''Does nothing.
        .. seealso:
           :py:meth:`vanir.vm.vanirvm.VanirVM.shutdown`
        '''
        raise vanir.exc.VanirVMError(self, 'Cannot shutdown Dom0 fake domain!')

    def kill(self):
        '''Does nothing.
        .. seealso:
           :py:meth:`vanir.vm.vanirvm.VanirVM.kill`
        '''
        raise vanir.exc.VanirVMError(self, 'Cannot kill Dom0 fake domain!')

    @property
    def icon_path(self):
        pass

    @property
    def untrusted_qdb(self):
        '''Vanirdb handle for this domain.'''
        if self._qdb_connection is None:
            import vanirdb  # pylint: disable=import-error
            self._qdb_connection = vanirdb.Vanirdb(self.name)
        return self._qdb_connection


#   def __init__(self, **kwargs):
#       super(VanirAdminVm, self).__init__(qid=0, name="dom0",
#                                            dir_path=None,
#                                            private_img = None,
#                                            template = None,
#                                            maxmem = 0,
#                                            vcpus = 0,
#                                            label = defaults["template_label"],
#                                            **kwargs)