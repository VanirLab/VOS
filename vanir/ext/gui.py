''' Vanir GUI Extensions '''
import vanir.config
import vanir.ext


class GUI(vanir.ext.Extension):
    # pylint: disable=too-few-public-methods
    # TODO put this somewhere...
    @staticmethod
    def send_gui_mode(vm):
        vm.run_service('vanir.SetGuiMode',
            input=('SEAMLESS'
            if vm.features.get('gui-seamless', False)
            else 'FULLSCREEN'))

    @vanir.ext.handler('domain-qdb-create')
    def on_domain_qdb_create(self, vm, event):
        # pylint: disable=unused-argument,no-self-use
        for feature in ('gui-videoram-overhead', 'gui-videoram-min'):
            try:
                vm.untrusted_qdb.write('/vanir-{}'.format(feature),
                    vm.features.check_with_template_and_adminvm(feature))
            except KeyError:
                pass