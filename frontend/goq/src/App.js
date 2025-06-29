import React, { useState, useEffect, useRef, useCallback } from 'react';
import './App.css';

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
  const transcriptRef = useRef(null);
  const sessionIdRef = useRef(null);
  const wsRef = useRef(null);
  const connectingRef = useRef(false);

  const handleVoiceInput = useCallback(async (text) => {
    console.log('handleVoiceInput called with:', text);
    console.log('Current sessionId state:', sessionId);
    console.log('Current sessionIdRef.current:', sessionIdRef.current);
    
    // Use sessionIdRef.current as fallback if sessionId state is null
    const currentSessionId = sessionId || sessionIdRef.current;
    console.log('Using sessionId:', currentSessionId);
    
    if (!currentSessionId || !text.trim()) {
      console.log('Early return - sessionId:', currentSessionId, 'text:', text);
      return;
    }
    
    // Add user message to transcript immediately when voice input is detected
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
      console.log('Sending voice input to backend:', text);
      console.log('Request URL:', `http://localhost:8000/bland_webhook/${currentSessionId}`);
      
      const requestBody = {
        from_: '+1234567890',
        to: '+0987654321',
        text: text,
        direction: 'inbound'
      };
      console.log('Request body:', requestBody);
      
      const response = await fetch(`http://localhost:8000/bland_webhook/${currentSessionId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      console.log('Response status:', response.status);
      console.log('Response ok:', response.ok);

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      console.log('Voice input processed:', data);
      
      // Clear voice input after sending
      setVoiceInput('');
      
    } catch (error) {
      console.error('Error sending voice input:', error);
      setError(`Failed to send voice input: ${error.message}`);
    }
  }, [sessionId]);

  // Initialize speech recognition
  useEffect(() => {
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      const recognitionInstance = new SpeechRecognition();
      
      recognitionInstance.continuous = true;
      recognitionInstance.interimResults = true;
      recognitionInstance.lang = 'en-US';
      
      recognitionInstance.onstart = () => {
        console.log('Speech recognition started');
        setIsListening(true);
      };
      
      recognitionInstance.onresult = (event) => {
        let interimTranscript = '';
        let finalTranscript = '';
        
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            finalTranscript += transcript;
          } else {
            interimTranscript += transcript;
          }
        }
        
        if (finalTranscript) {
          console.log('Final transcript:', finalTranscript);
          setVoiceInput(finalTranscript);
          handleVoiceInput(finalTranscript);
        } else if (interimTranscript) {
          console.log('Interim transcript:', interimTranscript);
          setVoiceInput(interimTranscript);
        }
      };
      
      recognitionInstance.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        setIsListening(false);
        setError(`Speech recognition error: ${event.error}`);
      };
      
      recognitionInstance.onend = () => {
        console.log('Speech recognition ended');
        setIsListening(false);
      };
      
      setRecognition(recognitionInstance);
    } else {
      setError('Speech recognition not supported in this browser');
    }
  }, [handleVoiceInput]);

  // WebSocket connection
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
        console.log('WebSocket connected');
        setIsConnected(true);
        connectingRef.current = false;
        setError(null);
      };
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('WebSocket message received:', data);
          
          if (data.type === 'transcript_update') {
            console.log('Processing transcript update:', data);
            const newMessage = {
              id: Date.now(),
              type: data.speaker === 'user' ? 'user' : 'bot',
              content: data.text,
              timestamp: new Date().toLocaleTimeString()
            };
            console.log('Adding new message to transcript:', newMessage);
            setTranscript(prev => {
              const updated = [...prev, newMessage];
              console.log('Updated transcript:', updated);
              return updated;
            });
          } else if (data.type === 'transcript' && data.data && Array.isArray(data.data)) {
            console.log('Processing transcript data array:', data.data);
            // Handle the transcript format with data array
            data.data.forEach(item => {
              const newMessage = {
                id: Date.now() + Math.random(), // Ensure unique ID
                type: item.speaker === 'user' ? 'user' : 'bot',
                content: item.text || item.content || item.message,
                timestamp: new Date().toLocaleTimeString()
              };
              console.log('Adding message from data array:', newMessage);
              setTranscript(prev => {
                const updated = [...prev, newMessage];
                console.log('Updated transcript from data array:', updated);
                return updated;
              });
            });
          } else {
            console.log('Received non-transcript message:', data.type);
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };
      
      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setIsConnected(false);
        connectingRef.current = false;
        wsRef.current = null;
      };
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
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
  }, [sessionId]);

  // Scroll to transcript when call starts
  const scrollToTranscript = useCallback(() => {
    if (transcriptRef.current) {
      setTimeout(() => {
        transcriptRef.current.scrollIntoView({ 
          behavior: 'smooth', 
          block: 'start' 
        });
      }, 100);
    }
  }, []);

  const startCall = async () => {
    try {
      setError(null);
      const response = await fetch('http://localhost:8000/start_call', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_name: userName
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      console.log('Call started:', data);
      console.log('Setting sessionId to:', data.session_id);
      
      sessionIdRef.current = data.session_id;
      setSessionId(data.session_id);
      setIsCallActive(true);
      
      console.log('After setting - sessionIdRef.current:', sessionIdRef.current);
      
      // Scroll to transcript when call starts
      scrollToTranscript();
      
    } catch (error) {
      console.error('Error starting call:', error);
      setError(`Failed to start call: ${error.message}`);
    }
  };

  const endCall = async () => {
    try {
      // Stop speech recognition if active
      if (recognition && isListening) {
        recognition.stop();
      }
      
      // Close WebSocket connection
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      
      // Reset connection state
      setIsConnected(false);
      connectingRef.current = false;
      
      // Call backend to end session
      if (sessionId) {
        try {
          const response = await fetch(`http://localhost:8000/end_call/${sessionId}`, {
            method: 'POST',
          });

          if (!response.ok) {
            console.warn(`Backend end call failed: ${response.status}`);
          } else {
            console.log('Call ended successfully');
          }
        } catch (error) {
          console.warn('Error calling backend end_call:', error);
        }
      }
      
      // Reset all state
      setSessionId(null);
      sessionIdRef.current = null;
      setIsCallActive(false);
      setTranscript([]);
      setError(null);
      setVoiceInput('');
      
    } catch (error) {
      console.error('Error ending call:', error);
      setError(`Failed to end call: ${error.message}`);
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
      {console.log('Current transcript state:', transcript)}
      <div className="container">
        <div className="header">
          <h1>Trading Bot</h1>
          <p>Voice-operated OTC Digital Asset Trading Platform</p>
        </div>

        <div className="main-content">
          <div className="user-input-section">
            <div className="input-group">
              <label htmlFor="userName">User Name</label>
              <input
                type="text"
                id="userName"
                value={userName}
                onChange={(e) => setUserName(e.target.value)}
                placeholder="Enter your name"
                style={{ color: '#ffd600', fontWeight: 'bold' }}
              />
            </div>

            <div className="call-controls">
              <button
                className="start-btn"
                onClick={startCall}
                disabled={isCallActive}
              >
                Start Conversation
              </button>
              <button
                className="end-btn"
                onClick={endCall}
                disabled={!isCallActive}
              >
                End Conversation
              </button>
            </div>

            <div className="status-indicators">
              <div className="status-indicator">
                <div className={`status-dot ${isConnected ? 'connected' : 'disconnected'}`}></div>
                WebSocket: {isConnected ? 'Connected' : 'Disconnected'}
              </div>
              <div className="status-indicator">
                <div className={`status-dot ${isCallActive ? 'connected' : 'disconnected'}`}></div>
                Call: {isCallActive ? 'Active' : 'Inactive'}
              </div>
            </div>

            {error && <div className="error-message">{error}</div>}
          </div>

          <div className="transcript-section" ref={transcriptRef}>
            <div className="transcript-header">
              <h2>Conversation Transcript</h2>
              {isCallActive && (
                <div className="voice-controls">
                  <button
                    className={`mic-btn ${isListening ? 'listening' : ''}`}
                    onClick={toggleListening}
                    disabled={!isCallActive}
                  >
                    {isListening ? 'Stop' : 'Listen'}
                  </button>
                  <div className="voice-status">
                    {isListening ? 'Listening...' : 'Ready'}
                  </div>
                </div>
              )}
            </div>

            <div className="transcript-container">
              {transcript.length === 0 ? (
                <div className="empty-transcript">
                  {isCallActive ? 'Start speaking to begin your trading conversation...' : 'Click "Start Conversation" to begin'}
                </div>
              ) : (
                transcript.map((message) => (
                  <div key={message.id} className={`message ${message.type}`}>
                    <div className="message-content">{message.content}</div>
                    <div className="message-timestamp">{message.timestamp}</div>
                  </div>
                ))
              )}
              
              {voiceInput && (
                <div className="voice-input-display">
                  "{voiceInput}"
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
