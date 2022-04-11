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
from dataclasses import dataclass
from lib389 import DirSrv
from lib389.utils import ensure_str, ensure_bytes, ensure_list_str, ensure_list_bytes, normalizeDN, escapeDNFiltValue
from lib389.cli_base import setup_script_logger
from ldap.ldapobject import SimpleLDAPObject

# dse.ldif important object classes
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

# Attributes ignored while processing dse.ldif file
IGNOREATTRS = ( 'creatorsName', 'modifiersName',
                'createTimestamp', 'modifyTimestamp', 'numSubordinates',
                'nsslapd-plugindescription', 'nsslapd-pluginid',
                'nsslapd-pluginvendor', 'nsslapd-pluginversion',
                'nsstate',
              )
log = None

def setLogger(name, verbose=0):
    global log
    """
        Reset the python logging system for STDOUT, and attach a new
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

def getLogger():
    global log
    return log

def toAnsibleResult(object):
   cb=getattr(object, "toAnsibleResult", None)
   if cb is not None:
        return cb(object)
   if isinstance(object, yaml.YAMLObject):
        log.debug(f"toAnsibleResult: object={object}")
        return toAnsibleResult( { 'tag':object.yaml_tag,  **object.__getstate__() } )
   if type(object) is list:
        l=[]
        for i in object:
            l.append(toAnsibleResult(i))
        return l
   if type(object) is tuple:
        return tuple(toAnsibleResult(list(object)))
   if type(object) is dict:
        d={}
        for k,v in object.items():
            d[toAnsibleResult(k)] = toAnsibleResult(v)
        return d
   return object


@dataclass
class NormalizedDict(dict, yaml.YAMLObject):
    """
        A dict with normalized key stored in hash table 
        Note: The original version of the key (or the first one
        in case of duplicates) is returned when walking the dict
    """
    yaml_tag = u'tag:yaml.org,2002:map'

    def __init__(self, *args):
        self.dict = {}         # The map: original-key --> value
        self.norm2keys = {}    # The map: normalized-key --> original-key

    def __getstate__(self):
        return { ** self.dict }

    def normalize(key):
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
        nk = NormalizedDict.normalize(key)
        return NormalizedDict.normalize(key) in self.norm2keys

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
        nk = NormalizedDict.normalize(key)
        if nk not in self.norm2keys:
            self.norm2keys[nk] = key
        self.dict[self.norm2keys[nk]] = value

    def __repr__(self):
        return str(self.dict)

    def __getitem__(self, key):
        return self.dict[self.norm2keys[NormalizedDict.normalize(key)]]

    def __delitem__(self, key):
        nk = NormalizedDict.normalize(key)
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
#fromkeys()     Returns a dictionary with the specified keys and value
#items()        Returns a list containing a tuple for each key value pair
#keys() Returns a list containing the dictionary's keys
#popitem()      Removes the last inserted key-value pair
#setdefault()   Returns the value of the specified key. If the key does not exist: insert the key, with the specified value
#values()       Returns a list of all the values in the dictionary
#

class LdapOp(yaml.YAMLObject):
    """
        A dict with normalized key  stored in hash table
        Note: The original version of the key (or the first one
        in case of duplicates) is returned when walking the dict
    """
    yaml_tag = u'!ds389LdapOp'
    yaml_loader = yaml.SafeLoader

    ADD_ENTRY = "AddEntry"
    DEL_ENTRY = "DeleteEntry"
    ADD_VALUES = "AddValues"
    DEL_VALUES = "DeleteValues"
    REPLACE_VALUES = "ReplaceValues"


    def __init__(self, op, dn):
        self.___opinfo = {
            LdapOp.ADD_ENTRY : { 'changetype' : 'add', 'attrtype': None, 'apply' : self._ldap_add, 'ldaptype': None},
            LdapOp.DEL_ENTRY : { 'changetype' : 'delete', 'attrtype': None, 'apply' : self._ldap_del, 'ldaptype': None }, 
            LdapOp.ADD_VALUES : { 'changetype' : 'modify', 'attrtype': 'add', 'apply' : self._ldap_mod,
                                'ldaptype': ldap.MOD_ADD }, 
            LdapOp.DEL_VALUES : { 'changetype' : 'modify', 'attrtype': 'delete', 'apply' : self._ldap_mod,
                                'ldaptype': ldap.MOD_DELETE }, 
            LdapOp.REPLACE_VALUES : { 'changetype' : 'modify', 'attrtype': 'replace', 'apply' : self._ldap_mod,
                                'ldaptype': ldap.MOD_REPLACE }, 
        }
        assert op in self.___opinfo
        super().__init__()
        self.dn = dn
        self.op = op
        self.attrs = NormalizedDict()
        self.nvals = {}

    def add_values(self, attr, vals):
        for val in vals:
            self.add_value(attr, val)

    def add_value(self, attr, val):
        nattr = NormalizedDict.normalize(attr)
        nval = NormalizedDict.normalize(ensure_str(val))
        if not self.attrs.has_key(attr):
            self.attrs[attr] = []
            self.nvals[nattr] = []
        s = self.attrs[attr]
        nv = self.nvals[nattr]
        if nval in nv:
            raise ldap.TYPE_OR_VALUE_EXISTS(f"while trying to add: dn={dn} attr={attr} val={val}")
        s.append(val)
        nv.append(nval)

    def to_ldif(self, fout):
        opinfo = self.___opinfo[self.op]
        fout.print(f"dn: {self.dn}")
        fout.print(f"changetype: {opinfo['changetype']}")
        first = True
        for attr in self.attrs.keys():
            attrtype = opinfo['attrtype']
            if attrtype:
                if first:
                    first = False
                else:
                    fout.print(f"dn: {self.dn}")
                fout.print(f"{attrtype}: {attr}")
            for val in self.attrs[attr]:
                fout.print(f"{attr}: {val}")

    def to_ldap_mods(self):
        mods = []
        opinfo = self.___opinfo[self.op]
        for attr in self.attrs.keys():
            vals = self.attrs[attr]
            if opinfo['ldaptype']:
                mods.append( (opinfo['ldaptype'], attr, ensure_list_bytes(vals)) )
            else:
                mods.append( (attr, ensure_list_bytes(vals)) )

    def _ldap_add(self, dirSrv):
        SimpleLDAPObject.add_s(dirSrv, self.dn, self.to_ldap_mods())

    def _ldap_del(self, dirSrv):
        SimpleLDAPObject.delete_s(dirSrv, self.dn)

    def _ldap_mod(self, dirSrv):
        SimpleLDAPObject.modify_s(dirSrv, self.dn, self.to_ldap_mods())

    def apply(self, dirSrv):
        opinfo = self.___opinfo[self.op]
        opinfo['apply'](self, dirSrv)

    def apply_list_op(listOp, dirSrv):
        for op in listOp:
            op.apply(dirSrv)

    def _d(self, varName):
        val = getattr(self, varName, None)
        if val:
            return { varName : val }
        return { }

    def __getstate__(self):
        return { **self._d('yaml_tag'), **self._d('op'), **self._d('dn'), **self._d('attrs') }

    def __repr__(self):
        if mods in self.__dict__:
            return f"({op} dn={dn} attrs={attrs})"

    def getAttrIterator(self, normalize=False):
        if normalize:
            return self.nvals.keys()
        else:
            return self.attrs.keys()
                        
    def getValues(self, attr, normalize=False):
        if not self.attrs.has_key(attr):
            return []
        if normalize == False:
            return self.attrs[attr]
        else:
            return self.nvals[NormalizedDict.normalize(attr)]

    def getvalIterator(self, attr, normalize=False):
        if not self.attrs.has_key(attr):
            return []
        if normalize == False:
            for val in self.attrs[attr]:
                yield (attr, val)
        else:
            attr = NormalizedDict.normalize(attr)
            for val in self.nvals[attr]:
                yield (attr, val)


    def getAttrValIterator(self, normalize=False):
        if normalize == False:
            for attr in self.attrs.keys():
                for val in self.attrs[attr]:
                    yield (attr, val)
        else:
            attr = NormalizedDict.normalize(attr)
            for attr in self.nvals.keys():
                for val in self.nvals[attr]:
                    yield (attr, val)

    def has_attr(self, attr):
        return self.attrs.has_key(attr)


class Entry:
    def __init__(self, dn, attributes):
        self._op = LdapOp(LdapOp.ADD_ENTRY, dn)
        self._ndn = normalizeDN(dn)
        for attr, vals in attributes.items():
            self._op.add_values(attr, vals)

    def getDN(self):
        return self._op.dn

    def getNDN(self):
        return self._ndn

    def normalize(self, val):
        return self._attrs.normalize(ensure_str(val))

    def getNormalizedAttributes(self):
        return [ i for i in self._op.getAttrIterator(True) ]

    def getNormalizedValues(self, attr):
        return [ i for i in self._op.getvalIterator(attr, True) ]

    def hasValue(self, attr, val):
        if self._op.attrs.has_key(attr):
            v = NormalizedDict.normalize(val) in self._op.getValues(attr, True)
            return v
        return False

    def hasAttr(self, attr):
        return self._op.has_attr(attr)

    def hasObjectclass(self, c):
        return self.hasValue('objectclass', c)

    def __repr__(self):
        return f"Entry({self._op.dn}, {self._op.attrs})"

    def get(self, attr):
        if self.hasAttr(attr):
            return self._op.getValues(attr)
        return None

    def getSingleValue(self, attr):
        val = self.get(attr)
        if not val:
            return None
        assert len(val) == 1
        return ensure_str(val[0])

    def hasSameAttributes(self, entry, attrlist=None):
        if attrlist is None:
            return self._attrs == entry._attrs
        for attr in attrlist:
            if self.getNormalizedValues(attr).sort() != entry.getNormalizedValues(attr).sort():
                return False
        return True

    def getAttributes(self):
            return self._op.getAttrIterator()


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

    def getValue(dict, key):
        if not dict.has_key(key):
            return None
        return dict[key]

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

    def diffAttr(self, attr, e1, e2):
        if e1 is None: 
            a1 = None
        else:
            a1 = attr
        if e2 is None: 
            a2 = None
        else:
            a2 = attr
        if a1 is None:
            self.addAction(DiffResult.DELETEVALUE, e2.getDN(), attr, None)
            return
        if a2 is None:
            for val in e1.attrdict[attr]:
                self.addAction(DiffResult.ADDVALUE, e1.getDN(), e1.attrnames[attr], val)
            return
        if a1 != a2:
            if (len(a1) == 1 and len(a2) == 1):
                val = e1.get(attr)
                self.addAction(DiffResult.REPLACEVALUE, e1.getDN(), e1.attrnames[attr], val)
                return
            for val in e1.get(attr):
                if not e2.hasValue(attr, val):
                    self.addAction(DiffResult.ADDVALUE, e1.getDN(), e1.attrnames[attr], val)
            for val in e2.get(attr):
                if not e1.hasValue(attr, val):
                    self.addAction(DiffResult.DELETEVALUE, e1.getDN(), e1.attrnames[attr], val)

    def diffEntry(self, e1, e2):
        if e1 is None:
            self.addAction(DiffResult.DELETEENTRY, e2.getDN(), None, None)
            return
        if e2 is None:
            for attr in e1.getAttributes():
                for val in e1.get(attr):
                    self.addAction(DiffResult.ADDENTRY, e1.getDN(), attr, val)
            return
        for attr in e1.getAttributes():
            self.diffAttr(attr, e1, e2)
        for attr in e2.getAttributes():
            if not e1.hasAttr(attr):
                self.diffAttr(attr, None, e2)

    def diff(self, entry1Dict, entry2Dict):
        dnsList = []
        dnsDict = {}

        for e in entry1Dict.values():
            ndn = e._ndn
            dnsList.append(ndn)
            dnsDict[ndn] = True
        for e in entry2Dict.values():
            ndn = e._ndn
            if not e._ndn in dnsDict:
                dnsList.append(ndn)
        for dn in dnsList:
            self.diffEntry(DiffResult.getValue(entry1Dict, dn), DiffResult.getValue(entry2Dict, dn))

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
        self.class2dn = {}                    # class -> dn map
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

    def getEntryDict(self):
        return self.dn2entry

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

