#!/bin/sh

# Misc dom0 startup setup

/usr/lib/vanir/fix-dir-perms.sh
DOM0_MAXMEM=`/usr/sbin/xl info | grep total_memory | awk '{ print $3 }'`
xenstore-write /local/domain/0/memory/static-max $[ $DOM0_MAXMEM * 1024 ]

xl sched-credit -d 0 -w 2000
cp /var/lib/vanir/vanir.xml /var/lib/vanir/backup/vanir-$(date +%F-%T).xml

/usr/lib/vanir/cleanup-dispvms

# Hide mounted devices from vanir-block list (at first udev run, only / is mounted)
udevadm trigger --action=change --subsystem-match=block
