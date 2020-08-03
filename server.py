# COMP9331 Assignment
# Created by: Patrick Li z5180847
# This is the server program
# Python version: 3.7


import socket
import csv
import sys
import threading
import time


# checks whether sufficient arguments have been provided
if len(sys.argv) != 4:
    print("Invalid input.")
    sys.exit()


# check if the input is in correct type
try:
    server_port = int(sys.argv[1])
    block_duration = int(sys.argv[2])
    timeout = int(sys.argv[3])
except ValueError:
    print("The input is in a wrong format.")


# create server socket
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)


# bind the server with the localhost and input port number
server.bind(("127.0.0.1", server_port))


# store all valid user information in a dictionary : {'USER NAME': 'USER PASSWORD'}
with open('credentials.txt') as file:
    csv_reader = csv.reader(file)
    authentications = {}
    for row in csv_reader:
        info = row[0].split(" ")
        authentications[info[0]] = info[1]


# start listen
server.listen(100)


# record the server starting time.
start_time = time.time()


# create a dictionary to store all online users: {'USER NAME': 'USER_ADDRESS'}
online_user_dict = {}


# create a dictionary to store login times of all users: {'USER NAME': [LOGIN TIME, LOGIN TIME, LOGIN TIME, ...]}
login_time_dict = {}
for user in authentications:
    login_time_dict[user] = []


# create a dictionary to store all blocked users for each user: {'USER NAME': ['USER 1', 'USER 2', 'USER 3', ... ]}
blocked_dict = {}
for user in authentications:
    blocked_dict[user] = []


# create a dictionary to store the failed login attempt for each user: {'USER NAME': TIMES}
fail_dict = {}
for user in authentications:
    fail_dict[user] = 0


# create a dictionary to store all offline messages: {'RECIPIENT USER NAME': ['MESSAGE 1', 'MESSAGE 2', ... ]}
offline_message_dict = {}

# create a dictionary to store addresses of all users: {'USER NAME': ADDRESS PAIR}
address_dict = {}


def user_thread(client, client_address):
    """ The thread for each client connected to the server.

    First process the login part.
    If the user logs in successfully then process receiving message from the user.

    Args:
        client:         The client socket.
        client_address: The client address.
    """
    global blocked_dict
    global online_user_dict
    global fail_dict
    global authentications
    global offline_message_dict


    # create a flag of user's login state and a flag of user's connection state.
    login = False
    connection_state = True


    # A flag is used to record the user's login state
    # Every time after receiving the user name and password, the user_authentication function is called.
    # If it returns "SUCCESS", the function if_already_online will be called.
    #       If the function returns False, the user will log in successfully,
    #               a broadcast notification will be sent,
    #               the user will be added in the online_user_dict,
    #               the login time will be added in the login_time_dict,
    #               the failed login times will be reset to 0.
    #               Also, it will check the offline_message_dict. If there is message for the user, send it.
    #       If the function returns True, the login attempt will be denied.
    # If it returns "FAIL", this user's failed time will be increased by one in fail_dict,
    #       and the function check_failed_times is called to check if it reaches 3 consecutive times.
    # If it returns "BLOCKED", the user will be informed being blocked.
    # If it returns "NOT EXIST", the user will be informed.
    while not login:
        try:
            user_info = client.recv(2048).decode().split(" ")
            user_name = user_info[0]
            user_password = user_info[1]
            if user_authentication(user_name, user_password) == "SUCCESS":
                if not if_already_online(user_name):
                    client.send(welcome_message[1].encode())
                    broadcast(f'{user_name} logs in.', user_name)
                    online_user_dict[user_name] = client
                    address_dict[user_name] = client_address
                    login_time_dict[user_name].append(time.time())
                    fail_dict[user_name] = 0
                    if user_name in offline_message_dict:
                        notification = ["system You have received the following offline messages:\n",
                                        "Above is all your offline messages."]
                        client.send(notification[0].encode())
                        for offline_message in offline_message_dict[user_name]:
                            client.send(offline_message.encode())
                        client.send(notification[1].encode())
                        del offline_message_dict[user_name]
                    login = True
                else:
                    client.send(welcome_message[2].encode())
                    fail_dict[user_name] = 0
            elif user_authentication(user_name, user_password) == "FAIL":
                fail_dict[user_name] += 1
                if not check_failed_times(user_name):
                    block_message = "Your account has been blocked. Please try again later."
                    client.send(block_message.encode())
                    connection_state = False
                    break
                else:
                    client.send(welcome_message[0].encode())
            elif user_authentication(user_name, user_password) == "BLOCKED":
                block_message = "Your account has been blocked. Please try again later."
                client.send(block_message.encode())
            else:
                client.send(welcome_message[3].encode())
        except:
            login = False
            connection_state = False


    # set a timer
    # If times out the client will be logged out automatically
    # timer = threading.Timer(timeout, log_out, [client])
    # timer.start()


    # While the connection state is True, handle the received messages from client.
    # First, get the message header, then deal with the message based on different headers.
    # If the header is "message",
    #       check if the sender is blocked by the recipient, if not then send it.
    # If the header is "broadcast",
    #       send the broadcast message to all online users, and check if the sender is blocked as well.
    # If the header is "whoelse",
    #       send a name list of currently online users to the requester.
    # If the header is "whoelsesince",
    #       send a name list of users who logged in at any time with the past specific time.
    # If the header is "block",
    #       block the user as requested.
    # If the header is "unblock",
    #       unblock the user as requested.
    # If the header is "logout",
    #       delete the user name from the online_user_dict and login_time_dict, then close the client socket.
    # If the header is "startprivate",
    #       it will call the start_private() function to start a private connection as required.
    # Else,
    #       send an error message to the user the command is invalid.
    while connection_state:
        try:
            message = client.recv(2048).decode().split(" ")
            # check_timer(timer, client)
            message_header = message[0]
            # get the list of keys and values from online_user_dict respectively.
            # Since the index of combined key (user_name) and value (user_address) is the same,
            # the user_name can be extracted in this way.
            online_user_name_list = list(online_user_dict.keys())
            online_user_address_list = list(online_user_dict.values())
            user_name = online_user_name_list[online_user_address_list.index(client)]
            if message_header == "message" and len(message) >= 3:
                send_message(user_name, message[1], message[2:])
            elif message_header == "broadcast" and len(message) >= 2:
                broadcast(f'<{user_name}>: ' + " ".join(message[1:]), user_name)
            elif message_header == "whoelse" and len(message) == 1:
                whoelse(user_name)
            elif message_header == "whoelsesince" and len(message) == 2:
                whoelsesince(user_name, message[1])
            elif message_header == "block" and len(message) == 2:
                if message[1] != user_name:
                    user_to_be_blocked = message[1]
                    block(user_name, user_to_be_blocked)
                else:
                    send_message("system", user_name, "Error. Invalid command.".split(" "))
            elif message_header == "unblock" and len(message) == 2:
                if message[1] != user_name:
                    user_to_be_unblocked = message[1]
                    unblock(user_name, user_to_be_unblocked)
                else:
                    send_message("system", user_name, "Error. Invalid command.".split(" "))
            elif message_header == "logout" and len(message) == 1:
                broadcast(f'{user_name} has logged out.', user_name)
                del online_user_dict[user_name]
                connection_state = False
            elif message_header == "startprivate" and len(message) == 2:
                if message[1] != user_name:
                    start_private(user_name, message[1], client)
                else:
                    send_message("system", user_name, "Error. Invalid command.".split(" "))
            else:
                send_message("system", user_name, "Error. Invalid command.".split(" "))
        except:
            online_user_name_list = list(online_user_dict.keys())
            online_user_address_list = list(online_user_dict.values())
            del online_user_dict[online_user_name_list[online_user_address_list.index(client)]]
            broadcast(f'{user_name} LOGS OUT', user_name)
            connection_state = False

    client.close()
    sys.exit()


def user_authentication(name, password):
    """ Check if the user name and password is valid or not.

    It will check whether the user name is in the authentications dictionary as a key.
    If the value of the key is a list, it means that the user has been blocked.
    If the user name is not in the dictionary, it means is not a valid user name.

    Args；
        name:       User name
        password:   Input password

    Returns:
        "SUCCESS":      Input user name and password are valid.
        "BLOCKED":      This user has been blocked.
        "FAIL":         Invalid password.
        "NOT EXIST":    User name is invalid.
    """
    if name in authentications:
        if authentications[name] == password:
            return "SUCCESS"
        elif authentications[name] is list:
            return "BLOCKED"
        else:
            return "FAIL"
    else:
        return "NOT EXIST"

'''
def check_timer(timer, client_socket):
    """The function below is to check and restart the timer.
    This function will be called every time the client server send a message to the server.
    If it's called again, it will cancel the previous timer and restart.
    If times out, the client will be logged out automatically."""
    if timer.is_alive():
        timer.stop()
    timer = threading.Timer(timeout, log_out, [client_socket])
    timer.start()
    return


def log_out(client_socket):
    try:
        timeout_message = "system You are logged out by the server for inactive."
        client_socket.send(timeout_message.encode())
    except OSError:
        client_socket.close()
'''

def check_failed_times(name):
    """ Check how many times the login attempt have failed consecutively with the same user name.

    It will check the value in the fail_dict of the key which is user name.
    If the user has failed exactly 3 times,
            set the password of this user in authentications dictionary to a list: [password, 0],
            and a timer will be set, the interval of which is block_duration.
                    When times up, the function set_user_unblocked will be called.
    Otherwise, simply return True or False.

    Args:
        name: User name

    Returns:
        False: The user has been blocked or was just blocked.
        True: The user is not blocked.
    """
    if fail_dict[name] == 3:
        authentications[name] = [authentications[name], 0]
        block_thread = threading.Timer(block_duration, set_user_unblocked, [name])
        block_thread.start()
        return False
    elif fail_dict[name] > 3:
        return False
    else:
        return True


def set_user_unblocked(name):
    """ Unblock the user.

    It will set the password of the user back to the original one in the authentications dictionary.

    Args:
        name: User name
    """
    authentications[name] = authentications[name][0]
    fail_dict[name] = 0


def send_message(source_user, dest_user, content):
    """ Forward message to a specific user.

    If the recipient exist,
            if the recipient is online, i.e. in the online_user_dict,
                    and if the user doesn't block the message sender, send the message to it.
                    if the user has blocked the sender,
                            the message won't be sent, and sender will be informed of being blocked by the recipient.
            if the recipient is offline,
                    store the message at the server and send it when the recipient is online.
    If the recipient doesn't exist, inform the sender.

    Args:
        source_user:    The sender.
        dest_user:      The recipient.
        content:        The content of the message.
    """
    if dest_user in authentications:
        if dest_user in online_user_dict:
            if source_user not in blocked_dict[dest_user]:
                content = source_user + " " + " ".join(content)
                online_user_dict[dest_user].send(content.encode())
            else:
                content = f'system Your message could not be delivered to {dest_user}. You have been blocked.'
                online_user_dict[source_user].send(content.encode())
        else:
            if source_user not in blocked_dict[dest_user]:
                content = f'<{source_user}>: ' + " ".join(content) + "\n"
                if dest_user in offline_message_dict:
                    offline_message_dict[dest_user].append(content)
                else:
                    offline_message_dict[dest_user] = [content]
                response = f'system {dest_user} is currently offline. Your message has been sent as an offline message.'
                online_user_dict[source_user].send(response.encode())
            else:
                content = f'system The use is offline. ' \
                    f'Your message could not be delivered to {dest_user}. You have been blocked.'
                online_user_dict[source_user].send(content.encode())
    else:
        content = "system Error. Invalid user."
        online_user_dict[source_user].send(content.encode())


def broadcast(message, sender):
    """ Send broadcast message/notification to all users currently online.

    Loop the online_user_dict's key, if the sender isn't blocked, send the broadcast message/notification,
    or inform the sender the message can't be send because of being blocked.

    Args:
        message:    The content of broadcast message/notification.
        sender:     The sender of the broadcast message/notification.
    """
    message = "broadcast " + message
    for online_user in online_user_dict:
        if online_user != sender:
            if sender not in blocked_dict[online_user]:
                online_user_dict[online_user].send(message.encode())
            else:
                online_user_dict[sender].send(
                    f'system Your message could not be delivered to {online_user}. You have been blocked.'.encode())


def whoelse(name):
    """ Send a name list of all users currently online to the user requiring for it.

    Get the key list of online_user_dict, i.e. a name list, and send it back to the user in alphabetical order.

    Args:
        name:   Requester's user name.
    """
    name_list = list(online_user_dict.keys())
    name_list.remove(name)
    name_list.sort()
    online_user_dict[name].send(("system Currently online users: " + ", ".join(name_list)).encode())


def whoelsesince(name, duration):
    """ Send a name list of users who logged in within the past <duration> time

    First get the current time.
    If the <duration> time is greater than when the server started running,
            send all the users who logged in excluding the requester.
    Else,
            loop the login_time_dict, check the last element of the login time list for each user.
            If it is less than the <duration> time, append the user name to the list, excluding the requester.
            Sort the list in a alphabetical order, and then send it to the requester.
    If the input cannot be converted to float, then send an error message to the requester.

    Args:
        name:       Requester's user name.
        duration:   A specific time.
    """
    try:
        current_time = time.time()
        duration = float(duration)
        name_list = []
        if current_time - duration <= start_time:
            for logged_in_user in login_time_dict:
                if len(login_time_dict[logged_in_user]) > 0 and logged_in_user != name:
                    name_list.append(logged_in_user)
            name_list.sort()
            response = f'system Users who logged in within {duration} are: ' + ", ".join(name_list)
            online_user_dict[name].send(response.encode())
        else:
            for logged_in_user in login_time_dict:
                if len(login_time_dict[logged_in_user]) > 0 and logged_in_user != name:
                    if current_time - login_time_dict[logged_in_user][-1] < duration:
                        name_list.append(logged_in_user)
            name_list.sort()
            response = f'system Users who logged in within {duration} are: ' + ", ".join(name_list)
            online_user_dict[name].send(response.encode())
    except ValueError:
        response = "system Error. Invalid command."
        online_user_dict[name].send(response.encode())


def block(name, name_to_be_blocked):
    """ Block a user as requested.

    Firstly check if the user exists.
            If it exists, then check if the user to be blocked is in the requester's black list.
                    If so, inform the requester that the user has been blocked already.
                    If not, append the user to the black list of the user in blocked_dict.
            If it doesn't, then inform the requester of this error.

    Args:
        name:               Requester's user name.
        name_to_be_blocked: The user is going to be blocked.
    """
    block_message = [f'system {name_to_be_blocked} is blocked.', "system You have already blocked this user.",
                     "system The user doesn't exist."]
    if name_to_be_blocked in authentications:
        if name_to_be_blocked not in blocked_dict[name]:
            blocked_dict[name].append(name_to_be_blocked)
            online_user_dict[name].send(block_message[0].encode())
        else:
            online_user_dict[name].send(block_message[1].encode())
    else:
        online_user_dict[name].send(block_message[2].encode())


def unblock(name, name_to_be_unblocked):
    """ Unblock the user as requested.

    Check if the user is in the requester's black list.
            If so, then remove it from the list and inform the requester.
            If not, then inform the requester that the user has not been blocked.

    Args:
        name:                   Requester's user name.
        name_to_be_unblocked:   The user is going to be unblocked.
    """
    unblock_message = [f'system Error. {name_to_be_unblocked} is not blocked.',
                       f'system {name_to_be_unblocked} is unblocked.']
    if name_to_be_unblocked in blocked_dict[name]:
        blocked_dict[name].remove(name_to_be_unblocked)
        online_user_dict[name].send(unblock_message[1].encode())
    else:
        online_user_dict[name].send(unblock_message[0].encode())


def if_already_online(name):
    """ Check if the user is already online.

    Check if the user name is in the online_user_dict.

    Args:
        name:   User name.

    Returns:
        True:   The user is already online.
        False:  The user is not online.
    """
    if name in online_user_dict:
        return True
    else:
        return False


def start_private(source_user, dest_user, client):
    """ Start a private messaging connection (peer-to-peer connection)

        If the target user exists and is online and hasn't block the user who started the private connection,
            it will send a message containing the address of the target user itself
                and the name of the user started the private connection to the target user,
            and send another message containing the address of the target user and the name of the target user
                to the user started the private connection.
        Else, it will send an error message containing the error information.

        Args:
            source_user : The user who started the private connection.
            dest_user   : The target user.
            client      : The socket of the user who started the private connection.
    """
    if dest_user in authentications:
        if dest_user in online_user_dict:
            if source_user not in blocked_dict[dest_user]:
                content_1 = f'start_private {address_dict[dest_user]} {source_user}'
                content_2 = f'private_approved {address_dict[dest_user]} {dest_user}'
                online_user_dict[dest_user].send(content_1.encode())
                time.sleep(0.5)
                client.send(content_2.encode())
            else:
                content = f'system Private messaging with {dest_user} is enable. You have been blocked by {dest_user}.'
                client.send(content.encode())
        else:
            content = f'system Private messaging with {dest_user} is enable. The user is offline.'
            client.send(content.encode())
    else:
        content = f'system Private messaging with {dest_user} is enable. The user does not exist.'
        client.send(content.encode())


# create welcome message
welcome_message = ["Invalid password.", "Welcome and enjoy your chat!",
                   "The user is already online.", "User name doesn't exit."]

while True:
    # accept the user's socket request
    # and get the user's name and password from the login message received
    user, address = server.accept()
    thread = threading.Thread(target=user_thread, args=[user, address])
    thread.start()

# close the server socket.
server.close()
