import zmq

ctx = zmq.Context(1)
sock = ctx.socket(zmq.SUB)
SERVER = "54.248.0.145"
PORT = 62233
sock.connect(f"tcp://{SERVER}:{PORT}")
sock.setsockopt_string(zmq.SUBSCRIBE, "")

while True:
    msg = sock.recv_multipart()
    print(f"Received: {msg}")
