import React, { useState, useEffect, useRef, useCallback } from 'react';
import './App.css';

const API_BASE = 'http://localhost:8000';

const fallbackMarkets = [
  { symbol: 'BTC-USDT', name: 'Bitcoin', exchange: 'OKX', price: 47250.25, change: '+2.4%', trend: 'Bullish', source: 'Demo' },
  { symbol: 'ETH-USDT', name: 'Ethereum', exchange: 'OKX', price: 3150.8, change: '+1.8%', trend: 'Rising', source: 'Demo' },
  { symbol: 'XRP-USDT', name: 'Ripple', exchange: 'Bybit', price: 0.58, change: '-0.7%', trend: 'Cooling', source: 'Demo' },
  { symbol: 'BTC-PERPETUAL', name: 'BTC Perpetual', exchange: 'Deribit', price: 47310.5, change: '+1.2%', trend: 'Active', source: 'Demo' },
  { symbol: 'ETH-BTC', name: 'ETH / BTC', exchange: 'Binance', price: 0.066, change: '+0.4%', trend: 'Stable', source: 'Demo' },
  { symbol: 'DOT-USDT', name: 'Polkadot', exchange: 'Bybit', price: 7.32, change: '+3.1%', trend: 'Momentum', source: 'Demo' }
];

const exchanges = [
  {
    name: 'OKX',
    focus: 'Spot crypto pairs',
    symbols: ['BTC-USDT', 'ETH-USDT', 'XRP-USDT', 'LTC-USDT', 'ADA-USDT']
  },
  {
    name: 'Bybit',
    focus: 'Spot and active alt markets',
    symbols: ['BTC-USDT', 'ETH-USDT', 'DOT-USDT', 'DOGE-USDT', 'CHZ-USDT']
  },
  {
    name: 'Deribit',
    focus: 'Perpetual and dated instruments',
    symbols: ['BTC-PERPETUAL', 'ETH-PERPETUAL', 'BTC-30JUN23']
  },
  {
    name: 'Binance',
    focus: 'BTC quoted trading pairs',
    symbols: ['ETH-BTC', 'LTC-BTC', 'BNB-BTC', 'NEO-BTC']
  }
];

const orderSteps = [
  'Choose an exchange',
  'Select a symbol',
  'Say quantity and price',
  'Confirm or correct the order'
];

const formatPrice = (price) => {
  const number = Number(price);
  if (!Number.isFinite(number)) return 'Loading';
  if (number < 1) return number.toLocaleString(undefined, { minimumFractionDigits: 4, maximumFractionDigits: 6 });
  return number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

function App() {
  const [sessionId, setSessionId] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [transcript, setTranscript] = useState([]);
  const [error, setError] = useState(null);
  const [isListening, setIsListening] = useState(false);
  const [voiceInput, setVoiceInput] = useState('');
  const [recognition, setRecognition] = useState(null);
  const [isCallActive, setIsCallActive] = useState(false);
  const [userName, setUserName] = useState('Trader');
  const [markets, setMarkets] = useState(fallbackMarkets);
  const [marketsUpdatedAt, setMarketsUpdatedAt] = useState('Demo snapshot');
  const [isMarketLoading, setIsMarketLoading] = useState(false);
  const transcriptRef = useRef(null);
  const consoleRef = useRef(null);
  const sessionIdRef = useRef(null);
  const wsRef = useRef(null);
  const connectingRef = useRef(false);

  useEffect(() => {
    let isMounted = true;

    const loadMarkets = async () => {
      setIsMarketLoading(true);
      try {
        const response = await fetch(`${API_BASE}/market_snapshot`);
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        if (isMounted && Array.isArray(data.markets) && data.markets.length > 0) {
          setMarkets(data.markets);
          setMarketsUpdatedAt(`Updated ${new Date(data.updated_at).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit'
          })}`);
        }
      } catch (marketError) {
        if (isMounted) {
          setMarkets(fallbackMarkets);
          setMarketsUpdatedAt('Demo snapshot');
        }
      } finally {
        if (isMounted) {
          setIsMarketLoading(false);
        }
      }
    };

    loadMarkets();
    return () => {
      isMounted = false;
    };
  }, []);

  const handleVoiceInput = useCallback(async (text) => {
    const currentSessionId = sessionId || sessionIdRef.current;

    if (!currentSessionId || !text.trim()) {
      return;
    }

    setTranscript(prev => [
      ...prev,
      {
        id: Date.now(),
        type: 'user',
        content: text,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }
    ]);

    try {
      const response = await fetch(`${API_BASE}/bland_webhook/${currentSessionId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          from_: '+1234567890',
          to: '+0987654321',
          text,
          direction: 'inbound'
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      setVoiceInput('');
    } catch (voiceError) {
      setError(`Failed to send voice input: ${voiceError.message}`);
    }
  }, [sessionId]);

  useEffect(() => {
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      const recognitionInstance = new SpeechRecognition();

      recognitionInstance.continuous = true;
      recognitionInstance.interimResults = true;
      recognitionInstance.lang = 'en-US';

      recognitionInstance.onstart = () => {
        setIsListening(true);
      };

      recognitionInstance.onresult = (event) => {
        let interimTranscript = '';
        let finalTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; i += 1) {
          const spokenText = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            finalTranscript += spokenText;
          } else {
            interimTranscript += spokenText;
          }
        }

        if (finalTranscript) {
          setVoiceInput(finalTranscript);
          handleVoiceInput(finalTranscript);
        } else if (interimTranscript) {
          setVoiceInput(interimTranscript);
        }
      };

      recognitionInstance.onerror = (event) => {
        setIsListening(false);
        setError(`Speech recognition error: ${event.error}`);
      };

      recognitionInstance.onend = () => {
        setIsListening(false);
      };

      setRecognition(recognitionInstance);
    } else {
      setError('Speech recognition is not supported in this browser');
    }
  }, [handleVoiceInput]);

  useEffect(() => {
    if (sessionId && !connectingRef.current) {
      connectingRef.current = true;

      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }

      const ws = new WebSocket(`ws://localhost:8000/ws/${sessionId}`);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        connectingRef.current = false;
        setError(null);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.type === 'transcript_update') {
            const newMessage = {
              id: Date.now(),
              type: data.speaker === 'user' ? 'user' : 'bot',
              content: data.text,
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            };
            setTranscript(prev => [...prev, newMessage]);
          } else if (data.type === 'transcript' && data.data && Array.isArray(data.data)) {
            data.data.forEach(item => {
              const newMessage = {
                id: Date.now() + Math.random(),
                type: item.speaker === 'user' ? 'user' : 'bot',
                content: item.text || item.content || item.message,
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
              };
              setTranscript(prev => [...prev, newMessage]);
            });
          }
        } catch (messageError) {
          setError(`Could not read WebSocket message: ${messageError.message}`);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        connectingRef.current = false;
        wsRef.current = null;
      };

      ws.onerror = () => {
        setError('WebSocket connection error');
        setIsConnected(false);
        connectingRef.current = false;
        wsRef.current = null;
      };

      return () => {
        connectingRef.current = false;
        if (wsRef.current) {
          wsRef.current.close();
          wsRef.current = null;
        }
      };
    }

    return undefined;
  }, [sessionId]);

  const scrollToConsole = useCallback(() => {
    if (consoleRef.current) {
      setTimeout(() => {
        consoleRef.current.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        });
      }, 100);
    }
  }, []);

  const startCall = async () => {
    try {
      setError(null);
      const response = await fetch(`${API_BASE}/start_call`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          user_name: userName
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      sessionIdRef.current = data.session_id;
      setSessionId(data.session_id);
      setIsCallActive(true);
      scrollToConsole();
    } catch (startError) {
      setError(`Failed to start conversation: ${startError.message}`);
    }
  };

  const endCall = async () => {
    try {
      if (recognition && isListening) {
        recognition.stop();
      }

      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }

      setIsConnected(false);
      connectingRef.current = false;

      if (sessionId) {
        try {
          const response = await fetch(`${API_BASE}/end_call/${sessionId}`, {
            method: 'POST'
          });

          if (!response.ok) {
            console.warn(`Backend end conversation failed: ${response.status}`);
          }
        } catch (endRequestError) {
          console.warn('Error calling backend end_call:', endRequestError);
        }
      }

      setSessionId(null);
      sessionIdRef.current = null;
      setIsCallActive(false);
      setTranscript([]);
      setError(null);
      setVoiceInput('');
    } catch (endError) {
      setError(`Failed to end conversation: ${endError.message}`);
    }
  };

  const toggleListening = () => {
    if (!recognition) return;

    if (isListening) {
      recognition.stop();
    } else {
      recognition.start();
    }
  };

  return (
    <div className="App">
      <header className="hero-section">
        <nav className="topbar">
          <div className="brand-mark">
            <span className="brand-symbol">GQ</span>
            <span>GOQ Trading Voice Desk</span>
          </div>
          <a className="nav-pill" href="#voice-console">Open Voice Desk</a>
        </nav>

        <div className="hero-grid">
          <section className="hero-copy">
            <div className="eyebrow">Voice operated OTC digital asset trading</div>
            <h1>Trade across OKX, Bybit, Deribit, and Binance with a guided voice workflow.</h1>
            <p>
              Start a conversation, choose a venue, pick a crypto symbol, set quantity and price,
              then confirm your order through the trading assistant.
            </p>

            <div className="hero-actions">
              <button className="primary-action" type="button" onClick={scrollToConsole}>
                Start from the Voice Desk
              </button>
              <a className="secondary-action" href="#markets">View Market Cards</a>
            </div>

            <div className="hero-stats" aria-label="Trading coverage">
              <div>
                <strong>4</strong>
                <span>venues</span>
              </div>
              <div>
                <strong>30+</strong>
                <span>listed pairs</span>
              </div>
              <div>
                <strong>Live</strong>
                <span>conversation state</span>
              </div>
            </div>
          </section>

          <section className="hero-panel" aria-label="Trading assistant preview">
            <div className="panel-header">
              <span>Desk Preview</span>
              <span className="live-chip">Ready</span>
            </div>
            <div className="quote-stack">
              <div className="quote-card featured">
                <span>Selected flow</span>
                <strong>Exchange -> Symbol -> Quantity -> Price -> Confirm</strong>
              </div>
              {orderSteps.map((step, index) => (
                <div className="quote-card" key={step}>
                  <span>Step {index + 1}</span>
                  <strong>{step}</strong>
                </div>
              ))}
            </div>
          </section>
        </div>
      </header>

      <main>
        <section className="section-shell" id="markets">
          <div className="section-heading">
            <div>
              <span className="eyebrow">Market trend</span>
              <h2>Current crypto rates offered by the desk</h2>
            </div>
            <span className="update-badge">{isMarketLoading ? 'Refreshing rates' : marketsUpdatedAt}</span>
          </div>

          <div className="market-grid">
            {markets.map((market) => (
              <article className="market-card" key={`${market.exchange}-${market.symbol}`}>
                <div className="market-card-top">
                  <span className="asset-symbol">{market.symbol}</span>
                  <span className={`trend-pill ${String(market.change).startsWith('-') ? 'down' : 'up'}`}>
                    {market.change}
                  </span>
                </div>
                <h3>{market.name}</h3>
                <p>{market.exchange}</p>
                <strong>${formatPrice(market.price)}</strong>
                <div className="mini-chart" aria-hidden="true">
                  <span></span>
                  <span></span>
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                <div className="market-meta">
                  <span>{market.trend}</span>
                  <span>{market.source || 'Live/fallback'}</span>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="section-shell platform-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">Supported platforms</span>
              <h2>Pick your venue by voice</h2>
            </div>
          </div>

          <div className="exchange-grid">
            {exchanges.map((exchange) => (
              <article className="exchange-card" key={exchange.name}>
                <div className="exchange-avatar">{exchange.name.slice(0, 2)}</div>
                <h3>{exchange.name}</h3>
                <p>{exchange.focus}</p>
                <div className="symbol-cloud">
                  {exchange.symbols.map((symbol) => (
                    <span key={symbol}>{symbol}</span>
                  ))}
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="voice-shell" id="voice-console" ref={consoleRef}>
          <div className="voice-heading">
            <div>
              <span className="eyebrow">Voice console</span>
              <h2>Run the trading conversation</h2>
            </div>
            {sessionId && <span className="session-chip">Session {sessionId.slice(0, 8)}</span>}
          </div>

          <div className="console-grid">
            <aside className="control-card">
              <div className="input-group">
                <label htmlFor="userName">Username</label>
                <input
                  type="text"
                  id="userName"
                  value={userName}
                  onChange={(e) => setUserName(e.target.value)}
                  placeholder="Enter your name"
                  disabled={isCallActive}
                />
              </div>

              <div className="call-controls">
                <button
                  className="start-btn"
                  type="button"
                  onClick={startCall}
                  disabled={isCallActive}
                >
                  Start Conversation
                </button>
                <button
                  className="end-btn"
                  type="button"
                  onClick={endCall}
                  disabled={!isCallActive}
                >
                  End Conversation
                </button>
              </div>

              <div className="status-card">
                <div className="status-row">
                  <span className={`status-dot ${isConnected ? 'connected' : 'disconnected'}`}></span>
                  <span>WebSocket</span>
                  <strong>{isConnected ? 'Connected' : 'Disconnected'}</strong>
                </div>
                <div className="status-row">
                  <span className={`status-dot ${isCallActive ? 'connected' : 'disconnected'}`}></span>
                  <span>Conversation</span>
                  <strong>{isCallActive ? 'Active' : 'Inactive'}</strong>
                </div>
                <div className="status-row">
                  <span className={`status-dot ${isListening ? 'connected pulse' : 'idle'}`}></span>
                  <span>Microphone</span>
                  <strong>{isListening ? 'Listening' : 'Ready'}</strong>
                </div>
              </div>

              {isCallActive && (
                <button
                  className={`mic-btn ${isListening ? 'listening' : ''}`}
                  type="button"
                  onClick={toggleListening}
                  disabled={!isCallActive}
                >
                  {isListening ? 'Stop Listening' : 'Start Listening'}
                </button>
              )}

              {error && <div className="error-message">{error}</div>}

              <div className="order-card">
                <h3>Order path</h3>
                {orderSteps.map((step, index) => (
                  <div className="order-step" key={step}>
                    <span>{index + 1}</span>
                    <p>{step}</p>
                  </div>
                ))}
              </div>
            </aside>

            <section className="transcript-card" ref={transcriptRef}>
              <div className="transcript-header">
                <div>
                  <span className="eyebrow">Live transcript</span>
                  <h2>Conversation Transcript</h2>
                </div>
                <span className="message-count">{transcript.length} messages</span>
              </div>

              <div className="transcript-container">
                {transcript.length === 0 ? (
                  <div className="empty-transcript">
                    <h3>{isCallActive ? 'The desk is ready.' : 'Start the conversation to open the desk.'}</h3>
                    <p>
                      {isCallActive
                        ? 'Say an exchange such as OKX, Bybit, Deribit, or Binance.'
                        : 'Your assistant will guide exchange, symbol, quantity, price, and confirmation here.'}
                    </p>
                  </div>
                ) : (
                  transcript.map((message) => (
                    <div key={message.id} className={`message ${message.type}`}>
                      <div className="message-label">
                        <span>{message.type === 'user' ? userName || 'You' : 'Trading Bot'}</span>
                        <time>{message.timestamp}</time>
                      </div>
                      <div className="message-content">{message.content}</div>
                    </div>
                  ))
                )}

                {voiceInput && (
                  <div className="voice-input-display">
                    Hearing: {voiceInput}
                  </div>
                )}
              </div>
            </section>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
