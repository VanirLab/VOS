'''
Vanir OS exception hierarchy
'''

class VanirException(Exception):
    '''Exception that can be shown to the user'''


class VanirVMNotFoundError(VanirException, KeyError):
    '''Domain cannot be found in the system'''
    def __init__(self, vmname):
        super(VanirVMNotFoundError, self).__init__(
            'No such domain: {!r}'.format(vmname))
        self.vmname = vmname


class VanirVMError(VanirException):
    '''Some problem with domain state.'''
    def __init__(self, vm, msg):
        super(VanirVMError, self).__init__(msg)
        self.vm = vm

class VanirVMInUseError(VanirVMError):
    '''VM is in use, cannot remove.'''
    def __init__(self, vm, msg=None):
        super(VanirVMInUseError, self).__init__(vm,
            msg or 'Domain is in use: {!r}'.format(vm.name))

class VanirVMNotStartedError(VanirVMError):
    '''Domain is not started.
    This exception is thrown when machine is halted, but should be started
    (that is, either running or paused).
    '''
    def __init__(self, vm, msg=None):
        super(VanirVMNotStartedError, self).__init__(vm,
            msg or 'Domain is powered off: {!r}'.format(vm.name))


class VanirVMNotRunningError(VanirVMNotStartedError):
    '''Domain is not running.
    This exception is thrown when machine should be running but is either
    halted or paused.
    '''
    def __init__(self, vm, msg=None):
        super(VanirVMNotRunningError, self).__init__(vm,
            msg or 'Domain not running (either powered off or paused): {!r}' \
                .format(vm.name))


class VanirVMNotPausedError(VanirVMNotStartedError):
    '''Domain is not paused.
    This exception is thrown when machine should be paused, but is not.
    '''
    def __init__(self, vm, msg=None):
        super(VanirVMNotPausedError, self).__init__(vm,
            msg or 'Domain is not paused: {!r}'.format(vm.name))


class VanirVMNotSuspendedError(VanirVMError):
    '''Domain is not suspended.
    This exception is thrown when machine should be suspended but is either
    halted or running.
    '''
    def __init__(self, vm, msg=None):
        super(VanirVMNotSuspendedError, self).__init__(vm,
            msg or 'Domain is not suspended: {!r}'.format(vm.name))


class VanirVMNotHaltedError(VanirVMError):
    '''Domain is not halted.
    This exception is thrown when machine should be halted, but is not (either
    running or paused).
    '''
    def __init__(self, vm, msg=None):
        super(VanirVMNotHaltedError, self).__init__(vm,
            msg or 'Domain is not powered off: {!r}'.format(vm.name))

class VanirVMShutdownTimeoutError(VanirVMError):
    '''Domain shutdown timed out.
    '''
    def __init__(self, vm, msg=None):
        super(VanirVMShutdownTimeoutError, self).__init__(vm,
            msg or 'Domain shutdown timed out: {!r}'.format(vm.name))


class VanirNoTemplateError(VanirVMError):
    '''Cannot start domain, because there is no template'''
    def __init__(self, vm, msg=None):
        super(VanirNoTemplateError, self).__init__(vm,
            msg or 'Template for the domain {!r} not found'.format(vm.name))


class VanirPoolInUseError(VanirException):
    '''VM is in use, cannot remove.'''
    def __init__(self, pool, msg=None):
        super(VanirPoolInUseError, self).__init__(
            msg or 'Storage pool is in use: {!r}'.format(pool.name))


class QubesValueError(VanirException, ValueError):
    '''Cannot set some value, because it is invalid, out of bounds, etc.'''


class VanirPropertyValueError(QubesValueError):
    '''Cannot set value of vanir.property, because user-supplied value is wrong.
    '''
    def __init__(self, holder, prop, value, msg=None):
        super(VanirPropertyValueError, self).__init__(
            msg or 'Invalid value {!r} for property {!r} of {!r}'.format(
                value, prop.__name__, holder))
        self.holder = holder
        self.prop = prop
        self.value = value


class VanirNoSuchPropertyError(VanirException, AttributeError):
    '''Requested property does not exist
    '''
    def __init__(self, holder, prop_name, msg=None):
        super(VanirNoSuchPropertyError, self).__init__(
            msg or 'Invalid property {!r} of {!s}'.format(
                prop_name, holder))
        self.holder = holder
        self.prop = prop_name


class VanirNotImplementedError(VanirException, NotImplementedError):
    '''Thrown at user when some feature is not implemented'''
    def __init__(self, msg=None):
        super(VanirNotImplementedError, self).__init__(
            msg or 'This feature is not available')


class BackupCancelledError(VanirException):
    '''Thrown at user when backup was manually cancelled'''
    def __init__(self, msg=None):
        super(BackupCancelledError, self).__init__(
            msg or 'Backup cancelled')


class VanirMemoryError(VanirVMError, MemoryError):
    '''Cannot start domain, because not enough memory is available'''
    def __init__(self, vm, msg=None):
        super(VanirMemoryError, self).__init__(vm,
            msg or 'Not enough memory to start domain {!r}'.format(vm.name))


class VanirFeatureNotFoundError(VanirException, KeyError):
    '''Feature not set for a given domain'''
    def __init__(self, domain, feature):
        super(VanirFeatureNotFoundError, self).__init__(
            'Feature not set for domain {}: {}'.format(domain, feature))
        self.feature = feature
        self.vm = domain

class VanirTagNotFoundError(VanirException, KeyError):
    '''Tag not set for a given domain'''

    def __init__(self, domain, tag):
        super().__init__('Tag not set for domain {}: {}'.format(
            domain, tag))
        self.vm = domain
        self.tag = tag