import React, { useState, useEffect, useRef } from 'react';
import { Send, Search, Paperclip, Smile, MessageCircle, MoreVertical, Check, CheckCheck, AlertCircle, Loader2, ChevronLeft, ChevronRight } from 'lucide-react';
import { whatsappApi, type Message, type Conversation } from '../services/whatsappApi';
import { wsService } from '../services/websocketService';
import { motion, AnimatePresence } from 'framer-motion';

const Conversations: React.FC = () => {
    const [conversations, setConversations] = useState<Conversation[]>([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(0);
    const [limit] = useState(15);
    const [search, setSearch] = useState('');
    const [selectedConvo, setSelectedConvo] = useState<Conversation | null>(null);
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [messagesLoading, setMessagesLoading] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const fetchConvos = async (isSilent = false) => {
        if (!isSilent) setLoading(true);
        try {
            const data = await whatsappApi.getConversations({
                skip: page * limit,
                limit: limit,
                search: search || undefined
            });
            setConversations(data.conversations);
            setTotal(data.total);
        } catch (err) {
            console.error("Failed to fetch conversations", err);
        } finally {
            if (!isSilent) setLoading(false);
        }
    };

    useEffect(() => {
        const timer = setTimeout(() => {
            setPage(0);
            fetchConvos();
        }, search ? 400 : 0);
        return () => clearTimeout(timer);
    }, [search]);

    useEffect(() => {
        fetchConvos();
    }, [page, limit]);

    // Polling for new conversations and messages
    useEffect(() => {
        const interval = setInterval(() => fetchConvos(true), 10000);
        return () => clearInterval(interval);
    }, [page, limit, search]);

    useEffect(() => {
        if (selectedConvo) {
            setMessagesLoading(true);
            whatsappApi.getConversationMessages(selectedConvo.phoneNumber)
                .then(setMessages)
                .finally(() => setMessagesLoading(false));

            // WebSocket listener for messages in the CURRENTLY SELECTED conversation
            const unsubscribe = wsService.subscribe('new_message', (payload) => {
                // Use last 10 digits for matching to handle direct/formatted number variants
                const payloadLast10 = payload.wa_id.replace(/\D/g, '').slice(-10);
                const selectedLast10 = selectedConvo.phoneNumber.replace(/\D/g, '').slice(-10);
                
                if (payloadLast10 === selectedLast10) {
                    const newMsg: Message = {
                        id: payload.data.id,
                        text: payload.data.text,
                        sender: payload.data.sender,
                        timestamp: payload.data.timestamp,
                        type: payload.data.type || 'text',
                        deliveryStatus: 'sent'
                    };
                    setMessages(prev => {
                        if (prev.find(m => m.id === newMsg.id)) return prev;
                        return [...prev, newMsg];
                    });
                }
            });
            return () => unsubscribe();
        } else {
            setMessages([]);
        }
    }, [selectedConvo?.sessionId]);

    // WebSocket listener for updating the SIDEBAR list
    useEffect(() => {
        const unsubscribe = wsService.subscribe('new_message', (payload) => {
            console.log("[WS] Sidebar update triggered:", payload);
            setConversations(prev => {
                const waIdClean = payload.wa_id.replace(/\D/g, '').slice(-10); // Match last 10 digits
                const index = prev.findIndex(c => c.phoneNumber.replace(/\D/g, '').slice(-10) === waIdClean);
                
                if (index !== -1) {
                    const updated = [...prev];
                    const convo = { ...updated[index] };
                    convo.lastMessage = payload.data.text;
                    convo.timestamp = payload.data.timestamp;
                    convo.contactName = payload.data.contactName || convo.contactName;
                    
                    updated.splice(index, 1);
                    return [convo, ...updated];
                } else {
                    fetchConvos(true);
                    return prev;
                }
            });
        });
        return () => unsubscribe();
    }, []);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const handleSend = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || !selectedConvo) return;

        const text = input;
        setInput('');

        const tempMsg: Message = {
            id: 'temp-' + Date.now(),
            text,
            sender: 'agent',
            timestamp: new Date().toISOString(),
            type: 'text',
            deliveryStatus: 'sent'
        };
        setMessages(prev => [...prev, tempMsg]);

        try {
            await whatsappApi.sendMessage(selectedConvo.phoneNumber, text);
            // Refresh messages after send
            const latest = await whatsappApi.getConversationMessages(selectedConvo.phoneNumber);
            setMessages(latest);
        } catch (err) {
            console.error("Failed to send message", err);
        }
    };

    return (
        <div className="flex h-[calc(100vh-100px)] bg-white dark:bg-slate-900/50 backdrop-blur-xl rounded-[2.5rem] border border-slate-200 dark:border-white/5 overflow-hidden shadow-sm dark:shadow-2xl transition-all duration-500">
            {/* Sidebar */}
            <div className="w-96 border-r border-slate-100 dark:border-white/5 flex flex-col bg-slate-50 dark:bg-[#111827]/40 transition-colors duration-500">
                <div className="p-6 border-b border-slate-100 dark:border-white/5 space-y-4">
                    <h2 className="text-xl font-black text-slate-800 dark:text-white">Conversations</h2>
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500 w-4 h-4" />
                        <input
                            type="text"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            placeholder="Search by ID..."
                            className="w-full bg-white dark:bg-white/5 border border-slate-200 dark:border-white/10 rounded-2xl pl-10 pr-4 py-2 text-sm text-slate-800 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none transition-all"
                        />
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto relative">
                    {loading && (
                        <div className="absolute inset-0 bg-white/50 dark:bg-black/20 backdrop-blur-[2px] z-10 flex items-center justify-center">
                            <Loader2 className="animate-spin text-emerald-500" size={24} />
                        </div>
                    )}
                    {conversations.map((convo) => (
                        <div
                            key={convo.sessionId}
                            onClick={() => setSelectedConvo(convo)}
                            className={`p-5 border-b border-slate-100 dark:border-white/5 cursor-pointer transition-all 
                                ${selectedConvo?.sessionId === convo.sessionId
                                    ? 'bg-emerald-50 dark:bg-emerald-500/10 border-l-4 border-l-emerald-500'
                                    : 'hover:bg-slate-100 dark:hover:bg-white/5'}`}
                        >
                            <div className="flex justify-between items-start mb-1">
                                <h4 className="font-bold text-sm text-slate-700 dark:text-slate-200 truncate pr-2 font-mono">
                                    {convo.contactName || `+${convo.phoneNumber}`}
                                </h4>
                                <span className="text-[9px] text-slate-400 font-bold uppercase shrink-0">
                                    {new Date(convo.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                </span>
                            </div>
                            {convo.contactName && (
                                <p className="text-[10px] text-slate-400 font-bold mb-1">+{convo.phoneNumber}</p>
                            )}
                            <p className="text-xs text-slate-500 truncate leading-relaxed">
                                {convo.lastMessage || 'No messages yet'}
                            </p>
                        </div>
                    ))}
                    {!loading && conversations.length === 0 && (
                        <div className="p-10 text-center space-y-2 opacity-40">
                            <MessageCircle className="mx-auto" size={32} />
                            <p className="text-sm font-medium">No conversations found</p>
                        </div>
                    )}
                </div>

                {total > limit && (
                    <div className="p-4 border-t border-slate-100 dark:border-white/5 flex justify-between items-center bg-white/30 dark:bg-white/5">
                        <button
                            disabled={page === 0}
                            onClick={() => setPage(p => p - 1)}
                            className="p-1.5 rounded-lg border border-slate-200 dark:border-white/10 disabled:opacity-30 hover:bg-white dark:hover:bg-white/5 transition-all"
                        >
                            <ChevronLeft size={16} />
                        </button>
                        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                            Page {page + 1}
                        </span>
                        <button
                            disabled={(page + 1) * limit >= total}
                            onClick={() => setPage(p => p + 1)}
                            className="p-1.5 rounded-lg border border-slate-200 dark:border-white/10 disabled:opacity-30 hover:bg-white dark:hover:bg-white/5 transition-all"
                        >
                            <ChevronRight size={16} />
                        </button>
                    </div>
                )}
            </div>

            {/* Chat Area */}
            <div className="flex-1 flex flex-col bg-slate-50 dark:bg-[#070b14]/30 relative transition-colors duration-500">
                {selectedConvo ? (
                    <>
                        <div className="h-20 border-b border-slate-100 dark:border-white/5 px-8 flex items-center justify-between bg-white dark:bg-[#111827]/20 transition-colors duration-500">
                            <div className="flex items-center gap-4">
                                <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-emerald-400 to-cyan-400 flex items-center justify-center text-white font-black shadow-lg shadow-emerald-500/20">
                                    {selectedConvo.phoneNumber.slice(-1)}
                                </div>
                                <div>
                                    <h3 className="font-bold text-slate-800 dark:text-slate-100 text-lg">
                                        {selectedConvo.contactName || `+${selectedConvo.phoneNumber}`}
                                    </h3>
                                    <div className="flex items-center gap-2">
                                        {selectedConvo.contactName && <span className="text-[10px] text-slate-400 font-bold">+{selectedConvo.phoneNumber}</span>}
                                        {selectedConvo.isActive ? (
                                            <span className="text-[10px] text-emerald-500 font-black uppercase tracking-widest flex items-center gap-1.5">
                                                <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                                                Session Active
                                            </span>
                                        ) : (
                                            <span className="text-[10px] text-slate-400 font-black uppercase tracking-widest flex items-center gap-1.5">
                                                <div className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                                                Session Expired
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                <button className="p-2.5 rounded-xl hover:bg-slate-100 dark:hover:bg-white/5 transition-colors text-slate-400 hover:text-slate-600 dark:hover:text-white">
                                    <MoreVertical size={20} />
                                </button>
                            </div>
                        </div>

                        <div className="flex-1 overflow-y-auto p-8 space-y-6 scrollbar-hide">
                            <AnimatePresence initial={false}>
                                {messages.map((msg) => {
                                    const isAgent = msg.sender === 'agent';
                                    return (
                                        <motion.div
                                            key={msg.id}
                                            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                                            className={`flex ${isAgent ? 'justify-end' : 'justify-start'}`}
                                        >
                                            <div className={`max-w-[75%] p-4 rounded-3xl relative shadow-sm group
                                                ${isAgent
                                                    ? 'bg-emerald-500 dark:bg-emerald-600 text-white rounded-tr-none shadow-emerald-500/20'
                                                    : 'bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 rounded-tl-none border border-slate-200 dark:border-white/5'}`}>
                                                <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.text}</p>
                                                <div className="flex items-center justify-end gap-1.5 mt-2 opacity-60 group-hover:opacity-100 transition-opacity">
                                                    <span className="text-[9px] font-bold uppercase tracking-tighter">
                                                        {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                                    </span>
                                                    {isAgent && (
                                                        msg.deliveryStatus === 'read' ? <CheckCheck size={12} className="text-cyan-200" /> :
                                                            msg.deliveryStatus === 'delivered' ? <CheckCheck size={12} /> :
                                                                msg.deliveryStatus === 'failed' ? <AlertCircle size={12} className="text-rose-300" /> :
                                                                    <Check size={12} />
                                                    )}
                                                </div>
                                            </div>
                                        </motion.div>
                                    );
                                })}
                            </AnimatePresence>
                            <div ref={messagesEndRef} />
                        </div>

                        <form onSubmit={handleSend} className="p-8 bg-white dark:bg-[#111827]/40 border-t border-slate-100 dark:border-white/5 flex items-center gap-4 transition-all duration-500 shadow-[0_-10px_20px_rgba(0,0,0,0.02)]">
                            <div className="flex gap-3 text-slate-400">
                                <button type="button" className="p-2 hover:bg-slate-100 dark:hover:bg-white/5 rounded-xl transition-colors hover:text-emerald-500"><Smile size={22} /></button>
                                <button type="button" className="p-2 hover:bg-slate-100 dark:hover:bg-white/5 rounded-xl transition-colors hover:text-emerald-500"><Paperclip size={22} /></button>
                            </div>
                            <input
                                type="text"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                placeholder="Write a message..."
                                className="flex-1 bg-slate-100 dark:bg-white/5 border border-slate-100 dark:border-white/10 rounded-[1.5rem] px-6 py-3.5 text-sm text-slate-800 dark:text-slate-100 placeholder-slate-400 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none transition-all shadow-inner"
                            />
                            <button
                                type="submit"
                                disabled={!input.trim()}
                                className="w-14 h-14 bg-gradient-to-br from-emerald-500 to-cyan-500 hover:from-emerald-600 hover:to-cyan-600 text-white rounded-[1.5rem] flex items-center justify-center shadow-xl shadow-emerald-500/30 transition-all active:scale-90 disabled:opacity-50 disabled:active:scale-100"
                            >
                                <Send size={22} className="ml-0.5" />
                            </button>
                        </form>
                    </>
                ) : (
                    <div className="flex-1 flex flex-col items-center justify-center text-slate-400 space-y-6">
                        <div className="w-24 h-24 rounded-[2.5rem] bg-white dark:bg-white/5 border border-slate-100 dark:border-white/5 flex items-center justify-center shadow-2xl transition-all duration-500 group hover:scale-110">
                            <MessageCircle size={48} className="opacity-10 group-hover:opacity-30 group-hover:text-emerald-500 transition-all" />
                        </div>
                        <div className="text-center space-y-1">
                            <p className="text-xl font-black text-slate-400 dark:text-slate-500 opacity-60">Adcom Messenger</p>
                            <p className="text-sm font-medium opacity-30">Select a real-time conversation to begin chatting</p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default Conversations;
