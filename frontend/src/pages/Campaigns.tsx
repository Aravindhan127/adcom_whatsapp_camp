import React, { useState, useEffect, useMemo } from 'react';
import {
  Send, Plus, X, ChevronRight, Play, Pause, CheckCircle2,
  AlertCircle, Clock, FileText, Users, BarChart3, Loader2,
  CalendarClock, ListFilter, Command, Search, Trash2, Image
} from 'lucide-react';
import { whatsappApi } from '../services/whatsappApi';
import { wsService } from '../services/websocketService';
import PageHeader from '../components/PageHeader';

// ──────────────────────────────────────────────────────────────
// Types
// ──────────────────────────────────────────────────────────────
interface Campaign {
  id: string;
  name: string;
  template_name: string;
  status: 'draft' | 'scheduled' | 'running' | 'completed' | 'failed' | 'paused' | 'on_hold';
  total_contacts: number;
  sent_count: number;
  delivered_count: number;
  read_count: number;
  failed_count: number;
  scheduled_at: string | null;
  created_at: string;
  completed_at: string | null;
}

interface Template {
  id: string;
  name: string;
  category: string;
  language: string;
  status: string;
  components?: any[];
  variable_mappings?: Record<string, string>;
  media_id?: string;
}

interface ContactList {
  id: string;
  name: string;
  count?: number;
}

// ──────────────────────────────────────────────────────────────
// Status config
// ──────────────────────────────────────────────────────────────
const STATUS_CONFIG: Record<Campaign['status'], { label: string; color: string; dot: string }> = {
  draft: { label: 'Draft', color: 'text-slate-500 bg-slate-100 border-slate-200 dark:bg-slate-800 dark:border-slate-700', dot: 'bg-slate-400' },
  scheduled: { label: 'Scheduled', color: 'text-amber-600 bg-amber-50 border-amber-200 dark:bg-amber-900/20 dark:border-amber-800/50', dot: 'bg-amber-500' },
  running: { label: 'Active', color: 'text-indigo-600 bg-indigo-50 border-indigo-200 dark:bg-indigo-900/20 dark:border-indigo-800/50', dot: 'bg-indigo-500' },
  completed: { label: 'Completed', color: 'text-emerald-600 bg-emerald-50 border-emerald-200 dark:bg-emerald-900/20 dark:border-emerald-800/50', dot: 'bg-emerald-500' },
  failed: { label: 'Failed', color: 'text-rose-600 bg-rose-50 border-rose-200 dark:bg-rose-900/20 dark:border-rose-800/50', dot: 'bg-rose-500' },
  paused: { label: 'Paused', color: 'text-amber-600 bg-amber-50 border-amber-200 dark:bg-amber-900/20 dark:border-amber-800/50', dot: 'bg-amber-500' },
  on_hold: { label: 'On Hold', color: 'text-slate-600 bg-slate-50 border-slate-200 dark:bg-slate-900/20 dark:border-slate-800/50', dot: 'bg-slate-500' },
};

const ProgressBar = ({ value, total, color }: { value: number; total: number; color: string }) => {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0;
  return (
    <div className="w-full h-1.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
      <div style={{ width: `${pct}%` }} className={`h-full transition-all duration-1000 ease-out ${color}`} />
    </div>
  );
};

const CampaignCard = ({ campaign, onClick }: { campaign: Campaign; onClick: () => void }) => {
  const cfg = STATUS_CONFIG[campaign.status] || { label: campaign.status, color: 'text-slate-500 bg-slate-100 border-slate-200 dark:bg-slate-800 dark:border-slate-700', dot: 'bg-slate-400' };
  const deliveryRate = campaign.sent_count > 0 ? ((campaign.delivered_count / campaign.sent_count) * 100).toFixed(1) : '0.0';
  const progress = campaign.total_contacts > 0 ? Math.round((campaign.sent_count / campaign.total_contacts) * 100) : 0;

  return (
    <div onClick={onClick} className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 cursor-pointer shadow-sm hover:shadow-md hover:border-indigo-200 dark:hover:border-indigo-900/50 transition-all group">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h3 className="text-lg font-bold text-slate-900 dark:text-white group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">{campaign.name}</h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">{campaign.template_name}</p>
        </div>
        <span className={`flex items-center gap-2 px-2.5 py-1 rounded-lg text-[10px] font-bold border ${cfg.color} shrink-0`}>
          <div className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
          {cfg.label}
        </span>
      </div>
      <div className="space-y-5">
        <div className="grid grid-cols-2 gap-3">
          <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-100 dark:border-slate-700">
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Messages Sent</p>
            <p className="text-xl font-bold text-slate-900 dark:text-white tabular-nums">{campaign.sent_count.toLocaleString()}</p>
          </div>
          <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-100 dark:border-slate-700">
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Success Rate</p>
            <p className="text-xl font-bold text-indigo-600 dark:text-indigo-400 tabular-nums">{deliveryRate}%</p>
          </div>
        </div>
        <div>
          <div className="flex justify-between items-end mb-1.5">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Overall Progress</span>
            <span className="text-xs font-bold text-slate-900 dark:text-white tabular-nums">{progress}%</span>
          </div>
          <ProgressBar value={campaign.sent_count} total={campaign.total_contacts} color="bg-indigo-600 dark:bg-indigo-500" />
        </div>
      </div>
    </div>
  );
};
const TemplatePreview = ({ template, mapping }: { template: Template, mapping: Record<string, string> }) => {
  if (!template || !template.components) return null;

  // Render preview body with variable mapping replaced by placeholders
  const renderBody = (text: string) => {
    let result = text;
    Object.entries(mapping).forEach(([key, val]) => {
      // replace {{key}} with [val]
      const regex = new RegExp(`\\{\\{${key}\\}\\}`, 'g');
      result = result.replace(regex, `<span class="bg-indigo-100 text-indigo-700 px-1 rounded font-bold">${val}</span>`);
    });
    return <div dangerouslySetInnerHTML={{ __html: result }} />;
  };

  const header = template.components.find(c => c.type === 'HEADER');
  const body = template.components.find(c => c.type === 'BODY');
  const footer = template.components.find(c => c.type === 'FOOTER');
  const buttons = template.components.find(c => c.type === 'BUTTONS');

  // Try to find an image URL from example header_handle
  const headerUrl = header?.example?.header_handle?.[0] || "";

  return (
    <div className="bg-[#e5ddd5] dark:bg-slate-950 p-4 rounded-xl shadow-inner border border-slate-200 dark:border-slate-800 max-w-sm mx-auto overflow-hidden">
      <div className="bg-white dark:bg-slate-900 rounded-lg shadow-sm p-3 space-y-2 relative">
        <div className="absolute top-0 right-0 w-2 h-2 bg-white dark:bg-slate-900 rotate-45 -translate-y-1 translate-x-1" />
        
        {header && (
          <div className="bg-slate-100 dark:bg-slate-800 rounded aspect-video flex items-center justify-center mb-2 overflow-hidden">
            {header.format === 'IMAGE' ? (
              headerUrl ? <img src={headerUrl} alt="Header Preview" className="w-full h-full object-cover" /> : <Image size={32} className="text-slate-400" />
            ) : <FileText size={32} className="text-slate-400" />}
          </div>
        )}
        
        <div className="text-[13px] text-slate-800 dark:text-slate-200 leading-relaxed">
          {body ? renderBody(body.text) : 'No template body content'}
        </div>

        {footer && <div className="text-[11px] text-slate-400 mt-1">{footer.text}</div>}
        
        <div className="flex justify-end gap-1 mt-1">
          <span className="text-[9px] text-slate-400 font-medium lowercase tabular-nums">{new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
        </div>
      </div>
      
      {buttons?.buttons?.map((btn: any, i: number) => (
        <div key={i} className="mt-2 bg-white dark:bg-slate-900 rounded-lg text-indigo-600 dark:text-indigo-400 text-sm font-semibold py-2.5 text-center shadow-sm">
          {btn.text}
        </div>
      ))}
    </div>
  );
};

const CreateCampaignModal = ({ onClose, onCreate }: { onClose: () => void; onCreate: (c: Campaign) => void }) => {
  const [step, setStep] = useState(1);
  const [name, setName] = useState('');
  const [templates, setTemplates] = useState<Template[]>([]);
  const [lists, setLists] = useState<ContactList[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  const [selectedContactIds, setSelectedContactIds] = useState<string[]>([]);
  const [templateSearch, setTemplateSearch] = useState('');
  const [contactSearch, setContactSearch] = useState('');
  const [contacts, setContacts] = useState<any[]>([]);
  const [contactsLoading, setContactsLoading] = useState(false);
  const [scheduleDate, setScheduleDate] = useState('');
  const [templateParams, setTemplateParams] = useState<Record<string, string>>({});
  const [sending, setSending] = useState(false);

  useEffect(() => {
    whatsappApi.getTemplates().then(setTemplates);
  }, []);

  // Robustly pre-fill variable mappings when a template is selected
  useEffect(() => {
    if (selectedTemplate) {
      if (selectedTemplate.variable_mappings && Object.keys(selectedTemplate.variable_mappings).length > 0) {
        setTemplateParams({ ...selectedTemplate.variable_mappings });
      } else {
        setTemplateParams({});
      }
    }
  }, [selectedTemplate]);

  useEffect(() => {
    if (step === 3) {
      setContactsLoading(true);
      whatsappApi.getContacts({ search: contactSearch || undefined, limit: 100 }).then(res => {
        setContacts(res.items);
        setContactsLoading(false);
      });
    }
  }, [step, contactSearch]);

  const filteredTemplates = templates.filter(t => t.status === 'APPROVED' && (t.name.toLowerCase().includes(templateSearch.toLowerCase())));

  const handleCreate = async (sendNow: boolean) => {
    if (!selectedTemplate || selectedContactIds.length === 0) return;
    
    setSending(true);
    try {
      const payload = {
        name,
        template_name: selectedTemplate.name,
        contact_ids: selectedContactIds,
        template_params: templateParams,
        scheduled_at: scheduleDate || null
      };
      const created = await whatsappApi.createCampaign(payload);
      if (sendNow && !scheduleDate) await whatsappApi.startCampaign(created.id);
      onCreate(created);
      onClose();
    } catch (err) { console.error(err); } finally { setSending(false); }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className={`w-full max-w-xl bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-2xl overflow-hidden transition-all duration-500`}>
        <div className="p-6 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center">
          <h2 className="text-lg font-bold text-slate-900 dark:text-white">New Campaign</h2>
          <button onClick={onClose} className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg"><X size={20} /></button>
        </div>
        <div className="p-6">
          {step === 1 && (
            <div className="space-y-4">
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-300">Campaign Name</label>
              <input value={name} onChange={e => setName(e.target.value)} className="w-full p-3 bg-slate-50 dark:bg-slate-800 border-2 border-transparent focus:border-indigo-500 rounded-lg outline-none transition-all" placeholder="e.g., Summer Promotion 2024" />
            </div>
          )}
          {step === 2 && (
            <div className="space-y-4">
              <input value={templateSearch} onChange={e => setTemplateSearch(e.target.value)} placeholder="Search templates..." className="w-full p-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg" />
              <div className="max-h-60 overflow-y-auto space-y-2">
                {filteredTemplates.map(t => (
                  <div key={t.id} onClick={() => {
                    setSelectedTemplate(t);
                    if (t.variable_mappings) setTemplateParams(t.variable_mappings);
                    else setTemplateParams({});
                  }} className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${selectedTemplate?.id === t.id ? 'border-indigo-600 bg-indigo-50 dark:bg-indigo-500/10' : 'border-transparent bg-slate-50 dark:bg-slate-800 hover:border-slate-200 hover:bg-slate-100'}`}>
                    <p className="font-bold text-sm text-slate-900 dark:text-white">{t.name}</p>
                    <p className="text-xs text-slate-500">{t.category} • {t.language}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              <div className="relative">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input value={contactSearch} onChange={e => setContactSearch(e.target.value)} placeholder="Search contacts..." className="w-full pl-10 pr-4 py-2.5 bg-slate-50 dark:bg-slate-800 border-none rounded-lg" />
              </div>

              <div className="flex justify-between items-center px-1">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">{selectedContactIds.length} Selected</span>
                <button onClick={() => setSelectedContactIds(selectedContactIds.length === contacts.length ? [] : contacts.map(c => c.id))} className="text-[10px] font-bold text-indigo-600 uppercase hover:underline">
                  {selectedContactIds.length === contacts.length ? 'Deselect All' : 'Select All on Page'}
                </button>
              </div>

              <div className="max-h-64 overflow-y-auto border border-slate-100 dark:border-slate-800 rounded-xl divide-y divide-slate-50 dark:divide-slate-800">
                {contactsLoading ? (
                  <div className="p-12 flex justify-center"><Loader2 size={24} className="animate-spin text-slate-300" /></div>
                ) : contacts.map(c => (
                  <div key={c.id} onClick={() => setSelectedContactIds(prev => prev.includes(c.id) ? prev.filter(id => id !== c.id) : [...prev, c.id])} className={`p-3 flex items-center gap-3 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors ${selectedContactIds.includes(c.id) ? 'bg-indigo-50/50 dark:bg-indigo-500/5' : ''}`}>
                    <div className={`w-4 h-4 rounded border flex items-center justify-center transition-all ${selectedContactIds.includes(c.id) ? 'bg-indigo-600 border-indigo-600' : 'border-slate-300 bg-white dark:bg-slate-900'}`}>
                      {selectedContactIds.includes(c.id) && <CheckCircle2 size={10} className="text-white" />}
                    </div>
                    <div>
                      <p className="text-sm font-bold text-slate-900 dark:text-white">{c.name || 'No Name'}</p>
                      <p className="text-xs text-slate-500 tabular-nums">+{c.phone_number}</p>
                    </div>
                    <span className="ml-auto px-2 py-0.5 rounded text-[9px] font-bold bg-slate-100 dark:bg-slate-800 text-slate-500 capitalize">{c.category}</span>
                  </div>
                ))}
                {!contactsLoading && contacts.length === 0 && <p className="p-8 text-center text-xs text-slate-400">No contacts found.</p>}
              </div>
            </div>
          )}
          {step === 4 && (
            <div className="flex flex-col items-center justify-center space-y-8 py-4">
              <div className="text-center space-y-2">
                <h3 className="text-xs font-black text-slate-900 dark:text-slate-300 uppercase tracking-[0.2em]">Message Preview</h3>
                <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">Ready to launch</p>
              </div>
              
              <TemplatePreview template={selectedTemplate!} mapping={templateParams} />

              <div className="px-6 py-3 bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-100 dark:border-indigo-500/20 rounded-2xl">
                <p className="text-[9px] text-indigo-600 dark:text-indigo-400 font-black uppercase tracking-[0.1em]">
                  Mappings applied from template configuration
                </p>
              </div>
            </div>
          )}
          {step === 5 && (
            <div className="space-y-4">
              <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-widest pl-1">Schedule (Optional)</label>
              <input type="datetime-local" value={scheduleDate} onChange={e => setScheduleDate(e.target.value)} className="w-full p-4 bg-slate-50 dark:bg-slate-800 border-none rounded-xl text-sm outline-none focus:ring-2 focus:ring-indigo-500/20" />
              <button
                onClick={() => handleCreate(true)}
                disabled={sending}
                className="w-full py-4 bg-indigo-600 text-white rounded-xl font-bold hover:bg-indigo-700 shadow-xl shadow-indigo-600/20 flex items-center justify-center gap-2 transition-all active:scale-[0.98]"
              >
                {sending ? <Loader2 size={18} className="animate-spin" /> : <Play size={18} fill="currentColor" />}
                {sending ? 'Launching...' : 'Launch Campaign'}
              </button>
            </div>
          )}
        </div>
        <div className="p-6 bg-slate-50 dark:bg-slate-800/50 border-t border-slate-100 dark:border-slate-800 flex justify-between">
          <button onClick={() => setStep(s => s - 1)} disabled={step === 1} className="px-4 py-2 text-sm font-bold text-slate-600 dark:text-slate-400 disabled:opacity-30 transition-opacity">Back</button>
          {step < 5 && <button onClick={() => setStep(s => s + 1)} disabled={(step === 2 && !selectedTemplate) || (step === 3 && selectedContactIds.length === 0)} className="px-6 py-2 bg-slate-900 dark:bg-white text-white dark:text-slate-900 rounded-lg text-sm font-bold shadow-md hover:scale-105 active:scale-95 disabled:opacity-50 transition-all">Next Step</button>}
        </div>
      </div>
    </div>
  );
};

const Campaigns: React.FC = () => {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [limit] = useState(9);
  const [showCreate, setShowCreate] = useState(false);
  const [filter, setFilter] = useState<Campaign['status'] | 'all'>('all');
  const [search, setSearch] = useState('');
  const [selectedCampaign, setSelectedCampaign] = useState<Campaign | null>(null);

  useEffect(() => {
    const fetch = async () => {
      setLoading(true);
      try {
        const res = await whatsappApi.getCampaigns({ skip: page * limit, limit, search: search || undefined, status: filter === 'all' ? undefined : filter });
        setCampaigns(res.items);
        setTotal(res.total);
      } catch (err) { console.error(err); } finally { setLoading(false); }
    };
    fetch();
  }, [page, limit, search, filter]);

  // Real-time progress updates via WebSockets
  useEffect(() => {
    const unsub = wsService.subscribe('campaign_progress', (payload) => {
      setCampaigns(prev => prev.map(c => {
        if (c.id === payload.campaign_id) {
          return {
            ...c,
            sent_count: payload.processed,
            delivered_count: payload.success,
            failed_count: payload.failed,
            status: payload.status as any
          };
        }
        return c;
      }));
      
      // Update selected campaign details if open
      if (selectedCampaign?.id === payload.campaign_id) {
        setSelectedCampaign(prev => prev ? ({
          ...prev,
          sent_count: payload.processed,
          delivered_count: payload.success,
          failed_count: payload.failed,
          status: payload.status as any
        }) : null);
      }
    });

    return unsub;
  }, [selectedCampaign]);

  const handleDelete = async (campaignId: string) => {
    if (!window.confirm("Are you sure you want to delete this campaign? This action cannot be undone.")) return;
    
    try {
      await whatsappApi.deleteCampaign(campaignId);
      setCampaigns(prev => prev.filter(c => c.id !== campaignId));
      setSelectedCampaign(null);
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to delete campaign. Ensure it is not currently running.");
    }
  };

  const handlePause = async (id: string) => {
    try {
      await whatsappApi.pauseCampaign(id);
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to pause campaign");
    }
  };

  const handleResume = async (id: string) => {
    try {
      await whatsappApi.resumeCampaign(id);
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to resume campaign");
    }
  };

  return (
    <div className="space-y-8 font-sans">
      <PageHeader
        title="Campaigns"
        description="Manage and track your messaging performance"
        actions={
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white rounded-lg font-bold shadow-sm hover:bg-indigo-700 transition-all"
          >
            <Plus size={18} /> Create
          </button>
        }
      />

      <div className="flex flex-col md:flex-row gap-4 justify-between items-center bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-100 dark:border-slate-800 shadow-sm">
        <div className="flex gap-2">
          {['all', 'running', 'scheduled', 'completed'].map(f => (
            <button key={f} onClick={() => setFilter(f as any)} className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${filter === f ? 'bg-indigo-50 text-indigo-600 dark:bg-indigo-500/10' : 'text-slate-500 hover:bg-slate-50'}`}>{f.charAt(0).toUpperCase() + f.slice(1)}</button>
          ))}
        </div>
        <div className="relative w-full md:w-64">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search..." className="w-full pl-10 pr-4 py-2 bg-slate-50 dark:bg-slate-800 border-none rounded-lg text-sm outline-none focus:ring-2 focus:ring-indigo-500/20" />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {campaigns.map(c => <CampaignCard key={c.id} campaign={c} onClick={() => setSelectedCampaign(c)} />)}
      </div>

      {showCreate && <CreateCampaignModal onClose={() => setShowCreate(false)} onCreate={(c) => setCampaigns([c, ...campaigns])} />}

      {selectedCampaign && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex justify-end">
          <div className="w-full max-w-sm bg-white dark:bg-slate-900 h-full border-l border-slate-200 dark:border-slate-800 p-8 shadow-2xl overflow-y-auto">
            <div className="flex justify-between items-start mb-8">
              <div>
                <h2 className="text-xl font-bold text-slate-800 dark:text-white">{selectedCampaign.name}</h2>
                <p className="text-xs text-slate-400">{selectedCampaign.template_name}</p>
              </div>
              <button onClick={() => setSelectedCampaign(null)} className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg"><X size={20} /></button>
            </div>
            <div className="space-y-6">
              {[
                { label: 'Total', value: selectedCampaign.total_contacts },
                { label: 'Sent', value: selectedCampaign.sent_count },
                { label: 'Delivered', value: selectedCampaign.delivered_count },
                { label: 'Read', value: selectedCampaign.read_count },
              ].map(stat => (
                <div key={stat.label}>
                  <div className="flex justify-between text-xs font-bold mb-2">
                    <span className="text-slate-400 uppercase tracking-wider">{stat.label}</span>
                    <span className="text-slate-900 dark:text-white">{stat.value}</span>
                  </div>
                  <ProgressBar value={stat.value} total={selectedCampaign.total_contacts} color="bg-indigo-600" />
                </div>
              ))}
            </div>

            <div className="mt-8 space-y-3">
              {selectedCampaign.status === 'running' && (
                <button 
                  onClick={() => handlePause(selectedCampaign.id)}
                  className="w-full py-3 bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400 font-bold text-sm border border-amber-100 dark:border-amber-500/20 rounded-xl hover:bg-amber-100 dark:hover:bg-amber-500/20 transition-all flex items-center justify-center gap-2"
                >
                  <Pause size={16} /> Pause Campaign
                </button>
              )}
              {selectedCampaign.status === 'paused' && (
                <button 
                  onClick={() => handleResume(selectedCampaign.id)}
                  className="w-full py-3 bg-indigo-600 text-white font-bold text-sm rounded-xl hover:bg-indigo-700 shadow-lg shadow-indigo-600/20 transition-all flex items-center justify-center gap-2"
                >
                  <Play size={16} fill="currentColor" /> Resume Campaign
                </button>
              )}
            </div>

            <div className="mt-12 pt-6 border-t border-slate-100 dark:border-slate-800">
              <button 
                onClick={() => handleDelete(selectedCampaign.id)}
                className="w-full py-3 bg-rose-50 dark:bg-rose-500/10 text-rose-600 dark:text-rose-400 font-bold text-sm border border-rose-100 dark:border-rose-500/20 rounded-xl hover:bg-rose-100 dark:hover:bg-rose-500/20 transition-all flex items-center justify-center gap-2"
              >
                <Trash2 size={16} /> Delete Campaign
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Campaigns;
