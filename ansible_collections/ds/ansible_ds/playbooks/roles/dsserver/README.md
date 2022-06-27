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
- name: Playbook to create a DS instance
  hosts: localhost

  vars:
    dsserver_instances:
        -
            name: i1
            rootpw: !vault |
                      $ANSIBLE_VAULT;1.1;AES256
                      30353330663535343236626331663332336636383562316662326463363161626163653731353564
                      6130636534336637353939643930383962306431323262390a663839666262313338613334303937
                      66656631313662343132346638643137396337613962636565393931636132663435306433643130
                      3661636162373437330a633066313635343063356635623137626635623764626139373061383634
                      3439

            port: 389
            secure_port: 636
            backends:
                -
                    name: "userroot"
                    suffix: "dc=example,dc=com"
                -
                    name: "second"
                    suffix: "dc=another example,dc=com"
                -
                    name: "peoplesubsuffix"
                    suffix: "o=people,dc=example,dc=com"

  collections:
    - ds.ansible_ds

  roles:
    - role: dsserver
      state: present
```

```yaml
---
- name: Playbook to remove an instances
  hosts: localhost

  vars:
    dsserver_instances:
        -
            name: i1
            state: "absent"

  collections:
    - ds.ansible_ds

  roles:
    - role: dsserver
      state: absent
```

```yaml
---
- name: Playbook to remove all instances
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

Authors
=======

Pierre Rogier
Big parts of README.md logic is taken from https://github.com/freeipa/ansible-freeipa/tree/master/roles/ipabackup
