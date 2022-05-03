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

short_description: This imodule provides info on the ldap server instances available on the local host.

version_added: "1.0.0"

description:
    - This module allow to collect the state of all the ds389 (or RHDS) instances on the local host.

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

from ansible.module_utils.basic import AnsibleModule, env_fallback
from pathlib import Path
import sys
import os
import json
import traceback

if __name__ == "__main__":
    sys.path += [str(Path(__file__).parent.parent)]
    from module_utils.dsentities import Option, DSEOption, ConfigOption, SpecialOption, OptionAction, MyYAMLObject, YAMLHost, YAMLInstance, YAMLBackend, YAMLIndex
    from module_utils.dsutil import setLogger, getLogger, log, toAnsibleResult
else:
    from ansible_collections.ds.ansible_ds.plugins.module_utils.dsentities import Option, DSEOption, ConfigOption, SpecialOption, OptionAction, MyYAMLObject, YAMLHost, YAMLInstance, YAMLBackend, YAMLIndex
    from ansible_collections.ds.ansible_ds.plugins.module_utils.dsutil import setLogger, getLogger, log, toAnsibleResult




def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        prefix=dict(type='path', required=False, fallback=(env_fallback, ['PREFIX', 'INSTALL_PREFIX'])),
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
        supports_check_mode=True
    )

    # if the user is working with this module in only check mode we do not
    # want to make any changes to the environment, just return the current
    # state with no modifications
    if module.check_mode:
        module.exit_json(**result)

    # manipulate or modify the state as needed (this is going to be the
    # part where your module will do what it needs to do)
    if module.params['prefix'] is not None:
        result['original_message'] = module.params['prefix']
        os.environ['PREFIX'] = module.params['prefix']

    verbose=0
    if 'DEBUGGING' in os.environ:
        verbose = 5
    setLogger(__file__, verbose)
    global log
    log = getLogger()

    ### Create the main "Host" node containing this host instances
    try:
        host = YAMLHost()
        host.getFacts() 
    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr)
        module.fail_json(f'Failed to determine the ds389 instances state. error is {e}')
        return
    result['message'] = 'goodbye'
    result['my_useful_info'] = {
        **toAnsibleResult(host)
    }
    #prefix in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    log.debug(json.dumps({**result}, sort_keys=True, indent=4))
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    if 'test' in sys.argv:
        buff = json.dumps( { "ANSIBLE_MODULE_ARGS": { "prefix" : os.getenv('PREFIX','') } } )
        sys.argv = [ sys.argv[0], buff ]
    main()

