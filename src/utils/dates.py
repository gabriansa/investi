from datetime import datetime, timezone
from dateutil import parser as dateutil_parser


def validate_date(
    date_str,
    input_format="%Y-%m-%d",
    tz=timezone.utc,
    check_future=False
) -> tuple[bool, datetime | None]:
    """
    Validates a date string and returns a datetime object.
    
    Args:
        date_str: Date string to validate (can be None)
        input_format: Format to parse from (e.g., "%Y-%m-%d"). Defaults to "%Y-%m-%d".
        tz: Timezone to apply to the datetime object. Defaults to UTC.
        check_future: If True, validates that the date is in the future. Defaults to False.
    
    Returns:
        Tuple of (is_valid, datetime_object | None)
    """
    try:
        if date_str is None:
            return True, None
        
        # If input format expects microseconds (%f), truncate fractional seconds to 6 digits
        if '%f' in input_format and '.' in date_str:
            parts = date_str.split('.')
            if len(parts) == 2:
                date_str = f"{parts[0]}.{parts[1][:6].ljust(6, '0')}"
        
        dt = datetime.strptime(date_str, input_format)
        
        # Always apply timezone for consistency
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        
        # Check if date is in the future if required
        if check_future:
            now = datetime.now(tz)
            if dt < now:
                return False, None
        
        return True, dt
    except:
        return False, None


def format_timestamp(dt: datetime, tz: timezone = timezone.utc) -> str:
    """
    Format a datetime object to the standard display format.
    
    Args:
        dt: datetime object to format (naive or aware)
        tz: timezone to apply if dt is naive (defaults to UTC)
    
    Returns:
        Formatted string in format: YYYY-MM-DD HH:MM:SS TZ
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.strftime("%Y-%m-%d %H:%M:%S %Z")


def parse_and_format_timestamp(timestamp_str: str | None, tz: timezone = timezone.utc) -> str | None:
    """
    Parse any common timestamp format and convert to our standard format.
    Handles ISO 8601, RFC 3339, and many other common formats.
    
    Args:
        timestamp_str: Timestamp string in any common format (can be None)
        tz: Timezone to apply if timestamp is naive (defaults to UTC)
    
    Returns:
        Formatted string in format: YYYY-MM-DD HH:MM:SS TZ, or None if parsing fails
    
    Examples:
        >>> parse_and_format_timestamp("2024-01-15T14:30:00.123456Z")
        "2024-01-15 14:30:00 UTC"
        
        >>> parse_and_format_timestamp("2024-01-15 14:30:00")
        "2024-01-15 14:30:00 UTC"
        
        >>> parse_and_format_timestamp("Jan 15, 2024 2:30 PM")
        "2024-01-15 14:30:00 UTC"
    """
    if timestamp_str is None:
        return None
    
    try:
        # Use dateutil parser which handles many formats intelligently
        dt = dateutil_parser.parse(timestamp_str)
        
        # Apply timezone if naive
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        
        return format_timestamp(dt)
    except:
        return None


def format_api_timestamps(data, timestamp_fields: list[str] | None = None):
    """
    Format timestamp fields in API response data from any format to our standard format.
    Handles both dict and list responses. Modifies data in-place.
    
    Args:
        data: Dict or list containing timestamp fields
        timestamp_fields: List of field names to format. If None, uses common API fields.
    
    Examples:
        >>> order = {"created_at": "2024-01-15T14:30:00Z", "price": "100.00"}
        >>> format_api_timestamps(order)
        >>> order["created_at"]
        "2024-01-15 14:30:00 UTC"
    """
    if timestamp_fields is None:
        # Default common timestamp fields from various APIs
        timestamp_fields = [
            'created_at', 'updated_at', 'submitted_at', 'filled_at', 
            'expired_at', 'canceled_at', 'timestamp', 'datetime',
            'last_updated', 'modified_at'
        ]
    
    if isinstance(data, dict):
        for field in timestamp_fields:
            if field in data and data[field]:
                formatted = parse_and_format_timestamp(data[field])
                if formatted:
                    data[field] = formatted
    elif isinstance(data, list):
        for item in data:
            format_api_timestamps(item, timestamp_fields)


def convert_date_format(
    date_str: str,
    input_format: str = "%Y-%m-%d",
    output_format: str = "%m/%d/%Y"
) -> tuple[bool, str | None]:
    """
    Convert date string from one format to another.
    Used for API integrations that require specific date formats.
    
    Args:
        date_str: Date string to convert
        input_format: Format to parse from (e.g., "%Y-%m-%d")
        output_format: Format to convert to (e.g., "%m/%d/%Y")
    
    Returns:
        Tuple of (success, converted_string | None)
    """
    try:
        dt = datetime.strptime(date_str, input_format)
        return True, dt.strftime(output_format)
    except:
        return False, None


def validate_date_range(
    start_date: str,
    end_date: str,
    input_format="%Y-%m-%d"
) -> tuple[bool, str | None]:
    """
    Validates that end_date is after start_date and they are not equal.
    
    Args:
        start_date: Start date string to validate (required)
        end_date: End date string to validate (required)
        input_format: Format to parse dates from. Defaults to "%Y-%m-%d".
        
    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if dates are valid
        - (False, error_message) if validation fails
    """
    try:
        # Parse both dates
        start_dt = datetime.strptime(start_date, input_format)
        end_dt = datetime.strptime(end_date, input_format)
        
        # Check if dates are equal
        if start_dt == end_dt:
            return False, f"end_date cannot be equal to start_date. Both are set to {start_date}"
        
        # Check if end_date is before start_date
        if end_dt < start_dt:
            return False, f"end_date ({end_date}) must be after start_date ({start_date})"
        
        return True, None
    except Exception as e:
        return False, f"Error validating date range: {str(e)}"
