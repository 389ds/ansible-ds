#!/usr/bin/python
"""Action plugin that calls ds389_module after having prepared its parameters."""

# Copyright: Contributors to the 389ds project
# GNU General Public License v3.0+ (see COPYRIGHT or https://www.gnu.org/licenses/gpl-3.0.txt)

# Make coding more python3-ish, this is required for contributions to Ansible
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type


from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleError

DOCUMENTATION = r'''
---
module:ds389_server

short_description: This action plugin provides method to gather facts about ds389 instances.
description:
    - This plugins call the module that allow to get the state of the ds389 (or RHDS) instances on the targeted host.

options:
    option-name: 
      ds389_option:
        description:
            - The 389ds installation prefix (empty for standard installation)
        type: path
        default: null
        version_added: "1.0.0"

author:
    - Pierre Rogier (@progier389)

requirements:
    - python >= 3.9
'''


class ActionModule(ActionBase):
    """The action plugin class."""

    def run(self, tmp=None, task_vars=None):
        """The action plugin method."""

        #pylint: disable=super-with-arguments
        super(ActionModule, self).run(tmp, task_vars)
        plugin_args = self._task.args.copy()


        try:
            args = {}
            for env in (task_vars, plugin_args, ):
                for key in ('ds389_prefix', 'ansible_verbosity', 'ansible_check_mode'):
                    if key in env:
                        args[key] = env[key]

            module_args = {'ds389info' : args}
            # Call the module on remote host
            module_return = self._execute_module(module_name='ds389.ansible_ds.ds389_module',
                                                 module_args=module_args,
                                                 task_vars=task_vars, tmp=tmp)
        except (AnsibleError, LookupError) as exc:
            module_return = { "failed": True, "exception": exc, "msg": str(exc) }
        return module_return
