# --- BEGIN COPYRIGHT BLOCK ---
# Copyright (C) 2022 Red Hat, Inc.
# All rights reserved.
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# --- END COPYRIGHT BLOCK ---
#
#

""" This module contains the testcases fore ds_info ansible module."""

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
from lib389.topologies import topology_m2 as topo_m2    # pylint: disable=wrong-import-position


def test_info1(topo_m2, ansibletest):
    """Test dsinfo module #1.
        Setup: two suppliers
        Step 1: Run ds_info module
        Step 2: Verify The output
        Result 1: No error
        Result 2: check that supplier1 and supplier2 instances are in the facts.
                  check that supplier1 userroot backend is in the facts.
                  check that supplier2 userroot backend is in the facts.
    """

    log = ansibletest.getLog(__name__)
    args = { "prefix" : os.getenv('PREFIX', '') }
    result = ansibletest.runTestModule( { "ANSIBLE_MODULE_ARGS": args } )
    log.info(f'result={result}')
    assert 'my_useful_info' in result
    assert ansibletest.getInstanceAttr('supplier1', 'name') == 'supplier1'
    assert ansibletest.getInstanceAttr('supplier2', 'name') == 'supplier2'
    assert ansibletest.getBackendAttr('supplier1', 'userroot', 'name') == 'userroot'
    assert ansibletest.getBackendAttr('supplier2', 'userroot', 'name') == 'userroot'
