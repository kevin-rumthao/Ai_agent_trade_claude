import pytest
from unittest.mock import MagicMock, patch
from app.tools.kotak_neo_tool import KotakNeoTool
from app.schemas.models import Order

@pytest.fixture
def mock_settings():
    with patch("app.tools.kotak_neo_tool.settings") as mock_settings:
        mock_settings.kotak_consumer_key = "test_key"
        mock_settings.kotak_mobile_number = "1234567890"
        mock_settings.kotak_password = "password"
        mock_settings.kotak_totp_secret = "secret"
        yield mock_settings

@pytest.fixture
def mock_neo_api():
    with patch("app.tools.kotak_neo_tool.NeoAPI") as mock_api:
        yield mock_api

@pytest.mark.asyncio
async def test_initialization(mock_settings, mock_neo_api):
    tool = KotakNeoTool()
    await tool.initialize()
    
    assert tool.is_initialized
    mock_neo_api.assert_called_once()
    tool.client.login.assert_called_once()

@pytest.mark.asyncio
async def test_execute_order(mock_settings, mock_neo_api):
    tool = KotakNeoTool()
    await tool.initialize()
    
    # Mock order response
    tool.client.place_order.return_value = {"nOrdNo": "12345"}
    
    order = Order(
        symbol="NSE_CM|RELIANCE-EQ",
        side="BUY",
        quantity=10,
        price=2500.0,
        order_type="LIMIT"
    )
    
    result = await tool.execute_order(order)
    
    assert result.success
    assert result.order_id == "12345"
    tool.client.place_order.assert_called_once()

@pytest.mark.asyncio
async def test_get_portfolio_state(mock_settings, mock_neo_api):
    tool = KotakNeoTool()
    await tool.initialize()
    
    # Mock responses
    tool.client.limits.return_value = {}
    tool.client.positions.return_value = {
        "data": [
            {
                "trdSym": "RELIANCE-EQ",
                "netQty": "10",
                "avgPrc": "2400",
                "ltp": "2500",
                "urPnl": "1000"
            }
        ]
    }
    
    portfolio = await tool.get_portfolio_state()
    
    assert len(portfolio.positions) == 1
    assert portfolio.positions[0].symbol == "RELIANCE-EQ"
    assert portfolio.positions[0].quantity == 10.0
    assert portfolio.positions[0].unrealized_pnl == 1000.0
