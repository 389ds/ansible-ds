# Basic installation using inventory

A simple set of playbooks that creates 4 docker images and install 389 and creates "localhost" instance with a single usertoot backend.

## Prerequiste

The following must be installed on the local host:

- ansible,
- docker client
- ds389.ansible_ds collection

## Commands to run:

../common/run_playbook.sh ../common/create_vms.yml
../common/run_playbook.sh ../common/install_module.yaml
../common/run_playbook.sh install_ds_on_vms.yaml

To remove the docker containers:
../common/run_playbook.sh ../common/destroy_vms.yml

## File descriptions

| *File*                         | *Description*                                                                      |
| ------------------------------ | ---------------------------------------------------------------------------------- |
| install_ds_on_vms.yaml         | Playbook that creates ds389 instance                                               |
| inventory                      | The inventory folder                                                               |
| inventory/testds389.yaml       | The main inventory file                                                            |
| inventory/testds389_vault.yaml | The crypted vault file generated by init_vault.sh                                  |
| README                         | This file                                                                          |
| test_basic_inventory.yml       | pytest testcase playbook that run install_ds_on_vms.yaml                           |

## Passwords

Password used in this test

| *Password*  | ldap DN                          | *Source*                                  | *Description*                                                                    |
| ----------- | -------------------------------- | ----------------------------------------- | -------------------------------------------------------------------------------- |
| vaultsecret | -                                | ../vault.pw                               | The password used to encrypt and decrypt the inventory/testds389_vault.yaml file |
| rootdnpw    | cn=directory manager             | vault_ds389_rootpw variable in the vault  | The 389ds directory manager password                                             |
| replmanpw   | cn=replication manager,cn=config | vault_ds389_replman variable in the vault | The replication manager password                                                 |
