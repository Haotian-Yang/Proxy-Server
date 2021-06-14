import socket
import select
import sys
import os
import time

expire_time = float(sys.argv[1])

def generateServer(ipAddr, port):
    '''
    generateServer will create and return a socket server 
    and return    
    '''
    proxyServer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxyServer.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    proxyServer.bind((ipAddr, port))

    return proxyServer

proxyServer =  generateServer('localhost', 8888)
proxyServer.listen(100)
print("Proxy Server has been started")


# HttpRequest Class initializes the request made from the client
# to be compatibale with the web-server
class HttpRequest:
    def __init__(self, hreq):
        '''
        Initializes takes in the client http request
        extracts out the corresponding path and the host required to make
        the http request
        '''
        self.properties = hreq.split('\n')
        self.path = self.properties[0].split(' ')[1][1:]
        self.host = self.path.split('/')[0]
        self.path = self.path.replace(self.host, '')[1:]
        self.request = ""

    def constructRequest(self):
        '''
        constructRequests constructs the http get request with corresponding parameters
        '''
        headerRequest = "GET /" + self.path + " HTTP/1.1\r\n"
        host = "Host: " + self.host + "\r\n"
        accept = "Accept: identity;q=0,text/html,application/xhtml+xml,\
                 application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,\
                application/signed-exchange;v=b3;q=0.9\r\n"        
        conn = "Connection: close\r\n\r\n"

        self.request = headerRequest + host + accept + conn
   

    def makeGetRequest(self, client, addr):
        # Have to check the cache in here
        completePath = self.host + '/' + self.path
        completePath = completePath.replace('/', '')

        # Checks the Cache, and if request data exists then send to client and return
        try:
            path = 'cache/' + completePath
            cache = open(path, 'rb')
            last_modi_time = os.path.getmtime(path)
            # not expire
            if time.time() - last_modi_time < expire_time:
                data = cache.read(1024)
                while 1:
                    try:
                        client.send(data)
                    except socket.error as e:
                        cache.close()
                        return
                    data = cache.read(1024)
                    if not data:
                        cache.close()
                        return
        except FileNotFoundError:
            print("Request doesn't exist in cache")
     
       
        # Cache expired or not in cache
        try:

            # Make connection to webserver
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(150)
            s.connect((self.host, 80))
            self.constructRequest()
            s.sendall(bytes(self.request.encode('utf-8')))
            # Variables for recived data
            header_check = True
            header_data = b''
            context_data = b''
            content_type = ''
            DATA = []
            totalData = 0
            acc_rec_data = 0
            need_rec = 1024
            # Loop over socket from web server 
            while True:
                firstRead = s.recv(need_rec)
                if len(firstRead) == 0:
                    break
                DATA.append(firstRead)

                # Check the header info and extract the Content-Length and Content-Type
                if header_check:
                    # check length in the chuck
                    headerProp = firstRead.split(b'\r\n')
                    for item in headerProp:
                        if b'Content-Type: ' in item:
                            content_type = item.split(b' ')[1]
                        if b'Content-Length: ' in item:
                            check = item.split(b' ')
                            totalData = int(check[1])
                    if b'\r\n\r\n' in firstRead:
                        header_check = False
                        data_split = firstRead.split(b'\r\n\r\n')
                        header_data+=data_split[0]
                        context_data+=data_split[1]
                        acc_rec_data += len(data_split[1])
                    else:
                        header_data+=firstRead
                
                # context
                else:

                    context_data+=firstRead
                    acc_rec_data += len(firstRead)
                    if acc_rec_data == totalData:
                        break

            s.close()

            # Injection Info
            #injection for client instant response after receiving from web-server
            curr_time = bytes(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()),'utf-8')
            data_inject = b"<p style='z-index:9999; position:fixed; top:20px; left:20px; \
                          width:200px;height:100px; background-color:yellow; padding:10px; font-weight:bold;'>\
                        THE FRESH VERSION AT: "+curr_time+b"</p>"
            
            #injection for the cached data
            data_inject_cache = b"<p style='z-index:9999; position:fixed; top:20px; left:20px;\
                                width:200px;height:100px; background-color:yellow; padding:10px; \
                                font-weight:bold;'>CACHED VERSION AS OF: " + curr_time+b"</p>"


            # Only inject when we reciving HTML
            if b'text/html' in content_type:
                headerProp = header_data.split(b'\r\n')
                i = 0
                while i < len(headerProp):
                    if b'Content-Length' in headerProp[i]:
                        break
                    i += 1
                newContentLen = 'Content-Length: ' + str(totalData + len(data_inject) )
                headerProp[i] = newContentLen.encode('utf-8')
                header_data = b'\r\n'.join(headerProp)
            header_data = header_data + b'\r\n\r\n' # Spliting between header and body
            all_data = header_data + context_data
            Cache_version = b''
            cache = open('./cache/' + completePath, 'wb') # Opening file for writing data

            if b'text/html' in content_type:
                begin_index = all_data.find(b"<body")
                end_index = all_data.find(b">", begin_index)
                if end_index != -1:
                    data_new = all_data[:end_index+1]+data_inject+all_data[end_index+1:] # instant response injection
                    Cache_version = all_data[:end_index+1]+data_inject_cache+all_data[end_index+1:] # cached response injection
                    all_data = data_new
                cache.write(Cache_version)
                client.send(all_data)
            else:
                # When content-type is not of a html format
                for data in DATA:
                    client.send(data)
                    cache.write(data)
            cache.close()
        except socket.error as e:
            print(e)
        s.close()


# Initializing lists for select, proxy server will always remain there
inputs = [proxyServer]
output = []
clientIP = {}

# Main Server Loop 
while True:
    # Waitting for a connection to send data
    readable, _, _ = select.select(inputs, output, inputs)
    if len(readable) != 0:
        #Reading through all connection that are ready to send us data (ie request)
        for conn in readable:
            # When we get new client
            if conn is proxyServer:
                # Make connection between client and proxy
                try:
                    clientConnection, clientAddress = conn.accept()
                    print("New client connected IP:%s  PORT:%s", clientAddress[0], clientAddress[1])
                    inputs.append(clientConnection)
                    clientIP[clientConnection] = clientAddress
                except socket.error:
                    print("Invalid connection")
            else:
                  # Reading from Client (ie reading http request)
                try:                    
                    request = conn.recv(1024).decode('utf-8')
                    if 'favicon' not in request and request != '':                      
                        req = HttpRequest(request)
                        print("Contacting Webserver for data  PATH: %s CLIENT:%s", req.path, clientIP[conn][0])

                        req.makeGetRequest(conn, clientIP[conn][0])
                except socket.error:
                    print("Error Reading Client Request")
                conn.close()
                inputs.remove(conn)
                clientIP.pop(conn)

proxyServer.close()
