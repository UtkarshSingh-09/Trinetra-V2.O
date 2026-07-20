import random
import datetime

class BankStatementGenerator:
    """
    Generates 12 months of realistic bank transactions.
    Supports standard business debits/credits, EMI payments, bank fees,
    cheque bounces, and fraudulent round-tripping cash flows (circular trading).
    """

    BANKS = ["HDFC Bank", "ICICI Bank", "State Bank of India", "Axis Bank", "Kotak Mahindra Bank"]

    PARTIES = [
        "Jindal Steel & Power", "Tata Power", "Balaji Logistics", "Shree Cement", 
        "Reliance Retail", "Infosys Ltd", "Kirloskar Brothers", "Godrej Properties", 
        "Supreme Industries", "Karan Traders", "Ambika Trading Corp", "Saraswati Enterprises"
    ]

    DEBIT_NARRATIONS = [
        "NEFT DR / {party} / NET_BANK",
        "RTGS DR / {party} / CORE_BANK",
        "IMPS DR / {party} / IMPS_REF_{ref}",
        "UPI DR / {upi_id} / PAYMENT_TO_VENDOR",
        "CHQ CLG / {chq_no} / PAID TO {party}"
    ]

    CREDIT_NARRATIONS = [
        "NEFT CR / {party} / NET_BANK",
        "RTGS CR / {party} / CORE_BANK",
        "IMPS CR / {party} / IMPS_REF_{ref}",
        "UPI CR / {upi_id} / PAYMENT_RCVD",
        "CHQ DEP / {chq_no} / DEPOSIT FROM {party}"
    ]

    BOUNCE_NARRATION = "CHQ RETURN / {chq_no} / INSUFFICIENT FUNDS / DEBIT_FEE_350"

    def __init__(self):
        pass

    def generate(self, company_profile: dict, financial_profile: dict) -> dict:
        """
        Generates 12 months of transactions.
        Integrates current year turnover and bounce rate into narration frequencies and values.
        """
        is_fraud = company_profile.get("is_fraudulent", False)
        fraud_type = company_profile.get("fraud_type", None)
        annual_revenue = financial_profile["revenue_annual"][-1]
        bounce_rate = financial_profile["bounce_rate"]
        bank_divergence_pct = financial_profile["bank_divergence_pct"]
        
        bank_name = random.choice(self.BANKS)
        account_no = f"{random.randint(1000000000, 9999999999)}"
        ifsc = f"{bank_name[:4].upper()}0{random.randint(100000, 999999)}"
        
        # Divergence adjustment
        divergence_multiplier = 1.0
        if is_fraud and fraud_type == "revenue_inflation":
            # GST/financials show high revenue, but actual bank credits are much lower
            divergence_multiplier = 1.0 - (bank_divergence_pct / 100.0)
            divergence_multiplier = max(0.3, divergence_multiplier)
        else:
            divergence_multiplier = 1.0 + (random.choice([-1, 1]) * (bank_divergence_pct / 100.0) * random.uniform(0.7, 1.0))
            
        annual_bank_inflows = annual_revenue * divergence_multiplier
        monthly_inflows = annual_bank_inflows / 12
        
        outflow_ratio = random.uniform(0.90, 0.96)
        
        # Start date
        current_date = datetime.date(2025, 4, 1)
        balance = monthly_inflows * random.uniform(0.15, 0.3)
        starting_balance = balance
        
        transactions = []
        total_credits = 0
        total_debits = 0
        bounce_count = 0
        
        for month in range(12):
            month_inflow = monthly_inflows * random.uniform(0.85, 1.15)
            month_outflow = month_inflow * outflow_ratio
            
            credits_count = random.randint(8, 12)
            debits_count = random.randint(12, 18)
            
            # Generate credit values
            credit_vals = [month_inflow * random.uniform(0.05, 0.15) for _ in range(credits_count - 1)]
            credit_vals.append(month_inflow - sum(credit_vals))
            
            # Generate debit values
            debit_vals = [month_outflow * random.uniform(0.03, 0.1) for _ in range(debits_count - 2)]
            monthly_emi = financial_profile["interest_expense"] / 12 + (financial_profile["total_debt"] * 0.05 / 12)
            debit_vals.append(monthly_emi)
            debit_vals.append(month_outflow - sum(debit_vals))
            
            txn_pool = []
            
            # Credit counterparty concentration setup
            main_credit_party = None
            if is_fraud and fraud_type == "shell_company":
                # >45% credits come from a single shell company party
                main_credit_party = "Shell Apex Corp"
            
            # Add credits to pool
            for val in credit_vals:
                if main_credit_party and random.random() < 0.5:
                    party = main_credit_party
                else:
                    party = random.choice(self.PARTIES)
                    
                ref = f"{random.randint(100000, 999999)}"
                upi = f"pay@{party.lower().replace(' ', '')}"
                chq_no = f"{random.randint(100000, 999999):06d}"
                
                narr_tmpl = random.choice(self.CREDIT_NARRATIONS)
                narration = narr_tmpl.format(party=party, ref=ref, upi_id=upi, chq_no=chq_no)
                
                txn_pool.append({
                    "type": "CREDIT",
                    "amount": round(val, 2),
                    "narration": narration
                })
                
            # Add debits to pool
            for val in debit_vals:
                party = random.choice(self.PARTIES)
                ref = f"{random.randint(100000, 999999)}"
                upi = f"pay@{party.lower().replace(' ', '')}"
                chq_no = f"{random.randint(100000, 999999):06d}"
                
                narr_tmpl = random.choice(self.DEBIT_NARRATIONS)
                narration = narr_tmpl.format(party=party, ref=ref, upi_id=upi, chq_no=chq_no)
                
                # Benami siphoning: divert some debits to personal accounts
                if is_fraud and fraud_type == "benami_siphoning" and random.random() < 0.2:
                    personal_names = ["promoter_personal", "director_wife", "relative_account"]
                    narration = f"UPI DR / {random.choice(personal_names)}@ybl / PRIVATE_TRANSFER"
                
                txn_pool.append({
                    "type": "DEBIT",
                    "amount": round(val, 2),
                    "narration": narration
                })
                
            # Cheque Bounces
            num_txns = len(txn_pool)
            expected_bounces = round((num_txns * (bounce_rate / 100.0)))
            for _ in range(expected_bounces):
                chq_no = f"{random.randint(100000, 999999):06d}"
                narration = self.BOUNCE_NARRATION.format(chq_no=chq_no)
                txn_pool.append({
                    "type": "DEBIT",
                    "amount": 350.00,
                    "narration": narration
                })
                bounce_count += 1
                
            # Evergreening: Inject new loan disbursement followed by immediate EMI
            if is_fraud and fraud_type == "evergreening" and random.random() < 0.3:
                loan_disb = monthly_emi * random.uniform(1.2, 2.0)
                txn_pool.append({
                    "type": "CREDIT",
                    "amount": round(loan_disb, 2),
                    "narration": f"OD_DISBURSE / loan_disb_{random.randint(1000,9999)} / {bank_name.upper()}"
                })
                txn_pool.append({
                    "type": "DEBIT",
                    "amount": round(monthly_emi, 2),
                    "narration": f"CHQ CLG / {random.randint(100000,999999):06d} / EMI_PAYMENT_LOAN"
                })

            # Round-tripping (circular trading) injection: same-day or near same-day credits & debits
            if is_fraud and fraud_type in ["circular_trading", "shell_company"] and random.random() < 0.5:
                round_trip_val = month_inflow * random.uniform(0.15, 0.35)
                shell_party_1 = "Shell Apex Corp"
                shell_party_2 = "Delta Trading LLP"
                
                txn_pool.append({
                    "type": "CREDIT",
                    "amount": round(round_trip_val, 2),
                    "narration": f"RTGS CR / {shell_party_1} / SETTLE_REF_{random.randint(10000, 99999)}"
                })
                txn_pool.append({
                    "type": "DEBIT",
                    "amount": round(round_trip_val * random.uniform(0.985, 0.995), 2),
                    "narration": f"RTGS DR / {shell_party_2} / PAYOUT_REF_{random.randint(10000, 99999)}"
                })
                
            random.shuffle(txn_pool)
            for j, txn in enumerate(txn_pool):
                day_offset = int((j / len(txn_pool)) * 28) + 1
                txn_date = datetime.date(current_date.year, current_date.month, day_offset)
                
                if txn["type"] == "CREDIT":
                    balance += txn["amount"]
                    total_credits += txn["amount"]
                else:
                    balance -= txn["amount"]
                    total_debits += txn["amount"]
                    
                if balance < 0:
                    overdraft_credit = abs(balance) + random.uniform(5000, 20000)
                    transactions.append({
                        "date": txn_date.isoformat(),
                        "type": "CREDIT",
                        "amount": round(overdraft_credit, 2),
                        "narration": f"OD_FACILITY / DRAW / {bank_name.upper()}_CREDIT_IN",
                        "balance": round(balance + overdraft_credit, 2)
                    })
                    balance += overdraft_credit
                    total_credits += overdraft_credit
                    
                transactions.append({
                    "date": txn_date.isoformat(),
                    "type": txn["type"],
                    "amount": txn["amount"],
                    "narration": txn["narration"],
                    "balance": round(balance, 2)
                })
                
            if current_date.month == 12:
                current_date = datetime.date(current_date.year + 1, 1, 1)
            else:
                current_date = datetime.date(current_date.year, current_date.month + 1, 1)

        monthly_end_balances = []
        for m in range(1, 13):
            month_txns = [t for t in transactions if int(t["date"].split("-")[1]) == m]
            if month_txns:
                monthly_end_balances.append(month_txns[-1]["balance"])
        avg_monthly_balance = sum(monthly_end_balances) / len(monthly_end_balances) if monthly_end_balances else balance

        return {
            "bank_name": bank_name,
            "account_number": account_no,
            "ifsc": ifsc,
            "transactions": transactions,
            "starting_balance": round(starting_balance, 2),
            "ending_balance": round(balance, 2),
            "total_credits": round(total_credits, 2),
            "total_debits": round(total_debits, 2),
            "avg_monthly_balance": round(avg_monthly_balance, 2),
            "bounce_count": bounce_count
        }
