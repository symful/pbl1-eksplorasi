_history = []
_memory = 0.0

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
