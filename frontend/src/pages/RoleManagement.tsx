import React, { useEffect, useState } from 'react';
import { Shield, ShieldCheck, Plus, Save, Loader2, Info, X, Edit3, Layers } from 'lucide-react';
import { whatsappApi, Role } from '../services/whatsappApi';
import PageHeader from '../components/PageHeader';
import { useToast } from '../components/Toast';
import { useAuth } from '../context/AuthContext';

const RoleManagement: React.FC = () => {
    const [roles, setRoles] = useState<Role[]>([]);
    const [permissions, setPermissions] = useState<Record<string, any[]>>({});
    const [isLoading, setIsLoading] = useState(true);
    
    const [selectedRole, setSelectedRole] = useState<Role | null>(null);
    const { success: toastSuccess, error: toastError } = useToast();
    const [selectedPermIds, setSelectedPermIds] = useState<string[]>([]);
    const [isSaving, setIsSaving] = useState(false);

    const [showNewForm, setShowNewForm] = useState(false);
    const [newRole, setNewRole] = useState({ name: '', slug: '', description: '' });
    
    // Modal state for managing permissions
    const [isManageModalOpen, setIsManageModalOpen] = useState(false);
    const { role: currentUserRole, refreshAuth } = useAuth();

    const fetchData = async () => {
        setIsLoading(true);
        try {
            const [rolesData, permsData] = await Promise.all([
                whatsappApi.getRoles(),
                whatsappApi.getPermissions()
            ]);
            setRoles(Array.isArray(rolesData) ? rolesData : []);
            setPermissions(typeof permsData === 'object' && permsData !== null ? permsData : {});
        } catch (err) {
            console.error(err);
            toastError('Error', 'Failed to fetch roles and permissions. You might not have the right access.');
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
            toastSuccess('Success', 'New role created successfully!');
        } catch (err: any) {
            toastError('Role Error', err.response?.data?.detail || "Failed to create role");
        }
    };

    const handleOpenManageModal = (role: Role) => {
        setSelectedRole(role);
        setSelectedPermIds(role.permission_ids || []);
        setIsManageModalOpen(true);
    };

    const handleSavePermissions = async () => {
        if (!selectedRole) return;
        setIsSaving(true);
        try {
            await whatsappApi.assignRolePermissions(selectedRole.id, selectedPermIds);
            toastSuccess('Permissions Updated', "Role permissions synchronized successfully!");
            setIsManageModalOpen(false);
            fetchData();
            
            // If the user modified their own role (e.g. Super Admin), refresh auth so sidebar updates
            if (selectedRole.slug === currentUserRole) {
                await refreshAuth();
            }
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
        <div className="space-y-8 animate-in slide-in-from-bottom-4 duration-500 font-sans">
            <PageHeader 
                title="System Role Management" 
                description="View and configure system roles, bypass policies, and detailed permission matrices"
            />

            <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                <div className="p-8 border-b border-slate-100 dark:border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-6 bg-slate-50/50 dark:bg-slate-800/30">
                    <div className="flex items-center gap-4">
                        <div className="w-10 h-10 bg-indigo-500/10 rounded-xl flex items-center justify-center">
                            <ShieldCheck size={20} className="text-indigo-600 dark:text-indigo-400" />
                        </div>
                        <div>
                            <h3 className="text-sm font-black uppercase tracking-widest text-slate-800 dark:text-slate-200">Global Roles</h3>
                            <p className="text-xs text-slate-500 font-medium">Manage access capabilities for user identities</p>
                        </div>
                    </div>
                    
                    {(currentUserRole === 'super_admin' || currentUserRole === 'superadmin') && (
                        <button 
                            onClick={() => setShowNewForm(true)}
                            className="flex items-center gap-2 px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-[10px] font-black uppercase tracking-widest transition-all shadow-md active:scale-95"
                        >
                            <Plus size={14} />
                            Create Role
                        </button>
                    )}
                </div>

                <div className="overflow-x-auto custom-scrollbar min-h-[400px]">
                    <table className="w-full text-left text-sm border-separate border-spacing-0">
                        <thead>
                            <tr className="bg-slate-50/50 dark:bg-slate-800/50">
                                <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800">Role Identity</th>
                                <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800">System Slug</th>
                                <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800 text-center">Isolation Bypass</th>
                                <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800 text-center">Attached Permissions</th>
                                <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800 text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-50 dark:divide-slate-800/50">
                            {isLoading ? (
                                <tr className="animate-pulse">
                                    <td colSpan={5} className="py-24 text-center">
                                        <Loader2 className="animate-spin text-indigo-500 mx-auto mb-4" size={32} />
                                        <p className="text-[10px] font-black uppercase tracking-widest text-slate-400">Loading Global Roles...</p>
                                    </td>
                                </tr>
                            ) : roles.length === 0 ? (
                                <tr>
                                    <td colSpan={5} className="py-24 text-center text-slate-400">
                                        <Shield size={48} className="opacity-20 mx-auto mb-4" />
                                        <p className="text-[10px] font-black uppercase tracking-widest">No Roles Found</p>
                                    </td>
                                </tr>
                            ) : roles.map(role => (
                                <tr key={role.id} className="hover:bg-indigo-50/30 dark:hover:bg-indigo-500/5 transition-all group">
                                    <td className="px-8 py-5">
                                        <div className="flex items-center gap-4">
                                            <div className="w-10 h-10 bg-slate-100 dark:bg-slate-800 rounded-xl flex items-center justify-center text-slate-400 font-black text-sm shadow-sm">
                                                {role.name.charAt(0)}
                                            </div>
                                            <div>
                                                <p className="text-sm font-black text-slate-900 dark:text-white leading-none mb-1">{role.name}</p>
                                                <p className="text-[10px] font-bold text-slate-400">{role.description || 'System Role'}</p>
                                            </div>
                                        </div>
                                    </td>
                                    
                                    <td className="px-8 py-5">
                                        <div className="flex items-center gap-2">
                                            <span className="text-[10px] font-black uppercase tracking-widest text-slate-500 bg-slate-100 dark:bg-slate-800 px-3 py-1 rounded-md">
                                                {role.slug}
                                            </span>
                                        </div>
                                    </td>

                                    <td className="px-8 py-5 text-center">
                                        <span className={`inline-flex items-center px-3 py-1 rounded-full text-[9px] font-black uppercase tracking-widest border ${role.can_bypass_isolation ? 'bg-amber-500/10 text-amber-600 border-amber-500/20' : 'bg-slate-100 text-slate-500 border-slate-200 dark:bg-slate-800 dark:border-slate-700'}`}>
                                            {role.can_bypass_isolation ? 'Bypass Enabled' : 'Restricted'}
                                        </span>
                                    </td>

                                    <td className="px-8 py-5 text-center">
                                        <div className="inline-flex items-center gap-1.5 px-3 py-1 bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 rounded-lg text-xs font-bold">
                                            <Layers size={14} />
                                            {role.permission_ids?.length || 0}
                                        </div>
                                    </td>

                                    <td className="px-8 py-5 text-right">
                                        <button
                                            onClick={() => handleOpenManageModal(role)}
                                            className="inline-flex items-center gap-2 px-4 py-2 bg-white dark:bg-slate-800 hover:bg-indigo-50 dark:hover:bg-indigo-500/10 text-indigo-600 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all shadow-sm border border-slate-200 dark:border-slate-700 hover:border-indigo-200"
                                        >
                                            <Edit3 size={14} />
                                            Manage Matrix
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Permission Management Modal */}
            {isManageModalOpen && selectedRole && (
                <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div className="bg-white dark:bg-slate-900 rounded-3xl shadow-2xl w-full max-w-5xl max-h-[90vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-200">
                        <div className="p-6 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center bg-slate-50/50 dark:bg-slate-800/30">
                            <div>
                                <h2 className="text-xl font-black text-slate-900 dark:text-white flex items-center gap-3">
                                    <ShieldCheck className="text-indigo-500" />
                                    {selectedRole.name} Permissions
                                </h2>
                                <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mt-1">Configure screen and action capabilities</p>
                            </div>
                            <button onClick={() => setIsManageModalOpen(false)} className="p-2 bg-slate-100 hover:bg-rose-100 text-slate-500 hover:text-rose-500 rounded-xl transition-all">
                                <X size={20} />
                            </button>
                        </div>
                        
                        <div className="flex-1 overflow-auto p-8 bg-slate-50/30 dark:bg-slate-950/30">
                            {Object.entries(permissions).map(([module, perms]) => (
                                <div key={module} className="mb-10 last:mb-0">
                                    <div className="flex items-center gap-3 pb-3 mb-4 border-b border-slate-200 dark:border-slate-800">
                                        <div className="p-2 bg-indigo-500/10 rounded-lg">
                                            <Layers size={16} className="text-indigo-500" />
                                        </div>
                                        <h4 className="text-sm font-black uppercase tracking-widest text-slate-800 dark:text-slate-200">{module}</h4>
                                    </div>
                                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 pl-2">
                                        {(Array.isArray(perms) ? perms : []).map((p: any) => (
                                            <div 
                                                key={p.id}
                                                onClick={() => togglePermission(p.id)}
                                                className={`p-4 rounded-xl border-2 cursor-pointer transition-all ${selectedPermIds.includes(p.id) ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-500/10 shadow-sm' : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-indigo-300'}`}
                                            >
                                                <div className="flex items-start justify-between mb-2">
                                                    <span className={`text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded-md ${p.type === 'screen' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                                                        {p.type}
                                                    </span>
                                                    <div className={`w-4 h-4 rounded border flex items-center justify-center transition-all ${selectedPermIds.includes(p.id) ? 'bg-indigo-500 border-indigo-500' : 'border-slate-300'}`}>
                                                        {selectedPermIds.includes(p.id) && <div className="w-2 h-2 bg-white rounded-full" />}
                                                    </div>
                                                </div>
                                                <p className="text-xs font-bold text-slate-900 dark:text-white leading-tight mt-3">{p.name}</p>
                                                <p className="text-[9px] font-bold text-slate-400 mt-1 uppercase tracking-widest truncate">{p.slug}</p>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>

                        <div className="p-6 border-t border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900 flex justify-end gap-3">
                            <button onClick={() => setIsManageModalOpen(false)} className="px-6 py-2.5 rounded-xl text-xs font-bold text-slate-500 hover:bg-slate-100 transition-all">
                                Discard Changes
                            </button>
                            <button 
                                onClick={handleSavePermissions}
                                disabled={isSaving}
                                className="flex items-center gap-2 px-8 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-black uppercase tracking-widest transition-all shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {isSaving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                                Save Policy
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Create Role Modal */}
            {showNewForm && (
                <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div className="bg-white dark:bg-slate-900 p-8 rounded-3xl shadow-2xl w-full max-w-md animate-in zoom-in-95 duration-200">
                        <div className="flex justify-between items-center mb-6">
                            <h3 className="text-xl font-black text-slate-900 dark:text-white">Create New Role</h3>
                            <button onClick={() => setShowNewForm(false)} className="p-2 bg-slate-100 hover:bg-rose-100 text-slate-500 hover:text-rose-500 rounded-xl transition-all">
                                <X size={18} />
                            </button>
                        </div>
                        <div className="space-y-5">
                            <div>
                                <label className="text-[10px] font-black uppercase tracking-widest text-slate-400 block mb-1">Role Name</label>
                                <input 
                                    type="text" 
                                    value={newRole.name} 
                                    onChange={e => setNewRole({...newRole, name: e.target.value, slug: e.target.value.toLowerCase().replace(/\s+/g, '_')})}
                                    className="w-full px-4 py-3 border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 rounded-xl text-sm font-bold focus:border-indigo-500 outline-none transition-all" 
                                    placeholder="e.g. Sales Manager"
                                />
                            </div>
                            <div>
                                <label className="text-[10px] font-black uppercase tracking-widest text-slate-400 block mb-1">System Slug (Auto-generated)</label>
                                <input 
                                    type="text" 
                                    value={newRole.slug} 
                                    onChange={e => setNewRole({...newRole, slug: e.target.value})}
                                    className="w-full px-4 py-3 border border-slate-200 dark:border-slate-800 bg-slate-100 dark:bg-slate-950 rounded-xl text-sm font-bold outline-none cursor-not-allowed opacity-70" 
                                    readOnly
                                />
                            </div>
                            <div>
                                <label className="text-[10px] font-black uppercase tracking-widest text-slate-400 block mb-1">Description</label>
                                <textarea 
                                    value={newRole.description} 
                                    onChange={e => setNewRole({...newRole, description: e.target.value})}
                                    className="w-full px-4 py-3 border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 rounded-xl text-sm font-bold focus:border-indigo-500 outline-none transition-all" 
                                    placeholder="Brief explanation of this role..."
                                    rows={3}
                                />
                            </div>
                            <div className="pt-4 flex gap-3">
                                <button onClick={() => setShowNewForm(false)} className="flex-1 py-3 border border-slate-200 dark:border-slate-800 rounded-xl text-xs font-bold hover:bg-slate-50 dark:hover:bg-slate-800 transition-all">Cancel</button>
                                <button onClick={handleCreateRole} className="flex-1 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-black uppercase tracking-widest transition-all shadow-md shadow-indigo-500/20">Save Role</button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default RoleManagement;
