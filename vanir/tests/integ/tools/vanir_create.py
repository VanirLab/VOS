import vanir
import vanir.tools.vanir_create

import vanir.tests

@vanir.tests.skipUnlessDom0
class TC_00_vanir_create(vanir.tests.SystemTestCase):
    def test_000_basic(self):
        self.assertEqual(0, vanir.tools.vanir_create.main([
            '--vanirxml', vanir.tests.XMLPATH]))

    def test_001_property(self):
        self.assertEqual(0, vanir.tools.vanir_create.main([
            '--vanirxml', vanir.tests.XMLPATH,
            '--property', 'default_kernel=testkernel']))

        self.assertEqual('testkernel',
            vanir.Vanir(vanir.tests.XMLPATH).default_kernel)
