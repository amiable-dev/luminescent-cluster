#!/bin/bash

# Ingestion Helper Script
# Simplifies re-ingesting codebase into Pixeltable knowledge base

set -e

SERVICE_NAME="${1:-context-aware-system}"

echo "Ingesting codebase into Pixeltable knowledge base..."
echo "Service name: $SERVICE_NAME"

docker-compose exec -T pixeltable-memory python -c "
from pixeltable_setup import setup_knowledge_base, ingest_codebase
import sys

kb = setup_knowledge_base()
print('✓ Knowledge base initialized')

files_count = ingest_codebase(kb, '/repos', '$SERVICE_NAME')
print(f'✓ Ingested {files_count} files from $SERVICE_NAME')
"

echo "✓ Ingestion complete"
