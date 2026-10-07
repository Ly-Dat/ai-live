from nicegui import ui

# Check whether it is purely digits
def is_pure_number(text):
    """Check whether it is purely digits

    Args:
        text (str): Text to detect

    Returns:
        bool: Whether it is purely digits
    """
    return text.isdigit()

# Whether it isurl
def is_url_check(url):
    from urllib.parse import urlparse
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False
    
ui.input(
    label='Text', 
    placeholder='start typing',
    on_change=lambda e: result.set_text('you typed: ' + e.value),
    validation=
    {
        'Input too long': lambda value: len(value) < 20,
        'Input too short': lambda value: len(value) > 5,
        'not num': lambda value: is_pure_number(value),

    }
)
ui.input(
    label='Text', 
    placeholder='start typing',
    on_change=lambda e: result.set_text('you typed: ' + e.value),
    validation=
    {
        'not url': lambda value: is_url_check(value),
    }
)
result = ui.label()

ui.run(port=8111)