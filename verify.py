"""
Verification script - Tests that all components are importable
"""
import sys

def verify_imports():
    """Verify all modules can be imported"""
    print("Verifying AI Trading Bot Platform Installation...")
    print("=" * 60)
    
    tests = []
    
    # Test 1: Main package
    try:
        import trading_bot
        print("✓ trading_bot package imported")
        tests.append(True)
    except ImportError as e:
        print(f"✗ Failed to import trading_bot: {e}")
        tests.append(False)
    
    # Test 2: Data module
    try:
        from trading_bot.data import MarketDataFetcher, FeatureEngineering
        print("✓ Data module imported (MarketDataFetcher, FeatureEngineering)")
        tests.append(True)
    except ImportError as e:
        print(f"✗ Failed to import data module: {e}")
        tests.append(False)
    
    # Test 3: Models module
    try:
        from trading_bot.models import LSTMModel, RandomForestModel, XGBoostModel, EnsembleModel
        print("✓ Models module imported (LSTM, RF, XGB, Ensemble)")
        tests.append(True)
    except ImportError as e:
        print(f"✗ Failed to import models module: {e}")
        tests.append(False)
    
    # Test 4: Strategies module
    try:
        from trading_bot.strategies import MLTradingStrategy, TechnicalStrategy, HybridStrategy
        print("✓ Strategies module imported (ML, Technical, Hybrid)")
        tests.append(True)
    except ImportError as e:
        print(f"✗ Failed to import strategies module: {e}")
        tests.append(False)
    
    # Test 5: Risk module
    try:
        from trading_bot.risk import Portfolio, RiskManager, PortfolioOptimizer
        print("✓ Risk module imported (Portfolio, RiskManager, Optimizer)")
        tests.append(True)
    except ImportError as e:
        print(f"✗ Failed to import risk module: {e}")
        tests.append(False)
    
    # Test 6: Config loading
    try:
        import yaml
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        print(f"✓ Configuration loaded ({len(config)} sections)")
        tests.append(True)
    except Exception as e:
        print(f"✗ Failed to load config: {e}")
        tests.append(False)
    
    # Test 7: Main entry point
    try:
        import main
        print("✓ Main entry point loaded")
        tests.append(True)
    except Exception as e:
        print(f"✗ Failed to import main: {e}")
        tests.append(False)
    
    # Test 8: Dashboard
    try:
        from dashboard import app
        print("✓ Dashboard app loaded")
        tests.append(True)
    except Exception as e:
        print(f"✗ Failed to import dashboard: {e}")
        tests.append(False)
    
    print("=" * 60)
    passed = sum(tests)
    total = len(tests)
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n�� ALL VERIFICATIONS PASSED!")
        print("\nThe AI Trading Bot Platform is ready to use!")
        print("\nNext steps:")
        print("1. Install dependencies: pip install -r requirements.txt")
        print("2. Run demo: python demo.py")
        print("3. Start bot: python main.py --train --cycles 1")
        print("4. Launch dashboard: python main.py --dashboard")
        return 0
    else:
        print("\n⚠️  Some verifications failed")
        print("Please install dependencies: pip install -r requirements.txt")
        return 1

if __name__ == "__main__":
    sys.exit(verify_imports())
