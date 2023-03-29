# --- BEGIN COPYRIGHT BLOCK ---
# Copyright (C) 2022 Red Hat, Inc.
# All rights reserved.
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# --- END COPYRIGHT BLOCK ---
#
#

"""This module provides utility classes and function useful for ansible_ds."""

DOCUMENTATION = r'''
---
module: ds389_entities

short_description: This module provides utility classes and function useful for ansible_ds

version_added: "1.0.0"

description:
    - setLogger function:     an utility function to initialize the log framework
    - LdapOp class:           the class reprensenting an ldap operation in YAML
    - Entry class:            the class storing an ldap entry within ansible-ds
    - DiffResult class:       the class used to store dse.ldif differences
    - DSE class:              a class allowing to compare dse.ldif files

author:
    - Pierre Rogier (@progier389)

requirements:
    - python3-lib389 >= 2.2
    - python >= 3.9
    - 389-ds-base >= 2.2
'''

# ##Should be fixed later on then removed:
# pylint: disable=missing-function-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=invalid-name
# pylint: disable=consider-iterating-dictionary


import sys
import os
import re
import logging
from tempfile import TemporaryDirectory
from dataclasses import dataclass
import ldap
import ldif
from lib389.utils import ensure_str, ensure_list_bytes

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
    'nsds5replica',
    'nsds5replicationagreement',
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


# Initialize logging system
_log = None


def init_log(name, stream=sys.stderr):
    # pylint: disable=global-statement
    global _log
    # pylint: enable=global-statement
    _log = logging.getLogger(name)
    _log.setLevel(logging.DEBUG)
    logh = logging.StreamHandler(stream)
    fmt = '[%(asctime)s] %(levelname)s - %(filename)s[%(lineno)d]: %(message)s'
    datefmt = '%Y/%m/%d %H:%M:%S %z'
    logh.setFormatter(logging.Formatter(fmt, datefmt))
    logh.setLevel(logging.DEBUG)
    _log.addHandler(logh)
    elogh = logging.StreamHandler(sys.stderr)
    elogh.setLevel(logging.ERROR)
    elogh.setFormatter(logging.Formatter(fmt, datefmt))
    _log.addHandler(elogh)
    _log.setLevel(logging.ERROR)


def get_log():
    if not _log:
        init_log("Bootstrap")
    return _log


def dictlist2dict(dictlist):
    if isinstance(dictlist, dict):
        return dictlist
    if dictlist is None:
        return {}
    r = {}
    for d in dictlist:
        r[d['name']] = { **d }
        r[d['name']].pop('name')
    return r


def _ldap_op_s(inst, f, fname, *args, **kwargs):
    """Define wrappers around the synchronous ldap operations to have a clear diagnostic."""

    # f.__name__ says 'inner' so the wanted name is provided as argument
    try:
        return f(*args, **kwargs)
    except ldap.LDAPError as e:
        new_desc = f"{fname}({args}, {kwargs}) on instance {inst.serverid}"
        if len(e.args) >= 1:
            e.args[0]['ldap_request'] = new_desc
        raise

def add_s(inst, *args, **kwargs):
    return _ldap_op_s(inst, inst.add_s, 'add_s', *args, **kwargs)

def add_ext_s(inst, *args, **kwargs):
    return _ldap_op_s(inst, inst.add_ext_s, 'add_ext_s', *args, **kwargs)

def modify_s(inst, *args, **kwargs):
    return _ldap_op_s(inst, inst.modify_s, 'modify_s', *args, **kwargs)

def modify_ext_s(inst, *args, **kwargs):
    return _ldap_op_s(inst, inst.modify_ext_s, 'modify_ext_s', *args, **kwargs)

def delete_s(inst, *args, **kwargs):
    return _ldap_op_s(inst, inst.delete_s, 'delete_s', *args, **kwargs)

def delete_ext_s(inst, *args, **kwargs):
    return _ldap_op_s(inst, inst.delete_ext_s, 'delete_ext_s', *args, **kwargs)

def search_s(inst, *args, **kwargs):
    return _ldap_op_s(inst, inst.search_s, 'search_s', *args, **kwargs)

def search_ext_s(inst, *args, **kwargs):
    return _ldap_op_s(inst, inst.search_ext_s, 'search_ext_s', *args, **kwargs)


@dataclass
class Key(str):
    """A normalizable string (typically an entry dn or an attribute name)."""

    @staticmethod
    def from_val(val):
        """This methods returns a key if val is a string."""
        if isinstance(val, bytes):
            try:
                val = val.decode('utf-8')
            except UnicodeError:
                pass
        if isinstance(val, str) and not isinstance(val, Key):
            return Key(val)
        return val

    def __init__(self, astring):
        assert astring is not None
        str.__init__(astring)
        self._astring = astring
        try:
            nkey = ldap.dn.dn2str(ldap.dn.str2dn(astring.lower()))
            for k,v in { r"\=": r"\3d", r"\,": r"\2c" }.items():
                nkey = nkey.replace(k, v)
            self.normalized = nkey
        except ldap.DECODING_ERROR:
            self.normalized = astring.lower()

    def __hash__(self) -> 'int':
        return hash(self.normalized)

    def __eq__(self, other):
        if not isinstance(other, str):
            return False
        return self.normalized == Key.from_val(other).normalized

    def decode(self,encoding, *args):
        """Works around ensure_str bug (that call decode if type is not str)."""
        del encoding # Avoid lint warning.
        del args # Avoid lint warning.
        return self

    def __str__(self):
        return str.__str__(self._astring)

    def __repr__(self):
        return str.__repr__(self._astring)

    def __lt__(self, obj):
        return self.normalized.__lt__(Key.from_val(obj).normalized)


# Following methods are inherited from dict:
#
#fromkeys()     Returns a dictionary with the specified keys and value
#items()        Returns a list containing a tuple for each key value pair
#keys() Returns a list containing the dictionary's keys
#popitem()      Removes the last inserted key-value pair
#setdefault()   Returns the value of the specified key. If the key does not exist: insert the key, with the specified value
#values()       Returns a list of all the values in the dictionary
#

class LdapOp():
    """
        A dict with normalized key  stored in hash table
        Note: The original version of the key (or the first one
        in case of duplicates) is returned when walking the dict
    """
    ADD_ENTRY = "AddEntry"
    DEL_ENTRY = "DeleteEntry"
    ADD_VALUES = "AddValues"
    DEL_VALUES = "DeleteValues"
    REPLACE_VALUES = "ReplaceValues"


    def __init__(self, op:str, dn:str):
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
        self.dn: Key = Key.from_val(dn)
        self.op = op
        self.attrs = {}

    def add_values(self, attr, vals):
        for val in vals:
            self.add_value(attr, val)

    def add_value(self, attr:str, val:str):
        attr = Key.from_val(attr)
        val = Key.from_val(val)

        if attr not in self.attrs:
            self.attrs[attr] = []
        if val in self.attrs[attr]:
            raise ldap.TYPE_OR_VALUE_EXISTS(f"while trying to add: dn={self.dn} attr={attr} val={val}")
        self.attrs[attr].append(val)

    def to_ldif(self, fout):
        opinfo = self.___opinfo[self.op]
        fout.print(f"dn: {self.dn}")
        fout.print(f"changetype: {opinfo['changetype']}")
        first = True
        for attr,vals in self.attrs.items():
            attrtype = opinfo['attrtype']
            if attrtype:
                if first:
                    first = False
                else:
                    fout.print(f"dn: {self.dn}")
                fout.print(f"{attrtype}: {attr}")
            for val in vals:
                fout.print(f"{attr}: {val}")

    def to_ldap_mods(self):
        mods = []
        opinfo = self.___opinfo[self.op]
        for attr, vals in self.attrs.items():
            if opinfo['ldaptype']:
                mods.append( (opinfo['ldaptype'], attr, ensure_list_bytes(vals)) )
            else:
                mods.append( (attr, ensure_list_bytes(vals)) )

    def _ldap_add(self, dirSrv):
        add_s(dirSrv, self.dn, self.to_ldap_mods(), escapehatch='i am sure')

    def _ldap_del(self, dirSrv):
        delete_s(dirSrv, self.dn, escapehatch='i am sure')

    def _ldap_mod(self, dirSrv):
        modify_s(dirSrv, self.dn, self.to_ldap_mods(), escapehatch='i am sure')

    def apply(self, dirSrv):
        opinfo = self.___opinfo[self.op]
        opinfo['apply'](self, dirSrv)

    @staticmethod
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
        return f"({self.op} dn={self.dn} attrs={self.attrs})"

    def getAttrIterator(self):
        return self.attrs.keys()

    def getValues(self, attr):
        if attr not in self.attrs:
            return []
        return self.attrs[attr]

    def getvalIterator(self, attr):
        if attr not in self.attrs:
            return []
        return self.attrs[attr].values()

    def getAttrValIterator(self):
        for attr,val in self.attrs.items():
            yield (attr, val)

    def has_attr(self, attr):
        return attr in self.attrs


class Entry:
    def __init__(self, dn, attributes):
        self.op = LdapOp(LdapOp.ADD_ENTRY, Key.from_val(dn))
        for attr, vals in attributes.items():
            self.op.add_values(Key.from_val(attr), vals)

    @staticmethod
    def get_values(entry, attr):
        attr = Key.from_val(attr)
        if entry and entry.hasAttr(attr):
            return entry.op.attrs[attr]
        return None

    @staticmethod
    def fromDS(dirSrv, dn):
        try:
            entry = dirSrv.search_ext_s(dn, ldap.SCOPE_BASE, 'objectclass=*', escapehatch='i am sure')[0]
            entry = Entry(entry.dn, entry.data)
            return entry
        except ldap.NO_SUCH_OBJECT:
            return None

    def getDN(self):
        return self.op.dn

    def hasValue(self, attr, val):
        if Key.from_val(attr) in self.op.attrs:
            return Key.from_val(val) in self.op.attrs[attr]
        return False

    def hasAttr(self, attr):
        return Key.from_val(attr) in self.op.attrs

    def hasObjectclass(self, c):
        return self.hasValue('objectclass', c)

    def __repr__(self):
        return f"Entry({self.op.dn}, {self.op.attrs})"

    def get(self, attr):
        attr = Key.from_val(attr)
        if self.hasAttr(attr):
            return self.op.getValues(attr)
        return None

    def getSingleValue(self, attr):
        val = self.get(attr)
        if not val:
            return None
        assert len(val) == 1
        return ensure_str(val[0])

    def hasSameAttributes(self, entry, attrlist=None):
        if attrlist is None:
            return self.op.attrs == entry.attrs
        for attr in attrlist:
            if self.op.getValues(attr).sort() != entry.op.getValues(attr).sort() :
                return False
        return True

    def getAttributes(self):
        return self.op.getAttrIterator()


class DiffResult:
    ADDENTRY = "addEntry"
    DELETEENTRY = "deleteEntry"
    ADDVALUE = "addValue"
    DELETEVALUE = "deleteValue"
    REPLACEVALUE = "replaceValue"
    ACTIONS = ( ADDENTRY, DELETEENTRY, ADDVALUE, DELETEVALUE, REPLACEVALUE)

    def __init__(self):
        self.result = {}

    def toYaml(self):
        return self.result

    def __str__(self):
        return str(self.result)

    @staticmethod
    def getValue(adict, key):
        key = Key.from_val(key)
        if key not in adict:
            return None
        return adict[key]

    @staticmethod
    def getDict(adict, key):
        if key not in adict:
            adict[key] = {}
        return adict[key]

    @staticmethod
    def getList(adict, key):
        key = Key.from_val(key)
        if not key in adict:
            adict[key] = []
        return adict[key]

    @staticmethod
    def addModifier(adict, dn, action, attr, val):
        get_log().debug('addModifier dn=%s action=%s attr=%s val=%s', dn, action, attr, val)
        assert action in DiffResult.ACTIONS
        if action == DiffResult.DELETEENTRY:
            DiffResult.getList(DiffResult.getDict(DiffResult.getDict(adict, dn), action), "fullRemoval").append(True)
        else:
            DiffResult.getList(DiffResult.getDict(DiffResult.getDict(adict, dn), action), attr).append(Key.from_val(val))

    def addAction(self, action, dn, attr, val):
        # result = { dn : { action: { attr : [val] } } }
        DiffResult.addModifier(self.result, dn, action, attr, val)

    @staticmethod
    def match(dn, pattern_list, flags=0):
        for pattern in pattern_list:
            m = re.match(pattern.replace('\\', '\\\\'), dn, flags)
            if m:
                return True
        return False

    def cloneDN(self, fromDict, dn):
        for action in fromDict[dn]:
            for attr in fromDict[dn][action]:
                self.addAction(action, dn, attr, [])
                self.result[dn][action][attr] = fromDict[dn][action][attr][:]

    def getSingleValuedValue(self, dn, attr):
        dn = Key.from_val(dn)
        attr = Key.from_val(attr)
        if dn and attr:
            for action in DiffResult.ACTIONS:
                if dn in self.result and action in self.result[dn] and attr in self.result[dn][action]:
                    assert len(self.result[dn][action][attr]) == 1
                    val = self.result[dn][action][attr][0]
                    if isinstance(val, Key):
                        val = str(val)
                    return (action, val)
        return (None, None)

    def diffAttr(self, attr:str, e1:Entry, e2:Entry):
        a1 = Entry.get_values(e1, attr)
        a2 = Entry.get_values(e2, attr)
        if a1 != a2:
            if a1 is None:
                self.addAction(DiffResult.DELETEVALUE, e2.getDN(), attr, None)
                return
            if a2 is None:
                for val in e1.op.attrs[attr]:
                    self.addAction(DiffResult.ADDVALUE, e1.getDN(), attr, val)
                return
            if (len(a1) == 1 and len(a2) == 1):
                self.addAction(DiffResult.REPLACEVALUE, e1.getDN(), attr, a1)
                return
            for val in a1:
                if not e2.hasValue(attr, val):
                    self.addAction(DiffResult.ADDVALUE, e1.getDN(), attr, val)
            for val in a2:
                if not e1.hasValue(attr, val):
                    self.addAction(DiffResult.DELETEVALUE, e1.getDN(), attr, val)

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
            dnsList.append(e.getDN())
            dnsDict[e.getDN()] = True
        for e in entry2Dict.values():
            if not e.getDN() in dnsDict:
                dnsList.append(e.getDN())
        for dn in dnsList:
            self.diffEntry(DiffResult.getValue(entry1Dict, dn), DiffResult.getValue(entry2Dict, dn))

class DSE:
    def __init__(self, dsePath):
        self.dsePath = dsePath
        # Count entries in dse.ldif
        nbentries = 0
        with open(dsePath, 'r', encoding='utf-8') as dsefd:
            for line in dsefd:
                if line.startswith('dn:'):
                    nbentries = nbentries + 1
            # Parse dse.ldif
            dsefd.seek(0)
            dse_parser = ldif.LDIFRecordList(dsefd, ignored_attr_types=IGNOREATTRS, max_entries=nbentries)
            if dse_parser is None:
                return
            dse_parser.parse()
        # And generap the entries maps
        dse = dse_parser.all_records
        self.dn2entry = {}                    # dn --> entry map
        self.class2dn = {}                    # class -> dn map
        for c in CLASSES:
            self.class2dn[c] = []
        self.class2dn['other'] = []
        entryid = 1
        for dn, entry in dse:
            e = Entry(dn, entry)
            e.id = entryid
            entryid = entryid + 1
            self.dn2entry[e.getDN()] = e
            found_class = 'other'
            for c in CLASSES:
                if e.hasObjectclass(c) is True:
                    found_class = c
            self.class2dn[found_class].append(e.getDN())

    def getEntryDict(self):
        return self.dn2entry

    @staticmethod
    def fromLines(lines):
        ### Transform list of lines into DSE
        with TemporaryDirectory() as tmp:
            dsePath = os.path.join(tmp, 'dse.ldif')
            with open(dsePath, 'w', encoding='utf-8') as f:
                f.write(lines)
            return DSE(dsePath)

    def __repr__(self):
        return str(self.dn2entry)

    def getEntry(self, dn):
        dn = Key.from_val(dn)
        if dn in self.dn2entry:
            return self.dn2entry[dn]
        return None

    def getSingleValue(self, dn, attr):
        entry = self.getEntry(dn)
        if entry:
            return entry.getSingleValue(attr)
        return None
