# # from fastapi import FastAPI

# # app = FastAPI()

# # @app.get("/")
# # def read_root():
# #   return {"message": "Hello from Laptop A!"}

# # Source - https://stackoverflow.com/q/67539425
# # Posted by Michał Strugarek
# # Retrieved 2026-09-06, License - CC BY-SA 4.0

# from socket import *


# lista = ['computer']

# s = socket(AF_INET, SOCK_STREAM)

# port = 21312
# s.bind(('172.20.10.2', port))

# s.listen(5)
# while True:
#     for i in range (0, len(lista)):
#         a = str(lista[i]).encode()
#         a = str(lista[i]).encode()
#         c, addr = s.accept()
#         print("CONNECTION WITH",addr)
#         c.send(a)
#         print(a)
#         c.close()
            
import socket

HOST = "0.0.0.0"
PORT = 21312

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

server.bind((HOST, PORT))
server.listen(5)

print(f"Server listening on port {PORT}...")

while True:
    client, addr = server.accept()

    print("Connection from:", addr)

    message = "computer"
    client.sendall(message.encode())

    client.close()

