import React, { useState, useEffect, useMemo } from 'react';
import {
  FileText,
  Plus,
  RefreshCw,
  CheckCircle2,
  Clock,
  XCircle,
  Search,
  Layers,
  X,
  Zap,
  ChevronRight,
  Info,
  Loader2,
  Image as ImageIcon,
  Video,
  File as FileIcon,
  Type,
  Smartphone,
  ExternalLink,
  MessageSquare,
  Trash2,
  AlertCircle
} from 'lucide-react';
import { whatsappApi, Template } from '../services/whatsappApi';
import PageHeader from '../components/PageHeader';

const TEMPLATE_LIBRARY = [
  {
    category: 'MARKETING',
    title: 'Flash Sale Promo',
    description: 'Perfect for limited-time offers and discounts.',
    name: 'flash_sale_promo',
    headerType: 'IMAGE',
    body: '🔥 *FLASH SALE!* 🔥\n\nHi {{1}}, get ready for our biggest sale yet! Use code *SAVE20* to get 20% OFF your entire order.\n\nShop now: {{2}}',
    footer: 'Limited time only. T&C apply.',
    buttons: [{ type: 'URL', text: 'Shop Now', url: 'https://example.com' }]
  },
  {
    category: 'UTILITY',
    title: 'Order Confirmation',
    description: 'Send automated order updates to your customers.',
    name: 'order_update',
    headerType: 'TEXT',
    headerText: 'Order #{{1}}',
    body: 'Great news {{2}}! Your order has been confirmed and is being prepared for shipping.\n\nYou can track your package here: {{3}}',
    footer: 'Thank you for choosing Adcom!',
    buttons: [{ type: 'URL', text: 'Track Order', url: 'https://example.com/track' }]
  },
  {
    category: 'AUTHENTICATION',
    title: 'Secure OTP',
    description: 'Standard security code for user authentication.',
    name: 'secure_auth_code',
    headerType: 'NONE',
    body: 'Your Adcom security code is: *{{1}}*.\n\nThis code expires in 10 minutes. Do not share it with anyone.',
    footer: 'Security Alert',
    buttons: [{ type: 'OTP', text: 'Copy Code', otp_type: 'COPY_CODE' }]
  },
  {
    category: 'MARKETING',
    title: 'Abandoned Cart',
    description: 'Recover lost sales by reminding customers of their cart.',
    name: 'cart_recovery',
    headerType: 'IMAGE',
    body: '👋 Hi {{1}}! You left something special in your cart.\n\nWe have saved your items for you. Click below to complete your purchase and get free shipping! 🚚',
    footer: 'Free shipping on all recovered orders.',
    buttons: [{ type: 'URL', text: 'Complete Purchase', url: 'https://example.com/cart' }]
  }
];

const TemplatePreview: React.FC<{
  name: string;
  headerType: string;
  headerText: string;
  headerUrl: string;
  body: string;
  footer: string;
  buttons: any[];
}> = ({ name, headerType, headerText, headerUrl, body, footer, buttons }) => {
  return (
    <div className="w-full max-w-[300px] border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-xl bg-[#e5ddd5] dark:bg-slate-950 p-4 font-sans">
      <div className="bg-white dark:bg-slate-900 rounded-lg shadow-sm overflow-hidden flex flex-col">
        {/* Header Preview */}
        {headerType !== 'NONE' && (
          <div className="bg-slate-100 dark:bg-slate-800 p-0 overflow-hidden min-h-[40px] flex items-center justify-center border-b border-slate-100 dark:border-slate-800">
            {headerType === 'TEXT' ? (
              <div className="p-3 w-full font-bold text-sm text-slate-800 dark:text-white break-words">{headerText || 'Header Text'}</div>
            ) : headerType === 'IMAGE' ? (
              headerUrl ? <img src={headerUrl} alt="Preview" className="w-full h-32 object-cover" /> : <div className="p-8 flex flex-col items-center gap-2 text-slate-400"><ImageIcon size={24} /> <span className="text-[10px] uppercase font-bold">Image Header</span></div>
            ) : headerType === 'VIDEO' ? (
              <div className="p-8 flex flex-col items-center gap-2 text-slate-400 w-full bg-slate-200 dark:bg-slate-800"><Video size={24} /> <span className="text-[10px] uppercase font-bold">Video Header</span></div>
            ) : (
              <div className="p-8 flex flex-col items-center gap-2 text-slate-400 w-full bg-slate-200 dark:bg-slate-800"><FileIcon size={24} /> <span className="text-[10px] uppercase font-bold">Document Header</span></div>
            )}
          </div>
        )}

        {/* Body Preview */}
        <div className="p-3 text-[13px] leading-relaxed text-slate-800 dark:text-slate-200 whitespace-pre-wrap break-words">
          {body || 'Message body content...'}
        </div>

        {/* Footer Preview */}
        {footer && (
          <div className="px-3 pb-2 text-[11px] text-slate-400 dark:text-slate-500 italic">
            {footer}
          </div>
        )}
      </div>

      {/* Buttons Preview */}
      {buttons.length > 0 && (
        <div className="mt-2 space-y-1">
          {buttons.map((btn, i) => (
            <div key={i} className="bg-white dark:bg-slate-900 rounded-lg py-2 flex items-center justify-center gap-2 text-indigo-600 dark:text-indigo-400 text-xs font-bold shadow-sm border border-slate-100 dark:border-slate-800">
              {btn.type === 'URL' ? <ExternalLink size={12} /> : btn.type === 'PHONE_NUMBER' ? <Smartphone size={12} /> : <MessageSquare size={12} />}
              {btn.text || 'Button text'}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const Templates: React.FC = () => {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [showOnlyApproved, setShowOnlyApproved] = useState(false);

  // Form State
  const [newName, setNewName] = useState('');
  const [newCategory, setNewCategory] = useState('MARKETING');
  const [newBody, setNewBody] = useState('');
  const [newFooter, setNewFooter] = useState('');
  const [headerType, setHeaderType] = useState('NONE');
  const [headerText, setHeaderText] = useState('');
  const [headerUrl, setHeaderUrl] = useState('');
  const [buttons, setButtons] = useState<any[]>([]);
  const [submitToMeta, setSubmitToMeta] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isUploadingMedia, setIsUploadingMedia] = useState(false);
  const [localPreviewUrl, setLocalPreviewUrl] = useState('');
  const [mediaId, setMediaId] = useState('');
  const [variableMappings, setVariableMappings] = useState<Record<string, string>>({});
  const [bodyVariables, setBodyVariables] = useState<string[]>([]);
  const [isEditing, setIsEditing] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [isLibraryOpen, setIsLibraryOpen] = useState(false);

  // Configure Modal State
  const [configTemplate, setConfigTemplate] = useState<Template | null>(null);
  const [isConfigModalOpen, setIsConfigModalOpen] = useState(false);

  const contactFields = [
    { label: 'Contact Name', value: 'contact.name' },
    { label: 'Phone Number', value: 'contact.phone_number' },
    { label: 'Company Name', value: 'contact.company_name' },
    { label: 'City', value: 'contact.city' },
    { label: 'Category', value: 'contact.category' },
    { label: 'Manual Text', value: 'manual' },
  ];

  const templateVariables = useMemo(() => {
    const vars = new Set<string>();
    const matches = newBody.match(/\{\{(\d+)\}\}/g);
    if (matches) matches.forEach(m => vars.add(m.replace(/\{\{|\}\}/g, '')));
    return Array.from(vars).sort((a, b) => parseInt(a) - parseInt(b));
  }, [newBody]);

  const configTemplateVariables = useMemo(() => {
    if (!configTemplate) return [];
    const vars = new Set<string>();
    const bodyComp = configTemplate.components.find((c: any) => c.type === 'BODY');
    if (bodyComp && typeof bodyComp.text === 'string') {
      const matches = bodyComp.text.match(/\{\{(\d+)\}\}/g);
      if (matches) matches.forEach((m: string) => vars.add(m.replace(/\{\{|\}\}/g, '')));
    }
    return Array.from(vars).sort((a, b) => parseInt(a) - parseInt(b));
  }, [configTemplate]);

  const fetchTemplates = async () => {
    setLoading(true);
    try {
      const data = await whatsappApi.getTemplates();
      setTemplates(data);
    } catch (error) {
      console.error('Error fetching templates:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTemplates();
  }, []);

  const filteredTemplates = useMemo(() => {
    return templates.filter(t => {
      const matchesSearch = t.name.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesStatus = showOnlyApproved ? t.status === 'APPROVED' : true;
      return matchesSearch && matchesStatus;
    });
  }, [templates, searchQuery, showOnlyApproved]);

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      await whatsappApi.syncTemplates();
      await fetchTemplates();
    } catch (error) {
      console.error('Error syncing templates:', error);
    } finally {
      setIsSyncing(false);
    }
  };

  const addButton = (type: 'QUICK_REPLY' | 'URL' | 'PHONE_NUMBER') => {
    if (buttons.length >= 10) return;
    const newBtn = { type, text: '' };
    if (type === 'URL') (newBtn as any).url = '';
    if (type === 'PHONE_NUMBER') (newBtn as any).phone_number = '';
    setButtons([...buttons, newBtn]);
  };

  const removeButton = (index: number) => {
    setButtons(buttons.filter((_, i) => i !== index));
  };

  const updateButton = (index: number, fields: any) => {
    const next = [...buttons];
    next[index] = { ...next[index], ...fields };
    setButtons(next);
  };

  const handleDelete = async (id: string, name: string) => {
    if (!window.confirm(`Are you sure you want to delete template "${name}"? This will attempt to delete it permanently from Meta (WhatsApp) as well.`)) return;

    setLoading(true);
    try {
      await whatsappApi.deleteTemplate(id);
      await fetchTemplates();
    } catch (error: any) {
      const msg = error.response?.data?.detail || 'Failed to delete template';
      alert(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (tpl: Template) => {
    resetForm();
    setIsEditing(true);
    setEditId(tpl.id);
    setNewName(tpl.name);
    setNewCategory(tpl.category);

    // Extract components
    const h = tpl.components.find(c => c.type === 'HEADER');
    if (h) {
      setHeaderType(h.format);
      if (h.format === 'TEXT') setHeaderText(h.text || '');
      // For media, we don't necessarily have the URL back, but we can try
      if (h.example?.header_handle?.[0]) setHeaderUrl(h.example.header_handle[0]);
    }

    const b = tpl.components.find(c => c.type === 'BODY');
    if (b) setNewBody(b.text || '');

    const f = tpl.components.find(c => c.type === 'FOOTER');
    if (f) setNewFooter(f.text || '');

    const btns = tpl.components.find(c => c.type === 'BUTTONS');
    if (btns && btns.buttons) {
      setButtons(btns.buttons.map((btn: any) => ({
        type: btn.type,
        text: btn.text,
        url: btn.url,
        phone_number: btn.phone_number
      })));
    }

    setIsModalOpen(true);
  };

  const extractVariables = (text: string) => {
    const matches = text.match(/\{\{(\d+)\}\}/g);
    if (!matches) return [];
    return matches.map(v => v.replace(/\{\{|\}\}/g, ''));
  };

  const cleanText = (text: string) => {
    return text.replace(/[^\x00-\x7F]/g, ""); // removes emoji/special chars
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();

    // ✅ Validation: Body must NOT end with a variable like {{1}}
    const trimmedBody = newBody.trim();
    if (/\{\{\d+\}\}$/.test(trimmedBody)) {
      alert('⚠️ Invalid Template Body\n\nYour message cannot end with a variable like {{1}}.\nPlease add some text after the variable.\n\nExample: "Hi {{1}}, welcome!" ✅\nInvalid:  "Hi {{1}}" ❌');
      return;
    }

    setIsSubmitting(true);
    try {
      const components = [];

      // Add Header
      if (headerType !== 'NONE') {
        const header: any = { type: 'HEADER', format: headerType };
        if (headerType === 'TEXT') {
          header.text = headerText;
        } else {
          if (!headerUrl) {
            alert('Please upload a header file before submitting.');
            setIsSubmitting(false);
            return;
          }
          header.example = { header_handle: [headerUrl] };
        }
        components.push(header);
      }

      // Add Body
      const cleanedBody = cleanText(newBody);
      const vars = extractVariables(cleanedBody);

      let bodyComponent: any = {
        type: 'BODY',
        text: cleanedBody
      };

      // ✅ Add example if variables exist
      if (vars.length > 0) {
        bodyComponent.example = {
          body_text: vars.map((v, i) => {
            if (variableMappings[v] && !variableMappings[v].startsWith('contact.')) {
              return variableMappings[v]; // manual value
            }
            return `sample_${i + 1}`; // fallback
          })
        };
      }

      components.push(bodyComponent);

      // Add Footer
      if (newFooter.trim()) {
        components.push({ type: 'FOOTER', text: newFooter });
      }

      // Add Buttons
      if (buttons.length > 0) {
        components.push({
          type: 'BUTTONS',
          buttons: buttons.map(b => {
            const btn: any = { type: b.type, text: b.text };
            if (b.type === 'URL') btn.url = b.url || 'https://example.com';
            if (b.type === 'PHONE_NUMBER') btn.phone_number = b.phone_number || '+1234567890';
            if (b.type === 'OTP') btn.otp_type = b.otp_type || 'COPY_CODE';
            return btn;
          })
        });
      }

      const payload: any = {
        name: newName.toLowerCase().trim().replace(/[^a-z0-9_]+/g, '_').replace(/^_+|_+$/g, ''),
        category: newCategory,
        language: 'en_US',
        components: components,
        submit_to_meta: submitToMeta,
        variable_mappings: Object.keys(variableMappings).length > 0 ? variableMappings : undefined,
        media_id: mediaId || undefined
      };

      if (isEditing && editId) {
        if (!window.confirm("Editing an approved template requires deleting the old version and re-submitting for approval. New approving usually takes 1-24 hours. Continue?")) {
          setIsSubmitting(false);
          return;
        }
        await whatsappApi.updateTemplate(editId, payload);
      } else {
        await whatsappApi.createTemplate(payload);
      }

      setIsModalOpen(false);
      resetForm();
      fetchTemplates();
    } catch (error: any) {
      alert(error.response?.data?.detail || 'Failed to process template');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleMediaUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Show local preview immediately
    if (file.type.startsWith('image/')) {
      const objectUrl = URL.createObjectURL(file);
      setLocalPreviewUrl(objectUrl);
    } else {
      setLocalPreviewUrl('');
    }

    setIsUploadingMedia(true);
    try {
      // 1. Upload for Meta Template Approval (Resumable Session) -> gets `handle`
      const res = await whatsappApi.uploadTemplateMedia(file);
      setHeaderUrl(res.handle);

      // 2. Upload for Actual Campaign Sending (Direct Upload) -> gets `media_id`
      const campaignMediaRes = await whatsappApi.uploadCampaignMedia(file);
      setMediaId(campaignMediaRes.id);
    } catch (error: any) {
      alert(`Upload failed: ${error.response?.data?.detail || error.message}`);
    } finally {
      setIsUploadingMedia(false);
    }
  };

  const resetForm = () => {
    setNewName('');
    setNewCategory('MARKETING');
    setNewBody('');
    setNewFooter('');
    setHeaderType('NONE');
    setHeaderText('');
    setHeaderUrl('');
    setLocalPreviewUrl('');
    setButtons([]);
    setMediaId('');
    setVariableMappings({});
    setIsEditing(false);
    setEditId(null);
    setIsLibraryOpen(false);
  };

  const loadLibraryTemplate = (item: any) => {
    resetForm();
    setNewName(item.name);
    setNewCategory(item.category);
    setNewBody(item.body);
    setNewFooter(item.footer);
    setHeaderType(item.headerType);
    setHeaderText(item.headerText || '');
    setButtons(item.buttons || []);
    setIsLibraryOpen(false);
    setIsModalOpen(true);
  };

  const getStatusBadge = (status: string) => {
    switch (status.toUpperCase()) {
      case 'APPROVED': return <span className="flex items-center gap-1.5 px-2 py-1 rounded bg-emerald-50 text-emerald-600 border border-emerald-100 text-[10px] font-bold uppercase tracking-wider"><CheckCircle2 size={12} /> Approved</span>;
      case 'PENDING': return <span className="flex items-center gap-1.5 px-2 py-1 rounded bg-amber-50 text-amber-600 border border-amber-100 text-[10px] font-bold uppercase tracking-wider"><Clock size={12} /> Pending</span>;
      case 'REJECTED': return <span className="flex items-center gap-1.5 px-2 py-1 rounded bg-rose-50 text-rose-600 border border-rose-100 text-[10px] font-bold uppercase tracking-wider"><XCircle size={12} /> Rejected</span>;
      default: return <span className="flex items-center gap-1.5 px-2 py-1 rounded bg-slate-50 text-slate-500 border border-slate-100 text-[10px] font-bold uppercase tracking-wider">{status}</span>;
    }
  };

  return (
    <div className="space-y-8 font-sans">
      <PageHeader
        title="Templates"
        description="Manage and sync your WhatsApp message blueprints"
        actions={
          <div className="flex gap-3">
            <button onClick={handleSync} disabled={isSyncing} className="flex items-center gap-2 px-4 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-200 rounded-lg text-sm font-bold hover:bg-slate-50 transition-all">
              <RefreshCw size={18} className={isSyncing ? 'animate-spin' : ''} /> Sync Meta
            </button>
            <button onClick={() => setIsLibraryOpen(true)} className="flex items-center gap-2 px-4 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-indigo-600 dark:text-indigo-400 rounded-lg text-sm font-bold shadow-sm hover:bg-slate-50 transition-all">
              <Layers size={18} /> Library
            </button>
            <button onClick={() => { resetForm(); setIsModalOpen(true); }} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-bold shadow-sm hover:bg-indigo-700 transition-all">
              <Plus size={18} /> New Template
            </button>
          </div>
        }
      />

      <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col md:flex-row gap-4 items-center justify-between">
        <div className="flex items-center gap-4 w-full md:w-auto">
          <div className="relative flex-1 md:flex-none">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
            <input value={searchQuery} onChange={e => setSearchQuery(e.target.value)} placeholder="Search templates..." className="w-full md:w-80 pl-10 pr-4 py-2 bg-slate-50 dark:bg-slate-800 border-none rounded-lg text-sm outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all" />
          </div>
          <div className="flex bg-slate-50 dark:bg-slate-800 p-1 rounded-lg">
            <button onClick={() => setShowOnlyApproved(false)} className={`px-4 py-1.5 rounded-md text-xs font-bold transition-all ${!showOnlyApproved ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm' : 'text-slate-400 hover:text-slate-600'}`}>All</button>
            <button onClick={() => setShowOnlyApproved(true)} className={`px-4 py-1.5 rounded-md text-xs font-bold transition-all ${showOnlyApproved ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm' : 'text-slate-400 hover:text-slate-600'}`}>Approved</button>
          </div>
        </div>
        <div className="hidden md:flex items-center gap-6 text-center">
          <div className="space-y-0.5"><p className="text-[10px] font-bold text-slate-400 uppercase">Approved</p><p className="text-xl font-bold text-emerald-600 tabular-nums">{templates.filter(t => t.status === 'APPROVED').length}</p></div>
          <div className="space-y-0.5"><p className="text-[10px] font-bold text-slate-400 uppercase">Pending</p><p className="text-xl font-bold text-amber-500 tabular-nums">{templates.filter(t => t.status === 'PENDING').length}</p></div>
          <div className="space-y-0.5"><p className="text-[10px] font-bold text-slate-400 uppercase">Rejected</p><p className="text-xl font-bold text-rose-500 tabular-nums">{templates.filter(t => t.status === 'REJECTED').length}</p></div>
        </div>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-32 gap-4">
          <Loader2 className="animate-spin text-indigo-600" size={40} />
          <p className="text-sm font-bold text-slate-400 uppercase tracking-widest leading-none">Loading Templates</p>
        </div>
      ) : filteredTemplates.length === 0 ? (
        <div className="text-center py-32 border-2 border-dashed border-slate-100 dark:border-slate-800 rounded-2xl">
          <FileText className="mx-auto text-slate-200 dark:text-slate-700 mb-4" size={48} />
          <p className="text-slate-500 font-bold">No templates found</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredTemplates.map(template => (
            <div key={template.id} className="bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col hover:border-indigo-500 transition-all group overflow-hidden">
              <div className="flex justify-between items-start mb-6">
                {getStatusBadge(template.status)}
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">{template.category}</span>
              </div>
              <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-4 line-clamp-1">{template.name.replace(/_/g, ' ')}</h3>

              {template.status === 'REJECTED' && template.rejection_reason && (
                <div className="mb-4 p-2 bg-rose-50 dark:bg-rose-500/10 border border-rose-100 dark:border-rose-500/20 rounded-lg text-[10px] text-rose-600 font-bold italic line-clamp-2">
                  Reason: {template.rejection_reason}
                </div>
              )}

              <div className="flex-1 bg-slate-50 dark:bg-slate-800/50 p-4 rounded-lg border border-slate-100 dark:border-slate-700/50 mb-6 font-mono text-xs text-slate-600 dark:text-slate-400 line-clamp-4 leading-relaxed group-hover:line-clamp-none transition-all">
                {template.components.find(c => c.type === 'HEADER' && c.format === 'TEXT')?.text && (
                  <span className="block font-bold mb-1">[H] {template.components.find(c => c.type === 'HEADER' && c.format === 'TEXT')?.text}</span>
                )}
                {template.components.find(c => c.type === 'BODY')?.text || 'No content'}
              </div>

              <div className="flex gap-2 mb-4 opacity-0 group-hover:opacity-100 transition-all translate-y-2 group-hover:translate-y-0 text-[10px] font-bold uppercase">
                <button onClick={() => {
                  setConfigTemplate(template);
                  setVariableMappings((template as any).variable_mappings || {});
                  setMediaId((template as any).media_id || '');
                  setIsConfigModalOpen(true);
                }} className="flex-1 flex items-center justify-center gap-1 py-1.5 px-3 bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 rounded-lg hover:bg-indigo-100"><Layers size={12} /> Config</button>
                <button onClick={() => handleEdit(template)} className="flex-1 flex items-center justify-center gap-1 py-1.5 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 rounded-lg hover:bg-slate-200"><RefreshCw size={12} /> Edit</button>
                <button onClick={() => handleDelete(template.id, template.name)} className="flex items-center justify-center p-1.5 bg-rose-50 dark:bg-rose-500/10 text-rose-600 rounded-lg hover:bg-rose-100 transition-all active:scale-95"><Trash2 size={14} /></button>
              </div>

              <div className="pt-4 border-t border-slate-50 dark:border-slate-800 flex justify-between items-center text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                <span className="flex items-center gap-1">
                  {template.components.some(c => c.type === 'HEADER' && c.format !== 'TEXT') && <ImageIcon size={10} />}
                  {template.components.some(c => c.type === 'BUTTONS') && <Zap size={10} />}
                  {template.language}
                </span>
                {template.last_synced_at && <span>Synced {new Date(template.last_synced_at).toLocaleDateString()}</span>}
              </div>
            </div>
          ))}
        </div>
      )}

      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-md">
          <div className="bg-white dark:bg-zinc-950 w-full max-w-6xl h-[90vh] rounded-3xl border border-slate-200 dark:border-white/10 shadow-2xl overflow-hidden flex flex-col scale-in-center">

            {/* Modal Header */}
            <div className="px-8 py-6 border-b border-slate-100 dark:border-white/5 flex justify-between items-center bg-white dark:bg-zinc-950">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-2xl bg-indigo-600 flex items-center justify-center text-white shadow-xl shadow-indigo-500/20"><Zap size={24} /></div>
                <div>
                  <h2 className="text-xl font-bold text-slate-900 dark:text-white">{isEditing ? 'Edit Template' : 'Template Builder'}</h2>
                  <p className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mt-0.5">Design, Preview & Submit to Meta</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <button onClick={() => setIsLibraryOpen(true)} className="flex items-center gap-2 px-4 py-2 bg-slate-100 dark:bg-white/5 rounded-xl text-xs font-bold text-slate-600 dark:text-slate-300 hover:bg-slate-200 transition-all">
                  <Layers size={16} /> Browse Library
                </button>
                <button onClick={() => setIsModalOpen(false)} className="p-2 rounded-xl hover:bg-slate-100 dark:hover:bg-white/5 transition-all text-slate-400"><X size={24} /></button>
              </div>
            </div>

            <div className="flex-1 overflow-hidden flex flex-col lg:flex-row">
              {/* Construction Zone */}
              <div className="flex-1 overflow-y-auto p-8 space-y-10 custom-scrollbar">

                {/* Section 1: Identity */}
                <div className="space-y-6">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-2 h-2 rounded-full bg-indigo-600 shadow-lg shadow-indigo-500/50"></div>
                    <h3 className="text-xs font-black text-slate-900 dark:text-slate-300 uppercase tracking-[0.2em]">Template Identity</h3>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="group space-y-2">
                      <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest pl-1">Template Name</label>
                      <input
                        required
                        value={newName}
                        onChange={e => {
                          const sanitized = e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '_').replace(/_+/g, '_');
                          setNewName(sanitized);
                        }}
                        placeholder="e.g. seasonal_sale_2024"
                        disabled={isEditing}
                        className="w-full p-4 bg-slate-50 dark:bg-white/5 border border-transparent rounded-2xl text-sm font-bold focus:ring-2 focus:ring-indigo-500/20 focus:bg-white dark:focus:bg-zinc-900 transition-all outline-none disabled:opacity-50"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest pl-1">Category</label>
                      <select value={newCategory} onChange={e => setNewCategory(e.target.value)} className="w-full p-4 bg-slate-50 dark:bg-white/5 border border-transparent rounded-2xl text-sm font-bold focus:ring-2 focus:ring-indigo-500/20 focus:bg-white dark:focus:bg-zinc-900 transition-all outline-none cursor-pointer">
                        <option value="MARKETING">Marketing (Promotional)</option>
                        <option value="UTILITY">Utility (Transactional)</option>
                        <option value="AUTHENTICATION">Authentication (OTP)</option>
                      </select>
                    </div>
                  </div>
                </div>

                {/* Section 2: Header */}
                <div className="space-y-6">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-2 h-2 rounded-full bg-amber-500 shadow-lg shadow-amber-500/50"></div>
                    <h3 className="text-xs font-black text-slate-900 dark:text-slate-300 uppercase tracking-[0.2em]">Header (Visuals)</h3>
                  </div>
                  <div className="grid grid-cols-5 gap-3">
                    {[
                      { id: 'NONE', label: 'None', icon: X },
                      { id: 'TEXT', label: 'Title', icon: Type },
                      { id: 'IMAGE', label: 'Image', icon: ImageIcon },
                      { id: 'VIDEO', label: 'Video', icon: Video },
                      { id: 'DOCUMENT', label: 'Doc', icon: FileIcon },
                    ].map(h => (
                      <button key={h.id} type="button" onClick={() => setHeaderType(h.id)} className={`flex flex-col items-center justify-center gap-3 p-4 rounded-2xl border-2 transition-all duration-300 ${headerType === h.id ? 'border-indigo-600 bg-indigo-50/50 dark:bg-indigo-500/10 text-indigo-600 shadow-sm' : 'border-slate-50 dark:border-white/5 text-slate-400 hover:border-slate-200 dark:hover:border-white/10'}`}>
                        <h.icon size={22} className={headerType === h.id ? 'scale-110 transition-transform' : ''} />
                        <span className="text-[9px] font-black uppercase tracking-widest">{h.label}</span>
                      </button>
                    ))}
                  </div>

                  {headerType === 'TEXT' && (
                    <div className="animate-in fade-in slide-in-from-top-2 duration-300">
                      <input value={headerText} onChange={e => setHeaderText(e.target.value)} placeholder="Header text..." className="w-full p-4 bg-indigo-50/30 dark:bg-indigo-500/5 border border-indigo-100 dark:border-indigo-500/20 rounded-2xl text-sm font-bold outline-none focus:ring-2 focus:ring-indigo-500/20" />
                    </div>
                  )}
                  {(headerType === 'IMAGE' || headerType === 'VIDEO' || headerType === 'DOCUMENT') && (
                    <div className="space-y-4 animate-in fade-in slide-in-from-top-2 duration-300">
                      <div className="flex gap-4">
                        <input value={headerUrl} onChange={e => setHeaderUrl(e.target.value)} placeholder={`Enter sample ${headerType.toLowerCase()} URL or Handle...`} className="flex-1 p-4 bg-indigo-50/30 dark:bg-indigo-500/5 border border-indigo-100 dark:border-indigo-500/20 rounded-2xl text-sm font-bold outline-none" />
                        <div className="relative">
                          <input type="file" id="media-upload-builder" className="hidden" onChange={handleMediaUpload} accept={headerType === 'IMAGE' ? 'image/*' : headerType === 'VIDEO' ? 'video/*' : '.pdf,.doc,.docx'} />
                          <label htmlFor="media-upload-builder" className={`flex items-center gap-2 px-6 h-full rounded-2xl bg-indigo-600 text-white text-[10px] font-black uppercase tracking-widest cursor-pointer hover:bg-indigo-700 shadow-lg shadow-indigo-600/20 transition-all ${isUploadingMedia ? 'opacity-50 pointer-events-none' : ''}`}>
                            {isUploadingMedia ? <Loader2 size={16} className="animate-spin" /> : <ImageIcon size={16} />}
                            {isUploadingMedia ? 'Syncing...' : 'Upload'}
                          </label>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Section 3: Body */}
                <div className="space-y-6">
                  <div className="flex justify-between items-center mb-2">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-lg shadow-emerald-500/50"></div>
                      <h3 className="text-xs font-black text-slate-900 dark:text-slate-300 uppercase tracking-[0.2em]">Message Content</h3>
                    </div>
                    <span className="text-[10px] text-indigo-600 dark:text-indigo-400 font-bold px-3 py-1 bg-indigo-50 dark:bg-indigo-500/10 rounded-full italic">Variables: Use {"{{1}}"}, {"{{2}}"}...</span>
                  </div>
                  <textarea
                    required
                    rows={6}
                    value={newBody}
                    onChange={e => setNewBody(e.target.value)}
                    placeholder="Type your message body here. Meta likes professional, clear language."
                    className="w-full p-8 bg-slate-50 dark:bg-white/5 border border-transparent rounded-[2rem] text-sm leading-relaxed outline-none focus:ring-2 focus:ring-emerald-500/20 focus:bg-white dark:focus:bg-zinc-900 transition-all font-medium"
                  />
                </div>

                {/* Section 4: Footer & Buttons */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-10">
                  <div className="space-y-6">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="w-2 h-2 rounded-full bg-slate-400"></div>
                      <h3 className="text-xs font-black text-slate-900 dark:text-slate-300 uppercase tracking-[0.2em]">Footer</h3>
                    </div>
                    <input value={newFooter} onChange={e => setNewFooter(e.target.value)} placeholder="e.g. Reply STOP to opt-out" className="w-full p-4 bg-slate-50 dark:bg-white/5 border border-transparent rounded-2xl text-sm focus:ring-2 focus:ring-slate-300/20 outline-none" />
                  </div>

                  <div className="space-y-6">
                    <div className="flex justify-between items-center mb-2">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-rose-500 shadow-lg shadow-rose-500/50"></div>
                        <h3 className="text-xs font-black text-slate-900 dark:text-slate-300 uppercase tracking-[0.2em]">Actions</h3>
                      </div>
                      <div className="flex gap-2">
                        <button type="button" onClick={() => addButton('QUICK_REPLY')} className="p-2 rounded-lg bg-indigo-50 dark:bg-white/5 text-indigo-600 hover:bg-indigo-100 transition-all"><MessageSquare size={16} /></button>
                        <button type="button" onClick={() => addButton('URL')} className="p-2 rounded-lg bg-emerald-50 dark:bg-white/5 text-emerald-600 hover:bg-emerald-100 transition-all"><ExternalLink size={16} /></button>
                      </div>
                    </div>
                    <div className="space-y-3">
                      {buttons.length === 0 ? (
                        <div className="py-10 border-2 border-dashed border-slate-100 dark:border-white/5 rounded-2xl text-center text-[10px] font-black text-slate-300 uppercase tracking-widest">No Buttons</div>
                      ) : (
                        buttons.map((btn, i) => (
                          <div key={i} className="group p-4 bg-slate-50 dark:bg-white/5 rounded-2xl relative border border-transparent hover:border-indigo-500/20 transition-all animate-in zoom-in-95 duration-200">
                            <button type="button" onClick={() => removeButton(i)} className="absolute top-2 right-2 text-slate-300 hover:text-rose-500 transition-all"><X size={14} /></button>
                            <div className="space-y-3">
                              <input value={btn.text} onChange={e => updateButton(i, { text: e.target.value })} placeholder="Label..." className="w-full p-2 bg-white dark:bg-zinc-900 border border-slate-100 dark:border-white/5 rounded-xl text-xs font-bold outline-none" />
                              {btn.type === 'URL' && <input value={btn.url} onChange={e => updateButton(i, { url: e.target.value })} placeholder="https://..." className="w-full p-2 bg-white dark:bg-zinc-900 border border-slate-100 dark:border-white/5 rounded-xl text-xs outline-none" />}
                              {btn.type === 'PHONE_NUMBER' && <input value={btn.phone_number} onChange={e => updateButton(i, { phone_number: e.target.value })} placeholder="+123..." className="w-full p-2 bg-white dark:bg-zinc-900 border border-slate-100 dark:border-white/5 rounded-xl text-xs outline-none" />}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </div>

                {/* Section 5: Adcom Local Logic */}
                {(templateVariables.length > 0) && (
                  <div className="p-8 bg-indigo-600 rounded-[2.5rem] text-white shadow-2xl shadow-indigo-600/30 space-y-8 animate-in slide-in-from-bottom-5 duration-500">
                    <div className="flex items-center gap-4">
                      <div className="w-14 h-14 rounded-2xl bg-white/20 backdrop-blur-md flex items-center justify-center text-white"><Zap size={28} className="text-amber-300" /></div>
                      <div>
                        <h3 className="text-xl font-extrabold tracking-tight">Smart Variable Mapping</h3>
                        <p className="text-indigo-100/70 text-[10px] mt-0.5 uppercase tracking-[0.2em] font-black">Meta compliance & Data precision</p>
                      </div>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {templateVariables.map((v: string) => (
                        <div key={v} className="p-5 bg-white/10 backdrop-blur-md rounded-2xl border border-white/10 space-y-4">
                          <div className="flex justify-between items-center">
                            <span className="px-3 py-1 bg-white text-indigo-600 rounded-full text-xs font-black tracking-tighter">{"{{"}{v}{"}}"}</span>
                          </div>
                          <select
                            value={variableMappings[v]?.startsWith('contact.') ? variableMappings[v] : (variableMappings[v] ? 'manual' : '')}
                            onChange={(e) => {
                              const val = e.target.value;
                              setVariableMappings(prev => ({ ...prev, [v]: val === 'manual' ? '' : val }));
                            }}
                            className="w-full p-3 bg-white/10 border border-white/20 rounded-xl text-xs font-bold outline-none text-white focus:bg-white/20 transition-all"
                          >
                            <option value="" className="text-slate-900">Choose Source...</option>
                            {contactFields.map(f => <option key={f.value} value={f.value} className="text-slate-900">{f.label}</option>)}
                            <option value="manual" className="text-slate-900">Custom Manual Text</option>
                          </select>
                          {(!variableMappings[v]?.startsWith('contact.') || variableMappings[v] === 'manual') && (
                            <input
                              value={variableMappings[v] || ''}
                              onChange={e => setVariableMappings(prev => ({ ...prev, [v]: e.target.value }))}
                              placeholder="Enter static value..."
                              className="w-full p-3 bg-white/10 border border-white/20 rounded-xl text-xs outline-none text-white placeholder:text-white/50"
                            />
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Preview Zone (Right Panel) */}
              <div className="w-full lg:w-[450px] bg-slate-50 dark:bg-zinc-900/40 p-10 flex flex-col items-center justify-between border-l border-slate-100 dark:border-white/5 overflow-y-auto">
                <div className="w-full flex flex-col items-center">
                  <div className="flex items-center gap-2 mb-10 bg-white dark:bg-zinc-950 px-5 py-2.5 rounded-full shadow-lg border border-slate-100 dark:border-white/5">
                    <Smartphone size={16} className="text-indigo-600" />
                    <span className="text-[10px] font-black text-slate-500 dark:text-slate-400 uppercase tracking-[0.2em]">WhatsApp Preview</span>
                  </div>

                  <TemplatePreview
                    name={newName}
                    headerType={headerType}
                    headerText={headerText}
                    headerUrl={localPreviewUrl || (headerUrl?.startsWith('h/') ? '' : headerUrl)}
                    body={newBody}
                    footer={newFooter}
                    buttons={buttons}
                  />

                  <div className="mt-12 w-full space-y-6">
                    <div
                      onClick={() => setSubmitToMeta(!submitToMeta)}
                      className={`group p-5 rounded-3xl border-2 cursor-pointer transition-all duration-300 flex items-center gap-4 ${submitToMeta ? 'bg-indigo-600 border-indigo-500 shadow-2xl shadow-indigo-600/30' : 'bg-white dark:bg-white/5 border-slate-100 dark:border-white/5 hover:border-slate-200'}`}
                    >
                      <div className={`w-10 h-10 rounded-2xl flex items-center justify-center transition-all ${submitToMeta ? 'bg-white/20 text-white' : 'bg-slate-100 dark:bg-white/10 text-slate-400'}`}><Zap size={20} /></div>
                      <div className="flex-1">
                        <p className={`text-xs font-black uppercase tracking-widest ${submitToMeta ? 'text-white' : 'text-slate-900 dark:text-white'}`}>Auto-Sync</p>
                        <p className={`text-[10px] ${submitToMeta ? 'text-indigo-100' : 'text-slate-500'}`}>Dispatch to Meta instantly</p>
                      </div>
                      {submitToMeta && <CheckCircle2 className="text-white" size={24} />}
                    </div>
                  </div>
                </div>

                <div className="w-full flex gap-4 mt-10">
                  <button onClick={() => setIsModalOpen(false)} className="flex-1 py-4 px-6 bg-white dark:bg-white/5 border border-slate-200 dark:border-white/10 rounded-2xl text-[11px] font-black uppercase tracking-widest text-slate-500 hover:bg-slate-100 transition-all">Discard</button>
                  <button
                    onClick={handleCreate}
                    disabled={isSubmitting || !newName || !newBody}
                    className="flex-[2] py-4 px-6 bg-indigo-600 text-white rounded-2xl text-[11px] font-black uppercase tracking-[0.2em] shadow-2xl shadow-indigo-600/40 hover:bg-indigo-700 transition-all disabled:opacity-50 flex items-center justify-center gap-3"
                  >
                    {isSubmitting ? <RefreshCw className="animate-spin" size={20} /> : <CheckCircle2 size={20} />}
                    {isSubmitting ? 'Syncing...' : (isEditing ? 'Update & Sync' : 'Launch Template')}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Template Library Sidebar */}
      <div className={`fixed inset-y-0 right-0 z-[100] w-full max-w-sm bg-white dark:bg-slate-950 shadow-[0_0_100px_rgba(0,0,0,0.3)] border-l border-slate-100 dark:border-white/5 transition-transform duration-500 ease-in-out transform ${isLibraryOpen ? 'translate-x-0' : 'translate-x-full'}`}>
        <div className="flex flex-col h-full">
          <div className="p-8 border-b border-slate-100 dark:border-white/5 flex justify-between items-center bg-slate-50 dark:bg-zinc-950">
            <div>
              <h2 className="text-xl font-black text-slate-900 dark:text-white flex items-center gap-3">
                <Layers className="text-indigo-600" size={24} /> Library
              </h2>
              <p className="text-[10px] text-slate-400 font-bold uppercase tracking-[0.2em] mt-1">Premium Adcom Presets</p>
            </div>
            <button onClick={() => setIsLibraryOpen(false)} className="p-2.5 hover:bg-slate-200 dark:hover:bg-white/10 rounded-2xl text-slate-400 transition-all"><X size={24} /></button>
          </div>
          <div className="flex-1 overflow-y-auto p-8 space-y-6 custom-scrollbar">
            {TEMPLATE_LIBRARY.map((item, idx) => (
              <div
                key={idx}
                className="group border border-slate-100 dark:border-white/5 rounded-[2rem] p-6 hover:border-indigo-600 dark:hover:border-indigo-500 hover:shadow-2xl hover:shadow-indigo-500/10 transition-all cursor-pointer bg-white dark:bg-zinc-900/40 relative overflow-hidden"
                onClick={() => loadLibraryTemplate(item)}
              >
                <div className="flex justify-between items-center mb-4">
                  <span className={`text-[9px] font-black px-3 py-1 rounded-full uppercase tracking-widest ${item.category === 'MARKETING' ? 'bg-indigo-100 text-indigo-700' : item.category === 'UTILITY' ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'}`}>
                    {item.category}
                  </span>
                  <div className="w-8 h-8 rounded-full bg-slate-50 dark:bg-white/10 flex items-center justify-center text-slate-300 group-hover:text-indigo-600 group-hover:bg-indigo-50 transition-all"><ChevronRight size={18} /></div>
                </div>
                <h3 className="font-black text-slate-900 dark:text-white text-base leading-tight group-hover:text-indigo-600 transition-colors uppercase tracking-tight">{item.title}</h3>
                <p className="text-xs text-slate-500 mt-2 font-medium leading-relaxed">{item.description}</p>
                <div className="mt-5 bg-slate-50 dark:bg-black/20 p-4 rounded-2xl text-[10px] font-mono text-slate-400 line-clamp-3 leading-relaxed border border-transparent group-hover:border-indigo-500/10 italic">
                  "{item.body}"
                </div>
              </div>
            ))}
          </div>
          <div className="p-8 bg-slate-50 dark:bg-zinc-950 border-t border-slate-100 dark:border-white/5">
            <div className="p-4 rounded-2xl bg-indigo-600/5 border border-indigo-600/10">
              <p className="text-[10px] text-indigo-600 dark:text-indigo-400 font-bold italic text-center leading-relaxed">Selecting a preset will instantly populate the builder with optimized Meta-compliant settings.</p>
            </div>
          </div>
        </div>
      </div>

      {/* Configuration Modal */}
      {isConfigModalOpen && configTemplate && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm shadow-2xl">
          <div className="bg-white dark:bg-slate-900 w-full max-w-lg rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden shadow-2xl">
            <div className="p-6 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center">
              <div>
                <h3 className="font-bold text-slate-900 dark:text-white">Configure Locals Settings</h3>
                <p className="text-[10px] uppercase font-bold tracking-widest text-slate-500 mt-1">{configTemplate.name.replace(/_/g, ' ')}</p>
              </div>
              <button onClick={() => setIsConfigModalOpen(false)} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
            </div>

            <div className="p-6 space-y-6 max-h-[60vh] overflow-y-auto">
              {/* Variable Config */}
              {configTemplateVariables.length > 0 && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-rose-500"></div>
                    <h3 className="text-xs font-bold text-slate-900 dark:text-slate-300 uppercase tracking-widest">Variable Default Rules</h3>
                  </div>
                  {configTemplateVariables.map((v: string) => (
                    <div key={v} className="flex gap-3 items-center">
                      <span className="text-[10px] font-bold text-slate-500 w-12 text-center bg-slate-100 dark:bg-slate-800 p-2 rounded-lg">{"{{"}{v}{"}}"}</span>
                      <select
                        value={variableMappings[v]?.startsWith('contact.') ? variableMappings[v] : (variableMappings[v] ? 'manual' : '')}
                        onChange={(e) => {
                          const val = e.target.value;
                          setVariableMappings(prev => ({ ...prev, [v]: val === 'manual' ? '' : val }));
                        }}
                        className="p-2 bg-slate-50 dark:bg-slate-800 rounded-lg text-xs font-bold outline-none flex-1"
                      >
                        <option value="">Select source...</option>
                        {contactFields.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
                      </select>
                      {(!variableMappings[v]?.startsWith('contact.') || variableMappings[v] === 'manual') && (
                        <input
                          value={variableMappings[v]?.startsWith('contact.') ? '' : variableMappings[v]}
                          onChange={(e) => setVariableMappings(prev => ({ ...prev, [v]: e.target.value }))}
                          placeholder="Static value"
                          className="p-2 bg-slate-50 dark:bg-slate-800 rounded-lg text-xs outline-none flex-1"
                        />
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Media Config */}
              {configTemplate.components.some((c: any) => c.type === 'HEADER' && ['IMAGE', 'VIDEO', 'DOCUMENT'].includes(c.format)) && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-indigo-500"></div>
                    <h3 className="text-xs font-bold text-slate-900 dark:text-slate-300 uppercase tracking-widest">Media Default Rule</h3>
                  </div>
                  <div className="text-xs text-slate-500 bg-slate-50 dark:bg-slate-800 p-3 rounded-lg flex items-center justify-between">
                    <span>Current Media ID:</span>
                    <span className="font-mono text-indigo-600 dark:text-indigo-400 font-bold">{mediaId || 'None'}</span>
                  </div>
                  <input type="file" onChange={async (e) => {
                    if (e.target.files?.[0]) {
                      const res = await whatsappApi.uploadCampaignMedia(e.target.files[0]);
                      setMediaId(res.id);
                    }
                  }} className="text-xs w-full file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-indigo-50 file:text-indigo-700 font-sans" />
                </div>
              )}

              {configTemplateVariables.length === 0 && !configTemplate.components.some((c: any) => c.type === 'HEADER' && ['IMAGE', 'VIDEO', 'DOCUMENT'].includes(c.format)) && (
                <p className="text-center text-xs text-slate-400 py-8 italic border border-dashed rounded-lg">No configurable items found.</p>
              )}
            </div>

            <div className="p-6 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900 flex justify-end">
              <button onClick={async () => {
                await whatsappApi.configureTemplate(configTemplate.id, {
                  variable_mappings: variableMappings,
                  media_id: mediaId
                });
                setIsConfigModalOpen(false);
                fetchTemplates();
              }} className="px-6 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-lg text-sm shadow-md transition-all active:scale-95">Save Configuration</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Templates;
