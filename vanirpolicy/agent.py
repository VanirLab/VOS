''' Agent running in user session, responsible for asking the user about policy
decisions.'''

import pydbus
# pylint: disable=import-error,wrong-import-position
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib
# pylint: enable=import-error

import vanirpolicy.rpcconfirmation
import vanirpolicy.policycreateconfirmation
# pylint: enable=wrong-import-position

class PolicyAgent:
    # pylint: disable=too-few-public-methods
    dbus = """
    <node>
      <interface name='org.qubesos.PolicyAgent'>
        <method name='Ask'>
          <arg type='s' name='source' direction='in'/>
          <arg type='s' name='service_name' direction='in'/>
          <arg type='as' name='targets' direction='in'/>
          <arg type='s' name='default_target' direction='in'/>
          <arg type='a{ss}' name='icons' direction='in'/>
          <arg type='s' name='response' direction='out'/>
        </method>
        <method name='ConfirmPolicyCreate'>
          <arg type='s' name='source' direction='in'/>
          <arg type='s' name='service_name' direction='in'/>
          <arg type='b' name='response' direction='out'/>
        </method>
      </interface>
    </node>
    """

    @staticmethod
    def Ask(source, service_name, targets, default_target,
            icons):
        # pylint: disable=invalid-name
        entries_info = {}
        for entry in icons:
            entries_info[entry] = {}
            entries_info[entry]['icon'] = icons.get(entry, None)

        response = vanirpolicy.rpcconfirmation.confirm_rpc(
            entries_info, source, service_name,
            targets, default_target or None)
        return response or ''

    @staticmethod
    def ConfirmPolicyCreate(source, service_name):
        # pylint: disable=invalid-name

        response = vanirpolicy.policycreateconfirmation.confirm(
            source, service_name)
        return response

def main():
    loop = GLib.MainLoop()
    bus = pydbus.SystemBus()
    obj = PolicyAgent()
    bus.publish('org.vos.PolicyAgent', obj)
    loop.run()


if __name__ == '__main__':
    main()