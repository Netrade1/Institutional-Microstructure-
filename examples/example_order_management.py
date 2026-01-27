"""
Example: Order Management
Demonstrates order creation and management
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.execution.order_manager import OrderManager, OrderType, OrderSide


def main():
    print("=" * 60)
    print("Order Management Example")
    print("=" * 60)
    
    # Initialize order manager
    order_manager = OrderManager()
    
    # Example 1: Create market orders
    print("\n1. Creating Market Orders:")
    print("-" * 40)
    buy_order = order_manager.create_order(
        symbol="AAPL",
        side="buy",
        quantity=100,
        order_type="market"
    )
    print(f"Created: {buy_order}")
    
    sell_order = order_manager.create_order(
        symbol="AAPL",
        side="sell",
        quantity=50,
        order_type="market"
    )
    print(f"Created: {sell_order}")
    
    # Example 2: Create limit orders
    print("\n2. Creating Limit Orders:")
    print("-" * 40)
    limit_order = order_manager.create_order(
        symbol="MSFT",
        side="buy",
        quantity=200,
        order_type="limit",
        price=350.50
    )
    print(f"Created: {limit_order}")
    
    # Example 3: Submit orders
    print("\n3. Submitting Orders:")
    print("-" * 40)
    order_manager.submit_order(buy_order.order_id)
    print(f"Submitted order: {buy_order.order_id[:8]}")
    
    # Simulate fills
    buy_order.add_fill(50, 150.25)
    buy_order.add_fill(50, 150.30)
    print(f"Order filled: {buy_order.filled_quantity}/{buy_order.quantity} @ avg ${buy_order.average_fill_price:.2f}")
    
    # Example 4: View active orders
    print("\n4. Active Orders:")
    print("-" * 40)
    active = order_manager.get_active_orders()
    print(f"Total active orders: {len(active)}")
    for order in active:
        print(f"  {order}")
    
    # Example 5: Cancel an order
    print("\n5. Cancelling Order:")
    print("-" * 40)
    cancelled = order_manager.cancel_order(limit_order.order_id)
    if cancelled:
        print(f"Cancelled order: {limit_order.order_id[:8]}")
    
    # Example 6: Calculate position
    print("\n6. Position Calculation:")
    print("-" * 40)
    position = order_manager.calculate_position("AAPL")
    print(f"Symbol: {position['symbol']}")
    print(f"Quantity: {position['quantity']}")
    print(f"Average Price: ${position['average_price']:.2f}")
    print(f"Total Cost: ${position['total_cost']:.2f}")
    
    # Example 7: Order history
    print("\n7. Order History:")
    print("-" * 40)
    history = order_manager.get_order_history("AAPL")
    print(f"Total orders for AAPL: {len(history)}")
    for order in history:
        print(f"  {order}")


if __name__ == "__main__":
    main()
