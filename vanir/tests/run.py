import argparse
import code
import curses
import itertools
import logging
import logging.handlers
import os
import socket
import subprocess
import sys
import unittest
import unittest.signals

import vanir.tests
import vanir.api.admin

class CursesColor(dict):
    colors = (
        'black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white')
    attrs = {
        'bold': 'bold', 'normal': 'sgr0'}
    def __init__(self):
        super(CursesColor, self).__init__()
        self.has_colors = False
        try:
            curses.setupterm()
            self.has_colors = True
        except curses.error:
            return


    def __missing__(self, key):
        # pylint: disable=unused-argument,no-self-use
        if not self.has_colors:
            return ''

        try:
            value = curses.tigetstr(self.attrs[key])
        except KeyError:
            try:
                value = curses.tparm(
                    curses.tigetstr('setaf'), self.colors.index(key))
            except ValueError:
                return ''

        value = value.decode()
        self[key] = value
        return value


class VanirTestResult(unittest.TestResult):
    '''A test result class that can print colourful text results to a stream.

    Used by TextTestRunner. This is a lightly rewritten unittest.TextTestResult.
    '''

    separator1 = unittest.TextTestResult.separator1
    separator2 = unittest.TextTestResult.separator2

    def __init__(self, stream, descriptions, verbosity):
        super(VanirTestResult, self).__init__(stream, descriptions, verbosity)
        self.stream = stream
        self.showAll = verbosity > 1 # pylint: disable=invalid-name
        self.dots = verbosity == 1
        self.descriptions = descriptions

        self.color = CursesColor()
        self.hostname = socket.gethostname()

        self.log = logging.getLogger('vanir.tests')


    def _fmtexc(self, err):
        if str(err[1]):
            return '{color[bold]}{}:{color[normal]} {!s}'.format(
                err[0].__name__, err[1], color=self.color)
        else:
            return '{color[bold]}{}{color[normal]}'.format(
                err[0].__name__, color=self.color)

    def get_log(self, test):
        try:
            return test.log
        except AttributeError:
            return self.log

    def getDescription(self, test): # pylint: disable=invalid-name
        teststr = str(test).split('/')
        for i in range(-2, 0):
            try:
                fullname = teststr[i].split('_', 2)
            except IndexError:
                continue
            fullname[-1] = '{color[bold]}{}{color[normal]}'.format(
                fullname[-1], color=self.color)
            teststr[i] = '_'.join(fullname)
        teststr = '/'.join(teststr)

        doc_first_line = test.shortDescription()
        if self.descriptions and doc_first_line:
            return '\n'.join((teststr, '  {}'.format(
                doc_first_line, color=self.color)))
        else:
            return teststr

    def startTest(self, test): # pylint: disable=invalid-name
        super(VanirTestResult, self).startTest(test)
        self.get_log(test).critical('started')
        if self.showAll:
            if not vanir.tests.in_git:
                self.stream.write('{}: '.format(self.hostname))
            self.stream.write(self.getDescription(test))
            self.stream.write(' ... ')
            self.stream.flush()

    def addSuccess(self, test): # pylint: disable=invalid-name
        super(VanirTestResult, self).addSuccess(test)
        self.get_log(test).warning('ok')
        if self.showAll:
            self.stream.writeln('{color[green]}ok{color[normal]}'.format(
                color=self.color))
        elif self.dots:
            self.stream.write('.')
            self.stream.flush()

    def addError(self, test, err): # pylint: disable=invalid-name
        super(VanirTestResult, self).addError(test, err)
        self.get_log(test).critical(
            'ERROR ({err[0].__name__}: {err[1]!r})'.format(err=err))
        if self.showAll:
            self.stream.writeln(
                '{color[red]}{color[bold]}ERROR{color[normal]} ({})'.format(
                    self._fmtexc(err), color=self.color))
        elif self.dots:
            self.stream.write(
                '{color[red]}{color[bold]}E{color[normal]}'.format(
                    color=self.color))
            self.stream.flush()

    def addFailure(self, test, err): # pylint: disable=invalid-name
        super(VanirTestResult, self).addFailure(test, err)
        self.get_log(test).error(
            'FAIL ({err[0].__name__}: {err[1]!r})'.format(err=err))
        if self.showAll:
            self.stream.writeln('{color[red]}FAIL{color[normal]}'.format(
                color=self.color))
        elif self.dots:
            self.stream.write('{color[red]}F{color[normal]}'.format(
                color=self.color))
            self.stream.flush()

    def addSkip(self, test, reason): # pylint: disable=invalid-name
        super(VanirTestResult, self).addSkip(test, reason)
        self.get_log(test).warning('skipped ({})'.format(reason))
        if self.showAll:
            self.stream.writeln(
                '{color[cyan]}skipped{color[normal]} ({})'.format(
                    reason, color=self.color))
        elif self.dots:
            self.stream.write('{color[cyan]}s{color[normal]}'.format(
                color=self.color))
            self.stream.flush()

    def addExpectedFailure(self, test, err): # pylint: disable=invalid-name
        super(VanirTestResult, self).addExpectedFailure(test, err)
        self.get_log(test).warning('expected failure')
        if self.showAll:
            self.stream.writeln(
                '{color[yellow]}expected failure{color[normal]}'.format(
                    color=self.color))
        elif self.dots:
            self.stream.write('{color[yellow]}x{color[normal]}'.format(
                color=self.color))
            self.stream.flush()

    def addUnexpectedSuccess(self, test): # pylint: disable=invalid-name
        super(VanirTestResult, self).addUnexpectedSuccess(test)
        self.get_log(test).error('unexpected success')
        if self.showAll:
            self.stream.writeln(
                '{color[yellow]}{color[bold]}unexpected success'
                    '{color[normal]}'.format(color=self.color))
        elif self.dots:
            self.stream.write(
                '{color[yellow]}{color[bold]}u{color[normal]}'.format(
                    color=self.color))
            self.stream.flush()

    def printErrors(self): # pylint: disable=invalid-name
        if self.dots or self.showAll:
            self.stream.writeln()
        self.printErrorList(
            '{color[red]}{color[bold]}ERROR{color[normal]}'.format(
                color=self.color),
            self.errors)
        self.printErrorList(
            '{color[red]}FAIL{color[normal]}'.format(
                color=self.color),
            self.failures)
        self.printErrorList(
            '{color[yellow]}EXPECTED{color[normal]}'.format(
                color=self.color),
            self.expectedFailures)

    def printErrorList(self, flavour, errors): # pylint: disable=invalid-name
        for test, err in errors:
            self.stream.writeln(self.separator1)
            self.stream.writeln('%s: %s' % (flavour, self.getDescription(test)))
            self.stream.writeln(self.separator2)
            self.stream.writeln('%s' % err)


def demo(verbosity=2):
    class TC_00_Demo(vanir.tests.QubesTestCase):
        '''Demo class'''
        # pylint: disable=no-self-use
        def test_0_success(self):
            '''Demo test (success)'''
            pass
        def test_1_error(self):
            '''Demo test (error)'''
            raise Exception()
        def test_2_failure(self):
            '''Demo test (failure)'''
            self.fail('boo')
        def test_3_skip(self):
            '''Demo test (skipped by call to self.skipTest())'''
            self.skipTest('skip')
        @unittest.skip(None)
        def test_4_skip_decorator(self):
            '''Demo test (skipped by decorator)'''
            pass
        @unittest.expectedFailure
        def test_5_expected_failure(self):
            '''Demo test (expected failure)'''
            self.fail()
        @unittest.expectedFailure
        def test_6_unexpected_success(self):
            '''Demo test (unexpected success)'''
            pass

    suite = unittest.TestLoader().loadTestsFromTestCase(TC_00_Demo)
    runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=verbosity)
    runner.resultclass = VanirTestResult
    return runner.run(suite).wasSuccessful()


parser = argparse.ArgumentParser(
    epilog='''When running only specific tests, write their names like in log,
        in format: MODULE+"/"+CLASS+"/"+FUNCTION. MODULE should omit initial
        "vanir.tests.". Example: basic/TC_00_Basic/test_000_create''')

parser.add_argument('--verbose', '-v',
    action='count',
    help='increase console verbosity level')
parser.add_argument('--quiet', '-q',
    action='count',
    help='decrease console verbosity level')

parser.add_argument('--list', '-l',
    action='store_true', dest='list',
    help='list all available tests and exit')

parser.add_argument('--failfast', '-f',
    action='store_true', dest='failfast',
    help='stop on the first fail, error or unexpected success')
parser.add_argument('--no-failfast',
    action='store_false', dest='failfast',
    help='disable --failfast')

# pylint: disable=protected-access
try:
    name_to_level = logging._nameToLevel
except AttributeError:
    name_to_level = logging._levelNames
parser.add_argument('--loglevel', '-L', metavar='LEVEL',
    action='store', choices=tuple(k
        for k in sorted(name_to_level.keys(),
            key=lambda x: name_to_level[x])
        if isinstance(k, str)),
    help='logging level for file and syslog forwarding '
        '(one of: %(choices)s; default: %(default)s)')
del name_to_level
# pylint: enable=protected-access

parser.add_argument('--logfile', '-o', metavar='FILE',
    action='store',
    help='if set, test run will be also logged to file')

parser.add_argument('--syslog',
    action='store_true', dest='syslog',
    help='reenable logging to syslog')
parser.add_argument('--no-syslog',
    action='store_false', dest='syslog',
    help='disable logging to syslog')

parser.add_argument('--kmsg', '--very-brave-or-very-stupid',
    action='store_true', dest='kmsg',
    help='log most important things to kernel ring-buffer')
parser.add_argument('--no-kmsg', '--i-am-smarter-than-kay-sievers',
    action='store_false', dest='kmsg',
    help='do not abuse kernel ring-buffer')

parser.add_argument('--allow-running-along-qubesd',
    action='store_true', default=False,
    help='allow running in parallel with qubesd;'
        ' this is DANGEROUS and WILL RESULT IN INCONSISTENT SYSTEM STATE')

parser.add_argument('--break-to-repl',
    action='store_true', default=False,
    help='break to REPL after tests')

parser.add_argument('names', metavar='TESTNAME',
    action='store', nargs='*',
    help='list of tests to run named like in description '
        '(default: run all tests)')

parser.set_defaults(
    failfast=False,
    loglevel='DEBUG',
    logfile=None,
    syslog=True,
    kmsg=False,
    verbose=2,
    quiet=0)


def list_test_cases(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            #yield from
            for i in list_test_cases(test):
                yield i
        else:
            yield test


def main(args=None):
    args = parser.parse_args(args)

    suite = unittest.TestSuite()
    loader = unittest.TestLoader()

    if args.names:
        alltests = loader.loadTestsFromName('vanir.tests')
        for name in args.names:
            suite.addTests(
                [test for test in list_test_cases(alltests)
                 if str(test).startswith(name)])
    else:
        suite.addTests(loader.loadTestsFromName('vanir.tests'))

    if args.list:
        for test in list_test_cases(suite):
            print(str(test)) # pylint: disable=superfluous-parens
        return True

    logging.root.setLevel(args.loglevel)

    if args.logfile is not None:
        ha_file = logging.FileHandler(
            os.path.join(os.environ['HOME'], args.logfile))
        ha_file.setFormatter(
            logging.Formatter('%(asctime)s %(name)s[%(process)d]: %(message)s'))
        logging.root.addHandler(ha_file)

    if args.syslog:
        ha_syslog = logging.handlers.SysLogHandler('/dev/log')
        ha_syslog.setFormatter(
            logging.Formatter('%(name)s[%(process)d]: %(message)s'))
        logging.root.addHandler(ha_syslog)

    if args.kmsg:
        try:
            subprocess.check_call(('sudo', 'chmod', '666', '/dev/kmsg'))
        except subprocess.CalledProcessError:
            parser.error('could not chmod /dev/kmsg')
        else:
            ha_kmsg = logging.FileHandler('/dev/kmsg', 'w')
            ha_kmsg.setFormatter(
                logging.Formatter('%(name)s[%(process)d]: %(message)s'))
            ha_kmsg.setLevel(logging.CRITICAL)
            logging.root.addHandler(ha_kmsg)

    if not args.allow_running_along_qubesd \
    and os.path.exists(vanir.api.admin.QubesAdminAPI.SOCKNAME):
        parser.error('refusing to run until qubesd is disabled')

    runner = unittest.TextTestRunner(stream=sys.stdout,
        verbosity=(args.verbose-args.quiet),
        failfast=args.failfast)
    unittest.signals.installHandler()
    runner.resultclass = VanirTestResult
    result = runner.run(suite)

    if args.break_to_repl:
        code.interact(local=locals())

    return result.wasSuccessful()


if __name__ == '__main__':
    sys.exit(not main())