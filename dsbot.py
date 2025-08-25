"""
This is a template for Project 1, Task 1 (Induced demand-supply)
"""

from enum import Enum
from fmclient import Agent, OrderSide, Order, OrderType, Session, Holding, Market
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
        self._public_order: Optional[Order] = None
        self._waiting_for_server: bool = False


    @property
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
        self._waiting_for_server = False
        self.inform(f"Sent order {order} accepted")
        self.inform(f"{Order.current()}")

        if order.market == self._public_market:
            if order.is_cancelled:
                self._public_order = None
            else:
                self._public_order = order



    def order_rejected(self, info, order: Order) -> None:
        self._waiting_for_server = False
        self.warning(f"Sent order {order} rejected {info}")

        # Recheck public orders for profitability

        if order.market == self._public_market:
            if self._bot_type == BotType.REACTIVE:
                for o in Order.current().values():
                    if o.market == self._public_market:
                        self._handle_public_order(order)

    def _handle_private_order(self, order: Order) -> None:
        if not order.is_private:
            self.error(f"Public order is being handled as private!")
            return

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

        # Do whatever checks needed to get new incentive orders
        
        # Check for any updates on the current target order, ie cancelled
        if (self._target_order is not None
            and self._target_order.fm_id == order.fm_id
            and not order.is_pending
        ):
            # Same target order showed up again and is no longer pending
            self.warning((
                f"Original target order is no longer available: "
                f"{self._target_order}"
            ))
            self._target_order = None
            return

        # Ignore updates to any other orders or my orders
        if not order.is_pending:
            return
        if order.mine:
            return

        # Target order assignment assumes there is only ever
        # ONE incentive trade in the private market
        # Any other orders up to this point should have been ignored
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
        
        
        role = self.role
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
        
        # If in reactive mode, check order book for any profitable opportunities
        # and handle them accordingly.
        
        if self._bot_type == BotType.REACTIVE:
            for order in Order.current().values():
                if order.market == self._public_market:
                    self._handle_public_order(order)

        # Otherwise if in proactive mode, place an order in the public market
        # to match and set profitability or trade requirements

        # This requires checking if there are any of my orders still active,
        # cancelling them and sending a new one

        if self._bot_type == BotType.PROACTIVE:
            pass


    def _handle_public_order(self, order: Order) -> None:
        if order.is_private:
            self.error(f"Private order is being handled as public!")
            return

        self.warning(f"Public {order}")

        # If in proactive mode, just ignore any public orders
        # They currently have no impact on decision making for sending orders
        # However, this is something that can be implemented to increase profit

        if self._bot_type == BotType.PROACTIVE:
            self.warning(f"Ignoring {order} while in proactive mode")
            return

        # In reactive mode, check order book for any profitable opportunities
        # and handle them accordingly.

        # Ignore updates to any other orders or my orders
        if not order.is_pending:
            return
        if order.mine:
            return

        if self._target_order is None:
            self.warning(f"No private incentive order available right now")
            return

        if self._evaluate_public_order(order):
            # Conditions met, trade
            new_order = Order.create_new(self._public_market)
            new_order.price = order.price
            new_order.units = 1
            new_order.order_type = OrderType.LIMIT
            new_order.order_side = OrderSide.BUY if self.role == Role.BUYER \
                                    else OrderSide.SELL
            self.send_order(new_order)
            self._waiting_for_server = True



    def received_orders(self, orders: List[Order]) -> None:
        self.inform(f"{Order.current()}")

        # We want to handle private orders first to make sure info is updated
        private_orders = []
        public_orders = []

        for order in orders:
            if order.market == self._private_market:
                private_orders.append(order)
            elif order.market == self._public_market:
                public_orders.append(order)
            else:
                self.error(f"Order came via unsupported market")

        for order in private_orders:
            self._handle_private_order(order)
        for order in public_orders:
            self._handle_public_order(order)
        
    def _evaluate_public_order(self, order: Order) -> bool:
        if self._target_order is None:
            self.error(f"Evaluating an order without a target incentive!")
            return False

        if (self.role == Role.BUYER
            and order.order_side == OrderSide.SELL
            and order.price < self._target_order.price
        ):
            return self._print_trade_opportunity(order)

        if (self.role == Role.SELLER
            and order.order_side == OrderSide.BUY
            and order.price > self._target_order.price
        ):
            return self._print_trade_opportunity(order)

        if self.role == None:
            self.error(f"Bot role not set!")

        return False

    def _print_trade_opportunity(self, order: Order) -> bool:
        if self._target_order is None:
            self.error(f"Evaluating a trade without a target incentive!")
            return False

        margin = abs(order.price - self._target_order.price)

        self.inform(f"I am a {self.role.name} with profitable order {order}")
        self.inform(f"\tTrade Margin:    {margin}")
        self.inform(f"\tRequired Margin: {PROFIT_MARGIN}")

        if margin < PROFIT_MARGIN:
            self.inform(f"\tMargin is not sufficient to trade")
            return False
        
        self.inform(f"\tCash Available:  {self.holdings.cash_available}")
        if self.holdings.cash_available < order.price:
            self.inform(f"\tCash available is not sufficient to trade")
            return False

        if self._waiting_for_server:
            self.inform(f"\tStill waiting on server response, cannot trade")
            return False

        if self._public_order is not None:
            self.inform(f"\tAlready have an open public order, cannot trade")
            return False

        # All conditions for trading have been checked, finally trade
        self.inform(f"\tAll conditions met to trade!")
        return True


    def received_holdings(self, holdings: Holding):
        pass

    def received_session_info(self, session: Session):
        pass

    def pre_start_tasks(self):
        pass


'''
1. Is it correct to assume that there will only ever be one incentive order
    in the private market?

2. If there are trades available at a better price (bid/ask), should we still
    identify new profitable trades and react, identify but not react, or not
    identify at all?
    
3. When reacting to an order, is it assumed that they will only be for one unit
    or do we need to handle any cases where they are for multiple units, and if
    so, are we allowed to react by placing orders for multiple units to fill or
    only one at a time?

4. Is this multithreaded async? Can I busy wait in one function for another

5. Can we assume that once order is accepted, order book reflects immediately?

'''


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
