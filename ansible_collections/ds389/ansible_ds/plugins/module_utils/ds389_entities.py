#!/usr/bin/python3

# --- BEGIN COPYRIGHT BLOCK ---
# Copyright (C) 2022 Red Hat, Inc.
# All rights reserved.
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# --- END COPYRIGHT BLOCK ---
#

"""This module provides utility classes and function for handling ds389 entities."""

### I found fstring more readable than lazy % formatting even if it is a bit slower:
# pylint: disable=logging-fstring-interpolation
### Ignore some code complexity warning
### Option class gave a lot of parameters and variables (dict would limit the number)
### but would also be less readable.
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-arguments
# pylint: disable=too-many-locals
### Some Option sub classes only overload the constructor
# pylint: disable=too-few-public-methods
### Config have lots of methods
# pylint: disable=too-many-public-methods
### In the ConfigXXXX instances member starting with _ does not means 'protected'
### (children entities code may irefer them) but it means that the value is
### hidden (i.e not exported in result nor in json) ==> disable protected-access
# pylint: disable=protected-access
### Work around what seems a pylint bug (
### Looks like it is searching the member in super class rather than in the class itself)
# pylint: disable=no-member

# ##Should be fixed later on then removed:
# pylint: disable=missing-function-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=invalid-name
# pylint: disable=consider-iterating-dictionary
# pylint: disable=no-self-use




DOCUMENTATION = r'''
---
module: ds389_entities

short_description: This module provides utility classes and function for handling ds389 entities

version_added: "1.0.0"

description:
    - Option class:           class handling ansible-ds parameters for each ConfigObject
    - DSEOption class:        class handling the Option associated with ds389 parameters that are in dse.ldif
    - ConfigOption class:     class handling the Option associated with ds389 parameters that are in ds389_create template file
    - SpecialOption class:    class handling special cases like ansible specific parameterss ( like 'state') or the ds389_prefix
    - OptionAction class:     utility class used to perform action on an Option
    - MyConfigObject class:     the generic class for ds389 entities
    - ConfigRoot class:         the MyConfigObject class associated with the root entity: (local host)
    - ConfigInstance class:     the MyConfigObject class associated with a ds389 instance
    - ConfigBackend class:      the MyConfigObject class associated with a backend
    - ConfigIndex class:        the MyConfigObject class associated with an index

author:
    - Pierre Rogier (@progier389)

requirements:
    - python >= 3.9
    - python3-lib389 >= 2.2
    - 389-ds-base >= 2.2
'''

import os
import io
import sys
import re
import json
import glob
import socket
import random
from shutil import copyfile
from tempfile import TemporaryDirectory
from configparser import ConfigParser
from types import MappingProxyType
import yaml
import ldap
from lib389 import DirSrv
from lib389.agreement import Agreement
from lib389.dseldif import DSEldif
from lib389.backend import Backend
from lib389.index import Index
from lib389.instance.setup import SetupDs
from lib389.utils import normalizeDN, escapeDNFiltValue, get_instance_list
from lib389._constants import ReplicaRole
from lib389.replica import Replicas, Replica, Changelog
from lib389.idm.services import ServiceAccount

from .ds389_util import Key, DSE, DiffResult, dictlist2dict, Entry, LdapOp, get_log

ROOT_ENTITY = socket.gethostname()
INDEX_ATTRS = ( 'nsIndexType', 'nsMatchingRule' )

INSTANCES = 'ds389_server_instances'
AGMTS = 'ds389_agmts'
PREFIX = 'ds389_prefix'

EMPTY_DICT = MappingProxyType({}) # Avoid pylint error about unsafe parameters

def isTrue(val):
    return val is True or val.lower() in ("true", "started")

def _get_new_value(inst, dn, attr):
    # Get value from entity or from dse.ldif file
    v = getattr(inst, 'root_dn', None)
    if v is not None:
        return v
    dse = inst.getDSE()
    return dse.getSingleValue(dn, attr)


def _is_password_ignored(inst, action, dn=None, pw=None):
    # Check if provided password is the same than the instance one.
    # We cannot compare the value because it is hashed so we try to bind.
    if not dn:
        dn = _get_new_value(inst, 'cn=config', 'nsslapd-rootdn')
    if not pw:
        pw = action.vto
    get_log().info(f'Entering _is_password_ignored checking dn {dn} and password {pw} against instance {inst.name}')
    if pw.startswith('{'):
        # Provided value is hashed and different from previous hash value
        # ==> let assume that the password changed.
        get_log().debug(f'Exiting _is_password_ignored returning False because {dn} password seems already hashed')
        return False
    dirsrv = inst.getDirSrv(mode=ConfigInstance.DIRSRV_NOLDAPI)
    if dirsrv is None:
        # We are creating a new instance and we need the password.
        get_log().debug('Exiting _is_password_ignored returning False because instance does not exists.')
        return False
    dirsrv.binddn = dn
    dirsrv.bindpw = pw
    dirsrv.sslport = _get_new_value(inst, 'cn=config', 'nsslapd-secureport')
    dirsrv.port = _get_new_value(inst, 'cn=config', 'nsslapd-port')
    if dirsrv.sslport:
        try:
            get_log().debug(f"Try to bind as {dirsrv.binddn} on instance {dirsrv.serverid} using ldaps.")
            dirsrv.open(uri=f"ldaps://{dirsrv.host}:{dirsrv.sslport}")
            get_log().debug("Success ==> password did not changed.")
            #log.info('Exiting _is_password_ignored returning True because ldaps bind is successful.')
            return True
        except ldap.LDAPError as e:
            get_log().debug(f"Failed ==> error is {e}.")
    try:
        get_log().debug(f"Try to bind as {dirsrv.binddn} on instance {dirsrv.serverid} using ldap with starttls.")
        dirsrv.open(uri=f"ldap://{dirsrv.host}:{dirsrv.port}", starttls=True)
        get_log().debug("Success ==> password did not changed.")
        #log.info('Exiting _is_password_ignored returning True because ldap bind with starttls is successful.')
        return True
    except ldap.LDAPError as e:
        get_log().debug(f"Failed ==> error is {e}.")
    try:
        get_log().debug(f"Try to bind as {dirsrv.binddn} on instance {dirsrv.serverid} using ldap without starttls.")
        dirsrv.open(uri=f"ldap://{dirsrv.host}:{dirsrv.port}", starttls=False)
        get_log().debug("Success ==> password did not changed.")
        #log.info('Exiting _is_password_ignored returning True because ldap bind is successful.')
        return True
    except ldap.LDAPError as e:
        #log.info(f'Exiting _is_password_ignored returning False because lfap bind failed with error {e}')
        get_log().debug(f"Failed ==> error is {e}.")
    return False


def _is_none_ignored(inst, action):
    del inst # Avoid pylint unused argument warning
    return action.vto is None or action.vto == 'None'


# class handling ansible-ds parameters for each Config Object
class Option:
    """An ansible-ds parameter and its relationship with 389ds configuration."""
    def __init__(self, name, desc, prio=10, actionCbName=None, dseName=None, dseDN=None, configName=None,
            configTag=None, choice=None, hidden=False, isIgnoredCb=None, readonly=False, required=False, vdef=None, otype="str"):
        self.name = Key(name)            # Ansible variable name
        self.desc = Option.unfold(desc)  # Human readable description
        self.prio = prio                 # Priority order ( low priority parameters are handled first )
        self.actioncbname = actionCbName # Name of action handler cb in entity object
        self.dsename = Key.from_val(dseName)  # Attribute name in dse.ldif file
        self.dsedn = Key.from_val(dseDN)      # Entry DN in dse.ldif file (may refer to the entity attributes have lower priority)
        self.configname = configName     # Attribute name in dscreate config file (cf ds389_create create-template --advanced)
        self.configtag = configTag       # Attribute section in dscreate config file (cf ds389_create create-template --advanced)
        self.choice = Option.lower(choice) # Allowed values if attribute is a choice
        self.hidden = hidden             # Tell whether attribute value is hidden (i.e not logged)
        self.isignoredcb = isIgnoredCb   # Callback to determine if attribute should be taken in account
        self.readonly = readonly         # True means that attribute change should be done when instance is stopped.
        self.required = required         # True means that attribute is mandatory.
        self.vdef = Option.unfold(vdef)  # Default value.
        self.otype = otype               # Expected python type for the values

    @staticmethod
    def unfold(desc):
        """ This method remove consecutive spaces that are added when folding long lines."""
        if isinstance(desc,str):
            return re.sub("  +", " ", desc)
        return desc

    @staticmethod
    def lower(val):
        """ This method conevert a value to its lower case counterpart."""
        if isinstance(val, str):
            return val.lower()
        if isinstance(val, tuple):
            return (Option.lower(elmt) for elmt in val)
        if isinstance(val, list):
            return [ Option.lower(elmt) for elmt in val ]
        return val

    def __repr__(self):
        myrepr = f"Option({self.name}"
        for key,val in self.__dict__.items():
            if key in ( "action", ):
                continue
            if not key.startswith("_"):
                myrepr = myrepr + f", {key}={val}"
        myrepr = myrepr + ")"
        return myrepr

    def _get_name_weight(self):
        """Define a order between option names."""
        if self.name in ('name', 'state'):
            res = 'A'
        else:
            res = 'B'
        if self.required:
            res += 'C'
        else:
            res += 'D'
        res += self.name
        return res

    def __lt__(self, other):
        """compare options by name."""
        return self._get_name_weight() < other._get_name_weight()

    def _get_action(self, target, facts, vfrom, vto):
        if self.actioncbname:
            func = getattr(target, self.actioncbname)
            return ( OptionAction(self, target, facts, vfrom, vto, func), )
        if self.dsedn:
            return ( OptionAction(self, target, facts, vfrom, vto, Option._action), )
        return []

    def _action(self=None, action=None, action2perform=None):
        option = action.option
        dsedn = action.target.getPath(option.dsedn)
        if action2perform == OptionAction.DESC:
            if option.hidden:
                return f"Set {option.dsename} in {dsedn}"
            return f"Set {option.dsename}:{action.vto} in {dsedn}"
        if action2perform == OptionAction.DEFAULT:
            vdef = getattr(action.option, 'vdef', None)
            if vdef:
                return vdef
            return action.target.getDefaultDSE().getSingleValue(dsedn, option.dsename)
        if action2perform == OptionAction.FACT:
            val = action.target.getDSE().getSingleValue(dsedn, option.dsename)
            get_log().debug(f"_action: OptionAction.FACT  dsedn={dsedn} dsename={option.dsename} val={val} type={type(val)}")
            return val
        if action2perform == OptionAction.CONFIG:
            val = action.getValue()
            get_log().debug(f"Instance: {action.target.name} config['slapd'][{option.name}] = {val} target={action.target}")
            if val is not None:
                name = option.configname
                if name is None:
                    name = option.name
                action.target._infConfig['slapd'][name] = str(val)
            return val
        if action2perform == OptionAction.UPDATE:
            setattr(action.facts, option.name, action.vto)
            if dsedn:
                action.target.addModifier(dsedn, DiffResult.REPLACEVALUE, option.dsename, action.vto)
            return action.vto
        return None


class DSEOption(Option):
    """Class handling the Option associated with ds389 parameters that are in dse.ldif."""

    def __init__(self, dsename, dsedn, vdef, desc, **kwargs):
        if 'name' in kwargs:
            name = kwargs['name']
            kwargs.pop('name')
        else:
            name = dsename.replace("-", "_")
        Option.__init__(self, name, desc, dseName=dsename, dseDN=dsedn, vdef=vdef, **kwargs)

class ConfigOption(DSEOption):
    """Class handling the Option associated with ds389 parameters that are in ds389_create template file."""

    def __init__(self, name, dsename, dsedn, vdef, desc, **kwargs):
        DSEOption.__init__(self, dsename, dsedn, vdef, desc, name=name, **kwargs)
        if not self.configname:
            self.configname = name
        if not self.configtag:
            self.configtag = "slapd"

class SpecialOption(Option):
    """Class handling special cases like ansible specific parameterss ( like 'state') or the ds389_prefix."""

    def __init__(self, name, prio, desc, vdef=None, **kwargs):
        Option.__init__(self, name, desc, prio=prio, actionCbName=f'_{name}Action', vdef=vdef, **kwargs)

class AgmtTgtOption(Option):
    """Class handling the Backends Options used to build replication agreements."""
    def __init__(self, name, desc, **kwargs):
        Option.__init__(self, name, desc, prio=8, **kwargs)

class ReplicaOption(Option):
    """Class handling the Backends Options used to build replicas."""

    DSEDN = 'cn=replica,cn={suffix},cn=mapping tree,cn=config'

    def __init__(self, name, desc, **kwargs):
        dsename = f'nsDS5{name}'
        Option.__init__(self, name, desc, dseName=dsename, **kwargs)

class ChangelogOption(Option):
    """Class handling replica parameters related to the changelog."""
    DSEDN = 'cn=changelog,cn={bename},cn=ldbm database,cn=plugins,cn=config'

    def __init__(self, name, desc, **kwargs):
        dsename = f'nsslapd{name}'
        Option.__init__(self, name, desc, dseName=dsename, dseDN=ChangelogOption.DSEDN, **kwargs)

class AgmtOption(Option):
    """Class handling explicit replication agreement parameters."""
    AGMTDN = "{agmtDN}"

    def __init__(self, name, desc, **kwargs):
        dsename = f'nsDS5{name}'
        Option.__init__(self, name, desc, dseName=dsename, dseDN=AgmtOption.AGMTDN, **kwargs)

class OptionAction:
    """This utility class represents an action to perform on an Option."""
    CONFIG="infFileConfig"   # Store value in ConfigParser Object
    DEFAULT="default"        # Get default value
    DESC="desc"              # Print the update action
    FACT="fact"              # get current value from system
    UPDATE="update"          # Update current state and facts

    # The various actions to perform
    TYPES = ( CONFIG, # Update instance config templates
              DEFAULT, # Compute default value
              DESC, # Describe the action to do
              FACT, # Get value from 389ds config
              UPDATE, #Set value in 389ds config
            )

    """
        Define the action to perform about an option
    """
    def __init__(self, option, target, facts, vfrom, vto, func):
        self.option = option    # The parameter definition
        self.target = target    # The target entity
        self.facts = facts      # Current state
        self.vfrom = vfrom      # Current value
        self.vto = vto          # Value to set
        self.func = func  #  func(self, action=action, action2perform=action2perform)

    def getPrio(self):
        return self.option.prio

    def getValue(self):
        return getattr(self.target, self.option.name, None)

    def perform(self, oatype):
        get_log().debug(f"Performing {oatype} on action: target={self.target.name} option={self.option.name} vto={self.vto}")
        assert oatype in OptionAction.TYPES
        return self.func(action=self, action2perform=oatype)

    def __repr__(self):
        return f'OptionAction(option={self.option.name}, prio={self.option.prio}, dsename={self.option.dsename}, target={self.target.name}, vfrom={self.vfrom}, vto={self.vto})'

# class representong the enties like instance, backends, indexes, ...
class MyConfigObject():
    """Generic class representing a ds389 entity (i.e: instance, backend, index or agmt ) ."""
    PARAMS = {
        'name' :  "Instance name",
    }
    OPTIONS = (
        # A list of Option ojects
    )
    OPTIONS_META = {
        # The options meta data (cf mutually_exclusive, required_together, required_one_of, required_if, required_by in
        # https://docs.ansible.com/ansible/latest/dev_guide/developing_program_flow_modules.html#argument-spec
    }
    CHILDREN = {
        # A dict (variableNamner:, objectClassi) of variable that contains a list of MyConfigObject
    }
    HIDDEN_VARS =  (
        # A list of pattern of variable that should not be dumped in Config
    )

    def __init__(self, name, parent=None):
        self.name = name
        self.state = "present"
        for child in self.CHILDREN.keys():
            self.__dict__[child] = {}
        self._children = []
        self._parent = parent
        self.setCtx()
        self._isDeleted = None

    def set(self, args):
        """Set the wanted options in the instance. args is a string containing json or a dict."""
        get_log().debug(f"MyConfigObject.set {self} {self.name} <-- {args}")
        ### Initialize the object from a raw dict
        if isinstance(args, str):
            args = json.loads(args)
        assert isinstance(args, dict)
        for key, val in args.items():
            if key == 'tag':
                continue
            if key.startswith('_'):
                continue
            if key in self.CHILDREN.keys():
                newval = {}
                # Lets recurse on the children objects
                for name, obj in dictlist2dict(val).items():
                    newval[name] = self.CHILDREN[key](name, parent=self)
                    newval[name].set(obj)
                self.setOption(key, newval)
                continue
            if key in ('state',):
                self.setOption(key, val)
                continue
            if val is None:
                continue
            # And finally handles the rgular options
            self.setOption(key, val)
        # Insure all childrens attributes have a dict value
        for key in self.CHILDREN.keys():
            if not hasattr(self, key):
                self.setOption(key, {})
        # And check that options are valids
        self.validate()

    def add_change(self, change):
        """Add a change in result message."""
        self.parent().add_change(change)

    def todict(self):
        """Convert list of dict to dict of dict whose key is name."""
        res = {}
        for key, val in self.__dict__.items():
            if key.startswith('_'):
                continue
            if key in ('tag', 'name'):
                continue
            if key in self.CHILDREN.keys():
                newval = {}
                # Lets recurse on the children objects
                for name, obj in val.items():
                    newval[name] = obj.todict()
                res[key] = newval
                continue
            # And finally handles the regular options
            res[key] = val
            #log.info(f"todict: {self.name} {key} <-- {val}")
        return res

    def tolist(self):
        """Convert dict of dict whose key is name to list of dict."""
        res = {}
        for key, val in self.__dict__.items():
            if key.startswith('_'):
                continue
            if key in ('tag', 'name'):
                continue
            if key in self.CHILDREN.keys():
                newval = []
                # Lets recurse on the children objects
                for name, obj in val.items():
                    child = obj.tolist()
                    child['name'] = name
                    newval.append(child)
                res[key] = newval
                continue
            # And finally handles the regular options
            res[key] = val
        return res

    def setCtx(self):
        self._infConfig = ConfigParser()
        self._cfgMods = {}
        self._isDeleted = False

    def getPathNames(self):
        ppn = {}
        if getattr(self,'_parent', None):
            ppn = self._parent.getPathNames()
        mpn = {}
        if getattr(self,'MyPathNames', None):
            mpn = self.MyPathNames()
        #get_log().debug(f"{self.getClass()}.getPathNames returned: { { **ppn, **mpn, } }")
        return { **ppn, **mpn, }

    def getClass(self):
        return self.__class__.__name__

    def getPath(self, path, extrapathnames = EMPTY_DICT):
        """Evaluate 'path' by replacing by replacing the variables by their values."""
        # Usually 'path' it either a file path or a DN
        if path is None:
            return path
        pathdict = { **self.getPathNames(), **extrapathnames }
        if not PREFIX in pathdict:
            pathdict[PREFIX] = os.getenv('PREFIX','')
        try:
            return path.format(**pathdict)
        except KeyError as e:
            get_log().error(f"getPath failed because of {e} instance is: {self} failing code is {path}.format(**{pathdict})")
            raise e

    def getName(self):
        return self.name

    def parent(self):
        return getattr(self, "_parent", None)

    def getConfigRoot(self):
        yobject = self
        while yobject.parent():
            yobject = yobject.parent()
        assert isinstance(yobject, ConfigRoot)
        return yobject

    def getConfigInstance(self):
        yobject = self
        while yobject is not None and yobject.getClass() != 'ConfigInstance':
            yobject = yobject.parent()
        return yobject

    def getDSE(self):
        yobject = self.getConfigInstance()
        if yobject:
            return yobject.getDSE()
        return None

    def getDefaultDSE(self):
        yobject = self.getConfigInstance()
        if yobject:
            return yobject.getDefaultDSE()
        return None

    def is_default_index(self, attrname, entry):
        dse = self.getDSE()
        if entry.hasValue('nssystemindex', 'true') is True:
            return True
        dn = f"cn={attrname},cn=default indexes,cn=config,cn=ldbm database,cn=plugins,cn=config"
        dn = Key.from_val(dn)
        if dn in dse.class2dn['nsindex']:
            return entry.hasSameAttributes(dse.dn2entry[dn], INDEX_ATTRS)
        return False

    def __getstate__(self):
        # Lets hide the variable that we do not want to see in Config dump
        state = self.__dict__.copy()
        for var in self.__dict__:
            if var.startswith('_'):
                state.pop(var, None)
        for var in self.HIDDEN_VARS:
            state.pop(var, None)
        for var in self.CHILDREN.keys():
            clist = self.__dict__[var]
            # Needs to keep ConfigRoot instances even if it is empty
            if len(clist) == 0 and not isinstance(self, ConfigRoot):
                state.pop(var, None)
        return state

    def setOption(self, option, val):
        get_log().debug(f'setOption: {type(self)} {self.name} option:{option} val={val} type={type(val)}')
        setattr(self, option, val)

    def validate(self):
        ### Check that attributes are valid.
        mydict = self.__dict__
        dictCopy = { **mydict }
        # Check that mandatory parameters exists and remove them from dictCopy
        for p in self.PARAMS:
            if not p in mydict:
                raise ValueError(f"Missing Mandatory parameter {p} in {self.__class__.__name__} object {self}")
            del dictCopy[p]
        # Remove internal parameters from dictCopy
        for o in mydict.keys():
            if o.startswith('_'):
                del dictCopy[o]
        # Remove expected parameters from dictCopy
        for o in self.OPTIONS:
            if o.name in dictCopy:
                del dictCopy[o.name]
        # Note: children are validated through "set" method recursion so remove them from dictCopy
        for key in self.CHILDREN.keys():
            if key in dictCopy:
                del dictCopy[key]
        # dictCopy should be empty, otherwise there are unexpected parameters
        if len(dictCopy) > 0:
            raise ValueError(f"Unexpected  parameters {dictCopy.keys()} in {self.getClass()} object {self}")

    @staticmethod
    def _get_dict_value(key, val):
        if key in ( '_dse', ):
            return '?????'
        return val

    def __repr__(self):
        tmpdict = { key: MyConfigObject._get_dict_value(key, val) for key,val in self.__dict__.items() }
        parent = tmpdict['_parent']
        tmpdict['_parent'] = f'{type(parent)} {getattr(parent,"name", None)}'
        children = tmpdict['_children']
        tmpdict['_children'] = [ f'{type(child)} {child.name}' for child in children ]
        return f"{self.__class__.__name__}(name={self.name}, variables={tmpdict})"

    def getFacts(self):
        ### populate the object (should be implemented in subclasses)
        raise NotImplementedError("Should not be here because this method is only implented in the subclasses.")

    def findFact(self, facts):
        if not facts:
            return facts
        if self.getClass() == facts.getClass() and self.name == facts.name:
            return facts
        # Handle special case for agmt
        if ConfigDs389Agmt.is_cn(self.name):
            # Handling a ConfigDs389Agmt mapped on a ConfigAgmt entry
            name = ConfigDs389Agmt.target_from_cn(self.name)
            rootfacts = facts.getConfigRoot()
            if name in rootfacts.ds389_agmts:
                facts = rootfacts.ds389_agmts[name]
                get_log().debug(f'find fact for {self.parent().fullname()} agmt={self.name} facts={facts}')
                return facts
        for var in facts.CHILDREN.keys():
            mylist = facts.__dict__[var]
            for child in mylist.values():
                if self.getClass() == child.getClass() and self.name == child.name:
                    return child
        # Create a dummy fact for absent resource and link it to the fact root
        # to avoid getting assertion in fact.getConfigRoot()
        facts = globals()[self.getClass()](self.name, parent=facts.getConfigRoot())
        facts.state = "absent"
        get_log().debug(f'findFact --> {facts}')
        return facts

    def getType(self):
        return self.getClass().replace("Config","")

    def getAllActions(self, facts):
        actions = []
        for option in self.OPTIONS:
            vfrom = str(getattr(facts, option.name, None))
            vto = str(getattr(self, option.name, None))
            for action in option._get_action(self, facts, vfrom, vto):
                actions.append(action)
        return sorted(actions, key = lambda x : x.getPrio())

    def update(self, facts, summary, onlycheck, args=None):
        if not facts:
            facts = ConfigRoot()
            facts.getFacts()
        facts = self.findFact(facts)

        # Determine if the change should be logged in first phase
        # Note: if updating an already existing instance then messages are displayed by applyMods
        inst = self.getConfigInstance()
        display_msg = True
        if inst and not inst._mustCreate:
            display_msg = False
        get_log().debug(f"Updating entity {self.name}  with facts {facts.name}. Entity is {self}. Facts is {facts}.")

        actions = self.getAllActions(facts)
        for action in actions:
            get_log().debug(f"{self.getClass()}.update: action={action}")
            if self._isDeleted is True:
                return
            if action.vfrom == action.vto:
                continue
            func = action.option.isignoredcb
            if func and func(self, action):
                continue
            msg = action.perform(OptionAction.DESC)
            if msg and display_msg:
                get_log().debug(f'SUMMARY += {msg}')
                summary.extend((msg,))
            if getattr(args, "no_actions", False):
                continue
            if onlycheck:
                continue
            action.perform(OptionAction.UPDATE)
        if inst:
            inst.applyMods(self._cfgMods, summary, onlycheck)
            inst.applyMods(getattr(self, "dseMods", None), summary, onlycheck)

        for var in self.CHILDREN.keys():
            for c in self.__dict__[var].values():
                c.update(facts, summary, onlycheck, args)

    def addModifier(self, dn, otype, attr, val):
        DiffResult.addModifier(self._cfgMods, dn, otype, attr, val)

    def get_interresting_properties(self, facts, options_list, dn=None, ignored_options=()):
        """Generate a dict of interresting properties
           result['lall'] is a list of all option.dsename
           result['dset'] is a dict of dsename ->vto for options whose values are set
           result['dchanged'] is a dict of dsename ->vto for options whose values are changed.
        """
        lall = []
        dset = {}
        dchanged={}
        for option in options_list:
            name = option.name
            dsename = str(option.dsename)
            if name in ignored_options:
                continue
            if dsename in (None, 'None'):
                # Option is not mapped in dse.ldif
                continue
            if dn and getattr(option, 'dsedn', None) != dn:
                # Option does not impact the targeted entry
                continue
            vfrom = getattr(facts, option.name, None)
            if not isinstance(vfrom, list):
                vfrom = str(vfrom)
            vto = getattr(self, option.name, None)
            if not isinstance(vto, list):
                vto = str(vto)
            get_log().debug(f'get_interresting_properties: name={name} dsename={dsename} vfrom={vfrom} vto={vto}')
            # all options that are in key group
            lall.append(dsename)
            if vto not in (None, 'None'):
                # value is set
                dset[dsename] = vto
            if vto != vfrom:
                # value is changed
                dchanged[dsename] = vto
        result = { 'lall':lall, 'dset':dset, 'dchanged':dchanged }
        get_log().debug(f'get_interresting_properties: (lall, dset, dchanged) = {result}')
        return result


class ConfigIndex(MyConfigObject):
    """This class handles the 389ds index config entries."""

    IDXDN = 'cn={attr},cn=index,cn={bename},cn=ldbm database,cn=plugins,cn=config'
    OPTIONS = (
        ConfigOption('indextype', 'nsIndexType', IDXDN, None, "Determine the index types (pres,eq,sub,matchingRuleOid)", required=True, otype="list" ),
        ConfigOption('systemindex', 'nsSystemIndex', IDXDN, "off", "Tells if the index is a system index" ),
        SpecialOption('state', 2, "Indicate whether the index is added(present), modified(updated), or removed(absent)", vdef="present", choice= ("present", "updated", "absent")),
    )

    def __init__(self, name, parent=None, beentrydn=None):
        super().__init__(name, parent=parent)
        self._beentrydn = beentrydn

    def MyPathNames(self):
        return { 'attr' : self.name }

    def getFacts(self):
        self.state = 'present'

        actions = self.getAllActions(self)
        bename = self.getPath("{bename}")
        for action in actions:
            val = action.perform(OptionAction.FACT)
            vdef = action.perform(OptionAction.DEFAULT)
            if val and val != vdef:
                get_log().debug(f"Index {self.name} from Backend {bename} option:{action.option.name} val:{val}")
                setattr(self, action.option.name, val)

    def _stateAction(self=None, action=None, action2perform=None):
        option = action.option
        bename = self.getPath("{bename}")
        get_log().debug(f"Configindex._stateAction: dn= {self.getPath(ConfigIndex.IDXDN)}")
        if _is_none_ignored(self, action):
            action.vto = "present"
        if action2perform == OptionAction.DESC:
            if action.vto == "present":
                return f"Creating index {action.target.name} on backend {bename}"
            return f"Deleting index {action.target.name} on backend {bename}"
        if action2perform == OptionAction.DEFAULT:
            return "present"
        if action2perform == OptionAction.FACT:
            dse = action.target.getDSE()
            if dse.getEntry(self.getPath(ConfigIndex.IDXDN)):
                return 'present'
            return 'absent'
        if action2perform == OptionAction.CONFIG:
            return None
        if action2perform == OptionAction.UPDATE:
            setattr(action.facts, option.name, action.vto)
            inst = action.target.getConfigInstance()
            baseDN = action.target.getPath('cn=index,cn={bename},cn=ldbm database,cn=plugins,cn=config')
            if action.vto == "present" and action.vfrom == "absent":
                # In fact that is the rdn that Backend.create method needs.
                dn = f'cn={action.target.name}'
                iadict = action.target.get_interresting_properties(action.facts, self.OPTIONS, dn=ConfigIndex.IDXDN)
                properties = iadict['dset']
                properties['nsSystemIndex'] = 'false'
                idx = Index(inst.getDirSrv())
                get_log().debug(f"Creating index dn:{dn},{baseDN} properties:{properties}")
                idx.create(dn, properties, baseDN)
            elif action.vfrom == "present" and action.vto == "absent":
                dn = action.target.getPath(ConfigIndex.IDXDN)
                idx = Index(inst.getDirSrv(), dn=dn)
                idx.delete()
        return None

class ConfigAgmt(MyConfigObject):
    OPTIONS = (
        SpecialOption('state', 2, "Indicate whether the replication agreement is added(present), modified(updated), or removed(absent)", vdef="present", choice= ("present", "updated", "absent")),

        # AgmtOption('BeginReplicaRefresh', "desc"),   Not an attribut but a action/task
        AgmtOption('ReplicaBindDN', "The DN used to connect to the target instance"),
        #AgmtOption('ReplicaBindDNGroup', "desc"),
        #AgmtOption('ReplicaBindDNGroupCheckInterval', "desc"),
        AgmtOption('ReplicaBindMethod', "The bind Method",  choice= ("SIMPLE", "SSLCLIENTAUTH", "SASL/GSSAPI", "SASL/DIGEST-MD5") ),
        AgmtOption('ReplicaBootstrapBindDN', "The fallback bind dn used after getting authentication error"),
        AgmtOption('ReplicaBootstrapBindMethod', "The fallback bind method", choice= ("SIMPLE", "SSLCLIENTAUTH", "SASL/GSSAPI", "SASL/DIGEST-MD5") ),

        AgmtOption('ReplicaBootstrapCredentials', "The credential associated with the fallback bind"),
        AgmtOption('ReplicaBootstrapTransportInfo', "The encryption method used on the connection after an authentication error.", choice= ("LDAP", "TLS", "SSL" )),
        AgmtOption('ReplicaBusyWaitTime', "The amount of time in seconds a supplier should wait after a consumer sends back a busy response before making another attempt to acquire access", otype="int"),
        AgmtOption('ReplicaCredentials', "The credentials associated with the bind", hidden=True),
        AgmtOption('ReplicaEnabled', "A flags telling wheter the replication agreement is enabled or not.", choice= ("on", "off")),
        AgmtOption('ReplicaFlowControlPause', "the time in milliseconds to pause after reaching the number of entries and updates set in the ReplicaFlowControlWindow parameter is reached.", otype="int"),
        AgmtOption('ReplicaFlowControlWindow', "The maximum number of entries and updates sent by a supplier, which are not acknowledged by the consumer. After reaching the limit, the supplier pauses the replication agreement for the time set in the nsDS5ReplicaFlowControlPause parameter", otype="int"),
        AgmtOption('ReplicaHost', "The target instance hostname"),
        AgmtOption('ReplicaIgnoreMissingChange', "Tells how the replication behaves when a csn is missing.", choice= ("never", "once", "always", "on", "off") ),
        AgmtOption('ReplicaPort', "Target instance port", otype="int"),
        #AgmtOption('ReplicaRoot', "Replicated suffix DN"),   # Same as the parent backend suffix
        AgmtOption('ReplicaSessionPauseTime', "The amount of time in seconds a supplier should wait between update sessions", otype="int"),
        AgmtOption('ReplicaStripAttrs', "Fractionnal replication attributes that does get replicated if the operation modifier list contains only these agreement", otype="list"),
        AgmtOption('ReplicatedAttributeList', "List of replication attribute ithat are not replicated in fractionnal replication", otype="list"),
        AgmtOption('ReplicatedAttributeListTotal', "List of attributes that are not replicated during a total update", otype="list"),
        AgmtOption('ReplicaTimeout', "The number of seconds outbound LDAP operations waits for a response from the remote replica before timing out and failing", otype="int"),
        AgmtOption('ReplicaTransportInfo', "The encryption method used on the connection", choice= ("LDAP", "TLS", "SSL") ),

        AgmtOption('ReplicaUpdateSchedule', "The replication schedule.", otype="list"),
        AgmtOption('ReplicaWaitForAsyncResults', "The time in milliseconds for which a supplier waits if the consumer is not ready before resending data."),
    )

    def __init__(self, name, parent=None, beentrydn=None):
        super().__init__(name, parent=parent)
        self._beentrydn = beentrydn

    def MyPathNames(self):
        agmtDN= f"cn={self.name},{self._parent.getPath(ReplicaOption.DSEDN)}"
        return { 'agmtDN' : agmtDN }

    def getFacts(self):
        actions = self.getAllActions(self)
        bename = self.getPath("{bename}")
        for action in actions:
            val = action.perform(OptionAction.FACT)
            vdef = action.perform(OptionAction.DEFAULT)
            get_log().debug(f"Index {self.name} from Backend {bename} option:{action.option.name} val:{val}")
            if val and val != vdef:
                setattr(self, action.option.name, val)

    def agmt_update(self, action):
        option = action.option
        setattr(action.facts, option.name, action.vto)
        inst = action.target.getConfigInstance()
        baseDN = action.target._parent.getPath(ReplicaOption.DSEDN)
        if action.vto == "present" and action.vfrom == "absent":
            # In fact that is the rdn that Backend.create method needs.
            dn = f'cn={action.target.name}'
            actions = action.target.getAllActions(action.target)
            properties = { 'nsDS5ReplicaRoot': self.parent().suffix }
            # Store ds389 full target name in 'description' attribute
            if hasattr(self, '_fulltargetname'):
                properties['description'] = self._fulltargetname
            for a in actions:
                if getattr(a.option, 'dsedn', None) == AgmtOption.AGMTDN and a.getValue():
                    properties[a.option.dsename] = Key.to_bytes(a.getValue())
            agmt = Agreement(inst.getDirSrv())
            get_log().debug(f"Creating agmt dn:{dn},{baseDN} properties:{properties}")
            agmt.create(dn, properties, baseDN)
        elif action.vfrom == "present" and action.vto == "absent":
            dn = action.target.getPath(AgmtOption.AGMTDN)
            agmt = Agreement(inst.getDirSrv(), dn=dn)
            agmt.delete()

    def _stateAction(self=None, action=None, action2perform=None):
        get_log().debug(f"ConfigAgmt._stateAction: dn= {self.getPath(AgmtOption.AGMTDN)}")
        bename = self.parent().fullname()
        if _is_none_ignored(self, action):
            action.vto = "present"
        if action2perform == OptionAction.DESC:
            if action.vto == "present":
                return f"Creating agreement {action.target.name} on {bename}"
            return f"Deleting agreement {action.target.name} on {bename}"
        if action2perform == OptionAction.DEFAULT:
            return "present"
        if action2perform == OptionAction.FACT:
            dse = action.target.getDSE()
            if dse.getEntry(self.getPath(AgmtOption.AGMTDN)):
                return 'present'
            return 'absent'
        if action2perform == OptionAction.CONFIG:
            return None
        if action2perform == OptionAction.UPDATE:
            self.agmt_update(action)
        return None


class ConfigBackend(MyConfigObject):
    CHILDREN = { 'indexes': ConfigIndex, 'agmts': ConfigAgmt }
    BEDN = 'cn={bename},cn=ldbm database,cn=plugins,cn=config'
    # Replication (type, flags, ReplicaRolem, promoteWeight) per roles
    REPL_ROLES = { None: ( "0", "0", ReplicaRole.STANDALONE, 0 ),
                   Key('None'): ( "0", "0", ReplicaRole.STANDALONE, 0 ),
                   Key("supplier"): ( "3", "1", ReplicaRole.SUPPLIER, 3 ),
                   Key("hub"): ( "2", "1", ReplicaRole.HUB, 2 ),
                   Key("consumer"): ( "2", "0", ReplicaRole.CONSUMER, 1 ) }

    AGMT_OPTIONS = (
        # AGMT_OPTIONS options are accepted but ignored as they are only used in the backends copied within ds389_agmts
        # AgmtTgtOption('BeginReplicaRefresh', "desc"),   Not an attribut but a action/task
        AgmtTgtOption('ReplicaBindMethod', "The bind Method",  choice= ("SIMPLE", "SSLCLIENTAUTH", "SASL/GSSAPI", "SASL/DIGEST-MD5") ),
        AgmtTgtOption('ReplicaBootstrapBindDN', "The fallback bind dn used after getting authentication error"),
        AgmtTgtOption('ReplicaBootstrapBindMethod', "The fallback bind method", choice= ("SIMPLE", "SSLCLIENTAUTH", "SASL/GSSAPI", "SASL/DIGEST-MD5") ),
        AgmtTgtOption('ReplicaBootstrapCredentials', "The credential associated with the fallback bind"),
        AgmtTgtOption('ReplicaBootstrapTransportInfo', "The encryption method used on the connection after an authentication error.", choice= ("LDAP", "TLS", "SSL" )),
        AgmtTgtOption('ReplicaHost', "The target instance hostname"),
        AgmtTgtOption('ReplicaPort', "Target instance port", otype="int"),
        #AgmtTgtOption('ReplicaRoot', "Replicated suffix DN"),   # Same as the parent backend suffix
        AgmtTgtOption('ReplicaTransportInfo', "The encryption method used on the connection", choice= ("LDAP", "TLS", "SSL") ),
    )

    REPLICA_MANAGER_OPTIONS = (
        ReplicaOption('ReplicaCredentials', "The credential associated with the bind",
                      isIgnoredCb=_is_password_ignored, hidden=True, configName="repl_password"),
        ReplicaOption('ReplicaBindDN', "DN of the user allowed to replay updates on this replica"),
    )

    REPLICA_OPTIONS = (
        ReplicaOption('ReplicaBackoffMax', "Maximum delay before retrying to send updates after a recoverable failure", otype="int"),
        ReplicaOption('ReplicaBackoffMin', "Minimum time before retrying to send updates after a recoverable failure", otype="int"),
        ReplicaOption('ReplicaBindDNGroupCheckInterval', "Interval between detection of the bind dn group changes", otype="int"),
        ReplicaOption('ReplicaBindDNGroup', "DN of the group containing users allowed to replay updates on this replica"),
        ReplicaOption('ReplicaId', "The unique ID for suppliers in a given replication environment (between 1 and 65534).", otype="int"),
        ReplicaOption('ReplicaPreciseTombstonePurging', "???"),
        ReplicaOption('ReplicaProtocolTimeout', "Timeout used when stopping replication to abort ongoing operations.", otype="int"),
        ReplicaOption('ReplicaPurgeDelay', "The maximum age of deleted entries (tombstone entries) and entry state information."),
        ReplicaOption('ReplicaReferral', "The user-defined referrals (returned when a write operation is attempted on a hub or a consumer.", otype="list"),
        ReplicaOption('ReplicaReleaseTimeout', "The timeout period (in seconds) after which a master will release a replica.", otype="int"),
        ReplicaOption('ReplicaTombstonePurgeInterval', "The time interval in seconds between purge operation cycles.", otype="int"),
        ReplicaOption('ReplicaUpdateSchedule', "Time schedule presented as XXXX-YYYY 0123456, where XXXX is the starting hour,YYYY is the finishing " +
                                               "hour, and the numbers 0123456 are the days of the week starting with Sunday.",
                                                otype="list"),
        SpecialOption('ReplicaRole', 9, "The replica role.", choice=(None, "supplier", "hub", "consumer")),
        ReplicaOption('ReplicaWaitForAsyncResults', "Delay in milliseconds before resending an update if consumer does not acknowledge it.", otype="int"),
    )


    OTHER_OPTIONS = (
        DSEOption('readonly', BEDN, "False", "Desc" ),
        ConfigOption('require_index', 'nsslapd-require-index', BEDN, None, "Desc", isIgnoredCb=_is_none_ignored),
        DSEOption('entry-cache-number', BEDN, None, "Desc" ),
        DSEOption('entry-cache-size', BEDN, None, "Desc" ),
        DSEOption('dn-cache-size', BEDN, None, "Desc" ),
        DSEOption('directory', BEDN, None, "Desc" ),
        DSEOption('db-deadlock', BEDN, None, "Desc" ),
        DSEOption('chain-bind-dn', BEDN, None, "Desc" ),
        DSEOption('chain-bind-pw', BEDN, None, "Desc" ),
        DSEOption('chain-urls', BEDN, None, "Desc" ),
        ConfigOption('suffix', 'nsslapd-suffix', BEDN, None, "DN subtree root of entries managed by this backend.", required=True, readonly=True, prio=5),
        ConfigOption('sample_entries', 'sample_entries', BEDN, None, "Tells whether sample entries are created on this backend when the instance is created", otype="bool" ),
        SpecialOption('state', 2, "Indicate whether the backend is added(present), modified(updated), or removed(absent)", vdef="present", choice= ("present", "updated", "absent")),
        ChangelogOption('ChangelogEncryptionAlgorithm', "Encryption algorithm used to encrypt the changelog."),
        ChangelogOption('ChangelogMaxAge', "Changelog record lifetime"),
        ChangelogOption('ChangelogMaxEntries', "Max number of changelog records"),
        ChangelogOption('ChangelogSymetricKey', "Encryption key (if changelog is encrypted)"),
        ChangelogOption('ChangelogTrimInterval', "Time (in seconds) between two runs of the changlog trimming. "),
    )

    OPTIONS = OTHER_OPTIONS + AGMT_OPTIONS + REPLICA_OPTIONS + REPLICA_MANAGER_OPTIONS

    def __init__(self, name, parent=None):
        super().__init__(name, parent=parent)

    def MyPathNames(self):
        s = getattr(self, 'suffix', None)
        if s:
            s = escapeDNFiltValue(normalizeDN(s))
        return { 'bename' : self.name, 'suffix' : s }

    def fullname(self):
        return f'backend {self.parent().name}.{self.name} from host {ROOT_ENTITY}'

    def getReplicaFacts(self, replicaDN, entry):
        get_log().debug(f"ConfigBackend.getReplicaFacts: {self.fullname()} replicaDN={replicaDN} entry={entry}")
        for option in self.OPTIONS:
            if isinstance(option, ReplicaOption):
                val = entry.getSingleValue(option.dsename)
                vdef = option.vdef
                if val and val != vdef:
                    get_log().debug(f"Backend {self.name} option:{option.name} val:{val} tye:{type(val)}")
                    setattr(self, option.name, val)
        role = self._getReplicaRole(entry = entry)
        get_log().debug(f"Backend {self.name} option:ReplicaRole val:{role} tye:{type(role)}")
        setattr(self, 'ReplicaRole',  role)

    def getAgmtsFacts(self, dse):
        """This method gets replication agreement facts."""
        hlog = f'ConfigBackend.getAgmtsFacts: {self.fullname()}'
        for dn in dse.class2dn['nsds5replicationagreement']:
            entry = dse.dn2entry[dn]
            get_log().debug(f"{hlog} Handling agmt {entry}")
            # Check whether the suffix matchs current backend.
            suffix = entry.getSingleValue('nsDS5ReplicaRoot')
            if suffix != self.suffix:
                get_log.debug(f'Ignoring replica agreement {dn} which has wrong suffix')
                continue
            # Check that dn is conform to lib389 ones
            m = re.match('cn=([^,]*),cn=replica,cn=.*,cn=mapping tree,cn=config', dn)
            if not m:
                get_log.info(f'Ignoring legacy replica agreement {dn}')
                continue
            name = m.group(1)
            get_log().debug(f"{hlog} Handling agmt {entry} dn={dn} name={name}")
            # Check whether it is a ds389_agmts agreement or a standard one
            fulltargetname = entry.getSingleValue('description')
            if ConfigDs389Agmt.is_cn(name) and fulltargetname:
                # It is a ds389_agmts agreement
                name = ConfigDs389Agmt.target_from_cn(name)
                agmt = ConfigDs389Agmt(name, parent=self)
                agmt.setOption('target', name)
                agmt.getFactsFromEntry(self, entry)
                self.getConfigRoot().ds389_agmts[agmt.name] = agmt
            else:
                agmt = ConfigAgmt(name, parent=self, beentrydn=dn)
                self.agmts[agmt.name] = agmt
                agmt.getFacts()

    def getFacts(self):
        dse = self.getDSE()
        self.state = 'present'

        actions = self.getAllActions(self)
        hlog = f'ConfigBackend.getFacts: {self.fullname()}'
        for action in actions:
            val = action.perform(OptionAction.FACT)
            vdef = action.perform(OptionAction.DEFAULT)
            if val and val != vdef:
                get_log().debug(f"{hlog} option:{action.option.name} val:{val} tye:{type(val)}")
                setattr(self, action.option.name, val)

        # Get replica
        replicaDN=Key.from_val(self.getPath(ReplicaOption.DSEDN))
        get_log().debug(f"{hlog} replicaDN={replicaDN} dsekeys=...")
        if replicaDN in dse.dn2entry:
            self.getReplicaFacts(replicaDN, dse.dn2entry[replicaDN])

        # Get indexes
        for dn in dse.class2dn['nsindex']:
            m = re.match(f'cn=([^,]*),cn=index,cn={self.name},cn=ldbm database,cn=plugins,cn=config', dn)
            if m:
                entry = dse.dn2entry[dn]
                if self.is_default_index(m.group(1), entry) is False:
                    index = ConfigIndex(m.group(1), parent=self, beentrydn=dn)
                    self.indexes[index.name] = index
                    index.getFacts()

        # Get replica agreements
        if 'nsds5replicationagreement' in dse.class2dn:
            self.getAgmtsFacts(dse)

    def _getReplicaRole(self, entry=None):
        if entry:
            rentry = entry
        else:
            dse = self.getDSE()
            if not dse:
                return None
            rentry = dse.getEntry(self.getPath(ReplicaOption.DSEDN))
        if not rentry:
            return None
        flags = rentry.getSingleValue('nsDS5Flags')
        rtype = rentry.getSingleValue('nsDS5ReplicaType')
        for key, val in ConfigBackend.REPL_ROLES.items():
            if (rtype, flags) == val[0:2]:
                return key
        return None

    def _getReplica(self):
        inst = self._parent.getDirSrv()
        replicas = Replicas(inst)
        replica = replicas.get(self.suffix)
        if replica:
            return replica
        return Replica(inst, self.suffix)

    def _getChangelog(self):
        inst = self._parent.getDirSrv()
        return Changelog(inst, suffix=self.suffix)

    def get_options(self, options):
        return tuple(opt for opt in self.OPTIONS if opt.name in options)

    def update_single_ds389agmt(self, agmt, facts, inst, onlycheck):
        """Create/update an agmt defined id ds389_agmts."""
        del inst
        hlog = f'update_agmts: {self.fullname()} agmt:{agmt.name}'
        get_log().debug(f'{hlog} agmt={agmt} self={self}')
        name = ConfigDs389Agmt.cn_from_target(agmt.name)
        adn = f'cn={name},{self.getPath(ReplicaOption.DSEDN)}'
        cfg = ConfigAgmt(name, parent=self, beentrydn=adn)
        # store ConfigDs389Agmt fulltargetname in ConfigAgmt _fulltargetname
        # So that in can be added in 'description' in cfg.agmt_update()
        setattr(cfg, '_fulltargetname', agmt.fulltargetname)
        # Get target agmt properties from AGMT_OPTIONS+REPLICA_MANAGER_OPTIONS
        # Get supplier agmt properties from AGMT_OPTIONS+REPLICA_MANAGER_OPTIONS
        onames = [ option.name.lower() for option in ConfigAgmt.OPTIONS ]
        options = { key:val for key,val in agmt.__dict__.items() if key.lower() in onames }
        cfg.set(options)
        summary = []
        cfg.update(facts, summary, onlycheck)
        for msg in summary:
            self.add_change(msg)

    def update_agmts(self, facts, inst, onlycheck):
        """Create/update all agmts defined in ds389_agmts."""
        root = self.getConfigRoot()
        for agmt in root.ds389_agmts.values():
            if not hasattr(agmt, 'suffix'):
                get_log().debug(f"ds389_agmts should have a 'suffix' option: {agmt}")
                raise AttributeError("ds389_agmts should have a 'suffix' option")
            if not hasattr(agmt, 'fulltargetname'):
                get_log().debug(f"ds389_agmts should have a 'fulltargetname' option: {agmt}")
                raise AttributeError("ds389_agmts should have a 'fulltargetname' option")
            instname = agmt.fulltargetname.split('.')[-2]
            if agmt.suffix == self.suffix and instname.lower() != self.parent().name.lower():
                # Add agmt if suffix is ok and if it does not target itself
                self.update_single_ds389agmt(agmt, facts, inst, onlycheck)

    def update_replman(self, facts, inst, onlycheck):
        """Creates of update Replication manager entry."""
        del facts
        cfginst = self.parent()
        # Get dn
        try:
            adn = self.replicabinddn
        except AttributeError:
            errmsg = f"Option 'ReplicaBindDn' is missing in {cfginst.name}.{self.name} on host {ROOT_ENTITY}"
            get_log().debug(f'update_replman: {errmsg}')
            return
        # Check if we can use that dn
        match = re.fullmatch('cn=([^,]*),(([^,]*,)*cn=config)', adn)
        if not match:
            get_log().debug(f'update_replman: Unable to handle dn {adn}')
            return
        # extract cn and basedn
        acn = match.group(1)
        basedn = match.group(2)
        # Get the password
        try:
            apw = self.replicacredentials
        except AttributeError:
            errmsg = f"Option 'ReplicaCredentials' is missing in {cfginst.name}.{self.name} on host {ROOT_ENTITY}"
            get_log().debug(f'update_replman: {errmsg}')
            get_log().error(f'{errmsg}')
            raise AttributeError(errmsg) from None
        account = ServiceAccount(inst, adn)
        if account.exists():
            if _is_password_ignored(cfginst, None, dn=adn, pw=apw):
                # Password has not changed ==> nothing to do.
                get_log().debug('update_replman: password is not changed.')
                return
            # Password has changed ==> update it.
            self.add_change(f'Updating password on entry {adn}')
            if not onlycheck:
                get_log().debug(f'Updating password on entry {adn}')
                account.reset_password(apw)
            return
        # Entry does not exist ==> Create it.
        self.add_change(f'Adding entry {adn}')
        if not onlycheck:
            get_log().debug(f'create entry {adn}')
            properties = {
                'cn': acn,
                'objectclass': [ 'netscapeServer', 'nsAccount', 'top' ],
                'userpassword': apw,
            }
            account.create(rdn=f'cn={acn}', properties=properties, basedn=basedn)

    def get_repl_role(self, val):
        """Get info about replica role."""
        val = Key.from_val(val)
        if not val:
            return ConfigBackend.REPL_ROLES[val]
        if val not in ConfigBackend.REPL_ROLES:
            raise AttributeError(f"Invalid 'ReplicaRole' value in backend {self._parent.name}.{self.name}")
        return ConfigBackend.REPL_ROLES[val]

    def synchronize_properties(self, dn, dchanged, onlycheck):
        """Write modified properties into the entry."""
        mods = {}
        summary = []
        if dchanged:
            get_log().debug(f'Replica for suffix {self.suffix} properties are modified.')
            self.add_change(f'Replica for suffix {self.suffix} properties are modified.')
        for attr,vals in dchanged.items():
            DiffResult.addModifier(mods, dn, DiffResult.REPLACEVALUE, attr, vals)
        if not onlycheck:
            self.parent().applyMods(mods, summary, False)
        del summary

    def replica_demote_or_delete(self, old_role, new_role, rid_changed, should_delete, onlycheck):
        """This method demotes and/or delete a replica."""
        args = f'rid_changed={rid_changed} should_delete={should_delete} {onlycheck}'
        get_log().debug(f'replica_demote_or_delete: {old_role} ==> {new_role} {args}')
        tf_from = self.get_repl_role(old_role)
        tf_to = self.get_repl_role(new_role)
        if rid_changed:
            demote_role = ReplicaRole.HUB
        elif should_delete:
            demote_role = ReplicaRole.CONSUMER
        else:
            demote_role = tf_to[2]
        if tf_from[3] > 0:
            # There is a replica
            replica = self._getReplica()
            if tf_from[2] != demote_role:
                if not onlycheck:
                    get_log().debug(f'Demote replica for suffix {self.suffix} from {old_role} to {new_role}')
                    replica.demote(demote_role)
                self.add_change(f'Demote replica for suffix {self.suffix} from {old_role} to {new_role}')
            if should_delete:
                if not onlycheck:
                    get_log().debug(f'Delete replica for suffix {self.suffix}')
                    replica.delete()
                self.add_change(f'Delete replica for suffix {self.suffix}')

    def replica_create_or_promote(self, new_role, properties, should_create, onlycheck):
        """This method creates or promotes a replica."""
        # Should create or promote
        inst = self._parent.getDirSrv()
        replicas = Replicas(inst)
        tf_to = self.get_repl_role(new_role)
        get_log().debug(f'replica_create_or_promote(new_role={new_role}, properties={properties}, should_create={should_create}')
        if should_create:
            properties = {
                'cn': 'replica',
                'nsDS5ReplicaRoot': self.suffix,
                'nsDS5Flags': str(tf_to[1]),
                'nsDS5ReplicaType': str(tf_to[0]),
                **properties,
            }
            if not onlycheck:
                get_log().debug(f'replica_create_or_promote: replicas.create(properties={properties})')
                replicas.create(properties=properties)
        else:
            # Promote case
            replica = self._getReplica()
            # Extract needed properties for 'promote'
            promote_args_config = {
                'nsDS5ReplicaId': 'rid',
                'nsDS5ReplicaBindDN': 'binddn',
                'nsDS5ReplicaBindDNGroup': 'binddn_group',
            }
            promote_args = { promote_args_config[key]:val
                for key,val in properties.items() if key in promote_args_config }
            if not onlycheck:
                get_log().debug(f'replica_create_or_promote: replicas.promote({new_role}, {promote_args})')
                replica.promote(tf_to[2], **promote_args)
            self.add_change(f'replica_create_or_promote: replicas.promote({new_role}, {promote_args})')

    def update_replica(self, facts, inst, onlycheck):
        """Update a replica."""
        vfrom = None
        rid = None
        # Get replica facts
        try:
            vto = self.replicarole
        except AttributeError:
            vto = None
        try:
            replica = Replicas(inst).get(self.suffix)
            rtype = replica.get_attr_val_utf8('nsDS5ReplicaType')
            flags = replica.get_attr_val_utf8('nsDS5Flags')
            rid = replica.get_attr_val_int('nsDS5ReplicaID')
            for key, val in ConfigBackend.REPL_ROLES.items():
                if (rtype, flags) == val[0:2]:
                    vfrom = key
            get_log().debug(f'update_replica: suffix={self.suffix} type={rtype} flags={flags} rid={rid} vfrom={vfrom}')
        except ldap.NO_SUCH_OBJECT:
            get_log().debug(f'update_replica: no replica for suffix {self.suffix}')
        setattr(facts, 'replicaid', rid)
        # Lets determine if replica must be demoted and/or promoted.
        tf_from = self.get_repl_role(vfrom)
        tf_to = self.get_repl_role(vto)
        options = self.REPLICA_OPTIONS + self.get_options(('ReplicaBindDN',))
        iadict = self.get_interresting_properties(facts, options)
        dset = iadict['dset']
        dchanged = iadict['dchanged']
        rid_changed = 'nsDS5ReplicaId' in dchanged
        get_log().debug(f'update_replica: dchanged={dchanged} {vfrom} ==> {vto}')
        from_weight = tf_from[3]
        to_weight = tf_to[3]
        if rid_changed or from_weight > to_weight:
            self.replica_demote_or_delete( vfrom, vto, rid_changed, to_weight==0, onlycheck)
        if rid_changed or from_weight < to_weight:
            self.replica_create_or_promote(vto, dset, from_weight==0, onlycheck)
        if from_weight * to_weight != 0:
            # Replica was neither created nor deleted
            # ==> Should update its modified properties
            # Rid is already handled through promote/demote
            dchanged.pop('replicaid', None)
            self.synchronize_properties(ReplicaOption.DSEDN, dchanged, onlycheck)

    def _ReplicaRoleAction(self=None, action=None, action2perform=None):
        get_log().debug(f'_ReplicaRoleAction names={self._parent.name}.{self.name}, \
            {action}={action}, action2perform={action2perform}')
        option = action.option
        if _is_none_ignored(self, action):
            action.vto = None
        if action2perform == OptionAction.DESC:
            # Check for consistency
            newrole = self.get_repl_role(action.vto)
            ridname = 'nsDS5ReplicaId'
            # Get properties that are set
            dset = action.target.get_interresting_properties(action.facts, ConfigBackend.REPLICA_OPTIONS,
                                                           ignored_options =(option.name,))['dset']
            if newrole[2] == ReplicaRole.SUPPLIER:
                if ridname not in dset:
                    raise AttributeError(f"Inconsistency between 'ReplicaRole' and ReplicaId values in backend \
                                           {self._parent.name}.{self.name} (supplier should have a 'Replicaid').")
            elif ridname in dset:
                raise AttributeError(f"Inconsistency between 'ReplicaRole' and ReplicaId values in backend \
                                       {self._parent.name}.{self.name} ({action.vto} should not have a 'Replicaid').")
            if action.vto:
                return f"Configure replication as {action.vto} for backend {action.target.name} on suffix {action.target.suffix}"
            return f"Unconfigure replication for backend {action.target.name} on suffix {action.target.suffix}"
        if action2perform == OptionAction.DEFAULT:
            return None
        if action2perform == OptionAction.FACT:
            return self._getReplicaRole()
        if action2perform == OptionAction.CONFIG:
            return None
        if action2perform == OptionAction.UPDATE:
            setattr(action.facts, option.name, action.vto)
        return None

    def update(self, facts, summary, onlycheck, args=None):
        super().update(facts, summary, onlycheck, args=None)
        if self.name in facts.backends:
            facts = facts.backends[self.name]
        inst = self._parent.getDirSrv()
        self.update_replman(facts, inst, onlycheck)
        self.update_agmts(facts, inst, onlycheck)

    def _stateAction(self=None, action=None, action2perform=None):
        option = action.option
        if _is_none_ignored(self, action):
            action.vto = "present"
        if action2perform == OptionAction.DESC:
            if action.vto == "present":
                return f"Creating backend {action.target.name} on suffix {action.target.suffix}"
            return f"Deleting backend {action.target.name} on suffix {action.target.suffix}"
        if action2perform == OptionAction.DEFAULT:
            return "present"
        if action2perform == OptionAction.FACT:
            dse = action.target.getDSE()
            if dse.getEntry(self.getPath(ConfigBackend.BEDN)):
                return 'present'
            return 'absent'
        if action2perform == OptionAction.CONFIG:
            return None
        if action2perform == OptionAction.UPDATE:
            setattr(action.facts, option.name, action.vto)
            inst = action.target.getConfigInstance()
            if action.vto == "present":
                # In fact that is the rdn that Backend.create method needs.
                dn = f'cn={action.target.name}'
                prop = {}
                actions = action.target.getAllActions(action.target)
                for a in actions:
                    if getattr(a.option, 'dsedn', None) == ConfigBackend.BEDN and a.getValue():
                        prop[a.option.dsename] = Key.to_bytes(a.getValue())
                assert 'nsslapd-suffix' in prop
                be = Backend(inst.getDirSrv())
                get_log().debug(f"Creating backend dn:{dn} properties:{prop}")
                be.create(dn, prop)
            else:
                dn = action.target.getPath(ConfigBackend.BEDN)
                be = Backend(action.target.getConfigInstance().getDirSrv(), dn=dn)
                be.delete()
            action.target.update_replica(action.facts, inst.getDirSrv(), False)
        return None

def _build_options(options):
    odict = { opt.name: Option(opt.name, opt.desc, dseName=opt.dsename) for opt in options }
    return tuple( odict.values() )


class ConfigDs389Agmt(MyConfigObject):
    OPTIONS = _build_options( ConfigBackend.OPTIONS + ConfigAgmt.OPTIONS + (
        Option('target', 'The raw replica agreements target (pattern speficing the backend).'),
        Option('fulltargetname', 'The resolved replica agreements target host.instance.backend.'),
    ))

    AGMT_CN_PREFIX = 'ansible-target: '

    def getFacts(self):
        pass

    @staticmethod
    def is_cn(cn):
        """This methods tells whether the cn is a ds389_agmts one."""
        return cn.lower().startswith(ConfigDs389Agmt.AGMT_CN_PREFIX)

    @staticmethod
    def target_from_cn(cn):
        """This methods compute agmt target from its cn."""
        return cn[16:]

    @staticmethod
    def cn_from_target(target):
        """This methods compute agmt cn from its target."""
        return f'{ConfigDs389Agmt.AGMT_CN_PREFIX}{target}'

    def getFactsFromEntry(self, backend, entry):
        hlog = f"ConfigDs389Agmt.getFactsFromEntry: {backend.fullname()} agmt={self.name}"
        get_log().debug(f"{hlog} entry={entry}")
        # Handle the paramaters that are stored in backend.
        seen = {}
        val = entry.getSingleValue('description')
        if val:
            option = 'fulltargetname'
            get_log().debug("{hlog} option:{option} val:{val}")
            setattr(self, option, val)
        for option in backend.OPTIONS:
            if isinstance(option, AgmtTgtOption) or option in ConfigBackend.REPLICA_MANAGER_OPTIONS:
                dsename = f'nsDS5{option.name}'
                val = entry.getSingleValue(dsename)
                vdef = option.vdef
                seen[dsename.lower()] = True
                if val and val != vdef:
                    get_log().debug(f"{hlog} backend option:{option.name} val:{val}")
                    setattr(backend, option.name, val)
        for option in ConfigAgmt.OPTIONS:
            if option.dsename and option.dsename.lower() not in seen:
                val = entry.getSingleValue(option.dsename)
                vdef = option.vdef
                if val and val != vdef:
                    get_log().debug("{hlog} agmt option:{option.name} val:{val}")
                    setattr(self, option.name, val)


class ConfigInstance(MyConfigObject):
    LDBM_CONFIG_DB = 'cn=config,cn=ldbm database,cn=plugins,cn=config'
    PARAMS = {
        ** MyConfigObject.PARAMS,
        'started' : "Boolean to tell whether the server should be started or stopped.",
        'dseMods' : "List of change that needs to be applied on dse.ldif after the instance creation",
    }
    CHILDREN = { 'backends' : ConfigBackend }
    # getDirSrv parameter
    DIRSRV_NOLDAPI = 1    # Used to check directory manager password
    DIRSRV_LDAPI = 2      # Used for connectionless operation (i.e: start/stop)
    DIRSRV_OPEN = 3       # Used to perform ldap operations
    DIRSRV_MODES = ( DIRSRV_NOLDAPI, DIRSRV_LDAPI, DIRSRV_OPEN )


    DEVWARN = ". Only set this parameter in a development environment"
    DEVNRWARN = f"{DEVWARN} or if using non root installation"
    OPTIONS = (
        ConfigOption('backup_dir', 'nsslapd-bakdir', 'cn=config', None, "Directory containing the backup files" ),
        ConfigOption('bin_dir', 'nsslapd-bin_dir', 'cn=config', None, f"Directory containing ns-slapd binary{DEVWARN}" ),
        ConfigOption('cert_dir', 'nsslapd-certdir', 'cn=config', None, "Directory containing the NSS certificate databases" ),
        ConfigOption('config_dir', None, None, None,
                     "Sets the configuration directory of the instance (containing the dse.ldif file)" ),
        ConfigOption('data_dir', None, None, None, f"Sets the location of Directory Server shared static data{DEVWARN}" ),
        ConfigOption('db_dir', 'nsslapd-directory', LDBM_CONFIG_DB, None, "Sets the database directory of the instance" ),
        ConfigOption('db_home_dir', 'nsslapd-db-home-directory', 'cn=bdb,cn=config,cn=ldbm database,cn=plugins,cn=config',
                      None, "Sets the memory-mapped database files location of the instance" ),
        ConfigOption('db_lib', 'nsslapd-backend-implement', LDBM_CONFIG_DB, None,
                     "Select the database implementation library", choice=("bdb", "mdb")),
        ConfigOption('full_machine_name', 'nsslapd-localhost', 'cn=config', None,
                     'The fully qualified hostname (FQDN) of this system. When installing this instance with GSSAPI ' +
                     'authentication behind a load balancer, set this parameter to the FQDN of the load balancer and, ' +
                     'additionally, set "strict_host_checking" to "false"' ),
        ConfigOption('group', 'nsslapd-group', 'cn=config', None,
                     "Sets the group name the ns-slapd process will use after the service started" ),
        ConfigOption('initconfig_dir', None, None, None,
                     f"Sets the directory of the operating system's rc configuration directory{DEVWARN}" ),
        ConfigOption('instance_name', None, None, None, "Sets the name of the instance." ),
        ConfigOption('inst_dir', None, None, None, "Directory containing instance-specific scripts" ),
        ConfigOption('ldapi', 'nsslapd-ldapifilepath', 'cn=config', None,
                     "Sets the location of socket interface of the Directory Server" ),
        ConfigOption('ldif_dir', 'nsslapd-ldifdir', 'cn=config', None,
                     "Directory containing the the instance import and export files" ),
        ConfigOption('lib_dir', None, None, None, f"Sets the location of Directory Server shared libraries{DEVWARN}" ),
        ConfigOption('local_state_dir', None, None, None, f"Sets the location of Directory Server variable data{DEVWARN}" ),
        ConfigOption('lock_dir', 'nsslapd-lockdir', 'cn=config', None, "Directory containing the lock files" ),
        ConfigOption('port', 'nsslapd-port', 'cn=config', None,
                     "Sets the TCP port the instance uses for LDAP connections", otype="int"),
        ConfigOption('root_dn', 'nsslapd-rootdn', 'cn=config', None,
                     "Sets the Distinquished Name (DN) of the administrator account for this instance. It is recommended " +
                     "that you do not change this value from the default 'cn=Directory Manager'" ),
        ConfigOption('rootpw', 'nsslapd-rootpw', 'cn=config', None, 'Sets the password of the "cn=Directory Manager" account ' +
            '("root_dn" parameter). You can either set this parameter to a plain text password ds389_create hashes during the ' +
            'installation or to a "{algorithm}hash" string generated by the pwdhash utility.  The password must be at least 8 ' +
            'characters long.  Note that setting a plain text password can be a security risk if unprivileged users can read ' +
            'this INF file',
            isIgnoredCb=_is_password_ignored, hidden=True, configName="root_password"),
        ConfigOption('run_dir', 'nsslapd-rundir', 'cn=config', None, "Directory containing the pid file" ),
        ConfigOption('sbin_dir', None, None, None, f"Sets the location where the Directory Server administration binaries are stored{DEVWARN}" ),
        ConfigOption('schema_dir', 'nsslapd-schemadir', 'cn=config', None, "Directory containing the schema files" ),
        ConfigOption('secure_port', 'nsslapd-secureport', 'cn=config', None, "Sets the TCP port the instance uses for TLS-secured LDAP connections (LDAPS)" ,otype="int"),
        ConfigOption('self_sign_cert', None, None, None, "Sets whether the setup creates a self-signed certificate and \
            enables TLS encryption during the installation. The certificate is not suitable for production, but it \
            enables administrators to use TLS right after the installation. You can replace the self-signed certificate \
            with a certificate issued by a Certificate Authority. If set to False, you can enable TLS later by \
            importing a CA/Certificate and enabling 'dsconf <instance_name> config replace nsslapd-security=on" ),
        ConfigOption('self_sign_cert_valid_months', None, None, None, "Set the number of months the issued self-signed certificate will be valid." ),
        ConfigOption('selinux', None, None, None, 'Enables SELinux detection and integration during the installation of this \
            instance. If set to "True", ds389_create auto-detects whether SELinux is enabled. Set this parameter only to \
            "False" in a development environment or if using a non root installation', otype="bool"),
        SpecialOption('started', 99, "Indicate whether the instance is (or should be) started", vdef=True, otype="bool"),
        ConfigOption('strict_host_checking', None, None, None, 'Sets whether the server verifies the forward and reverse record \
            set in the "full_machine_name" parameter. When installing this instance with GSSAPI authentication behind a load \
            balancer, set this parameter to "false". Container installs imply "false"', otype="bool"),
        ConfigOption('sysconf_dir', None, None, None, "sysconf directoryc" ),
        ConfigOption('systemd', None, None, None, f'Enables systemd platform features. If set to "True", ds389_create \
            auto-detects whether systemd is installed{DEVNRWARN}', otype="bool"),
        ConfigOption('tmp_dir', 'nsslapd-tmpdir', 'cn=config', None, "Sets the temporary directory of the instance" ),
        ConfigOption('user', 'nsslapd-localuser', 'cn=config', None,
            "Sets the user name the ns-slapd process will use after the service started" ),
        DSEOption('nsslapd-lookthroughlimit', LDBM_CONFIG_DB, '5000', "The maximum number of entries that are looked in search \
            operation before returning LDAP_ADMINLIMIT_EXCEEDED", otype="int"),
        DSEOption('nsslapd-mode', LDBM_CONFIG_DB, '600', "The database permission (mode) in octal", otype="int"),
        DSEOption('nsslapd-idlistscanlimit', LDBM_CONFIG_DB, '4000', "The maximum number of entries a given index key may refer \
            before the index is handled as unindexed.", otype="int"),
        DSEOption('nsslapd-directory', LDBM_CONFIG_DB, '{ds389_prefix}/var/lib/dirsrv/slapd-{instname}/db',
            "Default database directory", isIgnoredCb=_is_none_ignored),
        DSEOption('nsslapd-import-cachesize', LDBM_CONFIG_DB, '16777216', "Size of database cache when doing an import", otype="int"),
        DSEOption('nsslapd-search-bypass-filter-test', LDBM_CONFIG_DB, 'on', "Allowed values are: 'on', 'off' or 'verify'. \
            If you enable the nsslapd-search-bypass-filter-test parameter, Directory Server bypasses filter checks when \
            it builds candidate lists during a search. If you set the parameter to verify, Directory Server evaluates \
            the filter against the search candidate entries", choice=("on","off","verify")),
        DSEOption('nsslapd-search-use-vlv-index', LDBM_CONFIG_DB, 'on', "enables and disables virtual list view (VLV) searches", choice=("on","off")),
        DSEOption('nsslapd-exclude-from-export', LDBM_CONFIG_DB, 'entrydn entryid dncomp parentid numSubordinates \
            tombstonenumsubordinates entryusn', "list of attributes that are not exported"),
        DSEOption('nsslapd-pagedlookthroughlimit', LDBM_CONFIG_DB, '0', "lookthroughlimit when performing a paged search", otype="int"),
        DSEOption('nsslapd-pagedidlistscanlimit', LDBM_CONFIG_DB, '0', "idllistscanlimit when performing a paged search", otype="int"),
        DSEOption('nsslapd-rangelookthroughlimit', LDBM_CONFIG_DB, '5000', "Sets a separate range look-through limit that applies to all users, including Directory Manager", otype="int"),
        DSEOption('nsslapd-backend-opt-level', LDBM_CONFIG_DB, '1', "This parameter can trigger experimental code to improve write performance", otype="int"),
        SpecialOption('state', 2, "Indicate whether the instance is added(present), modified(updated), or removed(absent)", vdef="present", choice= ("present", "updated", "absent")),
    )

    DSE_PATH='{ds389_prefix}/etc/dirsrv/slapd-{instname}/dse.ldif'
    GLOBAL_DSE_PATH='{ds389_prefix}/etc/dirsrv/dse-ansible-default.ldif'


    def __init__(self, name, parent=None):
        super().__init__(name, parent=parent)
        self.started = True
        self.dseMods = None
        self.state = "absent"
        self._dse = None
        self._DirSrv = { }
        for m in ConfigInstance.DIRSRV_MODES:
            self._DirSrv[m] = None
        self._initial_state = "unknown"
        self._mustCreate = False

    def MyPathNames(self):
        return { 'instname' : self.name }

    def filterDiff(self, result):
        newResult = DiffResult()
        # List DN we are not interrested in
        ignore_dns = []
        for dns in ( ):
            ignore_dns.append(dns)
        for be in self.backends.values():
            bename = be.name
            ignore_dns.append(f'.*cn={bename},cn=ldbm database,cn=plugins,cn=config')
            try:
                suffix = be.suffix
            except KeyError:
                continue
            escapedSuffix = escapeDNFiltValue(normalizeDN(suffix))
            ignore_dns.append(f'.*cn={escapedSuffix}, *cn=mapping tree,cn=config')

        # And build a newresult without those dns
        get_log().debug(f'filterDiff: result.result = {result.result}')
        for dn in result.result:
            get_log().debug(f'filterDiff: dn={dn} ignore_dns={ignore_dns}')
            if DiffResult.match(dn, ignore_dns, re.IGNORECASE) is False:
                newResult.cloneDN(result.result, dn)

        for option in self.OPTIONS:
            if option.dsedn:
                dsedn = self.getPath(option.dsedn)
                action, val = newResult.getSingleValuedValue(dsedn, option.dsename)
                if action:
                    if action != DiffResult.DELETEVALUE:
                        self.setOption(option.name, val)
                    else:
                        self.setOption(option.name, None)
                    if action != DiffResult.ADDENTRY:
                        newResult.result[dsedn][action].pop(option.dsename, None)
        return newResult

    def _getInstanceStatus(self, dirSrv="get it"):
        if not self.exists():
            return "absent"
        if dirSrv == "get it":
            dirSrv = self.getDirSrv(mode = ConfigInstance.DIRSRV_LDAPI)
        if dirSrv is None:
            return "unknown"
        if not dirSrv.exists():
            return "absent"
        if dirSrv.status():
            return "started"
        return "stopped"

    def getDirSrv(self, mode = DIRSRV_OPEN):
        get_log().debug(f'getDirSrv: serverid={self.name}, mode={mode})')
        assert mode in ConfigInstance.DIRSRV_MODES
        dirSrv = None
        if self.exists():
            dirSrv = self._DirSrv[mode]
            if dirSrv:
                return dirSrv
            dirSrv = DirSrv()
            dirSrv.local_simple_allocate(serverid=self.name)
            self._DirSrv[mode] = dirSrv
        status = self._getInstanceStatus(dirSrv)
        get_log().debug(f'getDirSrv: status={status}')
        if self._initial_state == "unknown":
            self._initial_state = status
        if status == "absent":
            return dirSrv
        if mode == ConfigInstance.DIRSRV_NOLDAPI:
            if status == "stopped":
                dirSrv.start(post_open=False)
        elif mode == ConfigInstance.DIRSRV_LDAPI:
            dirSrv.setup_ldapi()
        elif mode == ConfigInstance.DIRSRV_OPEN:
            dirSrv.setup_ldapi()
            if status == "stopped":
                dirSrv.start(post_open=True)
        return dirSrv

    def exists(self):
        dsePath = self.getPath(self.DSE_PATH)
        return os.access(dsePath, os.R_OK)

    def getDSE(self):
        if self.exists():
            self._dse = DSE(self.getPath(self.DSE_PATH))
        else:
            self._dse = None
        return self._dse

    def getFacts(self):
        state = self._getInstanceStatus()
        if state == 'absent':
            return
        get_log().debug(f'ConfigInstance.getFacts(instance: {self.name} state:{state}')
        dse = self.getDSE()
        assert dse

        actions = self.getAllActions(self)
        for action in actions:
            val = action.perform(OptionAction.FACT)
            vdef = action.perform(OptionAction.DEFAULT)
            get_log().debug(f"ConfigInstance.getFacts {self.name} option:{action.option.name} val:{val}")
            if val and (val != vdef or action.option.name == 'state'):
                get_log().debug(f"ConfigInstance.getFacts {self.name} option:{action.option.name} val:{val} type:{type(val)}")
                setattr(self, action.option.name, val)

        if 'nsbackendinstance' in dse.class2dn:
            for dn in dse.class2dn['nsbackendinstance']:
                m = re.match('cn=([^,]*),cn=ldbm database,cn=plugins,cn=config', dn)
                if m:
                    backend = ConfigBackend(m.group(1), parent=self)
                    self.backends[backend.name] = backend
                    backend.getFacts()

        ### Now determine what has changed compared to the default entry
        defaultdse = self.getDefaultDSE()
        result = DiffResult()
        result.diff(dse.getEntryDict(), defaultdse.getEntryDict())
        result = self.filterDiff(result)
        self.setOption('dseMods', result.toYaml())

    def create(self):
        get_log().debug(f"ConfigInstance.create {self.name}")
        config = self._infConfig
        config['general'] = { 'version' : 2, 'start' : 'True' }
        config['slapd'] = { 'instance_name' : self.name }
        if not config.has_option('slapd', 'root_password'):
            # Do not use the default password but generates a random one
            # Anyway we do not need it any more as we use ldapi
            chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.!"
            randomPassword = "".join( random.choices(chars, k=25) )
            config.set('slapd', 'root_password', randomPassword)
            randomPassword=None

        actions = self.getAllActions(self)
        for action in actions:
            if action.option.configtag:
                action.perform(OptionAction.CONFIG)
        s = SetupDs(log=get_log())
        general, slapd, backends = s._validate_ds_config(config)
        s.create_from_args(general, slapd, backends)

    def delete(self):
        dirsrv = self.getDirSrv(mode=ConfigInstance.DIRSRV_LDAPI)
        dirsrv.stop()
        dirsrv.delete()
        self._isDeleted = True

    def get2ports(self):
        # Return 2 free tcp port numbers
        with socket.create_server(('localhost', 0)) as s1:
            port1 = s1.getsockname()[1]
            with socket.create_server(('localhost', 0)) as s2:
                port2 = s2.getsockname()[1]
                return (port1, port2)

    def getDefaultDSE(self):
        defaultDSE = getattr(self, "_defaultDSE", None)
        if defaultDSE:
            return defaultDSE
        ### Check if dse default value exists.
        defaultglobalDSEpath = self.getPath(self.GLOBAL_DSE_PATH)
        if not os.access(defaultglobalDSEpath, os.F_OK):
            ### If it does not exists then create a dummy instance
            dummyInstance = ConfigInstance('ansible-default', ConfigRoot())
            setattr(dummyInstance, 'started', False)
            port,sport = self.get2ports()
            setattr(dummyInstance, 'port', port)
            setattr(dummyInstance, 'secure_port', sport)
            setattr(dummyInstance, 'secure', 'on')
            setattr(dummyInstance, 'self_sign_cert', True)
            dummyInstance.create()
            dummydirSrv =  dummyInstance.getDirSrv(mode=ConfigInstance.DIRSRV_LDAPI)
            dsePath = dummyInstance.getPath(self.DSE_PATH)

            ### Preserve the dumy instance dse.ldif
            tmpPath = f'{defaultglobalDSEpath}.tmp'
            copyfile(dsePath, tmpPath)
            os.rename(tmpPath, defaultglobalDSEpath)
            ### Now we can remove the dummy instance
            dummydirSrv.delete()
        # Now generate the dse with the right instance name
        with TemporaryDirectory() as tmp:
            dse = DSEldif(None, path=defaultglobalDSEpath)
            defaultDSEPath = f'{tmp}/dse-{self.name}.ldif'
            dse.path = defaultDSEPath
            dse.globalSubstitute('ansible-default', self.name)
            defaultDSE = DSE(defaultDSEPath)
            setattr(self, "_defaultDSE", defaultDSE)
            return defaultDSE

    def _stateAction(self=None, action=None, action2perform=None):
        get_log().debug(f'ConfigInstance._stateAction inst={self.name} action2perform={action2perform} action={action}')
        option = action.option
        if _is_none_ignored(self, action):
            action.vto = "present"
        if action2perform == OptionAction.DESC:
            if self._mustCreate:
                return f"Creating instance slapd-{action.target.name}"
            return None
        if action2perform == OptionAction.DEFAULT:
            return "present"
        if action2perform == OptionAction.FACT:
            if self.exists():
                return 'present'
            return 'absent'
        if action2perform == OptionAction.CONFIG:
            return None
        if action2perform == OptionAction.UPDATE:
            setattr(action.facts, option.name, action.vto)
            if self._mustCreate:
                action.target.create()
                # Reset DirSrv cache
                for key in self._DirSrv.keys():
                    self._DirSrv[key] = None
                action.facts.getFacts()
        return None

    def _startedAction(self=None, action=None, action2perform=None):
        option = action.option
        if action2perform == OptionAction.DESC:
            if isTrue(action.vto):
                if self._initial_state != "started":
                    return f"Starting instance slapd-{action.target.name}"
                return None
            if self._initial_state != "stopped":
                return f"Stopping instance slapd-{action.target.name}"
        if action2perform == OptionAction.DEFAULT:
            return True
        if action2perform == OptionAction.FACT:
            return action.target.getDirSrv(mode=ConfigInstance.DIRSRV_LDAPI).status()
        if action2perform == OptionAction.CONFIG:
            return None
        if action2perform == OptionAction.UPDATE:
            setattr(action.facts, option.name, action.vto)
            # Has we need to keep the server started to update
            # the configuration
            # then do nothing here
            # stop the server if needed at the end or the instance update
        return None

    def update(self, facts, summary, onlycheck, args=None):
        curstate = self._getInstanceStatus()
        if self.state == "absent":
            if curstate != "absent":
				# Lets delete the instance
                summary.extend((f'Removing instance {self.name}',))
                if onlycheck:
                    return None
                inst = self.getDirSrv(mode=ConfigInstance.DIRSRV_LDAPI)
                inst.delete()
                if facts:
                    getattr(facts, INSTANCES).pop(self.name, None)
            return None
        if isTrue(self.started):
            wantedstate = "started"
        else:
            wantedstate = "stopped"
        if curstate == "absent":
            self._mustCreate = True

        # Lets create the instance (if needed) then update the config
        super().update(facts, summary, onlycheck, args)
        # Lets insure that started state is the wanted one.
        if wantedstate == "started":
            self.getDirSrv(mode=ConfigInstance.DIRSRV_LDAPI).start()
        else:
            self.getDirSrv(mode=ConfigInstance.DIRSRV_LDAPI).stop()
        return None

    def isAttrUpToDate(self, entry, attr, vals):
        if not entry:
            return True
        e = Entry(entry.getDN(), { attr: vals})
        return entry.hasSameAttributes(e, (attr,))

    def _filter_ops_add_entry_cb(self, ops, dn, entry, ldapop, overwrite):
        """This methods handles filterOps in DiffResult.ADDENTRY case."""
        if entry:
            # Replace existing attributes if they are not already set with the right value
            for attr, vals in ldapop.items():
                if not self.isAttrUpToDate(entry, attr, vals):
                    op = LdapOp(LdapOp.REPLACE, dn)
                    op.add_values(attr, vals)
                    ops.append((op,))
                    entry.attrs.pop(attr, None)
            if overwrite:
                # Lets remove the attributes that are not expected.
                for attr in entry.attrs.keys():
                    op = LdapOp(LdapOp.DEL_VALUES,dn)
                    op.add_values(attr, None)
                    ops.append((op,))
        else:
            # Add the entry
            op = LdapOp(LdapOp.ADD_ENTRY, dn)
            for attr, vals in ldapop.items():
                op.add_values(attr, vals)
            ops.append((op,))

    def _filter_ops_delete_entry_cb(self, ops, dn, entry, ldapop, overwrite):
        """This methods handles filterOps in DiffResult.DELETEENTRY case."""
        del ldapop
        del overwrite
        if entry:
            op = LdapOp(LdapOp.DEL_ENTRY, dn)
            ops.append((op,))

    def _filter_ops_add_value_cb(self, ops, dn, entry, ldapop, overwrite):
        """This methods handles filterOps in DiffResult.ADDVALUE case."""
        del overwrite
        if entry:
            for attr, vals in ldapop.items():
                v = []
                for val in vals:
                    if not entry.hasValue(attr, val):
                        v.append((val,))
                if len(v) > 0:
                    op = LdapOp(LdapOp.ADD_VALUE, dn)
                    op.add_values(attr, v)
                    ops.append((op,))

    def _filter_ops_delete_value_cb(self, ops, dn, entry, ldapop, overwrite):
        """This methods handles filterOps in DiffResult.DELETEVALUE case."""
        del overwrite
        if entry:
            for attr, vals in ldapop.items():
                v = []
                for val in vals:
                    if entry.hasValue(attr, val):
                        v.append((val,))
                if len(v) > 0:
                    op = LdapOp(LdapOp.DEL_VALUE, dn)
                    op.add_values(attr, v)
                    ops.append((op,))

    def _filter_ops_replace_value_cb(self, ops, dn, entry, ldapop, overwrite):
        """This methods handles filterOps in DiffResult.REPLACEVALUE case."""
        del overwrite
        if entry:
            for attr, vals in ldapop.items():
                if not self.isAttrUpToDate(entry, attr, vals):
                    op = LdapOp(LdapOp.REPLACE, dn)
                    op.add_values(attr, vals)
                    ops.append((op,))

    def filterOps(self, dirSrv, mods, overwrite):
        ops=[]
        get_log().debug(f'ConfigInstance.filterOps mods={type(mods)}: {mods}')
        cbdesc = {
            DiffResult.ADDENTRY: self._filter_ops_add_entry_cb,
            DiffResult.DELETEENTRY: self._filter_ops_delete_entry_cb,
            DiffResult.ADDVALUE: self._filter_ops_add_value_cb,
            DiffResult.DELETEVALUE: self._filter_ops_delete_value_cb,
            DiffResult.REPLACEVALUE: self._filter_ops_replace_value_cb,
        }

        for dn, ldapops in mods.items():
            entry = Entry.fromDS(dirSrv, dn)
            for action, ldapop in ldapops.items():
                if action in cbdesc:
                    cbdesc[action](ops, dn, entry, ldapop, overwrite)
        return ops

    def applyMods(self, mods, summary, onlycheck):
        if not mods:
            return
        dirSrv = self.getDirSrv()
        dirSrv.close()
        dirSrv.open()
        modsPerformed = []
        if self._getInstanceStatus(dirSrv) != "absent":
            ops = self.filterOps(dirSrv, mods, (self.state=="overwrite"))
            if not onlycheck:
                try:
                    LdapOp.apply_list_op(ops, dirSrv)
                except ldap.UNWILLING_TO_PERFORM:
                    self.applyOpsOffLine(dirSrv, mods, modsPerformed, onlycheck)
                if self.started is False:
                    dirSrv.stop()
                else:
                    dirSrv.start()
            for op in ops:
                summary.extend((str(op),))

    def applyOpsOffLine(self, dirSrv, odict, modsPerformed, onlycheck):
        del odict # For pylint
        del modsPerformed # For pylint
        del onlycheck # For pylint
        dirSrv.stop()
        raise NotImplementedError("Code not yet implemented.")

class ConfigRoot(MyConfigObject):
    OPTIONS = (
        SpecialOption(PREFIX, 1, "389 Directory Service non standard installation path" ),
        SpecialOption('state', 2, "If 'state' is 'absent' then all instances are removed", vdef="present", choice= ("present", "updated", "absent")),

    )
    CHILDREN = { INSTANCES: ConfigInstance, AGMTS: ConfigDs389Agmt }

    @staticmethod
    def from_path(path):
        ### Decode and validate parameters from yaml or json file. Returns a ConfigRoot object
        get_log().info(f'Decoding parameters from file {path}')
        if path.endswith('.yaml') or path.endswith('.yml'):
            with open(path, 'r', encoding='utf-8') as f:
                content = yaml.safe_load(f)
        else:
            with open(path, 'r', encoding='utf-8') as f:
                content = json.load(f)
        host = ConfigRoot()
        host.set(content)
        return host


    @staticmethod
    def from_stdin():
        data = sys.stdin.read()
        get_log().info(f'Decoding parameters from STDIN: {data}')
        ### Decode and validate parameters from stdin (interpreted as a json file. Returns a ConfigRoot object
        content = json.load(io.StringIO(data))
        host = ConfigRoot()
        host.set(content)
        return host


    @staticmethod
    def from_content(content):
        ### Validate parameters from raw dict object. Returns a ConfigRoot object
        get_log().debug(f'Decoding parameters from content {content}')
        host = ConfigRoot()
        host.set(content)
        return host


    @staticmethod
    def strip_instance_name(inst):
        if inst.startswith('slapd-'):
            return inst[6:]
        return inst


    def __init__(self, name=ROOT_ENTITY):
        super().__init__(name)
        self.ds389_prefix = self.getPath('{ds389_prefix}')
        self._changes = []

    def update(self, facts, summary, onlycheck, args=None):
        super().update(facts, summary, onlycheck, args)
        for change in self._changes:
            summary.append(change)

    def add_change(self, change):
        get_log().debug(f'ConfigRoot.add_change({change})')
        self._changes.append(change)

    def MyPathNames(self):
        return { 'hostname' : self.name, PREFIX : os.environ.get('PREFIX', "") }

    def getFacts(self):
        ### Lookup for all dse.ldif to list the instances
        for f in glob.glob(f'{self.ds389_prefix}/etc/dirsrv/slapd-*/dse.ldif'):
            ### Extract the instance name from dse.ldif path
            m = re.match('.*/slapd-([^/]*)/dse.ldif$', f)
            ### Then creates the Instance Objects
            instance = ConfigInstance(m.group(1), parent=self)
            self.ds389_server_instances[instance.name] = instance
            ### And populate them
            instance.getFacts()

    def _ds389_prefixAction(self=None, action=None, action2perform=None):
        option = action.option
        if action2perform == OptionAction.DESC:
            return f"Set PREFIX environment variable to {action.vto}"
        if action2perform == OptionAction.DEFAULT:
            return os.environ.get('PREFIX', "")
        if action2perform == OptionAction.FACT:
            return os.environ.get('PREFIX', "")
        if action2perform == OptionAction.CONFIG:
            val = action.getValue()
            get_log().debug(f"Instance: {action.target.name} config['slapd'][{option.name}] = {val} target={action.target}")
            action.target._infConfig['slapd'][option.name] = val
            return None
        if action2perform == OptionAction.UPDATE:
            setattr(action.facts, option.name, action.vto)
            os.environ.set('PREFIX', action.vto)
        return None

    def _get_instances_list(self, action):
        """This methods computes existing instances, instances to add, and instances to remove lists."""
        existing_instances = []

        #Compare existing instances to requested
        existing_instances = [ ConfigRoot.strip_instance_name(x) for x in get_instance_list() ]
        requested_instances = list(self.ds389_server_instances.keys())
        instances_to_add = [ inst for inst in requested_instances if not inst in existing_instances ]
        instances_to_remove = [ inst for inst in existing_instances if not inst in requested_instances ]
        get_log().debug(f'ConfigRoot._get_instances_list: existing_instances={existing_instances} \
                          requested_instances={requested_instances}')
        get_log().debug(f'ConfigRoot._get_instances_list: instances_to_add={instances_to_add} \
                          instances_to_remove={instances_to_remove} action.vto={action.vto}')
        if action.vto == "absent":
            instances_to_remove.extend(existing_instances)
            instances_to_add = []
        elif action.vto in ("stopped","started"):
            instances_to_add = []
            instances_to_remove = []
        elif action.vto != "updated":
            instances_to_remove = []

        get_log().debug(f'ConfigRoot._get_instances_list: instances_to_add={instances_to_add} \
                          instances_to_remove={instances_to_remove} \
                          existing_instances={existing_instances} action.vto={action.vto}')
        return [existing_instances, instances_to_add, instances_to_remove]

    def _stateAction(self=None, action=None, action2perform=None):
        """This is the state special action callback."""
        existing_instances, instances_to_add, instances_to_remove = self._get_instances_list(action)
        if action2perform == OptionAction.DESC:
            msg = []
            for instance in instances_to_add:
                msg.append(f'Creating instance: {instance}')
            for instance in instances_to_remove:
                msg.append(f'Deleting instance: {instance}')
            return str(msg)
        if action2perform == OptionAction.DEFAULT:
            return "present"
        if action2perform == OptionAction.FACT:
            if len(existing_instances)>0:
                return "present"
            return "absent"
        if action2perform == OptionAction.CONFIG:
            return None
        if action2perform == OptionAction.UPDATE:
            option = action.option
            setattr(action.facts, option.name, action.vto)
            for instance in existing_instances:
                dirSrv = DirSrv()
                dirSrv.local_simple_allocate(serverid=instance)
                if action.vto == "stopped":
                    dirSrv.stop()
                elif action.vto == "started":
                    dirSrv.start()
            for instance in instances_to_remove:
                dirSrv = DirSrv()
                dirSrv.local_simple_allocate(serverid=instance)
                dirSrv.delete()
        return None

def toAnsibleResult(obj):
    cb=getattr(obj, "toAnsibleResult", None)
    if cb is not None:
        return cb(obj)
    if isinstance(obj, MyConfigObject):
        get_log().debug(f"toAnsibleResult: obj={obj}")
        return toAnsibleResult( obj.__getstate__() )
    if isinstance(obj, list):
        return [toAnsibleResult(item) for item in obj]
    if isinstance(obj, tuple):
        return tuple(toAnsibleResult(list(object)))
    if isinstance(obj, dict):
        return { toAnsibleResult(key):toAnsibleResult(val) for key,val in obj.items()}
    return obj
