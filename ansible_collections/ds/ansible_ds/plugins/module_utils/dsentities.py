#!/usr/bin/python3

# --- BEGIN COPYRIGHT BLOCK ---
# Copyright (C) 2020 Red Hat, Inc.
# All rights reserved.
#
# License: GPL (version 3 or any later version).
# See LICENSE for details.
# --- END COPYRIGHT BLOCK ---
#

import sys
import os
import re
import json
import glob
import ldif
import ldap
import logging
import yaml
import socket
import random
from shutil import copyfile
from tempfile import TemporaryDirectory
from configparser import ConfigParser
from lib389 import DirSrv
from lib389.index import Index
from lib389.dseldif import DSEldif
from lib389.backend import Backend
from lib389.utils import ensure_str, ensure_bytes, ensure_list_str, ensure_list_bytes, normalizeDN, escapeDNFiltValue
from lib389.instance.setup import SetupDs
from lib389.cli_base import setup_script_logger
from lib389.instance.options import General2Base, Slapd2Base, Backend2Base
from ldap.ldapobject import SimpleLDAPObject
from argparse import Namespace

args = Namespace(a=1, b='c')

CLASSES = (
    'directoryserverfeature',
    'nsaccount',
    'nsbackendinstance',
    'nscontainer',
    'nsencryptionconfig',
    'nsencryptionmodule',
    'nsindex',
    'nsmappingtree',
    'nssaslmapping',
    'nsschemapolicy',
    'nsslapdconfig',
    'nsslapdplugin',
    'nssnmp',
    'pamconfig',
    'rootdnpluginconfig'
)

IGNOREATTRS = ( 'creatorsName', 'modifiersName',
                'createTimestamp', 'modifyTimestamp', 'numSubordinates',
                'nsslapd-plugindescription', 'nsslapd-pluginid',
                'nsslapd-pluginvendor', 'nsslapd-pluginversion',
                'nsstate',
              )


INDEX_ATTRS = ( 'nsIndexType', 'nsMatchingRule' )

log = None

def SetLogger(name, verbose=0):
    global log
    """Reset the python logging system for STDOUT, and attach a new
    console logger with cli expected formatting.

    :param name: Name of the logger
    :type name: str
    :param verbose: Enable verbose format of messages
    :type verbose: bool
    :return: logging.logger
    """
    root = logging.getLogger()
    log = logging.getLogger(name)
    log_handler = logging.StreamHandler(sys.stderr)

    if verbose:
        verbose = logging.DEBUG
    else:
        verbose = logging.INFO
    log.setLevel(verbose)
    log_format = '%(levelname)s: %(message)s'

    log_handler.setFormatter(logging.Formatter(log_format))
    root.addHandler(log_handler)



class NormalizedDict(dict, yaml.YAMLObject):
    ### A dict with normalized key  stored in hash table 
    ### Note: The original version of the key (or the first one
    ### in case of duplicates) is returned when walking the dict
    yaml_tag = u'tag:yaml.org,2002:map'

    def __init__(self, *args):
        self.dict = {}         # The map: original-key --> value
        self.norm2keys = {}    # The map: normalized-key --> original-key

    def __getstate__(self):
        return { ** self.dict }

    def normalize(self, key):
        nkey = None
        if key:
            nkey = ensure_str(key).lower()
            if re.match("^[a-z][a-z0-9-]* *= .*", nkey):
                nkey = normalizeDN(key)
        return nkey

    def get(self, key):
        return self[key]

    def update(self, key, value):
        self[key] = value

    def has_key(self, key):
        nk = self.normalize(key)
        return self.normalize(key) in self.norm2keys

    def keys(self):
        return dict.keys(self.dict)

    def __next__(self):
        return dict.__next__(self.dict)

    def __iter__(self):
        return dict.__iter__(self.dict)

    def items(self):
        return dict.items(self.dict)

    def values(self):
        return dict.values(self.dict)

    def __setitem__(self, key, value):
        nk = self.normalize(key)
        if nk not in self.norm2keys:
            self.norm2keys[nk] = key
        self.dict[self.norm2keys[nk]] = value

    def __repr__(self):
        return str(self.dict)

    def __getitem__(self, key):
        return self.dict[self.norm2keys[self.normalize(key)]]

    def __delitem__(self, key):
        nk = self.normalize(key)
        fk = self.norm2keys[nk]
        del self.norm2keys[nk]
        del self.dict[fk]

    def clear(self):
        self.dict.clear()
        self.norm2keys.clear()

    def copy(self):
        newDict = NormalizedDict()
        newDict.dict = self.dict.copy()
        newDict.norm2keys = self.norm2keys.copy()

    def pop(self, key, *args):
        try:
            val = self[key]
            self.__delitem__(key)
        except KeyError as e: 
            if len(args) == 0:
                raise e
            else:
                val = args[0]
        return val

# Following methods are inherited from dict:
#
#fromkeys()	Returns a dictionary with the specified keys and value
#items()	Returns a list containing a tuple for each key value pair
#keys()	Returns a list containing the dictionary's keys
#popitem()	Removes the last inserted key-value pair
#setdefault()	Returns the value of the specified key. If the key does not exist: insert the key, with the specified value
#values()	Returns a list of all the values in the dictionary
#


class Option:
    def __init__(self, name, desc):
        self.name = name
        self.desc = desc
        self.prio = 10

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
            if val:
                action.target._infConfig['slapd'][option.name] = str(val)
        elif action2perform == OptionAction.UPDATE:
            setattr(action.facts, option.name, action.vto)
            if dsedn:
                action.target.addModifier(option.dsedn, DiffResult.REPLACEVALUE, option.dsename, action.vto)


class ConfigOption(DSEOption):
    def __init__(self, name, dsename, dsedn, vdef, desc):
        DSEOption.__init__(self, name, dsedn, vdef, desc)
        self.dsename = dsename

class SpecialOption(Option):
    def __init__(self, name, prio, desc):
        Option.__init__(self, name, desc)
        self.prio = prio
        self.desc = desc

    def _get_action(self, target, facts, vfrom, vto):
        funcName = f"_{self.name}Action"
        func = getattr(target, funcName)
        return ( OptionAction(self, target, facts, vfrom, vto, func), )


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
        self.option = option
        self.target = target
        self.facts = facts
        self.vfrom = vfrom
        self.vto = vto
        self.func = func  #  func(self, action=action, action2perform=action2perform) 

    def getPrio(self):
        return self.option.prio

    def getValue(self):
        return getattr(self.target, self.option.name, None)

    def perform(self, type):
        log.debug(f"Performing {type} on action: target={self.target.name} option={self.option.name} vto={self.vto}")
        assert type in OptionAction.TYPES
        return self.func(action=self, action2perform=type)


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
        # A list of variable that contains a list of MyYAMLObject 
    )
    HIDDEN_VARS =  (
        # A list of pattern of variable that should not be dumped in YAML
    )

    def __init__(self, name, parent=None):
        self.name = name
        self.state = "present"
        for child in self.CHILDREN:
            self.__dict__[child] = []
        self._children = []
        self._parent = parent
        self.setCtx()

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
        for var in self.CHILDREN:
            list = self.__dict__[var]
            if len(list) == 0:
                state.pop(var, None)
        return state

    def setOption(self, option, val):
        setattr(self, option, val)

    def validate(self):
        dict = self.__dict__
        dictCopy = { **dict }
        # Rebuild the child/parent relationship and validate the children
        self._children = []
        self.setCtx()
        log.debug(f"Validate {self.getClass()}(name={self.name})")
        for c in self.CHILDREN:
            self._children.append(c)
            if not c in dict:
                self.setOption(c, [])
                dict[c] = []
            for c2 in dict[c]:
                log.debug(f"Validate {self.getClass()}(name={self.name}) children is {c2.getClass()}(name={c2.name})")
                c2.validate()
                c2._parent = self
                c2.setCtx()
            if c in dictCopy:
                del dictCopy[c]
        for p in self.PARAMS:
            if not p in dict:
                raise yaml.YAMLError(f"Missing Mandatory parameter {p} in {self.__class__.__name__} object {self}")
            del dictCopy[p]
        for o in self.OPTIONS:
            if o.name in dictCopy:
                del dictCopy[o.name]
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
        for var in facts.CHILDREN:
            list = facts.__dict__[var]
            for c in list:
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

    def update(self, facts=None, args=None):
        if not facts:
            facts = YAMLHost()
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
        if inst:
            inst.applyMods(self._cfgMods)
            dseMods = getattr(self, "dseMods", None)
            if dseMods:
                inst.applyMods(dseMods)

        for var in self.CHILDREN:
            list = self.__dict__[var]
            for c in list:
                c.update(facts, args)

    def addModifier(self, dn, type, attr, val):
        dict = self._cfgMods
        DiffResult.addModifier(dict, dn, type, attr, val)


class YAMLHost(MyYAMLObject):
    yaml_tag = u'!ds389Host'

    OPTIONS = (
        SpecialOption('prefix', 1, "389 Directory Service non standard installation path" ),
    )
    CHILDREN = ( 'instances', )

    def __init__(self):
        super().__init__(socket.gethostname())
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
            self.instances.append(instance)
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


class YAMLInstance(MyYAMLObject):
    yaml_tag = u'!ds389Instance'
    LDBM_CONFIG_DB = 'cn=config,cn=ldbm database,cn=plugins,cn=config'
    PARAMS = {
        ** MyYAMLObject.PARAMS,
        'started' : "Boolean to tell whether the server should be started or stopped.",
        'dseMods' : "List of change that needs to be applied on dse.ldif after the instance creation",
    }
    CHILDREN = ( 'backends', )
    OPTIONS = (
        ConfigOption('backup_dir', 'nsslapd-bakdir', 'cn=config', None, "Desc" ),
        ConfigOption('bin_dir', 'nsslapd-bin_dir', 'cn=config', None, "Desc" ),
        ConfigOption('cert_dir', 'nsslapd-certdir', 'cn=config', None, "Desc" ),
        ConfigOption('config_dir', 'nsslapd-config_dir', 'cn=config', None, "Desc" ),
        ConfigOption('data_dir', 'nsslapd-data_dir', 'cn=config', None, "Desc" ),
        ConfigOption('db_dir', 'nsslapd-db_dir', 'cn=config', None, "Desc" ),
        ConfigOption('db_home_dir', 'nsslapd-db_home_dir', 'cn=config', None, "Desc" ),
        ConfigOption('db_lib', 'nsslapd-db_lib', 'cn=config', None, "Desc" ),
        ConfigOption('extraLdif', None, None, None, "Desc" ),
        ConfigOption('full_machine_name', 'nsslapd-localhost', 'cn=config', None, "Desc" ),
        ConfigOption('group', 'nsslapd-group', 'cn=config', None, "Desc" ),
        ConfigOption('initconfig_dir', 'nsslapd-initconfig_dir', 'cn=config', None, "Desc" ),
        ConfigOption('instance_name', None, None, None, "Desc" ),
        ConfigOption('inst_dir', 'nsslapd-instancedir', 'cn=config', None, "Desc" ),
        ConfigOption('ldapi', 'nsslapd-ldapifilepath', 'cn=config', None, "Desc" ),
        ConfigOption('ldif_dir', 'nsslapd-ldifdir', 'cn=config', None, "Desc" ),
        ConfigOption('lib_dir', None, None, None, "Desc" ),
        ConfigOption('local_state_dir', 'nsslapd-local_state_dir', 'cn=config', None, "Desc" ),
        ConfigOption('lock_dir', 'nsslapd-lockdir', 'cn=config', None, "Desc" ),
        ConfigOption('port', 'nsslapd-port', 'cn=config', None, "Desc" ),
        ConfigOption('prefix', None, None, None, "Desc" ),
        ConfigOption('root_dn', 'nsslapd-rootdn', 'cn=config', None, "Desc" ),
        ConfigOption('root_password', 'nsslapd-root_password', 'cn=config', None, "Desc" ),
        ConfigOption('run_dir', 'nsslapd-rundir', 'cn=config', None, "Desc" ),
        ConfigOption('sbin_dir', None, None, None, "Desc" ),
        ConfigOption('schema_dir', 'nsslapd-schemadir', 'cn=config', None, "Desc" ),
        ConfigOption('secure_port', 'nsslapd-secureport', 'cn=config', None, "Desc" ),
        ConfigOption('self_sign_cert', None, None, None, "Desc" ),
        ConfigOption('self_sign_cert_valid_months', None, None, None, "Desc" ),
        ConfigOption('selinux', None, None, None, "Desc" ),
        SpecialOption('state', 2, "Indicate whether the instance is (or should be) present or absent" ),
        SpecialOption('started', 99, "Indicate whether the instance is (or should be) started" ),
        ConfigOption('strict_host_checking', None, None, None, "Desc" ),
        ConfigOption('sysconf_dir', None, None, None, "Desc" ),
        ConfigOption('systemd', None, None, None, "Desc" ),
        ConfigOption('tmp_dir', 'nsslapd-tmpdir', 'cn=config', None, "Desc" ),
        ConfigOption('user', 'nsslapd-localuser', 'cn=config', None, "Desc" ),

        DSEOption('nsslapd-lookthroughlimit', LDBM_CONFIG_DB, '5000', "Desc"),
        DSEOption('nsslapd-mode', LDBM_CONFIG_DB, '600', "Desc"),
        DSEOption('nsslapd-idlistscanlimit', LDBM_CONFIG_DB, '4000', "Desc"),
        DSEOption('nsslapd-directory', LDBM_CONFIG_DB, '{prefix}/var/lib/dirsrv/slapd-{instname}/db', "Desc"),
        DSEOption('nsslapd-import-cachesize', LDBM_CONFIG_DB, '16777216', "Desc"),
        DSEOption('nsslapd-idl-switch', LDBM_CONFIG_DB, 'new', "Desc"),
        DSEOption('nsslapd-search-bypass-filter-test', LDBM_CONFIG_DB, 'on', "Desc"),
        DSEOption('nsslapd-search-use-vlv-index', LDBM_CONFIG_DB, 'on', "Desc"),
        DSEOption('nsslapd-exclude-from-export', LDBM_CONFIG_DB, 'entrydn entryid dncomp parentid numSubordinates tombstonenumsubordinates entryusn', "Desc"),
        DSEOption('nsslapd-serial-lock', LDBM_CONFIG_DB, 'on', "Desc"),
        DSEOption('nsslapd-subtree-rename-switch', LDBM_CONFIG_DB, 'on', "Desc"),
        DSEOption('nsslapd-pagedlookthroughlimit', LDBM_CONFIG_DB, '0', "Desc"),
        DSEOption('nsslapd-pagedidlistscanlimit', LDBM_CONFIG_DB, '0', "Desc"),
        DSEOption('nsslapd-rangelookthroughlimit', LDBM_CONFIG_DB, '5000', "Desc"),
        DSEOption('nsslapd-backend-opt-level', LDBM_CONFIG_DB, '1', "Desc"),
        DSEOption('nsslapd-backend-implement', LDBM_CONFIG_DB, 'bdb', "Desc"),

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
        for be in self.backends:
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
                    self.backends.append(backend)
                    backend.getFacts()

        ### Now determine what has changed compared to the default entry
        defaultdse = self.getDefaultDSE()
        result = dse.diff(defaultdse)
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
        self._DirSrv = inst
        if not self.started:
            inst.stop()
        return inst

    def delete(self):
        dirsrv = self.getDirSrv()
        dirsrv.stop
        dirsrv.delete()
        self._isDeleted = True

    def getDefaultDSE(self):
        defaultDSE = getattr(self, "_defaultDSE", None)
        if defaultDSE:
            return defaultDSE
        ### Check if dse default value exists.
        defaultglobalDSEpath = self.getPath(self.GLOBAL_DSE_PATH)
        if not os.access(defaultglobalDSEpath, os.F_OK):
            ### If it does not exists then create a dummy instance
            dummyInstance = YAMLInstance('ansible-default')
            dummyInstance.started = False
            dummyInstance.port = 0
            dummyInstance.secure_port = 0
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
            if action.vto in ( True, "True", "started" ):
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

    def update(self, facts=None, args=None):
        super().update(facts, args)
        if getattr(self, "started", "True") not in ( "True", "started" ):
            self.getDirSrv().stop()


    def applyMods(self, dict):
        dirSrv = self.getDirSrv()
        started = dirSrv.status()
        if not started:
            dirSrv.start()
        dirSrv.open()
        for dn, actionDict in dict.items():
            modList = []
            for action in actionDict:
                if DiffResult.ADDENTRY in actionDict:
                    for attr, vals in actionDict[DiffResult.ADDENTRY].items():
                        modList.append( (attr, ensure_list_bytes(vals)) )
                    log.debug(f"YAMLInstance.applyMods: add({dn}, {modList})")
                    try:
                        SimpleLDAPObject.add_s(dirSrv, dn, modList)
                    except ldap.ALREADY_EXISTS:
                        log.debug(f"YAMLInstance.applyMods: add returned ldap.ALREADY_EXISTS")
                        mods = []
                        for attr, vals in modList:
                            mods.append( (ldap.MOD_REPLACE, attr, vals) )
                        log.debug(f"YAMLInstance.applyMods: modify({dn}, {mods})")
                        SimpleLDAPObject.modify_s(dirSrv, dn, mods)
                    modList.clear()
                elif DiffResult.DELETEENTRY in actionDict:
                    log.debug(f"YAMLInstance.applyMods: delete({dn})")
                    SimpleLDAPObject.delete_s(dirSrv, dn)
                elif DiffResult.ADDVALUE in actionDict:
                    modList.append( (ldap.MOD_ADD, attr, ensure_list_bytes(vals)) )
                elif DiffResult.DELETEVALUE in actionDict:
                    modList.append( (ldap.MOD_DELETE, attr, ensure_list_bytes(vals)) )
                elif DiffResult.REPLACEVALUE in actionDict:
                    modList.append( (ldap.MOD_REPLACE, attr, ensure_list_bytes(vals)) )
            if len(modList) > 0:
                log.debug(f"YAMLInstance.applyMods: modify({dn}, {modList})")
                SimpleLDAPObject.modify_s(dirSrv, dn, modList)
                modList.clear()
        if not started:
            dirSrv.stop()
        # Config changed so reload the dse.ldif next time we need it
        setattr(self, "_dse", None)
                

class YAMLBackend(MyYAMLObject):
    yaml_tag = u'!ds389Backend'
    CHILDREN = ( 'indexes', )
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
        ConfigOption('suffix', 'nsslapd-suffix', BEDN, None, "Desc" ),
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
            log.debug(f"Backend {self.name} option:{action.option.name} val:{val}")
            if val and val != vdef:
                setattr(self, action.option.name, val)

        for dn in dse.class2dn['nsindex']:
            m = re.match(f'cn=([^,]*),cn=index,cn={self.name},cn=ldbm database,cn=plugins,cn=config', dn)
            if m:
                entry = dse.dn2entry[dn]
                if self.is_default_index(m.group(1), entry) is False:
                    index = YAMLIndex(m.group(1), parent=self)
                    index._beentrydn = dn
                    self.indexes.append(index)
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


class YAMLIndex(MyYAMLObject):
    yaml_tag = u'!ds389Index'
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

class Entry:
    def __init__(self, dn, attributes):
        self._dn = dn
        self._ndn = normalizeDN(dn)
        self._attrs = NormalizedDict()  #  attr ==> ( [ vals ...], [ normalizedvals ... ] )
        for attr, vals in attributes.items():
            attrnvals = []
            for val in vals:
                attrnvals.append( self.normalize(ensure_str(val)) )
            self._attrs[attr] = ( vals, attrnvals )

    def getDN(self):
        return self._dn

    def getNDN(self):
        return self._ndn

    def normalize(self, val):
        return self._attrs.normalize(ensure_str(val))

    def getAttributes(self):
        return self._attrs.keys()

    def hasValue(self, attr, val):
        if self._attrs.has_key(attr):
            return self.normalize(val) in self._attrs[attr][1]
        return False

    def hasAttr(self, attr):
        return self._attrs.has_key(attr)

    def hasObjectclass(self, c):
        return self.hasValue('objectclass', c)

    def __repr__(self):
        return f"Entry({self._dn}, {self._attrs})"

    def get(self, attr):
        if self._attrs.has_key(attr):
            return self._attrs[attr][0]
        return None

    def getSingleValue(self, attr):
        val = self.get(attr)
        if not val:
            return None
        assert len(val) == 1
        return ensure_str(val[0])

    def getNormalizedValues(self, attr):
        if self._attrs.has_key(attr):
            self._attrs[attr][1].sort()
            return self._attrs[attr][1]
        return None

    def hasSameAttributes(self, entry, attrlist=None):
        if attrlist is None:
            return self._attrs == entry._attrs
        for attr in attrlist:
            if self.getNormalizedValues(attr) != entry.getNormalizedValues(attr):
                return False
        return True


class DiffResult:
    ADDENTRY = "addEntry"
    DELETEENTRY = "deleteEntry"
    ADDVALUE = "addValue"
    DELETEVALUE = "deleteValue"
    REPLACEVALUE = "replaceValue"
    ACTIONS = ( ADDENTRY, DELETEENTRY, ADDVALUE, DELETEVALUE, REPLACEVALUE)

    def __init__(self):
        self.result = NormalizedDict()

    def toYaml(self):
        return self.result

    def __str__(self):
        return str(self.result)

    def getDict(dict, key):
        if not dict.has_key(key):
            dict[key] = NormalizedDict()
        return dict[key]

    def getList(dict, key):
        if not dict.has_key(key):
            dict[key] = []
        return dict[key] 

    def addModifier(dict, dn, action, attr, val):
        assert (action in DiffResult.ACTIONS)
        DiffResult.getList(DiffResult.getDict(DiffResult.getDict(dict, dn), action), attr).append(ensure_str(val))

    def addAction(self, action, dn, attr, val):
        # result = { dn : { action: { attr : [val] } } }
        DiffResult.addModifier(self.result, dn, action, attr, val)

    def match(dn, pattern_list, flags=0):
        for pattern in pattern_list:
            m = re.match(pattern.replace('\\', '\\\\'), dn, flags)
            if m:
                return True
        return False

    def cloneDN(self, fromDict, dn):
        for action in fromDict[dn]:
            for attr in fromDict[dn][action]:
                self.addAction(action, dn, attr, None)
                self.result[dn][action][attr] = fromDict[dn][action][attr][:]

    def getSingleValuedValue(self, dn, attr):
        op = None
        val = None
        if dn and attr:
            for action in DiffResult.ACTIONS:
                if self.result.has_key(dn) and self.result[dn].has_key(action) and self.result[dn][action].has_key(attr):
                    assert len(self.result[dn][action][attr]) == 1
                    return (action, self.result[dn][action][attr][0])
        return (None, None)


class DSE:
    def __init__(self, dsePath):
        self.dsePath = dsePath;
        # Count entries in dse.ldif
        nbentries = 0
        with open(dsePath, 'r') as f:
            for line in f:
                if line.startswith('dn:'):
                    nbentries = nbentries + 1
        # Parse dse.ldif
        with open(dsePath, 'r') as f:
            dse_parser = ldif.LDIFRecordList(f, ignored_attr_types=IGNOREATTRS, max_entries=nbentries)
            if dse_parser is None:
                return
            dse_parser.parse()
        # And generap the entries maps
        dse = dse_parser.all_records
        self.dn2entry = NormalizedDict()      # dn --> entry map
        self.class2dn = {}      # class -> dn map
        for c in CLASSES:
            self.class2dn[c] = []
        self.class2dn['other'] = []
        entryid = 1
        for dn, entry in dse:
            e = Entry(dn, entry)
            e.id = entryid
            entryid = entryid + 1
            self.dn2entry[e.getNDN()] = e
            found_class = 'other'
            for c in CLASSES:
                if e.hasObjectclass(c) is True:
                    found_class = c
            self.class2dn[found_class].append(e.getNDN())

    def fromLines(lines):
        ### Transform list of lines into DSE
        with TemporaryDirectory() as tmp:
            dsePath = os.path.join(tmp, 'dse.ldif')
            with open(dsePath, 'w') as f:
                f.write(lines)
            return DSE(dsePath)

    def __repr__(self):
        return str(self.dn2entry)

    def getEntry(self, dn):
        if self.dn2entry.has_key(dn):
            return self.dn2entry[dn]
        else:
            return None

    def getSingleValue(self, dn, attr):
        entry = self.getEntry(dn)
        if entry:
            return entry.getSingleValue(attr)
        return None

    def diffAttr(self, result, attr, e1, e2):
        if e1 is None: 
            a1 = None
        else:
            a1 = attr
        if e2 is None: 
            a2 = None
        else:
            a2 = attr
        if a1 is None:
            result.addAction(DiffResult.DELETEVALUE, e2.getDN(), attr, None)
            return
        if a2 is None:
            for val in e1.attrdict[attr]:
                result.addAction(DiffResult.ADDVALUE, e1.getDN(), e1.attrnames[attr], val)
            return
        if a1 != a2:
            if (len(a1) == 1 and len(a2) == 1):
                val = e1.get(attr)
                result.addAction(DiffResult.REPLACEVALUE, e1.getDN(), e1.attrnames[attr], val)
                return
            for val in e1.get(attr):
                if not e2.hasValue(attr, val):
                    result.addAction(DiffResult.ADDVALUE, e1.getDN(), e1.attrnames[attr], val)
            for val in e2.get(attr):
                if not e1.hasValue(attr, val):
                    result.addAction(DiffResult.DELETEVALUE, e1.getDN(), e1.attrnames[attr], val)

    def diffEntry(self, result, e1, e2):
        if e1 is None:
            result.addAction(DiffResult.DELETEENTRY, e2.getDN(), None, None)
            return
        if e2 is None:
            for attr in e1.getAttributes():
                for val in e1.get(attr):
                    result.addAction(DiffResult.ADDENTRY, e1.getDN(), attr, val)
            return
        for attr in e1.getAttributes():
            self.diffAttr(result, attr, e1, e2)
        for attr in e2.getAttributes():
            if not e1.hasAttr(attr):
                self.diffAttr(result, attr, None, e2)

    def diff(self, dse2):
        result = DiffResult()
        for dn in self.dn2entry:
            self.diffEntry(result, self.dn2entry[dn], dse2.getEntry(dn))
        for dn in dse2.dn2entry:
            if not self.dn2entry.has_key(dn):
                self.diffEntry(result, None, dse2.getEntry(dn))
        return result

