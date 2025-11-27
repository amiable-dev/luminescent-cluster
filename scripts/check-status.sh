#!/bin/bash
#
# Check Pixeltable Knowledge Base Status
#
# This script queries the local Pixeltable database to display:
# - Total number of ingested items
# - Breakdown by type (code, decision, incident, etc.)
# - Per-service item counts
# - Recent entries (in verbose mode)
# - Ingestion timeline
#
# Usage:
#   ./check-status.sh           # Standard output
#   ./check-status.sh -v        # Verbose (shows last 10 entries)
#   ./check-status.sh -n 20     # Show last 20 entries
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

# Parse arguments
VERBOSE=false
LIMIT=10

while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -n|--limit)
            LIMIT="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [-v|--verbose] [-n|--limit N]"
            exit 1
            ;;
    esac
done

# Convert bash boolean to Python boolean
if [ "$VERBOSE" = true ]; then
    PY_VERBOSE="True"
else
    PY_VERBOSE="False"
fi

python3 -c "
import pixeltable as pxt
import sys
from datetime import datetime, timedelta

verbose = $PY_VERBOSE
limit = $LIMIT

try:
    # Connect to the local Pixeltable database
    kb = pxt.get_table('org_knowledge')
    
    total = kb.count()
    print(f'📊 Knowledge Base Status')
    print(f'=' * 60)
    print(f'Total items: {total:,}')
    print()
    
    # Ingestion timeline
    if total > 0:
        try:
            oldest = kb.order_by(kb.created_at, asc=True).limit(1).collect()[0]
            newest = kb.order_by(kb.created_at, asc=False).limit(1).collect()[0]
            
            oldest_time = oldest['created_at']
            newest_time = newest['created_at']
            
            duration = newest_time - oldest_time
            
            print(f'⏰ Ingestion Timeline:')
            print(f'  First entry: {oldest_time.strftime(\"%Y-%m-%d %H:%M:%S\")}')
            print(f'  Last entry:  {newest_time.strftime(\"%Y-%m-%d %H:%M:%S\")}')
            print(f'  Duration:    {duration}')
            
            # Calculate ingestion rate
            if duration.total_seconds() > 0:
                rate = total / (duration.total_seconds() / 60)  # items per minute
                print(f'  Rate:        {rate:.1f} items/minute')
            
            # Time since last entry
            time_since = datetime.now() - newest_time.replace(tzinfo=None)
            mins_since = int(time_since.total_seconds() / 60)
            print(f'  Last update: {mins_since} minute(s) ago')
            
            if mins_since > 5:
                print(f'  ⚠️  No new entries in {mins_since} minutes - ingestion may be complete or stalled')
            
            print()
        except Exception as e:
            print(f'Note: Could not retrieve timeline data: {e}')
            print()
    
    # Count by type
    print('📁 By Type:')
    type_groups = kb.select(kb.type).group_by(kb.type).order_by(kb.type).collect()
    
    unique_types = set()
    for row in type_groups:
        if row.get('type'):
            unique_types.add(row['type'])
    
    for type_name in sorted(unique_types):
        count = kb.where(kb.type == type_name).count()
        print(f'  {type_name:15s}: {count:,}')
    
    print()
    
    # List all unique services and their item counts
    print('🏢 By Service:')
    services = kb.select(kb.metadata['service']).collect()
    unique_services = sorted(set(s['service'] for s in services if s.get('service')))
    
    for service in unique_services:
        count = kb.where(kb.metadata['service'] == service).count()
        
        # Get latest entry for this service
        try:
            latest = kb.where(kb.metadata['service'] == service).order_by(kb.created_at, asc=False).limit(1).collect()[0]
            latest_time = latest['created_at'].strftime('%Y-%m-%d %H:%M')
            print(f'  {service:30s}: {count:4,} items (latest: {latest_time})')
        except:
            print(f'  {service:30s}: {count:4,} items')
    
    print()
    
    # Verbose mode: show recent entries
    if verbose:
        print(f'📝 Last {limit} Entries:')
        print('-' * 60)
        
        recent = kb.order_by(kb.created_at, asc=False).limit(limit).collect()
        
        for i, entry in enumerate(recent, 1):
            timestamp = entry['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            entry_type = entry.get('type', 'unknown')
            service = entry.get('metadata', {}).get('service', 'N/A') if isinstance(entry.get('metadata'), dict) else 'N/A'
            title = entry.get('title', 'N/A')
            path = entry.get('path', 'N/A')
            
            # Truncate long paths
            if len(path) > 50:
                path = '...' + path[-47:]
            
            print(f'{i:2d}. [{timestamp}] ({entry_type})')
            print(f'    Service: {service}')
            print(f'    Title:   {title[:60]}')
            print(f'    Path:    {path}')
            print()
    
    print('✓ Knowledge base is operational')
    print(f'Data location: ~/.pixeltable/')
    
    if not verbose and total > 0:
        print()
        print(f'💡 Tip: Run with -v flag to see last {limit} entries')
        print(f'   Example: ./check-status.sh -v')
    
except Exception as e:
    print(f'❌ Error: {e}')
    import traceback
    traceback.print_exc()
    print()
    print('Knowledge base may not be initialized yet.')
    print('Run: python3 pixeltable_setup.py')
    sys.exit(1)
"

