import os
from datetime import datetime

GROQ_API_KEY       = os.getenv("GROQ_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")
NCBI_EMAIL         = os.getenv("NCBI_EMAIL", "researcher@example.com")

PAPERS_PER_DAY = 1
GROQ_MODEL     = "llama-3.3-70b-versatile"
DATABASE_PATH  = "data/research_archive.db"
LOG_PATH       = "data/agent.log"

DAILY_THEMES = [
    {"name": "Phosphorus Use Efficiency (PUE)", "emoji": "🌱",
     "description": "Agronomic and biological strategies to maximize crop P uptake",
     "extra_keywords": ["phosphorus use efficiency", "PUE", "P uptake", "P recovery"]},
    {"name": "P-Induced N2O Mitigation", "emoji": "🌫️",
     "description": "How optimized P supply modulates soil denitrification and N2O emissions",
     "extra_keywords": ["phosphorus nitrous oxide", "P N2O", "denitrification phosphorus"]},
    {"name": "Soil-P-Microbiome Interactions", "emoji": "🦠",
     "description": "Microbial communities driving P cycling, solubilization, and GHG fluxes",
     "extra_keywords": ["phosphorus solubilizing bacteria", "PSB", "mycorrhiza phosphorus"]},
    {"name": "Long-Term Sustainability of P Management", "emoji": "📊",
     "description": "Legacy P, P saturation thresholds, and long-term soil P dynamics",
     "extra_keywords": ["legacy phosphorus", "P saturation", "long-term phosphorus"]},
    {"name": "Meta-Analyses on P Management and GHG", "emoji": "🔬",
     "description": "Quantitative syntheses across global datasets linking P to emissions",
     "extra_keywords": ["meta-analysis phosphorus GHG", "systematic review P emissions"]},
    {"name": "Climate-Smart Fertilizer Strategies", "emoji": "🌍",
     "description": "4R nutrient stewardship, split applications, climate-adaptive P management",
     "extra_keywords": ["4R nutrient stewardship", "climate smart fertilizer", "precision P"]},
    {"name": "Life Cycle Assessment of P Fertilizers", "emoji": "♻️",
     "description": "Full environmental footprint of P fertilizer production, use, and fate",
     "extra_keywords": ["LCA phosphorus fertilizer", "life cycle assessment P"]},
    {"name": "Circular Phosphorus Economy", "emoji": "🔄",
     "description": "P recovery from wastewater, manure, and organic wastes; struvite",
     "extra_keywords": ["phosphorus recovery", "struvite", "P recycling", "circular phosphorus"]},
    {"name": "Novel P Fertilizer Formulations", "emoji": "⚗️",
     "description": "Enhanced efficiency fertilizers, nano-P, polymer-coated P",
     "extra_keywords": ["enhanced efficiency phosphorus", "nano phosphorus", "polymer coated fertilizer"]},
    {"name": "Biochar and Organic Amendments for P", "emoji": "🌾",
     "description": "Biochar, compost, and organic amendments as P sources and GHG mitigants",
     "extra_keywords": ["biochar phosphorus", "compost P availability", "organic amendment GHG"]},
    {"name": "Crop Yield Response to P Fertilization", "emoji": "📈",
     "description": "Dose-response functions, yield thresholds, and agronomic optimum P rates",
     "extra_keywords": ["crop yield phosphorus response", "P fertilizer rate yield"]},
    {"name": "P and Soil Carbon Interactions", "emoji": "🌰",
     "description": "C-P co-limitation, priming effects, and soil organic matter dynamics",
     "extra_keywords": ["phosphorus soil carbon", "P organic matter", "P C stoichiometry"]},
    {"name": "Environmental Policy and P Regulation", "emoji": "📜",
     "description": "Regulatory frameworks, P indices, water quality limits, and policy instruments",
     "extra_keywords": ["phosphorus water quality", "P regulation agriculture", "phosphorus index"]},
    {"name": "Integrated Nutrient Management", "emoji": "🧩",
     "description": "Combining mineral P with organic sources for optimized GHG and yield outcomes",
     "extra_keywords": ["integrated nutrient management phosphorus", "INM GHG", "combined organic mineral P"]},
]

BASE_KEYWORDS = [
    "phosphorus management greenhouse gas",
    "phosphorus fertilizer GHG emissions",
    "P fertilizer nitrous oxide N2O",
    "phosphorus soil carbon sequestration",
    "phosphate fertilizer climate change",
    "phosphorus use efficiency sustainability",
    "P management crop yield GHG",
    "fertilizer management emissions mitigation",
]

HIGH_IMPACT_JOURNALS = [
    "Nature", "Science", "Nature Climate Change", "Nature Food",
    "Nature Sustainability", "Global Change Biology", "Global Biogeochemical Cycles",
    "Plant and Soil", "Soil Biology and Biochemistry", "Geoderma",
    "Agriculture Ecosystems and Environment", "Agricultural Systems",
    "Field Crops Research", "European Journal of Agronomy",
    "Journal of Cleaner Production", "Environmental Science and Technology",
    "Science of the Total Environment", "Biogeosciences",
    "Soil and Tillage Research", "Nutrient Cycling in Agroecosystems",
    "Frontiers in Plant Science", "Frontiers in Sustainable Food Systems",
    "Applied Soil Ecology", "Biology and Fertility of Soils",
    "Journal of Environmental Quality", "Resources Conservation and Recycling",
]

def get_today_theme() -> dict:
    day_of_year = datetime.utcnow().timetuple().tm_yday
    return DAILY_THEMES[day_of_year % len(DAILY_THEMES)]
