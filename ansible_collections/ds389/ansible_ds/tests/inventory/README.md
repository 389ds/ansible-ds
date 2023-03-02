# Inventory test framework

This directory contains subdirectory using specifics inventory that can be used as example

# Prerequiste

The following must be installed on the local host:

- ansible,
- docker client
- ds389.ansible_ds collection

# Test cases

The test cases are the playbooks prefixed by test_

# Files description

| *File*                     | *Description*                                                                                          |
| -------------------------- | ------------------------------------------------------------------------------------------------------ |
| vault.clear                | The clear text vault file. In a production environment this file only exist encrupted in the inventory |
| install_ds_on_vms.yaml     | Playbook that creates ds389 instance                                                                   |
| vault.pw                   | The vault password file (should not exists in a production environment)                                |
| common                     | This directory contains common playbooks and utilities                                                 |
| common/create_vms.yml      | A playbook that creates the ldapserver                                                                 |
| common/create_vms.yml      | A playbook that creates docker containers for ldapservers hosts                                        |
| common/destroy_vms.yml     | A playbook that removes docker containers for ldapservers hosts                                        |
| common/init_vault.sh       | A script that generates the encrypted vault on all inventories                                         |
| common/install_module.yaml | A playbook that creates install the ds389.ansible_ds module on ldapservers hosts                       |
| common/run_playbook.sh     | A wrapper around ansible-playbook                                                                      |
| common/run_playbook.sh     | A wrapper around ansible-inventory                                                                     |
| README.md                  | This file                                                                                              |
| basic                      | This directory contains a basic inventory and playbook example (no replication)                        |
| replication                | TBD                                                                                                    |
