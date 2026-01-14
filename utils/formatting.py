"""
Formatting utilities.
"""


def format_currency(amount: int, currency: str = "GBP") -> str:
    """
    Format an integer amount as currency.

    Args:
        amount: The amount in whole units (e.g., pounds, not pence).
        currency: Currency code (default GBP).

    Returns:
        Formatted currency string.
    """
    symbols = {
        "GBP": "£",
        "USD": "$",
        "EUR": "€",
    }
    symbol = symbols.get(currency, currency + " ")
    return f"{symbol}{amount:,}"


def format_percent(value: float, decimals: int = 1) -> str:
    """
    Format a number as a percentage.

    Args:
        value: The percentage value.
        decimals: Number of decimal places.

    Returns:
        Formatted percentage string.
    """
    return f"{value:.{decimals}f}%"
