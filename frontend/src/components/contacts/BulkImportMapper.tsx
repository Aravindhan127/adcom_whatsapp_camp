import React, { useState } from 'react';
import { Upload, X, Check, ArrowRight, Table, AlertCircle, Loader2 } from 'lucide-react';
import { whatsappApi } from '../../services/whatsappApi';
import * as XLSX from 'xlsx';

interface Props {
  onClose: () => void;
  onSuccess: () => void;
}

const SYSTEM_FIELDS = [
  { key: 'phone_number', label: 'Phone Number', required: true },
  { key: 'name', label: 'Full Name', required: false },
  { key: 'city', label: 'City', required: false },
  { key: 'lead_source', label: 'Source', required: false },
  { key: 'customer_category', label: 'Category', required: false },
  { key: 'customer_stage', label: 'Stage', required: false },
  { key: 'company_name', label: 'Company', required: false },
  { key: 'product_service_interest', label: 'Interest', required: false },
];

const BulkImportMapper: React.FC<Props> = ({ onClose, onSuccess }) => {
  const [file, setFile] = useState<File | null>(null);
  const [headers, setHeaders] = useState<string[]>([]);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [step, setStep] = useState(1); // 1: Upload, 2: Map, 3: Import
  const [isImporting, setIsImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;

    setFile(selectedFile);
    setError(null);

    try {
      if (selectedFile.name.endsWith('.csv')) {
        const text = await selectedFile.text();
        const firstLine = text.split('\n')[0];
        const cols = firstLine.split(',').map(c => c.trim().replace(/^"|"$/g, ''));
        setHeaders(cols);
      } else {
        const data = await selectedFile.arrayBuffer();
        const workbook = XLSX.read(data);
        const worksheet = workbook.Sheets[workbook.SheetNames[0]];
        const range = XLSX.utils.decode_range(worksheet['!ref'] || 'A1');
        const cols: string[] = [];
        for (let C = range.s.c; C <= range.e.c; ++C) {
          const cell = worksheet[XLSX.utils.encode_cell({ r: range.s.r, c: C })];
          cols.push(cell ? String(cell.v).trim() : `Column ${C + 1}`);
        }
        setHeaders(cols);
      }
      
      // Auto-mapping attempt
      const newMapping: Record<string, string> = {};
      const lowerHeaders = headers.map(h => h.toLowerCase());
      
      SYSTEM_FIELDS.forEach(field => {
        const match = headers.find(h => 
          h.toLowerCase() === field.key.toLowerCase() || 
          h.toLowerCase() === field.label.toLowerCase() ||
          (field.key === 'phone_number' && ['mobile', 'phone', 'contact'].includes(h.toLowerCase()))
        );
        if (match) newMapping[field.key] = match;
      });
      setMapping(newMapping);
      setStep(2);
    } catch (err) {
      setError("Failed to parse file headers. Please ensure it is a valid CSV or Excel file.");
    }
  };

  const handleImport = async () => {
    if (!file || !mapping.phone_number) return;
    
    setIsImporting(true);
    setError(null);

    try {
      await whatsappApi.bulkImport(file, undefined, true, JSON.stringify(mapping));
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Import failed. Please check your file data.");
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[60] flex items-center justify-center p-4">
      <div className="w-full max-w-2xl bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="p-6 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center bg-slate-50/50 dark:bg-slate-800/50">
          <div>
            <h2 className="text-xl font-bold text-slate-900 dark:text-white">Bulk Contact Import</h2>
            <p className="text-xs text-slate-500 mt-1">Upload and map your data columns</p>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-xl transition-colors">
            <X size={20} className="text-slate-500" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-8">
          {error && (
            <div className="mb-6 p-4 bg-rose-50 dark:bg-rose-500/10 border border-rose-100 dark:border-rose-500/20 rounded-xl flex items-start gap-3 text-rose-600 dark:text-rose-400">
              <AlertCircle size={20} className="shrink-0 mt-0.5" />
              <p className="text-sm font-medium">{error}</p>
            </div>
          )}

          {step === 1 ? (
            <div className="flex flex-col items-center justify-center py-12 border-2 border-dashed border-slate-200 dark:border-slate-700 rounded-3xl bg-slate-50/50 dark:bg-slate-800/30">
              <div className="w-16 h-16 bg-white dark:bg-slate-800 rounded-2xl shadow-sm flex items-center justify-center mb-6">
                <Upload className="text-indigo-600" size={32} />
              </div>
              <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-2">Upload your file</h3>
              <p className="text-sm text-slate-500 mb-8 px-12 text-center">Drag and drop your .csv or .xlsx file here, or click to browse</p>
              
              <label className="px-8 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-bold shadow-lg shadow-indigo-600/20 transition-all cursor-pointer active:scale-95">
                Select File
                <input type="file" className="hidden" accept=".csv,.xlsx" onChange={handleFileChange} />
              </label>
            </div>
          ) : (
            <div className="space-y-8">
              <div className="bg-amber-50 dark:bg-amber-500/10 border border-amber-100 dark:border-amber-500/20 p-4 rounded-xl flex items-start gap-3">
                <Table size={20} className="text-amber-600 dark:text-amber-400 shrink-0" />
                <p className="text-xs text-amber-800 dark:text-amber-300 leading-relaxed font-medium">
                  We found <strong>{headers.length} columns</strong> in your file. Please map them to the system fields below to ensure correct data import.
                </p>
              </div>

              <div className="grid gap-4">
                {SYSTEM_FIELDS.map(field => (
                  <div key={field.key} className="flex flex-col md:flex-row md:items-center gap-4 p-4 rounded-xl border border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-indigo-100 dark:hover:border-indigo-900/40 transition-all">
                    <div className="w-48 shrink-0">
                      <span className="text-sm font-bold text-slate-700 dark:text-slate-300">{field.label}</span>
                      {field.required && <span className="ml-1 text-rose-500">*</span>}
                    </div>
                    
                    <ArrowRight size={16} className="text-slate-300 hidden md:block" />
                    
                    <select 
                      value={mapping[field.key] || ''} 
                      onChange={(e) => setMapping(prev => ({...prev, [field.key]: e.target.value}))}
                      className="flex-1 bg-slate-50 dark:bg-slate-800 border-none rounded-lg py-2 px-3 text-sm font-medium outline-none focus:ring-2 focus:ring-indigo-500/20"
                    >
                      <option value="">Don't Import</option>
                      {headers.map(h => (
                        <option key={h} value={h}>{h}</option>
                      ))}
                    </select>
                    
                    <div className="w-6 flex justify-center">
                      {mapping[field.key] ? <Check size={16} className="text-emerald-500" /> : field.required ? <AlertCircle size={16} className="text-rose-400" /> : null}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/50 flex justify-between">
          <button 
            disabled={isImporting}
            onClick={() => step === 1 ? onClose() : setStep(1)} 
            className="px-6 py-2.5 text-sm font-bold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition-colors"
          >
            {step === 1 ? 'Cancel' : 'Back to Upload'}
          </button>
          
          {step === 2 && (
            <button 
              onClick={handleImport}
              disabled={isImporting || !mapping.phone_number}
              className="px-8 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-xl font-bold shadow-lg shadow-indigo-600/20 transition-all flex items-center gap-2"
            >
              {isImporting ? <Loader2 size={18} className="animate-spin" /> : <Check size={18} />}
              {isImporting ? 'Importing Data...' : 'Confirm & Import'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default BulkImportMapper;
