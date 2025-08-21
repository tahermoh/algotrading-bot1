"""
This is a template for Project 1, Task 1 (Induced demand-supply)
"""

from enum import Enum
from fmclient import Agent, OrderSide, Order, OrderType, Session, Holding
from typing import List

# Student details
SUBMISSION = {"number": "1473198", "name": "Taher Mohamed"}

# ------ Add a variable called PROFIT_MARGIN -----
PROFIT_MARGIN = 10 #Cents

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
    def __init__(self, account, email, password, marketplace_id):
        super().__init__(account, email, password, marketplace_id, name="DSBot")
        self._public_market = None
        self._private_market = None
        self._role = None
        # ------ Add new class variable _bot_type to store the type of the bot

    def role(self):
        return self._role

    def initialised(self):
        pass

    def order_accepted(self, order: Order):
        pass

    def order_rejected(self, info, order: Order):
        pass

    def received_orders(self, orders: List[Order]):
        pass

    def _print_trade_opportunity(self, other_order):
        self.inform(f"I am a {self.role()} with profitable order {other_order}")

    def received_holdings(self, holdings):
        pass

    def received_session_info(self, session: Session):
        pass

    def pre_start_tasks(self):
        pass


if __name__ == "__main__":
    FM_ACCOUNT = ""
    FM_EMAIL = ""
    FM_PASSWORD = ""
    MARKETPLACE_ID = ""

    ds_bot = DSBot(FM_ACCOUNT, FM_EMAIL, FM_PASSWORD, MARKETPLACE_ID)
    ds_bot.run()
