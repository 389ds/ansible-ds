import pytest
import logging
import json
import sys
import os
import io
import os
import subprocess
from pathlib import Path


class AnsibleTest:
    def __init__(self, caplog):
        caplog.set_level(logging.INFO)
        if os.getenv('DEBUGGING', None):
            caplog.set_level(logging.DEBUG)
        self.caplog = caplog

    def getLog(self, name):
        self.log = logging.getLogger(name)
        self.test_module_name = name;
        self.log.info(f'set_test_name: name={name} __name__={__name__} __file__={__file__}')
        items = name.split('.')
        l = len(items)
        self.log.info(f'items={items} l={l}')
        module = f'{items[l-2]}.{items[l-1].replace("test_", "")}'
        path = f'{Path(__file__).parent.parent}/plugins'
        self.log.info(f'set_test_name: path={path} module={module}')
        self.path = path
        self.module = module
        if not path in sys.path:
            sys.path.append(path)
        return self.log

    def runModule(self, stdinText):
        stdinText = str(stdinText).replace("'", '"')
        cmd = f'{self.path}/{self.module.replace(".","/")}.py'
        self.log.info(f'Running module {cmd} with stdin: {stdinText}')
        os.environ['PYTHONPATH'] = ":".join(sys.path)
        # should spawn a subprocess rather than importing the module and calls run_module
        # (because run_module calls sys.exit which break pytest framework)
        result = subprocess.run([cmd], encoding='utf8', text=True, input=stdinText, capture_output=True, check=False)
        self.log.info(f'Module {cmd} returned stdin: {result.stdout} stderr: {result.stderr}')
        assert result.returncode==0 or result.returncode==1
        self.result = json.loads(result.stdout)
        return self.result

    def listInstances(self):
        return [ instance['name'] for instance in result['my_useful_info']['instances'] ]

    def getInstanceAttr(self, instname, attr):
        return self.result['my_useful_info']['instances'][instname][attr]

    def listBackends(self, instname):
        backends = self.getInstanceAttr(instname, 'backends')
        return [ backends.keys() ]

    def getBackendAttr(self, instname, bename, attr):
        backends = self.getInstanceAttr(instname, 'backends')
        return backends[bename][attr]

@pytest.fixture(scope='function')
def ansibletest(caplog):
    return AnsibleTest(caplog)

# Init the variables needed to use prefixed build
def initPrefix():
    def isPrefix(dir):
        try:
            return os.path.isfile(f'{dir}/sbin/ns-slapd') and os.path.isdir(f'{dir}/etc/dirsrv')
        except PermissionError:
            return False

    def setPrefix(dir):
        log = logging.getLogger(__name__)
        os.environ['PREFIX'] = dir
        lp = f'{dir}/lib/python3.9/site-packages'
        # sys.path is reset by the framework so let save the lib389 path 
        # in an environment variable that will be set in the testcase
        # before importing lib389.topologies
        os.environ['LIB389PATH'] = lp
        log.error(f'PREFIX={dir} LIB389PATH={lp}')
        os.environ['ASAN_OPTIONS'] = 'exitcode=0 '

    if 'LIB389PATH' in os.environ:
        # setPrefix was already called ==> we are done.
        return
    if 'PREFIX' in os.environ:
        dir = os.environ['PREFIX']
        setPrefix(dir)
        return
    if os.getuid == 0:
        setPrefix('/usr')
        return
    lookup = [ ( Path(__file__).parent.parent.parent.parent.parent, 'ansible-ds'), ]
    while len(lookup) > 0:
        dir, ignore = lookup.pop(0)
        if dir == '/':
            setPrefix('/usr')
            return
        if isPrefix(dir):
            setPrefix(dir)
            return
        try:
            for f in os.listdir(dir):
                if os.path.isdir(f'{dir}/{f}') and f != ignore:
                    lookup.append( ( f'{dir}/{f}', None) )
        except PermissionError:
            pass
        if ignore != None:
            lookup.append( ( str(Path(dir).parent), str(Path(dir).name)) )

# Initialize the prefix before collecting the files.
def pytest_sessionstart(session):
    initPrefix()

