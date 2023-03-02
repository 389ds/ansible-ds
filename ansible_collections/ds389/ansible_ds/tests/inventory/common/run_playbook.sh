#/bin/sh

VAULT_PW_FILE=$PWD/../vault.pw
exec ansible-playbook -i inventory --vault-password-file $VAULT_PW_FILE "$@"
