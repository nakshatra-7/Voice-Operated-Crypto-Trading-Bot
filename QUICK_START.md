# 🚀 Quick Start Guide

## Prerequisites
- Python 3.8+ (✅ You have Python 3.13)
- Node.js 16+ (✅ You have Node.js 22.13.1)
- npm (✅ Included with Node.js)

## 🎯 Step-by-Step Setup

### 1. Get Bland.ai API Key
1. Go to [Bland.ai](https://bland.ai)
2. Sign up for a free account
3. Get your API key from the dashboard
4. Add it to `backend/.env` file

### 2. Configure Environment
```bash
cd backend
cp .env.example .env
# Edit .env and add your Bland.ai API key
```

### 3. Start the Application

#### Option A: Use the startup script (Recommended)
```bash
./start.sh
```

#### Option B: Manual start
```bash
# Terminal 1 - Backend
cd backend
source venv/bin/activate
python main.py

# Terminal 2 - Frontend  
cd frontend/goq
npm start
```

### 4. Access the Application
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## 🎮 How to Use

1. **Open the app** in your browser at http://localhost:3000
2. **Enter your name** in the input field
3. **Click "Start Trading Call"** to begin
4. **Follow the conversation flow**:
   - Choose an exchange (OKX, Bybit, Deribit, Binance)
   - Select a trading symbol (e.g., BTC-USDT)
   - Specify quantity and price
   - Confirm your order

## 🔧 Troubleshooting

### Backend Issues
- Make sure you're in the virtual environment: `source venv/bin/activate`
- Check if port 8000 is available: `lsof -i :8000`
- Verify your `.env` file has the Bland.ai API key

### Frontend Issues
- Make sure you're in the frontend directory: `cd frontend/goq`
- Run `npm install` if dependencies are missing
- Check if port 3000 is available: `lsof -i :3000`

### Common Errors
- **"Module not found"**: Run `pip install -r requirements.txt` in backend
- **"Port already in use"**: Stop the service using that port or use different ports
- **"WebSocket connection failed"**: Make sure backend is running first

## 📞 Support
- Check the main README.md for detailed documentation
- Review the API docs at http://localhost:8000/docs
- Check browser console for frontend errors
- Check terminal output for backend errors

## 🎉 You're Ready!
Your voice trading bot is now set up and ready to use! The system simulates OTC trading conversations without placing real orders. 