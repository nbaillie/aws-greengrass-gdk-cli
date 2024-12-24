import pytest
from gdk.common.diff_utils import deep_diff

def test_simple_dict_comparison():
    old = {"a": 1, "b": 2}
    new = {"b": 3, "c": 4}
    result = deep_diff(old, new)
    
    assert result["dictionary_item_added"] == ["root['c']"]
    assert result["dictionary_item_removed"] == ["root['a']"]
    assert result["values_changed"]["root['b']"] == {"old_value": 2, "new_value": 3}

def test_nested_dict_comparison():
    old = {"a": {"x": 1, "y": 2}, "b": 3}
    new = {"a": {"x": 1, "y": 5}, "b": 3}
    result = deep_diff(old, new)
    
    assert not result["dictionary_item_added"]
    assert not result["dictionary_item_removed"]
    assert result["values_changed"]["root['a']['y']"] == {"old_value": 2, "new_value": 5}

def test_list_comparison():
    old = [1, 2, 3]
    new = [1, 4, 3, 5]
    result = deep_diff(old, new)
    
    assert result["dictionary_item_added"] == ["root['3']"]
    assert result["values_changed"]["root['1']"] == {"old_value": 2, "new_value": 4}

def test_list_of_dicts_comparison():
    old = [{"name": "John", "age": 30}, {"name": "Jane", "data": {"x": 1}}]
    new = [{"name": "John", "age": 31}, {"name": "Jane", "data": {"x": 2}}]
    result = deep_diff(old, new)
    
    assert not result["dictionary_item_added"]
    assert not result["dictionary_item_removed"]
    assert result["values_changed"]["root['0']['age']"] == {"old_value": 30, "new_value": 31}
    assert result["values_changed"]["root['1']['data']['x']"] == {"old_value": 1, "new_value": 2}

def test_empty_diff():
    old = {"a": 1, "b": [1, 2, {"x": 3}]}
    new = {"a": 1, "b": [1, 2, {"x": 3}]}
    result = deep_diff(old, new)
    
    assert not result["dictionary_item_added"]
    assert not result["dictionary_item_removed"]
    assert not result["values_changed"]

def test_completely_different_structures():
    old = {"a": [1, 2, 3]}
    new = {"b": {"x": 1}}
    result = deep_diff(old, new)
    
    assert result["dictionary_item_added"] == ["root['b']"]
    assert result["dictionary_item_removed"] == ["root['a']"]

def test_exclude_paths():
    old = {"a": {"x": 1, "y": 2}, "b": {"z": 3}}
    new = {"a": {"x": 2, "y": 2}, "b": {"z": 4}}
    result = deep_diff(old, new, exclude_paths=["root['a']['x']"])
    
    assert not result["dictionary_item_added"]
    assert not result["dictionary_item_removed"]
    assert list(result["values_changed"].keys()) == ["root['b']['z']"]

def test_exclude_regex_paths():
    old = {"a": [{"x": 1}, {"x": 2}], "b": {"z": 3}}
    new = {"a": [{"x": 2}, {"x": 3}], "b": {"z": 4}}
    result = deep_diff(old, new, exclude_regex_paths=[r"^root\['a'\]\[.+\]\['x'\]"])
    
    assert not result["dictionary_item_added"]
    assert not result["dictionary_item_removed"]
    assert list(result["values_changed"].keys()) == ["root['b']['z']"]

def test_recipe_like_structure_all_excluded():
    old = {
        "ComponentVersion": "1.0.0",
        "Manifests": [
            {"Artifacts": [{"URI": "s3://bucket/v1/file.zip", "Digest": "abc"}]},
            {"Artifacts": [{"URI": "s3://bucket/v1/other.zip"}]}
        ]
    }
    new = {
        "ComponentVersion": "1.0.1", 
        "Manifests": [
            {"Artifacts": [{"URI": "s3://bucket/v2/file.zip", "Digest": "def"}]},
            {"Artifacts": [{"URI": "s3://bucket/v2/other.zip"}]}
        ]
    }
    result = deep_diff(
        old, new,
        exclude_paths=["root['ComponentVersion']"],
        exclude_regex_paths=[
            r"^root\['Manifests'\]\[.+\]\['Artifacts'\]"
        ]
    )
    
    assert not result["dictionary_item_added"]
    assert not result["dictionary_item_removed"]
    assert not result["values_changed"]

def test_recipe_like_structure():
    old = {
        "ComponentVersion": "1.0.0",
        "Manifests": [
            {"Artifacts": [{"URI": "s3://bucket/v1/file.zip", "Digest": "abc"}]},
            {"Artifacts": [{"URI": "s3://bucket/v1/other.zip"}]}
        ]
    }
    new = {
        "ComponentVersion": "1.0.1", 
        "Manifests": [
            {"Artifacts": [{"URI": "s3://bucket/v1/file.zip", "Digest": "def"}]},
            {"Artifacts": [{"URI": "s3://bucket/v2/other.zip"}]}
        ]
    }
    result = deep_diff(
        old, new,
    )
    
    assert not result["dictionary_item_added"]
    assert not result["dictionary_item_removed"]
    assert result["values_changed"]["root['ComponentVersion']"] == {"old_value": '1.0.0', "new_value": '1.0.1'}
    assert result["values_changed"]["root['Manifests']['0']['Artifacts']['0']['Digest']"] == {"old_value": 'abc', "new_value": 'def'}
    assert result["values_changed"]["root['Manifests']['1']['Artifacts']['0']['URI']"] == {"old_value": 's3://bucket/v1/other.zip', "new_value": 's3://bucket/v2/other.zip'}

def test_recipe_like_structure_artifacts_no_change():
    old = {
        'RecipeFormatVersion': '2020-01-25', 
        'ComponentName': 'com.example.PythonHelloWorld', 
        'ComponentVersion': '1.0.25', 
        'ComponentType': 'aws.greengrass.generic', 
        'ComponentDescription': 'This is simple Hello World component written in Python', 
        'ComponentPublisher': 'Neil Baillie', 
        'ComponentConfiguration': {
            'DefaultConfiguration': {'Message': 'World'}}, 
            'Manifests': [
                {
                    'Platform': {'os': 'all'}, 'Lifecycle': {'Run': 'python3 -u {artifacts:decompressedPath}/com.example.PythonHelloWorld/main.py {configuration:/Message}'}, 
                    'Artifacts': [{'Uri': 's3://ggv2artifacts-eu-west-2-546603155266/com.example.PythonHelloWorld/1.0.25/com.example.PythonHelloWorld.zip', 
                        'Digest': 'qZCu758rlWI0CYDmPy77dYDTpeBJgOnFAVv+BUumHPA=', 
                        'Algorithm': 'SHA-256', 
                        'Unarchive': 'ZIP', 
                        'Permission': {
                            'Read': 'OWNER', 
                            'Execute': 'NONE'
                        }
                    }]
                }
            ], 
        'Lifecycle': {}
    }
    new = {
        'RecipeFormatVersion': '2020-01-25', 
        'ComponentName': 'com.example.PythonHelloWorld', 
        'ComponentVersion': '1.0.25', 
        'ComponentType': 'aws.greengrass.generic', 
        'ComponentDescription': 'This is simple Hello World component written in Python', 
        'ComponentPublisher': 'Neil Baillie', 
        'ComponentConfiguration': {
            'DefaultConfiguration': {'Message': 'World'}}, 
            'Manifests': [
                {
                    'Platform': {'os': 'all'}, 'Lifecycle': {'Run': 'python3 -u {artifacts:decompressedPath}/com.example.PythonHelloWorld/main.py {configuration:/Message}'}, 
                    'Artifacts': [{'Uri': 's3://ggv2artifacts-eu-west-2-546603155266/com.example.PythonHelloWorld/1.0.25/com.example.PythonHelloWorld.zip', 
                        'Digest': 'qZCu758rlWI0CYDmPy77dYDTpeBJgOnFAVv+BUumHPA=', 
                        'Algorithm': 'SHA-256', 
                        'Unarchive': 'ZIP', 
                        'Permission': {
                            'Read': 'OWNER', 
                            'Execute': 'NONE'
                        }
                    }]
                }
            ], 
        'Lifecycle': {}
    }
    result = deep_diff(
        old, new,
    )

    assert not result["dictionary_item_added"]
    assert not result["dictionary_item_removed"]
    assert not result["values_changed"]

def test_recipe_like_structure_artifacts_with_change():
    old = {
        'RecipeFormatVersion': '2020-01-25', 
        'ComponentName': 'com.example.PythonHelloWorld', 
        'ComponentVersion': '1.0.25', 
        'ComponentType': 'aws.greengrass.generic', 
        'ComponentDescription': 'This is simple Hello World component written in Python', 
        'ComponentPublisher': 'Neil Baillie', 
        'ComponentConfiguration': {
            'DefaultConfiguration': {'Message': 'World'}
        }, 
        'Manifests': [
            {
                'Platform': {'os': 'all'}, 
                'Lifecycle': {
                    'Run': 'python3 -u {artifacts:decompressedPath}/com.example.PythonHelloWorld/main.py {configuration:/Message}'
                }, 
                'Artifacts': [
                    {
                        'Uri': 's3://ggv2artifacts-eu-west-2-546603155266/com.example.PythonHelloWorld/1.0.25/com.example.PythonHelloWorld.zip', 
                        'Digest': 'qZCu758rlWI0CYDmPy77dYDTpeBJgOnFAVv+BUumHPA=', 
                        'Algorithm': 'SHA-256', 
                        'Unarchive': 'ZIP', 
                        'Permission': {
                            'Read': 'OWNER', 
                            'Execute': 'NONE'
                        }
                    }
                ]
            }
        ], 
        'Lifecycle': {}
    }

    new = {
        'RecipeFormatVersion': '2020-01-25', 
        'ComponentName': 'com.example.PythonHelloWorld', 
        'ComponentVersion': '1.0.25', 
        'ComponentDescription': 'This is simple Hello World component written in Python', 
        'ComponentPublisher': 'Neil Baillie', 
        'ComponentConfiguration': {
            'DefaultConfiguration': {'Message': 'World'}
        }, 
        'Manifests': [
            {
                'Platform': {'os': 'all'}, 
                'Lifecycle': {
                    'Run': 'python3 -u {artifacts:decompressedPath}/com.example.PythonHelloWorld/main.py {configuration:/Message}'
                }, 
                'Artifacts': [
                    {
                        'Uri': 's3://ggv2artifacts-eu-west-2-546603155266/com.example.PythonHelloWorld/1.0.25/com.example.PythonHelloWorld.zip', 
                        'Unarchive': 'ZIP', 
                    }
                ]
            }
        ]
    }

    result = deep_diff(
        old, 
        new,
        exclude_paths=[
            "root['Lifecycle']",
            "root['ComponentVersion']",
            "root['ComponentType']"
        ],
        exclude_regex_paths=[
            "^root\['Manifests'\]\[.+\]\['Artifacts'\]\[.+\]",  # noqa: W605
            "^root\['Manifests'\]\[.+\]\['Artifacts'\]"         # noqa: W605
        ]
    )

    assert not result["dictionary_item_added"]
    assert not result["values_changed"]
    assert not result["dictionary_item_removed"]
    assert len(result["excluded_dictionary_item_removed"]) == 5