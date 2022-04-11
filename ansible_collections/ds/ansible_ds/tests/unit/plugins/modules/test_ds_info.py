
import os
import sys

# Set PYTHONPATH to be able to find lib389 (computed within conftest seesion initialization hook)
sys.path.insert(0, os.environ['LIB389PATH'])

from lib389.topologies import topology_m2 as topo_m2

def test_info1(topo_m2, ansibletest, monkeypatch):
    log = ansibletest.getLog(__name__)
    result = ansibletest.runModule( { "ANSIBLE_MODULE_ARGS": { "prefix" : os.getenv('PREFIX','') } } )
    log.info(f'result={result}')
    assert 'my_useful_info' in result
    assert ansibletest.getInstanceAttr('supplier1', 'name') == 'supplier1'
    assert ansibletest.getInstanceAttr('supplier2', 'name') == 'supplier2'
    assert ansibletest.getBackendAttr('supplier1', 'userroot', 'name') == 'userroot'
    assert ansibletest.getBackendAttr('supplier2', 'userroot', 'name') == 'userroot'



    #                                                          {"changed": false, "original_message": "/home/progier/sb/i111/tst/ci-install", "message": "goodbye", "my_useful_info": {"tag": "!ds389Host", "name": "linux.home", "state": "present", "instances": [{"tag": "!ds389Instance", "name": "supplier2", "state": "present", "backends": [{"tag": "!ds389Backend", "name": "userroot", "state": "present", "require_index": "off", "suffix": "dc=example,dc=com"}], "started": true, "dseMods": {"tag": "tag:yaml.org,2002:map", "cn=config": {"tag": "tag:yaml.org,2002:map", "deleteValue": {"tag": "tag:yaml.org,2002:map", "nsslapd-security": [null]}}, "cn=encryption,cn=config": {"tag": "tag:yaml.org,2002:map", "deleteValue": {"tag": "tag:yaml.org,2002:map", "CACertExtractFile": [null]}}, "cn=rfc 2829 u syntax,cn=mapping,cn=sasl,cn=config": {"tag": "tag:yaml.org,2002:map", "addEntry": {"tag": "tag:yaml.org,2002:map", "objectClass": ["top", "nsSaslMapping"], "cn": ["rfc 2829 u syntax"], "nsSaslMapRegexString": ["^u:\\(.*\\)"], "nsSaslMapBaseDNTemplate": ["dc=example,dc=com"], "nsSaslMapFilterTemplate": ["(uid=\\1)"]}}, "cn=uid mapping,cn=mapping,cn=sasl,cn=config": {"tag": "tag:yaml.org,2002:map", "addEntry": {"tag": "tag:yaml.org,2002:map", "objectClass": ["top", "nsSaslMapping"], "cn": ["uid mapping"], "nsSaslMapRegexString": ["^[^:@]+$"], "nsSaslMapBaseDNTemplate": ["dc=example,dc=com"], "nsSaslMapFilterTemplate": ["(uid=&)"]}}}, "port": "39002", "secure_port": "63702", "nsslapd_directory": "/home/progier/sb/i111/tst/ci-install/var/lib/dirsrv/slapd-supplier2/db"}, {"tag": "!ds389Instance", "name": "supplier1", "state": "present", "backends": [{"tag": "!ds389Backend", "name": "userroot", "state": "present", "require_index": "off", "suffix": "dc=example,dc=com"}], "started": true, "dseMods": {"tag": "tag:yaml.org,2002:map", "cn=config": {"tag": "tag:yaml.org,2002:map", "deleteValue": {"tag": "tag:yaml.org,2002:map", "nsslapd-security": [null]}}, "cn=encryption,cn=config": {"tag": "tag:yaml.org,2002:map", "deleteValue": {"tag": "tag:yaml.org,2002:map", "CACertExtractFile": [null]}}, "cn=rfc 2829 u syntax,cn=mapping,cn=sasl,cn=config": {"tag": "tag:yaml.org,2002:map", "addEntry": {"tag": "tag:yaml.org,2002:map", "objectClass": ["top", "nsSaslMapping"], "cn": ["rfc 2829 u syntax"], "nsSaslMapRegexString": ["^u:\\(.*\\)"], "nsSaslMapBaseDNTemplate": ["dc=example,dc=com"], "nsSaslMapFilterTemplate": ["(uid=\\1)"]}}, "cn=uid mapping,cn=mapping,cn=sasl,cn=config": {"tag": "tag:yaml.org,2002:map", "addEntry": {"tag": "tag:yaml.org,2002:map", "objectClass": ["top", "nsSaslMapping"], "cn": ["uid mapping"], "nsSaslMapRegexString": ["^[^:@]+$"], "nsSaslMapBaseDNTemplate": ["dc=example,dc=com"], "nsSaslMapFilterTemplate": ["(uid=&)"]}}}, "port": "39001", "secure_port": "63701", "nsslapd_directory": "/home/progier/sb/i111/tst/ci-install/var/lib/dirsrv/slapd-supplier1/db"}], "prefix": "/home/progier/sb/i111/tst/ci-install"}, "invocation": {"module_args": {"prefix": "/home/progier/sb/i111/tst/ci-install"}}}
