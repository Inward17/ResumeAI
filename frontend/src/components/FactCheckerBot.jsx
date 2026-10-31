import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, X, Loader2 } from 'lucide-react';
import { factCheck } from '../services/jobService';
import { cn } from '../lib/utils';
import { IconButton } from './common';

const SUGGESTIONS = ['Is their most recent role verified?', 'Do their GitHub projects match the resume?', 'Which resume claims have no supporting evidence?'];

const FactCheckerBot = ({ candidateId, candidateName, onClose }) => {
  const [messages, setMessages] = useState([
    { role: 'assistant', text: `Ask me to check any claim about ${candidateName}. I'll look at the resume and the verification evidence.` },
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  useEffect(() => { inputRef.current?.focus(); }, []);

  const send = async (text) => {
    const userMsg = text.trim();
    if (!userMsg || isTyping) return;
    setMessages((prev) => [...prev, { role: 'user', text: userMsg }]);
    setInputValue('');
    setIsTyping(true);
    try {
      const data = await factCheck(candidateId, userMsg, candidateName);
      setMessages((prev) => [...prev, { role: 'assistant', text: data.response, condition: data.condition }]);
    } catch (err) {
      setMessages((prev) => [...prev, { role: 'assistant', error: true, text: err.message }]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="flex h-full w-full flex-1 flex-col bg-surface">
      <div className="flex h-14 shrink-0 items-center justify-between border-b border-line px-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary-soft">
            <Bot className="h-4 w-4 text-primary-text" aria-hidden="true" />
          </div>
          <div className="leading-tight">
            <h3 className="font-serif text-lg leading-none text-ink">Fact checker</h3>
            <p className="text-xs text-ink-3">{candidateName}</p>
          </div>
        </div>
        <IconButton label="Close fact checker" onClick={onClose}><X aria-hidden="true" /></IconButton>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto bg-canvas p-4" aria-live="polite">
        {messages.map((msg, idx) => (
          <div key={idx} className={cn('flex', msg.role === 'user' ? 'justify-end' : 'justify-start')}>
            <div
              className={cn(
                'max-w-[88%] whitespace-pre-wrap rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed',
                msg.role === 'user' && 'rounded-br-md bg-primary text-white',
                msg.role === 'assistant' && !msg.error && 'rounded-bl-md border border-line bg-surface text-ink-2',
                msg.error && 'rounded-bl-md bg-danger-soft text-danger',
              )}
            >
              {msg.text}
            </div>
          </div>
        ))}
        {messages.length === 1 && !isTyping && (
          <div className="space-y-1.5 pt-1">
            <p className="text-xs text-ink-3">Try asking</p>
            {SUGGESTIONS.map((s) => (
              <button key={s} type="button" onClick={() => send(s)}
                className="block w-full rounded-lg border border-line bg-surface px-3 py-2 text-left text-sm text-ink-2 transition-colors hover:border-primary/40 hover:text-ink">
                {s}
              </button>
            ))}
          </div>
        )}
        {isTyping && (
          <div className="flex justify-start">
            <div className="flex items-center gap-2 rounded-2xl rounded-bl-md border border-line bg-surface px-3.5 py-2.5">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-ink-3" aria-hidden="true" />
              <span className="text-sm text-ink-3">Checking…</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form className="flex shrink-0 items-center gap-2 border-t border-line p-3" onSubmit={(e) => { e.preventDefault(); send(inputValue); }}>
        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="Ask about a claim…"
          aria-label="Claim to verify"
          className="h-10 flex-1 rounded-lg border border-line-strong bg-surface px-3 text-sm text-ink outline-none placeholder:text-ink-3 focus:border-primary focus:ring-2 focus:ring-primary/20"
        />
        <button
          type="submit"
          aria-label="Send"
          disabled={!inputValue.trim() || isTyping}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary text-white transition-colors hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Send className="h-4 w-4" aria-hidden="true" />
        </button>
      </form>
    </div>
  );
};

export default FactCheckerBot;
