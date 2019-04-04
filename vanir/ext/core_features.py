import asyncio

import vanir.ext

class CoreFeatures(vanir.ext.Extension):
    # pylint: disable=too-few-public-methods
    @vanir.ext.handler('features-request')
    @asyncio.coroutine
    def vanir_features_request(self, vm, event, untrusted_features):
        '''Handle features provided by vanir-core-agent and vanir-gui-agent'''
        # pylint: disable=no-self-use,unused-argument
        if getattr(vm, 'template', None):
            vm.log.warning(
                'Ignoring vanir.NotifyTools for template-based VM')
            return

        requested_features = {}
        for feature in ('qrexec', 'gui', 'gui-emulated', 'vanir-firewall'):
            untrusted_value = untrusted_features.get(feature, None)
            if untrusted_value in ('1', '0'):
                requested_features[feature] = bool(int(untrusted_value))
        del untrusted_features

        # default user for qvm-run etc
        # starting with Vanir 1.x ignored
        # qrexec agent presence (0 or 1)
        # gui agent presence (0 or 1)

        qrexec_before = vm.features.get('qrexec', False)
        for feature in ('qrexec', 'gui', 'gui-emulated'):
            # do not allow (Template)VM to override setting if already set
            # some other way
            if feature in requested_features and feature not in vm.features:
                vm.features[feature] = requested_features[feature]

        # those features can be freely enabled or disabled by template
        for feature in ('vanir-firewall',):
            if feature in requested_features:
                vm.features[feature] = requested_features[feature]

        if not qrexec_before and vm.features.get('qrexec', False):
            # if this is the first time qrexec was advertised, now can finish
            #  template setup
            yield from vm.fire_event_async('template-postinstall')