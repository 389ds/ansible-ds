#!/usr/bin/python
# Make coding more python3-ish, this is required for contributions to Ansible
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.plugins.action import ActionBase
from datetime import datetime


class ActionModule(ActionBase):

    """ The dict containing inventory/parameter variable name -> module option. """
    VAR_DICT = { 
        'ds389_server_instances' : 'instances',
        'ds389_prefix' : 'prefix',
        'state' : 'state',
    }

    def set_param(self, args, vars, key):
        """ Retrieve a value from parameters or from inventory
            and propagate it to the module parameters.
         """

        if 'content' not in args:
            args['content'] = dict()
        try:
            val = args[key]
        except KeyError:
            try:
                val = vars[key]
            except KeyError:
                return
        # Evaluate Jinja expressions
        val = self._templar.template(val)
        args['content'][ActionModule.VAR_DICT[key]] = val

    def run(self, tmp=None, task_vars=None):
        super(ActionModule, self).run(tmp, task_vars)
        module_args = self._task.args.copy()

        # Should extract the variables needed by ds389.ansible_ds.ds389_server
        for key in ActionModule.VAR_DICT.keys():
            self.set_param(module_args, task_vars, key)
            
        module_return = self._execute_module(module_name='ds389.ansible_ds.ds389_server',
                                             module_args=module_args,
                                             task_vars=task_vars, tmp=tmp)
        return module_return
