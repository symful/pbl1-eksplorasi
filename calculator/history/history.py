import json
import os

_history = []
_memory = 0.0
_variables = {}


def add_entry(expression, result):
    _history.append({"expression": str(expression), "result": str(result)})


def get_history():
    return list(_history)


def clear_history():
    _history.clear()


def save_to_file(path):
    data = {"history": _history, "variables": _variables, "memory": _memory}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_from_file(path):
    global _history, _variables, _memory
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        _history = data.get("history", [])
        _variables = data.get("variables", {})
        _memory = data.get("memory", 0.0)
    elif isinstance(data, list):
        _history = data


def memory_add(value):
    global _memory
    _memory += float(value)


def memory_sub(value):
    global _memory
    _memory -= float(value)


def memory_recall():
    return _memory


def memory_clear():
    global _memory
    _memory = 0.0


def set_variable(name, value):
    _variables[name] = float(value)


def get_variable(name):
    return _variables.get(name)


def list_variables():
    return dict(_variables)


def delete_variable(name):
    _variables.pop(name, None)


def clear_variables():
    _variables.clear()
