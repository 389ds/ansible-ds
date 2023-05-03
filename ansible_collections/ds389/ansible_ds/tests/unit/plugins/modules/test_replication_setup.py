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

from socket import gethostname
from ldap import LDAPError
from lib389 import DirSrv
from lib389.properties import SER_SERVERID_PROP
from lib389.replica import ReplicationManager
from lib389.agreement import Agreements
from lib389._constants import DEFAULT_SUFFIX
from lib389.cli_base import connect_instance, FakeArgs
from lib389.idm.domain import Domain


DIRECTORY_MANAGER_PASSWORD = "secret12"
REPLICATION_MANAGER_PASSWORD = "secret34"
SUFFIX = "dc=example,dc=com"
HOSTNAME = gethostname()

if "DEBUGGING" in os.environ:
    VERBOSITY = 5
else:
    VERBOSITY = 0

MODULE_ARGS = {
    "ANSIBLE_MODULE_ARGS":
    {
        "ds389": {
            "ds389_agmts": [
                {
                    "fulltargetname": "localhost.supplier2.userroot",
                    "name": "supplier2",
                    "target": "supplier2",
                    "replicabindmethod": "simple",
                    "replicacredentials": REPLICATION_MANAGER_PASSWORD,
                    "replicahost": HOSTNAME,
                    "replicaport": "5556",
                    "replicatransportinfo": "ldap",
                    "replicabinddn": "cn=replmgr,cn=config",
                    "replicaid": "2",
                    "replicarole": "supplier",
                    "suffix": SUFFIX
                }
            ],
            "ds389_server_instances": [
                {
                    "backends": [
                        {
                            "replicabinddn": "cn=replmgr,cn=config",
                            "replicaid": "2",
                            "replicarole": "supplier",
                            "replicacredentials": REPLICATION_MANAGER_PASSWORD,
                            "agmts":
                            [
                                {
                                    "replicabinddn": "cn=replmgr,cn=config",
                                    "replicabindmethod": "simple",
                                    "replicacredentials": REPLICATION_MANAGER_PASSWORD,
                                    "replicahost": HOSTNAME,
                                    "replicaport": "5555",
                                    "replicatransportinfo": "ldap",
                                    "name": "m2m1"
                                }
                            ],
                            "indexes": [],
                            "name": "userroot",
                            "suffix": SUFFIX
                        }
                    ],
                    "name": "supplier2",
                    "port": 5556,
                    "rootpw": DIRECTORY_MANAGER_PASSWORD,
                    "secure_port": 6667,
                    "started": True
                },
                {
                    "backends": [
                        {
                            "replicabinddn": "cn=replmgr,cn=config",
                            "replicabindmethod": "simple",
                            "replicacredentials": REPLICATION_MANAGER_PASSWORD,
                            "replicahost": HOSTNAME,
                            "replicaid": "1",
                            "replicaport": "5556",
                            "replicarole": "supplier",
                            "replicatransportinfo": "ldap",
                            "agmts": [],
                            "indexes": [],
                            "name": "userroot",
                            "suffix": SUFFIX
                        }
                    ],
                    "name": "supplier1",
                    "port": 5555,
                    "rootpw": DIRECTORY_MANAGER_PASSWORD,
                    "secure_port": 6666,
                    "started": True
                }
            ],
            "ansible_check_mode": False,
            "ansible_verbosity": VERBOSITY
        }
    }
}

def cleanup(instances):
    """Remove the instances."""
    for srv in instances:
        if srv.exists():
            srv.delete()

def encode(val):
    """Encode strings in ldap add modifier tuple."""
    attr = val[0]
    new_vals = [ elmt.encode(encoding='utf-8') for elmt in val[1] ]
    return ( attr, new_vals )


def init_suffix(inst):
    """Create suffix entry and replication manager group."""
    # replication manager group in needed because
    # test_replication_topology changes it to test replication
    entries = {
        "dc=example,dc=com" : [
            ( "dc", [ "example", ] ),
            ( "objectclass", [ "top", "domain", ] ) ],
        "cn=replication_managers,dc=example,dc=com" : [
            ( "cn", [ "replication_managers", ] ),
            ( "objectclass", [ "top", "groupOfNames", ] ) ],
    }
    for key,val in entries.items():
        new_val = [ encode(elmt) for elmt in val ]
        inst.add_s(key, new_val, escapehatch='i am sure')


def test_ds389_create_with_replication_is_idempotent(ansibletest):
    """Test  ds389_server module to create replicated topology.
        Setup: None
        Step 1: Ensure that supplier1 and supplier2 instances does not exist
        Step 2: Run ds389_server module
        Step 3: Verify that supplier1 ande supplier2 instances exists.
        Step 4: Verify changed is true
        Step 5: Run again ds389_server module
        Step 6: Verify changed is false
        Step 7: Add suffix entries
        Step 8: Initialize supplier2
        Step 9: Check that changes get replicated.
        Step 10: Perform cleanup
        Result 1: No error
        Result 3: No error
        Result 3: Instances should exist and be started.
        Result 4: change should be true
        Result 5: No error
        Result 6: change should be false
        Result 7: No error
        Result 8: No error
        Result 9: No error
        Result 10: No error
    """

    log = ansibletest.get_log(__name__)
    # Step 1: Ensure that i1 and i2 instances does not exist
    instances=[]
    for serverid in ( "supplier1", "supplier2" ):
        srv = DirSrv()
        srv.allocate({ SER_SERVERID_PROP: serverid })
        instances.append(srv)
    cleanup(instances)
    try:
        # Step 2: Run ds389_server module
        log.info('First run of ds389_server module ')
        result = ansibletest.run_test_module( MODULE_ARGS )
        # Step 3: Verify that supplier1 ande supplier2 instances exists and are started.
        for srv in instances:
            assert srv.exists()
            assert srv.status()
            srv.setup_ldapi()
            srv.open()
        # Step 4: Verify changed is true
        assert result['changed'] is True
        # Step 5: Run again ds389_server module
        log.info('Second run of ds389_server module ')
        result = ansibletest.run_test_module( MODULE_ARGS )
        # Step 6: Verify changed is false
        assert result['changed'] is False
        # Step 7: Create suffix entries.
        for inst in instances:
            init_suffix(inst)
        # Step 8: Init supplier 2
        agmt = Agreements(instances[0]).list()[0]
        agmt.begin_reinit()
        (done, error) = agmt.wait_reinit()
        assert done is True
        assert error is False
        # Step 9: Test replication
        repl = ReplicationManager(DEFAULT_SUFFIX)
        repl.test_replication_topology(instances)
    except ( AssertionError, LDAPError ) as exc:
        ansibletest.save_artefacts()
        raise exc
    finally:
        # Step 10: Perform cleanup
        # cleanup(instances)
        pass
