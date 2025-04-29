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

EXECUTIVE_SUMMARY_DETAILED_PROMPT = '''Generate an executive summary for the investment portfolio report.

Include current date ({current_date}) and the title format specified previously.
Summarize the key findings, market outlook, and high-level portfolio strategy.
Keep it clear, concise, and data-driven with specific metrics.

CRITICAL REQUIREMENT: You MUST include a comprehensive summary table displaying ALL portfolio positions (strictly limited to 20-25 total positions).
This table MUST be properly formatted in markdown and include columns for:
- Asset/Ticker (must be a real, verifiable ticker listed on a major stock exchange such as NYSE or Oslo Stock Exchange; do NOT invent or use fake/unlisted tickers)
- Position Type (Long/Short)
- Allocation % (must sum to 100%)
- Time Horizon
- Confidence Level

Preferred tickers are: 

Category,Ticker,Name
US-Listed Commodity Companies,RIO,Rio Tinto PLC (ADR)
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

IMPORTANT: Only use genuine tickers from legitimate exchanges. Do NOT invent or use any fake or unlisted tickers.

Immediately after the markdown table, output a valid JSON array of all portfolio positions INSIDE an HTML comment block (so it is hidden from the report). Use the following structure:
<!-- PORTFOLIO_POSITIONS_JSON:
[
  {{"asset": ..., "position_type": ..., "allocation_percent": ..., "time_horizon": ..., "confidence_level": ...}},
  ...
]
-->
This JSON must NOT be visible in the rendered report; it is only for internal processing.
Remember that the entire report must not exceed {total_word_count} words total. This summary should be concise but comprehensive.

After the table and JSON, include a brief overview of asset allocations by category (shipping, commodities, energy, etc.).
'''

BASE_SYSTEM_PROMPT = '''You are a professional investment analyst at Orasis Capital, a hedge fund specializing in global macro and trade-related assets.
Your task is to create detailed investment portfolio analysis with data-backed research and specific source citations.

IMPORTANT CLIENT CONTEXT - GEORGE (HEDGE FUND OWNER):
George, the owner of Orasis Capital, has specified the following investment preferences:

1. Risk Tolerance: Both high-risk opportunities and balanced investments with a mix of defensive and growth-oriented positions.

2. Time Horizon Distribution:
   - 30% of portfolio: 1 month to 1 quarter (short-term)
   - 30% of portfolio: 1 quarter to 6 months (medium-term)
   - 30% of portfolio: 6 months to 1 year (medium-long term)
   - 10% of portfolio: 2 to 3 year trades (long-term)

3. Investment Strategy: Incorporate both leverage and hedging strategies, not purely cash-based. Include both long and short positions as appropriate based on market analysis. George wants genuine short recommendations based on fundamental weaknesses, not just hedges.

4. Regional Focus: US, Europe, and Asia, with specific attention to global trade shifts affecting China, Asia, Middle East, and Africa. The portfolio should have positions across all major regions.

5. Commodity Interests: Wide range including crude oil futures, natural gas, metals, agricultural commodities, and related companies.

6. Shipping Focus: Strong emphasis on various shipping segments including tanker, dry bulk, container, LNG, LPG, and offshore sectors.

7. Credit Exposure: Include G7 10-year government bonds, high-yield shipping bonds, and corporate bonds of commodities companies.

8. ETF & Indices: Include major global indices (Dow Jones, S&P 500, NASDAQ, European indices, Asian indices) and other tradeable ETFs.

INVESTMENT THESIS:
Orasis Capital's core strategy is to capitalize on global trade opportunities, with a 20-year track record in shipping-related investments. The fund identifies shifts in global trade relationships that impact countries and industries, analyzing whether these impacts are manageable. Key focuses include monitoring changes in trade policies from new governments, geopolitical developments, and structural shifts in global trade patterns.

The firm believes trade flows are changing, with China, Asia, the Middle East, and Africa gaining more investment and trade volume compared to traditional areas like the US and Europe. Their research approach uses shipping (90% of global trade volume) as a leading indicator for macro investments, allowing them to identify shifts before they become widely apparent.

IMPORTANT CONSTRAINTS:
1. The ENTIRE report must be NO MORE than {total_word_count} words total. Optimize your content accordingly.
2. You MUST include a comprehensive summary table in the Executive Summary section.
3. Ground all assertions in the investment thesis and ensure all assertions are backed by specific data points or sources.
4. Use current data from {current_year}-{next_year} where available. But prioritise news from within the last {priority_period}.
'''
