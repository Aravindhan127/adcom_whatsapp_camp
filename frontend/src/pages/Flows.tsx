import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Workflow,
  Plus,
  Search,
  Edit2,
  Trash2,
  CheckCircle,
  XCircle,
  AlertCircle,
  Info,
  ChevronRight,
  Loader2,
  Tag,
  MessageSquare,
  FileText,
  HelpCircle,
  X,
  Settings,
  ToggleLeft,
  ToggleRight,
  Sparkles,
  RefreshCw,
  Layers,
  MousePointerClick,
  ArrowRight,
  Check,
  Copy,
  BookOpen
} from 'lucide-react';
import { whatsappApi, InteractiveFlow, Template } from '../services/whatsappApi';
import PageHeader from '../components/PageHeader';
import { useToast } from '../components/Toast';
import { CustomSelect } from '../components/CustomSelect';

const Flows: React.FC = () => {
  const { toast } = useToast();
  const navigate = useNavigate();
  
  // State
  const [flows, setFlows] = useState<InteractiveFlow[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [editingFlow, setEditingFlow] = useState<InteractiveFlow | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  // Interactive Template Wizard State
  const [showWizard, setShowWizard] = useState(false);
  const [wizardStep, setWizardStep] = useState(1);
  const [wizardTemplateName, setWizardTemplateName] = useState('');
  const [wizardBody, setWizardBody] = useState('');
  const [wizardButtons, setWizardButtons] = useState([
    { label: 'Product A', buttonId: 'click_product_a', flowResponse: '', flowType: 'text' as 'text' | 'template' },
    { label: 'Product B', buttonId: 'click_product_b', flowResponse: '', flowType: 'text' as 'text' | 'template' },
  ]);
  const [wizardCreating, setWizardCreating] = useState(false);

  // Form State
  const [flowName, setFlowName] = useState('');
  const [triggerKeyword, setTriggerKeyword] = useState('');
  const [responseType, setResponseType] = useState<'text' | 'template'>('text');
  const [responseText, setResponseText] = useState('');
  const [selectedTemplateName, setSelectedTemplateName] = useState('');
  const [isActive, setIsActive] = useState(true);
  
  // Template Dynamic Variables form state
  const [bodyParams, setBodyParams] = useState<string[]>([]);
  const [headerType, setHeaderType] = useState(''); // 'IMAGE', 'VIDEO', 'DOCUMENT', 'TEXT', 'NONE'
  const [headerUrl, setHeaderUrl] = useState('');
  
  // Fetch initial data
  const fetchData = async () => {
    setLoading(true);
    try {
      const [flowsRes, templatesRes] = await Promise.all([
        whatsappApi.getFlows(),
        whatsappApi.getTemplates({ limit: 100 })
      ]);
      setFlows(flowsRes.items || []);
      setTemplates(templatesRes.items || []);
    } catch (error: any) {
      toast({ title: error.response?.data?.detail || 'Failed to fetch interactive flows.', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Filtered flows
  const filteredFlows = useMemo(() => {
    if (!searchQuery) return flows;
    const query = searchQuery.toLowerCase();
    return flows.filter(
      flow =>
        flow.name.toLowerCase().includes(query) ||
        flow.trigger_keyword.toLowerCase().includes(query) ||
        (flow.response_template || '').toLowerCase().includes(query)
    );
  }, [flows, searchQuery]);

  // Find currently selected template
  const selectedTemplate = useMemo(() => {
    if (!selectedTemplateName) return null;
    return templates.find(t => t.name === selectedTemplateName) || null;
  }, [selectedTemplateName, templates]);

  // Analyze template components to render dynamic fields
  useEffect(() => {
    if (responseType === 'template' && selectedTemplate) {
      // 1. Analyze Header Component
      const headerComp = selectedTemplate.components.find(
        (c: any) => c.type.toUpperCase() === 'HEADER'
      );
      if (headerComp) {
        setHeaderType(headerComp.format || 'TEXT');
      } else {
        setHeaderType('NONE');
      }

      // 2. Analyze Body Component & count placeholders
      const bodyComp = selectedTemplate.components.find(
        (c: any) => c.type.toUpperCase() === 'BODY'
      );
      if (bodyComp) {
        const text = bodyComp.text || '';
        const matches = text.match(/\{\{(\d+)\}\}/g);
        const count = matches ? matches.length : 0;
        
        // Initialize body parameters with empty strings or edit defaults
        if (editingFlow && editingFlow.response_template === selectedTemplateName && editingFlow.variable_values?.body) {
          const loadedParams = [...editingFlow.variable_values.body];
          while (loadedParams.length < count) loadedParams.push('');
          setBodyParams(loadedParams.slice(0, count));
        } else {
          setBodyParams(Array(count).fill(''));
        }
      } else {
        setBodyParams([]);
      }

      // 3. Load existing header handle/url if editing
      if (editingFlow && editingFlow.response_template === selectedTemplateName && editingFlow.variable_values?.header) {
        setHeaderUrl(editingFlow.variable_values.header.url || editingFlow.variable_values.header.id || '');
      } else {
        setHeaderUrl('');
      }
    } else {
      setHeaderType('NONE');
      setBodyParams([]);
      setHeaderUrl('');
    }
  }, [responseType, selectedTemplateName, selectedTemplate, editingFlow]);

  // Open Create Modal
  const handleOpenCreate = () => {
    setEditingFlow(null);
    setFlowName('');
    setTriggerKeyword('');
    setResponseType('text');
    setResponseText('');
    setSelectedTemplateName('');
    setIsActive(true);
    setBodyParams([]);
    setHeaderUrl('');
    setShowModal(true);
  };

  // Open Edit Modal
  const handleOpenEdit = (flow: InteractiveFlow) => {
    setEditingFlow(flow);
    setFlowName(flow.name);
    setTriggerKeyword(flow.trigger_keyword);
    setResponseType(flow.response_type);
    setResponseText(flow.response_text || '');
    setSelectedTemplateName(flow.response_template || '');
    setIsActive(flow.is_active);
    
    // Body and Header params are loaded in the useEffect above when selectedTemplateName changes
    setShowModal(true);
  };

  // Delete Flow
  const handleDelete = async (id: string) => {
    try {
      await whatsappApi.deleteFlow(id);
      toast({ title: 'Interactive flow deleted successfully.', type: 'success' });
      setFlows(prev => prev.filter(f => f.id !== id));
      setDeleteConfirmId(null);
    } catch (error: any) {
      toast({ title: error.response?.data?.detail || 'Failed to delete flow.', type: 'error' });
    }
  };

  // Toggle Flow Active state
  const handleToggleActive = async (flow: InteractiveFlow) => {
    const originalState = flow.is_active;
    // Optimistic UI Update
    setFlows(prev =>
      prev.map(f => (f.id === flow.id ? { ...f, is_active: !originalState } : f))
    );
    
    try {
      await whatsappApi.updateFlow(flow.id, { is_active: !originalState });
      toast({ title: `Flow "${flow.name}" ${!originalState ? 'activated' : 'deactivated'}.`, type: 'success' });
    } catch (error: any) {
      // Revert if error
      setFlows(prev =>
        prev.map(f => (f.id === flow.id ? { ...f, is_active: originalState } : f))
      );
      toast({ title: error.response?.data?.detail || 'Failed to update flow status.', type: 'error' });
    }
  };

  // Submit Form
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!flowName.trim()) {
      toast({ title: 'Flow name is required.', type: 'warning' });
      return;
    }
    if (!triggerKeyword.trim()) {
      toast({ title: 'Trigger keyword is required.', type: 'warning' });
      return;
    }
    if (responseType === 'text' && !responseText.trim()) {
      toast({ title: 'Response text is required for Text response.', type: 'warning' });
      return;
    }
    if (responseType === 'template' && !selectedTemplateName) {
      toast({ title: 'Please select a WhatsApp Template.', type: 'warning' });
      return;
    }

    setSubmitLoading(true);

    // Build payload
    const variableValues: any = {};
    if (responseType === 'template') {
      if (bodyParams.length > 0) {
        variableValues.body = bodyParams;
      }
      if (headerType && headerType !== 'NONE' && headerUrl) {
        variableValues.header = {
          type: headerType,
          url: headerUrl
        };
      }
    }

    const payload: Partial<InteractiveFlow> = {
      name: flowName.trim(),
      trigger_keyword: triggerKeyword.trim(),
      response_type: responseType,
      response_text: responseType === 'text' ? responseText.trim() : null,
      response_template: responseType === 'template' ? selectedTemplateName : null,
      variable_values: responseType === 'template' ? variableValues : null,
      is_active: isActive
    };

    try {
      if (editingFlow) {
        const updated = await whatsappApi.updateFlow(editingFlow.id, payload);
        toast({ title: 'Interactive flow updated successfully.', type: 'success' });
        setFlows(prev => prev.map(f => (f.id === editingFlow.id ? updated : f)));
      } else {
        const created = await whatsappApi.createFlow(payload);
        toast({ title: 'Interactive flow created successfully.', type: 'success' });
        setFlows(prev => [created, ...prev]);
      }
      setShowModal(false);
    } catch (error: any) {
      toast({ title: error.response?.data?.detail || 'Failed to save flow. Check if trigger keyword is unique.', type: 'error' });
    } finally {
      setSubmitLoading(false);
    }
  };

  // Format templates to options list for dropdown
  const templateOptions = useMemo(() => {
    return templates.map(t => ({
      value: t.name,
      label: `${t.name} (${t.category} - ${t.status})`
    }));
  }, [templates]);

  // Wizard: open with defaults reset
  const handleOpenWizard = () => {
    setWizardStep(1);
    setWizardTemplateName('');
    setWizardBody('');
    setWizardButtons([
      { label: 'Product A', buttonId: 'click_product_a', flowResponse: '', flowType: 'text' },
      { label: 'Product B', buttonId: 'click_product_b', flowResponse: '', flowType: 'text' },
    ]);
    setShowWizard(true);
  };

  // Wizard: Create all flow rules then navigate to Templates
  const handleWizardCreateFlows = async () => {
    if (wizardButtons.some(b => !b.buttonId.trim() || !b.label.trim())) {
      toast({ title: 'All buttons must have a label and a Button ID.', type: 'warning' });
      return;
    }
    setWizardCreating(true);
    try {
      const created: InteractiveFlow[] = [];
      for (const btn of wizardButtons) {
        if (!btn.flowResponse.trim()) continue; // Skip empty flows silently
        const payload: Partial<InteractiveFlow> = {
          name: `Auto: ${btn.label} Reply`,
          trigger_keyword: btn.buttonId.trim().toLowerCase().replace(/\s+/g, '_'),
          response_type: btn.flowType,
          response_text: btn.flowType === 'text' ? btn.flowResponse.trim() : null,
          response_template: btn.flowType === 'template' ? btn.flowResponse.trim() : null,
          is_active: true,
        };
        try {
          const newFlow = await whatsappApi.createFlow(payload);
          created.push(newFlow);
        } catch (_) {
          // Skip duplicate triggers gracefully
        }
      }
      setFlows(prev => [...created, ...prev]);
      toast({ title: `✅ ${created.length} flow rule(s) created! Now create the template in Templates.`, type: 'success' });
      setShowWizard(false);
      // Navigate to templates page so user can create the actual template
      navigate('/templates');
    } catch (err: any) {
      toast({ title: err?.message || 'Failed to create flows.', type: 'error' });
    } finally {
      setWizardCreating(false);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto px-4 sm:px-6">
      <PageHeader
        title="Interactive Flows"
        description="Configure automated text or template replies triggered when a user clicks a button reply ID/payload or matches specific keywords."
        actions={
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={handleOpenWizard}
              className="flex items-center gap-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-semibold py-2.5 px-4 rounded-xl shadow-lg shadow-purple-500/20 border border-purple-500/20 transition-all hover:scale-[1.02] active:scale-[0.98]"
            >
              <Layers size={16} className="stroke-[2.5px]" />
              <span>Create Interactive Template</span>
            </button>
            <button
              onClick={handleOpenCreate}
              className="flex items-center gap-2 bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-white font-semibold py-2.5 px-4 rounded-xl shadow-lg shadow-indigo-500/20 dark:shadow-indigo-900/30 border border-indigo-500/20 transition-all hover:scale-[1.02] active:scale-[0.98]"
            >
              <Plus size={18} className="stroke-[3px]" />
              <span>Add Flow Rule</span>
            </button>
          </div>
        }
      />

      {/* How It Works Info Card */}
      <div className="bg-gradient-to-r from-indigo-50/80 to-purple-50/80 dark:from-indigo-500/5 dark:to-purple-500/5 border border-indigo-200/40 dark:border-indigo-500/20 rounded-2xl p-5 flex items-start gap-4">
        <div className="p-2.5 bg-indigo-100 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 rounded-xl shrink-0">
          <BookOpen size={20} />
        </div>
        <div className="flex-1">
          <h4 className="text-sm font-bold text-slate-800 dark:text-white">How Interactive Flows Work</h4>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 leading-relaxed">
            <strong>Step 1:</strong> In <span className="font-mono text-indigo-600 dark:text-indigo-400">Templates</span>, create a template with <strong>Quick Reply</strong> buttons. Set a unique <strong>Button ID</strong> for each button (e.g. <code className="bg-slate-100 dark:bg-slate-800 px-1 rounded">click_product_a</code>).
            <span className="mx-1.5 text-slate-300">→</span>
            <strong>Step 2:</strong> Here in Flows, create a rule with the same <strong>Trigger Keyword</strong> as that Button ID.
            <span className="mx-1.5 text-slate-300">→</span>
            <strong>Step 3:</strong> When a user clicks the button on WhatsApp, they automatically receive your configured reply.
          </p>
        </div>
        <button
          onClick={handleOpenWizard}
          className="shrink-0 flex items-center gap-1.5 px-3 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl transition-all shadow-sm"
        >
          <Sparkles size={14} />
          Quick Setup
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <div className="bg-white/40 dark:bg-slate-900/40 backdrop-blur-md border border-slate-200/50 dark:border-slate-800/50 p-6 rounded-2xl flex items-center justify-between shadow-sm">
          <div>
            <span className="text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">Total Flows</span>
            <h3 className="text-3xl font-black text-slate-800 dark:text-white mt-1">{flows.length}</h3>
          </div>
          <div className="p-3 bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 rounded-xl">
            <Workflow size={24} />
          </div>
        </div>
        <div className="bg-white/40 dark:bg-slate-900/40 backdrop-blur-md border border-slate-200/50 dark:border-slate-800/50 p-6 rounded-2xl flex items-center justify-between shadow-sm">
          <div>
            <span className="text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">Active Rules</span>
            <h3 className="text-3xl font-black text-emerald-600 dark:text-emerald-400 mt-1">
              {flows.filter(f => f.is_active).length}
            </h3>
          </div>
          <div className="p-3 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 rounded-xl">
            <CheckCircle size={24} />
          </div>
        </div>
        <div className="bg-white/40 dark:bg-slate-900/40 backdrop-blur-md border border-slate-200/50 dark:border-slate-800/50 p-6 rounded-2xl flex items-center justify-between shadow-sm">
          <div>
            <span className="text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">Inactive Rules</span>
            <h3 className="text-3xl font-black text-slate-400 dark:text-slate-500 mt-1">
              {flows.filter(f => !f.is_active).length}
            </h3>
          </div>
          <div className="p-3 bg-slate-100 dark:bg-slate-800 text-slate-400 dark:text-slate-500 rounded-xl">
            <XCircle size={24} />
          </div>
        </div>
      </div>

      {/* Control Panel */}
      <div className="flex flex-col sm:flex-row gap-4 items-center justify-between bg-white/40 dark:bg-slate-900/40 backdrop-blur-md border border-slate-200/50 dark:border-slate-800/50 p-4 rounded-2xl">
        <div className="relative w-full sm:max-w-md">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500" size={18} />
          <input
            type="text"
            placeholder="Search by flow name, trigger key, or template..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-slate-50/50 dark:bg-slate-950/50 border border-slate-200/60 dark:border-slate-800/60 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
          />
        </div>
        <button
          onClick={fetchData}
          className="flex items-center gap-1.5 text-xs text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 font-bold px-3 py-2 bg-indigo-50 dark:bg-indigo-500/10 rounded-xl transition-all self-end sm:self-auto"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Flow rules table/list */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <Loader2 className="animate-spin text-indigo-600" size={32} />
          <span className="text-sm font-semibold text-slate-400">Loading flow configuration...</span>
        </div>
      ) : filteredFlows.length === 0 ? (
        <div className="bg-white/40 dark:bg-slate-900/40 backdrop-blur-md border border-slate-200/50 dark:border-slate-800/50 p-16 rounded-3xl flex flex-col items-center justify-center text-center shadow-sm">
          <div className="p-4 bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 rounded-2xl mb-4">
            <Workflow size={40} />
          </div>
          <h3 className="text-xl font-bold text-slate-800 dark:text-white">No Interactive Flows Found</h3>
          <p className="text-sm text-slate-400 max-w-sm mt-2">
            {searchQuery ? 'Try adjusting your search criteria.' : 'Create rules to map incoming WhatsApp button clicks or keywords to automated responses.'}
          </p>
          {!searchQuery && (
            <button
              onClick={handleOpenCreate}
              className="mt-6 flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2 px-4 rounded-xl transition-all"
            >
              <Plus size={16} />
              <span>Create First Flow</span>
            </button>
          )}
        </div>
      ) : (
        <div className="bg-white/40 dark:bg-slate-900/40 backdrop-blur-md border border-slate-200/50 dark:border-slate-800/50 rounded-2xl overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-100 dark:border-slate-800/50 text-[10px] uppercase font-black tracking-wider text-slate-400 dark:text-slate-500">
                  <th className="px-6 py-4">Flow Name</th>
                  <th className="px-6 py-4">Trigger Keyword (Button ID)</th>
                  <th className="px-6 py-4">Response Type</th>
                  <th className="px-6 py-4">Response Details</th>
                  <th className="px-6 py-4 text-center">Status</th>
                  <th className="px-6 py-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100/50 dark:divide-slate-800/30">
                {filteredFlows.map(flow => (
                  <tr key={flow.id} className="hover:bg-slate-50/30 dark:hover:bg-slate-900/20 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 rounded-lg">
                          <Workflow size={16} />
                        </div>
                        <div>
                          <div className="font-bold text-slate-800 dark:text-slate-100">{flow.name}</div>
                          <div className="text-[10px] text-slate-400 dark:text-slate-500">Created: {new Date(flow.created_at || '').toLocaleDateString()}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-mono text-xs font-bold rounded-lg border border-slate-200/50 dark:border-slate-700/50">
                        <Tag size={12} className="text-slate-400" />
                        {flow.trigger_keyword}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold ${
                        flow.response_type === 'template'
                          ? 'bg-purple-50 dark:bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-200/20'
                          : 'bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-200/20'
                      }`}>
                        {flow.response_type === 'template' ? <FileText size={12} /> : <MessageSquare size={12} />}
                        {flow.response_type === 'template' ? 'WhatsApp Template' : 'Plain Text'}
                      </span>
                    </td>
                    <td className="px-6 py-4 max-w-xs sm:max-w-sm truncate">
                      {flow.response_type === 'template' ? (
                        <div className="space-y-1">
                          <div className="font-semibold text-slate-700 dark:text-slate-300 text-xs">
                            Template: <span className="font-mono text-indigo-600 dark:text-indigo-400">{flow.response_template}</span>
                          </div>
                          {flow.variable_values?.body && (
                            <div className="text-[10px] text-slate-400 dark:text-slate-500 truncate">
                              Body variables: {flow.variable_values.body.join(', ')}
                            </div>
                          )}
                        </div>
                      ) : (
                        <span className="text-xs text-slate-600 dark:text-slate-400 font-medium">
                          {flow.response_text}
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-center">
                      <button
                        onClick={() => handleToggleActive(flow)}
                        title={flow.is_active ? 'Click to deactivate' : 'Click to activate'}
                        className="focus:outline-none inline-block align-middle transition-transform active:scale-95"
                      >
                        {flow.is_active ? (
                          <ToggleRight className="text-emerald-500 dark:text-emerald-400 h-8 w-8 stroke-[1.5]" />
                        ) : (
                          <ToggleLeft className="text-slate-300 dark:text-slate-600 h-8 w-8 stroke-[1.5]" />
                        )}
                      </button>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => handleOpenEdit(flow)}
                          className="p-2 text-slate-400 dark:text-slate-500 hover:text-indigo-600 dark:hover:text-indigo-400 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                        >
                          <Edit2 size={16} />
                        </button>
                        <button
                          onClick={() => setDeleteConfirmId(flow.id)}
                          className="p-2 text-slate-400 dark:text-slate-500 hover:text-rose-600 dark:hover:text-rose-400 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Interactive Template Wizard Modal */}
      {showWizard && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-sm">
          <div className="w-full max-w-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl shadow-2xl flex flex-col animate-in fade-in zoom-in-95 duration-200 max-h-[90vh] overflow-hidden">
            {/* Wizard Header */}
            <div className="p-6 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-purple-50 dark:bg-purple-500/10 text-purple-600 dark:text-purple-400 rounded-xl">
                  <Layers size={20} />
                </div>
                <div>
                  <h3 className="text-lg font-black text-slate-800 dark:text-white">Interactive Template Wizard</h3>
                  <p className="text-xs text-slate-400">Set up buttons + flow rules in one guided flow</p>
                </div>
              </div>
              <button onClick={() => setShowWizard(false)} className="p-1.5 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg">
                <X size={20} />
              </button>
            </div>

            {/* Step Indicator */}
            <div className="px-6 pt-5 flex items-center gap-3">
              {[1, 2, 3].map(step => (
                <div key={step} className="flex items-center gap-2">
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-black transition-all ${
                    wizardStep > step
                      ? 'bg-emerald-500 text-white'
                      : wizardStep === step
                      ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-400'
                  }`}>
                    {wizardStep > step ? <Check size={14} strokeWidth={3} /> : step}
                  </div>
                  <span className={`text-xs font-bold ${
                    wizardStep === step ? 'text-slate-800 dark:text-white' : 'text-slate-400'
                  }`}>
                    {step === 1 ? 'Configure Buttons' : step === 2 ? 'Set Flow Responses' : 'Review & Create'}
                  </span>
                  {step < 3 && <ArrowRight size={14} className="text-slate-300 dark:text-slate-600" />}
                </div>
              ))}
            </div>

            {/* Step Content */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {wizardStep === 1 && (
                <div className="space-y-6">
                  <div className="p-4 bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200/30 dark:border-indigo-500/20 rounded-2xl text-xs text-indigo-700 dark:text-indigo-300 space-y-1.5">
                    <p className="font-bold">📋 What to do here:</p>
                    <p>Define each button that will appear in your WhatsApp template. The <strong>Button ID</strong> is a unique code that identifies which button was clicked — it must later match a <em>Flow Trigger Keyword</em>.</p>
                  </div>

                  {wizardButtons.map((btn, idx) => (
                    <div key={idx} className="p-5 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-2xl space-y-4">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-black uppercase tracking-wider text-slate-500 dark:text-slate-400">Button {idx + 1}</span>
                        {wizardButtons.length > 1 && (
                          <button
                            onClick={() => setWizardButtons(prev => prev.filter((_, i) => i !== idx))}
                            className="text-xs text-rose-500 hover:text-rose-600 font-bold"
                          >Remove</button>
                        )}
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-[10px] font-black uppercase tracking-wider text-slate-400 mb-1">Button Label (shown on WhatsApp)</label>
                          <input
                            value={btn.label}
                            onChange={e => {
                              const upd = [...wizardButtons];
                              upd[idx].label = e.target.value;
                              // Auto-generate button ID from label
                              upd[idx].buttonId = 'click_' + e.target.value.toLowerCase().trim().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
                              setWizardButtons(upd);
                            }}
                            placeholder="e.g. Product A"
                            className="w-full px-3 py-2.5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl text-sm font-bold focus:outline-none focus:ring-2 focus:ring-indigo-500"
                          />
                        </div>
                        <div>
                          <label className="block text-[10px] font-black uppercase tracking-wider text-indigo-500 mb-1">Button ID (auto-generated, editable)</label>
                          <input
                            value={btn.buttonId}
                            onChange={e => {
                              const upd = [...wizardButtons];
                              upd[idx].buttonId = e.target.value.toLowerCase().replace(/\s+/g, '_');
                              setWizardButtons(upd);
                            }}
                            placeholder="e.g. click_product_a"
                            className="w-full px-3 py-2.5 bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-300/40 dark:border-indigo-500/30 rounded-xl text-sm font-mono text-indigo-700 dark:text-indigo-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                          />
                        </div>
                      </div>
                    </div>
                  ))}

                  {wizardButtons.length < 3 && (
                    <button
                      onClick={() => setWizardButtons(prev => [...prev, { label: `Option ${prev.length + 1}`, buttonId: `click_option_${prev.length + 1}`, flowResponse: '', flowType: 'text' }])}
                      className="w-full py-3 border-2 border-dashed border-slate-200 dark:border-slate-700 rounded-2xl text-xs font-bold text-slate-400 hover:border-indigo-400 hover:text-indigo-500 transition-all flex items-center justify-center gap-2"
                    >
                      <Plus size={14} /> Add Another Button
                    </button>
                  )}
                </div>
              )}

              {wizardStep === 2 && (
                <div className="space-y-6">
                  <div className="p-4 bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200/30 dark:border-emerald-500/20 rounded-2xl text-xs text-emerald-700 dark:text-emerald-300 space-y-1.5">
                    <p className="font-bold">💬 What to do here:</p>
                    <p>For each button, enter the <strong>automated reply</strong> that will be sent when a customer clicks it. You can also leave it blank to skip creating a flow for that button.</p>
                  </div>
                  {wizardButtons.map((btn, idx) => (
                    <div key={idx} className="p-5 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-2xl space-y-3">
                      <div className="flex items-center gap-3">
                        <span className="px-2.5 py-1 bg-indigo-100 dark:bg-indigo-500/20 text-indigo-700 dark:text-indigo-300 font-mono text-xs font-bold rounded-lg">{btn.buttonId}</span>
                        <span className="font-bold text-slate-700 dark:text-slate-200 text-sm">{btn.label}</span>
                        <ArrowRight size={14} className="text-slate-300" />
                        <span className="text-xs text-slate-400">auto-reply with:</span>
                      </div>
                      <div className="flex gap-3">
                        <button
                          type="button"
                          onClick={() => { const u = [...wizardButtons]; u[idx].flowType = 'text'; setWizardButtons(u); }}
                          className={`px-3 py-1.5 rounded-xl text-xs font-bold border transition-all ${
                            btn.flowType === 'text'
                              ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600'
                              : 'border-slate-200 dark:border-slate-700 text-slate-400'
                          }`}
                        >
                          <MessageSquare size={12} className="inline mr-1" />Plain Text
                        </button>
                        <button
                          type="button"
                          onClick={() => { const u = [...wizardButtons]; u[idx].flowType = 'template'; setWizardButtons(u); }}
                          className={`px-3 py-1.5 rounded-xl text-xs font-bold border transition-all ${
                            btn.flowType === 'template'
                              ? 'border-purple-500 bg-purple-50 dark:bg-purple-500/10 text-purple-600'
                              : 'border-slate-200 dark:border-slate-700 text-slate-400'
                          }`}
                        >
                          <FileText size={12} className="inline mr-1" />Template Name
                        </button>
                      </div>
                      <textarea
                        rows={3}
                        value={btn.flowResponse}
                        onChange={e => { const u = [...wizardButtons]; u[idx].flowResponse = e.target.value; setWizardButtons(u); }}
                        placeholder={btn.flowType === 'text'
                          ? `Type the auto-reply message for "${btn.label}" button clicks...`
                          : `Enter the template name to send (e.g. product_a_details)`
                        }
                        className="w-full px-4 py-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                    </div>
                  ))}
                </div>
              )}

              {wizardStep === 3 && (
                <div className="space-y-5">
                  <div className="p-4 bg-amber-50 dark:bg-amber-500/10 border border-amber-200/30 dark:border-amber-500/20 rounded-2xl text-xs text-amber-700 dark:text-amber-300 space-y-1.5">
                    <p className="font-bold">🚀 Almost done!</p>
                    <p>Clicking <strong>"Create Flow Rules"</strong> will save all the automated response rules. You'll then be taken to <strong>Templates</strong> where you create the WhatsApp template with Quick Reply buttons — using the Button IDs shown below.</p>
                  </div>

                  <div className="space-y-3">
                    <h4 className="text-xs font-black uppercase tracking-wider text-slate-500 dark:text-slate-400">Flow Rules to Create</h4>
                    {wizardButtons.map((btn, idx) => (
                      <div key={idx} className="p-4 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-2xl flex items-start justify-between gap-4">
                        <div className="space-y-1.5">
                          <div className="flex items-center gap-2">
                            <span className="px-2 py-0.5 bg-indigo-100 dark:bg-indigo-500/20 text-indigo-700 dark:text-indigo-300 font-mono text-[10px] font-bold rounded">{btn.buttonId}</span>
                            <ArrowRight size={12} className="text-slate-300" />
                            <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                              btn.flowType === 'template'
                                ? 'bg-purple-100 dark:bg-purple-500/20 text-purple-600'
                                : 'bg-indigo-100 dark:bg-indigo-500/20 text-indigo-600'
                            }`}>{btn.flowType === 'template' ? 'Template' : 'Text'} Reply</span>
                          </div>
                          <p className="text-xs text-slate-600 dark:text-slate-400 font-medium">
                            {btn.flowResponse.trim() ? `"${btn.flowResponse.trim().slice(0, 60)}${btn.flowResponse.length > 60 ? '...' : ''}"` : <em className="text-slate-300">No flow will be created (empty)</em>}
                          </p>
                        </div>
                        {btn.flowResponse.trim() ? (
                          <CheckCircle size={16} className="text-emerald-500 shrink-0 mt-0.5" />
                        ) : (
                          <XCircle size={16} className="text-slate-300 shrink-0 mt-0.5" />
                        )}
                      </div>
                    ))}
                  </div>

                  <div className="p-4 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl space-y-2">
                    <h4 className="text-xs font-black uppercase tracking-wider text-slate-500">Next: Template Setup</h4>
                    <p className="text-xs text-slate-500 dark:text-slate-400">After creating flows, go to <strong>Templates → Create Template</strong> and add <strong>Quick Reply</strong> buttons with these exact Button IDs:</p>
                    <div className="flex flex-wrap gap-2 mt-2">
                      {wizardButtons.map((btn, idx) => (
                        <span key={idx} className="flex items-center gap-1 px-2.5 py-1 bg-indigo-100 dark:bg-indigo-500/20 text-indigo-700 dark:text-indigo-300 font-mono text-xs font-bold rounded-lg">
                          {btn.buttonId}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Wizard Footer */}
            <div className="p-6 border-t border-slate-100 dark:border-slate-800 flex justify-between gap-3">
              <button
                onClick={() => wizardStep > 1 ? setWizardStep(s => s - 1) : setShowWizard(false)}
                className="px-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-xs font-bold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 transition-all"
              >
                {wizardStep === 1 ? 'Cancel' : '← Back'}
              </button>
              <div className="flex gap-3">
                {wizardStep < 3 ? (
                  <button
                    onClick={() => setWizardStep(s => s + 1)}
                    className="flex items-center gap-2 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-bold py-2 px-6 rounded-xl shadow-lg transition-all"
                  >
                    <span>Next</span>
                    <ArrowRight size={15} />
                  </button>
                ) : (
                  <button
                    onClick={handleWizardCreateFlows}
                    disabled={wizardCreating}
                    className="flex items-center gap-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold py-2 px-6 rounded-xl shadow-lg transition-all disabled:opacity-50"
                  >
                    {wizardCreating ? <Loader2 size={15} className="animate-spin" /> : <Check size={15} strokeWidth={3} />}
                    <span>Create Flow Rules & Go to Templates</span>
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirmId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-sm">
          <div className="w-full max-w-md bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl p-6 shadow-2xl relative animate-in fade-in zoom-in-95 duration-200">
            <h4 className="text-lg font-bold text-slate-800 dark:text-white flex items-center gap-2">
              <AlertCircle className="text-rose-500" />
              <span>Confirm Deletion</span>
            </h4>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">
              Are you sure you want to delete this interactive flow rule? Users clicking matching buttons will no longer receive automated replies from this rule.
            </p>
            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={() => setDeleteConfirmId(null)}
                className="px-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-700/80 rounded-xl text-xs font-bold text-slate-600 dark:text-slate-300"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDelete(deleteConfirmId)}
                className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-xl text-xs font-bold shadow-md shadow-rose-600/20"
              >
                Delete Rule
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create / Edit Side Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-end bg-slate-950/60 backdrop-blur-sm">
          <div className="w-full max-w-xl h-full bg-white dark:bg-slate-900 border-l border-slate-200 dark:border-slate-800 shadow-2xl flex flex-col relative animate-in slide-in-from-right duration-300">
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <div className="p-2 bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 rounded-xl">
                  <Workflow size={20} />
                </div>
                <h3 className="text-lg font-black text-slate-800 dark:text-white">
                  {editingFlow ? 'Edit Interactive Flow' : 'Create Interactive Flow'}
                </h3>
              </div>
              <button
                onClick={() => setShowModal(false)}
                className="p-1.5 text-slate-400 dark:text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg"
              >
                <X size={20} />
              </button>
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-6">
              {/* Basic Fields */}
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-black uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-1.5">
                    Flow Rule Name
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Product A Details Click"
                    value={flowName}
                    onChange={(e) => setFlowName(e.target.value)}
                    className="w-full px-4 py-2.5 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                  />
                  <p className="text-[10px] text-slate-400 mt-1">A simple title to identify this auto-reply rule.</p>
                </div>

                <div>
                  <label className="block text-xs font-black uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-1.5">
                    Trigger Keyword / Button ID
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. click_product_a"
                    value={triggerKeyword}
                    onChange={(e) => setTriggerKeyword(e.target.value)}
                    className="w-full px-4 py-2.5 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono text-sm"
                  />
                  <div className="text-[10px] text-slate-400 mt-1 space-y-1">
                    <p>Must match the <strong>Button ID (button_reply.id or payload)</strong> defined in your templates, OR an incoming text keyword.</p>
                    <p className="text-amber-500 dark:text-amber-400 font-medium">⚠️ Case-insensitive match. Trigger keywords must be unique per organization.</p>
                  </div>
                </div>

                {/* Response Type Select */}
                <div>
                  <label className="block text-xs font-black uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-1.5">
                    Response Type
                  </label>
                  <div className="grid grid-cols-2 gap-4">
                    <button
                      type="button"
                      onClick={() => setResponseType('text')}
                      className={`flex flex-col items-center justify-center p-4 border rounded-2xl gap-2 transition-all ${
                        responseType === 'text'
                          ? 'border-indigo-600 dark:border-indigo-500 bg-indigo-50/50 dark:bg-indigo-500/5 text-indigo-600 dark:text-indigo-400 font-bold'
                          : 'border-slate-200 dark:border-slate-800 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300'
                      }`}
                    >
                      <MessageSquare size={24} />
                      <span className="text-xs">Plain Text Reply</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setResponseType('template')}
                      className={`flex flex-col items-center justify-center p-4 border rounded-2xl gap-2 transition-all ${
                        responseType === 'template'
                          ? 'border-indigo-600 dark:border-indigo-500 bg-indigo-50/50 dark:bg-indigo-500/5 text-indigo-600 dark:text-indigo-400 font-bold'
                          : 'border-slate-200 dark:border-slate-800 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300'
                      }`}
                    >
                      <FileText size={24} />
                      <span className="text-xs">WhatsApp Template</span>
                    </button>
                  </div>
                </div>

                {/* Conditional Fields */}
                {responseType === 'text' ? (
                  <div>
                    <label className="block text-xs font-black uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-1.5">
                      Response Message Content
                    </label>
                    <textarea
                      required
                      rows={5}
                      placeholder="Type the message that will be sent to the customer..."
                      value={responseText}
                      onChange={(e) => setResponseText(e.target.value)}
                      className="w-full px-4 py-2.5 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                    />
                    <div className="text-[10px] text-slate-400 mt-1 flex flex-wrap gap-x-3">
                      <span>Supports formatting (e.g. *bold*, _italics_)</span>
                      <span>Variables: <code>{`{{contact.name}}`}</code>, <code>{`{{contact.phone}}`}</code></span>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4 border-t border-slate-100 dark:border-slate-800/50 pt-4">
                    <div>
                      <label className="block text-xs font-black uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-1.5">
                        Select Approved Template
                      </label>
                      {templateOptions.length === 0 ? (
                        <div className="p-3 bg-rose-50 dark:bg-rose-500/10 border border-rose-200/20 text-rose-600 dark:text-rose-400 text-xs font-bold rounded-xl flex items-center gap-2">
                          <AlertCircle size={16} />
                          <span>No templates found. Please create/sync templates first.</span>
                        </div>
                      ) : (
                        <CustomSelect
                          value={selectedTemplateName}
                          onChange={(val) => setSelectedTemplateName(val)}
                          options={templateOptions}
                          placeholder="Search and select a WhatsApp template..."
                        />
                      )}
                    </div>

                    {/* Template Variable Configuration */}
                    {selectedTemplateName && selectedTemplate && (
                      <div className="bg-slate-50/50 dark:bg-slate-950/50 border border-slate-200/50 dark:border-slate-800/50 p-4 rounded-2xl space-y-4">
                        <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400">
                          <Sparkles size={16} className="text-indigo-500" />
                          <span className="text-xs font-bold uppercase tracking-wider">Configure Parameters</span>
                        </div>

                        {/* Header Media Link */}
                        {headerType && ['IMAGE', 'VIDEO', 'DOCUMENT'].includes(headerType) && (
                          <div>
                            <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-300 mb-1">
                              Header Media Link (URL or handle ID)
                            </label>
                            <input
                              type="text"
                              required
                              placeholder={`https://example.com/media.${headerType === 'IMAGE' ? 'jpg' : headerType === 'VIDEO' ? 'mp4' : 'pdf'}`}
                              value={headerUrl}
                              onChange={(e) => setHeaderUrl(e.target.value)}
                              className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl focus:outline-none focus:ring-1 focus:ring-indigo-500 text-xs"
                            />
                            <p className="text-[9px] text-slate-400 mt-0.5">Media URL or a valid upload handle ID for the header.</p>
                          </div>
                        )}

                        {/* Body Parameters List */}
                        {bodyParams.length > 0 && (
                          <div className="space-y-3">
                            <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-300">
                              Body Placeholder Parameters
                            </label>
                            {bodyParams.map((param, index) => (
                              <div key={index} className="flex items-center gap-2">
                                <span className="text-xs font-mono font-bold text-indigo-600 dark:text-indigo-400 shrink-0 w-8">
                                  {"{{" + (index + 1) + "}}"}
                                </span>
                                <input
                                  type="text"
                                  required
                                  placeholder={`Value for variable ${index + 1} (e.g. {{contact.name}})`}
                                  value={param}
                                  onChange={(e) => {
                                    const updated = [...bodyParams];
                                    updated[index] = e.target.value;
                                    setBodyParams(updated);
                                  }}
                                  className="flex-1 px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl focus:outline-none focus:ring-1 focus:ring-indigo-500 text-xs"
                                />
                              </div>
                            ))}
                            <div className="text-[9px] text-slate-400 flex flex-wrap gap-x-2 font-medium">
                              <span>Support contact fields:</span>
                              <code>{`{{contact.name}}`}</code>, <code>{`{{contact.phone}}`}</code>
                            </div>
                          </div>
                        )}

                        {/* Template Body Text Preview */}
                        <div className="border-t border-slate-200/50 dark:border-slate-800/50 pt-3">
                          <label className="block text-[9px] font-black uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-1">
                            Template Message Preview (Body Text)
                          </label>
                          <div className="p-3 bg-white dark:bg-slate-900 rounded-xl text-xs border border-slate-100 dark:border-slate-800/80 font-mono text-slate-500 dark:text-slate-400 whitespace-pre-wrap leading-relaxed">
                            {selectedTemplate.components.find((c: any) => c.type.toUpperCase() === 'BODY')?.text || ''}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Active switch */}
                <div className="flex items-center justify-between p-4 bg-slate-50/50 dark:bg-slate-950/50 border border-slate-200/50 dark:border-slate-800/50 rounded-2xl">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300">
                      Rule Enabled State
                    </label>
                    <span className="text-[10px] text-slate-400">Deactivated rules will not match incoming messages.</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setIsActive(!isActive)}
                    className="focus:outline-none transition-transform active:scale-95"
                  >
                    {isActive ? (
                      <ToggleRight className="text-emerald-500 dark:text-emerald-400 h-9 w-9 stroke-[1.5]" />
                    ) : (
                      <ToggleLeft className="text-slate-300 dark:text-slate-600 h-9 w-9 stroke-[1.5]" />
                    )}
                  </button>
                </div>
              </div>
            </form>

            {/* Footer */}
            <div className="p-6 border-t border-slate-100 dark:border-slate-800 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="px-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-750 rounded-xl text-xs font-bold text-slate-600 dark:text-slate-300 transition-all"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={submitLoading}
                className="flex items-center gap-2 bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-white font-bold py-2 px-6 rounded-xl shadow-lg shadow-indigo-500/10 transition-all disabled:opacity-50 disabled:pointer-events-none"
              >
                {submitLoading && <Loader2 size={14} className="animate-spin" />}
                <span>{editingFlow ? 'Save Changes' : 'Create Flow Rule'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Flows;
