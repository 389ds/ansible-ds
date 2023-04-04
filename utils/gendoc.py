#!/usr/bin/python3

# --- BEGIN COPYRIGHT BLOCK ---
# Copyright (C) 2022 Red Hat, Inc.
# All rights reserved.
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# --- END COPYRIGHT BLOCK ---
#


"""This module parse dsentities_options.py to generate different files:
    Usage:  python gendoc.py doc    Generate the doc fragment about ds389_server options.
            python gendoc.py spec   Generate the python file with the ansible parameters
                                    specification for ds_server module.
            python gendoc.py desc   Generate human readable markdown file containing
                                    the entities tree and options table
            python gendoc.py readme	Generate the playbook readme.
"""

import re
import glob
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from inspect import cleandoc

WORKSPACE_DIR = str(Path(__file__).parent.parent)

sys.path += ( f"{WORKSPACE_DIR}/ansible_collections/ds389/ansible_ds/plugins", )
from module_utils.ds389_util import init_log
from module_utils.ds389_entities import ConfigRoot

class AbstractAnsibleDsParser(ABC):
    """Abstract class to avoid pylint error about unused arguments."""

    @abstractmethod
    def print_item(self, item, tab):
        """Print a line about single data."""

    @abstractmethod
    def print_choices(self, choices, tab):
        """Print lines to describe a choice."""

    @abstractmethod
    def print_meta(self, entity, tab):
        """Print lines about entity metadata."""

    @abstractmethod
    def print_msg(self, msg):
        """Print a single data."""

    @abstractmethod
    def print(self, key, item, tab, skip=False):
        """Print a line about key+value."""

    @abstractmethod
    def walk_entity(self, oclass, tab, action_option="default", action_entity="default"):
        """The dsentities_options.py entity parser."""

    @abstractmethod
    def generate(self, tab):
        """Generate ansible option doc from module classes."""



class Doc(AbstractAnsibleDsParser):
    """This class contains the source parser and initialize its members to generate the doc fragment."""
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
        self.start_dict = None
        self.end_dict = None
        self.start_list = None
        self.end_list = None
        self.suboptions = "suboptions"

    def print(self, key, item, tab, skip=False):
        if item is None:
            if not skip:
                print(f"{tab}{key}:")
        else:
            print(f"{tab}{key}: {item}")

    def print_item(self, item, tab):
        """Print a line about single data."""
        if item:
            print(f"{tab}{item}")

    def print_choices(self, choices, tab):
        for val in choices:
            print(f"{tab} - {val}")

    def print_msg(self, msg):
        """Print a single data."""

    def print_meta(self, entity, tab):
        """Print lines about entity metadata."""

    def print_action_option(self, option, tab):
        """Hanles action options."""

        tab1 = tab + self.tab
        tab2 = tab1 + self.tab
        self.print(option.name, self.start_dict, tab)
        self.print("description", f"{option.desc}.", tab1)
        self.print("required", option.required, tab1)
        vdef = getattr(option, "vdef", None)
        if vdef is not None:
            self.print("default", vdef, tab1)
        if option.choice:
            self.print("type", "str", tab1)
            self.print("choices", self.start_list, tab1)
            self.print_choices(option.choice, tab2)
            self.print_item(self.end_list, tab1)
        else:
            self.print("type", option.otype, tab1)
        self.print_item(self.end_dict, tab)

    def print_action_entity(self, name, nclass, tab):
        """Handles action entity."""
        tab1 = tab + self.tab
        tab2 = tab1 + self.tab
        tab3 = tab2 + self.tab
        self.print(name, self.start_dict, tab)
        self.print("description", f"List of {name} options.", tab1)
        self.print("required", "False", tab1)
        self.print("type", "list", tab1)
        self.print("elements", "dict", tab1)
        self.print(self.suboptions, self.start_dict, tab1)
        if name == "indexes":
            desc = "index"
        else:
            desc = str(name[0:-1])
        self.print("name", self.start_dict, tab2)
        self.print("description", f"{desc}'s name.", tab3)
        self.print("type", "str", tab3)
        self.print("required", "True", tab3)
        self.print_item(self.end_dict, tab2)
        self.walk_entity(nclass, tab2)
        self.print_item(self.end_dict, tab1)
        self.print_item(self.end_dict, tab)

    def walk_entity(self, oclass, tab, action_option="default", action_entity="default"):
        tab1 = tab + self.tab
        tab2 = tab1 + self.tab
        if action_option == "default":
            # set default action
            action_option = self.print_action_option
        if action_entity == "default":
            # set default action
            action_entity = self.print_action_entity
        if action_option == "None":
            # set no action
            action_option = None
        if action_entity == "None":
            # set no action
            action_entity = None
        entity = oclass(name='foo')
        if action_option:
            for option in sorted(entity.OPTIONS):
                action_option(option, tab)
        for key in sorted(entity.CHILDREN.keys()):
            if key == 'ds389_agmts':
                continue
            nclass = entity.CHILDREN[key]
            if action_entity:
                action_entity(key, nclass, tab)
            else:
                self.walk_entity(nclass, tab2, action_option=action_option, action_entity=action_entity)
        self.print_meta(entity, tab)

    def generate(self, tab):
        print(cleandoc(self.header))
        self.walk_entity(ConfigRoot, tab + self.tab)
        print(cleandoc(self.footer))


class Spec(Doc):
    """This class reuses the source parser from Doc class but initialize its member to generate the spec file."""
    def __init__(self):
        super().__init__()
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

# pylint: disable=line-too-long

"\""This module contains the part of the ds389_module argspec (below ds389 dict)."\""

CONTENT_OPTIONS = {"""
        self.footer = "}"
        self.tab = "    "
        self.start_dict = "{"
        self.end_dict = "},"
        self.start_list = "("
        self.end_list = "),"
        self.suboptions = "options"
        self.doc_delim = '"""'

    def print(self, key, item, tab, skip=False):
        delim = {"\n", "'", '"'}
        if item is None:
            if not skip:
                print(f"{tab}'{key.lower()}':")
        elif isinstance(item, bool):
            print(f"{tab}'{key.lower()}': {item},")
        elif item in ("True", "False"):
            print(f"{tab}'{key.lower()}': {item},")
        elif item in ("{", "(", "["):
            print(f"{tab}'{key.lower()}': {item}")
        elif not set(item).isdisjoint(delim):
            print(f"{tab}'{key.lower()}': {self.doc_delim}{item}{self.doc_delim},")
        else:
            print(f"{tab}'{key.lower()}': '{item}',")

    def print_choices(self, choices, tab):
        for val in choices:
            print(f"{tab}'{val}',")

    def print_meta(self, entity, tab):
        tab1 = tab + self.tab
        for key,data in entity.OPTIONS_META.items():
            self.print(key, "[", tab)
            for val in data:
                print(f"{tab1}{str(val)},")
            print(f"{tab}],")

class Readme:
    """This class contains the code to generate the playbook Readme file."""
    def __init__(self):
        self.template = f"{WORKSPACE_DIR}/ansible_collections/ds389/ansible_ds/**/*.tmpl"
        self.encoding = 'utf-8'

    def cat(self, filename, fout):
        """Concanates filename into fout file."""
        with open(filename, 'r', encoding=self.encoding) as file:
            for line in file:
                fout.write(line)

    def parse_line(self, line, fout):
        """Parse Readme template line and expands the varaible."""
        res = re.match('@@@INSERT *([^ ]*)', line)
        if res:
            name = res.group(1).strip()
            self.cat(f'{WORKSPACE_DIR}/ansible_collections/ds389/ansible_ds/playbooks/{name}', fout)
        elif re.match('@@@DESC', line):
            Desc(fout).generate("")
        else:
            fout.write(line)

    def generate(self):
        """Generate the readme file."""

        for path in glob.iglob(self.template, recursive=True):
            with open(path, 'r', encoding=self.encoding) as fin:
                with open(path.replace('tmpl', 'md'), 'w', encoding=self.encoding) as fout:
                    for line in fin:
                        self.parse_line(line, fout)


class Desc(Doc):
    """ Generation entity tree and options table in human readable markdown format """

    @staticmethod
    def classname(nclass):
        """Get object classname."""
        res = re.match(".*Config([^']*)", str(nclass))
        return res.group(1).strip()

    def __init__(self, fout=sys.stdout):
        super().__init__()
        self.fout = fout
        self.silent = False

    def print_msg(self, msg):
        """Print a single data."""
        if not self.silent or self.fout == sys.stdout:
            print(msg, file=self.fout)

    def print_entity(self, name, nclass, tab):
        """Print an entity."""
        tab1 = tab + self.tab
        tab2 = tab1 + self.tab
        self.print_msg(f"{tab}- {name}: A list of {nclass}")
        self.walk_entity(nclass, tab2, action_option=None, action_entity=self.print_entity)

    def print_entity_header(self, _name, nclass, tab):
        """Print an entity header callback."""
        tab1 = tab + self.tab
        tab2 = tab1 + self.tab
        self.silent = False
        self.print_msg(f"\n## {Desc.classname(nclass)}")
        self.print_msg("| Option | Required | Type | Description | Comment |")
        self.print_msg("| - | -  | -  | -  | -  |")
        self.walk_entity(nclass, tab2, action_option=self.print_options, action_entity=self.print_entity_header)

    def print_options(self, option, _tab):
        """Print an option callback."""
        comment = ""
        if option.choice:
            comment += f"Value may be one of: {option.choice}. "
        if option.vdef:
            comment += f"Default value is: {option.vdef}."
        self.print_msg(f"| {option.name} | {option.required} | {option.otype} | {option.desc} | {comment} |")

    def generate(self, tab):
        """Generate ansible option doc from module classes."""
        self.silent = True
        self.print_msg("# Entities tree\n - Root")
        self.silent = False
        self.walk_entity(ConfigRoot, tab + self.tab, action_option=None, action_entity=self.print_entity)
        self.print_msg("\n# Options per entities")
        self.silent = True
        self.print_msg("## Root")
        self.print_msg("| Option | Required | Type | Description | Comment |")
        self.print_msg("| - | - | - | - | - |")
        self.walk_entity(ConfigRoot, tab + self.tab, action_option=self.print_options, action_entity=self.print_entity_header)



init_log('gendoc')
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
