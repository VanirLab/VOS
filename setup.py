import os

import setuptools
import setuptools.command.install


# don't import: import * is unreliable and there is no need, since this is
# compile time and we have source files
def get_console_scripts():
    yield 'qrexec-policy', 'vanirpolicy.cli'
    yield 'qrexec-policy-agent', 'vanirpolicy.agent'
    yield 'qrexec-policy-graph', 'vanirpolicy.graph'
    for filename in os.listdir('./vanir/tools'):
        basename, ext = os.path.splitext(os.path.basename(filename))
        if basename == '__init__' or ext != '.py':
            continue
        yield basename.replace('_', '-'), 'vanir.tools.{}'.format(basename)

# create simple scripts that run much faster than "console entry points"
class CustomInstall(setuptools.command.install.install):
    def run(self):
        bin = os.path.join(self.root, "usr/bin")
        try:
            os.makedirs(bin)
        except:
            pass
        for file, pkg in get_console_scripts():
           path = os.path.join(bin, file)
           with open(path, "w") as f:
               f.write(
"""#!/usr/bin/python3
from {} import main
import sys
if __name__ == '__main__':
	sys.exit(main())
""".format(pkg))

           os.chmod(path, 0o755)
        setuptools.command.install.install.run(self)

if __name__ == '__main__':
    setuptools.setup(
        name='vanir',
        version=open('version').read().strip(),
        author='Cybertrigo',
        description='vanir core package',
        license='GPL2+',
        url='https://github.com/VanirLab/VOS',
        packages=setuptools.find_packages(exclude=('core*', 'tests')),
        package_data = {
            'vanirpolicy': ['glade/*.glade'],
        },
        cmdclass={
            'install': CustomInstall,
        },
        entry_points={
            'vanir.vm': [
                'AppVM = vanir.vm.appvm:AppVM',
                'TemplateVM = vanir.vm.templatevm:TemplateVM',
                'StandaloneVM = vanir.vm.standalonevm:StandaloneVM',
                'AdminVM = vanir.vm.adminvm:AdminVM',
                'DispVM = vanir.vm.dispvm:DispVM',
            ],
            'vanir.ext': [
                'vanir.ext.admin = vanir.ext.admin:AdminExtension',
                'vanir.ext.core_features = vanir.ext.core_features:CoreFeatures',
                'vanir.ext.VanirManager = vanir.ext.VanirManager:VanirManager',
                'vanir.ext.gui = vanir.ext.gui:GUI',
                'vanir.ext.r3compatibility = vanir.ext.r3compatibility:R3Compatibility',
                'vanir.ext.pci = vanir.ext.pci:PCIDeviceExtension',
                'vanir.ext.block = vanir.ext.block:BlockDeviceExtension',
                'vanir.ext.services = vanir.ext.services:ServicesExtension',
                'vanir.ext.windows = vanir.ext.windows:WindowsFeatures',
            ],
            'vanir.devices': [
                'pci = vanir.ext.pci:PCIDevice',
                'block = vanir.ext.block:BlockDevice',
                'testclass = vanir.tests.devices:TestDevice',
            ],
            'vanir.storage': [
                'file = vanir.storage.file:FilePool',
                'file-reflink = vanir.storage.reflink:ReflinkPool',
                'linux-kernel = vanir.storage.kernels:LinuxKernel',
                'lvm_thin = vanir.storage.lvm:ThinPool',
            ],
            'vanir.tests.storage': [
                'test = vanir.tests.storage:TestPool',
                'file = vanir.storage.file:FilePool',
                'file-reflink = vanir.storage.reflink:ReflinkPool',
                'linux-kernel = vanir.storage.kernels:LinuxKernel',
                'lvm_thin = vanir.storage.lvm:ThinPool',
            ],
        })