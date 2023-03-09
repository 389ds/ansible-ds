#!/usr/bin/python3
# --- BEGIN COPYRIGHT BLOCK ---
# Copyright (C) 2022 Red Hat, Inc.
# All rights reserved.
#
# License: GPL (version 3 or any later version).
# See LICENSE for details.
# --- END COPYRIGHT BLOCK ---
#

"""Debugging tool used to convert yaml file to json.
    Usage: json2yaml.py json_file_path
    Generate a json_file_path.yml file containing the YAML

    Example: to collect ds state then replay then:
        echo '{ "ANSIBLE_MODULE_ARGS": { "prefix" : "'"$PREFIX"'" } }' | ds389_info.py > /tmp/o
        json2yaml.py /tmp/o
        dsupdate.py /tmp/o.yml
"""


import sys
import json
import yaml

class MyYamlObject(dict, yaml.YAMLObject):
    """Defines the entities objects associated with YAML tags.
        Note: is just a placeholder so that YAML tags get rightly displayed.
    """

    # handled normalized dict
    yaml_tag = 'tag:yaml.org,2002:map'

    def __init__(self, d):
        super().__init__()
        self.__dict__ = d
        d.pop('tag')

class ConfigRoot(MyYamlObject):
    """The Host entity placeholder."""
    yaml_tag = '!ds389Host'

class ConfigInstance(MyYamlObject):
    """The Instance entity placeholder."""
    yaml_tag = '!ds389Instance'

class ConfigBackend(MyYamlObject):
    """The Backend entity placeholder."""
    yaml_tag = '!ds389Backend'

class ConfigIndex(MyYamlObject):
    """The Index entity placeholder."""
    yaml_tag = '!ds389Index'

entities = { 'tag:yaml.org,2002:map' : MyYamlObject,
             '!ds389Host' : ConfigRoot ,
             '!ds389Instance' : ConfigInstance,
             '!ds389Backend' : ConfigBackend,
             '!ds389Index' : ConfigIndex
           }

# end of Config entities definition

def hook(_data):
    """Callback to compute object classes from json."""
    if isinstance(_data, dict):
        # handle Config entities
        if 'tag' in _data and  _data['tag'] in entities:
            return entities[_data['tag']](_data)
        # Handle fact result
        if 'my_useful_info' in _data:
            return hook(_data['my_useful_info'])
    return _data


F_IN_NAME = sys.argv[1]
F_OUT_NAME = F_IN_NAME.replace('.json','') + '.yml'
with open(F_IN_NAME, 'r', encoding='utf-8') as f_in:
    data = json.load(f_in, object_hook=hook)
    with open(F_OUT_NAME, 'w', encoding='utf-8') as f_out:
        yaml.dump(data, f_out, encoding='utf-8')
print(f'{sys.argv[0]}: created {F_OUT_NAME} file.')
