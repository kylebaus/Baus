from enum import Enum

class InstrumentType(Enum):
    SPOT = 0,
    LINEAR_FUTURE = 1,
    INVERSE_FUTURE = 2,
    LINEAR_PERPETUAL = 3,
    INVERSE_PERPETUAL = 4,
    LINEAR_OPTION = 5,
    INVERSE_OPTION = 6