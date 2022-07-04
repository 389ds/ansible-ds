# -*- coding: utf-8 -*-

# Authors:
#   Pierre Rogier <progier@redhat.com>
#
# Copyright (C) 2022  Red Hat
# see file 'COPYING' for use and warranty information
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# *** WARNING! DO NOT MODIFY THIS FILE. ***
# This file is generated from following files:
#  - utils/gendoc.py
#  - ansible_collections/ds/ansible_ds/plugins/module_utils/dsentities.py
# by using 'make gensrc'

from __future__ import (absolute_import, division, print_function)

__metaclass__ = type


class ModuleDocFragment(object):  # pylint: disable=R0205,R0903
    DOCUMENTATION = r"""
options:
  state:
    description: If 'state' is 'absent' then all instances are removed.
    required: False
    default: present
    type: str
    choices:
       - present
       - updated
       - absent
  prefix:
    description: 389 Directory Service non standard installation path.
    required: False
    type: str
  instances:
    description: List of instances options.
    required: False
    type: list
    elements: dict
    suboptions:
      name:
        description: instance's name.
        type: str
        required: True
      state:
        description: Indicate whether the instance is added(present), modified(updated), or removed(absent).
        required: False
        default: present
        type: str
        choices:
           - present
           - updated
           - absent
      backup_dir:
        description: Directory containing the backup files.
        required: False
        type: str
      bin_dir:
        description: Directory containing ns-slapd binary. Only set this parameter in a development environment.
        required: False
        type: str
      cert_dir:
        description: Directory containing the NSS certificate databases.
        required: False
        type: str
      config_dir:
        description: Sets the configuration directory of the instance (containing the dse.ldif file).
        required: False
        type: str
      data_dir:
        description: Sets the location of Directory Server shared static data. Only set this parameter in a development environment.
        required: False
        type: str
      db_dir:
        description: Sets the database directory of the instance.
        required: False
        type: str
      db_home_dir:
        description: Sets the memory-mapped database files location of the instance.
        required: False
        type: str
      db_lib:
        description: Select the database implementation library.
        required: False
        type: str
        choices:
           - bdb
           - mdb
      full_machine_name:
        description: The fully qualified hostname (FQDN) of this system. When installing this instance with GSSAPI authentication behind a load balancer, set this parameter to the FQDN of the load balancer and, additionally, set "strict_host_checking" to "false".
        required: False
        type: str
      group:
        description: Sets the group name the ns-slapd process will use after the service started.
        required: False
        type: str
      initconfig_dir:
        description: Sets the directory of the operating system's rc configuration directory. Only set this parameter in a development environment.
        required: False
        type: str
      inst_dir:
        description: Directory containing instance-specific scripts.
        required: False
        type: str
      instance_name:
        description: Sets the name of the instance..
        required: False
        type: str
      ldapi:
        description: Sets the location of socket interface of the Directory Server.
        required: False
        type: str
      ldif_dir:
        description: Directory containing the the instance import and export files.
        required: False
        type: str
      lib_dir:
        description: Sets the location of Directory Server shared libraries. Only set this parameter in a development environment.
        required: False
        type: str
      local_state_dir:
        description: Sets the location of Directory Server variable data. Only set this parameter in a development environment.
        required: False
        type: str
      lock_dir:
        description: Directory containing the lock files.
        required: False
        type: str
      nsslapd_backend_opt_level:
        description: This parameter can trigger experimental code to improve write performance.
        required: False
        default: 1
        type: int
      nsslapd_directory:
        description: Default database directory.
        required: False
        default: {prefix}/var/lib/dirsrv/slapd-{instname}/db
        type: str
      nsslapd_exclude_from_export:
        description: list of attributes that are not exported.
        required: False
        default: entrydn entryid dncomp parentid numSubordinates tombstonenumsubordinates entryusn
        type: str
      nsslapd_idlistscanlimit:
        description: The maximum number of entries a given index key may refer before the index is handled as unindexed..
        required: False
        default: 4000
        type: int
      nsslapd_import_cachesize:
        description: Size of database cache when doing an import.
        required: False
        default: 16777216
        type: int
      nsslapd_lookthroughlimit:
        description: The maximum number of entries that are looked in search operation before returning LDAP_ADMINLIMIT_EXCEEDED.
        required: False
        default: 5000
        type: int
      nsslapd_mode:
        description: The database permission (mode) in octal.
        required: False
        default: 600
        type: int
      nsslapd_pagedidlistscanlimit:
        description: idllistscanlimit when performing a paged search.
        required: False
        default: 0
        type: int
      nsslapd_pagedlookthroughlimit:
        description: lookthroughlimit when performing a paged search.
        required: False
        default: 0
        type: int
      nsslapd_rangelookthroughlimit:
        description: Sets a separate range look-through limit that applies to all users, including Directory Manager.
        required: False
        default: 5000
        type: int
      nsslapd_search_bypass_filter_test:
        description: Allowed values are: 'on', 'off' or 'verify'. If you enable the nsslapd-search-bypass-filter-test parameter, Directory Server bypasses filter checks when it builds candidate lists during a search. If you set the parameter to verify, Directory Server evaluates the filter against the search candidate entries.
        required: False
        default: on
        type: str
        choices:
           - on
           - off
           - verify
      nsslapd_search_use_vlv_index:
        description: enables and disables virtual list view (VLV) searches.
        required: False
        default: on
        type: str
        choices:
           - on
           - off
      port:
        description: Sets the TCP port the instance uses for LDAP connections.
        required: False
        type: int
      root_dn:
        description: Sets the Distinquished Name (DN) of the administrator account for this instance. It is recommended that you do not change this value from the default 'cn=Directory Manager'.
        required: False
        type: str
      rootpw:
        description: Sets the password of the "cn=Directory Manager" account ("root_dn" parameter). You can either set this parameter to a plain text password dscreate hashes during the installation or to a "{algorithm}hash" string generated by the pwdhash utility. The password must be at least 8 characters long.  Note that setting a plain text password can be a security risk if unprivileged users can read this INF file.
        required: False
        type: str
      run_dir:
        description: Directory containing the pid file.
        required: False
        type: str
      sbin_dir:
        description: Sets the location where the Directory Server administration binaries are stored. Only set this parameter in a development environment.
        required: False
        type: str
      schema_dir:
        description: Directory containing the schema files.
        required: False
        type: str
      secure_port:
        description: Sets the TCP port the instance uses for TLS-secured LDAP connections (LDAPS).
        required: False
        type: int
      self_sign_cert:
        description: Sets whether the setup creates a self-signed certificate and enables TLS encryption during the installation. The certificate is not suitable for production, but it enables administrators to use TLS right after the installation. You can replace the self-signed certificate with a certificate issued by a Certificate Authority. If set to False, you can enable TLS later by importing a CA/Certificate and enabling 'dsconf <instance_name> config replace nsslapd-security=on.
        required: False
        type: str
      self_sign_cert_valid_months:
        description: Set the number of months the issued self-signed certificate will be valid..
        required: False
        type: str
      selinux:
        description: Enables SELinux detection and integration during the installation of this instance. If set to "True", dscreate auto-detects whether SELinux is enabled. Set this parameter only to "False" in a development environment or if using a non root installation.
        required: False
        type: bool
      started:
        description: Indicate whether the instance is (or should be) started.
        required: False
        default: True
        type: bool
      strict_host_checking:
        description: Sets whether the server verifies the forward and reverse record set in the "full_machine_name" parameter. When installing this instance with GSSAPI authentication behind a load balancer, set this parameter to "false". Container installs imply "false".
        required: False
        type: bool
      sysconf_dir:
        description: sysconf directoryc.
        required: False
        type: str
      systemd:
        description: Enables systemd platform features. If set to "True", dscreate auto-detects whether systemd is installed. Only set this parameter in a development environment or if using non root installation.
        required: False
        type: bool
      tmp_dir:
        description: Sets the temporary directory of the instance.
        required: False
        type: str
      user:
        description: Sets the user name the ns-slapd process will use after the service started.
        required: False
        type: str
      backends:
        description: List of backends options.
        required: False
        type: list
        elements: dict
        suboptions:
          name:
            description: backend's name.
            type: str
            required: True
          state:
            description: Indicate whether the backend is added(present), modified(updated), or removed(absent).
            required: False
            default: present
            type: str
            choices:
               - present
               - updated
               - absent
          suffix:
            description: Desc.
            required: True
            type: str
          chain_bind_dn:
            description: Desc.
            required: False
            type: str
          chain_bind_pw:
            description: Desc.
            required: False
            type: str
          chain_urls:
            description: Desc.
            required: False
            type: str
          db_deadlock:
            description: Desc.
            required: False
            type: str
          directory:
            description: Desc.
            required: False
            type: str
          dn_cache_size:
            description: Desc.
            required: False
            type: str
          entry_cache_number:
            description: Desc.
            required: False
            type: str
          entry_cache_size:
            description: Desc.
            required: False
            type: str
          readonly:
            description: Desc.
            required: False
            default: False
            type: str
          require_index:
            description: Desc.
            required: False
            type: str
          sample_entries:
            description: Desc.
            required: False
            type: str
          indexes:
            description: List of indexes options.
            required: False
            type: list
            elements: dict
            suboptions:
              name:
                description: index's name.
                type: str
                required: True
              state:
                description: Indicate whether the index is added(present), modified(updated), or removed(absent).
                required: False
                default: present
                type: str
                choices:
                   - present
                   - updated
                   - absent
              indextype:
                description: Determine the index types (pres,eq,sub,matchingRuleOid).
                required: True
                type: str
              systemindex:
                description: Tells if the index is a system index.
                required: False
                default: off
                type: str
"""
