all:
	true

install:
	mkdir -p $(DESTDIR)/etc/xen/scripts
	cp vif-route-vanir $(DESTDIR)/etc/xen/scripts
	cp block-snapshot $(DESTDIR)/etc/xen/scripts
	ln -s block-snapshot $(DESTDIR)/etc/xen/scripts/block-origin
	install -d $(DESTDIR)/etc/xdg/autostart
	install -m 0644 qrexec-policy-agent.desktop $(DESTDIR)/etc/xdg/autostart/
	install -m 0644 -D tmpfiles-vanir.conf $(DESTDIR)/usr/lib/tmpfiles.d/vanir.conf
	install -d $(DESTDIR)/etc/dbus-1/system.d
	install -m 0644 dbus-org.vos.PolicyAgent.conf  \
		$(DESTDIR)/etc/dbus-1/system.d/org.vos.PolicyAgent.conf
	install -d $(DESTDIR)/etc/logrotate.d
	install -m 0644 logrotate-vanir \
		$(DESTDIR)/etc/logrotate.d/vanir
