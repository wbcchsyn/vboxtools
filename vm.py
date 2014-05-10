#-*- coding: utf-8 -*-

import sys
import re
from subprocess import Popen, PIPE


# Path to VBoxManage
VBoxManage = "VBoxManage"


class Vm(object):

    __vms = None

    @classmethod
    def list_vms(cls, reload=False):
        """
        Return list of all VMs registered in VirtualBox.

        If result isn't cached or argument 'reload' is False, fetch VMs using
        VirtualBox API, chache them and return. Otherwise, return the cache.
        """

        if cls.__vms is not None:
            return cls.__vms

        pattern = re.compile(r'^\"(?P<name>\S+)"\s+'
                             r'\{(?P<hash>[0-9a-fA-F\-]+)\}$')

        matches = [pattern.match(line)
                   for line in cls.__call(VBoxManage, 'list', 'vms')]
        cls.__vms = [m.groupdict()['name'] for m in matches if m]

        return cls.__vms

    def __init__(self, name):
        """ Argument 'name' is the VM name. """
        if name not in self.list_vms():
            raise RuntimeError('No such vm is.')

        self.__name = name
        self.__info = None

    @property
    def name(self):
        """ Return VM name. """

        return self.__name

    @property
    def info(self):
        """ Fetch VM infomation from VirtualBox. """

        if self.__info is None:
            self.__info = self.__call(VBoxManage, 'showvminfo', self.__name)

        return self.__info

    @property
    def core(self):
        """ Return how much CPU cores VM has. """

        pattern = re.compile(r'^Number of CPUs:\s+(?P<core>\d+)$')
        for line in self.info:
            m = pattern.match(line)
            if m:
                return int(m.groupdict()['core'])

        raise RuntimeError('Failed to parse vm info.')

    @property
    def memory(self):
        """ Return how much memory VM can use. """

        pattern = re.compile(r'^Memory size:\s+(?P<size>\w+)')
        for line in self.info:
            m = pattern.match(line)
            if m:
                return m.groupdict()['size']

        raise RuntimeError('Failed to parse vm info.')

    @property
    def is_running(self):
        """ Return True if VM is running. """

        return self.status.startswith('running')

    @property
    def status(self):
        """ Return VM status. """

        for line in self.info:
            if line.startswith('State:'):
                return line.split(':', 1)[1].strip()
        raise RuntimeError("Failed to fetch status.")

    @property
    def os(self):
        """ Return Guest OS. """

        for line in self.info:
            if line.startswith('Guest OS:'):
                return line.split(':', 1)[1].strip()

        raise RuntimeError("Failed to parse Guest OS.")

    @property
    def uuid(self):
        """ Return VM UUID. """

        for line in self.info:
            if line.startswith('UUID:'):
                return line.split(':', 1)[1].strip()

        raise RuntimeError("Failed to parse UUID.")

    @property
    def nics(self):
        """ Return VM Nics information. """

        ret = {}

        pattern = re.compile(r'^NIC (?P<number>\d+):\s+(?P<csv>.*)')
        for line in self.info:
            m = pattern.match(line)
            if m:
                if m.groupdict()['csv'] == 'disabled':
                    continue

                num = int(m.groupdict()['number'])
                nic = {}
                for cell in m.groupdict()['csv'].split(','):
                    k, v = [s.strip() for s in cell.split(':', 1)]
                    nic[k] = v
                if nic['Cable connected'] == 'on':
                    ret[num] = nic

        return ret

    @property
    def port_forward(self):
        """
        Fetch Port forward settings of the Nat and return the information.
        """

        nat_nics = [num for num, info in self.nics.items()
                    if info['Attachment'] == 'NAT']

        ret = []
        pattern = re.compile(r'^NIC (?P<nic_number>\d+)'
                             r' Rule\((?P<r_number>\d+)\):\s+(?P<csv>.*)$')
        for line in self.info:
            m = pattern.match(line)
            if m:
                nic_num = int(m.groupdict()['nic_number'])
                if nic_num not in nat_nics:
                    continue

                rule = {'nic': int(nic_num)}
                for cell in m.groupdict()['csv'].split(','):
                    k, v = [s.strip() for s in cell.split('=', 1)]
                    rule[k] = v
                ret.append(rule)

        return ret

    def __ssh_port_forward_rule(self):
        """ Return port forward rule for ssh. """

        ssh_rules = [rule for rule in self.port_forward
                     if rule['name'] == 'ssh' and rule['guest port'] == '22']

        if len(ssh_rules) == 0:
            return None
        elif len(ssh_rules) == 1:
            return ssh_rules[0]
        else:
            raise RuntimeError('%s has 2 or more than 2 ssh port forward.' %
                               self.name)

    @property
    def ssh_port(self):
        """ Return local port of port forwarding named 'ssh' """

        rule = self.__ssh_port_forward_rule()
        if rule:
            return int(rule['host port'])
        else:
            return None

    def set_ssh_port(self, port):
        """ Create a port forward rule to guest 22 port named 'ssh' """

        rule = self.__ssh_port_forward_rule()
        if rule:
            self.__call(VBoxManage, 'modifyvm', self.name,
                        '--natpf%s' % rule['nic'], 'delete', rule['name'])

        nic = [num for num, info in self.nics.items()
               if info['Attachment'] == 'NAT'][0]

        self.__call(VBoxManage, 'modifyvm', self.name,
                    '--natpf%d' % nic,
                    'ssh,tcp,127.0.0.1,%d,,22' % port)

        self.__info = None

    def up(self, gui=False):
        """ Start VM """

        if gui:
            self.__call(VBoxManage, 'startvm', self.name, '--type', 'gui')
        else:
            self.__call(VBoxManage, 'startvm', self.name, '--type', 'headless')

    def acpi(self):
        """ Send ACPI signal. """

        self.__call(VBoxManage, 'controlvm', self.name, 'acpipowerbutton')

    def unregister(self):
        """ Unregister VM and delete all files. """

        self.__call(VBoxManage, 'unregistervm', self.name, '--delete')

    def poweroff(self):
        """ Poweroff VM forcely. """

        self.__call(VBoxManage, 'controlvm', self.name, 'poweroff')

    def clone(self, new_name, snapshot=None, full=False):
        """ Create a clone VM.

        If argument 'full' is True, copy all image files and create a full
        clone. Otherwise, create a linked clone using snapshot. To use linked
        clone, VM must have at least one snapshot.

        If argument 'snapshot' is None, use current snapshot to create linked
        clone.
        """

        cmd = [VBoxManage, 'clonevm', self.name, '--register',
               '--name', new_name]
        if not full:
            cmd = cmd + ['--options', 'link']
        if snapshot:
            cmd = cmd + ['--snapshot', snapshot]

        self.__call(*cmd)

    def snap_list(self):
        """ Return list of snapshot dicts. """

        pattern = re.compile(r'^(?P<indent> +)Name: (?P<name>.*) '
                             r'\(UUID: (?P<uuid>[a-f0-9\-]+)\)'
                             r'(?P<current> \*)?$')
        matches = [pattern.match(line) for line in self.info]
        return [
            {'indent': int(len(m.groupdict()['indent']) / 3),
             'name': m.groupdict()['name'],
             'uuid': m.groupdict()['uuid'],
             'is_current': m.groupdict()['current'] is not None}
            for m in matches if m
        ]

    def snap_take(self, name):
        """ Create a new snapshot. """

        self.__call(VBoxManage, 'snapshot', self.name, 'take', name)

    def snap_remove(self, name):
        """ Remove specified snapshot. """

        self.__call(VBoxManage, 'snapshot', self.name, 'delete', name)

    def snap_restore(self, name=None):
        """ Restore to snapshot.

        If argument name is None, restore to current one.
        """

        if name is None:
            self.__call(VBoxManage, 'snapshot', self.name, 'restorecurrent')
        else:
            self.__call(VBoxManage, 'snapshot', self.name, 'restore', name)

    @staticmethod
    def __call(*cmd_list):
        """
        Execute shell command and return list of the stdout.
        """

        child = None
        try:
            child = Popen(cmd_list, stdout=PIPE)
            return [line.decode('utf-8') for line in child.stdout.readlines()]
        finally:
            if child and (not child.wait() == 0):
                raise RuntimeError('Failed cmd %s' % cmd_list)
