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

ANSIBLE_METADATA = {
    "metadata_version": "1.0",
    "supported_by": "community",
    "status": ["preview"],
}

DOCUMENTATION = r'''
---
module: ds_server

short_description: This module provides method to create or remove ldap server instances and update their configuration.
description:
    - This module allow to update the state of the ds389 (or RHDS) instances on the local host.
extends_documentation_fragment:
  - dsserver_doc

options:

author:
    - Pierre Rogier (@progier389)

requirements:
    - python >= 3.9
    - python3-lib389 >= 2.2
    - python3-lib389 patch from https://github.com/389ds/389-ds-base/pull/5253
    - 389-ds-base >= 2.2
'''

EXAMPLES = r'''
# Install an instance:
- name: Playbook to create a DS instance
  hosts: localhost

  vars:
    dsserver_instances:
        -
            name: i1
            rootpw: !vault |
                      $ANSIBLE_VAULT;1.1;AES256
                      30353330663535343236626331663332336636383562316662326463363161626163653731353564
                      6130636534336637353939643930383962306431323262390a663839666262313338613334303937
                      66656631313662343132346638643137396337613962636565393931636132663435306433643130
                      3661636162373437330a633066313635343063356635623137626635623764626139373061383634
                      3439

            port: 389
            secure_port: 636
            backends:
                -
                    name: "userroot"
                    suffix: "dc=example,dc=com"
                -
                    name: "second"
                    suffix: "dc=another example,dc=com"
                -
                    name: "peoplesubsuffix"
                    suffix: "o=people,dc=example,dc=com"

  collections:
    - ds.ansible_ds

  roles:
    - role: dsserver
      state: present
'''

RETURN = r'''
# These are examples of possible return values, and in general should use other names for return values.
original_message:
    description: The original name param that was passed in.
    type: str
    returned: always
    sample: {
        "state": "present",
        "dsserver_instances": [
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
        "dsserver_prefix": "/home/progier/sb/ai1/tst/ci-install"
    }

message:
    description: The output message that the test module generates.
    type: str
    returned: always
    sample: 'goodbye'

my_useful_info:
    description: The dictionary containing messages about changes
    type: dict
    returned: always
    sample: {
        msgs": [
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
    from module_utils.dsentities import ConfigRoot
    from module_utils.dsutil import setLogger, getLogger, log
    from module_utils.dsutil import setLogger, getLogger, log
    from module_utils.dsentities_options import CONTENT_OPTIONS
else:
    from ansible_collections.ds.ansible_ds.plugins.module_utils.dsentities import ConfigRoot
    from ansible_collections.ds.ansible_ds.plugins.module_utils.dsutil import setLogger, getLogger, log
    from ansible_collections.ds.ansible_ds.plugins.module_utils.dsentities_options import CONTENT_OPTIONS



def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        path=dict(type='path', required=False),
        content=dict(type='dict', required=False, options=CONTENT_OPTIONS),
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

    # Validate the parameter and get a ConfigRoot object
    c="{}"
    try:
        if path:
            wanted_state = ConfigRoot.from_path(path)
        elif content:
            wanted_state = ConfigRoot.from_content(content)
        else:
            wanted_state = ConfigRoot.from_stdin()
    except Exception as e:
        raise e
        module.fail_json(f'Failed to validate the parameters. error is {e}')
    result['original_message'] = wanted_state.tolist()

    log.debug(f"wanted_state={wanted_state}")
    # Determine current state
    host = ConfigRoot()
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

