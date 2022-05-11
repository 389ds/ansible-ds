dsbackup role
==============

Description
-----------

This role allows to backup 389 DS instance, to copy a backup from the server to the controller, to copy all backups from the server to the controller, to remove a backup from the server, to remove all backups from the server, to restore an 389 DS server locally and from the controller and also to copy a backup from the controller to the server.

**Note**: The ansible playbooks and role require a configured ansible environment where the ansible nodes are reachable and are properly set up to have an IP address and a working package manager.


Features
--------
* Server backup
* Server backup to controller
* Copy backup from server to controller
* Copy all backups from server to controller
* Remove backup from the server
* Remove all backups from the server
* Server restore from server local backup.
* Server restore from controller.
* Copy a backup from the controller to the server.


Supported 389 DS Versions
--------------------------

389 DS versions 2.1 and up are supported by the backup role.


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

Example playbook to create a backup on the 389 DS server locally:

```yaml
---
- name: Playbook to backup 389 DS server
  hosts: dsserver
  become: true

  roles:
  - role: dsbackup
    state: present
```


Example playbook to create a backup of the 389 DS server that is transferred to the controller using the server name as prefix for the backup and removed on the server:

```yaml
---
- name: Playbook to backup 389 DS server to controller
  hosts: dsserver
  become: true

  vars:
    dsbackup_to_controller: yes
    # dsbackup_keep_on_server: yes

  roles:
  - role: dsbackup
    state: present
```


Example playbook to create a backup of the 389 DS server that is transferred to the controller using the server name as prefix for the backup and kept on the server:

```yaml
---
- name: Playbook to backup 389 DS server to controller
  hosts: dsserver
  become: true

  vars:
    dsbackup_to_controller: yes
    dsbackup_keep_on_server: yes

  roles:
  - role: dsbackup
    state: present
```


Copy backup `ds-full-2020-10-01-10-00-00` from server to controller:

```yaml
---
- name: Playbook to copy backup from 389 DS server
  hosts: dsserver
  become: true

  vars:
    dsbackup_name: dsserver-2020-10-01-10-00-00
    dsbackup_to_controller: yes

  roles:
  - role: dsbackup
    state: copied
```


Copy backups `ds-full-2020-10-01-10-00-00` and `ds-full-2020-10-02-10-00-00` from server to controller:

```yaml
---
- name: Playbook to copy backup from 389 DS server
  hosts: dsserver
  become: true

  vars:
    dsbackup_name:
    - ds-full-2020-10-01-10-00-00
    - ds-full-2020-10-02-10-00-00
    dsbackup_to_controller: yes

  roles:
  - role: dsbackup
    state: copied
```


Copy all backups from server to controller that are following the backup naming scheme:

```yaml
---
- name: Playbook to copy all backups from 389 DS server
  hosts: dsserver
  become: true

  vars:
    dsbackup_name: all
    dsbackup_to_controller: yes

  roles:
  - role: dsbackup
    state: copied
```


Remove backup `ds-full-2020-10-01-10-00-00` from server:

```yaml
---
- name: Playbook to remove backup from 389 DS server
  hosts: dsserver
  become: true

  vars:
    dsbackup_name: ds-full-2020-10-01-10-00-00

  roles:
  - role: dsbackup
    state: absent
```


Remove backups `ds-full-2020-10-01-10-00-00` and `ds-full-2020-10-02-10-00-00` from server:

```yaml
---
- name: Playbook to remove backup from 389 DS server
  hosts: dsserver
  become: true

  vars:
    dsbackup_name:
    - ds-full-2020-10-01-10-00-00
    - ds-full-2020-10-02-10-00-00

  roles:
  - role: dsbackup
    state: absent
```


Remove all backups from server that are following the backup naming scheme:

```yaml
---
- name: Playbook to remove all backups from 389 DS server
  hosts: dsserver
  become: true

  vars:
    dsbackup_name: all

  roles:
  - role: dsbackup
    state: absent
```


Example playbook to restore an 389 DS server locally:

```yaml
---
- name: Playbook to restore an 389 DS server
  hosts: dsserver
  become: true

  vars:
    dsbackup_name: ds-full-2020-10-22-11-11-44

  roles:
  - role: dsbackup
    state: restored
```


Example playbook to restore 389 DS server from controller:

```yaml
---
- name: Playbook to restore 389 DS server from controller
  hosts: dsserver
  become: true

  vars:
    dsbackup_name: dsserver.test.local_ds-full-2020-10-22-11-11-44
    dsbackup_from_controller: yes

  roles:
  - role: dsbackup
    state: restored
```


Example playbook to copy a backup from controller to the 389 DS server:

```yaml
---
- name: Playbook to copy a backup from controller to the 389 DS server
  hosts: dsserver
  become: true

  vars:
    dsbackup_name: dsserver.test.local_ds-full-2020-10-22-11-11-44
    dsbackup_from_controller: yes

  roles:
  - role: dsbackup
    state: copied
```


Playbooks
=========

The example playbooks to do the backup, copy a backup and also to remove a backup, also to do the restore, copy a backup to the server are part of the repository in the playbooks folder.

```
backup_instance.yml
backup_server_to_controller.yml
copy_all_backups_from_server.yml
copy_backup_from_server.yml
remove_all_backups_from_server.yml
remove_backup_from_server.yml
restore_server.yml
restore_server_from_controller.yml
copy_backup_from_controller.yml
```


Variables
=========

Base Variables
--------------

Variable | Description | Required
-------- | ----------- | --------
state | `present` to make a new backup, `absent` to remove a backup and `copied` to copy a backup from the server to the controller or from the controller to the server, `restored` to restore a backup. string (default: `present`) | yes


Special Variables
-----------------

Variable | Description | Required
-------- | ----------- | --------
dsbackup_name | The 389 DS backup name(s). Only for removal of server local backup(s) with `state: absent`, to copy server local backup(s) to the controller with `state: copied` and `dsbackup_from_server` set, to copy a backup from the controller to the server with `state: copied` and `dsbackup_from_controller` set or to restore a backup with `state: restored` either locally on the server of from the controller with `dsbackup_from_controller` set. If `all` is used all available backups are copied or removed that are following the backup naming scheme. string list | no
dsbackup_keep_on_server | Keep local copy of backup on server with `state: present` and `dsbackup_to_controller`, bool (default: `no`) | no
dsbackup_to_controller | Copy backup to controller, prefixes backup with node name, remove backup on server if `dsbackup_keep_on_server` is not set, bool (default: `no`) | no
dsbackup_controller_path | Pre existing path on controller to store the backup in with `state: present`, path on the controller to copy the backup from with `state: copied` and `dsbackup_from_controller` set also for the restore with `state: restored` and `dsbackup_from_controller` set. If this is not set, the current working dir is used. string | no
dsbackup_name_prefix | Set prefix to use for backup directory on controller with `state: present` or `state: copied` and `dsbackup_to_controller` set, The default is the server FQDN, string | no
dsbackup_from_controller | Copy backup from controller to server, restore if `state: restored`, copy backup to server if `state: copied`, bool (default: `no`) | no


Authors
=======

Simon Pichugin
Big parts of README.md and basig Ansible logic is taken from https://github.com/freeipa/ansible-freeipa/tree/master/roles/ipabackup