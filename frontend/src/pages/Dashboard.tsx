import React, { useEffect, useState, useCallback } from 'react';
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
    RefreshCw,
    Filter,
} from 'lucide-react';
import { whatsappApi, type DashboardStats } from '../services/whatsappApi';
import { wsService } from '../services/websocketService';
import MessagingTrendsChart from '../components/MessagingTrendsChart';
import PageHeader from '../components/PageHeader';
import { FileDown } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { CustomSelect } from '../components/CustomSelect';

const DashboardV2: React.FC = () => {
    const navigate = useNavigate();
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
    const [campaigns, setCampaigns] = useState<any[]>([]);
    const [selectedCampaignId, setSelectedCampaignId] = useState<string>("");
    const [exchangeRate, setExchangeRate] = useState<number | null>(null);

    // FE-FIX FE-11: Wrapped in useCallback so WS event handlers don't capture a stale closure.
    // Without this, changing trendPeriod in UI didn't affect WS-triggered refreshes.
    const fetchStats = useCallback(async () => {
        try {
            const [statsData, trendData, activityData, rateData] = await Promise.all([
                whatsappApi.getStats(selectedCampaignId),
                whatsappApi.getTrends(trendPeriod, selectedCampaignId),
                whatsappApi.getRecentActivity(50, 24, selectedCampaignId),
                whatsappApi.getExchangeRate()
            ]);
            setStats(statsData);
            setTrendData(trendData);
            setRecentActivity(activityData);
            setExchangeRate(rateData.exchange_rate);
        } catch (err) {
            console.error("Failed to fetch dashboard data", err);
        } finally {
            setIsLoading(false);
        }
    }, [trendPeriod, selectedCampaignId]);

    useEffect(() => {
        const fetchCampaigns = async () => {
            try {
                const res = await whatsappApi.getCampaigns({ limit: 100 });
                setCampaigns(res.items);
            } catch (err) {
                console.error("Failed to fetch campaigns", err);
            }
        };
        fetchCampaigns();
    }, []);

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
    }, [trendPeriod, selectedCampaignId]);

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
                    <div className="flex items-center gap-4">
                        <div className="min-w-[200px]">
                            <CustomSelect
                                label="View Scope"
                                icon={<Filter size={14} />}
                                value={selectedCampaignId}
                                onChange={setSelectedCampaignId}
                                options={[
                                    { value: "", label: "All Campaigns" },
                                    ...campaigns.map(c => ({ value: c.id, label: c.name }))
                                ]}
                            />
                        </div>

                        <div className="flex items-center gap-5 p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm relative overflow-hidden">
                            <div className="w-12 h-12 bg-indigo-50 dark:bg-indigo-500/10 rounded-lg flex items-center justify-center text-indigo-600 dark:text-indigo-400">
                                <CreditCard size={24} />
                            </div>
                            <div>
                                 <div className="flex flex-col">
                                    <div className="flex items-baseline gap-2">
                                        <span className="text-2xl font-bold text-slate-900 dark:text-white tabular-nums tracking-tight">
                                            ₹{stats.balance.estimated_inr.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                        </span>
                                        <span className="text-[10px] font-medium text-slate-400 tabular-nums">
                                            (${(() => {
                                                const usd = exchangeRate 
                                                    ? stats.balance.estimated_inr / exchangeRate 
                                                    : stats.balance.estimated_usd;
                                                return usd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                                            })()})
                                        </span>
                                    </div>
                                </div>
                            </div>
                            <button
                                onClick={() => navigate('/settings')}
                                className="ml-4 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-bold transition-all shadow-sm"
                            >
                                {/* FE-FIX FE-12: Added navigate to /settings for recharge action */}
                                RECHARGE
                            </button>
                        </div>
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

                <div className="bg-white dark:bg-slate-900 rounded-2xl p-8 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col h-[75vh]">
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
                                    {/* FE-FIX FE-13: Fixed dynamic Tailwind class bug.
                                    Dynamic classes like bg-${color}-500 are purged in production.
                                    Use a fixed class lookup map instead. */}
                                    {(() => {
                                        const colorMap: Record<string, string> = {
                                            indigo: 'bg-indigo-500',
                                            emerald: 'bg-emerald-500',
                                            rose: 'bg-rose-500',
                                            amber: 'bg-amber-500',
                                        };
                                        return <div className={`w-2 h-2 rounded-full ${colorMap[log.color] ?? 'bg-slate-500'}`} />;
                                    })()}
                                    <div>
                                        <p className="text-xs font-semibold text-slate-900 dark:text-white">{log.user_name}</p>
                                        <p className="text-[10px] text-slate-500 dark:text-slate-400 font-medium">
                                            <span className="text-indigo-500/80 font-bold uppercase tracking-tighter text-[8px] mr-1">[{log.campaign}]</span>
                                            {log.msg}
                                            {log.user_name !== log.user && <span className="text-slate-400 dark:text-slate-500 ml-1 opacity-60">({log.user})</span>}
                                        </p>
                                    </div>
                                </div>
                                <div className="text-right">
                                    <p className="text-[10px] font-medium text-slate-400 mb-0.5">{log.exact_time} ({log.time})</p>
                                    {/* FE-FIX FE-13: Same fix for status text color */}
                                    {(() => {
                                        const textColorMap: Record<string, string> = {
                                            indigo: 'text-indigo-500',
                                            emerald: 'text-emerald-500',
                                            rose: 'text-rose-500',
                                            amber: 'text-amber-500',
                                        };
                                        return <span className={`text-[9px] font-bold uppercase tracking-widest ${textColorMap[log.color] ?? 'text-slate-500'}`}>{log.status}</span>;
                                    })()}
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
