import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
import base64
from io import BytesIO
from typing import Literal
from collections import defaultdict
from agents import RunContextWrapper, function_tool
from src.api.indicators import INDICATOR_REGISTRY, PANEL_REGISTRY, IndicatorLiteral
from src.agent.context import Context
from agents.tool import ToolOutputImage, ToolOutputImageDict


def get_b64_image(price_data: dict, indicator_data: dict) -> str:
    """
    Converts price data and optional indicator data into a base64 encoded candlestick chart.
    Now supports multiple indicators organized into 4 panels with proper styling.
    
    Args:
        price_data: Price data dict with 'values' and 'meta'
        indicator_data: Dict mapping indicator names to their data dicts
    """
    
    # Convert price data to DataFrame
    df = pd.DataFrame(price_data.get('values', []))
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.set_index('datetime', inplace=True)
    
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
    
    df = df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'})
    
    # Merge indicator data
    for indicator, data in indicator_data.items():
        ind_df = pd.DataFrame(data)
        ind_df['datetime'] = pd.to_datetime(ind_df['datetime'])
        ind_df.set_index('datetime', inplace=True)
        df = df.join(ind_df)
    
    # Dynamically build panel mapping based on available indicators
    panel_types_needed = set()
    for indicator in indicator_data.keys():
        if indicator in INDICATOR_REGISTRY:
            panel_types_needed.add(INDICATOR_REGISTRY[indicator]['panel'])
    
    # Assign sequential panel numbers
    # NOTE: mplfinance with volume=True reserves Panel 0 for Main and Panel 1 for Volume.
    # We must adhere to this structure to prevent overlaps.
    
    PANEL_MAPPING = {'main': 0, 'volume': 1}
    next_panel_id = 2
    
    # Use simple list order for remaining panels
    # This ensures consistent ordering: Oscillators -> Momentum -> Volatility -> Beta
    remaining_order = ['oscillators', 'momentum', 'volatility', 'beta']
    
    for panel_type in remaining_order:
        if panel_type in panel_types_needed:
            PANEL_MAPPING[panel_type] = next_panel_id
            next_panel_id += 1
            
    # Create reverse mapping for styling (ID -> Name)
    PANEL_TYPE_BY_ID = {v: k for k, v in PANEL_MAPPING.items()}
    
    # Create addplot configurations based on panel mapping
    addplots = []
    ylabel_set = set()  # Track which panels already have ylabels
    panel_color_idx = {}  # Track color index per panel
    
    for indicator, data in indicator_data.items():
        if indicator not in INDICATOR_REGISTRY:
            continue
        
        reg_config = INDICATOR_REGISTRY[indicator]
        vis_config = reg_config.get('visualization', {})
        panel_name = reg_config['panel']
        panel_config = PANEL_REGISTRY.get(panel_name, {})
        
        columns = reg_config['outputs']
        
        for col in columns:
            if col not in df.columns:
                continue
            
            plot_kwargs = {}
            panel_num = PANEL_MAPPING.get(panel_name, 0)
            
            plot_kwargs['panel'] = panel_num
            
            # Assign color using matplotlib's default cycle, tracked per panel
            if panel_num not in panel_color_idx:
                panel_color_idx[panel_num] = 0
            plot_kwargs['color'] = f'C{panel_color_idx[panel_num]}'
            panel_color_idx[panel_num] += 1
            
            # Use panel-level ylabel if available
            if panel_num not in ylabel_set and 'ylabel' in panel_config:
                plot_kwargs['ylabel'] = panel_config['ylabel']
                ylabel_set.add(panel_num)
            
            # Handle secondary_y for any panel (from panel config or indicator override)
            if panel_config.get('secondary_y', False) or vis_config.get('secondary_y', False):
                plot_kwargs['secondary_y'] = True
            
            # Set plot type
            plot_type = vis_config.get('type', 'line')
            if plot_type == 'scatter':
                plot_kwargs['type'] = 'scatter'
                plot_kwargs['marker'] = 'o'
                plot_kwargs['markersize'] = 10
            
            # Handle special cases for bar charts (like MACD histogram)
            if 'hist' in col:
                plot_kwargs['type'] = 'bar'
            else:
                plot_kwargs['width'] = 1.2
            
            # Add label for legend
            plot_kwargs['label'] = col
            
            addplots.append(mpf.make_addplot(df[col], **plot_kwargs))
    
    # Create custom style matching test1.py
    mc = mpf.make_marketcolors(volume='in', edge='black')
    custom_style = mpf.make_mpf_style(base_mpf_style='classic', marketcolors=mc, rc={'axes.labelsize': 9})
    
    # Create plot with custom style
    symbol = price_data.get('meta', {}).get('symbol', 'Stock')
    
    plot_kwargs = {
        'type': 'candle',
        'style': custom_style,
        'volume': True,
        'title': f"{symbol} Price Chart",
        'returnfig': True,
        'figsize': (14, 12)
    }
    
    if addplots:
        plot_kwargs['addplot'] = addplots
    
    fig, axes = mpf.plot(df, **plot_kwargs)
    
    # Adjust layout and consolidate legends per panel
    panel_groups = defaultdict(list)
    
    for ax in axes:
        # Shift plot right to make room for legends
        pos = ax.get_position()
        ax.set_position([0.20, pos.y0, 0.70, pos.height])
        if ax.get_legend(): 
            ax.get_legend().remove()
        panel_groups[round(pos.y0, 2)].append(ax)
    
    # Sort panel groups top to bottom (highest Y first).
    # mpf orders axes from top to bottom (0, 1, 2...). 
    # sorted_groups[0] corresponds to panel 0, etc.
    sorted_groups = sorted(panel_groups.items(), key=lambda x: -x[0])
    
    for i, (y_pos, group) in enumerate(sorted_groups):
        # Identify logical panel for this visual group
        logical_panel = PANEL_TYPE_BY_ID.get(i)
        if logical_panel:
            panel_conf = PANEL_REGISTRY.get(logical_panel, {})
            
            # Apply panel-specific styling (like ylim)
            if 'ylim' in panel_conf:
                ymin, ymax = panel_conf['ylim']
                for ax in group:
                    ax.set_ylim(ymin, ymax)
            
            if 'yticks' in panel_conf:
                ticks = panel_conf['yticks']
                for ax in group:
                    ax.set_yticks(ticks)
                    
            # Special handling for Oscillators style if we have specific configs
            # (Right-side ticks are generally good for lower panels to avoid clutter)
            if logical_panel == 'oscillators':
                # Find all axes at this position (primary + twins)
                panel_axes = []
                for ax in group:
                    panel_axes.append(ax)
                    for child_ax in ax.figure.axes:
                        if child_ax not in axes and hasattr(child_ax, 'get_position'):
                            child_pos = child_ax.get_position()
                            ax_pos = ax.get_position()
                            if abs(child_pos.y0 - ax_pos.y0) < 0.01:
                                panel_axes.append(child_ax)
                
                # Get data range from all oscillator indicators
                if panel_axes:
                    all_data = []
                    for ax in panel_axes:
                        for line in ax.get_lines():
                            ydata = line.get_ydata()
                            all_data.extend([y for y in ydata if not pd.isna(y)])
                    
                    if all_data:
                        ymin, ymax = min(all_data), max(all_data)
                        margin = (ymax - ymin) * 0.1
                        
                        # Apply same range to all axes
                        for ax in panel_axes:
                            ax.set_ylim(ymin - margin, ymax + margin)
                        
                        # Show right ticks only
                        for ax in panel_axes:
                            ax.yaxis.tick_right()
                            ax.yaxis.set_label_position('right')
                            ax.tick_params(left=False, labelleft=False)
            
            elif logical_panel == 'momentum':
                # Find all axes at this position (primary + twins)
                panel_axes = []
                for ax in group:
                    panel_axes.append(ax)
                    for child_ax in ax.figure.axes:
                        if child_ax not in axes and hasattr(child_ax, 'get_position'):
                            child_pos = child_ax.get_position()
                            ax_pos = ax.get_position()
                            if abs(child_pos.y0 - ax_pos.y0) < 0.01:
                                panel_axes.append(child_ax)
                
                # Get data range from all momentum indicators
                if panel_axes:
                    all_data = []
                    for ax in panel_axes:
                        for line in ax.get_lines():
                            ydata = line.get_ydata()
                            all_data.extend([y for y in ydata if not pd.isna(y)])
                    
                    if all_data:
                        ymin, ymax = min(all_data), max(all_data)
                        margin = (ymax - ymin) * 0.1
                        
                        # Apply same range to all axes
                        for ax in panel_axes:
                            ax.set_ylim(ymin - margin, ymax + margin)
                        
                        # Hide left ticks, show right ticks
                        for ax in panel_axes:
                            ax.yaxis.tick_right()
                            ax.yaxis.set_label_position('right')
                            ax.tick_params(left=False, labelleft=False)

        # Collect unique handles from all axes in the panel (primary + twins)
        handles, labels = [], []
        for ax in group:
            h, l = ax.get_legend_handles_labels()
            handles.extend(h)
            labels.extend(l)
        
        if handles:
            by_label = dict(zip(labels, handles))
            group[0].legend(by_label.values(), by_label.keys(), 
                            loc='center left', bbox_to_anchor=(-0.16, 0.5), 
                            frameon=True, fontsize=8)
    
    # Save to buffer with reduced DPI to minimize token usage
    # DPI=100 reduces base64 size by ~75% while maintaining readability
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    
    return base64.b64encode(buf.read()).decode('utf-8')

@function_tool
def get_candlestick_chart(
    ctx: RunContextWrapper[Context],
    ticker_symbol: str,
    interval: Literal["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "4h", "1d", "5d", "1wk", "1mo", "3mo"],
    indicators: list[IndicatorLiteral] | None = None,
    outputsize: int = 20,
    start_date: str = None, 
    end_date: str = None,
    benchmark_symbol: str | None = None,
    ) -> ToolOutputImage | ToolOutputImageDict:
    """
    Retrieves historical OHLCV (Open, High, Low, Close, Volume) price data for a given ticker symbol.
    Ideal for analyzing price trends, patterns, and historical performance purely based on price action.
    Returns a time series of price points with timestamps along with optional technical indicators.

    Args:
        ticker_symbol (required): Stock ticker or crypto symbol (e.g., "AAPL", "BTC-USD").
        interval (required): Time interval between data points. Options: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 4h, 1d, 5d, 1wk, 1mo, 3mo.
        indicators (optional): List of technical indicators to include. Options: ema, macd, adx, rsi, stoch, bbands, atr, obv, mfi, sar, typprice, beta, ppo.
        outputsize (optional): Number of data points to retrieve (default: 20).
        start_date (optional): Start date in YYYY-MM-DD format (e.g., "2024-01-01"). Overrides outputsize if provided.
        end_date (optional): End date in YYYY-MM-DD format (e.g., "2024-12-31"). Defaults to today if not provided.
        benchmark_symbol (optional): Benchmark symbol for beta calculation only.
    """

    success, price_data = ctx.context.yfinance_api.time_series(
        symbol=ticker_symbol, 
        interval=interval, 
        outputsize=outputsize, 
        start_date=start_date, 
        end_date=end_date
    )
    if not success:
        return {"error": price_data}

    indicator_data = {}
    if indicators:
        for indicator in indicators:
            kwargs = {}
            if indicator.startswith('beta'):
                kwargs['benchmark_symbol'] = benchmark_symbol

            success, data = ctx.context.yfinance_api.calculate_indicator(
                symbol=ticker_symbol, 
                indicator_name=indicator,
                interval=interval, 
                outputsize=outputsize, 
                start_date=start_date, 
                end_date=end_date,
                **kwargs
            )
            if not success:
                return {"error": data}
            indicator_data[indicator] = data

    b64_image = get_b64_image(price_data, indicator_data)
    return {
        "type": "image",
        "image_url": f"data:image/jpeg;base64,{b64_image}",
        "detail": "auto",
    }
