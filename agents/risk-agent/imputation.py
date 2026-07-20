import os
import json
import numpy as np

# Find the workspace root
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SYNTHETIC_DATA_DIR = os.path.join(BASE_DIR, "synthetic_data")

class DynamicImputationEngine:
    def __init__(self, vectorai_client=None):
        self.vectorai_client = vectorai_client
        self.companies = []
        self.company_financials = {}
        self.global_averages = {}
        self.sector_averages = {}
        self.fallback_defaults = {
            "dscr": 1.5,
            "icr": 4.0,
            "leverage": 1.2,
            "current_ratio": 1.5,
            "revenue_growth_yoy": 0.15,
            "ebitda_margin": 0.12,
            "cibil_score": 700.0,
            "promoter_holding_pct": 60.0,
            "gst_discrepancy_pct": 5.0,
            "bank_divergence_pct": 4.0,
            "web_sentiment_avg": 0.2,
            "bounce_rate": 2.0,
            "years_in_business": 5.0,
            "ltv_ratio": 0.6,
            "circular_trade_index": 0.0,
            "litigation_count": 0.0
        }
        self._load_synthetic_data()

    def _load_synthetic_data(self):
        companies_dir = os.path.join(SYNTHETIC_DATA_DIR, "companies")
        financials_dir = os.path.join(SYNTHETIC_DATA_DIR, "financials")
        
        if not os.path.exists(companies_dir) or not os.path.exists(financials_dir):
            # Fallback relative to current file if workspace structure is different
            parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            companies_dir = os.path.join(parent, "synthetic_data", "companies")
            financials_dir = os.path.join(parent, "synthetic_data", "financials")
            
        if not os.path.exists(companies_dir):
            # Default everything to fallback defaults if directories are not found
            for feat, val in self.fallback_defaults.items():
                self.global_averages[feat] = val
            return
            
        for file in os.listdir(companies_dir):
            if file.endswith(".json") and file.startswith("company_"):
                company_path = os.path.join(companies_dir, file)
                try:
                    with open(company_path, "r", encoding="utf-8") as f:
                        comp_data = json.load(f)
                    self.companies.append(comp_data)
                    
                    comp_id = comp_data.get("company_id")
                    if comp_id:
                        fin_file = f"{comp_id}_financials.json"
                        fin_path = os.path.join(financials_dir, fin_file)
                        if os.path.exists(fin_path):
                            with open(fin_path, "r", encoding="utf-8") as f:
                                fin_data = json.load(f)
                            self.company_financials[comp_id] = fin_data
                except Exception as e:
                    print(f"Error loading synthetic data for {file}: {e}")

        # Compute global averages for all 16 features
        features_to_average = list(self.fallback_defaults.keys())
        global_values = {feat: [] for feat in features_to_average}
        
        for comp_id, fin in self.company_financials.items():
            for feat in features_to_average:
                val = fin.get(feat)
                if val is not None:
                    global_values[feat].append(float(val))
                    
        for feat in features_to_average:
            vals = global_values[feat]
            if vals:
                self.global_averages[feat] = float(np.mean(vals))
            else:
                self.global_averages[feat] = self.fallback_defaults[feat]

        # Compute sector-wise averages (case-insensitive strip matching)
        sector_companies = {}
        for comp in self.companies:
            sector = comp.get("industry_sector", "").strip().lower()
            if sector:
                sector_companies.setdefault(sector, []).append(comp.get("company_id"))
                
        for sector, comp_ids in sector_companies.items():
            sector_vals = {feat: [] for feat in features_to_average}
            for comp_id in comp_ids:
                fin = self.company_financials.get(comp_id)
                if fin:
                    for feat in features_to_average:
                        val = fin.get(feat)
                        if val is not None:
                            sector_vals[feat].append(float(val))
            
            self.sector_averages[sector] = {}
            for feat in features_to_average:
                vals = sector_vals[feat]
                if vals:
                    self.sector_averages[sector][feat] = float(np.mean(vals))
                else:
                    self.sector_averages[sector][feat] = self.global_averages[feat]

    def impute_missing_features(self, raw_features: dict, sector: str = None) -> tuple[dict, dict]:
        """
        Impute missing underwriting features.
        
        A feature is missing if it is not present in raw_features or is None.
        
        Fallback Hierarchy:
        1. VectorAI RAG-driven matches for the sector.
        2. Local directory matching companies in the same sector.
        3. Global averages across the 200 synthetic companies.
        4. Global default constants.
        
        Returns:
            imputed_features: dict with all 16 features filled.
            feature_sources: dict indicating the source of each feature.
        """
        imputed_features = {}
        feature_sources = {}
        features_list = list(self.fallback_defaults.keys())

        # Determine which features are provided and valid (extracted)
        # We consider a feature extracted if it is present and not None,
        # and not 0.0 for ratios/financials where 0 is treated as missing.
        non_zero_check_features = {
            "dscr", "icr", "leverage", "current_ratio", "ebitda_margin",
            "cibil_score", "promoter_holding_pct", "years_in_business", "ltv_ratio"
        }
        
        extracted_features = {}
        for feat in features_list:
            val = raw_features.get(feat)
            if val is not None:
                if feat in non_zero_check_features and float(val) == 0.0:
                    # Treat 0.0 as missing/OCR failure for key financials
                    continue
                extracted_features[feat] = val

        # 1. Try VectorAI RAG matches
        rag_averages = {}
        rag_success = False
        if self.vectorai_client and not self.vectorai_client.mock_mode and sector:
            try:
                # Query VectorAI for financial profiles in this sector
                results = self.vectorai_client.search(
                    collection="financial_profiles",
                    query_text=f"sector: {sector}",
                    top_k=10
                )
                if results:
                    temp_vals = {feat: [] for feat in features_list}
                    for r in results:
                        metadata = r.get("metadata", {})
                        for feat in features_list:
                            val = metadata.get(feat)
                            if val is not None:
                                temp_vals[feat].append(float(val))
                    
                    for feat in features_list:
                        if temp_vals[feat]:
                            rag_averages[feat] = float(np.mean(temp_vals[feat]))
                    rag_success = True
            except Exception as e:
                print(f"[DynamicImputationEngine] VectorAI RAG lookup failed: {e}")

        # 2. Local sector averages fallback
        sector_clean = sector.strip().lower() if sector else ""
        local_sector_avg = self.sector_averages.get(sector_clean, {})

        for feat in features_list:
            if feat in extracted_features:
                imputed_features[feat] = extracted_features[feat]
                feature_sources[feat] = "EXTRACTED"
            elif rag_success and feat in rag_averages:
                imputed_features[feat] = rag_averages[feat]
                feature_sources[feat] = "IMPUTED_RAG"
            elif sector_clean and feat in local_sector_avg:
                imputed_features[feat] = local_sector_avg[feat]
                feature_sources[feat] = "IMPUTED_SECTOR"
            elif feat in self.global_averages:
                imputed_features[feat] = self.global_averages[feat]
                feature_sources[feat] = "IMPUTED_GLOBAL"
            else:
                imputed_features[feat] = self.fallback_defaults[feat]
                feature_sources[feat] = "GLOBAL_DEFAULT"

        return imputed_features, feature_sources
