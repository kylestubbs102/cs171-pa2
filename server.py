import socket
import threading
import time
import sys
import os


def do_exit(output_file, server_socket):
    sys.stdout.flush()
    output_file.flush()
    server_socket.close()
    os._exit(0)


def handle_input(output_file, server_socket):
    while True:
        try:
            inp = input()
            if inp == 'exit':
                do_exit(output_file, server_socket)
        except EOFError:
            pass


def handle_client(client_socket, address, output_file):
    print(f'Server connected to {address}')
    while True:
        time.sleep(2)
        client_socket.send(b'ready')
        try:
            word = client_socket.recv(1024).decode()
        except socket.error as e:
            print(f'Client {address} forcibly disconnected with {e}.')
            client_socket.close()
            break
        if not word:
            print(f'Client {address} disconnected.')
            client_socket.close()
            break
        elif word.find(' ') != -1:
            # send error and don't write if the
            # client sends more than one word
            print('Received invalid word \'{word}\' from {address}')
            client_socket.send(b'error')
        else:
            output_file.write(word + ' ')
            output_file.flush()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f'Usage: python {sys.argv[0]} <outputFile> <serverPort>')
        sys.exit()

    PORT = sys.argv[2]
    server_socket = socket.socket()
    server_socket.bind((socket.gethostname(), int(PORT)))
    server_socket.listen(32)
    print(f'Server listening on port {PORT}.')

    output_file = open(sys.argv[1], 'w')

    threading.Thread(target=handle_input, args=(
        output_file, server_socket)).start()

    while True:
        try:
            client_socket, address = server_socket.accept()
            threading.Thread(target=handle_client, args=(
                client_socket, address, output_file)).start()
        except KeyboardInterrupt:
            do_exit(output_file, server_socket)
