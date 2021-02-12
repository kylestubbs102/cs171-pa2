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
replies = 0
repliesExpected = 0
sentencesToWrite = []
sentencesToWriteAfterStart = []

priorityQueue = queue.PriorityQueue()
# actualQueue = queue.Queue()   won't need if priorityQueue locks in thread

lamportClock = 0

currentlyWriting = False


def do_exit():
    sys.stdout.flush()
    server_socket.close()
    for i in range(1,4):
        if (i != process_id):
            try:
                close_socket = connectedClientSockets[i]
                close_socket.close()
            except Exception as e:
                pass
    os._exit(0)


# handles send request when write is typed
def handle_send_request(pid):
    time.sleep(2)
    message = 'request ' + str(lamportClock) + ' ' + str(process_id)
    print("send: " + message)
    connectedClientSockets[pid].sendall(message.encode())


# handles reply command when request is received
def handle_send_reply(pid):
    time.sleep(2)
    message = 'reply ' + str(lamportClock) + ' ' + str(process_id)
    print("send: " + message)
    connectedClientSockets[pid].sendall(message.encode())


# handles release command after finished writing
def handle_send_release(pid):
    time.sleep(2)
    message = 'release ' + str(lamportClock) + ' ' + str(process_id)
    print("send: " + message)
    connectedClientSockets[pid].sendall(message.encode())


# handles request, reply, and release commands, increments lamport clock,
# redirected from handle_bind with the listening socket
def handle_listen_request(listen_socket, parameter_pid):
    global lamportClock
    global replies
    global priorityQueue
    while True:
        # try:
        messageReceive = listen_socket.recv(1024).decode()
        print("messageReceive: " + messageReceive)
        messageList = messageReceive.split()
        messageCode = messageList[0]
        count = int(messageList[1])
        pid = int(messageList[2])
        lamportClock = max(count, lamportClock) + 1
        if 'request' == messageCode:
            priorityQueue.put(tuple((lamportClock,pid)))
            # messageSend = 'reply ' + str(lamportClock) + ' ' + process_id
            # listen_socket.sendall(messageSend.encode())
            threading.Thread(target=handle_send_reply, args=[parameter_pid]).start()
        elif 'reply' == messageCode:
            print("replies += 1")
            replies += 1 # might only need 1 pid in this function
        elif 'release' == messageCode:
            priorityQueue.get() # pops it
        # except Exception as e:
        #     pass


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
    global replies
    global repliesExpected
    global lamportClock
    global startedWriteThread
    releaseCounter = 0
    stopped = False
    print("started")
    while not stopped:
        # time.sleep(2)
        # print(repliesExpected)
        # print(replies)
        if (repliesExpected == replies):
            startedWriteThread = True
            while not priorityQueue.empty():
                tempTuple = priorityQueue.get()
                if (tempTuple[1] == process_id):
                    sentence = sentencesToWrite[0]
                    sentencesToWrite.pop(0)
                    words = sentence.split()
                    while len(words):
                        server_socket.send(words[0].encode())
                        words.pop(0)
                        ready = server_socket.recv(2048).decode()
                    releaseCounter += 1
                else:
                    priorityQueue.put(tempTuple)
                    stopped = True
                    break
            if (priorityQueue.empty()):
                stopped = True
                

    while len(sentencesToWriteAfterStart):
        sentence = sentencesToWriteAfterStart[0]
        sentencesToWriteAfterStart.pop(0)
        words = sentence.split()
        while len(words):
            server_socket.sendall(words[0].encode())
            words.pop(0)
            ready = server_socket.recv(2048).decode()


    replies = 0
    repliesExpected = 0
    lamportClock += 1
    startedWriteThread = False
    for j in range(0, releaseCounter):
        for i in connectedClientIDs:
            threading.Thread(target=handle_send_release, args=[i]).start()
    print("finished")


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


startedWriteThread = False

# handles the users input
# create multiple threads for requests
def handle_input():
    global lamportClock
    global repliesExpected
    global startedWriteThread
    global connectedClientIDs
    global sentencesToWriteAfterStart
    global sentencesToWrite
    while True:
        try:
            inp = input()
            if inp == 'connect':
                threading.Thread(target=handle_connect()).start()
            elif 'write' in inp:
                inp = inp[7:-1]
                if not currentlyWriting:
                    sentencesToWrite.append(inp) # separate list for when it hasn't started
                    repliesExpected += 2
                    lamportClock += 1   # don't know if I increment here
                    priorityQueue.put(tuple((lamportClock, process_id)))
                    if not startedWriteThread:
                        threading.Thread(target=handle_write_to_server, args=([inp])).start()
                        startedWriteThread = True
                        for i in connectedClientIDs: # might not be correct indenting
                            threading.Thread(target=handle_send_request, args=[i]).start()
                else:
                    sentencesToWriteAfterStart.append(int)
            elif inp == 'exit':
                do_exit()
        except EOFError:
            pass


if __name__ == "__main__":
    # if len(sys.argv) != 3:
    #     print(f'Usage: python {sys.argv[0]} <process_id> <serverPort>')
    #     sys.exit()

    global process_id 
    process_id = int(sys.argv[1])
    server_port = int(sys.argv[2])

    server_socket.connect((socket.gethostname(), server_port))

    threading.Thread(target=handle_input).start()
    threading.Thread(target=handle_bind).start()

    firstReady = server_socket.recv(2048).decode()

    # a = tuple((2,2))
    # b = tuple((1,3))
    # q.put(item=(a))
    # q.put(item=(b))
    # print(q.get())
    # print(q.get())
    # example of comparison between tuples