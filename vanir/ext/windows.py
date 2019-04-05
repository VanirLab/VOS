import asyncio

import vanir.ext

class WindowsFeatures(vanir.ext.Extension):
    # pylint: disable=too-few-public-methods
    @vanir.ext.handler('features-request')
    def vanir_features_request(self, vm, event, untrusted_features):
        '''Handle features provided requested by vanir Windows Tools'''
        # pylint: disable=no-self-use,unused-argument
        if getattr(vm, 'template', None):
            vm.log.warning(
                'Ignoring vanir.NotifyTools for template-based VM')
            return

        guest_os = None
        if 'os' in untrusted_features:
            if untrusted_features['os'] in ['Windows', 'Linux']:
                guest_os = untrusted_features['os']

        qrexec = None
        if 'qrexec' in untrusted_features:
            if untrusted_features['qrexec'] == '1':
                # qrexec feature is set by CoreFeatures extension
                qrexec = True

        del untrusted_features

        if guest_os:
            vm.features['os'] = guest_os
        if guest_os == 'Windows' and qrexec:
            vm.features['rpc-clipboard'] = True

    @vanir.ext.handler('domain-create-on-disk')
    @asyncio.coroutine
    def on_domain_create_on_disk(self, vm, _event, **kwargs):
        # pylint: disable=no-self-use,unused-argument
        if getattr(vm, 'template', None) is None:
            # handle only template-based vms
            return

        template = vm.template
        if template.features.check_with_template('os', None) != 'Windows':
            # ignore non-windows templates
            return

        if vm.volumes['private'].save_on_stop:
            # until windows tools get ability to prepare private.img on its own,
            # copy one from the template
            vm.log.info('Windows template - cloning private volume')
            import_op = vm.volumes['private'].import_volume(
                template.volumes['private'])
            if asyncio.iscoroutine(import_op):
                yield from import_op