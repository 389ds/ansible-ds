#/bin/sh

VAULT_PW_FILE=$PWD/../vault.pw
ansible-inventory --list --playbook-dir $PWD -i inventory --vault-password-file $VAULT_PW_FILE "$@"
