#!/usr/bin/env python

import argparse
import os
import paramiko
import time


class ClientManager:
    def __init__(self):
        self.active_hosts = set()
        self.clients = {}
        self.shells = {}

        self.ssh_config = paramiko.SSHConfig()
        user_config_file = os.path.expanduser('~/.ssh/config')
        if os.path.exists(user_config_file):
            with open(user_config_file) as f:
                self.ssh_config.parse(f)

    def add_client(self, hostname):
        client = paramiko.SSHClient()
        client._policy = paramiko.WarningPolicy()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        cfg = {'hostname': hostname}

        user_config = self.ssh_config.lookup(hostname)
        for key in ('hostname', 'username', 'port'):
            if key in user_config:
                cfg[key] = user_config[key]

        if 'proxycommand' in user_config:
            cfg['sock'] = paramiko.ProxyCommand(user_config['proxycommand'])

        client.connect(**cfg)
        channel = client.get_transport().open_session()
        channel.invoke_shell()
        self.active_hosts.add(hostname)
        self.clients[hostname] = client
        self.shells[hostname] = channel

    def run_command(self, command):
        for hostname in self.active_hosts:
            shell = self.shells[hostname]
            shell.sendall(command)

    def recv(self):
        for hostname in self.active_hosts:
            shell = self.shells[hostname]
            if shell.recv_ready():
                print('***STDOUT from ' + hostname + '***')
            while shell.recv_ready():
                print(shell.recv(1024))
            if shell.recv_stderr_ready():
                print('***STDERR from ' + hostname + '***')
            while shell.recv_stderr_ready():
                print(shell.recv_stderr(1024))

    def get_hosts(self):
        return ', '.join(self.active_hosts)
        
    def close_all(self):
        for shell in self.shells.values():
            shell.close()
        for client in self.clients.values():
            client.close()

help_str = 'command: command description.\n\n' \
+ 'add: add a host to the active hosts.\n' \
+ 'exec: execute a shell command on all active hosts.\n' \
+ 'group: groups hosts together into a named group. First argument is the ' \
+  'group name, the rest are the hosts in that group.\n' \
+ 'groups: print out a list of groups.\n' \
+ 'help: prints all this.\n' \
+ 'hosts: prints all active hosts.\n' \
+ 'quit: closes all connections and quits.\n' \
+ 'recv: prints the stdout and stderr of all active hosts.\n' \
+ 'rm: remove a host from the active hosts.\n' \
+ 'switch: takes a list of hosts (or a group) and makes them active, then ' \
+  'prints the active hosts. Also supports "all" as an argument.'


def main():
    parser = argparse.ArgumentParser(description='A tool for simulatneously '
                                     'SSHing to multiple environments.')
    parser.add_argument('environments', nargs='+', help='the environments'
                        'to SSH into')

    args = parser.parse_args()
    environments = args.environments

    manager = ClientManager()

    print('Sending {} push notifications.'.format(2*len(environments)))
    
    for environment in environments:
        manager.add_client(environment)

    raw_input('Hit return when all {} push '.format(2*len(environments))
              + 'notifications have been accepted.')

    group_dict = {}
    
    while True:
        command_str = raw_input('> ')
        command_args = command_str.split()
        if len(command_args) == 0:
            continue
        command_name = command_args[0]
        command_args = command_args[1:]
        # future commands
        # script: run a script on active hosts

        if command_name == 'hosts':
            print('Active hosts: ' + manager.get_hosts() + '.')
        elif command_name == 'switch' and len(command_args) > 0:
            if command_args[0] == 'all':
                manager.active_hosts = set(manager.clients.keys())
                print('Active hosts set to all: ' + manager.get_hosts() + '.')
            elif command_args[0] in group_dict:
                group_name = command_args[0]
                manager.active_hosts = group_dict[group_name]
                print('Active hosts set to ' + group_name + ': ' \
                      + manager.get_hosts() + '.')
            elif all(host in manager.clients.keys() for host in command_args):
                manager.active_hosts = set(command_args)
                print('Active hosts: ' + manager.get_hosts() + '.')
            else:
                print('Invalid switch.')
        elif command_name == 'add' and len(command_args) > 0:
            to_add = set(command_args)
            if all(host in manager.clients.keys() for host in to_add):
                manager.active_hosts.update(to_add)
                print('Active hosts: ' + manager.get_hosts() + '.')
            else:
                print('Invalid host(s).')
        elif command_name == 'rm' and len(command_args) > 0:
            to_remove = set(command_args)
            if all(host in manager.clients.keys() for host in to_remove):
                manager.active_hosts.difference_update(to_remove)
                print('Active hosts: ' + manager.get_hosts() + '.')
            else:
                print('Invalid host(s).')
        elif command_name == 'group' and len(command_args) > 1:
            group_name = command_args[0]
            group_hosts = set(command_args[1:])
            if all(host in manager.clients.keys() for host in group_hosts):
                group_dict[group_name] = group_hosts
                print('Created group "' + group_name + '" with hosts ' \
                      + ', '.join(group_hosts) + '.')
            else:
                print('Invalid host(s).')
        elif command_name == 'groups':
            if len(group_dict) == 0:
                print('No groups.')
            else:
                print('\n'.join(name + ': ' \
                                + ', '.join(hosts) for name, hosts in group_dict.items()))
        elif command_name == 'exec':
            command = ' '.join(command_args)
            print('Running command "' + command + '".')
            manager.run_command(command + '\n')
        elif command_name == 'recv':
            manager.recv()
        elif command_name == 'help':
            print(help_str)
        elif command_name == 'quit':
            print('Quitting.')
            manager.close_all()
            break
        else:
            print('Invalid command.')
    

if __name__ == '__main__':
    main()
