# sector_profiles.py
# Calibrated sector profiles for 18 industry sectors based on typical MSME and RBI sectoral credit statistics.

SECTOR_PROFILES = {
    "Textile Manufacturing": {
        "nic": "17120",
        "npa_rate": 0.12,
        "dscr": {"mean": 1.25, "std": 0.25, "fraud_shift": -0.45},
        "icr": {"mean": 1.75, "std": 0.35, "fraud_shift": -0.65},
        "leverage": {"mean": 1.8, "std": 0.4, "fraud_shift": 0.9},
        "current_ratio": {"mean": 1.3, "std": 0.2, "fraud_shift": -0.4},
        "ebitda_margin": {"mean": 0.08, "std": 0.02, "fraud_shift": -0.04},
        "seasonality": [0.90, 1.10, 1.15, 0.85],  # Q1-Q4
        "fraud_archetypes": ["circular_trading", "revenue_inflation", "seasonal_manipulation"],
        "typical_turnover_range": (50_00_000, 50_00_00_000)
    },
    "Steel Fabrication": {
        "nic": "25111",
        "npa_rate": 0.11,
        "dscr": {"mean": 1.30, "std": 0.28, "fraud_shift": -0.40},
        "icr": {"mean": 1.85, "std": 0.40, "fraud_shift": -0.60},
        "leverage": {"mean": 1.6, "std": 0.35, "fraud_shift": 0.8},
        "current_ratio": {"mean": 1.35, "std": 0.22, "fraud_shift": -0.35},
        "ebitda_margin": {"mean": 0.09, "std": 0.025, "fraud_shift": -0.04},
        "seasonality": [0.95, 1.05, 1.10, 0.90],
        "fraud_archetypes": ["circular_trading", "evergreening", "shell_company"],
        "typical_turnover_range": (1_00_00_000, 100_00_00_000)
    },
    "Chemical Processing": {
        "nic": "20111",
        "npa_rate": 0.08,
        "dscr": {"mean": 1.45, "std": 0.30, "fraud_shift": -0.50},
        "icr": {"mean": 2.10, "std": 0.50, "fraud_shift": -0.80},
        "leverage": {"mean": 1.4, "std": 0.30, "fraud_shift": 0.7},
        "current_ratio": {"mean": 1.40, "std": 0.25, "fraud_shift": -0.40},
        "ebitda_margin": {"mean": 0.12, "std": 0.03, "fraud_shift": -0.05},
        "seasonality": [1.00, 1.00, 1.05, 0.95],
        "fraud_archetypes": ["revenue_inflation", "benami_siphoning", "circular_trading"],
        "typical_turnover_range": (2_00_00_000, 150_00_00_000)
    },
    "IT Services": {
        "nic": "62011",
        "npa_rate": 0.03,
        "dscr": {"mean": 2.20, "std": 0.40, "fraud_shift": -0.80},
        "icr": {"mean": 3.80, "std": 0.80, "fraud_shift": -1.50},
        "leverage": {"mean": 0.6, "std": 0.15, "fraud_shift": 0.8},
        "current_ratio": {"mean": 1.80, "std": 0.35, "fraud_shift": -0.60},
        "ebitda_margin": {"mean": 0.18, "std": 0.04, "fraud_shift": -0.08},
        "seasonality": [0.95, 0.95, 1.05, 1.05],
        "fraud_archetypes": ["revenue_inflation", "benami_siphoning", "shell_company"],
        "typical_turnover_range": (30_00_000, 120_00_00_000)
    },
    "Agro Processing": {
        "nic": "10300",
        "npa_rate": 0.09,
        "dscr": {"mean": 1.35, "std": 0.25, "fraud_shift": -0.40},
        "icr": {"mean": 1.90, "std": 0.38, "fraud_shift": -0.60},
        "leverage": {"mean": 1.5, "std": 0.30, "fraud_shift": 0.7},
        "current_ratio": {"mean": 1.30, "std": 0.20, "fraud_shift": -0.30},
        "ebitda_margin": {"mean": 0.07, "std": 0.02, "fraud_shift": -0.03},
        "seasonality": [0.80, 0.90, 1.20, 1.10], # Highly seasonal
        "fraud_archetypes": ["seasonal_manipulation", "evergreening", "revenue_inflation"],
        "typical_turnover_range": (40_00_000, 60_00_00_000)
    },
    "Logistics & Transport": {
        "nic": "49231",
        "npa_rate": 0.07,
        "dscr": {"mean": 1.50, "std": 0.30, "fraud_shift": -0.50},
        "icr": {"mean": 2.20, "std": 0.45, "fraud_shift": -0.80},
        "leverage": {"mean": 1.7, "std": 0.35, "fraud_shift": 0.9},
        "current_ratio": {"mean": 1.20, "std": 0.18, "fraud_shift": -0.30},
        "ebitda_margin": {"mean": 0.11, "std": 0.03, "fraud_shift": -0.05},
        "seasonality": [0.90, 1.00, 1.10, 1.00],
        "fraud_archetypes": ["shell_company", "benami_siphoning", "evergreening"],
        "typical_turnover_range": (20_00_000, 40_00_00_000)
    },
    "Retail Trade": {
        "nic": "47110",
        "npa_rate": 0.06,
        "dscr": {"mean": 1.60, "std": 0.32, "fraud_shift": -0.55},
        "icr": {"mean": 2.50, "std": 0.50, "fraud_shift": -0.90},
        "leverage": {"mean": 1.2, "std": 0.25, "fraud_shift": 0.6},
        "current_ratio": {"mean": 1.45, "std": 0.25, "fraud_shift": -0.40},
        "ebitda_margin": {"mean": 0.06, "std": 0.015, "fraud_shift": -0.025},
        "seasonality": [0.85, 0.95, 1.10, 1.10], # Festive season bump
        "fraud_archetypes": ["circular_trading", "revenue_inflation", "seasonal_manipulation"],
        "typical_turnover_range": (10_00_000, 30_00_00_000)
    },
    "Construction & Infrastructure": {
        "nic": "41001",
        "npa_rate": 0.15,
        "dscr": {"mean": 1.20, "std": 0.28, "fraud_shift": -0.45},
        "icr": {"mean": 1.65, "std": 0.35, "fraud_shift": -0.55},
        "leverage": {"mean": 2.2, "std": 0.50, "fraud_shift": 1.3},
        "current_ratio": {"mean": 1.25, "std": 0.20, "fraud_shift": -0.35},
        "ebitda_margin": {"mean": 0.10, "std": 0.03, "fraud_shift": -0.05},
        "seasonality": [1.05, 0.80, 1.05, 1.10], # Monsoon slowdown in Q2
        "fraud_archetypes": ["revenue_inflation", "shell_company", "benami_siphoning", "evergreening"],
        "typical_turnover_range": (2_00_00_000, 200_00_00_000)
    },
    "Healthcare Services": {
        "nic": "86100",
        "npa_rate": 0.04,
        "dscr": {"mean": 1.80, "std": 0.35, "fraud_shift": -0.60},
        "icr": {"mean": 2.80, "std": 0.60, "fraud_shift": -1.00},
        "leverage": {"mean": 1.1, "std": 0.22, "fraud_shift": 0.6},
        "current_ratio": {"mean": 1.50, "std": 0.28, "fraud_shift": -0.45},
        "ebitda_margin": {"mean": 0.15, "std": 0.035, "fraud_shift": -0.06},
        "seasonality": [0.98, 1.02, 1.00, 1.00],
        "fraud_archetypes": ["revenue_inflation", "benami_siphoning", "evergreening"],
        "typical_turnover_range": (30_00_000, 80_00_00_000)
    },
    "Pharma Manufacturing": {
        "nic": "21002",
        "npa_rate": 0.05,
        "dscr": {"mean": 1.70, "std": 0.33, "fraud_shift": -0.55},
        "icr": {"mean": 2.70, "std": 0.55, "fraud_shift": -0.90},
        "leverage": {"mean": 1.2, "std": 0.25, "fraud_shift": 0.6},
        "current_ratio": {"mean": 1.50, "std": 0.26, "fraud_shift": -0.40},
        "ebitda_margin": {"mean": 0.16, "std": 0.038, "fraud_shift": -0.06},
        "seasonality": [0.97, 1.01, 1.02, 1.00],
        "fraud_archetypes": ["circular_trading", "revenue_inflation", "benami_siphoning"],
        "typical_turnover_range": (1_50_00_000, 120_00_00_000)
    },
    "Auto Components": {
        "nic": "29301",
        "npa_rate": 0.08,
        "dscr": {"mean": 1.40, "std": 0.26, "fraud_shift": -0.45},
        "icr": {"mean": 2.00, "std": 0.42, "fraud_shift": -0.65},
        "leverage": {"mean": 1.5, "std": 0.32, "fraud_shift": 0.75},
        "current_ratio": {"mean": 1.30, "std": 0.21, "fraud_shift": -0.32},
        "ebitda_margin": {"mean": 0.10, "std": 0.024, "fraud_shift": -0.045},
        "seasonality": [0.90, 1.05, 1.10, 0.95],
        "fraud_archetypes": ["circular_trading", "evergreening", "shell_company"],
        "typical_turnover_range": (1_20_00_000, 90_00_00_000)
    },
    "Food & Beverages": {
        "nic": "11000",
        "npa_rate": 0.07,
        "dscr": {"mean": 1.55, "std": 0.28, "fraud_shift": -0.48},
        "icr": {"mean": 2.40, "std": 0.48, "fraud_shift": -0.80},
        "leverage": {"mean": 1.3, "std": 0.28, "fraud_shift": 0.65},
        "current_ratio": {"mean": 1.40, "std": 0.24, "fraud_shift": -0.38},
        "ebitda_margin": {"mean": 0.08, "std": 0.02, "fraud_shift": -0.035},
        "seasonality": [0.88, 0.96, 1.12, 1.04],
        "fraud_archetypes": ["seasonal_manipulation", "revenue_inflation", "circular_trading"],
        "typical_turnover_range": (50_00_000, 75_00_00_000)
    },
    "Electrical Equipment": {
        "nic": "27100",
        "npa_rate": 0.09,
        "dscr": {"mean": 1.38, "std": 0.27, "fraud_shift": -0.42},
        "icr": {"mean": 1.95, "std": 0.40, "fraud_shift": -0.65},
        "leverage": {"mean": 1.6, "std": 0.35, "fraud_shift": 0.8},
        "current_ratio": {"mean": 1.32, "std": 0.22, "fraud_shift": -0.34},
        "ebitda_margin": {"mean": 0.09, "std": 0.022, "fraud_shift": -0.04},
        "seasonality": [0.92, 1.04, 1.08, 0.96],
        "fraud_archetypes": ["circular_trading", "evergreening", "shell_company"],
        "typical_turnover_range": (80_00_000, 85_00_00_000)
    },
    "Plastics & Rubber": {
        "nic": "22200",
        "npa_rate": 0.10,
        "dscr": {"mean": 1.32, "std": 0.25, "fraud_shift": -0.40},
        "icr": {"mean": 1.80, "std": 0.36, "fraud_shift": -0.60},
        "leverage": {"mean": 1.7, "std": 0.38, "fraud_shift": 0.85},
        "current_ratio": {"mean": 1.28, "std": 0.19, "fraud_shift": -0.30},
        "ebitda_margin": {"mean": 0.085, "std": 0.02, "fraud_shift": -0.038},
        "seasonality": [0.94, 1.02, 1.06, 0.98],
        "fraud_archetypes": ["circular_trading", "revenue_inflation", "evergreening"],
        "typical_turnover_range": (60_00_000, 70_00_00_000)
    },
    "Education Services": {
        "nic": "85100",
        "npa_rate": 0.05,
        "dscr": {"mean": 1.65, "std": 0.34, "fraud_shift": -0.55},
        "icr": {"mean": 2.60, "std": 0.52, "fraud_shift": -0.85},
        "leverage": {"mean": 1.1, "std": 0.24, "fraud_shift": 0.6},
        "current_ratio": {"mean": 1.48, "std": 0.27, "fraud_shift": -0.42},
        "ebitda_margin": {"mean": 0.14, "std": 0.032, "fraud_shift": -0.06},
        "seasonality": [1.30, 0.90, 0.85, 0.95], # Higher in Q1 (admissions season)
        "fraud_archetypes": ["revenue_inflation", "benami_siphoning", "shell_company"],
        "typical_turnover_range": (40_00_000, 50_00_00_000)
    },
    "Real Estate": {
        "nic": "68100",
        "npa_rate": 0.16,
        "dscr": {"mean": 1.15, "std": 0.28, "fraud_shift": -0.40},
        "icr": {"mean": 1.50, "std": 0.32, "fraud_shift": -0.50},
        "leverage": {"mean": 2.5, "std": 0.60, "fraud_shift": 1.5},
        "current_ratio": {"mean": 1.20, "std": 0.18, "fraud_shift": -0.35},
        "ebitda_margin": {"mean": 0.22, "std": 0.06, "fraud_shift": -0.10},
        "seasonality": [0.90, 0.95, 1.05, 1.10],
        "fraud_archetypes": ["shell_company", "benami_siphoning", "evergreening", "revenue_inflation"],
        "typical_turnover_range": (3_00_00_000, 300_00_00_000)
    },
    "Tourism & Hospitality": {
        "nic": "55101",
        "npa_rate": 0.10,
        "dscr": {"mean": 1.35, "std": 0.30, "fraud_shift": -0.45},
        "icr": {"mean": 1.90, "std": 0.40, "fraud_shift": -0.65},
        "leverage": {"mean": 1.8, "std": 0.45, "fraud_shift": 0.9},
        "current_ratio": {"mean": 1.25, "std": 0.20, "fraud_shift": -0.32},
        "ebitda_margin": {"mean": 0.13, "std": 0.035, "fraud_shift": -0.06},
        "seasonality": [0.80, 0.85, 1.15, 1.20], # Winter & festive season peak
        "fraud_archetypes": ["seasonal_manipulation", "revenue_inflation", "benami_siphoning"],
        "typical_turnover_range": (30_00_000, 60_00_00_000)
    },
    "Renewable Energy": {
        "nic": "35106",
        "npa_rate": 0.06,
        "dscr": {"mean": 1.60, "std": 0.32, "fraud_shift": -0.50},
        "icr": {"mean": 2.50, "std": 0.50, "fraud_shift": -0.80},
        "leverage": {"mean": 2.0, "std": 0.40, "fraud_shift": 1.0},
        "current_ratio": {"mean": 1.35, "std": 0.22, "fraud_shift": -0.35},
        "ebitda_margin": {"mean": 0.25, "std": 0.05, "fraud_shift": -0.08},
        "seasonality": [1.05, 1.15, 0.90, 0.90], # Solar/wind peak in Q1-Q2
        "fraud_archetypes": ["revenue_inflation", "evergreening", "shell_company"],
        "typical_turnover_range": (2_50_00_000, 250_00_00_000)
    }
}
