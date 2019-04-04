import vanir.events
import vanir.vm.vanirvm
import vanir.config

class StandaloneVM(vanir.vm.vanirvm.VanirVM):
    '''Standalone Application VM'''

    def __init__(self, *args, **kwargs):
        self.volume_config = {
            'root': {
                'name': 'root',
                'snap_on_start': False,
                'save_on_stop': True,
                'rw': True,
                'source': None,
                'size': vanir.config.defaults['root_img_size'],
            },
            'private': {
                'name': 'private',
                'snap_on_start': False,
                'save_on_stop': True,
                'rw': True,
                'source': None,
                'size': vanir.config.defaults['private_img_size'],
            },
            'volatile': {
                'name': 'volatile',
                'snap_on_start': False,
                'save_on_stop': False,
                'rw': True,
                'size': vanir.config.defaults['root_img_size'],
            },
            'kernel': {
                'name': 'kernel',
                'snap_on_start': False,
                'save_on_stop': False,
                'rw': False,
            }
        }
        super(StandaloneVM, self).__init__(*args, **kwargs)