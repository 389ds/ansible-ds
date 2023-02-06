389 Directory Server Ansible collection tests
==========================

This directory contains the test framework

Note: tests are either:
    - test_xxxx methods within python file or 
    - test_xxxx.yml playbooks

They can be run:
    - directly from pytest. (Usefull when wanting to run a single test: i.e pytest $PWD -k test_gather_dsinst_info.yml)
    - through ansible-test (i.e: ansible-test units)

========================
Installation instruction are described in ../../../../README.md (See the section about testing)
