"""Pint を利用した、GUI に依存しない単位変換・計算エンジン。"""

from __future__ import annotations

import ast
import io
import math
import re
import sys
import token
import tokenize
from pathlib import Path
from typing import Any

import pint
from pint import Quantity, Unit, UnitRegistry
from pint.errors import (
    DimensionalityError,
    OffsetUnitCalculusError,
    UndefinedUnitError,
)


class UnitEngineError(ValueError):
    """画面へ安全に表示できる、単位エンジン由来エラーの基底クラス。"""


class InvalidNumberError(UnitEngineError):
    """入力を単一の有限な数値として解釈できない場合のエラー。"""


class UnknownUnitError(UnitEngineError):
    """入力された単位を Pint が認識できない場合のエラー。"""


class DimensionMismatchError(UnitEngineError):
    """変換または演算の対象となる次元が一致しない場合のエラー。"""


class ExpressionSyntaxError(UnitEngineError):
    """計算式が未対応または不正な構文を含む場合のエラー。"""


_NUMBER_PATTERN = re.compile(
    r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z"
)
_UNSIGNED_NUMBER_PATTERN = re.compile(
    r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z"
)
_SIMPLE_QUANTITY_PATTERN = re.compile(
    r"(?P<number>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)"
    r"\s+"
    r"(?P<unit>[^\W\d]\w*)"
    r"\Z",
    re.UNICODE,
)
_SUPERSCRIPT_PATTERN = re.compile(r"[⁺⁻]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+")
_SUPERSCRIPT_TRANSLATION = str.maketrans(
    {
        "⁺": "+",
        "⁻": "-",
        "⁰": "0",
        "¹": "1",
        "²": "2",
        "³": "3",
        "⁴": "4",
        "⁵": "5",
        "⁶": "6",
        "⁷": "7",
        "⁸": "8",
        "⁹": "9",
    }
)
_IGNORED_TOKEN_TYPES = {
    token.ENDMARKER,
    token.NEWLINE,
    tokenize.NL,
    tokenize.ENCODING,
}
_ALLOWED_OPERATORS = {"+", "-", "*", "/", "**", "(", ")"}


def get_application_directory() -> Path:
    """開発時または PyInstaller ``--onedir`` 実行時の配置先を返す。"""

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def create_unit_registry(
    units_path: str | Path,
) -> tuple[UnitRegistry, str | None]:
    """標準レジストリへ独自定義を追加し、レジストリと警告を返す。

    定義ファイルが存在しない場合は標準レジストリをそのまま返す。
    追加定義の読み込みに失敗した場合は、途中まで反映された定義を
    残さないため、新しい標準レジストリを作り直す。
    """

    path = Path(units_path)
    registry = pint.UnitRegistry()
    if not path.exists():
        return registry, None

    try:
        registry.load_definitions(str(path))
    except Exception as exc:  # 読み込み境界では I/O と Pint の全失敗を回復する。
        warning = (
            "単位定義ファイルを読み込めなかったため、"
            f"標準単位のみで続行します: {exc}"
        )
        return pint.UnitRegistry(), warning

    return registry, None


def normalize_expression(expression: str) -> str:
    """画面入力用の演算記号を Pint が解釈する記号へ置き換える。"""

    return expression.replace("×", "*").replace("÷", "/").replace("^", "**")


def format_number(value: Any) -> str:
    """数値を約 12 桁の有効数字で、不要な末尾ゼロなしに整形する。"""

    try:
        numeric = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise InvalidNumberError("結果を数値として表示できません。") from exc

    if not math.isfinite(numeric):
        raise InvalidNumberError("有限な数値として表示できません。")
    if numeric == 0:
        return "0"
    return format(numeric, ".12g")


def format_quantity(value: Quantity[Any] | int | float) -> str:
    """Quantity または通常の数値を、一般的な単位記号で整形する。"""

    if not isinstance(value, Quantity):
        return format_number(value)

    number_text = format_number(value.magnitude)
    if value.dimensionless and value.units == value._REGISTRY.dimensionless:
        return number_text

    try:
        unit_text = format(value.units, "~P")
    except (TypeError, ValueError):
        unit_text = format(value.units, "~")
    return f"{number_text} {unit_text}"


def _normalize_unit_text(unit_text: str) -> str:
    """一般的な Unicode 単位表記を Pint の移植性の高い表記へ直す。"""

    normalized = unit_text.strip()
    replacements = (
        ("Δ°C", "delta_degC"),
        ("Δ°F", "delta_degF"),
        ("∆°C", "delta_degC"),
        ("∆°F", "delta_degF"),
        ("℃", "degC"),
        ("℉", "degF"),
        ("°C", "degC"),
        ("°F", "degF"),
        ("·", "*"),
        ("⋅", "*"),
    )
    for source, target in replacements:
        normalized = normalized.replace(source, target)

    return _SUPERSCRIPT_PATTERN.sub(
        lambda match: f"**{match.group(0).translate(_SUPERSCRIPT_TRANSLATION)}",
        normalized,
    )


def _parse_number(value: str | int | float) -> int | float:
    """入力をコードとして評価せず、単一の有限な数値へ変換する。"""

    if isinstance(value, bool):
        raise InvalidNumberError("数値として解釈できません。")

    text = str(value).strip()
    if not text or _NUMBER_PATTERN.fullmatch(text) is None:
        raise InvalidNumberError("数値として解釈できません。")

    try:
        if "." not in text and "e" not in text.lower():
            return int(text)
        number = float(text)
    except (OverflowError, ValueError) as exc:
        raise InvalidNumberError("数値として解釈できません。") from exc

    if not math.isfinite(number):
        raise InvalidNumberError("有限な数値を入力してください。")
    return number


def _parse_unit(registry: UnitRegistry, unit_text: str) -> Unit:
    """単位文字列を解析し、利用者向けの例外へ変換する。"""

    text = _normalize_unit_text(str(unit_text))
    if not text:
        raise UnknownUnitError("単位が入力されていません。")

    try:
        return registry.Unit(text)
    except Exception as exc:
        # Pint の単位パーサは入力によって TokenError、AssertionError、
        # ZeroDivisionError なども送出する。編集可能な単位欄からそれらを
        # GUI へ漏らさず、すべて同じ公開エラーへ変換する。
        raise UnknownUnitError(f"単位「{unit_text}」を認識できません。") from exc


def _tokenize_for_validation(expression: str) -> list[tuple[int, str]]:
    """Pint に渡す前の式を、許可したトークンだけへ制限する。"""

    try:
        generated = tokenize.generate_tokens(io.StringIO(expression).readline)
        tokens = [
            (item.type, item.string)
            for item in generated
            if item.type not in _IGNORED_TOKEN_TYPES
        ]
    except (IndentationError, tokenize.TokenError) as exc:
        raise ExpressionSyntaxError("計算式の構文が不正です。") from exc

    if not tokens:
        raise ExpressionSyntaxError("計算式を入力してください。")

    for token_type, text in tokens:
        if token_type == token.NUMBER:
            if _UNSIGNED_NUMBER_PATTERN.fullmatch(text) is None:
                raise ExpressionSyntaxError("計算式の数値表記が不正です。")
        elif token_type == token.NAME:
            continue
        elif token_type == token.OP and text in _ALLOWED_OPERATORS:
            continue
        else:
            raise ExpressionSyntaxError(
                "計算式には四則演算、括弧、整数の累乗だけを使用できます。"
            )

    return tokens


def _python_validation_expression(tokens: list[tuple[int, str]]) -> str:
    """暗黙の単位乗算を補い、Python AST で検査可能な式を作る。"""

    parts: list[str] = []
    previous: tuple[int, str] | None = None

    for current in tokens:
        if previous is not None:
            previous_type, previous_text = previous
            current_type, current_text = current
            left_is_atom = (
                previous_type in {token.NUMBER, token.NAME}
                or previous_text == ")"
            )
            right_is_atom = (
                current_type in {token.NUMBER, token.NAME}
                or current_text == "("
            )
            if left_is_atom and right_is_atom:
                if previous_type == token.NAME and current_text == "(":
                    raise ExpressionSyntaxError(
                        "関数呼び出しは計算式で使用できません。"
                    )
                if (
                    previous_type == token.NUMBER
                    and current_type == token.NUMBER
                ):
                    raise ExpressionSyntaxError("計算式の数値表記が不正です。")
                parts.append("*")

        parts.append(current[1])
        previous = current

    return " ".join(parts)


def _unit_atom_end(tokens: list[tuple[int, str]], start: int) -> int:
    """単位名と、その直後にある累乗表記の終端位置を返す。"""

    end = start + 1
    if end >= len(tokens) or tokens[end] != (token.OP, "**"):
        return end

    cursor = end + 1
    if cursor < len(tokens) and tokens[cursor] in {
        (token.OP, "+"),
        (token.OP, "-"),
    }:
        cursor += 1
    if cursor < len(tokens) and tokens[cursor][0] == token.NUMBER:
        return cursor + 1

    # ``m ** (2)`` のような整数リテラルの括弧も単位側へ含める。
    cursor = end + 1
    if cursor >= len(tokens) or tokens[cursor] != (token.OP, "("):
        return end
    cursor += 1
    if cursor < len(tokens) and tokens[cursor] in {
        (token.OP, "+"),
        (token.OP, "-"),
    }:
        cursor += 1
    if cursor >= len(tokens) or tokens[cursor][0] != token.NUMBER:
        return end
    cursor += 1
    if cursor < len(tokens) and tokens[cursor] == (token.OP, ")"):
        return cursor + 1
    return end


def _group_quantity_literals(
    tokens: list[tuple[int, str]],
) -> list[tuple[int, str]]:
    """暗黙表記の ``数値 単位`` を一つの数量として括弧でまとめる。

    Pint は ``10 J / 2 s`` を ``10 * J / 2 * s`` と左結合で扱う。
    利用者が入力した ``10 J`` と ``2 s`` をそれぞれ Quantity として
    解釈できるよう、評価前に ``(10 * J) / (2 * s)`` へ整える。
    明示された乗算（``2 * m``）の優先順位は変更しない。
    """

    grouped: list[tuple[int, str]] = []
    index = 0
    while index < len(tokens):
        current_type, _ = tokens[index]
        previous_index = index - 1
        if (
            previous_index >= 0
            and tokens[previous_index]
            in {(token.OP, "+"), (token.OP, "-")}
        ):
            previous_index -= 1
        is_power_exponent = (
            previous_index >= 0
            and tokens[previous_index] == (token.OP, "**")
        )
        if (
            current_type != token.NUMBER
            or is_power_exponent
            or index + 1 >= len(tokens)
            or tokens[index + 1][0] != token.NAME
        ):
            grouped.append(tokens[index])
            index += 1
            continue

        unit_end = _unit_atom_end(tokens, index + 1)
        while (
            unit_end + 1 < len(tokens)
            and tokens[unit_end][0] == token.OP
            and tokens[unit_end][1] in {"*", "/"}
            and tokens[unit_end + 1][0] == token.NAME
        ):
            unit_end = _unit_atom_end(tokens, unit_end + 1)

        grouped.append((token.OP, "("))
        grouped.append(tokens[index])
        grouped.append((token.OP, "*"))
        grouped.extend(tokens[index + 1 : unit_end])
        grouped.append((token.OP, ")"))
        index = unit_end

    return grouped


def _is_integer_literal(node: ast.AST) -> bool:
    """AST ノードが符号付き整数リテラルだけで構成されるかを返す。"""

    if isinstance(node, ast.Constant):
        return isinstance(node.value, int) and not isinstance(node.value, bool)
    return (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, (ast.UAdd, ast.USub))
        and isinstance(node.operand, ast.Constant)
        and isinstance(node.operand.value, int)
        and not isinstance(node.operand.value, bool)
    )


def _validate_ast(node: ast.AST) -> None:
    """式の AST が MVP で許可した演算だけを含むことを検査する。"""

    if isinstance(node, ast.Expression):
        _validate_ast(node.body)
        return

    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
            raise ExpressionSyntaxError("対応していない演算子があります。")
        if isinstance(node.op, ast.Pow) and not _is_integer_literal(node.right):
            raise ExpressionSyntaxError("累乗の指数には整数を指定してください。")
        _validate_ast(node.left)
        _validate_ast(node.right)
        return

    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, (ast.UAdd, ast.USub)):
            raise ExpressionSyntaxError("対応していない単項演算子があります。")
        _validate_ast(node.operand)
        return

    if isinstance(node, ast.Name):
        return

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ExpressionSyntaxError("計算式に使用できない値があります。")
        return

    raise ExpressionSyntaxError(
        "計算式には四則演算、括弧、整数の累乗だけを使用できます。"
    )


def _validate_expression(expression: str) -> str:
    """正規化済みの式を安全性と対応構文の両面から検査する。"""

    parse_text = _normalize_unit_text(expression)
    tokens = _tokenize_for_validation(parse_text)
    evaluation_tokens = _group_quantity_literals(tokens)
    validation_text = _python_validation_expression(evaluation_tokens)
    try:
        tree = ast.parse(validation_text, mode="eval")
    except (SyntaxError, ValueError) as exc:
        raise ExpressionSyntaxError("計算式の構文が不正です。") from exc
    _validate_ast(tree)
    return validation_text


def _parse_simple_quantity(
    registry: UnitRegistry,
    expression: str,
) -> Quantity[Any] | None:
    """``数値 単位`` を Quantity として生成し、オフセット単位を守る。

    Pint の式パーサでは空白による乗算として扱われるオフセット単位も、
    数値と単位を分けた Quantity 生成なら曖昧さなく表現できる。
    複合式は ``None`` を返し、通常の安全な式パーサへ委ねる。
    """

    match = _SIMPLE_QUANTITY_PATTERN.fullmatch(expression)
    if match is None:
        return None

    number = _parse_number(match.group("number"))
    unit = _parse_unit(registry, match.group("unit"))
    return registry.Quantity(number, unit)


class UnitEngine:
    """単位変換と、制限された単位付き計算式を提供する。"""

    def __init__(self, units_path: str | Path | None = None) -> None:
        """標準単位と任意の ``units.txt`` からエンジンを初期化する。"""

        self.units_path = (
            Path(units_path)
            if units_path is not None
            else get_application_directory() / "units.txt"
        )
        self.registry, self.warning = create_unit_registry(self.units_path)

    def convert(
        self,
        value: str | int | float,
        from_unit: str,
        to_unit: str,
    ) -> str:
        """数値と単位を分けて Quantity を生成し、指定単位へ変換する。"""

        number = _parse_number(value)
        source_unit = _parse_unit(self.registry, from_unit)
        target_unit = _parse_unit(self.registry, to_unit)

        try:
            quantity = self.registry.Quantity(number, source_unit)
            converted = quantity.to(target_unit)
        except DimensionalityError as exc:
            raise DimensionMismatchError(
                "変換元と変換先の次元が一致しません。"
            ) from exc
        except OffsetUnitCalculusError as exc:
            raise DimensionMismatchError(
                "オフセット単位を含むため、この変換は実行できません。"
            ) from exc
        return format_quantity(converted)

    def calculate(self, expression: str, output_unit: str = "") -> str:
        """安全に検査した単位付き式を計算し、必要なら単位変換する。"""

        normalized = normalize_expression(str(expression)).strip()
        if not normalized:
            raise ExpressionSyntaxError("計算式を入力してください。")
        simple_quantity_text = _normalize_unit_text(normalized)

        try:
            result = _parse_simple_quantity(self.registry, simple_quantity_text)
            if result is None:
                evaluation_text = _validate_expression(normalized)
                result = self.registry.parse_expression(evaluation_text)
        except UnitEngineError:
            raise
        except UndefinedUnitError as exc:
            unit_name = exc.unit_names[0] if exc.unit_names else ""
            detail = f"「{unit_name}」" if unit_name else ""
            raise UnknownUnitError(f"単位{detail}を認識できません。") from exc
        except DimensionalityError as exc:
            raise DimensionMismatchError(
                "計算式に次元の異なる量が含まれています。"
            ) from exc
        except OffsetUnitCalculusError as exc:
            raise DimensionMismatchError(
                "オフセット単位に対して実行できない計算です。"
            ) from exc
        except (SyntaxError, TypeError, ValueError, ZeroDivisionError) as exc:
            raise ExpressionSyntaxError(
                "計算式の構文が不正か、計算できない内容です。"
            ) from exc

        target_text = str(output_unit).strip()
        if target_text:
            target_unit = _parse_unit(self.registry, target_text)
            try:
                if isinstance(result, Quantity):
                    result = result.to(target_unit)
                else:
                    result = self.registry.Quantity(result).to(target_unit)
            except DimensionalityError as exc:
                raise DimensionMismatchError(
                    "計算結果と出力単位の次元が一致しません。"
                ) from exc
            except OffsetUnitCalculusError as exc:
                raise DimensionMismatchError(
                    "オフセット単位を含むため、この変換は実行できません。"
                ) from exc

        return format_quantity(result)
