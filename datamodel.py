"""
IMC Prosperity datamodel.py
---------------------------
Local copy of the data model classes that IMC's servers provide in the
submission environment. Keep this file next to your trader.py so local
backtesters and your IDE can resolve `from datamodel import ...` imports.

Do NOT upload this file to IMC — they provide their own version at runtime.
"""

from json import JSONEncoder
from typing import Dict, List

# Type aliases used throughout Prosperity code
Time = int
Symbol = str
Product = str
Position = int
UserId = str
Observation = int


class Listing:
    def __init__(self, symbol: Symbol, product: Product, denomination: Product):
        self.symbol = symbol
        self.product = product
        self.denomination = denomination


class ConversionObservation:
    def __init__(
        self,
        bidPrice: float,
        askPrice: float,
        transportFees: float,
        exportTariff: float,
        importTariff: float,
        sugarPrice: float,
        sunlightIndex: float,
    ):
        self.bidPrice = bidPrice
        self.askPrice = askPrice
        self.transportFees = transportFees
        self.exportTariff = exportTariff
        self.importTariff = importTariff
        self.sugarPrice = sugarPrice
        self.sunlightIndex = sunlightIndex


class Observations:
    def __init__(
        self,
        plainValueObservations: Dict[Product, Observation],
        conversionObservations: Dict[Product, ConversionObservation],
    ):
        self.plainValueObservations = plainValueObservations
        self.conversionObservations = conversionObservations

    def __str__(self) -> str:
        return (
            "(plainValueObservations: "
            + str(self.plainValueObservations)
            + ", conversionObservations: "
            + str(self.conversionObservations)
            + ")"
        )


class Order:
    def __init__(self, symbol: Symbol, price: int, quantity: int) -> None:
        self.symbol = symbol
        self.price = price
        self.quantity = quantity

    def __str__(self) -> str:
        return "(" + self.symbol + ", " + str(self.price) + ", " + str(self.quantity) + ")"

    def __repr__(self) -> str:
        return "(" + self.symbol + ", " + str(self.price) + ", " + str(self.quantity) + ")"


class OrderDepth:
    def __init__(self):
        self.buy_orders: Dict[int, int] = {}
        self.sell_orders: Dict[int, int] = {}


class Trade:
    def __init__(
        self,
        symbol: Symbol,
        price: int,
        quantity: int,
        buyer: UserId = None,
        seller: UserId = None,
        timestamp: int = 0,
    ) -> None:
        self.symbol = symbol
        self.price = price
        self.quantity = quantity
        self.buyer = buyer
        self.seller = seller
        self.timestamp = timestamp

    def __str__(self) -> str:
        return (
            "("
            + self.symbol
            + ", "
            + str(self.buyer)
            + " << "
            + str(self.seller)
            + ", "
            + str(self.price)
            + ", "
            + str(self.quantity)
            + ", "
            + str(self.timestamp)
            + ")"
        )

    def __repr__(self) -> str:
        return (
            "("
            + self.symbol
            + ", "
            + str(self.buyer)
            + " << "
            + str(self.seller)
            + ", "
            + str(self.price)
            + ", "
            + str(self.quantity)
            + ", "
            + str(self.timestamp)
            + ")"
        )


class TradingState(object):
    def __init__(
        self,
        traderData: str,
        timestamp: Time,
        listings: Dict[Symbol, Listing],
        order_depths: Dict[Symbol, OrderDepth],
        own_trades: Dict[Symbol, List[Trade]],
        market_trades: Dict[Symbol, List[Trade]],
        position: Dict[Product, Position],
        observations: Observations,
    ):
        self.traderData = traderData
        self.timestamp = timestamp
        self.listings = listings
        self.order_depths = order_depths
        self.own_trades = own_trades
        self.market_trades = market_trades
        self.position = position
        self.observations = observations

    def toJSON(self):
        import json
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True)


class ProsperityEncoder(JSONEncoder):
    def default(self, o):
        return o.__dict__