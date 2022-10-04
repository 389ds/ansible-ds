#!/usr/bin/python3
# --- BEGIN COPYRIGHT BLOCK ---
# Copyright (C) 2022 Red Hat, Inc.
# All rights reserved.
#
# License: GPL (version 3 or any later version).
# See LICENSE for details.
# --- END COPYRIGHT BLOCK ---
#

#
# Usage: json2yaml.py json_file_path
#  Generate a json_file_path.yml file containing the YAML
#
# Example: to collect ds state then replay then:
#   echo '{ "ANSIBLE_MODULE_ARGS": { "prefix" : "'"$PREFIX"'" } }' | ds389_info.py > /tmp/o
#   j2y.py /tmp/o
#   dsupdate.py /tmp/o.yml


import sys
import os
import json
import yaml

# Lets define the entities objects associated with YAML tags
# Note that is just a placeholder so that YAML tags get rightly displayed.
class MyYamlObject(dict, yaml.YAMLObject):
    # handled normalized dict
    yaml_tag = u'tag:yaml.org,2002:map'

    def __init__(self, d):
        self.__dict__ = d
        d.pop('tag')

class ConfigRoot(MyYamlObject):
    yaml_tag = u'!ds389Host'

class ConfigInstance(MyYamlObject):
    yaml_tag = u'!ds389Instance'

class ConfigBackend(MyYamlObject):
    yaml_tag = u'!ds389Backend'

class ConfigIndex(MyYamlObject):
    yaml_tag = u'!ds389Index'

entities = { u'tag:yaml.org,2002:map' : MyYamlObject,
             u'!ds389Host' : ConfigRoot ,
             u'!ds389Instance' : ConfigInstance,
             u'!ds389Backend' : ConfigBackend,
             u'!ds389Index' : ConfigIndex
           }

# end of Config entities definition

# Callback to compute object classes from json
def hook(d):
    if isinstance(d, dict):
        # handle Config entities
        if 'tag' in d and  d['tag'] in entities:
            return entities[d['tag']](d)
        # Handle fact result
        if 'my_useful_info' in d:
            return hook(d['my_useful_info'])
    return d


fin_name = sys.argv[1]
fout_name = fin_name.replace('.json','') + '.yml'
with open(fin_name, 'r') as fin:
    data = json.load(fin, object_hook=hook)
    with open(fout_name, 'w') as fout:
        yaml.dump(data, fout, encoding='utf-8')
print(f'{sys.argv[0]}: created {fout_name} file.')



