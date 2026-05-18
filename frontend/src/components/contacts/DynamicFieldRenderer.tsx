import React from 'react';
import { CustomSelect } from '../CustomSelect';

interface FieldConfig {
    id: string;
    field_name: string;
    field_label: string;
    field_type: string;
    is_required?: boolean;
    options?: string[];
}

interface DynamicFieldRendererProps {
    config: FieldConfig;
    value: any;
    onChange: (value: any) => void;
}

export const DynamicFieldRenderer: React.FC<DynamicFieldRendererProps> = ({ config, value, onChange }) => {
    const { field_label, field_type, options, field_name } = config;

    const labelElement = (
        <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest ml-1">
            {field_label}
            {config.is_required && <span className="text-rose-500 ml-1">*</span>}
        </label>
    );

    if (field_type === 'select' || field_type === 'dropdown') {
        const selectOptions = [
            { value: "", label: `Select ${field_label}` },
            ...(options || []).map(opt => ({ value: opt, label: opt }))
        ];
        return (
            <CustomSelect
                label={field_label}
                value={value || ""}
                onChange={onChange}
                options={selectOptions}
            />
        );
    }

    if (field_type === 'number') {
        return (
            <div className="space-y-1.5">
                {labelElement}
                <input 
                    type="number"
                    value={value || ""} 
                    onChange={e => onChange(e.target.value)} 
                    placeholder={`Enter ${field_label.toLowerCase()}`}
                    className="w-full h-[48px] px-4 bg-slate-50/50 dark:bg-slate-800/30 border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all text-sm" 
                />
            </div>
        );
    }

    // Default to text
    return (
        <div className="space-y-1.5">
            {labelElement}
            <input 
                type="text"
                value={value || ""} 
                onChange={e => onChange(e.target.value)} 
                placeholder={`Enter ${field_label.toLowerCase()}`}
                className="w-full h-[48px] px-4 bg-slate-50/50 dark:bg-slate-800/30 border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all text-sm" 
            />
        </div>
    );
};
