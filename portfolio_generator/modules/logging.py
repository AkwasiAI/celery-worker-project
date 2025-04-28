"""Logging functions for the portfolio generator."""

def log_error(message):
    """Print an error message in red."""
    print(f"\033[91m[ERROR] {message}\033[0m")
    
def log_warning(message):
    """Print a warning message in yellow."""
    print(f"\033[93m[WARNING] {message}\033[0m")
    
def log_success(message):
    """Print a success message in green."""
    print(f"\033[92m[SUCCESS] {message}\033[0m")
    
def log_info(message):
    """Print an info message in blue."""
    print(f"\033[94m[INFO] {message}\033[0m")
