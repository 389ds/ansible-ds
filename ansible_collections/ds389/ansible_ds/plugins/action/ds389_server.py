#!/usr/bin/python
"""Action plugin that calls ds389_module after having prepared its parameters."""

# Copyright: Contributors to the 389ds project
# GNU General Public License v3.0+ (see COPYRIGHT or https://www.gnu.org/licenses/gpl-3.0.txt)

# Make coding more python3-ish, this is required for contributions to Ansible
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type


from copy import deepcopy
import os
import re
import logging
from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleError

DOCUMENTATION = r'''
---
module:ds389_server

short_description: This action plugin provides method to create or remove ldap server instances and update their configuration.
description:
    - This plugins call the module that allow to update the state of the ds389 (or RHDS) instances on the local host.
extends_documentation_fragment:
  - ds389_server_doc

options:
  - option-name:
      ds389_option_*
        description:
          - A modifier that allows to merge option in existing dict or to add items in existing list
          - * means any characters that are valid in an ansible variable name
          - These modifiers are processed using increasing lexicographic order
          - These options are processed at the plugin level and not sent to the module.
        type: dict
        suboptions:
          option-name:
            name:
              description:
                - The name defines the target dict or list that should be modified.
                - the target in nested list/dict is defined using a dot notation.
              type: string
              required: true
            merge:
              description:
                - merge option means that the sub keys must be merged in the target dict
              type: dict
            append:
              description:
                - append option means that following items must be added in target list
              type: list
            required_one_of:
                - merge
                - append
            mutually_exclusive:
                - merge
                - append
        version: 1.0.0

author:
    - Pierre Rogier (@progier389)

requirements:
    - python >= 3.9
'''


class _PH:
    """ This class handles the module parameters."""

    INSTANCES = 'ds389_server_instances'

    AGMTS = 'ds389_agmts'

    # The expected options in plugin parameters.
    OPTIONS = ( INSTANCES, AGMTS, 'ds389_prefix', 'state' )

    # The attribute telling that backend is a replica
    REPLICATED = 'replicarole'
    RID = 'replicaid'

    # The usefull keys from invemtory (keys starting with ds389_ are handled dynamically).
    INVENTORY_KEYS = ( 'ansible_verbosity', 'ansible_host', 'ansible_check_mode', 'hostvars' )

    HIDDEN_ARGS = ( 'userpassword', 'rootpw', 'ReplicationManagerPassword'.lower() )

    log = logging.getLogger('ds389_server')
    log.setLevel(logging.INFO)

    @staticmethod
    def target_match(varname, target):
        """Determine weither variable name match the agmt target name."""

        # escape the .
        target = target.replace('.', '\\.')
        # * means any string without .
        target = target.replace('*', '[^.]+')
        # Target may be at start and should finish with . or end of value.
        # or it mat start with antthing followed by . and
        # should finish with . or end of value.
        target = f'(^{target}([.]|$))|(^.*[.]{target}([.]|$))'
        return re.match(target, varname)


    @staticmethod
    def is_host_key(key):
        """Tells if inventory key is interresting."""
        if key in ( 'ansible_verbosity', 'ansible_host', 'ansible_check_mode' ):
            return True
        return key.startswith("ds389_")


    @staticmethod
    def get_safe_host_from_inventory(src, target):
        """Copy the interresting data and hide vault value for a single inventory hosts."""
        for key in src.keys():
            if _PH.is_host_key(key):
                target[key] = src[key]
            if key.startswith("vault_"):
                target[key] = "******"


    @staticmethod
    def get_safe_inventory(task_vars):
        """Copy interesting data from the inventory and hide vault values."""
        res = {}
        _PH.get_safe_host_from_inventory(task_vars, res)
        res["hostvars"] = {}
        for host in task_vars["hostvars"]:
            res["hostvars"][host] = {}
            _PH.get_safe_host_from_inventory(task_vars["hostvars"][host], res["hostvars"][host])
        return res


    @staticmethod
    def safe_dup_keyval(key, val):
        """Duplicate dict val and hide values associated with HIDDEN_ARGS."""
        if key.lower() in _PH.HIDDEN_ARGS:
            return "******"
        return val


    @staticmethod
    def safe_dup(src):
        """Duplicate data from src and hide values associated with HIDDEN_ARGS."""
        if isinstance(src, list):
            return [ _PH.safe_dup(val) for val in src ]
        if isinstance(src, dict):
            return { key: _PH.safe_dup_keyval(key, val) for (key,val) in src.items() }
        return src


    @staticmethod
    def lower_key_dict(arg):
        """Lowerize recursively all keys in a dict."""
        if isinstance(arg, list):
            return [ _PH.lower_key_dict(x) for x in arg ]
        if isinstance(arg, dict):
            return { key.lower(): _PH.lower_key_dict(val) for key,val in arg.items() }
        return arg


    @staticmethod
    def check_replica_roles(bedict, roles):
        """ Check whether backend replica role is one of the roles."""
        if _PH.REPLICATED in bedict:
            for role in roles:
                if bedict[_PH.REPLICATED].lower() == role:
                    return True
        return False


    def __init__(self, module, hostname, debuglvl, parent=None):
        self.args = {}
        self.host = hostname
        self.module = module
        self.vars = {}
        self.from_inventory = True
        self.debug = debuglvl
        self.replbes = None # Replica backends
        if parent:
            self.debug_info = parent.debug_info
            self.log = parent.log
        else:
            self.debug_info = {}
            home = os.getenv('HOME')
            logf = f'{home}/.ansible.ds389_server.log'
            # logh = logging.handlers.RotatingFileHandler(logf,
            #      maxBytes=1024*1024, backupCount=1, encoding="utf-8")
            logh = logging.FileHandler(logf, encoding="utf-8")
            fmt = '[%(asctime)s] %(levelname)s - [%(lineno)d]: %(message)s'
            datefmt = '%Y/%m/%d %H:%M:%S %z'
            logh.setFormatter(logging.Formatter(fmt, datefmt))
            if debuglvl >= 3:
                _PH.log.setLevel(logging.DEBUG)
            _PH.log.addHandler(logh)

    def __str__(self):
        return f'_PH(args={self.args}, host={self.host}, vars={self.vars})'

    def eval_jinja2(self, expr):
        """Evaluate Jinja2 expression."""
        #pylint: disable=protected-access
        return _PH.lower_key_dict(self.module._templar.template(expr))

    def add_keys(self, source, keylist):
        """Copy interresting key from source to the args dict."""

        for key in keylist:
            if key in source:
                _PH.log.debug('add_keys %s ==> %s', key, source[key])
                self.args[key.lower()] = _PH.lower_key_dict(source[key])

    def register_vars(self, name, val, nameprefix):
        """Recursively compute all parameter fullnames and makes all keys lowercase ."""

        self.vars[f'{nameprefix}{name}'] = val
        try:
            dictlist = isinstance(val[0], dict)
        except (KeyError, TypeError, IndexError):
            dictlist = False
        if dictlist:
            for item in val:
                # Recurse on named dict
                if 'name' in item:
                    self.register_vars(item['name'], item, nameprefix)
        elif isinstance(val, dict):
            nameprefix = f'{nameprefix}{name}.'
            for (key,val2) in val.items():
                if key != "name":
                    self.register_vars(key, val2, nameprefix)

    def apply_option(self, name, option):
        """Append/Merge parameters value according to 'option'."""
        try:
            tgtname = option['name'].lower()
        except TypeError as exc:
            raise AnsibleError(f"Option {name} value type is '{type(option)}' instead of 'dict'.") from exc
        except KeyError:
            raise AnsibleError(f"Option {name}: name attribute is missing.") from exc
        try:
            tgt = self.vars[tgtname]
        except KeyError as exc:
            error_info = {
                'option': option,
                'host': self.host,
                'vars': self.vars.keys() }
            _PH.log.error("Option %s:  %s attribute is not found in host %s.", name, tgtname, self.host)
            raise AnsibleError(f"Option {name}: {tgtname} attribute is not found in host {self.host}.") from exc
        if 'merge' in option:
            moption =  self.eval_jinja2(option['merge'])
            if not isinstance(moption, dict):
                error_info = { 'option': option, 'merge_option': moption }
                _PH.log.error("Option %s:  'merge' value type is '%s' instead of 'dict'. error_info=%s.", name, type(moption), error_info)
                raise AnsibleError(f"Option {name}: 'merge' value type is '{type(moption)}' instead of 'dict'.")
            if not isinstance(tgt, dict):
                error_info = { 'option': option, 'target': tgt }
                _PH.log.error("Option %s:  'merge' requires that target %s type is a 'dict' instead of '%s'. error_info=%s.", name, tgtname, type(tgt), error_info)
                raise AnsibleError(f"Option {name}: 'merge' requires that target {tgtname} type is a 'dict' instead of '{type(tgt)}'.")
            for key,val in moption.items():
                tgt[key.lower()] = _PH.lower_key_dict(val)
        elif 'append' in option:
            mappend =  self.eval_jinja2(option['append'])
            if isinstance(mappend, str) or not isinstance(mappend, list):
                error_info = { 'option': option, 'append_option': mappend }
                _PH.log.error("Option %s:  'append' value type is '%s' instead of 'list'. error_info=%s.", name, type(mappend), error_info)
                raise AnsibleError(f"Option {name}: 'append' value type is '{type(mappend)}' instead of 'list'.")
            if not isinstance(tgt, list):
                error_info = { 'option': option, 'target': tgt }
                _PH.log.error("Option %s:  'append' requires that target %s type is a 'list' instead of '%s'. error_info=%s.", name, tgtname, type(tgt), error_info)
                raise AnsibleError(f"Option {name}: 'append' requires that target {tgtname} type is a 'list' instead of '{type(tgt)}'.")
            for val in mappend:
                tgt.append(_PH.lower_key_dict(val))

    def apply_option_list(self, name, option):
        """Append/Merge parameters value according to 'option' items."""
        if isinstance(option, list) and not isinstance(option, str):
            for item in option:
                self.apply_option(name, item)
        else:
            self.apply_option(name, option)

    def resolve_agmt(self, agmt, agmtlist, bedict):
        """Merge the backend values with the agreement according to the target."""

        found = False
        for (befn, bedata) in bedict.items():
            if _PH.target_match(befn, agmt['target']):
                _PH.log.debug("Found target backend %s for agmt %s", befn, agmt)
                found = True
                ragmt = { **agmt, **bedata }
                # Remove children list of dicts
                ragmt.pop('indexes', None)
                ragmt.pop('agmts', None)
                agmtlist.append(ragmt)
        if not found:
            _PH.log.debug("Unable to resolve agmt %s. bedict=%s.", agmt, bedict)
            raise AnsibleError(f"Unable to resolve agmt {agmt}.")

    def common_handling(self, varsdict):
        """Perform operations common to all hosts."""
        # Save original data
        calling_args = deepcopy(self.args)

        # Evaluate Jinja2 expressions
        #pylint: disable=consider-iterating-dictionary
        for key in self.args.keys():
            self.args[key] = self.eval_jinja2(self.args[key])
            # Register parameters according to their full name
            self.register_vars(key, self.args[key], "")

        if self.from_inventory:
            # Then apply option_* changes
            options = sorted((key for key in varsdict.keys() if key.startswith("ds389_option_") ))
            for option in options:
                calling_args[option] = deepcopy(varsdict[option])
                self.apply_option_list(option, calling_args[option])

    def get_backends(self, hosts):
        """Get a dict of all replicated backends that have same suffix
           that one of the current host backend with supplier or hub role.
        """

        res = {}
        # Get all replicated backends
        for (host, hostargs) in hosts.items():
            for (varname, var) in hostargs.vars.items():
                if isinstance(var, dict) and _PH.REPLICATED in var:
                    if 'suffix' in var:
                        res[f'{host}.{varname}'] = var
        self.replbes = res
        _PH.log.debug('get_backends: all replicated backends are %s', res.keys())
        mybes = [ val for key,val in res.items() if key.startswith(f'{self.host}.') ]
        mysuffixes = [ val['suffix'] for val in mybes if _PH.check_replica_roles(val, ('supplier', 'hub')) ]
        return {key:val for key,val in res.items() if val['suffix'] in mysuffixes}

    def process_args(self, task_vars):
        """Main parameter processing code on plugin side."""

        self.add_debug_info(5, "inventory", _PH.get_safe_inventory(task_vars))
        self.add_debug_info(5, "args.vars", self.vars)
        # module_args is overwritten later on with safe values
        # but lets have the full value in case of exception
        # Eval Jinja2 expression and register variable by full names
        self.common_handling(task_vars)

        # Get instances data for all hosts
        hosts = { self.host: self }
        for (host, hostvar) in task_vars['hostvars'].items():
            if host == self.host:
                continue
            hosts[host] = _PH(self.module, host, self.debug, parent=self)
            hosts[host].add_keys(task_vars, (_PH.INSTANCES, _PH.AGMTS))
            hosts[host].common_handling(hostvar)

        # and use it to generate the backend list
        bedict = self.get_backends(hosts)
        self.add_debug_info(4, "replicated-backends", str(bedict.keys()))

        # then resolve the agmts
        if _PH.AGMTS in self.args:
            agmtlist=[]
            for agmt in self.args[_PH.AGMTS]:
                if not 'target' in agmt:
                    raise AnsibleError("Missing 'target' key in an ds389_agmts element.")
                if not isinstance(agmt['target'], list) and not isinstance(agmt['target'], str):
                    raise AnsibleError("'target' should contain a string or a list of strings" +
                         f" instead of {type(agmt['target'])}. Target is {agmt['target']}.")
                if isinstance(agmt['target'], str):
                    self.resolve_agmt(agmt, agmtlist, bedict)
                else:
                    for tgt in agmt['target']:
                        self.resolve_agmt({**agmt, 'target': tgt}, agmtlist, bedict)
            self.args[_PH.AGMTS] = agmtlist

        self.add_debug_info(1, "module_args", {'ds389' : self.safe_dup(self.args)})

    def add_debug_info(self, lvl, name, data):
        """Add debug info that are later added to the return message."""
        if lvl <= self.debug:
            self.debug_info[f'debug-{self.host}-{name}'] = data

    def validate_topology(self):
        """Perform global topology consistency checks."""
<<<<<<< HEAD
        rids = {} # { "rid::suffix" : bename }
        errors = []
        for bevname,bedict in self.replbes.items():
            suffix = bedict['suffix']
            try:
                rid = bedict[_PH.RID]
            except KeyError:
                rid = None
            if _PH.check_replica_roles(bedict, ('supplier',)):
                if  rid:
                    key = f'{rid}::{suffix}'
                    if key in rids:
                        errors.append((f"Duplicate ReplicaId {rid} for suffix {suffix}.",
                                       f"Backends {bevname} and {rids[key]} have same ReplicaId."))
                    else:
                        rids[key] = bevname
                else:
                    errors.append((f"Backend {bevname} is configured as a supplier but has no ReplicaId.",))
            if _PH.check_replica_roles(bedict, ('hub','consumer')):
                if  rid:
                    role = bedict[_PH.REPLICATED]
                    errors.append((f"Backend {bevname} is configured as a {role} but has a ReplicaID.",))
            if _PH.check_replica_roles(bedict, ('consumer',)) and "agmts" in bedict:
                errors.append((f"Backend {bevname} is configured as a consumer but has replica agreements.",))
        if errors:
            raise AnsibleError(f'Topology errors: {errors}')
=======
        pass
>>>>>>> 8304674 (Issue 31 - Add ds389_info plugin)


class ActionModule(ActionBase):
    """The action plugin class."""

    def run(self, tmp=None, task_vars=None):
        """The action plugin method."""

        #pylint: disable=super-with-arguments
        super(ActionModule, self).run(tmp, task_vars)
        plugin_args = self._task.args.copy()

        args = _PH(self, task_vars['ansible_host'], task_vars['ansible_verbosity'])
        _PH.log.info('Running ds389_server action plugin for target host: %s and verbosity %i.',
            task_vars['ansible_host'], task_vars['ansible_verbosity'])
        args.add_debug_info(1, "plugin_args", plugin_args)

        try:
            # Verify the parameters
            for key in plugin_args.keys():
                if not key in _PH.OPTIONS and not key.startswith('_'):
                    raise AnsibleError(f"Unexpected option '{key}' in plugin arguments")

            # Grab interresting ansible variables
            args.add_keys(task_vars,  ('ansible_verbosity', 'ansible_check_mode'))
            # Grab parameters from the source (either the parameter or the inventory
            if _PH.INSTANCES in plugin_args:
                args.add_keys(plugin_args, _PH.OPTIONS)
                args.from_inventory = False
            else:
                args.add_keys(task_vars, _PH.OPTIONS)
                # Some parameter may still come from parameters (i.e state)
                args.add_keys(plugin_args, ('state',))
            # Process the data
            args.process_args(task_vars)

            args.validate_topology()

            module_args = {'ds389' : args.args}
            args.add_debug_info(1, "module_args", module_args)
            # Call the module on remote host
            module_return = self._execute_module(module_name='ds389.ansible_ds.ds389_module',
                                                 module_args=module_args,
                                                 task_vars=task_vars, tmp=tmp)
        except (AnsibleError, LookupError) as exc:
            module_return = { "failed": True, "msg": str(exc) }
        # Then add some additionnal debug data in the result
        for (key,val) in args.debug_info.items():
            module_return[f'plugin-{key}'] = val
        return module_return
