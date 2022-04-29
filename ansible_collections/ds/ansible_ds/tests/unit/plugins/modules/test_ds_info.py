# --- BEGIN COPYRIGHT BLOCK ---
# Copyright (C) 2022 Red Hat, Inc.
# All rights reserved.
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# --- END COPYRIGHT BLOCK ---
#
#

import os
import sys

# Set PYTHONPATH to be able to find lib389 in PREFIX install (computed within conftest seesion initialization hook)
if "LIB389PATH" in os.environ:
    sys.path.insert(0, os.environ['LIB389PATH'])


from lib389.topologies import topology_m2 as topo_m2

def test_info1(topo_m2, ansibletest):
    log = ansibletest.getLog(__name__)
    result = ansibletest.runModule( { "ANSIBLE_MODULE_ARGS": { "prefix" : os.getenv('PREFIX', '') } } )
    log.info(f'result={result}')
    assert 'my_useful_info' in result
    assert ansibletest.getInstanceAttr('supplier1', 'name') == 'supplier1'
    assert ansibletest.getInstanceAttr('supplier2', 'name') == 'supplier2'
    assert ansibletest.getBackendAttr('supplier1', 'userroot', 'name') == 'userroot'
    assert ansibletest.getBackendAttr('supplier2', 'userroot', 'name') == 'userroot'
