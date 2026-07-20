import os
import json
import csv
import argparse
import random
import shutil

from company_generator import CompanyGenerator
from financial_generator import FinancialProfileGenerator
from gstr_generator import GSTRGenerator
from bank_generator import BankStatementGenerator
from director_generator import DirectorNetworkGenerator
from pdf_renderer import PDFRenderer
from dataset_validator import DatasetValidator

class TrinetraDatasetGenerator:
    """
    Master generator class that orchestrates the generation of a complete credit underwriting dataset:
    - Company Profiles (JSON)
    - Financial Statements & Ratios (JSON)
    - GSTR Filings (JSON + PDFs)
    - Bank Transactions (JSON + PDFs)
    - Director Graph (JSON)
    - Ground Truth Labels (CSV)
    """

    def __init__(self, output_dir: str = "./synthetic_data", regime: str = "neutral"):
        self.output_dir = output_dir
        self.regime = regime
        self.company_gen = CompanyGenerator()
        self.financial_gen = FinancialProfileGenerator(regime=regime)
        self.gstr_gen = GSTRGenerator()
        self.bank_gen = BankStatementGenerator()
        self.director_gen = DirectorNetworkGenerator()
        self.pdf_renderer = PDFRenderer()

    def clean_output_dir(self):
        """Cleans existing synthetic data to start fresh."""
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(os.path.join(self.output_dir, "companies"), exist_ok=True)
        os.makedirs(os.path.join(self.output_dir, "financials"), exist_ok=True)
        os.makedirs(os.path.join(self.output_dir, "documents"), exist_ok=True)

    def generate(self, n_companies: int = 10000, fraud_rate: float = 0.15, generate_pdfs: bool = False):
        """Orchestrates generation of all profiles, statements, and PDFs."""
        print(f"[*] Initializing dataset generation for {n_companies} companies (regime: {self.regime}, target fraud rate: {fraud_rate * 100}%)...")
        self.clean_output_dir()
        
        # 1. Generate companies
        companies = self.company_gen.generate_batch(n_companies, fraud_rate)
        
        # 2. Generate director network
        print("[*] Generating corporate director network...")
        director_data = self.director_gen.generate(companies, fraud_rate)
        
        # Save director graph
        with open(os.path.join(self.output_dir, "director_network.json"), "w") as f:
            json.dump(director_data, f, indent=4)

        # 3. Process each company
        labels = []
        for idx, company in enumerate(companies):
            comp_id = f"company_{idx+1:05d}"
            comp_name = company["company_name"]
            is_fraud = company["is_fraudulent"]
            
            if (idx + 1) % 100 == 0 or idx < 10 or n_companies <= 100:
                print(f"[{idx+1}/{n_companies}] Generating profiles for {comp_name} (ID: {comp_id})...")
            
            # Save company profile
            company["company_id"] = comp_id
            company["directors"] = [d["name"] for d in director_data["company_directors"][comp_name]]
            
            comp_file = os.path.join(self.output_dir, "companies", f"{comp_id}.json")
            with open(comp_file, "w") as f:
                json.dump(company, f, indent=4)
                
            # Generate and save financials
            financials = self.financial_gen.generate(company)
            financials["company_id"] = comp_id
            
            fin_file = os.path.join(self.output_dir, "financials", f"{comp_id}_financials.json")
            with open(fin_file, "w") as f:
                json.dump(financials, f, indent=4)
                
            # Generate and save GSTR
            gstr = self.gstr_gen.generate(company, financials)
            gstr["company_id"] = comp_id
            
            gstr_file = os.path.join(self.output_dir, "financials", f"{comp_id}_gstr.json")
            with open(gstr_file, "w") as f:
                json.dump(gstr, f, indent=4)
                
            # Generate and save Bank Statement
            bank = self.bank_gen.generate(company, financials)
            bank["company_id"] = comp_id
            
            bank_file = os.path.join(self.output_dir, "financials", f"{comp_id}_bank.json")
            with open(bank_file, "w") as f:
                json.dump(bank, f, indent=4)
                
            # Write ground truth labels
            is_early_stage_fraud = company.get("is_early_stage_fraud", False)
            true_fraud_state = is_fraud or is_early_stage_fraud
            
            if is_early_stage_fraud:
                pd_target = random.uniform(0.40, 0.75)
            elif is_fraud:
                if company.get("is_sophisticated", False):
                    pd_target = random.uniform(0.50, 0.85)
                else:
                    pd_target = random.uniform(0.85, 0.99)
            else:
                pd_target = random.uniform(0.01, 0.35)
                
            labels.append({
                "company_id": comp_id,
                "company_name": comp_name,
                "is_fraudulent": 1 if is_fraud else 0,
                "is_early_stage_fraud": 1 if is_early_stage_fraud else 0,
                "true_fraud_state": 1 if true_fraud_state else 0,
                "pd_target": float(round(pd_target, 4)),
                "fraud_type": company.get("fraud_type") or "None",
                # Add key features for quick reference
                "cibil_score": financials["cibil_score"],
                "dscr": financials["dscr"],
                "gst_discrepancy_pct": financials["gst_discrepancy_pct"],
                "bank_divergence_pct": financials["bank_divergence_pct"],
                "bounce_rate": financials["bounce_rate"]
            })
            
            # 4. Render PDFs if requested (usually disabled for scale > 100)
            if generate_pdfs:
                comp_doc_dir = os.path.join(self.output_dir, "documents", comp_id)
                os.makedirs(comp_doc_dir, exist_ok=True)
                self.pdf_renderer.render_bank_statement(company, bank, os.path.join(comp_doc_dir, "bank_statement.pdf"))
                self.pdf_renderer.render_gstr_3b(company, gstr, os.path.join(comp_doc_dir, "gstr_3b.pdf"))
                self.pdf_renderer.render_itr(company, financials, os.path.join(comp_doc_dir, "itr_6.pdf"))
                self.pdf_renderer.render_annual_report(company, financials, os.path.join(comp_doc_dir, "annual_report.pdf"))
                
        # Save ground truth labels CSV
        labels_file = os.path.join(self.output_dir, "ground_truth_labels.csv")
        with open(labels_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=labels[0].keys())
            writer.writeheader()
            writer.writerows(labels)
            
        # Run Validation
        validator = DatasetValidator(self.output_dir)
        val_report = validator.validate()
            
        # Save overall generation metadata
        metadata = {
            "n_companies": n_companies,
            "fraud_rate": fraud_rate,
            "regime": self.regime,
            "timestamp": os.path.getmtime(labels_file),
            "validation_status": val_report["status"]
        }
        with open(os.path.join(self.output_dir, "dataset_metadata.json"), "w") as f:
            json.dump(metadata, f, indent=4)
            
        print(f"\n[+] Success! Synthetic dataset generated at: {self.output_dir}")
        print(f"    - Validation Status: {val_report['status']}")
        print(f"    - Labels: ground_truth_labels.csv")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trinetra High-Fidelity Synthetic Dataset Generator")
    parser.add_argument("--num-companies", type=int, default=10000, help="Number of company profiles to generate")
    parser.add_argument("--fraud-rate", type=float, default=0.15, help="Rate of fraudulent/shell companies (0.0 to 1.0)")
    parser.add_argument("--no-pdfs", action="store_true", default=True, help="Disable generating PDF documents (faster JSON-only generation)")
    parser.add_argument("--generate-pdfs", action="store_true", help="Explicitly enable generating PDF documents")
    parser.add_argument("--regime", type=str, default="neutral", choices=["neutral", "expansion", "contraction"], help="Macro-economic regime")
    parser.add_argument("--output", type=str, default="./synthetic_data", help="Output directory path")
    
    args = parser.parse_args()
    
    # pdf generation defaults to False unless generate_pdfs is explicitly requested
    gen_pdfs = args.generate_pdfs and not args.no_pdfs
    
    generator = TrinetraDatasetGenerator(output_dir=args.output, regime=args.regime)
    generator.generate(
        n_companies=args.num_companies,
        fraud_rate=args.fraud_rate,
        generate_pdfs=gen_pdfs
    )
