import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, X, Loader2 } from 'lucide-react';
import { C } from '../theme';
import { factCheck } from '../services/jobService';

const FactCheckerBot = ({ candidateId, candidateName, onClose }) => {
  const [messages, setMessages] = useState([
    { role: 'assistant', text: `Hi! I'm your AI Assistant. What claim would you like me to verify about ${candidateName}?` }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  const handleSend = async () => {
    if (!inputValue.trim() || isTyping) return;
    
    // Add user message
    const userMsg = inputValue.trim();
    setMessages(prev => [...prev, { role: 'user', text: userMsg }]);
    setInputValue('');
    setIsTyping(true);

    try {
      const data = await factCheck(candidateId, userMsg, candidateName);
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        text: data.response,
        condition: data.condition,
      }]);
    } catch (err) {
      console.error('Fact check failed:', err);
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        text: 'Sorry, I encountered an error while verifying that claim. Please try again.' 
      }]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="flex-1 w-full h-full bg-white flex flex-col z-50">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between" style={{ background: C.primary }}>
        <div className="flex items-center gap-2 text-white">
          <Bot className="h-4 w-4" />
          <h3 className="text-sm font-bold">AI Fact Checker</h3>
        </div>
        <button onClick={onClose} className="p-1 hover:bg-white/20 rounded-md transition-colors text-indigo-100 hover:text-white">
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'assistant' && (
              <div className="h-6 w-6 rounded-md flex items-center justify-center shrink-0 mt-1" style={{ background: C.cyan, color: 'white' }}>
                <Bot className="h-3.5 w-3.5" />
              </div>
            )}
            <div 
              className={`p-3 rounded-xl text-sm leading-relaxed max-w-[85%] ${
                msg.role === 'user' 
                  ? 'bg-indigo-600 text-white rounded-tr-none' 
                  : 'bg-white border border-slate-200 text-slate-700 rounded-tl-none shadow-sm'
              }`}
              style={{ whiteSpace: 'pre-wrap' }}
            >
              {msg.text}
            </div>
          </div>
        ))}
        {isTyping && (
          <div className="flex gap-2 justify-start">
            <div className="h-6 w-6 rounded-md flex items-center justify-center shrink-0 mt-1" style={{ background: C.cyan, color: 'white' }}>
              <Bot className="h-3.5 w-3.5" />
            </div>
            <div className="bg-white border border-slate-200 p-3 rounded-xl rounded-tl-none shadow-sm flex items-center gap-2">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-400" />
              <span className="text-xs text-slate-500 font-medium tracking-wide">Verifying claim...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-3 bg-white border-t border-slate-100 flex items-center gap-2">
        <input 
          type="text" 
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Ask, e.g. 'Does he know NextJS?'"
          className="flex-1 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-200 transition-all text-slate-700 placeholder:text-slate-400"
        />
        <button 
          onClick={handleSend}
          disabled={!inputValue.trim() || isTyping}
          className="h-9 w-9 rounded-lg flex items-center justify-center shrink-0 transition-colors disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-90"
          style={{ background: C.primary, color: 'white' }}
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
};

export default FactCheckerBot;
