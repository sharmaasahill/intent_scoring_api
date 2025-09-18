"""
Lead Qualification Backend Service

A FastAPI-based service that scores leads based on product/offer context
using rule-based logic and AI reasoning (Gemini).
"""

import os
import csv
import io
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
import requests
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Lead Qualification API",
    description="Backend service for scoring leads based on product/offer context",
    version="1.0.0"
)

# Enable CORS (allow all origins by default; tighten for production as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure Gemini AI (REST)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-1.5-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY not found. AI scoring will use heuristic approach.")

# In-memory storage (in production, use a database)
offer_data = {}
leads_data = []
scored_results = []

# Pydantic Models
class Offer(BaseModel):
    name: str = Field(..., description="Product/offer name")
    value_props: List[str] = Field(..., description="Value propositions")
    ideal_use_cases: List[str] = Field(..., description="Ideal use cases")

class Lead(BaseModel):
    name: str
    role: str
    company: str
    industry: str
    location: str
    linkedin_bio: str

class ScoredLead(BaseModel):
    name: str
    role: str
    company: str
    industry: str
    location: str
    linkedin_bio: str
    intent: str  # High/Medium/Low
    score: int  # 0-100
    reasoning: str
    rule_score: int
    ai_score: int

# Rule-based scoring functions
def calculate_role_score(role: str) -> int:
    """Calculate role relevance score (0-20 points)"""
    role_lower = role.lower()
    
    # Decision makers (20 points)
    decision_makers = [
        'ceo', 'cto', 'cfo', 'cmo', 'coo', 'president', 'founder', 'owner',
        'head of', 'director', 'vp', 'vice president', 'chief'
    ]
    
    # Influencers (10 points)
    influencers = [
        'manager', 'lead', 'senior', 'principal', 'architect', 'specialist'
    ]
    
    for keyword in decision_makers:
        if keyword in role_lower:
            return 20
    
    for keyword in influencers:
        if keyword in role_lower:
            return 10
    
    return 0

def calculate_industry_score(industry: str, ideal_use_cases: List[str]) -> int:
    """Calculate industry match score (0-20 points)"""
    industry_lower = industry.lower()
    
    # Check for exact matches in ideal use cases
    for use_case in ideal_use_cases:
        use_case_lower = use_case.lower()
        if industry_lower in use_case_lower or use_case_lower in industry_lower:
            return 20
    
    # Check for adjacent industries
    adjacent_keywords = ['tech', 'software', 'saas', 'technology', 'digital', 'online']
    for keyword in adjacent_keywords:
        if keyword in industry_lower:
            return 10
    
    return 0

def calculate_data_completeness_score(lead: Lead) -> int:
    """Calculate data completeness score (0-10 points)"""
    fields = [lead.name, lead.role, lead.company, lead.industry, lead.location, lead.linkedin_bio]
    complete_fields = sum(1 for field in fields if field and field.strip())
    return min(10, complete_fields * 2)  # 2 points per field, max 10

def get_ai_score(lead: Lead, offer: Offer) -> tuple[int, str]:
    """Get AI-based intent score and reasoning.

    Uses Gemini when configured; otherwise falls back to a heuristic score.
    This function is synchronous so it can be safely called from a standard
    FastAPI (threadpool) endpoint.
    """
    # Heuristic fallback if key not available
    if not GEMINI_API_KEY:
        role_lower = lead.role.lower()
        industry_lower = lead.industry.lower()
        ai_score = 30
        reasoning = "AI disabled: heuristic based on role/industry"
        high_intent_roles = ['ceo', 'cto', 'founder', 'head of', 'director', 'vp']
        high_intent_industries = ['saas', 'technology', 'software', 'tech']
        if any(role in role_lower for role in high_intent_roles) and any(ind in industry_lower for ind in high_intent_industries):
            return 50, "Heuristic: decision-maker in tech industry"
        if any(role in role_lower for role in high_intent_roles):
            return 40, "Heuristic: decision-maker role"
        if any(ind in industry_lower for ind in high_intent_industries):
            return 35, "Heuristic: tech industry match"
        return 20, reasoning

    try:
        prompt = f"""
        You are a B2B sales qualification expert. Analyze this lead against the product offer and classify their buying intent.

        PRODUCT/OFFER:
        Name: {offer.name}
        Value Propositions: {', '.join(offer.value_props)}
        Ideal Use Cases: {', '.join(offer.ideal_use_cases)}

        LEAD PROFILE:
        Name: {lead.name}
        Role: {lead.role}
        Company: {lead.company}
        Industry: {lead.industry}
        Location: {lead.location}
        LinkedIn Bio: {lead.linkedin_bio}

        Task:
        1) Classify intent as High, Medium, or Low.
        2) Provide a brief 1–2 sentence explanation.

        Respond exactly in this format:
        Intent: <High/Medium/Low>
        Reasoning: <1–2 sentences>
        """

        # REST call to Gemini
        payload = {
            "contents": [
                {"parts": [{"text": prompt}]}
            ]
        }
        params = {"key": GEMINI_API_KEY}
        r = requests.post(GEMINI_URL, params=params, json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()

        response_text = ""
        try:
            # Extract first candidate text
            response_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception:
            # Fallback: stringify
            response_text = str(data)

        intent = "Medium"
        reasoning = ""
        for line in response_text.split('\n'):
            if line.strip().lower().startswith("intent:"):
                intent = line.split(":", 1)[1].strip().capitalize()
            elif line.strip().lower().startswith("reasoning:"):
                reasoning = line.split(":", 1)[1].strip()

        intent_scores = {"High": 50, "Medium": 30, "Low": 10}
        score = intent_scores.get(intent, 30)
        if not reasoning:
            reasoning = "AI provided no explanation"
        return score, reasoning

    except Exception as e:
        logger.error(f"AI scoring error: {str(e)}")
        # Gracefully fall back
        return 25, f"AI scoring failed: {str(e)}"

def score_lead(lead: Lead, offer: Offer) -> ScoredLead:
    """Score a single lead using rule-based and AI logic"""
    # Rule-based scoring
    role_score = calculate_role_score(lead.role)
    industry_score = calculate_industry_score(lead.industry, offer.ideal_use_cases)
    completeness_score = calculate_data_completeness_score(lead)
    rule_score = role_score + industry_score + completeness_score
    
    # AI scoring
    ai_score, ai_reasoning = get_ai_score(lead, offer)
    
    # Final score and intent
    final_score = rule_score + ai_score
    intent = "High" if final_score >= 70 else "Medium" if final_score >= 40 else "Low"
    
    # Combine reasoning
    reasoning_parts = []
    if role_score > 0:
        reasoning_parts.append(f"Role relevance: {role_score} points")
    if industry_score > 0:
        reasoning_parts.append(f"Industry match: {industry_score} points")
    if completeness_score > 0:
        reasoning_parts.append(f"Data completeness: {completeness_score} points")
    reasoning_parts.append(f"AI assessment: {ai_reasoning}")
    
    reasoning = ". ".join(reasoning_parts)
    
    return ScoredLead(
        name=lead.name,
        role=lead.role,
        company=lead.company,
        industry=lead.industry,
        location=lead.location,
        linkedin_bio=lead.linkedin_bio,
        intent=intent,
        score=final_score,
        reasoning=reasoning,
        rule_score=rule_score,
        ai_score=ai_score
    )

# API Endpoints
@app.post("/offer")
async def create_offer(offer: Offer):
    """Accept product/offer details"""
    global offer_data
    offer_data = offer.model_dump()
    logger.info(f"Offer created: {offer.name}")
    return {"message": "Offer created successfully", "offer": offer_data}

@app.post("/leads/upload")
async def upload_leads(file: UploadFile = File(...)):
    """Accept CSV file with lead data"""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    try:
        # Read CSV content
        content = await file.read()
        csv_content = content.decode('utf-8')
        
        # Parse CSV
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        leads = []
        
        for row in csv_reader:
            # Validate required columns
            required_columns = ['name', 'role', 'company', 'industry', 'location', 'linkedin_bio']
            if not all(col in row for col in required_columns):
                raise HTTPException(
                    status_code=400, 
                    detail=f"CSV must contain columns: {', '.join(required_columns)}"
                )
            
            lead = Lead(**row)
            leads.append(lead)
        
        global leads_data
        leads_data = leads
        logger.info(f"Uploaded {len(leads)} leads")
        
        return {"message": f"Successfully uploaded {len(leads)} leads", "count": len(leads)}
        
    except Exception as e:
        logger.error(f"Error uploading leads: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error processing CSV: {str(e)}")

@app.post("/score")
def score_leads():
    """Run scoring on uploaded leads"""
    if not offer_data:
        raise HTTPException(status_code=400, detail="No offer data found. Please create an offer first.")
    
    if not leads_data:
        raise HTTPException(status_code=400, detail="No leads found. Please upload leads first.")
    
    try:
        offer = Offer(**offer_data)
        global scored_results
        scored_results = []
        
        for lead in leads_data:
            scored_lead = score_lead(lead, offer)
            scored_results.append(scored_lead)
        
        logger.info(f"Scored {len(scored_results)} leads")
        return {"message": f"Successfully scored {len(scored_results)} leads", "count": len(scored_results)}
        
    except Exception as e:
        logger.error(f"Error scoring leads: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error scoring leads: {str(e)}")

@app.get("/results")
async def get_results():
    """Return scored leads"""
    if not scored_results:
        raise HTTPException(status_code=404, detail="No results found. Please run scoring first.")
    
    return [result.model_dump() for result in scored_results]

@app.get("/results/csv")
async def export_results_csv():
    """Export results as CSV"""
    if not scored_results:
        raise HTTPException(status_code=404, detail="No results found. Please run scoring first.")
    
    # Create CSV content
    output = io.StringIO()
    fieldnames = ['name', 'role', 'company', 'industry', 'location', 'linkedin_bio', 'intent', 'score', 'reasoning', 'rule_score', 'ai_score']
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    
    for result in scored_results:
        writer.writerow(result.model_dump())
    
    csv_content = output.getvalue()
    output.close()
    
    return StreamingResponse(
        io.BytesIO(csv_content.encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=scored_leads.csv"}
    )

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Lead Qualification API is running", "status": "healthy"}

@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "offer_loaded": bool(offer_data),
        "leads_loaded": len(leads_data),
        "results_available": len(scored_results),
        "ai_enabled": bool(GEMINI_API_KEY)
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
