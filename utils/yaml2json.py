#!/usr/bin/python3
# --- BEGIN COPYRIGHT BLOCK ---
# Copyright (C) 2022 Red Hat, Inc.
# All rights reserved.
#
# License: GPL (version 3 or any later version).
# See LICENSE for details.
# --- END COPYRIGHT BLOCK ---
#

"""Debugging tool used to convert json file to yaml.
    Usage: yaml2json.py yaml_file_path
           Generate a yaml_file_path.json file containing the JSON.
"""

import sys
import json
import yaml

class MyClassObject(yaml.YAMLObject):
    """Defines the entities objects associated with YAML tags.
        Note: is just a placeholder so that YAML tags get rightly displayed.
    """

    yaml_loader = yaml.SafeLoader

    def to_obj(self):
        """Convert object into dict."""
        _dict = { "tag" : self.yaml_tag }
        for key, val in self.__dict__.items():
            print(f"{key}->{val}")
            _dict[key] = val
        return _dict

class ConfigHost(MyClassObject):
    """The Host entity placeholder."""
    yaml_tag = '!ds389Host'

class ConfigInstance(MyClassObject):
    """The Instance entity placeholder."""
    yaml_tag = '!ds389Instance'

class ConfigBackend(MyClassObject):
    """The Backend entity placeholder."""
    yaml_tag = '!ds389Backend'

class ConfigIndex(MyClassObject):
    """The Index entity placeholder."""
    yaml_tag = '!ds389Index'

class MyJsonEncoder(json.JSONEncoder):
    """A custom json encoder."""
    def default(self, o):
        print(f"obj={o}")
        if isinstance(o, MyClassObject):
            return o.to_obj()
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, o)




F_IN_NAME = sys.argv[1]
F_OUT_NAME = F_IN_NAME.replace('.yml','') + '.json'
with open(F_IN_NAME, 'r', encoding='utf-8') as f_in:
    data = yaml.safe_load(f_in)
    with open(F_OUT_NAME, 'w', encoding='utf-8') as f_out:
        f_out.write(json.dumps(data, cls=MyJsonEncoder))
print(f'{sys.argv[0]}: created {F_OUT_NAME} file.')
