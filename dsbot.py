"""
This is a template for Project 1, Task 1 (Induced demand-supply)
"""

from dataclasses import dataclass
from enum import Enum
from fmclient import Agent, OrderSide, Order, \
    OrderType, Session, Holding, Market
from typing import List, Optional

# Student details
SUBMISSION = {"number": "1473198", "name": "Taher Mohamed"}

# ------ Add a variable called PROFIT_MARGIN -----
PROFIT_MARGIN = 10 # Cents

# Enum for the roles of the bot
class Role(Enum):
    BUYER = 0
    SELLER = 1


# Let us define another enumeration to deal with the type of bot
class BotType(Enum):
    PROACTIVE = 0
    REACTIVE = 1

@dataclass(frozen=True)
class TargetOrder():
    order_id: int
    price: int
    units: int
    side: OrderSide

    def describe(self) -> str:
        return f"{self.order_id}: {self.side.name} order on private market for {self.units}@{self.price}"


class DSBot(Agent):
    # ------ Add an extra argument bot_type to the constructor -----
    def __init__(
            self, 
            account: str, 
            email: str, 
            password: str, 
            marketplace_id: int, 
            bot_type: BotType
    ) -> None:
        super().__init__(account, email, password, marketplace_id, name="DSBot")
        self._public_market: Optional[Market] = None
        self._private_market: Optional[Market] = None
        self._role: Optional[Role] = None
        self._bot_type: BotType = bot_type
        self._target_order: Optional[Order] = None


    def role(self) -> Optional[Role]:
        return self._role

    def initialised(self) -> None:
        for market_id, market in self.markets.items():
            self.warning((
                f"There is a market with id: {market_id}"
                f"| Private: {market.private_market}"
            ))
            if market.private_market:
                self._private_market = market
            else:
                self._public_market = market

    def order_accepted(self, order: Order) -> None:
        pass

    def order_rejected(self, info, order: Order) -> None:
        pass

    def received_orders(self, orders: List[Order]) -> None:
        self.inform(f"{Order.current()}")



        for order in orders:
            if order.market == self._private_market:
                '''
                self.warning(f"Order came in on private market: {order}")
                self.warning(f"Balance {order.is_balance}")
                self.warning(f"Cancelled {order.is_cancelled}")
                self.warning(f"Consumed {order.is_consumed}")
                self.warning(f"Partial {order.is_partial}")
                self.warning(f"Partial Trade {order.is_partial_trade}")
                self.warning(f"Pending {order.is_pending}")
                self.warning(f"Split {order.is_split}")
                self.warning(f"Traded {order.has_traded}")
                self.warning(f"Consumer {order.consumer}")
                self.warning(f"Traded Order {order.traded_order}")
                # self.warning(f"cons id: {order.consumer_id}")
                # does it matter if 0 or none?
                '''

                # Do whatever checks to get new order

                if (self._target_order is not None
                    and self._target_order.fm_id == order.fm_id
                    and not order.is_pending
                ):
                    # Same order showed up again and is no longer pending
                    self.warning((
                        f"Original target order is no longer available: "
                        f"{self._target_order}"
                    ))
                    self._target_order = None
                    continue

                if not order.is_pending:
                    # Don't worry about orders that are gone
                    continue
                    
                if order.mine:
                    # Don't use my orders to set goals
                    continue

                # Assuming there is only ever one trade from the private market
                # and we have continued otherwise
                try: 
                    self._role = {
                        OrderSide.SELL: Role.SELLER,
                        OrderSide.BUY: Role.BUYER,
                    }[order.order_side]
                except KeyError:
                    self.error((
                        f"Order: {order}, has unexpected order side: "
                        f"{order.order_side}"
                    ))
                
                
                role = self.role()
                if role is None:
                    self.error(f"Bot role not set!")
                else:
                    goal_message = {
                        Role.BUYER: (
                            f"\tGoal is to BUY"
                            f" {order.units}@{order.price - PROFIT_MARGIN}"
                            f" or lower"
                        ),
                        Role.SELLER: (
                            f"\tGoal is to SELL"
                            f" {order.units}@{order.price + PROFIT_MARGIN}"
                            f" or higher"
                        ),
                    }[role]
                    self._target_order = order
                    self.inform((
                        f"Received {order.order_side.name} "
                        f"order on private market: "
                        f"{order.units}@{order.price}"
                    ))
                    self.inform(f"\tTarget Profit Margin: {PROFIT_MARGIN}")
                    self.inform(goal_message)

                # Check order book for any profitable opportunities atm.


            elif order.market == self._public_market:
                self.warning(f"Order came in on public market: {order}")

                if not order.is_pending:
                    # Don't worry about orders that are gone
                    continue
                    
                if order.mine:
                    # Don't use my orders as opportunities
                    continue

                if self._bot_type == BotType.REACTIVE:

                    if self._target_order is None:
                        self.warning(f"No target order available right now")
                        continue

                    if self.role() == Role.BUYER:
                        if (order.order_side == OrderSide.SELL
                            and order.price < self._target_order.price
                        ):
                            self.inform(f"Spotted a profitable order: {order}")
                            
                            if order.price > self._target_order.price \
                                                - PROFIT_MARGIN:
                                self.inform(
                                    f"\tHowever, it does not meet"
                                    f" the required profit margin"
                                )
                            else:
                                self.inform(
                                    f"\tIt also meets the required"
                                    f" profit margin!"
                                )

                    elif self.role() == Role.SELLER:
                        if (order.order_side == OrderSide.SELL
                            and order.price > self._target_order.price
                        ):
                            self.inform(f"Spotted a profitable order: {order}")
                            
                            if order.price < self._target_order.price \
                                                + PROFIT_MARGIN:
                                self.inform(
                                    f"\tHowever, it does not meet"
                                    f" the required profit margin"
                                )
                            else:
                                self.inform(
                                    f"\tIt also meets the required"
                                    f" profit margin!"
                                )

                    else:
                        self.error(f"Bot role not set!")

            else:
                self.error(f"Order came via unsupported market")

    def _print_trade_opportunity(self, other_order):
        self.inform(f"I am a {self.role()} with profitable order {other_order}")

    def received_holdings(self, holdings):
        pass

    def received_session_info(self, session: Session):
        pass

    def pre_start_tasks(self):
        pass


if __name__ == "__main__":
    FM_ACCOUNT = "coltish-charity"
    FM_EMAIL = "tmmoh@student.unimelb.edu.au"
    FM_PASSWORD = "1473198"
    MARKETPLACE_ID = 1573

    ds_bot = DSBot(
        FM_ACCOUNT, 
        FM_EMAIL, 
        FM_PASSWORD, 
        MARKETPLACE_ID, 
        BotType.REACTIVE
    )
    ds_bot.run()
