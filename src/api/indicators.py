from typing import List, Dict, Any, Optional
from typing_extensions import Literal

PANEL_REGISTRY = {
    'main': {},
    'volume': {'secondary_y': True},
    'oscillators': {
        'ylabel': 'Oscillators',
        'ylim': (0, 100),
        'yticks': [25, 50, 75]
    },
    'momentum': {'ylabel': 'Momentum'},
    'volatility': {'ylabel': 'Volatility'},
    'beta': {'ylabel': 'Beta'}
}

INDICATOR_REGISTRY = {
    'ema_20': {
        'talib_function': 'EMA',
        'inputs': ['close'],
        'params': {'timeperiod': 20},
        'outputs': ['ema_20'],
        'panel': 'main',
        'visualization': {}
    },
    'ema_50': {
        'talib_function': 'EMA',
        'inputs': ['close'],
        'params': {'timeperiod': 50},
        'outputs': ['ema_50'],
        'panel': 'main',
        'visualization': {}
    },
    'sma_20': {
        'talib_function': 'SMA',
        'inputs': ['close'],
        'params': {'timeperiod': 20},
        'outputs': ['sma_20'],
        'panel': 'main',
        'visualization': {}
    },
    'sma_50': {
        'talib_function': 'SMA',
        'inputs': ['close'],
        'params': {'timeperiod': 50},
        'outputs': ['sma_50'],
        'panel': 'main',
        'visualization': {}
    },
    'macd_12_26_9': {
        'talib_function': 'MACD',
        'inputs': ['close'],
        'params': {'fastperiod': 12, 'slowperiod': 26, 'signalperiod': 9},
        'outputs': ['macd', 'macd_signal', 'macd_hist'],
        'panel': 'momentum',
        'visualization': {'type': 'bar_for_hist'} # Custom logic for hist
    },
    'adx_14': {
        'talib_function': 'ADX',
        'inputs': ['high', 'low', 'close'],
        'params': {'timeperiod': 14},
        'outputs': ['adx_14'],
        'panel': 'oscillators',
        'visualization': {}
    },
    'rsi_14': {
        'talib_function': 'RSI',
        'inputs': ['close'],
        'params': {'timeperiod': 14},
        'outputs': ['rsi_14'],
        'panel': 'oscillators',
        'visualization': {}
    },
    'stoch_5_3_3': {
        'talib_function': 'STOCH',
        'inputs': ['high', 'low', 'close'],
        'params': {'fastk_period': 5, 'slowk_period': 3, 'slowd_period': 3},
        'outputs': ['slowk', 'slowd'],
        'panel': 'oscillators',
        'visualization': {}
    },
    'bbands_20_2': {
        'talib_function': 'BBANDS',
        'inputs': ['close'],
        'params': {'timeperiod': 20, 'nbdevup': 2.0, 'nbdevdn': 2.0, 'matype': 0},
        'outputs': ['upper', 'middle', 'lower'],
        'panel': 'main',
        'visualization': {}
    },
    'atr_14': {
        'talib_function': 'ATR',
        'inputs': ['high', 'low', 'close'],
        'params': {'timeperiod': 14},
        'outputs': ['atr_14'],
        'panel': 'volatility',
        'visualization': {}
    },
    'obv': {
        'talib_function': 'OBV',
        'inputs': ['close', 'volume'],
        'params': {},
        'outputs': ['obv'],
        'panel': 'volume',
        'visualization': {}
    },
    'mfi_14': {
        'talib_function': 'MFI',
        'inputs': ['high', 'low', 'close', 'volume'],
        'params': {'timeperiod': 14},
        'outputs': ['mfi_14'],
        'panel': 'oscillators',
        'visualization': {}
    },
    'sar_002_020': {
        'talib_function': 'SAR',
        'inputs': ['high', 'low'],
        'params': {'acceleration': 0.02, 'maximum': 0.2},
        'outputs': ['sar'],
        'panel': 'main',
        'visualization': {'type': 'scatter'}
    },
    'typprice': {
        'talib_function': 'TYPPRICE',
        'inputs': ['high', 'low', 'close'],
        'params': {},
        'outputs': ['typprice'],
        'panel': 'main',
        'visualization': {}
    },
    'ppo_12_26': {
        'talib_function': 'PPO',
        'inputs': ['close'],
        'params': {'fastperiod': 12, 'slowperiod': 26, 'matype': 0},
        'outputs': ['ppo'],
        'panel': 'momentum',
        'visualization': {}
    },
    'beta_5': {
        'talib_function': 'BETA',
        'inputs': ['close', 'benchmark_close'], # Special handling needed
        'params': {'timeperiod': 5},
        'outputs': ['beta'],
        'panel': 'beta',
        'visualization': {},
        'requires_benchmark': True
    }
}

IndicatorLiteral = Literal.__getitem__(tuple(INDICATOR_REGISTRY.keys()))

def get_indicator_config(name: str) -> Optional[Dict[str, Any]]:
    return INDICATOR_REGISTRY.get(name)

def get_panel_config(name: str) -> Optional[Dict[str, Any]]:
    return PANEL_REGISTRY.get(name)

def get_available_indicators() -> List[str]:
    return list(INDICATOR_REGISTRY.keys())
