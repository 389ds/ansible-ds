#!/usr/bin/python3

# --- BEGIN COPYRIGHT BLOCK ---
# Copyright (C) 2022 Red Hat, Inc.
# All rights reserved.
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# --- END COPYRIGHT BLOCK ---
#

DOCUMENTATION = r'''
---
module: dsentities

short_description: This module provides utility classes and function for handling ds389 entities

version_added: "1.0.0"

description:
    - NormalizedDict class:   a dict whose keys are normalized
    - Option class:           class handling ansible-ds parameters for each YAMLObject
    - DSEOption class:        class handling the Option associated with ds389 parameters that are in dse.ldif
    - ConfigOption class:     class handling the Option associated with ds389 parameters that are in dscreate template file
    - SpecialOption class:    class handling special cases like ansible specific parameterss ( like 'state') or the ds389 prefix
    - OptionAction class:     utility class used to perform action on an Option
    - MyYAMLObject class:     the generic class for ds389 entities
    - YAMLRoot class:         the MyYAMLObject class associated with the root entity: (local host)
    - YAMLInstance class:     the MyYAMLObject class associated with a ds389 instance
    - YAMLBackend class:      the MyYAMLObject class associated with a backend
    - YAMLIndex class:        the MyYAMLObject class associated with an index

author:
    - Pierre Rogier (@progier389)

requirements:
    - python >= 3.9
    - python3-lib389 >= 2.2
    - 389-ds-base >= 2.2
'''

import os
import sys
import re
import json
import glob
import ldif
import ldap
import yaml
import socket
import random
from shutil import copyfile
from tempfile import TemporaryDirectory
from ldap.ldapobject import SimpleLDAPObject
from lib389 import DirSrv
from lib389.dseldif import DSEldif
from lib389.backend import Backend
from lib389.instance.setup import SetupDs
from lib389.utils import ensure_str, ensure_bytes, ensure_list_str, ensure_list_bytes, normalizeDN, escapeDNFiltValue

from configparser import ConfigParser
from .dsutil import NormalizedDict, DSE, DiffResult, getLogger

ROOT_ENTITY = "ds"
INDEX_ATTRS = ( 'nsIndexType', 'nsMatchingRule' )

log = None

def isTrue(val):
    return val is True or val.lower() in ("true", "started")


# class handling ansible-ds parameters for each YAML Object
class Option:
    def __init__(self, name, desc):
        self.name = name
        self.desc = desc
        self.prio = 10
        self.rdonly = False

    def __repr__(self):
        repr = f"Option({self.name}"
        for var in self.__dict__:
            if var in ( "action", ):
                continue
            if not var.startswith("_"):
                repr = repr + f", {var}={self.__dict__[var]}"
        repr = repr + ")"
        return repr

    def _get_action(self, target, facts, vfrom, vto):
        return []

# class handling the Option associated with ds389 parameters that are in dse.ldif
class DSEOption(Option):
    def __init__(self, dsename, dsedn, vdef, desc):
        name = dsename.replace("-", "_").lower()
        Option.__init__(self, name, desc)
        self.dsename = dsename
        self.dsedn = dsedn
        self.vdef = vdef

    def _get_action(self, target, facts, vfrom, vto):
        return ( OptionAction(self, target, facts, vfrom, vto, DSEOption._action), )

    def _action(self=None, action=None, action2perform=None):
        option = action.option
        dsedn = action.target.getPath(option.dsedn)
        if action2perform == OptionAction.DESC:
            return f"Set {option.dsename}:{action.vto} in {dsedn}"
        elif action2perform == OptionAction.DEFAULT:
            vdef = getattr(action.option, 'vdef', None)
            if vdef:
                return vdef
            return action.target.getDefaultDSE().getSingleValue(dsedn, option.dsename)
        elif action2perform == OptionAction.FACT:
            return action.target.getDSE().getSingleValue(dsedn, option.dsename)
        elif action2perform == OptionAction.CONFIG:
            val = action.getValue()
            log.debug(f"Instance: {action.target.name} config['slapd'][{option.name}] = {val} target={action.target}")
            if val is not None:
                action.target._infConfig['slapd'][option.name] = str(val)
        elif action2perform == OptionAction.UPDATE:
            setattr(action.facts, option.name, action.vto)
            if dsedn and not action.option.rdonly:
                action.target.addModifier(dsedn, DiffResult.REPLACEVALUE, option.dsename, action.vto)

# class handling the Option associated with ds389 parameters that are in dscreate template file
class ConfigOption(DSEOption):
    def __init__(self, name, dsename, dsedn, vdef, desc):
        DSEOption.__init__(self, name, dsedn, vdef, desc)
        self.dsename = dsename

# For read-only attributes (or attributes that cannot be changed while server is on line
class ConfigOptionRO(ConfigOption):
    def __init__(self, name, dsename, dsedn, vdef, desc):
        super().__init__(name, dsename, dsedn, vdef, desc)
        self.rdonly = True
# class handling special cases like ansible specific parameterss ( like 'state') or the ds389 prefix
class SpecialOption(Option):
    def __init__(self, name, prio, desc):
        Option.__init__(self, name, desc)
        self.prio = prio
        self.desc = desc

    def _get_action(self, target, facts, vfrom, vto):
        funcName = f"_{self.name}Action"
        func = getattr(target, funcName)
        return ( OptionAction(self, target, facts, vfrom, vto, func), )

# utility class used to perform action on an Option
class OptionAction:
    CONFIG="infFileConfig"   # Store value in ConfigParser Object
    DEFAULT="default"        # Get default value
    DESC="desc"              # Print the update action
    FACT="fact"              # get current value from system
    UPDATE="update"          # Update current state and facts

    TYPES = ( CONFIG, DEFAULT, DESC, FACT, UPDATE)

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

    def perform(self, type):
        log.debug(f"Performing {type} on action: target={self.target.name} option={self.option.name} vto={self.vto}")
        assert type in OptionAction.TYPES
        return self.func(action=self, action2perform=type)

    def __str__(self):
        #return f'OptionAction({self.__dict__})'
        return f'OptionAction(option={self.option.name}, prio={self.option.prio}, dsename={self.option.dsename}, target={self.target.name}, vfrom={self.vfrom}, vto={self.vto})'

# class representong the enties like instance, backends, indexes, ...
class MyYAMLObject(yaml.YAMLObject):
    yaml_loader = yaml.SafeLoader
    PARAMS = {
        'name' :  "Instance name",
        'state' :  "Could be set to 'absent' (to remove the instance) or 'present' (the default value)"
    }
    OPTIONS = (
        # A list of Option ojects
    )
    CHILDREN = (
        # A dict (variableNamner:, objectClassi) of variable that contains a list of MyYAMLObject
    )
    HIDDEN_VARS =  (
        # A list of pattern of variable that should not be dumped in YAML
    )

    def __init__(self, name, parent=None):
        global log
        log = getLogger()
        self.name = name
        self.state = "present"
        for child in self.CHILDREN.keys():
            self.__dict__[child] = {}
        self._children = []
        self._parent = parent
        self.setCtx()

    def set(self, args):
        log.debug(f"MyYAMLObject.set {self} {self.name} <-- {args}")
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
                for name, obj in val.items():
                    newval[name] = self.CHILDREN[key](name, parent=self)
                    newval[name].set(obj)
                self.setOption(key, newval)
                continue
            # And finally handles the rgular options
            self.setOption(key, val)
        # Insure all childrens attributes have a dict value
        for key in self.CHILDREN.keys():
            if not hasattr(self, key):
                self.setOption(key, {})
        # And check that options are valids
        self.validate()

    def todict(self):
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
            log.info(f"todict: {self.name} {key} <-- {val}")
        return res

    def setCtx(self):
        self._infConfig = ConfigParser()
        self._cfgMods = NormalizedDict()
        self._isDeleted = False

    def getPathNames(self):
        pathnames = {}
        ppn = {}
        if getattr(self,'_parent', None):
            ppn = self._parent.getPathNames()
        mpn = {}
        if getattr(self,'MyPathNames', None):
            mpn = self.MyPathNames()
        log.debug(f"{self.getClass()}.getPathNames returned: { { **ppn, **mpn, } }")
        return { **ppn, **mpn, }

    def getClass(self):
        return self.__class__.__name__

    def getPath(self, path, extrapathnames = {}):
        if path is None:
            return path
        dict = { **self.getPathNames(), **extrapathnames }
        if not 'prefix' in dict:
            dict['prefix'] = os.getenv('prefix','')
        try:
            return path.format(**dict)
        except KeyError as e:
            log.debug(f"getPath failed because of {e} instance is: {self}")
            raise e

    def getName(self):
        return self.name

    def parent(self):
        return getattr(self, "_parent", None)

    def getYAMLInstance(self):
        yobject = self
        while yobject is not None and yobject.getClass() != 'YAMLInstance':
            yobject = yobject.parent()
        return yobject

    def getDSE(self):
        yobject = self.getYAMLInstance()
        if yobject:
            return yobject.getDSE()
        return None

    def getDefaultDSE(self):
        yobject = self.getYAMLInstance()
        if yobject:
            return yobject.getDefaultDSE()
        return None

    def is_default_index(self, attrname, entry):
        dse = self.getDSE()
        if entry.hasValue('nssystemindex', 'true') is True:
            return True
        dn = f"cn={attrname},cn=default indexes,cn=config,cn=ldbm database,cn=plugins,cn=config"
        if normalizeDN(dn) in dse.class2dn['nsindex']:
            return entry.hasSameAttributes(dse.dn2entry[dn], INDEX_ATTRS)
        return False

    def __getstate__(self):
        # Lets hide the variable that we do not want to see in YAML dump
        state = self.__dict__.copy()
        for var in self.__dict__:
            if var.startswith('_'):
                state.pop(var, None)
        for var in self.HIDDEN_VARS:
            state.pop(var, None)
        for var in self.CHILDREN.keys():
            list = self.__dict__[var]
            # Meeds to keep YAMLRoot instances even if it is empty
            if len(list) == 0 and not isinstance(self, YAMLRoot):
                state.pop(var, None)
        return state

    def setOption(self, option, val):
        setattr(self, option, val)

    def validate(self):
        ### Check that attributes are valid.
        dict = self.__dict__
        dictCopy = { **dict }
        # Check that mandatory parameters exists and remove them from dictCopy
        for p in self.PARAMS:
            if not p in dict:
                raise yaml.YAMLError(f"Missing Mandatory parameter {p} in {self.__class__.__name__} object {self}")
            del dictCopy[p]
        # Remove internal parameters from dictCopy
        for o in dict.keys():
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
            raise yaml.YAMLError(f"Unexpected  parameters {dictCopy.keys()} in {self.getClass()} object {self}")

    def __repr__(self):
        return f"{self.__class__.__name__}(variables={self.__dict__})"
        return f"{self.__class__.__name__}(name={self.name}, variables={self.__dict__})"

    def getFacts(self):
        ### populate the object (should be implemented in subclasses)
        assert False

    def findFact(self, facts):
        if not facts:
            return facts
        if self.getClass() == facts.getClass() and self.name == facts.name:
            return facts
        for var in facts.CHILDREN.keys():
            list = facts.__dict__[var]
            for c in list.values():
                if self.getClass() == c.getClass() and self.name == c.name:
                    return c
        facts = globals()[self.getClass()](self.name)
        facts.state = "absent"
        return facts

    def getType(self):
        return self.getClass().replace("YAML","")

    def getAllActions(self, facts):
        actions = []
        for option in self.OPTIONS:
            vfrom = getattr(facts, option.name, None)
            vto = getattr(self, option.name, None)
            for action in option._get_action(self, facts, vfrom, vto):
                actions.append(action)
        return sorted(actions, key = lambda x : x.getPrio())

    def addModsToSummary(self, mods, summary):
        for dn, actionDict in mods.items():
            for action in actionDict:
                for attr, vals in actionDict[action].items():
                    if action == DiffResult.ADDENTRY:
                        summary.append((f"Adding entry {dn}",))
                        for val in vals:
                            summary.append((f"Adding value in entry {dn} <-- {attr}={val}",))
                    elif DiffResult.DELETEENTRY in actionDict:
                        summary.append((f"Deleting entry {dn}",))
                        assert len(actionDict) == 1
                    elif action == DiffResult.ADDVALUE:
                        for val in vals:
                            summary.append((f"Adding value in entry {dn} <-- {attr}={val}",))
                    elif action == DiffResult.DELETEVALUE:
                        if vals == [ None ] or vals is None:
                            summary.append((f"Deleting attribute in entry {dn} <-- {attr}",))
                        else:
                            for val in vals:
                                summary.append((f"Deleting value in entry {dn} <-- {attr}={val}",))
                    elif action == DiffResult.REPLACEVALUE:
                        for val in vals:
                            summary.append((f"Replacing value(s) in entry {dn} <-- {attr}={val}",))


    def update(self, facts=None, summary=[], onlycheck=False, args=None):
        if not facts:
            facts = YAMLRoot()
            facts.getFacts()
        facts = self.findFact(facts)

        log.debug(f"Updating instance {self.name}  with facts {facts.name}")

        actions = self.getAllActions(facts)
        for action in actions:
            if self._isDeleted is True:
                return
            if action.vfrom == action.vto:
                continue
            msg = action.perform(OptionAction.DESC)
            if (msg):
                log.info(msg)
            if getattr(args, "no_actions", False):
                continue
            action.perform(OptionAction.UPDATE)
        inst = self.getYAMLInstance()
        if inst and not action.option.rdonly:
            if not onlycheck:
                inst.applyMods(self._cfgMods)
                self.addModsToSummary(self._cfgMods, summary)
            dseMods = getattr(self, "dseMods", None)
            if dseMods:
                self.addModsToSummary(dseMods, summary)
                if inst and not action.option.rdonly:
                    inst.applyMods(dseMods)

        for var in self.CHILDREN.keys():
            list = self.__dict__[var]
            for c in list.values():
                c.update(facts, summary, onlycheck, args)

    def addModifier(self, dn, type, attr, val):
        dict = self._cfgMods
        DiffResult.addModifier(dict, dn, type, attr, val)


class YAMLIndex(MyYAMLObject):
    IDXDN = 'cn={attr},cn=index,cn={bename},cn=ldbm database,cn=plugins,cn=config'
    OPTIONS = (
        ConfigOption('indextype', 'nsIndexType', IDXDN, None, "Determine the index types (pres,eq,sub,matchingRuleOid)" ),
        ConfigOption('systemindex', 'nsSystemIndex', IDXDN, "off", "Tells if the index is a system index" ),
        SpecialOption('state', 2, "Indicate whether the index is (or should be) present or absent" ),
    )

    def __init__(self, name, parent=None):
        super().__init__(name, parent=parent)

    def MyPathNames(self):
        return { 'attr' : self.name }

    def getFacts(self):
        dse = self.getDSE()
        self.state = 'present'

        actions = self.getAllActions(self)
        bename = self.getPath("{bename}")
        for action in actions:
            val = action.perform(OptionAction.FACT)
            vdef = action.perform(OptionAction.DEFAULT)
            log.debug(f"Index {self.name} from Backend {bename} option:{action.option.name} val:{val}")
            if val and val != vdef:
                setattr(self, action.option.name, val)

    def _stateAction(self=None, action=None, action2perform=None):
        option = action.option
        bename = self.getPath("{bename}")
        log.debug(f"YAMLindex._stateAction: dn= {self.getPath(YAMLIndex.IDXDN)}")
        if action2perform == OptionAction.DESC:
            if action.vto == "present":
                return f"Creating index {action.target.name} on backend {bename}"
            else:
                return f"Deleting index {action.target.name} on backend {bename}"
        elif action2perform == OptionAction.DEFAULT:
            return "present"
        elif action2perform == OptionAction.FACT:
            dse = action.target.getDSE()
            if dse.getEntry(self.getPath(YAMLIndex.IDXDN)):
                return 'present'
            else:
                return 'absent'
        elif action2perform == OptionAction.CONFIG:
            pass
        elif action2perform == OptionAction.UPDATE:
            setattr(action.facts, option.name, action.vto)
            inst = action.target.getYAMLInstance()
            baseDN = action.target.getPath('cn=index,cn={bename},cn=ldbm database,cn=plugins,cn=config')
            if action.vto == "present":
                # In fact that is the rdn that Backend.create method needs.
                dn = f'cn={action.target.name}'
                actions = action.target.getAllActions(action.target)
                for a in actions:
                    if getattr(a.option, 'dsedn', None) == YAMLIndex.IDXDN and a.getValue():
                        mods.append( (prop[a.option.dsename], ensure_list_bytes(a.getValue())) )
                idx = Index(inst.getDirSrv())
                log.debug(f"Creating index dn:{dn},{baseDN} properties:{mods}")
                idx.create(dn, mods, baseDN)
            else:
                dn = action.target.getPath(YAMLIndex.IDXDN)
                idx = Index(inst.getDirSrv(), dn=dn)
                idx.delete()


class YAMLBackend(MyYAMLObject):
    CHILDREN = { 'indexes': YAMLIndex }
    BEDN = 'cn={bename},cn=ldbm database,cn=plugins,cn=config'
    OPTIONS = (
        DSEOption('read-only', BEDN, "False", "Desc" ),
        ConfigOption('require_index', 'nsslapd-require-index', BEDN, None, "Desc" ),
        DSEOption('entry-cache-number', BEDN, None, "Desc" ),
        DSEOption('entry-cache-size', BEDN, None, "Desc" ),
        DSEOption('dn-cache-size', BEDN, None, "Desc" ),
        DSEOption('directory', BEDN, None, "Desc" ),
        DSEOption('db-deadlock', BEDN, None, "Desc" ),
        DSEOption('chain-bind-dn', BEDN, None, "Desc" ),
        DSEOption('chain-bind-pw', BEDN, None, "Desc" ),
        DSEOption('chain-urls', BEDN, None, "Desc" ),
        ConfigOptionRO('suffix', 'nsslapd-suffix', BEDN, None, "Desc" ),
        ConfigOption('sample_entries', 'sample_entries', BEDN, None, "Desc" ),
        SpecialOption('state', 2, "Indicate whether the backend is (or should be) present or absent" ),
    )


    def __init__(self, name, parent=None):
        super().__init__(name, parent=parent)

    def MyPathNames(self):
        return { 'bename' : self.name }

    def getFacts(self):
        dse = self.getDSE()
        self.state = 'present'

        actions = self.getAllActions(self)
        for action in actions:
            val = action.perform(OptionAction.FACT)
            vdef = action.perform(OptionAction.DEFAULT)
            log.info(f"Backend {self.name} option:{action.option.name} val:{val}")
            if val and val != vdef:
                setattr(self, action.option.name, val)

        for dn in dse.class2dn['nsindex']:
            m = re.match(f'cn=([^,]*),cn=index,cn={self.name},cn=ldbm database,cn=plugins,cn=config', dn)
            if m:
                entry = dse.dn2entry[dn]
                if self.is_default_index(m.group(1), entry) is False:
                    index = YAMLIndex(m.group(1), parent=self)
                    index._beentrydn = dn
                    self.indexes[index].name = index
                    index.getFacts()

    def _stateAction(self=None, action=None, action2perform=None):
        option = action.option
        if action2perform == OptionAction.DESC:
            if action.vto == "present":
                return f"Creating backend {action.target.name} on suffix {action.target.suffix}"
            else:
                return f"Deleting backend {action.target.name} on suffix {action.target.suffix}"
        elif action2perform == OptionAction.DEFAULT:
            return "present"
        elif action2perform == OptionAction.FACT:
            dse = action.target.getDSE()
            if dse.getEntry(self.getPath(YAMLBackend.BEDN)):
                return 'present'
            else:
                return 'absent'
        elif action2perform == OptionAction.CONFIG:
            pass
        elif action2perform == OptionAction.UPDATE:
            setattr(action.facts, option.name, action.vto)
            inst = action.target.getYAMLInstance()
            if action.vto == "present":
                # In fact that is the rdn that Backend.create method needs.
                dn = f'cn={action.target.name}'
                prop = {}
                actions = action.target.getAllActions(action.target)
                for a in actions:
                    if getattr(a.option, 'dsedn', None) == YAMLBackend.BEDN and a.getValue():
                        prop[a.option.dsename] = ensure_bytes(a.getValue())
                assert 'nsslapd-suffix' in prop
                be = Backend(inst.getDirSrv())
                log.debug(f"Creating backend dn:{dn} properties:{prop}")
                be.create(dn, prop)
            else:
                dn = action.target.getPath(YAMLBackend.BEDN)
                be = Backend(action.target.getYAMLInstance().getDirSrv(), dn=dn)
                be.delete()


class YAMLInstance(MyYAMLObject):
    LDBM_CONFIG_DB = 'cn=config,cn=ldbm database,cn=plugins,cn=config'
    PARAMS = {
        ** MyYAMLObject.PARAMS,
        'started' : "Boolean to tell whether the server should be started or stopped.",
        'dseMods' : "List of change that needs to be applied on dse.ldif after the instance creation",
    }
    CHILDREN = { 'backends' : YAMLBackend }

    DEVWARN = ". Only set this parameter in a development environment"
    DEVNRWARN = f"{DEVWARN} or if using non root installation"
    OPTIONS = (
        ConfigOption('backup_dir', 'nsslapd-bakdir', 'cn=config', None, "Directory containing the backup files" ),
        ConfigOption('bin_dir', 'nsslapd-bin_dir', f'cn=config', None, f"Directory containing ns-slapd binary{DEVWARN}" ),
        ConfigOption('cert_dir', 'nsslapd-certdir', 'cn=config', None, "Directory containing the NSS certificate databases" ),
        ConfigOption('config_dir', None, None, None, "Sets the configuration directory of the instance (containing the dse.ldif file)" ),
        ConfigOption('data_dir', None, None, None, f"Sets the location of Directory Server shared static data{DEVWARN}" ),
        ConfigOption('db_dir', 'nsslapd-directory', LDBM_CONFIG_DB, None, "Sets the database directory of the instance" ),
        ConfigOption('db_home_dir', 'nsslapd-db-home-directory', 'cn=bdb,cn=config,cn=ldbm database,cn=plugins,cn=config', None, "Sets the memory-mapped database files location of the instance" ),
        ConfigOption('db_lib', 'nsslapd-backend-implement', LDBM_CONFIG_DB, None, "Select the database implementation library (bdb or mdb)" ),
        ConfigOption('full_machine_name', 'nsslapd-localhost', 'cn=config', None, 'The fully qualified hostname (FQDN) of this system. When installing this instance with GSSAPI authentication behind a load balancer, set this parameter to the FQDN of the load balancer and, additionally, set "strict_host_checking" to "false"' ),
        ConfigOption('group', 'nsslapd-group', 'cn=config', None, "Sets the group name the ns-slapd process will use after the service started" ),
        ConfigOption('initconfig_dir', None, None, None, f"Sets the directory of the operating system's rc configuration directory{DEVWARN}" ),
        ConfigOption('instance_name', None, None, None, "Sets the name of the instance." ),
        ConfigOption('inst_dir', None, None, None, "Directory containing instance-specific scripts" ),
        ConfigOption('ldapi', 'nsslapd-ldapifilepath', 'cn=config', None, "Sets the location of socket interface of the Directory Server" ),
        ConfigOption('ldif_dir', 'nsslapd-ldifdir', 'cn=config', None, "Directory containing the the instance import and export files" ),
        ConfigOption('lib_dir', None, None, None, f"Sets the location of Directory Server shared libraries{DEVWARN}" ),
        ConfigOption('local_state_dir', None, None, None, f"Sets the location of Directory Server variable data{DEVWARN}" ),
        ConfigOption('lock_dir', 'nsslapd-lockdir', 'cn=config', None, "Directory containing the lock files" ),
        ConfigOption('port', 'nsslapd-port', 'cn=config', None, "Sets the TCP port the instance uses for LDAP connections" ),
        ConfigOption('prefix', None, None, None, "Sets the file system prefix for all other directories. Should be the same as the $PREFIX environment variable when using dsconf/dsctl/dscreate" ),
        ConfigOption('root_dn', 'nsslapd-rootdn', 'cn=config', None, "Sets the Distinquished Name (DN) of the administrator account for this instance. " +
            "It is recommended that you do not change this value from the default 'cn=Directory Manager'" ),
        ConfigOption('root_password', 'nsslapd-rootpw', 'cn=config', None, 'Sets the password of the "cn=Directory Manager" account ("root_dn" parameter). ' +
            'You can either set this parameter to a plain text password dscreate hashes during the installation or to a "{algorithm}hash" string generated by the pwdhash utility. ' +
            'The password must be at least 8 characters long.  Note that setting a plain text password can be a security risk if unprivileged users can read this INF file' ),
        ConfigOption('run_dir', 'nsslapd-rundir', 'cn=config', None, "Directory containing the pid file" ),
        ConfigOption('sbin_dir', None, None, None, f"Sets the location where the Directory Server administration binaries are stored{DEVWARN}" ),
        ConfigOption('schema_dir', 'nsslapd-schemadir', 'cn=config', None, "Directory containing the schema files" ),
        ConfigOption('secure_port', 'nsslapd-secureport', 'cn=config', None, "Sets the TCP port the instance uses for TLS-secured LDAP connections (LDAPS)" ),
        ConfigOption('self_sign_cert', None, None, None, "Sets whether the setup creates a self-signed certificate and enables TLS encryption during the installation. " +
            "The certificate is not suitable for production, but it enables administrators to use TLS right after the installation. " +
            "You can replace the self-signed certificate with a certificate issued by a Certificate Authority. If set to False, " +
            "you can enable TLS later by importing a CA/Certificate and enabling 'dsconf <instance_name> config replace nsslapd-security=on" ),
        ConfigOption('self_sign_cert_valid_months', None, None, None, "Set the number of months the issued self-signed certificate will be valid." ),
        ConfigOption('selinux', None, None, None, "Enables SELinux detection and integration during the installation of this instance. " +
            'If set to "True", dscreate auto-detects whether SELinux is enabled. Set this parameter only to "False" in a development environment ' +
            'or if using a non root installation' ),
        SpecialOption('state', 2, "Indicate whether the instance is (or should be) present or absent" ),
        SpecialOption('started', 99, "Indicate whether the instance is (or should be) started" ),
        ConfigOption('strict_host_checking', None, None, None, 'Sets whether the server verifies the forward and reverse record set in the "full_machine_name" parameter. ' +
            'When installing this instance with GSSAPI authentication behind a load balancer, set this parameter to "false". Container installs imply "false"' ),
        ConfigOption('sysconf_dir', None, None, None, "Desc" ),
        ConfigOption('systemd', None, None, None, f'Enables systemd platform features. If set to "True", dscreate auto-detects whether systemd is installed{DEVNRWARN}'  ),
        ConfigOption('tmp_dir', 'nsslapd-tmpdir', 'cn=config', None, "Sets the temporary directory of the instance" ),
        ConfigOption('user', 'nsslapd-localuser', 'cn=config', None, "Sets the user name the ns-slapd process will use after the service started" ),

        DSEOption('nsslapd-lookthroughlimit', LDBM_CONFIG_DB, '5000', "The maximum number of entries that are looked in search operation before returning LDAP_ADMINLIMIT_EXCEEDED"),
        DSEOption('nsslapd-mode', LDBM_CONFIG_DB, '600', "The database permission (mode) in octal"),
        DSEOption('nsslapd-idlistscanlimit', LDBM_CONFIG_DB, '4000', "The maximum number of entries a given index key may refer before the index is handled as unindexed."),
        DSEOption('nsslapd-directory', LDBM_CONFIG_DB, '{prefix}/var/lib/dirsrv/slapd-{instname}/db', "Default database directory"),
        DSEOption('nsslapd-import-cachesize', LDBM_CONFIG_DB, '16777216', "Size of database cache when doing an import"),
        DSEOption('nsslapd-search-bypass-filter-test', LDBM_CONFIG_DB, 'on', "Allowed values are: 'on', 'off' or 'verify'. " +
            "If you enable the nsslapd-search-bypass-filter-test parameter, Directory Server bypasses filter checks when it builds candidate lists during a search. " +
            "If you set the parameter to verify, Directory Server evaluates the filter against the search candidate entries" ),
        DSEOption('nsslapd-search-use-vlv-index', LDBM_CONFIG_DB, 'on', "enables and disables virtual list view (VLV) searches"),
        DSEOption('nsslapd-exclude-from-export', LDBM_CONFIG_DB, 'entrydn entryid dncomp parentid numSubordinates tombstonenumsubordinates entryusn', "Desc"),
        DSEOption('nsslapd-pagedlookthroughlimit', LDBM_CONFIG_DB, '0', "lookthroughlimit when performing a paged search"),
        DSEOption('nsslapd-pagedidlistscanlimit', LDBM_CONFIG_DB, '0', "idllistscanlimit when performing a paged search"),
        DSEOption('nsslapd-rangelookthroughlimit', LDBM_CONFIG_DB, '5000', "Sets a separate range look-through limit that applies to all users, including Directory Manager"),
        DSEOption('nsslapd-backend-opt-level', LDBM_CONFIG_DB, '1', "This parameter can trigger experimental code to improve write performance"),

    )

    DSE_PATH='{prefix}/etc/dirsrv/slapd-{instname}/dse.ldif'
    GLOBAL_DSE_PATH='{prefix}/etc/dirsrv/dse-ansible-default.ldif'


    def __init__(self, name, parent=None):
        super().__init__(name, parent=parent)
        self.started = True
        self.dseMods = None
        self.state = "absent"
        self._dse = None
        self._DirSrv = None

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
        for dn in result.result:
            if DiffResult.match(dn, ignore_dns, re.IGNORECASE) is False:
                newResult.cloneDN(result.result, dn)

        for option in self.OPTIONS:
            if not isinstance(option, DSEOption):
                continue
            action, val = newResult.getSingleValuedValue(option.dsedn, option.dsename)
            if not action:
                continue
            if (action != DiffResult.DELETEVALUE):
                self.setOption(option.name, val)
            else:
                self.setOption(option.name, None)
            if (action != DiffResult.ADDENTRY):
                newResult.result[option.dsedn][action].pop(option.dsename, None)
        return newResult

    def getDirSrv(self):
        dirSrv = getattr(self, "_DirSrv", None)
        if dirSrv:
            return dirSrv
        dirSrv = DirSrv()
        dirSrv.local_simple_allocate(serverid=self.name)
        dirSrv.setup_ldapi()
        if  dirSrv.exists() and not dirSrv.status():
            dirSrv.start()
        setattr(self, "_DirSrv", dirSrv)
        return dirSrv;

    def getDSE(self):
        dsePath = self.getPath(self.DSE_PATH)
        if not os.access(dsePath, os.R_OK):
            self._dse = None
        elif not self._dse:
            self._dse = DSE(dsePath)
        return self._dse

    def getFacts(self):
        dse = self.getDSE()
        if not dse:
            self.state = 'absent'
            self.started = False
            return

        self.state = 'present'
        inst = self.getDirSrv()
        self.started = inst.status()

        actions = self.getAllActions(self)
        for action in actions:
            val = action.perform(OptionAction.FACT)
            vdef = action.perform(OptionAction.DEFAULT)
            log.debug(f"Instance {self.name} option:{action.option.name} val:{val}")
            if val and val != vdef:
                setattr(self, action.option.name, val)

        if 'nsbackendinstance' in dse.class2dn:
            for dn in dse.class2dn['nsbackendinstance']:
                m = re.match('cn=([^,]*),cn=ldbm database,cn=plugins,cn=config', dn)
                if m:
                    backend = YAMLBackend(m.group(1), parent=self)
                    self.backends[backend.name] = backend
                    backend.getFacts()

        ### Now determine what has changed compared to the default entry
        defaultdse = self.getDefaultDSE()
        result = DiffResult()
        result.diff(dse.getEntryDict(), defaultdse.getEntryDict())
        result = self.filterDiff(result)
        self.setOption('dseMods', result.toYaml())

    def create(self):
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
            if isinstance(action.option, ConfigOption):
                action.perform(OptionAction.CONFIG)
        s = SetupDs(log=log)
        general, slapd, backends = s._validate_ds_config(config)
        s.create_from_args(general, slapd, backends)
        inst = DirSrv()
        inst.local_simple_allocate(serverid=self.name)
        inst.setup_ldapi()
        self._DirSrv = inst
        if not self.started:
            inst.stop()
        return inst

    def delete(self):
        dirsrv = self.getDirSrv()
        dirsrv.stop
        dirsrv.delete()
        self._isDeleted = True

    def get2ports(self):
        # Return 2 free tcp port numbers
        with socket.create_server(('localhost', 0)) as s1:
            host1, port1 = s1.getsockname()
            with socket.create_server(('localhost', 0)) as s2:
                host2, port2 = s2.getsockname()
                return (port1, port2)

    def getDefaultDSE(self):
        defaultDSE = getattr(self, "_defaultDSE", None)
        if defaultDSE:
            return defaultDSE
        ### Check if dse default value exists.
        defaultglobalDSEpath = self.getPath(self.GLOBAL_DSE_PATH)
        if not os.access(defaultglobalDSEpath, os.F_OK):
            ### If it does not exists then create a dummy instance
            dummyInstance = YAMLInstance('ansible-default', YAMLRoot())
            dummyInstance.started = False
            dummyInstance.port, dummyInstance.secure_port = self.get2ports()
            dummyInstance.secure = 'on'
            dummyInstance.self_sign_cert = True
            dummydirSrv = dummyInstance.create()
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
        option = action.option
        if action2perform == OptionAction.DESC:
            if action.vto == "present":
                return f"Creating instance slapd-{action.target.name}"
            else:
                return f"Deleting instance slapd-{action.target.name}"
        elif action2perform == OptionAction.DEFAULT:
            return "present"
        elif action2perform == OptionAction.FACT:
            dsePath = self.getPath(action.target.DSE_PATH)
            if os.access(dsePath, os.R_OK):
                return 'present'
            else:
                return 'absent'
        elif action2perform == OptionAction.CONFIG:
            pass
        elif action2perform == OptionAction.UPDATE:
            setattr(action.facts, option.name, action.vto)
            if action.vto == "present":
                action.target.create()
                action.facts.getFacts()
            else:
                action.target.delete()
                action.facts._parent.instances.remove(action.facts)

    def _startedAction(self=None, action=None, action2perform=None):
        option = action.option
        if action2perform == OptionAction.DESC:
            if isTrue(action.vto):
                return f"Starting instance slapd-{action.target.name}"
            else:
                return f"Stopping instance slapd-{action.target.name}"
        elif action2perform == OptionAction.DEFAULT:
            return True
        elif action2perform == OptionAction.FACT:
            return action.target.getDirSrv().status()
        elif action2perform == OptionAction.CONFIG:
            pass
        elif action2perform == OptionAction.UPDATE:
            setattr(action.facts, option.name, action.vto)
            # Has we need to keep the server started to update
            # the configuration
            # then do nothing here
            # stop the server if needed at the end or the instance update

    def update(self, facts=None, summary=[], onlycheck=False, args=None):
        super().update(facts, summary, onlycheck, args)
        if not isTrue(getattr(self, "started", "True")):
            summary.append((f"Stopping instance {self.getDirSrv().serverid}",))
            self.getDirSrv().stop()


    def applyMods(self, dict):
        dirSrv = self.getDirSrv()
        if not dirSrv.can_autobind():
            dirSrv.setup_ldapi()
        started = dirSrv.status()
        if not started:
            dirSrv.start()
        dirSrv.open()
        for dn, actionDict in dict.items():
            modList = []
            for action in actionDict:
                for attr, vals in actionDict[action].items():
                    if action == DiffResult.ADDENTRY:
                        # try to add the entry
                        assert len(actionDict) == 1
                        log.info(f"YAMLInstance.applyMods: add({dn}, {modList})")
                        try:
                            SimpleLDAPObject.add_s(dirSrv, dn, modList)
                        except ldap.ALREADY_EXISTS:
                            log.info(f"YAMLInstance.applyMods: add returned ldap.ALREADY_EXISTS")
                    elif DiffResult.DELETEENTRY in actionDict:
                        assert len(actionDict) == 1
                        log.info(f"YAMLInstance.applyMods: delete({dn})")
                        SimpleLDAPObject.delete_s(dirSrv, dn)
                    elif action == DiffResult.ADDVALUE:
                        modList.append( (ldap.MOD_ADD, attr, ensure_list_bytes(vals)) )
                    elif action == DiffResult.DELETEVALUE:
                        if vals == [ None ] or vals is None:
                            modList.append( (ldap.MOD_DELETE, attr, None ) )
                        else:
                            modList.append( (ldap.MOD_DELETE, attr, ensure_list_bytes(vals)) )
                    elif action == DiffResult.REPLACEVALUE:
                        if vals == [ None ] or vals is None:
                            modList.append( (ldap.MOD_REPLACE, attr, None) )
                        else:
                            modList.append( (ldap.MOD_REPLACE, attr, ensure_list_bytes(vals)) )

            if len(modList) > 0:
                log.info(f"YAMLInstance.applyMods: modify({dn}, {modList})")
                SimpleLDAPObject.modify_s(dirSrv, dn, modList)
        if not started:
            dirSrv.stop()
        # Config changed so reload the dse.ldif next time we need it
        setattr(self, "_dse", None)


class YAMLRoot(MyYAMLObject):
    OPTIONS = (
        SpecialOption('prefix', 1, "389 Directory Service non standard installation path" ),
    )
    CHILDREN = { 'instances': YAMLInstance }

    def from_path(path):
        ### Decode and validate parameters from yaml or json file. Returns a YAMLRoot object
        if path.endswith('.yaml') or path.endswith('.yml'):
            with open(path, 'r') as f:
                content = yaml.safe_load(f)
        else:
            with open(path, 'r') as f:
                content = json.load(f)
        host = YAMLRoot()
        host.set(content)
        return host

    def from_stdin():
        ### Decode and validate parameters from stdin (interpreted as a json file. Returns a YAMLRoot object
        content = json.load(sys.stdin)
        host = YAMLRoot()
        host.set(content)
        return host

    def from_content(content):
        ### Validate parameters from raw dict object. Returns a YAMLRoot object
        host = YAMLRoot()
        host.set(content)
        return host

    def __init__(self, name=ROOT_ENTITY):
        super().__init__(name)
        self.prefix = self.getPath('{prefix}')

    def MyPathNames(self):
        return { 'hostname' : self.name, 'prefix' : os.environ.get('PREFIX', "") }

    def getFacts(self):
        ### Lookup for all dse.ldif to list the instances
        for f in glob.glob(f'{self.prefix}/etc/dirsrv/slapd-*/dse.ldif'):
            ### Extract the instance name from dse.ldif path
            m = re.match(f'.*/slapd-([^/]*)/dse.ldif$', f)
            ### Then creates the Instance Objects
            instance = YAMLInstance(m.group(1), parent=self)
            self.instances[instance.name] = instance
            ### And populate them
            instance.getFacts()

    def _prefixAction(self=None, action=None, action2perform=None):
        option = action.option
        if action2perform == OptionAction.DESC:
            return f"Set PREFIX environment variable to {action.vto}"
        elif action2perform == OptionAction.DEFAULT:
            return os.environ.get('PREFIX', "")
        elif action2perform == OptionAction.FACT:
            return os.environ.get('PREFIX', "")
        elif action2perform == OptionAction.CONFIG:
            val = action.getValue()
            log.debug(f"Instance: {action.target.name} config['slapd'][{option.name}] = {val} target={action.target}")
            action.target._infConfig['slapd'][option.name] = val
        elif action2perform == OptionAction.UPDATE:
            setattr(action.facts, option.name, action.vto)
            os.environ.set('PREFIX', action.vto)
