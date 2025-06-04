import datetime as dt 
from portfolio_generator.modules.reward_eval import predict_next_day_prices, firestore_helper, evaluate_predictions, generate_learnings_from_predictions

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
    "^N225", "^HSI", "^AXJO" ]

    # # # --- Part 2: Symbols That Failed Last Test (2 symbols - for re-test) ---
    # "FTSEMIB.MI",       # FTSE MIB Italy
    # "000300.SS",    # CSI 300 Shanghai
    # "CL=F", # "CLA",
    # "BZ=F", # "COA",
    # "HO=F", # "HOA",
    # "NG=F", # "NGA",
    # "TTF=F", # "TZTA",
    # "^OMX", # "OMX",

    # # --- Part 3: Items Previously Set Aside (14 symbols - mostly expected to fail with /quote/) ---
    # # Commodity Codes:
    # "RBTA",

    # "QSA",
    # "XBA",

    # "LMAHDS03",
    # "LMCADS03",
    # "LMNIDS03",
    # "IOEA",
    # # Generic Index Placeholders:
    # "WORLD"




if not firestore_helper:
    print("Firestore helper not initialized. Cannot run example workflow.")
    exit()
    
print("---  Price Forecaster Script (with Firestore) ---")


import datetime as dt

def predict_tomorrow():
    """
    Makes predictions for tomorrow using sample news and saves results.
    """
    prediction_day_iso = dt.date.today().isoformat()
    print(f"Making predictions for tomorrow based on sample news.")

    predicted_prices_today = predict_next_day_prices(
        tickers=TICKERS_TO_PREDICT,
        prediction_date_iso=prediction_day_iso
        # No news_summary argument needed here anymore
    )
    if predicted_prices_today:
        print(f"Predictions made and saved.")
    else:
        print(f"Failed to make or save predictions.")


def evaluate_yesterday():
    """
    Evaluates yesterday's predictions, generates learnings, and saves results.
    """
    yesterday_iso = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    today_iso_eval = dt.date.today().isoformat()

    # Check if predictions for yesterday exist before trying to evaluate
    if firestore_helper.load_latest_document("price_forecast_data", "predictions", "prediction_date", yesterday_iso):
        print(f"\n--- Attempting Evaluation for predictions made on {yesterday_iso} ---")
        evaluation_output = evaluate_predictions(
            prediction_date_iso=yesterday_iso,
            evaluation_date_iso=today_iso_eval
        )
        if evaluation_output and "error" not in evaluation_output:
            print(f"Evaluation complete for predictions from {yesterday_iso}.")

            # No need to pass news/scratchpad text to generate_learnings, it will load them.
            print(f"\n--- Attempting to Generate Learnings for predictions from {yesterday_iso} ---")
            learnings = generate_learnings_from_predictions(
                prediction_date_iso=yesterday_iso,
                evaluation_date_iso=today_iso_eval
            )
            if learnings:
                print("Learnings document generated and saved.")
                print("\nGenerated Learnings:\n", learnings)
            else:
                print("Could not generate or save learnings document.")
        elif evaluation_output:
            print(f"Evaluation failed: {evaluation_output.get('error')}")
        else:
            print(f"Evaluation could not be performed or saved for predictions from {yesterday_iso}.")
    else:
        print(f"No predictions found for {yesterday_iso} in Firestore. Skipping evaluation and learning for this date.")

    print("--- Price Forecaster Script (with Firestore) Finished ---")