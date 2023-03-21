#!/usr/bin/python3
# -*- coding: utf-8 -*

# Copyright: Contributors to the Ansible project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

""" This module manage the 389ds instances configuration."""

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

ANSIBLE_METADATA = {
    "metadata_version": "1.0",
    "supported_by": "community",
    "status": ["preview"],
}

DOCUMENTATION = r'''
---
module:ds389_module

short_description: This module provides method manage 389ds instances configuration.
description:
    This module allow to:
    - Create or remove ldap server instances and update their configuration.
    - Update the state of the ds389 (or RHDS) instances on the local host.
    - Gather instances status and configuration.
version_added: 1.0.0
extends_documentation_fragment:
  - ds389_server_doc

options:
    ds389:
      description: This option is added by ds389_server plugin and contains the options that are needed to configure 389ds instances.
      type: dict
      suboptions: See the ds389_server_doc documentation fragment.
    ds389info:
      description: This option is added by ds389_info plugin and contains the options that are needed to gather 389ds instances configuration.
      type: dict
      suboptions:
        ds389_prefix:
        description: The 389ds installation prefix
        type: path

author:
    - Pierre Rogier (@progier389)

requirements:
    - python3-lib389 patch from https://github.com/389ds/389-ds-base/pull/5253

    - python >= 3.9
    - python3-lib389 >= 2.2
    - 389-ds-base >= 2.2
'''

EXAMPLES = r'''
# Create a set of DS instances
- name: Playbook to create a set of DS instances
  hosts: ldapservers
  become: true

  tasks:
    - name: "Create 389ds instances according to the inventory"
      ds389.ansible_ds.ds389_server:

# Remove all DS instances
- name: Playbook to remove all DS instances
  hosts: ldapservers
  become: true

  tasks:
    - name: "Remove all 389ds instances on targeted hosts"
      ds389.ansible_ds.ds389_server:
        state: absent

# Playbook to gather DS instances info
- name: Playbook to gather DS instances info
  hosts: ldapservers
  become: true

  tasks:
    - name: "Gather 389ds instances status and configuration"
      ds389.ansible_ds.ds389_info:
'''

RETURN = r'''
# These are examples of possible return values, and in general should use other names for return values.
original_message:
    description: The original name param that was passed in.
    type: str
    returned: always
    sample: {
        "state": "present",
        "ds389_server_instances": [
            {
                "state": "present",
                "backends": [
                    {
                        "state": "present",
                        "indexes": [ ],
                        "suffix": "dc=example,dc=com",
                        "name": "userroot"
                    }
                ],
                "started": "true",
                "dseMods": null,
                "rootpw": "secret12",
                "port": "38901",
                "secure_port": "63601",
                "name": "i1"
            },
            {
                "state": "present",
                "backends": [
                    {
                        "state": "present",
                        "indexes": [ ],
                        "suffix": "dc=example,dc=com",
                        "name": "userroot"
                    }
                ],
                "started": "true",
                "dseMods": null,
                "rootpw": "secret12",
                "port": "38902",
                "secure_port": "63602",
                "name": "i2"
            }
        ],
        "ds389_server_prefix": "/home/progier/sb/ai1/tst/ci-install"
    }

message:
    description: The list containing messages about changes
    type: list
    returned: always
    sample: [
        "Creating instance slapd-i1",
        "Set nsslapd-port:38901 in cn=config",
        "Set nsslapd-secureport:63601 in cn=config",
        "Creating backend userroot on suffix dc=example,dc=com",
        "Set nsslapd-suffix:dc=example,dc=com in cn=userroot,cn=ldbm database,cn=plugins,cn=config",
        "Creating instance slapd-i2",
        "Set nsslapd-port:38902 in cn=config",
        "Set nsslapd-secureport:63602 in cn=config",
        "Creating backend userroot on suffix dc=example,dc=com",
        "Set nsslapd-suffix:dc=example,dc=com in cn=userroot,cn=ldbm database,cn=plugins,cn=config"
     ]

'''



import sys
import os
import io
import itertools
import json
import logging

from pathlib import Path
from ansible.module_utils.basic import AnsibleModule
from ansible.errors import AnsibleError


home = os.getenv("HOME")
path=f'{home}/.ansible/collections/ansible_collections/ds389/ansible_ds/plugins'
sys.path += [str(Path(__file__).parent.parent), path]
from module_utils.ds389_entities_options import CONTENT_OPTIONS
from module_utils.ds389_entities import ConfigRoot, toAnsibleResult
from module_utils.ds389_util import init_log, get_log


_logbuff = io.StringIO()
init_log("ds389_module", stream=_logbuff)


HIDDEN_ARGS = ( 'userpassword', 'rootpw', 'ReplicationManagerPassword'.lower() )

COMMON_OPTIONS= {
    'ds389_prefix': {
        'description': '389 Directory Service non standard installation path.',
        'required': False,
        'type': 'str',
    },
    'ansible_verbosity': {
        'description': 'Number of -v options in ansible-playbook command',
        'required': True,
        'type': 'int',
    },
    'ansible_check_mode': {
        'description': 'Tells whether check mode is enabled',
        'required': True,
        'type': 'bool',
    },
}


def safe_dup_keyval(key, val):
    """Duplicate dict val and hide values associated with HIDDEN_ARGS."""
    if key.lower() in HIDDEN_ARGS:
        return "******"
    return safe_dup(val)


def safe_dup(src):
    """Duplicate data from src and hide values associated with HIDDEN_ARGS."""
    if isinstance(src, list):
        return [ safe_dup(val) for val in src ]
    if isinstance(src, dict):
        return { key: safe_dup_keyval(key, val) for (key,val) in src.items() }
    return src


def manage_instances(content, result, checkmode):
    """Manage the instances configuration."""

    try:
        wanted_state = ConfigRoot.from_content(content)
    #pylint: disable=broad-exception-caught
    except Exception as exc:
        raise AnsibleError('Failed to validate the parameters.') from exc
    #result['cooked_message'] = safe_dup(wanted_state.tolist())
    get_log().debug(f"wanted_state={wanted_state}")
    # Determine current state
    host = ConfigRoot()
    host.getFacts()
    # Then change it
    summary = []
    wanted_state.update(host, summary, checkmode)
    result['message'] =  summary
    # Summary is a list of string describing the changes
    # So config changed if the list is not empty
    if summary:
        result['changed'] = True


#pylint: disable=unused-argument
def manage_facts(fact, result, checkmode):
    """Get the facts: The instances status and configuration."""
    # if the user is working with this module in only check mode we do not
    # want to make any changes to the environment, just return the current
    # state with no modifications
    if checkmode:
        return
    dsroot = ConfigRoot()
    dsroot.getFacts()
    result['ansible_facts'] = {
        **toAnsibleResult(dsroot.tolist())
    }


def handle_common_parameters(params):
    """Handle parameters that are common to all ds389_module 'functions'."""
    res = {}
    if 'ds389_prefix' in params:
        prefix = params['ds389_prefix']
    else:
        prefix = None
    if prefix:
        os.environ['PREFIX'] = prefix
    res['prefix'] = prefix
    debuglvl = params['ansible_verbosity']
    if debuglvl >= 4:
        get_log().setLevel(logging.DEBUG)
        os.environ['DEBUGGING'] = '1' # Enable lib389 debug logs
    elif debuglvl == 3:
        get_log().setLevel(logging.INFO)
    elif debuglvl == 1:
        get_log().setLevel(logging.WARNING)
    res['debuglvl'] = debuglvl
    # Then removes common params
    #pylint: disable=consider-iterating-dictionary
    for key in COMMON_OPTIONS.keys():
        params.pop(key, None)
    return res


def conv_val(key, val):
    """Perform conversion on an option specifier to support case insensitivity."""
    if key == "choices":
        # Get all lowercase/uppercase combination of all values
        allowed_values = []
        # For user readability put first the original values
        for value in val:
            allowed_values.append(value)
        # Then add all uppercase/lowercase combinations
        for value in val:
            for items in itertools.product(*zip(value.upper(), value.lower())):
                newval = "".join(items)
                if newval not in allowed_values:
                    allowed_values.append(newval)
        return allowed_values
    if isinstance(val, dict):
        return conv_specs(val)
    return val


def conv_specs(spec):
    """Perform conversion on option specifier to support case insensitivity."""
    return { key:conv_val(key, val) for key,val in spec.items() }


def run_module():
    """Module core function."""

    # define available arguments/parameters a user can pass to the module
    module_args = {
        'ds389': { 'type':'dict', 'required':False,
                   'options': { **COMMON_OPTIONS, **conv_specs(CONTENT_OPTIONS) }, },
        'ds389info': { 'type':'dict', 'required':False,
                   'options': COMMON_OPTIONS, },
    }

    # seed the result dict in the object
    # we primarily care about changed and state
    # changed is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = {
        "changed": False,
        "invocation": '',
        "message": '',
    }

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(
        argument_spec=module_args,
        mutually_exclusive=[ ('ds389', 'ds389info'), ],
        supports_check_mode=True
    )

<<<<<<< HEAD
    result['raw_invocation'] = module.params
=======
>>>>>>> 8304674 (Issue 31 - Add ds389_info plugin)
    result['invocation'] = safe_dup(module.params)
    content = module.params['ds389']
    fact = module.params['ds389info']
    try:
        if content:
            common_params = handle_common_parameters(content)
            manage_instances(content, result, module.check_mode)
        elif fact:
            common_params = handle_common_parameters(fact)
            manage_facts(fact, result, module.check_mode)
        else:
            raise AnsibleError("Operation failed: Missing 'ds389' or 'ds389info' parameter.")
    #pylint: disable=broad-exception-caught
    except Exception as exc:
        get_log().error(f'ds389_module failed: {str(result)}')
        logbuff = str(_logbuff.getvalue())
        if logbuff:
            result['module_debug'] = logbuff
        result['exception'] = exc
        module.fail_json('ds389_module failed', **result)

    #prefix in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    get_log().debug(f"Result is: {json.dumps({**result}, sort_keys=True, indent=4)}")
<<<<<<< HEAD
    logbuff = str(_logbuff.getvalue())
    if common_params['debuglvl'] >0 and logbuff:
        result['module_debug'] = logbuff
=======
    if common_params['debuglvl'] >0 and _logbuff.getvalue():
        result['debug'] = _logbuff.getvalue()
>>>>>>> 8304674 (Issue 31 - Add ds389_info plugin)
    module.exit_json(**result)


if __name__ == '__main__':
    #from ansible.module_utils.basic import AnsibleModule, _ANSIBLE_ARGS
    #with open(f'{home}/ds389_module.stdin', 'wb') as fout:
    #    if _ANSIBLE_ARGS:
    #        fout.write(_ANSIBLE_ARGS)
    run_module()
