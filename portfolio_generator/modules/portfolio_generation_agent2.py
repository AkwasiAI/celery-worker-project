# portfolio_generation_agent_gemini.py

import os
import json
import datetime
import logging
import time
from typing import List, Dict, Any, TypedDict, Literal, Optional

from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field, field_validator
import re

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") 

# Logger setup
log = logging.getLogger(__name__)

# --- Pydantic Models ---
class PortfolioPosition(BaseModel):
    asset: str = Field(..., description="Ticker symbol or identifier for the asset")
    position_type: Literal["LONG", "SHORT"] = Field(..., description="Position type (LONG or SHORT)")
    allocation_percent: float = Field(..., description="Percentage allocation in the portfolio (0-100)")
    time_horizon: str = Field(..., description="Investment time horizon (e.g., '3-6 months', '1-2 years')")
    confidence_level: Literal["High", "Medium", "Low"] = Field(..., description="Confidence level in the position")
    
    @field_validator('allocation_percent')
    def check_allocation(cls, v):
        if not 0 <= v <= 100:
            raise ValueError(f'allocation_percent must be between 0 and 100, got {v}')
        return round(v, 2)
    
    @field_validator('asset')
    def check_asset(cls, v):
        if not v or not v.strip():
            raise ValueError('asset cannot be empty')
        return v.strip().upper()

    @field_validator('position_type')
    def normalize_position_type(cls, v):
        return v.upper()

    @field_validator('confidence_level')
    def normalize_confidence_level(cls, v):
        val_lower = v.lower()
        if val_lower in ["very high", "highest", "high"]: return "High"
        if val_lower in ["very low", "lowest", "low"]: return "Low"
        if val_lower == "medium": return "Medium"
        log.warning(f"Unknown confidence level '{v}', defaulting to Medium.")
        return "Medium"

class ProposerDraft(BaseModel):
    summary_markdown: str
    portfolio_positions_json_str: str

# --- Global LLM Clients (Initialized by main entry point function) ---
LLM_CLIENT: Optional[ChatGoogleGenerativeAI] = None
CIO_LLM_CLIENT: Optional[ChatGoogleGenerativeAI] = None

if not GEMINI_API_KEY: # This check runs at import time
    log.error("GEMINI_API_KEY environment variable is missing. Gemini models will not be available.")
    # Not raising error here to allow module import, but functions will fail if key isn't passed.

# --- Prompt Templates ---
PROPOSER_SYSTEM_PROMPT = "You are the Portfolio Proposer. Your goal is to generate an initial comprehensive executive summary and portfolio based on all available information."
PROPOSER_USER_PROMPT_TEMPLATE = """
Based on the provided Orasis Base Principles, Executive Summary Detailed Instructions, LLM News Corpus, George Elliott's Latest Feedback, and the Previous Portfolio, please generate a new draft for the Executive Summary.

**Orasis Base Principles & Instructions (already includes current date and other dynamic info):**
{base_system_prompt_content}

**Executive Summary Detailed Instructions (Your Target Output Format, already includes current date and other dynamic info):**
{executive_summary_detailed_prompt_content}

**LLM News Corpus (Key insights derived from recent news):**
{llm_corpus_content}

**George Elliott's Latest Feedback (High Priority Context - consider this strongly):**
{georges_feedback_text}

**Previous Portfolio (for 60/40 consistency reference):**
{previous_portfolio_json_str}

**Specific Instructions for this Draft:**
1.  Construct a portfolio of 10-15 assets from the PREFERRED_TICKERS list found in the 'Executive Summary Detailed Instructions'.
2.  Your proposal MUST reflect understanding and consideration of insights from "George Elliott's Latest Feedback". If specific news, sectors, or sentiments are highlighted there, ensure your themes and asset choices align or address them.
3.  Aim to retain minimum of 60% of the assets/themes/instruments from the 'Previous Portfolio' if their rationale still holds given the 'LLM News Corpus' AND "George Elliott's Latest Feedback". Introduce approximately 40% new or significantly re-weighted positions unless otherwise stated by George.
4.  Ensure all allocation percentages sum to 100.0%.
5.  Adhere to George's specified time horizon distribution.
6.  Provide clear, forward-looking rationales in the narrative, integrating insights from all provided contexts.
7.  Output the ENTIRE executive summary including the narrative, the Markdown table, and the hidden JSON block for portfolio positions (<!-- PORTFOLIO_POSITIONS_JSON: [your JSON array here] -->), all as a single string. DO NOT ADD ANYTHING ELSE! YOUR OUTPUT WILL BE PROCESSED DIRECTLY.
{cio_revision_instructions}
"""

CRITIC_SYSTEM_PROMPT = "You are the Portfolio Critic. Your role is to meticulously review the Portfolio Proposer's draft and provide constructive criticism and suggestions for improvement."
CRITIC_USER_PROMPT_TEMPLATE = """
Please review the following "Portfolio Proposer's Draft" in the context of the "LLM News Corpus" and "George Elliott's Latest Feedback".

**Portfolio Proposer's Draft:**
{proposer_draft_markdown}

**LLM News Corpus (Key insights derived from recent news):**
{llm_corpus_content}

**George Elliott's Latest Feedback (Important context on recent focus):**
{georges_feedback_text}

**Your Task:**
1.  Critique the narrative: Is it logical? Is it consistent with the proposed portfolio, the market outlook from the LLM News Corpus, AND reflective of insights or focus areas from George's recent feedback?
2.  Critique the portfolio positions: Are the rationales sound? Are there obvious omissions or questionable inclusions given the news and George's feedback? Does it align with Orasis's investment thesis and George's preferences (risk, themes)?
3.  Identify any structural issues you notice (e.g., allocations not summing to 100%, incorrect ticker usage, formatting problems with the table or hidden JSON).
4.  Suggest specific improvements, alternative tickers (from the preferred list if applicable), or changes to rationale. Be concise and actionable.
"""

CIO_SYSTEM_PROMPT = "You are the Chief Investment Officer (CIO). You will review the portfolio proposal, the critic's feedback, and make a final decision or provide specific instructions for revision. You are also responsible for final validation against all requirements."
CIO_USER_PROMPT_TEMPLATE = """
As CIO, review the following:
1.  **Portfolio Proposer's Latest Draft:**
    {proposer_draft_markdown}

2.  **Portfolio Critic's Feedback:**
    {critic_feedback}

3.  **George Elliott's Latest Feedback (Crucial Context):**
    {georges_feedback_text}

4.  **LLM News Corpus (for context):**
    {llm_corpus_content}

5.  **Previous Portfolio (for 60/40 consistency check):**
    {previous_portfolio_json_str}

6.  **Orasis Base Principles & Executive Summary Requirements (for validation - these are already fully formatted with dates etc.):**
    {base_system_prompt_content}
    {executive_summary_detailed_prompt_content}

**Your Tasks:**
1.  **Assess:** Evaluate the Proposer's draft against the Critic's feedback, George's latest feedback, and all Orasis requirements (preferred tickers, 10-15 positions, allocation sum 100%, time horizon distribution, 60/40 consistency with previous portfolio, markdown and hidden JSON format).
2.  **Consider Exa Search (Optional):** If enabled and you believe external information is CRITICAL to resolve a conflict or validate a key assumption, you can request a search by stating "REQUEST_EXA_SEARCH: [your search query]". (For now, this feature is informational; the graph will not execute a search).
3.  **Decide and Instruct:**
    *   **If revisions are needed:** Provide clear, numbered, actionable instructions for the Portfolio Proposer to create the next draft. State "INSTRUCTIONS_FOR_REVISION:" followed by the instructions.
    *   **If the current draft is acceptable (or acceptable after minor self-correction you can state):** State "FINAL_PROPOSAL_APPROVED".
"""

# --- Helper Functions ---
def _clean_json_text(json_text: str) -> str:
    json_text = json_text.replace('\\\\', '__ESCAPED_BACKSLASH__')
    json_text = re.sub(r'\\(?!["\\/bfnrtu])', '', json_text)
    json_text = json_text.replace('__ESCAPED_BACKSLASH__', '\\\\')
    json_text = re.sub(r'[\x00-\x1F\x7F]', '', json_text)
    return json_text

def extract_structured_parts_from_llm_output(content: str) -> ProposerDraft: # Changed to always return ProposerDraft
    log.debug("Attempting to extract structured parts from LLM output...")
    comment_pattern = re.compile(r"<!-- PORTFOLIO_POSITIONS_JSON:\s*(.*?)\s*-->\s*", re.DOTALL)
    match = comment_pattern.search(content)

    if match:
        positions_json_str = match.group(1).strip()
        summary_markdown = content.strip() 
        try:
            cleaned_json_str = _clean_json_text(positions_json_str)
            json.loads(cleaned_json_str) 
            log.debug("Successfully extracted Markdown summary and portfolio JSON string.")
            return ProposerDraft(summary_markdown=summary_markdown, portfolio_positions_json_str=cleaned_json_str)
        except json.JSONDecodeError as e:
            log.error(f"Extracted JSON string from comment is invalid: {e}. JSON string from comment: '{positions_json_str}'")
            return ProposerDraft(summary_markdown=summary_markdown, portfolio_positions_json_str="[]")
    else:
        log.warning("PORTFOLIO_POSITIONS_JSON comment block not found in LLM output. Treating entire output as summary and using empty JSON for positions.")
        return ProposerDraft(summary_markdown=content.strip(), portfolio_positions_json_str="[]")

# --- Agent State Definition ---
class PortfolioGenerationState(TypedDict):
    llm_corpus_content: str
    previous_portfolio_data: Dict[str, Any]
    base_system_prompt_fully_formatted: str
    exec_summary_detailed_prompt_fully_formatted: str
    georges_feedback_text: Optional[str] # NEW
    proposer_draft_markdown: Optional[str]
    proposer_draft_positions_json_str: Optional[str]
    critic_feedback: Optional[str]
    cio_decision_text: Optional[str]
    final_executive_summary_md: Optional[str]
    portfolio_scratchpad: List[Dict[str, Any]]
    enable_cio_exa_search: bool
    iteration_count: int
    max_iterations: int
    current_date_iso_for_run: str

# --- Agent Nodes ---
def load_data_node(state: PortfolioGenerationState) -> Dict[str, Any]:
    log.info("LOAD_DATA_NODE: Initializing state for new run.")
    # iteration_count is set to 0 by the calling function.
    # georges_feedback_text is also passed in by the calling function.
    return {
        "portfolio_scratchpad": [{"actor": "SYSTEM", "message": "State initialized."}],
        "current_date_iso_for_run": datetime.date.today().isoformat()
    }

def portfolio_proposer_node(state: PortfolioGenerationState) -> Dict[str, Any]:
    global LLM_CLIENT
    if not LLM_CLIENT:
        log.critical("LLM_CLIENT (Gemini) not initialized in portfolio_proposer_node!")
        raise ValueError("LLM_CLIENT (Gemini) not initialized")

    current_run_iteration_number = state.get("iteration_count", 0) + 1
    log.info(f"PROPOSER_NODE: Starting Iteration {current_run_iteration_number} / {state['max_iterations']}")

    cio_instructions = ""
    if current_run_iteration_number > 1 and state.get("cio_decision_text") and \
       "INSTRUCTIONS_FOR_REVISION:" in state["cio_decision_text"]:
        cio_instructions = "\n**CIO Revision Instructions:**\n" + state["cio_decision_text"].split("INSTRUCTIONS_FOR_REVISION:", 1)[1].strip()
        log.info(f"Proposer received CIO instructions:\n{cio_instructions[:200]}")

    georges_feedback = state.get("georges_feedback_text", "No specific feedback from George provided for this cycle.")
    if not georges_feedback.strip(): # Ensure it's not just whitespace
        georges_feedback = "No specific feedback from George provided for this cycle."

    user_prompt = PROPOSER_USER_PROMPT_TEMPLATE.format(
        base_system_prompt_content=state["base_system_prompt_fully_formatted"],
        executive_summary_detailed_prompt_content=state["exec_summary_detailed_prompt_fully_formatted"],
        llm_corpus_content=state["llm_corpus_content"][:30000],
        georges_feedback_text=georges_feedback, # ADDED GF
        previous_portfolio_json_str=json.dumps(state["previous_portfolio_data"], indent=2),
        cio_revision_instructions=cio_instructions
    )
    messages = [
        SystemMessage(content=PROPOSER_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt)
    ]
    log.info("Proposer calling Gemini LLM...")
    try:
        response = LLM_CLIENT.invoke(messages)
        raw_llm_output = response.content
        log.debug(f"Proposer Gemini LLM Raw Output:\n{raw_llm_output}")
    except Exception as e:
        log.error(f"Proposer Gemini LLM call failed: {e}", exc_info=True)
        raw_llm_output = "Error: LLM call failed in Proposer."

    parsed_draft = extract_structured_parts_from_llm_output(raw_llm_output)
    
    current_scratchpad = state.get("portfolio_scratchpad", [])
    new_scratchpad_entry = {
        "actor": f"PROPOSER (Iter {current_run_iteration_number})",
        "output_markdown": parsed_draft.summary_markdown,
        "output_positions_json": parsed_draft.portfolio_positions_json_str
    }
    return {
        "proposer_draft_markdown": parsed_draft.summary_markdown,
        "proposer_draft_positions_json_str": parsed_draft.portfolio_positions_json_str,
        "portfolio_scratchpad": current_scratchpad + [new_scratchpad_entry],
        "iteration_count": current_run_iteration_number
    }

def portfolio_critic_node(state: PortfolioGenerationState) -> Dict[str, Any]:
    global LLM_CLIENT
    if not LLM_CLIENT:
        log.critical("LLM_CLIENT (Gemini) not initialized in portfolio_critic_node!")
        raise ValueError("LLM_CLIENT (Gemini) not initialized")
    log.info("CRITIC_NODE: Reviewing proposer's draft.")

    proposer_draft_md = state.get("proposer_draft_markdown")
    georges_feedback = state.get("georges_feedback_text", "No specific feedback from George provided for this cycle.")
    if not georges_feedback.strip():
        georges_feedback = "No specific feedback from George provided for this cycle."

    if not proposer_draft_md:
        log.warning("Critic node: No proposer draft markdown to review.")
        critique = "Error: No draft provided by proposer to critique."
    else:
        user_prompt = CRITIC_USER_PROMPT_TEMPLATE.format(
            proposer_draft_markdown=proposer_draft_md,
            llm_corpus_content=state["llm_corpus_content"][:30000],
            georges_feedback_text=georges_feedback # ADDED GF
        )
        messages = [SystemMessage(content=CRITIC_SYSTEM_PROMPT), HumanMessage(content=user_prompt)]
        log.info("Critic calling Gemini LLM...")
        try:
            response = LLM_CLIENT.invoke(messages)
            critique = response.content.strip()
            log.info(f"Critic feedback received:\n{critique[:300]}")
        except Exception as e:
            log.error(f"Critic Gemini LLM call failed: {e}", exc_info=True)
            critique = "Error: LLM call failed in Critic."
            
    current_scratchpad = state.get("portfolio_scratchpad", [])
    new_scratchpad_entry = {"actor": "CRITIC", "feedback": critique}
    return {"critic_feedback": critique, "portfolio_scratchpad": current_scratchpad + [new_scratchpad_entry]}

def cio_judge_node(state: PortfolioGenerationState) -> Dict[str, Any]:
    global CIO_LLM_CLIENT
    if not CIO_LLM_CLIENT:
        log.critical("CIO_LLM_CLIENT (Gemini) not initialized in cio_judge_node!")
        raise ValueError("CIO_LLM_CLIENT (Gemini) not initialized")
    log.info("CIO_JUDGE_NODE: Reviewing proposal and critique.")
    
    georges_feedback = state.get("georges_feedback_text", "No specific feedback from George provided for this cycle.")
    if not georges_feedback.strip():
        georges_feedback = "No specific feedback from George provided for this cycle."

    user_prompt = CIO_USER_PROMPT_TEMPLATE.format(
        proposer_draft_markdown=state.get("proposer_draft_markdown", "N/A"),
        critic_feedback=state.get("critic_feedback", "N/A"),
        georges_feedback_text=georges_feedback, # ADDED GF
        llm_corpus_content=state["llm_corpus_content"][:1000000], #Let's do one million characters for cutoff
        previous_portfolio_json_str=json.dumps(state["previous_portfolio_data"], indent=2),
        base_system_prompt_content=state["base_system_prompt_fully_formatted"],
        executive_summary_detailed_prompt_content=state["exec_summary_detailed_prompt_fully_formatted"]
    )
    messages = [SystemMessage(content=CIO_SYSTEM_PROMPT), HumanMessage(content=user_prompt)]
    log.info("CIO calling Gemini LLM...")
    try:
        response = CIO_LLM_CLIENT.invoke(messages)
        cio_decision = response.content.strip()
        log.info(f"CIO decision/instructions received:\n{cio_decision}")
    except Exception as e:
        log.error(f"CIO Gemini LLM call failed: {e}", exc_info=True)
        cio_decision = "Error: LLM call failed in CIO. Defaulting to finalize."
    
    current_scratchpad = state.get("portfolio_scratchpad", [])
    new_scratchpad_entry = {"actor": "CIO", "decision_text": cio_decision}
    return {"cio_decision_text": cio_decision, "portfolio_scratchpad": current_scratchpad + [new_scratchpad_entry]}

# --- Conditional Edges ---
def decide_next_step(state: PortfolioGenerationState) -> str:
    iterations_completed = state["iteration_count"] 
    max_allowed_iterations = state.get("max_iterations", 3)
    cio_decision = state.get("cio_decision_text", "")
    log.info(f"DECISION_NODE: Iterations completed = {iterations_completed}, Max allowed = {max_allowed_iterations}, CIO Decision (first 50 chars) = '{cio_decision[:50]}'")

    if "FINAL_PROPOSAL_APPROVED" in cio_decision:
        log.info("CIO approved the proposal. Routing to finalize_output.")
        return "finalize_output"
    elif "INSTRUCTIONS_FOR_REVISION:" in cio_decision:
        if iterations_completed < max_allowed_iterations:
            log.info(f"CIO provided revision instructions. Iterations completed: {iterations_completed}. Will start iteration {iterations_completed + 1}. Routing to proposer_node.")
            return "proposer_node" 
        else:
            log.warning(f"Max iterations ({max_allowed_iterations}) reached. Last CIO revision instructions were for iteration {iterations_completed}. Routing to finalize_output.")
            return "finalize_output" 
    else: 
        log.warning(f"CIO decision unclear or unhandled: '{cio_decision}'.")
        if iterations_completed < max_allowed_iterations:
             log.warning(f"Attempting another proposer cycle due to unclear CIO decision. Iterations completed: {iterations_completed}. Will start iteration {iterations_completed + 1}.")
             return "proposer_node"
        log.warning(f"Max iterations ({max_allowed_iterations}) reached with unclear CIO decision. Routing to finalize_output.")
        return "finalize_output"

def finalize_output_node(state: PortfolioGenerationState) -> Dict[str, Any]:
    log.info("FINALIZE_OUTPUT_NODE: Preparing final executive summary.")
    final_md = "Error: Could not determine final summary."
    cio_decision = state.get("cio_decision_text", "")
    last_proposer_draft = state.get("proposer_draft_markdown")

    if "FINAL_PROPOSAL_APPROVED" in cio_decision:
        parts = cio_decision.split("FINAL_PROPOSAL_APPROVED", 1)
        if len(parts) > 1 and parts[1].strip() and len(parts[1].strip()) > 100: 
            potential_final_summary = parts[1].strip()
            if "Portfolio Holdings" in potential_final_summary and "<!-- PORTFOLIO_POSITIONS_JSON:" in potential_final_summary:
                final_md = potential_final_summary
                log.info("Using CIO provided text (after 'FINAL_PROPOSAL_APPROVED') as final summary.")
            elif last_proposer_draft:
                final_md = last_proposer_draft
                log.info("Using last proposer draft as final summary after CIO approval (CIO text unsuitable/missing structure).")
            else:
                 log.error("CIO approved, but no suitable final summary text found from CIO or proposer.")
        elif last_proposer_draft:
            final_md = last_proposer_draft
            log.info("Using last proposer draft as final summary after CIO approval (CIO approval was standalone or text too short).")
        else:
            log.error("CIO approved, but no proposer draft available to use as final summary.")
    elif last_proposer_draft:
        log.warning("Finalizing output without explicit CIO approval (e.g., max iterations or unclear decision). Using last proposer draft.")
        final_md = last_proposer_draft
    else:
        log.error("No proposer draft available and no CIO approval for final output.")
        
    scratchpad_dir = "scratchpads"
    os.makedirs(scratchpad_dir, exist_ok=True)
    today_date = state.get("current_date_iso_for_run", datetime.date.today().isoformat())
    # Use a timestamp in the scratchpad filename to make it unique for each run
    timestamp = time.strftime('%Y%m%d-%H%M%S')
    scratchpad_filename = os.path.join(scratchpad_dir, f"portfolio_gen_scratchpad.json")
    try:
        with open(scratchpad_filename, "w", encoding="utf-8") as f:
            json.dump(state.get("portfolio_scratchpad", []), f, indent=2)
        log.info(f"Portfolio scratchpad saved to {scratchpad_filename}")
    except Exception as e:
        log.error(f"Failed to save portfolio scratchpad to {scratchpad_filename}: {e}", exc_info=True)
        
    return {"final_executive_summary_md": final_md}

# --- Graph Compilation ---
_portfolio_graph_gemini: Optional[StateGraph] = None
def get_portfolio_generation_graph_gemini() -> StateGraph:
    global _portfolio_graph_gemini
    if _portfolio_graph_gemini is None:
        log.debug("Building portfolio generation graph (Gemini) for the first time.")
        builder = StateGraph(PortfolioGenerationState)
        builder.add_node("load_data", load_data_node)
        builder.add_node("proposer_node", portfolio_proposer_node)
        builder.add_node("critic_node", portfolio_critic_node)
        builder.add_node("cio_judge_node", cio_judge_node)
        builder.add_node("finalize_output", finalize_output_node)

        builder.set_entry_point("load_data")
        builder.add_edge("load_data", "proposer_node")
        builder.add_edge("proposer_node", "critic_node")
        builder.add_edge("critic_node", "cio_judge_node")
        builder.add_conditional_edges(
            "cio_judge_node",
            decide_next_step,
            {"proposer_node": "proposer_node", "finalize_output": "finalize_output"}
        )
        builder.add_edge("finalize_output", END)
        _portfolio_graph_gemini = builder.compile()
        log.info("Portfolio generation graph (Gemini) built and compiled.")
    else:
        log.debug("Reusing existing compiled portfolio generation graph (Gemini).")
    return _portfolio_graph_gemini

# --- Main Entry Point Function ---
# Changed to be a synchronous function for easier integration if your main loop is sync.
# LangGraph stream() is synchronous if nodes are synchronous.
async def generate_portfolio_executive_summary_sync( # Renamed to indicate synchronous nature
    llm_corpus_content: str,
    previous_portfolio_data: Dict[str, Any],
    fully_formatted_base_prompt: str,
    fully_formatted_exec_detailed_prompt: str,
    georges_latest_feedback: Optional[str] = None, # NEW
    google_api_key: Optional[str] = None, # Made optional, will use env var if None
    log_file_path: str = "portfolio_generator.log",
    enable_cio_exa_search: bool = False,
    max_iterations: int = 2,
    proposer_critic_model_name: str = "gemini-2.5-flash-preview-05-20", # Default to Gemini
    cio_model_name: str = "gemini-2.5-pro-preview-05-06" # Default to Gemini
) -> Dict[str, Any]:
    """
    Generates the portfolio executive summary using an agentic workflow with Gemini models.
    """
    # --- Centralized Logging Setup ---
    # Remove any existing handlers from the root logger
    # This is important if this function is called multiple times in the same Python process
    # to avoid logs being duplicated or written to old file handlers.
    # root_logger = logging.getLogger()
    # for handler in root_logger.handlers[:]:
    #     root_logger.removeHandler(handler)
    
    # logging.basicConfig(
    #     level=logging.INFO,
    #     format="%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] %(message)s",
    #     filename=log_file_path,
    #     filemode="a" 
    # )
    # logging.getLogger("httpx").setLevel(logging.WARNING)
    # logging.getLogger("google.generativeai").setLevel(logging.INFO)
    # logging.getLogger("google.api_core").setLevel(logging.INFO)
    
    global LLM_CLIENT, CIO_LLM_CLIENT

    final_google_api_key = google_api_key or GEMINI_API_KEY # Use passed key or fallback to env var
    if not final_google_api_key:
        log.critical("Google API key not provided and GEMINI_API_KEY env var is not set.")
        raise ValueError("Google API key is required.")
        
    LLM_CLIENT = ChatGoogleGenerativeAI(
        model=proposer_critic_model_name, 
        temperature=0.1, 
        google_api_key=final_google_api_key,
        # safety_settings={ # Example safety settings if needed
        #     HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        #     HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        #     HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        #     HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        # }
    )
    CIO_LLM_CLIENT = ChatGoogleGenerativeAI(
        model=cio_model_name, 
        temperature=0.0, 
        google_api_key=final_google_api_key
    )
    
    log.info(f"--- Starting new portfolio generation cycle (Gemini) ---")
    log.info(f"Max iterations: {max_iterations}, Proposer/Critic Model: {proposer_critic_model_name}, CIO Model: {cio_model_name}")
    log.info(f"Log file: {os.path.abspath(log_file_path)}")

    initial_state = PortfolioGenerationState(
        llm_corpus_content=llm_corpus_content,
        previous_portfolio_data=previous_portfolio_data,
        base_system_prompt_fully_formatted=fully_formatted_base_prompt,
        exec_summary_detailed_prompt_fully_formatted=fully_formatted_exec_detailed_prompt,
        georges_feedback_text=georges_latest_feedback, # Pass GF
        proposer_draft_markdown=None,
        proposer_draft_positions_json_str=None,
        critic_feedback=None,
        cio_decision_text=None,
        final_executive_summary_md=None,
        portfolio_scratchpad=[],
        enable_cio_exa_search=enable_cio_exa_search,
        iteration_count=0,
        max_iterations=max_iterations,
        current_date_iso_for_run=datetime.date.today().isoformat()
    )

    app = get_portfolio_generation_graph_gemini()
    final_run_state = None
    
    graph_recursion_limit = (max_iterations * 3) + 10 # Increased buffer slightly
    log.info(f"Using graph recursion limit: {graph_recursion_limit}")

    try:
        for step_output in app.stream(initial_state, {"recursion_limit": graph_recursion_limit}):
            node_name_executed = list(step_output.keys())[0]
            log.debug(f"Graph step executed: {node_name_executed}") # Removed verbose state keys log
            final_run_state = step_output[node_name_executed]
    except Exception as e:
        log.error(f"Error during graph execution: {e}", exc_info=True)
        final_summary_md = final_run_state.get("final_executive_summary_md", "Error: Graph execution failed before final summary.") if final_run_state else "Error: Graph execution failed critically."
        scratchpad = final_run_state.get("portfolio_scratchpad", [{"actor": "SYSTEM", "error": f"Graph execution error: {e}"}]) if final_run_state else [{"actor": "SYSTEM", "error": f"Graph execution error: {e}"}]
        return {
            "summary": final_summary_md, # Match output keys
            "portfolio_scratchpad": scratchpad,
            "portfolio_positions": "[]"  # Match output keys
        }

    if not final_run_state or "final_executive_summary_md" not in final_run_state:
        log.error("Portfolio generation process completed, but failed to produce a final_executive_summary_md in the state.")
        return {
            "summary": "Error: Portfolio generation process completed without a final summary.",
            "portfolio_scratchpad": final_run_state.get("portfolio_scratchpad", []) if final_run_state else [],
            "portfolio_positions": "[]"
        }
    
    final_portfolio_json_str = "[]"
    final_summary_output_md = final_run_state.get("final_executive_summary_md", "Error: Final summary markdown missing.")
    if final_summary_output_md and not final_summary_output_md.startswith("Error:"):
        parsed_final_output = extract_structured_parts_from_llm_output(final_summary_output_md)
        if parsed_final_output: # extract_structured_parts_from_llm_output now always returns ProposerDraft
            final_portfolio_json_str = parsed_final_output.portfolio_positions_json_str

    log.info(f"--- Portfolio generation cycle (Gemini) finished ---")
    
    if isinstance(final_summary_output_md, str):
        final_summary_output_md = final_summary_output_md.strip()
        if final_summary_output_md.startswith("```markdown"):
            final_summary_output_md = final_summary_output_md[len("```markdown"):].strip()
        if final_summary_output_md.endswith("```"):
            final_summary_output_md = final_summary_output_md[:-len("```")].strip()

    return {
        "summary": final_summary_output_md,
        "portfolio_scratchpad": final_run_state.get("portfolio_scratchpad", []) if final_run_state else [],
        "portfolio_positions": final_portfolio_json_str
    }