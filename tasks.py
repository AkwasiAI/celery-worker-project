# tasks.py
import time
import logging
import asyncio
from celery_config import celery_app # Import the configured Celery app

# Import the report improvement logic
from portfolio_generator.report_improver import _run_improvement_logic
REPORT_IMPROVER_AVAILABLE = True

logger = logging.getLogger(__name__)

@celery_app.task(bind=True) # bind=True allows access to self (task instance)
def say_hello(self, name: str):
    """
    Simple task that takes a name, prepends 'Hello ', and returns the result.
    """
    task_id = self.request.id
    logger.info(f"Task {task_id}: Received name '{name}'")
    print(f"Task {task_id}: Received name '{name}'") # Also print for visibility in docker logs

    # Simulate some work (optional)
    # time.sleep(5)

    try:
        result = f"Hello {name}"
        logger.info(f"Task {task_id}: Processing complete. Result: '{result}'")
        print(f"Task {task_id}: Processing complete. Result: '{result}'")
        return result
    except Exception as e:
        logger.error(f"Task {task_id}: Failed to process name '{name}'. Error: {e}", exc_info=True)
        print(f"Task {task_id}: Failed to process name '{name}'. Error: {e}")
        # Reraise the exception so Celery marks the task as FAILED
        raise


@celery_app.task(name="tasks.improve_report_with_feedback", bind=True)
def improve_report_with_feedback(self, document_id: str, annotations: list = None, weight_changes: list = None, position_count: int = None):
    """
    Celery task to improve a report using OpenAI based on annotations AND weight changes, using the provided original report content.
    Incorporates web search and saves the improved report back to Firestore.
    
    Args:
        document_id: The Firestore document ID of the report to improve
        annotations: List of annotation objects containing text snippets, comments, and sentiment
        weight_changes: List of weight change objects with asset name, ticker, old weight, and new weight
        position_count: The required number of portfolio positions to enforce in the improved report
        original_report_content: The original report text to be improved (required)
    
    Returns:
        Dict containing success message, document ID, and runtime information
    """
    task_id = self.request.id
    logger.info(f"Task {task_id}: Starting improve_report_with_feedback for document: {document_id} (position_count={position_count})")
    print(f"Task {task_id}: Starting improve_report_with_feedback for document: {document_id} (position_count={position_count})")
    
    # Ensure we have list objects, even if None was provided
    annotations = annotations or []
    weight_changes = weight_changes or []
    
    if not REPORT_IMPROVER_AVAILABLE:
        error_msg = "Report improver module is not available. Cannot process the task."
        logger.error(f"Task {task_id}: {error_msg}")
        print(f"Task {task_id}: {error_msg}")
        raise ImportError(error_msg)
    

    try:
        # Run the async improvement logic using asyncio
        result = asyncio.run(_run_improvement_logic(document_id, annotations, weight_changes, position_count))
        
        logger.info(f"Task {task_id}: Successfully improved report {document_id} in {result.get('runtime_seconds', 0)} seconds")
        print(f"Task {task_id}: Successfully improved report {document_id} in {result.get('runtime_seconds', 0)} seconds")
        
        return result
    except Exception as e:
        logger.error(f"Task {task_id}: Failed to improve report {document_id}. Error: {e}", exc_info=True)
        print(f"Task {task_id}: Failed to improve report {document_id}. Error: {e}")
        # Reraise the exception so Celery marks the task as FAILED
        raise