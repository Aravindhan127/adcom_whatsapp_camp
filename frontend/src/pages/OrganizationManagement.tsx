import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Plus,
    Settings,
    MoreHorizontal,
    Globe,
    Shield,
    Trash2,
    Save,
    ExternalLink,
    Search,
    Loader2,
    CheckCircle2,
    XCircle,
    Info,
    Layout
} from 'lucide-react';
import { whatsappApi, Organization, FieldConfig } from '../services/whatsappApi';
import PageHeader from '../components/PageHeader';
import { useToast } from '../components/Toast';

interface OrgConfig {
    whatsapp_business_id: string;
    phone_number_id: string;
    access_token: string;
    meta_app_id: string;
    meta_app_secret: string;
    webhook_verify_token: string;
    timezone: string;
}

const OrganizationManagement: React.FC = () => {
    const navigate = useNavigate();
    const { success: toastSuccess, error: toastError, info: toastInfo } = useToast();
    const [orgs, setOrgs] = useState<Organization[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [searchQuery, setSearchQuery] = useState("");
    
    // Modals
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [showConfigModal, setShowConfigModal] = useState(false);
    
    // Selected Objects
    const [selectedOrg, setSelectedOrg] = useState<Organization | null>(null);
    const [config, setConfig] = useState<OrgConfig | null>(null);
    const [newOrg, setNewOrg] = useState({ name: "", slug: "" });
    
    // Dynamic Fields State
    const [showFieldsModal, setShowFieldsModal] = useState(false);
    const [fieldConfigs, setFieldConfigs] = useState<FieldConfig[]>([]);
    const [newField, setNewField] = useState<Partial<FieldConfig>>({
        field_label: '',
        field_name: '',
        field_type: 'text',
        is_required: false,
        options: []
    });

    const fetchOrgs = async () => {
        setIsLoading(true);
        try {
            const data = await whatsappApi.getOrganizations();
            setOrgs(data);
        } catch (err) {
            console.error(err);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchOrgs();
    }, []);

    const handleOpenConfig = async (org: Organization) => {
        setSelectedOrg(org);
        setShowConfigModal(true);
        setConfig(null); // Loading state inside modal
        try {
            const configData = await whatsappApi.getOrgConfig(org.id);
             setConfig(configData);
        } catch (err) {
             // Handle 404 (no config yet)
             setConfig({ 
                whatsapp_business_id: "", 
                phone_number_id: "", 
                access_token: "", 
                meta_app_id: "",
                meta_app_secret: "",
                webhook_verify_token: "adcom_verify_token",
                timezone: "Asia/Kolkata" 
            });
        }
    };

    const handleSaveConfig = async () => {
        if (!selectedOrg || !config) return;
        setIsSaving(true);
        try {
            await whatsappApi.updateOrgConfig(selectedOrg.id, config);
            toastSuccess('Infrastructure Updated', "Meta credentials and system configuration synchronized.");
            setShowConfigModal(false);
            // Optionally fetch orgs again if status changes
        } catch (err) {
            console.error(err);
            toastError('Sync Failed', "Failed to update Meta infrastructure settings.");
        } finally {
            setIsSaving(false);
        }
    };

    const handleCreateOrg = async () => {
        if (!newOrg.name || !newOrg.slug) return;
        setIsSaving(true);
        try {
            await whatsappApi.createOrganization(newOrg);
            setShowCreateModal(false);
            setNewOrg({ name: "", slug: "" });
            fetchOrgs();
        } catch (err) {
            console.error(err);
        } finally {
            setIsSaving(false);
        }
    };

    const handleOpenFields = async (org: Organization) => {
        setSelectedOrg(org);
        setShowFieldsModal(true);
        try {
            const data = await whatsappApi.getOrganizationFieldConfigs(org.id);
            setFieldConfigs(data);
        } catch (err) {
            setFieldConfigs([]);
        }
    };

    const handleAddField = async () => {
        if (!selectedOrg || !newField.field_label || !newField.field_name) return;
        setIsSaving(true);
        try {
            await whatsappApi.configureCustomField(selectedOrg.id, newField as FieldConfig);
            toastSuccess('Field Injected', "New dynamic field successfully added to organization schema.");
            setNewField({ field_label: '', field_name: '', field_type: 'text', is_required: false, options: [] });
            handleOpenFields(selectedOrg); // Refresh
        } catch (err: any) {
            console.error(err);
            toastError('Injection Failed', (err?.response?.data?.detail || "Unknown error occurred while adding field"));
        } finally {
            setIsSaving(false);
        }
    };

    const handleDeleteField = async (fieldName: string) => {
        if (!selectedOrg) return;
        toastInfo('Processing', "Removing dynamic field from schema...");
        try {
            await whatsappApi.deleteCustomField(selectedOrg.id, fieldName);
            toastSuccess('Field Deleted', "Dynamic field removed from organization schema.");
            handleOpenFields(selectedOrg);
        } catch (err: any) {
            console.error(err);
            toastError('Delete Failed', (err?.response?.data?.detail || "Unknown error occurred during deletion"));
        }
    };

    const filteredOrgs = orgs.filter(o => 
        o.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
        o.slug.toLowerCase().includes(searchQuery.toLowerCase()) ||
        o.id.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div className="space-y-8 animate-in slide-in-from-bottom-4 duration-500 font-sans">
            <PageHeader 
                title="Management Console" 
                description="Global administration of tenants and Meta infrastructure"
                actions={
                    <button 
                        onClick={() => setShowCreateModal(true)}
                        className="flex items-center gap-2 px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-black transition-all shadow-lg active:scale-95 uppercase tracking-widest"
                    >
                        <Plus size={18} strokeWidth={3} />
                        Register Tenant
                    </button>
                }
            />

            <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden flex flex-col">
                <div className="p-6 border-b border-slate-100 dark:border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-50/50 dark:bg-slate-800/30">
                     <div className="flex items-center gap-4">
                        <div className="relative w-full md:w-80">
                            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                            <input 
                                type="text"
                                placeholder="Search by name, slug or ID..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="w-full pl-12 pr-4 py-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl text-[11px] font-black uppercase tracking-wider focus:ring-2 focus:ring-indigo-500 transition-all placeholder:opacity-50"
                            />
                        </div>
                     </div>
                     <div className="px-4 py-1.5 bg-slate-100 dark:bg-slate-800 rounded-full text-[10px] font-black text-slate-500 uppercase tracking-widest">
                        {filteredOrgs.length} Active Organizations
                     </div>
                </div>

                <div className="overflow-x-auto custom-scrollbar min-h-[500px]">
                    <table className="w-full text-left text-sm border-separate border-spacing-0">
                        <thead>
                            <tr className="bg-slate-50/50 dark:bg-slate-800/50 transition-all">
                                <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800">Organization</th>
                                <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800">Unique Identifier</th>
                                <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800 text-center">Status</th>
                                <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800 text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-50 dark:divide-slate-800/50">
                            {isLoading ? (
                                <tr className="animate-pulse">
                                    <td colSpan={4} className="py-24 text-center">
                                        <Loader2 className="animate-spin text-indigo-500 mx-auto mb-4" size={32} />
                                        <p className="text-[10px] font-black uppercase tracking-widest text-slate-400">Decrypting Registry...</p>
                                    </td>
                                </tr>
                            ) : filteredOrgs.map(org => (
                                <tr key={org.id} className="hover:bg-indigo-50/30 dark:hover:bg-indigo-500/5 transition-all group">
                                    <td className="px-8 py-5">
                                        <div className="flex items-center gap-4">
                                            <div className="w-10 h-10 bg-indigo-500/10 rounded-xl flex items-center justify-center text-indigo-600 font-black text-sm border border-indigo-500/10">
                                                {org.name.charAt(0).toUpperCase()}
                                            </div>
                                            <div>
                                                <p className="text-sm font-black text-slate-900 dark:text-white">{org.name}</p>
                                                <p className="text-[11px] font-bold text-slate-400 uppercase tracking-tighter">/{org.slug}</p>
                                            </div>
                                        </div>
                                    </td>
                                    <td className="px-8 py-5">
                                        <code className="px-2 py-1 bg-slate-50 dark:bg-slate-800/80 rounded-md text-[9px] font-bold text-slate-400 border border-slate-200/50 dark:border-slate-700/50 font-mono">
                                            {org.id}
                                        </code>
                                    </td>
                                    <td className="px-8 py-5 text-center">
                                        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-[9px] font-black uppercase tracking-widest border border-emerald-500/20">
                                            <div className="w-1 h-1 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)]" />
                                            Active Tenant
                                        </span>
                                    </td>
                                    <td className="px-8 py-5 text-right">
                                        <div className="flex items-center justify-end gap-2 transition-all">
                                            <button 
                                                onClick={() => handleOpenFields(org)}
                                                className="flex items-center gap-2 px-4 py-2.5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all shadow-sm hover:bg-slate-50"
                                            >
                                                <Layout size={14} className="text-violet-500" />
                                                Fields
                                            </button>
                                            <button 
                                                onClick={() => handleOpenConfig(org)}
                                                className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-[10px] font-black uppercase tracking-widest transition-all shadow-md active:scale-95"
                                            >
                                                <Settings size={14} className="animate-spin-slow" />
                                                Infra
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Dynamic Fields Management Modal */}
            {showFieldsModal && selectedOrg && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-md animate-in fade-in duration-300">
                    <div className="bg-white dark:bg-slate-900 w-full max-w-4xl rounded-[32px] shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden animate-in zoom-in-95 duration-300">
                        <div className="p-8 border-b border-slate-100 dark:border-slate-800 bg-violet-600 flex justify-between items-center text-white">
                            <div>
                                <h3 className="text-2xl font-black tracking-tight uppercase">Custom Schema Configuration</h3>
                                <p className="text-violet-100/60 text-[10px] font-black uppercase tracking-widest mt-1">Tenant: {selectedOrg.name}</p>
                            </div>
                            <button onClick={() => setShowFieldsModal(false)} className="p-2 hover:bg-white/10 rounded-full transition-all"><XCircle size={24} /></button>
                        </div>
                        
                        <div className="flex flex-col md:flex-row h-[60vh]">
                            {/* Left: Current Fields */}
                            <div className="flex-1 p-8 border-r border-slate-100 dark:border-slate-800 overflow-y-auto custom-scrollbar">
                                <span className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] mb-6 block">Active Dynamic Fields</span>
                                <div className="space-y-4">
                                    {fieldConfigs.length === 0 && (
                                        <div className="py-20 text-center text-slate-300 italic text-sm">No custom fields defined for this tenant.</div>
                                    )}
                                    {fieldConfigs.map(f => (
                                        <div key={f.field_name} className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800/50 rounded-2xl border border-slate-200 dark:border-slate-700">
                                            <div className="flex items-center gap-4">
                                                <div className="w-8 h-8 bg-violet-500/10 text-violet-500 rounded-lg flex items-center justify-center font-black text-xs">{f.field_type.charAt(0).toUpperCase()}</div>
                                                <div>
                                                    <p className="text-sm font-black text-slate-900 dark:text-white">{f.field_label} {f.is_required && <span className="text-rose-500">*</span>}</p>
                                                    <p className="text-[10px] text-slate-400 font-bold uppercase tracking-tighter">{f.field_name}</p>
                                                </div>
                                            </div>
                                            <button onClick={() => handleDeleteField(f.field_name)} className="p-2 text-slate-300 hover:text-rose-500 transition-colors"><Trash2 size={16} /></button>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* Right: Add New Field */}
                            <div className="w-full md:w-80 bg-slate-50/50 dark:bg-slate-800/30 p-8 space-y-6">
                                <span className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] mb-2 block">Define New Field</span>
                                <AdminField label="Field Label" value={newField.field_label || ''} onChange={v => setNewField({...newField, field_label: v})} placeholder="e.g. Member ID" />
                                <AdminField label="Database Key (Unique)" value={newField.field_name || ''} onChange={v => setNewField({...newField, field_name: v.toLowerCase().replace(/ /g, '_')})} placeholder="member_id" />
                                
                                <div className="space-y-2">
                                    <label className="text-[10px] font-black uppercase tracking-widest text-slate-400 ml-1">Input Type</label>
                                    <select 
                                        className="w-full px-5 py-3.5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl text-xs font-bold outline-none focus:ring-4 focus:ring-violet-500/10"
                                        value={newField.field_type}
                                        onChange={e => setNewField({...newField, field_type: e.target.value as any})}
                                    >
                                        <option value="text">Standard Text</option>
                                        <option value="number">Numeric Value</option>
                                        <option value="select">Dropdown Menu</option>
                                    </select>
                                </div>

                                <label className="flex items-center gap-3 cursor-pointer p-4 bg-white dark:bg-slate-800 rounded-2xl border border-slate-200 dark:border-slate-700 transition-all hover:bg-slate-50">
                                    <input type="checkbox" checked={newField.is_required} onChange={e => setNewField({...newField, is_required: e.target.checked})} className="w-4 h-4 rounded text-violet-600 focus:ring-violet-500" />
                                    <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">Mark as Required</span>
                                </label>

                                <button 
                                    onClick={handleAddField}
                                    disabled={isSaving || !newField.field_label || !newField.field_name}
                                    className="w-full py-4 bg-violet-600 text-white rounded-2xl text-[10px] font-black uppercase tracking-widest hover:bg-violet-700 transition-all shadow-xl shadow-violet-500/20 disabled:opacity-50"
                                >
                                    {isSaving ? <Loader2 className="animate-spin mx-auto" /> : "Inject into Schema"}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Infrastructure Config Modal (Popup) */}
            {showConfigModal && selectedOrg && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-md animate-in fade-in duration-300">
                    <div className="bg-white dark:bg-slate-900 w-full max-w-2xl rounded-[32px] shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden animate-in zoom-in-95 duration-300">
                        <div className="p-8 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 flex justify-between items-center">
                            <div className="flex items-center gap-4">
                                <div className="w-12 h-12 bg-indigo-600 rounded-2xl flex items-center justify-center text-white shadow-lg font-black text-xl">
                                    {selectedOrg.name.charAt(0)}
                                </div>
                                <div>
                                    <h3 className="text-xl font-black text-slate-900 dark:text-white leading-none mb-1 uppercase tracking-tight">{selectedOrg.name}</h3>
                                    <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">{selectedOrg.id}</p>
                                </div>
                            </div>
                            <button 
                                onClick={() => setShowConfigModal(false)}
                                className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-full transition-all text-slate-400"
                            >
                                <XCircle size={24} />
                            </button>
                        </div>

                        <div className="p-8 space-y-8 max-h-[70vh] overflow-y-auto custom-scrollbar">
                            {!config ? (
                                <div className="py-20 flex flex-col items-center justify-center text-center space-y-4">
                                     <Loader2 className="animate-spin text-indigo-500" size={40} />
                                     <p className="text-[11px] font-black uppercase tracking-widest text-slate-400">Loading Infrastructure Data...</p>
                                </div>
                            ) : (
                                <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
                                    <div className="bg-amber-500/5 border border-amber-500/20 p-5 rounded-2xl flex gap-4 items-start">
                                        <Shield className="text-amber-600 shrink-0 mt-0.5" size={20} />
                                        <div className="space-y-1">
                                            <p className="text-xs font-black uppercase tracking-widest text-amber-700 dark:text-amber-400">Meta Infrastructure Sync</p>
                                            <p className="text-[11px] text-amber-600/80 font-bold leading-relaxed">
                                                These credentials allow API access to this tenant's Meta ecosystem. Required scopes: <code className="px-1 text-red-500">whatsapp_business_management</code>
                                            </p>
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                         <AdminField 
                                            label="WhatsApp Business ID" 
                                            value={config.whatsapp_business_id || ""}
                                            onChange={(v) => setConfig({...config, whatsapp_business_id: v})}
                                            placeholder="Enter 15-digit WABA ID"
                                        />
                                        <AdminField 
                                            label="Phone Number ID" 
                                            value={config.phone_number_id || ""}
                                            onChange={(v) => setConfig({...config, phone_number_id: v})}
                                            placeholder="Enter Meta Phone ID"
                                        />
                                        <AdminField 
                                            label="Meta App ID" 
                                            value={config.meta_app_id || ""}
                                            onChange={(v) => setConfig({...config, meta_app_id: v})}
                                            placeholder="Enter 15-digit App ID"
                                        />
                                        <AdminField 
                                            label="Webhook Verify Token" 
                                            value={config.webhook_verify_token || ""}
                                            onChange={(v) => setConfig({...config, webhook_verify_token: v})}
                                            placeholder="adcom_verify_token"
                                        />
                                        <div className="md:col-span-2">
                                            <AdminField 
                                                label="Meta App Secret" 
                                                value={config.meta_app_secret || ""}
                                                onChange={(v) => setConfig({...config, meta_app_secret: v})}
                                                placeholder="Enter App Secret"
                                                isSecret
                                            />
                                        </div>
                                        <div className="md:col-span-2">
                                            <AdminField 
                                                label="Permanent Access Token" 
                                                value={config.access_token || ""}
                                                onChange={(v) => setConfig({...config, access_token: v})}
                                                placeholder="EAAG... (Must be permanent token)"
                                                isSecret
                                            />
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>

                        <div className="p-8 bg-slate-50/50 dark:bg-slate-800/30 border-t border-slate-100 dark:border-slate-800 flex justify-between items-center">
                            <button className="flex items-center gap-2 text-rose-500 font-black text-[10px] uppercase tracking-widest hover:opacity-80 transition-all opacity-40 hover:opacity-100">
                                <Trash2 size={16} />
                                SUSPEND TENANT
                            </button>
                            <div className="flex gap-4">
                                <button 
                                    onClick={() => setShowConfigModal(false)}
                                    className="px-6 py-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-500 rounded-xl text-[10px] font-black uppercase tracking-widest hover:bg-slate-100 transition-all"
                                >
                                    Cancel
                                </button>
                                <button 
                                    onClick={handleSaveConfig}
                                    disabled={isSaving || !config}
                                    className="flex items-center gap-2 px-8 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-[10px] font-black uppercase tracking-widest transition-all shadow-lg active:scale-95 disabled:opacity-50"
                                >
                                    {isSaving ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />}
                                    Update Infrastructure
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Create Org Modal */}
            {showCreateModal && (
                <div className="fixed inset-0 z-[101] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-md animate-in fade-in duration-300">
                    <div className="bg-white dark:bg-slate-900 w-full max-w-lg rounded-[32px] shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden animate-in zoom-in-95 duration-300">
                        <div className="p-8 border-b border-slate-100 dark:border-slate-800 bg-indigo-600">
                            <h3 className="text-2xl font-black text-white tracking-tight">Onboard New Tenant</h3>
                            <p className="text-white/60 text-[10px] font-black uppercase tracking-[0.2em] mt-1">Tenant provisioning protocol</p>
                        </div>
                        <div className="p-8 space-y-6">
                            <AdminField label="Organization Full Name" value={newOrg.name} onChange={(v) => setNewOrg({...newOrg, name: v})} placeholder="e.g. Adcom Partner Co." />
                            <AdminField label="Public Identifier (URL Slug)" value={newOrg.slug} onChange={(v) => setNewOrg({...newOrg, slug: v})} placeholder="partner-slug" />
                            <div className="flex gap-3 bg-blue-500/5 p-4 rounded-xl border border-blue-500/10">
                                <Info size={18} className="text-blue-500 shrink-0" />
                                <p className="text-[10px] text-blue-600 font-bold leading-relaxed uppercase tracking-tighter">
                                    Slug will be used for isolation. Choose a short, alphanumeric string.
                                </p>
                            </div>
                        </div>
                        <div className="p-8 flex gap-4 bg-slate-50/50 dark:bg-slate-800/30">
                            <button 
                                onClick={() => setShowCreateModal(false)}
                                className="flex-1 py-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-500 rounded-2xl text-[10px] font-black uppercase tracking-widest hover:bg-slate-100 transition-all"
                            >
                                ABORT
                            </button>
                            <button 
                                onClick={handleCreateOrg}
                                disabled={isSaving || !newOrg.name || !newOrg.slug}
                                className="flex-1 py-4 bg-indigo-600 text-white rounded-2xl text-[10px] font-black uppercase tracking-widest hover:bg-indigo-700 transition-all shadow-xl shadow-indigo-500/20 disabled:opacity-50"
                            >
                                {isSaving ? <Loader2 className="animate-spin mx-auto" /> : "PROVISION TENANT"}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

interface AdminFieldProps {
    label: string;
    value: string;
    onChange: (value: string) => void;
    placeholder?: string;
    isSecret?: boolean;
}

const AdminField = ({ label, value, onChange, placeholder, isSecret }: AdminFieldProps) => {
    const [isVisible, setIsVisible] = useState(!isSecret);
    return (
        <div className="space-y-2 flex-1">
            <label className="text-[10px] font-black uppercase tracking-widest text-slate-400 ml-1 block">{label}</label>
            <div className="relative group">
                <input 
                    type={isVisible ? "text" : "password"}
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    placeholder={placeholder}
                    className="w-full px-5 py-3.5 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-2xl text-xs font-bold focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all group-hover:border-slate-300 dark:group-hover:border-slate-600 placeholder:opacity-40"
                />
                {isSecret && (
                    <button 
                        onClick={() => setIsVisible(!isVisible)}
                        className="absolute right-4 top-1/2 -translate-y-1/2 text-[9px] font-black uppercase tracking-widest text-slate-400 hover:text-indigo-500 transition-all"
                    >
                        {isVisible ? "Hide" : "Show"}
                    </button>
                )}
            </div>
        </div>
    );
};

export default OrganizationManagement;
