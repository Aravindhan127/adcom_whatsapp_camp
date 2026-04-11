import React, { useState, useEffect } from 'react';
import { Upload, FileText, Database, Send, CheckCircle2, Loader2, Search, Filter, Trash2, UserPlus, ChevronLeft, ChevronRight, X, List, AlertCircle, Edit2, MoreVertical } from 'lucide-react';
import { whatsappApi } from '../services/whatsappApi';
import PageHeader from '../components/PageHeader';

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
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
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

    const handleUpload = async () => {
        if (!file) return;
        setUploading(true);
        try {
            const res = await whatsappApi.bulkImport(file, undefined, true);
            setResult(res.data);
            setFile(null);
            setTimeout(() => {
                onSave();
                if (!res.data.failed) onClose();
            }, 1500);
        } catch (err) { console.error(err); } finally { setUploading(false); }
    };

    return (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-white dark:bg-slate-900 w-full max-w-md rounded-xl border border-slate-200 dark:border-slate-800 shadow-2xl p-8 relative">
                <button onClick={onClose} className="absolute top-6 right-6 p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-all text-slate-400"><X size={20} /></button>
                <div className="mb-6">
                    <h2 className="text-xl font-bold text-slate-900 dark:text-white">Bulk Import</h2>
                    <p className="text-sm text-slate-500 mt-1">Upload CSV or Excel file to add multiple contacts</p>
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
                        <div className="p-4 bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-100 dark:border-emerald-500/20 rounded-lg">
                            <p className="text-emerald-700 dark:text-emerald-400 font-bold text-xs flex items-center gap-2"><CheckCircle2 size={14}/> Successfully Processed</p>
                            <p className="text-[11px] text-emerald-600/70 mt-1">{result.success} records added to registry.</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

const ContactModal = ({ onClose, onSave, contact }: { onClose: () => void; onSave: () => void; contact?: any }) => {
    const [phone, setPhone] = useState(contact?.phone_number || '');
    const [name, setName] = useState(contact?.name || '');
    const [category, setCategory] = useState(contact?.category || 'General');
    const [selectedList, setSelectedList] = useState(contact?.list_id || '');
    
    // New Fields State
    const [companyName, setCompanyName] = useState(contact?.company_name || '');
    const [leadSource, setLeadSource] = useState(contact?.lead_source || '');
    const [dob, setDob] = useState(contact?.date_of_birth ? new Date(contact.date_of_birth).toISOString().split('T')[0] : '');
    const [custCategory, setCustCategory] = useState(contact?.customer_category || '');
    const [custStage, setCustStage] = useState(contact?.customer_stage || '');
    const [city, setCity] = useState(contact?.city || '');
    const [interest, setInterest] = useState(contact?.product_service_interest || '');
    const [consent, setConsent] = useState(contact?.consent_confirmation || '');

    const [lists, setLists] = useState<ContactList[]>([]);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        whatsappApi.getContactLists().then(setLists);
    }, []);

    const handleSave = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        const payload: any = {
            name,
            list_id: selectedList || undefined,
            company_name: companyName,
            lead_source: leadSource,
            date_of_birth: dob || undefined,
            customer_category: custCategory,
            customer_stage: custStage,
            city,
            product_service_interest: interest,
            consent_confirmation: consent
        };

        // Include phone_number for both create and edit
        if (phone) {
            payload.phone_number = phone;
        }

        try {
            if (contact) {
                await whatsappApi.updateContact(contact.id, payload);
            } else {
                await whatsappApi.createContact({ ...payload, upsert: true });
            }
            onSave();
            onClose();
        } catch (err: any) {
            setError(err.response?.data?.detail || "Failed to save contact.");
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-white dark:bg-slate-900 w-full max-w-md rounded-xl border border-slate-200 dark:border-slate-800 shadow-2xl p-8 relative">
                <button onClick={onClose} className="absolute top-6 right-6 p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-all text-slate-400"><X size={20} /></button>
                <div className="mb-6">
                    <h2 className="text-xl font-bold text-slate-900 dark:text-white">{contact ? "Edit Contact" : "Add Contact"}</h2>
                    <p className="text-sm text-slate-500 mt-1">{contact ? "Update contact information" : "Manually register a single contact"}</p>
                </div>
                <form onSubmit={handleSave} className="space-y-4">
                    {error && <div className="p-3 bg-rose-50 border border-rose-100 text-rose-600 text-xs font-bold rounded-lg flex items-center gap-2"><AlertCircle size={14} /> {error}</div>}
                    <div className="space-y-1">
                        <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Phone Number</label>
                        <input
                            autoFocus={!contact}
                            value={phone}
                            onChange={e => setPhone(e.target.value)}
                            placeholder="+91 XXXX XXXX"
                            className="w-full p-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all"
                        />
                    </div>
                    <div className="space-y-1">
                        <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Full Name</label>
                        <input autoFocus={!!contact} value={name} onChange={e => setName(e.target.value)} placeholder="Full Name" className="w-full p-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all" />
                    </div>
                    <div className="space-y-1">
                        <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Assign to List</label>
                        <select value={selectedList} onChange={e => setSelectedList(e.target.value)} className="w-full p-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none">
                            <option value="">None</option>
                            {lists.map(l => (
                                <option key={l.id} value={l.id}>{l.name}</option>
                            ))}
                        </select>
                    </div>

                    <div className="space-y-4 border-t border-slate-100 dark:border-slate-800 pt-4">
                        <h3 className="text-xs font-black text-indigo-600 uppercase tracking-[0.2em]">Segmentation Data</h3>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-1">
                                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Company Name</label>
                                <input value={companyName} onChange={e => setCompanyName(e.target.value)} placeholder="Company Ltd" className="w-full p-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-indigo-500/20" />
                            </div>
                            <div className="space-y-1">
                                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Lead Source</label>
                                <input value={leadSource} onChange={e => setLeadSource(e.target.value)} placeholder="Website/Referral" className="w-full p-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-indigo-500/20" />
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-1">
                                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Date of Birth</label>
                                <input type="date" value={dob} onChange={e => setDob(e.target.value)} className="w-full p-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-indigo-500/20" />
                            </div>
                            <div className="space-y-1">
                                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">City</label>
                                <input value={city} onChange={e => setCity(e.target.value)} placeholder="New York" className="w-full p-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-indigo-500/20" />
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-1">
                                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Customer Category</label>
                                <select value={custCategory} onChange={e => setCustCategory(e.target.value)} className="w-full p-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none">
                                    <option value="">Select Category</option>
                                    <option value="SI">SI</option>
                                    <option value="Distributor">Distributor</option>
                                    <option value="Super Stockist">Super Stockist</option>
                                </select>
                            </div>
                            <div className="space-y-1">
                                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Customer Stage</label>
                                <select value={custStage} onChange={e => setCustStage(e.target.value)} className="w-full p-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none">
                                    <option value="">Select Stage</option>
                                    <option value="Prospective">Prospective</option>
                                    <option value="New">New</option>
                                    <option value="Old">Old</option>
                                    <option value="Cancelled">Cancelled</option>
                                </select>
                            </div>
                        </div>

                        <div className="space-y-1">
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Product / Service Interest</label>
                            <input value={interest} onChange={e => setInterest(e.target.value)} placeholder="e.g. Cloud Hosting" className="w-full p-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-indigo-500/20" />
                        </div>

                        <div className="space-y-1">
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Consent Proof (WhatsApp)</label>
                            <input value={consent} onChange={e => setConsent(e.target.value)} placeholder="Opted-in via Form #123" className="w-full p-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-indigo-500/20" />
                        </div>
                    </div>
                    <button disabled={saving} type="submit" className="w-full mt-4 bg-indigo-600 py-3 rounded-lg text-white font-bold hover:bg-indigo-700 transition-all shadow-md">
                        {saving ? <Loader2 size={18} className="animate-spin mx-auto" /> : "Save Record"}
                    </button>
                </form>
            </div>
        </div>
    );
};

const Contacts: React.FC = () => {
    const [contacts, setContacts] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(0);
    const [limit] = useState(12);
    const [search, setSearch] = useState('');
    const [showAddModal, setShowAddModal] = useState(false);
    const [showBulkModal, setShowBulkModal] = useState(false);
    const [showListModal, setShowListModal] = useState(false);
    const [selectedContact, setSelectedContact] = useState<any | null>(null);

    const fetchContacts = async () => {
        setLoading(true);
        try {
            const res = await whatsappApi.getContacts({ offset: page * limit, limit, search: search || undefined });
            setContacts(res.items);
            setTotal(res.total);
        } catch (err) { console.error(err); } finally { setLoading(false); }
    };

    useEffect(() => { fetchContacts(); }, [page, limit, search]);

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

            <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden flex flex-col min-h-[600px]">
                <div className="p-6 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center bg-slate-50/50 dark:bg-slate-800/30">
                     <h3 className="font-bold text-slate-900 dark:text-white">Contact Records</h3>
                     <div className="relative">
                        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                        <input value={search} onChange={e => { setSearch(e.target.value); setPage(0); }} placeholder="Search identity..." className="pl-9 pr-4 py-1.5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-xs outline-none focus:ring-2 focus:ring-indigo-500/20" />
                     </div>
                </div>
                <div className="flex-1 overflow-x-auto">
                    <table className="w-full text-left text-sm">
                        <thead>
                            <tr className="border-b border-slate-100 dark:border-slate-800 text-[10px] font-bold text-slate-400 uppercase tracking-widest whitespace-nowrap">
                                <th className="px-6 py-4">Phone Number</th>
                                <th className="px-6 py-4">Full Identity</th>
                                <th className="px-6 py-4">Company</th>
                                <th className="px-6 py-4">City</th>
                                <th className="px-6 py-4">Cust. Category</th>
                                <th className="px-6 py-4">Stage</th>
                                <th className="px-6 py-4">Source</th>
                                <th className="px-6 py-4">DOB</th>
                                <th className="px-6 py-4">Interest</th>
                                <th className="px-6 py-4">Consent</th>
                                <th className="px-6 py-4 text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-50 dark:divide-slate-800/50">
                            {contacts.map(c => (
                                <tr key={c.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors group whitespace-nowrap">
                                    <td className="px-6 py-4 font-medium text-slate-900 dark:text-white tabular-nums">+{c.phone_number?.replace(/\+/g, '')}</td>
                                    <td className="px-6 py-4 text-slate-700 dark:text-slate-300 font-bold">{c.name || '--'}</td>
                                    <td className="px-6 py-4 text-slate-500">{c.company_name || '--'}</td>
                                    <td className="px-6 py-4 text-slate-500">{c.city || '--'}</td>
                                    <td className="px-6 py-4">
                                        <span className="px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-[10px] font-bold text-slate-600 dark:text-slate-400">
                                            {c.customer_category || '--'}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4">
                                        <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase ${
                                            c.customer_stage === 'Prospective' ? 'bg-amber-50 text-amber-600' : 
                                            c.customer_stage === 'New' ? 'bg-emerald-50 text-emerald-600' :
                                            'bg-slate-50 text-slate-500'
                                        }`}>
                                            {c.customer_stage || '--'}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4 text-slate-500 italic">{c.lead_source || '--'}</td>
                                    <td className="px-6 py-4 text-slate-500 tabular-nums">
                                        {c.date_of_birth ? new Date(c.date_of_birth).toLocaleDateString() : '--'}
                                    </td>
                                    <td className="px-6 py-4 text-slate-500 max-w-[150px] truncate">{c.product_service_interest || '--'}</td>
                                    <td className="px-6 py-4 text-slate-400 text-[10px]">{c.consent_confirmation || '--'}</td>
                                    <td className="px-6 py-4 text-right">
                                        <div className="flex justify-end gap-2">
                                            <button onClick={() => setSelectedContact(c)} className="p-1.5 text-slate-400 hover:text-indigo-600 transition-colors"><Edit2 size={16}/></button>
                                            <button onClick={async () => { if(confirm("Purge record?")) { await whatsappApi.deleteContact(c.id); fetchContacts(); } }} className="p-1.5 text-slate-400 hover:text-rose-600 transition-colors"><Trash2 size={16}/></button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
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

export default Contacts;
