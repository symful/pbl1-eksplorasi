import json
import os

_history = []
_memory = 0.0
_variables = {}

def add_entry(expression, result):
    """Menambahkan entri baru ke riwayat perhitungan."""
    _history.append({"expression": str(expression), "result": str(result)})

def get_history():
    """Mengambil seluruh riwayat perhitungan."""
    return list(_history)

def clear_history():
    """Menghapus semua data dalam riwayat perhitungan."""
    _history.clear()

def memory_add(value):
    """Menambahkan nilai ke memori kalkulator (M+)."""
    global _memory
    _memory += float(value)

def memory_sub(value):
    """Mengurangi nilai dari memori kalkulator (M-)."""
    global _memory
    _memory -= float(value)

def memory_recall():
    """Mengambil nilai yang tersimpan di memori (MR)."""
    return _memory

def memory_clear():
    """Menghapus/mereset nilai memori menjadi 0.0 (MC)."""
    global _memory
    _memory = 0.0

def set_variable(name, value):
    """Menyimpan nilai ke dalam variabel dengan nama tertentu."""
    _variables[name] = float(value)

def get_variable(name):
    """Mengambil nilai variabel berdasarkan namanya."""
    return _variables.get(name)

def list_variables():
    """Mengambil salinan seluruh variabel yang tersimpan."""
    return dict(_variables)

def delete_variable(name):
    """Menghapus variabel tertentu berdasarkan namanya."""
    _variables.pop(name, None)

def clear_variables():
    """Menghapus seluruh variabel yang tersimpan."""
    _variables.clear()

def save_to_file(path):
    """Menyimpan riwayat, variabel, dan nilai memori ke file JSON."""
    data = {"history": _history, "variables": _variables, "memory": _memory}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
def load_from_file(path):
    """Memuat data riwayat, variabel, dan memori dari file JSON."""
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