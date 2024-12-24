from typing import Any, Dict, List, Union
import re

def deep_diff(old: Union[Dict, List], new: Union[Dict, List], exclude_paths: List[str] = None, exclude_regex_paths: List[str] = None) -> Dict[str, Any]:
    """Compare two objects (dicts or lists) recursively and return their differences.
    
    Args:
        old: Original object (dict or list)
        new: New object to compare against (dict or list)
        
    Returns:
        Dict containing differences in DeepDiff format with keys:
        - dictionary_item_added
        - excluded_dictionary_item_added
        - dictionary_item_removed
        - excluded_dictionary_item_removed
        - values_changed
        - excluded_values_changed
    """
    result = {
        "dictionary_item_added": [],
        "excluded_dictionary_item_added": [],
        "dictionary_item_removed": [],
        "excluded_dictionary_item_removed": [],
        "values_changed": {},
        "excluded_values_changed": {}
    }

    if isinstance(old, dict) and isinstance(new, dict):
        _compare_dicts(old, new, "root", result, exclude_paths, exclude_regex_paths)
    elif isinstance(old, list) and isinstance(new, list):
        _compare_lists(old, new, "root", result, exclude_paths, exclude_regex_paths)
    else:
        if old != new and not _should_exclude("root", exclude_paths, exclude_regex_paths):
            result["values_changed"]["root"] = {"old_value": old, "new_value": new}
        elif old != new and _should_exclude("root", exclude_paths, exclude_regex_paths):
            result["excluded_values_changed"]["root"] = {"old_value": old, "new_value": new}
    
    return result

def _should_exclude(path: str, exclude_paths: List[str] = None, exclude_regex_paths: List[str] = None) -> bool:
    """Check if the current path should be excluded from comparison."""
    if exclude_paths and path in exclude_paths:
        return True
    if exclude_regex_paths:
        for pattern in exclude_regex_paths:
            return any(re.match(pattern, path) for pattern in exclude_regex_paths)
    return False

def _compare_dicts(old: Dict, new: Dict, path: str, result: Dict, exclude_paths: List[str] = None, exclude_regex_paths: List[str] = None) -> None:
    """Compare two dictionaries recursively and track differences."""
    old_keys = set(old.keys())
    new_keys = set(new.keys())
    
    # Find added and removed items
    for key in new_keys - old_keys:
        if not _should_exclude(f"{path}['{key}']", exclude_paths, exclude_regex_paths):
            result["dictionary_item_added"].append(f"{path}['{key}']" if path else f"['{key}']")
        else:
            result["excluded_dictionary_item_added"].append(f"{path}['{key}']" if path else f"['{key}']")
    for key in old_keys - new_keys:
        if not _should_exclude(f"{path}['{key}']", exclude_paths, exclude_regex_paths):
            result["dictionary_item_removed"].append(f"{path}['{key}']" if path else f"['{key}']")
        else:
            result["excluded_dictionary_item_removed"].append(f"{path}['{key}']" if path else f"['{key}']")
        
    # Compare common keys (values_changed)
    for key in old_keys & new_keys:
        current_path = f"{path}['{key}']" if path else f"['{key}']"
        if isinstance(old[key], dict) and isinstance(new[key], dict):
            _compare_dicts(old[key], new[key], current_path, result, exclude_paths, exclude_regex_paths)
        elif isinstance(old[key], list) and isinstance(new[key], list):
            _compare_lists(old[key], new[key], current_path, result, exclude_paths, exclude_regex_paths)
        elif old[key] != new[key] and not _should_exclude(f"{path}['{key}']", exclude_paths, exclude_regex_paths):
            result["values_changed"][current_path] = {
                "old_value": old[key],
                "new_value": new[key]
            }
        elif old[key] != new[key] and _should_exclude(f"{path}['{key}']", exclude_paths, exclude_regex_paths):
            result["excluded_values_changed"][current_path] = {
                "old_value": old[key],
                "new_value": new[key]
            }

def _compare_lists(old: List, new: List, path: str, result: Dict, exclude_paths: List[str] = None, exclude_regex_paths: List[str] = None) -> None:
    """Compare two lists recursively and track differences."""
    # For simplicity, treat lists like dictionaries with numeric keys
    old_dict = {str(i): val for i, val in enumerate(old)}
    new_dict = {str(i): val for i, val in enumerate(new)}
    _compare_dicts(old_dict, new_dict, path, result, exclude_paths, exclude_regex_paths)