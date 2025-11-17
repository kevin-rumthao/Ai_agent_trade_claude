#!/bin/bash
# Post-Installation Verification Script
# Run this after completing the setup to verify everything works

echo "======================================================================"
echo "  AI Trading Agent - Post-Installation Verification"
echo "======================================================================"
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version
if [ $? -ne 0 ]; then
    echo "❌ Python 3 not found"
    exit 1
fi
echo "✓ Python OK"
echo ""

# Check if poetry is installed
echo "Checking Poetry..."
poetry --version
if [ $? -ne 0 ]; then
    echo "❌ Poetry not found. Install with: curl -sSL https://install.python-poetry.org | python3 -"
    exit 1
fi
echo "✓ Poetry OK"
echo ""

# Check if dependencies are installed
echo "Checking dependencies..."
poetry run python -c "import langgraph; import langchain; import alpaca; print('Dependencies OK')" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  Dependencies not installed or incomplete"
    echo "Running: poetry install..."
    poetry install
fi
echo "✓ Dependencies OK"
echo ""

# Check if .env file exists
echo "Checking configuration..."
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found"
    echo ""
    echo "Would you like to run the interactive setup? (y/n)"
    read -r response
    if [ "$response" = "y" ] || [ "$response" = "Y" ]; then
        poetry run python scripts/quickstart.py
    else
        echo "Please create .env file manually or run: poetry run python scripts/quickstart.py"
        exit 1
    fi
else
    echo "✓ .env file exists"
fi
echo ""

# Check if critical env vars are set
echo "Checking environment variables..."
source .env 2>/dev/null
if [ -z "$TRADING_PROVIDER" ]; then
    echo "⚠️  TRADING_PROVIDER not set in .env"
    WARNINGS=1
fi
if [ -z "$GEMINI_API_KEY" ]; then
    echo "⚠️  GEMINI_API_KEY not set in .env"
    WARNINGS=1
fi
if [ "$TRADING_PROVIDER" = "alpaca" ] && [ -z "$ALPACA_API_KEY" ]; then
    echo "⚠️  ALPACA_API_KEY not set for Alpaca provider"
    WARNINGS=1
fi
if [ "$TRADING_PROVIDER" = "binance" ] && [ -z "$BINANCE_API_KEY" ]; then
    echo "⚠️  BINANCE_API_KEY not set for Binance provider"
    WARNINGS=1
fi

if [ -z "$WARNINGS" ]; then
    echo "✓ Environment variables OK"
else
    echo ""
    echo "Please update your .env file with missing variables"
fi
echo ""

# Run health checks
echo "======================================================================"
echo "  Running Health Checks"
echo "======================================================================"
echo ""
echo "This will verify connectivity to:"
echo "- Trading provider ($TRADING_PROVIDER)"
echo "- Gemini LLM"
echo ""

poetry run python -m app.healthcheck

if [ $? -eq 0 ]; then
    echo ""
    echo "======================================================================"
    echo "  ✅ All Checks Passed!"
    echo "======================================================================"
    echo ""
    echo "Your trading system is ready. To start trading:"
    echo ""
    echo "  poetry run python -m app.main"
    echo ""
    echo "For more information:"
    echo "  - README.md - Overview and quick start"
    echo "  - QUICK_REFERENCE.md - Common commands and configs"
    echo "  - docs/SETUP_GUIDE.md - Detailed setup guide"
    echo ""
else
    echo ""
    echo "======================================================================"
    echo "  ❌ Health Checks Failed"
    echo "======================================================================"
    echo ""
    echo "Please check the error messages above and:"
    echo "  1. Verify API keys in .env are correct"
    echo "  2. Check your internet connection"
    echo "  3. Ensure API services are accessible"
    echo ""
    echo "For help, see: docs/SETUP_GUIDE.md"
    echo ""
    exit 1
fi

