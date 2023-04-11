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
# Disable similarities test
# pylint: disable=R0801

import os
import sys
import itertools
import pytest
import ldap
from copy import deepcopy

# Set PYTHONPATH to be able to find lib389 in PREFIX install
# (computed within conftest seesion initialization hook)
from ldap import LDAPError
from lib389 import DirSrv
from lib389.properties import SER_SERVERID_PROP
from lib389.replica import Replicas


DIRECTORY_MANAGER_PASSWORD = "secret12"
REPLICATION_MANAGER_PASSWORD = "secret34"
SUFFIX = "dc=example,dc=com"

if "DEBUGGING" in os.environ:
    VERBOSITY = 5
else:
    VERBOSITY = 0

MODULE_ARGS = {
    "ANSIBLE_MODULE_ARGS":
    {
        "ds389": {
            "ds389_server_instances": [
                {
                    "backends": [
                        {
                            "name": "userroot",
                            "suffix": SUFFIX
                        }
                    ],
                    "name": "replica",
                    "port": 5555,
                    "rootpw": DIRECTORY_MANAGER_PASSWORD,
                    "secure_port": 6666,
                    "started": True
                },
            ],
            "ansible_check_mode": False,
            "ansible_verbosity": VERBOSITY
        }
    }
}

def get_args(log, role, mymods=None):
    """Compute parameters for the given role."""
    mods = {
        "None": { },
        "supplier": {
            "replicabinddn": "cn=replmgr,cn=config",
            "replicaid": "1",
            "replicarole": "supplier",
            "replicacredentials": REPLICATION_MANAGER_PASSWORD,
        },
        "hub": {
            "replicabinddn": "cn=replmgr,cn=config",
            "replicarole": "hub",
            "replicacredentials": REPLICATION_MANAGER_PASSWORD,
        },
        "consumer": {
            "replicabinddn": "cn=replmgr,cn=config",
            "replicarole": "consumer",
            "replicacredentials": REPLICATION_MANAGER_PASSWORD,
        },
    }
    res = deepcopy(MODULE_ARGS)
    mybe = res["ANSIBLE_MODULE_ARGS"]["ds389"]["ds389_server_instances"][0]["backends"][0]
    for key,val in mods[role].items():
        mybe[key] = val
    if mymods:
        for key,val in mymods.items():
            mybe[key] = val
    log.info(f'get_args role: {role} args: {res}')
    return res


def verify_role(log, inst, role, expected=None):
    """Verify that instance has the right replica attrbutes."""
    if expected is None:
        expected = {
            "None" : {},
            "supplier" : {
                    "nsDS5Flags": 1,
                    "nsDS5ReplicaType": 3,
                    "nsDS5ReplicaId": 1,
                },
            "hub" : {
                    "nsDS5Flags": 1,
                    "nsDS5ReplicaType": 2,
                    "nsDS5ReplicaId": 65535,
                },
            "consumer" : {
                    "nsDS5Flags": 0,
                    "nsDS5ReplicaType": 2,
                    "nsDS5ReplicaId": 65535,
                },
        }[role]
    replicas = Replicas(inst)
    rep = {}
    try:
        replica = replicas.get(SUFFIX)
        rep["nsDS5Flags"] = replica.get_attr_val_int("nsDS5Flags")
        rep["nsDS5ReplicaType"] = replica.get_attr_val_int("nsDS5ReplicaType")
        rep["nsDS5ReplicaId"] = replica.get_attr_val_int("nsDS5ReplicaId")
    except ldap.NO_SUCH_OBJECT:
        pass
    log.info(f'verify_role: role: {role} expected: {expected} found: {rep}')
    assert rep == expected


def cleanup(instances):
    """Remove the instances."""
    for srv in instances:
        if srv.exists():
            srv.delete()


@pytest.mark.parametrize(
    "from_role,to_role",
    itertools.permutations( ("None", "supplier", "hub", "consumer" ) , 2 )
)
def test_switching_replica_roles(ansibletest, from_role, to_role):
    """Test  change of replica role in ds389_server module.
        Setup: None
        Step 1: Ensure that 'replica' instance does not exist
        Step 2: Run ds389_server module with from_role parameters
        Step 3: Verify that instance exists, is started and has expected role
        Step 4: Run ds389_server module with to_role parameters
        Step 5: Verify that instance exists, is started and has expected role
        Step 6: Perform cleanup
        Result 1: No error
        Result 2: No error
        Result 3: No error
        Result 4: No error
        Result 5: No error
        Result 6: No error
    """

    log = ansibletest.get_log(__name__)
    if to_role == "None":
        pytest.skip("Test skipped because of BZ 2184599 (389ds crashes when replication is disabled.")
    # Step 1: Ensure that i1 and i2 instances does not exist
    instances=[]
    for serverid in ( "replica", ):
        srv = DirSrv()
        srv.allocate({ SER_SERVERID_PROP: serverid })
        instances.append(srv)
    cleanup(instances)
    try:
        # Step 2: Run ds389_server module with from_role
        log.info(f'First run of ds389_server module (using {from_role})')
        result = ansibletest.run_test_module( get_args(log, from_role) )
        del result
        # Step 3: Verify that instance exists, is started and has expected role
        for srv in instances:
            assert srv.exists()
            assert srv.status()
            srv.setup_ldapi()
            srv.open()
            verify_role(log, srv, from_role)
        # Step 4: Run ds389_server module with to_role
        log.info(f'Second run of ds389_server module (using {to_role})')
        result = ansibletest.run_test_module( get_args(log, to_role) )
        del result
        # Step 5: Verify that instance exists, is started and has expected role
        for srv in instances:
            assert srv.exists()
            assert srv.status()
            srv.setup_ldapi()
            srv.open()
            verify_role(log, srv, to_role)
    except ( AssertionError, LDAPError ) as exc:
        ansibletest.save_artefacts()
        raise exc
    finally:
        # Step 10: Perform cleanup
        cleanup(instances)


def test_change_replica_id(ansibletest):
    """Test  change of replica id in ds389_server module.
        Setup: None
        Step 1: Ensure that 'replica' instance does not exist
        Step 2: Run ds389_server module with supplier parameters and rid=1
        Step 3: Verify that instance exists, is started and has expected role
        Step 4: Verify that changed attribute is True
        Step 5: Run ds389_server module with supplier parameters and rid=2
        Step 6: Verify that instance exists, is started and has expected role
        Step 7: Perform cleanup
        Result 1: No error
        Result 2: No error
        Result 3: No error
        Result 4: No error
        Result 5: No error
        Result 6: No error
        Result 7: No error
    """

    log = ansibletest.get_log(__name__)
    # Step 1: Ensure that replica instance do not exist
    instances=[]
    for serverid in ( "replica", ):
        srv = DirSrv()
        srv.allocate({ SER_SERVERID_PROP: serverid })
        instances.append(srv)
    cleanup(instances)
    try:
        # Step 2: Run ds389_server module with from_role
        log.info('First run of ds389_server module ')
        result = ansibletest.run_test_module( get_args(log, "supplier") )
        # Step 3: Verify that instance exists, is started and has expected role
        for srv in instances:
            assert srv.exists()
            assert srv.status()
            srv.setup_ldapi()
            srv.open()
            verify_role(log, srv, 'supplier')
        # Step 4: Verify that changed attribute is True
        assert result['changed'] is True
        # Step 5: Run ds389_server module with to_role
        log.info('Second run of ds389_server module ')
        result = ansibletest.run_test_module( get_args(log, 'supplier', mymods = { 'replicaid': 2 }) )
        del result
        # Step 6: Verify that instance exists, is started and has expected role
        for srv in instances:
            assert srv.exists()
            assert srv.status()
            srv.setup_ldapi()
            srv.open()
            expected = {
                "nsDS5Flags": 1,
                "nsDS5ReplicaType": 3,
                "nsDS5ReplicaId": 2,
            }
            verify_role(log, srv, None, expected=expected)
    except ( AssertionError, LDAPError ) as exc:
        ansibletest.save_artefacts()
        raise exc
    finally:
        # Step 7: Perform cleanup
        cleanup(instances)
