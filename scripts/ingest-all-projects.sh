#!/bin/bash
# Quick ingestion helper - customize for your projects

cd ~/.mcp-servers/luminescent-cluster

python3 << 'EOF'
from pixeltable_setup import setup_knowledge_base, ingest_codebase

kb = setup_knowledge_base()

# Add your projects here
projects = [
    ('/Users/christopherjoseph/projects/project1', 'project1-api'),
    ('/Users/christopherjoseph/projects/project2', 'frontend-app'),
    # Add more as needed
]

for repo_path, service_name in projects:
    print(f"\nIngesting {service_name} from {repo_path}...")
    try:
        count = ingest_codebase(kb, repo_path, service_name)
        print(f"✓ Ingested {count} files from {service_name}")
    except Exception as e:
        print(f"✗ Error ingesting {service_name}: {e}")

print("\n✓ All projects ingested!")
EOF
