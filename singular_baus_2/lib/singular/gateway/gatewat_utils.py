from singular.core import Instrument, InstrumentType


def okx_convert_quantity(quantity: float, instrument: Instrument, price: float = None):
    """
    Converts quantity, which is always supplied in number of base currency to number of contracts. Only applies to
    futures and swaps
    e.g. convert_quantity(1, 'AAVE-USDT-SWAP') -> 1 / contract_value=0.1 = 10 contracts
    e.g. convert_quantity(0.1, 'BTC-USD-SWAP') -> 0.1 / contract_value=100 * limit_price=20000 = 20 contracts
    Args:
        price: price to trade at. Only relevant for inverse futures and swaps
        quantity: number of base currency
        instrument: Instrument object of target market

    Returns: number of contracts to be traded

    """
    if instrument.contract_value:  # only swaps and futures should have this field populated
        quantity /= instrument.contract_value
        if instrument.type in [InstrumentType.INVERSE_PERPETUAL, InstrumentType.INVERSE_FUTURE]:
            quantity *= price
    return quantity