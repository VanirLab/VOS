#!/bin/sh
chgrp vanir /etc/xen
chmod 710 /etc/xen
chgrp vanir /var/run/xenstored/*
chmod 660 /var/run/xenstored/*
chgrp vanir /var/lib/xen
chmod 770 /var/lib/xen
chgrp vanir /var/log/xen
chmod 770 /var/log/xen
chgrp vanir /proc/xen/privcmd
chmod 660 /proc/xen/privcmd
chgrp vanir /proc/xen/xenbus
chmod 660 /proc/xen/xenbus
chgrp vanir /dev/xen/evtchn
chmod 660 /dev/xen/evtchn
chgrp -R vanir /var/log/xen
chmod -R g+rX /var/log/xen
chmod g+s /var/log/xen/console
