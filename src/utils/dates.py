from datetime import datetime, timezone


def validate_date(
    date_str,
    input_format="%Y-%m-%d",
    output_format="%Y-%m-%d",
    tz=timezone.utc,
    check_future=False
) -> tuple[bool, str | None]:
    """
    Validates a date string format and converts it to another format if specified.
    
    Args:
        date_str: Date string to validate (can be None)
        input_format: Format to parse from (e.g., "%Y-%m-%d"). Defaults to "%Y-%m-%d".
        output_format: Format to convert to (e.g., "%m/%d/%Y" or "%Y-%m-%d %H:%M:%S %Z"). Defaults to "%Y-%m-%d".
                      If format includes %Z or %z, the specified timezone will be applied.
        tz: Timezone to apply when output format includes timezone specifiers. Defaults to UTC.
        check_future: If True, validates that the date is in the future. Defaults to False.
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
        
        # Add timezone if output format includes timezone specifiers or if checking future
        if output_format and ('%Z' in output_format or '%z' in output_format):
            dt = dt.replace(tzinfo=tz)
        elif check_future and dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        
        # Check if date is in the future if required
        if check_future:
            now = datetime.now(tz)
            if dt < now:
                return False, None
        
        if output_format:
            return True, dt.strftime(output_format)
        return True, dt.strftime()
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
