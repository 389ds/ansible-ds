# --- BEGIN COPYRIGHT BLOCK ---
# Copyright (C) 2022 Red Hat, Inc.
# All rights reserved.
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# --- END COPYRIGHT BLOCK ---
#
#

""" This module contains the testcases fore ds389_info ansible module."""

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


def test_info(topo_m2, ansibletest):
    """Test  ds389_info module #1.
        Setup: two suppliers
        Step 1: Run ds389_info module
        Step 2: Verify The output
        Result 1: No error
        Result 2: check that supplier1 and supplier2 instances are in the facts.
                  check that supplier1 userroot backend is in the facts.
                  check that supplier2 userroot backend is in the facts.
    """

    log = ansibletest.get_log(__name__)
    args = { 'ds389info' : {
        "ansible_verbosity" : 0,
        "ansible_check_mode": False,
        "ds389_prefix" : os.getenv('PREFIX', '') } }
    result = ansibletest.run_test_module( { "ANSIBLE_MODULE_ARGS": args } )
    log.info(f'result={result}')
    assert 'ansible_facts' in result
    assert ansibletest.get_instance_attr('supplier1', 'state') == 'present'
    assert ansibletest.get_instance_attr('supplier2', 'state') == 'present'
    assert ansibletest.get_backend_attr('supplier1', 'userroot', 'state') == 'present'
    assert ansibletest.get_backend_attr('supplier2', 'userroot', 'state') == 'present'
