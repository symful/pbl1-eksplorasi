_history = []

def add_entry(expression, result):
    """Menambahkan entri baru ke riwayat perhitungan."""
    _history.append({"expression": str(expression), "result": str(result)})

def get_history():
    """Mengambil seluruh riwayat perhitungan."""
    return list(_history)

def clear_history():
    """Menghapus semua data dalam riwayat perhitungan."""
    _history.clear()
