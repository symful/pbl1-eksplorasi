import math


def add(a, b):
    return a + b


def subtract(a, b):
    return a - b


def multiply(a, b):
    return a * b


def divide(a, b):
    if b == 0:
        raise ValueError("Division by zero")
    return a / b


def power(base, exp):
    return math.pow(base, exp)


def sqrt(x):
    if x < 0:
        raise ValueError("Square root of negative number")
    return math.sqrt(x)


def factorial(n):
    if not float(n).is_integer() or n < 0:
        raise ValueError("Factorial requires a non-negative integer")
    return math.factorial(int(n))


def exp(x):
    return math.exp(x)


def log(x, base=10):
    if x <= 0:
        raise ValueError("Logarithm of non-positive number")
    return math.log(x, base)


def ln(x):
    if x <= 0:
        raise ValueError("Logarithm of non-positive number")
    return math.log(x)


def sin(x, angle_mode="deg"):
    rad = math.radians(x) if angle_mode == "deg" else x
    return math.sin(rad)


def cos(x, angle_mode="deg"):
    rad = math.radians(x) if angle_mode == "deg" else x
    return math.cos(rad)


def tan(x, angle_mode="deg"):
    rad = math.radians(x) if angle_mode == "deg" else x
    return math.tan(rad)


def asin(x, angle_mode="deg"):
    if not -1 <= x <= 1:
        raise ValueError("asin domain error")
    result = math.asin(x)
    return math.degrees(result) if angle_mode == "deg" else result


def acos(x, angle_mode="deg"):
    if not -1 <= x <= 1:
        raise ValueError("acos domain error")
    result = math.acos(x)
    return math.degrees(result) if angle_mode == "deg" else result


def atan(x, angle_mode="deg"):
    result = math.atan(x)
    return math.degrees(result) if angle_mode == "deg" else result


def _build_allowed(angle_mode, variables=None):
    ns = {
        "sin": lambda v: sin(v, angle_mode),
        "cos": lambda v: cos(v, angle_mode),
        "tan": lambda v: tan(v, angle_mode),
        "asin": lambda v: asin(v, angle_mode),
        "acos": lambda v: acos(v, angle_mode),
        "atan": lambda v: atan(v, angle_mode),
        "sqrt": sqrt,
        "log": log,
        "ln": ln,
        "exp": exp,
        "factorial": factorial,
        "pi": math.pi,
        "e": math.e,
        "abs": abs,
        "pow": power,
    }
    if variables:
        ns.update(variables)
    return ns


def evaluate(expr, angle_mode="deg", variables=None):
    ns = _build_allowed(angle_mode, variables)
    try:
        result = eval(expr, {"__builtins__": {}}, ns)
        return float(result)
    except ZeroDivisionError:
        raise ValueError("Division by zero")
    except Exception:
        raise ValueError("Invalid expression")


def evaluate_at(expr, x_val, angle_mode="deg", variables=None):
    ns = _build_allowed(angle_mode, variables)
    ns["x"] = float(x_val)
    try:
        result = eval(expr, {"__builtins__": {}}, ns)
        return float(result)
    except ZeroDivisionError:
        raise ValueError("Division by zero")
    except Exception:
        raise ValueError("Invalid expression")


def derivative(expr, x_val, angle_mode="deg", variables=None, h=1e-7):
    f_plus = evaluate_at(expr, x_val + h, angle_mode, variables)
    f_minus = evaluate_at(expr, x_val - h, angle_mode, variables)
    return (f_plus - f_minus) / (2 * h)


def definite_integral(expr, a, b, angle_mode="deg", variables=None):
    from scipy import integrate

    def f(xv):
        return evaluate_at(expr, xv, angle_mode, variables)

    result, _ = integrate.quad(f, a, b)
    return result
