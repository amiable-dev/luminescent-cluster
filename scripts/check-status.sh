#!/bin/bash
#
# Check Pixeltable Knowledge Base Status
#
# This script queries the local Pixeltable database to display:
# - Total number of ingested items
# - Breakdown by type (code, decision, incident, etc.)
# - Per-service item counts
#
# Usage:
#   ./check-status.sh
#
#   # Monitor in real-time during ingestion
#   watch -n 30 ./check-status.sh
#
# Requirements:
#   - Pixeltable installed (pip install pixeltable)
#   - Knowledge base initialized (python pixeltable_setup.py)
#
# Data Location:
#   All data is stored locally at ~/.pixeltable/
#   This script reads from that local database.
#

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

python3 -c "
import pixeltable as pxt
import sys

try:
    # Connect to the local Pixeltable database
    # By default, Pixeltable stores data at ~/.pixeltable/
    kb = pxt.get_table('org_knowledge')
    
    total = kb.count()
    print(f'📊 Knowledge Base Status')
    print(f'=' * 40)
    print(f'Total items: {total:,}')
    print()
    
    # Count by type (code, decision, incident, etc.)
    print('By type:')
    for row in kb.select(kb.type).group_by(kb.type).order_by(kb.type):
        type_name = row['type']
        count = kb.where(kb.type == type_name).count()
        print(f'  {type_name}: {count:,}')
    
    print()
    
    # List all unique services and their item counts
    # Services are tagged via metadata during ingestion
    services = kb.select(kb.metadata['service']).collect()
    unique_services = sorted(set(s['service'] for s in services if s.get('service')))
    
    print(f'Services ({len(unique_services)}):')
    for service in unique_services:
        count = kb.where(kb.metadata['service'] == service).count()
        print(f'  {service}: {count:,} items')
    
    print()
    print('✓ Knowledge base is operational')
    print(f'Data location: ~/.pixeltable/')
    
except Exception as e:
    print(f'❌ Error: {e}')
    print()
    print('Knowledge base may not be initialized yet.')
    print('Run: python3 pixeltable_setup.py')
    sys.exit(1)
"
