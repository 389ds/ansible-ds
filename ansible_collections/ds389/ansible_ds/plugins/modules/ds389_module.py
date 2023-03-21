#!/usr/bin/python3
""" This module manage the 389ds instances configuration."""
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

ANSIBLE_METADATA = {
    "metadata_version": "1.0",
    "supported_by": "community",
    "status": ["preview"],
}



import sys
import os
import io
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
    return val


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
    wanted_state.update(facts=host, summary=summary, onlycheck=checkmode)
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
            


def run_module():
    """Module core function."""

    # define available arguments/parameters a user can pass to the module
    module_args = {
        'ds389': { 'type':'dict', 'required':False,
                   'options': { **COMMON_OPTIONS, **CONTENT_OPTIONS }, },
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
        if _logbuff.getvalue():
            result['debug'] = _logbuff.getvalue()
        result['exception'] = exc
        get_log().error(f'ds389_module failed: {str(result)}')
        module.fail_json('ds389_module failed', **result)

    #prefix in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    get_log().debug(f"Result is: {json.dumps({**result}, sort_keys=True, indent=4)}")
    if common_params['debuglvl'] >0 and _logbuff.getvalue():
        result['debug'] = _logbuff.getvalue()
    module.exit_json(**result)


if __name__ == '__main__':
    #from ansible.module_utils.basic import AnsibleModule, _ANSIBLE_ARGS
    #with open(f'{home}/ds389_module.stdin', 'wb') as fout:
    #    if _ANSIBLE_ARGS:
    #        fout.write(_ANSIBLE_ARGS)
    run_module()
