#!/bin/bash

# Vocal View - Complete Project Setup Script
# This script generates all necessary files and sets up the project

set -e  # Exit on error

echo "================================================"
echo "  Vocal View - AI Interview Coach Setup"
echo "================================================"
echo ""

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

PROJECT_ROOT="/home/claude/vocal_view_project"

# Function to create directory
create_dir() {
    mkdir -p "$1"
    echo -e "${GREEN}✓${NC} Created directory: $1"
}

# Function to create file with content
create_file() {
    local filepath="$1"
    local content="$2"
    echo "$content" > "$filepath"
    echo -e "${GREEN}✓${NC} Created file: $filepath"
}

echo -e "${BLUE}Step 1:${NC} Creating project structure..."

# Create all directories
create_dir "$PROJECT_ROOT/interviews"
create_dir "$PROJECT_ROOT/interviews/ai_services"
create_dir "$PROJECT_ROOT/interviews/migrations"
create_dir "$PROJECT_ROOT/interviews/management"
create_dir "$PROJECT_ROOT/interviews/management/commands"
create_dir "$PROJECT_ROOT/interviews/templates"
create_dir "$PROJECT_ROOT/interviews/templates/interviews"
create_dir "$PROJECT_ROOT/interviews/templates/auth"
create_dir "$PROJECT_ROOT/interviews/templates/reports"
create_dir "$PROJECT_ROOT/interviews/static"
create_dir "$PROJECT_ROOT/interviews/static/css"
create_dir "$PROJECT_ROOT/interviews/static/js"
create_dir "$PROJECT_ROOT/interviews/static/images"
create_dir "$PROJECT_ROOT/media/interviews/audio"
create_dir "$PROJECT_ROOT/media/interviews/video"
create_dir "$PROJECT_ROOT/media/reports/pdf"
create_dir "$PROJECT_ROOT/media/reports/json"
create_dir "$PROJECT_ROOT/static"
create_dir "$PROJECT_ROOT/templates"
create_dir "$PROJECT_ROOT/logs"

echo ""
echo -e "${BLUE}Step 2:${NC} Creating Django application files..."

# Create __init__.py files
touch "$PROJECT_ROOT/interviews/__init__.py"
touch "$PROJECT_ROOT/interviews/ai_services/__init__.py"
touch "$PROJECT_ROOT/interviews/migrations/__init__.py"
touch "$PROJECT_ROOT/interviews/management/__init__.py"
touch "$PROJECT_ROOT/interviews/management/commands/__init__.py"

echo -e "${GREEN}✓${NC} Created __init__.py files"

# Create manage.py
cat > "$PROJECT_ROOT/manage.py" << 'EOF'
#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vocalview.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
EOF

chmod +x "$PROJECT_ROOT/manage.py"
echo -e "${GREEN}✓${NC} Created manage.py"

# Create .env.example
cat > "$PROJECT_ROOT/.env.example" << 'EOF'
# Django Settings
SECRET_KEY=your-secret-key-here-generate-a-strong-one
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_NAME=vocalview_db
DATABASE_USER=vocalview_user
DATABASE_PASSWORD=your_secure_password_here
DATABASE_HOST=localhost
DATABASE_PORT=5432
EOF

echo -e "${GREEN}✓${NC} Created .env.example"

# Create .gitignore
cat > "$PROJECT_ROOT/.gitignore" << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Django
*.log
local_settings.py
db.sqlite3
db.sqlite3-journal
/media
/staticfiles
/static

# Environment
.env
.venv

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# AI Models (these will be downloaded)
*.pt
*.pth
models/

# Logs
logs/
*.log
EOF

echo -e "${GREEN}✓${NC} Created .gitignore"

echo ""
echo -e "${BLUE}Step 3:${NC} Project structure created successfully!"
echo ""
echo "Next steps:"
echo "1. cd $PROJECT_ROOT"
echo "2. python3 -m venv venv"
echo "3. source venv/bin/activate"
echo "4. pip install -r requirements.txt"
echo "5. Setup PostgreSQL database"
echo "6. Copy .env.example to .env and configure"
echo "7. python manage.py migrate"
echo "8. python manage.py createsuperuser"
echo "9. python manage.py runserver"
echo ""
echo -e "${GREEN}Setup script completed!${NC}"
EOF

chmod +x "$PROJECT_ROOT/setup.sh"
