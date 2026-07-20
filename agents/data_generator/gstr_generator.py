import random
import datetime

class GSTRGenerator:
    """
    Generates realistic GST returns (GSTR-3B and GSTR-2B) for 12 months.
    Simulates specific anomalies based on the company's assigned fraud archetype.
    """

    def __init__(self):
        pass

    def generate(self, company_profile: dict, financial_profile: dict) -> dict:
        """
        Generates 12 months of GSTR data.
        Ties GST turnover to current year's annual revenue.
        """
        is_fraud = company_profile.get("is_fraudulent", False)
        fraud_type = company_profile.get("fraud_type", None)
        annual_revenue = financial_profile["revenue_annual"][-1]
        gst_discrepancy_pct = financial_profile["gst_discrepancy_pct"]
        
        monthly_base = annual_revenue / 12
        months = []
        
        # Start of Fiscal Year (April 1, 2025)
        start_date = datetime.date(2025, 4, 1)
        
        total_gstr_turnover = 0
        total_3b_itc = 0
        total_2b_itc = 0
        
        gstr_records = []
        
        for i in range(12):
            month_date = start_date + datetime.timedelta(days=i*30)
            month_str = month_date.strftime("%B %Y")
            
            # ── 1. Seasonality & Fraud Modulation ──
            seasonal_factor = random.uniform(0.85, 1.15)
            
            if is_fraud and fraud_type == "seasonal_manipulation":
                # In March-rushing (seasonal manipulation), Q4 (Jan, Feb, Mar) spikes 3x-5x
                if i >= 9:
                    seasonal_factor = random.uniform(3.0, 4.5)
                else:
                    seasonal_factor = random.uniform(0.2, 0.4)
            elif is_fraud and fraud_type == "revenue_inflation":
                # Revenue is inflated in GST compared to real book/bank values
                seasonal_factor *= random.uniform(1.3, 1.5)
                
            monthly_sales = monthly_base * seasonal_factor
            
            # Standard GST rate of 18%
            tax_rate = 0.18
            igst_ratio = 0.4 # 40% interstate
            
            total_tax = monthly_sales * tax_rate
            igst_sales = total_tax * igst_ratio
            cgst_sales = (total_tax * (1 - igst_ratio)) / 2
            sgst_sales = cgst_sales
            
            # Purchase calculation (normally 60% of sales)
            purchase_ratio = random.uniform(0.55, 0.65)
            if is_fraud and fraud_type == "circular_trading":
                # Purchases are artificially inflated to match sales (circular economy)
                purchase_ratio = random.uniform(0.90, 0.98)
                
            monthly_purchases = monthly_sales * purchase_ratio
            purchase_tax = monthly_purchases * tax_rate
            igst_purchases = purchase_tax * igst_ratio
            cgst_purchases = (purchase_tax * (1 - igst_ratio)) / 2
            sgst_purchases = cgst_purchases
            
            # ITC Claimed (GSTR-3B)
            itc_claimed_igst = igst_purchases
            itc_claimed_cgst = cgst_purchases
            itc_claimed_sgst = sgst_purchases
            total_3b_itc_month = itc_claimed_igst + itc_claimed_cgst + itc_claimed_sgst
            
            # ── 2. ITC Mismatch & Delay Injection ──
            if is_fraud:
                if fraud_type == "circular_trading":
                    # Circular trading has heavy mismatch due to fake invoices
                    discrepancy_factor = 1.0 - (gst_discrepancy_pct / 100.0)
                    discrepancy_factor = max(0.2, min(0.7, discrepancy_factor))
                elif fraud_type == "shell_company":
                    # Sister GSTINs aren't filing their returns on time
                    discrepancy_factor = random.uniform(0.3, 0.6)
                else:
                    discrepancy_factor = 1.0 - (gst_discrepancy_pct / 100.0)
                    discrepancy_factor = max(0.4, min(0.9, discrepancy_factor))
                    
                itc_available_igst = itc_claimed_igst * discrepancy_factor
                itc_available_cgst = itc_claimed_cgst * discrepancy_factor
                itc_available_sgst = itc_claimed_sgst * discrepancy_factor
            else:
                # Legitimate slight mismatch or 0-3% timing discrepancy
                discrepancy_factor = 1.0 - random.uniform(0.0, 0.03)
                itc_available_igst = itc_claimed_igst * discrepancy_factor
                itc_available_cgst = itc_claimed_cgst * discrepancy_factor
                itc_available_sgst = itc_claimed_sgst * discrepancy_factor
                
            total_2b_itc_month = itc_available_igst + itc_available_cgst + itc_available_sgst
            
            # Cash Payment calculation
            itc_offset = min(total_tax, total_3b_itc_month)
            cash_payment = max(0.0, total_tax - itc_offset)
            
            record = {
                "month": month_str,
                "date": month_date.isoformat(),
                "gstr_3b": {
                    "outward_taxable_supplies": round(monthly_sales, 2),
                    "integrated_tax_sales": round(igst_sales, 2),
                    "central_tax_sales": round(cgst_sales, 2),
                    "state_tax_sales": round(sgst_sales, 2),
                    "inward_taxable_supplies": round(monthly_purchases, 2),
                    "itc_claimed": {
                        "igst": round(itc_claimed_igst, 2),
                        "cgst": round(itc_claimed_cgst, 2),
                        "sgst": round(itc_claimed_sgst, 2),
                        "total": round(total_3b_itc_month, 2)
                    },
                    "cash_payment": round(cash_payment, 2)
                },
                "gstr_2b": {
                    "itc_available": {
                        "igst": round(itc_available_igst, 2),
                        "cgst": round(itc_available_cgst, 2),
                        "sgst": round(itc_available_sgst, 2),
                        "total": round(total_2b_itc_month, 2)
                    }
                },
                "discrepancy_pct": round(((total_3b_itc_month - total_2b_itc_month) / max(1.0, total_2b_itc_month)) * 100, 2)
            }
            
            total_gstr_turnover += monthly_sales
            total_3b_itc += total_3b_itc_month
            total_2b_itc += total_2b_itc_month
            
            gstr_records.append(record)
            
        overall_discrepancy = round(((total_3b_itc - total_2b_itc) / max(1.0, total_2b_itc)) * 100, 2)
        
        return {
            "gstr_records": gstr_records,
            "total_gst_turnover": round(total_gstr_turnover, 2),
            "total_3b_itc": round(total_3b_itc, 2),
            "total_2b_itc": round(total_2b_itc, 2),
            "overall_discrepancy_pct": overall_discrepancy
        }
