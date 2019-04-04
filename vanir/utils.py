import hashlib
import random
import string
import os
import re
import socket
import subprocess

import pkg_resources

import docutils
import docutils.core
import docutils.io
import vanir.exc


def get_timezone():
    # fc18
    if os.path.islink('/etc/localtime'):
        return '/'.join(os.readlink('/etc/localtime').split('/')[-2:])
    # <=fc17
    if os.path.exists('/etc/sysconfig/clock'):
        clock_config = open('/etc/sysconfig/clock', "r")
        clock_config_lines = clock_config.readlines()
        clock_config.close()
        zone_re = re.compile(r'^ZONE="(.*)"')
        for line in clock_config_lines:
            line_match = zone_re.match(line)
            if line_match:
                return line_match.group(1)
    # last resort way, some applications makes /etc/localtime
    # hardlink instead of symlink...
    tz_info = os.stat('/etc/localtime')
    if not tz_info:
        return None
    if tz_info.st_nlink > 1:
        p = subprocess.Popen(['find', '/usr/share/zoneinfo',
            '-inum', str(tz_info.st_ino), '-print', '-quit'],
            stdout=subprocess.PIPE)
        tz_path = p.communicate()[0].strip()
        return tz_path.replace(b'/usr/share/zoneinfo/', b'')
    return None


def format_doc(docstring):
    '''Return parsed documentation string, stripping RST markup.
    '''

    if not docstring:
        return ''

    # pylint: disable=unused-variable
    output, pub = docutils.core.publish_programmatically(
        source_class=docutils.io.StringInput,
        source=' '.join(docstring.strip().split()),
        source_path=None,
        destination_class=docutils.io.NullOutput, destination=None,
        destination_path=None,
        reader=None, reader_name='standalone',
        parser=None, parser_name='restructuredtext',
        writer=None, writer_name='null',
        settings=None, settings_spec=None, settings_overrides=None,
        config_section=None, enable_exit_status=None)
    return pub.writer.document.astext()

def parse_size(size):
    units = [
        ('K', 1000), ('KB', 1000),
        ('M', 1000 * 1000), ('MB', 1000 * 1000),
        ('G', 1000 * 1000 * 1000), ('GB', 1000 * 1000 * 1000),
        ('Ki', 1024), ('KiB', 1024),
        ('Mi', 1024 * 1024), ('MiB', 1024 * 1024),
        ('Gi', 1024 * 1024 * 1024), ('GiB', 1024 * 1024 * 1024),
    ]

    size = size.strip().upper()
    if size.isdigit():
        return int(size)

    for unit, multiplier in units:
        if size.endswith(unit.upper()):
            size = size[:-len(unit)].strip()
            return int(size) * multiplier

    raise vanir.exc.VanirException("Invalid size: {0}.".format(size))

def mbytes_to_kmg(size):
    if size > 1024:
        return "%d GiB" % (size / 1024)

    return "%d MiB" % size


def kbytes_to_kmg(size):
    if size > 1024:
        return mbytes_to_kmg(size / 1024)

    return "%d KiB" % size


def bytes_to_kmg(size):
    if size > 1024:
        return kbytes_to_kmg(size / 1024)

    return "%d B" % size


def size_to_human(size):
    """Humane readable size, with 1/10 precision"""
    if size < 1024:
        return str(size)
    if size < 1024 * 1024:
        return str(round(size / 1024.0, 1)) + ' KiB'
    if size < 1024 * 1024 * 1024:
        return str(round(size / (1024.0 * 1024), 1)) + ' MiB'

    return str(round(size / (1024.0 * 1024 * 1024), 1)) + ' GiB'


def urandom(size):
    rand = os.urandom(size)
    if rand is None:
        raise IOError('failed to read urandom')
    return hashlib.sha512(rand).digest()


def get_entry_point_one(group, name):
    epoints = tuple(pkg_resources.iter_entry_points(group, name))
    if not epoints:
        raise KeyError(name)
    if len(epoints) > 1:
        raise TypeError(
            'more than 1 implementation of {!r} found: {}'.format(name,
                ', '.join('{}.{}'.format(ep.module_name, '.'.join(ep.attrs))
                    for ep in epoints)))
    return epoints[0].load()


def random_string(length=5):
    ''' Return random string consisting of ascii_leters and digits '''
    return ''.join(random.choice(string.ascii_letters + string.digits)
                   for _ in range(length))

def systemd_notify():
    '''Notify systemd'''
    nofity_socket = os.getenv('NOTIFY_SOCKET')
    if not nofity_socket:
        return
    if nofity_socket.startswith('@'):
        nofity_socket = '\0' + nofity_socket[1:]
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock.connect(nofity_socket)
    sock.sendall(b'READY=1')
    sock.close()

def match_vm_name_with_special(vm, name):
    '''Check if *vm* matches given name, which may be specified as @tag:...
    or @type:...'''
    if name.startswith('@tag:'):
        return name[len('@tag:'):] in vm.tags
    if name.startswith('@type:'):
        return name[len('@type:'):] == vm.__class__.__name__
    return name == vm.name