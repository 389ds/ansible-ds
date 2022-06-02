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
from shutil import copyfile, rmtree
from pwd import getpwuid
from tempfile import mkdtemp
import json
import logging
import subprocess
import pytest

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
        All above variables defaults to None

    """

    BASE = str(Path(__file__).parent.parent)  # the galaxy collection source root path
    EXPORTS = ( 'PREFIX',  'LIB389PATH', 'DEBUGGING', 'BASE' ) # Variables to export from ini file
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
                        os.environ[var] = val
                except NoOptionError as e:
                    pass
        os.environ['ASAN_OPTIONS'] = 'exitcode=0 '

    @staticmethod
    def getPath(relpath):
        """return the full path from a path that is relative to the galaxy collection source root (i.e: ..)."""
        return f"{IniFileConfig.BASE}/{relpath}"

class PlaybookTestEnv:
    """This provides contains method to run test playbooks."""

    def __init__(self):
        self.testfailed = False
        self.skip = True
        self.dir = None
        tarballpath = Path(f'{Path(IniFileConfig.BASE).parent.parent}/ds-ansible_ds-1.0.0.tar.gz')
        if tarballpath.exists():
            # Create a working directory for running the playbooks
            self.dir = mkdtemp()
            self.pbdir = f'{self.dir}/playbooks'
            os.makedirs(self.pbdir, mode=0o750)
            # Install our ansible  collection
            subprocess.run(('ansible-galaxy', 'collection', 'install', '-p', self.pbdir, tarballpath), encoding='utf8', text=True)
            self.skip = False
            os.environ['ANSIBLE_LIBRARY'] = f'{self.pbdir}/ansible_collections/ds/ansible_ds'
        # setup the envirnment variables
        lp = os.getenv("LIB389PATH", None)
        pp = os.getenv("PYTHONPATH", "")
        self.debugging = os.getenv('DEBUGGING', None)
        if lp and lp not in pp.split(':'):
            os.environ["PYTHONPATH"] = f"{lp}:{pp}"

    def run(self, testitem, playbook):
        if self.skip:
            pytest.skip('Failed to create playbook test environment (conftest.py)')
            return
        pb_name = f'{playbook.name}'
        pb = Path(f'{self.pbdir}/{pb_name}')
        copyfile(playbook, pb)
        if self.debugging:
            cmd = (IniFileConfig.ANSIBLE_PLAYBOOK, '-vvvvv', pb_name)
        else:
            cmd = (IniFileConfig.ANSIBLE_PLAYBOOK, pb_name)
        result = subprocess.run(cmd, capture_output=True, encoding='utf-8', cwd=self.pbdir) # pylint: disable=subprocess-run-check
        testitem.add_report_section("call", "stdout", result.stdout)
        testitem.add_report_section("call", "stderr", result.stderr)
        testitem.add_report_section("call", "cwd", self.pbdir)
        if result.returncode != 0:
            self.testfailed = True
            raise AssertionError(f"ansible-playbook failed: return code is {result.returncode}")

    def cleanup(self):
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


    def listInstances(self):
        """return the list of ds389 instances (extracted from runModule result)."""
        return [ instance['name'] for instance in self.result['my_useful_info']['instances'] ]

    def getInstanceAttr(self, instname, attr):
        """Return an instance attribute (extracted from runModule result)."""
        return self.result['my_useful_info']['instances'][instname][attr]

    def listBackends(self, instname):
        """return the list of backends of a ds389 instances (extracted from runModule result)."""
        backends = self.getInstanceAttr(instname, 'backends')
        return [ backends.keys() ]

    def getBackendAttr(self, instname, bename, attr):
        """return a backend attribute (extracted from runModule result)."""
        backends = self.getInstanceAttr(instname, 'backends')
        return backends[bename][attr]


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
