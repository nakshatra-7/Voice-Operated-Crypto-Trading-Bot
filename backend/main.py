import asyncio
import json
import logging
import re
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from difflib import SequenceMatcher

import httpx
import nltk
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv


load_dotenv()    # loading  envirionment variables 

# smart text processor globally initialised
smart_processor = None

# for debugging mainly, monitoring APIs, conversation,etc. , all content saved to trading_bot.log 
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('trading_bot.log')
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Trading Bot API", version="1.0.0")  # FastAPI app initialised

# CORS middleware, allows requests from any origin, CORS connects frontend and backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state, to keep track of active sessions and Websocket connections
active_sessions: Dict[str, Dict] = {}
active_connections: Dict[str, WebSocket] = {}

# Exchange configurations
EXCHANGES = {
    "okx": {
        "name": "OKX",
        "base_url": "https://www.okx.com",
        "symbols": ["BTC-USDT", "ETH-USDT", "XRP-USDT", "LTC-USDT", "ADA-USDT", "DOT-USDT", "LINK-USDT", "BCH-USDT", "EOS-USDT", "TRX-USDT"],
        "price_endpoint": "/api/v5/market/ticker",
        "symbols_endpoint": "/api/v5/public/instruments"
    },
    "bybit": {
        "name": "Bybit",
        "base_url": "https://api.bybit.com",
        "symbols": ["BTC-USDT", "ETH-USDT", "XRP-USDT", "ETH-BTC", "XRP-BTC", "DOT-USDT", "XLM-USDT", "LTC-USDT", "DOGE-USDT", "CHZ-USDT"],
        "price_endpoint": "/v5/market/tickers",
        "symbols_endpoint": "/v5/market/instruments-info"
    },
    "deribit": {
        "name": "Deribit",
        "base_url": "https://www.deribit.com",
        "symbols": ["BTC-PERPETUAL", "ETH-PERPETUAL", "BTC-30JUN23", "ETH-30JUN23", "BTC-29SEP23", "ETH-29SEP23"],
        "price_endpoint": "/api/v2/public/ticker",
        "symbols_endpoint": "/api/v2/public/get_instruments"
    },
    "binance": {
        "name": "Binance",
        "base_url": "https://api.binance.com",
        "symbols": ["ETH-BTC", "LTC-BTC", "BNB-BTC", "NEO-BTC", "QTUM-ETH", "EOS-ETH", "SNT-ETH", "BNT-ETH", "BCC-BTC", "GAS-BTC"],
        "price_endpoint": "/api/v3/ticker/price",
        "symbols_endpoint": "/api/v3/exchangeInfo"
    }
}

#call setup
#Basemodel is  library, its main job to validate the data, and convert it to objects

class CallRequest(BaseModel):
    user_name: str

class VoiceInput(BaseModel):
    from_: str
    to: str
    text: str
    direction: str 

class SessionState:
    def __init__(self):
        self.state = "await_exchange"
        self.exchange = None
        self.symbol = None
        self.quantity = None
        self.price = None
        self.symbols = []
        self.current_price = 0.0

def get_session_state(session_id: str) -> SessionState:
    if session_id not in active_sessions:
        # Create a new session if it doesn't exist
        session_state = SessionState()
        active_sessions[session_id] = {
            "state": session_state,
            "user_name": "Trader",
            "created_at": datetime.now().isoformat()
        }
        return session_state
    
    # Return the existing session state
    return active_sessions[session_id]["state"]

#setting symbols, exchanges, quantity, fetching price, etc.
#retry logic used
async def fetch_price_with_retry(symbol: str, exchange: str, max_retries: int = 3) -> float:

    exchange_config = EXCHANGES.get(exchange.lower())
    if not exchange_config:
        logger.error(f"Unsupported exchange: {exchange}")
        return 0.0

    for attempt in range(max_retries):
        try:
            logger.info(f"Fetching price for {symbol} from {exchange_config['name']} (attempt {attempt + 1})")
            
            # Try different price fetching strategies
            price = await fetch_price_strategy_1(symbol, exchange_config)
            if price > 0:
                return price
                
            price = await fetch_price_strategy_2(symbol, exchange_config)
            if price > 0:
                return price
                
            mock_price = generate_mock_price(symbol)
            logger.warning(f"Using mock price for {symbol}: ${mock_price}")
            return mock_price
            
        except Exception as e:
            logger.error(f"Error fetching price (attempt {attempt + 1}): {str(e)}")
            if attempt == max_retries - 1:
                logger.error(f"Failed to fetch price after {max_retries} attempts")
                return generate_mock_price(symbol)
            await asyncio.sleep(1)  # Wait before retry
    
    return generate_mock_price(symbol)


async def fetch_price_strategy_1(symbol: str, exchange_config: Dict) -> float:

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if exchange_config["name"] == "Bybit":
                url = f"{exchange_config['base_url']}{exchange_config['price_endpoint']}?category=spot&symbol={symbol}"
            elif exchange_config["name"] == "Binance":
                url = f"{exchange_config['base_url']}{exchange_config['price_endpoint']}?symbol={symbol}"
            elif exchange_config["name"] == "OKX":
                url = f"{exchange_config['base_url']}{exchange_config['price_endpoint']}?instId={symbol}"
            else:
                url = f"{exchange_config['base_url']}{exchange_config['price_endpoint']}?symbol={symbol}"

            logger.info(f"Making request to: {url}")
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            logger.info(f"Response from {exchange_config['name']}: {data}")

            price = extract_price_from_response(data, exchange_config["name"], symbol)
            if price > 0:
                logger.info(f"Extracted price for {symbol}: {price}")
                return price
                
    except Exception as e:
        logger.error(f"Strategy 1 failed for {symbol}: {str(e)}")
    
    return 0.0

async def fetch_price_strategy_2(symbol: str, exchange_config: Dict) -> float:

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Try alternative endpoints or different symbol formats
            alt_symbol = symbol.replace("-", "").replace("_", "")
            url = f"{exchange_config['base_url']}/api/v1/ticker?symbol={alt_symbol}"
            
            logger.info(f"Strategy 2 - Making request to: {url}")
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            price = extract_price_from_response(data, exchange_config["name"], alt_symbol)
            if price > 0:
                logger.info(f"Strategy 2 extracted price for {symbol}: {price}")
                return price
                
    except Exception as e:
        logger.error(f"Strategy 2 failed for {symbol}: {str(e)}")
    
    return 0.0

def extract_price_from_response(data: Dict, exchange_name: str, symbol: str) -> float:

    try:
        if exchange_name == "Bybit":
            if "result" in data and "list" in data["result"]:
                for item in data["result"]["list"]:
                    if item.get("symbol") == symbol:
                        return float(item.get("lastPrice", 0))
        elif exchange_name == "Binance":
            if "price" in data:
                return float(data["price"])
        elif exchange_name == "OKX":
            if "data" in data and len(data["data"]) > 0:
                return float(data["data"][0].get("last", 0))
        else:
            # Generic extraction
            if "price" in data:
                return float(data["price"])
            elif "last" in data:
                return float(data["last"])
            elif "close" in data:
                return float(data["close"])
                
    except (ValueError, KeyError, TypeError) as e:
        logger.error(f"Error extracting price from {exchange_name} response: {str(e)}")
    
    return 0.0

def generate_mock_price(symbol: str) -> float:
    """Generate a realistic mock price for demonstration"""
    import random
    base_prices = {
        "BTC": 45000 + random.uniform(-2000, 2000),
        "ETH": 3000 + random.uniform(-200, 200),
        "XRP": 2 + random.uniform(-0.5, 0.5),
        "LTC": 150 + random.uniform(-20, 20),
        "ADA": 1.5 + random.uniform(-0.3, 0.3),
        "DOT": 25 + random.uniform(-5, 5),
        "LINK": 18 + random.uniform(-3, 3),
        "BCH": 400 + random.uniform(-50, 50),
        "EOS": 3 + random.uniform(-0.5, 0.5),
        "TRX": 0.1 + random.uniform(-0.02, 0.02),
        "NEO": 35 + random.uniform(-5, 5),
        "QTUM": 8 + random.uniform(-1, 1),
        "SNT": 0.05 + random.uniform(-0.01, 0.01),
        "BNT": 2 + random.uniform(-0.3, 0.3),
        "GAS": 12 + random.uniform(-2, 2)
    }
    
    for coin, base_price in base_prices.items():
        if coin in symbol.upper():
            return round(base_price, 4)
    
    return round(random.uniform(1, 100), 4)

async def get_exchange_symbols(exchange: str) -> List[str]:
    exchange_config = EXCHANGES.get(exchange.lower())
    if not exchange_config:
        logger.error(f"Unsupported exchange: {exchange}")
        return []
    
    # Return default symbols immediately to avoid async issues
    default_symbols = ["BTC-USDT", "ETH-USDT", "XRP-USDT", "LTC-USDT", "ADA-USDT", "DOT-USDT", "LINK-USDT", "BCH-USDT", "EOS-USDT", "TRX-USDT"]
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            url = f"{exchange_config['base_url']}{exchange_config['symbols_endpoint']}"
            logger.info(f"Fetching symbols from: {url}")
            
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            # Extract symbols based on exchange
            symbols = extract_symbols_from_response(data, exchange_config["name"])
            if symbols:
                return symbols[:10]  # Return top 10 symbols
            else:
                return default_symbols
                
    except Exception as e:
        logger.error(f"Error fetching symbols for {exchange}: {str(e)}")
        return default_symbols

def extract_symbols_from_response(data: Dict, exchange_name: str) -> List[str]:
    """Extract symbols from exchange response"""
    try:
        symbols = []
        if exchange_name == "Bybit":
            if "result" in data and "list" in data["result"]:
                symbols = [item["symbol"] for item in data["result"]["list"][:10]]
        elif exchange_name == "Binance":
            if "symbols" in data:
                symbols = [item["symbol"] for item in data["symbols"][:10]]
        elif exchange_name == "OKX":
            if "data" in data:
                symbols = [item["instId"] for item in data["data"][:10]]
        return symbols
    except Exception as e:
        logger.error(f" Error extracting symbols from {exchange_name}: {str(e)}")
        return []

def normalize_symbol(symbol: str, exchange: str) -> str:
   
    symbol = symbol.upper().strip()
    # Remove common words
    symbol = re.sub(r'\b(USDT|USD|BTC|ETH)\b', '', symbol).strip()
    # Add back the base currency based on exchange
    exchange_config = EXCHANGES.get(exchange.lower())
    if exchange_config:
        if exchange_config["name"] == "Binance":
            return f"{symbol}BTC"
        elif exchange_config["name"] == "Bybit":
            return f"{symbol}USDT"
        elif exchange_config["name"] == "OKX":
            return f"{symbol}-USDT"
    return symbol

def extract_quantity_and_price(text: str) -> tuple:
    
    try:
        quantity_patterns = [
            r'(\d+(?:\.\d+)?)\s*(?:of|units?|coins?|tokens?|shares?)',
            r'trade\s*(\d+(?:\.\d+)?)',
            r'buy\s*(\d+(?:\.\d+)?)',
            r'sell\s*(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*(?:at|for|price)',
        ]
        
        price_patterns = [
            r'at\s*\$?(\d+(?:\.\d+)?)',
            r'price\s*\$?(\d+(?:\.\d+)?)',
            r'for\s*\$?(\d+(?:\.\d+)?)',
            r'Rs\s*(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*dollars?',
        ]
        
        quantity = None
        price = None
        
        # Extract quantity
        for pattern in quantity_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                quantity = float(match.group(1))
                break
        
        # Extract price
        for pattern in price_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                price = float(match.group(1))
                break
        
        logger.info(f"🔍 Extracted from '{text}': quantity={quantity}, price={price}")
        return quantity, price
        
    except Exception as e:
        logger.error(f"Error extracting quantity and price: {str(e)}")
        return None, None
 
# voice processing system 
async def process_voice_input(text: str, session_state: SessionState) -> str:

    try:
        logger.info(f"Type of session_state: {type(session_state)}")
        text = text.strip().lower()
        logger.info(f"Processing voice input: '{text}' in state: {session_state.state}")
        
        if smart_processor.is_correction(text):
            return await handle_correction(text, session_state)
        
        if session_state.state == "await_exchange":
            exchange = smart_processor.extract_exchange(text)
            
            if exchange:
                session_state.exchange = exchange
                session_state.state = "await_symbol"
                
                try:
                    symbols = await fetch_symbols_with_retry(exchange)
                    session_state.symbols = symbols
                    return f"Great! I've selected {exchange.capitalize()}. Now please specify which symbol you'd like to trade. Available symbols: {', '.join(symbols[:5])}. You can also ask for specific types like 'show only bitcoin symbols' or 'show only ethereum symbols'."
                except Exception as e:
                    logger.error(f"Error fetching symbols for {exchange}: {str(e)}")
                    return f"Great! I've selected {exchange.capitalize()}. Now please specify which symbol you'd like to trade."
            else:
                return "Please specify which exchange you'd like to use. Available exchanges: OKX, Bybit, Deribit, Binance"
        
        elif session_state.state == "await_symbol":

            if smart_processor.is_filter_request(text):
                crypto = smart_processor.extract_filter_crypto(text)
                if crypto:

                    filtered_symbols = []
                    for symbol in session_state.symbols:
                        symbol_lower = symbol.lower()
                        if crypto in symbol_lower or any(var in symbol_lower for var in smart_processor.crypto_variations.get(crypto, [])):
                            filtered_symbols.append(symbol)
                    
                    if filtered_symbols:
                        session_state.symbols = filtered_symbols
                        return f"Here are all {crypto.capitalize()}-related symbols: {', '.join(filtered_symbols)}"
                    else:
                        return f"No {crypto.capitalize()} symbols found on {session_state.exchange.capitalize()}. Please try a different symbol or ask to see all available symbols."
                else:

                    symbols = session_state.symbols
                    return f"Here are all available symbols: {', '.join(symbols)}"
            
            if not session_state.symbols:
                session_state.symbols = ["BTC-USDT", "ETH-USDT", "XRP-USDT", "LTC-USDT", "ADA-USDT"]
            
            for symbol in session_state.symbols:
                symbol_clean = symbol.lower().replace("-", "").replace("_", "")
                text_clean = text.replace(" ", "").lower()
                
                if symbol_clean in text_clean or text_clean in symbol_clean:
                    session_state.symbol = symbol
                    session_state.state = "await_quantity_and_price"
                    
                    # Fetching current price for the selected symbol
                    try:
                        current_price = await fetch_price_with_retry(symbol, session_state.exchange)
                        session_state.current_price = current_price
                        return f"Perfect! I've selected {symbol}. Current price: ${current_price:,.2f} USDT. Now please specify both the quantity and price you'd like to trade at (e.g., '0.1 BTC at 50000' or '100 USDT at 50000')."
                    except Exception as e:
                        logger.error(f"Error fetching price for {symbol}: {str(e)}")
                        return f"Perfect! I've selected {symbol}. Now please specify both the quantity and price you'd like to trade at (e.g., '0.1 BTC at 50000' or '100 USDT at 50000')."
            
            return f"Please specify which symbol you'd like to trade. Available symbols: {', '.join(session_state.symbols[:5])}. You can also ask for specific types like 'show only bitcoin symbols' or 'show only ethereum symbols'."
        
        elif session_state.state == "await_quantity_and_price":
            # Extracting quantity and price
            quantity, price = smart_processor.extract_quantity_and_price(text)
            
            # Checking if we already have quantity or price from previous input
            current_quantity = session_state.quantity
            current_price = session_state.price
            
            if quantity is not None:
                current_quantity = quantity
                session_state.quantity = quantity
            if price is not None:
                current_price = price
                session_state.price = price
            
            # if we have both quantity and price, proceed to confirmation
            if current_quantity is not None and current_price is not None:
                session_state.state = "confirm_order"
                
                symbol = session_state.symbol
                exchange = session_state.exchange
                
                return f"Perfect! I'm about to place a {exchange.capitalize()} order for {current_quantity} {symbol} at ${current_price:,.2f} USDT. Please confirm by saying 'yes' or 'confirm'."
            
            # ask for price input if only quantity input there
            elif current_quantity is not None:
                return f"Got the quantity: {current_quantity}. Now please specify the price you'd like to trade at (e.g., 'at 50000' or 'price 50000')."
            
            # ask for quantity input if only price input there
            elif current_price is not None:
                return f"Got the price: ${current_price:,.2f}. Now please specify the quantity you'd like to trade (e.g., '0.25 BTC' or '100 USDT')."
            
            # If we have neither, ask for both
            else:
                return "I couldn't understand the quantity and price. Please specify both the quantity and price you'd like to trade at (e.g., '0.1 BTC at 50000' or '100 USDT at 50000')."
        
        elif session_state.state == "confirm_order":
            if any(word in text for word in ["yes", "confirm", "okay", "sure", "go ahead"]):

                symbol = session_state.symbol
                quantity = session_state.quantity
                price = session_state.price
                exchange = session_state.exchange
                
                logger.info(f"Placing order: {quantity} {symbol} at ${price} on {exchange}")
                
                session_state.state = "await_continue"
                return f"Order placed successfully! {quantity} {symbol} at ${price:,.2f} USDT on {exchange.capitalize()}. Would you like to place another order? Say 'yes' to continue or 'no' to end the call."
            elif any(word in text for word in ["no", "cancel", "stop", "end"]):
                session_state.state = "end_call"
                return "Order cancelled. Thank you for using the our Trading Bot!"
            else:
                return "Please confirm the order by saying 'yes' or 'confirm', or cancel by saying 'no'."
        
        elif session_state.state == "await_continue":
            if any(word in text for word in ["yes", "continue", "another", "more"]):
                # Reset session state to start over
                session_state.state = "await_exchange"
                session_state.exchange = None
                session_state.symbol = None
                session_state.quantity = None
                session_state.price = None
                session_state.symbols = []
                session_state.current_price = None
                return "Perfect! Let's place another order. Please specify which exchange you'd like to use. Available exchanges: OKX, Bybit, Deribit, Binance"
            elif any(word in text for word in ["no", "stop", "end", "done"]):
                session_state.state = "end_call"
                return "Thank you for using the our Trading Bot! Have a great day!"
            else:
                return "Please say 'yes' to place another order or 'no' to end the call."
        
        else:
            return "I'm not sure what you're asking. Please try again."
    
    except Exception as e:
        logger.error(f"Error processing voice input: {str(e)}")
        return "I encountered an error processing your request. Please try again."

async def handle_correction(text: str, session_state: SessionState) -> str:

    try:
        what_to_correct, new_value = smart_processor.extract_correction(text)
        
        if not what_to_correct or not new_value:
            return "I didn't understand the correction. Please try again with a clearer format like 'not ethereum, I meant bitcoin' or 'change ethereum to bitcoin'."
        

        if what_to_correct in smart_processor.exchange_variations:
            if new_value in smart_processor.exchange_variations:

                session_state.exchange = new_value
                session_state.state = "await_symbol"
                session_state.symbol = None
                session_state.quantity = None
                session_state.price = None
                
                try:
                    symbols = await fetch_symbols_with_retry(new_value)
                    session_state.symbols = symbols
                    return f"Got it! I've changed the exchange to {new_value.capitalize()}. Now please specify which symbol you'd like to trade. Available symbols: {', '.join(symbols[:5])}."
                except Exception as e:
                    logger.error(f"Error fetching symbols for {new_value}: {str(e)}")
                    return f"Got it! I've changed the exchange to {new_value.capitalize()}. Now please specify which symbol you'd like to trade."
        

        elif what_to_correct in smart_processor.crypto_variations:
            if new_value in smart_processor.crypto_variations:
                if session_state.state == "await_symbol":
                    new_symbol = None
                    for symbol in session_state.symbols:
                        symbol_lower = symbol.lower()
                        if new_value in symbol_lower or any(var in symbol_lower for var in smart_processor.crypto_variations.get(new_value, [])):
                            new_symbol = symbol
                            break
                    
                    if new_symbol:
                        session_state.symbol = new_symbol
                        session_state.state = "await_quantity_and_price"
                        
                        try:
                            current_price = await fetch_price_with_retry(new_symbol, session_state.exchange)
                            session_state.current_price = current_price
                            return f"Got it! I've changed the symbol to {new_symbol}. Current price: ${current_price:,.2f} USDT. Now please specify both the quantity and price you'd like to trade at."
                        except Exception as e:
                            logger.error(f"Error fetching price for {new_symbol}: {str(e)}")
                            return f"Got it! I've changed the symbol to {new_symbol}. Now please specify both the quantity and price you'd like to trade at."
                    else:
                        return f"I couldn't find a {new_value.capitalize()} symbol on {session_state.exchange.capitalize()}. Please choose from the available symbols."
            
            elif new_value in smart_processor.exchange_variations:

                session_state.exchange = new_value
                session_state.state = "await_symbol"
                session_state.symbol = None
                session_state.quantity = None
                session_state.price = None
                
                try:
                    symbols = await fetch_symbols_with_retry(new_value)
                    session_state.symbols = symbols
                    return f"Got it! I've changed the exchange to {new_value.capitalize()}. Now please specify which symbol you'd like to trade. Available symbols: {', '.join(symbols[:5])}."
                except Exception as e:
                    logger.error(f"Error fetching symbols for {new_value}: {str(e)}")
                    return f"Got it! I've changed the exchange to {new_value.capitalize()}. Now please specify which symbol you'd like to trade."
        
        return f"I've updated your selection from {what_to_correct.capitalize()} to {new_value.capitalize()}. Please continue with your order."
    
    except Exception as e:
        logger.error(f"Error handling correction: {str(e)}")
        return "I encountered an error processing your correction. Please try again."

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "active_sessions": len(active_sessions),
            "active_connections": len(active_connections)
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Service unhealthy")

@app.post("/start_call")
async def start_call(request: CallRequest, background_tasks: BackgroundTasks):
    """Start a new call session"""
    try:
        session_id = str(uuid.uuid4())
        session_state = SessionState()
        
        active_sessions[session_id] = {
            "state": session_state,
            "user_name": request.user_name,
            "created_at": datetime.now().isoformat()
        }
        
        logger.info(f"Starting new call session: {session_id} for user: {request.user_name}")
        logger.info(f"Session initialized with state: {session_state.state}")
        
        background_tasks.add_task(simulate_bland_call, session_id)
        
        logger.info(f"Call session {session_id} ready. Active sessions: {list(active_sessions.keys())}")
        
        return {
            "session_id": session_id,
            "message": "Call session started successfully",
            "status": "ready"
        }
        
    except Exception as e:
        logger.error(f"Error starting call: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start call: {str(e)}")

@app.post("/end_call/{session_id}")
async def end_call(session_id: str):
    """End a call session"""
    try:
        logger.info(f"Ending call session: {session_id}")
        
        # Close WebSocket connection if exists
        if session_id in active_connections:
            try:
                await active_connections[session_id].close()
                logger.info(f"Closed WebSocket connection for session {session_id}")
            except Exception as e:
                logger.error(f"Error closing WebSocket: {str(e)}")
            finally:
                del active_connections[session_id]
        
        # Remove session from active sessions
        if session_id in active_sessions:
            del active_sessions[session_id]
            logger.info(f"Call session {session_id} ended")
            return {"message": "Call ended successfully"}
        else:
            logger.warning(f"Session {session_id} not found in active sessions")
            return {"message": "Session not found, but cleaned up connections"}
            
    except Exception as e:
        logger.error(f"Error ending call: {str(e)}")
        # Still try to clean up
        if session_id in active_connections:
            del active_connections[session_id]
        if session_id in active_sessions:
            del active_sessions[session_id]
        raise HTTPException(status_code=500, detail=f"Failed to end call: {str(e)}")

# Bland.ai webhook,receives voice input, processes it and sends back response
@app.post("/bland_webhook/{session_id}")
async def bland_webhook(session_id: str, request: Request):
    try:
        body = await request.body()
        logger.info(f"Raw request body: {body}")
        try:
            import json
            raw_data = json.loads(body)
            logger.info(f"Parsed JSON data: {raw_data}")
        except Exception as json_error:
            logger.error(f"Failed to parse JSON: {json_error}")
        voice_input = VoiceInput(**raw_data)
        logger.info(f"Received webhook request for session {session_id}")
        logger.info(f"Voice input data: {voice_input}")
        logger.info(f"Voice input text: {voice_input.text}")
        logger.info(f"Voice input from_: {voice_input.from_}")
        logger.info(f"Voice input to: {voice_input.to}")
        logger.info(f"Voice input direction: {voice_input.direction}")
        if session_id not in active_sessions:
            logger.error(f"Session {session_id} not found")
            raise HTTPException(status_code=404, detail="Session not found")
        logger.info(f"Received voice input webhook for session {session_id}: {voice_input.text}")
        session_state = get_session_state(session_id)
        bot_response = await process_voice_input(voice_input.text, session_state)
        logger.info(f"Bot response: {bot_response}")
        
        # Check if call should be ended
        if session_state.state == "end_call":
            logger.info(f"Call ended for session {session_id}, cleaning up...")
            # Clean up the session
            if session_id in active_sessions:
                del active_sessions[session_id]
            if session_id in active_connections:
                try:
                    await active_connections[session_id].close()
                except Exception as e:
                    logger.error(f"Error closing WebSocket: {str(e)}")
                finally:
                    del active_connections[session_id]
        
        if session_id in active_connections:
            try:
                await active_connections[session_id].send_json({
                    "type": "transcript_update",
                    "speaker": "bot",
                    "text": bot_response,
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                logger.error(f"Error sending WebSocket message: {str(e)}")
        return {"status": "processed", "response": bot_response}
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to process webhook: {str(e)}")

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time communication"""
    try:
        await websocket.accept()
        logger.info(f"WebSocket connection established for session {session_id}")
        
        # Store the connection
        active_connections[session_id] = websocket
        
        # Send initial connection message
        try:
            await websocket.send_json({
                "type": "connection_established",
                "session_id": session_id,
                "timestamp": datetime.now().isoformat()
            })
            
            # Send initial greeting if session exists
            if session_id in active_sessions:
                session_state = get_session_state(session_id)
                greeting = "Hello! Welcome to our OTC Trading Bot. I'm here to help you place trades. Which exchange would you like to use? Available exchanges: OKX, Bybit, Deribit, and Binance."
                
                await websocket.send_json({
                    "type": "transcript_update",
                    "speaker": "bot",
                    "text": greeting,
                    "timestamp": datetime.now().isoformat()
                })
                
                logger.info(f"Sent initial greeting for session {session_id}")
            
        except Exception as e:
            logger.error(f"Error sending initial message: {str(e)}")
        
        try:
            while True:
                # Keep connection alive and handle incoming messages
                data = await websocket.receive_text()
                logger.info(f"Received WebSocket message: {data}")
                
                # Process any incoming messages if needed
                try:
                    message_data = json.loads(data)
                    if message_data.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received: {data}")
                    
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for session {session_id}")
        except Exception as e:
            logger.error(f"WebSocket error for session {session_id}: {str(e)}")
        finally:
            # Clean up connection
            if session_id in active_connections:
                del active_connections[session_id]
                logger.info(f"Cleaned up WebSocket connection for session {session_id}")
                
    except Exception as e:
        logger.error(f"Error in WebSocket endpoint: {str(e)}")
        # cllean up connection on error
        if session_id in active_connections:
            del active_connections[session_id]

async def simulate_bland_call(session_id: str):
    """Simulate Bland.ai call setup"""
    try:
        logger.info(f"Simulating Bland.ai call for session {session_id}")
        await asyncio.sleep(1)  # Simulate call setup time
        logger.info(f"Bland.ai call simulation completed for session {session_id}")
    except Exception as e:
        logger.error(f"Error in Bland.ai simulation: {str(e)}")

# Smart text processing class
class SmartTextProcessor:
    def __init__(self):
        try:
            nltk.download('punkt', quiet=True)
            nltk.download('stopwords', quiet=True)
        except:
            pass
        
        self.exchange_variations = {
            "binance": ["binance", "bynance", "bynants", "finance"],
            "bybit": ["bybit", "by bit", "by bits", "by weight"],
            "okx": ["okx", "ok x", "okay x", "ok"],
            "deribit": ["deribit", "deri bit", "derive it", "derivate"]
        }
        
        self.crypto_variations = {
            "bitcoin": ["bitcoin", "btc", "bit coin", "bit"],
            "ethereum": ["ethereum", "eth", "ether", "eutherium", "uthirium", "you theory", "you turium"],
            "ripple": ["ripple", "xrp", "rip"],
            "litecoin": ["litecoin", "ltc", "lite coin"],
            "cardano": ["cardano", "ada"],
            "polkadot": ["polkadot", "dot"],
            "chainlink": ["chainlink", "link"],
            "stellar": ["stellar", "xlm"],
            "dogecoin": ["dogecoin", "doge"],
            "chiliz": ["chiliz", "chz"]
        }
        
        self.correction_phrases = [
            "not", "no", "change", "correction", "actually", "i meant", "i mean",
            "instead", "rather", "switch", "different", "wrong", "mistake"
        ]
        
        self.negation_words = ["not", "no", "wrong", "incorrect", "different", "change"]
    
    def normalize_text(self, text: str) -> str:
        return text.lower().strip()
    
    def is_correction(self, text: str) -> bool:
        text_lower = text.lower()
        return any(phrase in text_lower for phrase in self.correction_phrases)
    
    def extract_correction(self, text: str) -> tuple[Optional[str], Optional[str]]:

        text_lower = text.lower()
        
        # Handle patterns like "not ethereum, i meant bitcoin"
        if "not" in text_lower and ("i meant" in text_lower or "i mean" in text_lower):
            parts = text_lower.split("i meant")
            if len(parts) == 2:
                not_part = parts[0].replace("not", "").strip()
                meant_part = parts[1].strip()
                
                # Extract what to correct
                for crypto, variations in self.crypto_variations.items():
                    if any(var in not_part for var in variations):
                        # Extract new value
                        for new_crypto, new_variations in self.crypto_variations.items():
                            if any(var in meant_part for var in new_variations):
                                return crypto, new_crypto
                        
                        # Check for exchange corrections
                        for exchange, exchange_vars in self.exchange_variations.items():
                            if any(var in meant_part for var in exchange_vars):
                                return crypto, exchange
        
        # Handle patterns like "change ethereum to bitcoin"
        if "change" in text_lower and "to" in text_lower:
            parts = text_lower.split("to")
            if len(parts) == 2:
                change_part = parts[0].replace("change", "").strip()
                to_part = parts[1].strip()
                
                # Extract what to change and what to change to
                old_value = None
                new_value = None
                
                # Check for crypto corrections
                for crypto, variations in self.crypto_variations.items():
                    if any(var in change_part for var in variations):
                        old_value = crypto
                        break
                
                # Check for exchange corrections
                for exchange, variations in self.exchange_variations.items():
                    if any(var in change_part for var in variations):
                        old_value = exchange
                        break
                
                # Find new value
                for crypto, variations in self.crypto_variations.items():
                    if any(var in to_part for var in variations):
                        new_value = crypto
                        break
                
                for exchange, variations in self.exchange_variations.items():
                    if any(var in to_part for var in variations):
                        new_value = exchange
                        break
                
                if old_value and new_value:
                    return old_value, new_value
        
        return None, None
    
    def fuzzy_match(self, text: str, candidates: List[str], threshold: float = 0.6) -> Optional[str]:
        """Fuzzy match text against candidates"""
        text_lower = text.lower()
        
        for candidate in candidates:
            candidate_lower = candidate.lower()
            
            # Exact match
            if text_lower == candidate_lower:
                return candidate
            
            # Contains match
            if text_lower in candidate_lower or candidate_lower in text_lower:
                return candidate
            
            # Fuzzy match
            similarity = SequenceMatcher(None, text_lower, candidate_lower).ratio()
            if similarity >= threshold:
                return candidate
        
        return None

    def extract_exchange(self, text: str) -> Optional[str]:
        """Extract exchange from text"""
        text_lower = text.lower()
        
        for exchange, variations in self.exchange_variations.items():
            if any(var in text_lower for var in variations):
                return exchange
        
        return None

    def extract_crypto(self, text: str) -> Optional[str]:
        """Extract cryptocurrency from text"""
        text_lower = text.lower()
        
        for crypto, variations in self.crypto_variations.items():
            if any(var in text_lower for var in variations):
                return crypto
        
        return None

    def is_filter_request(self, text: str) -> bool:
        """Check if text is requesting filtered symbols"""
        text_lower = text.lower()
        filter_indicators = ["show", "only", "filter", "just", "bitcoin", "ethereum", "symbols"]
        return any(indicator in text_lower for indicator in filter_indicators)

    def extract_filter_crypto(self, text: str) -> Optional[str]:
        """Extract cryptocurrency for filtering"""
        return self.extract_crypto(text)

    def extract_quantity_and_price(self, text: str) -> tuple[Optional[float], Optional[float]]:
        """Extract quantity and price from text"""
        text_lower = text.lower()
        
        # Remove common words that might interfere
        text_clean = text_lower.replace("usdt", "").replace("usd", "").replace("dollars", "").replace("dollar", "")
        
        # Extract numbers
        numbers = re.findall(r'\d+\.?\d*', text_clean)
        
        if len(numbers) >= 2:
            # Assume first number is quantity, second is price
            try:
                quantity = float(numbers[0])
                price = float(numbers[1])
                return quantity, price
            except ValueError:
                pass
        
        elif len(numbers) == 1:
            number = float(numbers[0])
            
            # Check for price indicators
            price_indicators = ["at", "price", "cost", "per", "for", "dollars", "dollar", "usd", "usdt", "us dollars"]
            is_price = any(indicator in text_lower for indicator in price_indicators)
            
            # Check for quantity indicators
            quantity_indicators = ["quantity", "amount", "btc", "eth", "coins", "tokens"]
            is_quantity = any(indicator in text_lower for indicator in quantity_indicators)
            
            if is_price:
                return None, number
            elif is_quantity:
                return number, None
            else:
                # If no clear indicators, assume it's a quantity if it's small (< 1000) or price if large
                if number < 1000:
                    return number, None
                else:
                    return None, number
        
        return None, None

# Initialize smart text processor
smart_processor = SmartTextProcessor()

async def fetch_symbols_with_retry(exchange: str, max_retries: int = 3) -> List[str]:
    """Fetch symbols from exchange with retry logic"""
    for attempt in range(max_retries):
        try:
            symbols = await get_exchange_symbols(exchange)
            if symbols:
                return symbols
        except Exception as e:
            logger.error(f"Error fetching symbols for {exchange} (attempt {attempt + 1}): {str(e)}")
            if attempt == max_retries - 1:
                logger.error(f"Failed to fetch symbols after {max_retries} attempts")
                # Return default symbols as fallback
                return EXCHANGES.get(exchange.lower(), {}).get("symbols", ["BTC-USDT", "ETH-USDT", "XRP-USDT", "LTC-USDT", "ADA-USDT"])
            await asyncio.sleep(1)
    
    # Return default symbols as fallback
    return EXCHANGES.get(exchange.lower(), {}).get("symbols", ["BTC-USDT", "ETH-USDT", "XRP-USDT", "LTC-USDT", "ADA-USDT"])

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Trading Bot API...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
