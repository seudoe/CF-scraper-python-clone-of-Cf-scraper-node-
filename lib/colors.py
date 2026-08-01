"""Color utilities for terminal output"""
from colorama import Fore, Style, init

# Initialize colorama for Windows compatibility
init(autoreset=True)

def red(text):
    """Red for errors"""
    return f"{Fore.RED}{text}{Style.RESET_ALL}"

def green(text):
    """Green for success (saved to DB, etc)"""
    return f"{Fore.GREEN}{text}{Style.RESET_ALL}"

def yellow(text):
    """Yellow for fetching/loading"""
    return f"{Fore.YELLOW}{text}{Style.RESET_ALL}"

def cyan(text):
    """Cyan for info"""
    return f"{Fore.CYAN}{text}{Style.RESET_ALL}"

def magenta(text):
    """Magenta for parsing"""
    return f"{Fore.MAGENTA}{text}{Style.RESET_ALL}"

def light_red(text):
    """Light red for warnings"""
    return f"{Fore.LIGHTRED_EX}{text}{Style.RESET_ALL}"

def dark_red(text):
    """Dark red for critical errors"""
    return f"{Fore.RED}{Style.DIM}{text}{Style.RESET_ALL}"

def blue(text):
    """Blue for database operations"""
    return f"{Fore.BLUE}{text}{Style.RESET_ALL}"

def gray(text):
    """Gray for debug/minor info"""
    return f"{Fore.LIGHTBLACK_EX}{text}{Style.RESET_ALL}"

def bold(text):
    """Bold text"""
    return f"{Style.BRIGHT}{text}{Style.RESET_ALL}"

# Semantic helpers
def error(text):
    """Error message (red)"""
    return red(f"✗ {text}")

def success(text):
    """Success message (green)"""
    return green(f"✓ {text}")

def warning(text):
    """Warning message (light red)"""
    return light_red(f"⚠ {text}")

def info(text):
    """Info message (cyan)"""
    return cyan(text)
