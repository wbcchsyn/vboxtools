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
                ret[num] = {}
                for cell in m.groupdict()['csv'].split(','):
                    k, v = [s.strip() for s in cell.split(':', 1)]
                    ret[num][k] = v

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

    def del_port_forward(self, rule):
        try:
            if not self.nics[rule['nic']]['Attachment'] == "NAT":
                raise RuntimeError("NIC %d is not NAT." % rule['nic'])

            self.__call(VBoxManage, 'modifyvm', self.name,
                        '--natpf%s' % rule['nic'], 'delete', rule['name'])
        except KeyError as e:
            raise ArgumentError('Argument rule is requested to be dict and has'
                                ' %s key.' %
                                e.args[0])

    def set_port_forward(self, rule):

        try:
            if not self.nics[rule['nic']]['Attachment'] == "NAT":
                raise RuntimeError("NIC %d is not NAT." % rule['nic'])

            self.__call(VBoxManage, 'modifyvm', self.name,
                        '--natpf%d' % rule['nic'],
                        '%s,%s,%s,%s,%s,%s' % (rule['name'],
                                               rule['protocol'],
                                               rule['host ip'],
                                               rule['host port'],
                                               rule['guest ip'],
                                               rule['guest port']))
        except KeyError as e:
            raise ArgumentError('Argument rule is requested to be dict and has'
                                ' key %s.' % e.args[0])

    def up(self, headless=True):
        if headless:
            self.__call(VBoxManage, 'startvm', self.name, '--type', 'headless')
        else:
            self.__call(VBoxManage, 'startvm', self.name, '--type', 'gui')

    def acpi(self):
        self.__call(VBoxManage, 'controlvm', self.name, 'acpipowerbutton')

    def unregister(self):
        self.__call(VBoxManage, 'unregistervm', self.name, '--delete')

    def poweroff(self):
        self.__call(VBoxManage, 'controlvm', self.name, 'poweroff')

    def snap_take(self, name):
        self.__call(VBoxManage, 'snapshot', self.name, 'take', name)

    def snap_remove(self, name):
        self.__call(VBoxManage, 'snapshot', self.name, 'delete', name)

    def snap_restore(self, name=None):
        if name is None:
            self.__call(VBoxManage, 'snapshot', self.name, 'restorecurrent')
        else:
            self.__call(VBoxManage, 'snapshot', self.name, 'restore', name)

    @staticmethod
    def __call(*cmd_list):
        """
        Execute shell command and return its stdout.
        """

        child = None
        try:
            child = Popen(cmd_list, stdout=PIPE)
            return [line.decode('utf-8') for line in child.stdout.readlines()]
        finally:
            if child and (not child.wait() == 0):
                raise RuntimeError('Failed cmd %s' % cmd_list)
