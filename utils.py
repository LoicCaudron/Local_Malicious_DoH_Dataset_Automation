import uuid
import logging
import constants

def logging_configuration(logging_filename, logging_format, logging_level):

    logging.basicConfig(
        filename = logging_filename,
        format = logging_format)
    logger = logging.getLogger(__name__)
    logger.setLevel(level = logging_level)

    return logger


def random_string(length):
    """Generate universally unique identifier in hexadecimal.
    If the length is defined, truncate the characters chain on this length.

    Parameters
    ----------
    length: int
        Length of the hexadecimal unique identifier.

    Returns
    -------
    hex_uuid: str
        Hexadecimal unique identifier    
    """

    hex_uuid = uuid.uuid4().hex

    if length:
        hex_uuid = hex_uuid[:length]
    return hex_uuid

def kill_all_processes(connection):
    """Kill all the processes related to the tools
    
    Parameters
    ----------
    connection: fabric.Connection
        Connection object of the Fabric library related to SSH connection to 
        the machines where we need to kill specific processes.
    """

    # Run the command as root
    connection.sudo("killall {proc_names} && sleep {wait} && killall -9 {proc_names}".format(
         passwd=constants.SUDO_PASSWORD, 
         proc_names=' '.join(('ruby', 'dnscat2', 'dnscat', 'conda', 'python' )), 
         wait=2), warn=True)
    print("killall finished on " + connection.host)

def run_background(connection, command, socket_name=None, sudo=False):
    """Run in background a process with a socket name associated in
    order to interact with the background process.

    Parameters
    ----------
    connection: fabric.Connection
        Connection object of the Fabric library related to SSH connection to 
        the machines where we need to execute a process in background.
    command: str
        Command to execute in background
    socket_name: str, optional
        Socket name used in order to interact with the process which we want to
        run in background.
    sudo: bool
        Determine if we want to run the command as root

    Returns
    -------
    socket_name: str
        Socket_name used or created if not indicated returned to interact later
        with the background process
    """

    if socket_name is None:
        random_name = random_string(length = 6)

        socket = '/tmp/{}.XXXXXX'.format(random_name)
        socket_name = '`mktemp -u {}`'.format(socket)

    # Concatenate the command with the `dtach` command to run in background
    dtach_command = 'dtach -n {socket} {cmd}'.format(socket=socket_name, 
                                                     cmd=command)
    # Precise to run with bash
    command_to_run = 'bash -c "{}"'.format(dtach_command)

    if sudo:
        connection.sudo(command_to_run)
    else:
        connection.run(command_to_run)

    return socket_name

def command_through_socket(connection, command, socket_name):
    """Allow to execute command on the tool thanks to the socket name of 
    the background process.

    Parameters
    ----------
    connection: fabric.Connection
        Connection object of the Fabric library related to SSH connection to 
        the machine where we need to execute a command in a background process.
    command: str
        Command to execute in the background process
    socket_name: str, optional
        Socket name used in order to interact with the process which is in 
        background.
    """

    print(command)
    dtach_command = 'echo {cmd} | dtach -p {socket}'.format(socket=socket_name, 
                                                            cmd=command)
    command_to_run = 'bash -c "{}"'.format(dtach_command)
    # Run the command as root
    connection.sudo(command_to_run)
