import React, { useState, useEffect, useRef } from 'react';
import { Send, User, Clock, CheckCheck, Paperclip, Image as ImageIcon, FileText, Search, MoreVertical, ShieldCheck, Loader2, MessageSquare } from 'lucide-react';
import { whatsappApi, type Conversation, type Message, type Campaign } from '../services/whatsappApi';
import { wsService } from '../services/websocketService';
import { Megaphone, FilterX } from 'lucide-react';

const Chat: React.FC = () => {
    const [conversations, setConversations] = useState<Conversation[]>([]);
    const [selectedConv, setSelectedConv] = useState<Conversation | null>(null);
    const [messages, setMessages] = useState<Message[]>([]);
    const [campaigns, setCampaigns] = useState<Campaign[]>([]);
    const [selectedCampaignId, setSelectedCampaignId] = useState<string>('');
    const [inputText, setInputText] = useState('');
    const [searchTerm, setSearchTerm] = useState('');
    const [isLoadingConv, setIsLoadingConv] = useState(true);
    const [isSending, setIsSending] = useState(false);
    const scrollRef = useRef<HTMLDivElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        whatsappApi.getCampaigns({ limit: 100 }).then(res => setCampaigns(res.items));
    }, []);

    useEffect(() => {
        const fetchConversations = async () => {
            setIsLoadingConv(true);
            try {
                const res = await whatsappApi.getConversations({ 
                    limit: 50, 
                    search: searchTerm || undefined,
                    campaign_id: selectedCampaignId || undefined
                });
                setConversations(res.conversations);
                if (res.conversations.length > 0 && !selectedConv) {
                    setSelectedConv(res.conversations[0]);
                }
            } catch (err) { console.error(err); } finally { setIsLoadingConv(false); }
        };
        fetchConversations();
    }, [searchTerm, selectedCampaignId]);

    const fetchMessages = React.useCallback(async () => {
        if (!selectedConv) return;
        try {
            const msgs = await whatsappApi.getConversationMessages(selectedConv.phoneNumber);
            setMessages(msgs);
        } catch (err) { console.error(err); }
    }, [selectedConv]);

    useEffect(() => {
        if (!selectedConv) return;
        fetchMessages();

        // Subscribe to real-time updates
        const unsubMessage = wsService.subscribe('new_message', (payload) => {
            // Skip agent-sent messages — they are already shown via optimistic update
            if (payload.data?.sender === 'agent') {
                // Still update conversations sidebar, but don't duplicate the message
            } else if (payload.wa_id === selectedConv.phoneNumber) {
                const incoming: Message = {
                    id: payload.data.id,
                    text: payload.data.text,
                    sender: 'user',
                    timestamp: payload.data.timestamp,
                    type: 'text'
                };
                // Deduplicate: don't add if message with same id already exists
                setMessages(prev => {
                    if (prev.some(m => m.id === incoming.id)) return prev;
                    return [...prev, incoming];
                });
            }
            
            // Update conversations list regardless of which one is selected
            setConversations(prev => {
                const existing = prev.find(c => c.phoneNumber === payload.wa_id);
                if (existing) {
                    const updated = { ...existing, lastMessage: payload.data.text, timestamp: payload.data.timestamp };
                    return [updated, ...prev.filter(c => c.phoneNumber !== payload.wa_id)];
                }
                return prev; // Or fetch again if it's a new contact
            });
        });

        const unsubStatus = wsService.subscribe('status_update', (payload) => {
            if (payload.wa_id === selectedConv.phoneNumber) {
                setMessages(prev => prev.map(m => 
                    m.id === payload.meta_id || m.id === payload.id ? { ...m, deliveryStatus: payload.status } : m
                ));
            }
        });

        return () => {
            unsubMessage();
            unsubStatus();
        };
    }, [selectedConv, fetchMessages]);

    useEffect(() => {
        scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const handleSendMessage = async (e?: React.FormEvent) => {
        if (e) e.preventDefault();
        if (!inputText.trim() || !selectedConv || isSending) return;
        setIsSending(true);
        const tempId = `temp-${Date.now()}`;
        const newMessage: Message = { id: tempId, text: inputText, sender: 'agent', timestamp: new Date().toISOString(), type: 'text', deliveryStatus: 'sent' };
        setMessages(prev => [...prev, newMessage]);
        const sentText = inputText;
        setInputText('');
        try {
            await whatsappApi.sendMessage(selectedConv.phoneNumber, sentText);
        } catch (err) { 
            console.error(err); 
            // Remove optimistic message on failure
            setMessages(prev => prev.filter(m => m.id !== tempId));
            setInputText(sentText);
        } finally { setIsSending(false); }
    };

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file || !selectedConv) return;
        setIsSending(true);
        const mediaType = file.type.startsWith('image/') ? 'image' : (file.type.startsWith('video/') ? 'video' : 'document');
        try {
            await whatsappApi.sendMedia(selectedConv.phoneNumber, file, mediaType);
            fetchMessages();
        } catch (err) { console.error(err); } finally { setIsSending(false); }
    };

    return (
        <div className="flex h-[calc(100vh-120px)] gap-6 font-sans overflow-hidden">
            {/* Sidebar */}
            <div className="w-80 md:w-96 flex flex-col bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm overflow-hidden shrink-0">
                <div className="p-6 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/20 space-y-4">
                    <div className="flex items-center justify-between">
                        <h2 className="text-xl font-bold text-slate-900 dark:text-white">Messages</h2>
                        {selectedCampaignId && (
                            <button 
                                onClick={() => setSelectedCampaignId('')}
                                className="p-1.5 hover:bg-slate-200 dark:hover:bg-slate-800 rounded-lg text-slate-500 transition-colors"
                                title="Clear Campaign Filter"
                            >
                                <FilterX size={16} />
                            </button>
                        )}
                    </div>

                    <div className="space-y-3">
                        {/* Campaign Dropdown */}
                        <div className="relative group">
                            <Megaphone className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 group-focus-within:text-indigo-500 transition-colors" size={14} />
                            <select 
                                value={selectedCampaignId} 
                                onChange={e => setSelectedCampaignId(e.target.value)}
                                className="w-full pl-9 pr-4 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-[11px] font-bold uppercase tracking-wider outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all appearance-none cursor-pointer"
                            >
                                <option value="">All Campaigns</option>
                                {campaigns.map(camp => (
                                    <option key={camp.id} value={camp.id}>{camp.name}</option>
                                ))}
                            </select>
                        </div>

                        {/* Search Bar */}
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14} />
                            <input 
                                value={searchTerm} 
                                onChange={e => setSearchTerm(e.target.value)} 
                                placeholder="Search contacts..." 
                                className="w-full pl-9 pr-4 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-xs outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all" 
                            />
                        </div>
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto p-2 space-y-1">
                    {isLoadingConv ? (
                        <div className="flex justify-center py-10"><Loader2 className="animate-spin text-indigo-600" size={24} /></div>
                    ) : conversations.map(conv => (
                        <div key={conv.sessionId} onClick={() => setSelectedConv(conv)} className={`p-4 rounded-lg cursor-pointer transition-all flex items-center gap-4 border ${selectedConv?.sessionId === conv.sessionId ? 'bg-indigo-50 dark:bg-indigo-500/10 border-indigo-100 dark:border-indigo-500/20 shadow-sm' : 'border-transparent hover:bg-slate-50 dark:hover:bg-slate-800/50'}`}>
                            <div className="relative">
                                <div className={`w-12 h-12 rounded-lg flex items-center justify-center font-bold text-lg ${selectedConv?.sessionId === conv.sessionId ? 'bg-indigo-600 text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-400'}`}>{conv.phoneNumber.slice(-2)}</div>
                                {conv.isActive && <div className="absolute -top-1 -right-1 w-3.5 h-3.5 bg-emerald-500 rounded-full border-2 border-white dark:border-slate-900 shadow-sm" />}
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="flex justify-between items-center mb-0.5">
                                    <p className="font-bold text-sm truncate text-slate-900 dark:text-white">{conv.phoneNumber}</p>
                                    <span className="text-[10px] font-medium text-slate-400">{new Date(conv.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                                </div>
                                <div className="flex items-center justify-between gap-2">
                                    <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate flex-1">{conv.lastMessage}</p>
                                    {!conv.isActive && <span className="text-[8px] font-black uppercase text-slate-400 bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded">Exp</span>}
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Chat Area */}
            <div className="flex-1 flex flex-col bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm overflow-hidden">
                {selectedConv ? (
                    <>
                        <div className="p-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between bg-white dark:bg-slate-900 relative z-10 shadow-sm">
                            <div className="flex items-center gap-4">
                                <div className="w-10 h-10 bg-indigo-600 rounded-lg flex items-center justify-center font-bold text-white shadow-sm">{selectedConv.phoneNumber.slice(-2)}</div>
                                <div>
                                    <h2 className="font-bold text-slate-900 dark:text-white leading-none">{selectedConv.phoneNumber}</h2>
                                    <div className="flex items-center gap-1.5 mt-1.5">
                                        <div className={`w-1.5 h-1.5 ${selectedConv.isActive ? 'bg-emerald-500' : 'bg-slate-400'} rounded-full ${selectedConv.isActive ? 'shadow-[0_0_8px_rgba(16,185,129,0.6)]' : ''}`} />
                                        <span className={`${selectedConv.isActive ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-400'} text-[10px] font-black uppercase tracking-wider`}>
                                            {selectedConv.isActive ? 'Session Active' : 'Session Expired'}
                                        </span>
                                    </div>
                                </div>
                            </div>
                            <div className="flex gap-1">
                                <button className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400"><ShieldCheck size={18} /></button>
                                <button className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400"><MoreVertical size={18} /></button>
                            </div>
                        </div>

                        <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-slate-50/30 dark:bg-slate-900/50">
                            {messages.map((msg, i) => (
                                <div key={i} className={`flex ${msg.sender === 'agent' ? 'justify-end' : 'justify-start'}`}>
                                    <div className={`max-w-[70%] p-4 rounded-xl text-sm leading-relaxed shadow-sm ${msg.sender === 'agent' ? 'bg-indigo-600 text-white rounded-tr-none' : 'bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 rounded-tl-none border border-slate-100 dark:border-slate-700'}`}>
                                        {msg.type === 'text' ? <p>{msg.text}</p> : <div className="flex items-center gap-2 p-2 bg-black/5 dark:bg-white/5 rounded-lg">{msg.type === 'image' ? <ImageIcon size={20} /> : <FileText size={20} />}<span className="text-xs font-bold uppercase">{msg.type}</span></div>}
                                        <div className={`mt-2 flex items-center justify-end gap-1.5 text-[10px] font-bold ${msg.sender === 'agent' ? 'text-indigo-100' : 'text-slate-400'}`}>
                                            {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                            {msg.sender === 'agent' && <CheckCheck size={12} className={msg.deliveryStatus === 'read' ? 'text-white' : 'opacity-50'} />}
                                        </div>
                                    </div>
                                </div>
                            ))}
                            <div ref={scrollRef} />
                        </div>

                        <div className="p-4 bg-white dark:bg-slate-900 border-t border-slate-100 dark:border-slate-800">
                            <form onSubmit={handleSendMessage} className="flex items-center gap-3">
                                <input type="file" className="hidden" ref={fileInputRef} onChange={handleFileUpload} />
                                <button type="button" onClick={() => fileInputRef.current?.click()} className="p-2.5 bg-slate-50 dark:bg-slate-800 text-slate-400 rounded-lg hover:text-indigo-600 transition-all shadow-inner"><Paperclip size={20} /></button>
                                <input type="text" value={inputText} onChange={e => setInputText(e.target.value)} placeholder="Type a message..." className="flex-1 bg-slate-50 dark:bg-slate-800 border border-slate-100 dark:border-slate-700 rounded-lg px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-indigo-500/20" />
                                <button type="submit" disabled={isSending || !inputText.trim()} className="bg-indigo-600 text-white p-2.5 rounded-lg shadow-md hover:bg-indigo-700 disabled:opacity-50 transition-all">{isSending ? <Loader2 className="animate-spin" size={20} /> : <Send size={20} />}</button>
                            </form>
                        </div>
                    </>
                ) : (
                    <div className="flex-1 flex flex-col items-center justify-center p-20 text-center space-y-4">
                        <div className="w-16 h-16 bg-slate-50 dark:bg-slate-800 rounded-full flex items-center justify-center text-slate-200 dark:text-slate-700 mb-2"><MessageSquare size={32} /></div>
                        <div>
                            <h3 className="text-lg font-bold text-slate-900 dark:text-white">Active Engagement</h3>
                            <p className="text-sm text-slate-500 max-w-[240px] mx-auto">Select a contact from the sidebar to start a conversation.</p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default Chat;
