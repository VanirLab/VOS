import dbus
import vanir.ext


class VanirManager(vanir.ext.Extension):
    def __init__(self, *args, **kwargs):
        super(VanirManager, self).__init__(*args, **kwargs)
        try:
            self._system_bus = dbus.SystemBus()
        except dbus.exceptions.DBusException:
            # we can't access Vanir() object here to check for offline mode,
            # so lets assume it is this case...
            self._system_bus = None

    # pylint: disable=no-self-use,unused-argument,too-few-public-methods

    @vanir.ext.handler('status:error')
    def on_status_error(self, vm, event, status, message):
        if self._system_bus is None:
            return
        try:
            vanir_manager = self._system_bus.get_object(
                'org.vaniros.VanirManager',
                '/org/vaniros/VanirManager')
            vanir_manager.notify_error(vm.name, message,
                dbus_interface='org.vaniros.VanirManager')
        except dbus.DBusException:
            # ignore the case when no vanir-manager is running
            pass

    @vanir.ext.handler('status:no-error')
    def on_status_no_error(self, vm, event, status, message):
        if self._system_bus is None:
            return
        try:
            vanir_manager = self._system_bus.get_object(
                'org.vaniros.VanirManager',
                '/org/vaniros/VanirManager')
            vanir_manager.clear_error_exact(vm.name, message,
                dbus_interface='org.vaniros.VanirManager')
        except dbus.DBusException:
            # ignore the case when no vanir-manager is running
            pass