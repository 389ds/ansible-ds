#!/usr/bin/python3

# --- BEGIN COPYRIGHT BLOCK ---
# Copyright (C) 2022 Red Hat, Inc.
# All rights reserved.
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# --- END COPYRIGHT BLOCK ---
#

###### GENERATE DOC FRAGMENT ###########
# Usage:  python gendoc.py doc  Generate the doc fragment about ds389_server options
# Usage:  python gendoc.py spec  Generate the python file with the ansible parameter
#                                specification for ds389_server module

import os
import re
import glob
import sys
from pathlib import Path
from inspect import cleandoc

p = str(Path(__file__).parent.parent)

sys.path += ( f"{p}/ansible_collections/ds389/ansible_ds/plugins", )
from module_utils.ds389_entities import ConfigRoot
from module_utils.ds389_util import setLogger, getLogger, log

class Doc:
    STATE_DESC = """'state' option determines how the other option are handled:
                     If 'present' then specified options are added.
                     If 'absent' then specified options are removed.
                     If 'overwritten' then specified options are added and non specified options are removed."""

    STATE_CHOICES = ( "present", "absent", "overwritten" )


    def __init__(self):
        self.header = """
            # -*- coding: utf-8 -*-

            # Authors:
            #   Pierre Rogier <progier@redhat.com>
            #
            # Copyright (C) 2022  Red Hat
            # see file 'COPYING' for use and warranty information
            #
            # This program is free software; you can redistribute it and/or modify
            # it under the terms of the GNU General Public License as published by
            # the Free Software Foundation, either version 3 of the License, or
            # (at your option) any later version.
            #
            # This program is distributed in the hope that it will be useful,
            # but WITHOUT ANY WARRANTY; without even the implied warranty of
            # MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
            # GNU General Public License for more details.
            #
            # You should have received a copy of the GNU General Public License
            # along with this program.  If not, see <http://www.gnu.org/licenses/>.

            # *** WARNING! DO NOT MODIFY THIS FILE. ***
            # This file is generated from following files:
            #  - utils/gendoc.py
            #  - ansible_collections/ds389/ansible_ds/plugins/module_utils/ds389_entities.py
            # by using 'make gensrc'

            from __future__ import (absolute_import, division, print_function)

            __metaclass__ = type


            class ModuleDocFragment(object):  # pylint: disable=R0205,R0903
                DOCUMENTATION = r"\"\"
            options:
        """

        self.footer = '"""'
        self.tab = "  "
        self.sd = None
        self.ed = None
        self.sl = None
        self.el = None
        self.suboptions = "suboptions"
        setLogger(__file__, None)

    def prt(self, key, item, tab, skip=False):
        if item is None:
            if not skip:
                print(f"{tab}{key}:")
        else:
            print(f"{tab}{key}: {item}")

    def prt_item(self, item, tab):
        if item:
            print(f"{tab}{item}")

    def prt_choices(self, choices, tab):
        for v in choices:
            print(f"{tab} - {v}")

    def prt_meta(self, entity, tab):
        pass

    def sortweight(self, option):
        if option.name in ('name', 'state'):
            res = 'A'
        else:
            res = 'B'
        if option.required:
            res += 'C'
        else:
            res += 'D'
        res += option.name
        return res

    def sortOptions(self, keys):
        s = sorted( [ (self.sortweight(key), key) for key in keys])
        return [ k[1] for k in s ]

    def _actionOption(self, option, tab):
        t1 = tab + self.tab
        t2 = t1 + self.tab
        t3 = t2 + self.tab
        self.prt(option.name, self.sd, tab)
        self.prt("description", f"{option.desc}.", t1)
        self.prt("required", option.required, t1)
        vdef = getattr(option, "vdef", None)
        if vdef is not None:
            self.prt("default", vdef, t1)
        if option.choice:
            self.prt("type", "str", t1)
            self.prt("choices", self.sl, t1)
            self.prt_choices(option.choice, t2)
            self.prt_item(self.el, t1)
        else:
            self.prt("type", option.type, t1)
        self.prt_item(self.ed, tab)
    
    def _actionEntity(self, name, nclass, tab):
        t1 = tab + self.tab
        t2 = t1 + self.tab
        t3 = t2 + self.tab
        self.prt(name, self.sd, tab)
        self.prt("description", f"List of {name} options.", t1)
        self.prt("required", "False", t1)
        self.prt("type", "list", t1)
        self.prt("elements", "dict", t1)
        self.prt(self.suboptions, self.sd, t1)
        if name == "indexes":
            desc = "index"
        else:
            desc = str(name[0:-1])
        self.prt("name", self.sd, t2)
        self.prt("description", f"{desc}'s name.", t3)
        self.prt("type", "str", t3)
        self.prt("required", "True", t3)
        self.prt_item(self.ed, t2)
        self.walk_entity(nclass, t2)
        self.prt_item(self.ed, t1)
        self.prt_item(self.ed, tab)

    def walk_entity(self, oclass, tab, actionOption="default", actionEntity="default"):
        t1 = tab + self.tab
        t2 = t1 + self.tab
        if actionOption == "default":
            # set default action
            actionOption = self._actionOption
        if actionEntity == "default":
            # set default action
            actionEntity = self._actionEntity
        if actionOption == "None":
            # set no action
            actionOption = None
        if actionEntity == "None":
            # set no action
            actionEntity = None
        entity = oclass(name='foo')
        if actionOption:
            for option in self.sortOptions(entity.OPTIONS):
                actionOption(option, tab)
        for key in sorted(entity.CHILDREN.keys()):
            nclass = entity.CHILDREN[key]
            if actionEntity:
                actionEntity(key, nclass, tab)
            else:
                self.walk_entity(nclass, t2, actionOption=actionOption, actionEntity=actionEntity)
        self.prt_meta(entity, tab)


    def generate(self, tab):
        # Generate ansible option doc from module classes
        print(cleandoc(self.header))
        self.walk_entity(ConfigRoot, tab + self.tab)
        print(cleandoc(self.footer))

class Spec(Doc):
    def __init__(self):
        super(Spec, self).__init__()
        self.header = """#!/usr/bin/python3

# --- BEGIN COPYRIGHT BLOCK ---
# Copyright (C) 2022 Red Hat, Inc.
# All rights reserved.
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# --- END COPYRIGHT BLOCK ---
#

# *** WARNING! DO NOT MODIFY THIS FILE. ***
# This file is generated from following files:
#  - utils/gendoc.py
#  - ansible_collections/ds389/ansible_ds/plugins/module_utils/ds389_entities.py
# by using 'make gensrc'

CONTENT_OPTIONS = {"""
        self.footer = "}"
        self.tab = "    "
        self.sd = "{"
        self.ed = "},"
        self.sl = "("
        self.el = "),"
        self.suboptions = "options"
        self.dd = '"""'

    def prt(self, key, item, tab, skip=False):
        delim = {"\n", "'", '"'}
        if item is None:
            if not skip:
                print(f"{tab}'{key}':")
        elif isinstance(item, bool):
            print(f"{tab}'{key}': {item},")
        elif item in ("True", "False"):
            print(f"{tab}'{key}': {item},")
        elif item in ("{", "(", "["):
            print(f"{tab}'{key}': {item}")
        elif not set(item).isdisjoint(delim):
            print(f"{tab}'{key}': {self.dd}{item}{self.dd},")
        else:
            print(f"{tab}'{key}': '{item}',")

    def prt_choices(self, choices, tab):
        for v in choices:
            print(f"{tab}'{v}',")

    def prt_meta(self, entity, tab):
        t1 = tab + self.tab
        for k,d in entity.OPTIONS_META.items():
            self.prt(k, "[", tab)
            for i in d:
                print(f"{t1}{str(i)},")
            print(f"{tab}],")

class Readme:
    def __init__(self):
        pass

    def cat(self, filename, fout):
        with open(filename, 'r') as f:
            for line in f:
                fout.write(line)

    def parseLine(self, line, fout):
        res = re.match('@@@INSERT *([^ ]*)', line)
        if res:
            name = res.group(1).strip()
            self.cat(f'{p}/ansible_collections/ds389/ansible_ds/playbooks/{name}', fout)
        elif re.match('@@@DESC', line):
            Desc(fout).generate("")
        else:
            fout.write(line)
            
    def generate(self):
        for path in glob.iglob(f"{p}/ansible_collections/ds389/ansible_ds/**/*.tmpl", recursive=True):
            with open(path, 'r') as fin:
                with open(path.replace('tmpl', 'md'), 'w') as fout:
                    for line in fin:
                        self.parseLine(line, fout)


class Desc(Doc):
    """ Generation entity tree and options table in human readable markdown format """

    def classname(nclass):
        res = re.match(".*Config([^']*)", str(nclass))
        return res.group(1).strip()

    def __init__(self, fout=sys.stdout):
        super(Desc, self).__init__()
        self.fout = fout
        self.silent = False

    def print(self, msg):
        if not self.silent or self.fout == sys.stdout:
            print(msg, file=self.fout)

    def printEntity(self, name, nclass, tab):
        t1 = tab + self.tab
        t2 = t1 + self.tab
        self.print(f"{tab}- {name}: A list of {nclass}")
        self.walk_entity(nclass, t2, actionOption=None, actionEntity=self.printEntity)

    def printEntityHeader(self, name, nclass, tab):
        t1 = tab + self.tab
        t2 = t1 + self.tab
        self.silent = False
        self.print(f"\n## {Desc.classname(nclass)}")
        self.print("| Option | Required | Type | Description | Comment |")
        self.print("| - | -  | -  | -  | -  |")
        self.walk_entity(nclass, t2, actionOption=self.printOptions, actionEntity=self.printEntityHeader)

    def printOptions(self, option, tab):
        comment = ""
        if option.choice:
            comment += f"Value may be one of: {option.choice}. "
        if option.vdef:
            comment += f"Default value is: {option.vdef}." 
        self.print(f"| {option.name} | {option.required} | {option.type} | {option.desc} | {comment} |")

    def generate(self, tab):
        # Generate ansible option doc from module classes
        self.silent = True
        self.print("# Entities tree\n - Root")
        self.silent = False
        self.walk_entity(ConfigRoot, tab + self.tab, actionOption=None, actionEntity=self.printEntity)
        self.print("\n# Options per entities")
        self.silent = True 
        self.print("## Root")
        self.print("| Option | Required | Type | Description | Comment |")
        self.print("| - | - | - | - | - |")
        self.walk_entity(ConfigRoot, tab + self.tab, actionOption=self.printOptions, actionEntity=self.printEntityHeader)



if "doc" in sys.argv:
	Doc().generate("")
elif "spec" in sys.argv:
	Spec().generate("")
elif "desc" in sys.argv:
	Desc().generate("")
elif "readme" in sys.argv:
	Readme().generate()
else:
    print("Usage: python gendoc.py doc|spec|readme|desc")
