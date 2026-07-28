"""GUIを起動せずに単位計算エンジンの公開動作を検証する。"""

from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path

import pytest

import unit_engine
from unit_engine import (
    DimensionMismatchError,
    ExpressionSyntaxError,
    InvalidNumberError,
    UnitEngine,
    UnitEngineError,
    UnknownUnitError,
    format_number,
    get_application_directory,
    normalize_expression,
)


@pytest.fixture
def engine(tmp_path: Path) -> UnitEngine:
    """独自定義ファイルが存在しない標準レジストリを返す。"""

    return UnitEngine(units_path=tmp_path / "missing-units.txt")


def test_public_errors_share_a_common_base_class() -> None:
    """画面側がエンジン由来のエラーをまとめて捕捉できる。"""

    error_types = (
        InvalidNumberError,
        UnknownUnitError,
        DimensionMismatchError,
        ExpressionSyntaxError,
    )
    assert all(issubclass(error_type, UnitEngineError) for error_type in error_types)


def test_convert_kilometres_to_metres(engine: UnitEngine) -> None:
    assert engine.convert("10", "km", "m") == "10000 m"


def test_convert_offset_temperature_from_celsius_to_fahrenheit(
    engine: UnitEngine,
) -> None:
    assert engine.convert("0", "°C", "°F") == "32 °F"


@pytest.mark.parametrize("value", ["", "not-a-number", "1 + 2"])
def test_convert_rejects_invalid_number_text(
    engine: UnitEngine,
    value: str,
) -> None:
    with pytest.raises(InvalidNumberError, match="数値"):
        engine.convert(value, "m", "cm")


def test_convert_rejects_unknown_unit(engine: UnitEngine) -> None:
    with pytest.raises(UnknownUnitError, match="単位"):
        engine.convert("1", "unit_that_does_not_exist", "m")


@pytest.mark.parametrize("unit_text", ["(", "m +", "1/0"])
def test_convert_wraps_invalid_unit_syntax(
    engine: UnitEngine,
    unit_text: str,
) -> None:
    with pytest.raises(UnknownUnitError, match="単位"):
        engine.convert("1", unit_text, "m")


def test_convert_rejects_different_dimensions(engine: UnitEngine) -> None:
    with pytest.raises(DimensionMismatchError, match="次元"):
        engine.convert("1", "m", "s")


@pytest.mark.parametrize(
    ("output_unit", "expected"),
    [
        ("m", "408 m"),
        ("km", "0.408 km"),
    ],
)
def test_calculate_quantity_with_requested_output_unit(
    engine: UnitEngine,
    output_unit: str,
    expected: str,
) -> None:
    assert engine.calculate("51 m/s * 8 s", output_unit) == expected


def test_calculate_groups_implicit_number_unit_quantities(
    engine: UnitEngine,
) -> None:
    assert engine.calculate("10 J / 2 s", "W") == "5 W"
    assert engine.calculate("2 m / 1 m") == "2"


def test_calculate_rejects_addition_of_different_dimensions(
    engine: UnitEngine,
) -> None:
    with pytest.raises(DimensionMismatchError, match="次元"):
        engine.calculate("10 m + 5 s")


def test_calculate_rejects_incompatible_output_unit(engine: UnitEngine) -> None:
    with pytest.raises(DimensionMismatchError, match="次元"):
        engine.calculate("51 m/s * 8 s", "s")


def test_calculate_distinguishes_an_unknown_simple_unit(
    engine: UnitEngine,
) -> None:
    with pytest.raises(UnknownUnitError, match="単位"):
        engine.calculate("1 unit_that_does_not_exist")


def test_calculate_plain_arithmetic_without_output_unit(
    engine: UnitEngine,
) -> None:
    assert engine.calculate("2 + 3 * 4", "") == "14"


def test_calculate_supports_parentheses_and_integer_power(
    engine: UnitEngine,
) -> None:
    assert engine.calculate("2 ^ 3 + (4 - 1) * 2") == "14"


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("2 ^ 3 m", "8 m"),
        ("2 ^ -3 m", "0.125 m"),
    ],
)
def test_calculate_keeps_units_outside_the_power_exponent(
    engine: UnitEngine,
    expression: str,
    expected: str,
) -> None:
    assert engine.calculate(expression, "m") == expected


@pytest.mark.parametrize(
    ("expression", "output_unit", "expected"),
    [
        ("3 m × 4", "m", "12 m"),
        ("12 m ÷ 3", "m", "4 m"),
    ],
)
def test_calculate_accepts_input_helper_symbols(
    engine: UnitEngine,
    expression: str,
    output_unit: str,
    expected: str,
) -> None:
    assert engine.calculate(expression, output_unit) == expected


def test_normalize_expression_replaces_only_input_helper_symbols() -> None:
    assert normalize_expression("2 × 3 ÷ 4 ^ 2") == "2 * 3 / 4 ** 2"
    assert normalize_expression("2 ** 3") == "2 ** 3"


@pytest.mark.parametrize(
    "expression",
    [
        "",
        "2 +",
        "(2 + 3",
        "x = 2",
        "sum([1, 2])",
    ],
)
def test_calculate_reports_invalid_or_unsupported_syntax(
    engine: UnitEngine,
    expression: str,
) -> None:
    with pytest.raises(ExpressionSyntaxError, match="式|構文"):
        engine.calculate(expression)


def test_calculate_rejects_non_integer_power(engine: UnitEngine) -> None:
    """MVPで対応する累乗を整数に限定する。"""

    with pytest.raises(ExpressionSyntaxError, match="式|構文|整数"):
        engine.calculate("9 ^ 0.5")


def test_calculate_rejects_non_finite_result(engine: UnitEngine) -> None:
    with pytest.raises(InvalidNumberError, match="有限"):
        engine.calculate("1e308 * 1e308")


def test_calculate_does_not_execute_python_code(
    engine: UnitEngine,
    tmp_path: Path,
) -> None:
    sentinel = tmp_path / "must-not-be-created.txt"
    expression = (
        f"__import__('pathlib').Path('{sentinel.as_posix()}')"
        ".write_text('executed')"
    )

    with pytest.raises(ExpressionSyntaxError):
        engine.calculate(expression)

    assert not sentinel.exists()


def test_engine_source_does_not_call_eval_or_exec() -> None:
    """任意のPythonコード実行につながる組み込み関数を直接使わない。"""

    tree = ast.parse(inspect.getsource(unit_engine))
    forbidden_calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"eval", "exec"}
    }
    assert forbidden_calls == set()


def test_custom_units_work_in_conversion_and_calculation(tmp_path: Path) -> None:
    definitions = tmp_path / "units.txt"
    definitions.write_text(
        "custom_count = 0.25 * millimeter = cnt\n",
        encoding="utf-8",
    )

    custom_engine = UnitEngine(units_path=definitions)

    assert not custom_engine.warning
    assert custom_engine.convert("4", "custom_count", "mm") == "1 mm"
    assert custom_engine.calculate("4 cnt", "mm") == "1 mm"
    # 追加定義を読んでもPintの標準定義は維持される。
    assert custom_engine.convert("1", "km", "m") == "1000 m"


def test_missing_definitions_file_uses_standard_units(tmp_path: Path) -> None:
    definitions = tmp_path / "does-not-exist" / "units.txt"

    missing_file_engine = UnitEngine(units_path=definitions)

    assert Path(missing_file_engine.units_path).resolve() == definitions.resolve()
    assert not missing_file_engine.warning
    assert missing_file_engine.convert("1", "km", "m") == "1000 m"


def test_empty_definitions_file_uses_standard_units(tmp_path: Path) -> None:
    definitions = tmp_path / "units.txt"
    definitions.write_text(" \n\t\n", encoding="utf-8")

    empty_file_engine = UnitEngine(units_path=definitions)

    assert not empty_file_engine.warning
    assert empty_file_engine.convert("1", "m", "cm") == "100 cm"


def test_invalid_definitions_warns_and_recreates_standard_registry(
    tmp_path: Path,
) -> None:
    definitions = tmp_path / "units.txt"
    definitions.write_text(
        "should_not_survive = 2 * meter\n"
        "broken_unit = 1 *\n",
        encoding="utf-8",
    )

    fallback_engine = UnitEngine(units_path=definitions)

    assert fallback_engine.warning
    assert "単位" in fallback_engine.warning
    assert fallback_engine.convert("1", "km", "m") == "1000 m"
    with pytest.raises(UnknownUnitError):
        fallback_engine.convert("1", "should_not_survive", "m")


def test_registry_attribute_exposes_the_active_standard_registry(
    engine: UnitEngine,
) -> None:
    converted = engine.registry.Quantity(1, "m").to("cm")
    assert converted.magnitude == pytest.approx(100)


def test_default_units_path_is_based_on_application_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(unit_engine, "get_application_directory", lambda: tmp_path)

    default_engine = UnitEngine()

    assert Path(default_engine.units_path).resolve() == (
        tmp_path / "units.txt"
    ).resolve()


def test_application_directory_during_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)

    assert get_application_directory() == Path(unit_engine.__file__).resolve().parent


def test_application_directory_for_pyinstaller_onedir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    executable = tmp_path / "UnitCalculator.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(executable))

    assert get_application_directory() == tmp_path.resolve()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.0, "0"),
        (-0.0, "0"),
        (1.23, "1.23"),
        (10000.0, "10000"),
        (1.23456789012345, "1.23456789012"),
    ],
)
def test_format_number_removes_noise_and_limits_significant_digits(
    value: float,
    expected: str,
) -> None:
    assert format_number(value) == expected
