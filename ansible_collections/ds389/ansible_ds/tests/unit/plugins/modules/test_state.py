# --- BEGIN COPYRIGHT BLOCK ---
# Copyright (C) 2022 Red Hat, Inc.
# All rights reserved.
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# --- END COPYRIGHT BLOCK ---
#
#

""" This module contains the testcases fore ds389_server ansible module."""

# Disable pylint warning triggered by standard fixture usage
# pylint: disable=redefined-outer-name
# pylint: disable=unused-import
# pylint: disable=unused-argument
# Disable similarities test
# pylint: disable=R0801

import os
import sys
import re
from abc import ABC, abstractmethod
import pytest
import ldap

# Set PYTHONPATH to be able to find lib389 in PREFIX install
# (computed within conftest seesion initialization hook)
from lib389 import DirSrv
from lib389.properties import SER_SERVERID_PROP
from lib389.utils import ensure_str


DIRECTORY_MANAGER_PASSWORD = "secret12"
REPLICATION_MANAGER_PASSWORD = "secret34"
SUFFIX = "dc=example,dc=com"

if "DEBUGGING" in os.environ:
    VERBOSITY = 5
else:
    VERBOSITY = 0

IDX2ATTR = { 1:'nsSizeLimit', 2:'nsTimeLimit', 3:'nsIdleTimeout', }
ATTR2IDX = { val.lower(): key for key,val in IDX2ATTR.items() }


class _StateTestHandler(ABC):
    ACTIONS = []

    def __init__(self):
        self.args = None
        self.expected_entities = []
        self.ansibletest = None
        self.log = None
        self.instances = []
        self.changed = None
        self.ok = True

    @staticmethod
    def get_handler(hname):
        """Get an handler from its name."""
        return {
            "present": _PresentHandler(),
            "absent": _AbsentHandler(),
            "updated": _UpdatedHandler(),
        }[hname]

    def _get_ds389_agmt_args(self, idx):
        """Get ds389_server options for a ds389_agmt."""
        for instidx in self.get_range(1):
            self.expected_entities.append(f'ds389_agmt_be{100*instidx+idx}_localhost.inst5.be50{idx}')
        return {
            "fulltargetname": f"localhost.inst5.be50{idx}",
            "name": "inst5",
            "target": "inst5",
            "replicabindmethod": "simple",
            "replicacredentials": REPLICATION_MANAGER_PASSWORD,
            "replicahost": "localhost",
            "replicaport": 5555,
            "replicatransportinfo": "ldap",
            "replicabinddn": "cn=replmgr,cn=config",
            "replicarole": "consumer",
            "suffix": f'ou=s{idx},{SUFFIX}'
        }

    def _get_agmt_args(self, idx, beidx, instidx):
        """Get ds389_server options for an agmt."""
        self.expected_entities.append(f'a{idx}_be{beidx}_inst{instidx}')
        return {
            "replicabinddn": "cn=replmgr,cn=config",
            "replicabindmethod": "simple",
            "replicacredentials": REPLICATION_MANAGER_PASSWORD,
            "replicahost": "localhost",
            "replicaport": 5551+instidx,
            "replicatransportinfo": "ldap",
            "name": f'a{idx}_be{beidx}_inst{instidx}'
        }

    def _get_index_args(self, idx, beidx, instidx):
        """Get ds389_server options for an index."""
        self.expected_entities.append(f'index{idx}_be{100*instidx+beidx}')
        return {
            "name": IDX2ATTR[idx],
            "indextype": [ "eq" ],
        }

    def _get_backend_args(self, beidx, instidx):
        """Get ds389_server options for a backend."""
        self.expected_entities.append(f'be{100*instidx+beidx}')
        return {
            "replicabinddn": "cn=replmgr,cn=config",
            "replicaid": 100*instidx+beidx,
            "replicarole": "supplier",
            "replicacredentials": REPLICATION_MANAGER_PASSWORD,
            "agmts": [ self._get_agmt_args(idx, beidx, instidx) for idx in self.get_range(3, beidx, instidx) ],
            "indexes": [ self._get_index_args(idx, beidx, instidx) for idx in self.get_range(4, beidx, instidx) ],
            "name": f'be{100*instidx+beidx}',
            "sample_entries": True,
            "suffix": f'ou=s{beidx},{SUFFIX}',
        }

    def _get_instance_args(self, idx):
        """Get ds389_server options for an instance."""
        self.expected_entities.append(f"inst{idx}")
        return {
            "backends": [ self._get_backend_args(beidx, idx) for beidx in self.get_range(2, idx)],
            "name": f"inst{idx}",
            "port": 5550+idx,
            "rootpw": DIRECTORY_MANAGER_PASSWORD,
            "secure_port": 6660+idx,
            "started": True
        }

    def get_range(self, itemidx, *args):
        """Get range for building entity args:
           itemidx=0 ==> ds389_agmt
           itemidx=1 ==> instance
           itemidx=2 ==> backend
           itemidx=3 ==> agmt
           itemidx=4 ==> index
        """
        return range(1,4)

    def get_args(self):
        """Get ds389_server initial options."""
        return {
            "ds389_agmts": [ self._get_ds389_agmt_args(idx) for idx in self.get_range(0)],
            "ds389_server_instances": [ self._get_instance_args(idx) for idx in self.get_range(1)],
            "ansible_check_mode": False,
            "ansible_verbosity": VERBOSITY
        }

    def reset_parameters(self):
        """Reset test handler parameters to the initial values."""
        self.expected_entities.clear()
        self.args = { "ANSIBLE_MODULE_ARGS": { "ds389": self.get_args() } }
        self.expected_entities.sort()

    def init_test(self, ansibletest, log):
        """Initialize the test"""
        # Get the DirSrv instances
        for idx in range(1,4):
            serverid = f'inst{idx}'
            srv = DirSrv()
            srv.allocate({ SER_SERVERID_PROP: serverid })
            self.instances.append(srv)
        self.cleanup()
        self.ansibletest = ansibletest
        self.log = log
        self.reset_parameters()
        self._init_test()

    def end_test(self):
        """Last action to perform if test succeed."""
        pass

    @abstractmethod
    def _init_test(self):
        """Overloaded in subclasses."""

    @abstractmethod
    def run(self, action):
        """run a test action."""

    def cleanup(self):
        """Remove the instances."""
        for srv in self.instances:
            if srv.exists():
                srv.delete()

    @staticmethod
    def _pp(data):
        if isinstance(data,list):
            return f'set of {len(data)} items'
        if isinstance(data,dict):
            return data.keys()
        return data

    def _iter(self, args, fullname, f_cb, ctx):
        """Iter the paramaters and apply dict_cb of every dict key,val and list_cb on every list."""
        #self.log.debug(f'iter(args={_StateTestHandler._pp(args)}')
        res = f_cb(args, fullname, ctx, None, None)
        if res is not None:
            return res
        if isinstance(args,list):
            for elmt in args:
                res = self._iter(elmt, fullname, f_cb, ctx)
                if res is not None:
                    return res
        elif isinstance(args, dict):
            if 'name' in args:
                fullname = f'{fullname}.{args["name"]}'
            for dkey,dval in args.items():
                res = f_cb(args, fullname, ctx, dkey, dval)
                if res is not None:
                    return res
                res = self._iter(dval, f'{fullname}.{dkey}', f_cb, ctx)
                if res is not None:
                    return res
        return None

    def get_target(self, args, avas):
        """Get the dict that matchs the avas."""
        def get_target_cb(cbargs, _, ctx, key, val):
            if key==ctx[0] and val == ctx[1]:
                return cbargs
            return None

        for ava in avas:
            args = self._iter(args, "", get_target_cb, ava)
            self.log.debug(f'get_target(ava={ava} ==> {args}') 
        return args

    def remove_target(self, args, tgt):
        """Remove target from parameters."""
        def remove_target_cb(cbargs, fullname, ctx, key, val):
            if isinstance(cbargs, list) and ctx in cbargs:
                # Check again that it is same pointer (equality is not enough)
                if [ item for item in cbargs if item is ctx ]:
                    self.log.debug(f'remove_target {fullname} {ctx} in {cbargs}')
                    cbargs.remove(ctx)
                    return tgt
            return None

        return self._iter(args, "", remove_target_cb, tgt)

    def _add_entities(self, inst, res):
        """Add akk existing entities with inst into res."""
        res.append(inst.serverid)
        # Search backends
        inst.open()
        ents = inst.search_s('cn=config', ldap.SCOPE_SUBTREE, '(objectclass=nsBackendInstance)',
                                  [ 'cn' ], escapehatch='i am sure')
        for entry in ents:
            name = ensure_str(entry.getValue('cn').lower())
            res.append(name)
        # Search user defined indexes
        ents = inst.search_s('cn=config', ldap.SCOPE_SUBTREE, '(objectclass=nsIndex)',
                                  [ 'dn' ], escapehatch='i am sure')
        for entry in ents:
            match = re.fullmatch('cn=([^,]*),cn=index,cn=([^,]*),cn=ldbm database,cn=plugins,cn=config',
                                 entry.dn)
            if match:
                attr=match.group(1).lower()
                bename=match.group(2)
                if attr in ATTR2IDX:
                    res.append(f'index{ATTR2IDX[attr]}_{bename}')
        # Search agmt and ds389_agmts
        ents = inst.search_s('cn=config', ldap.SCOPE_SUBTREE, '(objectclass=nsds5replicationagreement)',
                                  [ 'description', 'cn', 'nsDS5ReplicaRoot' ], escapehatch='i am sure')
        for entry in ents:
            name = ensure_str(entry.getValue('cn').lower())
            suffix = ensure_str(entry.getValue('nsDS5ReplicaRoot').lower())
            #self.log.debug(f'_add_entities: dn={entry.dn} suffix={suffix} inst:{inst.serverid}')
            if name.startswith('ansible'):
                srcbename=f'be{inst.serverid[4]}0{suffix[4]}'
                tgtbename = ensure_str(entry.getValue('description').lower())
                name = f'ds389_agmt_{srcbename}_{tgtbename}'
            res.append(name)

    def _list_entities(self):
        """List all existing entities."""
        res = []
        for inst in self.instances:
            if inst.exists():
                inst.setup_ldapi()
                inst.open()
                self._add_entities(inst, res)
        res.sort()
        return res

    def verify_entities(self, result, logmsg):
        """Verify that result is changed and entity list is the expected one."""
        entities = self._list_entities()
        self.log.info(f"Verify entities {logmsg}")
        self.log.info(f'entities:\n{entities}')
        self.log.info(f'expected entities:\n{self.expected_entities}')
        assert entities == self.expected_entities
        if self.changed:
            assert result['changed'] is self.changed


class _PresentHandler(_StateTestHandler):
    ACTIONS = [
        {
            'msg': 'after adding full instances inst1 and inst2 and agmt localhost.inst5.be501 and 502',
            'step': (3, 3, None, None, None),
        },
        {
            'msg': 'after adding agmt localhost.inst5.be503',
            'step': (4, 3, None, None, None),
        },
        {
            'msg': 'after adding an instance',
            'step': (4, 4, None, None, None),
        },
        {
            'msg': 'after adding a backend',
            'step': (4, 4, 4, None, None),
        },
        {
            'msg': 'after adding an agmt',
            'step': (4, 4, 4, 4, None),
        },
        {
            'msg': 'after adding an index',
            'step': (4, 4, 4, 4, 4),
        },
    ]

    def __init__(self):
        super().__init__()
        self.step = (3, 3, None, None, None)

    def _init_test(self):
        pass

    def get_range(self, itemidx, *args):
        if self.step is None:
            return range(1, 4)
        val = self.step[itemidx]
        if val:
            return range(1, val)
        for arg in args:
            if arg != 3:
                return range(1, 4)
        return range(1, 3)

    def run(self, action):
        self.log.info(f"Run ds389_server module {action['msg']}")
        self.reset_parameters()
        self.log.debug(f"RUN ACTION: step={self.step} args={self.args}")
        result = self.ansibletest.run_test_module( self.args )
        self.verify_entities(result, action['msg'])

    def end_test(self):
        self.log.info(f"Verify that ds389_server does not remove missing entities when 'present' is used.")
        # Save current state
        exp = self.expected_entities
        self.step = (3, 3, None, None, None)
        self.reset_parameters()
        self.expected_entities = exp
        self.log.info(f"Run ds389_server module with missing entries")
        result = self.ansibletest.run_test_module( self.args )
        self.verify_entities(result, "with missing entries")

class _AbsentHandler(_StateTestHandler):
    ACTIONS = [
        {
            'msg': 'after marking an index as absent',
            'avas': [('name', 'be303'), ('name', 'nsIdleTimeout')],
            'removed': [ 'index3_be303', ],
        },
        {
            'msg': 'after marking an agmt as absent',
            'avas': [('name', 'a3_be3_inst3'), ],
            'removed': [ 'a3_be3_inst3', ],
        },
        {
            'msg': 'after marking a backend as absent',
            'avas': [('name', 'be303'), ],
            'removed': [ 'a1_be3_inst3', 'a2_be3_inst3', 'be303',
                         'index1_be303', 'index2_be303',
                         'ds389_agmt_be303_localhost.inst5.be503',],
        },
        {
            'msg': 'after marking an instance as absent',
            'avas': [('name', 'inst3'), ],
            'removed': [ 'a1_be1_inst3', 'a1_be2_inst3',
                         'a2_be1_inst3', 'a2_be2_inst3',
                         'a3_be1_inst3', 'a3_be2_inst3',
                         'be301', 'be302',
                         'ds389_agmt_be301_localhost.inst5.be501',
                         'ds389_agmt_be302_localhost.inst5.be502',
                         'index1_be301', 'index1_be302',
                         'index2_be301', 'index2_be302',
                         'index3_be301', 'index3_be302',
                         'inst3', ],
        },
        {
            'msg': 'after marking a ds389_agmt as absent',
            'avas': [('fulltargetname', 'localhost.inst5.be503')],
            'removed': [ 'ds389_agmt_be103_localhost.inst5.be503',
                         'ds389_agmt_be203_localhost.inst5.be503', ],
        },
    ]

    def _init_test(self):
        self.log.info('Initialize 389ds instance using ds389_server module ')
        result = self.ansibletest.run_test_module( self.args )
        self.verify_entities(result, "after initialization")

    def run(self, action):
        self.log.info(f"Run ds389_server module {action['msg']}")
        tgt = self.get_target(self.args, action['avas'])
        for elmt in action['removed']:
            self.expected_entities.remove(elmt)
        tgt['state'] = 'absent'
        result = self.ansibletest.run_test_module( self.args )
        self.verify_entities(result, action['msg'])


class _UpdatedHandler(_StateTestHandler):
    ACTIONS = [
        {
            'msg': 'after removing an index',
            'avas': [('name', 'be202'), ('name', 'nsIdleTimeout')],
            'removed': [ 'index3_be202', ],
        },
        {
            'msg': 'after removing an agmt',
            'avas': [('name', 'a2_be2_inst2'), ],
            'removed': [ 'a2_be2_inst2', ],
        },
        {
            'msg': 'after removing a backend',
            'avas': [('name', 'be202'), ],
            'removed': [ 'a1_be2_inst2', 'a3_be2_inst2', 'be202',
                         'index1_be202', 'index2_be202',
                         'ds389_agmt_be202_localhost.inst5.be502'],
        },
        {
            'msg': 'after removing an instance',
            'avas': [('name', 'inst2'), ],
            'removed': [ 'a1_be1_inst2', 'a2_be1_inst2', 'a3_be1_inst2',
                         'a1_be3_inst2', 'a2_be3_inst2', 'a3_be3_inst2',
                         'be201', 'be203',
                         'ds389_agmt_be201_localhost.inst5.be501',
                         'index1_be201', 'index2_be201', 'index3_be201',
                         'index1_be203', 'index2_be203', 'index3_be203',
                         'inst2', ],
        },
        {
            'msg': 'after marking a ds389_agmt as absent',
            'avas': [('fulltargetname', 'localhost.inst5.be502')],
            'removed': [ 'ds389_agmt_be102_localhost.inst5.be502', ],
        },
    ]

    def _init_test(self):
        # Initialize 389ds instances  as if _AbsentHandler tests have run
        for action in _AbsentHandler.ACTIONS:
            tgt = self.get_target(self.args, action['avas'])
            tgt['state'] = 'absent'
            
            if tgt:
                self.remove_target(self.args, tgt)
            for elmt in action['removed']:
                self.expected_entities.remove(elmt)
        tgt = self.get_target(self.args,[('state', 'absent'),])
        while tgt:
            self.remove_target(tgt)
            tgt = self.get_target(self.args,[('state', 'absent'),])
        self.log.info('Initialize 389ds instance using ds389_server module')
        result = self.ansibletest.run_test_module( self.args )
        self.verify_entities(result, "after initialization")
        # Set state to updated.
        self.args["ANSIBLE_MODULE_ARGS"]["ds389"]["state"] = "updated"

    def run(self, action):
        self.log.info(f"Run ds389_server module {action['msg']}")
        tgt = self.get_target(self.args, action['avas'])
        for elmt in action['removed']:
            if elmt in self.expected_entities:
                self.expected_entities.remove(elmt)
            else:
                self.log.debug(f'_UpdatedHandler: Cannot remove expected_entities {elmt} in action {action}')
                self.ok = False
        self.remove_target(self.args, tgt)
        #self.log.debug(f'_UpdatedHandler.run: action={action} removed tgt = {tgt} self.args={self.args}')
        result = self.ansibletest.run_test_module( self.args )
        self.verify_entities(result, action['msg'])


@pytest.mark.parametrize(
    "testname",
    ( "present", "absent", "updated" )
)
def test_states(ansibletest, testname):
    """Test ds389_server module by changing state of various entities.
        Setup: None
        Step 1: Creates initial configuration
        Step 2: Run test actions then verify the entity lists:
               - add/remove an index
               - add/remove an agmt
               - add/remove a backend
               - add/remove an instance
               - add/remove a ds389_agmt
        Result 1: No error
        Result 2: No error
    """

    log = ansibletest.get_log(__name__)
    try:
        action_handler = _StateTestHandler.get_handler(testname)
        action_handler.init_test(ansibletest, log)
        for action in action_handler.ACTIONS:
            action_handler.run(action)
        action_handler.end_test()
        assert action_handler.ok
    except ( AssertionError, ldap.LDAPError ) as exc:
        action_handler.ansibletest.save_artefacts()
        raise exc
    finally:
        # Step 10: Perform cleanup
        action_handler.cleanup()
