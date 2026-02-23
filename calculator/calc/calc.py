import math

def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b

def divide(a, b):
    if b == 0:
        raise ValueError("Tidak bisa membagi dengan nol")
    return a / b

def power(a, b):
    return a ** b

def modulus(a, b):
    if b == 0:
        raise ValueError("Tidak bisa modulus dengan nol")
    return a % b

def square_root(a):
    if a < 0:
        raise ValueError("Tidak bisa menghitung akar dari bilangan negatif")
    return math.sqrt(a)

def factorial(a):
    if a < 0:
        raise ValueError("Faktorial tidak terdefinisi untuk bilangan negatif")
    if not float(a).is_integer():
        raise ValueError("Faktorial hanya untuk bilangan bulat")
    return math.factorial(int(a))

def logarithm(a, base=10):
    if a <= 0:
        raise ValueError("Logaritma hanya untuk bilangan positif")
    if base <= 0 or base == 1:
        raise ValueError("Basis logaritma harus > 0 dan tidak boleh 1")
    return math.log(a, base)

def sine(a):
    return math.sin(a)

def cosine(a):
    return math.cos(a)

def tangent(a):
    return math.tan(a)
