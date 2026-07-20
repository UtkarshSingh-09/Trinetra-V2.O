import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

class PDFRenderer:
    """
    Renders generated financial data into high-fidelity PDF documents:
    1. Bank Statement (similar to major Indian banks like HDFC/ICICI)
    2. GSTR-3B Monthly Return Form
    3. ITR-6 Corporate Income Tax Return Summary
    """

    def __init__(self):
        self.styles = getSampleStyleSheet()
        
        # Define some custom styles to make PDFs look clean and premium
        self.title_style = ParagraphStyle(
            'DocTitle',
            parent=self.styles['Heading1'],
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#1e293b"), # Slate 800
            spaceAfter=12
        )
        
        self.subtitle_style = ParagraphStyle(
            'DocSubTitle',
            parent=self.styles['Normal'],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#475569"), # Slate 600
            spaceAfter=15
        )

        self.header_style = ParagraphStyle(
            'SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#0f172a"), # Slate 900
            spaceBefore=10,
            spaceAfter=8,
            keepWithNext=True
        )

        self.body_style = ParagraphStyle(
            'BodyTextCustom',
            parent=self.styles['BodyText'],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#334155") # Slate 700
        )
        
        self.body_bold_style = ParagraphStyle(
            'BodyTextBold',
            parent=self.body_style,
            fontName="Helvetica-Bold"
        )

        self.table_header_style = ParagraphStyle(
            'TableHeader',
            parent=self.styles['Normal'],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.white
        )

        self.table_cell_style = ParagraphStyle(
            'TableCell',
            parent=self.styles['Normal'],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#334155")
        )

        self.table_cell_right = ParagraphStyle(
            'TableCellRight',
            parent=self.table_cell_style,
            alignment=2 # Right align
        )

    def render_bank_statement(self, company_profile: dict, bank_data: dict, filepath: str):
        """Generates a professional-looking Bank Statement PDF."""
        doc = SimpleDocTemplate(filepath, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
        story = []
        
        # 1. Header Table
        header_data = [
            [
                Paragraph(f"<b>{bank_data['bank_name']}</b><br/>MSME Corporate Branch", self.title_style),
                Paragraph(f"<b>STATEMENT OF ACCOUNT</b><br/>Period: 01-Apr-2025 to 31-Mar-2026", self.subtitle_style)
            ]
        ]
        t1 = Table(header_data, colWidths=[270, 270])
        t1.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ]))
        story.append(t1)
        story.append(Spacer(1, 15))
        
        # 2. Account Information Table
        info_data = [
            [
                Paragraph(f"<b>Account Holder:</b> {company_profile['company_name']}<br/>"
                          f"<b>Address:</b> 402, Trade Tower, Bandra Kurla Complex,<br/>"
                          f"Mumbai, Maharashtra - 400051", self.body_style),
                Paragraph(f"<b>Account Number:</b> {bank_data['account_number']}<br/>"
                          f"<b>IFSC:</b> {bank_data['ifsc']}<br/>"
                          f"<b>Account Type:</b> Corporate Current Account", self.body_style)
            ]
        ]
        t2 = Table(info_data, colWidths=[270, 270])
        t2.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#e2e8f0")),
            ('PADDING', (0,0), (-1,-1), 8),
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ]))
        story.append(t2)
        story.append(Spacer(1, 15))
        
        # 3. Summary Table
        summary_data = [
            [
                Paragraph("<b>Starting Balance</b>", self.body_style),
                Paragraph(f"₹{bank_data['starting_balance']:,.2f}", self.body_bold_style),
                Paragraph("<b>Total Deposits (Cr)</b>", self.body_style),
                Paragraph(f"₹{bank_data['total_credits']:,.2f}", self.body_bold_style)
            ],
            [
                Paragraph("<b>Ending Balance</b>", self.body_style),
                Paragraph(f"₹{bank_data['ending_balance']:,.2f}", self.body_bold_style),
                Paragraph("<b>Total Withdrawals (Dr)</b>", self.body_style),
                Paragraph(f"₹{bank_data['total_debits']:,.2f}", self.body_bold_style)
            ],
            [
                Paragraph("<b>Avg Monthly Balance (AMB)</b>", self.body_style),
                Paragraph(f"₹{bank_data['avg_monthly_balance']:,.2f}", self.body_bold_style),
                Paragraph("<b>Cheque Bounces</b>", self.body_style),
                Paragraph(f"{bank_data['bounce_count']}", self.body_bold_style)
            ]
        ]
        t3 = Table(summary_data, colWidths=[150, 120, 150, 120])
        t3.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ('PADDING', (0,0), (-1,-1), 6),
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#f1f5f9")),
            ('BACKGROUND', (2,0), (2,-1), colors.HexColor("#f1f5f9")),
        ]))
        story.append(t3)
        story.append(Spacer(1, 20))
        
        # 4. Transactions List Table (Top 50 to keep PDF page sizes reasonable, or all)
        story.append(Paragraph("<b>TRANSACTION HISTORY</b>", self.header_style))
        
        tx_headers = [
            Paragraph("Date", self.table_header_style),
            Paragraph("Narration", self.table_header_style),
            Paragraph("Type", self.table_header_style),
            Paragraph("Amount (₹)", self.table_header_style),
            Paragraph("Balance (₹)", self.table_header_style)
        ]
        
        tx_rows = [tx_headers]
        for tx in bank_data['transactions'][:80]: # Limit to 80 transactions for page limit
            tx_rows.append([
                Paragraph(tx['date'], self.table_cell_style),
                Paragraph(tx['narration'], self.table_cell_style),
                Paragraph(tx['type'], self.table_cell_style),
                Paragraph(f"{tx['amount']:,.2f}", self.table_cell_right),
                Paragraph(f"{tx['balance']:,.2f}", self.table_cell_right)
            ])
            
        t_tx = Table(tx_rows, colWidths=[65, 245, 45, 90, 95])
        
        # Color transaction types
        t_style = [
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1e293b")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('PADDING', (0,0), (-1,-1), 4),
        ]
        
        # Highlight bounces or alternate rows
        for idx in range(1, len(tx_rows)):
            narration_text = bank_data['transactions'][idx-1]['narration']
            if "INSUFFICIENT FUNDS" in narration_text:
                t_style.append(('BACKGROUND', (0, idx), (-1, idx), colors.HexColor("#fee2e2"))) # Light red
            elif idx % 2 == 0:
                t_style.append(('BACKGROUND', (0, idx), (-1, idx), colors.HexColor("#f8fafc")))
                
        t_tx.setStyle(TableStyle(t_style))
        story.append(t_tx)
        
        doc.build(story)

    def render_gstr_3b(self, company_profile: dict, gstr_data: dict, filepath: str):
        """Generates a professional-looking GSTR-3B Monthly Return Form summary."""
        doc = SimpleDocTemplate(filepath, pagesize=letter, leftMargin=45, rightMargin=45, topMargin=45, bottomMargin=45)
        story = []
        
        story.append(Paragraph("<b>FORM GSTR-3B</b>", self.title_style))
        story.append(Paragraph("<b>[See Rule 61(5)]</b><br/>"
                               "Self-Declared Summary of Outward and Inward Supplies", self.subtitle_style))
        story.append(Spacer(1, 10))
        
        # GST registration info
        reg_info = [
            [Paragraph("<b>GSTIN:</b>", self.body_bold_style), Paragraph(company_profile['gstin'], self.body_style),
             Paragraph("<b>Legal Name:</b>", self.body_bold_style), Paragraph(company_profile['company_name'], self.body_style)],
            [Paragraph("<b>Filing Mode:</b>", self.body_bold_style), Paragraph("Monthly", self.body_style),
             Paragraph("<b>Financial Year:</b>", self.body_bold_style), Paragraph("2025-26", self.body_style)]
        ]
        t_reg = Table(reg_info, colWidths=[100, 160, 100, 160])
        t_reg.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ('PADDING', (0,0), (-1,-1), 6),
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ]))
        story.append(t_reg)
        story.append(Spacer(1, 15))
        
        story.append(Paragraph("<b>1. Details of Outward Supplies and Inward Supplies Liable to Reverse Charge</b>", self.header_style))
        
        outward_headers = ["Nature of Supplies", "Total Taxable Value (₹)", "Integrated Tax (₹)", "Central Tax (₹)", "State/UT Tax (₹)"]
        outward_rows = [
            [Paragraph(f"<b>{col}</b>", self.table_cell_style) for col in outward_headers]
        ]
        
        # Summarize total sales from GSTR data
        total_taxable_sales = gstr_data['total_gst_turnover']
        total_igst = sum(r['gstr_3b']['integrated_tax_sales'] for r in gstr_data['gstr_records'])
        total_cgst = sum(r['gstr_3b']['central_tax_sales'] for r in gstr_data['gstr_records'])
        total_sgst = sum(r['gstr_3b']['state_tax_sales'] for r in gstr_data['gstr_records'])
        
        outward_rows.append([
            Paragraph("(a) Outward taxable supplies (other than zero rated, nil rated and exempted)", self.table_cell_style),
            Paragraph(f"{total_taxable_sales:,.2f}", self.table_cell_right),
            Paragraph(f"{total_igst:,.2f}", self.table_cell_right),
            Paragraph(f"{total_cgst:,.2f}", self.table_cell_right),
            Paragraph(f"{total_sgst:,.2f}", self.table_cell_right)
        ])
        
        t_out = Table(outward_rows, colWidths=[200, 80, 80, 80, 80])
        t_out.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ('PADDING', (0,0), (-1,-1), 6),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
        ]))
        story.append(t_out)
        story.append(Spacer(1, 15))
        
        story.append(Paragraph("<b>2. Details of Eligible Input Tax Credit (ITC)</b>", self.header_style))
        
        itc_headers = ["ITC Details", "Integrated Tax (₹)", "Central Tax (₹)", "State/UT Tax (₹)", "Total (₹)"]
        itc_rows = [
            [Paragraph(f"<b>{col}</b>", self.table_cell_style) for col in itc_headers]
        ]
        
        total_igst_itc = sum(r['gstr_3b']['itc_claimed']['igst'] for r in gstr_data['gstr_records'])
        total_cgst_itc = sum(r['gstr_3b']['itc_claimed']['cgst'] for r in gstr_data['gstr_records'])
        total_sgst_itc = sum(r['gstr_3b']['itc_claimed']['sgst'] for r in gstr_data['gstr_records'])
        total_itc = gstr_data['total_3b_itc']
        
        itc_rows.append([
            Paragraph("<b>(A) ITC Available (whether in full or part)</b>", self.table_cell_style),
            Paragraph("", self.table_cell_style),
            Paragraph("", self.table_cell_style),
            Paragraph("", self.table_cell_style),
            Paragraph("", self.table_cell_style)
        ])
        itc_rows.append([
            Paragraph("  (1) Import of goods", self.table_cell_style),
            Paragraph("0.00", self.table_cell_right),
            Paragraph("0.00", self.table_cell_right),
            Paragraph("0.00", self.table_cell_right),
            Paragraph("0.00", self.table_cell_right)
        ])
        itc_rows.append([
            Paragraph("  (2) All other ITC (purchases, services)", self.table_cell_style),
            Paragraph(f"{total_igst_itc:,.2f}", self.table_cell_right),
            Paragraph(f"{total_cgst_itc:,.2f}", self.table_cell_right),
            Paragraph(f"{total_sgst_itc:,.2f}", self.table_cell_right),
            Paragraph(f"{total_itc:,.2f}", self.table_cell_right)
        ])
        
        t_itc = Table(itc_rows, colWidths=[200, 80, 80, 80, 80])
        t_itc.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ('PADDING', (0,0), (-1,-1), 6),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
        ]))
        story.append(t_itc)
        story.append(Spacer(1, 15))
        
        story.append(Paragraph("<b>3. Monthly Returns Breakdown (Last 12 Months)</b>", self.header_style))
        
        breakdown_headers = ["Month", "Taxable Sales (₹)", "ITC Claimed (3B) (₹)", "ITC Auto-Drafted (2B) (₹)", "Discrepancy (₹)", "Discrepancy %"]
        breakdown_rows = [
            [Paragraph(f"<b>{col}</b>", self.table_header_style) for col in breakdown_headers]
        ]
        
        for r in gstr_data['gstr_records']:
            disc_val = r['gstr_3b']['itc_claimed']['total'] - r['gstr_2b']['itc_available']['total']
            breakdown_rows.append([
                Paragraph(r['month'], self.table_cell_style),
                Paragraph(f"{r['gstr_3b']['outward_taxable_supplies']:,.2f}", self.table_cell_right),
                Paragraph(f"{r['gstr_3b']['itc_claimed']['total']:,.2f}", self.table_cell_right),
                Paragraph(f"{r['gstr_2b']['itc_available']['total']:,.2f}", self.table_cell_right),
                Paragraph(f"{disc_val:,.2f}", self.table_cell_right),
                Paragraph(f"{r['discrepancy_pct']}%", self.table_cell_right)
            ])
            
        t_bd = Table(breakdown_rows, colWidths=[80, 95, 95, 95, 80, 75])
        
        t_bd_style = [
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1e293b")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('PADDING', (0,0), (-1,-1), 4),
        ]
        
        for idx in range(1, len(breakdown_rows)):
            disc_pct = gstr_data['gstr_records'][idx-1]['discrepancy_pct']
            if disc_pct > 10:
                t_bd_style.append(('BACKGROUND', (0, idx), (-1, idx), colors.HexColor("#fee2e2")))
            elif idx % 2 == 0:
                t_bd_style.append(('BACKGROUND', (0, idx), (-1, idx), colors.HexColor("#f8fafc")))
                
        t_bd.setStyle(TableStyle(t_bd_style))
        story.append(t_bd)
        
        doc.build(story)

    def render_itr(self, company_profile: dict, financial_profile: dict, filepath: str):
        """Generates a professional-looking Indian ITR-6 Form Summary PDF."""
        doc = SimpleDocTemplate(filepath, pagesize=letter, leftMargin=45, rightMargin=45, topMargin=45, bottomMargin=45)
        story = []
        
        story.append(Paragraph("<b>INDIAN INCOME TAX RETURN</b>", self.title_style))
        story.append(Paragraph("<b>FORM ITR-6</b><br/>"
                               "For Companies other than companies claiming exemption under Section 11", self.subtitle_style))
        story.append(Spacer(1, 10))
        
        # General company details
        comp_info = [
            [Paragraph("<b>Company Name:</b>", self.body_bold_style), Paragraph(company_profile['company_name'], self.body_style),
             Paragraph("<b>PAN:</b>", self.body_bold_style), Paragraph(company_profile['pan'], self.body_style)],
            [Paragraph("<b>CIN:</b>", self.body_bold_style), Paragraph(company_profile['cin'], self.body_style),
             Paragraph("<b>Assessment Year:</b>", self.body_bold_style), Paragraph("2026-27 (FY 2025-26)", self.body_style)]
        ]
        t_comp = Table(comp_info, colWidths=[100, 160, 100, 160])
        t_comp.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ('PADDING', (0,0), (-1,-1), 6),
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ]))
        story.append(t_comp)
        story.append(Spacer(1, 15))
        
        story.append(Paragraph("<b>Part A-P&L: Profit and Loss Account Summary</b>", self.header_style))
        
        pl_headers = ["Financial Metrics", "FY 2023-24 (₹)", "FY 2024-25 (₹)", "FY 2025-26 (₹)"]
        pl_rows = [
            [Paragraph(f"<b>{col}</b>", self.table_cell_style) for col in pl_headers]
        ]
        
        revs = financial_profile['revenue_annual']
        ebitdas = financial_profile['ebitda_annual']
        nps = financial_profile['net_profit_annual']
        
        pl_rows.append([
            Paragraph("Revenue from Operations (Turnover)", self.body_style),
            Paragraph(f"{revs[0]:,.2f}", self.table_cell_right),
            Paragraph(f"{revs[1]:,.2f}", self.table_cell_right),
            Paragraph(f"{revs[2]:,.2f}", self.table_cell_right),
        ])
        pl_rows.append([
            Paragraph("EBITDA", self.body_style),
            Paragraph(f"{ebitdas[0]:,.2f}", self.table_cell_right),
            Paragraph(f"{ebitdas[1]:,.2f}", self.table_cell_right),
            Paragraph(f"{ebitdas[2]:,.2f}", self.table_cell_right),
        ])
        pl_rows.append([
            Paragraph("Interest Expenses", self.body_style),
            Paragraph(f"{(financial_profile['interest_expense']*0.8):,.2f}", self.table_cell_right),
            Paragraph(f"{(financial_profile['interest_expense']*0.9):,.2f}", self.table_cell_right),
            Paragraph(f"{financial_profile['interest_expense']:,.2f}", self.table_cell_right),
        ])
        pl_rows.append([
            Paragraph("Net Profit After Tax (PAT)", self.body_bold_style),
            Paragraph(f"{nps[0]:,.2f}", self.table_cell_right),
            Paragraph(f"{nps[1]:,.2f}", self.table_cell_right),
            Paragraph(f"{nps[2]:,.2f}", self.table_cell_right),
        ])
        
        t_pl = Table(pl_rows, colWidths=[200, 105, 105, 110])
        t_pl.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ('PADDING', (0,0), (-1,-1), 6),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
        ]))
        story.append(t_pl)
        story.append(Spacer(1, 15))
        
        story.append(Paragraph("<b>Part A-BS: Balance Sheet Summary (As of 31st March 2026)</b>", self.header_style))
        
        bs_data = [
            [Paragraph("<b>Liabilities</b>", self.table_cell_style), Paragraph("<b>Amount (₹)</b>", self.table_cell_style),
             Paragraph("<b>Assets</b>", self.table_cell_style), Paragraph("<b>Amount (₹)</b>", self.table_cell_style)],
            [Paragraph("Share Capital", self.body_style), Paragraph(f"{financial_profile['share_capital']:,.2f}", self.table_cell_right),
             Paragraph("Non-Current Assets (Fixed Assets)", self.body_style), Paragraph(f"{(financial_profile['net_worth']*1.1):,.2f}", self.table_cell_right)],
            [Paragraph("Reserves and Surplus", self.body_style), Paragraph(f"{(financial_profile['net_worth'] - financial_profile['share_capital']):,.2f}", self.table_cell_right),
             Paragraph("Current Assets", self.body_style), Paragraph(f"{financial_profile['current_assets']:,.2f}", self.table_cell_right)],
            [Paragraph("Long-term Borrowings (Debt)", self.body_style), Paragraph(f"{(financial_profile['total_debt']*0.6):,.2f}", self.table_cell_right),
             Paragraph("Inventories", self.body_style), Paragraph(f"{(financial_profile['current_assets']*0.35):,.2f}", self.table_cell_right)],
            [Paragraph("Current Liabilities", self.body_style), Paragraph(f"{financial_profile['current_liabilities']:,.2f}", self.table_cell_right),
             Paragraph("Trade Receivables (Sundry Debtors)", self.body_style), Paragraph(f"{(financial_profile['current_assets']*0.45):,.2f}", self.table_cell_right)],
            [Paragraph("<b>Total Equity & Liabilities</b>", self.body_bold_style), Paragraph(f"{(financial_profile['net_worth'] + financial_profile['total_debt'] + financial_profile['current_liabilities']):,.2f}", self.table_cell_right),
             Paragraph("<b>Total Assets</b>", self.body_bold_style), Paragraph(f"{(financial_profile['net_worth']*1.1 + financial_profile['current_assets']):,.2f}", self.table_cell_right)]
        ]
        
        t_bs = Table(bs_data, colWidths=[150, 110, 150, 110])
        t_bs.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ('PADDING', (0,0), (-1,-1), 6),
            ('BACKGROUND', (0,0), (1,0), colors.HexColor("#f1f5f9")),
            ('BACKGROUND', (2,0), (3,0), colors.HexColor("#f1f5f9")),
        ]))
        story.append(t_bs)
        
        doc.build(story)

    def render_annual_report(self, company_profile: dict, financial_profile: dict, filepath: str):
        """Generates a professional-looking corporate Annual Report PDF."""
        doc = SimpleDocTemplate(filepath, pagesize=letter, leftMargin=45, rightMargin=45, topMargin=45, bottomMargin=45)
        story = []
        
        # Title
        story.append(Paragraph(f"<b>ANNUAL REPORT 2025-26</b>", self.title_style))
        story.append(Paragraph(f"<b>{company_profile['company_name']}</b><br/>"
                               f"CIN: {company_profile['cin']} | PAN: {company_profile['pan']}", self.subtitle_style))
        story.append(Spacer(1, 15))
        
        # Director Network Overview
        story.append(Paragraph("<b>1. Board of Directors & Corporate Details</b>", self.header_style))
        directors_str = ", ".join(company_profile.get("directors", ["Not Disclosed"]))
        details_data = [
            [Paragraph("<b>Registered Office:</b>", self.body_bold_style), Paragraph("402, Trade Tower, BKC, Mumbai - 400051", self.body_style)],
            [Paragraph("<b>Board of Directors:</b>", self.body_bold_style), Paragraph(directors_str, self.body_style)],
            [Paragraph("<b>Industry Classification:</b>", self.body_bold_style), Paragraph(company_profile['industry_sector'], self.body_style)],
            [Paragraph("<b>Entity Classification:</b>", self.body_bold_style), Paragraph(company_profile['entity_type'], self.body_style)]
        ]
        t_details = Table(details_data, colWidths=[150, 370])
        t_details.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
            ('PADDING', (0,0), (-1,-1), 6),
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ]))
        story.append(t_details)
        story.append(Spacer(1, 15))
        
        # Directors' Report summary
        story.append(Paragraph("<b>2. Directors' Report to the Shareholders</b>", self.header_style))
        directors_report = (
            f"Your Directors have pleasure in presenting the Annual Report on the business and operations of the "
            f"Company, together with the Audited Financial Statements for the financial year ended March 31, 2026. "
            f"The company registered operations within the <b>{company_profile['industry_sector']}</b> sector, "
            f"maintaining a workforce of approximately <b>{company_profile['employee_count']}</b> employees. "
            f"During the year, operations were managed under the guidance of the board of directors: {directors_str}."
        )
        story.append(Paragraph(directors_report, self.body_style))
        story.append(Spacer(1, 15))
        
        # Financial Highlights Table
        story.append(Paragraph("<b>3. Financial Performance Summary</b>", self.header_style))
        
        revs = financial_profile['revenue_annual']
        ebitdas = financial_profile['ebitda_annual']
        nps = financial_profile['net_profit_annual']
        
        perf_headers = ["Key Metrics", "FY 2023-24 (₹)", "FY 2024-25 (₹)", "FY 2025-26 (₹)", "Growth YoY %"]
        
        yoy_growth = ((revs[2] - revs[1]) / revs[1] * 100) if revs[1] else 0.0
        
        perf_data = [
            [Paragraph(f"<b>{col}</b>", self.table_cell_style) for col in perf_headers],
            [Paragraph("Revenue from Operations", self.body_style), Paragraph(f"{revs[0]:,.2f}", self.table_cell_right), Paragraph(f"{revs[1]:,.2f}", self.table_cell_right), Paragraph(f"{revs[2]:,.2f}", self.table_cell_right), Paragraph(f"{yoy_growth:.2f}%", self.table_cell_right)],
            [Paragraph("EBITDA", self.body_style), Paragraph(f"{ebitdas[0]:,.2f}", self.table_cell_right), Paragraph(f"{ebitdas[1]:,.2f}", self.table_cell_right), Paragraph(f"{ebitdas[2]:,.2f}", self.table_cell_right), Paragraph("-", self.table_cell_right)],
            [Paragraph("Net Profit After Tax (PAT)", self.body_bold_style), Paragraph(f"{nps[0]:,.2f}", self.table_cell_right), Paragraph(f"{nps[1]:,.2f}", self.table_cell_right), Paragraph(f"{nps[2]:,.2f}", self.table_cell_right), Paragraph("-", self.table_cell_right)],
        ]
        t_perf = Table(perf_data, colWidths=[160, 90, 90, 90, 90])
        t_perf.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ('PADDING', (0,0), (-1,-1), 6),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
        ]))
        story.append(t_perf)
        
        doc.build(story)
