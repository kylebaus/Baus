from enum import Enum

class OrderType(Enum):
    LIMIT = 0,
    POST_ONLY = 1,
    IOC = 2