# --- BEGIN COPYRIGHT BLOCK ---
# Copyright (C) 2022 Red Hat, Inc.
# All rights reserved.
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# --- END COPYRIGHT BLOCK ---
#
#

""" This module contains the testcases fore ds389_server ansible module."""

# Disable pylint warning triggered by standard fixture usage
# pylint: disable=redefined-outer-name
# pylint: disable=unused-import
# pylint: disable=unused-argument

import os
import sys

# Set PYTHONPATH to be able to find lib389 in PREFIX install
# (computed within conftest seesion initialization hook)
from lib389 import DirSrv
from lib389.properties import SER_SERVERID_PROP
from lib389.topologies import topology_m2 as topo_s2

DIRECTORY_MANAGER_PASSWORD = "secret12"

common_args = {
    "ansible_verbosity" : 5,
    "ansible_check_mode" : False,
}


config_2i={
    "ds389_server_instances": [
        {
            "name": "i1",
            "backends": [
                {
                    "name": "userroot",
                    "state": "present",
                    "suffix": "dc=example,dc=com",
                }
            ],
            "rootpw" : DIRECTORY_MANAGER_PASSWORD,
            "port": "38901",
            "secure_port": "63601",
            "started": "true",
            "state": "present",
        },
        {
            "name": "i2",
            "backends": [
                {
                    "name": "userroot",
                    "state": "present",
                    "suffix": "dc=example,dc=com",
                }
            ],
            "rootpw" : DIRECTORY_MANAGER_PASSWORD,
            "port": "38902",
            "secure_port": "63602",
            "started": "true",
            "state": "present",
        },
    ],
    "ds389_prefix": os.getenv("PREFIX",""),
    "state": "present"
}

def test_ds389_create_is_idempotent(ansibletest):
    """Setup two instances twice using ds389_server module.
        Setup: None
        Step 1: Ensure that i1 and i2 instances does not exist
        Step 2: Run ds389_server module
        Step 3: Verify that i1 ande i2 instances exists.
        Step 4: Verify changed is true
        Step 5: Run again ds389_server module
        Step 6: Verify changed is false
        Step 7: Perform cleanup
        Result 1: No error
        Result 3: No error
        Result 3: Instances should exist and be started.
        Result 4: change should be true
        Result 5: No error
        Result 6: change should be false
        Result 7: No error
    """

    log = ansibletest.get_log(__name__)
    # Step 1: Ensure that i1 and i2 instances does not exist
    instances=[]
    for serverid in ( "i1", "i2" ):
        srv = DirSrv()
        srv.allocate({ SER_SERVERID_PROP: serverid })
        instances.append(srv)
        if srv.exists():
            srv.delete()
    # Step 2: Run ds389_server module
    args = { "ds389" : { **config_2i, **common_args }  }
    result = ansibletest.run_test_module( { "ANSIBLE_MODULE_ARGS": args } )
    # Step 3: Verify that i1 ande i2 instances exists.
    for srv in instances:
        assert srv.exists()
        assert srv.status()
    # Step 4: Verify changed is true
    assert result['changed'] is True
    # Step 5: Run again ds389_server module
    result = ansibletest.run_test_module( { "ANSIBLE_MODULE_ARGS": args } )
    log.info(f'second result={result}')
    # Step 6: Verify changed is false
    assert result['changed'] is False
    # Step 7: Perform cleanup
    for srv in instances:
        if srv.exists():
            srv.delete()

def test_ds289_remove_all(ansibletest, topo_s2):
    """Remove all instances using ds389_server module.
        Setup: Two suppliers
        Step 1: Ensure that instances exist
        Step 2: Run ds389_server module
        Step 3: Verify that instances do not exist.
   """

    log = ansibletest.get_log(__name__)
    # Step 1: Ensure that instances exist
    for inst in topo_s2:
        assert inst.exists(), f"Instance {inst} does not exist at the beginning of the test"
    # Step 2: Run ds389_server module
    args = { "ds389" : { "state": "absent", **common_args }  }
    result = ansibletest.run_test_module( { "ANSIBLE_MODULE_ARGS": args } )
    # Step 3: Verify that instances do not exist.
    for inst in topo_s2:
        assert not inst.exists()
    del log
    del result
