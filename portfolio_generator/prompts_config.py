# Prompt templates for report generation

SHIPPING_INDUSTRY_PROMPT = '''Write a detailed analysis (aim for approximately {per_section_word_count} words) of the Shipping Industry as part of an investment portfolio report.
Include:
- Container shipping market dynamics with specific freight rates
- Dry bulk shipping trends and key routes with rate data
- Tanker market analysis and oil shipping routes
- Major shipping companies performance and outlook with specific companies
- Port congestion and logistics bottlenecks with wait time statistics
- Fleet capacity and orderbook analysis with specific tonnage figures
- Shipping regulation changes and environmental initiatives
- Charter rate trends and forecasts with specific rate ranges

Format in markdown starting with:
## Shipping Industry
'''

CONCLUSION_OUTLOOK_PROMPT = '''Write a concise conclusion and outlook (aim for approximately {per_section_word_count} words) for an investment portfolio report.
Include:
- Summary of key portfolio positioning and investment thesis
- Forward-looking market expectations with timeframes
- Upcoming catalysts to monitor with specific dates where possible
- Potential portfolio adjustments to consider
- Long-term strategic themes guiding investment decisions
- Tactical opportunities on the horizon
- Key risks to the investment outlook
- Final investment recommendations and action items

Format in markdown starting with:
## Conclusion & Outlook
'''

REFERENCES_SOURCES_PROMPT = '''Create a properly formatted references and sources section for the investment portfolio report. 

Only use the web searches provided to generate the references and sources section.

Format in markdown starting with:
## References & Sources
'''

RISK_ASSESSMENT_PROMPT = '''Write a detailed analysis (aim for approximately {per_section_word_count} words for the whole section) of Risk Assessment as part of an investment portfolio report. 
Look specifically at the portfolio weights and use them to generate the markdown. 

Web searches with the latest data have been provided use them if need be.

Write analysis for the following under the following headers : 

1. Overview 
2. Key Risk Factors by Asset & Portfolio
3. Value-at-Risk (VaR) & Stress Testing
4. Correlation Matrix (12-m daily returns)
5. Monitoring Framework
6. Hedging Strategies
7. Liquidity Risk Assessment
8. Concentration Risk Analysis

Format in markdown starting with:
## Risk Assessment
'''

GLOBAL_TRADE_ECONOMY_PROMPT = '''Write a concise but comprehensive analysis (aim for approximately {per_section_word_count} words) of Global Trade & Economy as part of a macroeconomic outlook section.
Include:
- Regional breakdowns and economic indicators with specific figures
- GDP growth projections by region with exact percentages
- Trade flow statistics with exact volumes and year-over-year changes
- Container throughput at major ports with specific TEU figures
- Supply chain metrics and logistics indicators
- Currency valuations and impacts on trade relationships
- Trade agreements and policy changes with implementation timelines
- Inflation rates across major economies with comparisons

Format in markdown starting with:
## Global Trade & Economy
'''

PORTFOLIO_HOLDINGS_PROMPT = '''Write a detailed analysis (aim for approximately {per_section_word_count} words) of the current Portfolio Holdings as part of an investment portfolio report.
Include:
- Individual analysis of key positions with specific entry rationales
- Sector allocation strategy and rationale
- Geographic exposure analysis
- Position sizing methodology
- Risk management approach for current holdings
- Expected holding periods and exit strategies for major positions
- Recent portfolio changes and the rationale behind them
- Correlation analysis between holdings

Format in markdown starting with:
## Portfolio Holdings
'''

ENERGY_MARKETS_PROMPT = '''Write a detailed analysis (aim for approximately {per_section_word_count} words) of Energy Markets as part of an investment portfolio report.
Include:
- Oil markets: production, demand, and price forecasts with specific data points
- Natural gas markets: regional analysis and price dynamics
- Renewable energy growth and investment opportunities with specific companies
- Energy transition trends and policy impacts
- Geopolitical factors affecting energy markets
- Supply constraints and infrastructure developments
- Commodity trader positioning in energy markets

Format in markdown starting with:
## Energy Markets
'''

COMMODITIES_MARKETS_PROMPT = '''Write a detailed analysis (aim for approximately {per_section_word_count} words) of Commodities Markets as part of an investment portfolio report.
Include:
- Precious metals market analysis (gold, silver, platinum) with specific price targets
- Industrial metals outlook (copper, aluminum, nickel) with supply/demand figures
- Agricultural commodities trends and price forecasts
- Soft commodities market dynamics
- Commodity-specific factors driving price movements
- Seasonal patterns and historical context
- Warehousing and inventory levels with specific data points

Format in markdown starting with:
## Commodities Markets
'''

BENCHMARKING_PERFORMANCE_PROMPT = '''Write a detailed analysis (aim for approximately {per_section_word_count} words) of Portfolio Benchmarking & Performance as part of an investment portfolio report.
Include:
- Performance comparison to relevant benchmarks with specific percentage figures
- Attribution analysis by sector and asset class
- Risk-adjusted return metrics (Sharpe, Sortino, etc.) with specific values
- Volatility analysis compared to markets
- Drawdown analysis and recovery periods
- Factor exposure analysis (value, momentum, quality, etc.)
- Historical performance in similar market environments
- Performance of specific investment themes within the portfolio

Format in markdown starting with:
## Benchmarking & Performance
'''

EXECUTIVE_SUMMARY_DETAILED_PROMPT = '''**PROMPT: Generate a Forward-Looking Investment Portfolio Executive Summary**

**Objective:** Create a concise, data-driven executive summary for a hypothetical investment portfolio report, suitable for stakeholders. This summary should focus on the portfolio's **strategic positioning and expected performance drivers** based on the anticipated market environment. Assume this summary is being generated based on a recent portfolio review and strategy setting.

**Core Instructions:**

1.  **Date and Title:**
    *   Start with the title: `Investment Portfolio Executive Summary`
    *   Immediately below the title, include the current date: `{current_date}`

2.  **Content Sections:** Include the following sections, keeping the language clear, professional, and **forward-looking**:
    *   **Portfolio Positioning & Expected Drivers:** Briefly state the portfolio's primary objective based on its current structure (e.g., 'positioned for resilience', 'targeting growth from energy and tankers', 'balanced for anticipated volatility') and highlight the key factors or sectors expected to drive future performance. *Generate a plausible forward-looking statement based on the anticipated market outlook and portfolio construction.*
    *   **Market Outlook:** Provide a concise view of the anticipated market environment (e.g., inflation trends, interest rate expectations, geopolitical risks/opportunities, specific sector forecasts like energy prices or shipping rates). Keep it high-level and forward-looking. *Ensure this outlook directly informs the Portfolio Strategy & Positioning.*
    *   **Portfolio Strategy & Positioning Rationale:** Explain *how* the portfolio is strategically positioned to capitalize on the anticipated market outlook and Orasis' core investment thesis (global trade shifts, shipping as a leading indicator). Emphasize *why* this positioning is expected to generate positive returns or manage risk effectively going forward. *Ground this in Orasis Investment Principles where applicable.*

3.  **CRITICAL REQUIREMENT: Portfolio Holdings Table:**
    *   You MUST include a comprehensive summary table displaying the *current* portfolio positions, reflecting the forward-looking strategy.
    *   **Portfolio Construction:** Select **10 to 15 tickers** from the `PREFERRED_TICKERS` list below. Aim for diversification across categories that align with the forward-looking strategy. *Consider George's preferred time horizon distribution (~30% <3mo, ~30% 3-6mo, ~30% 6-12mo, ~10% 1yr+) when assigning Time Horizons.*
    *   **Table Format:** Use Markdown for the table.
    *   **Table Columns:**
        *   `Asset/Ticker`: Use the real, verifiable ticker symbol from the list.
        *   `Position Type`: Assume `Long` for most positions. Include 1-2 genuine `Short` positions if justified by a fundamentally negative forward outlook for that specific asset/sector, explaining the rationale briefly in the main report body (not required in the summary itself).
        *   `Allocation %`: Assign *plausible* percentage allocations. **These MUST sum exactly to 100.0%.** Use one decimal place.
        *   `Time Horizon`: Assign realistic, forward-looking horizons (e.g., `"1-3 months"`, `"3-6 months"`, `"6-12 months"`, `"1-2 years"`, `"2-3 years"`).
        *   `Confidence Level`: Assign a confidence level (e.g., `Medium`, `High`, `Very High`).
    *   **Ticker Source List (PREFERRED_TICKERS):**
        ```csv
        Category,Ticker,Name
        US-Listed Commodity Companies,RIO,Rio Tinto PLC (ADR)
        # ... (rest of the ticker list remains the same as in the previous prompt) ...
        US-Listed Commodity Companies,BHP,BHP Group Ltd (ADR)
        US-Listed Commodity Companies,VALE,Vale SA (ADR)
        US-Listed Commodity Companies,GLNCY,Glencore PLC (ADR)
        US-Listed Commodity Companies,ADM,Archer-Daniels-Midland Co
        US-Listed Commodity Companies,BG,Bunge Global SA
        US-Listed Commodity Companies,SHEL,Shell PLC (ADR)
        US-Listed Commodity Companies,XOM,Exxon Mobil Corp
        US-Listed Commodity Companies,CVX,Chevron Corp
        US-Listed Commodity Companies,TTE,TotalEnergies SE (ADR)
        US-Listed Commodity Companies,WPM,Wheaton Precious Metals Corp
        US-Listed Commodity Companies,GOLD,Barrick Gold Corp
        US-Listed Commodity Companies,CLF,Cleveland-Cliffs Inc
        US-Listed Commodity Companies,ALB,Albemarle Corp
        US-Listed Commodity Companies,MOS,Mosaic Co/The
        Non-US-Listed Commodity Companies,WIL.SI,Wilmar International Ltd (Singapore Exchange)
        US-Listed Shipping Companies,HAFNIA,Hafnia Ltd
        US-Listed Shipping Companies,STNG,Scorpio Tankers Inc
        US-Listed Shipping Companies,TRMD,TORM PLC (ADR)
        US-Listed Shipping Companies,FRO,Frontline PLC
        US-Listed Shipping Companies,OET,Okeanis Eco Tankers Corp
        US-Listed Shipping Companies,DHT,DHT Holdings Inc
        US-Listed Shipping Companies,INSW,International Seaways Inc
        US-Listed Shipping Companies,NAT,Nordic American Tankers Ltd
        US-Listed Shipping Companies,TNP,Tsakos Energy Navigation Ltd
        US-Listed Shipping Companies,IMPP,Imperial Petroleum Inc
        US-Listed Shipping Companies,PSHG,Performance Shipping Inc
        US-Listed Shipping Companies,TORO,Toro Corp
        US-Listed Shipping Companies,TK,Teekay Tankers Ltd
        US-Listed Shipping Companies,PXS,Pyxis Tankers Inc
        US-Listed Shipping Companies,TOPS,TOP Ships Inc
        US-Listed Shipping Companies,DSX,Diana Shipping Inc
        US-Listed Shipping Companies,GNK,Genco Shipping & Trading Ltd
        US-Listed Shipping Companies,GOGL,Golden Ocean Group Ltd
        US-Listed Shipping Companies,NMM,Navios Maritime Partners LP
        US-Listed Shipping Companies,SB,Safe Bulkers Inc
        US-Listed Shipping Companies,SBLK,Star Bulk Carriers Corp
        US-Listed Shipping Companies,SHIP,Seanergy Maritime Holdings Corp
        US-Listed Shipping Companies,CTRM,Castor Maritime Inc
        US-Listed Shipping Companies,GLBS,Globus Maritime Ltd
        US-Listed Shipping Companies,CMRE,Costamare Inc
        US-Listed Shipping Companies,DAC,Danaos Corp
        US-Listed Shipping Companies,GSL,Global Ship Lease Inc
        US-Listed Shipping Companies,ESEA,Euroseas Ltd
        US-Listed Shipping Companies,ZIM,ZIM Integrated Shipping Services
        US-Listed Shipping Companies,SFL,SFL Corp Ltd
        US-Listed Shipping Companies,GASS,StealthGas Inc
        US-Listed Shipping Companies,DLNG,Dynagas LNG Partners LP
        US-Listed Shipping Companies,FLNG,FLEX LNG Ltd
        Non-US-Listed Shipping Companies,CMB.BR,CMB Tech NV
        Non-US-Listed Shipping Companies,2020.OL,2020 Bulkers Ltd
        Non-US-Listed Shipping Companies,HSHIP.OL,Himalaya Shipping Ltd
        Non-US-Listed Shipping Companies,JIN.OL,Jinhui Shipping & Transportation
        Non-US-Listed Shipping Companies,BELCO.OL,Belships ASA
        Non-US-Listed Shipping Companies,ICON,Icon Energy Corp
        Non-US-Listed Shipping Companies,MAERSK-B.CO,AP Moller - Maersk A/S
        Non-US-Listed Shipping Companies,BW LPG.OL,BW LPG Ltd
        Non-US-Listed Shipping Companies,AVANCE.OL,Avance Gas Holding Ltd
        Non-US-Listed Shipping Companies,ALNG.OL,Awilco LNG AS
        Non-US-Listed Shipping Companies,COOL.OL,Cool Co Ltd
        US-Listed Offshore Energy Companies,RIG,Transocean Ltd
        US-Listed Offshore Energy Companies,HLX,Helix Energy Solutions Group Inc
        US-Listed Offshore Energy Companies,TDW,Tidewater Inc
        Non-US-Listed Offshore Energy Companies,PROSE.OL,Prosafe SE
        Non-US-Listed Offshore Energy Companies,SPM.MI,Saipem SpA
        Non-US-Listed Offshore Energy Companies,SBMO.AS,SBM Offshore NV
        Shipping & Tanker ETFs,BDRY,Breakwave Dry Bulk Shipping ETF
        Shipping & Tanker ETFs,BWET,Breakwave Tanker Shipping ETF
        Popular ETFs,SPY,SPDR S&P 500 ETF
        ```

4.  **CRITICAL REQUIREMENT: Hidden JSON Output:**
    *   Immediately following the Markdown table, output a valid JSON array containing objects for each position in the table.
    *   This JSON array MUST be enclosed within an HTML comment block: `<!-- PORTFOLIO_POSITIONS_JSON: ... -->` so it is not visible in the rendered output.
    *   Use the following JSON structure for each object:
        {{"asset": "...", "position_type": "...", "allocation_percent": ..., "time_horizon": "...", "confidence_level": "..."}} (Note: `allocation_percent` should be a number, not a string; `time_horizon` should be a string like `"1-3 months"`).
    *   Ensure the JSON perfectly matches the data presented in the Markdown table.

5.  **Asset Allocation Overview:**
    *   After the hidden JSON block, include a brief (1-2 sentences) qualitative summary of the portfolio's allocation breakdown by major asset category (e.g., "The portfolio is strategically weighted towards Energy (X%) and Tanker Shipping (Y%), reflecting our positive outlook, with diversifying positions in Commodities (Z%) and Broad Market ETFs (W%)."). *Calculate approximate category percentages based on the table you generated.*

6.  **Constraints:**
    *   The entire output (including table and hidden JSON) should aim to be concise, ideally under **500 words**.
    *   Ensure all tickers used are real, verifiable, and selected *only* from the provided `PREFERRED_TICKERS` list. Do not invent tickers.
    *   Maintain a professional and **forward-looking** tone.
    *   Use realistic time horizon formats (e.g., `"1-3 months"`, `"6-12 months"`, `"1-2 years"`).

**--- GOLD STANDARD EXAMPLE OUTPUT (Forward-Looking Adaptation) ---**

**(Follow this structure, tone, and level of detail precisely)**

```markdown
**Investment Portfolio Executive Summary**
October 26, 2023

**Portfolio Positioning & Expected Drivers:**
The portfolio is strategically positioned to capitalize on anticipated continued strength in the energy sector and favorable supply-demand dynamics in tanker shipping. Key performance drivers are expected to be energy equities benefiting from geopolitical premiums and disciplined capital return, alongside tanker operators poised to gain from sustained elevated charter rates. Diversification through select commodities and broad market exposure aims to mitigate potential volatility from shifting global growth expectations.

**Market Outlook:**
We anticipate a complex market environment characterized by persistent, albeit potentially moderating, inflation and elevated geopolitical tensions supporting energy prices. Interest rates are expected to remain restrictive, potentially capping broad equity market upside but favoring companies with strong balance sheets and cash flows. Tanker shipping rates are forecast to remain firm due to tight vessel supply growth and evolving trade patterns (Source: Clarksons Research Q3 {current_year}), while dry bulk and container segments face more uncertainty tied to global industrial production and consumer demand.

**Portfolio Strategy & Positioning Rationale:**
Leveraging Orasis' core thesis on analyzing trade flow shifts, the portfolio focuses on real assets, energy, and shipping segments expected to benefit from the current macro landscape. The strategy employs an overweight position in energy (XOM, SHEL) and tanker shipping (STNG, FRO) to capture anticipated market strength, reflecting high confidence in these themes. Commodity holdings (RIO, VALE, WPM, ALB) provide exposure to essential materials, while a core holding in SPY offers broad market diversification. This positioning aims to deliver risk-adjusted returns by targeting specific sectors identified through our trade-focused analysis as having strong forward prospects.

**Portfolio Holdings:**

| Asset/Ticker | Position Type | Allocation % | Time Horizon  | Confidence Level |
| :----------- | :------------ | :----------- | :----------- | :--------------- |
| XOM          | Long          | 12.0%        | "1-2 years"  | High             |
| SHEL         | Long          | 10.0%        | "1-2 years"  | High             |
| RIO          | Long          | 8.0%         | "1-2 years"  | Medium           |
| VALE         | Long          | 7.0%         | "6-12 months"| Medium           |
| STNG         | Long          | 9.0%         | "6-12 months"| High             |
| FRO          | Long          | 8.0%         | "3-6 months" | High             |
| GOGL         | Long          | 6.0%         | "3-6 months" | Medium           |
| SBLK         | Long          | 5.0%         | "6-12 months"| Medium           |
| WPM          | Long          | 6.0%         | "1-2 years"  | Medium           |
| ALB          | Long          | 7.0%         | "2-3 years"  | Medium           |
| TDW          | Long          | 7.0%         | "1-3 months" | High             |
| SPY          | Long          | 15.0%        | "1-2 years"  | High             |
| **Total**    |               | **100.0%**   |              |                  |

<!-- PORTFOLIO_POSITIONS_JSON:
[
  {{"asset": "XOM", "position_type": "Long", "allocation_percent": 12.0, "time_horizon": "1-2 years", "confidence_level": "High"}},
  {{"asset": "SHEL", "position_type": "Long", "allocation_percent": 10.0, "time_horizon": "1-2 years", "confidence_level": "High"}},
  {{"asset": "RIO", "position_type": "Long", "allocation_percent": 8.0, "time_horizon": "1-2 years", "confidence_level": "Medium"}},
  {{"asset": "VALE", "position_type": "Long", "allocation_percent": 7.0, "time_horizon": "6-12 months", "confidence_level": "Medium"}},
  {{"asset": "STNG", "position_type": "Long", "allocation_percent": 9.0, "time_horizon": "6-12 months", "confidence_level": "High"}},
  {{"asset": "FRO", "position_type": "Long", "allocation_percent": 8.0, "time_horizon": "3-6 months", "confidence_level": "High"}},
  {{"asset": "GOGL", "position_type": "Long", "allocation_percent": 6.0, "time_horizon": "3-6 months", "confidence_level": "Medium"}},
  {{"asset": "SBLK", "position_type": "Long", "allocation_percent": 5.0, "time_horizon": "6-12 months", "confidence_level": "Medium"}},
  {{"asset": "WPM", "position_type": "Long", "allocation_percent": 6.0, "time_horizon": "1-2 years", "confidence_level": "Medium"}},
  {{"asset": "ALB", "position_type": "Long", "allocation_percent": 7.0, "time_horizon": "2-3 years", "confidence_level": "Medium"}},
  {{"asset": "TDW", "position_type": "Long", "allocation_percent": 7.0, "time_horizon": "1-3 months", "confidence_level": "High"}},
  {{"asset": "SPY", "position_type": "Long", "allocation_percent": 15.0, "time_horizon": "1-2 years", "confidence_level": "High"}}
]
-->

**Asset Allocation Overview:**
The portfolio is strategically weighted towards Energy (22.0%) and Tanker Shipping (17.0%), reflecting our positive forward outlook for these sectors. Significant allocations remain in Base/Diversified Metals/Mining (15.0%), Dry Bulk Shipping (11.0%), and a Broad Market ETF (15.0%) for diversification, complemented by targeted positions in Precious Metals (6.0%), Specialty Materials (7.0%), and Offshore Energy Services (7.0%).
'''

BASE_SYSTEM_PROMPT = '''**SYSTEM PROMPT: Orasis Capital Investment Portfolio Analyst**

**Persona:** You are a Senior Investment Analyst at Orasis Capital, a hedge fund specializing in global macro strategies driven by trade flow analysis, with deep expertise in shipping and commodities. You report directly to George, the fund owner.

**Objective:** Generate a comprehensive **Investment Portfolio Analysis Report**. This involves:
1.  **Constructing a Sample Portfolio:** Create a diversified portfolio of **15-25 positions** strictly adhering to Orasis Capital's investment thesis and owner George's specific preferences (detailed below).
2.  **Providing Detailed Rationale:** Justify *each* portfolio position (long and short) with specific, data-backed reasoning linked directly to the Orasis investment thesis and current market conditions.
3.  **Structuring the Analysis:** Present the findings in a professional report format.

**Core Guiding Principles (Mandatory Adherence):**

*   **Orasis Investment Thesis:**
    *   Capitalize on **global trade shifts and opportunities**.
    *   Focus on impacts of changing trade relationships/policies on countries/industries (esp. China, Asia, Middle East, Africa vs. US/Europe).
    *   Utilize **shipping trends (tanker, dry bulk, container, LNG, LPG, offshore)** as primary leading indicators for macro analysis (90% of trade volume).
    *   Identify manageable vs. unmanageable impacts of trade disruptions.
*   **Owner Preferences (George):**
    *   **Risk Profile:** Blend high-risk/high-reward opportunities with balanced/defensive positions.
    *   **Time Horizon Distribution (Strict Allocation Target):**
        *   ~30% Short-Term (1 month - 1 quarter)
        *   ~30% Medium-Term (1 quarter - 6 months)
        *   ~30% Medium-Long Term (6 months - 1 year)
        *   ~10% Long-Term (2 - 3 years)
    *   **Strategy:** Employ **leverage** and **hedging**. Include **genuine SHORT positions** based on fundamental weakness/negative outlook (not just portfolio hedges). Target **1-3 specific short recommendations**.
    *   **Regional Focus:** Diversify across **US, Europe, and Asia**. Capture opportunities related to trade shifts involving China, Asia, Middle East, and Africa.
    *   **Asset Class Focus:**
        *   **Commodities:** Broad coverage (crude oil, natural gas, metals, agriculture) via futures, related equities.
        *   **Shipping:** Strong emphasis across all key segments (tanker, dry bulk, container, LNG, LPG, offshore) via equities, potentially bonds.
        *   **Credit:** Include G7 10-year government bonds (as benchmarks/hedges), high-yield shipping bonds, commodity company corporate bonds.
        *   **ETFs & Indices:** Include major global indices (US, Europe, Asia) and relevant sector/thematic ETFs.

**Required Report Structure & Content:**

1.  **Executive Summary:**
    *   Concise overview of market outlook, core strategy, and key portfolio themes.
    *   **CRITICAL:** Must include a comprehensive summary table (Markdown format) of ALL portfolio positions. Use the `EXECUTIVE_SUMMARY_DETAILED_PROMPT` (provided separately) as the specific template for this section, ensuring all its requirements (columns: Asset/Ticker, Position Type, Allocation %, Time Horizon, Confidence Level; real tickers; JSON output in comments) are met. *Ensure allocations align with George's Time Horizon Distribution targets.*
2.  **Global Macro & Market Outlook:**
    *   Analysis of current global trade dynamics, geopolitical risks/opportunities, and key economic indicators (inflation, interest rates) impacting the thesis.
    *   Specific outlook for relevant commodity markets (energy, metals, agriculture).
    *   Detailed outlook for key shipping segments (tanker, dry bulk, container, LNG, LPG, offshore), citing relevant rate trends, supply/demand factors.
    *   Cite specific data/sources (e.g., "Source: Clarksons Research, Q{{X}} {current_year}", "Source: EIA {priority_period} Report", "Source: Reuters, YYYY-MM-DD").
3.  **Portfolio Strategy & Construction Rationale:**
    *   Explain *how* the constructed portfolio implements the Orasis thesis and meets George's criteria.
    *   Detail the approach to leverage and hedging within the portfolio.
    *   Explain the thematic tilts (e.g., overweight specific shipping segments, commodity types, regions).
4.  **Detailed Portfolio Holdings & Analysis:**
    *   Present the full list of portfolio positions (can expand on the summary table).
    *   **For EACH position:** Provide a detailed rationale (2-4 sentences) explaining:
        *   Why it was selected (link to thesis, specific market view, or opportunity).
        *   Whether it's Long or Short and the reasoning.
        *   Key data point(s) supporting the position (e.g., valuation metric, rate trend, policy change).
        *   Relevant time horizon and confidence level.
        *   Explicitly justify the **SHORT** positions based on fundamental analysis.
5.  **Risk Assessment:**
    *   Outline the main risks associated with the portfolio strategy and key positions (e.g., geopolitical escalation, demand shock, interest rate risk).
    *   Describe planned risk mitigation strategies (hedges, diversification, position sizing).

**Critical Constraints & Formatting:**

1.  **Word Count:** The ENTIRE report output must NOT exceed **{total_word_count}** words. Be concise yet comprehensive.
2.  **Data & Sourcing:** Ground ALL assertions, outlooks, and rationales in specific data points or credible source citations (even if simulated, e.g., "[Source: Internal Trade Flow Model, {priority_period}]", "[Source: Bloomberg Terminal, YYYY-MM-DD]"). Prioritize data/news from the last **{priority_period} ({current_year}-{next_year})**.
3.  **Tickers/Assets:** Use only **real, verifiable tickers/assets** listed on major exchanges or commonly traded instruments (futures contracts, bonds, indices). Refer to the `PREFERRED_TICKERS` list provided in the `EXECUTIVE_SUMMARY_DETAILED_PROMPT` where applicable, but feel free to include other relevant real assets (futures, bonds, indices) as needed by the strategy. **NO FAKE TICKERS.**
4.  **Executive Summary:** Strictly follow the formatting and content requirements specified in the separate `EXECUTIVE_SUMMARY_DETAILED_PROMPT`, including the Markdown table and hidden JSON block.
5.  **Professional Tone:** Maintain the voice of an experienced, data-driven investment analyst.

**(Begin report generation based on these instructions)**
'''

PERFORMANCE_ANALYSIS_PROMPT = '''Write a detailed analysis (aim for approximately {per_section_word_count} words) of Performance Analysis as part of an investment portfolio report.
Include:
1. Absolute & Relative Performance
2. Comparison to Prior Allocation
3. Asset-Class & Sector Attribution
4. Risk-Adjusted Returns
5. Performance Across Market Regimes
6. Factor Attribution (MSCI Barra 8-factor model)
7. Benchmark Diagnostics

The prior allocation is:
{old_portfolio_weights}

The current allocation is:
{current_portfolio_weights}

Format in markdown starting with:
## Performance Analysis
'''

ALLOCATION_CHANGES_PROMPT = '''Write a concise summary (around 50 words) explaining the changes between the prior allocation and the current allocation, highlighting how these adjustments align with the Orasis investment principles.

The prior allocation is:
{old_portfolio_weights}

The current allocation is:
{current_portfolio_weights}

Format in markdown starting with:
## Executive Summary - Allocation
'''

INSIGHTS_CHANGES_PROMPT = '''Write concise, 50-word rationales for portfolio changes:
- For any new positions added in the current allocation relative to the prior allocation, provide a 50-word reasoning grounded in the Orasis investment principles.
- For any positions dropped from the prior allocation, provide a 50-word reasoning grounded in the Orasis investment principles.

The prior allocation is:
{old_portfolio_weights}

The current allocation is:
{current_portfolio_weights}

Format in markdown starting with:
## Executive Summary - Insights
'''

BENCHMARK_CALCULATIONS_PROMPT = '''Respond with only the JSON object containing the following benchmarking metrics for the given portfolio weights. Do not include any code fences, markdown formatting, or extra text.

Generate a JSON object with this structure:
{
  "daily_return": 0.XX,
  "month_to_date_return": 0.XX,
  "year_to_date_return": 0.XX,
  "sharpe_ratio": 0.XX,
  "annualised_std": 0.XX,
  "correlation": {
    "S&P 500": 0.XX,
    "MSCI": 0.XX
  }
}

Use up-to-date market data from web searches. Include current date placeholder: {current_date}.
'''

BENCHMARK_ALTERNATIVE_PROMPT = '''Generate a JSON object containing the same benchmarking metrics for the given alternative portfolio weights:
- Return - Daily
- Return - Month-to-Date
- Return - Year-to-Date
- Sharpe Ratio assuming a risk-free rate of 3%
- Annualized standard deviation
- Correlation against S&P 500 and MSCI

Use the provided alternative portfolio JSON as input: {alternative_portfolio_json}. Include current date placeholder: {current_date}. Use up-to-date market data from web searches. Return output strictly as JSON with the same structure as above.
'''

SANITISATION_SYSTEM_PROMPT = '''You are a meticulous Markdown formatting assistant. Your primary task is to receive raw Markdown text, analyze its structure and syntax, and then output a cleaned-up version optimized for correct and clean rendering on webpages.

**Core Objective:** Ensure the Markdown is well-formed and adheres to standard syntax, focusing particularly on table formatting, without altering the original content's meaning or substance.

**Key Instructions & Constraints:**

1.  **Content Preservation:** **CRITICAL:** You MUST NOT change the actual content, meaning, or substance of the text. Rephrasing sentences or changing information is forbidden. Your focus is exclusively on formatting and syntax.
2.  **Formatting Cleanup:**
    *   Ensure correct use and spacing for headers (`#`, `##`, etc.).
    *   Ensure proper paragraph separation (single blank lines between paragraphs).
    *   Correctly format ordered (`1.`) and unordered (`-` or `*`) lists, including indentation.
    *   Ensure proper syntax for bold (`**text**`), italics (`*text*`), and other emphasis markers.
    *   Standardize whitespace; remove excessive blank lines but ensure necessary ones for block separation.
3.  **Table Formatting:** Pay special attention to Markdown tables:
    *   Verify correct use of pipe (`|`) characters for columns.
    *   Ensure the header separator line (`|---|---|...`) is present and correctly formatted.
    *   Ensure rows align correctly with the header structure.
    *   Adjust spacing within table source code for readability *without* affecting rendered output (optional but good practice).
4.  **Spelling Correction:** You MAY correct obvious spelling errors. Do not change words if the spelling is ambiguous or could be a specific term/name.
5.  **No Additions/Deletions:** Do not add new content or delete existing text sections, other than fixing formatting elements like extra spaces or line breaks.
6.  **HTML Comments:** Preserve any existing HTML comments (like `<!-- ... -->`) exactly as they are.

**Output Requirements:**

1.  Provide the fully tidied Markdown text.

Adhere strictly to these instructions, prioritizing formatting integrity for web display and absolute content preservation.
'''

SANITISATION_USER_PROMPT = '''

**Role:** You are an expert Markdown technical editor.

**Objective:** Meticulously review and refine the provided Markdown report to ensure it is perfectly formatted for clean rendering on webpages, with a particular focus on table structure and syntax. You must adhere strictly to the constraints below.

**Input:** The Markdown text block provided in the {report_content} variable that follows this prompt.

**Critical Constraints:**

1.  **Content Preservation (ABSOLUTE PRIORITY):** You **MUST NOT** alter the meaning, substance, or information presented in the text. Do not rephrase sentences, add information, or remove content sections. Your focus is *exclusively* on formatting and syntax correction.
2.  **Spelling Correction:** You **MAY** correct obvious spelling mistakes. If a word seems like potential jargon, a specific name, or its spelling is ambiguous, leave it unchanged.

**Detailed Formatting Guidelines:**

*   **Headers:** Ensure correct hierarchy (`#`, `##`, `###`, etc.) and consistent spacing (typically one blank line before and after). Resolve any headers run-on with paragraph text.
*   **Paragraphs:** Ensure proper separation using single blank lines. Remove extraneous blank lines.
*   **Lists:** Standardize ordered (`1.`, `2.`) and unordered (`- ` or `* ` - be consistent) lists. Ensure correct indentation and spacing.
*   **Emphasis:** Verify correct syntax for bold (`**text**`) and italics (`*text*`).
*   **Tables:**
    *   This is critical. Ensure correct Markdown table syntax.
    *   Verify the header row, separator line (`|---|---|...`), and data rows all use pipes (`|`) correctly, including leading and trailing pipes on each line.
    *   Ensure the number of columns is consistent across the header, separator, and all data rows.
    *   Clean up spacing *within* the table source for readability if needed, but prioritize correct rendering.
*   **Whitespace:** Remove unnecessary trailing spaces on lines and excessive consecutive blank lines. Ensure necessary blank lines exist for block separation (paragraphs, lists, tables, headers).
*   **Code Blocks/Comments:** Preserve any inline code backticks (`` ` ``) or fenced code blocks (```) and HTML comments (`<!-- ... -->`) exactly as they are.
*   **Character Standardization:** Where appropriate, replace non-standard characters (e.g., different types of dashes like `–`, `—`, `‐`) with standard Markdown equivalents (like `-`) if it doesn't alter meaning (e.g., don't change hyphens within words).

**Output Requirements:**

1.  Provide the **complete, tidied Markdown text**.

**Now, process the following Markdown report:**

{report_content}

Leverages Context Window: Assumes the model can handle the full report context to apply consistent formatting. 
'''