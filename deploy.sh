#!/bin/bash
# StudyPartner AI — One-command Cloud Run deployment
# Usage: ./deploy.sh
# Prerequisites: gcloud CLI installed and authenticated

set -e

# --- Configuration ---
PROJECT_ID="${GCP_PROJECT_ID:-}"
REGION="${GCP_REGION:-us-west1}"
SERVICE_NAME="studypartner-backend"
GEMINI_API_KEY="${GEMINI_API_KEY:-}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🧠 StudyPartner AI — Cloud Run Deployment${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# --- Check prerequisites ---
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI not found. Install: https://cloud.google.com/sdk/docs/install${NC}"
    exit 1
fi

if [ -z "$PROJECT_ID" ]; then
    # Try to get from gcloud config
    PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
    if [ -z "$PROJECT_ID" ]; then
        echo -e "${RED}❌ No GCP project set. Run: gcloud config set project YOUR_PROJECT_ID${NC}"
        exit 1
    fi
fi

if [ -z "$GEMINI_API_KEY" ]; then
    echo -e "${YELLOW}⚠️  GEMINI_API_KEY not set.${NC}"
    echo "Get one at: https://aistudio.google.com/apikey"
    read -p "Enter your Gemini API key: " GEMINI_API_KEY
    if [ -z "$GEMINI_API_KEY" ]; then
        echo -e "${RED}❌ API key required.${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✓ Project: ${PROJECT_ID}${NC}"
echo -e "${GREEN}✓ Region:  ${REGION}${NC}"
echo ""

# --- Enable required APIs ---
echo -e "${BLUE}Enabling required APIs...${NC}"
gcloud services enable run.googleapis.com --project="$PROJECT_ID" --quiet
gcloud services enable cloudbuild.googleapis.com --project="$PROJECT_ID" --quiet
gcloud services enable artifactregistry.googleapis.com --project="$PROJECT_ID" --quiet

# --- Build and deploy ---
echo -e "${BLUE}Building and deploying to Cloud Run...${NC}"
echo "(This may take 2-5 minutes on first deploy)"
echo ""

gcloud run deploy "$SERVICE_NAME" \
    --source . \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --platform=managed \
    --allow-unauthenticated \
    --memory=512Mi \
    --cpu=1 \
    --min-instances=0 \
    --max-instances=3 \
    --timeout=3600 \
    --set-env-vars="GEMINI_API_KEY=$GEMINI_API_KEY" \
    --quiet

# --- Get the URL ---
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --format="value(status.url)")

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Deployment successful!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "Backend URL: ${BLUE}${SERVICE_URL}${NC}"
echo ""
echo "Next steps:"
echo "  1. Run: studypartner setup"
echo "  2. Enter this backend URL when prompted: ${SERVICE_URL}"
echo "  3. Run: studypartner start"
echo ""
echo -e "${YELLOW}💡 Save this URL — you'll need it for client setup.${NC}"
