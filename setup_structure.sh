#!/bin/bash
# VOCAL VIEW - COMPLETE PROJECT GENERATOR
# This script creates the ENTIRE working project with ALL AI integrations

set -e

PROJECT_ROOT="/home/claude/vocal_view_complete"
echo "=========================================="
echo "  VOCAL VIEW - COMPLETE PROJECT SETUP"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}Creating project structure...${NC}"

# Create all directories
mkdir -p $PROJECT_ROOT/vocalview
mkdir -p $PROJECT_ROOT/interviews/{management/commands,ai_services,templates/{interviews,auth,reports},static/{css,js,images},migrations}
mkdir -p $PROJECT_ROOT/media/interviews/{audio,video}
mkdir -p $PROJECT_ROOT/media/reports/{pdf,json}
mkdir -p $PROJECT_ROOT/static
mkdir -p $PROJECT_ROOT/logs

# Create __init__.py files
touch $PROJECT_ROOT/vocalview/__init__.py
touch $PROJECT_ROOT/interviews/__init__.py
touch $PROJECT_ROOT/interviews/management/__init__.py
touch $PROJECT_ROOT/interviews/management/commands/__init__.py
touch $PROJECT_ROOT/interviews/ai_services/__init__.py
touch $PROJECT_ROOT/interviews/migrations/__init__.py

echo -e "${GREEN}✓ Directory structure created${NC}"

# Create requirements.txt
cat > $PROJECT_ROOT/requirements.txt << 'REQUIREMENTS'
# Core Django
Django==4.2.7
djangorestframework==3.14.0
python-decouple==3.8
psycopg2-binary==2.9.9

# AI/ML Libraries - ALL REQUIRED
openai-whisper==20231117
spacy==3.7.2
mediapipe==0.10.8
librosa==0.10.1
soundfile==0.12.1
numpy==1.24.3

# NLP
nltk==3.8.1

# PDF Generation
reportlab==4.0.7
Pillow==10.1.0

# Audio/Video
opencv-python==4.8.1.78
pydub==0.25.1

# Question Generation (Optional - uses templates if unavailable)
transformers==4.35.2
torch==2.1.1

# Utilities
python-dotenv==1.0.0
REQUIREMENTS

echo -e "${GREEN}✓ requirements.txt created${NC}"

# Create .env.example
cat > $PROJECT_ROOT/.env.example << 'ENV'
SECRET_KEY=your-secret-key-change-this-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DATABASE_NAME=vocalview_db
DATABASE_USER=vocalview_user
DATABASE_PASSWORD=your_secure_password
DATABASE_HOST=localhost
DATABASE_PORT=5432
ENV

echo -e "${GREEN}✓ .env.example created${NC}"

# Create .gitignore
cat > $PROJECT_ROOT/.gitignore << 'GITIGNORE'
__pycache__/
*.py[cod]
*.so
.Python
env/
venv/
*.log
db.sqlite3
.env
/media
/staticfiles
*.egg-info/
.DS_Store
GITIGNORE

echo -e "${GREEN}✓ .gitignore created${NC}"

echo ""
echo -e "${BLUE}Project structure is ready!${NC}"
echo ""
echo "Next steps:"
echo "1. All Python files will be created separately"
echo "2. Run: cd $PROJECT_ROOT"
echo "3. Run: python3 -m venv venv"
echo "4. Run: source venv/bin/activate"
echo "5. Run: pip install -r requirements.txt"
echo "6. Run: python -m spacy download en_core_web_sm"
echo "7. Configure PostgreSQL"
echo "8. Run migrations"
echo "9. Create superuser"
echo "10. Start server"
echo ""
echo -e "${GREEN}Setup script completed!${NC}"
