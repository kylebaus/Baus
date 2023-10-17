from enum import Enum

class RejectReasonType(Enum):
    RATE_LIMITED = 0,
    ALREADY_FILLED = 1,
    ALREADY_CANCELED = 2