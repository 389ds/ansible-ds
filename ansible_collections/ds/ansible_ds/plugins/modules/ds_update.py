#!/usr/bin/python3
# -*- coding: utf-8 -*

# --- BEGIN COPYRIGHT BLOCK ---
# Copyright (C) 2022 Red Hat, Inc.
# All rights reserved.
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# --- END COPYRIGHT BLOCK ---
#

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r'''
---
module: ds_info

short_description: This module provides method to update the ldap server instances available on the local host.

version_added: "1.0.0"

description:
    - This module allow to update the state of the ds389 (or RHDS) instances on the local host.

options:
    prefix:
        description: This is the prefix install path in which instances will be looked at.
        required: false
        type: path

author:
    - Pierre Rogier (@progier389)

requirements:
    - python >= 3.9
    - python3-lib389 >= 2.2
    - python3-lib389 patch from https://github.com/389ds/389-ds-base/pull/5253
    - 389-ds-base >= 2.2
'''

EXAMPLES = r'''
# Pass in a message
- name: Test with a message
  my_namespace.my_collection.my_test_info:
    name: hello world
'''

RETURN = r'''
# These are examples of possible return values, and in general should use other names for return values.
original_message:
    description: The original name param that was passed in.
    type: str
    returned: always
    sample: 'hello world'
message:
    description: The output message that the test module generates.
    type: str
    returned: always
    sample: 'goodbye'
my_useful_info:
    description: The dictionary containing information about your system.
    type: dict
    returned: always
    sample: {
        'foo': 'bar',
        'answer': 42,
    }
'''

from ansible.module_utils.basic import AnsibleModule
from pathlib import Path
import sys
import os
import io
import json
import traceback
import yaml
import argparse

# import the collection module_utils modules.
if __name__ == "__main__":
    sys.path += [str(Path(__file__).parent.parent)]
    from module_utils.dsentities import YAMLRoot
    from module_utils.dsutil import setLogger, getLogger, log
    from module_utils.dsutil import setLogger, getLogger, log, toAnsibleResult
else:
    from ansible_collections.ds.ansible_ds.plugins.module_utils.dsentities import YAMLRoot
    from ansible_collections.ds.ansible_ds.plugins.module_utils.dsutil import setLogger, getLogger, log, toAnsibleResult



def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        path=dict(type='path', required=False),
        content=dict(type='raw', required=False),
    )

    # seed the result dict in the object
    # we primarily care about changed and state
    # changed is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = dict(
        changed=False,
        original_message='',
        message='',
        my_useful_info={},
    )

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(
        argument_spec=module_args,
        mutually_exclusive=[ ('path', 'content'), ],
        supports_check_mode=True
    )

    verbose=0
    if 'DEBUGGING' in os.environ:
        verbose = 5
    setLogger(__file__, verbose)
    global log
    log = getLogger()

    path = module.params['path']
    content = module.params['content']

    # Validate the parameter and get a YAMLRoot object
    c="{}"
    try:
        if path:
            wanted_state = YAMLRoot.from_path(path)
        elif content:
            wanted_state = YAMLRoot.from_content(content)
        else:
            wanted_state = YAMLRoot.from_stdin()
    except Exception as e:
        raise e
        module.fail_json(f'Failed to validate the parameters. error is {e}')
    result['original_message'] = wanted_state.todict()

    log.debug(f"wanted_state={wanted_state}")
    # Determine current state
    host = YAMLRoot()
    host.getFacts()
    # Then change it
    summary = []
    wanted_state.update(facts=host, summary=summary, onlycheck=module.check_mode)
    result['my_useful_info'] =  { "msgs": summary }
    result['message'] = 'goodbye'
    # Summary is a list of string describing the changes
    # So config changed if the list is not empty
    if summary:
        result['changed'] = True

    #prefix in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    log.debug(f"Result is: {json.dumps({**result}, sort_keys=True, indent=4)}")
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    #sys.stdout = "foo"
    p = os.getenv("DEBUG_DSUPDATE_MODULE", None)
    if p:
        buff = json.dumps( { "ANSIBLE_MODULE_ARGS": { "path" : p } } )
        sys.argv = [ sys.argv[0], buff ]
    main()

