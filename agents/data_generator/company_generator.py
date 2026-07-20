import random
import datetime
from sector_profiles import SECTOR_PROFILES
from fraud_simulator import FraudSimulator

class CompanyGenerator:
    """
    Generates realistic Indian company profiles with structurally valid identifiers:
    - CIN (Corporate Identification Number)
    - PAN (Permanent Account Number)
    - GSTIN (Goods and Services Tax Identification Number)
    """

    STATES = [
        {"name": "Maharashtra", "code": "27", "abbr": "MH", "risk_weight": 0.9},
        {"name": "Delhi", "code": "07", "abbr": "DL", "risk_weight": 0.8},
        {"name": "Karnataka", "code": "29", "abbr": "KA", "risk_weight": 0.75},
        {"name": "Tamil Nadu", "code": "33", "abbr": "TN", "risk_weight": 0.85},
        {"name": "Gujarat", "code": "24", "abbr": "GJ", "risk_weight": 0.7},
        {"name": "West Bengal", "code": "19", "abbr": "WB", "risk_weight": 1.4},
        {"name": "Uttar Pradesh", "code": "09", "abbr": "UP", "risk_weight": 1.3},
        {"name": "Telangana", "code": "36", "abbr": "TS", "risk_weight": 0.8},
        {"name": "Haryana", "code": "06", "abbr": "HR", "risk_weight": 1.0}
    ]

    INDUSTRIES = [{"sector": sector, "nic": prof["nic"]} for sector, prof in SECTOR_PROFILES.items()]

    COMPANY_NAME_NOUNS = [
        "Apex", "Shivam", "Vanguard", "Delta", "Radhe", "Bhaskar", "Zenith", "Sterling", 
        "Karan", "Ambika", "Aditya", "Infinity", "Matrix", "Kalyani", "Surya", "Ganesh", 
        "Hindustan", "Bharat", "Navrachana", "Tejas", "Urja", "Arogya", "Vidya"
    ]
    COMPANY_NAME_SECTORS = [
        "Textiles", "Metals", "Logistics", "Enterprises", "Industries", "Solutions", 
        "Builders", "Chemicals", "Foods", "Healthcare", "Pharma", "Automotive", 
        "Energy", "Renewables", "Infrastructure", "Power", "Retail", "Infotech"
    ]
    COMPANY_NAME_POSTFIX = ["Private Limited", "LLP", "Partnership Firm"]

    def __init__(self):
        self.generated_names = set()

    def generate_pan(self, entity_type: str, company_name: str) -> str:
        """
        Generates structurally valid 10-character Indian PAN.
        Format: 5 letters, 4 digits, 1 letter
        4th char: C (Company), F (Firm), P (Individual/Promoter)
        5th char: First character of entity's name
        """
        first_three = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=3))
        
        if entity_type == "Private Limited":
            fourth = "C"
        elif entity_type == "LLP" or entity_type == "Partnership Firm":
            fourth = "F"
        else:
            fourth = "P"
            
        clean_name = "".join(filter(str.isalnum, company_name.upper())).strip()
        fifth = clean_name[0] if clean_name else "A"
        if not fifth.isalpha():
            fifth = "A"
            
        four_digits = "".join(random.choices("0123456789", k=4))
        last_char = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        
        return f"{first_three}{fourth}{fifth}{four_digits}{last_char}"

    def generate_cin(self, state_abbr: str, nic_code: str, inc_year: int) -> str:
        """
        Generates a valid 21-character Corporate Identification Number (CIN).
        Format: L/U (1) + NIC (5) + State (2) + Year (4) + PTC/PLC/NPL (3) + Reg No (6)
        """
        listing_status = random.choice(["U", "L"])
        ownership_type = random.choice(["PTC", "PLC"])
        reg_no = f"{random.randint(1, 999999):06d}"
        
        return f"{listing_status}{nic_code}{state_abbr}{inc_year}{ownership_type}{reg_no}"

    def generate_gstin(self, state_code: str, pan: str) -> str:
        """
        Generates valid 15-character GSTIN.
        Format: 2-digit state code + 10-char PAN + 1 entity code + Z + 1 checksum char
        """
        entity_code = random.choice("123456789")
        checksum = random.choice("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        return f"{state_code}{pan}{entity_code}Z{checksum}"

    def generate_company(self, is_fraudulent: bool = False, fraud_type: str = None) -> dict:
        """Generates a single company profile."""
        state = random.choice(self.STATES)
        industry = random.choice(self.INDUSTRIES)
        
        while True:
            noun = random.choice(self.COMPANY_NAME_NOUNS)
            sector = random.choice(self.COMPANY_NAME_SECTORS)
            postfix = random.choice(self.COMPANY_NAME_POSTFIX)
            company_name = f"{noun} {sector} {postfix}"
            if company_name not in self.generated_names:
                self.generated_names.add(company_name)
                break
            # If set gets large, inject random digits to prevent infinite loop
            if len(self.generated_names) > 500:
                company_name = f"{noun} {sector} {random.randint(100, 999)} {postfix}"
                self.generated_names.add(company_name)
                break

        
        # Vintage stratification: peak at 5-10 years, long tail to 20+ years
        current_year = 2026
        age_cohorts = [random.randint(1, 4), random.randint(5, 10), random.randint(11, 20)]
        age = random.choices(age_cohorts, weights=[0.2, 0.6, 0.2])[0]
        inc_year = current_year - age
        inc_date = datetime.date(inc_year, random.randint(1, 12), random.randint(1, 28)).isoformat()
        
        pan = self.generate_pan(postfix, company_name)
        
        cin = ""
        if postfix == "Private Limited":
            cin = self.generate_cin(state["abbr"], industry["nic"], inc_year)
            
        gstin = self.generate_gstin(state["code"], pan)
        
        # Get typical turnover range from sector profiles
        sector_prof = SECTOR_PROFILES[industry["sector"]]
        turnover_range = sector_prof["typical_turnover_range"]
        
        turnover_class = random.choices(["Micro", "Small", "Medium"], weights=[0.7, 0.25, 0.05])[0]
        if turnover_class == "Micro":
            turnover = random.uniform(20_00_000, min(5_00_00_000, turnover_range[1]))
            employees = random.randint(5, 30)
        elif turnover_class == "Small":
            turnover = random.uniform(max(5_00_00_000, turnover_range[0]), min(50_00_00_000, turnover_range[1]))
            employees = random.randint(30, 150)
        else:
            turnover = random.uniform(max(50_00_00_000, turnover_range[0]), min(150_00_00_000, turnover_range[1]))
            employees = random.randint(150, 500)
            
        # Handle fraud assignment
        if is_fraudulent and not fraud_type:
            fraud_type = FraudSimulator.get_archetype_for_sector(industry["sector"], sector_prof)

        return {
            "company_name": company_name,
            "entity_type": postfix,
            "cin": cin if cin else "N/A",
            "pan": pan,
            "gstin": gstin,
            "industry_sector": industry["sector"],
            "incorporation_date": inc_date,
            "registered_state": state["name"],
            "state_code": state["code"],
            "turnover_class": turnover_class,
            "target_turnover": turnover,
            "employee_count": employees,
            "is_fraudulent": is_fraudulent,
            "is_sophisticated": is_fraudulent and random.random() < 0.3,
            "fraud_type": fraud_type
        }

    def generate_batch(self, count: int, fraud_rate: float = 0.1) -> list:
        companies = []
        # Calculate base average NPA rate for normalization
        avg_npa = sum(p["npa_rate"] for p in SECTOR_PROFILES.values()) / len(SECTOR_PROFILES)
        
        for _ in range(count):
            # Select state and industry first to apply weighted fraud rate
            state = random.choice(self.STATES)
            industry = random.choice(self.INDUSTRIES)
            
            sector_npa = SECTOR_PROFILES[industry["sector"]]["npa_rate"]
            # Calibrate probability based on industry NPA rate and state risk weighting
            calibrated_fraud_prob = fraud_rate * (sector_npa / avg_npa) * state["risk_weight"]
            
            is_fraud = random.random() < calibrated_fraud_prob
            is_early_stage_fraud = False
            if not is_fraud and random.random() < 0.04:
                is_early_stage_fraud = True
            
            company = self.generate_company(is_fraud or is_early_stage_fraud)
            company["is_early_stage_fraud"] = is_early_stage_fraud
            if is_early_stage_fraud:
                company["is_fraudulent"] = False # observed as legitimate
                
            companies.append(company)
            
        return companies
