#!/usr/bin/python3

# --- BEGIN COPYRIGHT BLOCK ---
# Copyright (C) 2022 Red Hat, Inc.
# All rights reserved.
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# --- END COPYRIGHT BLOCK ---
#

###### GENERATE DOC FRAGMENT ###########
# Usage:  python gendoc.py doc  Generate the doc fragment about ds_server options
# Usage:  python gendoc.py spec  Generate the python file with the ansible parameter
#                                specification for ds_server module

import os
import re
import sys
from pathlib import Path
from inspect import cleandoc

p = str(Path(__file__).parent.parent)

sys.path += ( f"{p}/ansible_collections/ds/ansible_ds/plugins", )
from module_utils.dsentities import YAMLRoot
from module_utils.dsutil import setLogger, getLogger, log

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
            #  - ansible_collections/ds/ansible_ds/plugins/module_utils/dsentities.py
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

    def getext(entity, key, vdef):
        if key in entity.extension:
            return entity.extension[key]
        return vdef

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

    def prt_state(self, tab):
        # Print the 'state' option
        t1 = tab + self.tab
        t2 = t1 + self.tab

        self.prt("state", self.sd, tab)
        self.prt("description", Doc.STATE_DESC, t1)
        self.prt("type", "str", t1)
        self.prt("required", "false", t1)
        self.prt("default", "present", t1)
        self.prt("choices", self.sl, t1)
        self.prt_choices(Doc.STATE_CHOICES, t2)
        self.prt_item(self.el, t1)
        self.prt_item(self.ed, tab)

    def walk_entity(self, oclass, tab):
        entity = oclass(name='foo')
        t1 = tab + self.tab
        t2 = t1 + self.tab
        t3 = t2 + self.tab
        self.prt_state(tab)
        for option in entity.OPTIONS:
            self.prt(option.name, self.sd, tab)
            self.prt("description", f"{option.desc}.", t1)
            self.prt("required", Doc.getext(option, "required", "false"), t1)
            vdef = getattr(option, "vdef", None)
            if vdef is not None:
                self.prt("default", vdef, t1)
            choices = Doc.getext(option, "choice", None)
            if choices:
                self.prt("type", "str", t1)
                self.prt("choices", self.sl, t1)
                self.prt_choices(choices, t2)
                self.prt_item(self.el, t1)
            else:
                self.prt("type", Doc.getext(option, "type", "str"), t1)
            self.prt_item(self.ed, tab)

        for key,nclass in entity.CHILDREN.items():
            self.prt(key, self.sd, tab)
            self.prt("description", f"List of {key} options.", t1)
            self.prt("required", "false", t1)
            self.prt("type", "list", t1)
            self.prt("elements", "dict", t1)
            self.prt(self.suboptions, self.sd, t1)
            if key == "indexes":
                desc = "index"
            else:
                desc = str(key[0:-1])
            self.prt("name", self.sd, t2)
            self.prt("description", f"{desc}'s name.", t3)
            self.prt("type", "str", t3)
            self.prt("required", "true", t3)
            self.prt_item(self.ed, t2)
            self.walk_entity(nclass, t2)
            self.prt_item(self.ed, t1)
            self.prt_item(self.ed, tab)
        self.prt_meta(entity, tab)


    def generate(self, tab):
        # Generate ansible option doc from module classes
        print(cleandoc(self.header))
        self.walk_entity(YAMLRoot, tab + self.tab)
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
#  - ansible_collections/ds/ansible_ds/plugins/module_utils/dsentities.py
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
        if key == "required":
            if item == "true":
                item = "True"
            else:
                item = "False"
        delim = {"\n", "'", '"'}
        if item is None:
            if not skip:
                print(f"{tab}'{key}':")
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

if "doc" in sys.argv:
	Doc().generate("")
elif "spec" in sys.argv:
	Spec().generate("")
else:
    print("Usage: python gendoc.py doc|spec")
