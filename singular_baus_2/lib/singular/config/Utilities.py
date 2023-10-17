from ..core import Exchange

def exchange_str_to_exchange(exchange_str):
    if exchange_str == "OKX":
        return Exchange.OKX
    elif exchange_str == "BINANCEUSDM":
        return Exchange.BINANCEUSDM
    elif exchange_str == "BINANCECM":
        return Exchange.BINANCECM
    elif exchange_str == "DERIBIT":
        return Exchange.DERIBIT
    else:
        return None
