from distutils import spawn

import asyncio
import subprocess
import sys
import time
import unittest

import vanir.tests
import vanir.firewall
import vanir.vm.vanirvm
import vanir.vm.appvm


# noinspection PyAttributeOutsideInit,PyPep8Naming
class VmNetworkingMixin(object):
    test_ip = '192.168.123.45'
    test_name = 'test.example.com'

    ping_cmd = 'ping -W 1 -n -c 1 {target}'
    ping_ip = ping_cmd.format(target=test_ip)
    ping_name = ping_cmd.format(target=test_name)

    # filled by load_tests
    template = None

    def run_cmd(self, vm, cmd, user="root"):
        '''Run a command *cmd* in a *vm* as *user*. Return its exit code.
        :type self: vanir.tests.SystemTestCase | VmNetworkingMixin
        :param vanir.vm.vanirvm.VanirVM vm: VM object to run command in
        :param str cmd: command to execute
        :param std user: user to execute command as
        :return int: command exit code
        '''
        try:
            self.loop.run_until_complete(vm.run_for_stdio(cmd, user=user))
        except subprocess.CalledProcessError as e:
            return e.returncode
        return 0

    def setUp(self):
        '''
        :type self: vanir.tests.SystemTestCase | VMNetworkingMixin
        '''
        super(VmNetworkingMixin, self).setUp()
        if self.template.startswith('whonix-'):
            self.skipTest("Test not supported here - Whonix uses its own "
                          "firewall settings")
        self.init_default_template(self.template)
        self.testnetvm = self.app.add_new_vm(vanir.vm.appvm.AppVM,
            name=self.make_vm_name('netvm1'),
            label='red')
        self.loop.run_until_complete(self.testnetvm.create_on_disk())
        self.testnetvm.provides_network = True
        self.testnetvm.netvm = None
        self.testvm1 = self.app.add_new_vm(vanir.vm.appvm.AppVM,
            name=self.make_vm_name('vm1'),
            label='red')
        self.loop.run_until_complete(self.testvm1.create_on_disk())
        self.testvm1.netvm = self.testnetvm
        self.app.save()

        self.configure_netvm()


    def configure_netvm(self):
        '''
        :type self: vanir.tests.SystemTestCase | VMNetworkingMixin
        '''
        def run_netvm_cmd(cmd):
            if self.run_cmd(self.testnetvm, cmd) != 0:
                self.fail("Command '%s' failed" % cmd)

        if not self.testnetvm.is_running():
            self.loop.run_until_complete(self.testnetvm.start())
        # Ensure that dnsmasq is installed:
        try:
            self.loop.run_until_complete(self.testnetvm.run_for_stdio(
                'dnsmasq --version', user='root'))
        except subprocess.CalledProcessError:
            self.skipTest("dnsmasq not installed")

        run_netvm_cmd("ip link add test0 type dummy")
        run_netvm_cmd("ip link set test0 up")
        run_netvm_cmd("ip addr add {}/24 dev test0".format(self.test_ip))
        run_netvm_cmd("iptables -I INPUT -d {} -j ACCEPT --wait".format(
            self.test_ip))
        # ignore failure
        self.run_cmd(self.testnetvm, "killall --wait dnsmasq")
        run_netvm_cmd("dnsmasq -a {ip} -A /{name}/{ip} -i test0 -z".format(
            ip=self.test_ip, name=self.test_name))
        run_netvm_cmd("echo nameserver {} > /etc/resolv.conf".format(
            self.test_ip))
        run_netvm_cmd("/usr/lib/vanir/vanir-setup-dnat-to-ns")


    def test_000_simple_networking(self):
        '''
        :type self: vanir.tests.SystemTestCase | VMNetworkingMixin
        '''
        self.loop.run_until_complete(self.testvm1.start())
        self.assertEqual(self.run_cmd(self.testvm1, self.ping_ip), 0)
        self.assertEqual(self.run_cmd(self.testvm1, self.ping_name), 0)


    def test_010_simple_proxyvm(self):
        '''
        :type self: vanir.tests.SystemTestCase | VMNetworkingMixin
        '''
        self.proxy = self.app.add_new_vm(vanir.vm.appvm.AppVM,
            name=self.make_vm_name('proxy'),
            label='red')
        self.proxy.provides_network = True
        self.proxy.netvm = self.testnetvm
        self.loop.run_until_complete(self.proxy.create_on_disk())
        self.testvm1.netvm = self.proxy
        self.app.save()

        self.loop.run_until_complete(self.testvm1.start())
        self.assertTrue(self.proxy.is_running())
        self.assertEqual(self.run_cmd(self.proxy, self.ping_ip), 0,
                         "Ping by IP from ProxyVM failed")
        self.assertEqual(self.run_cmd(self.proxy, self.ping_name), 0,
                         "Ping by name from ProxyVM failed")
        self.assertEqual(self.run_cmd(self.testvm1, self.ping_ip), 0,
                         "Ping by IP from AppVM failed")
        self.assertEqual(self.run_cmd(self.testvm1, self.ping_name), 0,
                         "Ping by IP from AppVM failed")


    @vanir.tests.expectedFailureIfTemplate('debian-7')
    @unittest.skipUnless(spawn.find_executable('xdotool'),
                         "xdotool not installed")
    def test_020_simple_proxyvm_nm(self):
        '''
        :type self: vanir.tests.SystemTestCase | VMNetworkingMixin
        '''
        self.proxy = self.app.add_new_vm(vanir.vm.appvm.AppVM,
            name=self.make_vm_name('proxy'),
            label='red')
        self.proxy.provides_network = True
        self.loop.run_until_complete(self.proxy.create_on_disk())
        self.proxy.netvm = self.testnetvm
        self.proxy.features['service.network-manager'] = True
        self.testvm1.netvm = self.proxy
        self.app.save()

        self.loop.run_until_complete(self.testvm1.start())
        self.assertTrue(self.proxy.is_running())
        self.assertEqual(self.run_cmd(self.testvm1, self.ping_ip), 0,
                         "Ping by IP failed")
        self.assertEqual(self.run_cmd(self.testvm1, self.ping_name), 0,
                         "Ping by name failed")

        # reconnect to make sure that device was configured by NM
        self.assertEqual(
            self.run_cmd(self.proxy, "nmcli device disconnect eth0",
                user="user"),
            0, "Failed to disconnect eth0 using nmcli")

        self.assertNotEqual(self.run_cmd(self.testvm1, self.ping_ip), 0,
            "Network should be disabled, but apparently it isn't")
        self.assertEqual(
            self.run_cmd(self.proxy,
                'nmcli connection up "VM uplink eth0" ifname eth0',
                user="user"),
            0, "Failed to connect eth0 using nmcli")
        self.assertEqual(self.run_cmd(self.proxy, "nm-online", user="user"), 0,
                         "Failed to wait for NM connection")

        # check for nm-applet presence
        self.assertEqual(subprocess.call([
            'xdotool', 'search', '--class', '{}:nm-applet'.format(
                self.proxy.name)],
            stdout=subprocess.DEVNULL), 0, "nm-applet window not found")
        self.assertEqual(self.run_cmd(self.testvm1, self.ping_ip), 0,
                         "Ping by IP failed (after NM reconnection")
        self.assertEqual(self.run_cmd(self.testvm1, self.ping_name), 0,
                         "Ping by name failed (after NM reconnection)")


    def test_030_firewallvm_firewall(self):
        '''
        :type self: vanir.tests.SystemTestCase | VMNetworkingMixin
        '''
        self.proxy = self.app.add_new_vm(vanir.vm.appvm.AppVM,
            name=self.make_vm_name('proxy'),
            label='red')
        self.proxy.provides_network = True
        self.loop.run_until_complete(self.proxy.create_on_disk())
        self.proxy.netvm = self.testnetvm
        self.testvm1.netvm = self.proxy
        self.app.save()

        # block all for first

        self.testvm1.firewall.rules = [vanir.firewall.Rule(action='drop')]
        self.testvm1.firewall.save()
        self.loop.run_until_complete(self.testvm1.start())
        self.assertTrue(self.proxy.is_running())

        server = self.loop.run_until_complete(self.testnetvm.run(
            'socat TCP-LISTEN:1234,fork EXEC:/bin/uname'))

        try:
            self.assertEqual(self.run_cmd(self.proxy, self.ping_ip), 0,
                            "Ping by IP from ProxyVM failed")
            self.assertEqual(self.run_cmd(self.proxy, self.ping_name), 0,
                            "Ping by name from ProxyVM failed")
            self.assertNotEqual(self.run_cmd(self.testvm1, self.ping_ip), 0,
                            "Ping by IP should be blocked")

            client_cmd = "socat TCP:{}:1234 -".format(self.test_ip)
            self.assertNotEqual(self.run_cmd(self.testvm1, client_cmd), 0,
                            "TCP connection should be blocked")

            # block all except ICMP

            self.testvm1.firewall.rules = [(
                vanir.firewall.Rule(None, action='accept', proto='icmp')
            )]
            self.testvm1.firewall.save()
            # Ugly hack b/c there is no feedback when the rules are actually
            # applied
            time.sleep(3)
            self.assertEqual(self.run_cmd(self.testvm1, self.ping_ip), 0,
                            "Ping by IP failed (should be allowed now)")
            self.assertNotEqual(self.run_cmd(self.testvm1, self.ping_name), 0,
                            "Ping by name should be blocked")

            # all TCP still blocked

            self.testvm1.firewall.rules = [
                vanir.firewall.Rule(None, action='accept', proto='icmp'),
                vanir.firewall.Rule(None, action='accept', specialtarget='dns'),
            ]
            self.testvm1.firewall.save()
            # Ugly hack b/c there is no feedback when the rules are actually
            # applied
            time.sleep(3)
            self.assertEqual(self.run_cmd(self.testvm1, self.ping_name), 0,
                            "Ping by name failed (should be allowed now)")
            self.assertNotEqual(self.run_cmd(self.testvm1, client_cmd), 0,
                            "TCP connection should be blocked")

            # block all except target

            self.testvm1.firewall.rules = [
                vanir.firewall.Rule(None, action='accept', dsthost=self.test_ip,
                    proto='tcp', dstports=1234),
            ]
            self.testvm1.firewall.save()

            # Ugly hack b/c there is no feedback when the rules are actually
            # applied
            time.sleep(3)
            self.assertEqual(self.run_cmd(self.testvm1, client_cmd), 0,
                            "TCP connection failed (should be allowed now)")

            # allow all except target

            self.testvm1.firewall.rules = [
                vanir.firewall.Rule(None, action='drop', dsthost=self.test_ip,
                    proto='tcp', dstports=1234),
                vanir.firewall.Rule(action='accept'),
            ]
            self.testvm1.firewall.save()

            # Ugly hack b/c there is no feedback when the rules are actually
            # applied
            time.sleep(3)
            self.assertNotEqual(self.run_cmd(self.testvm1, client_cmd), 0,
                            "TCP connection should be blocked")
        finally:
            server.terminate()
            self.loop.run_until_complete(server.wait())


    def test_040_inter_vm(self):
        '''
        :type self: vanir.tests.SystemTestCase | VMNetworkingMixin
        '''
        self.proxy = self.app.add_new_vm(vanir.vm.appvm.AppVM,
            name=self.make_vm_name('proxy'),
            label='red')
        self.loop.run_until_complete(self.proxy.create_on_disk())
        self.proxy.provides_network = True
        self.proxy.netvm = self.testnetvm
        self.testvm1.netvm = self.proxy

        self.testvm2 = self.app.add_new_vm(vanir.vm.appvm.AppVM,
            name=self.make_vm_name('vm2'),
            label='red')
        self.loop.run_until_complete(self.testvm2.create_on_disk())
        self.testvm2.netvm = self.proxy
        self.app.save()

        self.loop.run_until_complete(asyncio.wait([
            self.testvm1.start(),
            self.testvm2.start()]))

        self.assertNotEqual(self.run_cmd(self.testvm1,
            self.ping_cmd.format(target=self.testvm2.ip)), 0)

        self.testvm2.netvm = self.testnetvm

        self.assertNotEqual(self.run_cmd(self.testvm1,
            self.ping_cmd.format(target=self.testvm2.ip)), 0)
        self.assertNotEqual(self.run_cmd(self.testvm2,
            self.ping_cmd.format(target=self.testvm1.ip)), 0)

        self.testvm1.netvm = self.testnetvm

        self.assertNotEqual(self.run_cmd(self.testvm1,
            self.ping_cmd.format(target=self.testvm2.ip)), 0)
        self.assertNotEqual(self.run_cmd(self.testvm2,
            self.ping_cmd.format(target=self.testvm1.ip)), 0)

    def test_050_spoof_ip(self):
        '''Test if VM IP spoofing is blocked

        :type self: vanir.tests.SystemTestCase | VMNetworkingMixin
        '''
        self.loop.run_until_complete(self.testvm1.start())

        self.assertEqual(self.run_cmd(self.testvm1, self.ping_ip), 0)
        self.assertEqual(self.run_cmd(self.testnetvm,
            'iptables -I INPUT -i vif+ ! -s {} -p icmp -j LOG'.format(
                self.testvm1.ip)), 0)
        self.loop.run_until_complete(self.testvm1.run_for_stdio(
            'ip addr flush dev eth0 && '
            'ip addr add 10.137.1.128/24 dev eth0 && '
            'ip route add default dev eth0',
            user='root'))
        self.assertNotEqual(self.run_cmd(self.testvm1, self.ping_ip), 0,
                         "Spoofed ping should be blocked")
        try:
            (output, _) = self.loop.run_until_complete(
                self.testnetvm.run_for_stdio('iptables -nxvL INPUT',
                    user='root'))
        except subprocess.CalledProcessError:
            self.fail('iptables -nxvL INPUT failed')

        output = output.decode().splitlines()
        packets = output[2].lstrip().split()[0]
        self.assertEquals(packets, '0', 'Some packet hit the INPUT rule')

    def test_100_late_xldevd_startup(self):
        '''Regression test for #1990

        :type self: vanir.tests.SystemTestCase | VMNetworkingMixin
        '''
        # Simulater late xl devd startup
        cmd = "systemctl stop xendriverdomain"
        if self.run_cmd(self.testnetvm, cmd) != 0:
            self.fail("Command '%s' failed" % cmd)
        self.loop.run_until_complete(self.testvm1.start())

        cmd = "systemctl start xendriverdomain"
        if self.run_cmd(self.testnetvm, cmd) != 0:
            self.fail("Command '%s' failed" % cmd)

        self.assertEqual(self.run_cmd(self.testvm1, self.ping_ip), 0)

    def test_110_dynamic_attach(self):
        self.testvm1.netvm = None
        self.loop.run_until_complete(self.testvm1.start())
        self.testvm1.netvm = self.testnetvm
        # wait for it to settle down
        self.loop.run_until_complete(self.testvm1.run_for_stdio(
            'udevadm settle'))
        self.assertEqual(self.run_cmd(self.testvm1, self.ping_ip), 0)

    def test_111_dynamic_detach_attach(self):
        self.loop.run_until_complete(self.testvm1.start())
        self.testvm1.netvm = None
        # wait for it to settle down
        self.loop.run_until_complete(self.testvm1.run_for_stdio(
            'udevadm settle'))
        self.testvm1.netvm = self.testnetvm
        # wait for it to settle down
        self.loop.run_until_complete(self.testvm1.run_for_stdio(
            'udevadm settle'))
        self.assertEqual(self.run_cmd(self.testvm1, self.ping_ip), 0)

    def test_112_reattach_after_provider_shutdown(self):
        self.proxy = self.app.add_new_vm(vanir.vm.appvm.AppVM,
            name=self.make_vm_name('proxy'),
            label='red')
        self.proxy.provides_network = True
        self.proxy.netvm = self.testnetvm
        self.loop.run_until_complete(self.proxy.create_on_disk())
        self.testvm1.netvm = self.proxy

        self.loop.run_until_complete(self.testvm1.start())
        self.loop.run_until_complete(self.proxy.shutdown(force=True, wait=True))
        self.loop.run_until_complete(self.proxy.start())
        # wait for it to settle down
        self.loop.run_until_complete(asyncio.sleep(5))
        self.assertEqual(self.run_cmd(self.testvm1, self.ping_ip), 0)

    def test_113_reattach_after_provider_kill(self):
        self.proxy = self.app.add_new_vm(vanir.vm.appvm.AppVM,
            name=self.make_vm_name('proxy'),
            label='red')
        self.proxy.provides_network = True
        self.proxy.netvm = self.testnetvm
        self.loop.run_until_complete(self.proxy.create_on_disk())
        self.testvm1.netvm = self.proxy

        self.loop.run_until_complete(self.testvm1.start())
        self.loop.run_until_complete(self.proxy.kill())
        self.loop.run_until_complete(self.proxy.start())
        # wait for it to settle down
        self.loop.run_until_complete(asyncio.sleep(5))
        self.assertEqual(self.run_cmd(self.testvm1, self.ping_ip), 0)

    def test_114_reattach_after_provider_crash(self):
        self.proxy = self.app.add_new_vm(vanir.vm.appvm.AppVM,
            name=self.make_vm_name('proxy'),
            label='red')
        self.proxy.provides_network = True
        self.proxy.netvm = self.testnetvm
        self.loop.run_until_complete(self.proxy.create_on_disk())
        self.testvm1.netvm = self.proxy

        self.loop.run_until_complete(self.testvm1.start())
        p = self.loop.run_until_complete(self.proxy.run(
            'echo c > /proc/sysrq-trigger', user='root'))
        self.loop.run_until_complete(p.wait())
        timeout = 10
        while self.proxy.is_running():
            self.loop.run_until_complete(asyncio.sleep(1))
            timeout -= 1
            self.assertGreater(timeout, 0,
                'timeout waiting for crash cleanup')
        self.loop.run_until_complete(self.proxy.start())
        # wait for it to settle down
        self.loop.run_until_complete(asyncio.sleep(5))
        self.assertEqual(self.run_cmd(self.testvm1, self.ping_ip), 0)

    def test_200_fake_ip_simple(self):
        '''Test hiding VM real IP

        :type self: vanir.tests.SystemTestCase | VMNetworkingMixin
        '''
        self.testvm1.features['net.fake-ip'] = '192.168.1.128'
        self.testvm1.features['net.fake-gateway'] = '192.168.1.1'
        self.testvm1.features['net.fake-netmask'] = '255.255.255.0'
        self.app.save()
        self.loop.run_until_complete(self.testvm1.start())
        self.assertEqual(self.run_cmd(self.testvm1, self.ping_ip), 0)
        self.assertEqual(self.run_cmd(self.testvm1, self.ping_name), 0)

        try:
            (output, _) = self.loop.run_until_complete(
                self.testvm1.run_for_stdio(
                    'ip addr show dev eth0', user='root'))
        except subprocess.CalledProcessError:
            self.fail('ip addr show dev eth0 failed')

        output = output.decode()
        self.assertIn('192.168.1.128', output)
        self.assertNotIn(str(self.testvm1.ip), output)

        try:
            (output, _) = self.loop.run_until_complete(
                self.testvm1.run_for_stdio('ip route show', user='root'))
        except subprocess.CalledProcessError:
            self.fail('ip route show failed')

        output = output.decode()
        self.assertIn('192.168.1.1', output)
        self.assertNotIn(str(self.testvm1.netvm.ip), output)

    def test_201_fake_ip_without_gw(self):
        '''Test hiding VM real IP

        :type self: vanir.tests.SystemTestCase | VMNetworkingMixin
        '''
        self.testvm1.features['net.fake-ip'] = '192.168.1.128'
        self.app.save()
        self.loop.run_until_complete(self.testvm1.start())
        self.assertEqual(self.run_cmd(self.testvm1, self.ping_ip), 0)
        self.assertEqual(self.run_cmd(self.testvm1, self.ping_name), 0)

        try:
            (output, _) = self.loop.run_until_complete(
                self.testvm1.run_for_stdio('ip addr show dev eth0',
                    user='root'))
        except subprocess.CalledProcessError:
            self.fail('ip addr show dev eth0 failed')

        output = output.decode()
        self.assertIn('192.168.1.128', output)
        self.assertNotIn(str(self.testvm1.ip), output)

    def test_202_fake_ip_firewall(self):
        '''Test hiding VM real IP, firewall

        :type self: vanir.tests.SystemTestCase | VMNetworkingMixin
        '''
        self.testvm1.features['net.fake-ip'] = '192.168.1.128'
        self.testvm1.features['net.fake-gateway'] = '192.168.1.1'
        self.testvm1.features['net.fake-netmask'] = '255.255.255.0'

        self.proxy = self.app.add_new_vm(vanir.vm.appvm.AppVM,
            name=self.make_vm_name('proxy'),
            label='red')
        self.proxy.provides_network = True
        self.loop.run_until_complete(self.proxy.create_on_disk())
        self.proxy.netvm = self.testnetvm
        self.testvm1.netvm = self.proxy
        self.app.save()

        # block all but ICMP and DNS

        self.testvm1.firewall.rules = [
            vanir.firewall.Rule(None, action='accept', proto='icmp'),
            vanir.firewall.Rule(None, action='accept', specialtarget='dns'),
        ]
        self.testvm1.firewall.save()
        self.loop.run_until_complete(self.testvm1.start())
        self.assertTrue(self.proxy.is_running())

        server = self.loop.run_until_complete(self.testnetvm.run(
            'socat TCP-LISTEN:1234,fork EXEC:/bin/uname'))

        try:
            self.assertEqual(self.run_cmd(self.proxy, self.ping_ip), 0,
                            "Ping by IP from ProxyVM failed")
            self.assertEqual(self.run_cmd(self.proxy, self.ping_name), 0,
                            "Ping by name from ProxyVM failed")
            self.assertEqual(self.run_cmd(self.testvm1, self.ping_ip), 0,
                            "Ping by IP should be allowed")
            self.assertEqual(self.run_cmd(self.testvm1, self.ping_name), 0,
                            "Ping by name should be allowed")
            client_cmd = "socat TCP:{}:1234 -".format(self.test_ip)
            self.assertNotEqual(self.run_cmd(self.testvm1, client_cmd), 0,
                            "TCP connection should be blocked")
        finally:
            server.terminate()
            self.loop.run_until_complete(server.wait())

    def test_203_fake_ip_inter_vm_allow(self):
        '''Access VM with "fake IP" from other VM (when firewall allows)

        :type self: vanir.tests.SystemTestCase | VMNetworkingMixin
        '''
        self.proxy = self.app.add_new_vm(vanir.vm.appvm.AppVM,
            name=self.make_vm_name('proxy'),
            label='red')
        self.loop.run_until_complete(self.proxy.create_on_disk())
        self.proxy.provides_network = True
        self.proxy.netvm = self.testnetvm
        self.testvm1.netvm = self.proxy
        self.testvm1.features['net.fake-ip'] = '192.168.1.128'
        self.testvm1.features['net.fake-gateway'] = '192.168.1.1'
        self.testvm1.features['net.fake-netmask'] = '255.255.255.0'

        self.testvm2 = self.app.add_new_vm(vanir.vm.appvm.AppVM,
            name=self.make_vm_name('vm2'),
            label='red')
        self.loop.run_until_complete(self.testvm2.create_on_disk())
        self.testvm2.netvm = self.proxy
        self.app.save()

        self.loop.run_until_complete(self.testvm1.start())
        self.loop.run_until_complete(self.testvm2.start())

        cmd = 'iptables -I FORWARD -s {} -d {} -j ACCEPT'.format(
            self.testvm2.ip, self.testvm1.ip)
        try:
            self.loop.run_until_complete(self.proxy.run_for_stdio(
                cmd, user='root'))
        except subprocess.CalledProcessError as e:
            raise AssertionError(
                '{} failed with: {}'.format(cmd, e.returncode)) from None

        try:
            cmd = 'iptables -I INPUT -s {} -j ACCEPT'.format(self.testvm2.ip)
            self.loop.run_until_complete(self.testvm1.run_for_stdio(
                cmd, user='root'))
        except subprocess.CalledProcessError as e:
            raise AssertionError(
                '{} failed with: {}'.format(cmd, e.returncode)) from None

        self.assertEqual(self.run_cmd(self.testvm2,
            self.ping_cmd.format(target=self.testvm1.ip)), 0)

        try:
            cmd = 'iptables -nvxL INPUT | grep {}'.format(self.testvm2.ip)
            (stdout, _) = self.loop.run_until_complete(
                self.testvm1.run_for_stdio(cmd, user='root'))
        except subprocess.CalledProcessError as e:
            raise AssertionError(
                '{} failed with {}'.format(cmd, e.returncode)) from None
        self.assertNotEqual(stdout.decode().split()[0], '0',
            'Packets didn\'t managed to the VM')

    def test_204_fake_ip_proxy(self):
        '''Test hiding VM real IP

        :type self: vanir.tests.SystemTestCase | VMNetworkingMixin
        '''
        self.proxy = self.app.add_new_vm(vanir.vm.appvm.AppVM,
            name=self.make_vm_name('proxy'),
            label='red')
        self.loop.run_until_complete(self.proxy.create_on_disk())
        self.proxy.provides_network = True
        self.proxy.netvm = self.testnetvm
        self.proxy.features['net.fake-ip'] = '192.168.1.128'
        self.proxy.features['net.fake-gateway'] = '192.168.1.1'
        self.proxy.features['net.fake-netmask'] = '255.255.255.0'
        self.testvm1.netvm = self.proxy
        self.app.save()
        self.loop.run_until_complete(self.testvm1.start())

        self.assertEqual(self.run_cmd(self.proxy, self.ping_ip), 0)
        self.assertEqual(self.run_cmd(self.proxy, self.ping_name), 0)

        self.assertEqual(self.run_cmd(self.testvm1, self.ping_ip), 0)
        self.assertEqual(self.run_cmd(self.testvm1, self.ping_name), 0)

        try:
            (output, _) = self.loop.run_until_complete(
                self.proxy.run_for_stdio(
                    'ip addr show dev eth0', user='root'))
        except subprocess.CalledProcessError:
            self.fail('ip addr show dev eth0 failed')
        output = output.decode()
        self.assertIn('192.168.1.128', output)
        self.assertNotIn(str(self.testvm1.ip), output)

        try:
            (output, _) = self.loop.run_until_complete(
                self.proxy.run_for_stdio(
                    'ip route show', user='root'))
        except subprocess.CalledProcessError:
            self.fail('ip route show failed')
        output = output.decode()
        self.assertIn('192.168.1.1', output)
        self.assertNotIn(str(self.testvm1.netvm.ip), output)

        try:
            (output, _) = self.loop.run_until_complete(
                self.testvm1.run_for_stdio(
                    'ip addr show dev eth0', user='root'))
        except subprocess.CalledProcessError:
            self.fail('ip addr show dev eth0 failed')
        output = output.decode()
        self.assertNotIn('192.168.1.128', output)
        self.assertIn(str(self.testvm1.ip), output)

        try:
            (output, _) = self.loop.run_until_complete(
                self.testvm1.run_for_stdio(
                    'ip route show', user='root'))
        except subprocess.CalledProcessError:
            self.fail('ip route show failed')
        output = output.decode()
        self.assertIn('192.168.1.128', output)
        self.assertNotIn(str(self.proxy.ip), output)

    def test_210_custom_ip_simple(self):
        '''Custom AppVM IP

        :type self: vanir.tests.SystemTestCase | VMNetworkingMixin
        '''
        self.testvm1.ip = '192.168.1.1'
        self.app.save()
        self.loop.run_until_complete(self.testvm1.start())
        self.assertEqual(self.run_cmd(self.testvm1, self.ping_ip), 0)
        self.assertEqual(self.run_cmd(self.testvm1, self.ping_name), 0)

    def test_211_custom_ip_proxy(self):
        '''Custom ProxyVM IP

        :type self: vanir.tests.SystemTestCase | VMNetworkingMixin
        '''
        self.proxy = self.app.add_new_vm(vanir.vm.appvm.AppVM,
            name=self.make_vm_name('proxy'),
            label='red')
        self.loop.run_until_complete(self.proxy.create_on_disk())
        self.proxy.provides_network = True
        self.proxy.netvm = self.testnetvm
        self.proxy.ip = '192.168.1.1'
        self.testvm1.netvm = self.proxy
        self.app.save()

        self.loop.run_until_complete(self.testvm1.start())

        self.assertEqual(self.run_cmd(self.testvm1, self.ping_ip), 0)
        self.assertEqual(self.run_cmd(self.testvm1, self.ping_name), 0)

    def test_212_custom_ip_firewall(self):
        '''Custom VM IP and firewall

        :type self: vanir.tests.SystemTestCase | VMNetworkingMixin
        '''
        self.testvm1.ip = '192.168.1.1'

        self.proxy = self.app.add_new_vm(vanir.vm.appvm.AppVM,
            name=self.make_vm_name('proxy'),
            label='red')
        self.proxy.provides_network = True
        self.loop.run_until_complete(self.proxy.create_on_disk())
        self.proxy.netvm = self.testnetvm
        self.testvm1.netvm = self.proxy
        self.app.save()

        # block all but ICMP and DNS

        self.testvm1.firewall.rules = [
            vanir.firewall.Rule(None, action='accept', proto='icmp'),
            vanir.firewall.Rule(None, action='accept', specialtarget='dns'),
        ]
        self.testvm1.firewall.save()
        self.loop.run_until_complete(self.testvm1.start())
        self.assertTrue(self.proxy.is_running())

        server = self.loop.run_until_complete(self.testnetvm.run(
            'socat TCP-LISTEN:1234,fork EXEC:/bin/uname'))

        try:
            self.assertEqual(self.run_cmd(self.proxy, self.ping_ip), 0,
                            "Ping by IP from ProxyVM failed")
            self.assertEqual(self.run_cmd(self.proxy, self.ping_name), 0,
                            "Ping by name from ProxyVM failed")
            self.assertEqual(self.run_cmd(self.testvm1, self.ping_ip), 0,
                            "Ping by IP should be allowed")
            self.assertEqual(self.run_cmd(self.testvm1, self.ping_name), 0,
                            "Ping by name should be allowed")
            client_cmd = "socat TCP:{}:1234 -".format(self.test_ip)
            self.assertNotEqual(self.run_cmd(self.testvm1, client_cmd), 0,
                            "TCP connection should be blocked")
        finally:
            server.terminate()
            self.loop.run_until_complete(server.wait())


# noinspection PyAttributeOutsideInit,PyPep8Naming
class VmIPv6NetworkingMixin(VmNetworkingMixin):
    test_ip6 = '2000:abcd::1'

    ping6_cmd = 'ping6 -W 1 -n -c 1 {target}'

    def setUp(self):
        super(VmIPv6NetworkingMixin, self).setUp()
        self.ping6_ip = self.ping6_cmd.format(target=self.test_ip6)
        self.ping6_name = self.ping6_cmd.format(target=self.test_name)

    def configure_netvm(self):
        '''
        :type self: vanir.tests.SystemTestCase | VmIPv6NetworkingMixin
        '''
        self.testnetvm.features['ipv6'] = True
        super(VmIPv6NetworkingMixin, self).configure_netvm()

        def run_netvm_cmd(cmd):
            if self.run_cmd(self.testnetvm, cmd) != 0:
                self.fail("Command '%s' failed" % cmd)

        run_netvm_cmd("ip addr add {}/128 dev test0".format(self.test_ip6))
        run_netvm_cmd(
            "ip6tables -I INPUT -d {} -j ACCEPT".format(self.test_ip6))
        # ignore failure
        self.run_cmd(self.testnetvm, "killall --wait dnsmasq")
        run_netvm_cmd(
            "dnsmasq -a {ip} -A /{name}/{ip} -A /{name}/{ip6} -i test0 -z".
            format(ip=self.test_ip, ip6=self.test_ip6, name=self.test_name))

    def test_500_ipv6_simple_networking(self):
        '''
        :type self: vanir.tests.SystemTestCase | VmIPv6NetworkingMixin
        '''
        self.loop.run_until_complete(self.testvm1.start())
        self.assertEqual(self.run_cmd(self.testvm1, self.ping6_ip), 0)
        self.assertEqual(self.run_cmd(self.testvm1, self.ping6_name), 0)


    def test_510_ipv6_simple_proxyvm(self):
        '''
        :type self: vanir.tests.SystemTestCase | VmIPv6NetworkingMixin
        '''
        self.proxy = self.app.add_new_vm(vanir.vm.appvm.AppVM,
            name=self.make_vm_name('proxy'),
            label='red')
        self.proxy.provides_network = True
        self.proxy.netvm = self.testnetvm
        self.loop.run_until_complete(self.proxy.create_on_disk())
        self.testvm1.netvm = self.proxy
        self.app.save()

        self.loop.run_until_complete(self.testvm1.start())
        self.assertTrue(self.proxy.is_running())
        self.assertEqual(self.run_cmd(self.proxy, self.ping6_ip), 0,
                         "Ping by IP from ProxyVM failed")
        self.assertEqual(self.run_cmd(self.proxy, self.ping6_name), 0,
                         "Ping by name from ProxyVM failed")
        self.assertEqual(self.run_cmd(self.testvm1, self.ping6_ip), 0,
                         "Ping by IP from AppVM failed")
        self.assertEqual(self.run_cmd(self.testvm1, self.ping6_name), 0,
                         "Ping by IP from AppVM failed")


    @vanir.tests.expectedFailureIfTemplate('debian-7')
    @unittest.skipUnless(spawn.find_executable('xdotool'),
                         "xdotool not installed")
    def test_520_ipv6_simple_proxyvm_nm(self):
        '''
        :type self: vanir.tests.SystemTestCase | VmIPv6NetworkingMixin
        '''
        self.proxy = self.app.add_new_vm(vanir.vm.appvm.AppVM,
            name=self.make_vm_name('proxy'),
            label='red')
        self.proxy.provides_network = True
        self.loop.run_until_complete(self.proxy.create_on_disk())
        self.proxy.netvm = self.testnetvm
        self.proxy.features['service.network-manager'] = True
        self.testvm1.netvm = self.proxy
        self.app.save()

        self.loop.run_until_complete(self.testvm1.start())
        self.assertTrue(self.proxy.is_running())
        self.assertEqual(self.run_cmd(self.testvm1, self.ping6_ip), 0,
                         "Ping by IP failed")
        self.assertEqual(self.run_cmd(self.testvm1, self.ping6_name), 0,
                         "Ping by name failed")

        # reconnect to make sure that device was configured by NM
        self.assertEqual(
            self.run_cmd(self.proxy, "nmcli device disconnect eth0",
                user="user"),
            0, "Failed to disconnect eth0 using nmcli")

        self.assertNotEqual(self.run_cmd(self.testvm1, self.ping6_ip), 0,
            "Network should be disabled, but apparently it isn't")
        self.assertEqual(
            self.run_cmd(self.proxy,
                'nmcli connection up "VM uplink eth0" ifname eth0',
                user="user"),
            0, "Failed to connect eth0 using nmcli")
        self.assertEqual(self.run_cmd(self.proxy, "nm-online",
            user="user"), 0,
                         "Failed to wait for NM connection")

        # wait for duplicate-address-detection to complete - by default it has
        #  1s timeout
        time.sleep(2)

        # check for nm-applet presence
        self.assertEqual(subprocess.call([
            'xdotool', 'search', '--class', '{}:nm-applet'.format(
                self.proxy.name)],
            stdout=subprocess.DEVNULL), 0, "nm-applet window not found")
        self.assertEqual(self.run_cmd(self.testvm1, self.ping6_ip), 0,
                         "Ping by IP failed (after NM reconnection")
        self.assertEqual(self.run_cmd(self.testvm1, self.ping6_name), 0,
                         "Ping by name failed (after NM reconnection)")


    def test_530_ipv6_firewallvm_firewall(self):
        '''
        :type self: vanir.tests.SystemTestCase | VmIPv6NetworkingMixin
        '''
        self.proxy = self.app.add_new_vm(vanir.vm.appvm.AppVM,
            name=self.make_vm_name('proxy'),
            label='red')
        self.proxy.provides_network = True
        self.loop.run_until_complete(self.proxy.create_on_disk())
        self.proxy.netvm = self.testnetvm
        self.testvm1.netvm = self.proxy
        self.app.save()

        # block all for first

        self.testvm1.firewall.rules = [vanir.firewall.Rule(action='drop')]
        self.testvm1.firewall.save()
        self.loop.run_until_complete(self.testvm1.start())
        self.assertTrue(self.proxy.is_running())

        server = self.loop.run_until_complete(self.testnetvm.run(
            'socat TCP6-LISTEN:1234,fork EXEC:/bin/uname'))

        try:
            self.assertEqual(self.run_cmd(self.proxy, self.ping6_ip), 0,
                            "Ping by IP from ProxyVM failed")
            self.assertEqual(self.run_cmd(self.proxy, self.ping6_name), 0,
                            "Ping by name from ProxyVM failed")
            self.assertNotEqual(self.run_cmd(self.testvm1, self.ping6_ip), 0,
                            "Ping by IP should be blocked")

            client6_cmd = "socat TCP:[{}]:1234 -".format(self.test_ip6)
            client4_cmd = "socat TCP:{}:1234 -".format(self.test_ip)
            self.assertNotEqual(self.run_cmd(self.testvm1, client6_cmd), 0,
                            "TCP connection should be blocked")

            # block all except ICMP

            self.testvm1.firewall.rules = [(
                vanir.firewall.Rule(None, action='accept', proto='icmp')
            )]
            self.testvm1.firewall.save()
            # Ugly hack b/c there is no feedback when the rules are actually
            # applied
            time.sleep(3)
            self.assertEqual(self.run_cmd(self.testvm1, self.ping6_ip), 0,
                            "Ping by IP failed (should be allowed now)")
            self.assertNotEqual(self.run_cmd(self.testvm1, self.ping6_name), 0,
                            "Ping by name should be blocked")

            # all TCP still blocked

            self.testvm1.firewall.rules = [
                vanir.firewall.Rule(None, action='accept', proto='icmp'),
                vanir.firewall.Rule(None, action='accept', specialtarget='dns'),
            ]
            self.testvm1.firewall.save()

            # Ugly hack b/c there is no feedback when the rules are actually
            # applied
            time.sleep(3)
            self.assertEqual(self.run_cmd(self.testvm1, self.ping6_name), 0,
                            "Ping by name failed (should be allowed now)")
            self.assertNotEqual(self.run_cmd(self.testvm1, client6_cmd), 0,
                            "TCP connection should be blocked")

            # block all except target

            self.testvm1.firewall.rules = [
                vanir.firewall.Rule(None, action='accept',
                    dsthost=self.test_ip6,
                    proto='tcp', dstports=1234),
            ]
            self.testvm1.firewall.save()

            # Ugly hack b/c there is no feedback when the rules are actually
            # applied
            time.sleep(3)
            self.assertEqual(self.run_cmd(self.testvm1, client6_cmd), 0,
                            "TCP connection failed (should be allowed now)")

            # block all except target - by name

            self.testvm1.firewall.rules = [
                vanir.firewall.Rule(None, action='accept',
                    dsthost=self.test_name,
                    proto='tcp', dstports=1234),
            ]
            self.testvm1.firewall.save()

            # Ugly hack b/c there is no feedback when the rules are actually
            # applied
            time.sleep(3)
            self.assertEqual(self.run_cmd(self.testvm1, client6_cmd), 0,
                "TCP (IPv6) connection failed (should be allowed now)")
            self.assertEqual(self.run_cmd(self.testvm1, client4_cmd),
                0,
                "TCP (IPv4) connection failed (should be allowed now)")

            # allow all except target

            self.testvm1.firewall.rules = [
                vanir.firewall.Rule(None, action='drop', dsthost=self.test_ip6,
                    proto='tcp', dstports=1234),
                vanir.firewall.Rule(action='accept'),
            ]
            self.testvm1.firewall.save()

            # Ugly hack b/c there is no feedback when the rules are actually
            # applied
            time.sleep(3)
            self.assertNotEqual(self.run_cmd(self.testvm1, client6_cmd), 0,
                            "TCP connection should be blocked")
        finally:
            server.terminate()
            self.loop.run_until_complete(server.wait())


    def test_540_ipv6_inter_vm(self):
        '''
        :type self: vanir.tests.SystemTestCase | VmIPv6NetworkingMixin
        '''
        self.proxy = self.app.add_new_vm(vanir.vm.appvm.AppVM,
            name=self.make_vm_name('proxy'),
            label='red')
        self.loop.run_until_complete(self.proxy.create_on_disk())
        self.proxy.provides_network = True
        self.proxy.netvm = self.testnetvm
        self.testvm1.netvm = self.proxy

        self.testvm2 = self.app.add_new_vm(vanir.vm.appvm.AppVM,
            name=self.make_vm_name('vm2'),
            label='red')
        self.loop.run_until_complete(self.testvm2.create_on_disk())
        self.testvm2.netvm = self.proxy
        self.app.save()

        self.loop.run_until_complete(asyncio.wait([
            self.testvm1.start(),
            self.testvm2.start()]))

        self.assertNotEqual(self.run_cmd(self.testvm1,
            self.ping_cmd.format(target=self.testvm2.ip6)), 0)

        self.testvm2.netvm = self.testnetvm

        self.assertNotEqual(self.run_cmd(self.testvm1,
            self.ping_cmd.format(target=self.testvm2.ip6)), 0)
        self.assertNotEqual(self.run_cmd(self.testvm2,
            self.ping_cmd.format(target=self.testvm1.ip6)), 0)

        self.testvm1.netvm = self.testnetvm

        self.assertNotEqual(self.run_cmd(self.testvm1,
            self.ping_cmd.format(target=self.testvm2.ip6)), 0)
        self.assertNotEqual(self.run_cmd(self.testvm2,
            self.ping_cmd.format(target=self.testvm1.ip6)), 0)



    def test_550_ipv6_spoof_ip(self):
        '''Test if VM IP spoofing is blocked

        :type self: vanir.tests.SystemTestCase | VmIPv6NetworkingMixin
        '''
        self.loop.run_until_complete(self.testvm1.start())

        self.assertEqual(self.run_cmd(self.testvm1, self.ping6_ip), 0)
        # add a simple rule counting packets
        self.assertEqual(self.run_cmd(self.testnetvm,
            'ip6tables -I INPUT -i vif+ ! -s {} -p icmpv6 -j LOG'.format(
                self.testvm1.ip6)), 0)
        self.loop.run_until_complete(self.testvm1.run_for_stdio(
            'ip -6 addr flush dev eth0 && '
            'ip -6 addr add {}/128 dev eth0 && '
            'ip -6 route add default via {} dev eth0'.format(
                str(self.testvm1.visible_ip6) + '1',
                str(self.testvm1.visible_gateway6)),
            user='root'))
        self.assertNotEqual(self.run_cmd(self.testvm1, self.ping6_ip), 0,
                         "Spoofed ping should be blocked")
        try:
            (output, _) = self.loop.run_until_complete(
                self.testnetvm.run_for_stdio('ip6tables -nxvL INPUT',
                    user='root'))
        except subprocess.CalledProcessError:
            self.fail('ip6tables -nxvL INPUT failed')

        output = output.decode().splitlines()
        packets = output[2].lstrip().split()[0]
        self.assertEquals(packets, '0', 'Some packet hit the INPUT rule')

    def test_710_ipv6_custom_ip_simple(self):
        '''Custom AppVM IP

        :type self: vanir.tests.SystemTestCase | VmIPv6NetworkingMixin
        '''
        self.testvm1.ip6 = '2000:aaaa:bbbb::1'
        self.app.save()
        self.loop.run_until_complete(self.testvm1.start())
        self.assertEqual(self.run_cmd(self.testvm1, self.ping6_ip), 0)
        self.assertEqual(self.run_cmd(self.testvm1, self.ping6_name), 0)

    def test_711_ipv6_custom_ip_proxy(self):
        '''Custom ProxyVM IP

        :type self: vanir.tests.SystemTestCase | VmIPv6NetworkingMixin
        '''
        self.proxy = self.app.add_new_vm(vanir.vm.appvm.AppVM,
            name=self.make_vm_name('proxy'),
            label='red')
        self.loop.run_until_complete(self.proxy.create_on_disk())
        self.proxy.provides_network = True
        self.proxy.netvm = self.testnetvm
        self.testvm1.ip6 = '2000:aaaa:bbbb::1'
        self.testvm1.netvm = self.proxy
        self.app.save()

        self.loop.run_until_complete(self.testvm1.start())

        self.assertEqual(self.run_cmd(self.testvm1, self.ping6_ip), 0)
        self.assertEqual(self.run_cmd(self.testvm1, self.ping6_name), 0)

    def test_712_ipv6_custom_ip_firewall(self):
        '''Custom VM IP and firewall

        :type self: vanir.tests.SystemTestCase | VmIPv6NetworkingMixin
        '''
        self.testvm1.ip6 = '2000:aaaa:bbbb::1'

        self.proxy = self.app.add_new_vm(vanir.vm.appvm.AppVM,
            name=self.make_vm_name('proxy'),
            label='red')
        self.proxy.provides_network = True
        self.loop.run_until_complete(self.proxy.create_on_disk())
        self.proxy.netvm = self.testnetvm
        self.testvm1.netvm = self.proxy
        self.app.save()

        # block all but ICMP and DNS

        self.testvm1.firewall.rules = [
            vanir.firewall.Rule(None, action='accept', proto='icmp'),
            vanir.firewall.Rule(None, action='accept', specialtarget='dns'),
        ]
        self.testvm1.firewall.save()
        self.loop.run_until_complete(self.testvm1.start())
        self.assertTrue(self.proxy.is_running())

        server = self.loop.run_until_complete(self.testnetvm.run(
            'socat TCP6-LISTEN:1234,fork EXEC:/bin/uname'))

        try:
            self.assertEqual(self.run_cmd(self.proxy, self.ping6_ip), 0,
                            "Ping by IP from ProxyVM failed")
            self.assertEqual(self.run_cmd(self.proxy, self.ping6_name), 0,
                            "Ping by name from ProxyVM failed")
            self.assertEqual(self.run_cmd(self.testvm1, self.ping6_ip), 0,
                            "Ping by IP should be allowed")
            self.assertEqual(self.run_cmd(self.testvm1, self.ping6_name), 0,
                            "Ping by name should be allowed")
            client_cmd = "socat TCP:[{}]:1234 -".format(self.test_ip6)
            self.assertNotEqual(self.run_cmd(self.testvm1, client_cmd), 0,
                            "TCP connection should be blocked")
        finally:
            server.terminate()
            self.loop.run_until_complete(server.wait())

# noinspection PyAttributeOutsideInit,PyPep8Naming
class VmUpdatesMixin(object):
    """
    Tests for VM updates
    """

    # filled by load_tests
    template = None

    # made this way to work also when no package build tools are installed
    """
    $ cat test-pkg.spec:
    Name:		test-pkg
    Version:	1.0
    Release:	1%{?dist}
    Summary:	Test package

    Group:		System
    License:	GPL
    URL:		http://example.com/

    %description
    Test package

    %files

    %changelog
    $ rpmbuild -bb test-pkg.spec
    $ cat test-pkg-1.0-1.fc21.x86_64.rpm | gzip | base64
    $ cat test-pkg-1.1-1.fc21.x86_64.rpm | gzip | base64
    """
    RPM_PACKAGE_GZIP_BASE64 = [(
        b"H4sIAPzRLlYAA+2Y728URRjHn7ueUCkERKJVJDnTxLSxs7293o8WOER6ljYYrtKCLUSa3"
        b"bnZ64bd22VmTq8nr4wJbwxvjNHIG0x8oTHGGCHB8AcYE1/0lS80GgmQFCJU3wgB4ZjdfZ"
        b"q2xDe8NNlvMjfzmeeZH7tPbl98b35169cOUEpIJiTxT9SIrmVUs2hWh8dUAp54dOrM14s"
        b"JHK4D2DKl+j2qrVfjsuq3qEWbohjuAB2Lqk+p1o/8Z5QPmSi/YwnjezH+F8bLQZjqllW0"
        b"hvODRmFIL5hFk9JMXi/mi5ZuDleNwSEzP5wtmLnouNQnm3/6fndz7FLt9M/Hruj37gav4"
        b"tTjPnasWLFixYoVK1asWLFixYoV63+p0KNot9vnIPQc1vgYOwCSgXfxCoS+QzKHOVXVOj"
        b"Fn2ccIfI0k8nXkLuQbyJthxed4UrVnkG8i9yDfgsj3yCAv4foc8t+w1hf5B+Nl5Du43xj"
        b"yvxivIN9HpsgPkO2IU9uQfeRn8Xk/iJ4x1Y3nfxH1qecwfhH5+YgT25F7o/0SRdxvOppP"
        b"7MX9ZjB/DNnE/OOYX404uRGZIT+FbCFvQ3aQ8f0+/WF0XjJ8nyOw7H+BrmUA/a8pNZf2D"
        b"XrCqLG1cERbWHI8ajhznpBY9P0Tr8PkvJDMhTkp/Z0DA6xpuL7DNOq5A+DY9UYTmkOF2U"
        b"IO/sNt0wSnGvfdlZssD3rVIlLI9UUX37C6qXzHNntHPNfnTAhWHbUddtBwmegDjAUzZbu"
        b"m9lqZmzDmHc8Ik8WY8Tab4Myym4+Gx8V0qw8GtYyWIzrktEJwV9UHv3ktG471rAqHTmFQ"
        b"685V5uGqIalk06SWJr7tszR503Ac9cs493jJ8rhrSCIYbXBbzqt5v5+UZ0crh6bGR2dmJ"
        b"yuHD428VlLLLdakzJe2VxcKhFSFID73JKPS40RI7tXVCcQ3uOGWhPCJ2bAspiJ2i5Vy6n"
        b"jOqMerpEYpEe/Yks4xkU4Tt6BirmzUWanG6ozbFKhve9BsQRaLRTirzqk7hgUktXojKnf"
        b"n8jeg3X4QepP3i63po6oml+9t/CwJLya2Bn/ei6f7/4B3Ycdb0L3pt5Q5mNz16rWJ9fLk"
        b"vvOff/nxS7//8O2P2gvt7nDDnoV9L1du9N4+ucjl9u/8+a7dC5Nnvjlv9Ox5r+v9Cy0NE"
        b"m+c6rv60S/dZw98Gn6MNswcfQiWUvg3wBUAAA=="
    ), (
        b"H4sIAMY1B1wCA+2Y72scRRjH537U1MZorKLRVjgJSIKdvf11u3dq0jZJ0wRLL+1VvBRrn"
        b"J2dvVu6t7vd3bN3sS9ECr6RIkgR9JXQF5aiIk1L/gJF8EVe+KqiKLQQi03tmypojXO3zz"
        b"Vp8YW+3y/MPvOZ55lnZthhXjw3Lqx9n0FcqYiFEfaP17AkSLxZVJbQ/1QKbbl/6Mxnqyn"
        b"o9iE0uMTtOPTPcTvIJw1w+8DdDCj1KPBozJlVbrO8OcC/xvORH8/P3AT/2+D/DfynuTtH"
        b"FKtANKNo6KpKJIs3jSkl3VIkvSAWSiZTlCL3akhXZCKKKmPcaRRJqURFS2MlSTMsgyqMz"
        b"6RUp8SQFcmixZJpMlEWi0w1da3Eu3p3+1uW1saPHfpWOSvNXtruDVx4+A0+eAolSpQoUa"
        b"JEiRIlSpQoUaJEiRJBTWR9ff191K1p3FM3ySGUEbndjbp1jUwOYkzetkJMr07SqZukgX8"
        b"B7ge+DvwI2qijPMjbE8A3gIeB11BcVxGBb8J8FfgW+PcA3wb/FPAfkG8G+C/wl4HvAFPg"
        b"v4HtmLOPA/vAT8J534vPmB2C9T+NbfYp8C8DPx1zagfwSJwvpUO+ajye2gP55iF+BtiA+"
        b"Nch3ow5/TkwA74IbAFfBnaAl2N+7IN4vfQK8Ffg/w74arx++grwtTg+s7PDk6hXn0OSIC"
        b"Gozx3hYzmf0OOkxu6F1/oKlx2PEqfuhRFckv1zB1ClHUasgepR5L+Qz7MWafgOE6jXyCP"
        b"Hdpst1CpqC5qK/qUaKIQBFQK/sbGTXmeET8KaCgW7bZsbj3dsY2TSa/gBC0NmTtsOO0ga"
        b"LBxF4OuMTNk1nmtjbI60HY90g8MZ8iabC5hlt+53z4bVxVGkCKKgYgmpgiaIXdv5FgS52"
        b"5dUQY6P37kbWzcVNzd1cVnO4VoO+7bPcvhV4jj8y4LAC8YsL2iQCIeMNgM7avNxfxeeWp"
        b"guHz4yOz2/UCm/cnhy35jcG99/YHZislpd2Fup7OMR5YOVHLZYizI/sj035BBG/BdhP/A"
        b"iRiMvwGEUeC5fuxYw6gUmrlGKw5N2ROuMh4c+o+FYvhkGeX7wPD9/PmBmnURgcJ0EJnOZ"
        b"iSmV/kM4cV3PsN04uqGp/BM1XTZW4zkCm/L9kbDt0jrfk9cMcdM9absmjojhsI3NU4eE9"
        b"d4R+LG4g1qbGFHf9lBrEclwnTCs3r1iuOY2u/+jGVm4iCwiyXpJE61SkUq6RhVW0FVFpo"
        b"ZZ0oiu6ppuFSxSFBXTUOQCFRmhhElFQ9XNgiyJhbv/dnf8hnaeETR4R1+sHuX37+c/H/o"
        b"kjZ5Nbe88bMvv7voJvYWeOYaGBn7IGkr6xb3X5vqiExNL585/+NyPX3/5jbBzfaibcHhl"
        b"4vny9ZHfT6wG0Y6Lfrv/pZXKmS+WyPD4O/2nLy0KKHXo1OjVs1eGPn75o+5DvW3+6D9jd"
        b"bFaTBcAAA=="
    )]

    """
    Minimal package generated by running dh_make on empty directory
    Then cat test-pkg_1.0-1_amd64.deb | gzip | base64
    Then cat test-pkg_1.1-1_amd64.deb | gzip | base64
    """
    DEB_PACKAGE_GZIP_BASE64 = [(
        b"H4sIACTXLlYAA1O0SSxKzrDjSklNykzM003KzEssqlRQUDA0MTG1NDQwNDVTUDBQAAEIa"
        b"WhgYGZioqBgogADCVxGegZcyfl5JUX5OXoliUV66VVE6DcwheuX7+ZgAAEW5rdXHb0PG4"
        b"iwf5j3WfMT6zWzzMuZgoE3jjYraNzbbFKWGms0SaRw/r2SV23WZ4IdP8preM4yqf0jt95"
        b"3c8qnacfNxJUkf9/w+/3X9ph2GEdgQdixrz/niHKKTnYXizf4oSC7tHOz2Zzq+/6vn8/7"
        b"ezQ7c1tmi7xZ3SGJ4yzhT2dcr7V+W3zM5ZPu/56PSv4Zdok+7Yv/V/6buWaKVlFkkV58S"
        b"N3GmLgnqzRmeZ3V3ymmurS5fGa85/LNx1bpZMin3S6dvXKqydp3ubP1vmyarJZb/qSh62"
        b"C8oIdxqm/BtvkGDza+On/Vfv2py7/0LV7VH+qR6a+bkKUbHXt5/SG187d+nps1a5PJfMO"
        b"i11dWcUe1HjwaW3Q5RHXn9LmcHy+tW9YcKf0768XVB1t3R0bKrzs5t9P+6r7rZ99svH10"
        b"+Q6F/o8tf1fO/32y+fWa14eifd+WxUy0jcxYH7N9/tUvmnUZL74pW32qLeuRU+ZwYGASa"
        b"GBgUWBgxM90ayy3VdmykkGDgYErJbEkERydFVWQmCMQo8aWZvAY/WteFRHFwMCYqXTPjI"
        b"lBkVEMGLsl+k8XP1D/z+gXyyDOvUemlnHqAVkvu0rRQ2fUFodkN3mtU9uwhqk8V+TqPEE"
        b"Nc7fzoQ4n71lqRs/7kbbT0+qOZuKH4r8mjzsc1k/YkCHN8Pjg48fbpE+teHa96LNcfu0V"
        b"5n2/Z2xa2KDvaCOx8cqBFxc514uZ3TmadXS+6cpzU7wSzq5SWfapJOD9n6wLXSwtlgxZh"
        b"xITzWW7buhx/bb291RcVlEfeC9K5hlrqunSzIMSZT7/Nqgc/qMvMNW227WI8ezB8mVuZh"
        b"0hERJSvysfburr4Dx0I9BW57UwR4+e1gxu49PcEt8sbK18Xpvt//Hj5UYm+Zc25q+T4xl"
        b"rJvxfVnh80oadq57OZxPaU1bbztv1yF365W4t45Yr+XrFzov237GVY1Zgf7NvE4+W2SuR"
        b"lQtLauR1TQ/mbOiIONYya6tU1jPGpWfk/i1+ttiXe3ZO14n0YOWggndznjGlGLyfVbBC6"
        b"MRP5aMM7aCco/s7sZqB8RlTQwADw8rnuT/sDHi7mUASjJFRAAbWwNLiAwAA"
    ), (
        b"H4sIAL05B1wCA1O0SSxKzrDjSklNykzM003KzEssqlRQUDA0NTG2NDc3NjdTUDBQAAEIa"
        b"WhgYGZioqBgogADCVxGegZcyfl5JUX5OXoliUV66VVE6De3gOuX7+ZgAAEW5rdXzmbdMR"
        b"BgSJj/VeQzQ+ztT/W+EVEnFraKOTlXh6+JXB8RbTRpzgWb2qdLX0+RmTRZcYlyxJutJsk"
        b"/pfsfq9yqWZJ4JVVS97jBPPnz1yviluw51b0q4tnrWemCU2a/17mTUBYX0XBC6nH8rvvZ"
        b"n/WP7nu40+Jlz7drPNLvCjULQkXOv677OV9s4bPsv5+tvCzPG8s57no479qV/5V/813Kh"
        b"Wy3Pbj4827Jq5v6W/wk7zL1/+zbfH6btVb/3Pm5EapukaJvdgfcape/JZZWe+mZ4+Grby"
        b"7UTaroPzyv9urC1W2MT9+F2bZtWJOyXfGo5dv7DGXJUzee+p930Od0j8QNceNHJffOTr2"
        b"kOJe93mWG+nPdLsG6fz++MV5h1OGr0N9yf3N2ydzQ5x/E9Aw/s9xzmOpULnKtsSZqc/rr"
        b"RQdf/Lu/ckKE9xU5VRuNehbzTr6789a+P2lt2zk5cFqe3N2289+j/hfH2X39/+nvc5vTW"
        b"a/+83pvWqY3e93JWYsmup693HzCOPBk0LI9O7PtiqawN9y8eaTV75DLLL2dNWqTLsTsOn"
        b"7wy0fTe5oLH//7eNf89Co3dRUHJmLRh20s/xhYJkoeYdBgYEhJLEkEJ4uKKkgKIJQyjI3"
        b"gKeOveVVEFAMDY6bSPTMmBkVGMWAqKdF/uviB+n/GwlgGce49MrWMUw/IetlVih46o7Y4"
        b"0uZe/t9lt85aMUrdWhjueTHRd1nr1uK830feH74vcPKU2pkbP4SZnta5PhC9dfPTqvv7f"
        b"n068XRDRDzLuv8Oa5p1L+02ZN127vp6mzSzzFqpLkmbwyl131J1xW58YlcxXSWs0PTbpT"
        b"z28ZUnE/e+NN93weAd40a/zzJ7+Re/v+R7+f3VBVFJCyZsv523ySJ12t7Nt5b8uBu8zuJ"
        b"2Laer//nZCkbXlxtYXvvA8+VSVsCRpo8BawtftKWyZBjkWa6/0X7qXfbF9reH/ro6S63Y"
        b"rCj8t8cltPIOj9H/8LyIxj6bMsZVVtu+ngj6MCNV5JXhOs07RXWxrb3xsqJMDRksx/5bO"
        b"bNtevXz2cdpzzI19Roede4NXxAyK9Dlrtp8JtELLNPWbBe9HfJlj1Hiv69erIFBnX/Pe1"
        b"4QnzLD+p2AiTc383/P+7sW3WoxnXra49iJKJeZy7gc9Z02S57qrvWW3day501VhsbPtfK"
        b"C5nyBG9qjr08E59KY1vUTGRg7mRsCGBimFa+3sTPg7WYCSTBGRgEAzEOeH04EAAA="
    )]

    def run_cmd(self, vm, cmd, user="root"):
        '''Run a command *cmd* in a *vm* as *user*. Return its exit code.

        :type self: vanir.tests.SystemTestCase | VmUpdatesMixin
        :param vanir.vm.vanirvm.VanirVM vm: VM object to run command in
        :param str cmd: command to execute
        :param std user: user to execute command as
        :return int: command exit code
        '''
        try:
            self.loop.run_until_complete(vm.run_for_stdio(cmd))
        except subprocess.CalledProcessError as e:
            return e.returncode
        return 0

    def assertRunCommandReturnCode(self, vm, cmd, expected_returncode):
        p = self.loop.run_until_complete(
            vm.run(cmd, user='root',
            stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        (stdout, stderr) = self.loop.run_until_complete(p.communicate())
        self.assertIn(
            self.loop.run_until_complete(p.wait()), expected_returncode,
            '{}: {}\n{}'.format(cmd, stdout, stderr))

    def setUp(self):
        '''
        :type self: vanir.tests.SystemTestCase | VmUpdatesMixin
        '''
        if not self.template.count('debian') and \
                not self.template.count('fedora'):
            self.skipTest("Template {} not supported by this test".format(
                self.template))
        super(VmUpdatesMixin, self).setUp()

        self.update_cmd = None
        if self.template.count("debian"):
            self.update_cmd = "set -o pipefail; apt-get update 2>&1 | " \
                              "{ ! grep '^W:\|^E:'; }"
            self.upgrade_cmd = "apt-get -V dist-upgrade -y"
            self.install_cmd = "apt-get install -y {}"
            self.install_test_cmd = "dpkg -l {}"
            self.exit_code_ok = [0]
        elif self.template.count("fedora"):
            cmd = "yum"
            try:
                # assume template name in form "fedora-XX-suffix"
                if int(self.template.split("-")[1]) > 21:
                    cmd = "dnf"
            except ValueError:
                pass
            self.update_cmd = "{cmd} clean all; {cmd} check-update".format(
                cmd=cmd)
            self.upgrade_cmd = "{cmd} upgrade -y".format(cmd=cmd)
            self.install_cmd = cmd + " install -y {}"
            self.install_test_cmd = "rpm -q {}"
            self.exit_code_ok = [0, 100]

        self.init_default_template(self.template)
        self.init_networking()
        self.testvm1 = self.app.add_new_vm(
            vanir.vm.appvm.AppVM,
            name=self.make_vm_name('vm1'),
            label='red')
        self.loop.run_until_complete(self.testvm1.create_on_disk())

    def test_000_simple_update(self):
        '''
        :type self: vanir.tests.SystemTestCase | VmUpdatesMixin
        '''
        self.app.save()
        self.testvm1 = self.app.domains[self.testvm1.qid]
        self.loop.run_until_complete(self.testvm1.start())
        self.assertRunCommandReturnCode(self.testvm1,
            self.update_cmd, self.exit_code_ok)

    def create_repo_apt(self, version=0):
        '''
        :type self: vanir.tests.SystemTestCase | VmUpdatesMixin
        '''
        pkg_file_name = "test-pkg_1.{}-1_amd64.deb".format(version)
        self.loop.run_until_complete(self.netvm_repo.run_for_stdio('''
            mkdir -p /tmp/apt-repo \
            && cd /tmp/apt-repo \
            && base64 -d | zcat > {}
            '''.format(pkg_file_name),
            input=self.DEB_PACKAGE_GZIP_BASE64[version]))
        # do not assume dpkg-scanpackage installed
        packages_path = "dists/test/main/binary-amd64/Packages"
        self.loop.run_until_complete(self.netvm_repo.run_for_stdio('''
            mkdir -p /tmp/apt-repo/dists/test/main/binary-amd64 \
            && cd /tmp/apt-repo \
            && cat > {packages} \
            && echo MD5sum: $(openssl md5 -r {pkg} | cut -f 1 -d ' ') \
                >> {packages} \
            && echo SHA1: $(openssl sha1 -r {pkg} | cut -f 1 -d ' ') \
                >> {packages} \
            && echo SHA256: $(openssl sha256 -r {pkg} | cut -f 1 -d ' ') \
                >> {packages} \
            && sed -i -e "s,@SIZE@,$(stat -c %s {pkg})," {packages} \
            && gzip < {packages} > {packages}.gz
            '''.format(pkg=pkg_file_name, packages=packages_path),
            input='''\
Package: test-pkg
Version: 1.{version}-1
Architecture: amd64
Maintainer: unknown <user@host>
Installed-Size: 25
Filename: {pkg}
Size: @SIZE@
Section: unknown
Priority: optional
Description: Test package'''.format(pkg=pkg_file_name, version=version).encode(
                'utf-8')))

        self.loop.run_until_complete(self.netvm_repo.run_for_stdio('''
            mkdir -p /tmp/apt-repo/dists/test \
            && cd /tmp/apt-repo/dists/test \
            && cat > Release \
            && echo '' $(sha256sum {p} | cut -f 1 -d ' ') $(stat -c %s {p}) {p}\
                >> Release \
            && echo '' $(sha256sum {z} | cut -f 1 -d ' ') $(stat -c %s {z}) {z}\
                >> Release
            '''.format(p='main/binary-amd64/Packages',
                    z='main/binary-amd64/Packages.gz'),
            input=b'''\
Label: Test repo
Suite: test
Codename: test
Date: Tue, 27 Oct 2015 03:22:09 UTC
Architectures: amd64
Components: main
SHA256:
'''))

    def create_repo_yum(self, version=0):
        '''
        :type self: vanir.tests.SystemTestCase | VmUpdatesMixin
        '''
        pkg_file_name = "test-pkg-1.{}-1.fc21.x86_64.rpm".format(version)
        self.loop.run_until_complete(self.netvm_repo.run_for_stdio('''
            mkdir -p /tmp/yum-repo \
            && cd /tmp/yum-repo \
            && base64 -d | zcat > {}
            '''.format(pkg_file_name), input=self.RPM_PACKAGE_GZIP_BASE64[
            version]))

        # createrepo is installed by default in Fedora template
        self.loop.run_until_complete(self.netvm_repo.run_for_stdio(
            'createrepo /tmp/yum-repo'))

    def create_repo_and_serve(self):
        '''
        :type self: vanir.tests.SystemTestCase | VmUpdatesMixin
        '''
        if self.template.count("debian") or self.template.count("whonix"):
            self.create_repo_apt()
            self.loop.run_until_complete(self.netvm_repo.run(
                'cd /tmp/apt-repo && python -m SimpleHTTPServer 8080',
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        elif self.template.count("fedora"):
            self.create_repo_yum()
            self.loop.run_until_complete(self.netvm_repo.run(
                'cd /tmp/yum-repo && python -m SimpleHTTPServer 8080',
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        else:
            # not reachable...
            self.skipTest("Template {} not supported by this test".format(
                self.template))

    def add_update_to_repo(self):
        if self.template.count("debian") or self.template.count("whonix"):
            self.create_repo_apt(1)
        elif self.template.count("fedora"):
            self.create_repo_yum(1)

    def configure_test_repo(self):
        """
        Configure test repository in test-vm and disable rest of them.
        The critical part is to use "localhost" - this will work only when
        accessed through update proxy and this is exactly what we want to
        test here.

        :type self: vanir.tests.SystemTestCase | VmUpdatesMixin
        """

        if self.template.count("debian") or self.template.count("whonix"):
            self.loop.run_until_complete(self.testvm1.run_for_stdio(
                "rm -f /etc/apt/sources.list.d/* &&"
                "echo 'deb [trusted=yes] http://localhost:8080 test main' "
                "> /etc/apt/sources.list",
                user="root"))
        elif self.template.count("fedora"):
            self.loop.run_until_complete(self.testvm1.run_for_stdio(
                "rm -f /etc/yum.repos.d/*.repo &&"
                "echo '[test]' > /etc/yum.repos.d/test.repo &&"
                "echo 'name=Test repo' >> /etc/yum.repos.d/test.repo &&"
                "echo 'gpgcheck=0' >> /etc/yum.repos.d/test.repo &&"
                "echo 'baseurl=http://localhost:8080/'"
                " >> /etc/yum.repos.d/test.repo",
                user="root"
            ))
        else:
            # not reachable...
            self.skipTest("Template {} not supported by this test".format(
                self.template))

    def test_010_update_via_proxy(self):
        '''
        Test both whether updates proxy works and whether is actually used
        by the VM

        :type self: vanir.tests.SystemTestCase | VmUpdatesMixin
        '''
        if self.template.count("minimal"):
            self.skipTest("Template {} not supported by this test".format(
                self.template))

        self.netvm_repo = self.app.add_new_vm(
            vanir.vm.appvm.AppVM,
            name=self.make_vm_name('net'),
            label='red')
        self.netvm_repo.provides_network = True
        self.loop.run_until_complete(self.netvm_repo.create_on_disk())
        self.testvm1.netvm = self.netvm_repo
        self.netvm_repo.features['service.vanir-updates-proxy'] = True
        # TODO: consider also adding a test for the template itself
        self.testvm1.features['service.updates-proxy-setup'] = True
        self.app.save()

        # Setup test repo
        self.loop.run_until_complete(self.netvm_repo.start())
        self.create_repo_and_serve()

        # Configure local repo
        self.loop.run_until_complete(self.testvm1.start())
        self.configure_test_repo()

        with self.qrexec_policy('vanir.UpdatesProxy', self.testvm1,
                '$default', action='allow,target=' + self.netvm_repo.name):
            # update repository metadata
            self.assertRunCommandReturnCode(self.testvm1,
                self.update_cmd, self.exit_code_ok)

            # install test package
            self.assertRunCommandReturnCode(self.testvm1,
                self.install_cmd.format('test-pkg'), self.exit_code_ok)

            # verify if it was really installed
            self.assertRunCommandReturnCode(self.testvm1,
                self.install_test_cmd.format('test-pkg'), self.exit_code_ok)

    def test_020_updates_available_notification(self):
        # override with StandaloneVM
        self.testvm1 = self.app.add_new_vm(
            vanir.vm.standalonevm.StandaloneVM,
            name=self.make_vm_name('vm2'),
            label='red')
        tpl = self.app.domains[self.template]
        self.testvm1.clone_properties(tpl)
        self.testvm1.features.update(tpl.features)
        self.loop.run_until_complete(
            self.testvm1.clone_disk_files(tpl))
        self.loop.run_until_complete(self.testvm1.start())
        self.netvm_repo = self.testvm1

        self.create_repo_and_serve()
        self.configure_test_repo()

        self.loop.run_until_complete(
            self.testvm1.run_for_stdio(
                '/usr/lib/vanir/upgrades-status-notify',
                user='root',
            ))
        self.assertFalse(self.testvm1.features.get('updates-available', False))

        # update repository metadata
        self.assertRunCommandReturnCode(
            self.testvm1, self.update_cmd, self.exit_code_ok)

        # install test package
        self.assertRunCommandReturnCode(
            self.testvm1, self.install_cmd.format('test-pkg'), self.exit_code_ok)

        self.assertFalse(self.testvm1.features.get('updates-available', False))

        self.add_update_to_repo()
        # update repository metadata
        self.assertRunCommandReturnCode(
            self.testvm1, self.update_cmd, self.exit_code_ok)

        self.loop.run_until_complete(
            self.testvm1.run_for_stdio(
                '/usr/lib/vanir/upgrades-status-notify',
                user='root',
            ))
        self.assertTrue(self.testvm1.features.get('updates-available', False))

        # install updates
        self.assertRunCommandReturnCode(
            self.testvm1, self.upgrade_cmd, self.exit_code_ok)

        self.assertFalse(self.testvm1.features.get('updates-available', False))


def create_testcases_for_templates():
    yield from vanir.tests.create_testcases_for_templates('VmNetworking',
        VmNetworkingMixin, vanir.tests.SystemTestCase,
        module=sys.modules[__name__])
    yield from vanir.tests.create_testcases_for_templates('VmIPv6Networking',
        VmIPv6NetworkingMixin, vanir.tests.SystemTestCase,
        module=sys.modules[__name__])
    yield from vanir.tests.create_testcases_for_templates('VmUpdates',
        VmUpdatesMixin, vanir.tests.SystemTestCase,
        module=sys.modules[__name__])

def load_tests(loader, tests, pattern):
    tests.addTests(loader.loadTestsFromNames(
        create_testcases_for_templates()))
    return tests

vanir.tests.maybe_create_testcases_on_import(create_testcases_for_templates)
