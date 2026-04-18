import React, { useState, useEffect, useRef } from 'react';
import { Send, User, Clock, CheckCheck, Paperclip, Image as ImageIcon, FileText, Search, MoreVertical, ShieldCheck, Loader2, MessageSquare, Video } from 'lucide-react';
import { whatsappApi, type Conversation, type Message, type Campaign, API_BASE } from '../services/whatsappApi';
import { wsService } from '../services/websocketService';
import { useToast } from '../components/Toast';
import { CustomSelect } from '../components/CustomSelect';
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
    const [timeLeft, setTimeLeft] = useState<string>('');
    const scrollRef = useRef<HTMLDivElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const { error: toastError, success } = useToast();
    console.log(campaigns, "campaigns   ")

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

                // Sync the active conversation header (timer, name)
                setSelectedConv(prev => {
                    if (!prev) return null;
                    // Match by phone number to ensure we're updating the correct open chat
                    if (prev.phoneNumber === payload.wa_id) {
                        return {
                            ...prev,
                            lastMessage: payload.data.text,
                            timestamp: payload.data.timestamp,
                            isActive: payload.data.is_active ?? prev.isActive,
                            windowExpiresAt: payload.data.window_expires_at ?? prev.windowExpiresAt,
                            contactName: payload.contactName || prev.contactName
                        };
                    }
                    return prev;
                });
            }

            // Update conversations list regardless of which one is selected
            setConversations(prev => {
                const waIdClean = payload.wa_id.replace(/\D/g, '').slice(-10); // Match last 10 digits
                const index = prev.findIndex(c => c.phoneNumber.replace(/\D/g, '').slice(-10) === waIdClean);
                
                if (index !== -1) {
                    const updated = [...prev];
                    const convo = { ...updated[index] };
                    convo.lastMessage = payload.data.text;
                    convo.timestamp = payload.data.timestamp;
                    convo.isActive = payload.data.is_active ?? convo.isActive;
                    convo.windowExpiresAt = payload.data.window_expires_at ?? convo.windowExpiresAt;
                    convo.contactName = payload.contactName || convo.contactName;
                    
                    // Move to top of list
                    return [convo, ...updated.filter((_, i) => i !== index)];
                } else {
                    // New conversation from websocket
                    const newConv: Conversation = {
                        sessionId: payload.data.conversation_id || payload.wa_id,
                        phoneNumber: payload.wa_id,
                        contactName: payload.contactName,
                        lastMessage: payload.data.text,
                        timestamp: payload.data.timestamp,
                        unreadCount: 1,
                        isActive: payload.data.is_active ?? true,
                        windowExpiresAt: payload.data.window_expires_at
                    };
                    return [newConv, ...prev];
                }
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
        // FE-FIX FE-9: Dep array uses selectedConv?.phoneNumber (stable string) instead of
        // selectedConv (object). Previously, setConversations spread created new object refs
        // each time a WS message arrived, triggering this effect and causing a re-subscription
        // cascade of full API refetches on every incoming message.
    }, [selectedConv?.phoneNumber, fetchMessages]);

    useEffect(() => {
        scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    useEffect(() => {
        if (!selectedConv?.windowExpiresAt || !selectedConv?.isActive) {
            setTimeLeft('');
            return;
        }
        const calculateTime = () => {
            const expires = new Date(selectedConv.windowExpiresAt!).getTime();
            const now = new Date().getTime();
            const diff = expires - now;
            if (diff <= 0) {
                setTimeLeft('Expired');
                return;
            }
            const hours = Math.floor(diff / (1000 * 60 * 60));
            const mins = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
            setTimeLeft(`${hours}h ${mins}m left`);
        };
        calculateTime();
        const timer = setInterval(calculateTime, 60000);
        return () => clearInterval(timer);
    }, [selectedConv?.windowExpiresAt, selectedConv?.isActive]);

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
        } catch (err: any) {
            console.error(err);
            // Remove optimistic message on failure
            setMessages(prev => prev.filter(m => m.id !== tempId));
            setInputText(sentText);
            toastError('Failed to send', err?.response?.data?.detail || 'Message could not be delivered.');
        } finally { setIsSending(false); }
    };

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file || !selectedConv) return;
        setIsSending(true);
        const mediaType = file.type.startsWith('image/') ? 'image' : (file.type.startsWith('video/') ? 'video' : 'document');
        try {
            await whatsappApi.sendMedia(selectedConv.phoneNumber, file, mediaType);
            success('Media sent', 'File delivered successfully.');
            fetchMessages();
        } catch (err: any) {
            toastError('Media failed', err?.response?.data?.detail || 'Could not send the file.');
        } finally {
            setIsSending(false);
            // FE-FIX FE-15: Reset file input so the same file can be selected again.
            // Without this, onChange doesn't fire if user picks the same file twice.
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
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
                        <div className="relative group">
                            <CustomSelect
                                value={selectedCampaignId}
                                onChange={setSelectedCampaignId}
                                icon={<Megaphone size={14} />}
                                placeholder="All Campaigns"
                                options={[
                                    { value: "", label: "All Campaigns" },
                                    ...campaigns.map(camp => ({ value: camp.id, label: camp.name }))
                                ]}
                            />
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
                                <div className={`w-12 h-12 rounded-lg flex items-center justify-center font-bold text-lg ${selectedConv?.sessionId === conv.sessionId ? 'bg-indigo-600 text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-400'}`}>
                                    {conv.contactName ? conv.contactName.charAt(0).toUpperCase() : conv.phoneNumber.slice(-2)}
                                </div>
                                {conv.isActive && <div className="absolute -top-1 -right-1 w-3.5 h-3.5 bg-emerald-500 rounded-full border-2 border-white dark:border-slate-900 shadow-sm" />}
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="flex justify-between items-start mb-0.5">
                                    <div className="flex flex-col min-w-0">
                                        <p className="font-bold text-sm truncate text-slate-900 dark:text-white leading-tight">
                                            {conv.contactName || conv.phoneNumber}
                                        </p>
                                        {conv.contactName && (
                                            <p className="text-[10px] text-slate-400 font-bold tabular-nums leading-tight mt-0.5">
                                                {conv.phoneNumber}
                                            </p>
                                        )}
                                    </div>
                                    <span className="text-[10px] font-medium text-slate-400 whitespace-nowrap ml-2">
                                        {new Date(conv.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                    </span>
                                </div>
                                <div className="flex items-center justify-between gap-2 mt-1">
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
                                <div className="w-10 h-10 bg-indigo-600 rounded-lg flex items-center justify-center font-bold text-white shadow-sm">
                                    {selectedConv.contactName ? selectedConv.contactName.charAt(0).toUpperCase() : selectedConv.phoneNumber.slice(-2)}
                                </div>
                                <div>
                                    <h2 className="font-bold text-slate-900 dark:text-white leading-none">
                                        {selectedConv.contactName || selectedConv.phoneNumber}
                                    </h2>
                                    {selectedConv.contactName && (
                                        <p className="text-[10px] text-slate-400 font-bold tabular-nums mt-1.5 leading-none">
                                            {selectedConv.phoneNumber}
                                        </p>
                                    )}
                                    <div className="flex items-center gap-1.5 mt-2.5">
                                        <div className={`w-1.5 h-1.5 ${selectedConv.isActive ? 'bg-emerald-500' : 'bg-slate-400'} rounded-full ${selectedConv.isActive ? 'shadow-[0_0_8px_rgba(16,185,129,0.6)]' : ''}`} />
                                        <span className={`${selectedConv.isActive ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-400'} text-[10px] font-black uppercase tracking-wider`}>
                                            {selectedConv.isActive ? (timeLeft ? `Active: ${timeLeft}` : 'Session Active') : 'Session Expired'}
                                        </span>
                                    </div>
                                </div>
                            </div>
                            <div className="flex gap-1">
                                <button className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400"><ShieldCheck size={18} /></button>
                                <button className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400"><MoreVertical size={18} /></button>
                            </div>
                        </div>

                        <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-[#efe7de] dark:bg-[#0b141a] custom-scrollbar">
                            {messages.map((msg) => {
                                const isAgent = msg.sender === 'agent';
                                return (
                                    <div key={msg.id} className={`flex ${isAgent ? 'justify-end' : 'justify-start'} animate-in slide-in-from-bottom-2 duration-300`}>
                                        <div className={`relative max-w-[85%] md:max-w-[70%] px-1 py-1 rounded-xl shadow-sm border ${
                                            isAgent 
                                            ? 'bg-[#dcf8c6] dark:bg-[#056162] text-slate-800 dark:text-slate-100 rounded-tr-none border-[#c3e8a4] dark:border-white/10' 
                                            : 'bg-white dark:bg-[#202c33] text-slate-800 dark:text-slate-100 rounded-tl-none border-slate-200 dark:border-white/5'
                                        }`}>
                                            {/* Media Content - Card Style */}
                                            {msg.type !== 'text' && (
                                                <div className="mb-1 overflow-hidden rounded-lg bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/10 flex flex-col">
                                                    {/* Card Header (Matches "TEMPLATE attachment" style) */}
                                                    <div className={`px-3 py-2 flex items-center gap-2 border-b border-black/5 dark:border-white/5 ${isAgent ? 'bg-black/5' : 'bg-slate-50 dark:bg-white/5'}`}>
                                                        {msg.type === 'image' ? <ImageIcon size={14} className="text-indigo-500" /> : (msg.type === 'video' ? <Video size={14} className="text-rose-500" /> : <FileText size={14} className="text-slate-500" />)}
                                                        <span className="text-[10px] font-black uppercase tracking-[0.2em] opacity-60">
                                                            {msg.type === 'image' ? 'Media' : (msg.type?.includes('template') ? 'Template' : msg.type)} Attachment
                                                        </span>
                                                    </div>

                                                    <div className="relative">
                                                        {msg.type === 'image' ? (
                                                            <img 
                                                                src={msg.mediaUrl ? (msg.mediaUrl.startsWith('http') ? msg.mediaUrl : `${API_BASE}${msg.mediaUrl}${msg.mediaUrl.includes('?') ? '&' : '?'}token=${localStorage.getItem('token')}`) : ''} 
                                                                alt="Media" 
                                                                className="max-w-full h-auto object-cover min-h-[100px] w-full"
                                                                onError={(e) => {
                                                                    (e.target as HTMLImageElement).src = 'https://placehold.co/400x300/e2e8f0/64748b?text=Media+Expired';
                                                                }}
                                                            />
                                                        ) : (
                                                            <div className="p-4 flex flex-col items-center justify-center gap-2 py-8 bg-slate-50/50 dark:bg-slate-800/10">
                                                                {msg.type === 'video' ? <Video size={40} className="text-slate-300" /> : <FileText size={40} className="text-slate-300" />}
                                                                <p className="text-[11px] font-bold text-slate-400">View attachment</p>
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            )}

                                            <div className="px-2 py-1.5 flex flex-col">
                                                {/* Text Content */}
                                                <div className="text-[13px] leading-relaxed break-words whitespace-pre-wrap pr-12">
                                                    {msg.text}
                                                </div>

                                                {/* Info Line */}
                                                <div className="flex justify-end items-center gap-1 mt-1 opacity-60">
                                                    <span className="text-[9px] font-medium tabular-nums">
                                                        {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                                    </span>
                                                    {isAgent && (
                                                        <div className="flex items-center scale-110">
                                                            {msg.deliveryStatus === 'read' ? (
                                                                <CheckCheck size={12} className="text-[#53bdeb] drop-shadow-sm" />
                                                            ) : msg.deliveryStatus === 'delivered' ? (
                                                                <CheckCheck size={12} className="text-slate-400 dark:text-slate-500" />
                                                            ) : (
                                                                <CheckCheck size={12} className="text-slate-400/50" />
                                                            )}
                                                        </div>
                                                    )}
                                                </div>
                                            </div>

                                            {/* Bubble Tail Hook (CSS) */}
                                            <div className={`absolute top-0 w-2.5 h-3 overflow-hidden ${isAgent ? '-right-2.5' : '-left-2.5'}`}>
                                                <div className={`w-3 h-3 rotate-45 transform origin-top-${isAgent ? 'left' : 'right'} ${isAgent ? 'bg-[#dcf8c6] dark:bg-[#056162]' : 'bg-white dark:bg-[#202c33]'}`} />
                                            </div>
                                        </div>
                                    </div>
                                );
                            })}
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
