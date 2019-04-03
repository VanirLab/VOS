import pkg_resources
import vanir.events


class Extension:
    '''Base class for all extensions
    '''  # pylint: disable=too-few-public-methods

    def __new__(cls):
        if '_instance' not in cls.__dict__:
            cls._instance = super(Extension, cls).__new__(cls)

            for name in cls.__dict__:
                attr = getattr(cls._instance, name)
                if not vanir.events.ishandler(attr):
                    continue

                if attr.ha_vm is not None:
                    for event in attr.ha_events:
                        attr.ha_vm.__handlers__[event].add(attr)
                else:
                    # global hook
                    for event in attr.ha_events:
                        # pylint: disable=no-member
                        vanir.vanir.__handlers__[event].add(attr)

        return cls._instance


def get_extensions():
    return set(ext.load()()
        for ext in pkg_resources.iter_entry_points('vanir.ext'))


def handler(*events, **kwargs):
    '''Event handler decorator factory.
    To hook an event, decorate a method in your plugin class with this
    decorator. You may hook both per-vm-class and global events.
    .. note::
        This decorator is intended only for extensions! For regular use in the
        core, see :py:func:`vanir.events.handler`.
    :param str event: event type
    :param type vm: VM to hook (leave as None to hook all VMs)
    :param bool system: when :py:obj:`True`, hook is system-wide (not attached \
        to any VM)
    '''

    def decorator(func):
        func.ha_events = events

        if kwargs.get('system', False):
            func.ha_vm = None
        elif 'vm' in kwargs:
            func.ha_vm = kwargs['vm']
        else:
            func.ha_vm = vanir.vm.BaseVM

        return func

    return decorator