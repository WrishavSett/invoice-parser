"""
Helper Module

This module provides utility functions for invoice data processing,
including number-to-words conversion and value validation.
"""

try:
    from num2words import num2words
except ImportError:
    raise ImportError("Please install num2words: pip install num2words")


def number_to_words_inr(amount: float) -> str:
    """
    Convert a numeric amount to its word representation in Indian Rupees format.
    
    This function converts a decimal amount into a properly formatted string
    representation following Indian English conventions for currency.
    
    Args:
        amount (float): The monetary amount to convert (e.g., 12345.67).
    
    Returns:
        str: The amount in words formatted as "Rupees [Amount] and [Paisa] Paisa Only."
             Example: "Rupees Twelve Thousand Three Hundred Forty Five and Sixty Seven Paisa Only."
             If there are no paise, returns: "Rupees [Amount] and Paisa Only."
    
    Examples:
        >>> number_to_words_inr(1234.56)
        'Rupees One Thousand Two Hundred Thirty Four and Fifty Six Paisa Only.'
        
        >>> number_to_words_inr(5000.00)
        'Rupees Five Thousand and Paisa Only.'
    """
    rupees = int(amount)
    paise = int(round((amount - rupees) * 100))

    rupees_words = num2words(rupees, lang="en_IN").replace("-", " ").title()

    rupees_words = (
        rupees_words
        .replace("-", "")
        .replace(",", "")
        .replace(" and ", " ")
        .replace(" And ", " ")
        .title()
    )

    if paise > 0:
        paise_words = num2words(paise, lang="en_IN").replace("-", " ").title()
        return f"Rupees {rupees_words} and {paise_words} Paisa Only."
    else:
        return f"Rupees {rupees_words} and Paisa Only."
    

def is_value_present(value) -> bool:
    """
    Check if a value is present and non-empty.
    
    This function validates whether a value contains actual data or is effectively empty.
    It handles various data types including None, strings, lists, and dictionaries.
    
    Args:
        value: The value to check. Can be of any type (str, list, dict, None, etc.).
    
    Returns:
        bool: True if the value is present and non-empty, False otherwise.
        
    Examples:
        >>> is_value_present(None)
        False
        
        >>> is_value_present("")
        False
        
        >>> is_value_present("   ")
        False
        
        >>> is_value_present("Hello")
        True
        
        >>> is_value_present([])
        False
        
        >>> is_value_present([1, 2, 3])
        True
        
        >>> is_value_present({})
        False
        
        >>> is_value_present({"key": "value"})
        True
    """
    if value is None:
        return False
    if isinstance(value, str) and value.strip() == "":
        return False
    if isinstance(value, (list, dict)) and len(value) == 0:
        return False
    return True