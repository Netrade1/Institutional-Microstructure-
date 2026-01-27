"""
Order Manager
Manages order creation, execution, and tracking
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum


class OrderType(Enum):
    """Order type enumeration"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(Enum):
    """Order side enumeration"""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """Order status enumeration"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class Order:
    """Represents a trading order"""
    
    def __init__(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        order_type: OrderType,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "GTC"
    ):
        """
        Initialize an order.
        
        Args:
            symbol: Trading symbol
            side: Order side (BUY or SELL)
            quantity: Order quantity
            order_type: Order type (MARKET, LIMIT, etc.)
            price: Limit price (for limit orders)
            stop_price: Stop price (for stop orders)
            time_in_force: Time in force ('GTC', 'DAY', 'IOC', 'FOK')
        """
        self.order_id = str(uuid.uuid4())
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.order_type = order_type
        self.price = price
        self.stop_price = stop_price
        self.time_in_force = time_in_force
        self.status = OrderStatus.PENDING
        self.filled_quantity = 0
        self.average_fill_price = 0.0
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.fills: List[Dict] = []
    
    def add_fill(self, quantity: int, price: float):
        """
        Add a fill to the order.
        
        Args:
            quantity: Filled quantity
            price: Fill price
        """
        fill = {
            'timestamp': datetime.now(),
            'quantity': quantity,
            'price': price
        }
        self.fills.append(fill)
        
        # Update filled quantity and average price
        total_value = self.average_fill_price * self.filled_quantity + price * quantity
        self.filled_quantity += quantity
        self.average_fill_price = total_value / self.filled_quantity
        
        # Update status
        if self.filled_quantity >= self.quantity:
            self.status = OrderStatus.FILLED
        elif self.filled_quantity > 0:
            self.status = OrderStatus.PARTIAL
        
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict:
        """Convert order to dictionary"""
        return {
            'order_id': self.order_id,
            'symbol': self.symbol,
            'side': self.side.value,
            'quantity': self.quantity,
            'order_type': self.order_type.value,
            'price': self.price,
            'stop_price': self.stop_price,
            'time_in_force': self.time_in_force,
            'status': self.status.value,
            'filled_quantity': self.filled_quantity,
            'average_fill_price': self.average_fill_price,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'fills': self.fills
        }
    
    def __repr__(self) -> str:
        return (f"Order(id={self.order_id[:8]}, {self.side.value} {self.quantity} "
                f"{self.symbol} @ {self.price or 'MKT'}, status={self.status.value})")


class OrderManager:
    """
    Manages order lifecycle and execution.
    """
    
    def __init__(self):
        """Initialize the order manager"""
        self.orders: Dict[str, Order] = {}
        self.active_orders: Dict[str, Order] = {}
    
    def create_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str = "market",
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "GTC"
    ) -> Order:
        """
        Create a new order.
        
        Args:
            symbol: Trading symbol
            side: Order side ('buy' or 'sell')
            quantity: Order quantity
            order_type: Order type ('market', 'limit', 'stop', 'stop_limit')
            price: Limit price
            stop_price: Stop price
            time_in_force: Time in force
            
        Returns:
            Created Order object
        """
        # Convert string inputs to enums
        side_enum = OrderSide.BUY if side.lower() == 'buy' else OrderSide.SELL
        type_enum = OrderType[order_type.upper()]
        
        order = Order(
            symbol=symbol,
            side=side_enum,
            quantity=quantity,
            order_type=type_enum,
            price=price,
            stop_price=stop_price,
            time_in_force=time_in_force
        )
        
        self.orders[order.order_id] = order
        self.active_orders[order.order_id] = order
        
        return order
    
    def submit_order(self, order_id: str) -> bool:
        """
        Submit an order for execution.
        
        Args:
            order_id: Order ID
            
        Returns:
            True if submitted successfully
        """
        if order_id in self.orders:
            order = self.orders[order_id]
            order.status = OrderStatus.SUBMITTED
            order.updated_at = datetime.now()
            return True
        return False
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an active order.
        
        Args:
            order_id: Order ID
            
        Returns:
            True if cancelled successfully
        """
        if order_id in self.active_orders:
            order = self.active_orders[order_id]
            order.status = OrderStatus.CANCELLED
            order.updated_at = datetime.now()
            del self.active_orders[order_id]
            return True
        return False
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """
        Get an order by ID.
        
        Args:
            order_id: Order ID
            
        Returns:
            Order object or None
        """
        return self.orders.get(order_id)
    
    def get_active_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """
        Get all active orders, optionally filtered by symbol.
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            List of active orders
        """
        if symbol:
            return [order for order in self.active_orders.values() 
                   if order.symbol == symbol]
        return list(self.active_orders.values())
    
    def get_order_history(self, symbol: Optional[str] = None) -> List[Order]:
        """
        Get order history, optionally filtered by symbol.
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            List of all orders
        """
        if symbol:
            return [order for order in self.orders.values() 
                   if order.symbol == symbol]
        return list(self.orders.values())
    
    def calculate_position(self, symbol: str) -> Dict:
        """
        Calculate current position for a symbol based on filled orders.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Dictionary with position information
        """
        position = 0
        total_cost = 0.0
        
        for order in self.orders.values():
            if order.symbol == symbol and order.filled_quantity > 0:
                quantity = order.filled_quantity
                if order.side == OrderSide.BUY:
                    position += quantity
                    total_cost += quantity * order.average_fill_price
                else:
                    position -= quantity
                    total_cost -= quantity * order.average_fill_price
        
        avg_price = total_cost / position if position != 0 else 0.0
        
        return {
            'symbol': symbol,
            'quantity': position,
            'average_price': avg_price,
            'total_cost': total_cost
        }
