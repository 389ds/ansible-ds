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
# Usage: j2y.py json_file_path
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

class MyClassObject(yaml.YAMLObject):
    yaml_loader = yaml.SafeLoader

    def toObj(self):
        dict = { "tag" : self.yaml_tag }
        for key, val in self.__dict__.items():
            print(f"{key}->{val}")
            dict[key] = val
        return dict

class YAMLHost(MyClassObject):
    yaml_tag = u'!ds389Host'

class YAMLInstance(MyClassObject):
    yaml_tag = u'!ds389Instance'

class YAMLBackend(MyClassObject):
    yaml_tag = u'!ds389Backend'

class YAMLIndex(MyClassObject):
    yaml_tag = u'!ds389Index'

class MyJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        print(f"obj={obj}")
        if isinstance(obj, MyClassObject):
            return obj.toObj()
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)




fin_name = sys.argv[1]
fout_name = fin_name.replace('.yml','') + '.json'
with open(fin_name, 'r') as fin:
    data = yaml.safe_load(fin)
    print(f'data: {data}')
    with open(fout_name, 'w') as fout:
        fout.write(json.dumps(data, cls=MyJsonEncoder))
print(f'{sys.argv[0]}: created {fout_name} file.')



