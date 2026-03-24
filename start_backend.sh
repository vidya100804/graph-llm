#!/bin/bash
# ================================================
# Dodge AI — SAP Order to Cash Graph Explorer
# Startup Script
# ================================================

echo ""
echo "======================================"
echo "  Dodge AI — O2C Graph Explorer"
echo "======================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found. Please install Python 3.8+"
    exit 1
fi

echo "✅ Python3 found: $(python3 --version)"

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
pip install flask flask-cors requests --quiet

echo ""
echo "🚀 Starting backend server on http://localhost:5000"
echo ""
echo "IMPORTANT: Set your Groq API key (free at console.groq.com):"
echo "  export GROQ_API_KEY=your_key_here"
echo ""

cd backend && python3 app.py
