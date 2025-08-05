import datetime
import json
import os
import requests # New import for making HTTP requests to FMP API
import google.generativeai as genai # NEW IMPORT
# Ensure Firestore is imported if not already present
try:
    from google.cloud import firestore
except ImportError:
    firestore = None # Handle case where google-cloud-firestore is not installed

# Import FMP_API_KEY from config
# from app.config import FMP_API_KEY # Assuming you added FMP_API_KEY to app/config.py

# Custom JSON encoder (already exists in your provided script, ensure it's accessible)
class FirestoreEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'isoformat'): # Handles datetime objects including Firestore Timestamps
            return obj.isoformat()
        if isinstance(obj, bytes): # Handle bytes data if any (e.g., from Firestore Blob, though not expected here)
            return obj.decode('utf-8')
        try: # Attempts to convert other non-serializable objects (like Firestore DocumentReference) to dict
            return dict(obj)
        except (TypeError, ValueError):
            pass
        return super().default(obj)

# --- FMP API Configuration ---
# --- FMP API Configuration ---
FMP_BASE_URL = "https://financialmodelingprep.com/api/v3" # Still use /api/v3 for general FMP base, but specific endpoints below
FMP_STABLE_BASE_URL = "https://financialmodelingprep.com/stable" # Use this for stable API endpoints

FMP_API_KEY = os.environ.get("FMP_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# --- List of Tickers of Interest ---
# This list is derived from the CSV data you provided.
# You might want to move this to a separate file or a database for easier management
# if it grows very large or needs dynamic updates.
INTERESTED_TICKERS = [
    "HAFNI.OL", 
     "STNG", "TRMD", "FRO", "ECO", "DHT", "INSW", "NAT", "TEN", "IMPP",
    "PSHG", "TORO", "TNK", "PXS", "TOPS", "DSX", "GNK", "GOGL", "NMM", "SB",
    "SBLK", "SHIP", "2020.OL", "HSHP", "EDRY", "JINO.XD", "CTRM", "ICON", "GLBS", "CMRE",
    "DAC", "GSL", "ESEA", "MPCC.OL", "ZIM", "SFL", "BWLPGO.XD", "LPG", "CCEC", "GASS",
    "DLNG", "AGASO.OL", "ALNGO.OL", "CLCO", "FLNG",
    "RIG", "HLX", "PRS.OL", "SPM.MI", "SBMO.VI", "TDW",
    "RIO", "BHP", "VALE", "GLNCY", "ADM", "WLMIY", "BG", "SHEL", "XOM", "CVX",
    "TTE", "WPM", "VALE", "CLF", "ALB", "MOS",
    "BDRY", "BWET",
    "^DJI", "^SPX", "^GSPTSE", "^MXX", "^BVSP", "^STOXX50E", "UKXDUK.L", "^FCHI", "FTSEMIB.MI",
    "^OMX", "SMIN.SW", "^N225", "^HSI", "000300.SS", "^AXJO"
]

ticker_name = {
    "HAFNI.OL": "Hafnia Ltd", "STNG": "Scorpio Tankers Inc", "TRMD": "TORM PLC",
    "FRO": "Frontline PLC", "ECO": "Okeanis Eco Tankers Corp", "DHT": "DHT Holdings Inc",
    "INSW": "International Seaways Inc", "NAT": "Nordic American Tankers Ltd",
    "TEN": "Tsakos Energy Navigation Ltd", "IMPP": "Imperial Petroleum Inc",
    "PSHG": "Performance Shipping Inc", "TORO": "Toro Corp", "TNK": "Teekay Tankers Ltd",
    "PXS": "Pyxis Tankers Inc", "TOPS": "TOP Ships Inc", "DSX": "Diana Shipping Inc",
    "GNK": "Genco Shipping & Trading Ltd", "GOGL": "Golden Ocean Group Ltd",
    "NMM": "Navios Maritime Partners LP", "SB": "Safe Bulkers Inc",
    "SBLK": "Star Bulk Carriers Corp", "SHIP": "Seanergy Maritime Holdings Cor",
    "2020.OL": "2020 Bulkers Ltd", "HSHP": "Himalaya Shipping Ltd", "EDRY": "EuroDry Ltd",
    "JINO.XD": "Jinhui Shipping & Transportation", "CTRM": "Castor Maritime Inc",
    "ICON": "Icon Energy Corp", "GLBS": "Globus Maritime Ltd", "CMRE": "Costamare Inc",
    "DAC": "Danaos Corp", "GSL": "Global Ship Lease Inc", "ESEA": "Euroseas Ltd",
    "MPCC.OL": "MPC Container Ships ASA", "ZIM": "ZIM Integrated Shipping Services",
    "SFL": "SFL Corp Ltd", "BWLPGO.XD": "BW LPG Ltd", "LPG": "Dorian LPG Ltd",
    "CCEC": "Capital Clean Energy Carriers", "GASS": "StealthGas Inc",
    "DLNG": "Dynagas LNG Partners LP", "AGASO.OL": "Avance Gas Holding Ltd",
    "ALNGO.OL": "Awilco LNG AS", "CLCO": "Cool Co Ltd", "FLNG": "FLEX LNG Ltd",

    "RIG": "Transocean Ltd", "HLX": "Helix Energy Solutions Group Inc",
    "PRS.OL": "Prosafe SE", "SPM.MI": "Saipem SpA", "SBMO.VI": "SBM Offshore NV",
    "TDW": "Tidewater Inc",

    "RIO": "Rio Tinto PLC", "BHP": "BHP Group Ltd", "VALE": "Vale SA",
    "GLNCY": "Glencore PLC", "ADM": "Archer-Daniels-Midland Co",
    "WLMIY": "Wilmar International Ltd", "BG": "Bunge Global SA", "SHEL": "Shell PLC",
    "XOM": "Exxon Mobil Corp", "CVX": "Chevron Corp", "TTE": "TotalEnergies SE",
    "WPM": "Wheaton Precious Metals Corp", "CLF": "Cleveland-Cliffs Inc",
    "ALB": "Albemarle Corp", "MOS": "Mosaic Co/The",

    "BDRY": "Breakwave Dry Bulk Shipping ETF", "BWET": "Breakwave Tanker Shipping ETF",

    "^DJI": "Dow Jones Industrial Average", "^SPX": "S&P 500 Index",
    "^GSPTSE": "S&P/TSX Composite Index", "^MXX": "S&P/BMV IPC",
    "^BVSP": "Ibovespa Brasil Sao Paulo Stock", "^STOXX50E": "EURO STOXX 50 Price EUR",
    "UKXDUK.L": "FTSE 100 Index", "^FCHI": "CAC 40", "FTSEMIB.MI": "FTSE MIB Index",
    "^OMX": "OMX Stockholm 30 Index", "SMIN.SW": "Swiss Market Index",
    "^N225": "Nikkei 225", "^HSI": "Hang Seng Index",
    "000300.SS": "Shanghai Shenzhen CSI 300 Index", "^AXJO": "S&P/ASX 200"
}



FMP_V4_BASE_URL = "https://financialmodelingprep.com/api/v4"

# (Existing imports and helper functions, including parse_fmp_date_string)

# Make sure the constants like FMP_BASE_URL, FMP_V4_BASE_URL, INTERESTED_TICKERS are defined above this route.

def parse_fmp_date_string(date_string):
    """
    Parses a date string from FMP, handling various known formats (with/without seconds/microseconds).
    Returns a timezone-aware datetime object (UTC) or None if parsing fails.
    """
    if not isinstance(date_string, str):
        return None

    # Ordered from most specific (with microseconds) to least specific (date only)
    formats_to_try = [
        "%Y-%m-%d %H:%M:%S.%f", # e.g., "2020-07-30 23:35:04.123"
        "%Y-%m-%d %H:%M:%S",   # e.g., "2020-07-30 23:35:04"
        "%Y-%m-%d %H:%M",      # e.g., "2020-07-30 23:35"
        "%Y-%m-%d"             # e.g., "2020-07-30"
    ]

    for fmt in formats_to_try:
        try:
            # Parse the string and make it timezone-aware UTC
            dt_obj = datetime.datetime.strptime(date_string, fmt).replace(tzinfo=datetime.timezone.utc)
            return dt_obj
        except ValueError:
            continue # Try next format if this one fails

    return None # All formats failed


def fetch_fmp_earnings_transcripts(ticker, start_date_filter=None):
    """
    Fetches earnings transcripts for a given ticker from FMP, prioritizing v4 batch API.
    Falls back to v4 dates + v3 individual transcript API if batch fails.
    
    Args:
        ticker (str): The stock ticker symbol.
        start_date_filter (datetime.datetime, optional): Transcripts with conference_date
                                                          on or after this date will be fetched.
                                                          This should be a timezone-aware datetime.
    Returns:
        list: A list of transcript dictionaries, each containing raw FMP data.
    """
    if not FMP_API_KEY:
        print("FMP_API_KEY is not configured.")
        return []

    transcripts_data = []
    current_year = datetime.datetime.now().year
    
    # Determine the years to fetch for.
    # If a filter date is provided, start from that year. Otherwise, look back 3 full years.
    fetch_start_year = start_date_filter.year if start_date_filter else (current_year - 3)
    
    # Ensure we don't go too far back to avoid excessive calls or hitting very old, non-existent data
    if fetch_start_year < 2020: # Adjust this minimum year as per your FMP plan's historical data depth
        fetch_start_year = 2020

    years_to_fetch = list(range(fetch_start_year, current_year + 1))
    
    # --- Attempt 1: Use FMP v4 Batch Earning Call Transcript API ---
    # This is the most efficient if available.
    batch_api_success = False
    print(f"Attempting to fetch transcripts for {ticker} using FMP v4 batch API for years {years_to_fetch}.")
    for year in years_to_fetch:
        batch_url = f"{FMP_V4_BASE_URL}/batch_earning_call_transcript/{ticker}?year={year}&apikey={FMP_API_KEY}"
        try:
            batch_response = requests.get(batch_url, timeout=30)
            batch_response.raise_for_status()
            batch_data = batch_response.json()
            
            if batch_data and isinstance(batch_data, list):
                # Filter by conference_date here if start_date_filter is present
                for item in batch_data:
                    conf_date_str = item.get("date") # v4 batch has "date"
                    if conf_date_str:
                        # Use the robust parser here
                        conf_date_dt = parse_fmp_date_string(conf_date_str)
                        
                        if conf_date_dt and (not start_date_filter or conf_date_dt >= start_date_filter):
                            transcripts_data.append(item)
                            batch_api_success = True # Mark success if we get any valid data this way
                        elif not conf_date_dt:
                            print(f"Could not parse date '{conf_date_str}' for {ticker} in {year} from v4 batch API. Skipping.")
                print(f"Fetched {len(batch_data)} transcripts for {ticker} in {year} using v4 batch.")
            else:
                print(f"V4 batch API returned no data or unexpected format for {ticker} in {year}.")

        except requests.exceptions.HTTPError as e:
            print(f"V4 batch API failed for {ticker} in {year} (HTTP {e.response.status_code}). Falling back if needed. Error: {e}")
            # Do not set batch_api_success = False immediately, as some years might work.
            # We'll re-evaluate batch_api_success after the loop.
        except requests.exceptions.RequestException as e:
            print(f"Request error for V4 batch API for {ticker} in {year}: {e}. Falling back if needed.")
        except json.JSONDecodeError:
            print(f"JSON decode error for V4 batch API for {ticker} in {year}. Response: {batch_response.text[:500]}... Falling back if needed.")
        except Exception as e:
            print(f"Unexpected error with V4 batch API for {ticker} in {year}: {e}. Falling back if needed.")

    if batch_api_success:
        print(f"Successfully fetched transcripts using FMP v4 batch API for {ticker}.")
        return transcripts_data

    # --- Fallback: Use FMP v4 Transcript Dates API + FMP v3 Individual Transcript API ---
    print(f"FMP v4 batch API did not provide data or failed for {ticker}. Falling back to v4 dates + v3 individual API.")
    transcripts_data = [] # Reset transcripts_data for fallback attempt

    # 1. Fetch available transcript dates for the ticker using v4
    dates_url = f"{FMP_V4_BASE_URL}/earning_call_transcript?symbol={ticker}&apikey={FMP_API_KEY}"
    try:
        print(f"Fetching transcript dates for {ticker} from: {dates_url}")
        dates_response = requests.get(dates_url, timeout=30)
        dates_response.raise_for_status()
        available_dates_v4 = dates_response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching FMP v4 transcript dates for {ticker}: {e}")
        return []
    except json.JSONDecodeError:
        print(f"JSON decode error for FMP v4 transcript dates for {ticker}. Response: {dates_response.text[:500]}...")
        return []

    if not available_dates_v4:
        print(f"No available transcript dates found for {ticker} using FMP v4 dates API.")
        return []

    # 2. Fetch individual transcripts for each filtered date using v3
    print(f"Processing {len(available_dates_v4)} transcript dates for {ticker} (from v4 dates API).")
    for date_info_list in available_dates_v4:
        # v4 dates API returns [[quarter, fiscalYear, date_string], ...]
        if not isinstance(date_info_list, list) or len(date_info_list) < 3:
            print(f"Unexpected date_info format for {ticker}: {date_info_list}. Skipping.")
            continue

        quarter = date_info_list[0]
        year = date_info_list[1]
        conf_date_str = date_info_list[2] # Format: YYYY-MM-DD HH:MM:SS

        # Use the robust parser here
        conf_date_dt = parse_fmp_date_string(conf_date_str)

        if not conf_date_dt:
            print(f"Could not parse date '{conf_date_str}' from v4 dates API for {ticker}. Skipping.")
            continue

        # Apply filter: only include if on or after the start_date_filter
        if start_date_filter and conf_date_dt < start_date_filter:
            print(f"Skipping transcript date {conf_date_dt} for {ticker} as it's older than start_date_filter {start_date_filter}")
            continue

        # Fetch transcript content using FMP v3 individual API
        transcript_url = f"{FMP_BASE_URL}/earning_call_transcript/{ticker}?year={year}&quarter={quarter}&apikey={FMP_API_KEY}"
        
        try:
            print(f"Fetching transcript for {ticker} Q{quarter} {year} from: {transcript_url}")
            transcript_response = requests.get(transcript_url, timeout=30)
            transcript_response.raise_for_status()
            transcript_data = transcript_response.json()
            
            if transcript_data and isinstance(transcript_data, list) and len(transcript_data) > 0:
                # FMP v3 returns a list, usually with one dictionary if found
                transcripts_data.append(transcript_data[0])
            elif transcript_data and isinstance(transcript_data, dict): # Fallback for single dict
                transcripts_data.append(transcript_data)
            else:
                print(f"No actual transcript content found for {ticker} Q{quarter} {year} from v3 API.")

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print(f"No FMP transcript content found for {ticker} Q{quarter} {year} from v3 API. (404 Not Found)")
            else:
                print(f"HTTP error fetching FMP v3 transcript for {ticker} Q{quarter} {year}: {e}")
        except requests.exceptions.RequestException as e:
            print(f"Request error fetching FMP v3 transcript for {ticker} Q{quarter} {year}: {e}")
        except json.JSONDecodeError:
            print(f"JSON decode error for FMP v3 transcript for {ticker} Q{quarter} {year}. Response: {transcript_response.text[:500]}...")
        except Exception as e:
            print(f"Unexpected error fetching FMP v3 transcript for {ticker} Q{quarter} {year}: {e}")
            
    return transcripts_data

# --- New Gemini Analysis Function ---
def analyze_transcript_with_gemini(transcript_text, ticker, conference_date):
    """
    Analyzes an earnings call transcript using Google Gemini to extract alpha, sentiment, and summary.
    
    Args:
        transcript_text (str): The full text of the earnings call transcript.
        ticker (str): The ticker symbol for context in logging.
        conference_date (datetime.datetime): The date of the conference for context in logging.
        
    Returns:
        dict: A dictionary containing 'ExtractedAlpha', 'confidence_score', 'sentiment', 'summary'.
              Returns None if analysis fails or no valid data is extracted.
    """
    if not GEMINI_API_KEY:
        print("Gemini API Key is not configured. Skipping AI analysis.")
        return None

    # Handle potentially very long transcripts for Gemini (Gemini Pro has a large context window, but still limits)
    # A simple truncation might be needed for extremely long transcripts if they exceed Gemini's token limits.
    # For now, we'll send the full transcript and let the API handle length warnings/errors.
    
    model = genai.GenerativeModel('gemini-2.5-flash') # Using gemini-pro for text generation

    # Craft the prompt for Gemini
    # It's crucial to be very specific about the output JSON format and negative constraints.
    prompt_text = f"""
    Analyze the following earnings call transcript for {ticker} (Conference Date: {conference_date.strftime('%Y-%m-%d %H:%M:%S')}).
    
    Extract the following information in a concise JSON format:
    1.  **ExtractedAlpha**: A string (around 50-70 words) summarizing the key financial insights, future outlook, strategic developments, and any significant operational highlights that represent the company's "alpha" or competitive edge. Focus on new, forward-looking, or unexpected information from the call.
    2.  **confidence_score**: A float (between 0.0 and 1.0) indicating your confidence in the clarity and strength of the financial performance and outlook presented in the transcript. Higher score means more certainty in the positive/negative aspects and clear data.
    3.  **sentiment**: A single string indicating the overall sentiment of the earnings call. Choose one from: "positive", "neutral", "negative".
    4.  **summary**: A concise, comprehensive summary of the entire earnings call transcript (around 100-150 words). Include key financial figures, operational updates, and management commentary.

    Important constraints:
    -   The output MUST be a valid JSON object.
    -   Do NOT include any external references or URLs.
    -   Do NOT attempt to identify individual speakers or perform speaker diarization.
    -   Ensure the 'ExtractedAlpha' is truly focused on key, impactful insights for investors.
    -   Ensure the 'summary' covers all major points discussed.

    Transcript:
    ---
    {transcript_text}
    ---
    """

    try:
        response = model.generate_content(prompt_text, generation_config={"response_mime_type": "application/json"})
        
        # Gemini with "response_mime_type": "application/json" should return valid JSON directly in text attribute
        content = response.text
        
        # Parse the JSON response
        try:
            result = json.loads(content)
            
            # Basic validation of expected fields
            if not all(k in result for k in ["ExtractedAlpha", "confidence_score", "sentiment", "summary"]):
                print(f"Gemini response for {ticker} missing expected fields: {result}. Attempting best effort extraction.")
                # Fallback to manual extraction if JSON is malformed or missing keys
                extracted_alpha = result.get("ExtractedAlpha")
                confidence_score = result.get("confidence_score")
                sentiment = result.get("sentiment")
                summary = result.get("summary")
            else:
                extracted_alpha = result["ExtractedAlpha"]
                confidence_score = float(result["confidence_score"])
                sentiment = result["sentiment"]
                summary = result["summary"]
            
            # Return extracted data
            return {
                "ExtractedAlpha": extracted_alpha,
                "confidence_score": confidence_score,
                "sentiment": sentiment,
                "summary": summary
            }

        except (json.JSONDecodeError, ValueError) as e:
            print(f"Failed to parse JSON from Gemini response for {ticker}: {e}. Response text: {content[:500]}...")
            return None
        
    except Exception as e:
        print(f"Error calling Gemini API for {ticker}: {e}", exc_info=True)
        return None



def transform_fmp_to_firestore_doc(fmp_data):
    """
    Transforms FMP transcript data into a Firestore document format.
    Assumes FMP data has 'symbol', 'date', 'quarter', 'year', 'content', 'summary'.
    """
    # Use timezone-aware datetime for conference_date
    conference_date_str = fmp_data.get("date")
    try:
        # FMP date format is YYYY-MM-DD
        conference_date = datetime.datetime.strptime(conference_date_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc)
    except (ValueError, TypeError):
        print(f"Invalid conference_date format for {fmp_data.get('symbol')}: {conference_date_str}. Using current time for timestamp, None for conference_date.")
        conference_date = None # Indicate invalid date

    firestore_doc = {
        "ticker": fmp_data.get("symbol"),
        "company_name": ticker_name.get(fmp_data.get("symbol"), "N/A"), # FMP provides companyName in earnings-transcript-list endpoint, but not consistently in transcript
        "conference_date": conference_date, # This is the actual date of the call from FMP
        "quarter": fmp_data.get("quarter") or fmp_data.get("period"), # FMP uses 'period' or 'quarter'
        "year": fmp_data.get("year") or fmp_data.get("fiscalYear"), # FMP uses 'year' or 'fiscalYear'
        "transcript": fmp_data.get("content"), # Map FMP's 'content' to our 'transcript' field
        "summary": fmp_data.get("summary"), # FMP often provides a summary
        # These fields are usually added by AI later, so we omit them or set to None initially
        "alphaConfidence": None,
        "alphaReferences": [],
        "extractedAlpha": None,
        "sentiment": None,
        "transcript_by_speaker": [],
        "timestamp": datetime.datetime.now(datetime.timezone.utc) # When this record was created/ingested
    }
    return firestore_doc

# (Keep all your existing imports and helper functions like FirestoreEncoder,
#  fetch_fmp_earnings_transcripts, and transform_fmp_to_firestore_doc from the previous response.)

# Make sure the constants like FMP_BASE_URL, FMP_STABLE_BASE_URL, and INTERESTED_TICKERS are defined above this route.

# @app.route("/api/earnings-calls/ingest-new-transcripts", methods=["POST"])
def ingest_new_earnings_transcripts():
    """
    POST endpoint to trigger the ingestion of new earnings call transcripts from FMP
    into the Firestore 'transcripts' collection, enriched with Gemini analysis.

    This function is designed to be called by a cron job or similar scheduler.
    It iterates through a predefined list of tickers, fetches new transcripts
    since the last recorded conference date for each ticker in Firestore,
    analyzes them with Gemini, and stores them.
    """
    if firestore is None:
        print("Google Cloud Firestore library not found. Please install it.")
        return ({
            "status": "error",
            "message": "Server configuration error: Firestore library not available."
        }), 500

    if not FMP_API_KEY:
        print("FMP API Key is missing. Cannot fetch transcripts.")
        return ({
            "status": "error",
            "message": "FMP API Key is not configured on the server."
        }), 500
    
    if not GEMINI_API_KEY:
        print("Gemini API Key is missing. AI analysis will be skipped.")

    try:
        db = firestore.Client(database='hedgefundintelligence')
        collection_ref = db.collection("earnings_transcripts")
        print("Initialized Firestore client for earnings call ingestion.")

        new_transcripts_added = 0
        total_tickers_processed = 0
        tickers_with_updates = []
        errors_by_ticker = {}

        for ticker in INTERESTED_TICKERS:
            total_tickers_processed += 1
            print(f"Processing ticker: {ticker}")

            try:
                latest_firestore_doc_query = collection_ref\
                    .where("ticker", "==", ticker)\
                    .order_by("conference_date", firestore.Query.DESCENDING)\
                    .limit(1)
                
                latest_firestore_conference_date = None
                for doc in latest_firestore_doc_query.stream():
                    firestore_data = doc.to_dict()
                    latest_firestore_conference_date = firestore_data.get("conference_date")
                    if isinstance(latest_firestore_conference_date, datetime.datetime):
                        if latest_firestore_conference_date.tzinfo is None:
                            latest_firestore_conference_date = latest_firestore_conference_date.replace(tzinfo=datetime.timezone.utc)
                        print(f"Latest 'conference_date' in Firestore for {ticker}: {latest_firestore_conference_date}")
                    else:
                        latest_firestore_conference_date = None
                        print(f"Invalid 'conference_date' found for {ticker} in Firestore document {doc.id}: {firestore_data.get('conference_date')}")

                fmp_transcripts = fetch_fmp_earnings_transcripts(ticker, start_date_filter=latest_firestore_conference_date)
                print(f"Fetched {len(fmp_transcripts)} potential new transcripts from FMP for {ticker}.")

                for fmp_transcript_data in fmp_transcripts:
                    fmp_conf_date_str = fmp_transcript_data.get("date")
                    fmp_quarter = fmp_transcript_data.get("quarter") or fmp_transcript_data.get("period")
                    fmp_year = fmp_transcript_data.get("year") or fmp_transcript_data.get("fiscalYear")

                    if not fmp_conf_date_str or fmp_quarter is None or fmp_year is None:
                        print(f"Skipping FMP transcript for {ticker} due to missing date/quarter/year: {fmp_transcript_data}")
                        continue
                    
                    fmp_conference_date = parse_fmp_date_string(fmp_conf_date_str)
                    
                    if not fmp_conference_date:
                        print(f"Skipping FMP transcript for {ticker} with unparsable date format: {fmp_conf_date_str}")
                        continue

                    existing_doc_query = collection_ref\
                        .where("ticker", "==", ticker)\
                        .where("conference_date", "==", fmp_conference_date)\
                        .limit(1)
                    
                    existing_docs = existing_doc_query.stream()
                    if any(True for _ in existing_docs):
                        print(f"Transcript for {ticker} on {fmp_conf_date_str} already exists. Skipping.")
                        continue

                    if latest_firestore_conference_date and fmp_conference_date <= latest_firestore_conference_date:
                        print(f"Transcript for {ticker} on {fmp_conf_date_str} is older than or equal to latest recorded {latest_firestore_conference_date}. Skipping (already processed).")
                        continue

                    # Transform FMP data to basic Firestore document structure
                    firestore_doc = transform_fmp_to_firestore_doc(fmp_transcript_data)

                    # --- AI Analysis with Gemini for new transcripts ---
                    transcript_text_to_analyze = firestore_doc.get("transcript")
                    if transcript_text_to_analyze and GEMINI_API_KEY: # Only run AI if transcript exists and API key is set
                        print(f"Analyzing transcript for {ticker} on {fmp_conf_date_str} with Gemini.")
                        gemini_analysis_result = analyze_transcript_with_gemini(
                            transcript_text=transcript_text_to_analyze,
                            ticker=ticker,
                            conference_date=fmp_conference_date
                        )

                        if gemini_analysis_result:
                            firestore_doc["alphaConfidence"] = gemini_analysis_result.get("confidence_score")
                            firestore_doc["extractedAlpha"] = gemini_analysis_result.get("ExtractedAlpha")
                            firestore_doc["sentiment"] = gemini_analysis_result.get("sentiment")
                            firestore_doc["summary"] = gemini_analysis_result.get("summary")
                            # alphaReferences and transcript_by_speaker are already initialized as [] in transform_fmp_to_firestore_doc
                        else:
                            print(f"Gemini analysis failed or returned no data for {ticker} on {fmp_conf_date_str}. AI fields will remain None.")
                    elif not GEMINI_API_KEY:
                        print(f"Gemini API Key not configured. Skipping AI analysis for {ticker} on {fmp_conf_date_str}.")
                    else:
                        print(f"No transcript content for AI analysis for {ticker} on {fmp_conf_date_str}.")

                    # Add document to Firestore.
                    collection_ref.add(firestore_doc)
                    new_transcripts_added += 1
                    tickers_with_updates.append(ticker)
                    print(f"Added new transcript for {ticker} on {fmp_conf_date_str}.")

            except Exception as e:
                print(f"Error processing ticker {ticker}: {e}", exc_info=True)
                errors_by_ticker[ticker] = str(e)

        response_message = f"Ingestion process completed. Processed {total_tickers_processed} tickers. Added {new_transcripts_added} new transcripts."
        if errors_by_ticker:
            response_message += f" Errors occurred for {len(errors_by_ticker)} tickers."
            status_code = 500
        else:
            status_code = 200

        response = {
            "status": "success" if not errors_by_ticker else "partial_success",
            "message": response_message,
            "new_transcripts_added_count": new_transcripts_added,
            "tickers_with_updates": sorted(list(set(tickers_with_updates))),
            "errors": errors_by_ticker
        }

        return response

    except Exception as e:
        print(f"Critical error during earnings call ingestion: {e}", exc_info=True)
        return ({
            "status": "error",
            "message": f"An unhandled error occurred during ingestion: {str(e)}"
        }), 500