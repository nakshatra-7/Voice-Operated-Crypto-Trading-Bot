# 🎤 Voice Integration Test Guide

## 🔧 **How to Test Voice Integration:**

### **Step 1: Open the App**
1. Go to http://localhost:3000
2. Open browser console (F12 → Console tab)

### **Step 2: Start a Call**
1. Enter your name
2. Click "Start Trading Call"
3. Check console for: `✅ Call started: {...}`

### **Step 3: Test Voice**
1. Click "🎤 Start Listening"
2. Check console for: `🎤 Speech recognition started`
3. Speak clearly: "Binance"
4. Check console for: `🎤 Voice input received: Binance`
5. Check console for: `📤 Sending voice input to backend: Binance`

### **Step 4: Verify Response**
1. Look for bot response in transcript
2. Check console for: `📨 WebSocket message: {...}`

## 🐛 **Common Issues & Solutions:**

### **Issue 1: "Speech recognition not supported"**
- **Solution**: Use Chrome, Firefox, or Safari
- **Check**: Browser console should show `❌ Speech recognition not supported`

### **Issue 2: Microphone permission denied**
- **Solution**: Allow microphone access when browser asks
- **Check**: Look for microphone icon in browser address bar

### **Issue 3: Voice not being processed**
- **Check**: Console should show voice input logs
- **Solution**: Speak clearly and wait for recognition to complete

### **Issue 4: No response from bot**
- **Check**: Backend logs for processing messages
- **Solution**: Ensure backend is running and WebSocket is connected

## 🎯 **Test Commands to Try:**

1. **"Binance"** - Should select Binance exchange
2. **"BTC-USDT"** - Should select Bitcoin trading pair
3. **"I want to trade 1.5 Bitcoin at $45,000"** - Should parse quantity and price
4. **"Yes"** - Should confirm the order

## 📊 **Expected Console Output:**

```
✅ Call started: {session_id: "...", voice_enabled: true, ...}
🎤 Speech recognition started
🎤 Voice input received: Binance
📤 Sending voice input to backend: Binance
✅ Voice input processed: {response_text: "..."}
📨 WebSocket message: {type: "update", data: [...]}
```

## 🔍 **Debugging Steps:**

1. **Check browser console** for voice recognition logs
2. **Check backend terminal** for processing logs
3. **Verify WebSocket connection** is active
4. **Test with simple words** first (e.g., "Binance", "Yes")
5. **Check microphone permissions** in browser settings 