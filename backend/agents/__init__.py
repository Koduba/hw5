"""The five Campus Customs agents. Importing this package builds and registers all of them."""

from .base import AGENTS, SHOP_TOOLS
from .boss import boss
from .inventory import inventory
from .accounting import accounting
from .facilities import facilities
from .customer_service import customer_service

__all__ = ["AGENTS", "SHOP_TOOLS", "boss", "inventory", "accounting", "facilities", "customer_service"]
