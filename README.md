389 Directory Server Ansible collection
==========================

This repository contains [Ansible](https://www.ansible.com/) roles and playbooks with which you can manage [389 Directory Server](https://www.port389.org/) (389 DS).


Supported 389 Directory Server Versions
--------------------------

389 Directory Server versions 2.2 and up are supported by all roles.

Supported Distributions
-----------------------

* RHEL/CentOS 9+
* Fedora 36+

Requirements
------------

**Controller**
* Ansible version: 2.9+
* Python version: 3.9+

**Node**
* Supported 389 DS version (see above)
* Supported distribution (needed for package installation only, see above)

Usage
=====

How to use ansible-ds
--------------------------

**Development Usage**

Clone this repository:

```bash
git clone https://github.com/droideck/ansible-ds.git
cd ansible-ds
```

cp ansible_collections/ds389/ansible_ds/playbooks/gather_dsinst_info.yml ansible_collections/ds389/ansible_ds/gather_dsinst_info.yml
ansible-playbook ansible_collections/ds389/ansible_ds/gather_dsinst_info.yml

Make sure that Ansible is installed:

```bash
dnf install ansible -y
```

Build and install this collection locally:

```bash
make all
```

Run the playbook:

```bash
ansible-playbook ds389.ansible_ds.gather_dsinst_info
```

How to run tests
--------------------------

Make sure that *Development Usage* steps are completed.

Install additional dependencies:

```bash
dnf install ansible-test -y # Only for Ansible 2.9 version. The later versions already have it included in the base package
pip3 install -r requirements.txt
```

Run Ansible tests (see the supported Python version above):

```bash
make unit_test
```