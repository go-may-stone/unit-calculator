"""Windows向け単位変換・単位計算アプリのTkinter GUI。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from unit_engine import UnitEngine, UnitEngineError


# 画面には一般的な表記を示し、エンジンにはPintで曖昧さなく解釈できる
# 単位名を渡す。リストにない単位は編集可能な入力欄から直接指定できる。
UNIT_CATEGORIES: dict[str, tuple[tuple[str, str], ...]] = {
    "長さ": (
        ("mm", "millimeter"),
        ("cm", "centimeter"),
        ("m", "meter"),
        ("km", "kilometer"),
        ("inch", "inch"),
        ("foot", "foot"),
        ("yard", "yard"),
        ("mile", "mile"),
    ),
    "面積": (
        ("mm²", "millimeter ** 2"),
        ("cm²", "centimeter ** 2"),
        ("m²", "meter ** 2"),
        ("km²", "kilometer ** 2"),
        ("hectare", "hectare"),
        ("acre", "acre"),
    ),
    "体積": (
        ("mL", "milliliter"),
        ("L", "liter"),
        ("m³", "meter ** 3"),
        ("US gallon", "gallon"),
    ),
    "質量": (
        ("mg", "milligram"),
        ("g", "gram"),
        ("kg", "kilogram"),
        ("t", "metric_ton"),
        ("ounce", "ounce"),
        ("pound", "pound"),
    ),
    "時間": (
        ("ms", "millisecond"),
        ("s", "second"),
        ("min", "minute"),
        ("h", "hour"),
        ("day", "day"),
    ),
    "速度": (
        ("m/s", "meter / second"),
        ("km/h", "kilometer / hour"),
        ("knot", "knot"),
        ("mph", "mile / hour"),
    ),
    "温度": (
        ("°C", "degC"),
        ("°F", "degF"),
        ("K", "kelvin"),
    ),
    "圧力": (
        ("Pa", "pascal"),
        ("kPa", "kilopascal"),
        ("MPa", "megapascal"),
        ("bar", "bar"),
        ("psi", "psi"),
    ),
    "エネルギー": (
        ("J", "joule"),
        ("kJ", "kilojoule"),
        ("Wh", "watt_hour"),
        ("kWh", "kilowatt_hour"),
    ),
    "電力": (
        ("W", "watt"),
        ("kW", "kilowatt"),
        ("horsepower", "horsepower"),
    ),
}


CATEGORY_DEFAULTS: dict[str, tuple[str, str]] = {
    "長さ": ("m", "km"),
    "面積": ("m²", "km²"),
    "体積": ("mL", "L"),
    "質量": ("g", "kg"),
    "時間": ("s", "min"),
    "速度": ("m/s", "km/h"),
    "温度": ("°C", "°F"),
    "圧力": ("Pa", "kPa"),
    "エネルギー": ("J", "kJ"),
    "電力": ("W", "kW"),
}


class UnitCalculatorApp:
    """単位変換と単位付き計算の画面および操作状態を管理する。"""

    _BACKGROUND = "#f3f3f3"
    _CARD_BACKGROUND = "#ffffff"
    _TEXT = "#202020"
    _SUBTLE_TEXT = "#5f5f5f"
    _ERROR = "#b42318"
    _WARNING = "#8a5700"
    _SUCCESS = "#177245"

    def __init__(
        self,
        root: tk.Tk,
        engine: UnitEngine | None = None,
    ) -> None:
        """画面を構築し、計算エンジンとキーボード操作を接続する。"""

        self.root = root
        self.engine = engine if engine is not None else UnitEngine()
        self._last_result = ""

        self.category_var = tk.StringVar(value="長さ")
        self.convert_value_var = tk.StringVar()
        self.from_unit_var = tk.StringVar(value="m")
        self.to_unit_var = tk.StringVar(value="km")
        self.expression_var = tk.StringVar()
        self.output_unit_var = tk.StringVar()
        self.result_var = tk.StringVar(value="—")
        self.message_var = tk.StringVar()
        self.warning_var = tk.StringVar(
            value=str(getattr(self.engine, "warning", "") or "")
        )

        self._configure_window()
        self._configure_styles()
        self._build_ui()
        self._bind_keyboard()

        self._update_warning_visibility()
        self.root.after_idle(self.convert_value_entry.focus_set)

    def _configure_window(self) -> None:
        """ウィンドウの初期サイズと基本色を設定する。"""

        self.root.title("Unit Calculator")
        self.root.geometry("560x720")
        self.root.minsize(520, 650)
        self.root.configure(background=self._BACKGROUND)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

    def _configure_styles(self) -> None:
        """ttk部品を落ち着いたWindows 11風の配色と余白に整える。"""

        self.style = ttk.Style(self.root)
        if "vista" in self.style.theme_names():
            self.style.theme_use("vista")

        self.style.configure("App.TFrame", background=self._BACKGROUND)
        self.style.configure("Card.TFrame", background=self._CARD_BACKGROUND)
        self.style.configure(
            "Title.TLabel",
            background=self._BACKGROUND,
            foreground=self._TEXT,
            font=("Segoe UI Variable Display", 20, "bold"),
        )
        self.style.configure(
            "Subtitle.TLabel",
            background=self._BACKGROUND,
            foreground=self._SUBTLE_TEXT,
            font=("Segoe UI", 9),
        )
        self.style.configure(
            "CardTitle.TLabel",
            background=self._CARD_BACKGROUND,
            foreground=self._SUBTLE_TEXT,
            font=("Segoe UI", 9),
        )
        self.style.configure(
            "Result.TLabel",
            background=self._CARD_BACKGROUND,
            foreground=self._TEXT,
            font=("Segoe UI Variable Display", 25, "bold"),
        )
        self.style.configure(
            "Warning.TLabel",
            background="#fff4ce",
            foreground=self._WARNING,
            font=("Segoe UI", 9),
            padding=(10, 8),
        )
        self.style.configure(
            "Error.TLabel",
            background=self._BACKGROUND,
            foreground=self._ERROR,
            font=("Segoe UI", 9),
        )
        self.style.configure(
            "Success.TLabel",
            background=self._BACKGROUND,
            foreground=self._SUCCESS,
            font=("Segoe UI", 9),
        )
        self.style.configure(
            "Input.TEntry",
            font=("Segoe UI", 12),
            padding=(8, 7),
        )
        self.style.configure(
            "Unit.TCombobox",
            font=("Segoe UI", 11),
            padding=(7, 6),
        )
        self.style.configure(
            "Keypad.TButton",
            font=("Segoe UI", 12),
            padding=(8, 10),
        )
        self.style.configure(
            "Equals.TButton",
            font=("Segoe UI", 14, "bold"),
            padding=(8, 10),
        )
        self.style.configure(
            "Action.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(12, 8),
        )

    def _build_ui(self) -> None:
        """モード画面、結果欄、メッセージ欄、キーパッドを配置する。"""

        main = ttk.Frame(self.root, padding=(20, 16, 20, 18), style="App.TFrame")
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(5, weight=1)

        heading = ttk.Frame(main, style="App.TFrame")
        heading.grid(row=0, column=0, sticky="ew")
        heading.columnconfigure(0, weight=1)
        ttk.Label(
            heading,
            text="Unit Calculator",
            style="Title.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            heading,
            text="単位変換と単位付き計算",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(1, 0))

        self.warning_label = ttk.Label(
            main,
            textvariable=self.warning_var,
            style="Warning.TLabel",
            anchor="w",
            justify="left",
            wraplength=500,
        )
        self.warning_label.grid(row=1, column=0, sticky="ew", pady=(10, 0))

        self.notebook = ttk.Notebook(main)
        self.notebook.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        self.convert_page = ttk.Frame(self.notebook, padding=(14, 12))
        self.calculate_page = ttk.Frame(self.notebook, padding=(14, 12))
        self.notebook.add(self.convert_page, text="  単位変換  ")
        self.notebook.add(self.calculate_page, text="  単位計算  ")
        self._build_convert_page()
        self._build_calculate_page()
        self.notebook.bind("<<NotebookTabChanged>>", self._on_mode_changed)

        self._build_result_card(main)

        self.message_label = ttk.Label(
            main,
            textvariable=self.message_var,
            style="Error.TLabel",
            anchor="w",
            justify="left",
            wraplength=500,
        )
        self.message_label.grid(row=4, column=0, sticky="ew", pady=(7, 3))

        self._build_keypad(main)

    def _build_convert_page(self) -> None:
        """単位変換モードの入力欄を作成する。"""

        page = self.convert_page
        page.columnconfigure(0, weight=1)
        page.columnconfigure(1, weight=0)
        page.columnconfigure(2, weight=1)

        ttk.Label(page, text="カテゴリ").grid(
            row=0,
            column=0,
            columnspan=3,
            sticky="w",
        )
        self.category_combo = ttk.Combobox(
            page,
            textvariable=self.category_var,
            values=tuple(UNIT_CATEGORIES),
            state="readonly",
            style="Unit.TCombobox",
        )
        self.category_combo.grid(
            row=1,
            column=0,
            columnspan=3,
            sticky="ew",
            pady=(4, 10),
        )
        self.category_combo.bind("<<ComboboxSelected>>", self._on_category_changed)

        ttk.Label(page, text="値").grid(
            row=2,
            column=0,
            columnspan=3,
            sticky="w",
        )
        self.convert_value_entry = ttk.Entry(
            page,
            textvariable=self.convert_value_var,
            style="Input.TEntry",
        )
        self.convert_value_entry.grid(
            row=3,
            column=0,
            columnspan=3,
            sticky="ew",
            pady=(4, 10),
        )

        ttk.Label(page, text="変換元").grid(row=4, column=0, sticky="w")
        ttk.Label(page, text="変換先").grid(row=4, column=2, sticky="w")
        initial_values = self._category_labels("長さ")
        self.from_unit_combo = ttk.Combobox(
            page,
            textvariable=self.from_unit_var,
            values=initial_values,
            state="normal",
            style="Unit.TCombobox",
        )
        self.from_unit_combo.grid(row=5, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(
            page,
            text="⇄",
            width=3,
            command=self._swap_units,
        ).grid(row=5, column=1, padx=9, pady=(4, 0))
        self.to_unit_combo = ttk.Combobox(
            page,
            textvariable=self.to_unit_var,
            values=initial_values,
            state="normal",
            style="Unit.TCombobox",
        )
        self.to_unit_combo.grid(row=5, column=2, sticky="ew", pady=(4, 0))

        ttk.Button(
            page,
            text="変換する",
            command=self._execute_conversion,
            style="Action.TButton",
        ).grid(
            row=6,
            column=0,
            columnspan=3,
            sticky="e",
            pady=(11, 0),
        )

    def _build_calculate_page(self) -> None:
        """単位計算モードの式と出力単位入力欄を作成する。"""

        page = self.calculate_page
        page.columnconfigure(0, weight=1)

        ttk.Label(page, text="計算式").grid(row=0, column=0, sticky="w")
        self.expression_entry = ttk.Entry(
            page,
            textvariable=self.expression_var,
            style="Input.TEntry",
        )
        self.expression_entry.grid(row=1, column=0, sticky="ew", pady=(4, 3))
        ttk.Label(
            page,
            text="例: 51 m/s × 8 s",
            foreground=self._SUBTLE_TEXT,
        ).grid(row=2, column=0, sticky="w", pady=(0, 9))

        ttk.Label(page, text="出力単位（省略可）").grid(
            row=3,
            column=0,
            sticky="w",
        )
        self.output_unit_combo = ttk.Combobox(
            page,
            textvariable=self.output_unit_var,
            values=self._all_unit_labels(),
            state="normal",
            style="Unit.TCombobox",
        )
        self.output_unit_combo.grid(row=4, column=0, sticky="ew", pady=(4, 0))

        ttk.Button(
            page,
            text="計算する",
            command=self._execute_calculation,
            style="Action.TButton",
        ).grid(row=5, column=0, sticky="e", pady=(11, 0))

    def _build_result_card(self, parent: ttk.Frame) -> None:
        """強調した結果表示とコピーボタンを作成する。"""

        card = ttk.Frame(
            parent,
            padding=(14, 10, 12, 12),
            style="Card.TFrame",
        )
        card.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        card.columnconfigure(0, weight=1)

        ttk.Label(card, text="結果", style="CardTitle.TLabel").grid(
            row=0,
            column=0,
            sticky="w",
        )
        self.result_label = ttk.Label(
            card,
            textvariable=self.result_var,
            style="Result.TLabel",
            anchor="e",
            justify="right",
            wraplength=430,
        )
        self.result_label.grid(row=1, column=0, sticky="ew", pady=(3, 0))

        self.copy_button = ttk.Button(
            card,
            text="コピー",
            command=self._copy_result,
        )
        self.copy_button.grid(row=0, column=1, rowspan=2, padx=(12, 0))
        self.copy_button.state(["disabled"])

    def _build_keypad(self, parent: ttk.Frame) -> None:
        """数値、演算子、括弧、累乗を入力できる画面ボタンを作成する。"""

        keypad = ttk.Frame(parent, style="App.TFrame")
        keypad.grid(row=5, column=0, sticky="nsew", pady=(6, 0))
        for column in range(5):
            keypad.columnconfigure(column, weight=1, uniform="keypad")
        for row in range(5):
            keypad.rowconfigure(row, weight=1, uniform="keypad")

        controls: tuple[tuple[str, int, int, int], ...] = (
            ("C", 0, 0, 1),
            ("(", 0, 1, 1),
            (")", 0, 2, 1),
            ("^", 0, 3, 1),
            ("⌫", 0, 4, 1),
            ("7", 1, 0, 1),
            ("8", 1, 1, 1),
            ("9", 1, 2, 1),
            ("÷", 1, 3, 1),
            ("4", 2, 0, 1),
            ("5", 2, 1, 1),
            ("6", 2, 2, 1),
            ("×", 2, 3, 1),
            ("1", 3, 0, 1),
            ("2", 3, 1, 1),
            ("3", 3, 2, 1),
            ("-", 3, 3, 1),
            ("0", 4, 0, 2),
            (".", 4, 2, 1),
            ("+", 4, 3, 1),
        )
        for text, row, column, columnspan in controls:
            if text == "C":
                command = self._clear_current_input
            elif text == "⌫":
                command = self._backspace_current_input
            else:
                command = lambda token=text: self._insert_keypad_token(token)
            ttk.Button(
                keypad,
                text=text,
                command=command,
                style="Keypad.TButton",
            ).grid(
                row=row,
                column=column,
                columnspan=columnspan,
                sticky="nsew",
                padx=3,
                pady=3,
            )

        ttk.Button(
            keypad,
            text="=",
            command=self._execute_current_mode,
            style="Equals.TButton",
        ).grid(
            row=1,
            column=4,
            rowspan=4,
            sticky="nsew",
            padx=3,
            pady=3,
        )

    def _bind_keyboard(self) -> None:
        """要件で定められたキーボードショートカットを登録する。"""

        self.root.bind("<Return>", self._on_enter)
        self.root.bind("<KP_Enter>", self._on_enter)
        self.root.bind("<Escape>", self._on_escape)
        self.root.bind("<BackSpace>", self._on_backspace_key)
        self.root.bind("<Control-c>", self._on_copy_key)
        self.root.bind("<Control-C>", self._on_copy_key)

    @staticmethod
    def _category_labels(category: str) -> tuple[str, ...]:
        """指定カテゴリの画面表示用単位名を返す。"""

        return tuple(label for label, _ in UNIT_CATEGORIES[category])

    @staticmethod
    def _all_unit_labels() -> tuple[str, ...]:
        """出力単位候補を重複なしでカテゴリ順に返す。"""

        return tuple(
            dict.fromkeys(
                label
                for choices in UNIT_CATEGORIES.values()
                for label, _ in choices
            )
        )

    @staticmethod
    def _resolve_unit(unit_text: str) -> str:
        """候補の表示名をPint名へ変換し、直接入力はそのまま返す。"""

        text = unit_text.strip()
        for choices in UNIT_CATEGORIES.values():
            for label, pint_name in choices:
                if text == label:
                    return pint_name
        return text

    def _on_category_changed(self, _event: tk.Event | None = None) -> None:
        """カテゴリに応じて候補と扱いやすい初期単位を更新する。"""

        category = self.category_var.get()
        labels = self._category_labels(category)
        self.from_unit_combo.configure(values=labels)
        self.to_unit_combo.configure(values=labels)
        from_default, to_default = CATEGORY_DEFAULTS[category]
        self.from_unit_var.set(from_default)
        self.to_unit_var.set(to_default)
        self._clear_message()
        self.convert_value_entry.focus_set()

    def _on_mode_changed(self, _event: tk.Event | None = None) -> None:
        """切り替え先モードの主入力欄へフォーカスを移す。"""

        self._clear_message()
        if self._is_conversion_mode():
            self.root.after_idle(self.convert_value_entry.focus_set)
        else:
            self.root.after_idle(self.expression_entry.focus_set)

    def _is_conversion_mode(self) -> bool:
        """現在表示中のタブが単位変換かを返す。"""

        return self.notebook.index("current") == 0

    def _current_input_entry(self) -> ttk.Entry:
        """現在のモードでキーパッド操作の対象となる入力欄を返す。"""

        if self._is_conversion_mode():
            return self.convert_value_entry
        return self.expression_entry

    def _insert_keypad_token(self, token: str) -> None:
        """選択範囲またはカーソル位置へ画面ボタンの文字を挿入する。"""

        if self._is_conversion_mode() and token not in {
            "0",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            ".",
            "+",
            "-",
        }:
            self._show_error(
                "四則演算、括弧、累乗は「単位計算」モードで使用してください。"
            )
            return

        entry = self._current_input_entry()
        try:
            selection_start = entry.index("sel.first")
            selection_end = entry.index("sel.last")
        except tk.TclError:
            selection_start = selection_end = entry.index(tk.INSERT)
        if selection_start != selection_end:
            entry.delete(selection_start, selection_end)
            entry.icursor(selection_start)
        entry.insert(tk.INSERT, token)
        entry.focus_set()
        self._clear_message()

    def _backspace_current_input(self) -> None:
        """現在の入力欄から選択範囲またはカーソル直前の1文字を削除する。"""

        entry = self._current_input_entry()
        try:
            selection_start = entry.index("sel.first")
            selection_end = entry.index("sel.last")
        except tk.TclError:
            selection_start = selection_end = entry.index(tk.INSERT)

        if selection_start != selection_end:
            entry.delete(selection_start, selection_end)
            entry.icursor(selection_start)
        elif selection_start > 0:
            entry.delete(selection_start - 1, selection_start)
        entry.focus_set()
        self._clear_message()

    def _clear_current_input(self) -> None:
        """現在のモードの値または式だけを消し、単位選択は保持する。"""

        entry = self._current_input_entry()
        entry.delete(0, tk.END)
        entry.focus_set()
        self._clear_message()

    def _swap_units(self) -> None:
        """変換元と変換先を交換し、入力済みなら新しい向きで再計算する。"""

        from_unit = self.from_unit_var.get()
        self.from_unit_var.set(self.to_unit_var.get())
        self.to_unit_var.set(from_unit)
        self.convert_value_entry.focus_set()
        if self.convert_value_var.get().strip():
            self._execute_conversion()

    def _execute_current_mode(self) -> None:
        """現在のモードに対応する変換または計算を実行する。"""

        if self._is_conversion_mode():
            self._execute_conversion()
        else:
            self._execute_calculation()

    def _execute_conversion(self) -> None:
        """数値と単位を分離したままエンジンへ渡して変換する。"""

        value = self.convert_value_var.get().strip()
        from_unit = self.from_unit_var.get().strip()
        to_unit = self.to_unit_var.get().strip()
        if not value:
            self._show_error("変換する数値を入力してください。")
            return
        if not from_unit:
            self._show_error("変換元の単位を入力してください。")
            return
        if not to_unit:
            self._show_error("変換先の単位を入力してください。")
            return

        try:
            result = self.engine.convert(
                value,
                self._resolve_unit(from_unit),
                self._resolve_unit(to_unit),
            )
        except UnitEngineError as exc:
            self._show_error(str(exc))
            return
        except Exception:
            self._show_error("変換中に予期しないエラーが発生しました。")
            return
        self._show_result(str(result))

    def _execute_calculation(self) -> None:
        """式と任意の出力単位をエンジンへ渡して計算する。"""

        expression = self.expression_var.get().strip()
        output_unit = self.output_unit_var.get().strip()
        if not expression:
            self._show_error("計算式を入力してください。")
            return

        try:
            result = self.engine.calculate(
                expression,
                self._resolve_unit(output_unit) if output_unit else "",
            )
        except UnitEngineError as exc:
            self._show_error(str(exc))
            return
        except Exception:
            self._show_error("計算中に予期しないエラーが発生しました。")
            return
        self._show_result(str(result))

    def _show_result(self, result: str) -> None:
        """成功した結果を強調表示し、コピー操作を有効にする。"""

        self._last_result = result
        self.result_var.set(result)
        self.copy_button.state(["!disabled"])
        self._clear_message()

    def _show_error(self, message: str) -> None:
        """入力を保持したまま日本語エラーを画面内へ表示する。"""

        self.message_var.set(message)
        self.message_label.configure(style="Error.TLabel")
        self.root.bell()

    def _clear_message(self) -> None:
        """一時的なエラーまたは操作完了メッセージを消す。"""

        self.message_var.set("")
        self.message_label.configure(style="Error.TLabel")

    def _update_warning_visibility(self) -> None:
        """units.txt読み込み警告がある場合だけ警告欄を表示する。"""

        if self.warning_var.get():
            self.warning_label.grid()
        else:
            self.warning_label.grid_remove()

    def _copy_result(self) -> None:
        """最後に成功した結果をクリップボードへコピーする。"""

        if not self._last_result:
            self._show_error("コピーできる結果がありません。")
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(self._last_result)
            self.root.update_idletasks()
        except tk.TclError:
            self._show_error("クリップボードへコピーできませんでした。")
            return
        self.message_var.set("結果をコピーしました。")
        self.message_label.configure(style="Success.TLabel")

    def _on_enter(self, _event: tk.Event) -> str:
        """Enterキーで現在の処理を実行する。"""

        self._execute_current_mode()
        return "break"

    def _on_escape(self, _event: tk.Event) -> str:
        """Escapeキーで現在の入力だけをクリアする。"""

        self._clear_current_input()
        return "break"

    def _on_backspace_key(self, _event: tk.Event) -> str | None:
        """編集欄以外にフォーカスがある場合もBackspaceを入力へ適用する。"""

        focused = self.root.focus_get()
        if isinstance(focused, (tk.Entry, ttk.Entry, ttk.Combobox)):
            return None
        self._backspace_current_input()
        return "break"

    def _on_copy_key(self, _event: tk.Event) -> str:
        """Ctrl+Cで結果をコピーする。"""

        self._copy_result()
        return "break"


def main() -> None:
    """Tkinterアプリケーションを生成してイベントループを開始する。"""

    root = tk.Tk()
    UnitCalculatorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
