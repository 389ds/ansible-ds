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

Authors
=======

Pierre Rogier
Big parts of README.md logic is taken from https://github.com/freeipa/ansible-freeipa/tree/master/roles/ipabackup
