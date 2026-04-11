import React, { useEffect, useState } from 'react';
import { 
  MessageSquare, 
  CreditCard, 
  Activity, 
  ArrowUpRight, 
  ArrowDownRight, 
  CheckCircle2, 
  Send,
  Zap,
  LayoutDashboard,
  RefreshCw
} from 'lucide-react';
import { whatsappApi, type DashboardStats } from '../services/whatsappApi';
import { wsService } from '../services/websocketService';
import MessagingTrendsChart from '../components/MessagingTrendsChart';
import PageHeader from '../components/PageHeader';
import { FileDown } from 'lucide-react';

const DashboardV2: React.FC = () => {
    const [stats, setStats] = useState<DashboardStats>({
        messages: { total: 0, delivered: 0, read: 0, failed: 0, trend: 0 },
        rates: { delivery_trend: 0, read_trend: 0 },
        costs: { total_usd: 0, total_inr: 0, trend_inr: 0 },
        balance: { estimated_inr: 0, estimated_usd: 0 },
        brochures: { sent: 0 }
    });
    const [isLoading, setIsLoading] = useState(true);
    const [trendData, setTrendData] = useState<any[]>([]);
    const [trendPeriod, setTrendPeriod] = useState(7);
    const [recentActivity, setRecentActivity] = useState<any[]>([]);

    const fetchStats = async () => {
        try {
            const [statsData, trendData, activityData] = await Promise.all([
                whatsappApi.getStats(),
                whatsappApi.getTrends(trendPeriod),
                whatsappApi.getRecentActivity(5)
            ]);
            setStats(statsData);
            setTrendData(trendData);
            setRecentActivity(activityData);
        } catch (err) {
            console.error("Failed to fetch dashboard data", err);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchStats();
        
        // Subscribe to real-time events to refresh stats or update activity
        const unsub = wsService.subscribe('new_message', () => {
             // Refresh stats when messages come in
             fetchStats();
        });

        const unsubProgress = wsService.subscribe('campaign_progress', (payload) => {
             if (payload.status === "completed") {
                 fetchStats();
             }
        });

        // Slow polling as fallback
        const interval = setInterval(fetchStats, 60000); 
        return () => {
            unsub();
            unsubProgress();
            clearInterval(interval);
        };
    }, [trendPeriod]);

    const exportToCSV = () => {
        const headers = ["Date", "Sent", "Delivered", "Read"];
        const rows = trendData.map(d => [d.date, d.sent, d.delivered, d.read]);
        const csvContent = [headers, ...rows].map(e => e.join(",")).join("\n");
        const blob = new Blob([csvContent], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.setAttribute('hidden', '');
        a.setAttribute('href', url);
        a.setAttribute('download', `messaging_stats_${new Date().toISOString().split('T')[0]}.csv`);
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    };

    const deliveryRate = stats.messages.total > 0 ? (stats.messages.delivered / stats.messages.total) * 100 : 0;
    const readRate = stats.messages.delivered > 0 ? (stats.messages.read / stats.messages.delivered) * 100 : 0;

    return (
        <div className="space-y-10 font-sans selection:bg-indigo-500/30">
            
            <PageHeader 
                title="Dashboard" 
                description="Monitor your messaging performance and balance" 
                actions={
                    <div className="flex items-center gap-5 p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm relative overflow-hidden">
                        <div className="w-12 h-12 bg-indigo-50 dark:bg-indigo-500/10 rounded-lg flex items-center justify-center text-indigo-600 dark:text-indigo-400">
                            <CreditCard size={24} />
                        </div>
                        <div>
                            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Available Balance</p>
                            <div className="flex items-baseline gap-2">
                                <span className="text-2xl font-bold text-slate-900 dark:text-white tabular-nums tracking-tight">
                                    ₹{stats.balance.estimated_inr.toLocaleString()}
                                </span>
                                <span className="text-[10px] font-medium text-slate-400 tabular-nums">(${stats.balance.estimated_usd.toLocaleString()})</span>
                            </div>
                        </div>
                        <button className="ml-4 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-bold transition-all shadow-sm">
                            RECHARGE
                        </button>
                    </div>
                } 
            />

            {/* Core Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <StatCard 
                    title="Total Messages" 
                    value={stats.messages.total} 
                    subValue="Outbound success"
                    icon={<MessageSquare className="text-indigo-500" />} 
                    trend={`${stats.messages.trend > 0 ? '+' : ''}${stats.messages.trend}%`} 
                    isUp={stats.messages.trend >= 0} 
                />
                <StatCard 
                    title="Delivery Rate" 
                    value={`${deliveryRate.toFixed(1)}%`} 
                    subValue={`${stats.messages.delivered} delivered`}
                    icon={<CheckCircle2 className="text-emerald-500" />} 
                    trend={`${stats.rates.delivery_trend > 0 ? '+' : ''}${stats.rates.delivery_trend.toFixed(1)}%`} 
                    isUp={stats.rates.delivery_trend >= 0} 
                />
                <StatCard 
                    title="Read Rate" 
                    value={`${readRate.toFixed(1)}%`} 
                    subValue={`${stats.messages.read} read receipts`}
                    icon={<Activity className="text-cyan-500" />} 
                    trend={`${stats.rates.read_trend > 0 ? '+' : ''}${stats.rates.read_trend.toFixed(1)}%`} 
                    isUp={stats.rates.read_trend >= 0} 
                />
                <StatCard 
                    title="Total Spend" 
                    value={`₹${stats.costs.total_inr.toFixed(2)}`} 
                    subValue={`$${stats.costs.total_usd.toFixed(2)} USD`}
                    icon={<CreditCard className="text-slate-500" />} 
                    trend={`${stats.costs.trend_inr > 0 ? '+' : ''}${stats.costs.trend_inr.toFixed(1)}%`} 
                    isUp={stats.costs.trend_inr <= 0} // For spend, "up" is usually bad, but we stick to numerical for consistency or reverse if requested. Let's stick to numerical up/down.
                />
            </div>

            {/* Visual Funnel & Live Stream */}
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
                <div className="xl:col-span-2 bg-white dark:bg-slate-900 rounded-2xl p-8 border border-slate-200 dark:border-slate-800 shadow-sm">
                    <div className="flex justify-between items-center mb-10">
                        <div>
                            <h3 className="text-lg font-bold text-slate-900 dark:text-white tracking-tight">Messaging Statistics</h3>
                            <p className="text-slate-500 dark:text-slate-400 text-xs mt-1 font-medium">Efficiency transition through funnel</p>
                        </div>
                        <div className="flex bg-slate-50 dark:bg-slate-800 p-1 rounded-lg border border-slate-200 dark:border-slate-700">
                            {[7, 14, 30].map(d => (
                                <button 
                                    key={d} 
                                    onClick={() => setTrendPeriod(d)}
                                    className={`px-4 py-1.5 rounded-md text-[10px] font-bold transition-all ${trendPeriod === d ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm' : 'text-slate-400 hover:text-slate-600'}`}
                                >
                                    {d}D
                                </button>
                            ))}
                        </div>
                        <button 
                            onClick={exportToCSV}
                            className="flex items-center gap-2 px-4 py-2 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 rounded-lg text-xs font-bold transition-all"
                        >
                            <FileDown size={14} />
                            EXPORT
                        </button>
                    </div>

                    <div className="mb-10">
                        <MessagingTrendsChart data={trendData} />
                    </div>

                    <div className="space-y-8">
                        <FunnelStep label="Total Sent" value={stats.messages.total} percentage={100} color="bg-slate-200 dark:bg-slate-700" />
                        <FunnelStep label="Delivered" value={stats.messages.delivered} percentage={deliveryRate} color="bg-indigo-500" />
                        <FunnelStep label="Read" value={stats.messages.read} percentage={stats.messages.total > 0 ? (stats.messages.read / stats.messages.total * 100) : 0} color="bg-emerald-500" />
                        <FunnelStep label="Failed" value={stats.messages.failed} percentage={stats.messages.total > 0 ? (stats.messages.failed / stats.messages.total * 100) : 0} color="bg-rose-500" />
                    </div>
                </div>

                <div className="bg-white dark:bg-slate-900 rounded-2xl p-8 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col">
                    <div className="flex items-center justify-between mb-8">
                        <h3 className="text-lg font-bold text-slate-900 dark:text-white">Recent Activity</h3>
                        <Activity className="text-indigo-500" size={20} />
                    </div>
                    
                    <div className="space-y-4 flex-1 overflow-y-auto pr-2">
                        {isLoading ? (
                            <div className="h-full flex flex-col items-center justify-center gap-2 opacity-30">
                                <RefreshCw className="animate-spin" size={24} />
                                <span className="text-[10px] font-bold uppercase tracking-widest">Loading...</span>
                            </div>
                        ) : recentActivity.length === 0 ? (
                            <div className="h-full flex flex-col items-center justify-center gap-2 opacity-30 text-center py-10">
                                <MessageSquare size={24} />
                                <span className="text-[10px] font-bold uppercase tracking-widest">No Recent Activity</span>
                            </div>
                        ) : recentActivity.map((log, i) => (
                            <div key={i} className="flex items-center justify-between p-4 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-100 dark:border-slate-700 group transition-all">
                                <div className="flex items-center gap-3">
                                    <div className={`w-2 h-2 rounded-full bg-${log.color}-500`} />
                                    <div>
                                        <p className="text-xs font-semibold text-slate-900 dark:text-white">{log.user}</p>
                                        <p className="text-[10px] text-slate-500 dark:text-slate-400 font-medium">{log.msg}</p>
                                    </div>
                                </div>
                                <div className="text-right">
                                    <p className="text-[10px] font-medium text-slate-400 mb-0.5">{log.time}</p>
                                    <span className={`text-[9px] font-bold uppercase tracking-widest text-${log.color}-500`}>{log.status}</span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
};

const StatCard = ({ title, value, subValue, icon, trend, isUp }: any) => (
    <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm transition-all duration-200 hover:shadow-md group">
        <div className="flex justify-between items-start mb-6">
            <div className="w-10 h-10 bg-slate-50 dark:bg-slate-800 rounded-lg flex items-center justify-center text-slate-500 transition-transform">
                {icon}
            </div>
            <div className={`text-[10px] ${isUp ? 'text-emerald-600' : 'text-rose-600'} font-bold tabular-nums px-2 py-1 rounded bg-slate-50 dark:bg-slate-800 border border-slate-100 dark:border-slate-700`}>
                {trend}
            </div>
        </div>
        
        <div>
            <h4 className="text-2xl font-bold text-slate-900 dark:text-white tabular-nums tracking-tight mb-1">{value}</h4>
            <p className="text-slate-500 dark:text-slate-400 font-medium text-xs tracking-tight">{title}</p>
            <p className="mt-3 text-[10px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">{subValue}</p>
        </div>
    </div>
);

const FunnelStep = ({ label, value, percentage, color }: any) => (
    <div className="space-y-2">
        <div className="flex justify-between items-end">
            <span className="text-[10px] font-bold uppercase text-slate-500 tracking-wider ml-1">{label}</span>
            <div className="flex items-baseline gap-2">
                <span className="text-xl font-bold text-slate-800 dark:text-white tracking-tight">
                    {value.toLocaleString()}
                </span>
                <span className="text-[10px] font-medium text-slate-400">({percentage.toFixed(1)}%)</span>
            </div>
        </div>
        <div className="h-2 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
            <div 
                style={{ width: `${percentage}%` }}
                className={`h-full ${color} rounded-full transition-all duration-1000 ease-out`}
            />
        </div>
    </div>
);

export default DashboardV2;
