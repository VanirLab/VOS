import libvirt

import copy

import vanir.events
import vanir.vm.vanirvm
from vanir.config import defaults

class AppVM(vanir.vm.vanirvm.VanirVM):
    '''Application VM'''

    template = vanir.VMProperty('template',
                                load_stage=4,
                                vmclass=vanir.vm.templatevm.TemplateVM,
                                doc='Template, on which this AppVM is based.')

    template_for_dispvms = vanir.property('template_for_dispvms',
        type=bool,
        default=False,
        doc='Should this VM be allowed to start as Disposable VM')

    default_volume_config = {
            'root': {
                'name': 'root',
                'snap_on_start': True,
                'save_on_stop': False,
                'rw': True,
                'source': None,
            },
            'private': {
                'name': 'private',
                'snap_on_start': False,
                'save_on_stop': True,
                'rw': True,
                'size': defaults['private_img_size'],
            },
            'volatile': {
                'name': 'volatile',
                'snap_on_start': False,
                'save_on_stop': False,
                'size': defaults['root_img_size'],
                'rw': True,
            },
            'kernel': {
                'name': 'kernel',
                'snap_on_start': False,
                'save_on_stop': False,
                'rw': False,
            }
        }

    def __init__(self, app, xml, **kwargs):
        # migrate renamed properties
        if xml is not None:
            node_dispvm_allowed = xml.find(
                './properties/property[@name=\'dispvm_allowed\']')
            if node_dispvm_allowed is not None:
                kwargs['template_for_dispvms'] = \
                    vanir.property.bool(None, None, node_dispvm_allowed.text)
                node_dispvm_allowed.getparent().remove(node_dispvm_allowed)

        self.volume_config = copy.deepcopy(self.default_volume_config)
        template = kwargs.get('template', None)

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

        super(AppVM, self).__init__(app, xml, **kwargs)

    @property
    def dispvms(self):
        ''' Returns a generator containing all Disposable VMs based on the
        current AppVM.
        '''
        for vm in self.app.domains:
            if hasattr(vm, 'template') and vm.template is self:
                yield vm

    @vanir.events.handler('domain-load')
    def on_domain_loaded(self, event):
        ''' When domain is loaded assert that this vm has a template.
        '''  # pylint: disable=unused-argument
        assert self.template

    @vanir.events.handler('property-pre-del:template')
    def on_property_pre_del_template(self, event, name, oldvalue=None):
        '''Forbid deleting template of running VM
        '''  # pylint: disable=unused-argument,no-self-use
        raise vanir.exc.VanirValueError('Cannot unset template')

    @vanir.events.handler('property-pre-set:template')
    def on_property_pre_set_template(self, event, name, newvalue,
            oldvalue=None):
        '''Forbid changing template of running VM
        '''  # pylint: disable=unused-argument
        if not self.is_halted():
            raise vanir.exc.VanirVMNotHaltedError(self,
                'Cannot change template while qube is running')
        if any(self.dispvms):
            raise vanir.exc.VanirVMInUseError(self,
                'Cannot change template '
                'while there are DispVMs based on this qube')

    @vanir.events.handler('property-set:template')
    def on_property_set_template(self, event, name, newvalue, oldvalue=None):
        ''' Adjust root (and possibly other snap_on_start=True) volume
        on template change.
        '''  # pylint: disable=unused-argument

        for volume_name, conf in self.default_volume_config.items():
            if conf.get('snap_on_start', False) and \
                    conf.get('source', None) is None:
                config = conf.copy()
                self.volume_config[volume_name] = config
                self.storage.init_volume(volume_name, config)