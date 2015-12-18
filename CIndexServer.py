#!/usr/bin/python

import socket
import time
import threading
import json
import random
import argparse
import sys
from Queue import Queue
from concurrent import futures

def get_args():
    """
    Get command line args from the user.
    """
    parser = argparse.ArgumentParser(
        description='Standard Arguments for talking to Central Index Server')
    parser.add_argument('-p', '--port',
                        type=int,
                        required=True,
                        action='store',
                        help='Server Port Number')
    parser.add_argument('-r', '--replica',
                        type=int,
                        default=1,
                        action='store',
                        help='Data Replication Factor')
    args = parser.parse_args()
    return args

class ServerOperations(threading.Thread):
    def __init__(self, threadid, name, rep_factor, server_port):
        """
        Constructor used to initialize class object.

        @param threadid:    Thread ID.
        @param name:        Name of the thread.
        """
        threading.Thread.__init__(self)
        self.threadID = threadid
        self.name = name
        self.replication_factor = rep_factor
        self.server_port = server_port
        self.hash_table_ports_peers = {}
        self.hash_table_files = {}
        self.hash_table_replica_files = {}
        self.hash_table_peer_files = {}
        self.listener_queue = Queue()

    def server_listener(self):
        """
        Server Listener Method is used start Central Index Server to listen on
        port: 3344 for incoming connections.
        """
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_host = socket.gethostname()
            server_socket.bind((server_host, self.server_port))
            server_socket.listen(10)
            while True:
                conn, addr = server_socket.accept()
                self.listener_queue.put((conn,addr))
        except Exception as e:
            print "Server Listener on port Failed: %s" % e
            sys.exit(1)

    def registry(self, addr, files, peer_port):
        """
        This method is invoked by the peer trying to register itself 
        with the Indexing Server.

        @param addr:           Address of the incoming connection.
        @param files:          File list sent by the peer.
        @param peer_port:      Peer's server port.

        @return free_socket:   Socket port to be used as a Peer Server.
        """
        try:
            self.hash_table_ports_peers[peer_port] = addr[0]
            peer_id = addr[0] + ":" + str(peer_port)
            self.hash_table_peer_files[peer_id] = files
            for f in files:
                if self.hash_table_files.has_key(f):
                    self.hash_table_files[f].append(peer_id)
                else:
                    self.hash_table_files[f] = [peer_id]
            return True
        except Exception as e:
            print "Peer registration failure: %s" % e
            return False

    def update(self, peer_update):
        """
        This method is invoked by the peer's file handler to update the files 
        in the Index Server. Peer file handler invokes this method upon addition 
        of new file or removal of existing file.

        @param peer_update:      Peer File Update details.
        """
        try:
            if peer_update['task'] == 'add':
                for f in peer_update['files']:
                    self.hash_table_peer_files[peer_update['peer_id']].append(f)
                    if self.hash_table_files.has_key(f):
                        self.hash_table_files[f].append(str(peer_update['peer_id']))
                    else:
                        self.hash_table_files[f] = [str(peer_update['peer_id'])]

            if peer_update['task'] == 'rm':
                for f in peer_update['files']:
                    self.hash_table_peer_files[peer_update['peer_id']].remove(f)
                    if self.hash_table_files.has_key(f):
                        for peer_id in self.hash_table_files[f]:
                            if peer_id == peer_update['peer_id']:
                                self.hash_table_files[f].remove(peer_id)
                                if len(self.hash_table_files[f]) == 0:
                                    self.hash_table_files.pop(f, None)
            return True
        except Exception as e:
            print "Peer File Update failure: %s" % e
            return False

    def list_files_index_server(self):
        """
        This method is used display the list of files registered with 
        the Central Index Server.

        @return files_list:    List of files present in the server.
        """
        try:
            files_list = self.hash_table_files.keys()
            return files_list
        except Exception as e:
            print "Listing Files Error, %s" % e

    def search(self, file_name):
        """
        This method is used to search for a particular file.

        @param file_name:    File name to be searched.
        @return:             List of Peers associated with the file.
        """
        try:
            if self.hash_table_files.has_key(file_name):
                peer_list = self.hash_table_files[file_name]
            else:
                peer_list = []
            return peer_list
        except Exception as e:
            print "Listing Files Error, %s" % e

    def deregistry(self, peer_data):
        """
        The method is invoked when the Peer dies or Peer shutsdown to 
        remove all its entry from the Central Index Server.

        @param peer_data:      Peer data containing Peer details.
        @return True/False:    Return success or failure.
        """
        try:
            if self.hash_table_ports_peers.has_key(peer_data['hosting_port']):
                self.hash_table_ports_peers.pop(peer_data['hosting_port'], None)
            if self.hash_table_peer_files.has_key(peer_data['peer_id']):
                self.hash_table_peer_files.pop(peer_data['peer_id'], None)
            for f in peer_data['files']:
                if self.hash_table_files.has_key(f):
                    for peer_id in self.hash_table_files[f]:
                        if peer_id == peer_data['peer_id']:
                            self.hash_table_files[f].remove(peer_id)
                            if len(self.hash_table_files[f]) == 0:
                                self.hash_table_files.pop(f, None)
            return True
        except Exception as e:
            print "Peer deregistration failure: %s" % e
            return False

    def random_peer(self, f, peer_id_list, file_peer_list):
        """
        This method is to obtained a random peer for the file to be replicated.

        @return choise:     Random Peer to be returned.
        """
        try:
            choise = random.choice(peer_id_list)
            if (choise in file_peer_list) or \
                    (choise in self.hash_table_replica_files[f]):
                choise = self.random_peer(f, peer_id_list, file_peer_list)
            return choise
        except Exception as e:
            print "Chosing random peer for replica error, %s" % e


    def data_resilience(self):
        """
        This method is used to ensure data resilience system wide.
        """
        try:
            while True:
                perform_replication = False
                peer_id_list = self.hash_table_peer_files.keys()
                if len(peer_id_list) > self.replication_factor:
                    for key,val in self.hash_table_files.items():
                        if not self.hash_table_replica_files.has_key(key):
                            self.hash_table_replica_files[key] = []
                            perform_replication = True
                        elif len(self.hash_table_replica_files[key]) < \
                                self.replication_factor:
                            perform_replication = True

                        if perform_replication:
                            random_peer = self.random_peer(
                                key, peer_id_list, val)
                            print "file %s to be replicated to %s" % \
                                  (key,random_peer)
                            peer_issue_addr, peer_issue_port = \
                                random_peer.split(':')
                            peer_issue_socket = \
                                socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            peer_issue_socket.setsockopt(
                                socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                            peer_issue_socket.connect(
                                (socket.gethostname(), int(peer_issue_port)))

                            cmd_issue = {
                                'command' : 'obtain_replica',
                                'file_name' : key,
                                'peer_server' : random.choice(
                                    self.hash_table_files[key]),
                            }
                            peer_issue_socket.sendall(json.dumps(cmd_issue))
                            rcv_data = json.loads(peer_issue_socket.recv(1024))
                            peer_issue_socket.close()
                            if rcv_data:
                                self.hash_table_replica_files[key].append(
                                    random_peer)
                elif not self.hash_table_replica_files:
                    print "Waiting for more active peers to start with " \
                          "data replication..."
                    time.sleep(10)
        except Exception as e:
            print "Data Resilience Error, %s" % e

    def run(self):
        """
        Starting thread to carry out server operations.
        """
        try:
            print "Starting Server Listener Deamon Thread..."
            listener_thread = threading.Thread(target=self.server_listener)
            listener_thread.setDaemon(True)
            listener_thread.start()
            print "Stating Data Resilience Deamon Thread with " \
                  "replication factor = %s" % self.replication_factor
            dr_thread = threading.Thread(target=self.data_resilience)
            dr_thread.setDaemon(True)
            dr_thread.start()
            while True:
                while not self.listener_queue.empty():
                    with futures.ThreadPoolExecutor(max_workers=8) as executor:
                        conn, addr = self.listener_queue.get()
                        data_received = json.loads(conn.recv(1024))

                        print "Got connection from %s on port %s, requesting " \
                              "for: %s" % (addr[0], addr[1], data_received['command'])

                        if data_received['command'] == 'register':
                            fut = executor.submit(self.registry, addr,
                                                  data_received['files'], 
                                                  data_received['peer_port'])
                            success = fut.result(timeout= None)
                            if success:
                                print "registration successfull, Peer ID: %s:%s" \
                                      % (addr[0], data_received['peer_port'])
                                conn.send(json.dumps([addr[0], success]))
                            else:
                                print "registration unsuccessfull, Peer ID: %s:%s" \
                                      % (addr[0], data_received['peer_port'])
                                conn.send(json.dumps([addr[0], success]))

                        elif data_received['command'] == 'update':
                            fut = executor.submit(self.update, data_received)
                            success = fut.result(timeout= None)
                            if success:
                                print "Update of Peer ID: %s successful" \
                                      % (data_received['peer_id'])
                                conn.send(json.dumps(success))
                            else:
                                print "Update of Peer ID: %s unsuccessful" \
                                      % (data_received['peer_id'])
                                conn.send(json.dumps(success))

                        elif data_received['command'] == 'list':
                            fut = executor.submit(self.list_files_index_server)
                            file_list = fut.result(timeout= None)
                            print "File list generated, %s" % file_list
                            conn.send(json.dumps(file_list))

                        elif data_received['command'] == 'search':
                            fut = executor.submit(self.search,
                                                  data_received['file_name'])
                            peer_list = fut.result(timeout= None)
                            print "Peer list generated, %s" % peer_list
                            conn.send(json.dumps(peer_list))

                        elif data_received['command'] == 'deregister':
                            fut = executor.submit(self.deregistry, data_received)
                            success = fut.result(timeout= None)
                            if success:
                                print "deregistration of Peer ID: %s successful" \
                                      % (data_received['peer_id'])
                                conn.send(json.dumps(success))
                            else:
                                print "deregistration of Peer ID: %s unsuccessful" \
                                      % (data_received['peer_id'])
                                conn.send(json.dumps(success))

                        print "hash table: Files || %s" % \
                              self.hash_table_files
                        print "hash table: Port-Peers || %s" % \
                              self.hash_table_ports_peers
                        print "hash table: Peer-Files || %s" % \
                              self.hash_table_peer_files
                        conn.close()
        except Exception as e:
            print "Server Operations error, %s " % e
            sys.exit(1)

if __name__ == '__main__':
    """
    Main method to start deamon threads for listener and operations.
    """
    try:
        args = get_args()
        print "Starting Central Indexing Server..."
        print "Starting Server Operations Thread..."
        operations_thread = ServerOperations(1, "ServerOperations",
                                             args.replica, args.port)
        operations_thread.start()
    except Exception as e:
        print e
        sys.exit(1)
    except (KeyboardInterrupt, SystemExit):
        print "Central Index Server Shutting down..."
        time.sleep(1)
        sys.exit(1)


__author__ = 'arihant'
