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
#   echo '{ "ANSIBLE_MODULE_ARGS": { "prefix" : "'"$PREFIX"'" } }' | ds_info.py > /tmp/o
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

class YAMLRoot(MyYamlObject):
    yaml_tag = u'!ds389Host'

class YAMLInstance(MyYamlObject):
    yaml_tag = u'!ds389Instance'

class YAMLBackend(MyYamlObject):
    yaml_tag = u'!ds389Backend'

class YAMLIndex(MyYamlObject):
    yaml_tag = u'!ds389Index'

entities = { u'tag:yaml.org,2002:map' : MyYamlObject,
             u'!ds389Host' : YAMLRoot ,
             u'!ds389Instance' : YAMLInstance,
             u'!ds389Backend' : YAMLBackend,
             u'!ds389Index' : YAMLIndex
           }

# end of YAML entities definition

# Callback to compute object classes from json
def hook(d):
    if isinstance(d, dict):
        # handle YAML entities
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



