import os
import logging

class SecurityError(Exception):
    """Raised when a security violation is detected."""
    pass

def validate_path(path: str, root_dir: str) -> str:
    """
    Validates that a path is safe and within the root directory.
    Prevents directory traversal attacks.
    
    Args:
        path: The path to validate (absolute or relative).
        root_dir: The allowed root directory.
        
    Returns:
        The absolute path if valid.
        
    Raises:
        SecurityError: If the path is outside the root directory.
    """
    # Resolve absolute paths
    abs_root = os.path.abspath(root_dir)
    abs_path = os.path.abspath(os.path.join(abs_root, path))
    
    # Check if path is within root
    # os.path.commonpath returns the longest common sub-path
    # If the common path is the root, then the file is inside (or is) the root
    try:
        common = os.path.commonpath([abs_root, abs_path])
    except ValueError:
        # Can happen on Windows if drives are different, or other edge cases
        raise SecurityError(f"Path '{path}' is on a different drive/location than root '{root_dir}'")

    if common != abs_root:
        logging.warning(f"Security Alert: Path traversal attempt detected. {path} is outside {root_dir}")
        raise SecurityError(f"Access denied: Path '{path}' is outside the allowed root directory.")
        
    return abs_path

def safe_write_file(path: str, content: str, root_dir: str):
    """
    Safely writes content to a file, ensuring it's within the root directory.
    Creates parent directories if needed.
    """
    try:
        # Validate path first
        # If path is relative, join with root. If absolute, validate against root.
        if not os.path.isabs(path):
            full_path = os.path.join(root_dir, path)
        else:
            full_path = path
            
        validated_path = validate_path(full_path, root_dir)
        
        # Create directories
        os.makedirs(os.path.dirname(validated_path), exist_ok=True)
        
        with open(validated_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        logging.info(f"Successfully wrote to {validated_path}")
        
    except SecurityError as e:
        logging.error(f"Blocked write attempt: {e}")
        raise e
    except Exception as e:
        logging.error(f"Failed to write file {path}: {e}")
        raise e
