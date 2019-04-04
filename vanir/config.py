import os.path

vanir_base_dir = "/var/lib/vanir"
system_path = {
    'vanir_guid_path': '/usr/bin/vanir-guid',
    'qrexec_daemon_path': '/usr/lib/vanir/qrexec-daemon',
    'qrexec_client_path': '/usr/lib/vanir/qrexec-client',
    'vanirdb_daemon_path': '/usr/sbin/vanirdb-daemon',

    # Relative to vanir_base_dir
    'vanir_appvms_dir': 'appvms',
    'vanir_templates_dir': 'vm-templates',
    'vanir_servicevms_dir': 'servicevms',
    'vanir_store_filename': 'vanir.xml',
    'vanir_kernels_base_dir': 'vm-kernels',

    # qubes_icon_dir is obsolete
    # use QIcon.fromTheme() where applicable
    'vanir_icon_dir': '/usr/share/icons/hicolor/128x128/devices',

    'qrexec_policy_dir': '/etc/vanir-rpc/policy',

    'config_template_pv': '/usr/share/vanir/vm-template.xml',
}

vm_files = {
    'root_img': 'root.img',
    'rootcow_img': 'root-cow.img',
    'volatile_img': 'volatile.img',
    'clean_volatile_img': 'clean-volatile.img.tar',
    'private_img': 'private.img',
    'kernels_subdir': 'kernels',
    'firewall_conf': 'firewall.xml',
    'whitelisted_appmenus': 'whitelisted-appmenus.list',
    'updates_stat_file': 'updates.stat',
}

defaults = {
    'libvirt_uri': 'xen:///',
    'memory': 400,
    'hvm_memory': 400,
    'kernelopts': "nopat",
    'kernelopts_pcidevs': "nopat iommu=soft swiotlb=8192",
    'kernelopts_common': ('root=/dev/mapper/dmroot ro nomodeset console=hvc0 '
             'rd_NO_PLYMOUTH rd.plymouth.enable=0 plymouth.enable=0 '),

    'dom0_update_check_interval': 6*3600,

    'private_img_size': 2*1024*1024*1024,
    'root_img_size': 10*1024*1024*1024,

    'pool_configs': {
        # create file(-reflink) pool even when the default one is LVM
        'varlibqubes': {'dir_path': vanir_base_dir,
                    'name': 'varlibqubes'},
        'linux-kernel': {
            'dir_path': os.path.join(vanir_base_dir,
                                     system_path['vanir_kernels_base_dir']),
            'driver': 'linux-kernel',
            'name': 'linux-kernel'
        }
    },

    # how long (in sec) to wait for VMs to shutdown,
    # before killing them (when used qvm-run with --wait option),
    'shutdown_counter_max': 60,

    'vm_default_netmask': "255.255.255.0",

    'appvm_label': 'red',
    'template_label': 'black',
    'servicevm_label': 'red',
}

max_qid = 254
max_dispid = 10000
#: built-in standard labels, if creating new one, allocate them above this
# number, at least until label index is removed from API
max_default_label = 8

#: profiles for admin.backup.* calls
backup_profile_dir = '/etc/vanir/backup'

#: site-local prefix for all VMs
vanir_ipv6_prefix = 'fd09:24ef:4179:0000'