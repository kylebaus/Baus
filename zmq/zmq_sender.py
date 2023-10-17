import zmq
import time

ctx = zmq.Context(1)
sock = ctx.socket(zmq.PUB)
SERVER = "54.248.0.145"
PORT = 62232
sock.connect(f"tcp://{SERVER}:{PORT}")
time.sleep(1)

def send_order(order):
    sock.send_multipart(order)

def place_order(order_id, side, product, quantity, price, account):
    message = f"PLACE PT76AAAAQ{order_id} {side} ZMQ.BUF/P_{product} {quantity} @ {price} (PENDING,PLACE,LIMIT,{account})"
    print(message)
    send_order([b'PT76', message.encode()])

def cancel_order(order_id, side, product, quantity, price, account):
    message = f"CANCEL PT76AAAAQ{order_id} {side} ZMQ.BUF/P_{product} {quantity} @ {price} (PENDING,CANCEL,LIMIT,{account})"
    print(message)
    send_order([b'PT76', message.encode()])

def cancel_all_orders(account):
    message = f"CANCEL-ALL {account} BTCUSDT BUF"
    print(message)
    send_order([b'PT76', message.encode('UTF-8')])
    # send_order([b'PT76', b'CANCEL-ALL jynx1 BTCUSDT BUF'])

def cancel_all_orders_for_product(product, account):
    message = f"CANCEL-ALL {account} {product} BUF"
    print(message)
    send_order([b'PT76', message.encode()])


#### run this file to cancel all orders
if __name__ == "__main__":
    # cancel_all_orders("jynx1")
    cancel_all_orders_for_product("OCEANUSDT", "jynx1")
