import sys
from socket import socket, create_connection, AF_INET, SOCK_STREAM

from serial import Serial
from drivers.switcher.switcher import SwitcherInterface

# This is going to need to be async
RECVBUF = 1024

server = '161.31.67.53'
port = 5000

