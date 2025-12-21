from datetime import datetime, timezone
import yfinance as yf
from yfinance.screener import screen
from .screeners import AVAILABLE_SCREENERS
from src.utils import validate_date, validate_date_range
import talib
import numpy as np


class YFinanceAPI:
    def __init__(self):
        pass

    def market_status(
        self,
        market: str = "US",
        ):
        """
        The market status endpoint provides the status of the market.
        """
        try:
            market = yf.Market(market=market)
            return True, {"message": market.status['message'], "status": market.status['status']}
        except:
            return False, "Unable to fetch market status"

    def time_series(
        self,
        symbol: str,
        interval: str,
        outputsize: int = 30,
        start_date: str = None,
        end_date: str = None,
        ):
        """
        The time series endpoint provides detailed historical data for a specified financial instrument. 
        It returns two main components: metadata, which includes essential information about the instrument, 
        and a time series dataset. 
        The time series consists of chronological entries with Open, High, Low, and Close prices, 
        and for applicable instruments, it also includes trading volume. 
        This endpoint is ideal for retrieving comprehensive historical price data for analysis 
        or visualization purposes.
        """
        
        try:
            ticker = yf.Ticker(symbol)

            if start_date:
                is_valid, _ = validate_date(start_date)
                if not is_valid:
                    return False, f"Invalid start date format. Use YYYY-MM-DD format (e.g., '2024-01-01'). Provided: {start_date}"
            if end_date:
                is_valid, _ = validate_date(end_date)
                if not is_valid:
                    return False, f"Invalid end date format. Use YYYY-MM-DD format (e.g., '2024-12-31'). Provided: {end_date}"
            
            # Validate date range if both dates are provided
            if start_date and end_date:
                is_valid, error_msg = validate_date_range(start_date, end_date)
                if not is_valid:
                    return False, error_msg

            if outputsize > 5000 or outputsize < 1:
                return False, f"outputsize must be between 1 and 5000, got {outputsize}"

            # Get historical data
            import warnings
            import io
            import sys
            
            # Capture warnings and stderr to include Yahoo Finance error messages
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                old_stderr = sys.stderr
                sys.stderr = captured_stderr = io.StringIO()
                
                try:
                    if start_date and end_date:
                        # Use specific date range if provided
                        data = ticker.history(interval=interval, start=start_date, end=end_date)
                    elif start_date:
                        # Only start date provided
                        data = ticker.history(interval=interval, start=start_date)
                    elif end_date:
                        # Only end date provided
                        data = ticker.history(interval=interval, end=end_date)
                    else:
                        # Get maximum available historical data for the interval
                        # Note: Intraday intervals are limited to ~7 days by Yahoo Finance
                        data = ticker.history(interval=interval, period="max")
                finally:
                    sys.stderr = old_stderr
                    stderr_output = captured_stderr.getvalue()
            
            # Check if data is empty
            if data.empty:
                error_msg = f"No data available for symbol '{symbol}' with interval '{interval}'"
                # Add Yahoo Finance error details if available
                if stderr_output:
                    error_msg += f". Yahoo Finance error: {stderr_output.strip()}"
                elif w:
                    warning_msgs = [str(warning.message) for warning in w]
                    if warning_msgs:
                        error_msg += f". Warnings: {'; '.join(warning_msgs)}"
                return False, error_msg
            
            # Limit to outputsize if specified
            if outputsize and len(data) > outputsize:
                data = data.tail(outputsize)
            
            # Get ticker info for metadata
            try:
                info = ticker.info
            except Exception:
                # If info fails, use minimal metadata
                info = {}
            
            # Build metadata
            meta = {
                "symbol": info.get('symbol', 'N/A'),
                "interval": interval,
                "currency": info.get('currency', 'N/A'),
                "exchange_timezone": info.get('exchangeTimezoneName', 'N/A'),
                "exchange": info.get('fullExchangeName', 'N/A'),
                "type": info.get('quoteType', 'N/A'),
            }
            
            # Build values array
            values = []
            for timestamp, row in data.iterrows():
                values.append({
                    "datetime": timestamp.tz_convert('UTC').strftime("%Y-%m-%d %H:%M:%S %Z"),
                    "open": f"{row['Open']:.5f}",
                    "high": f"{row['High']:.5f}",
                    "low": f"{row['Low']:.5f}",
                    "close": f"{row['Close']:.5f}",
                    "volume": str(int(row['Volume']))
                })
            
            result = {
                "meta": meta,
                "values": values
            }
            
            return True, result
            
        except Exception as e:
            return False, str(e)

    def quote(
        self,
        symbol: str, # string
        interval: str = "1d", # string; valid intervals: [1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 4h, 1d, 5d, 1wk, 1mo, 3mo]
        rolling_period: int = 24, # integer; Number of hours for calculate rolling change at period. By default set to 24, it can be in range [1, 168].
        ):
        """
        The quote endpoint provides real-time data for a selected financial instrument, 
        returning essential information such as the latest price, open, high, low, close, 
        volume, and price change. This endpoint is ideal for users needing up-to-date 
        market data to track price movements and trading activity for specific stocks, 
        ETFs, or other securities.
        """
        try:
            # Validate rolling_period
            if rolling_period < 1 or rolling_period > 168:
                return False, f"rolling_period must be between 1 and 168 hours, got {rolling_period}"
            
            ticker = yf.Ticker(symbol)
            
            # Get ticker info
            info = ticker.info
            
            # Determine asset type
            quote_type = info.get('quoteType')
            is_crypto = quote_type == 'CRYPTOCURRENCY'
            
            # Get the latest bar data based on interval
            hist = ticker.history(period="1d", interval=interval)
            
            # Use interval-based data if available, otherwise fall back to info data
            if not hist.empty:
                latest_bar = hist.iloc[-1]
                bar_timestamp = hist.index[-1]

                bar_open = float(latest_bar['Open'])
                bar_high = float(latest_bar['High'])
                bar_low = float(latest_bar['Low'])
                bar_close = float(latest_bar['Close'])
                bar_volume = int(latest_bar['Volume'])
                bar_datetime = bar_timestamp.tz_convert('UTC').strftime("%Y-%m-%d %H:%M:%S %Z")
            else:
                # Fallback to info data
                bar_open = info.get('regularMarketOpen', 'N/A')
                bar_high = info.get('regularMarketDayHigh', 'N/A')
                bar_low = info.get('regularMarketDayLow', 'N/A')
                bar_close = info.get('regularMarketPrice', 'N/A')
                bar_volume = info.get('regularMarketVolume', 'N/A')
                bar_datetime = datetime.fromtimestamp(info.get('regularMarketTime'), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z") if info.get('regularMarketTime') else 'N/A'
            
            # Build base result with always-present fields
            result = {
                "symbol": info.get('symbol', 'N/A'),
                "name": info.get('longName', 'N/A'),
                "exchange": info.get('fullExchangeName', 'N/A'),
                "currency": info.get('currency', 'N/A'),
                "datetime": bar_datetime,
                "last_quote_at": datetime.fromtimestamp(info.get('regularMarketTime'), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z") if info.get('regularMarketTime') else 'N/A',
                "open": bar_open,
                "high": bar_high,
                "low": bar_low,
                "close": bar_close,
                "volume": bar_volume,
                "average_volume": info.get('averageVolume', 'N/A'),
                "previous_close": info.get('regularMarketPreviousClose', 'N/A'),
                "change": info.get('regularMarketChange', 'N/A'),
                "percent_change": info.get('regularMarketChangePercent', 'N/A'),
                "is_market_open": info.get('marketState', 'N/A'),
                "fifty_two_week": {
                    "low": info.get('fiftyTwoWeekLow', 'N/A'),
                    "high": info.get('fiftyTwoWeekHigh', 'N/A'),
                    "low_change": info.get('fiftyTwoWeekLowChange', 'N/A'),
                    "high_change": info.get('fiftyTwoWeekHighChange', 'N/A'),
                    "low_change_percent": info.get('fiftyTwoWeekLowChangePercent', 'N/A'),
                    "high_change_percent": info.get('fiftyTwoWeekHighChangePercent', 'N/A'),
                    "range": info.get('fiftyTwoWeekRange', 'N/A')
                },
                "extended_change": info.get('postMarketChange', 'N/A'),
                "extended_percent_change": info.get('postMarketChangePercent', 'N/A'),
                "extended_price": info.get('postMarketPrice', 'N/A'),
                "extended_timestamp": datetime.fromtimestamp(info.get('postMarketTime'), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z") if info.get('postMarketTime') else 'N/A',
            }
            
            # Calculate and add rolling changes
            current_price = info.get('regularMarketPrice')
            if current_price:
                try:
                    # Get historical data for rolling calculations (8 days to cover 7d + buffer)
                    hist_rolling = ticker.history(period="8d", interval="1h")
                    
                    if not hist_rolling.empty:
                        # Calculate rolling_1d_change (24 hours ago)
                        if len(hist_rolling) >= 24:
                            price_1d_ago = float(hist_rolling.iloc[-24]['Close'])
                            result["rolling_1d_change"] = f"{((current_price - price_1d_ago) / price_1d_ago * 100):.5f}"
                        
                        # Calculate rolling_7d_change (168 hours ago)
                        if len(hist_rolling) >= 168:
                            price_7d_ago = float(hist_rolling.iloc[-168]['Close'])
                            result["rolling_7d_change"] = f"{((current_price - price_7d_ago) / price_7d_ago * 100):.5f}"
                        
                        # Calculate rolling_change based on rolling_period
                        if len(hist_rolling) >= rolling_period:
                            price_period_ago = float(hist_rolling.iloc[-rolling_period]['Close'])
                            result["rolling_change"] = f"{((current_price - price_period_ago) / price_period_ago * 100):.5f}"
                except Exception:
                    # If rolling calculations fail, don't include them
                    pass      
            
            return True, result
            
        except Exception as e:
            return False, str(e)

    def screener(
        self, 
        screener_name: str, 
        outputsize: int = 30
        ):
        """
        The screener endpoint provides a list of all available screeners in Yahoo Finance.
        """
        try:
            response = screen(screener_name, count=outputsize)

            result = {
                "values": [
                    {   
                        "rank": index + 1,
                        **record
                    } for index, record in enumerate(response['quotes'] if 'quotes' in response else response['records'])
                ]
            }

            return True, result
        except Exception as e:
            return False, str(e)

    def available_screeners(
        self
        ):
        """
        The available screeners endpoint provides a list of all available screeners in Yahoo Finance.
        """
        try:    
            return True, AVAILABLE_SCREENERS
        except Exception as e:
            return False, str(e)

    def symbol_search(
        self,
        query: str, # string; this is a super simple qeury with company name or guessed symbol (e.g. "apple" or "AAPL", "microsoft" or "MSFT")
        outputsize: int = 30, # int; Specifies the size of the snapshot. Can be in a range from 1 to 50. Default is 30.
        ):
        """
        The symbol search endpoint allows users to find financial instruments by name or symbol. 
        It returns a list of matching symbols, ordered by relevance, with the most relevant 
        instrument first. This is useful for quickly locating specific stocks, ETFs, or other 
        financial instruments when only partial information is available.
        """
        try:
            result = yf.Search(query, max_results=outputsize).quotes

            return True, result

        except Exception as e:
            return False, {"error": str(e)}

    def profile(
        self,
        symbol: str, # string
        ):
        """
        The fundamentals endpoint provides comprehensive financial data for a specified financial 
        instrument. It returns detailed information about the company's financial performance, 
        including key metrics, financial ratios, and other relevant data. This endpoint is ideal 
        for users needing in-depth analysis of a company's financial health and performance.
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            return True, info
        except Exception as e:
            return False, {"error": str(e)}

    def calculate_indicator(
        self,
        symbol: str,
        indicator_name: str,
        interval: str,
        outputsize: int = 30,
        start_date: str = None,
        end_date: str = None,
        **kwargs
        ):
        """
        Generic method to calculate any supported technical indicator using the registry.
        """
        try:
            from src.api.indicators import get_indicator_config
            config = get_indicator_config(indicator_name)
            if not config:
                return False, f"Indicator '{indicator_name}' not supported."

            # Merge defaults with kwargs
            params = config['params'].copy()
            params.update(kwargs)
            
            # Determine buffer size needed for calculation
            buffer = 0
            for k, v in params.items():
                if 'period' in k and isinstance(v, int):
                    buffer = max(buffer, v)
            if buffer == 0: buffer = 50 
            
            # Special case buffers - these need more warmup for stability
            if indicator_name.startswith('ema'):
                # EMAs need 2-3x their period to stabilize properly
                buffer = params.get('timeperiod', 20) * 3
            elif indicator_name.startswith('sma'):
                # SMAs need 2x their period to ensure smooth data
                buffer = params.get('timeperiod', 20) * 2
            elif indicator_name.startswith('macd'):
                buffer = params.get('slowperiod', 26) + params.get('signalperiod', 9)
            elif indicator_name.startswith('stoch'):
                buffer = params.get('fastk_period', 5) + params.get('slowk_period', 3) + params.get('slowd_period', 3)
            elif indicator_name.startswith('adx'):
                 buffer = params.get('timeperiod', 14) * 2
            elif indicator_name.startswith('bbands'):
                # Bollinger Bands need 2x period for MA calculation
                buffer = params.get('timeperiod', 20) * 2
            
            # Fetch data
            success, data = self.time_series(
                symbol=symbol, 
                interval=interval, 
                outputsize=outputsize + buffer, 
                start_date=start_date, 
                end_date=end_date
            )
            if not success:
                return False, data

            # Prepare inputs
            inputs = {}
            # Need to map 'close' -> data['values']...['close']
            arrays = {
                'open': [], 'high': [], 'low': [], 'close': [], 'volume': []
            }
            for v in data['values']:
                for k in arrays:
                    arrays[k].append(float(v[k]))
            
            for k in arrays:
                arrays[k] = np.array(arrays[k])
            
            # Handle Benchmark (Beta)
            if config.get('requires_benchmark'):
                benchmark_symbol = params.pop('benchmark_symbol', None)
                if not benchmark_symbol:
                    return False, "A benchmark_symbol parameter is required for the beta indicator."
                success_bench, data_bench = self.time_series(
                    symbol=benchmark_symbol,
                    interval=interval,
                    outputsize=outputsize + buffer,
                    start_date=start_date,
                    end_date=end_date
                )
                if not success_bench:
                    return False, f"Benchmark data failed: {data_bench}"
                
                bench_closes = np.array([float(v['close']) for v in data_bench['values']])
                
                # Ensure equal length
                min_len = min(len(arrays['close']), len(bench_closes))
                arrays['close'] = arrays['close'][-min_len:]
                bench_closes = bench_closes[-min_len:]
                
                # Update data values for result mapping
                data['values'] = data['values'][-min_len:]
                
                # Helper for args
                inputs['benchmark_close'] = bench_closes

            # Build args list
            args = []
            for inp_name in config['inputs']:
                if inp_name == 'benchmark_close':
                    args.append(inputs['benchmark_close'])
                else:
                    args.append(arrays[inp_name])
            
            # Call Talib
            func_name = config['talib_function']
            func = getattr(talib, func_name)
            
            try:
                result_arrays = func(*args, **params)
            except Exception as e:
                return False, f"Talib calculation failed for {indicator_name}: {str(e)}"
            
            if isinstance(result_arrays, tuple):
                results = result_arrays
            else:
                results = (result_arrays,)
            
            # Format output
            output_names = config['outputs']
            formatted_result = []
            
            result_len = len(results[0])
            # We want the last 'outputsize' elements, but result_len matches input len
            # data['values'] matches input len
            
            # Valid indices are where we have data. Talib puts NaNs at start.
            # We return exactly what corresponds to the requested outputsize from the end
            
            start_idx = max(0, result_len - outputsize)
            
            for i in range(start_idx, result_len):
                 dt = data['values'][i]['datetime']
                 row = {"datetime": dt}
                 for j, out_name in enumerate(output_names):
                     val = results[j][i]
                     if np.isnan(val):
                         row[out_name] = None
                     else:
                         row[out_name] = float(val)
                 formatted_result.append(row)
                 
            return True, formatted_result

        except Exception as e:
            return False, str(e)

