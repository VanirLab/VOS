RPMS_DIR=rpm/

VERSION = 1
PATCHLEVEL = 1
SUBLEVEL = 0
EXTRAVERSION = -rc1
VERSION := $(shell cat version)

DIST_DOM0 ?= fc18

ifeq ($(OS),Windows_NT)
    CCFLAGS += -D WIN32
    ifeq ($(PROCESSOR_ARCHITEW6432),AMD64)
        CCFLAGS += -D AMD64
    else
        ifeq ($(PROCESSOR_ARCHITECTURE),AMD64)
            CCFLAGS += -D AMD64
        endif
        ifeq ($(PROCESSOR_ARCHITECTURE),x86)
            CCFLAGS += -D IA32
        endif
    endif
else
    UNAME_S := $(shell uname -s)
    ifeq ($(UNAME_S),Linux)
        CCFLAGS += -D LINUX
    endif
    ifeq ($(UNAME_S),Darwin)
        CCFLAGS += -D OSX
    endif
    UNAME_P := $(shell uname -p)
    ifeq ($(UNAME_P),x86_64)
        CCFLAGS += -D AMD64
    endif
    ifneq ($(filter %86,$(UNAME_P)),)
        CCFLAGS += -D IA32
    endif
    ifneq ($(filter arm%,$(UNAME_P)),)
        CCFLAGS += -D ARM
    endif
endif

PYTHON ?= python3

# That's VOS default commando line
PHONY := _all
_all:

ADMIN_API_METHODS_SIMPLE = \
	admin.vmclass.List \
	admin.Events \
	admin.backup.Execute \
	admin.backup.Info \
	admin.backup.Cancel \
	admin.label.Create \
	admin.label.Get \
	admin.label.List \
	admin.label.Index \
	admin.label.Remove \
	admin.pool.Add \
	admin.pool.Info \
	admin.pool.List \
	admin.pool.ListDrivers \
	admin.pool.Remove \
	admin.pool.Set.revisions_to_keep \
	admin.pool.volume.Info \
	admin.pool.volume.List \
	admin.pool.volume.ListSnapshots \
	admin.pool.volume.Resize \
	admin.pool.volume.Revert \
	admin.pool.volume.Set.revisions_to_keep \
	admin.pool.volume.Set.rw \
	admin.pool.volume.Snapshot \
	admin.property.Get \
	admin.property.GetDefault \
	admin.property.Help \
	admin.property.HelpRst \
	admin.property.List \
	admin.property.Reset \
	admin.property.Set \
	admin.vm.Create.AppVM \
	admin.vm.Create.DispVM \
	admin.vm.Create.StandaloneVM \
	admin.vm.Create.TemplateVM \
	admin.vm.CreateInPool.AppVM \
	admin.vm.CreateInPool.DispVM \
	admin.vm.CreateInPool.StandaloneVM \
	admin.vm.CreateInPool.TemplateVM \
	admin.vm.CreateDisposable \
	admin.vm.Kill \
	admin.vm.List \
	admin.vm.Pause \
	admin.vm.Remove \
	admin.vm.Shutdown \
	admin.vm.Start \
	admin.vm.Unpause \
	admin.vm.device.pci.Attach \
	admin.vm.device.pci.Available \
	admin.vm.device.pci.Detach \
	admin.vm.device.pci.List \
	admin.vm.device.pci.Set.persistent \
	admin.vm.device.block.Attach \
	admin.vm.device.block.Available \
	admin.vm.device.block.Detach \
	admin.vm.device.block.List \
	admin.vm.device.block.Set.persistent \
	admin.vm.device.mic.Attach \
	admin.vm.device.mic.Available \
	admin.vm.device.mic.Detach \
	admin.vm.device.mic.List \
	admin.vm.device.mic.Set.persistent \
	admin.vm.feature.CheckWithNetvm \
	admin.vm.feature.CheckWithTemplate \
	admin.vm.feature.CheckWithAdminVM \
	admin.vm.feature.CheckWithTemplateAndAdminVM \
	admin.vm.feature.Get \
	admin.vm.feature.List \
	admin.vm.feature.Remove \
	admin.vm.feature.Set \
	admin.vm.firewall.Flush \
	admin.vm.firewall.Get \
	admin.vm.firewall.Set \
	admin.vm.firewall.GetPolicy \
	admin.vm.firewall.SetPolicy \
	admin.vm.firewall.Reload \
	admin.vm.property.Get \
	admin.vm.property.GetDefault \
	admin.vm.property.Help \
	admin.vm.property.HelpRst \
	admin.vm.property.List \
	admin.vm.property.Reset \
	admin.vm.property.Set \
	admin.vm.tag.Get \
	admin.vm.tag.List \
	admin.vm.tag.Remove \
	admin.vm.tag.Set \
	admin.vm.volume.CloneFrom \
	admin.vm.volume.CloneTo \
	admin.vm.volume.Info \
	admin.vm.volume.List \
	admin.vm.volume.ListSnapshots \
	admin.vm.volume.Resize \
	admin.vm.volume.Revert \
	admin.vm.volume.Set.revisions_to_keep \
	admin.vm.volume.Set.rw \
	admin.vm.Stats \
	$(null)

ifeq ($(OS),Linux)
DATADIR ?= /var/lib/vanir
STATEDIR ?= /var/run/vanir
LOGDIR ?= /var/log/vanir
FILESDIR ?= /usr/share/vanir
else ifeq ($(OS),Windows_NT)
DATADIR ?= c:/vanir
STATEDIR ?= c:/vanir/state
LOGDIR ?= c:/vanir/log
FILESDIR ?= c:/program files/Invisible Things Lab/vanir
endif

help:
	@echo "make rpms                  -- generate binary rpm packages"
	@echo "make rpms-dom0             -- generate binary rpm packages for Dom0"
	@echo "make update-repo-current   -- copy newly generated rpms to vanir yum repo"
	@echo "make update-repo-current-testing  -- same, but to -current-testing repo"
	@echo "make update-repo-unstable  -- same, but to -testing repo"
	@echo "make update-repo-installer -- copy dom0 rpms to installer repo"
	@echo "make clean                 -- cleanup"

rpms: rpms-dom0

rpms-vm:
	@true

rpms-dom0:
	rpmbuild --define "_rpmdir $(RPMS_DIR)" -bb rpm_spec/core-dom0.spec
	rpmbuild --define "_rpmdir $(RPMS_DIR)" -bb rpm_spec/core-dom0-doc.spec
	rpm --addsign \
		$(RPMS_DIR)/x86_64/vanir-core-dom0-$(VERSION)*.rpm \
		$(RPMS_DIR)/noarch/vanir-core-dom0-doc-$(VERSION)*rpm

all:
	$(PYTHON) setup.py build
	$(MAKE) -C vanir-rpc all
	# Currently supported only on xen

install:
ifeq ($(OS),Linux)
	$(MAKE) install -C linux/systemd
	$(MAKE) install -C linux/aux-tools
	$(MAKE) install -C linux/system-config
endif
	$(PYTHON) setup.py install -O1 --skip-build --root $(DESTDIR)
	ln -s qvm-device $(DESTDIR)/usr/bin/qvm-block
	ln -s qvm-device $(DESTDIR)/usr/bin/qvm-pci
	ln -s qvm-device $(DESTDIR)/usr/bin/qvm-usb
	install -d $(DESTDIR)/usr/share/man/man1
	ln -s qvm-device.1.gz $(DESTDIR)/usr/share/man/man1/qvm-block.1.gz
	ln -s qvm-device.1.gz $(DESTDIR)/usr/share/man/man1/qvm-pci.1.gz
	ln -s qvm-device.1.gz $(DESTDIR)/usr/share/man/man1/qvm-usb.1.gz
	$(MAKE) install -C relaxng
	mkdir -p $(DESTDIR)/etc/vanir
ifeq ($(BACKEND_VMM),xen)
	# Currently supported only on xen
	cp etc/qmemman.conf $(DESTDIR)/etc/vanir/
endif
	mkdir -p $(DESTDIR)/etc/vanir-rpc/policy
	mkdir -p $(DESTDIR)/usr/libexec/vanir
	cp vanir-rpc-policy/vanir.FeaturesRequest.policy $(DESTDIR)/etc/vanir-rpc/policy/vanir.FeaturesRequest
	cp vanir-rpc-policy/vanir.Filecopy.policy $(DESTDIR)/etc/vanir-rpc/policy/vanir.Filecopy
	cp vanir-rpc-policy/vanir.OpenInVM.policy $(DESTDIR)/etc/vanir-rpc/policy/vanir.OpenInVM
	cp vanir-rpc-policy/vanir.OpenURL.policy $(DESTDIR)/etc/vanir-rpc/policy/vanir.OpenURL
	cp vanir-rpc-policy/vanir.VMShell.policy $(DESTDIR)/etc/vanir-rpc/policy/vanir.VMShell
	cp vanir-rpc-policy/vanir.VMRootShell.policy $(DESTDIR)/etc/vanir-rpc/policy/vanir.VMRootShell
	cp vanir-rpc-policy/vanir.NotifyUpdates.policy $(DESTDIR)/etc/vanir-rpc/policy/vanir.NotifyUpdates
	cp vanir-rpc-policy/vanir.NotifyTools.policy $(DESTDIR)/etc/vanir-rpc/policy/vanir.NotifyTools
	cp vanir-rpc-policy/vanir.GetImageRGBA.policy $(DESTDIR)/etc/vanir-rpc/policy/vanir.GetImageRGBA
	cp vanir-rpc-policy/vanir.GetRandomizedTime.policy $(DESTDIR)/etc/vanir-rpc/policy/vanir.GetRandomizedTime
	cp vanir-rpc-policy/vanir.NotifyTools.policy $(DESTDIR)/etc/vanir-rpc/policy/vanir.NotifyTools
	cp vanir-rpc-policy/vanir.NotifyUpdates.policy $(DESTDIR)/etc/vanir-rpc/policy/vanir.NotifyUpdates
	cp vanir-rpc-policy/vanir.OpenInVM.policy $(DESTDIR)/etc/vanir-rpc/policy/vanir.OpenInVM
	cp vanir-rpc-policy/vanir.StartApp.policy $(DESTDIR)/etc/vanir-rpc/policy/vanir.StartApp
	cp vanir-rpc-policy/vanir.VMShell.policy $(DESTDIR)/etc/vanir-rpc/policy/vanir.VMShell
	cp vanir-rpc-policy/vanir.UpdatesProxy.policy $(DESTDIR)/etc/vanir-rpc/policy/vanir.UpdatesProxy
	cp vanir-rpc-policy/vanir.GetDate.policy $(DESTDIR)/etc/vanir-rpc/policy/vanir.GetDate
	cp vanir-rpc-policy/policy.RegisterArgument.policy $(DESTDIR)/etc/vanir-rpc/policy/policy.RegisterArgument
	cp vanir-rpc/vanir.FeaturesRequest $(DESTDIR)/etc/vanir-rpc/
	cp vanir-rpc/vanir.GetDate $(DESTDIR)/etc/vanir-rpc/
	cp vanir-rpc/vanir.GetRandomizedTime $(DESTDIR)/etc/vanir-rpc/
	cp vanir-rpc/vanir.NotifyTools $(DESTDIR)/etc/vanir-rpc/
	cp vanir-rpc/vanir.NotifyUpdates $(DESTDIR)/etc/vanir-rpc/
	cp vanir-rpc/policy.RegisterArgument $(DESTDIR)/etc/vanir-rpc/
	install vanir-rpc/qubesd-query-fast $(DESTDIR)/usr/libexec/vanir/
	install -m 0755 qvm-tools/vanir-bug-report $(DESTDIR)/usr/bin/vanir-bug-report
	install -m 0755 qvm-tools/vanir-hcl-report $(DESTDIR)/usr/bin/vanir-hcl-report
	install -m 0755 qvm-tools/qvm-sync-clock $(DESTDIR)/usr/bin/qvm-sync-clock
	for method in $(ADMIN_API_METHODS_SIMPLE); do \
		ln -s ../../usr/libexec/vanir/qubesd-query-fast \
			$(DESTDIR)/etc/vanir-rpc/$$method || exit 1; \
	done
	install vanir-rpc/admin.vm.volume.Import $(DESTDIR)/etc/vanir-rpc/
	PYTHONPATH=.:test-packages vanir-rpc-policy/generate-admin-policy \
		--destdir=$(DESTDIR)/etc/vanir-rpc/policy \
		--exclude admin.vm.Create.AdminVM \
				  admin.vm.CreateInPool.AdminVM \
		          admin.vm.device.testclass.Attach \
				  admin.vm.device.testclass.Detach \
				  admin.vm.device.testclass.List \
				  admin.vm.device.testclass.Set.persistent \
				  admin.vm.device.testclass.Available
	# sanity check
	for method in $(DESTDIR)/etc/vanir-rpc/policy/admin.*; do \
		ls $(DESTDIR)/etc/vanir-rpc/$$(basename $$method) >/dev/null || exit 1; \
	done
	install -d $(DESTDIR)/etc/vanir-rpc/policy/include
	install -m 0644 vanir-rpc-policy/admin-local-ro \
		vanir-rpc-policy/admin-local-rwx \
		vanir-rpc-policy/admin-global-ro \
		vanir-rpc-policy/admin-global-rwx \
		$(DESTDIR)/etc/vanir-rpc/policy/include/

	mkdir -p "$(DESTDIR)$(FILESDIR)"
	cp -r templates "$(DESTDIR)$(FILESDIR)/templates"
	rm -f "$(DESTDIR)$(FILESDIR)/templates/README"

	mkdir -p $(DESTDIR)$(DATADIR)
	mkdir -p $(DESTDIR)$(DATADIR)/vm-templates
	mkdir -p $(DESTDIR)$(DATADIR)/appvms
	mkdir -p $(DESTDIR)$(DATADIR)/servicevms
	mkdir -p $(DESTDIR)$(DATADIR)/vm-kernels
	mkdir -p $(DESTDIR)$(DATADIR)/backup
	mkdir -p $(DESTDIR)$(DATADIR)/dvmdata
	mkdir -p $(DESTDIR)$(STATEDIR)
	mkdir -p $(DESTDIR)$(LOGDIR)

msi:
	rm -rf destinstdir
	mkdir -p destinstdir
	$(MAKE) install \
		DESTDIR=$(PWD)/destinstdir \
		PYTHON_SITEPATH=/site-packages \
		FILESDIR=/pfiles \
		BINDIR=/bin \
		DATADIR=/vanir \
		STATEDIR=/vanir/state \
		LOGDIR=/vanir/log
	# icons placeholder
	mkdir -p destinstdir/icons
	for i in blue gray green yellow orange black purple red; do touch destinstdir/icons/$$i.png; done
	candle -arch x64 -dversion=$(VERSION) installer.wxs
	light -b destinstdir -o core-admin.msm installer.wixobj
	rm -rf destinstdir
	
distcheck-hook:
	@echo "Checking disted files against files in git"
	@$(srcdir)/tools/check-for-missing.py $(srcdir) $(distdir) $(DIST_EXCLUDE)
