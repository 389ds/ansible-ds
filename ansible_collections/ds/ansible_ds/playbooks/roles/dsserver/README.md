dsserver role
==============

Description
-----------

This role allows to create or remove directory server instances and to update their configuration.

**Note**: The ansible playbooks and role require a configured ansible environment where the ansible nodes are reachable and are properly set up to have an IP address and a working package manager.


Features
--------
* Instance creation
* Instance removal
* Updating instance configuration

Supported 389 DS Versions
--------------------------

389 DS versions 2.1 and up are supported by the dsserver role.


Supported Distributions
-----------------------

* RHEL/CentOS 9+
* Fedora 36+


Requirements
------------

**Controller**
* Ansible version: 2.9+

**Node**
* Supported 389 DS version (see above)
* Supported distribution (needed for package installation only, see above)


Usage
=====

Example inventory file with fixed domain and realm, setting up of the DNS server and using forwarders from /etc/resolv.conf:

```ini
[dsserver]
dsserver.example.com
```

TODO: For now, this rol uses `localhost` as an instance name.


Example playbook to create an instance of the 389 DS server locally:

```yaml
---
- name: Playbook to create a set of DS instances
  hosts: localhost

  vars:
    # In a real deployment, variables should be customized
    # In this playbook all the variables are commented out because
    # they are provided by the calling test playbook

    # Mandatory variables:

    # dsserver_rootpw: The default Directory manager password
    # In real deployment it should be set by using:
    #  ansible-vault encrypt_string --stdin-name dsserver_rootpw
    # i.e:
    #dsserver_rootpw: !vault |
    #     $ANSIBLE_VAULT;1.1;AES256
    #     65386361623432656133343230333636626164353230623935616632636361356265623530366232
    #     6662333634333066613430616461623433633766333936330a616239636266666465343235316666
    #     34373235366537323163623339373332323338326266356339303337363736646563623862366261
    #     3435303734383335390a323638313539333338313866636134393731306162343837393966333735
    #     6134

    # Optionnal variables:
    # Description format is:  # variableName (default value) : description

    # dsserver_instance (myinstance) : Instance name
    # dsserver_port (389) : Non secure port (could be 0 if there is no such port)
    # dsserver_secure_port (636) : Secure port (could be 0 if there is no such port)
    # dsserver_backends (None): Backend map using the backend name: suffix notation


  collections:
    - ds.ansible_ds

  roles:
    - role: dsserver
      state: present
```

Example playbook to delete an instance of the 389 DS server locally:
```yaml
---
- name: Playbook to remove a DS instance
  hosts: localhost

  vars:
    # In a real deployment, variables should be customized
    # In this playbook all the variables are commented out because
    # they are provided by the calling test playbook

    # Optionnal variables:
    # Description format is:  # variableName (default value) : description
    # dsserver_instances (empty list) : list of dict with instance name and state 'absent'

    # Example:
    # dsserver_instances:
    #    -
    #        name: i1
    #        state: absent
    # dsserver_prefix: ''

  collections:
    - ds.ansible_ds

  roles:
    - role: dsserver
      state: present
```

Example playbook to delete all instances of the 389 DS server locally:
```yaml
---
- name: Playbook to remove all DS instances
  hosts: localhost

  collections:
    - ds.ansible_ds

  roles:
    - role: dsserver
      state: absent
```

Playbooks
=========

The example playbooks are part of the repository in the playbooks folder.

```
dscreate.yml
dsremove.yml
dsremoveall.yml
```


Variables
=========

Base Variables
--------------

Variable | Description | Required
-------- | ----------- | --------
state | `present` or 'overwrite' to update instances configuration, `absent` to remove all instance (default is 'present') | no

Special Variables
-----------------

Variable | Description | Required
-------- | ----------- | --------
dsserver_instances | a list of dict containing the instance configuration (see ds_server module documentation to get the full duescription) (default is empty list) | no
dsserver_prefix | the directory server installation prefix (default is '') | no

Variable tree description
-------------------------
  - instances: A list of <class 'module_utils.dsentities.ConfigInstance'>
      - backends: A list of <class 'module_utils.dsentities.ConfigBackend'>
          - agmts: A list of <class 'module_utils.dsentities.ConfigAgmt'>
          - indexes: A list of <class 'module_utils.dsentities.ConfigIndex'>

# Options per entities

## Instance
| Option | Required | Type | Description | Comment |
| - | -  | -  | -  | -  |
| state | False | str | Indicate whether the instance is added(present), modified(updated), or removed(absent) | Value may be one of: ('present', 'updated', 'absent'). Default value is: present. |
| backup_dir | False | str | Directory containing the backup files |  |
| bin_dir | False | str | Directory containing ns-slapd binary. Only set this parameter in a development environment |  |
| cert_dir | False | str | Directory containing the NSS certificate databases |  |
| config_dir | False | str | Sets the configuration directory of the instance (containing the dse.ldif file) |  |
| data_dir | False | str | Sets the location of Directory Server shared static data. Only set this parameter in a development environment |  |
| db_dir | False | str | Sets the database directory of the instance |  |
| db_home_dir | False | str | Sets the memory-mapped database files location of the instance |  |
| db_lib | False | str | Select the database implementation library | Value may be one of: ('bdb', 'mdb').  |
| full_machine_name | False | str | The fully qualified hostname (FQDN) of this system. When installing this instance with GSSAPI authentication behind a load balancer, set this parameter to the FQDN of the load balancer and, additionally, set "strict_host_checking" to "false" |  |
| group | False | str | Sets the group name the ns-slapd process will use after the service started |  |
| initconfig_dir | False | str | Sets the directory of the operating system's rc configuration directory. Only set this parameter in a development environment |  |
| inst_dir | False | str | Directory containing instance-specific scripts |  |
| instance_name | False | str | Sets the name of the instance. |  |
| ldapi | False | str | Sets the location of socket interface of the Directory Server |  |
| ldif_dir | False | str | Directory containing the the instance import and export files |  |
| lib_dir | False | str | Sets the location of Directory Server shared libraries. Only set this parameter in a development environment |  |
| local_state_dir | False | str | Sets the location of Directory Server variable data. Only set this parameter in a development environment |  |
| lock_dir | False | str | Directory containing the lock files |  |
| nsslapd_backend_opt_level | False | int | This parameter can trigger experimental code to improve write performance | Default value is: 1. |
| nsslapd_directory | False | str | Default database directory | Default value is: {prefix}/var/lib/dirsrv/slapd-{instname}/db. |
| nsslapd_exclude_from_export | False | str | list of attributes that are not exported | Default value is: entrydn entryid dncomp parentid numSubordinates tombstonenumsubordinates entryusn. |
| nsslapd_idlistscanlimit | False | int | The maximum number of entries a given index key may refer before the index is handled as unindexed. | Default value is: 4000. |
| nsslapd_import_cachesize | False | int | Size of database cache when doing an import | Default value is: 16777216. |
| nsslapd_lookthroughlimit | False | int | The maximum number of entries that are looked in search operation before returning LDAP_ADMINLIMIT_EXCEEDED | Default value is: 5000. |
| nsslapd_mode | False | int | The database permission (mode) in octal | Default value is: 600. |
| nsslapd_pagedidlistscanlimit | False | int | idllistscanlimit when performing a paged search | Default value is: 0. |
| nsslapd_pagedlookthroughlimit | False | int | lookthroughlimit when performing a paged search | Default value is: 0. |
| nsslapd_rangelookthroughlimit | False | int | Sets a separate range look-through limit that applies to all users, including Directory Manager | Default value is: 5000. |
| nsslapd_search_bypass_filter_test | False | str | Allowed values are: 'on', 'off' or 'verify'. If you enable the nsslapd-search-bypass-filter-test parameter, Directory Server bypasses filter checks when it builds candidate lists during a search. If you set the parameter to verify, Directory Server evaluates the filter against the search candidate entries | Value may be one of: ('on', 'off', 'verify'). Default value is: on. |
| nsslapd_search_use_vlv_index | False | str | enables and disables virtual list view (VLV) searches | Value may be one of: ('on', 'off'). Default value is: on. |
| port | False | int | Sets the TCP port the instance uses for LDAP connections |  |
| root_dn | False | str | Sets the Distinquished Name (DN) of the administrator account for this instance. It is recommended that you do not change this value from the default 'cn=Directory Manager' |  |
| rootpw | False | str | Sets the password of the "cn=Directory Manager" account ("root_dn" parameter). You can either set this parameter to a plain text password dscreate hashes during the installation or to a "{algorithm}hash" string generated by the pwdhash utility. The password must be at least 8 characters long.  Note that setting a plain text password can be a security risk if unprivileged users can read this INF file |  |
| run_dir | False | str | Directory containing the pid file |  |
| sbin_dir | False | str | Sets the location where the Directory Server administration binaries are stored. Only set this parameter in a development environment |  |
| schema_dir | False | str | Directory containing the schema files |  |
| secure_port | False | int | Sets the TCP port the instance uses for TLS-secured LDAP connections (LDAPS) |  |
| self_sign_cert | False | str | Sets whether the setup creates a self-signed certificate and enables TLS encryption during the installation. The certificate is not suitable for production, but it enables administrators to use TLS right after the installation. You can replace the self-signed certificate with a certificate issued by a Certificate Authority. If set to False, you can enable TLS later by importing a CA/Certificate and enabling 'dsconf <instance_name> config replace nsslapd-security=on |  |
| self_sign_cert_valid_months | False | str | Set the number of months the issued self-signed certificate will be valid. |  |
| selinux | False | bool | Enables SELinux detection and integration during the installation of this instance. If set to "True", dscreate auto-detects whether SELinux is enabled. Set this parameter only to "False" in a development environment or if using a non root installation |  |
| started | False | bool | Indicate whether the instance is (or should be) started | Default value is: True. |
| strict_host_checking | False | bool | Sets whether the server verifies the forward and reverse record set in the "full_machine_name" parameter. When installing this instance with GSSAPI authentication behind a load balancer, set this parameter to "false". Container installs imply "false" |  |
| sysconf_dir | False | str | sysconf directoryc |  |
| systemd | False | bool | Enables systemd platform features. If set to "True", dscreate auto-detects whether systemd is installed. Only set this parameter in a development environment or if using non root installation |  |
| tmp_dir | False | str | Sets the temporary directory of the instance |  |
| user | False | str | Sets the user name the ns-slapd process will use after the service started |  |

## Backend
| Option | Required | Type | Description | Comment |
| - | -  | -  | -  | -  |
| state | False | str | Indicate whether the backend is added(present), modified(updated), or removed(absent) | Value may be one of: ('present', 'updated', 'absent'). Default value is: present. |
| suffix | True | str | DN subtree root of entries managed by this backend. |  |
| ReplicaRole | False | str | The replica role. | Value may be one of: (None, 'supplier', 'hub', 'consumer').  |
| chain_bind_dn | False | str | Desc |  |
| chain_bind_pw | False | str | Desc |  |
| chain_urls | False | str | Desc |  |
| changelogencryptionalgorithm | False | str | Encryption algorithm used to encrypt the changelog. |  |
| changelogmaxage | False | str | Changelog record lifetime |  |
| changelogmaxentries | False | str | Max number of changelog records |  |
| changelogsymetrickey | False | str | Encryption key (if changelog is encrypted) |  |
| changelogtriminterval | False | str | Time (in seconds) between two runs of the changlog trimming.  |  |
| db_deadlock | False | str | Desc |  |
| directory | False | str | Desc |  |
| dn_cache_size | False | str | Desc |  |
| entry_cache_number | False | str | Desc |  |
| entry_cache_size | False | str | Desc |  |
| readonly | False | str | Desc | Default value is: False. |
| replicabackoffmax | False | int | Maximum delay before retrying to send updates after a recoverable failure |  |
| replicabackoffmin | False | int | Minimum time before retrying to send updates after a recoverable failure |  |
| replicabinddn | False | str | DN of the user allowed to replay updates on this replica |  |
| replicabinddngroup | False | str | DN of the group containing users allowed to replay updates on this replica |  |
| replicabinddngroupcheckinterval | False | int | Interval between detection of the bind dn group changes |  |
| replicaid | False | int | The unique ID for suppliers in a given replication environment (between 1 and 65534). |  |
| replicaprecisetombstonepurging | False | str | ??? |  |
| replicaprotocoltimeout | False | int | Timeout used when stopping replication to abort ongoing operations. |  |
| replicapurgedelay | False | str | The maximum age of deleted entries (tombstone entries) and entry state information. |  |
| replicareferral | False | list | The user-defined referrals (returned when a write operation is attempted on a hub or a consumer. |  |
| replicareleasetimeout | False | int | The timeout period (in seconds) after which a master will release a replica. |  |
| replicatombstonepurgeinterval | False | int | The time interval in seconds between purge operation cycles. |  |
| replicatransportinfo | False | str | The type of transport used for transporting data to and from the replica. | Value may be one of: ('LDAP', 'SSL', 'TLS').  |
| replicaupdateschedule | False | list | Time schedule presented as XXXX-YYYY 0123456, where XXXX is the starting hour,YYYY is the finishing hour, and the numbers 0123456 are the days of the week starting with Sunday. |  |
| replicawaitforasyncresults | False | int | Delay in milliseconds before resending an update if consumer does not acknowledge it. |  |
| require_index | False | str | Desc |  |
| sample_entries | False | bool | Tells whether sample entries are created on this backend when the instance is created |  |

## Agmt
| Option | Required | Type | Description | Comment |
| - | -  | -  | -  | -  |
| state | False | str | Indicate whether the replication agreement is added(present), modified(updated), or removed(absent) | Value may be one of: ('present', 'updated', 'absent'). Default value is: present. |
| replicabinddn | False | str | The DN used to connect to the target instance |  |
| replicabindmethod | False | str | The bind Method | Value may be one of: ('SIMPLE', 'SSLCLIENTAUTH', 'SASL/GSSAPI', 'SASL/DIGEST-MD5').  |
| replicabootstrapbinddn | False | str | The fallback bind dn used after getting authentication error |  |
| replicabootstrapbindmethod | False | str | The fallback bind method | Value may be one of: ('SIMPLE', 'SSLCLIENTAUTH', 'SASL/GSSAPI', 'SASL/DIGEST-MD5').  |
| replicabootstrapcredentials | False | str | The credential associated with the fallback bind |  |
| replicabootstraptransportinfo | False | str | The encryption method used on the connection after an authentication error. | Value may be one of: ('LDAP', 'TLS', 'SSL').  |
| replicabusywaittime | False | int | The amount of time in seconds a supplier should wait after a consumer sends back a busy response before making another attempt to acquire access |  |
| replicacredentials | False | str | The crendential associated with the bind |  |
| replicaenabled | False | str | A flags telling wheter the replication agreement is enabled or not. | Value may be one of: ('on', 'off').  |
| replicaflowcontrolpause | False | int | the time in milliseconds to pause after reaching the number of entries and updates set in the ReplicaFlowControlWindow parameter is reached. |  |
| replicaflowcontrolwindow | False | int | The maximum number of entries and updates sent by a supplier, which are not acknowledged by the consumer. After reaching the limit, the supplier pauses the replication agreement for the time set in the nsds5ReplicaFlowControlPause parameter |  |
| replicahost | False | str | The target instance hostname |  |
| replicaignoremissingchange | False | str | Tells how the replication behaves when a csn is missing. | Value may be one of: ('never', 'once', 'always', 'on', 'off').  |
| replicaport | False | int | Target instance port |  |
| replicasessionpausetime | False | int | The amount of time in seconds a supplier should wait between update sessions |  |
| replicastripattrs | False | list | Fractionnal replication attributes that does get replicated if the operation modifier list contains only these agreement |  |
| replicatedattributelist | False | list | List of replication attribute ithat are not replicated in fractionnal replication |  |
| replicatedattributelisttotal | False | list | List of attributes that are not replicated during a total update |  |
| replicatimeout | False | int | The number of seconds outbound LDAP operations waits for a response from the remote replica before timing out and failing |  |
| replicatransportinfo | False | str | The encryption method used on the connection | Value may be one of: ('LDAP', 'TLS', 'SSL').  |
| replicaupdateschedule | False | list | The replication schedule. |  |
| replicawaitforasyncresults | False | str | The time in milliseconds for which a supplier waits if the consumer is not ready before resending data. |  |

## Index
| Option | Required | Type | Description | Comment |
| - | -  | -  | -  | -  |
| state | False | str | Indicate whether the index is added(present), modified(updated), or removed(absent) | Value may be one of: ('present', 'updated', 'absent'). Default value is: present. |
| indextype | True | str | Determine the index types (pres,eq,sub,matchingRuleOid) |  |
| systemindex | False | str | Tells if the index is a system index | Default value is: off. |

Authors
=======

Pierre Rogier
Big parts of README.md logic is taken from https://github.com/freeipa/ansible-freeipa/tree/master/roles/ipabackup
