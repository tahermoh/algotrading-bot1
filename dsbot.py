"""
This is a template for Project 1, Task 1 (Induced demand-supply)
"""

from enum import Enum
from fmclient import Agent, OrderSide, Order, OrderType, Session, Holding, Market
from typing import List, Optional
import copy

# Student details
SUBMISSION = {"number": "1473198", "name": "Taher Mohamed"}

# ------ Add a variable called PROFIT_MARGIN -----
PROFIT_MARGIN = 250 # Cents

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
        self._best_bid: Optional[Order] = None
        self._best_ask: Optional[Order] = None
        self._target_order: Optional[Order] = None
        self._public_order_pending: bool = False
        self._waiting_for_server: bool = False


    @property
    def role(self) -> Optional[Role]:
        return self._role

    @property
    def current_public_orders(self) -> list[Order]:
        return [
            o for o in Order.current().values()
            if o.market == self._public_market
        ]

    @property
    def current_private_orders(self) -> list[Order]:
        return [
            o for o in Order.current().values()
            if o.market == self._private_market
        ]

    @property
    def best_bid(self) -> Optional[Order]:
        bids = [o for o in self.current_public_orders
                if o.order_side == OrderSide.BUY
                ]
        return max(bids, key=lambda o: o.price) if bids else None

    @property
    def best_ask(self) -> Optional[Order]:
        asks = [o for o in self.current_public_orders
                if o.order_side == OrderSide.SELL
                ]
        return min(asks, key=lambda o: o.price) if asks else None

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

        if order.market == self._public_market:
            if order.order_type == OrderType.LIMIT:
                self._public_order_pending = True
            if order.order_type == OrderType.CANCEL:
                self._public_order_pending = False

                if self._bot_type == BotType.PROACTIVE:
                    self._proactive_order()

        if order.market == self._private_market:
            pass



    def order_rejected(self, info, order: Order) -> None:
        self._waiting_for_server = False
        self.warning(f"Sent order {order} rejected {info}")

        # Recheck public orders for profitability
        if order.market == self._public_market:
            if self._bot_type == BotType.REACTIVE:
                if tradeable_order := self._check_trade_opportunity():
                    self._trade_order(tradeable_order)
                    # Potential infinite loop?
        
        if order.market == self._private_market:
            pass

    def _set_target_order(self, order: Optional[Order]) -> None:
        self._target_order = order

        if order is None:
            self._role = None
        else:
            self._role = {
                OrderSide.SELL: Role.SELLER,
                OrderSide.BUY: Role.BUYER,
            }[order.order_side]

    def _handle_private_order(self, order: Order) -> None:
        if order.market != self._private_market:
            self.error(f"Public order is being handled as private!")
            return

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
            self._set_target_order(None)

            # Incentive cancelled, cancel any open orders to reevaluate
            for order in Order.my_current().values():
                self._cancel_order(order)

            return

        # Ignore updates to any other orders or my orders
        if not order.is_pending:
            return
        if order.mine:
            return

        # Target order assignment assumes there is only ever
        # ONE incentive trade in the private market
        # Any other orders up to this point should have been ignored
        self._set_target_order(order)

        
        assert self.role is not None # Suppresses warning 
        assert self._target_order is not None
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
        }[self.role]
        self.inform((
            f"Received {order.order_side.name} "
            f"order on private market: "
            f"{order.units}@{order.price}"
        ))
        self.inform(f"\tTarget Profit Margin: {PROFIT_MARGIN}")
        self.inform(goal_message)
        

        # If in proactive mode, place an order in the public market
        # to match and set profitability or trade requirements

        # This requires checking if there are any of my orders still active,
        # cancelling them and sending a new one
        # However, it is assumed from above that if incentives change
        # then all orders are cancelled -> BUGGY IF DISCONNECT WITH ACTIVE ORDER
        # We only make it this far in the method if a new incentive is given
        # Need to take into account min and max prices of the asset and
        # how it relates to our profit margin, as well as cash/units

        # Incentive cancelled, cancel any open orders to reevaluate
        for order in Order.my_current().values():
            self._cancel_order(order)

        if self._bot_type == BotType.PROACTIVE:
            self._proactive_order()

    def _check_role_and_target(self) -> bool:
        if self.role is None:
            self.warning(
                f"Bot role not set!"
                f"There currently aren't any active private incentives"
             )
            return False

        return True
    
    def _trade_order(self, order: Order) -> None:
        self.inform(f"Responding to order {order}")

        new_order = Order.create_new(order.market)
        new_order.price = order.price
        new_order.units = 1
        new_order.order_type = OrderType.LIMIT
        new_order.order_side = {
                OrderSide.BUY: OrderSide.SELL,
                OrderSide.SELL: OrderSide.BUY,
            }[order.order_side]
        new_order.owner_or_target = order.owner_or_target
        self._waiting_for_server = True
        self.send_order(new_order)

    def _proactive_order(self) -> None:
        if self._bot_type != BotType.PROACTIVE:
            self.error(f"Trying to send a proactive order in a different mode")
            return 

        if not self._check_role_and_target():
            return

        assert self.role is not None
        assert self._target_order is not None
        assert self._public_market is not None

        new_order = copy.copy(self._target_order)
        new_order.market = self._public_market
        new_order.units = 1
        new_order.price = {
                OrderSide.BUY: self._target_order.price - PROFIT_MARGIN,
                OrderSide.SELL: self._target_order.price + PROFIT_MARGIN,
        }[new_order.order_side]
        
        tradeable, msg = self._check_tradeable(new_order)
        self.inform(f"Creating a proactive order {new_order}")
        self.inform(msg)
        if tradeable:
            self._waiting_for_server = True
            self.send_order(new_order)

    def _cancel_order(self, order: Order) -> None:
        if not order.mine:
            self.error(f"Trying to cancel order {order} which is not mine!")
            return

        self.inform(f"Cancelling order {order}")

        cancel_order = copy.copy(order)
        cancel_order.order_type = OrderType.CANCEL
        self._waiting_for_server = True
        self.send_order(cancel_order)

    def _check_trade_opportunity(self) -> Optional[Order]:
        if not self._check_role_and_target():
            return None

        assert self.role is not None
        assert self._target_order is not None

        best_order = {
            Role.BUYER: self.best_ask,
            Role.SELLER: self.best_bid,
        }[self.role]

        if best_order is None:
            return None

        if self._check_profitable(best_order):
            tradeable, message = self._check_tradeable(best_order)
            self._print_trade_opportunity(best_order, message)

            return best_order if tradeable else None
        
        return None


    def _check_profitable(self, order: Order) -> bool:
        if not self._check_role_and_target():
            return False
        assert self._target_order is not None

        return ((
            self.role == Role.BUYER
            and order.order_side == OrderSide.SELL
            and order.price < self._target_order.price
            ) or (
            self.role == Role.SELLER
            and order.order_side == OrderSide.BUY
            and order.price > self._target_order.price
            )
        )

    def _print_trade_opportunity(self, order: Order, status: str) -> None:
        if not self._check_role_and_target():
            return

        assert self.role is not None
        assert self._target_order is not None
        assert self._public_market is not None

        margin = abs(order.price - self._target_order.price)
        units = self.holdings.assets[self._public_market].units_available

        self.inform(f"I am a {self.role.name} with profitable order {order}")
        self.inform(f"\tTrade Margin:    {margin}")
        self.inform(f"\tRequired Margin: {PROFIT_MARGIN}")
        self.inform(f"\tCash Available:  {self.holdings.cash_available}")
        self.inform(f"\tUnits Available: {units}")
        self.inform(status)

    def _check_tradeable(self, order: Order) -> tuple[bool, str]:
        if not self._check_role_and_target():
            return (False, "")

        assert self._target_order is not None
        assert self._public_market is not None

        margin = abs(order.price - self._target_order.price)
        units = self.holdings.assets[self._public_market].units_available

        if margin < PROFIT_MARGIN:
            msg = f"\tMargin is not sufficient to trade"
            return (False, msg)
        
        if self.role == Role.BUYER and \
           self.holdings.cash_available < order.price:
            msg = f"\tCash available is not sufficient to trade"
            return (False, msg)

        if self.role == Role.SELLER and units < 1:
            msg = f"\tUnits available is not sufficient to trade"
            return (False, msg)

        if self._waiting_for_server:
            msg = f"\tStill waiting on server response, cannot trade"
            return (False, msg)

        if Order.my_current():
            msg = f"\tAlready have an open public order, cannot trade"
            return (False, msg)

        #min_price = self.holdings.assets[self._public_market].

        # All conditions for trading have been checked, finally trade
        msg = f"\tAll conditions met to trade!"
        return (True, msg)



    def _handle_public_order(self, order: Order) -> None:
        if order.market != self._public_market:
            self.error(f"Private order is being handled as public!")
            return

        self.warning(f"Public {order}")

        '''
        # If in proactive mode, just ignore any public orders
        # They currently have no impact on decision making for sending orders
        # However, this is something that can be implemented to increase profit

        if self._bot_type == BotType.PROACTIVE:
            self.warning(f"Ignoring {order} while in proactive mode")
            return
        '''


        if not order.mine:
            return

        # Check if public reactive or proactive order has been consumed
        # Now we're allowed to send another
        # Need to trade in the private market to take advantage of the arbitrage!

        if (order.has_traded 
            and self._target_order 
            and not self._waiting_for_server
            and self._public_order_pending
        ):
            self._public_order_pending = False
            self._trade_order(self._target_order)



    def received_orders(self, orders: List[Order]) -> None:
        self.inform(f"{Order.current()}")

        if self._bot_type == BotType.REACTIVE:
            for order in Order.my_current().values():
                self.error(
                    f"Order {order} didn't trade in reactive mode"
                    f"Cancelling it now..."
                )

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

        # If in reactive mode, check order book for any profitable opportunities
        # and handle them accordingly on every update
        
        if self._bot_type == BotType.REACTIVE:
            if tradeable_order := self._check_trade_opportunity():
                self._trade_order(tradeable_order)

        # If it any point I have an open private order, something has gone wrong
        # Likely incentive got cancelled as trade was being sent
        # Cancel open trades

        my_private_orders = [o for o in Order.my_current().values() 
                             if o.market == self._private_market]

        for order in my_private_orders:
            self.error(f"{order} open in the private market! Cancelling it...")
            if self._waiting_for_server:
                self.error(f"Waiting for server, can't cancel now...")
                continue

            self._cancel_order(order)
        



    def received_holdings(self, holdings: Holding):
        assert self._public_market is not None
        assert self._private_market is not None

        # Use this to trade in the private market whenever there is an
        # imbalance in holdings, which is assumed to only happen when
        # public trades happen
        pub_init = holdings.assets[self._public_market].units_initial
        pub_curr = holdings.assets[self._public_market].units
        pvt_init = holdings.assets[self._private_market].units_initial
        pvt_curr = holdings.assets[self._private_market].units
        total_init = pub_init + pvt_init
        total_curr = pub_curr + pvt_curr

        self.inform(f"HOLDINGS INIT: {pub_init}, {pvt_init}")
        self.inform(f"HOLDINGS NOW: {pub_curr}, {pvt_curr}")


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

6. I'm always interacting in the public market first, which means I might not
    have enough assets to trade that I *could* get by trading in private first

7. Can we modify print trade opportunity

8. Do we have to track _role or can it stay just a property?

9. If my bot disconnects and misses an incentive refresh, that

'''


if __name__ == "__main__":
    FM_ACCOUNT = "coltish-charity"
    FM_EMAIL = "tmmoh@student.unimelb.edu.au"
    FM_PASSWORD = "1473198"
    MARKETPLACE_ID = 1579

    ds_bot = DSBot(
        FM_ACCOUNT, 
        FM_EMAIL, 
        FM_PASSWORD, 
        MARKETPLACE_ID, 
        BotType.PROACTIVE
    )
    ds_bot.run()
