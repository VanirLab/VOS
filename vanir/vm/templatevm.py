import warnings

import vanir
import vanir.config
import vanir.vm.vanirvm
import vanir.vm.mix.net
from vanir.config import defaults
from vanir.vm.vanirvm import VanirVM


class TemplateVM(VanirVM):
    '''Template for AppVM'''

    dir_path_prefix = vanir.config.system_path['vanir_templates_dir']

    @property
    def rootcow_img(self):
        '''COW image'''
        warnings.warn("rootcow_img is deprecated, use "
                      "volumes['root'].path_origin", DeprecationWarning)
        return self.volumes['root'].path_cow

    @property
    def appvms(self):
        ''' Returns a generator containing all domains based on the current
            TemplateVM.
        '''
        for vm in self.app.domains:
            if hasattr(vm, 'template') and vm.template is self:
                yield vm

    netvm = vanir.VMProperty('netvm', load_stage=4, allow_none=True,
        default=None,
        # pylint: disable=protected-access
        setter=vanir.vm.vanirvm.VanirVM.netvm._setter,
        doc='VM that provides network connection to this domain. When '
            '`None`, machine is disconnected.')

    def __init__(self, *args, **kwargs):
        assert 'template' not in kwargs, "A TemplateVM can not have a template"
        self.volume_config = {
            'root': {
                'name': 'root',
                'snap_on_start': False,
                'save_on_stop': True,
                'rw': True,
                'source': None,
                'size': defaults['root_img_size'],
            },
            'private': {
                'name': 'private',
                'snap_on_start': False,
                'save_on_stop': True,
                'rw': True,
                'source': None,
                'size': defaults['private_img_size'],
                'revisions_to_keep': 0,
            },
            'volatile': {
                'name': 'volatile',
                'size': defaults['root_img_size'],
                'snap_on_start': False,
                'save_on_stop': False,
                'rw': True,
            },
            'kernel': {
                'name': 'kernel',
                'snap_on_start': False,
                'save_on_stop': False,
                'rw': False
            }
        }
        super(TemplateVM, self).__init__(*args, **kwargs)