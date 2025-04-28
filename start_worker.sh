#!/bin/bash

if [ -f /app/.env ]; then
  export $(grep -v '^#' /app/.env | xargs)
fi

echo "🔧 Cleaning up stale Celery files..."
rm -f /tmp/celery_worker.pid /tmp/celery_beat.pid /app/portfolio_generator/celerybeat-schedule

cd /app

# Run all in background using correct module path
celery -A portfolio_generator.comprehensive_portfolio_generator worker --loglevel=info &
celery -A portfolio_generator.comprehensive_portfolio_generator beat --loglevel=info &
celery -A portfolio_generator.comprehensive_portfolio_generator flower --port=5555 --address=0.0.0.0 &

# Keep container alive
wait
