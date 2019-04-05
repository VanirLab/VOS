import vanir.ext

class ServicesExtension(vanir.ext.Extension):
    '''This extension export features with 'service.' prefix to VanirDB in
    /vanir-service/ tree.
    '''
    # pylint: disable=no-self-use
    @vanir.ext.handler('domain-qdb-create')
    def on_domain_qdb_create(self, vm, event):
        '''Actually export features'''
        # pylint: disable=unused-argument
        for feature, value in vm.features.items():
            if not feature.startswith('service.'):
                continue
            service = feature[len('service.'):]
            # forcefully convert to '0' or '1'
            vm.untrusted_qdb.write('/vanir-service/{}'.format(service),
                str(int(bool(value))))

        # always set meminfo-writer according to maxmem
        vm.untrusted_qdb.write('/vanir-service/meminfo-writer',
            '1' if vm.maxmem > 0 else '0')

    @vanir.ext.handler('domain-feature-set:*')
    def on_domain_feature_set(self, vm, event, feature, value, oldvalue=None):
        '''Update /vanir-service/ VanirDB tree in runtime'''
        # pylint: disable=unused-argument

        # TODO: remove this compatibility hack in Qubes 4.1
        if feature == 'service.meminfo-writer':
            # if someone try to enable meminfo-writer ...
            if value:
                # ... reset maxmem to default
                vm.maxmem = vanir.property.DEFAULT
            else:
                # otherwise, set to 0
                vm.maxmem = 0
            # in any case, remove the entry, as it does not indicate memory
            # balancing state anymore
            del vm.features['service.meminfo-writer']

        if not vm.is_running():
            return
        if not feature.startswith('service.'):
            return
        service = feature[len('service.'):]
        # forcefully convert to '0' or '1'
        vm.untrusted_qdb.write('/vanir-service/{}'.format(service),
            str(int(bool(value))))

    @vanir.ext.handler('domain-feature-delete:*')
    def on_domain_feature_delete(self, vm, event, feature):
        '''Update /vanir-service/ VanirDB tree in runtime'''
        # pylint: disable=unused-argument
        if not vm.is_running():
            return
        if not feature.startswith('service.'):
            return
        service = feature[len('service.'):]
        # this one is excluded from user control
        if service == 'meminfo-writer':
            return
        vm.untrusted_qdb.rm('/vanir-service/{}'.format(service))

    @vanir.ext.handler('domain-load')
    def on_domain_load(self, vm, event):
        '''Migrate meminfo-writer service into maxmem'''
        # pylint: disable=no-self-use,unused-argument
        if 'service.meminfo-writer' in vm.features:
            # if was set to false, force maxmem=0
            # otherwise, simply ignore as the default is fine
            if not vm.features['service.meminfo-writer']:
                vm.maxmem = 0
            del vm.features['service.meminfo-writer']

    @vanir.ext.handler('features-request')
    def supported_services(self, vm, event, untrusted_features):
        '''Handle advertisement of supported services'''
        # pylint: disable=no-self-use,unused-argument

        if getattr(vm, 'template', None):
            vm.log.warning(
                'Ignoring vanir.FeaturesRequest from template-based VM')
            return

        new_supported_services = set()
        for requested_service in untrusted_features:
            if not requested_service.startswith('supported-service.'):
                continue
            if untrusted_features[requested_service] == '1':
                # only allow to advertise service as supported, lack of entry
                #  means service is not supported
                new_supported_services.add(requested_service)
        del untrusted_features

        # if no service is supported, ignore the whole thing - do not clear
        # all services in case of empty request (manual or such)
        if not new_supported_services:
            return

        old_supported_services = set(
            feat for feat in vm.features
            if feat.startswith('supported-service.') and vm.features[feat])

        for feature in new_supported_services.difference(
                old_supported_services):
            vm.features[feature] = True

        for feature in old_supported_services.difference(
                new_supported_services):
            del vm.features[feature]