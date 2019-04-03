import vanir.api
import vanir.ext
import vanir.vm.adminvm

class AdminExtension(vanir.ext.Extension):
    # pylint: disable=too-few-public-methods
    @vanir.ext.handler(
        'admin-permission:admin.vm.tag.Set',
        'admin-permission:admin.vm.tag.Remove')
    def on_tag_set_or_remove(self, vm, event, arg, **kwargs):
        '''Forbid changing specific tags'''
        # pylint: disable=no-self-use,unused-argument
        if arg.startswith('created-by-') and \
                not isinstance(vm, vanir.vm.adminvm.AdminVM):
            raise vanir.api.PermissionDenied(
                'changing this tag is prohibited by {}.{}'.format(
                    __name__, type(self).__name__))