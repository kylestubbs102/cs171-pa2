import socket
import threading
import time
import sys
import os
import json
import queue

with open("config.json", "r") as jsonfile:
    data = json.load(jsonfile)
    jsonfile.close()

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # might not need parameters

connectedClientIDs = []
connectedClientSockets = {}
replies = []

priorityQueue = queue.PriorityQueue()
# actualQueue = queue.Queue()   won't need if priorityQueue locks in thread

lamportClock = 0


def do_exit():
    sys.stdout.flush()
    server_socket.close()
    for i in range(1,4):
        if (i != process_id):
            try:
                print(len(connectedClientSockets))
                print(len(connectedClientIDs))
                close_socket = connectedClientSockets[i]
                close_socket.close()
            except Exception as e:
                pass
    os._exit(0)


# connects to all sockets on connect command, puts ID and socket in map and list
def handle_connect():
    global connectedClientSockets
    global connectedClientIDs
    for i in range(1,4):
        try:
            if i != process_id and i not in connectedClientIDs:
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client_socket.connect((socket.gethostname(), int(data[str(i)])))
                client_socket.sendall(str(process_id).encode())
                connectedClientIDs.append(i)
                connectedClientSockets[i] = client_socket
        except Exception as e:
            pass


# handles send request when write is typed
def handle_send_request(pid):
    time.sleep(2)
    message = 'request ' + lamportClock + ' ' + pid
    connectedClientSockets[pid].sendall(message.encode())


# handles reply command when request is received
def handle_send_reply(pid):
    time.sleep(2)
    message = 'reply ' + lamportClock + ' ' + pid
    connectedClientSockets[pid].sendall(message.encode())


# handles release command after finished writing
def handle_send_release(pid):
    time.sleep(2)
    message = 'release ' + lamportClock + ' ' + pid
    connectedClientSockets[pid].sendall(message.encode())


# handles request, reply, and release commands, increments lamport clock,
# redirected from handle_bind with the listening socket
def handle_listen_request(listen_socket, parameter_pid):
    global lamportClock
    while True:
        try:
            messageReceive = listen_socket.recv(1024).decode()
            messageList = messageReceive.split()
            messageCode = messageReceive[0]
            count = int(messageList[1])
            pid = int(messageList[2])
            lamportClock = max(count, lamportClock) + 1
            print(lamportClock)
            if 'request' == messageCode:
                priorityQueue.put(tuple((lamportClock,pid)))
                messageSend = 'reply ' + lamportClock + ' ' + process_id
                listen_socket.sendall(messageSend.encode())
                threading.Thread(target=handle_send_reply, args=(parameter_pid)).start()
            elif 'reply' == messageCode:
                replies.append([count,pid]) # might only need 1 pid in this function
            elif 'release' == messageCode:
                priorityQueue.get() # pops it
        except IndexError as IE:
            pass


# constantly listening for when the user enters 'connect' and connections are sent out
# receives other socket's pid and passes it as a variable
def handle_bind():
    bind_socket = socket.socket()
    bind_socket.bind((socket.gethostname(), data[str(process_id)]))
    bind_socket.listen(32)
    while True:
        other_client_socket, address = bind_socket.accept()
        pid = other_client_socket.recv(2048).decode()
        threading.Thread(target=handle_listen_request, args=(other_client_socket, int(pid))).start()


# writes each word to server, when each ready is received, increment ready counter to check
# lock counter in this thread
# if write is typed while current thread is writing, find way to continue writing
# Approach: create separate queue for client, clear on exit
# 
def handle_write_to_server(sentence):
    print(sentence.split())


# handles the users input
# create multiple threads for requests
def handle_input():
    global lamportClock
    while True:
        try:
            inp = input()
            if inp == 'connect':
                threading.Thread(target=handle_connect()).start()
            elif 'write' in inp:
                inp = inp[7:-1]
                lamportClock += 1   # don't know if I increment here
                threading.Thread(target=handle_write_to_server, args=([inp])).start()
                for i in connectedClientIDs:
                    threading.Thread(target=handle_send_request, args=(i)).start()
            elif inp == 'exit':
                do_exit()
        except EOFError:
            pass


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f'Usage: python {sys.argv[0]} <process_id> <serverPort>')
        sys.exit()

    global process_id 
    process_id = int(sys.argv[1])
    server_port = int(sys.argv[2])

    server_socket.connect((socket.gethostname(), server_port))

    threading.Thread(target=handle_input).start()
    threading.Thread(target=handle_bind).start()

    # a = tuple((2,2))
    # b = tuple((1,3))
    # q.put(item=(a))
    # q.put(item=(b))
    # print(q.get())
    # print(q.get())
    # example of comparison between tuples