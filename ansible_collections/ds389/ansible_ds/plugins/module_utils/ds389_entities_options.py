#!/usr/bin/python3

# --- BEGIN COPYRIGHT BLOCK ---
# Copyright (C) 2022 Red Hat, Inc.
# All rights reserved.
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# --- END COPYRIGHT BLOCK ---
#

# *** WARNING! DO NOT MODIFY THIS FILE. ***
# This file is generated from following files:
#  - utils/gendoc.py
#  - ansible_collections/ds389/ansible_ds/plugins/module_utils/ds389_entities.py
# by using 'make gensrc'

# pylint: disable=line-too-long

"""This module contains the part of the ds389_module argspec (below ds389 dict)."""

CONTENT_OPTIONS = {
    'state': {
        'description': """If 'state' is 'absent' then all instances are removed.""",
        'required': False,
        'default': 'present',
        'type': 'str',
        'choices': (
            'present',
            'updated',
            'absent',
        ),
    },
    'ds389_prefix': {
        'description': '389 Directory Service non standard installation path.',
        'required': False,
        'type': 'str',
    },
    'ds389_agmts': {
        'description': 'List of ds389_agmts options.',
        'required': False,
        'type': 'list',
        'elements': 'dict',
        'options': {
            'name': {
                'description': """ds389_agmt's name.""",
                'type': 'str',
                'required': True,
            },
            'state': {
                'description': 'Indicate whether the replication agreement is added(present), modified(updated), or removed(absent).',
                'required': False,
                'type': 'str',
            },
            'changelogencryptionalgorithm': {
                'description': 'Encryption algorithm used to encrypt the changelog..',
                'required': False,
                'type': 'str',
            },
            'changelogmaxage': {
                'description': 'Changelog record lifetime.',
                'required': False,
                'type': 'str',
            },
            'changelogmaxentries': {
                'description': 'Max number of changelog records.',
                'required': False,
                'type': 'str',
            },
            'changelogsymetrickey': {
                'description': 'Encryption key (if changelog is encrypted).',
                'required': False,
                'type': 'str',
            },
            'changelogtriminterval': {
                'description': 'Time (in seconds) between two runs of the changlog trimming. .',
                'required': False,
                'type': 'str',
            },
            'replicabackoffmax': {
                'description': 'Maximum delay before retrying to send updates after a recoverable failure.',
                'required': False,
                'type': 'str',
            },
            'replicabackoffmin': {
                'description': 'Minimum time before retrying to send updates after a recoverable failure.',
                'required': False,
                'type': 'str',
            },
            'replicabinddn': {
                'description': 'The DN used to connect to the target instance.',
                'required': False,
                'type': 'str',
            },
            'replicabinddngroup': {
                'description': 'DN of the group containing users allowed to replay updates on this replica.',
                'required': False,
                'type': 'str',
            },
            'replicabinddngroupcheckinterval': {
                'description': 'Interval between detection of the bind dn group changes.',
                'required': False,
                'type': 'str',
            },
            'replicabindmethod': {
                'description': 'The bind Method.',
                'required': False,
                'type': 'str',
            },
            'replicabootstrapbinddn': {
                'description': 'The fallback bind dn used after getting authentication error.',
                'required': False,
                'type': 'str',
            },
            'replicabootstrapbindmethod': {
                'description': 'The fallback bind method.',
                'required': False,
                'type': 'str',
            },
            'replicabootstrapcredentials': {
                'description': 'The credential associated with the fallback bind.',
                'required': False,
                'type': 'str',
            },
            'replicabootstraptransportinfo': {
                'description': 'The encryption method used on the connection after an authentication error..',
                'required': False,
                'type': 'str',
            },
            'replicabusywaittime': {
                'description': 'The amount of time in seconds a supplier should wait after a consumer sends back a busy response before making another attempt to acquire access.',
                'required': False,
                'type': 'str',
            },
            'replicacredentials': {
                'description': 'The credentials associated with the bind.',
                'required': False,
                'type': 'str',
            },
            'replicaenabled': {
                'description': 'A flags telling wheter the replication agreement is enabled or not..',
                'required': False,
                'type': 'str',
            },
            'replicaflowcontrolpause': {
                'description': 'the time in milliseconds to pause after reaching the number of entries and updates set in the ReplicaFlowControlWindow parameter is reached..',
                'required': False,
                'type': 'str',
            },
            'replicaflowcontrolwindow': {
                'description': 'The maximum number of entries and updates sent by a supplier, which are not acknowledged by the consumer. After reaching the limit, the supplier pauses the replication agreement for the time set in the nsDS5ReplicaFlowControlPause parameter.',
                'required': False,
                'type': 'str',
            },
            'replicahost': {
                'description': 'The target instance hostname.',
                'required': False,
                'type': 'str',
            },
            'replicaid': {
                'description': 'The unique ID for suppliers in a given replication environment (between 1 and 65534)..',
                'required': False,
                'type': 'str',
            },
            'replicaignoremissingchange': {
                'description': 'Tells how the replication behaves when a csn is missing..',
                'required': False,
                'type': 'str',
            },
            'replicaport': {
                'description': 'Target instance port.',
                'required': False,
                'type': 'str',
            },
            'replicaprecisetombstonepurging': {
                'description': '???.',
                'required': False,
                'type': 'str',
            },
            'replicaprotocoltimeout': {
                'description': 'Timeout used when stopping replication to abort ongoing operations..',
                'required': False,
                'type': 'str',
            },
            'replicapurgedelay': {
                'description': 'The maximum age of deleted entries (tombstone entries) and entry state information..',
                'required': False,
                'type': 'str',
            },
            'replicareferral': {
                'description': 'The user-defined referrals (returned when a write operation is attempted on a hub or a consumer..',
                'required': False,
                'type': 'str',
            },
            'replicareleasetimeout': {
                'description': 'The timeout period (in seconds) after which a master will release a replica..',
                'required': False,
                'type': 'str',
            },
            'replicarole': {
                'description': 'The replica role..',
                'required': False,
                'type': 'str',
            },
            'replicasessionpausetime': {
                'description': 'The amount of time in seconds a supplier should wait between update sessions.',
                'required': False,
                'type': 'str',
            },
            'replicastripattrs': {
                'description': 'Fractionnal replication attributes that does get replicated if the operation modifier list contains only these agreement.',
                'required': False,
                'type': 'str',
            },
            'replicatimeout': {
                'description': 'The number of seconds outbound LDAP operations waits for a response from the remote replica before timing out and failing.',
                'required': False,
                'type': 'str',
            },
            'replicatombstonepurgeinterval': {
                'description': 'The time interval in seconds between purge operation cycles..',
                'required': False,
                'type': 'str',
            },
            'replicatransportinfo': {
                'description': 'The encryption method used on the connection.',
                'required': False,
                'type': 'str',
            },
            'replicaupdateschedule': {
                'description': 'The replication schedule..',
                'required': False,
                'type': 'str',
            },
            'replicawaitforasyncresults': {
                'description': 'The time in milliseconds for which a supplier waits if the consumer is not ready before resending data..',
                'required': False,
                'type': 'str',
            },
            'replicatedattributelist': {
                'description': 'List of replication attribute ithat are not replicated in fractionnal replication.',
                'required': False,
                'type': 'str',
            },
            'replicatedattributelisttotal': {
                'description': 'List of attributes that are not replicated during a total update.',
                'required': False,
                'type': 'str',
            },
            'chain_bind_dn': {
                'description': 'Desc.',
                'required': False,
                'type': 'str',
            },
            'chain_bind_pw': {
                'description': 'Desc.',
                'required': False,
                'type': 'str',
            },
            'chain_urls': {
                'description': 'Desc.',
                'required': False,
                'type': 'str',
            },
            'db_deadlock': {
                'description': 'Desc.',
                'required': False,
                'type': 'str',
            },
            'directory': {
                'description': 'Desc.',
                'required': False,
                'type': 'str',
            },
            'dn_cache_size': {
                'description': 'Desc.',
                'required': False,
                'type': 'str',
            },
            'entry_cache_number': {
                'description': 'Desc.',
                'required': False,
                'type': 'str',
            },
            'entry_cache_size': {
                'description': 'Desc.',
                'required': False,
                'type': 'str',
            },
            'fulltargetname': {
                'description': 'The resolved replica agreements target host.instance.backend..',
                'required': False,
                'type': 'str',
            },
            'readonly': {
                'description': 'Desc.',
                'required': False,
                'type': 'str',
            },
            'require_index': {
                'description': 'Desc.',
                'required': False,
                'type': 'str',
            },
            'sample_entries': {
                'description': 'Tells whether sample entries are created on this backend when the instance is created.',
                'required': False,
                'type': 'str',
            },
            'suffix': {
                'description': 'DN subtree root of entries managed by this backend..',
                'required': False,
                'type': 'str',
            },
            'target': {
                'description': 'The raw replica agreements target (pattern speficing the backend)..',
                'required': False,
                'type': 'str',
            },
        },
    },
    'ds389_server_instances': {
        'description': 'List of ds389_server_instances options.',
        'required': False,
        'type': 'list',
        'elements': 'dict',
        'options': {
            'name': {
                'description': """ds389_server_instance's name.""",
                'type': 'str',
                'required': True,
            },
            'state': {
                'description': 'Indicate whether the instance is added(present), modified(updated), or removed(absent).',
                'required': False,
                'default': 'present',
                'type': 'str',
                'choices': (
                    'present',
                    'absent',
                ),
            },
            'backup_dir': {
                'description': 'Directory containing the backup files.',
                'required': False,
                'type': 'str',
            },
            'bin_dir': {
                'description': 'Directory containing ns-slapd binary. Only set this parameter in a development environment.',
                'required': False,
                'type': 'str',
            },
            'cert_dir': {
                'description': 'Directory containing the NSS certificate databases.',
                'required': False,
                'type': 'str',
            },
            'config_dir': {
                'description': 'Sets the configuration directory of the instance (containing the dse.ldif file).',
                'required': False,
                'type': 'str',
            },
            'data_dir': {
                'description': 'Sets the location of Directory Server shared static data. Only set this parameter in a development environment.',
                'required': False,
                'type': 'str',
            },
            'db_dir': {
                'description': 'Sets the database directory of the instance.',
                'required': False,
                'type': 'str',
            },
            'db_home_dir': {
                'description': 'Sets the memory-mapped database files location of the instance.',
                'required': False,
                'type': 'str',
            },
            'db_lib': {
                'description': 'Select the database implementation library.',
                'required': False,
                'type': 'str',
                'choices': (
                    'bdb',
                    'mdb',
                ),
            },
            'full_machine_name': {
                'description': """The fully qualified hostname (FQDN) of this system. When installing this instance with GSSAPI authentication behind a load balancer, set this parameter to the FQDN of the load balancer and, additionally, set "strict_host_checking" to "false".""",
                'required': False,
                'type': 'str',
            },
            'group': {
                'description': 'Sets the group name the ns-slapd process will use after the service started.',
                'required': False,
                'type': 'str',
            },
            'initconfig_dir': {
                'description': """Sets the directory of the operating system's rc configuration directory. Only set this parameter in a development environment.""",
                'required': False,
                'type': 'str',
            },
            'inst_dir': {
                'description': 'Directory containing instance-specific scripts.',
                'required': False,
                'type': 'str',
            },
            'instance_name': {
                'description': 'Sets the name of the instance..',
                'required': False,
                'type': 'str',
            },
            'ldapi': {
                'description': 'Sets the location of socket interface of the Directory Server.',
                'required': False,
                'type': 'str',
            },
            'ldif_dir': {
                'description': 'Directory containing the the instance import and export files.',
                'required': False,
                'type': 'str',
            },
            'lib_dir': {
                'description': 'Sets the location of Directory Server shared libraries. Only set this parameter in a development environment.',
                'required': False,
                'type': 'str',
            },
            'local_state_dir': {
                'description': 'Sets the location of Directory Server variable data. Only set this parameter in a development environment.',
                'required': False,
                'type': 'str',
            },
            'lock_dir': {
                'description': 'Directory containing the lock files.',
                'required': False,
                'type': 'str',
            },
            'nsslapd_backend_opt_level': {
                'description': 'This parameter can trigger experimental code to improve write performance.',
                'required': False,
                'default': '1',
                'type': 'int',
            },
            'nsslapd_directory': {
                'description': 'Default database directory.',
                'required': False,
                'default': '{ds389_prefix}/var/lib/dirsrv/slapd-{instname}/db',
                'type': 'str',
            },
            'nsslapd_exclude_from_export': {
                'description': 'list of attributes that are not exported.',
                'required': False,
                'default': 'entrydn entryid dncomp parentid numSubordinates tombstonenumsubordinates entryusn',
                'type': 'str',
            },
            'nsslapd_idlistscanlimit': {
                'description': 'The maximum number of entries a given index key may refer before the index is handled as unindexed..',
                'required': False,
                'default': '4000',
                'type': 'int',
            },
            'nsslapd_import_cachesize': {
                'description': 'Size of database cache when doing an import.',
                'required': False,
                'default': '16777216',
                'type': 'int',
            },
            'nsslapd_lookthroughlimit': {
                'description': 'The maximum number of entries that are looked in search operation before returning LDAP_ADMINLIMIT_EXCEEDED.',
                'required': False,
                'default': '5000',
                'type': 'int',
            },
            'nsslapd_mode': {
                'description': 'The database permission (mode) in octal.',
                'required': False,
                'default': '600',
                'type': 'int',
            },
            'nsslapd_pagedidlistscanlimit': {
                'description': 'idllistscanlimit when performing a paged search.',
                'required': False,
                'default': '0',
                'type': 'int',
            },
            'nsslapd_pagedlookthroughlimit': {
                'description': 'lookthroughlimit when performing a paged search.',
                'required': False,
                'default': '0',
                'type': 'int',
            },
            'nsslapd_rangelookthroughlimit': {
                'description': 'Sets a separate range look-through limit that applies to all users, including Directory Manager.',
                'required': False,
                'default': '5000',
                'type': 'int',
            },
            'nsslapd_search_bypass_filter_test': {
                'description': """Allowed values are: 'on', 'off' or 'verify'. If you enable the nsslapd-search-bypass-filter-test parameter, Directory Server bypasses filter checks when it builds candidate lists during a search. If you set the parameter to verify, Directory Server evaluates the filter against the search candidate entries.""",
                'required': False,
                'default': 'on',
                'type': 'str',
                'choices': (
                    'on',
                    'off',
                    'verify',
                ),
            },
            'nsslapd_search_use_vlv_index': {
                'description': 'enables and disables virtual list view (VLV) searches.',
                'required': False,
                'default': 'on',
                'type': 'str',
                'choices': (
                    'on',
                    'off',
                ),
            },
            'port': {
                'description': 'Sets the TCP port the instance uses for LDAP connections.',
                'required': False,
                'type': 'int',
            },
            'root_dn': {
                'description': """Sets the Distinquished Name (DN) of the administrator account for this instance. It is recommended that you do not change this value from the default 'cn=Directory Manager'.""",
                'required': False,
                'type': 'str',
            },
            'rootpw': {
                'description': """Sets the password of the "cn=Directory Manager" account ("root_dn" parameter). You can either set this parameter to a plain text password ds389_create hashes during the installation or to a "{algorithm}hash" string generated by the pwdhash utility. The password must be at least 8 characters long. Note that setting a plain text password can be a security risk if unprivileged users can read this INF file.""",
                'required': False,
                'type': 'str',
            },
            'run_dir': {
                'description': 'Directory containing the pid file.',
                'required': False,
                'type': 'str',
            },
            'sbin_dir': {
                'description': 'Sets the location where the Directory Server administration binaries are stored. Only set this parameter in a development environment.',
                'required': False,
                'type': 'str',
            },
            'schema_dir': {
                'description': 'Directory containing the schema files.',
                'required': False,
                'type': 'str',
            },
            'secure_port': {
                'description': 'Sets the TCP port the instance uses for TLS-secured LDAP connections (LDAPS).',
                'required': False,
                'type': 'int',
            },
            'self_sign_cert': {
                'description': """Sets whether the setup creates a self-signed certificate and enables TLS encryption during the installation. The certificate is not suitable for production, but it enables administrators to use TLS right after the installation. You can replace the self-signed certificate with a certificate issued by a Certificate Authority. If set to False, you can enable TLS later by importing a CA/Certificate and enabling 'dsconf <instance_name> config replace nsslapd-security=on.""",
                'required': False,
                'type': 'str',
            },
            'self_sign_cert_valid_months': {
                'description': 'Set the number of months the issued self-signed certificate will be valid..',
                'required': False,
                'type': 'str',
            },
            'selinux': {
                'description': """Enables SELinux detection and integration during the installation of this instance. If set to "True", ds389_create auto-detects whether SELinux is enabled. Set this parameter only to "False" in a development environment or if using a non root installation.""",
                'required': False,
                'type': 'bool',
            },
            'started': {
                'description': 'Indicate whether the instance is (or should be) started.',
                'required': False,
                'default': True,
                'type': 'bool',
            },
            'strict_host_checking': {
                'description': """Sets whether the server verifies the forward and reverse record set in the "full_machine_name" parameter. When installing this instance with GSSAPI authentication behind a load balancer, set this parameter to "false". Container installs imply "false".""",
                'required': False,
                'type': 'bool',
            },
            'sysconf_dir': {
                'description': 'sysconf directoryc.',
                'required': False,
                'type': 'str',
            },
            'systemd': {
                'description': """Enables systemd platform features. If set to "True", ds389_create auto-detects whether systemd is installed. Only set this parameter in a development environment or if using non root installation.""",
                'required': False,
                'type': 'bool',
            },
            'tmp_dir': {
                'description': 'Sets the temporary directory of the instance.',
                'required': False,
                'type': 'str',
            },
            'user': {
                'description': 'Sets the user name the ns-slapd process will use after the service started.',
                'required': False,
                'type': 'str',
            },
            'backends': {
                'description': 'List of backends options.',
                'required': False,
                'type': 'list',
                'elements': 'dict',
                'options': {
                    'name': {
                        'description': """backend's name.""",
                        'type': 'str',
                        'required': True,
                    },
                    'state': {
                        'description': 'Indicate whether the backend is added(present), modified(updated), or removed(absent).',
                        'required': False,
                        'default': 'present',
                        'type': 'str',
                        'choices': (
                            'present',
                            'updated',
                            'absent',
                        ),
                    },
                    'suffix': {
                        'description': 'DN subtree root of entries managed by this backend..',
                        'required': True,
                        'type': 'str',
                    },
                    'changelogencryptionalgorithm': {
                        'description': 'Encryption algorithm used to encrypt the changelog..',
                        'required': False,
                        'type': 'str',
                    },
                    'changelogmaxage': {
                        'description': 'Changelog record lifetime.',
                        'required': False,
                        'type': 'str',
                    },
                    'changelogmaxentries': {
                        'description': 'Max number of changelog records.',
                        'required': False,
                        'type': 'str',
                    },
                    'changelogsymetrickey': {
                        'description': 'Encryption key (if changelog is encrypted).',
                        'required': False,
                        'type': 'str',
                    },
                    'changelogtriminterval': {
                        'description': 'Time (in seconds) between two runs of the changlog trimming. .',
                        'required': False,
                        'type': 'str',
                    },
                    'replicabackoffmax': {
                        'description': 'Maximum delay before retrying to send updates after a recoverable failure.',
                        'required': False,
                        'type': 'int',
                    },
                    'replicabackoffmin': {
                        'description': 'Minimum time before retrying to send updates after a recoverable failure.',
                        'required': False,
                        'type': 'int',
                    },
                    'replicabinddn': {
                        'description': 'DN of the user allowed to replay updates on this replica.',
                        'required': False,
                        'type': 'str',
                    },
                    'replicabinddngroup': {
                        'description': 'DN of the group containing users allowed to replay updates on this replica.',
                        'required': False,
                        'type': 'str',
                    },
                    'replicabinddngroupcheckinterval': {
                        'description': 'Interval between detection of the bind dn group changes.',
                        'required': False,
                        'type': 'int',
                    },
                    'replicabindmethod': {
                        'description': 'The bind Method.',
                        'required': False,
                        'type': 'str',
                        'choices': (
                            'simple',
                            'sslclientauth',
                            'sasl/gssapi',
                            'sasl/digest-md5',
                        ),
                    },
                    'replicabootstrapbinddn': {
                        'description': 'The fallback bind dn used after getting authentication error.',
                        'required': False,
                        'type': 'str',
                    },
                    'replicabootstrapbindmethod': {
                        'description': 'The fallback bind method.',
                        'required': False,
                        'type': 'str',
                        'choices': (
                            'simple',
                            'sslclientauth',
                            'sasl/gssapi',
                            'sasl/digest-md5',
                        ),
                    },
                    'replicabootstrapcredentials': {
                        'description': 'The credential associated with the fallback bind.',
                        'required': False,
                        'type': 'str',
                    },
                    'replicabootstraptransportinfo': {
                        'description': 'The encryption method used on the connection after an authentication error..',
                        'required': False,
                        'type': 'str',
                        'choices': (
                            'ldap',
                            'tls',
                            'ssl',
                        ),
                    },
                    'replicacredentials': {
                        'description': 'The credential associated with the bind.',
                        'required': False,
                        'type': 'str',
                    },
                    'replicahost': {
                        'description': 'The target instance hostname.',
                        'required': False,
                        'type': 'str',
                    },
                    'replicaid': {
                        'description': 'The unique ID for suppliers in a given replication environment (between 1 and 65534)..',
                        'required': False,
                        'type': 'int',
                    },
                    'replicaport': {
                        'description': 'Target instance port.',
                        'required': False,
                        'type': 'int',
                    },
                    'replicaprecisetombstonepurging': {
                        'description': '???.',
                        'required': False,
                        'type': 'str',
                    },
                    'replicaprotocoltimeout': {
                        'description': 'Timeout used when stopping replication to abort ongoing operations..',
                        'required': False,
                        'type': 'int',
                    },
                    'replicapurgedelay': {
                        'description': 'The maximum age of deleted entries (tombstone entries) and entry state information..',
                        'required': False,
                        'type': 'str',
                    },
                    'replicareferral': {
                        'description': 'The user-defined referrals (returned when a write operation is attempted on a hub or a consumer..',
                        'required': False,
                        'type': 'list',
                    },
                    'replicareleasetimeout': {
                        'description': 'The timeout period (in seconds) after which a master will release a replica..',
                        'required': False,
                        'type': 'int',
                    },
                    'replicarole': {
                        'description': 'The replica role..',
                        'required': False,
                        'type': 'str',
                        'choices': (
                            'None',
                            'supplier',
                            'hub',
                            'consumer',
                        ),
                    },
                    'replicatombstonepurgeinterval': {
                        'description': 'The time interval in seconds between purge operation cycles..',
                        'required': False,
                        'type': 'int',
                    },
                    'replicatransportinfo': {
                        'description': 'The encryption method used on the connection.',
                        'required': False,
                        'type': 'str',
                        'choices': (
                            'ldap',
                            'tls',
                            'ssl',
                        ),
                    },
                    'replicaupdateschedule': {
                        'description': 'Time schedule presented as XXXX-YYYY 0123456, where XXXX is the starting hour,YYYY is the finishing hour, and the numbers 0123456 are the days of the week starting with Sunday..',
                        'required': False,
                        'type': 'list',
                    },
                    'replicawaitforasyncresults': {
                        'description': 'Delay in milliseconds before resending an update if consumer does not acknowledge it..',
                        'required': False,
                        'type': 'int',
                    },
                    'chain_bind_dn': {
                        'description': 'Desc.',
                        'required': False,
                        'type': 'str',
                    },
                    'chain_bind_pw': {
                        'description': 'Desc.',
                        'required': False,
                        'type': 'str',
                    },
                    'chain_urls': {
                        'description': 'Desc.',
                        'required': False,
                        'type': 'str',
                    },
                    'db_deadlock': {
                        'description': 'Desc.',
                        'required': False,
                        'type': 'str',
                    },
                    'directory': {
                        'description': 'Desc.',
                        'required': False,
                        'type': 'str',
                    },
                    'dn_cache_size': {
                        'description': 'Desc.',
                        'required': False,
                        'type': 'str',
                    },
                    'entry_cache_number': {
                        'description': 'Desc.',
                        'required': False,
                        'type': 'str',
                    },
                    'entry_cache_size': {
                        'description': 'Desc.',
                        'required': False,
                        'type': 'str',
                    },
                    'readonly': {
                        'description': 'Desc.',
                        'required': False,
                        'default': False,
                        'type': 'str',
                    },
                    'require_index': {
                        'description': 'Desc.',
                        'required': False,
                        'type': 'str',
                    },
                    'sample_entries': {
                        'description': 'Tells whether sample entries are created on this backend when the instance is created.',
                        'required': False,
                        'type': 'bool',
                    },
                    'agmts': {
                        'description': 'List of agmts options.',
                        'required': False,
                        'type': 'list',
                        'elements': 'dict',
                        'options': {
                            'name': {
                                'description': """agmt's name.""",
                                'type': 'str',
                                'required': True,
                            },
                            'state': {
                                'description': 'Indicate whether the replication agreement is added(present), modified(updated), or removed(absent).',
                                'required': False,
                                'default': 'present',
                                'type': 'str',
                                'choices': (
                                    'present',
                                    'updated',
                                    'absent',
                                ),
                            },
                            'replicabinddn': {
                                'description': 'The DN used to connect to the target instance.',
                                'required': False,
                                'type': 'str',
                            },
                            'replicabindmethod': {
                                'description': 'The bind Method.',
                                'required': False,
                                'type': 'str',
                                'choices': (
                                    'simple',
                                    'sslclientauth',
                                    'sasl/gssapi',
                                    'sasl/digest-md5',
                                ),
                            },
                            'replicabootstrapbinddn': {
                                'description': 'The fallback bind dn used after getting authentication error.',
                                'required': False,
                                'type': 'str',
                            },
                            'replicabootstrapbindmethod': {
                                'description': 'The fallback bind method.',
                                'required': False,
                                'type': 'str',
                                'choices': (
                                    'simple',
                                    'sslclientauth',
                                    'sasl/gssapi',
                                    'sasl/digest-md5',
                                ),
                            },
                            'replicabootstrapcredentials': {
                                'description': 'The credential associated with the fallback bind.',
                                'required': False,
                                'type': 'str',
                            },
                            'replicabootstraptransportinfo': {
                                'description': 'The encryption method used on the connection after an authentication error..',
                                'required': False,
                                'type': 'str',
                                'choices': (
                                    'ldap',
                                    'tls',
                                    'ssl',
                                ),
                            },
                            'replicabusywaittime': {
                                'description': 'The amount of time in seconds a supplier should wait after a consumer sends back a busy response before making another attempt to acquire access.',
                                'required': False,
                                'type': 'int',
                            },
                            'replicacredentials': {
                                'description': 'The credentials associated with the bind.',
                                'required': False,
                                'type': 'str',
                            },
                            'replicaenabled': {
                                'description': 'A flags telling wheter the replication agreement is enabled or not..',
                                'required': False,
                                'type': 'str',
                                'choices': (
                                    'on',
                                    'off',
                                ),
                            },
                            'replicaflowcontrolpause': {
                                'description': 'the time in milliseconds to pause after reaching the number of entries and updates set in the ReplicaFlowControlWindow parameter is reached..',
                                'required': False,
                                'type': 'int',
                            },
                            'replicaflowcontrolwindow': {
                                'description': 'The maximum number of entries and updates sent by a supplier, which are not acknowledged by the consumer. After reaching the limit, the supplier pauses the replication agreement for the time set in the nsDS5ReplicaFlowControlPause parameter.',
                                'required': False,
                                'type': 'int',
                            },
                            'replicahost': {
                                'description': 'The target instance hostname.',
                                'required': False,
                                'type': 'str',
                            },
                            'replicaignoremissingchange': {
                                'description': 'Tells how the replication behaves when a csn is missing..',
                                'required': False,
                                'type': 'str',
                                'choices': (
                                    'never',
                                    'once',
                                    'always',
                                    'on',
                                    'off',
                                ),
                            },
                            'replicaport': {
                                'description': 'Target instance port.',
                                'required': False,
                                'type': 'int',
                            },
                            'replicasessionpausetime': {
                                'description': 'The amount of time in seconds a supplier should wait between update sessions.',
                                'required': False,
                                'type': 'int',
                            },
                            'replicastripattrs': {
                                'description': 'Fractionnal replication attributes that does get replicated if the operation modifier list contains only these agreement.',
                                'required': False,
                                'type': 'list',
                            },
                            'replicatimeout': {
                                'description': 'The number of seconds outbound LDAP operations waits for a response from the remote replica before timing out and failing.',
                                'required': False,
                                'type': 'int',
                            },
                            'replicatransportinfo': {
                                'description': 'The encryption method used on the connection.',
                                'required': False,
                                'type': 'str',
                                'choices': (
                                    'ldap',
                                    'tls',
                                    'ssl',
                                ),
                            },
                            'replicaupdateschedule': {
                                'description': 'The replication schedule..',
                                'required': False,
                                'type': 'list',
                            },
                            'replicawaitforasyncresults': {
                                'description': 'The time in milliseconds for which a supplier waits if the consumer is not ready before resending data..',
                                'required': False,
                                'type': 'str',
                            },
                            'replicatedattributelist': {
                                'description': 'List of replication attribute ithat are not replicated in fractionnal replication.',
                                'required': False,
                                'type': 'list',
                            },
                            'replicatedattributelisttotal': {
                                'description': 'List of attributes that are not replicated during a total update.',
                                'required': False,
                                'type': 'list',
                            },
                        },
                    },
                    'indexes': {
                        'description': 'List of indexes options.',
                        'required': False,
                        'type': 'list',
                        'elements': 'dict',
                        'options': {
                            'name': {
                                'description': """index's name.""",
                                'type': 'str',
                                'required': True,
                            },
                            'state': {
                                'description': 'Indicate whether the index is added(present), modified(updated), or removed(absent).',
                                'required': False,
                                'default': 'present',
                                'type': 'str',
                                'choices': (
                                    'present',
                                    'updated',
                                    'absent',
                                ),
                            },
                            'indextype': {
                                'description': 'Determine the index types (pres,eq,sub,matchingRuleOid).',
                                'required': True,
                                'type': 'list',
                            },
                            'systemindex': {
                                'description': 'Tells if the index is a system index.',
                                'required': False,
                                'default': 'off',
                                'type': 'str',
                            },
                        },
                    },
                },
            },
        },
    },
}
