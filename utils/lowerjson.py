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

def transform(adata):
    """Convert recursively all dict keys in adata."""
    if isinstance(adata, dict):
        if 'ANSIBLE_MODULE_ARGS' in adata:
            return { 'ANSIBLE_MODULE_ARGS': transform(adata['ANSIBLE_MODULE_ARGS']) }
        return { key.lower():transform(val) for key,val in adata.items() }
    if isinstance(adata, list):
        return [ transform(val) for val in adata ]
    return adata


F_IN_NAME = sys.argv[1]
F_OUT_NAME = f'lower_{F_IN_NAME}'
with open(F_IN_NAME, 'r', encoding='utf-8') as f_in:
    data = json.load(f_in)
data = transform(data)
with open(F_OUT_NAME, 'w', encoding='utf-8') as f_out:
    f_out.write(json.dumps(data))
