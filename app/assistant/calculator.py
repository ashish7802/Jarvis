"""Bounded, local arithmetic for spoken questions. Never executes Python code."""
import ast
from decimal import Decimal, DecimalException, localcontext
import re

_NUMBERS = dict(zip(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split(),
    range(21),
))


def _evaluate(expression):
    tree = ast.parse(expression, mode="eval")
    if len(list(ast.walk(tree))) > 40:
        raise ValueError("too many operations")

    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = Decimal(ast.get_source_segment(expression, node))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        elif isinstance(node, ast.BinOp):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add):
                value = left + right
            elif isinstance(node.op, ast.Sub):
                value = left - right
            elif isinstance(node.op, ast.Mult):
                value = left * right
            elif isinstance(node.op, ast.Div):
                if right == 0:
                    raise ZeroDivisionError
                value = left / right
            elif isinstance(node.op, ast.Pow) and right == int(right) and abs(right) <= 12:
                if left == 0 and right <= 0:
                    raise ZeroDivisionError
                value = left ** int(right)
            else:
                raise ValueError("unsupported operation")
        else:
            raise ValueError("unsupported expression")
        if not value.is_finite() or abs(value) > Decimal("1e18"):
            raise ValueError("number too large")
        return value

    with localcontext() as ctx:
        ctx.prec = 40
        return visit(tree)


def calculation_reply(text):
    expression = text.casefold().strip().rstrip("?!.")
    expression = re.sub(r"^(?:please )?(?:calculate|what is|what's|work out)\s+", "", expression)
    for word, number in _NUMBERS.items():
        expression = re.sub(rf"\b{word}\b", str(number), expression)
    # English thousands separators, without accepting ambiguous decimal commas.
    expression = re.sub(r"(?<=\d),(?=\d{3}(?:\D|$))", "", expression)
    percent = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*(?:percent|per cent|%)\s+of\s+(-?\d+(?:\.\d+)?)", expression)
    if percent:
        expression = f"({percent[1]} / 100) * {percent[2]}"
    else:
        for phrase, symbol in (("to the power of", "**"), ("multiplied by", "*"),
                               ("divided by", "/"), ("times", "*"), ("plus", "+"),
                               ("minus", "-"), ("over", "/")):
            expression = re.sub(rf"\b{phrase}\b", symbol, expression)
        expression = expression.replace("×", "*").replace("÷", "/").replace("^", "**")
    if not re.fullmatch(r"[\d\s.+*/()\-]+", expression) or not re.search(r"[+*/\-]", expression):
        return None
    if len(expression) > 160:
        return "That calculation is too long. Please split it into smaller steps."
    try:
        value = _evaluate(expression)
        rounded = value.quantize(Decimal("0.000001"))
        result = format(rounded, "f").rstrip("0").rstrip(".") if "." in format(rounded, "f") else str(rounded)
        if rounded == 0:
            result = "0"
        qualifier = "approximately " if rounded != value else ""
        return f"The result is {qualifier}{result}."
    except ZeroDivisionError:
        return "That calculation is undefined; you can't divide by zero."
    except (SyntaxError, ValueError, DecimalException):
        return None  # A natural-language or advanced question belongs to Gemini.
