import React, { useEffect, useState } from 'react';
import { Shield, Layers, Plus, Save, Loader2, Info } from 'lucide-react';
import { whatsappApi, Role } from '../services/whatsappApi';
import PageHeader from '../components/PageHeader';
import { useToast } from '../components/Toast';

const RoleManagement: React.FC = () => {
    const [roles, setRoles] = useState<Role[]>([]);
    const [permissions, setPermissions] = useState<Record<string, any[]>>({});
    const [isLoading, setIsLoading] = useState(true);
    
    const [selectedRole, setSelectedRole] = useState<Role | null>(null);
    const { success: toastSuccess, error: toastError } = useToast();
    const [selectedPermIds, setSelectedPermIds] = useState<string[]>([]);
    const [isSaving, setIsSaving] = useState(false);

    // New Role Form
    const [showNewForm, setShowNewForm] = useState(false);
    const [newRole, setNewRole] = useState({ name: '', slug: '', description: '' });

    const fetchData = async () => {
        setIsLoading(true);
        try {
            const [rolesData, permsData] = await Promise.all([
                whatsappApi.getRoles(),
                whatsappApi.getPermissions()
            ]);
            setRoles(rolesData);
            setPermissions(permsData);
            
            if (rolesData.length > 0 && !selectedRole) {
                // By default select first role
                setSelectedRole(rolesData[0]);
                setSelectedPermIds(rolesData[0].permission_ids || []);
            } else if (selectedRole) {
                // Refresh selected role data
                const updated = rolesData.find(r => r.id === selectedRole.id);
                if (updated) {
                    setSelectedRole(updated);
                    setSelectedPermIds(updated.permission_ids || []);
                }
            }
        } catch (err) {
            console.error(err);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    const handleCreateRole = async () => {
        try {
            await whatsappApi.createRole(newRole);
            setShowNewForm(false);
            setNewRole({ name: '', slug: '', description: '' });
            fetchData();
        } catch (err: any) {
            toastError('Role Error', err.response?.data?.detail || "Failed to create role");
        }
    };

    const handleSavePermissions = async () => {
        if (!selectedRole) return;
        setIsSaving(true);
        try {
            await whatsappApi.assignRolePermissions(selectedRole.id, selectedPermIds);
            toastSuccess('Permissions Updated', "Role permissions synchronized successfully!");
        } catch (err: any) {
            toastError('Update Failed', err.response?.data?.detail || "Failed to update permissions");
        } finally {
            setIsSaving(false);
        }
    };

    const togglePermission = (id: string) => {
        setSelectedPermIds(prev => 
            prev.includes(id) ? prev.filter(p => p !== id) : [...prev, id]
        );
    };

    return (
        <div className="space-y-8 animate-in fade-in duration-500 font-sans">
            <PageHeader 
                title="Advanced Role Management" 
                description="Configure granular screen and action access across all modules"
            />

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
                {/* Roles Sidebar */}
                <div className="lg:col-span-1 space-y-4">
                    <div className="flex items-center justify-between">
                        <h3 className="text-sm font-black uppercase tracking-widest text-slate-500">System Roles</h3>
                        <button 
                            onClick={() => setShowNewForm(true)}
                            className="p-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-600 rounded-lg transition-all"
                        >
                            <Plus size={16} />
                        </button>
                    </div>

                    <div className="space-y-2">
                        {isLoading ? (
                            <div className="py-8 flex justify-center"><Loader2 className="animate-spin text-slate-300" /></div>
                        ) : roles.map(role => (
                            <div 
                                key={role.id}
                                onClick={() => {
                                    setSelectedRole(role);
                                    setSelectedPermIds(role.permission_ids || []);
                                }}
                                className={`p-4 rounded-2xl border cursor-pointer transition-all ${selectedRole?.id === role.id ? 'bg-indigo-500 text-white border-indigo-600 shadow-lg' : 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 hover:border-indigo-300'}`}
                            >
                                <div className="flex items-center gap-3">
                                    <Shield size={16} className={selectedRole?.id === role.id ? 'text-white/80' : 'text-slate-400'} />
                                    <div>
                                        <p className="text-sm font-black tracking-tight">{role.name}</p>
                                        <p className={`text-[10px] font-bold uppercase tracking-widest mt-1 ${selectedRole?.id === role.id ? 'text-indigo-200' : 'text-slate-400'}`}>
                                            {role.slug}
                                        </p>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Permissions Matrix */}
                <div className="lg:col-span-3">
                    {showNewForm ? (
                        <div className="bg-white dark:bg-slate-900 p-8 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm">
                            <h3 className="text-lg font-black mb-6">Create New Role</h3>
                            <div className="space-y-4">
                                <div>
                                    <label className="text-[10px] font-black uppercase tracking-widest text-slate-400">Role Name</label>
                                    <input 
                                        type="text" 
                                        value={newRole.name} 
                                        onChange={e => setNewRole({...newRole, name: e.target.value, slug: e.target.value.toLowerCase().replace(/\s+/g, '_')})}
                                        className="w-full mt-1 px-4 py-2 border rounded-xl" 
                                    />
                                </div>
                                <div>
                                    <label className="text-[10px] font-black uppercase tracking-widest text-slate-400">System Slug (Auto-generated)</label>
                                    <input 
                                        type="text" 
                                        value={newRole.slug} 
                                        onChange={e => setNewRole({...newRole, slug: e.target.value})}
                                        className="w-full mt-1 px-4 py-2 border rounded-xl bg-slate-50" 
                                    />
                                </div>
                                <div className="pt-4 flex gap-2">
                                    <button onClick={() => setShowNewForm(false)} className="px-6 py-2 border rounded-xl text-xs font-bold">Cancel</button>
                                    <button onClick={handleCreateRole} className="px-6 py-2 bg-indigo-600 text-white rounded-xl text-xs font-bold">Save Role</button>
                                </div>
                            </div>
                        </div>
                    ) : selectedRole ? (
                        <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden flex flex-col h-[calc(100vh-200px)] min-h-[600px]">
                            <div className="p-6 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 flex justify-between items-center">
                                <div>
                                    <h2 className="text-xl font-black text-slate-900 dark:text-white">{selectedRole.name} Access Matrix</h2>
                                    <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mt-1">Select the screens and actions this role can perform</p>
                                </div>
                                <button 
                                    onClick={handleSavePermissions}
                                    disabled={isSaving}
                                    className="flex items-center gap-2 px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-[10px] font-black uppercase tracking-widest transition-all shadow-md disabled:opacity-50"
                                >
                                    {isSaving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                                    Save Policy
                                </button>
                            </div>

                            <div className="flex-1 overflow-auto p-6 space-y-8 custom-scrollbar">
                                {Object.entries(permissions).map(([module, perms]) => (
                                    <div key={module} className="space-y-4">
                                        <div className="flex items-center gap-2 pb-2 border-b border-slate-100 dark:border-slate-800">
                                            <Layers size={14} className="text-indigo-500" />
                                            <h4 className="text-sm font-black uppercase tracking-widest text-slate-800 dark:text-slate-200">{module}</h4>
                                        </div>
                                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                            {perms.map((p: any) => (
                                                <div 
                                                    key={p.id}
                                                    onClick={() => togglePermission(p.id)}
                                                    className={`p-4 rounded-xl border-2 cursor-pointer transition-all ${selectedPermIds.includes(p.id) ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-500/10' : 'border-slate-100 dark:border-slate-800 hover:border-slate-300'}`}
                                                >
                                                    <div className="flex items-center justify-between mb-2">
                                                        <span className={`text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded-md ${p.type === 'screen' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                                                            {p.type}
                                                        </span>
                                                        <div className={`w-4 h-4 rounded border flex items-center justify-center ${selectedPermIds.includes(p.id) ? 'bg-indigo-500 border-indigo-500' : 'border-slate-300'}`}>
                                                            {selectedPermIds.includes(p.id) && <div className="w-1.5 h-1.5 bg-white rounded-full" />}
                                                        </div>
                                                    </div>
                                                    <p className="text-xs font-bold text-slate-900 dark:text-white leading-tight">{p.name}</p>
                                                    <p className="text-[9px] font-black text-slate-400 mt-1 uppercase tracking-widest">{p.slug}</p>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ) : (
                        <div className="h-full flex flex-col items-center justify-center text-slate-400">
                            <Info size={48} className="opacity-20 mb-4" />
                            <p className="text-sm font-black uppercase tracking-widest">Select a role to manage permissions</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default RoleManagement;
