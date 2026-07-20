import random
import datetime

class DirectorNetworkGenerator:
    """
    Generates realistic corporate director networks.
    - Legitimate companies have unique directors.
    - Fraudulent companies share directors, creating multi-hop network graphs.
    """

    FIRST_NAMES = ["Rajesh", "Amit", "Sunil", "Sanjay", "Anil", "Suresh", "Vijay", "Ramesh", "Deepak", "Vikram", 
                   "Priya", "Anjali", "Neha", "Pooja", "Sunita", "Ritu", "Karan", "Rahul", "Arjun", "Preeti"]
    LAST_NAMES = ["Kumar", "Sharma", "Gupta", "Verma", "Singh", "Joshi", "Mehra", "Patel", "Shah", "Jain",
                  "Yadav", "Choudhury", "Reddy", "Nair", "Rao", "Mishra", "Dubey", "Prasad", "Sinha", "Bansal"]
    
    STATES = ["Maharashtra", "Delhi", "Karnataka", "Tamil Nadu", "Gujarat", "West Bengal", "Uttar Pradesh", "Telangana", "Haryana"]

    def __init__(self):
        pass

    def generate_director_profile(self) -> dict:
        name = f"{random.choice(self.FIRST_NAMES)} {random.choice(self.LAST_NAMES)}"
        din = f"{random.randint(10000000, 99999999):08d}"
        age = random.randint(21, 80)
        state = random.choice(self.STATES)
        return {
            "name": name,
            "din": din,
            "age": age,
            "state": state
        }

    def generate(self, companies: list, fraud_rate: float = 0.1) -> dict:
        """
        Generates directors for each company.
        Connects fraudulent companies to simulate multi-hop networks.
        """
        # Set of active directors to reuse for fraud
        fraud_director_profiles = [self.generate_director_profile() for _ in range(8)]
        
        company_directors = {}
        director_companies = {}
        
        for company in companies:
            comp_name = company["company_name"]
            is_fraud = company.get("is_fraudulent", False)
            fraud_type = company.get("fraud_type", None)
            inc_date = company.get("incorporation_date", "2018-01-01")
            inc_year = int(inc_date.split("-")[0])
            
            directors = []
            
            if is_fraud and (fraud_type in ["shell_company", "circular_trading"] or random.random() < 0.7):
                # Shares directors with other fraud companies to form a network
                num_shared = random.randint(1, 3)
                chosen = random.sample(fraud_director_profiles, min(num_shared, len(fraud_director_profiles)))
                for d in chosen:
                    d_copy = d.copy()
                    # Generate appointment date relative to incorporation date
                    appt_year = inc_year + random.randint(0, 3)
                    d_copy["appointment_date"] = datetime.date(appt_year, random.randint(1, 12), random.randint(1, 28)).isoformat()
                    d_copy["is_cross_state"] = d_copy["state"] != company.get("registered_state", "")
                    directors.append(d_copy)
                
                # Add 1 unique director to blend in
                d_unique = self.generate_director_profile()
                appt_year = inc_year + random.randint(0, 3)
                d_unique["appointment_date"] = datetime.date(appt_year, random.randint(1, 12), random.randint(1, 28)).isoformat()
                d_unique["is_cross_state"] = d_unique["state"] != company.get("registered_state", "")
                directors.append(d_unique)
            else:
                # Legitimate: 2-3 unique directors
                num_directors = random.randint(2, 3)
                for _ in range(num_directors):
                    d_unique = self.generate_director_profile()
                    appt_year = inc_year + random.randint(0, 3)
                    d_unique["appointment_date"] = datetime.date(appt_year, random.randint(1, 12), random.randint(1, 28)).isoformat()
                    d_unique["is_cross_state"] = d_unique["state"] != company.get("registered_state", "")
                    directors.append(d_unique)
                    
            company_directors[comp_name] = directors
            
            for d in directors:
                d_name = d["name"]
                if d_name not in director_companies:
                    director_companies[d_name] = []
                director_companies[d_name].append(comp_name)
                
        # Format as graph
        nodes = []
        edges = []
        
        for comp in companies:
            nodes.append({
                "id": comp["company_name"],
                "type": "COMPANY",
                "is_fraudulent": comp["is_fraudulent"],
                "fraud_type": comp.get("fraud_type", None)
            })
            
        # Unique mapping of director names to profiles for node attributes
        director_profiles_map = {}
        for comp_name, dir_list in company_directors.items():
            for d in dir_list:
                director_profiles_map[d["name"]] = d

        for d_name, comps in director_companies.items():
            d_prof = director_profiles_map[d_name]
            nodes.append({
                "id": d_name,
                "type": "DIRECTOR",
                "din": d_prof["din"],
                "age": d_prof["age"],
                "state": d_prof["state"],
                "is_shared": len(comps) > 1
            })
            
            for comp in comps:
                edges.append({
                    "source": d_name,
                    "target": comp,
                    "relation": "DIRECTOR_OF",
                    "appointment_date": d_prof.get("appointment_date", ""),
                    "is_cross_state": d_prof.get("is_cross_state", False)
                })
                
        return {
            "company_directors": company_directors,
            "director_companies": director_companies,
            "graph": {
                "nodes": nodes,
                "edges": edges
            }
        }
