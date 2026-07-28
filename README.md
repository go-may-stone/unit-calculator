# Unit Calculator

Windows標準電卓に近い操作感を目指した、単位変換・単位計算用のWindowsデスクトップアプリです。

## 現在の状態

このフォルダは実装前のスターターです。
`CODEX_IMPLEMENTATION_PROMPT.md`の指示をCodexへ渡すと、アプリ本体とテストを実装する想定です。

## 主な機能

- 数値を入力して別の単位へ変換
- 変換元と変換先の入れ替え
- 単位付き計算式
- 出力単位の指定
- 次元不一致の検出
- `units.txt`による独自単位の追加

詳細は`REQUIREMENTS.md`を参照してください。

## 開発環境の準備

PowerShellでプロジェクトフォルダを開き、次を実行します。

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## 実行

実装完了後、次で起動します。

```powershell
.\.venv\Scripts\python.exe unit_calculator.py
```

## テスト

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Windows用フォルダの作成

実装とテストが完了した後、次を実行します。

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

生成物は`dist\UnitCalculator\`に作られます。`UnitCalculator.exe`と`units.txt`を同じフォルダに置いたまま使用してください。

## 独自単位

`units.txt`へPint形式の定義を追加します。

```text
custom_count = 0.25 * millimeter = cnt
```

保存後にアプリを再起動すると利用できます。
