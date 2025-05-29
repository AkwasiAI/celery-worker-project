# price_forecaster_firestore.py

import os
import json
import datetime as dt 
import logging
import time
from typing import List, Dict, Any, Tuple, Optional

import requests
from sklearn.metrics import mean_squared_error, r2_score
import numpy as np
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] %(message)s",
#     filename="price_forecaster_firestore.log",
#     filemode="w"
# )
log = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("google.generativeai").setLevel(logging.INFO)
logging.getLogger("google.api_core").setLevel(logging.INFO)

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FMP_API_KEY = os.getenv("FMP_API_KEY")
FIRESTORE_PROJECT_ID = os.getenv("FIRESTORE_PROJECT", "hedgefundintelligence")
FIRESTORE_DATABASE_ID = os.getenv("FIRESTORE_DATABASE", "hedgefundintelligence")

if not GEMINI_API_KEY: raise ValueError("GEMINI_API_KEY is missing.")
if not FMP_API_KEY: raise ValueError("FMP_API_KEY is missing.")
if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
    log.warning("GOOGLE_APPLICATION_CREDENTIALS environment variable not set.")

GEMINI_MODEL = ChatGoogleGenerativeAI(
    model="gemini-1.5-pro-latest", temperature=0.2, GEMINI_API_KEY=GEMINI_API_KEY
)
log.info(f"LLM initialized with Google Gemini model: {GEMINI_MODEL.model}")


import datetime as dt # Your alias (keep this one)

def convert_firestore_timestamps_to_iso(data: Any) -> Any:
    """
    Recursively traverses a data structure (dict or list) and converts
    datetime.datetime and datetime.date objects to ISO 8601 strings.
    """
    if isinstance(data, dict):
        return {k: convert_firestore_timestamps_to_iso(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_firestore_timestamps_to_iso(i) for i in data]
    # Firestore usually converts its timestamps to datetime.datetime objects in Python
    elif isinstance(data, dt.datetime): # This should catch Firestore timestamps
        return data.isoformat()
    elif isinstance(data, dt.date): # Handle date objects if they exist separately
        return data.isoformat()
    return data


class PriceForecastFirestore:
    def __init__(self, project_id: str, database_id: str):
        try:
            self.db = firestore.Client(project=project_id, database=database_id)
            log.info(f"Firestore client initialized for project '{project_id}', database '{database_id}'.")
        except Exception as e:
            log.critical(f"Failed to initialize Firestore client: {e}", exc_info=True)
            raise

    def _set_latest_flag(self, collection_name: str, doc_type: str, specific_filter_field: Optional[str] = None, specific_filter_value: Optional[Any] = None):
        col_ref = self.db.collection(collection_name)
        query = col_ref.where(filter=FieldFilter("doc_type", "==", doc_type)).where(filter=FieldFilter("is_latest", "==", True))
        if specific_filter_field and specific_filter_value is not None: # Check for None explicitly
            query = query.where(filter=FieldFilter(specific_filter_field, "==", specific_filter_value))
        
        for doc in query.stream():
            log.debug(f"Setting is_latest=False for old doc: {doc.id} in {collection_name}")
            doc.reference.update({"is_latest": False})

    def save_document(self, collection_name: str, doc_type: str, data: Dict[str, Any], 
                      unique_field_for_latest: Optional[str] = None, unique_value: Optional[Any] = None) -> str:
        try:
            if unique_field_for_latest and unique_value is not None:
                self._set_latest_flag(collection_name, doc_type, unique_field_for_latest, unique_value)
            elif not unique_field_for_latest:
                 self._set_latest_flag(collection_name, doc_type)

            doc_ref = self.db.collection(collection_name).document()
            payload = {
                **data, "doc_type": doc_type, "timestamp": firestore.SERVER_TIMESTAMP,
                "created_at_script": dt.datetime.now(dt.timezone.utc), "is_latest": True
            }
            doc_ref.set(payload)
            log.info(f"Saved {doc_type} document with ID: {doc_ref.id} to {collection_name}.")
            return doc_ref.id
        except Exception as e:
            log.error(f"Error saving {doc_type} document to {collection_name}: {e}", exc_info=True)
            raise

    def load_latest_document(self, collection_name: str, doc_type: str, 
                             unique_field_for_latest: Optional[str] = None, unique_value: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        try:
            col_ref = self.db.collection(collection_name)
            query = col_ref.where(filter=FieldFilter("doc_type", "==", doc_type)).where(filter=FieldFilter("is_latest", "==", True))
            
            # If we are filtering by another unique field for "latest" (e.g., prediction_date)
            if unique_field_for_latest and unique_value is not None:
                query = query.where(filter=FieldFilter(unique_field_for_latest, "==", unique_value))
            
            # If you GUARANTEE only one document will have is_latest: true (for the given doc_type and optional unique_value)
            # then ordering by timestamp might not be strictly necessary to find *that one* document.
            # However, including it is safer if the guarantee might be broken.
            # For news_scratchpad, if only ONE is_latest:true globally for that doc_type, this simpler query might work:
            if collection_name == "news_scratchpad" and doc_type == "news_scratchpad" and not unique_field_for_latest:
                 log.debug(f"Using simplified query for globally latest {doc_type} in {collection_name}")
                 # No order_by here, relies on the guarantee of a single 'is_latest: true'
            else:
                # For other cases or for safety, keep the order_by
                query = query.order_by("timestamp", direction=firestore.Query.DESCENDING)

            query = query.limit(1) # Still limit to 1, just in case
            
            docs = list(query.stream())
            if not docs:
                log.warning(f"No latest '{doc_type}' document found in '{collection_name}'"
                            f"{f' for {unique_field_for_latest}={unique_value}' if unique_field_for_latest else ''}.")
                return None
            
            data = docs[0].to_dict()
            # Add document ID to the returned data, can be useful
            data['id'] = docs[0].id 
            log.info(f"Loaded latest '{doc_type}' document ID: {docs[0].id} from '{collection_name}'.")
            return data
        except Exception as e:
            log.error(f"Error loading latest '{doc_type}' document from '{collection_name}': {e}", exc_info=True)
            return None


try:
    firestore_helper = PriceForecastFirestore(project_id=FIRESTORE_PROJECT_ID, database_id=FIRESTORE_DATABASE_ID)
except Exception:
    log.critical("Failed to initialize PriceForecastFirestore. Exiting.")
    firestore_helper = None

TICKERS_TO_PREDICT = [
    # --- Part 1: Symbols Confirmed Working in Last Test (88 symbols) ---
    "HAFNI.OL", "STNG", "TRMD", "FRO", "ECO", "DHT", "EURN.BR", "INSW", "NAT", "TEN",
    "IMPP", "PSHG", "TORO", "TNK", "PXS", "TOPS", "DSX", "GNK", "GOGL", "NMM",
    "SB", "SBLK", "SHIP", "HSHP.OL", "EDRY", "CTRM", "ICON", "GLBS", "CMRE", "DAC",
    "GSL", "ESEA", "MPCC.OL", "ZIM", "SFL", "MAERSK-B.CO", "BWLPG.OL", "LPG", "CCEC", "GASS",
    "DLNG", "AGAS.OL", "ALNG.OL", "FLNG", "RIG", "HLX", "PRS", "SBMO.AS", "TDW", "RIO",
    "BHP", "VALE", "GLNCY", "ADM", "WLMIY", "BG", "SHEL", "XOM", "CVX", "TTE",
    "WPM", "GOLD", "CLF", "ALB", "MOS", "BDRY", "BWET",
    "CCMP", "CAC", "DAX", "IBEX", "SMI",
    "2020.OL", "JIN.OL", "BELCO.OL", "COOL.OL", "SPM.MI",
    "^DJI", "^GSPC", "^GSPTSE", "^MXX", "^BVSP", "^STOXX50E", "^FTSE",
    "^N225", "^HSI", "^AXJO",
]

# --- Part 2: Symbols That Failed Last Test (2 symbols - for re-test) ---
# "^FTMIB",       # FTSE MIB Italy
# "000300.SS",    # CSI 300 Shanghai

# --- Part 3: Items Previously Set Aside (14 symbols - mostly expected to fail with /quote/) ---
# Commodity Codes:
# "RBTA",
# "CLA",
# "COA",
# "QSA",
# "XBA",
# "HOA",
# "NGA",
# "TZTA",
# "LMAHDS03",
# "LMCADS03",
# "LMNIDS03",
# "IOEA",
# Generic Index Placeholders:
# "OMX",
# "WORLD"


PRICE_PREDICTION_PROMPT_TEMPLATE = """
You are a sophisticated financial analyst AI. Your task is to predict the **next trading day's closing price** for a list of stock tickers.
Today's date is: {current_date_iso}
The prediction should be for the close of the *next trading day*.

Consider the following inputs:
1.  **Current Market Prices:**
    {current_prices_json}

2.  **Recent News Summary (from today):**
    --- NEWS START ---
    {todays_news_summary_text}
    --- NEWS END ---

Based on all this information, provide your price predictions.
For each ticker, output a single predicted closing price for the next trading day.
Be realistic. Drastic overnight changes are rare unless driven by major specific news for that stock.
The news summary provides general market sentiment and key events.

Output your predictions ONLY as a JSON object where keys are the ticker symbols (exactly as provided in current prices) and values are the predicted numerical prices. Do not include any other text, explanation, or markdown.

Example Output:
{{
  "AAPL": 175.50,
  "MSFT": 330.20,
  "GOOGL": 140.10
}}
"""

def fetch_current_prices(tickers: List[str]) -> Dict[str, float | None]:
    log.info(f"Fetching current prices for {len(tickers)} tickers.")
    prices = {}
    batch_size = 50 
    for i in range(0, len(tickers), batch_size):
        batch_tickers = tickers[i:i+batch_size]
        symbols_str = ",".join(batch_tickers)
        url = f"https://financialmodelingprep.com/api/v3/quote/{symbols_str}?apikey={FMP_API_KEY}"
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status() 
            data = response.json()
            if isinstance(data, list):
                for stock_data in data:
                    if isinstance(stock_data, dict) and 'symbol' in stock_data and 'price' in stock_data:
                        prices[stock_data['symbol']] = float(stock_data['price']) if stock_data['price'] is not None else None
        except Exception as e: # Catch broader exceptions for robustness
            log.error(f"Error during price fetching for batch {symbols_str}: {e}")
        time.sleep(0.2) # Shorter sleep
        
    for ticker in tickers:
        if ticker not in prices: prices[ticker] = None
    log.info(f"Fetched prices for {len([p for p in prices.values() if p is not None])} of {len(tickers)} tickers.")
    return prices

def predict_next_day_prices(
    tickers: List[str],
    prediction_date_iso: str # The date for which predictions are being made
) -> Optional[Dict[str, float | None]]: # No longer takes news_summary as argument
    """
    Fetches today's news from Firestore, then predicts next day's prices.
    Saves predictions and the used news summary to Firestore.
    """
    if not firestore_helper: return None
    log.info(f"Starting price prediction for {prediction_date_iso} (predicting for next trading day's close).")

    # Fetch today's news summary from Firestore
    # Based on your screenshot: collection="news_scratchpad", doc_type="news_scratchpad"
    # The field containing the text is "total_content"
    log.info(f"Fetching latest news summary from Firestore for date {prediction_date_iso}...")
    latest_news_doc = firestore_helper.load_latest_document(
        collection_name="news_scratchpad",
        doc_type="news_scratchpad",
         # Assuming this is the doc_type value
        # If news_scratchpad documents are also dated, you might add:
        # unique_field_for_latest="some_date_field_in_news_scratchpad",
        # unique_value=prediction_date_iso
    )

    if not latest_news_doc or "total_content" not in latest_news_doc:
        log.error(f"Could not find latest news summary ('total_content' in 'news_scratchpad') in Firestore. Cannot proceed with prediction.")
        return None
    todays_news_summary_text = latest_news_doc["total_content"]
    log.info(f"Successfully loaded news summary for {prediction_date_iso} from Firestore.")

    current_prices = fetch_current_prices(tickers)
    if not any(price is not None for price in current_prices.values()):
        log.error("Failed to fetch any current prices. Cannot proceed with prediction.")
        return None

    valid_current_prices = {k: v for k,v in current_prices.items() if v is not None}
    if not valid_current_prices:
        log.error("No valid current prices to use for prediction after filtering.")
        return None

    prompt_content = PRICE_PREDICTION_PROMPT_TEMPLATE.format(
        current_date_iso=prediction_date_iso,
        current_prices_json=json.dumps(valid_current_prices, indent=2),
        todays_news_summary_text=todays_news_summary_text
    )
    messages = [SystemMessage(content="You are a specialized financial price prediction AI."), HumanMessage(content=prompt_content)]

    log.info("Calling Gemini for price predictions...")
    predicted_prices_payload: Dict[str, float | None] = {ticker: None for ticker in tickers}

    try:
        response = GEMINI_MODEL.invoke(messages)
        raw_llm_output = response.content.strip()
        log.debug(f"Raw LLM prediction output: {raw_llm_output}")
        json_string = raw_llm_output
        if json_string.startswith("```json"): json_string = json_string.lstrip("```json").rstrip("```").strip()
        elif json_string.startswith("```"): json_string = json_string.lstrip("```").rstrip("```").strip()
        
        parsed_predictions = json.loads(json_string)
        for ticker in tickers:
            if ticker in parsed_predictions:
                try: predicted_prices_payload[ticker] = float(parsed_predictions[ticker])
                except (ValueError, TypeError): log.warning(f"LLM non-float prediction for {ticker}: {parsed_predictions[ticker]}.")
            else: log.warning(f"LLM no prediction for ticker: {ticker}.")
    except Exception as e:
        log.error(f"Error during LLM price prediction or parsing: {e}", exc_info=True)

    try:
        firestore_helper.save_document(
            collection_name="price_forecast_data", doc_type="predictions",
            data={"prediction_date": prediction_date_iso, "prices": predicted_prices_payload},
            unique_field_for_latest="prediction_date", unique_value=prediction_date_iso
        )
        # Save the news summary that was *used* for this prediction run
        firestore_helper.save_document(
            collection_name="price_forecast_data", doc_type="news_summary_for_prediction_run", # Differentiate from general news_scratchpad
            data={"prediction_date": prediction_date_iso, "news_text_used": todays_news_summary_text, "source_news_doc_id": latest_news_doc.get("id", "N/A") if latest_news_doc else "N/A"},
            unique_field_for_latest="prediction_date", unique_value=prediction_date_iso
        )
        log.info(f"Price predictions and used news summary for {prediction_date_iso} saved to Firestore.")
        return predicted_prices_payload
    except Exception as e:
        log.error(f"Failed to save predictions/news for {prediction_date_iso} to Firestore: {e}")
        return None

# === Function 2: Evaluate Predictions ===
def evaluate_predictions(
    prediction_date_iso: str, 
    evaluation_date_iso: str  
) -> Optional[Dict[str, Any]]:
    if not firestore_helper: return None
    log.info(f"Starting prediction evaluation. Predictions on {prediction_date_iso}, actuals from {evaluation_date_iso}.")

    prediction_doc_data = firestore_helper.load_latest_document("price_forecast_data", "predictions", "prediction_date", prediction_date_iso)
    if not prediction_doc_data or "prices" not in prediction_doc_data:
        log.error(f"Predictions for {prediction_date_iso} not found in Firestore.")
        return None
    predicted_prices: Dict[str, float | None] = prediction_doc_data["prices"]
    
    tickers_with_predictions = [t for t, p in predicted_prices.items() if p is not None]
    if not tickers_with_predictions: return {"error": "No valid predictions to evaluate."}

    actual_prices_dict = fetch_current_prices(tickers_with_predictions)
    y_true_list, y_pred_list, per_ticker_perf = [], [], {}
    for ticker in tickers_with_predictions:
        pred_p, actual_p = predicted_prices.get(ticker), actual_prices_dict.get(ticker)
        if pred_p is not None and actual_p is not None:
            y_true_list.append(actual_p); y_pred_list.append(pred_p)
            per_ticker_perf[ticker] = {"predicted": pred_p, "actual": actual_p, "error": pred_p - actual_p, "abs_percentage_error": abs((pred_p - actual_p) / actual_p) * 100 if actual_p != 0 else float('inf')}
        else:
            per_ticker_perf[ticker] = {"predicted": pred_p, "actual": actual_p, "error": "N/A", "abs_percentage_error": "N/A"}

    if not y_true_list: return {"error": "Insufficient data for metrics.", "per_ticker_performance": per_ticker_perf}

    mse, rmse, r2 = mean_squared_error(y_true_list, y_pred_list), np.sqrt(mean_squared_error(y_true_list, y_pred_list)), r2_score(y_true_list, y_pred_list)
    
    results = {
        "prediction_date": prediction_date_iso, "evaluation_date": evaluation_date_iso,
        "num_evaluated_tickers": len(y_true_list),
        "metrics": {"mse": mse, "rmse": rmse, "r_squared": r2},
        "per_ticker_performance": per_ticker_perf
    }
    log.info(f"Eval Metrics: MSE={mse:.4f}, RMSE={rmse:.4f}, R2={r2:.4f}")

    try:
        eval_doc_id = f"eval_{prediction_date_iso}_vs_{evaluation_date_iso}"
        firestore_helper.save_document(
            "price_forecast_data", "prediction_evaluation",
            {"eval_id": eval_doc_id, **results},
            "prediction_date", prediction_date_iso
        )
        return results
    except Exception as e:
        log.error(f"Failed to save evaluation {eval_doc_id} to Firestore: {e}")
        return None


# === Function 3: Generate Key Takeaways/Learnings ===
LEARNINGS_PROMPT_TEMPLATE = """
You are an AI assistant tasked with generating key learnings from a price prediction exercise.
Today's date is: {evaluation_date_iso}

You are provided with:
1.  **Price Predictions made on {prediction_date_iso} (for {evaluation_date_iso} close):**
    {predicted_prices_json}

2.  **Prediction Performance Evaluation Results (actuals, metrics, per-ticker):**
    {evaluation_results_json}
    
3.  **News Summary from {prediction_date_iso} (this news influenced the predictions):**
    --- NEWS START ---
    {news_summary_from_prediction_date}
    --- NEWS END ---

4.  **Portfolio Agent Scratchpad/Reasoning from {prediction_date_iso} (if available, this shows other agent thoughts that might have informed a broader outlook):**
    --- SCRATCHPAD START ---
    {portfolio_scratchpad_text}
    --- SCRATCHPAD END ---

Based on ALL the above information, analyze the prediction performance and derive 3-5 key takeaways or learnings.
Focus on:
-   Overall accuracy (qualitative assessment based on metrics and context).
-   Were there any particular tickers or groups of tickers where predictions were notably good or bad? Why might that be, considering the news or lack thereof?
-   Did the news on {prediction_date_iso} seem to correctly inform the predictions, or were there surprising outcomes?
-   What patterns or factors (e.g., specific news items, market sentiment, model biases) might have contributed to the prediction accuracy or inaccuracy?
-   What could be learned or adjusted for future prediction attempts? (e.g., pay more attention to certain news types, consider volatility, etc.)

Structure your output as a concise, bulleted list of key takeaways in Markdown format.
Be insightful and actionable.
"""

def generate_learnings_from_predictions(
    prediction_date_iso: str,
    evaluation_date_iso: str,
) -> Optional[str]:
    if not firestore_helper: return None
    log.info(f"Generating learnings for predictions on {prediction_date_iso}, evaluated on {evaluation_date_iso}.")

    predicted_prices_doc_raw = firestore_helper.load_latest_document("price_forecast_data", "predictions", "prediction_date", prediction_date_iso)
    evaluation_results_doc_raw = firestore_helper.load_latest_document("price_forecast_data", "prediction_evaluation", "prediction_date", prediction_date_iso)
    news_summary_used_doc_raw = firestore_helper.load_latest_document("price_forecast_data", "news_summary_for_prediction_run", "prediction_date", prediction_date_iso)
    
    portfolio_scratchpad_data_raw = firestore_helper.load_latest_document(
        collection_name="portfolio_scratchpad",
        doc_type="portfolio_scratchpad",
        unique_field_for_latest="created_at_date_str_ref", 
        unique_value=prediction_date_iso
    )
    
    if not all([predicted_prices_doc_raw, evaluation_results_doc_raw, news_summary_used_doc_raw]):
        log.error(f"Missing data from Firestore for {prediction_date_iso} to generate learnings.")
        return None

    # Clean the documents by converting timestamps BEFORE serializing to JSON for the prompt
    predicted_prices_for_prompt = convert_firestore_timestamps_to_iso(predicted_prices_doc_raw.get("prices", {}))
    evaluation_results_for_prompt = convert_firestore_timestamps_to_iso(evaluation_results_doc_raw)
    news_summary_for_prompt = convert_firestore_timestamps_to_iso(news_summary_used_doc_raw) # just in case it has timestamps
    
    portfolio_scratchpad_text = convert_firestore_timestamps_to_iso(portfolio_scratchpad_data_raw.get("total_content", "Portfolio scratchpad not available for this date.")) if portfolio_scratchpad_data_raw else "Portfolio scratchpad not found."
    # If total_content itself is a complex object with timestamps, apply conversion. If it's just a string, this won't harm.
    # If portfolio_scratchpad_data_raw itself needs to be json.dumps'd, convert it too.
    # Assuming portfolio_scratchpad_text is the final string needed for the prompt.

    predicted_prices_json_str = json.dumps(predicted_prices_for_prompt, indent=2)
    evaluation_results_json_str = json.dumps(evaluation_results_for_prompt, indent=2)
    news_text_for_learnings = news_summary_for_prompt.get("news_text_used", "News summary used for prediction not found.") if isinstance(news_summary_for_prompt, dict) else "News summary format error."
    
    prompt_content = LEARNINGS_PROMPT_TEMPLATE.format(
        prediction_date_iso=prediction_date_iso, evaluation_date_iso=evaluation_date_iso,
        predicted_prices_json=predicted_prices_json_str, 
        evaluation_results_json=evaluation_results_json_str, # This now contains ISO strings for dates
        news_summary_from_prediction_date=news_text_for_learnings,
        portfolio_scratchpad_text=portfolio_scratchpad_text
    )
    messages = [SystemMessage(content="You are an AI assistant specialized in deriving insights from financial prediction performance."), HumanMessage(content=prompt_content)]

    log.info("Calling Gemini for generating learnings...")
    learnings_markdown = "Error: LLM call for learnings failed."
    try:
        response = GEMINI_MODEL.invoke(messages)
        learnings_markdown = response.content.strip()
        log.info("Learnings generated successfully.")
    except Exception as e:
        log.error(f"Error during LLM call for learnings: {e}", exc_info=True)

    try:
        learnings_doc_id = f"learnings_{evaluation_date_iso}_for_pred_{prediction_date_iso}"
        # Data being saved to Firestore can retain Firestore Timestamps if you want
        # The conversion was primarily for json.dumps for the prompt
        firestore_helper.save_document(
            "price_forecast_data", "prediction_learnings",
            {"learnings_id": learnings_doc_id, "prediction_date_ref": prediction_date_iso,
             "evaluation_date": evaluation_date_iso, "learnings_markdown": learnings_markdown,
             # Optionally include references to the raw docs used
             "source_prediction_doc": predicted_prices_doc_raw, # This will save with Firestore timestamps
             "source_evaluation_doc": evaluation_results_doc_raw, # This will save with Firestore timestamps
             "source_news_doc": news_summary_used_doc_raw
            },
            "learnings_id", learnings_doc_id
        )
        return learnings_markdown
    except Exception as e:
        log.error(f"Failed to save learnings {learnings_doc_id} to Firestore: {e}")
        return None