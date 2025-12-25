import requests
from urllib.parse import urlencode
from difflib import SequenceMatcher

def to_alpaca_format(symbol: str) -> str:
    """Convert internal symbol format to Alpaca format (uses slash)."""
    return symbol.replace('-', '/')

def to_yfinance_format(symbol: str) -> str:
    """Convert Alpaca symbol format to internal format (uses dash)."""
    return symbol.replace('/', '-')

def convert_response_symbols(response):
    """Convert symbol fields in API responses from Alpaca format to internal format."""
    if isinstance(response, dict) and 'symbol' in response:
        response['symbol'] = to_yfinance_format(response['symbol'])
    elif isinstance(response, list):
        for item in response:
            if isinstance(item, dict) and 'symbol' in item:
                item['symbol'] = to_yfinance_format(item['symbol'])
    return response

class AlpacaAPI:
    @staticmethod
    def validate_keys(api_key: str, secret_key: str):
        """Validate Alpaca API keys by attempting to fetch account info."""
        live_url = "https://api.alpaca.markets/v2"
        paper_url = "https://paper-api.alpaca.markets/v2"
        
        if not api_key or not secret_key:
            return False, ""
            
        try:
            headers = {
                "accept": "application/json",
                "APCA-API-KEY-ID": api_key,
                "APCA-API-SECRET-KEY": secret_key
            }
            
            # Try paper trading URL first
            response = requests.get(paper_url + "/account", headers=headers)
            if response.status_code == 200:
                return True, paper_url
            
            # If paper fails, try live trading URL
            response = requests.get(live_url + "/account", headers=headers)
            return response.status_code == 200, live_url if response.status_code == 200 else ""
        except:
            return False, ""

    def __init__(self, api_key: str, secret_key: str):
        _, self.url = AlpacaAPI.validate_keys(api_key, secret_key)

        
        self.url_orders = self.url + "/orders"
        self.url_positions = self.url + "/positions"
        self.url_assets = self.url + "/assets"
        self.url_account = self.url + "/account"
        
        self.api_key = api_key
        self.api_secret = secret_key

        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret
        }

    def get_account(self):
        """
        Get the account information.
        """
        try:
            response = requests.get(self.url_account, headers=self.headers)
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, f"Request to Alpaca succeeded but API returned an error: {response.json()}"
        except Exception as e:
            return False, f"Request to Alpaca failed (network error or unexpected exception): {str(e)}"

    #########################################################
    # Orders
    #########################################################
    def create_order(
        self, 
        symbol, # string
        qty, # float/int or None
        notional, # float/int or None
        side, # string enum
        type, # string enum
        time_in_force, # string enum
        limit_price, # float/int or None
        stop_price, # float/int or None
        trail_price, # float/int or None
        trail_percent, # float/int or None
        extended_hours, # boolean
        order_class, # string enum
        take_profit, # dict with float values or None
        stop_loss, # dict with float values or None
        ):
        
        # Convert numeric values to strings for API
        take_profit_api = None
        if take_profit:
            take_profit_api = {k: str(v) for k, v in take_profit.items()}
        
        stop_loss_api = None
        if stop_loss:
            stop_loss_api = {k: str(v) for k, v in stop_loss.items()}
        
        payload = {
            "time_in_force": time_in_force,
            "symbol": to_alpaca_format(symbol),
            "qty": str(qty) if qty is not None else None,
            "notional": str(notional) if notional is not None else None,
            "side": side,
            "type": type,
            "time_in_force": time_in_force,
            "limit_price": str(limit_price) if limit_price is not None else None,
            "stop_price": str(stop_price) if stop_price is not None else None,
            "trail_price": str(trail_price) if trail_price is not None else None,
            "trail_percent": str(trail_percent) if trail_percent is not None else None,
            "extended_hours": extended_hours,
            "order_class": order_class,
            "take_profit": take_profit_api,
            "stop_loss": stop_loss_api,

        }

        try:
            response = requests.post(self.url_orders, json=payload, headers=self.headers)
            # if the response is 200, return true and the response
            if response.status_code == 200:
                return True, convert_response_symbols(response.json())
            # if the response is 422 or 403, return false and the error message
            if response.status_code == 422 or response.status_code == 403:
                return False, f"Request to Alpaca succeeded but API returned an error: {response.json()}"
            # if the response is unknown, return false and the error message
            else:
                return False, f"Request to Alpaca succeeded but API returned an unknown error: {response.json()}"
        except Exception as e:
            return False, f"Request to Alpaca failed (network error or unexpected exception): {str(e)}"

    def get_orders(
        self,
        status = None,  # string enum: "open", "closed", "all"
        symbols = None,  # list of strings
        side = None,  # string enum: "buy", "sell"
        ):
        """
        Get orders with optional filters.
        
        Args:
            status: Filter by order status ("open", "closed", "all")
            symbols: List of ticker symbols to filter by
            side: Filter by order side ("buy", "sell")
        
        Returns:
            Tuple of (success: bool, response: dict or list)
        """
        # Build query parameters dictionary
        params = {}
        
        if status is not None:
            params["status"] = status
        
        # Join symbols with comma for the API
        if symbols is not None and len(symbols) > 0:
            params["symbols"] = ",".join([to_alpaca_format(symbol) for symbol in symbols])

        if side is not None:
            params["side"] = side
        
        # Construct URL with query parameters
        url = self.url_orders
        if params:
            url = f"{self.url_orders}?{urlencode(params)}"
        
        try:
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                return True, convert_response_symbols(response.json())
            else:
                return False, f"Request to Alpaca succeeded but API returned an error: {response.json()}"
        except Exception as e:
            return False, f"Request to Alpaca failed (network error or unexpected exception): {str(e)}"

    def delete_order_by_id(
        self,
        order_id,  # string
        ):
        """
        Delete an order with the specified ID.

        Args:
            order_id (str): The ID of the order to delete

        Returns:
            Tuple of (success: bool, response: dict)
        """
        url = f"{self.url_orders}/{order_id}"
        try:
            response = requests.delete(url, headers=self.headers)
            if response.status_code == 204:
                return True, "Order cancelled successfully"
            elif response.status_code == 422:
                return False, f"The order status is not cancelable: {response.json()}"
            else:
                return False, f"Request to Alpaca succeeded but API returned an unknown error: {response.json()}"
        except Exception as e:
            return False, f"Request to Alpaca failed (network error or unexpected exception): {str(e)}"

    #########################################################
    # Positions
    #########################################################
    def get_all_positions(
        self,
        ):
        """
        Get all positions.
        """
        try:
            response = requests.get(self.url_positions, headers=self.headers)
            if response.status_code == 200:
                return True, convert_response_symbols(response.json())
            else:
                return False, f"Request to Alpaca succeeded but API returned an error: {response.json()}"
        except Exception as e:
            return False, f"Request to Alpaca failed (network error or unexpected exception): {str(e)}"

    def get_position_by_symbol(
        self,
        symbol,  # string
        ):
        """
        Get a position by symbol.
        """
        try:
            url = f"{self.url_positions}/{to_alpaca_format(symbol)}"
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                return True, convert_response_symbols(response.json())
            else:
                return False, f"Request to Alpaca succeeded but API returned an error: {response.json()}"
        except Exception as e:
            return False, f"Request to Alpaca failed (network error or unexpected exception): {str(e)}"

    def close_position_by_symbol(
        self,
        symbol,  # string
        qty, # number
        percentage, # number
        ):
        """
        Close a position by symbol.
        """
        # Build query parameters dictionary
        params = {}
        
        if qty is not None:
            params["qty"] = qty
        
        if percentage is not None:
            params["percentage"] = percentage
        
        # Construct URL with query parameters
        url = f"{self.url_positions}/{to_alpaca_format(symbol)}"
        if params:
            url = f"{url}?{urlencode(params)}"
        
        try:
            response = requests.delete(url, headers=self.headers)
            if response.status_code == 200:
                return True, convert_response_symbols(response.json())
            else:
                return False, f"Request to Alpaca succeeded but API returned an error: {response.json()}"
        except Exception as e:
            return False, f"Request to Alpaca failed (network error or unexpected exception): {str(e)}"

    #########################################################
    # Assets
    #########################################################
    def get_asset_by_symbol(
        self,
        symbol,  # string
        ):
        """
        Get an asset by symbol.
        Returns 200 if asset exists, 404 if not found.
        """
        url = f"{self.url_assets}/{to_alpaca_format(symbol)}"
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                return True, convert_response_symbols(response.json())
            elif response.status_code == 404:
                return False, f"Asset not found: {response.json()}"
            else:
                return False, f"Request to Alpaca succeeded but API returned an error: {response.json()}"
        except Exception as e:
            return False, f"Request to Alpaca failed (network error or unexpected exception): {str(e)}"

    def symbol_search(
        self,
        query: str,  # string
        outputsize: int = 30,  # int
        ):
        """
        Search for ticker symbols using similarity matching on the ticker itself.
        Use this when you have a guessed ticker and want to find the correct symbol.
        Filters out symbols with dots and returns matches in internal format.
        
        Args:
            query: Guessed ticker symbol (e.g., "BTCUSD", "AAPL", "TSLA")
            outputsize: Maximum number of results to return (default: 30)
        
        Returns:
            Tuple of (success: bool, results: list of dicts)
        """
        try:
            # Fetch all assets
            response = requests.get(self.url_assets, headers=self.headers)
            if response.status_code != 200:
                return False, f"Request to Alpaca succeeded but API returned an error: {response.json()}"
            
            assets = response.json()
            
            # Filter out symbols with dots
            filtered_assets = [asset for asset in assets if '.' not in asset['symbol']]
            
            # Calculate similarity scores
            matches = []
            for asset in filtered_assets:
                symbol = asset['symbol']
                similarity = SequenceMatcher(None, query.upper(), symbol.upper()).ratio()
                matches.append((similarity, asset))
            
            # Sort by similarity (descending) and get top N
            matches.sort(reverse=True, key=lambda x: x[0])
            top_matches = matches[:outputsize]
            
            # Convert to internal format
            results = []
            for similarity, asset in top_matches:
                result = {
                    'symbol': to_yfinance_format(asset['symbol']),
                    'name': asset.get('name', ''),
                    'class': asset.get('class', ''),
                    'exchange': asset.get('exchange', ''),
                    'similarity': round(similarity, 3)
                }
                results.append(result)
            
            return True, results
            
        except Exception as e:
            return False, f"Request to Alpaca failed (network error or unexpected exception): {str(e)}"