import React, { useState, useEffect } from 'react';
import { Upload, FileText, Database, Send, CheckCircle2, Loader2, Search, Filter, Trash2, UserPlus, ChevronLeft, ChevronRight, X, List, AlertCircle, Edit2, MoreVertical, ChevronUp, ChevronDown, ArrowUpDown, Calendar } from 'lucide-react';
import { whatsappApi } from '../services/whatsappApi';
import { useToast } from '../components/Toast';
import PageHeader from '../components/PageHeader';
import PhoneInput from 'react-phone-input-2';
import 'react-phone-input-2/lib/style.css';
import { CustomSelect } from '../components/CustomSelect';
import { CustomDatePicker } from '../components/CustomDatePicker';
import { COUNTRY_CODES } from '../components/CountryCodeSelector';
interface ContactList {
    id: string;
    name: string;
    count?: number;
}

const CreateListModal = ({ onClose, onSave }: { onClose: () => void; onSave: () => void }) => {
    const [name, setName] = useState('');
    const [description, setDescription] = useState('');
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSave = async (e: React.FormEvent) => {
        e.preventDefault();
        if (name.trim().length < 2) return;
        setSaving(true);
        try {
            await whatsappApi.createContactList(name, description);
            onSave();
            onClose();
        } catch (err: any) {
            setError(err.response?.data?.detail || "Failed to create list.");
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="fixed top-[-5vh] left-[-5vw] w-[110vw] h-[110vh] bg-slate-900/60 backdrop-blur-md z-[9999] flex items-center justify-center p-4 m-0">
            <div className="bg-white dark:bg-slate-900 w-full max-w-md rounded-xl border border-slate-200 dark:border-slate-800 shadow-2xl p-8 relative">
                <button onClick={onClose} className="absolute top-6 right-6 p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-all text-slate-400"><X size={20} /></button>
                <div className="mb-6">
                    <h2 className="text-xl font-bold text-slate-900 dark:text-white">New List</h2>
                    <p className="text-slate-500 text-sm mt-1">Create a group for targeted messaging</p>
                </div>
                <form onSubmit={handleSave} className="space-y-5">
                    {error && <div className="p-3 bg-rose-50 border border-rose-100 text-rose-600 text-xs font-bold rounded-lg flex items-center gap-2"><AlertCircle size={14} /> {error}</div>}
                    <div className="space-y-1.5">
                        <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">List Name</label>
                        <input autoFocus value={name} onChange={e => setName(e.target.value)} placeholder="e.g. VIP Customers" className="w-full p-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all" />
                    </div>
                    <div className="space-y-1.5">
                        <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Description</label>
                        <textarea value={description} onChange={e => setDescription(e.target.value)} placeholder="Optional details..." className="w-full p-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all h-24 resize-none" />
                    </div>
                    <button disabled={name.length < 2 || saving} type="submit" className="w-full bg-indigo-600 py-3 rounded-lg text-white font-bold hover:bg-indigo-700 transition-all shadow-md flex items-center justify-center gap-2">
                        {saving ? <Loader2 size={18} className="animate-spin" /> : "Save List"}
                    </button>
                </form>
            </div>
        </div>
    );
};

const BulkUploadModal = ({ onClose, onSave }: { onClose: () => void; onSave: () => void }) => {
    const [file, setFile] = useState<File | null>(null);
    const [uploading, setUploading] = useState(false);
    const [result, setResult] = useState<any>(null);

    const { success, error: toastError } = useToast();

    const handleUpload = async () => {
        if (!file) return;
        setUploading(true);
        try {
            const res = await whatsappApi.bulkImport(file, undefined, true);
            setResult(res.data);
            setFile(null);
            success('Import complete', `${res.data?.success ?? 0} records imported successfully.`);
            setTimeout(() => {
                onSave();
                if (!res.data.failed) onClose();
            }, 1500);
        } catch (err: any) {
            toastError('Upload failed', err?.response?.data?.detail || err.message || 'Could not import file.');
        } finally { setUploading(false); }
    };

    return (
        <div className="fixed top-[-5vh] left-[-5vw] w-[110vw] h-[110vh] bg-slate-900/60 backdrop-blur-md z-[9999] flex items-center justify-center p-4 m-0">
            <div className="bg-white dark:bg-slate-900 w-full max-w-md rounded-xl border border-slate-200 dark:border-slate-800 shadow-2xl p-8 relative">
                <button onClick={onClose} className="absolute top-6 right-6 p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-all text-slate-400"><X size={20} /></button>
                <div className="mb-6">
                    <h2 className="text-xl font-bold text-slate-900 dark:text-white">Bulk Import</h2>
                    <div className="flex justify-between items-center mt-1">
                        <p className="text-sm text-slate-500">Upload CSV or Excel file</p>
                        <button 
                            onClick={() => {
                                const headers = "phone_number,name,company_name,lead_source,city,customer_category,customer_stage,product_service_interest\n";
                                const sample = "+918939590459,Aravindhan,Adcom,Website,Chennai,marketing,lead,Business Consulting";
                                const blob = new Blob([headers + sample], { type: 'text/csv' });
                                const url = window.URL.createObjectURL(blob);
                                const a = document.createElement('a');
                                a.href = url;
                                a.download = 'adcom_contacts_sample.csv';
                                a.click();
                            }}
                            className="text-[10px] font-bold text-indigo-600 hover:text-indigo-700 uppercase tracking-wider flex items-center gap-1 bg-indigo-50 dark:bg-indigo-500/10 px-2 py-1 rounded"
                        >
                            <FileText size={12} /> Download Sample
                        </button>
                    </div>
                </div>
                <div className="space-y-6">
                    <label className="block w-full border-2 border-dashed border-slate-200 dark:border-slate-700 rounded-xl p-10 hover:border-indigo-500 cursor-pointer transition-all text-center">
                        <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} className="hidden" />
                        {file ? (
                            <div className="text-indigo-600 flex flex-col items-center gap-2">
                                <FileText size={48}/>
                                <span className="text-xs font-bold truncate max-w-[250px]">{file.name}</span>
                            </div>
                        ) : (
                            <div className="text-slate-400 flex flex-col items-center gap-2">
                                <Upload size={48}/>
                                <span className="text-xs font-bold uppercase tracking-widest">Select Data File</span>
                            </div>
                        )}
                    </label>
                    <button onClick={handleUpload} disabled={!file || uploading} className="w-full py-3 bg-indigo-600 text-white rounded-lg font-bold shadow-md hover:bg-indigo-700 disabled:opacity-40 transition-all flex items-center justify-center gap-2">
                        {uploading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
                        {uploading ? "Ingesting..." : "Initialize Upload"}
                    </button>
                    {result && (
                        <div className="space-y-3">
                            <div className="p-4 bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-100 dark:border-emerald-500/20 rounded-lg">
                                <p className="text-emerald-700 dark:text-emerald-400 font-bold text-xs flex items-center gap-2">
                                    <CheckCircle2 size={14}/> Import Processed by {result.uploaded_by || 'you'}
                                </p>
                                <p className="text-[11px] text-emerald-600/70 mt-1">
                                    {result.success} accepted, {result.updated} updated, {result.duplicates} skipped.
                                </p>
                            </div>

                            {(result.duplicate_list?.length > 0 || result.invalid_list?.length > 0) && (
                                <div className="max-h-48 overflow-y-auto border border-slate-200 dark:border-slate-800 rounded-xl bg-slate-50/50 dark:bg-slate-900/50 p-4 space-y-4 custom-scrollbar">
                                    {result.invalid_list?.length > 0 && (
                                        <div className="space-y-1.5">
                                            <h4 className="text-[10px] font-black text-rose-500 uppercase tracking-[0.2em]">Invalid Fields</h4>
                                            {result.invalid_list.map((err: any, idx: number) => (
                                                <div key={idx} className="text-[10px] flex justify-between border-b border-slate-100 dark:border-slate-800 pb-1">
                                                    <span className="text-slate-600 dark:text-slate-400 font-mono">{err.phone || `Row ${err.row}`}</span>
                                                    <span className="text-rose-600 font-bold">{err.error}</span>
                                                </div>
                                            ))}
                                        </div>
                                    )}

                                    {result.duplicate_list?.length > 0 && (
                                        <div className="space-y-1.5">
                                            <h4 className="text-[10px] font-black text-amber-500 uppercase tracking-[0.2em]">Duplicates Skipped</h4>
                                            <div className="space-y-1">
                                                {result.duplicate_list.map((item: any, idx: number) => (
                                                    <div key={idx} className="flex justify-between items-center text-[10px] bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 px-2 py-1 rounded">
                                                        <span className="font-bold text-slate-700 dark:text-slate-200">
                                                            {typeof item === 'object' ? (item.name || 'Unnamed') : 'Unnamed'}
                                                        </span>
                                                        <span className="font-mono text-slate-500">
                                                            +{ (typeof item === 'object' ? item.phone : item).replace(/\+/g, '')}
                                                        </span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

const ContactModal = ({ onClose, onSave, contact }: { onClose: () => void; onSave: () => void; contact?: any }) => {
    const initialPhone = contact?.phone_number ? contact.phone_number.replace(/\+/g, '') : '91';
    const [fullPhone, setFullPhone] = useState(initialPhone);
    const [name, setName] = useState(contact?.name || '');
    const [category, setCategory] = useState(contact?.category || 'General');
    
    // New Fields State
    const [companyName, setCompanyName] = useState(contact?.company_name || '');
    const [leadSource, setLeadSource] = useState(contact?.lead_source || '');
    const [dob, setDob] = useState(contact?.date_of_birth ? new Date(contact.date_of_birth).toISOString().split('T')[0] : '');
    const [custCategory, setCustCategory] = useState(contact?.customer_category || '');
    const [custStage, setCustStage] = useState(contact?.customer_stage || '');
    const [city, setCity] = useState(contact?.city || '');
    const [interest, setInterest] = useState(contact?.product_service_interest || '');
    
    // Consent Logic: Default to opted_in if empty or matches standard string
    const STANDARD_CONSENT = "Opted-in via WhatsApp";
    const [consentChoice, setConsentChoice] = useState<'opted_in' | 'manual'>(
        (!contact?.consent_confirmation || contact.consent_confirmation === STANDARD_CONSENT) ? 'opted_in' : 'manual'
    );
    const [consent, setConsent] = useState(contact?.consent_confirmation || STANDARD_CONSENT);

    const [saving, setSaving] = useState(false);
    const { success: toastSuccess, error: toastError } = useToast();

    // Sync consent text when choice changes
    useEffect(() => {
        if (consentChoice === 'opted_in') {
            setConsent(STANDARD_CONSENT);
        }
    }, [consentChoice]);

    const handleSave = async (e: React.FormEvent) => {
        e.preventDefault();

        // ✅ Validation
        const cleanPhone = fullPhone.replace(/\D/g, '');
        if (cleanPhone.length < 8 || cleanPhone.length > 18) {
            toastError('Invalid Phone', 'Please enter a valid phone number (8-15 digits).');
            return;
        }

        setSaving(true);
        const payload: any = {
            name,
            phone_number: cleanPhone,
            category: category,
            company_name: companyName,
            lead_source: leadSource,
            date_of_birth: dob || undefined,
            customer_category: custCategory,
            customer_stage: custStage,
            city,
            product_service_interest: interest,
            consent_confirmation: consent
        };

        try {
            if (contact) {
                await whatsappApi.updateContact(contact.id, payload);
                toastSuccess('Updated', 'Contact information saved.');
            } else {
                await whatsappApi.createContact({ ...payload, upsert: true });
                toastSuccess('Created', 'New contact added to registry.');
            }
            onSave();
            onClose();
        } catch (err: any) {
            toastError('Save Failed', err.response?.data?.detail || "Failed to save contact.");
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="fixed top-[-5vh] left-[-5vw] w-[110vw] h-[110vh] bg-slate-900/60 backdrop-blur-md z-[9999] flex items-center justify-center p-4 m-0">
            <div className="bg-white dark:bg-slate-900 w-full max-w-lg rounded-3xl border border-slate-200 dark:border-slate-800 shadow-2xl p-0 relative overflow-hidden scale-in-center">
                <button onClick={onClose} className="absolute top-6 right-6 p-2 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition-all text-slate-400 z-10"><X size={20} /></button>
                
                <div className="px-10 pt-10 pb-6 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
                    <h2 className="text-2xl font-black text-slate-900 dark:text-white tracking-tight">{contact ? "Identity Profile" : "New Contact"}</h2>
                    <p className="text-sm text-slate-500 font-medium mt-1 uppercase tracking-widest text-[10px]">{contact ? "Update existing registry member" : "Manually register a single node"}</p>
                </div>

                <form onSubmit={handleSave} className="p-10 space-y-8 max-h-[70vh] overflow-auto custom-scrollbar">
                    {/* SECTION: BASIC IDENTITY */}
                    <div className="space-y-4">
                        <div className="flex items-center gap-2 mb-2">
                            <div className="w-1.5 h-1.5 rounded-full bg-indigo-500 shadow-[0_0_8px_rgba(99,102,241,0.6)]"></div>
                            <h3 className="text-[10px] font-black text-indigo-600 dark:text-indigo-400 uppercase tracking-[0.2em]">Basic Identity</h3>
                        </div>
                        
                        <div className="space-y-1.5">
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest ml-1">Phone Number</label>
                            <div className="react-phone-input-custom-wrapper">
                                <PhoneInput
                                    country={'in'}
                                    value={fullPhone}
                                    onChange={phone => setFullPhone(phone)}
                                    disabled={!!contact}
                                    enableSearch={true}
                                    searchPlaceholder="Search country..."
                                    inputProps={{ autoFocus: !contact }}
                                    containerClass="w-full flex"
                                    inputClass="!w-full !p-3 !bg-slate-50/50 dark:!bg-slate-800/30 !border !border-slate-200 dark:!border-slate-700 !rounded-xl !outline-none focus:!ring-2 focus:!ring-indigo-500/20 transition-all font-mono !pl-12 !h-[48px] text-slate-900 dark:text-white"
                                    buttonClass="!bg-slate-50/50 dark:!bg-slate-800/30 !border !border-slate-200 dark:!border-slate-700 !rounded-l-xl hover:!bg-slate-100 dark:hover:!bg-slate-700"
                                    dropdownClass="!bg-white dark:!bg-slate-900 !border-slate-200 dark:!border-slate-700 !text-slate-900 dark:!text-white custom-scrollbar"
                                />
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-1.5">
                                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest ml-1">Full Identity</label>
                                <input autoFocus={!!contact} value={name} onChange={e => setName(e.target.value)} placeholder="Full Name" className="w-full h-[48px] px-4 bg-slate-50/50 dark:bg-slate-800/30 border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all text-sm" />
                            </div>
                            <div className="space-y-1.5">
                                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest ml-1">Local Category</label>
                                <input value={category} onChange={e => setCategory(e.target.value)} placeholder="e.g. VIP, WH" className="w-full h-[48px] px-4 bg-slate-50/50 dark:bg-slate-800/30 border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all text-sm" />
                            </div>
                        </div>
                    </div>

                    {/* SECTION: SEGMENTATION DATA */}
                    <div className="space-y-4 pt-4 border-t border-slate-100 dark:border-slate-800">
                        <div className="flex items-center gap-2 mb-2">
                           <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]"></div>
                           <h3 className="text-[10px] font-black text-emerald-600 dark:text-emerald-400 uppercase tracking-[0.2em]">Segmentation Data</h3>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-1.5">
                                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest ml-1">Company Name</label>
                                <input value={companyName} onChange={e => setCompanyName(e.target.value)} placeholder="Company Ltd" className="w-full h-[48px] px-4 bg-slate-50/50 dark:bg-slate-800/30 border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all text-sm" />
                            </div>
                            <div className="space-y-1.5">
                                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest ml-1">Lead Source</label>
                                <input value={leadSource} onChange={e => setLeadSource(e.target.value)} placeholder="Website/Ads" className="w-full h-[48px] px-4 bg-slate-50/50 dark:bg-slate-800/30 border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all text-sm" />
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <CustomDatePicker
                                label="Date of Birth"
                                value={dob}
                                onChange={setDob}
                                placeholder="mm/dd/yyyy"
                            />
                            <div className="space-y-1.5">
                                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest ml-1">City</label>
                                <input value={city} onChange={e => setCity(e.target.value)} placeholder="e.g. Delhi" className="w-full h-[48px] px-4 bg-slate-50/50 dark:bg-slate-800/30 border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all text-sm" />
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <CustomSelect
                                label="Customer Category"
                                value={custCategory}
                                onChange={setCustCategory}
                                options={[
                                    { value: "", label: "Select Category" },
                                    { value: "SI", label: "SI" },
                                    { value: "Distributor", label: "Distributor" },
                                    { value: "Super Stockist", label: "Super Stockist" },
                                ]}
                            />
                            <CustomSelect
                                label="Customer Stage"
                                value={custStage}
                                onChange={setCustStage}
                                options={[
                                    { value: "", label: "Select Stage" },
                                    { value: "Prospective", label: "Prospective" },
                                    { value: "New", label: "New" },
                                    { value: "Old", label: "Old" },
                                    { value: "Cancelled", label: "Cancelled" },
                                ]}
                            />
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest ml-1">Interest / Intent</label>
                            <input value={interest} onChange={e => setInterest(e.target.value)} placeholder="e.g. Real Estate, Consulting" className="w-full h-[48px] px-4 bg-slate-50/50 dark:bg-slate-800/30 border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all text-sm" />
                        </div>
                    </div>

                    {/* SECTION: CONSENT VERIFICATION (Hidden) */}
                </form>

                <div className="p-10 pt-0">
                    <button disabled={saving} type="submit" onClick={handleSave} className="w-full bg-indigo-600 py-4 rounded-2xl text-white font-black uppercase tracking-widest text-xs hover:bg-indigo-700 transition-all shadow-xl shadow-indigo-500/20 active:scale-[0.98] disabled:opacity-50">
                        {saving ? <Loader2 size={20} className="animate-spin mx-auto" /> : (contact ? "Update Identity" : "Save Record")}
                    </button>
                </div>
            </div>
        </div>
    );
};

const Contacts: React.FC = () => {
    const [contacts, setContacts] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(0);
    const [limit] = useState(10);
    const [search, setSearch] = useState('');
    const [showAddModal, setShowAddModal] = useState(false);
    const [showBulkModal, setShowBulkModal] = useState(false);
    const [showListModal, setShowListModal] = useState(false);
    const [selectedContact, setSelectedContact] = useState<any | null>(null);
    const [sort, setSort] = useState<{ column: string; order: 'asc' | 'desc' }>({ column: 'created_at', order: 'desc' });

    const { success, error: toastError } = useToast();

    const fetchContacts = async () => {
        setLoading(true);
        try {
            const res = await whatsappApi.getContacts({ 
                offset: page * limit, 
                limit, 
                search: search || undefined,
                sort_by: sort.column,
                sort_order: sort.order
            });
            setContacts(res.items);
            setTotal(res.total);
        } catch (err: any) {
            toastError('Failed to load contacts', err?.response?.data?.detail || 'Please refresh the page.');
        } finally { setLoading(false); }
    };

    const handleSort = (column: string) => {
        setSort(prev => ({
            column,
            order: prev.column === column && prev.order === 'asc' ? 'desc' : 'asc'
        }));
        setPage(0);
    };

    useEffect(() => { fetchContacts(); }, [page, limit, search, sort]);

    return (
        <div className="space-y-8 font-sans">
            <PageHeader 
                title="Contacts" 
                description="Manage and organize your contact database" 
                actions={
                    <div className="flex gap-3">
                        <button onClick={() => setShowBulkModal(true)} className="flex items-center gap-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 px-4 py-2 rounded-lg text-sm font-bold text-slate-700 dark:text-slate-200 hover:bg-slate-50 transition-all">
                            <Upload size={18}/> Bulk Import
                        </button>
                        <button onClick={() => setShowAddModal(true)} className="flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-bold shadow-sm hover:bg-indigo-700 transition-all">
                            <UserPlus size={18}/> Add Contact
                        </button>
                    </div>
                } 
            />

            <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden flex flex-col">
                <div className="p-4 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center bg-slate-50/50 dark:bg-slate-800/30">
                     <h3 className="text-sm font-bold text-slate-900 dark:text-white">Contact Records</h3>
                     <div className="relative">
                        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                        <input value={search} onChange={e => { setSearch(e.target.value); setPage(0); }} placeholder="Search identity..." className="pl-9 pr-4 py-1 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-[11px] outline-none focus:ring-2 focus:ring-indigo-500/20" />
                     </div>
                </div>
                <div className="h-[55vh] overflow-auto custom-scrollbar relative">
                    <table className="w-full text-left text-sm">
                        <thead className="sticky top-0 z-10 bg-white dark:bg-slate-900 shadow-sm">
                            <tr className="border-b border-slate-100 dark:border-slate-800 text-[10px] font-black text-slate-400 uppercase tracking-[0.15em] whitespace-nowrap">
                                <SortHeader label="Phone Number" column="phone_number" currentSort={sort} onSort={handleSort} />
                                <SortHeader label="Full Identity" column="name" currentSort={sort} onSort={handleSort} />
                                <SortHeader label="Company" column="company_name" currentSort={sort} onSort={handleSort} />
                                <SortHeader label="City" column="city" currentSort={sort} onSort={handleSort} />
                                <SortHeader label="Cust. Category" column="customer_category" currentSort={sort} onSort={handleSort} />
                                <SortHeader label="Stage" column="customer_stage" currentSort={sort} onSort={handleSort} />
                                <SortHeader label="Source" column="lead_source" currentSort={sort} onSort={handleSort} />
                                <SortHeader label="DOB" column="date_of_birth" currentSort={sort} onSort={handleSort} />
                                <SortHeader label="Interest" column="product_service_interest" currentSort={sort} onSort={handleSort} />
                                {/* <SortHeader label="Consent" column="consent_confirmation" currentSort={sort} onSort={handleSort} /> */}
                                <th className="px-5 py-4 bg-white dark:bg-slate-900 text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-50 dark:divide-slate-800/50">
                            {contacts.map(c => {
                                const cleanPhone = String(c.phone_number || '').replace(/\+/g, '');
                                const countryMatch = COUNTRY_CODES.find(cc => cleanPhone.startsWith(cc.code.replace('+', '')));
                                
                                return (
                                <tr key={c.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors group whitespace-nowrap font-bold">
                                    <td className="px-5 py-3 text-slate-900 dark:text-white tabular-nums">
                                        <div className="flex flex-col">
                                            <span className="text-sm flex items-center gap-2">
                                                {countryMatch?.iso ? (
                                                    <img src={`https://flagcdn.com/w20/${countryMatch.iso}.png`} alt={countryMatch.country} className="w-4 flex-shrink-0 rounded-[2px]" />
                                                ) : (
                                                    <span>🌐</span>
                                                )}
                                                <span>+{cleanPhone}</span>
                                            </span>
                                            <span className="text-[10px] text-slate-400 font-medium ml-6">
                                                {countryMatch?.country || 'Global'}
                                            </span>
                                        </div>
                                    </td>
                                    <td className="px-5 py-3 text-slate-900 dark:text-white text-sm">{c.name || '--'}</td>
                                    <td className="px-5 py-3 text-slate-600 dark:text-slate-400 text-sm">{c.company_name || '--'}</td>
                                    <td className="px-5 py-3 text-slate-600 dark:text-slate-400 text-sm">{c.city || '--'}</td>
                                    <td className="px-5 py-3">
                                        <span className="px-2.5 py-1 rounded-md bg-slate-100 dark:bg-slate-800 text-[10px] font-black text-slate-700 dark:text-slate-300">
                                            {c.customer_category || '--'}
                                        </span>
                                    </td>
                                    <td className="px-5 py-3">
                                        <span className={`px-2.5 py-1 rounded-md text-[10px] font-black uppercase ${
                                            c.customer_stage === 'Prospective' ? 'bg-amber-100/50 text-amber-700' : 
                                            c.customer_stage === 'New' ? 'bg-emerald-100/50 text-emerald-700' :
                                            'bg-slate-100 text-slate-500'
                                        }`}>
                                            {c.customer_stage || '--'}
                                        </span>
                                    </td>
                                    <td className="px-5 py-3 text-slate-500 italic text-sm">{c.lead_source || '--'}</td>
                                    <td className="px-5 py-3 text-slate-600 dark:text-slate-400 tabular-nums text-sm">
                                        {c.date_of_birth ? new Date(c.date_of_birth).toLocaleDateString() : '--'}
                                    </td>
                                    <td className="px-5 py-3 text-slate-600 dark:text-slate-400 max-w-[150px] truncate text-sm">{c.product_service_interest || '--'}</td>
                                    {/* <td className="px-5 py-3 text-slate-500 text-[10px]">{c.consent_confirmation || '--'}</td> */}
                                    <td className="px-5 py-3 text-right">
                                        <div className="flex justify-end gap-2">
                                            <button onClick={() => setSelectedContact(c)} className="p-1.5 text-slate-400 hover:text-indigo-600 transition-colors"><Edit2 size={16}/></button>
                                            <button onClick={async () => { if(confirm("Purge record?")) { try { await whatsappApi.deleteContact(c.id); success('Contact deleted'); fetchContacts(); } catch(e: any) { toastError('Delete failed', e?.response?.data?.detail); } } }} className="p-1.5 text-slate-400 hover:text-rose-600 transition-colors"><Trash2 size={16}/></button>
                                        </div>
                                    </td>
                                </tr>
                                );
                            })}
                        </tbody>
                    </table>
                    {loading && <div className="flex items-center justify-center py-24"><Loader2 className="animate-spin text-indigo-600" size={32} /></div>}
                    {!loading && contacts.length === 0 && <div className="flex flex-col items-center justify-center py-24 text-slate-400 space-y-2"><Database size={40} className="mb-2 opacity-20"/><p className="text-sm font-medium">No records found in database</p></div>}
                </div>
                {total > 0 && (
                    <div className="p-4 border-t border-slate-100 dark:border-slate-800 flex justify-between items-center bg-slate-50/30">
                        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest pl-2">Sync: {page * limit + 1} - {Math.min((page + 1) * limit, total)} of {total}</span>
                        <div className="flex gap-2">
                            <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0} className="p-2 border border-slate-200 dark:border-slate-700 rounded-lg disabled:opacity-20 hover:bg-white transition-all shadow-sm"><ChevronLeft size={16}/></button>
                            <button onClick={() => setPage(p => p + 1)} disabled={(page + 1) * limit >= total} className="p-2 border border-slate-200 dark:border-slate-700 rounded-lg disabled:opacity-20 hover:bg-white transition-all shadow-sm"><ChevronRight size={16}/></button>
                        </div>
                    </div>
                )}
            </div>

            {showAddModal && <ContactModal onClose={() => setShowAddModal(false)} onSave={fetchContacts} />}
            {showBulkModal && <BulkUploadModal onClose={() => setShowBulkModal(false)} onSave={fetchContacts} />}
            {selectedContact && <ContactModal contact={selectedContact} onClose={() => setSelectedContact(null)} onSave={fetchContacts} />}
            {showListModal && <CreateListModal onClose={() => setShowListModal(false)} onSave={() => {}} />}
        </div>
    );
};

const SortHeader = ({ label, column, currentSort, onSort }: { label: string; column: string; currentSort: any; onSort: (col: string) => void }) => {
    const isActive = currentSort.column === column;
    return (
        <th 
            className="px-5 py-4 bg-white dark:bg-slate-900 cursor-pointer hover:bg-slate-50/80 dark:hover:bg-slate-800 transition-colors group"
            onClick={() => onSort(column)}
        >
            <div className="flex items-center justify-between gap-2 min-w-[max-content]">
                <span className={`text-[10px] font-black uppercase tracking-wider ${isActive ? 'text-indigo-600' : 'text-slate-400'}`}>
                    {label}
                </span>
                <div className={`flex-shrink-0 transition-opacity ${isActive ? 'text-indigo-600 opacity-100' : 'text-slate-300 opacity-40 group-hover:opacity-100'}`}>
                    {isActive ? (
                        currentSort.order === 'asc' ? <ChevronUp size={14} className="stroke-[3px]" /> : <ChevronDown size={14} className="stroke-[3px]" />
                    ) : (
                        <ArrowUpDown size={12} />
                    )}
                </div>
            </div>
        </th>
    );
};

export default Contacts;
