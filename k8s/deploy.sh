#!/bin/bash
# Deploy the entire context-aware AI system to Kubernetes

set -e

echo "======================================================================"
echo "Deploying Context-Aware AI System to Kubernetes"
echo "======================================================================"
echo ""

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "Error: kubectl not found. Please install kubectl first."
    exit 1
fi

# Check if cluster is accessible
if ! kubectl cluster-info &> /dev/null; then
    echo "Error: Cannot connect to Kubernetes cluster."
    echo "Please check your kubeconfig and cluster access."
    exit 1
fi

echo "✓ kubectl found and cluster is accessible"
echo ""

# Prompt for OpenAI API key if not set
if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  OPENAI_API_KEY not set in environment"
    echo "Multimodal features (meeting transcription) will not work without it."
    read -p "Enter OpenAI API key (or press Enter to skip): " OPENAI_KEY
    if [ -n "$OPENAI_KEY" ]; then
        OPENAI_API_KEY="$OPENAI_KEY"
    else
        OPENAI_API_KEY="REPLACE_ME"
    fi
fi

echo ""
echo "Step 1: Creating namespace..."
kubectl apply -f k8s/namespace.yaml

echo ""
echo "Step 2: Creating ConfigMaps..."
kubectl apply -f k8s/configmaps.yaml

echo ""
echo "Step 3: Creating Secrets..."
# Create secret from environment variable, not from file
kubectl create secret generic openai-api-key \
  --from-literal=OPENAI_API_KEY="$OPENAI_API_KEY" \
  -n context-aware-ai \
  --dry-run=client -o yaml | kubectl apply -f -

echo ""
echo "Step 4: Creating PersistentVolumeClaims..."
kubectl apply -f k8s/persistent-volumes.yaml

echo ""
echo "Step 5: Deploying Session Memory server..."
kubectl apply -f k8s/deployment-session-memory.yaml

echo ""
echo "Step 6: Deploying Pixeltable Memory server..."
kubectl apply -f k8s/deployment-pixeltable.yaml

echo ""
echo "Step 7: Creating Services..."
kubectl apply -f k8s/services.yaml

echo ""
echo "======================================================================"
echo "✓ Deployment Complete!"
echo "======================================================================"
echo ""
echo "Checking deployment status..."
kubectl get pods -n context-aware-ai
echo ""
echo "To watch pods start:"
echo "  kubectl get pods -n context-aware-ai -w"
echo ""
echo "To view logs:"
echo "  kubectl logs -f deployment/session-memory -n context-aware-ai"
echo "  kubectl logs -f deployment/pixeltable-memory -n context-aware-ai"
echo ""
echo "To access the MCP servers from Claude Code:"
echo "  Update your MCP configuration to point to the Kubernetes services"
echo ""
