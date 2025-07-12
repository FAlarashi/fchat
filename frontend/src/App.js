import React, { useState, useEffect, useRef } from 'react';
import './App.css';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const WS_URL = BACKEND_URL.replace('https://', 'wss://').replace('http://', 'ws://');

function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [username, setUsername] = useState('');
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [onlineUsers, setOnlineUsers] = useState([]);
  const [ws, setWs] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [registering, setRegistering] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Load messages on mount
  useEffect(() => {
    loadMessages();
  }, []);

  const loadMessages = async () => {
    try {
      const response = await axios.get(`${API}/messages`);
      setMessages(response.data);
    } catch (error) {
      console.error('Failed to load messages:', error);
    }
  };

  const handleRegister = async () => {
    if (!username.trim()) return;
    
    setRegistering(true);
    try {
      const response = await axios.post(`${API}/register`, {
        username: username.trim()
      });
      
      const user = response.data;
      setCurrentUser(user);
      connectWebSocket(user.id, user.username);
    } catch (error) {
      alert(error.response?.data?.detail || 'Registration failed');
    } finally {
      setRegistering(false);
    }
  };

  const connectWebSocket = (userId, username) => {
    const websocket = new WebSocket(`${WS_URL}/api/ws/${userId}?username=${encodeURIComponent(username)}`);
    
    websocket.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
    };
    
    websocket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'message') {
        setMessages(prev => [...prev, {
          id: data.id,
          user_id: data.user_id,
          username: data.username,
          content: data.content,
          timestamp: data.timestamp
        }]);
      } else if (data.type === 'users_online') {
        setOnlineUsers(data.users);
      }
    };
    
    websocket.onclose = () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
    };
    
    websocket.onerror = (error) => {
      console.error('WebSocket error:', error);
      setIsConnected(false);
    };
    
    setWs(websocket);
  };

  const sendMessage = () => {
    if (!newMessage.trim() || !ws || !isConnected) return;
    
    ws.send(JSON.stringify({
      type: 'message',
      content: newMessage.trim()
    }));
    
    setNewMessage('');
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const formatTime = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString('en-US', { 
      hour12: true, 
      hour: 'numeric', 
      minute: '2-digit' 
    });
  };

  // Login Screen
  if (!currentUser) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center p-4">
        <div className="bg-gray-800 rounded-lg shadow-xl p-8 w-full max-w-md">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-white mb-2">SecureChat</h1>
            <p className="text-gray-400">Enter the secure messaging world</p>
          </div>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Choose your username
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleRegister()}
                className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
                placeholder="Enter username..."
                disabled={registering}
              />
            </div>
            
            <button
              onClick={handleRegister}
              disabled={!username.trim() || registering}
              className="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-medium py-3 px-4 rounded-lg transition duration-200"
            >
              {registering ? 'Joining...' : 'Join Chat'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Chat Interface
  return (
    <div className="h-screen bg-gray-900 flex">
      {/* Sidebar */}
      <div className="w-80 bg-gray-800 border-r border-gray-700 flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-gray-700">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-green-600 rounded-full flex items-center justify-center">
              <span className="text-white font-bold text-lg">
                {currentUser.username.charAt(0).toUpperCase()}
              </span>
            </div>
            <div>
              <h2 className="text-white font-semibold">{currentUser.username}</h2>
              <div className="flex items-center space-x-1">
                <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
                <span className="text-xs text-gray-400">
                  {isConnected ? 'Connected' : 'Disconnected'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Online Users */}
        <div className="flex-1 overflow-y-auto">
          <div className="p-4">
            <h3 className="text-gray-300 font-medium mb-3">
              Online Users ({onlineUsers.length})
            </h3>
            <div className="space-y-2">
              {onlineUsers.map((user) => (
                <div key={user.id} className="flex items-center space-x-3 p-2 rounded-lg hover:bg-gray-700">
                  <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center">
                    <span className="text-white text-sm font-medium">
                      {user.username.charAt(0).toUpperCase()}
                    </span>
                  </div>
                  <div>
                    <p className="text-white text-sm">{user.username}</p>
                    <div className="flex items-center space-x-1">
                      <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                      <span className="text-xs text-gray-400">Online</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Chat Header */}
        <div className="p-4 bg-gray-800 border-b border-gray-700">
          <h1 className="text-xl font-semibold text-white">SecureChat</h1>
          <p className="text-sm text-gray-400">End-to-end encrypted messaging</p>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.user_id === currentUser.id ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                  message.user_id === currentUser.id
                    ? 'bg-green-600 text-white'
                    : 'bg-gray-700 text-white'
                }`}
              >
                {message.user_id !== currentUser.id && (
                  <p className="text-xs text-gray-300 mb-1">{message.username}</p>
                )}
                <p className="break-words">{message.content}</p>
                <p className="text-xs mt-1 opacity-70">
                  {formatTime(message.timestamp)}
                </p>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Message Input */}
        <div className="p-4 bg-gray-800 border-t border-gray-700">
          <div className="flex space-x-3">
            <input
              type="text"
              value={newMessage}
              onChange={(e) => setNewMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              className="flex-1 px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
              placeholder="Type a message..."
              disabled={!isConnected}
            />
            <button
              onClick={sendMessage}
              disabled={!newMessage.trim() || !isConnected}
              className="bg-green-600 hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white px-6 py-3 rounded-lg transition duration-200"
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;