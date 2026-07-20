# Shared Risk Calculation Constants and Utilities

# Risk weights (common baseline used for risk scoring)
WEIGHTS = {
    "dscr_normalized":           0.25,
    "leverage_normalized":       0.18,
    "revenue_growth_normalized": 0.12,
    "ebitda_margin_normalized":  0.10,
    "gst_discrepancy_norm":      0.12,
    "circular_trade_norm":       0.08,
    "litigation_norm":           0.10,
    "news_sentiment_norm":       0.05,
}

# Indian national medians for key financial features (heuristic baselines)
FEATURE_MEDIANS = {
    "dscr_normalized":           0.45,
    "leverage_normalized":       0.40,
    "revenue_growth_normalized": 0.35,
    "ebitda_margin_normalized":  0.30,
    "gst_discrepancy_norm":      0.10,
    "circular_trade_norm":       0.05,
    "litigation_norm":           0.15,
    "news_sentiment_norm":       0.50,
}

def assign_band(score: float) -> str:
    """Assign risk band based on score thresholds."""
    if score < 0.30:
        return "LOW"
    if score < 0.55:
        return "MEDIUM"
    if score < 0.75:
        return "HIGH"
    return "REJECT"
