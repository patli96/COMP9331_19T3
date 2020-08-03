# COMP9331 Assignment
# Created by: Patrick Li z5180847
# This is the client program
# Python version: 3.7


import socket
import sys
import threading
import re


def receive_message(client_socket):
    """ Receive messages from the server.

    Print messages based on their message headers.
    If message header is "broadcast" or "system", then just print the message content.
            If the message header is "system" and the content is "logout",
                    it means the client is logged out by the server, because of being inactive.
                    It will send a "logout" message to the server to delete the user from the online_user_dict.
    If message header is "start_private", it will create a new socket for the private messaging connection,
        bind the IP address and port number, and begin listening.
        Once accepting a new connection,
            it will add new value to the private_connections dictionary and private_host dictionary,
                and start the private_messaging thread to handle receiving private messages.
    If message header is "private_approved", it will create a new socket to connect to the target user,
        and add new value to the private_connections dictionary.
        Once connection established, it will start the private_messaging thread to handle receiving private messages.
    If message header is a user, then print: <USER NAME>: MESSAGE CONTENT

    Args:
        client_socket: The socket of the connection with the server.
    """
    global connection_state
    global private_connections
    global private_local_host

    while connection_state:
        try:
            new_message_raw = client_socket.recv(2048).decode()
            new_message = new_message_raw.split(" ")
            if new_message and new_message_raw:
                sender = new_message[0]
                content = " ".join(new_message[1:])
                if sender == "broadcast" or sender == "system":
                    print(content)
                    if content == timeout_message:
                        client.send("logout".encode())
                        connection_state = False
                elif sender == "start_private":
                    ip_address = "".join(re.findall(r"[0123456789.]", new_message[1]))
                    port = int("".join(re.findall(r"[0123456789]", new_message[2])))
                    private_user_name = new_message[-1]
                    private_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    private_conn.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    private_conn.bind((ip_address, port))
                    private_conn.listen(20)
                    print(f'Private messaging connection with {private_user_name} has been established.')
                    while True:
                        private_user, private_address = private_conn.accept()
                        private_connections[private_user_name] = private_user
                        private_local_host[private_user_name] = private_conn
                        private_thread = threading.Thread(target=private_messaging, args=[private_user, private_user_name])
                        private_thread.start()
                elif sender == "private_approved":
                    ip_address = "".join(re.findall(r"[0123456789.]", new_message[1]))
                    port = int("".join(re.findall(r"[0123456789]", new_message[2])))
                    private_user_name = new_message[-1]
                    private_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    private_conn.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    private_conn.connect((ip_address, port))
                    private_connections[private_user_name] = private_conn
                    print(f'Private messaging connection with {private_user_name} has been established.')
                    private_thread = threading.Thread(target=private_messaging, args=[private_conn, private_user_name])
                    private_thread.start()
                else:
                    print(f'<{sender}>: {content}')
        except:
            break
    connection_state = False


def private_messaging(private_socket, private_user):
    """ Receive messages from a p2p connection.

        Once receiving a new message, it will split the string to a list,
            and check the first element of the message list.
        If the first element is "logout", it means that the other user of this p2p connection has logged out,
            and the socket for the private connections will close.
        Else, print the message it received.
        If there is an exception during the connection,
            it will close the socket in the private_connections dictionary first by finding the name of the other user,
            and then it will check if there's a relevant socket in the private_local_host dictionary,
                if so close the socket in the same way.

        Args:
            private_socket  : The socket of this private connection in the private_connections dictionary.
            private_user    : The name of the other user in the private connection.
    """
    global connection_state
    global private_connections
    global private_local_host
    try:
        while connection_state:
            new_message = private_socket.recv(2048).decode().split(" ")
            if len(new_message) != 0:
                if len(new_message) == 1 and new_message[0] == "logout":
                    break
                print(f'<{private_user} (private)>: {" ".join(new_message[2:])}')
        print(f'Private connection with {private_user} lost.')
        private_connections[private_user].close()
        del private_connections[private_user]
    except:
        print(f'Private connection with {private_user} lost.')
        if private_user in private_connections:
            private_connections[private_user].close()
            del private_connections[private_user]
        if private_user in private_local_host:
            private_local_host[private_user].close()
            del private_local_host[private_user]
        sys.exit()


# checks whether sufficient arguments have been provided
if len(sys.argv) != 3:
    print("Invalid input.")
    sys.exit()


# check if the input is in correct type
try:
    server_ip = sys.argv[1]
    server_port = int(sys.argv[2])
except ValueError:
    print("The input is in a wrong format.\n")


# create the client socket
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)


# connect the client socket to the server
client.connect((server_ip, server_port))


# create welcome message and timeout message
welcome_message = ["Invalid password.", "Welcome and enjoy your chat!",
                   "The user is already online.", "User name doesn't exit.",
                   "Your account has been blocked. Please try again later."]
timeout_message = "You are logged out by the server for inactive."


# create a dictionary to store all the sockets for private connections: {'USER NAME': SOCKET}
private_connections = {}


# create a dictionary to store all the sockets acting as a server for private connections: {'USER NAME': SOCKET}
private_local_host = {}


# Set a flag to record user's login state.
# While the flag is false,
#       it will keep prompting the user the to input user name and password,
#       and receive a welcome message and print it.
# If the user receive the successful message then will set the flag to True.
log_in = False
while not log_in:
    try:
        user_name = input("Username: ")
        user_password = input("Password: ")
        client.send((user_name + " " + user_password).encode())
        received_welcome_message = client.recv(2048).decode()
        print(received_welcome_message)
        if received_welcome_message == welcome_message[1]:
            log_in = True
        elif received_welcome_message == welcome_message[0]:
            while not log_in:
                user_password = input("Password: ")
                client.send((user_name + " " + user_password).encode())
                received_welcome_message = client.recv(2048).decode()
                print(received_welcome_message)
                if received_welcome_message == welcome_message[1]:
                    log_in = True
                elif received_welcome_message == welcome_message[2]:
                    break
                elif received_welcome_message == welcome_message[4]:
                    client.close()
                    sys.exit()
        else:
            continue
    except:
        print("Connection lost.")
        client.close()
        sys.exit()


# Set the flag of the state of connection to True.
connection_state = True


# While the connect state is True,
#       get the input message and split it into a list.
#       If the message is "logout", set the state to False after sending it to the server.
#       If the first element of the list is "private", check if the target user name is valid,
#           if so, send the message to the p2p socket.
#       If the first element of the list is "stopprivate", check if the target user name is valid,
#           if so, close the p2p socket and send a "logout" message to the target user p2p socket.
# When the state turns to False, close the connection.
while connection_state:
    # Start the thread to receive message.
    thread = threading.Thread(target=receive_message, args=[client]).start()
    message = input()
    message_list = message.split(" ")
    if len(message_list) != 0:
        if message == "logout":
            client.send(message.encode())
            connection_state = False
            for key in list(private_connections):
                private_connections[key].send("logout".encode())
                private_connections[key].close()
            if len(private_local_host) != 0:
                for key in list(private_local_host):
                    private_local_host[key].close()
        elif message_list[0] == "private":
            if len(private_connections) != 0:
                dest_user = message_list[1]
                if dest_user in private_connections:
                    private_connections[dest_user].send(message.encode())
                else:
                    print(f'Error. Private messaging to {dest_user} not enable.')
            else:
                print("Error. No private messaging connection established.")
        elif message_list[0] == "stopprivate" and len(message_list) == 2:
            if len(private_connections) != 0:
                dest_user = message_list[1]
                if dest_user in private_connections:
                    private_connections[dest_user].send("logout".encode())
                    private_connections[dest_user].close()
                    if dest_user in private_local_host:
                        private_local_host[dest_user].close()
                else:
                    print(f'Error. No private connection with {dest_user} established.')
            else:
                print("Error. No private connection established.")
        else:
            client.send(message.encode())


# close the client socket.
client.close()
sys.exit()
