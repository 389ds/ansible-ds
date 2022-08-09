# --- BEGIN COPYRIGHT BLOCK ---
# Copyright (C) 2022 Red Hat, Inc.
# All rights reserved.
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# --- END COPYRIGHT BLOCK ---
#
#

"""This module contains the pytest helpers"""

import os
import sys
from configparser import ConfigParser, ExtendedInterpolation, NoOptionError
from pathlib import Path
from shutil import copyfile, copytree, rmtree
from pwd import getpwuid
from tempfile import mkdtemp
import json
import logging
import subprocess
import pytest
from lib389.utils import get_instance_list
from lib389 import DirSrv

_the_env = {}

def _setenv(var, val):
    """Helper to set environment and keep a local copy."""
    os.environ[var] = val
    _the_env[var] = val

def _mylog(msg):
    """Helper to incondionnaly log a message in a test."""
    with open('/tmp/atlog.txt', 'at') as f:
        f.write(f'{msg}\n')

class IniFileConfig:
    """This class retrieve the ini file options out of the best section and export them in os.environ.

       The  ini file is ~/.389ds-ansible.ini
       Sections names are directory path
        the section with the longest path that starts this file path is considered as the best one.

        Interpolation supported:
          ${HOME}  for home directory
          ${BASE}  the directory containing ansible_ds sub-directory (computed from this file path)

        Option (or Variable) supported:
          PREFIX            where ds is installed
          LIB389PATH        where to look up for the lib389
          DEBUGGING         if set then verbose debugging mode is turned on (and some cleanup task are not done)
          PLAYBOOKHOME      where the playbook are run. 
        All above variables defaults to None

    """

    BASE = str(Path(__file__).parent.parent)  # the galaxy collection source root path
    EXPORTS = ( 'PREFIX',  'LIB389PATH', 'DEBUGGING', 'PLAYBOOKHOME', 'BASE' ) # Variables to export from ini file
    HOME = str(getpwuid(os.getuid()).pw_dir) # Home directory
    INIFILE = f'{HOME}/.389ds-ansible.ini'
    if os.getuid() == 0:
        ANSIBLE_PLAYBOOK  = "/usr/bin/ansible-playbook"
        ANSIBLE_HOME  = f"{HOME}/.ansible"
    else:
        ANSIBLE_PLAYBOOK  = f"{HOME}/.local/bin/ansible-playbook"
        ANSIBLE_HOME  = f"{HOME}/.ansible"

    def __init__(self):
        self.config = ConfigParser(interpolation=ExtendedInterpolation())
        self.config.read(f'{IniFileConfig.HOME}/.389ds-ansible.ini')
        # Set default section for extended interpolation
        self.config['DEFAULT'] = { 'BASE': IniFileConfig.BASE, 'HOME' : IniFileConfig.HOME }
        # initialize logging
        self.log = logging.getLogger(__name__)

        # determine which section to use for this test
        self.best_section = None
        for section in sorted(self.config.sections(), key=lambda x: -len(x)):
            if IniFileConfig.BASE.startswith(section):
                self.best_section = section
                break

    def exportAll(self):
        """Put all param from the best section in the environment"""
        if self.best_section:
            for var in IniFileConfig.EXPORTS:
                try:
                    val = self.config.get(self.best_section, var)
                    if val:
                        _setenv(var, val)
                except NoOptionError as e:
                    pass
        _setenv('ASAN_OPTIONS', 'exitcode=0')

    @staticmethod
    def getPath(relpath):
        """return the full path from a path that is relative to the galaxy collection source root (i.e: ..)."""
        return f"{IniFileConfig.BASE}/{relpath}"

class PlaybookTestEnv:
    """This provides contains method to run test playbooks."""

    VAULT_FILE = 'vars/vault.yml'
    VAULT_PW_FILE = 'vault_pass.txt'
    VAULT_PASSWORD = 'A very big secret!'
    # Test value of some encryted variables
    SECRETS = {
        'dsserver_rootpw' : 'secret12',
        'dsserver_replmgrpw' : 'repl-secret',
    }

    def _init_vault(vault_dir):
        """Generates the vault password file and vault file for the playbook test
        """

        vault_pw_file = f'{vault_dir}/{PlaybookTestEnv.VAULT_PW_FILE}'
        vault_file = Path(f'{vault_dir}/{PlaybookTestEnv.VAULT_FILE}')
        os.makedirs(vault_file.parent, mode=0o700, exist_ok=True)
        # Generate vault password file
        with open(vault_pw_file, 'wt') as f:
            f.write(PlaybookTestEnv.VAULT_PASSWORD)
            f.write('\n')
        _setenv("ANSIBLE_VAULT_PASSWORD_FILE", vault_pw_file)
        # Generate vault file
        with open(vault_file, 'wt') as f:
            for key,val in PlaybookTestEnv.SECRETS.items():
                cmd =  ( 'ansible-vault', 'encrypt_string', '--stdin-name', key )
                result = subprocess.run(cmd, encoding='utf8', text=True, input=val, capture_output=True)
                f.write(result.stdout)
                f.write('\n')

    def _remove_all_instances():
        for serverid in get_instance_list():
            inst = DirSrv()
            inst.local_simple_allocate(serverid)
            inst.stop()
            inst.delete()

    def __init__(self):
        self.testfailed = False
        self.skip = True
        self.dir = None
        self.pbh = None
        acdir = Path(IniFileConfig.BASE).parent.parent
        repodir = acdir.parent
        tarballpath = Path(f'{acdir}/ds-ansible_ds-1.0.0.tar.gz')
        if tarballpath.exists():
            # Create a working directory for running the playbooks
            self.pbh = os.getenv('PLAYBOOKHOME', None)
            if self.pbh:
                self.dir = self.pbh
                rmtree(self.dir, ignore_errors=True)
            else:
                self.dir = mkdtemp()
            self.pbdir = f'{self.dir}/playbooks'
            # Copy the test playbooks
            copytree(f'{IniFileConfig.BASE}/tests/playbooks', f'{self.dir}/playbooks')
            # Install our ansible  collection
            subprocess.run(('ansible-galaxy', 'collection', 'install', '-p', self.pbdir, tarballpath), encoding='utf8', text=True)
            self.skip = False
            _setenv('ANSIBLE_LIBRARY', f'{self.pbdir}/ansible_collections/ds/ansible_ds')
            # Create the vars/vault.yml encrypted variable file
            PlaybookTestEnv._init_vault(self.pbdir)
        # setup the envirnment variables
        lp = os.getenv("LIB389PATH", None)
        pp = os.getenv("PYTHONPATH", "")
        self.debugging = os.getenv('DEBUGGING', None)
        if lp and lp not in pp.split(':'):
            _setenv("PYTHONPATH", f"{lp}:{pp}")
        if self.dir:
            # Generate a file to set up the environment when debugging
            # (Usefull only if PLAYBOOKHOME is set in ~/.389ds-ansible.ini)
            with open(f'{self.pbdir}/env.sh', 'wt') as f:
                f.write(f'#set up environment to run playbook directly.\n')
                f.write(f'# . ./env.sh\n')
                for key,val in _the_env.items():
                    f.write(f'export {key}="{val}"\n')
                # Then update the collection from the repository
                f.write(f'cd {repodir}\n')
                f.write('make clean all\n')
                f.write(f'cd {self.pbdir}\n')
                f.write('/bin/rm -rf ansible_collections\n')
                f.write(f'ansible-galaxy collection install --force -p {self.pbdir} {tarballpath}\n')

    def run(self, testitem, playbook):
        if self.skip:
            pytest.skip('Failed to create playbook test environment (conftest.py)')
            return
        pb_name = f'{playbook.name}'
        if self.debugging:
            cmd = (IniFileConfig.ANSIBLE_PLAYBOOK, '-vvvvv', pb_name)
        else:
            cmd = (IniFileConfig.ANSIBLE_PLAYBOOK, pb_name)
        PlaybookTestEnv._remove_all_instances()
        result = subprocess.run(cmd, capture_output=True, encoding='utf-8', cwd=self.pbdir) # pylint: disable=subprocess-run-check
        testitem.add_report_section("call", "stdout", result.stdout)
        testitem.add_report_section("call", "stderr", result.stderr)
        testitem.add_report_section("call", "cwd", self.pbdir)
        if not self.debugging:
            PlaybookTestEnv._remove_all_instances()
        if result.returncode != 0:
            self.testfailed = True
            raise AssertionError(f"ansible-playbook failed: return code is {result.returncode}")

    def cleanup(self):
        if self.pbh:
            return
        if self.dir and not (self.debugging and self.testfailed):
            rmtree(self.dir)


_CONFIG = IniFileConfig()
_CONFIG.exportAll()
_PLAYBOOK = PlaybookTestEnv()


class AnsibleTest:
    """ instances of this class is generated by ansibletest fixture.
        it provides initialization and some utilies used by the tests.
    """

    # pylint: disable=too-many-instance-attributes
    # Should not limit variables in this class as it is a placeholder
    # could use ad  dict but that will needlessly complexify the code

    def __init__(self, caplog):
        self.debugging = False
        self.test_module_name = None
        self.caplog = caplog
        self.result = None
        self.log_info = None
        self.log = None
        self.module = None
        caplog.set_level(logging.INFO)
        if os.getenv('DEBUGGING', None):
            caplog.set_level(logging.DEBUG)
            self.debugging = True

    def getLog(self, name):
        """Return the current logger."""
        self.log = logging.getLogger(name)
        self.test_module_name = name
        self.log.info('set_test_name: name={%s} __name__={%s} __file__={%s}', name, __name__, __file__)
        items = name.split('.')
        nbi = len(items)
        module = f'{items[nbi-2]}.{items[nbi-1].replace("test_", "")}'
        path = _CONFIG.getPath('plugins')
        self.module = module
        if not path in sys.path:
            sys.path.append(path)
        return self.log


    def _logStdio(self, name, result):
        """Log strings from subprocess.run result associated with stdio members."""
        text = getattr(result, name, None)
        if text:
            for line in text.split('\n'):
                self.log.info('  %s: %s', name.upper(), line)


    def _logRunResult(self, result):
        """Displays subprocess.run result in a pretty way."""
        self.log.info('Running: %s', str(result.args))
        self.log.info('  ReturnCode: %d', result.returncode)
        self._logStdio('stdin', result)
        self._logStdio('stdout', result)
        self._logStdio('stderr', result)


    def run(self, cmd):
        """Run a sub command."""
        result = subprocess.run(cmd, capture_output=True, encoding='utf-8' ) # pylint: disable=subprocess-run-check
        self._logRunResult(result)
        result.check_returncode()


    def runModule(self, cmd, stdin_text):
        """Run a specific ansible module."""
        stdin_text = json.dumps(stdin_text)
        self.log.info('Running module {%s} with stdin: %s', cmd, stdin_text)
        os.environ['PYTHONPATH'] = ":".join(sys.path)
        # should spawn a subprocess rather than importing the module and calls run_module
        # (because run_module calls sys.exit which break pytest framework)
        result = subprocess.run([cmd], encoding='utf8', text=True, input=stdin_text, capture_output=True, check=False) # pylint: disable=subprocess-run-check
        self._logRunResult(result)
        assert result.returncode in (0, 1)
        self.log.info(f'Module {cmd} result is {result.stdout}')
        self.result = json.loads(result.stdout)
        return self.result


    def runTestModule(self, stdin_text):
        """Run the ansible module associated with the test module."""
        cmd = _CONFIG.getPath(f'plugins/{self.module.replace(".","/")}.py')
        return self.runModule(cmd, stdin_text)

    def lookup(self, obj, name):
        for item in obj:
            if item['name'] == name:
                return item
        raise KeyError(f'No children entity named {name} in {obj.name}.')


    def listInstances(self):
        """return the list of ds389 instances (extracted from runModule result)."""
        return [ instance['name'] for instance in self.result['my_useful_info']['dsserver_instances'] ]

    def getInstanceAttr(self, instname, attr):
        """Return an instance attribute (extracted from runModule result)."""
        return self.lookup(self.result['my_useful_info']['dsserver_instances'], instname)[attr]

    def listBackends(self, instname):
        """return the list of backends of a ds389 instances (extracted from runModule result)."""
        backends = self.getInstanceAttr(instname, 'backends')
        return [ backends.keys() ]

    def getBackendAttr(self, instname, bename, attr):
        """return a backend attribute (extracted from runModule result)."""
        backends = self.getInstanceAttr(instname, 'backends')
        return self.lookup(backends, bename)[attr]


@pytest.fixture(scope='function')
def ansibletest(caplog):
    """Provide an AnsibleTest instance."""
    return AnsibleTest(caplog)

def pytest_sessionfinish():
    _PLAYBOOK.cleanup()

### Lets run test_*.yml playbooks

class PlaybookItem(pytest.Item):
    def __init__(self, pytest_file, parent):
        super(PlaybookItem, self).__init__(pytest_file.name, parent)
        self.pytest_file = pytest_file

    def runtest(self):
        _PLAYBOOK.run(self, self.pytest_file.path)

class PlaybookFile(pytest.File):
    def collect(self):
        yield PlaybookItem.from_parent(parent=self, pytest_file=self)

def pytest_collect_file(parent, file_path):
    if file_path.suffix == ".yml" and file_path.name.startswith("test_"):
        return PlaybookFile.from_parent(parent, path=file_path)
