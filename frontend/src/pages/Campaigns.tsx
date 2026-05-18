import React, { useState, useEffect, useMemo } from 'react';
import {
  Send, Plus, X, ChevronRight, Play, Pause, CheckCircle2,
  AlertCircle, Clock, FileText, Users, BarChart3, Loader2,
  CalendarClock, ListFilter, Command, Search, Trash2, Image,
  Filter, ChevronDown, ChevronUp, MessageSquare, ArrowUpDown,
  ChevronLeft, Download, RefreshCw
} from 'lucide-react';
import { whatsappApi, type Campaign, type Template, type ContactList } from '../services/whatsappApi';
import { wsService } from '../services/websocketService';
import { useToast } from '../components/Toast';
import PageHeader from '../components/PageHeader';
import { CustomSelect } from '../components/CustomSelect';

function SortHeader({ label, column, currentSort, onSort }: { label: string; column: string; currentSort: any; onSort: (col: string) => void }) {
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
}


// ──────────────────────────────────────────────────────────────
// Types are imported from ../services/whatsappApi
// ──────────────────────────────────────────────────────────────

// ──────────────────────────────────────────────────────────────
// Status config
// ──────────────────────────────────────────────────────────────
const META_ERROR_MAP: Record<string, string> = {
  '100': 'Generic Error: Invalid parameters or server issue.',
  '131000': 'Meta Internal Error: Something went wrong on Meta\'s side.',
  '131008': 'Missing Parameter: A required field was not sent.',
  '131009': 'Invalid Parameter: One of the field values is not supported.',
  '131016': 'User Not Found: The recipient phone number is not registered on WhatsApp.',
  '131021': 'Not Authorized: You don\'t have permission to message this user yet.',
  '131026': 'Message Undeliverable: Recipient phone is unreachable or not on WhatsApp.',
  '131030': 'Message Blocked: The recipient has blocked this business.',
  '131042': 'Business eligibility payment issue: Check your Meta billing or account status.',
  '131045': 'Rate Limit Hit: Too many messages sent in a short period.',
  '131047': 'Daily Sending Limit: You have reached your account sending limit for today.',
  '131048': 'Spam/Policy: Message blocked by Meta automation as potential spam.',
  '131049': 'Quality Restricted: Account quality is too low to send messages.',
  '131051': 'Message Expired: Outside the 24h customer service window.',
  '131052': 'Template Missing: This template does not exist on your Meta account.',
  '131053': 'Language Missing: The requested language is not available for this template.',
  '131057': 'Account Restricted: Business account restricted due to policy violations.',
  '132000': 'Template Error: Template has been deleted or disabled.',
  '132001': 'Template Name Mismatch: The requested template name was not found.',
  '132015': 'Format Error: Template parameter count mismatch or structure invalid.',
  '132016': 'Language Mismatch: Requested language not supported by template.',
  '133004': 'Server Unavailable: Meta Cloud API is temporarily down.',
  '133010': 'Verification Needed: Phone number verification is pending or failed.',
  '135000': 'Meta System Error: Internal server error at Meta (Please retry).'
};

const parseMetaError = (errorStr: string | null): string => {
  if (!errorStr) return '';
  
  // 1. Handle our enhanced "(Code) Message" format
  const codeMatch = errorStr.match(/^\((\d+)\)\s+(.*)/);
  if (codeMatch) {
    const code = codeMatch[1];
    const friendly = META_ERROR_MAP[code];
    return friendly ? `${friendly} (Code: ${code})` : `${codeMatch[2]} (Code: ${code})`;
  }

  // 2. Handle raw JSON format (legacy/fallback)
  try {
    const data = JSON.parse(errorStr);
    const code = data.errors?.[0]?.code || data.code;
    const msg = data.errors?.[0]?.message || data.message || errorStr;
    const friendly = code ? META_ERROR_MAP[String(code)] : null;
    
    return friendly ? `${friendly} (Code: ${code})` : msg.replace(/^(\(#\d+\)\s+)/, '');
  } catch (e) {
    return errorStr;
  }
};

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
      {campaign.status === 'failed' && campaign.failure_reason && (
        <div className="mb-4 p-2 bg-rose-50 dark:bg-rose-500/10 border border-rose-100 dark:border-rose-500/20 rounded-lg">
          <p className="text-[10px] text-rose-600 dark:text-rose-400 font-bold leading-tight">
            {parseMetaError(campaign.failure_reason)}
          </p>
        </div>
      )}
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

  // FE-FIX FE-2: Sanitize val before DOM injection to prevent XSS.
  // Template variable values come from user input and must not contain raw HTML.
  const escapeHtml = (unsafe: string): string =>
    unsafe
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#x27;');

  const renderBody = (text: string) => {
    let result = text;
    Object.entries(mapping).forEach(([key, val]) => {
      const regex = new RegExp(`\\{\\{${key}\\}\\}`, 'g');
      const safeVal = escapeHtml(String(val));  // FE-FIX FE-2: escape before inject
      result = result.replace(regex, `<span class="bg-indigo-100 text-indigo-700 px-1 rounded font-bold">${safeVal}</span>`);
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
  const [templateCategory, setTemplateCategory] = useState('');
  const [templateSkip, setTemplateSkip] = useState(0);
  const [hasMoreTemplates, setHasMoreTemplates] = useState(true);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const [contactSearch, setContactSearch] = useState('');
  const [contacts, setContacts] = useState<any[]>([]);
  const [contactsLoading, setContactsLoading] = useState(false);
  const [scheduleDate, setScheduleDate] = useState('');
  const [templateParams, setTemplateParams] = useState<Record<string, string>>({});
  const [sending, setSending] = useState(false);
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  const [contactFilters, setContactFilters] = useState({
    company_name: '',
    lead_source: '',
    customer_category: '',
    customer_stage: '',
    city: ''
  });
  const [filterOptions, setFilterOptions] = useState({
    categories: [] as string[],
    stages: [] as string[],
    cities: [] as string[],
    sources: [] as string[]
  });

  const fetchTemplates = async (reset = false) => {
    if (!reset && loadingTemplates) return;
    setLoadingTemplates(true);

    const skip = reset ? 0 : templateSkip;
    try {
      const res = await whatsappApi.getTemplates({
        search: templateSearch || undefined,
        category: templateCategory || undefined,
        status: 'APPROVED',
        skip,
        limit: 10
      });
      if (reset) {
        setTemplates(res.items || []);
        setTemplateSkip((res.items || []).length);
      } else {
        setTemplates(prev => [...(prev || []), ...(res.items || [])]);
        setTemplateSkip(prev => prev + (res.items || []).length);
      }
      setHasMoreTemplates(res.items.length === 10);
    } catch (err) {
      console.error('Failed to fetch templates:', err);
    } finally {
      setLoadingTemplates(false);
    }
  };

  useEffect(() => {
    if (step === 2) {
      const timer = setTimeout(() => {
        fetchTemplates(true);
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [step, templateSearch, templateCategory]);

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
      const params = {
        search: contactSearch || undefined,
        limit: 100,
        ...Object.fromEntries(Object.entries(contactFilters).map(([k, v]) => [k, v || undefined]))
      };
      whatsappApi.getContacts(params).then(res => {
        setContacts(res.items);
        setContactsLoading(false);
      });
    }
  }, [step, contactSearch, contactFilters]);

  useEffect(() => {
    if (step === 3 && filterOptions.categories.length === 0) {
      whatsappApi.getContactFilterOptions().then(setFilterOptions).catch(console.error);
    }
  }, [step]);

  // Backend now handles filtering
  const filteredTemplates = templates;

  const { success, error: toastError } = useToast();

  const handleCreate = async (sendNow: boolean) => {
    if (!selectedTemplate || selectedContactIds.length === 0) return;

    setSending(true);
    try {
      const payload = {
        name: name.trim(),
        template_name: selectedTemplate.name,
        contact_ids: selectedContactIds,
        template_params: templateParams,
        // FE-FIX FE-5: Convert local datetime-local string to UTC ISO timestamp.
        // datetime-local input has no timezone info — appending IST offset prevents
        // scheduled campaigns firing 5.5h late for Indian users.
        scheduled_at: scheduleDate
          ? new Date(scheduleDate).toISOString()  // JS Date auto-converts local → UTC
          : null
      };
      const created = await whatsappApi.createCampaign(payload);
      const campaignId = created?.id;

      if (!campaignId) {
        console.error('DEBUG: Campaign created but ID is missing from response:', created);
        throw new Error('Server did not return a valid Campaign ID. Please check console.');
      }

      // BE-FIX FE-Scheduling: Always call startCampaign if we intend to launch OR schedule.
      if (sendNow || scheduleDate) await whatsappApi.startCampaign(campaignId);

      const title = scheduleDate ? 'Campaign Scheduled!' : 'Campaign Launched!';
      const msg = scheduleDate
        ? `"${name}" is scheduled for ${new Date(scheduleDate).toLocaleString()}`
        : `"${name}" is now running.`;

      success(title, msg);
      onCreate(created);
      onClose();
    } catch (err: any) {
      toastError('Failed to create campaign', err?.response?.data?.detail || err.message);
    } finally { setSending(false); }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className={`w-full max-w-xl bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-2xl overflow-hidden transition-all duration-500`}>
        <div className="p-6 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center">
          <h2 className="text-lg font-bold text-slate-900 dark:text-white">New Campaign</h2>
          <button onClick={onClose} className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg"><X size={20} /></button>
        </div>
        <div className="p-6 max-h-[60vh] overflow-y-auto">
          {step === 1 && (
            <div className="space-y-4">
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-300">Campaign Name</label>
              <input value={name} onChange={e => setName(e.target.value)} className="w-full p-3 bg-slate-50 dark:bg-slate-800 border-2 border-transparent focus:border-indigo-500 rounded-lg outline-none transition-all" placeholder="e.g., Summer Promotion 2024" />
            </div>
          )}
          {step === 2 && (
            <div className="space-y-4">
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input value={templateSearch} onChange={e => setTemplateSearch(e.target.value)} placeholder="Search templates..." className="w-full pl-10 pr-4 py-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg outline-none focus:ring-2 focus:ring-indigo-500/20" />
                </div>
                <CustomSelect
                  value={templateCategory}
                  onChange={setTemplateCategory}
                  className="w-48"
                  options={[
                    { value: "", label: "All Categories" },
                    { value: "MARKETING", label: "Marketing" },
                    { value: "UTILITY", label: "Utility" },
                    { value: "AUTHENTICATION", label: "Auth" },
                  ]}
                />
              </div>
              <div className="max-h-60 overflow-y-auto space-y-2 pr-1 custom-scrollbar">
                {(templates || []).map(t => (
                  <div key={t.id} onClick={() => {
                    setSelectedTemplate(t);
                    if (t.variable_mappings) setTemplateParams(t.variable_mappings);
                    else setTemplateParams({});
                  }} className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${selectedTemplate?.id === t.id ? 'border-indigo-600 bg-indigo-50 dark:bg-indigo-500/10' : 'border-transparent bg-slate-50 dark:bg-slate-800 hover:border-slate-200 hover:bg-slate-100'}`}>
                    <div className="flex justify-between items-start">
                      <div>
                        <p className="font-bold text-sm text-slate-900 dark:text-white">{t.name}</p>
                        <p className="text-[10px] font-bold text-slate-500 uppercase tracking-tight">{t.category} • {t.language}</p>
                      </div>
                      {selectedTemplate?.id === t.id && <CheckCircle2 size={16} className="text-indigo-600" />}
                    </div>
                  </div>
                ))}

                {loadingTemplates && (
                  <div className="py-4 flex justify-center"><Loader2 size={20} className="animate-spin text-slate-400" /></div>
                )}

                {hasMoreTemplates && !loadingTemplates && (
                  <button
                    onClick={() => fetchTemplates(false)}
                    className="w-full py-2.5 text-[10px] font-bold text-indigo-600 uppercase tracking-widest border border-dashed border-indigo-200 dark:border-indigo-900/50 rounded-lg hover:bg-indigo-50 dark:hover:bg-indigo-500/5 transition-all"
                  >
                    Load More Templates
                  </button>
                )}

                {!loadingTemplates && templates.length === 0 && (
                  <div className="py-10 text-center text-xs text-slate-400 font-medium">No approved templates match your criteria.</div>
                )}
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input value={contactSearch} onChange={e => setContactSearch(e.target.value)} placeholder="Search name or number..." className="w-full pl-10 pr-4 py-2.5 bg-slate-50 dark:bg-slate-800 border-none rounded-lg" />
                </div>
                <button
                  onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
                  className={`px-3 flex items-center gap-2 rounded-lg border transition-all ${showAdvancedFilters ? 'bg-indigo-50 border-indigo-200 text-indigo-600' : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-600'}`}
                >
                  <Filter size={16} />
                  <span className="text-xs font-bold uppercase">Filter</span>
                </button>
              </div>

              {showAdvancedFilters && (
                <div className="grid grid-cols-2 gap-3 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-100 dark:border-slate-800">
                  <CustomSelect
                    label="Category"
                    value={contactFilters.customer_category}
                    onChange={v => setContactFilters(prev => ({ ...prev, customer_category: v }))}
                    options={[
                      { value: "", label: "All Categories" },
                      ...filterOptions.categories.map(c => ({ value: c, label: c }))
                    ]}
                  />
                  <CustomSelect
                    label="Stage"
                    value={contactFilters.customer_stage}
                    onChange={v => setContactFilters(prev => ({ ...prev, customer_stage: v }))}
                    options={[
                      { value: "", label: "All Stages" },
                      ...filterOptions.stages.map(s => ({ value: s, label: s }))
                    ]}
                  />
                  <CustomSelect
                    label="City"
                    value={contactFilters.city}
                    onChange={v => setContactFilters(prev => ({ ...prev, city: v }))}
                    options={[
                      { value: "", label: "All Cities" },
                      ...filterOptions.cities.map(ct => ({ value: ct, label: ct }))
                    ]}
                  />
                  <CustomSelect
                    label="Lead Source"
                    value={contactFilters.lead_source}
                    onChange={v => setContactFilters(prev => ({ ...prev, lead_source: v }))}
                    options={[
                      { value: "", label: "All Sources" },
                      ...filterOptions.sources.map(src => ({ value: src, label: src }))
                    ]}
                  />
                  <div className="col-span-2 flex justify-end">
                    <button
                      onClick={() => setContactFilters({ company_name: '', lead_source: '', customer_category: '', customer_stage: '', city: '' })}
                      className="text-[10px] font-black text-indigo-600 uppercase tracking-widest hover:underline"
                    >
                      Clear Filters
                    </button>
                  </div>
                </div>
              )}

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
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-bold text-slate-900 dark:text-white truncate">{c.name || 'No Name'}</p>
                      <p className="text-[10px] text-slate-500 tabular-nums">
                        {c.phone_number?.startsWith('+') ? c.phone_number : `+${c.phone_number}`}
                        {c.city && <span className="mx-1">• {c.city}</span>}
                      </p>
                    </div>
                    {c.customer_category && (
                      <span className="shrink-0 px-2 py-0.5 rounded text-[9px] font-black uppercase tracking-tighter bg-slate-100 dark:bg-slate-800 text-slate-500">
                        {c.customer_category}
                      </span>
                    )}
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
          {step < 5 && <button onClick={() => setStep(s => s + 1)} disabled={
            (step === 1 && !name.trim()) ||  // FE-FIX FE-7: empty campaign name not allowed
            (step === 2 && !selectedTemplate) ||
            (step === 3 && selectedContactIds.length === 0)
          } className="px-6 py-2 bg-slate-900 dark:bg-white text-white dark:text-slate-900 rounded-lg text-sm font-bold shadow-md hover:scale-105 active:scale-95 disabled:opacity-50 transition-all">Next Step</button>}
        </div>
      </div>
    </div>
  );
};

const CampaignDetailPanel = ({ campaign, onClose, onPause, onResume, onDelete }: {
  campaign: Campaign;
  onClose: () => void;
  onPause: (id: string) => void;
  onResume: (id: string) => void;
  onDelete: (id: string) => void;
}) => {
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [logPage, setLogPage] = useState(0);
  const [logTotal, setLogTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState('all');
  const [exporting, setExporting] = useState(false);
  const [retryingCooldown, setRetryingCooldown] = useState(false);
  const toast = useToast();

  const handleRetryCooldown = async () => {
    setRetryingCooldown(true);
    try {
      await whatsappApi.retryCooldown(campaign.id);
      toast.show("Success", "Cooldown retry queued in background! Messages will be resent once health check passes.", "success");
      fetchLogs();
    } catch (err) {
      console.error("Retry cooldown failed:", err);
      toast.show("Error", "Failed to queue cooldown retry.", "error");
    } finally {
      setRetryingCooldown(false);
    }
  };

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const res = await whatsappApi.getCampaignLogs(campaign.id, { 
        skip: logPage * 50, 
        limit: 50,
        status: statusFilter === 'all' ? undefined : statusFilter
      });
      setLogs(res.items);
      setLogTotal(res.total);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [campaign.id, logPage, statusFilter]);

  const handleExport = async () => {
    setExporting(true);
    try {
      const blob = await whatsappApi.exportCampaignLogs(campaign.id, statusFilter === 'all' ? undefined : statusFilter);
      const url = window.URL.createObjectURL(new Blob([blob]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `campaign_logs_${campaign.name}_${new Date().toISOString().split('T')[0]}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      console.error('Export failed:', err);
    } finally {
      setExporting(false);
    }
  };

  // BE-FIX: Live status updates for the Log table
  useEffect(() => {
    const unsub = wsService.subscribe('status_update', (payload) => {
      // payload: { meta_id, status, wa_id }
      // Update logs if this message is in our current view
      setLogs(prev => prev.map(log => {
        if (log.meta_id === payload.meta_id) {
          return { ...log, status: payload.status };
        }
        return log;
      }));
    });
    return unsub;
  }, []);

  // Status Badge Helper
  const getStatusPill = (log: any) => {
    const s = log.status?.toLowerCase();
    const isFailed = s === 'failed';
    const isRead = s === 'read';
    const isDelivered = s === 'delivered';
    const isCooldown = s === 'cooldown';
    
    const baseClasses = "px-2 py-0.5 rounded-full text-[9px] font-black uppercase transition-all duration-200 active:scale-95 flex items-center gap-1 group";
    
    let colorClasses = "bg-slate-100 text-slate-500 hover:bg-slate-200";
    if (isRead) colorClasses = "bg-indigo-100 text-indigo-700 hover:bg-indigo-200";
    if (isDelivered) colorClasses = "bg-emerald-100 text-emerald-700 hover:bg-emerald-200";
    if (isFailed) colorClasses = "bg-rose-100 text-rose-700 hover:bg-rose-200";
    if (isCooldown) colorClasses = "bg-amber-100 text-amber-700 hover:bg-amber-200 dark:bg-amber-900/20 dark:text-amber-400";
    
    return (
      <button 
        onClick={() => setViewingLog(log)}
        className={`${baseClasses} ${colorClasses}`}
      >
        {s || 'Sent'}
        {(isFailed || isRead || isDelivered || isCooldown) && <AlertCircle size={8} className="transition-transform group-hover:rotate-12" />}
      </button>
    );
  };

  const [viewingLog, setViewingLog] = useState<any | null>(null);

  return (
    <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-md z-[60] flex justify-center sm:justify-end transition-all p-0 sm:p-0">
      <div className="w-full sm:max-w-xl bg-white dark:bg-slate-900 h-full shadow-2xl flex flex-col border-l border-slate-200 dark:border-slate-800 animate-in slide-in-from-right duration-300">

        {/* Header */}
        <div className="p-4 sm:p-6 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center bg-slate-50/50 dark:bg-slate-800/20">
          <div className="min-w-0">
            <h2 className="text-lg sm:text-xl font-bold text-slate-900 dark:text-white leading-tight truncate">{campaign.name}</h2>
            <p className="text-xs text-slate-500 font-medium truncate">{campaign.template_name}</p>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-white dark:hover:bg-slate-800 rounded-xl shadow-sm border border-transparent hover:border-slate-200 transition-all shrink-0">
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 flex flex-col overflow-hidden p-4 sm:p-6 min-h-0">
          {/* Top section (Stats + Buttons) - Fixed Height */}
          <div className="shrink-0 space-y-6 sm:space-y-8 mb-4">
            {/* Stats Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
              {[
                { label: 'Total Contacts', value: campaign.total_contacts, icon: Users, color: 'text-slate-600' },
                { label: 'Sent', value: campaign.sent_count, icon: Send, color: 'text-indigo-600' },
                { label: 'Delivered', value: campaign.delivered_count, icon: CheckCircle2, color: 'text-emerald-600' },
                { label: 'Read', value: campaign.read_count, icon: MessageSquare, color: 'text-indigo-500' },
                { label: 'Failed', value: campaign.failed_count, icon: AlertCircle, color: 'text-rose-600', error: campaign.failure_reason }
              ].map((stat, idx) => (
                <div
                  key={stat.label}
                  className={`p-4 rounded-2xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800 transition-all ${stat.label === 'Failed' ? 'sm:col-span-2' : ''} ${stat.label === 'Failed' && stat.value > 0 ? 'border-rose-200 dark:border-rose-900/30' : ''}`}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <stat.icon size={14} className={stat.color} />
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">{stat.label}</span>
                  </div>
                  <div className="flex items-baseline gap-2">
                    <p className="text-2xl font-black text-slate-900 dark:text-white tabular-nums">{stat.value.toLocaleString()}</p>
                    {stat.label === 'Failed' && stat.error && (
                      <button 
                        onClick={() => setViewingLog({ status: 'failed', error: stat.error, phone: 'Campaign Total' })}
                        className="text-[10px] font-bold text-rose-500 bg-rose-50 dark:bg-rose-500/10 px-2 py-0.5 rounded animate-pulse hover:bg-rose-100 dark:hover:bg-rose-500/20 transition-colors"
                      >
                        VIEW REASON
                      </button>
                    )}
                  </div>

                  <div className="mt-3">
                    <ProgressBar value={stat.value} total={campaign.total_contacts} color={stat.color.replace('text', 'bg')} />
                  </div>
                </div>
              ))}
            </div>

            {/* Action Buttons */}
            <div className="flex flex-col gap-3">
              <div className="flex gap-3 w-full">
                {campaign.status === 'running' && (
                  <button onClick={() => onPause(campaign.id)} className="flex-1 py-3 px-4 bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400 font-bold rounded-xl border border-amber-200/50 flex items-center justify-center gap-2 hover:bg-amber-100 transition-all">
                    <Pause size={16} fill="currentColor" /> Pause
                  </button>
                )}
                {campaign.status === 'paused' && (
                  <button onClick={() => onResume(campaign.id)} className="flex-1 py-3 px-4 bg-indigo-600 text-white font-bold rounded-xl shadow-lg shadow-indigo-600/20 flex items-center justify-center gap-2 hover:bg-indigo-700 transition-all">
                    <Play size={16} fill="currentColor" /> Resume
                  </button>
                )}
                <button onClick={() => onDelete(campaign.id)} className="px-4 py-3 bg-rose-50 dark:bg-rose-500/10 text-rose-600 dark:text-rose-400 font-bold rounded-xl border border-rose-200/50 flex items-center justify-center gap-2 hover:bg-rose-100 transition-all">
                  <Trash2 size={16} /> Delete
                </button>
              </div>

              {logs.some(l => l.status?.toLowerCase() === 'cooldown') && (
                <button 
                  onClick={handleRetryCooldown} 
                  disabled={retryingCooldown}
                  className="w-full py-3.5 px-4 bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700 text-white font-black rounded-xl shadow-lg shadow-amber-500/20 flex items-center justify-center gap-2 transition-all active:scale-[0.98] disabled:opacity-50"
                >
                  {retryingCooldown ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <RefreshCw size={16} />
                  )}
                  {retryingCooldown ? 'Queueing Retry...' : 'Retry Cooldown Messages'}
                </button>
              )}
            </div>
          </div>

          {/* Detailed Logs Table - Scrollable Inner Area */}
          <div className="flex-1 flex flex-col min-h-0 pt-4 border-t border-slate-100 dark:border-slate-800 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 shrink-0">
              <div className="flex items-center justify-between sm:justify-start gap-3">
                <h3 className="text-xs font-black text-slate-900 dark:text-slate-300 uppercase tracking-widest">Recipient Logs</h3>
                <span className="text-[10px] font-bold text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded-full">{logTotal} Records</span>
              </div>
              
              <div className="flex items-center gap-2">
                <CustomSelect
                  value={statusFilter}
                  onChange={(v) => { setStatusFilter(v); setLogPage(0); }}
                  className="w-full sm:w-32 h-8 text-[10px]"
                  options={[
                    { value: "all", label: "All Status" },
                    { value: "sent", label: "Sent" },
                    { value: "delivered", label: "Delivered" },
                    { value: "read", label: "Read" },
                    { value: "failed", label: "Failed" },
                    { value: "cooldown", label: "Cooldown" },
                  ]}
                />
                <button
                  onClick={handleExport}
                  disabled={exporting || logs.length === 0}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-[10px] font-black uppercase tracking-widest rounded-lg border border-emerald-100 dark:border-emerald-900/30 hover:bg-emerald-100 transition-all disabled:opacity-50"
                >
                  {exporting ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
                  Export
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar border border-slate-100 dark:border-slate-800 rounded-2xl bg-white dark:bg-slate-900 shadow-sm relative">
              <table className="w-full text-left text-xs">
                <thead className="sticky top-0 bg-slate-50 dark:bg-slate-800/90 backdrop-blur-md z-10">
                  <tr className="text-[10px] font-bold text-slate-400 uppercase tracking-widest shadow-[0_1px_2px_rgba(0,0,0,0.05)] border-b border-slate-100 dark:border-slate-800">
                    <th className="px-4 py-3">Contact</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 text-right">Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50 dark:divide-slate-800/50">
                  {loading && logs.length === 0 ? (
                    <tr><td colSpan={3} className="px-4 py-12 text-center text-slate-300"><Loader2 className="animate-spin inline mr-2" size={16} /> Loading logs...</td></tr>
                  ) : (
                    logs.map((log, i) => (
                      <tr key={i} className="hover:bg-slate-50/50 transition-colors">
                        <td className="px-4 py-3">
                          <p className="font-bold text-slate-700 dark:text-slate-200">{log.name}</p>
                          <p className="text-[10px] text-slate-400 tabular-nums">{log.phone}</p>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex flex-col gap-1.5 items-start">
                            {getStatusPill(log)}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right text-[10px] text-slate-400 whitespace-nowrap">
                          {new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </td>
                      </tr>
                    ))
                  )}
                  {logs.length === 0 && !loading && (
                    <tr><td colSpan={3} className="px-4 py-12 text-center text-slate-400 text-xs italic">No delivery records yet.</td></tr>
                  )}
                </tbody>
              </table>
            </div>

            {logTotal > 50 && (
              <div className="flex justify-center gap-2 shrink-0">
                <button onClick={() => setLogPage(p => Math.max(0, p - 1))} disabled={logPage === 0} className="px-3 py-1 bg-white border border-slate-200 rounded-lg text-[10px] font-bold disabled:opacity-30">Prev</button>
                <button onClick={() => setLogPage(p => p + 1)} disabled={(logPage + 1) * 50 >= logTotal} className="px-3 py-1 bg-white border border-slate-200 rounded-lg text-[10px] font-bold disabled:opacity-30">Next</button>
              </div>
            )}
          </div>
        </div>
      </div>
      {/* Status Detail Modal (Message Passport) */}
      {viewingLog && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm" onClick={() => setViewingLog(null)} />
          <div className="relative w-full max-w-md bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden animate-in zoom-in-95 duration-200">
            <div className={`p-4 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center ${
              viewingLog.status?.toLowerCase() === 'failed' ? 'bg-rose-50/50 dark:bg-rose-500/5' : 
              viewingLog.status?.toLowerCase() === 'cooldown' ? 'bg-amber-50/50 dark:bg-amber-500/5' :
              'bg-slate-50 dark:bg-slate-800/50'
            }`}>
              <div className={`flex items-center gap-2 ${
                viewingLog.status?.toLowerCase() === 'failed' ? 'text-rose-600' : 
                viewingLog.status?.toLowerCase() === 'cooldown' ? 'text-amber-600' : 
                'text-indigo-600'
              }`}>
                {viewingLog.status?.toLowerCase() === 'failed' ? <AlertCircle size={18} /> : 
                 viewingLog.status?.toLowerCase() === 'cooldown' ? <Clock size={18} className="text-amber-500" /> : 
                 <Clock size={18} />}
                <h3 className="font-black text-xs uppercase tracking-widest">Message Status Details</h3>
              </div>
              <button onClick={() => setViewingLog(null)} className="p-1 hover:bg-white dark:hover:bg-slate-800 rounded-lg transition-colors">
                <X size={18} />
              </button>
            </div>
            
            <div className="p-6 space-y-6">
              {/* Recipient Info */}
              <div className="flex justify-between items-center bg-slate-50 dark:bg-slate-800/50 p-3 rounded-xl">
                <div className="min-w-0">
                  <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Recipient</p>
                  <p className="text-sm font-bold text-slate-900 dark:text-white truncate">{viewingLog.name || viewingLog.phone}</p>
                </div>
                <div className="text-right">
                  <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Status</p>
                  <p className={`text-xs font-black uppercase ${
                    viewingLog.status?.toLowerCase() === 'failed' ? 'text-rose-600' : 
                    viewingLog.status?.toLowerCase() === 'cooldown' ? 'text-amber-600' : 
                    'text-emerald-600'
                  }`}>
                    {viewingLog.status}
                  </p>
                </div>
              </div>

              {/* Time Info */}
              {viewingLog.timestamp && (
                <div className="space-y-1 pl-1">
                    <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Event Timestamp</p>
                    <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
                        {new Date(viewingLog.timestamp).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}
                    </p>
                </div>
              )}

              {/* Error Details if Failed or Cooldown */}
              {(viewingLog.status?.toLowerCase() === 'failed' || viewingLog.status?.toLowerCase() === 'cooldown') ? (
                <div className="space-y-4">
                  <div className={`p-4 rounded-xl border ${
                    viewingLog.status?.toLowerCase() === 'cooldown' ? 
                    'bg-amber-50/50 dark:bg-amber-500/5 border-amber-100 dark:border-amber-900/20' : 
                    'bg-rose-50/50 dark:bg-rose-500/5 border-rose-100 dark:border-rose-900/20'
                  }`}>
                    <p className={`text-[10px] font-bold uppercase tracking-wider mb-2 ${
                      viewingLog.status?.toLowerCase() === 'cooldown' ? 'text-amber-500' : 'text-rose-500'
                    }`}>
                      {viewingLog.status?.toLowerCase() === 'cooldown' ? 'Cooldown Warning:' : 'Failure Reason:'}
                    </p>
                    <p className="text-sm font-bold text-slate-800 dark:text-slate-100 leading-relaxed">
                      {parseMetaError(viewingLog.error || viewingLog.statusError || 'Unknown failure')}
                    </p>
                  </div>
                  
                  {(viewingLog.error || viewingLog.statusError) && (
                    <div className="space-y-2">
                      <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider ml-1">Technical Context:</p>
                      <div className="p-3 bg-slate-900 rounded-lg overflow-x-auto max-h-32">
                        <pre className={`text-[9px] font-mono tracking-tight leading-relaxed ${
                          viewingLog.status?.toLowerCase() === 'cooldown' ? 'text-amber-400' : 'text-rose-400'
                        }`}>
                          {viewingLog.error || viewingLog.statusError}
                        </pre>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="bg-emerald-50/50 dark:bg-emerald-500/5 p-4 rounded-xl border border-emerald-100 dark:border-emerald-900/20">
                  <p className="text-[10px] text-emerald-600 font-bold uppercase tracking-wider mb-2">Technical Confirmation:</p>
                  <p className="text-sm font-bold text-slate-800 dark:text-slate-100 leading-relaxed">
                    Meta Cloud API successfully accepted and processed this message.
                  </p>
                </div>
              )}

              {/* Meta ID Trace */}
              {(viewingLog.meta_id || viewingLog.meta_message_id) && (
                <div className="pt-4 border-t border-slate-100 dark:border-slate-800">
                    <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1">Meta Message ID:</p>
                    <div className="flex items-center gap-2 p-2 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-100 dark:border-slate-800">
                        <code className="text-[10px] text-slate-600 dark:text-slate-400 font-mono break-all">{viewingLog.meta_id || viewingLog.meta_message_id}</code>
                    </div>
                </div>
              )}
            </div>
            
            <div className="p-4 bg-slate-50 dark:bg-slate-800/80 border-t border-slate-100 dark:border-slate-800 flex justify-end">
              <button 
                onClick={() => setViewingLog(null)}
                className="px-6 py-2 bg-slate-900 dark:bg-white text-white dark:text-slate-900 rounded-lg text-[10px] font-black uppercase tracking-widest hover:scale-105 active:scale-95 transition-all shadow-md"
              >
                Close Details
              </button>
            </div>
          </div>
        </div>
      )}
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
  const [sort, setSort] = useState<{ column: string; order: 'asc' | 'desc' }>({ column: 'created_at', order: 'desc' });

  useEffect(() => {
    const fetch = async () => {
      setLoading(true);
      try {
        const res = await whatsappApi.getCampaigns({
          skip: page * limit,
          limit,
          search: search || undefined,
          status: filter === 'all' ? undefined : filter,
          sort_by: sort.column,
          sort_order: sort.order
        });
        setCampaigns(res.items || []);
        setTotal(res.total || 0);
      } catch (err) { console.error(err); } finally { setLoading(false); }
    };
    fetch();
  }, [page, limit, search, filter, sort]);

  const handleSort = (column: string) => {
    setSort(prev => ({
      column,
      order: prev.column === column && prev.order === 'asc' ? 'desc' : 'asc'
    }));
  };

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
            total_contacts: payload.total || c.total_contacts, // FE-FIX: Sync total contacts live
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
          total_contacts: payload.total || prev.total_contacts, // FE-FIX: Sync total contacts live
          status: payload.status as any
        }) : null);
      }
    });

    return unsub;
  }, [selectedCampaign]);

  // BE-FIX: Summary counter updates from Webhook Statuses
  useEffect(() => {
    const unsub = wsService.subscribe('status_update', (payload) => {
      setCampaigns(prev => prev.map(c => {
        if (c.id === payload.campaign_id) {
          const newDelivered = payload.status === 'delivered' ? c.delivered_count + 1 : c.delivered_count;
          const newRead = payload.status === 'read' ? c.read_count + 1 : c.read_count;
          
          return {
            ...c,
            delivered_count: newDelivered,
            read_count: newRead
          };
        }
        return c;
      }));
    });
    return unsub;
  }, []);

  const { success, error: toastError, warning, info: toastInfo } = useToast();

  const handleDelete = async (campaignId: string) => {
    toastInfo('Processing Request', 'Attempting to delete campaign...');

    try {
      await whatsappApi.deleteCampaign(campaignId);
      setCampaigns(prev => prev.filter(c => c.id !== campaignId));
      setSelectedCampaign(null);
      success('Campaign deleted', 'The campaign has been removed.');
    } catch (err: any) {
      toastError('Delete failed', err.response?.data?.detail || "Failed to delete campaign. Ensure it is not currently running.");
    }
  };

  const handlePause = async (id: string) => {
    try {
      await whatsappApi.pauseCampaign(id);
      // FE-FIX FE-6: Update local state immediately — without this, button still shows
      // 'Pause' after clicking and user has to refresh the page to see the change.
      setCampaigns(prev => prev.map(c => c.id === id ? { ...c, status: 'paused' as const } : c));
      if (selectedCampaign?.id === id) setSelectedCampaign(prev => prev ? { ...prev, status: 'paused' as const } : null);
      warning('Campaign paused', 'The campaign has been paused.');
    } catch (err: any) {
      toastError('Pause failed', err.response?.data?.detail || "Failed to pause campaign");
    }
  };

  const handleResume = async (id: string) => {
    try {
      await whatsappApi.resumeCampaign(id);
      // FE-FIX FE-6: Update local state immediately after resume.
      setCampaigns(prev => prev.map(c => c.id === id ? { ...c, status: 'running' as const } : c));
      if (selectedCampaign?.id === id) setSelectedCampaign(prev => prev ? { ...prev, status: 'running' as const } : null);
      success('Campaign resumed', 'The campaign is running again.');
    } catch (err: any) {
      toastError('Resume failed', err.response?.data?.detail || "Failed to resume campaign");
    }
  };

  return (
    <>
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

        {loading && campaigns.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-32 gap-4">
            <Loader2 className="animate-spin text-indigo-600" size={40} />
            <p className="text-sm font-bold text-slate-400 uppercase tracking-widest">Loading Campaigns</p>
          </div>
        ) : campaigns.length === 0 ? (
          <div className="text-center py-32 border-2 border-dashed border-slate-100 dark:border-slate-800 rounded-2xl">
            <Send className="mx-auto text-slate-200 dark:text-slate-700 mb-4" size={48} />
            <p className="text-slate-500 font-bold">No campaigns found</p>
          </div>
        ) : (
          <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden flex flex-col">
            <div className="p-4 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">Active Runs</h3>
            </div>
            <div className="h-[60vh] overflow-auto custom-scrollbar relative">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 z-10 bg-white dark:bg-slate-900 shadow-sm">
                  <tr className="border-b border-slate-100 dark:border-slate-800 text-[10px] font-black text-slate-400 uppercase tracking-[0.15em] whitespace-nowrap">
                    <SortHeader label="Status" column="status" currentSort={sort} onSort={handleSort} />
                    <SortHeader label="Campaign Name" column="name" currentSort={sort} onSort={handleSort} />
                    <SortHeader label="Template" column="template_name" currentSort={sort} onSort={handleSort} />
                    <SortHeader label="Sent" column="sent_count" currentSort={sort} onSort={handleSort} />
                    <th className="px-5 py-4 bg-white dark:bg-slate-900 font-black uppercase">Success Rate</th>
                    <th className="px-5 py-4 bg-white dark:bg-slate-900 font-black uppercase">Progress</th>
                    <SortHeader label="Created" column="created_at" currentSort={sort} onSort={handleSort} />
                    <th className="px-5 py-4 bg-white dark:bg-slate-900 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800/50">
                  {campaigns.map(c => {
                    const cfg = STATUS_CONFIG[c.status] || { label: c.status, color: 'text-slate-500 bg-slate-100 border-slate-200', dot: 'bg-slate-400' };
                    const deliveryRate = c.sent_count > 0 ? ((c.delivered_count / c.sent_count) * 100).toFixed(1) : '0.0';
                    const progress = c.total_contacts > 0 ? Math.round((c.sent_count / c.total_contacts) * 100) : 0;

                    return (
                      <tr key={c.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors group whitespace-nowrap font-bold">
                        <td className="px-5 py-3">
                          <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-lg text-[10px] font-black uppercase tracking-tighter border ${cfg.color}`}>
                            <div className={`w-1 h-1 rounded-full ${cfg.dot}`} />
                            {cfg.label}
                          </span>
                        </td>
                        <td className="px-5 py-3 cursor-pointer" onClick={() => setSelectedCampaign(c)}>
                          <span className="text-slate-900 dark:text-white group-hover:text-indigo-600 transition-colors">{c.name}</span>
                        </td>
                        <td className="px-5 py-3 text-slate-500 dark:text-slate-400 font-medium">
                          {c.template_name}
                        </td>
                        <td className="px-5 py-3 tabular-nums text-slate-900 dark:text-white">
                          {c.sent_count.toLocaleString()}
                        </td>
                        <td className="px-5 py-3 tabular-nums text-indigo-600 dark:text-indigo-400">
                          {deliveryRate}%
                        </td>
                        <td className="px-5 py-3 min-w-[120px]">
                          <div className="flex flex-col gap-1.5">
                            <div className="flex justify-between items-center text-[9px] font-black uppercase">
                              <span className="text-slate-400">{c.sent_count} / {c.total_contacts}</span>
                              <span className="text-slate-900 dark:text-white">{progress}%</span>
                            </div>
                            <ProgressBar value={c.sent_count} total={c.total_contacts} color="bg-indigo-600 dark:bg-indigo-500" />
                          </div>
                        </td>
                        <td className="px-5 py-3 text-slate-400 tabular-nums">
                          {new Date(c.created_at || '').toLocaleDateString()}
                        </td>
                        <td className="px-5 py-3">
                          <div className="flex justify-end gap-2">
                            {c.status === 'running' && <button onClick={() => handlePause(c.id)} className="p-1.5 bg-amber-50 text-amber-600 rounded-lg hover:bg-amber-100" title="Pause"><Pause size={14} fill="currentColor" /></button>}
                            {c.status === 'paused' && <button onClick={() => handleResume(c.id)} className="p-1.5 bg-indigo-50 text-indigo-600 rounded-lg hover:bg-indigo-100" title="Resume"><Play size={14} fill="currentColor" /></button>}
                            <button onClick={() => setSelectedCampaign(c)} className="p-1.5 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 rounded-lg hover:bg-slate-200" title="View Details"><BarChart3 size={14} /></button>
                            <button onClick={() => handleDelete(c.id)} className="p-1.5 bg-rose-50 text-rose-600 rounded-lg hover:bg-rose-100" title="Delete"><Trash2 size={14} /></button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {total > 0 && (
          <div className="p-4 border-t border-slate-100 dark:border-slate-800 flex justify-between items-center bg-slate-50/30">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest pl-2">
              Sync: {page * limit + 1} - {Math.min((page + 1) * limit, total)} of {total}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage(p => Math.max(0, p - 1))}
                disabled={page === 0}
                className="p-2 border border-slate-200 dark:border-slate-700 rounded-lg disabled:opacity-20 hover:bg-white transition-all shadow-sm text-slate-600 dark:text-slate-400"
              >
                <ChevronLeft size={16} />
              </button>
              <button
                onClick={() => setPage(p => p + 1)}
                disabled={(page + 1) * limit >= total}
                className="p-2 border border-slate-200 dark:border-slate-700 rounded-lg disabled:opacity-20 hover:bg-white transition-all shadow-sm text-slate-600 dark:text-slate-400"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        )}

      </div>

      {showCreate && <CreateCampaignModal onClose={() => setShowCreate(false)} onCreate={(c) => setCampaigns([c, ...campaigns])} />}

      {selectedCampaign && (
        <CampaignDetailPanel
          campaign={selectedCampaign}
          onClose={() => setSelectedCampaign(null)}
          onPause={handlePause}
          onResume={handleResume}
          onDelete={handleDelete}
        />
      )}
    </>
  );
};


export default Campaigns;
