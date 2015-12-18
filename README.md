Peer-to-Peer File Sharing System:
	
	The Peer-to-Peer File Sharing system is written using Python programming language.

	Requirements:

	* Python version: 2.* , should be equal or greater than 2.6.

Below are the steps to be followed to execute and run the program.

Method 1:

	Central Indexing Server:
	
	1.1	File name “CIndexServer.py” contains the source code
		
	1.2	To execute the program, follow the below steps.

			$ python CIndexServer.py [-h] -p PORT [-r REPLICA]

		Standard Arguments for talking to Central Index Server

		optional arguments:
			  -h, --help            show this help message and exit
			  -p PORT, --port PORT  Server Port Number
			  -r REPLICA, --replica REPLICA
                        			Data Replication Factor

		Note: * arugment -p is mandatory
		      * default replication factor is set to 1

		Example:
			$ python CIndexServer.py -p 3344 -r 2
			or
			$ python CIndexServer.py -p 3344
		
		The above example will start the central index server on socket port 3344 with replication factor 2 or 1.

	Peer:

	2.1	Depending on the requirement, open n number of terminals (here n = 3).

	2.2	Change directory to Peer#(1/2/3)

	2.3	File name “Peer.py” contains the source code
		
	2.4	To execute the program, follow the below steps.

			$ python Peer.py [-h] -s SERVER

		Standard Arguments for talking to Central Index Server

		optional arguments:
			  -h, --help            show this help message and exit
			  -s SERVER, --server SERVER
			                        Index Server Port Number

		Note: * arugment -s is mandatory and need to specify Index Server Port Number.

		Example:
			$ python Peer.py -s 3344

	2.5	This outputs the below:  

			eg: $ python Peer.py -s 3344
			Starting Peer...
			Registring Peer with Server...
			registration successfull, Peer ID: 127.0.0.1:23838
			Stating Peer Server Deamon Thread...
			Starting File Handler Deamon Thread...
			********************
			1. List all files in Index Server
			2. Search for File
			3. Get File from Peer
			4. Exit
			*****
			Enter choise : 

Method 2:

	The entire process is automated using shell script.

	Requirements to run the shell script:

		1. gnome-terminal

	To execute the program, follow the below steps.

		$ chmod +x start.sh
		$ ./start.sh

