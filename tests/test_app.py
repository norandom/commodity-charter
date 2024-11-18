import pytest
import pandas as pd
from datetime import datetime, timedelta
import sys
import os
import warnings

# Ignore warnings during tests
warnings.filterwarnings("ignore")

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import get_price_data, load_cot_signals, get_position_signal

@pytest.fixture
def mock_cot_data():
    """Create mock COT data for testing"""
    data = {
        'Market_and_Exchange_Names': ['CRUDE OIL, LIGHT SWEET'],
        'Report_Date_as_MM_DD_YYYY': ['01/01/2024'],
        'Open_Interest_All': [1000000],
        'Prod_Merc_Positions_Long_All': [300000],
        'Prod_Merc_Positions_Short_All': [400000]
    }
    return pd.DataFrame(data)

def test_load_cot_signals():
    """Test loading COT signals from CSV"""
    signals_df = load_cot_signals()
    assert not signals_df.empty
    assert all(col in signals_df.columns for col in ['Commodity', 'Bullish_Min', 'Bullish_Max', 'Bearish_Min', 'Bearish_Max'])

def test_get_position_signal():
    """Test signal generation logic"""
    # Create a mock signals DataFrame
    signals_data = {
        'Commodity': ['TEST'],
        'Bullish_Min': [30],
        'Bullish_Max': [40],
        'Bearish_Min': [60],
        'Bearish_Max': [70]
    }
    signals_df = pd.DataFrame(signals_data)
    
    # Test bullish signal
    signal, reasons = get_position_signal(35.0, 20.0, signals_df, 'TEST')
    assert signal == 'BULLISH'
    
    # Test bearish signal
    signal, reasons = get_position_signal(20.0, 65.0, signals_df, 'TEST')
    assert signal == 'BEARISH'
    
    # Test neutral signal
    signal, reasons = get_position_signal(50.0, 50.0, signals_df, 'TEST')
    assert signal == 'NEUTRAL'

def test_get_price_data():
    """Test price data retrieval"""
    end_date = pd.Timestamp.now(tz='America/New_York')
    start_date = end_date - pd.Timedelta(days=30)
    
    # Test with a known symbol
    df = get_price_data('CL=F', start_date, end_date)
    assert not df.empty
    assert all(col in df.columns for col in ['Open', 'High', 'Low', 'Close', 'Volume'])
    
    # Convert df index to same timezone for comparison
    df.index = df.index.tz_convert('America/New_York')
    
    # Test date range
    assert df.index.min() >= start_date
    assert df.index.max() <= end_date
