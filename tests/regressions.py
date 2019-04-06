import multiprocessing
import os
import time
import unittest

import vanir.vanir
import vanir.tests
import subprocess


class TC_00_Regressions(vanir.tests.SystemTestsMixin, vanir.tests.VanirTestCase):
    # Bug: #906
    def test_000_bug_906_db_locking(self):
        def create_vm(vmname):
            qc = vanir.vanir.VanirVmCollection()
            qc.lock_db_for_writing()
            qc.load()
            time.sleep(1)
            qc.add_new_vm('VanirAppVm',
                name=vmname, template=qc.get_default_template())
            qc.save()
            qc.unlock_db()

        vmname1, vmname2 = map(self.make_vm_name, ('test1', 'test2'))
        t = multiprocessing.Process(target=create_vm, args=(vmname1,))
        t.start()
        create_vm(vmname2)
        t.join()

        qc = vanir.vanir.VanirVmCollection()
        qc.lock_db_for_reading()
        qc.load()
        qc.unlock_db()

        self.assertIsNotNone(qc.get_vm_by_name(vmname1))
        self.assertIsNotNone(qc.get_vm_by_name(vmname2))

    def test_bug_1389_dispvm_vanirdb_crash(self):
        """
        Sometimes VanirDB instance in DispVM crashes at startup.
        Unfortunately we don't have reliable way to reproduce it, so try twice
        :return:
        """
        self.qc.unlock_db()
        for try_no in xrange(2):
            p = subprocess.Popen(['/usr/lib/vanir/qfile-daemon-dvm',
                                  'vanir.VMShell', 'dom0', 'DEFAULT'],
                                 stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 stderr=open(os.devnull, 'w'))
            p.stdin.write("vanirdb-read /name || echo ERROR\n")
            dispvm_name = p.stdout.readline()
            p.stdin.close()
            self.assertTrue(dispvm_name.startswith("disp"),
                                 "Try {} failed".format(try_no))