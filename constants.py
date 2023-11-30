SUDO_PASSWORD = 'notroot'


# DNSCat2 variables
CLIENT_DNSCAT2_PATH = '/home/client/dnscat2/client'
CLIENT_DNSCAT2_SOCKETNAME = '/tmp/dnscat2_client.sock'
NS_DNSCAT2_PATH = '/home/attacker/dnscat2/server'
NS_DNSCAT2_SOCKETNAME = '/tmp/dnscat2_server.sock'


# DNSExfiltrator variables
CLIENT_DNSEXFILTRATOR_PATH ='C:\\Users\\Client\\Documents'
NS_DNSEXFILTRATOR_PATH = '/home/attacker/DNSExfiltrator'
DNSEXFILTRATOR_FILE_PATH = 'C:\\Users\\Client\\Documents\\testWindows.txt'
NS_DNSEXFILTRATOR_SOCKETNAME = '/tmp/dnsexfiltrator_server.sock'
ENV_SERVER= 'det'
PASSWORD_KEY = 'test'

# Data Exfiltration Toolkit variables
DET_FILE_PATH = '/home/notroot/DET/fileToTransfer'
CLIENT_DET_PATH = '/home/notroot/DET'


# Proxy variables on Linux
LIN_LOCAL_DNS_PROXY = '10.0.2.15' # not useful, has been replaced by automated process
ENV_PROXY = 'DoH_proxyConda'
LIN_LISTEN_PORT_PROXY = '5553'
LIN_CONDA_PATH = '/home/client/anaconda3/condabin'
LIN_CERT_PATH = '/home/client/Documents/dohpub.pem'
PROXY_SOCKETNAME = '/tmp/dohproxy.sock'

# Proxy variables on Win10
WIN_CONDA_PATH = 'C:\\Users\\Client\\anaconda3\\condabin'
WIN_LOCAL_DNS_PROXY = '10.0.2.18' # not useful, has been replaced by automated process
DOWNLOADS_PATH = 'C:\\Users\\Client\\Downloads'
WIN_LISTEN_PORT_PROXY = '53'


DNSCAT2_PCAP_FILES_PATH = '/home/client/Documents/'
#DNSEXFILTRATOR_PCAP_PATH = 'C:\\Users\\Client\\Documents\\dnsexfiltrator_capture.pcap'
DNSEXFILTRATOR_PCAP_FILES_PATH = 'C:\\Users\\Client\\Documents\\'

DOMAIN = 'testlab.lan'
#LOCAL_DUMP_PATH = './dumps/'
