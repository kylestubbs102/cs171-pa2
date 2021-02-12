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
sentencesToWriteAfterStart = []

priorityQueue = queue.PriorityQueue()

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
def handle_send_request(clock, pid):
    time.sleep(2)
    message = 'request ' + str(clock) + ' ' + str(process_id)
    print("send: " + message)
    connectedClientSockets[pid].sendall(message.encode())


# handles reply command when request is received
def handle_send_reply(clock, pid):
    time.sleep(2)
    message = 'reply ' + str(clock) + ' ' + str(process_id)
    print("send: " + message)
    connectedClientSockets[pid].sendall(message.encode())


# handles release command after finished writing
def handle_send_release(clock, pid):
    time.sleep(2)
    message = 'release ' + str(clock) + ' ' + str(process_id)
    # message = 'release ' + str(lamportClock) + ' ' + str(process_id)
    print("send: " + message)
    connectedClientSockets[pid].sendall(message.encode())


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
            priorityQueue.put(tuple((count,pid)))
            # lamportClock = max(count, lamportClock) + 1   # maybe send it after
            threading.Thread(target=handle_send_reply, args=(lamportClock, parameter_pid)).start()
            lamportClock += 1
        elif 'reply' == messageCode:
            print("replies += 1")
            replies += 1
            if (replies == repliesExpected and not priorityQueue.empty()):
                tempTuple = priorityQueue.get()
                priorityQueue.put(tempTuple)
                if tempTuple[1] == process_id:
                    threading.Thread(target=handle_write_to_server).start()
        elif 'release' == messageCode:
            priorityQueue.get()
            if (replies == repliesExpected and not priorityQueue.empty()):
                tempTuple = priorityQueue.get()
                priorityQueue.put(tempTuple)
                if tempTuple[1] == process_id:
                    threading.Thread(target=handle_write_to_server).start()
        # except Exception as e:
        #     pass


tempTupleToSentence = {}

# writes each word to server, when each ready is received, increment ready counter to check
# lock counter in this thread
# if write is typed while current thread is writing, find way to continue writing
# Approach: create separate queue for client, clear on exit
# 
def handle_write_to_server():
    global replies
    global repliesExpected
    global lamportClock
    global startedWriteThread
    releaseCounter = 0
    stopped = False
    tempClock = lamportClock
    print("started")
    while not stopped:
        startedWriteThread = True
        while not priorityQueue.empty():
            tempTuple = priorityQueue.get()
            print(tempTuple)
            if (tempTuple[1] == process_id):
                sentence = tempTupleToSentence[tempTuple]
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
    startedWriteThread = False
    # for j in range(0, releaseCounter):
    for i in connectedClientIDs:
        threading.Thread(target=handle_send_release, args=(lamportClock, i)).start()
    lamportClock += 1
    print("finished")


startedWriteThread = False

# handles the users input
# create multiple threads for requests
def handle_input():
    global lamportClock
    global repliesExpected
    global startedWriteThread
    global connectedClientIDs
    global sentencesToWriteAfterStart
    while True:
        try:
            inp = input()
            if inp == 'connect':
                threading.Thread(target=handle_connect()).start()
            elif 'write' in inp:
                inp = inp[7:-1]
                lamportClock += 1
                if startedWriteThread == True:
                    sentencesToWriteAfterStart.append(inp)
                else:
                    repliesExpected += 2
                    priorityQueue.put(tuple((lamportClock, process_id)))
                    tempTupleToSentence[tuple((lamportClock, process_id))] = inp
                    for i in connectedClientIDs: # might not be correct indenting
                        threading.Thread(target=handle_send_request, args=(lamportClock, i)).start()
                    lamportClock += 1
            elif inp == 'exit':
                do_exit()
        except EOFError:
            pass


if __name__ == "__main__":
    global process_id 
    process_id = int(sys.argv[1])
    server_port = int(sys.argv[2])

    server_socket.connect((socket.gethostname(), server_port))

    threading.Thread(target=handle_input).start()
    threading.Thread(target=handle_bind).start()

    firstReady = server_socket.recv(2048).decode()