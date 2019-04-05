import argparse
from collections import OrderedDict
import os
import re
import sys

STRIP_COMMENT = re.compile(r'\s*(?!^\# ([\w]+) is not set)#.*');
SET = re.compile(r'(^[\w]+)=')
UNSET = re.compile(r'^\# ([\w]+) is not set')

def strip(line):
    line = line.rstrip()
    line = STRIP_COMMENT.sub('', line)
    return line

def read_config(filename, into, sources=None, src=None):
    with open(filename) as f:
        for line in f:
            line = strip(line)
            m = SET.match(line)
            if m is None:
                m = UNSET.match(line)
            if m is not None:
                into[m.group(1)] = line
                if sources is not None:
                    sources[m.group(1)] = src

    return into

def do_merge(configs):
    options = OrderedDict()
    for configfile in reversed(configs):
        read_config(os.path.join(srcdir, configfile), options)

    for value in options.itervalues():
        print (value)

def update_config(old, new, sources, src, configfile):
    tmpname = configfile + ".tmp"
    infile = open(configfile)
    outfile = open(tmpname, "w")

    try:
        for line in infile:
            stripped = strip(line)
            unset = False
            m = SET.match(stripped)
            if m is None:
                unset = True
                m = UNSET.match(stripped)
            handled = False
            if m is not None:
                option = m.group(1)
                assert option in old
                if not option in new:
                    if not unset:
                        handled = True
                elif sources[option] == src:
                    if new[option] != stripped:
                        outfile.write(new[option])
                        outfile.write("\n")
                        handled = True

            if not handled:
                outfile.write(line)
    except:
        outfile.close()
        os.remove(tmpname)
        raise

    infile.close()
    outfile.close()
    os.rename(tmpname, configfile)

def do_update(newfile, configs):
    old = OrderedDict()
    sources = dict()
    for configfile in reversed(configs):
        read_config(os.path.join(srcdir, configfile), old, sources, configfile)

    new = OrderedDict()
    read_config(newfile, new)

    for configfile in configs:
        update_config(old, new, sources, configfile, os.path.join(srcdir, configfile))

def usage():
    print (sys.stderr, "Usage: manage_configs [--srcdir=<SRCDIR>] [merge <CONFIGS> | update <NEWCONFIG> <CONFIGS>]")
    sys.exit(1)

parser = argparse.ArgumentParser()
parser.add_argument('--srcdir', metavar='SRCDIR', type=str, nargs='?',
                    help='source directory relative to which to look for configs', default='.')
parser.add_argument('args', metavar='ARGS', type=str, nargs='*')
args = parser.parse_args()

srcdir = args.srcdir

if len(args.args) < 1:
    usage()

if args.args[0] == 'merge':
    do_merge(args.args[1:])
elif args.args[0] == 'update':
    if len(args.args) < 3:
        usage()
    do_update(args.args[1], args.args[2:])
else:
    usage()

