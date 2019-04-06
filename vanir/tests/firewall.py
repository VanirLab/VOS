import datetime
import os

import asyncio
import lxml.etree
import unittest

import vanir.firewall
import vanir.tests


class TestOption(vanir.firewall.RuleChoice):
    opt1 = 'opt1'
    opt2 = 'opt2'
    another = 'another'

class TestVMM(object):
    def __init__(self):
        self.offline_mode = True


class TestApp(object):
    def __init__(self):
        self.vmm = TestVMM()


class TestVM(object):
    def __init__(self):
        self.firewall_conf = 'test-firewall.xml'
        self.dir_path = '/tmp'
        self.app = TestApp()

    def fire_event(self, event):
        pass

# noinspection PyPep8Naming
class TC_00_RuleChoice(vanir.tests.VanirTestCase):
    def test_000_accept_allowed(self):
        with self.assertNotRaises(ValueError):
            TestOption('opt1')
            TestOption('opt2')
            TestOption('another')

    def test_001_value_list(self):
        instance = TestOption('opt1')
        self.assertEqual(
            set(instance.allowed_values), {'opt1', 'opt2', 'another'})

    def test_010_reject_others(self):
        self.assertRaises(ValueError, lambda: TestOption('invalid'))


class TC_01_Action(vanir.tests.VanirTestCase):
    def test_000_allowed_values(self):
        with self.assertNotRaises(ValueError):
            instance = vanir.firewall.Action('accept')
        self.assertEqual(
            set(instance.allowed_values), {'accept', 'drop'})

    def test_001_rule(self):
        instance = vanir.firewall.Action('accept')
        self.assertEqual(instance.rule, 'action=accept')
        self.assertEqual(instance.api_rule, 'action=accept')


# noinspection PyPep8Naming
class TC_02_Proto(vanir.tests.VanirTestCase):
    def test_000_allowed_values(self):
        with self.assertNotRaises(ValueError):
            instance = vanir.firewall.Proto('tcp')
        self.assertEqual(
            set(instance.allowed_values), {'tcp', 'udp', 'icmp'})

    def test_001_rule(self):
        instance = vanir.firewall.Proto('tcp')
        self.assertEqual(instance.rule, 'proto=tcp')
        self.assertEqual(instance.api_rule, 'proto=tcp')


# noinspection PyPep8Naming
class TC_02_DstHost(vanir.tests.VanirTestCase):
    def test_000_hostname(self):
        with self.assertNotRaises(ValueError):
            instance = vanir.firewall.DstHost('vanir-os.org')
        self.assertEqual(instance.type, 'dsthost')

    def test_001_ipv4(self):
        with self.assertNotRaises(ValueError):
            instance = vanir.firewall.DstHost('127.0.0.1')
        self.assertEqual(instance.type, 'dst4')
        self.assertEqual(instance.prefixlen, 32)
        self.assertEqual(str(instance), '127.0.0.1/32')
        self.assertEqual(instance.rule, 'dst4=127.0.0.1/32')

    def test_002_ipv4_prefixlen(self):
        with self.assertNotRaises(ValueError):
            instance = vanir.firewall.DstHost('127.0.0.0', 8)
        self.assertEqual(instance.type, 'dst4')
        self.assertEqual(instance.prefixlen, 8)
        self.assertEqual(str(instance), '127.0.0.0/8')
        self.assertEqual(instance.rule, 'dst4=127.0.0.0/8')

    def test_003_ipv4_parse_prefixlen(self):
        with self.assertNotRaises(ValueError):
            instance = vanir.firewall.DstHost('127.0.0.0/8')
        self.assertEqual(instance.type, 'dst4')
        self.assertEqual(instance.prefixlen, 8)
        self.assertEqual(str(instance), '127.0.0.0/8')
        self.assertEqual(instance.rule, 'dst4=127.0.0.0/8')

    def test_004_ipv4_invalid_prefix(self):
        with self.assertRaises(ValueError):
            vanir.firewall.DstHost('127.0.0.0/33')
        with self.assertRaises(ValueError):
            vanir.firewall.DstHost('127.0.0.0', 33)
        with self.assertRaises(ValueError):
            vanir.firewall.DstHost('127.0.0.0/-1')

    def test_005_ipv4_reject_shortened(self):
        # not strictly required, but ppl are used to it
        with self.assertRaises(ValueError):
            vanir.firewall.DstHost('127/8')

    def test_006_ipv4_invalid_addr(self):
        with self.assertRaises(ValueError):
            vanir.firewall.DstHost('137.327.0.0/16')
        with self.assertRaises(ValueError):
            vanir.firewall.DstHost('1.2.3.4.5/32')

    @unittest.expectedFailure
    def test_007_ipv4_invalid_network(self):
        with self.assertRaises(ValueError):
            vanir.firewall.DstHost('127.0.0.1/32')

    def test_010_ipv6(self):
        with self.assertNotRaises(ValueError):
            instance = vanir.firewall.DstHost('2001:abcd:efab::3')
        self.assertEqual(instance.type, 'dst6')
        self.assertEqual(instance.prefixlen, 128)
        self.assertEqual(str(instance), '2001:abcd:efab::3/128')
        self.assertEqual(instance.rule, 'dst6=2001:abcd:efab::3/128')
        self.assertEqual(instance.api_rule, 'dst6=2001:abcd:efab::3/128')

    def test_011_ipv6_prefixlen(self):
        with self.assertNotRaises(ValueError):
            instance = vanir.firewall.DstHost('2001:abcd:efab::', 64)
        self.assertEqual(instance.type, 'dst6')
        self.assertEqual(instance.prefixlen, 64)
        self.assertEqual(str(instance), '2001:abcd:efab::/64')
        self.assertEqual(instance.rule, 'dst6=2001:abcd:efab::/64')
        self.assertEqual(instance.api_rule, 'dst6=2001:abcd:efab::/64')

    def test_012_ipv6_parse_prefixlen(self):
        with self.assertNotRaises(ValueError):
            instance = vanir.firewall.DstHost('2001:abcd:efab::/64')
        self.assertEqual(instance.type, 'dst6')
        self.assertEqual(instance.prefixlen, 64)
        self.assertEqual(str(instance), '2001:abcd:efab::/64')
        self.assertEqual(instance.rule, 'dst6=2001:abcd:efab::/64')
        self.assertEqual(instance.api_rule, 'dst6=2001:abcd:efab::/64')

    def test_013_ipv6_invalid_prefix(self):
        with self.assertRaises(ValueError):
            vanir.firewall.DstHost('2001:abcd:efab::3/129')
        with self.assertRaises(ValueError):
            vanir.firewall.DstHost('2001:abcd:efab::3', 129)
        with self.assertRaises(ValueError):
            vanir.firewall.DstHost('2001:abcd:efab::3/-1')

    def test_014_ipv6_invalid_addr(self):
        with self.assertRaises(ValueError):
            vanir.firewall.DstHost('2001:abcd:efab0123::3/128')
        with self.assertRaises(ValueError):
            vanir.firewall.DstHost('2001:abcd:efab:3/128')
        with self.assertRaises(ValueError):
            vanir.firewall.DstHost('2001:abcd:efab:a:a:a:a:a:a:3/128')
        with self.assertRaises(ValueError):
            vanir.firewall.DstHost('2001:abcd:efgh::3/128')

    @unittest.expectedFailure
    def test_015_ipv6_invalid_network(self):
        with self.assertRaises(ValueError):
            vanir.firewall.DstHost('2001:abcd:efab::3/64')

    def test_020_invalid_hostname(self):
        with self.assertRaises(ValueError):
            vanir.firewall.DstHost('www  vanir-os.org')
        with self.assertRaises(ValueError):
            vanir.firewall.DstHost('https://vanir-os.org')

class TC_03_DstPorts(vanir.tests.VanirTestCase):
    def test_000_single_str(self):
        with self.assertNotRaises(ValueError):
            instance = vanir.firewall.DstPorts('80')
        self.assertEqual(str(instance), '80')
        self.assertEqual(instance.range, [80, 80])
        self.assertEqual(instance.rule, 'dstports=80-80')
        self.assertEqual(instance.api_rule, 'dstports=80-80')

    def test_001_single_int(self):
        with self.assertNotRaises(ValueError):
            instance = vanir.firewall.DstPorts(80)
        self.assertEqual(str(instance), '80')
        self.assertEqual(instance.range, [80, 80])
        self.assertEqual(instance.rule, 'dstports=80-80')
        self.assertEqual(instance.api_rule, 'dstports=80-80')

    def test_002_range(self):
        with self.assertNotRaises(ValueError):
            instance = vanir.firewall.DstPorts('80-90')
        self.assertEqual(str(instance), '80-90')
        self.assertEqual(instance.range, [80, 90])
        self.assertEqual(instance.rule, 'dstports=80-90')

    def test_003_invalid(self):
        with self.assertRaises(ValueError):
            vanir.firewall.DstPorts('80-90-100')
        with self.assertRaises(ValueError):
            vanir.firewall.DstPorts('abcdef')
        with self.assertRaises(ValueError):
            vanir.firewall.DstPorts('80 90')
        with self.assertRaises(ValueError):
            vanir.firewall.DstPorts('')

    def test_004_reversed_range(self):
        with self.assertRaises(ValueError):
            vanir.firewall.DstPorts('100-20')

    def test_005_out_of_range(self):
        with self.assertRaises(ValueError):
            vanir.firewall.DstPorts('1000000000000')
        with self.assertRaises(ValueError):
            vanir.firewall.DstPorts(1000000000000)
        with self.assertRaises(ValueError):
            vanir.firewall.DstPorts('1-1000000000000')


class TC_04_IcmpType(vanir.tests.VanirTestCase):
    def test_000_number(self):
        with self.assertNotRaises(ValueError):
            instance = vanir.firewall.IcmpType(8)
        self.assertEqual(str(instance), '8')
        self.assertEqual(instance.rule, 'icmptype=8')

    def test_001_str(self):
        with self.assertNotRaises(ValueError):
            instance = vanir.firewall.IcmpType('8')
        self.assertEqual(str(instance), '8')
        self.assertEqual(instance.rule, 'icmptype=8')
        self.assertEqual(instance.api_rule, 'icmptype=8')

    def test_002_invalid(self):
        with self.assertRaises(ValueError):
            vanir.firewall.IcmpType(600)
        with self.assertRaises(ValueError):
            vanir.firewall.IcmpType(-1)
        with self.assertRaises(ValueError):
            vanir.firewall.IcmpType('abcde')
        with self.assertRaises(ValueError):
            vanir.firewall.IcmpType('')


class TC_05_SpecialTarget(vanir.tests.VanirTestCase):
    def test_000_allowed_values(self):
        with self.assertNotRaises(ValueError):
            instance = vanir.firewall.SpecialTarget('dns')
        self.assertEqual(
            set(instance.allowed_values), {'dns'})

    def test_001_rule(self):
        instance = vanir.firewall.SpecialTarget('dns')
        self.assertEqual(instance.rule, 'specialtarget=dns')
        self.assertEqual(instance.api_rule, 'specialtarget=dns')


class TC_06_Expire(vanir.tests.VanirTestCase):
    def test_000_number(self):
        with self.assertNotRaises(ValueError):
            instance = vanir.firewall.Expire(1463292452)
        self.assertEqual(str(instance), '1463292452')
        self.assertEqual(instance.api_rule, 'expire=1463292452')
        self.assertEqual(instance.datetime,
            datetime.datetime.fromtimestamp(1463292452))
        self.assertIsNone(instance.rule)

    def test_001_str(self):
        with self.assertNotRaises(ValueError):
            instance = vanir.firewall.Expire('1463292452')
        self.assertEqual(str(instance), '1463292452')
        self.assertEqual(instance.datetime,
            datetime.datetime.fromtimestamp(1463292452))
        self.assertIsNone(instance.rule)

    def test_002_invalid(self):
        with self.assertRaises(ValueError):
            vanir.firewall.Expire('abcdef')
        with self.assertRaises(ValueError):
            vanir.firewall.Expire('')

    def test_003_expired(self):
        with self.assertNotRaises(ValueError):
            instance = vanir.firewall.Expire('1463292452')
        self.assertTrue(instance.expired)
        with self.assertNotRaises(ValueError):
            instance = vanir.firewall.Expire('1583292452')
        self.assertFalse(instance.expired)


class TC_07_Comment(vanir.tests.VanirTestCase):
    def test_000_str(self):
        with self.assertNotRaises(ValueError):
            instance = vanir.firewall.Comment('Some comment')
        self.assertEqual(str(instance), 'Some comment')
        self.assertEqual(instance.api_rule, 'comment=Some comment')
        self.assertIsNone(instance.rule)


class TC_08_Rule(vanir.tests.VanirTestCase):
    def test_000_simple(self):
        with self.assertNotRaises(ValueError):
            rule = vanir.firewall.Rule(None, action='accept', proto='icmp')
        self.assertEqual(rule.rule, 'action=accept proto=icmp')
        self.assertIsNone(rule.dsthost)
        self.assertIsNone(rule.dstports)
        self.assertIsNone(rule.icmptype)
        self.assertIsNone(rule.comment)
        self.assertIsNone(rule.expire)
        self.assertEqual(str(rule.action), 'accept')
        self.assertEqual(str(rule.proto), 'icmp')

    def test_001_expire(self):
        with self.assertNotRaises(ValueError):
            rule = vanir.firewall.Rule(None, action='accept', proto='icmp',
                expire='1463292452')
        self.assertIsNone(rule.rule)

        with self.assertNotRaises(ValueError):
            rule = vanir.firewall.Rule(None, action='accept', proto='icmp',
                expire='1663292452')
        self.assertIsNotNone(rule.rule)


    def test_002_dstports(self):
        with self.assertNotRaises(ValueError):
            rule = vanir.firewall.Rule(None, action='accept', proto='tcp',
                dstports=80)
        self.assertEqual(str(rule.dstports), '80')
        with self.assertNotRaises(ValueError):
            rule = vanir.firewall.Rule(None, action='accept', proto='udp',
                dstports=80)
        self.assertEqual(str(rule.dstports), '80')

    def test_003_reject_invalid(self):
        with self.assertRaises((ValueError, AssertionError)):
            # missing action
            vanir.firewall.Rule(None, proto='icmp')
        with self.assertRaises(ValueError):
            # not proto=tcp or proto=udp for dstports
            vanir.firewall.Rule(None, action='accept', proto='icmp',
                dstports=80)
        with self.assertRaises(ValueError):
            # not proto=tcp or proto=udp for dstports
            vanir.firewall.Rule(None, action='accept', dstports=80)
        with self.assertRaises(ValueError):
            # not proto=icmp for icmptype
            vanir.firewall.Rule(None, action='accept', proto='tcp',
                icmptype=8)
        with self.assertRaises(ValueError):
            # not proto=icmp for icmptype
            vanir.firewall.Rule(None, action='accept', icmptype=8)

    def test_004_proto_change(self):
        rule = vanir.firewall.Rule(None, action='accept', proto='tcp')
        with self.assertNotRaises(ValueError):
            rule.proto = 'udp'
        self.assertEqual(rule.rule, 'action=accept proto=udp')
        rule = vanir.firewall.Rule(None, action='accept', proto='tcp',
            dstports=80)
        with self.assertNotRaises(ValueError):
            rule.proto = 'udp'
        self.assertEqual(rule.rule, 'action=accept proto=udp dstports=80-80')
        rule = vanir.firewall.Rule(None, action='accept')
        with self.assertNotRaises(ValueError):
            rule.proto = 'udp'
        self.assertEqual(rule.rule, 'action=accept proto=udp')
        with self.assertNotRaises(ValueError):
            rule.dstports = 80
        self.assertEqual(rule.rule, 'action=accept proto=udp dstports=80-80')
        with self.assertNotRaises(ValueError):
            rule.proto = 'icmp'
        self.assertEqual(rule.rule, 'action=accept proto=icmp')
        self.assertIsNone(rule.dstports)
        rule.icmptype = 8
        self.assertEqual(rule.rule, 'action=accept proto=icmp icmptype=8')
        with self.assertNotRaises(ValueError):
            rule.proto = vanir.property.DEFAULT
        self.assertEqual(rule.rule, 'action=accept')
        self.assertIsNone(rule.dstports)

    def test_005_from_xml_v1(self):
        xml_txt = \
            '<rule address="192.168.0.0" proto="tcp" netmask="24" port="443"/>'
        with self.assertNotRaises(ValueError):
            rule = vanir.firewall.Rule.from_xml_v1(
                lxml.etree.fromstring(xml_txt), 'accept')
        self.assertEqual(rule.dsthost, '192.168.0.0/24')
        self.assertEqual(rule.proto, 'tcp')
        self.assertEqual(rule.dstports, '443')
        self.assertIsNone(rule.expire)
        self.assertIsNone(rule.comment)

    def test_006_from_xml_v1(self):
        xml_txt = \
            '<rule address="vanir-os.org" proto="tcp" ' \
            'port="443" toport="1024"/>'
        with self.assertNotRaises(ValueError):
            rule = vanir.firewall.Rule.from_xml_v1(
                lxml.etree.fromstring(xml_txt), 'drop')
        self.assertEqual(rule.dsthost, 'vanir-os.org')
        self.assertEqual(rule.proto, 'tcp')
        self.assertEqual(rule.dstports, '443-1024')
        self.assertEqual(rule.action, 'drop')
        self.assertIsNone(rule.expire)
        self.assertIsNone(rule.comment)

    def test_007_from_xml_v1(self):
        xml_txt = \
            '<rule address="192.168.0.0" netmask="24" expire="1463292452"/>'
        with self.assertNotRaises(ValueError):
            rule = vanir.firewall.Rule.from_xml_v1(
                lxml.etree.fromstring(xml_txt), 'accept')
        self.assertEqual(rule.dsthost, '192.168.0.0/24')
        self.assertEqual(rule.expire, '1463292452')
        self.assertEqual(rule.action, 'accept')
        self.assertIsNone(rule.proto)
        self.assertIsNone(rule.dstports)

    def test_008_from_api_string(self):
        rule_txt = 'action=drop proto=tcp dstports=80-80'
        with self.assertNotRaises(ValueError):
            rule = vanir.firewall.Rule.from_api_string(
                rule_txt)
        self.assertEqual(rule.dstports.range, [80, 80])
        self.assertEqual(rule.proto, 'tcp')
        self.assertEqual(rule.action, 'drop')
        self.assertIsNone(rule.dsthost)
        self.assertIsNone(rule.expire)
        self.assertIsNone(rule.comment)
        self.assertEqual(rule.api_rule, rule_txt)

    def test_009_from_api_string(self):
        rule_txt = 'action=accept expire=2063292452 proto=tcp ' \
                   'comment=Some comment, with spaces'
        with self.assertNotRaises(ValueError):
            rule = vanir.firewall.Rule.from_api_string(
                rule_txt)
        self.assertEqual(rule.comment, 'Some comment, with spaces')
        self.assertEqual(rule.proto, 'tcp')
        self.assertEqual(rule.action, 'accept')
        self.assertEqual(rule.expire, '2063292452')
        self.assertIsNone(rule.dstports)
        self.assertIsNone(rule.dsthost)
        self.assertEqual(rule.api_rule, rule_txt)


class TC_10_Firewall(vanir.tests.VanirTestCase):
    def setUp(self):
        super(TC_10_Firewall, self).setUp()
        self.vm = TestVM()
        firewall_path = os.path.join('/tmp', self.vm.firewall_conf)
        if os.path.exists(firewall_path):
            os.unlink(firewall_path)

    def tearDown(self):
        firewall_path = os.path.join('/tmp', self.vm.firewall_conf)
        if os.path.exists(firewall_path):
            os.unlink(firewall_path)
        return super(TC_10_Firewall, self).tearDown()

    def test_000_defaults(self):
        fw = vanir.firewall.Firewall(self.vm, False)
        fw.load_defaults()
        self.assertEqual(fw.policy, 'drop')
        self.assertEqual(fw.rules, [vanir.firewall.Rule(None, action='accept')])

    def test_001_save_load_empty(self):
        fw = vanir.firewall.Firewall(self.vm, True)
        self.assertEqual(fw.policy, 'drop')
        self.assertEqual(fw.rules, [vanir.firewall.Rule(None, action='accept')])
        fw.save()
        fw.load()
        self.assertEqual(fw.policy, 'drop')
        self.assertEqual(fw.rules, [vanir.firewall.Rule(None, action='accept')])

    def test_002_save_load_rules(self):
        fw = vanir.firewall.Firewall(self.vm, True)
        rules = [
            vanir.firewall.Rule(None, action='drop', proto='icmp'),
            vanir.firewall.Rule(None, action='drop', proto='tcp', dstports=80),
            vanir.firewall.Rule(None, action='accept', proto='udp',
                dstports=67),
            vanir.firewall.Rule(None, action='accept', specialtarget='dns'),
            ]
        fw.rules.extend(rules)
        fw.save()
        self.assertTrue(os.path.exists(os.path.join(
            self.vm.dir_path, self.vm.firewall_conf)))
        fw = vanir.firewall.Firewall(TestVM(), True)
        self.assertEqual(fw.policy, vanir.firewall.Action.drop)
        self.assertEqual(fw.rules,
            [vanir.firewall.Rule(None, action='accept')] + rules)

    def test_003_load_v1(self):
        xml_txt = """<QubesFirewallRules dns="allow" icmp="allow"
        policy="deny" yumProxy="allow">
            <rule address="192.168.0.0" proto="tcp" netmask="24" port="80"/>
            <rule address="vanir-os.org" proto="tcp" port="443"/>
        </QubesFirewallRules>
        """
        with open(os.path.join('/tmp', self.vm.firewall_conf), 'w') as f:
            f.write(xml_txt)
        with self.assertNotRaises(ValueError):
            fw = vanir.firewall.Firewall(self.vm)
        self.assertEqual(str(fw.policy), 'drop')
        rules = [
            vanir.firewall.Rule(None, action='accept', specialtarget='dns'),
            vanir.firewall.Rule(None, action='accept', proto='icmp'),
            vanir.firewall.Rule(None, action='accept', proto='tcp',
                dsthost='192.168.0.0/24', dstports='80'),
            vanir.firewall.Rule(None, action='accept', proto='tcp',
                dsthost='vanir-os.org', dstports='443')
        ]
        self.assertEqual(fw.rules, rules)

    def test_004_save_skip_expired(self):
        fw = vanir.firewall.Firewall(self.vm, True)
        rules = [
            vanir.firewall.Rule(None, action='drop', proto='icmp'),
            vanir.firewall.Rule(None, action='drop', proto='tcp', dstports=80),
            vanir.firewall.Rule(None, action='accept', proto='udp',
                dstports=67, expire=1373300257),
            vanir.firewall.Rule(None, action='accept', specialtarget='dns'),
            ]
        fw.rules = rules
        fw.save()
        rules.pop(2)
        fw = vanir.firewall.Firewall(self.vm, True)
        self.assertEqual(fw.rules, rules)

    def test_005_qdb_entries(self):
        fw = vanir.firewall.Firewall(self.vm, True)
        rules = [
            vanir.firewall.Rule(None, action='drop', proto='icmp'),
            vanir.firewall.Rule(None, action='drop', proto='tcp', dstports=80),
            vanir.firewall.Rule(None, action='accept', proto='udp'),
            vanir.firewall.Rule(None, action='accept', specialtarget='dns'),
        ]
        fw.rules = rules
        expected_qdb_entries = {
            'policy': 'drop',
            '0000': 'action=drop proto=icmp',
            '0001': 'action=drop proto=tcp dstports=80-80',
            '0002': 'action=accept proto=udp',
            '0003': 'action=accept specialtarget=dns',
        }
        self.assertEqual(fw.qdb_entries(), expected_qdb_entries)

    def test_006_auto_expire_rules(self):
        fw = vanir.firewall.Firewall(self.vm, True)
        rules = [
            vanir.firewall.Rule(None, action='drop', proto='icmp'),
            vanir.firewall.Rule(None, action='drop', proto='tcp', dstports=80),
            vanir.firewall.Rule(None, action='accept', proto='udp',
                dstports=67, expire=self.loop.time() + 5),
            vanir.firewall.Rule(None, action='accept', specialtarget='dns'),
        ]
        fw.rules = rules
        fw.save()
        self.assertEqual(fw.rules, rules)
        self.loop.run_until_complete(asyncio.sleep(3))
        # still old rules should be there
        self.assertEqual(fw.rules, rules)

        rules.pop(2)
        self.loop.run_until_complete(asyncio.sleep(3))
        # expect new rules
        self.assertEqual(fw.rules, rules)