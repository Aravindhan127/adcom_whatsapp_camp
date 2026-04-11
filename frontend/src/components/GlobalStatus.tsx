import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, Database, Zap, Loader2, Minus, ChevronUp, Move } from 'lucide-react';
import { whatsappApi } from '../services/whatsappApi';

const GlobalStatus: React.FC = () => {
  const location = useLocation();
  const [redisHealthy, setRedisHealthy] = useState<boolean | null>(null);
  const [activeCampaigns, setActiveCampaigns] = useState<any[]>([]);
  const [visible, setVisible] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [health, progress] = await Promise.all([
          whatsappApi.getHealthSummary(),
          whatsappApi.getActiveProgress()
        ]);
        setRedisHealthy(health.redis?.status === 'healthy');
        setActiveCampaigns(progress);
        setVisible(true);
      } catch (err) {
        setRedisHealthy(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 2000);
    return () => clearInterval(interval);
  }, []);

  if (!visible) return null;

  return (
    <div className="fixed bottom-6 right-6 z-[9999] pointer-events-none">
      <motion.div 
        drag
        dragMomentum={false}
        className="pointer-events-auto flex flex-col items-end gap-3"
      >
        {/* Redis Status Pill (Persists and can be dragged) */}
        <div className="bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border border-slate-200 dark:border-slate-800 px-3 py-1.5 rounded-full shadow-lg flex items-center gap-2 transition-all hover:scale-105 group cursor-move">
          <Move size={10} className="text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity" />
          <div className={`w-2 h-2 rounded-full ${redisHealthy ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)] animate-pulse' : 'bg-rose-500 animate-bounce'}`} />
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400">
            Redis: {redisHealthy ? 'Online' : 'Offline'}
          </span>
          {activeCampaigns.length > 0 && (
            <button 
              onClick={() => setIsMinimized(!isMinimized)}
              className="ml-1 p-1 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-full transition-colors"
            >
              {isMinimized ? <ChevronUp size={12} /> : <Minus size={12} />}
            </button>
          )}
        </div>

        {/* Active Campaign Progress List */}
        <AnimatePresence mode="popLayout">
          {!isMinimized && activeCampaigns.length > 0 && (
            <motion.div 
              initial={{ opacity: 0, y: 20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 20, scale: 0.95 }}
              className="flex flex-col gap-3"
            >
              {activeCampaigns.map(camp => (
                <div key={camp.id} className="w-64 bg-white/90 dark:bg-slate-900/90 backdrop-blur-xl border border-indigo-100 dark:border-indigo-500/20 p-4 rounded-2xl shadow-2xl overflow-hidden relative group">
                  {/* Subtle Background Icon */}
                  <div className="absolute -right-4 -bottom-4 opacity-[0.03] dark:opacity-[0.05] rotate-12 transition-transform group-hover:scale-110">
                    <Zap size={100} />
                  </div>

                  <div className="flex justify-between items-center mb-2">
                    <div className="flex items-center gap-2">
                      <div className="p-1.5 bg-indigo-100 dark:bg-indigo-500/20 rounded-lg">
                        <Zap size={14} className="text-indigo-600 dark:text-indigo-400 shadow-[0_0_8px_rgba(99,102,241,0.4)]" />
                      </div>
                      <span className="text-sm font-bold text-slate-800 dark:text-white truncate max-w-[120px]">{camp.name}</span>
                    </div>
                    <span className="text-xs font-black text-indigo-600 dark:text-indigo-400 tabular-nums">{camp.progress}%</span>
                  </div>
                  
                  <div className="relative h-1.5 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                    <motion.div 
                      className="absolute top-0 left-0 h-full bg-indigo-600 dark:bg-indigo-500"
                      initial={{ width: 0 }}
                      animate={{ width: `${camp.progress}%` }}
                      transition={{ duration: 1, ease: "easeOut" }}
                    />
                    <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer" style={{ transform: 'translateX(-100%)' }} />
                  </div>
                  
                  <div className="mt-2 flex justify-between text-[9px] font-bold text-slate-400 uppercase tracking-widest">
                     <span className="flex items-center gap-1">
                       <span className="w-1 h-1 bg-indigo-500 rounded-full animate-ping" />
                       Processing
                     </span>
                     <span>{camp.sent.toLocaleString()} / {camp.total.toLocaleString()}</span>
                  </div>
                </div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
};

export default GlobalStatus;
