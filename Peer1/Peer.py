#!/usr/bin/python

import socket
import time
import threading
import json
import os
import argparse
import sys
sys.path.append('..')
from Queue import Queue
from concurrent import futures

SHARED_DIR = "./Active-Files"
REPLICA_DIR = "./Replica-Files"

def get_args():
    """
    Get command line args from the user.
    """
    parser = argparse.ArgumentParser(
        description='Standard Arguments for talking to Central Index Server')
    parser.add_argument('-s', '--server',
                        type=int,
                        required=True,
                        action='store',
                        help='Index Server Port Number')
    args = parser.parse_args()
    return args

class PeerOperations(threading.Thread):
    def __init__(self, threadid, name, p):
        """
        Constructor used to initialize class object.

        @param threadid:    Thread ID.
        @param name:        Name of the thread.
        @param p:           Class Peer Object.
        """
        threading.Thread.__init__(self)
        self.threadID = threadid
        self.name = name
        self.peer = p
        self.peer_server_listener_queue = Queue()

    def peer_server_listener(self):
        """
        Peer Server Listener Method is used Peer Server to listen on
        port: assigned by Index Server for incoming connections.
        """
        try:
            peer_server_socket = socket.socket(
                socket.AF_INET, socket.SOCK_STREAM)
            peer_server_socket.setsockopt(
                socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            peer_server_host = socket.gethostname()
            peer_server_port = self.peer.hosting_port
            peer_server_socket.bind(
                (peer_server_host, peer_server_port))
            peer_server_socket.listen(10)
            while True:
                conn, addr = peer_server_socket.accept()
                #print "Got connection from %s on port %s" \
                #          % (addr[0], addr[1])
                self.peer_server_listener_queue.put((conn,addr))
        except Exception as e:
            print "Peer Server Listener on port Failed: %s" % e
            sys.exit(1)

    def peer_server_upload(self, conn, data_received):
        """
        This method is used to enable file transfer between peers.

        @param conn:              Connection object.
        @param data_received:     Received data containing file name.
        """
        try:
            f = open(SHARED_DIR+'/'+data_received['file_name'], 'rb')
            #print "Hosting File: %s for download" % data_received
            data = f.read()
            f.close()
            conn.sendall(data)
            conn.close()
        except Exception as e:
            print "File Upload Error, %s" % e

    def peer_replica_download(self, conn, data_received):
        """
        This method is used to enable replica file transfer between peers.

        @param conn:              Connection object.
        @param data_received:     Received data containing file name.
        """
        try:
            peer_replica_request_addr, peer_replica_request_port = \
                data_received['peer_server'].split(':')
            peer_replica_request_socket = \
                socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peer_replica_request_socket.setsockopt(
                socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            peer_replica_request_socket.connect(
                (socket.gethostname(), int(peer_replica_request_port)))

            cmd_issue = {
                'command' : 'obtain_active',
                'file_name' : data_received['file_name']
            }

            peer_replica_request_socket.sendall(json.dumps(cmd_issue))
            rcv_data = peer_replica_request_socket.recv(1024000)
            f = open(REPLICA_DIR+'/'+data_received['file_name'], 'wb')
            f.write(rcv_data)
            f.close()
            peer_replica_request_socket.close()
            conn.sendall(json.dumps(True))
            conn.close()
        except Exception as e:
            conn.sendall(json.dumps(False))
            conn.close()
            print "Replica File Download Error, %s" % e

    def peer_server_host(self):
        """
        This method is used process client download request and file
        replication using pool of threads.
        """
        try:
            while True:
                while not self.peer_server_listener_queue.empty():
                    with futures.ThreadPoolExecutor(max_workers=8) as executor:
                        conn, addr = self.peer_server_listener_queue.get()
                        data_received = json.loads(conn.recv(1024))

                        if data_received['command'] == 'obtain_active':
                            fut = executor.submit(
                                self.peer_server_upload, conn, data_received)
                        elif data_received['command'] == 'obtain_replica':
                            fut = executor.submit(
                                self.peer_replica_download, conn, data_received)
        except Exception as e:
            print "Peer Server Hosting Error, %s" % e

    def peer_server(self):
        """
        This method is used start peer server listener and peer server 
        download deamon thread.
        """
        try:
            listener_thread = threading.Thread(target=self.peer_server_listener)
            listener_thread.setDaemon(True)

            operations_thread = threading.Thread(target=self.peer_server_host)
            operations_thread.setDaemon(True)

            listener_thread.start()
            operations_thread.start()

            threads = []
            threads.append(listener_thread)
            threads.append(operations_thread)

            for t in threads:
                t.join()
        except Exception as e:
            print "Peer Server Error, %s" % e
            sys.exit(1)

    def peer_file_handler(self):
        """
        Peer file handler is deamon thread handling file update and 
        file removal updater to Index Server.
        """
        try:
            while True:
                file_monitor_list = []
                for filename in os.listdir(SHARED_DIR):
                    file_monitor_list.append(filename)
                diff_list_add = list(
                    set(file_monitor_list) - set(self.peer.file_list))
                diff_list_rm = list(
                    set(self.peer.file_list) - set(file_monitor_list))
                if len(diff_list_add) > 0:
                    peer_to_server_socket = \
                        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    peer_to_server_socket.setsockopt(
                        socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    peer_to_server_socket.connect(
                        (self.peer.peer_hostname, self.peer.server_port))

                    cmd_issue = {
                        'command' : 'update',
                        'task' : 'add',
                        'peer_id' : self.peer.peer_id,
                        'files' : diff_list_add,
                    }
                    peer_to_server_socket.sendall(json.dumps(cmd_issue))
                    rcv_data = json.loads(peer_to_server_socket.recv(1024))
                    peer_to_server_socket.close()
                    if rcv_data:
                        print "File Update of Peer: %s on server successful" \
                          % (self.peer.peer_id)
                    else:
                        print "File Update of Peer: %s on server unsuccessful" \
                          % (self.peer.peer_id)
                if len(diff_list_rm) > 0:
                    peer_to_server_socket = \
                        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    peer_to_server_socket.setsockopt(
                        socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    peer_to_server_socket.connect(
                        (self.peer.peer_hostname, self.peer.server_port))

                    cmd_issue = {
                        'command' : 'update',
                        'task' : 'rm',
                        'peer_id' : self.peer.peer_id,
                        'files' : diff_list_rm,
                    }
                    peer_to_server_socket.sendall(json.dumps(cmd_issue))
                    rcv_data = json.loads(peer_to_server_socket.recv(1024))
                    peer_to_server_socket.close()
                    if rcv_data:
                        print "File Update of Peer: %s on server successful" \
                          % (self.peer.peer_id)
                    else:
                        print "File Update of Peer: %s on server unsuccessful" \
                          % (self.peer.peer_id)
                self.peer.file_list = file_monitor_list
                time.sleep(10)
        except Exception as e:
            print "File Handler Error, %s" % e
            sys.exit(1)

    def run(self):
        """
        Deamon thread for Peer Server and File Handler.
        """
        if self.name == "PeerServer":
            self.peer_server()
        elif self.name == "PeerFileHandler":
            self.peer_file_handler()

class Peer():
    def __init__(self, server_port):
        """
        Constructor used to initialize class object.
        """
        self.peer_hostname = socket.gethostname()
        self.server_port = server_port
        self.file_list = []

    def get_file_list(self):
        """
        Obtain file list in shared dir.
        """
        try:
            for filename in os.listdir(SHARED_DIR):
                self.file_list.append(filename)
        except Exception as e:
            print "Error: retriving file list, %s" % e

    def get_free_socket(self):
        """
        This method is used to obtain free socket port for the registring peer 
        where the peer can use this port for hosting file as a server.

        @return free_socket:    Socket port to be used as a Peer Server.
        """
        try:
            peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peer_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            peer_socket.bind(('', 0))
            free_socket = peer_socket.getsockname()[1]
            peer_socket.close()
            return free_socket
        except Exception as e:
            print "Obtaining free sockets failed: %s" % e
            sys.exit(1)

    def register_peer(self):
        """
        Registering peer with Central Index Server.
        """
        try:
            self.get_file_list()
            free_socket = self.get_free_socket()
            print "Registring Peer with Server..."

            peer_to_server_socket = \
                socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peer_to_server_socket.setsockopt(
                socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            peer_to_server_socket.connect(
                (self.peer_hostname, self.server_port))

            cmd_issue = {
                'command' : 'register',
                'peer_port' : free_socket,
                'files' : self.file_list,
            }
            peer_to_server_socket.sendall(json.dumps(cmd_issue))
            rcv_data = json.loads(peer_to_server_socket.recv(1024))
            peer_to_server_socket.close()
            if rcv_data[1]:
                self.hosting_port = free_socket
                self.peer_id = rcv_data[0] + ":" + str(free_socket)
                print "registration successfull, Peer ID: %s:%s" \
                              % (rcv_data[0], free_socket)
            else:
                print "registration unsuccessfull, Peer ID: %s:%s" \
                              % (rcv_data[0], free_socket)
                sys.exit(1)
        except Exception as e:
            print "Registering Peer Error, %s" % e
            sys.exit(1)

    def list_files_index_server(self):
        """
        Obtain files present in Index Server.
        """
        try:
            peer_to_server_socket = \
                socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peer_to_server_socket.setsockopt(
                socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            peer_to_server_socket.connect(
                (self.peer_hostname, self.server_port))

            cmd_issue = {
                'command' : 'list'
            }
            peer_to_server_socket.sendall(json.dumps(cmd_issue))
            rcv_data = json.loads(peer_to_server_socket.recv(1024))
            peer_to_server_socket.close()
            print "File List in Index Server:"
            for f in rcv_data:
                print f
        except Exception as e:
            print "Listing Files from Index Server Error, %s" % e

    def search_file(self, file_name):
        """
        Search for a file in Index Server.

        @param file_name:      File name to be searched.
        """
        try:
            peer_to_server_socket = \
                socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peer_to_server_socket.setsockopt(
                socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            peer_to_server_socket.connect(
                (self.peer_hostname, self.server_port))

            cmd_issue = {
                'command' : 'search',
                'file_name' : file_name
            }
            peer_to_server_socket.sendall(json.dumps(cmd_issue))
            rcv_data = json.loads(peer_to_server_socket.recv(1024))
            if len(rcv_data) == 0:
                print "File Not Found"
            else:
                print "\nFile Present in below following Peers:"
                for peer in rcv_data:
                    if peer == self.peer_id:
                        print "File Present Locally, Peer ID: %s" % peer
                    else:
                        print "Peer ID: %s" % peer
            peer_to_server_socket.close()
        except Exception as e:
            print "Search File Error, %s" % e

    def obtain(self, file_name, peer_request_id):
        """
        Download file from another peer.

        @param file_name:          File name to be downloaded.
        @param peer_request_id:    Peer ID to be downloaded.
        """
        try:
            peer_request_addr, peer_request_port = peer_request_id.split(':')
            peer_request_socket = \
                socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peer_request_socket.setsockopt(
                socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            peer_request_socket.connect(
                (socket.gethostname(), int(peer_request_port)))

            cmd_issue = {
                'command' : 'obtain_active',
                'file_name' : file_name
            }

            peer_request_socket.sendall(json.dumps(cmd_issue))
            rcv_data = peer_request_socket.recv(1024000)
            f = open(SHARED_DIR+'/'+file_name, 'wb')
            f.write(rcv_data)
            f.close()
            peer_request_socket.close()
            print "File downloaded successfully"
        except Exception as e:
            print "Obtain File Error, %s" % e

    def deregister_peer(self):
        """
        Deregister peer from Central Index Server.
        """
        try:
            print "Deregistring Peer with Server..."

            peer_to_server_socket = \
                socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peer_to_server_socket.setsockopt(
                socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            peer_to_server_socket.connect(
                (self.peer_hostname, self.server_port))

            cmd_issue = {
                'command' : 'deregister',
                'peer_id' : self.peer_id,
                'files' : self.file_list,
                'hosting_port' : self.hosting_port
            }
            peer_to_server_socket.sendall(json.dumps(cmd_issue))
            rcv_data = json.loads(peer_to_server_socket.recv(1024))
            peer_to_server_socket.close()
            if rcv_data:
                print "deregistration of Peer: %s on server successful" \
                      % (self.peer_id)
            else:
                print "deregistration of Peer: %s on server unsuccessful" \
                      % (self.peer_id)
        except Exception as e:
            print "Deregistering Peer Error, %s" % e

if __name__ == '__main__':
    """
    Main method starting deamon threads and peer operations.
    """
    try:
        args = get_args()
        print "Starting Peer..."
        p = Peer(args.server)
        p.register_peer()

        print "Stating Peer Server Deamon Thread..."
        server_thread = PeerOperations(1, "PeerServer", p)
        server_thread.setDaemon(True)
        server_thread.start()

        print "Starting File Handler Deamon Thread..."
        file_handler_thread = PeerOperations(2, "PeerFileHandler", p)
        file_handler_thread.setDaemon(True)
        file_handler_thread.start()

        while True:
            print "*" * 20
            print "1. List all files in Index Server"
            print "2. Search for File"
            print "3. Get File from Peer"
            print "4. Exit"
            print "*" * 5
            print "Enter choise : "
            ops = raw_input()

            if int(ops) == 1:
                p.list_files_index_server()

            elif int(ops) == 2:
                print "Enter File Name: "
                file_name = raw_input()
                p.search_file(file_name)

            elif int(ops) == 3:
                print "Enter File Name: "
                file_name = raw_input()
                print "Enter Peer ID: "
                peer_request_id = raw_input()
                p.obtain(file_name, peer_request_id)

            elif int(ops) == 4:
                p.deregister_peer()
                print "Peer Shutting down..."
                time.sleep(1)
                break

            else:
                print "Invaild choice...\n"
                continue

    except Exception as e:
        print e
        sys.exit(1)
    except (KeyboardInterrupt, SystemExit):
        p.deregister_peer()
        print "Peer Shutting down..."
        time.sleep(1)
        sys.exit(1)

__author__ = 'arihant'