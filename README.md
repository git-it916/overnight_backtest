# overnight_backtest

## Purpose

Alpha Factor Testing Framework that validates "t-1 condition -> t opening alpha (approx)"
using DAILY OHLCV plus flow data.

## Data

- DataGuide raw Excel export.
- Parsed by Item codes (not header names).
- Daily data only (no intraday bars).

## Run

```bash
pip install -r requirements.txt
python run_analysis.py
```

## Experiment options

`optimistic_fill=True` assumes take-profit fills before stop when both are hit in the same
opening bar; `False` assumes the stop hits first.
