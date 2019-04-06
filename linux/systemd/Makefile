UNITDIR ?= /usr/lib/systemd/system

all:
	true

install:
	mkdir -p $(DESTDIR)$(UNITDIR)
	cp vanir-core.service $(DESTDIR)$(UNITDIR)
	cp vanir-vm@.service $(DESTDIR)$(UNITDIR)
	cp vanir-qmemman.service $(DESTDIR)$(UNITDIR)
	cp vanirsd.service $(DESTDIR)$(UNITDIR)
	install -d $(DESTDIR)$(UNITDIR)/lvm2-pvscan@.service.d
	install -m 0644 lvm2-pvscan@.service.d_30_vanir.conf \
		$(DESTDIR)$(UNITDIR)/lvm2-pvscan@.service.d/30_vanir.conf