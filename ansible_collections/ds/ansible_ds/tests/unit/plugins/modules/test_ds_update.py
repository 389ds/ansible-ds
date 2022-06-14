# --- BEGIN COPYRIGHT BLOCK ---
# Copyright (C) 2022 Red Hat, Inc.
# All rights reserved.
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# --- END COPYRIGHT BLOCK ---
#
#

""" This module contains the testcases fore ds_update ansible module."""

# Disable pylint warning triggered by standard fixture usage
# pylint: disable=redefined-outer-name
# pylint: disable=unused-import
# pylint: disable=unused-argument

import os
import sys

# Set PYTHONPATH to be able to find lib389 in PREFIX install
# (computed within conftest seesion initialization hook)
if "LIB389PATH" in os.environ:
    sys.path.insert(0, os.environ['LIB389PATH'])
from lib389 import DirSrv
from lib389.properties import SER_SERVERID_PROP

DIRECTORY_MANAGER_PASSWORD = "secret12"

config_2i={
    "instances": {
        "i1": {
            "backends": {
                "userroot": {
                    "state": "present",
                    "suffix": "dc=example,dc=com"
                }
            },
            "root_password" : DIRECTORY_MANAGER_PASSWORD,
            "port": "38901",
            "secure_port": "63601",
            "started": "true",
            "state": "present"
        },
        "i2": {
            "backends": {
                "userroot": {
                "state": "present",
                "suffix": "dc=example,dc=com"}
            },
            "root_password" : DIRECTORY_MANAGER_PASSWORD,
            "port": "38902",
            "secure_port": "63602",
            "started": "true",
            "state": "present"
        }
    },
    "prefix": os.getenv("PREFIX",""),
    "state": "present"
}

def test_dscreate_is_idempotent(ansibletest):
    """Test dsinfo module #1.
        Setup: None
        Step 1: Ensure that i1 and i2 instances does not exist
        Step 2: Run ds_update module
        Step 3: Verify that i1 ande i2 instances exists.
        Step 4: Verify changed is true
        Step 5: Run again ds_update module
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

    log = ansibletest.getLog(__name__)
    # Step 1: Ensure that i1 and i2 instances does not exist
    instances=[]
    for serverid in ( "i1", "i2" ):
        srv = DirSrv()
        srv.allocate({ SER_SERVERID_PROP: serverid })
        instances.append(srv)
        if srv.exists():
            srv.delete()
    # Step 2: Run ds_update module
    args = { "content" : config_2i }
    result = ansibletest.runTestModule( { "ANSIBLE_MODULE_ARGS": args } )
    log.info(f'result={result}')
    # Step 3: Verify that i1 ande i2 instances exists.
    for srv in instances:
        assert srv.exists()
        assert srv.status()
    # Step 4: Verify changed is true
    assert result['changed'] is True
    # Step 5: Run again ds_update module
    result = ansibletest.runTestModule( { "ANSIBLE_MODULE_ARGS": args } )
    log.info(f'second result={result}')
    # Step 6: Verify changed is false
    assert result['changed'] is False
    # Step 7: Perform cleanup
    for srv in instances:
        if srv.exists():
            srv.delete()
