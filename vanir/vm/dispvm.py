import asyncio

import vanir.vm.vanirvm
import vanir.vm.appvm
import vanir.config

class DispVM(vanir.vm.vanirvm.VanirVM):
    '''Disposable VM'''

    template = vanir.VMProperty('template',
                                load_stage=4,
                                vmclass=vanir.vm.appvm.AppVM,
                                doc='AppVM, on which this DispVM is based.')

    dispid = vanir.property('dispid', type=int, write_once=True,
        clone=False,
        doc='''Internal, persistent identifier of particular DispVM.''')

    auto_cleanup = vanir.property('auto_cleanup', type=bool, default=False,
        doc='automatically remove this VM upon shutdown')

    include_in_backups = vanir.property('include_in_backups', type=bool,
        default=(lambda self: not self.auto_cleanup),
        doc='If this domain is to be included in default backup.')

    default_dispvm = vanir.VMProperty('default_dispvm',
        load_stage=4,
        allow_none=True,
        default=(lambda self: self.template),
        doc='Default VM to be used as Disposable VM for service calls.')

    def __init__(self, app, xml, *args, **kwargs):
        self.volume_config = {
            'root': {
                'name': 'root',
                'snap_on_start': True,
                'save_on_stop': False,
                'rw': True,
                'source': None,
            },
            'private': {
                'name': 'private',
                'snap_on_start': True,
                'save_on_stop': False,
                'rw': True,
                'source': None,
            },
            'volatile': {
                'name': 'volatile',
                'snap_on_start': False,
                'save_on_stop': False,
                'rw': True,
                'size': vanir.config.defaults['root_img_size'] +
                        vanir.config.defaults['private_img_size'],
            },
            'kernel': {
                'name': 'kernel',
                'snap_on_start': False,
                'save_on_stop': False,
                'rw': False,
            }
        }

        template = kwargs.get('template', None)

        if xml is None:
            assert template is not None

            if not getattr(template, 'template_for_dispvms', False):
                raise vanir.exc.VanirValueError(
                    'template for DispVM ({}) needs to be an AppVM with '
                    'template_for_dispvms=True'.format(template.name))

            if 'dispid' not in kwargs:
                kwargs['dispid'] = app.domains.get_new_unused_dispid()
            if 'name' not in kwargs:
                kwargs['name'] = 'disp' + str(kwargs['dispid'])

        if template is not None:
            # template is only passed if the AppVM is created, in other cases we
            # don't need to patch the volume_config because the config is
            # coming from XML, already as we need it
            for name, config in template.volume_config.items():
                # in case the template vm has more volumes add them to own
                # config
                if name not in self.volume_config:
                    self.volume_config[name] = config.copy()
                    if 'vid' in self.volume_config[name]:
                        del self.volume_config[name]['vid']

        super(DispVM, self).__init__(app, xml, *args, **kwargs)

        if xml is None:
            # by default inherit properties from the DispVM template
            proplist = [prop.__name__ for prop in template.property_list()
                if prop.clone and prop.__name__ not in ['template']]
            self_props = [prop.__name__ for prop in self.property_list()]
            self.clone_properties(template, set(proplist).intersection(
                self_props))

            self.firewall.clone(template.firewall)
            self.features.update(template.features)
            self.tags.update(template.tags)

    @vanir.events.handler('domain-load')
    def on_domain_loaded(self, event):
        ''' When domain is loaded assert that this vm has a template.
        '''  # pylint: disable=unused-argument
        assert self.template

    @vanir.events.handler('property-pre-set:template',
        'property-pre-del:template')
    def on_property_pre_set_template(self, event, name, newvalue=None,
            oldvalue=None):
        ''' Disposable VM cannot have template changed '''
        # pylint: disable=unused-argument
        raise vanir.exc.VanirValueError(self,
            'Cannot change template of Disposable VM')

    @vanir.events.handler('domain-shutdown')
    @asyncio.coroutine
    def on_domain_shutdown(self, _event, **_kwargs):
        yield from self._auto_cleanup()

    @asyncio.coroutine
    def _auto_cleanup(self):
        '''Do auto cleanup if enabled'''
        if self.auto_cleanup and self in self.app.domains:
            del self.app.domains[self]
            yield from self.remove_from_disk()
            self.app.save()

    @classmethod
    @asyncio.coroutine
    def from_appvm(cls, appvm, **kwargs):
        '''Create a new instance from given AppVM
        :param vanir.vm.appvm.AppVM appvm: template from which the VM should \
            be created
        :returns: new disposable vm
        *kwargs* are passed to the newly created VM
        >>> import vanir.vm.dispvm.DispVM
        >>> dispvm = vanir.vm.dispvm.DispVM.from_appvm(appvm).start()
        >>> dispvm.run_service('vanir.VMShell', input='firefox')
        >>> dispvm.cleanup()
        This method modifies :file:`vanir.xml` file.
        The qube returned is not started.
        '''
        if not appvm.template_for_dispvms:
            raise vanir.exc.VanirException(
                'Refusing to create DispVM out of this AppVM, because '
                'template_for_dispvms=False')
        app = appvm.app
        dispvm = app.add_new_vm(
            cls,
            template=appvm,
            auto_cleanup=True,
            **kwargs)
        yield from dispvm.create_on_disk()
        app.save()
        return dispvm

    @asyncio.coroutine
    def cleanup(self):
        '''Clean up after the DispVM
        This stops the disposable qube and removes it from the store.
        This method modifies :file:`vanir.xml` file.
        '''
        try:
            # pylint: disable=not-an-iterable
            yield from self.kill()
        except vanir.exc.VanirVMNotStartedError:
            pass
        # if auto_cleanup is set, this will be done automatically
        if not self.auto_cleanup:
            del self.app.domains[self]
            yield from self.remove_from_disk()
            self.app.save()

    @asyncio.coroutine
    def start(self, **kwargs):
        # pylint: disable=arguments-differ

        try:
            # sanity check, if template_for_dispvm got changed in the meantime
            if not self.template.template_for_dispvms:
                raise vanir.exc.VanirException(
                    'template for DispVM ({}) needs to have '
                    'template_for_dispvms=True'.format(self.template.name))

            yield from super(DispVM, self).start(**kwargs)
        except:
            # Cleanup also on failed startup
            yield from self._auto_cleanup()
            raise

    def create_qdb_entries(self):
        super().create_qdb_entries()
        self.untrusted_qdb.write('/vanir-vm-persistence', 'none')