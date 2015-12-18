gnome-terminal --window-with-profile=P2P -e "bash -c python\ CIndexServer.py\ -p\ 3344\ -r\ 1;bash" &
sleep 2
gnome-terminal --window-with-profile=P2P -e "bash -c cd\ Peer1;python\ Peer.py\ -s\ 3344;bash" &
gnome-terminal --window-with-profile=P2P -e "bash -c cd\ Peer2;python\ Peer.py\ -s\ 3344;bash" &
gnome-terminal --window-with-profile=P2P -e "bash -c cd\ Peer3;python\ Peer.py\ -s\ 3344;bash" &
wait
