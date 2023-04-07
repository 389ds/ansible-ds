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
from shutil import copytree, rmtree
from pwd import getpwuid
from tempfile import mkdtemp
import glob
import json
import logging
import shutil
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
    with open('/tmp/atlog.txt', 'at', encoding='utf-8') as file:
        file.write(f'{msg}\n')

class IniFileConfig:
    """This class retrieve the ini file options out of the best section and export them in os.environ.

       The  ini file is ~/.ds389-ansible.ini
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
    INIFILE = f'{HOME}/.ds389-ansible.ini'
    if os.getuid() == 0:
        ANSIBLE_PLAYBOOK  = "/usr/bin/ansible-playbook"
        ANSIBLE_HOME  = f"{HOME}/.ansible"
    else:
        ANSIBLE_PLAYBOOK  = f"{HOME}/.local/bin/ansible-playbook"
        ANSIBLE_HOME  = f"{HOME}/.ansible"

    def __init__(self):
        self.config = ConfigParser(interpolation=ExtendedInterpolation())
        self.config.read(f'{IniFileConfig.HOME}/.ds389-ansible.ini')
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

    def export_all(self):
        """Put all param from the best section in the environment"""
        if self.best_section:
            for var in IniFileConfig.EXPORTS:
                try:
                    val = self.config.get(self.best_section, var)
                    if val:
                        _setenv(var, val)
                except NoOptionError:
                    pass
        _setenv('ASAN_OPTIONS', 'exitcode=0')

    @staticmethod
    def get_path(relpath):
        """return the full path from a path that is relative to the galaxy collection source root (i.e: ..)."""
        return f"{IniFileConfig.BASE}/{relpath}"

class PlaybookTestEnv:
    """This provides contains method to run test playbooks."""

    VAULT_FILE = 'vars/vault.yml'
    VAULT_PW_FILE = 'vault_pass.txt'
    VAULT_PASSWORD = 'A very big secret!'
    # Test value of some encryted variables
    SECRETS = {
        'ds389_server_rootpw' : 'secret12',
        'ds389_server_replmgrpw' : 'repl-secret',
    }

    @staticmethod
    def _init_vault(vault_dir):
        """Generates the vault password file and vault file for the playbook test
        """

        vault_pw_file = f'{vault_dir}/{PlaybookTestEnv.VAULT_PW_FILE}'
        vault_file = Path(f'{vault_dir}/{PlaybookTestEnv.VAULT_FILE}')
        os.makedirs(vault_file.parent, mode=0o700, exist_ok=True)
        # Generate vault password file
        with open(vault_pw_file, 'wt', encoding='utf-8') as file:
            file.write(PlaybookTestEnv.VAULT_PASSWORD)
            file.write('\n')
        _setenv("ANSIBLE_VAULT_PASSWORD_FILE", vault_pw_file)
        # Generate vault file
        with open(vault_file, 'wt', encoding='utf-8') as file:
            for key,val in PlaybookTestEnv.SECRETS.items():
                cmd =  ( 'ansible-vault', 'encrypt_string', '--stdin-name', key )
                result = subprocess.run(cmd, encoding='utf8', check=False, text=True, input=val, capture_output=True)
                file.write(result.stdout)
                file.write('\n')

    @staticmethod
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
        self.docker = False
        repodir = Path(IniFileConfig.BASE).parent.parent.parent
        tarballpath = Path(f'{repodir}/ansible_ds.tgz')
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
            subprocess.run(('ansible-galaxy', 'collection', 'install', '-p', self.pbdir, tarballpath),
                           encoding='utf8', check=True, text=True)
            self.skip = False
            _setenv('ANSIBLE_LIBRARY', f'{self.pbdir}/ansible_collections/ds389/ansible_ds')
            # Create the vars/vault.yml encrypted variable file
            PlaybookTestEnv._init_vault(self.pbdir)
        # setup the envirnment variables
        self.debugging = os.getenv('DEBUGGING', None)
        if self.dir:
            # Generate a file to set up the environment when debugging
            # (Usefull only if PLAYBOOKHOME is set in ~/.389ds-ansible.ini)
            with open(f'{self.pbdir}/env.sh', 'wt', encoding='utf-8') as file:
                file.write('#set up environment to run playbook directly.\n')
                file.write('# . ./env.sh\n')
                for key,val in _the_env.items():
                    file.write(f'export {key}="{val}"\n')
                # Then update the collection from the repository
                file.write(f'cd {repodir}\n')
                file.write('make clean all\n')
                file.write(f'cd {self.pbdir}\n')
                file.write('/bin/rm -rf ansible_collections\n')
                file.write(f'ansible-galaxy collection install --force -p {self.pbdir} {tarballpath}\n')
        # Check if docker is available
        try:
            result = subprocess.run(['docker', 'info'], capture_output=True, encoding='utf8', check=False)
            if result.returncode == 0 and 'Server:' in result.stdout:
                self.docker = True
        except FileNotFoundError:
            pass

    def run(self, testitem, playbook):
        """Run a playbook
        """

        if self.skip:
            assert not 'Aborting test Failed to create playbook test environment (conftest.py)'
            # pytest.skip('Failed to create playbook test environment (conftest.py)')
            # return
        cmd = [ IniFileConfig.ANSIBLE_PLAYBOOK, ]
        if self.debugging:
            cmd.append( '-vvvvv' )
        cmd_dir = self.pbdir
        pb_fullname = str(playbook)
        pb_name = f'{playbook.name}'
        if '/inventory/' in pb_fullname:
            # Lets run directly the playbook from the test directory
            cmd_dir, pb_name = os.path.split(pb_fullname)
            # Add inventory and vault options
            cmd = cmd + [ '-i', 'inventory', '--vault-password-file', f'{cmd_dir}/../vault.pw' ]
            # Verify docker presence.
            if not self.docker:
                pytest.skip("Inventory tests requires 'docker'")
                return

        cmd.append(pb_name)
        PlaybookTestEnv._remove_all_instances()
        result = subprocess.run(cmd, capture_output=True, encoding='utf-8', cwd=cmd_dir) # pylint: disable=subprocess-run-check
        testitem.add_report_section("call", "stdout", result.stdout)
        testitem.add_report_section("call", "stderr", result.stderr)
        testitem.add_report_section("call", "cwd", cmd_dir)
        if not self.debugging:
            PlaybookTestEnv._remove_all_instances()
        if result.returncode != 0:
            self.testfailed = True
            print(f'ERROR: Command {cmd} run in {cmd_dir} failed with return code {result.returncode}', file=sys.stderr)
            print(f'STDOUT is: {result.stdout}', file=sys.stderr)
            print(f'STDERR is: {result.stderr}', file=sys.stderr)

            raise AssertionError(f"ansible-playbook failed: return code is {result.returncode}")

    def cleanup(self):
        """Cleanup after running last playbook"""
        if self.pbh:
            return
        if self.dir and not (self.debugging and self.testfailed):
            rmtree(self.dir)


_CONFIG = IniFileConfig()
_CONFIG.export_all()
_PLAYBOOK = PlaybookTestEnv()
lib389path = os.getenv('LIB389PATH')
pypath = os.getenv('PYTHONPATH')
if lib389path and not lib389path in pypath:
    os.environ['PYTHONPATH'] = f'{lib389path}:{pypath}'


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

    def get_log(self, name):
        """Return the current logger."""
        self.log = logging.getLogger(name)
        self.test_module_name = name
        self.log.info('set_test_name: name={%s} __name__={%s} __file__={%s}', name, __name__, __file__)
        items = name.split('.')
        nbi = len(items)
        module = f'{items[nbi-2]}.{items[nbi-1].replace("test_", "")}'
        path = _CONFIG.get_path('plugins')
        self.module = module
        if not path in sys.path:
            sys.path.append(path)
        artefact_root = f"/workspace/assets/{self.module}"
        shutil.rmtree(artefact_root, ignore_errors=True)
        return self.log

    def _log_stdio(self, name, result):
        """Log strings from subprocess.run result associated with stdio members."""
        text = getattr(result, name, None)
        if text:
            for line in text.split('\n'):
                self.log.info('  %s: %s', name.upper(), line)

    def _log_run_result(self, result):
        """Displays subprocess.run result in a pretty way."""
        self.log.info('Running: %s', str(result.args))
        self.log.info('  ReturnCode: %d', result.returncode)
        self._log_stdio('stdin', result)
        self._log_stdio('stdout', result)
        self._log_stdio('stderr', result)

    def run(self, cmd):
        """Run a sub command."""
        result = subprocess.run(cmd, capture_output=True, encoding='utf-8' ) # pylint: disable=subprocess-run-check
        self._log_run_result(result)
        result.check_returncode()

    def run_test_module(self, stdin_text):
        """Run the ansible module associated with the test module."""
        cmd = _CONFIG.get_path('plugins/modules/ds389_module.py')
        stdin_text = json.dumps(stdin_text)
        self.log.info('Running module {%s} with stdin: %s', cmd, stdin_text)
        os.environ['PYTHONPATH'] = ":".join(sys.path)
        # should spawn a subprocess rather than importing the module and calls run_module
        # (because run_module calls sys.exit which break pytest framework)
        result = subprocess.run([cmd], encoding='utf8', text=True, input=stdin_text, capture_output=True, check=False) # pylint: disable=subprocess-run-check
        self._log_run_result(result)
        assert result.returncode in (0, 1)
        try:
            self.result = json.loads(result.stdout)
            self.log.info('Module %s result is %s', cmd, self.result)
            return self.result
        except json.JSONDecodeError:
            self.log.error('Module %s: failed to decode module output: {result}')
            raise AssertionError(f'Module %s returned valid output') from None

    def save_artefacts(self):
        """Save error logs and dse.ldif in /workspace/assets."""
        if not os.path.isdir("/workspace"):
            return
        artefact_root = f"/workspace/assets/{self.module}"
        os.makedirs(artefact_root, mode=0o750, exist_ok=True)
        prefix = ""
        if "PREFIX" in _the_env:
            prefix = _the_env["PREFIX"]
            pattern = f'{prefix}/etc/dirsrv/slapd-*'
            for inst in [ inst.rsplit('/',1)[1] for inst in glob.glob(i) ]:
                shutil.copytree(f'{prefix}/etc/dirsrv/var/log/dirsrv/{inst}', f'{artefact_root}/{inst}')
            shutil.copyfile(f'{prefix}/etc/dirsrv/{inst}/dse.ldif', f'{artefact_root}/{inst}/dse.ldif')

    # pylint: disable-next=R0201
    def lookup(self, obj, name):
        """Search key (name) in listed maps (in obj list)."""
        # Defined as a function rather than a static method
        # Because classes defined in conftest are a bit cumbersome to refer within pytests
        # So lets use a workaround to avoid R0201 lint warning
        self.get_log("foo")
        for item in obj:
            if item['name'].lower() == name.lower():
                return item
        raise KeyError(f'No children entity named {name} in {obj}.')

    def list_instances(self):
        """return the list of ds389 instances (extracted from runModule result)."""
        return [ instance['name'] for instance in self.result['ansible_facts']['ds389_server_instances'] ]

    def get_instance_attr(self, instname, attr):
        """Return an instance attribute (extracted from runModule result)."""
        return self.lookup(self.result['ansible_facts']['ds389_server_instances'], instname)[attr]

    def list_backends(self, instname):
        """return the list of backends of a ds389 instances (extracted from runModule result)."""
        backends = self.get_instance_attr(instname, 'backends')
        return [ backends.keys() ]

    def get_backend_attr(self, instname, bename, attr):
        """return a backend attribute (extracted from runModule result)."""
        backends = self.get_instance_attr(instname, 'backends')
        return self.lookup(backends, bename)[attr]


@pytest.fixture(scope='function')
def ansibletest(caplog):
    """Provide an AnsibleTest instance."""
    return AnsibleTest(caplog)

def pytest_sessionfinish():
    """Pytest pytest_sessionfinish hook."""
    _PLAYBOOK.cleanup()


### Lets run test_*.yml playbooks

# This code is derivated from 'Working with non-python tests'
# But unfortunatly the API depends of pytest version.
# cf https://docs.pytest.org/en/7.2.x/example/nonpython.html#a-basic-example-for-specifying-tests-in-yaml-files
# cf https://docs.pytest.org/en/6.2.x/example/nonpython.html#a-basic-example-for-specifying-tests-in-yaml-files

# And of course version checking confuses pylint
# pylint: disable=E1125


class PlaybookItem6(pytest.Item):
    """Helper class for pytest_collect_file hook that run yaml tests."""

    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.pytest_file = name

    def runtest(self):
        """Run a test playbook."""
        _PLAYBOOK.run(self, self.pytest_file)


class PlaybookFile6(pytest.File):
    """Helper class for pytest_collect_file hook that run yaml tests."""

    def collect(self):
        """Helper for pytest_collect_file hook."""
        yield PlaybookItem6.from_parent(self, name=str(self.fspath))


class PlaybookItem7(pytest.Item):
    """Helper class for pytest_collect_file hook that run yaml tests."""

    def __init__(self, pytest_file, parent):
        super().__init__(pytest_file.name, parent)
        self.pytest_file = pytest_file

    def runtest(self):
        """Run a test playbook."""
        _PLAYBOOK.run(self, self.pytest_file.path)


class PlaybookFile7(pytest.File):
    """Helper class for pytest_collect_file hook that run yaml tests."""

    def collect(self):
        """Helper for pytest_collect_file hook."""
        yield PlaybookItem7.from_parent(parent=self, pytest_file=self)


pytestMajorVersion = int(pytest.__version__.split('.', maxsplit=1)[0])
if pytestMajorVersion == 6:
    def pytest_collect_file(parent, path):
        """Pytest pytest_collect_file hook that handles yaml files."""
        if path.ext == ".yml" and path.basename.startswith("test_"):
            return PlaybookFile6.from_parent(parent, fspath=path)
        return None
elif pytestMajorVersion >= 7:
    def pytest_collect_file(parent, file_path):
        """Pytest pytest_collect_file hook that handles yaml files."""
        if file_path.suffix == ".yml" and file_path.name.startswith("test_"):
            return PlaybookFile7.from_parent(parent, path=file_path)
        return None
else:
    raise NotImplementedError(f"pytest version {pytestMajorVersion}.x is not supported. Need 6.x or 7.x")
