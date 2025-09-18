# Lead Qualification Backend Service

A FastAPI-based backend service that scores leads based on product/offer context using rule-based logic and AI reasoning (Gemini).

## Features

- **Product/Offer Management**: Store and manage product details with value propositions and ideal use cases
- **Lead Upload**: Accept CSV files with lead information
- **Dual Scoring System**: 
  - Rule-based scoring (0-50 points): Role relevance, industry match, data completeness
  - AI-based scoring (0-50 points): Gemini AI intent classification
- **Results Export**: Get scored results as JSON or CSV
- **RESTful API**: Clean, well-documented endpoints

## Setup Instructions

### 1. Clone and Install Dependencies

```bash
git clone <your-repo-url>
cd intent_scoring_api
pip install -r requirements.txt
```

### 2. Environment Configuration

Create a `.env` file in the project root:

```bash
cp env.example .env
```

Edit `.env` and add your Gemini API key:

```
GEMINI_API_KEY=your_actual_gemini_api_key_here
```

### 3. Run the Service

```bash
export PORT=8000  # optional; many hosts set this automatically
python main.py
```

The service will start on `http://localhost:${PORT:-8000}`

### 4. View API Documentation

Visit `http://localhost:8000/docs` for interactive API documentation.

## API Usage Examples

### 1. Create an Offer

```bash
curl -X POST "http://localhost:8000/offer" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "AI Outreach Automation",
    "value_props": ["24/7 outreach", "6x more meetings", "Personalized messaging"],
    "ideal_use_cases": ["B2B SaaS mid-market", "Sales teams", "Marketing automation"]
  }'
```

### 2. Upload Leads CSV

Create a CSV file with the following columns:
- `name`: Lead's full name
- `role`: Job title/role
- `company`: Company name
- `industry`: Industry sector
- `location`: Geographic location
- `linkedin_bio`: LinkedIn profile bio

Example CSV content:
```csv
name,role,company,industry,location,linkedin_bio
Ava Patel,Head of Growth,FlowMetrics,SaaS,San Francisco,Experienced growth marketer with 8+ years in B2B SaaS
John Smith,CEO,TechStart,Technology,New York,Serial entrepreneur building the next unicorn
Sarah Johnson,Marketing Manager,RetailCorp,Retail,Chicago,Passionate about customer acquisition and retention
```

Upload the CSV:
```bash
curl -X POST "http://localhost:8000/leads/upload" \
  -F "file=@leads.csv"
```

### 3. Score Leads

```bash
curl -X POST "http://localhost:8000/score"
```

### 4. Get Results

```bash
curl -X GET "http://localhost:8000/results"
```

### 5. Export Results as CSV

```bash
curl -X GET "http://localhost:8000/results/csv" -o scored_leads.csv
```

## Scoring Logic

### Rule-Based Scoring (0-50 points)

1. **Role Relevance (0-20 points)**:
   - Decision makers (CEO, CTO, Head of, Director, VP): 20 points
   - Influencers (Manager, Lead, Senior, Specialist): 10 points
   - Others: 0 points

2. **Industry Match (0-20 points)**:
   - Exact match with ideal use cases: 20 points
   - Adjacent industries (tech, software, SaaS): 10 points
   - No match: 0 points

3. **Data Completeness (0-10 points)**:
   - 2 points per complete field (name, role, company, industry, location, linkedin_bio)
   - Maximum 10 points

### AI-Based Scoring (0-50 points)

The system sends lead and offer information to Gemini AI with the following prompt:

```
You are a B2B sales qualification expert. Analyze this lead against the product offer and classify their buying intent.

[Product details and lead profile are provided]

Classify this lead's buying intent as High, Medium, or Low and provide a brief 1-2 sentence explanation.
```

**Score Mapping**:
- High intent: 50 points
- Medium intent: 30 points
- Low intent: 10 points

### Final Score

- **Total Score**: Rule Score + AI Score (0-100)
- **Intent Classification**:
  - High: 70+ points
  - Medium: 40-69 points
  - Low: 0-39 points

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/offer` | Create/update product offer |
| POST | `/leads/upload` | Upload leads CSV file |
| POST | `/score` | Run scoring on uploaded leads |
| GET | `/results` | Get scored results as JSON |
| GET | `/results/csv` | Export results as CSV |
| GET | `/health` | Health check with system status |
| GET | `/` | Basic health check |

## Error Handling

The API includes comprehensive error handling for:
- Invalid CSV formats
- Missing required fields
- API key issues
- File upload errors
- Scoring failures

## Deployment

### Using Render (Recommended)

1. Connect your GitHub repository to Render
2. Create a new Web Service
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `python main.py` (or `uvicorn main:app --host 0.0.0.0 --port $PORT`)
5. Add environment variable: `GEMINI_API_KEY=your_key`

### Using Railway

1. Connect your GitHub repository to Railway
2. Add environment variable: `GEMINI_API_KEY=your_key`
3. Set start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Deploy automatically

### Using Docker (Any Host)

Build and run locally:
```bash
docker build -t intent-scoring-api .
docker run -p 8000:8000 --env GEMINI_API_KEY=your_key intent-scoring-api
```

### Live URL & Demo

- Live API Base URL: `https://intent-scoring-api.onrender.com`
- Swagger UI: `https://intent-scoring-api.onrender.com/docs`
- Health: `https://intent-scoring-api.onrender.com/health`
- Loom demo link: <ADD HERE>

#### Live cURL quickstart
```bash
curl -s https://intent-scoring-api.onrender.com/health
curl -s https://intent-scoring-api.onrender.com/docs

# Offer
curl -X POST https://intent-scoring-api.onrender.com/offer -H "Content-Type: application/json" -d @offer.json

# Leads (uses the sample CSV in repo)
curl -X POST https://intent-scoring-api.onrender.com/leads/upload -F "file=@leads.csv"

# Score
curl -X POST https://intent-scoring-api.onrender.com/score

# Results (JSON)
curl -s https://intent-scoring-api.onrender.com/results | jq .

# Results (CSV)
curl -L https://intent-scoring-api.onrender.com/results/csv -o scored_leads.csv
```

## Testing

### Health Check
```bash
curl http://localhost:8000/health
```

### Complete Workflow Test
```bash
# 1. Create offer
curl -X POST "http://localhost:8000/offer" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Product", "value_props": ["Test prop"], "ideal_use_cases": ["Test case"]}'

# 2. Upload leads (create a test CSV first)
curl -X POST "http://localhost:8000/leads/upload" -F "file=@test_leads.csv"

# 3. Score leads
curl -X POST "http://localhost:8000/score"

# 4. Get results
curl -X GET "http://localhost:8000/results"
```

## Project Structure

```
intent_scoring_api/
├── main.py              # Main FastAPI application
├── requirements.txt     # Python dependencies
├── env.example         # Environment variables template
├── README.md           # This file
└── .env               # Environment variables (create this)
```

## Technologies Used

- **FastAPI**: Modern, fast web framework for building APIs
- **Pydantic**: Data validation and settings management
- **Google Generative AI**: Gemini AI integration for intent classification
- **Uvicorn**: ASGI server for running the application

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License.
