import React, { useEffect, useState } from 'react';
import {
    Globe,
    Users,
    Layers,
    ShieldCheck,
    TrendingUp,
    TrendingDown,
    Activity,
    CreditCard,
    Plus,
    Settings,
    MoreHorizontal,
    Search,
    ExternalLink,
    Eye
} from 'lucide-react';
import { whatsappApi } from '../services/whatsappApi';
import PageHeader from '../components/PageHeader';
import { useNavigate } from 'react-router-dom';

const SuperAdminDashboard: React.FC = () => {
    const navigate = useNavigate();
    const [orgs, setOrgs] = useState<any[]>([]);
    const [users, setUsers] = useState<any[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState("");

    useEffect(() => {
        const fetchData = async () => {
            try {
                const [orgsData, usersData] = await Promise.all([
                    whatsappApi.getOrganizations(),
                    whatsappApi.getAllUsers()
                ]);
                setOrgs(orgsData);
                setUsers(usersData);
            } catch (err) {
                console.error("Failed to fetch super admin data", err);
            } finally {
                setIsLoading(false);
            }
        };
        fetchData();
    }, []);

    const filteredOrgs = orgs.filter(o => 
        o.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
        o.slug.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div className="space-y-8 animate-in fade-in duration-700">
            <PageHeader 
                title="System Overview" 
                description="Global multi-tenant infrastructure management"
                actions={
                    <button 
                        onClick={() => navigate('/admin/organizations')}
                        className="flex items-center gap-2 px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-bold transition-all shadow-lg shadow-indigo-500/20 active:scale-95"
                    >
                        <Plus size={18} />
                        NEW ORGANIZATION
                    </button>
                }
            />

            {/* Global Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <GlobalStatCard 
                    title="Total Organizations" 
                    value={orgs.length} 
                    icon={<Layers className="text-indigo-500" />} 
                    trend="+12%" 
                    isUp={true}
                    color="indigo"
                />
                <GlobalStatCard 
                    title="Active Users" 
                    value={users.filter(u => u.is_active).length} 
                    icon={<Users className="text-emerald-500" />} 
                    trend="+5.4%" 
                    isUp={true}
                    color="emerald"
                />
                <GlobalStatCard 
                    title="System Success Rate" 
                    value="98.2%" 
                    icon={<ShieldCheck className="text-cyan-500" />} 
                    trend="+0.2%" 
                    isUp={true}
                    color="cyan"
                />
                <GlobalStatCard 
                    title="Total Infrastructure Cost" 
                    value="₹1.2M" 
                    icon={<CreditCard className="text-rose-500" />} 
                    trend="+8%" 
                    isUp={false}
                    color="rose"
                />
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
                <div className="xl:col-span-2 bg-white dark:bg-slate-900 rounded-[32px] border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col overflow-hidden">
                    <div className="p-8 border-b border-slate-100 dark:border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-6 bg-slate-50/50 dark:bg-slate-800/30">
                        <div>
                            <h3 className="text-xl font-black text-slate-900 dark:text-white tracking-tight uppercase">Registry Overview</h3>
                            <p className="text-slate-500 dark:text-slate-400 text-[10px] mt-1 font-black uppercase tracking-widest leading-none">Global Multi-Tenant Registry</p>
                        </div>
                        <div className="relative">
                            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                            <input 
                                type="text"
                                placeholder="Search registry..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="pl-12 pr-4 py-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl text-[11px] font-black uppercase tracking-wider focus:ring-2 focus:ring-indigo-500 transition-all w-64 shadow-inner"
                            />
                        </div>
                    </div>

                    <div className="overflow-x-auto custom-scrollbar">
                        <table className="w-full text-left text-sm border-separate border-spacing-0">
                            <thead>
                                <tr className="bg-slate-50/50 dark:bg-slate-800/50 transition-all">
                                    <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800">Organization</th>
                                    <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800">Slug</th>
                                    <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800">Population</th>
                                    <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800 text-center">Security</th>
                                    <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800 text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-50 dark:divide-slate-800/50">
                                {filteredOrgs.map((org) => (
                                    <tr key={org.id} className="hover:bg-indigo-50/30 dark:hover:bg-indigo-500/5 transition-all group">
                                        <td className="px-8 py-5">
                                            <div className="flex items-center gap-4">
                                                <div className="w-10 h-10 bg-indigo-500/10 rounded-xl flex items-center justify-center text-indigo-600 dark:text-indigo-400 font-black shadow-sm group-hover:scale-110 transition-transform">
                                                    {org.name.charAt(0)}
                                                </div>
                                                <span className="text-sm font-black text-slate-900 dark:text-white">{org.name}</span>
                                            </div>
                                        </td>
                                        <td className="px-8 py-5">
                                            <code className="px-2 py-1 bg-slate-100 dark:bg-slate-800 rounded-md text-[9px] font-black text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-slate-700">/{org.slug}</code>
                                        </td>
                                        <td className="px-8 py-5 text-[11px] font-bold text-slate-500 dark:text-slate-400">
                                            {org.member_count} Accounts
                                        </td>
                                        <td className="px-8 py-5 text-center">
                                            <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[9px] font-black uppercase tracking-widest border ${org.is_active ? 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20 shadow-[0_0_12px_rgba(16,185,129,0.1)]' : 'bg-slate-100 dark:bg-slate-800 text-slate-400 border-slate-200'}`}>
                                                <div className={`w-1 h-1 rounded-full ${org.is_active ? 'bg-emerald-500' : 'bg-slate-400'}`} />
                                                {org.is_active ? 'Active' : 'Suspended'}
                                            </span>
                                        </td>
                                        <td className="px-8 py-5 text-right">
                                            <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-all translate-x-2 group-hover:translate-x-0">
                                                <button 
                                                    onClick={() => navigate(`/admin/dashboard?orgId=${org.id}`)}
                                                    className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-[10px] font-black uppercase tracking-widest transition-all shadow-md"
                                                >
                                                    <Eye size={14} />
                                                    Explore
                                                </button>
                                                <button 
                                                    onClick={() => navigate(`/admin/organizations/${org.id}`)}
                                                    className="p-2.5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl transition-all text-slate-400 hover:text-indigo-500 hover:border-indigo-500 shadow-sm"
                                                >
                                                    <Settings size={16} />
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* System Health / Recent Signups */}
                <div className="bg-white dark:bg-slate-900 rounded-3xl p-8 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col">
                    <h3 className="text-xl font-bold text-slate-900 dark:text-white mb-8">System Health</h3>
                    <div className="space-y-6 flex-1">
                        <HealthItem label="Core API" status="online" ping="12ms" />
                        <HealthItem label="Messaging Engine (Redis)" status="online" ping="2ms" />
                        <HealthItem label="Database Cluster" status="online" ping="4ms" />
                        <HealthItem label="Meta Webhook Listener" status="online" ping="18ms" />
                    </div>

                    <div className="mt-10 pt-10 border-t border-slate-100 dark:border-slate-800">
                        <h4 className="text-sm font-bold text-slate-900 dark:text-white mb-4">Recent Global Activity</h4>
                        <div className="space-y-4">
                            {users.slice(0, 4).map(u => (
                                <div key={u.id} className="flex items-center justify-between text-xs">
                                    <div className="flex items-center gap-2">
                                        <div className="w-6 h-6 bg-slate-100 dark:bg-slate-800 rounded-full flex items-center justify-center text-[10px] font-bold">
                                            {u.username.charAt(0).toUpperCase()}
                                        </div>
                                        <span className="font-medium">{u.username}</span>
                                    </div>
                                    <span className="text-slate-400 text-[10px]">{u.organization_name}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

const GlobalStatCard = ({ title, value, icon, trend, isUp, color }: any) => {
    const bgColors: any = {
        indigo: 'bg-indigo-500',
        emerald: 'bg-emerald-500',
        rose: 'bg-rose-500',
        cyan: 'bg-cyan-500',
    };
    
    return (
        <div className="relative bg-white dark:bg-slate-900 p-8 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden group">
            <div className={`absolute top-0 right-0 w-32 h-32 ${bgColors[color]} opacity-[0.03] -mr-16 -mt-16 blur-3xl transition-opacity group-hover:opacity-[0.08]`} />
            
            <div className="flex justify-between items-start mb-6">
                <div className="w-12 h-12 bg-slate-50 dark:bg-slate-800 rounded-2xl flex items-center justify-center text-xl shadow-inner group-hover:scale-110 transition-transform">
                    {icon}
                </div>
                <div className={`flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-full ${isUp ? 'text-emerald-600 bg-emerald-50 dark:bg-emerald-500/10' : 'text-rose-600 bg-rose-50 dark:bg-rose-500/10'}`}>
                    {isUp ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                    {trend}
                </div>
            </div>

            <div>
                <h4 className="text-3xl font-black text-slate-900 dark:text-white tracking-tighter mb-1">{value}</h4>
                <p className="text-slate-500 dark:text-slate-400 font-bold text-[10px] uppercase tracking-widest leading-none">{title}</p>
            </div>
        </div>
    );
};

const HealthItem = ({ label, status, ping }: any) => (
    <div className="flex items-center justify-between group">
        <div className="flex items-center gap-3">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
            <span className="text-xs font-bold text-slate-700 dark:text-slate-300">{label}</span>
        </div>
        <div className="flex items-center gap-3">
            <span className="text-[10px] font-bold text-slate-400 tabular-nums">{ping}</span>
            <span className="text-[10px] font-black uppercase text-emerald-500 tracking-tighter transition-all group-hover:tracking-widest cursor-default">
                {status}
            </span>
        </div>
    </div>
);

export default SuperAdminDashboard;
