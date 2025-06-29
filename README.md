# 1. Prerequisites

- Python 3.9 or higher 
- Node.js (v16 or higher) and npm 

# 2. Project Structure

After extracting the project folder, you should see:

    goq/
      backend/
        main.py
        requirements.txt
        .env (you will create this)
      frontend/
        goq/
          package.json
          src/


# 3. Backend Setup (Python FastAPI)

        1. Open a terminal and navigate to the backend folder:
    
        cd path/to/goq/backend

        2. Create and activate a virtual environment:
    
        python3 -m venv venv
        source venv/bin/activate   # On Windows: venv\Scripts\activate

        3. Install dependencies:
    
        pip install --upgrade pip
        pip install -r requirements.txt

        4. Create a `.env` file in the backend folder with your API key:
    
        BLAND_API_KEY=[YOUR_API_KEY]
    


5. Download NLTK data if prompted:
    
        python
        >>> import nltk
        >>> nltk.download('punkt')
        >>> nltk.download('wordnet')
        >>> nltk.download('omw-1.4')
        >>> exit()

6. Start the backend server:
    
        uvicorn main:app --reload
    
    - The backend will be available at: http://localhost:8000

---

# 4. Frontend Setup (React)

        1. Open a new terminal window and navigate to the frontend folder:
    
        cd path/to/goq/frontend/goq

        2. Install Node.js dependencies:
    
        npm install

        3. Start the frontend server:
    
        npm start
    
         - The frontend will open at: http://localhost:3000

---

 5. Using the App

- Open http://localhost:3000 in your browser.
- Click the Start Call button.
- Allow microphone access when prompted.
- Speak your commands (e.g., “Binance”, “Bitcoin”, “Buy 0.1 at 30000”).
- The bot will respond in real-time and guide you through the trading process.


