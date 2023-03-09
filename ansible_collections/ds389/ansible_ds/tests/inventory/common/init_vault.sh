#/bin/sh

# Create vault in all inventories

set -x

if [ ! -f init_vault.sh ]
then
    echo "Current directory should be ansible_collections/ds389/ansible_ds/tests/inventory/common"
    exit 1
fi

VAULT_PW_FILE=$PWD/../vault.pw
VAULT_CLEAR_FILE=$PWD/../vault.clear

for inv in ../*/inventory/
do
    VAULT_FILE=$inv/testds389_vault.yaml
    cp $VAULT_CLEAR_FILE $VAULT_FILE
    ansible-vault encrypt --vault-password-file $VAULT_PW_FILE $VAULT_FILE
done
