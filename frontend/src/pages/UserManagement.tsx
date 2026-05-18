import React, { useEffect, useState } from 'react';
import {
    Users,
    Shield,
    Globe,
    Search,
    Filter,
    Edit3,
    Trash2,
    CheckCircle2,
    XCircle,
    ChevronDown,
    MoreVertical,
    Loader2,
    Settings,
    Save,
    UserCircle,
    PowerOff
} from 'lucide-react';
import { whatsappApi, Organization, User, Role } from '../services/whatsappApi';
import PageHeader from '../components/PageHeader';
import { useToast } from '../components/Toast';

const UserManagement: React.FC = () => {
    const [users, setUsers] = useState<User[]>([]);
    const { error: toastError, success: toastSuccess, info: toastInfo } = useToast();
    const [roles, setRoles] = useState<Role[]>([]);
    const [organizations, setOrganizations] = useState<Organization[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState("");

    // Modals & Selection
    const [showEditModal, setShowEditModal] = useState(false);
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [selectedUser, setSelectedUser] = useState<User | null>(null);
    const [isSaving, setIsSaving] = useState(false);

    const [editForm, setEditForm] = useState({
        role_id: "",
        organization_id: "",
        is_active: true
    });

    const [createForm, setCreateForm] = useState({
        username: "",
        email: "",
        password: "",
        full_name: "",
        role_id: "",
        organization_id: ""
    });

    const fetchData = async () => {
        setIsLoading(true);
        try {
            const [usersData, rolesData, orgsData] = await Promise.all([
                whatsappApi.getAllUsers(),
                whatsappApi.getRoles(),
                whatsappApi.getOrganizations()
            ]);
            setUsers(usersData);
            setRoles(rolesData);
            setOrganizations(orgsData);
        } catch (err) {
            console.error(err);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    const handleOpenEdit = (user: User) => {
        setSelectedUser(user);
        setEditForm({
            role_id: user.role_id || roles.find(r => r.slug === user.role)?.id || "",
            organization_id: user.organization_id || "",
            is_active: user.is_active
        });
        setShowEditModal(true);
    };

    const handleSaveAccess = async () => {
        if (!selectedUser) return;
        setIsSaving(true);
        try {
            await whatsappApi.updateUserAccess(selectedUser.id, editForm);
            setShowEditModal(false);
            fetchData();
        } catch (err) {
            console.error(err);
        } finally {
            setIsSaving(false);
        }
    };

    const handleCreateSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsSaving(true);
        try {
            const selectedRoleObj = roles.find(r => r.id === createForm.role_id);
            const roleSlug = selectedRoleObj ? selectedRoleObj.slug : "agent";

            await whatsappApi.registerAgent({
                username: createForm.username,
                email: createForm.email,
                password: createForm.password,
                full_name: createForm.full_name,
                role: roleSlug,
                organization_id: createForm.organization_id || null
            });
            setShowCreateModal(false);
            setCreateForm({ username: "", email: "", password: "", full_name: "", role_id: "", organization_id: "" });
            fetchData();
        } catch (err: any) {
            console.error(err);
            const errMsg = err?.response?.data?.detail || "Failed to create user. Ensure username and email are unique.";
            toastError('Account Creation Failed', errMsg);
        } finally {
            setIsSaving(false);
        }
    };

    const handleDeleteUser = async (userId: string) => {
        toastInfo('Processing', "Terminating user's access...");
        try {
            await whatsappApi.deleteUser(userId);
            fetchData();
        } catch (err) {
            console.error(err);
        }
    };

    const handleImpersonate = async (userId: string) => {
        toastInfo('Identity Switch', "Switching into user perspective...");
        try {
            const data = await whatsappApi.impersonateUser(userId);
            localStorage.setItem('token', data.access_token);
            localStorage.setItem('role', data.role);
            localStorage.setItem('username', data.username);
            window.location.href = '/'; // Reload whole app
        } catch (err) {
            console.error("Impersonation failed", err);
            toastError('Switch Failed', "Failed to impersonate user.");
        }
    };

    const handleForceLogout = async (userId: string) => {
        toastInfo('Security Action', "Invalidating all active sessions...");
        try {
            await whatsappApi.forceLogoutUser(userId);
            toastSuccess('Sessions Cleared', "User sessions invalidated.");
        } catch (err) {
            console.error("Force logout failed", err);
            toastError('Action Failed', "Failed to force logout user.");
        }
    };

    const filteredUsers = users.filter((u: User) =>
        u.username.toLowerCase().includes(searchQuery.toLowerCase()) ||
        u.email?.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div className="space-y-8 animate-in slide-in-from-bottom-4 duration-500 font-sans">
            <PageHeader
                title="Global User Access"
                description="Manage permissions and organization assignments across the entire platform"
            />

            <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                <div className="p-8 border-b border-slate-100 dark:border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-6 bg-slate-50/50 dark:bg-slate-800/30">
                    <div className="relative w-full md:w-96">
                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                        <input
                            type="text"
                            placeholder="Find user by identity or email..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="w-full pl-12 pr-4 py-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl text-[11px] font-black uppercase tracking-wider focus:ring-2 focus:ring-indigo-500 transition-all placeholder:opacity-50"
                        />
                    </div>

                    <div className="flex items-center gap-4">
                        <button
                            onClick={() => setShowCreateModal(true)}
                            className="px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-2xl text-[11px] font-black uppercase tracking-widest transition-all shadow-lg active:scale-95 flex items-center gap-2"
                        >
                            <Users size={16} />
                            Create User
                        </button>
                        <div className="px-4 py-1.5 bg-slate-100 dark:bg-slate-800 rounded-full text-[10px] font-black text-slate-500 uppercase tracking-widest">
                            {users.length} Platform Accounts
                        </div>
                    </div>
                </div>

                <div className="overflow-x-auto custom-scrollbar min-h-[500px]">
                    <table className="w-full text-left text-sm border-separate border-spacing-0">
                        <thead>
                            <tr className="bg-slate-50/50 dark:bg-slate-800/50">
                                <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800">User Identity</th>
                                <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800">Home Organization</th>
                                <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800">Assigned Role</th>
                                <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800 text-center">Health</th>
                                <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800 text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-50 dark:divide-slate-800/50">
                            {isLoading ? (
                                <tr className="animate-pulse">
                                    <td colSpan={5} className="py-24 text-center">
                                        <Loader2 className="animate-spin text-indigo-500 mx-auto mb-4" size={32} />
                                        <p className="text-[10px] font-black uppercase tracking-widest text-slate-400">Synchronizing Platform Users...</p>
                                    </td>
                                </tr>
                            ) : filteredUsers.map((user) => {
                                const userOrg = organizations.find(o => o.id === user.organization_id);
                                const userRole = roles.find(r => r.id === user.role_id || r.slug === user.role);
                                return (
                                    <tr key={user.id} className="hover:bg-indigo-50/30 dark:hover:bg-indigo-500/5 transition-all group">
                                        <td className="px-8 py-5">
                                            <div className="flex items-center gap-4">
                                                <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-indigo-700 rounded-xl flex items-center justify-center text-white font-black text-sm shadow-md">
                                                    {user.username.charAt(0).toUpperCase()}
                                                </div>
                                                <div>
                                                    <p className="text-sm font-black text-slate-900 dark:text-white leading-none mb-1">{user.username}</p>
                                                    <p className="text-[10px] font-bold text-slate-400 lowercase">{user.email || 'no-email@system'}</p>
                                                </div>
                                            </div>
                                        </td>

                                        <td className="px-8 py-5">
                                            <div className="flex items-center gap-2">
                                                <Globe size={14} className="text-slate-300" />
                                                <span className="text-xs font-bold text-slate-600 dark:text-slate-400">{userOrg?.name || 'Unassigned'}</span>
                                            </div>
                                        </td>

                                        <td className="px-8 py-5">
                                            <div className="flex items-center gap-2">
                                                <Shield size={14} className="text-slate-300" />
                                                <span className="text-[10px] font-black uppercase tracking-widest text-indigo-600 dark:text-indigo-400">{userRole?.name || 'Guest'}</span>
                                            </div>
                                        </td>

                                        <td className="px-8 py-5 text-center">
                                            <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[9px] font-black uppercase tracking-widest border ${user.is_active ? 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20' : 'bg-rose-500/10 text-rose-600 border-rose-500/20'}`}>
                                                <div className={`w-1 h-1 rounded-full ${user.is_active ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                                                {user.is_active ? 'Active' : 'Suspended'}
                                            </span>
                                        </td>

                                        <td className="px-8 py-5 text-right">
                                            <div className="flex items-center justify-end gap-2 transition-all">
                                                <button
                                                    onClick={() => handleImpersonate(user.id)}
                                                    className="p-2 bg-indigo-50 hover:bg-indigo-600 text-indigo-500 hover:text-white border border-indigo-200 dark:border-indigo-800 rounded-xl transition-all shadow-sm"
                                                    title="Impersonate User"
                                                >
                                                    <UserCircle size={16} />
                                                </button>
                                                <button
                                                    onClick={() => handleForceLogout(user.id)}
                                                    className="p-2 bg-amber-50 hover:bg-amber-500 text-amber-500 hover:text-white border border-amber-200 dark:border-amber-800 rounded-xl transition-all shadow-sm"
                                                    title="Force Logout All Sessions"
                                                >
                                                    <PowerOff size={16} />
                                                </button>
                                                <button
                                                    onClick={() => handleOpenEdit(user)}
                                                    className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-[10px] font-black uppercase tracking-widest transition-all shadow-md active:scale-95"
                                                >
                                                    <Settings size={14} />
                                                    Manage
                                                </button>
                                                <button
                                                    onClick={() => handleDeleteUser(user.id)}
                                                    className="p-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-slate-400 hover:text-rose-500 transition-all shadow-sm"
                                                    title="Delete User"
                                                >
                                                    <Trash2 size={16} />
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* User Edit Modal (Popup) */}
            {showEditModal && selectedUser && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-md animate-in fade-in duration-300">
                    <div className="bg-white dark:bg-slate-900 w-full max-w-lg rounded-[32px] shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden animate-in zoom-in-95 duration-300">
                        <div className="p-8 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 flex justify-between items-center">
                            <div className="flex items-center gap-4">
                                <div className="w-12 h-12 bg-gradient-to-br from-indigo-500 to-indigo-700 rounded-2xl flex items-center justify-center text-white shadow-lg font-black text-xl">
                                    {selectedUser.username.charAt(0)}
                                </div>
                                <div>
                                    <h3 className="text-xl font-black text-slate-900 dark:text-white leading-none mb-1 uppercase tracking-tight">{selectedUser.username}</h3>
                                    <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">{selectedUser.email || 'Global Access Policy'}</p>
                                </div>
                            </div>
                            <button
                                onClick={() => setShowEditModal(false)}
                                className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-full transition-all text-slate-400"
                            >
                                <XCircle size={24} />
                            </button>
                        </div>

                        <div className="p-8 space-y-8">
                            <div className="space-y-6">
                                <section className="space-y-4">
                                    <label className="text-[10px] font-black uppercase tracking-widest text-slate-400 ml-1">Platform Credentials</label>
                                    <div className="grid grid-cols-1 gap-4">
                                        <div className="space-y-2">
                                            <label className="text-[10px] font-black uppercase tracking-widest text-slate-400 flex items-center gap-2">
                                                <Globe size={12} /> Home Organization
                                            </label>
                                            <select
                                                value={editForm.organization_id}
                                                onChange={(e) => setEditForm({ ...editForm, organization_id: e.target.value })}
                                                className="w-full px-5 py-3.5 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-2xl text-xs font-bold focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all appearance-none cursor-pointer"
                                            >
                                                {organizations.map(org => (
                                                    <option key={org.id} value={org.id}>{org.name}</option>
                                                ))}
                                            </select>
                                        </div>

                                        <div className="space-y-2">
                                            <label className="text-[10px] font-black uppercase tracking-widest text-slate-400 flex items-center gap-2">
                                                <Shield size={12} /> Access Permissions
                                            </label>
                                            <select
                                                value={editForm.role_id}
                                                onChange={(e) => setEditForm({ ...editForm, role_id: e.target.value })}
                                                className="w-full px-5 py-3.5 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-2xl text-xs font-bold focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all appearance-none cursor-pointer"
                                            >
                                                {roles.map(role => (
                                                    <option key={role.id} value={role.id}>{role.name}</option>
                                                ))}
                                            </select>
                                        </div>
                                    </div>
                                </section>

                                <div className="pt-4 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
                                    <div className="space-y-1">
                                        <p className="text-[11px] font-black uppercase tracking-widest text-slate-700 dark:text-slate-200">Account Health State</p>
                                        <p className="text-[10px] font-bold text-slate-400">Suspended users cannot access any tenant UI.</p>
                                    </div>
                                    <button
                                        onClick={() => setEditForm({ ...editForm, is_active: !editForm.is_active })}
                                        className={`px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${editForm.is_active ? 'bg-emerald-500/10 text-emerald-600 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-600 border border-rose-500/20'}`}
                                    >
                                        {editForm.is_active ? 'ENABLED' : 'TERMINATED'}
                                    </button>
                                </div>
                            </div>
                        </div>

                        <div className="p-8 bg-slate-50/50 dark:bg-slate-800/30 border-t border-slate-100 dark:border-slate-800 flex justify-end gap-4">
                            <button
                                onClick={() => setShowEditModal(false)}
                                className="px-8 py-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-500 rounded-xl text-[10px] font-black uppercase tracking-widest hover:bg-slate-100 transition-all"
                            >
                                Discard
                            </button>
                            <button
                                onClick={handleSaveAccess}
                                disabled={isSaving}
                                className="flex items-center gap-2 px-10 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-[10px] font-black uppercase tracking-widest transition-all shadow-lg active:scale-95 disabled:opacity-50"
                            >
                                {isSaving ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />}
                                Update Access Policy
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* User Create Modal (Popup) */}
            {showCreateModal && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-md animate-in fade-in duration-300">
                    <div className="bg-white dark:bg-slate-900 w-full max-w-lg rounded-[32px] shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden animate-in zoom-in-95 duration-300">
                        <div className="p-8 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 flex justify-between items-center">
                            <div className="flex items-center gap-4">
                                <div className="w-12 h-12 bg-gradient-to-br from-emerald-500 to-emerald-700 rounded-2xl flex items-center justify-center text-white shadow-lg font-black text-xl">
                                    <Users size={24} />
                                </div>
                                <div>
                                    <h3 className="text-xl font-black text-slate-900 dark:text-white leading-none mb-1 uppercase tracking-tight">Create User</h3>
                                    <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Provision new platform account</p>
                                </div>
                            </div>
                            <button
                                onClick={() => setShowCreateModal(false)}
                                className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-full transition-all text-slate-400"
                            >
                                <XCircle size={24} />
                            </button>
                        </div>

                        <form onSubmit={handleCreateSubmit}>
                            <div className="p-8 space-y-6">
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                        <label className="text-[10px] font-black uppercase tracking-widest text-slate-400 ml-1">Username *</label>
                                        <input
                                            type="text"
                                            required
                                            value={createForm.username}
                                            onChange={(e) => setCreateForm({ ...createForm, username: e.target.value })}
                                            className="w-full bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3 text-sm font-semibold text-slate-900 dark:text-white focus:ring-2 focus:ring-indigo-500 transition-all outline-none"
                                            placeholder="johndoe"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-[10px] font-black uppercase tracking-widest text-slate-400 ml-1">Full Name</label>
                                        <input
                                            type="text"
                                            value={createForm.full_name}
                                            onChange={(e) => setCreateForm({ ...createForm, full_name: e.target.value })}
                                            className="w-full bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3 text-sm font-semibold text-slate-900 dark:text-white focus:ring-2 focus:ring-indigo-500 transition-all outline-none"
                                            placeholder="John Doe"
                                        />
                                    </div>
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                        <label className="text-[10px] font-black uppercase tracking-widest text-slate-400 ml-1">Email *</label>
                                        <input
                                            type="email"
                                            required
                                            value={createForm.email}
                                            onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
                                            className="w-full bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3 text-sm font-semibold text-slate-900 dark:text-white focus:ring-2 focus:ring-indigo-500 transition-all outline-none"
                                            placeholder="john@example.com"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-[10px] font-black uppercase tracking-widest text-slate-400 ml-1">Password *</label>
                                        <input
                                            type="password"
                                            required
                                            value={createForm.password}
                                            onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
                                            className="w-full bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3 text-sm font-semibold text-slate-900 dark:text-white focus:ring-2 focus:ring-indigo-500 transition-all outline-none"
                                            placeholder="••••••••"
                                        />
                                        <p className="text-[8px] font-bold text-slate-400 uppercase tracking-tighter mt-1 ml-1">Min 8 chars, 1 Uppercase, 1 Digit, 1 Special Char</p>
                                    </div>
                                </div>

                                <section className="space-y-4 pt-4 border-t border-slate-100 dark:border-slate-800">
                                    <label className="text-[10px] font-black uppercase tracking-widest text-slate-400 ml-1">Platform Credentials</label>
                                    <div className="grid grid-cols-1 gap-4">
                                        <div className="space-y-2">
                                            <p className="text-[11px] font-black text-slate-700 dark:text-slate-200 uppercase tracking-widest">Home Organization</p>
                                            <div className="relative">
                                                <select
                                                    value={createForm.organization_id}
                                                    onChange={(e) => setCreateForm({ ...createForm, organization_id: e.target.value })}
                                                    className="w-full bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3 text-sm font-semibold text-slate-900 dark:text-white focus:ring-2 focus:ring-indigo-500 transition-all outline-none appearance-none cursor-pointer"
                                                >
                                                    <option value="">-- System Level (No Org) --</option>
                                                    {organizations.map(org => (
                                                        <option key={org.id} value={org.id}>{org.name}</option>
                                                    ))}
                                                </select>
                                                <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={16} />
                                            </div>
                                        </div>

                                        <div className="space-y-2">
                                            <p className="text-[11px] font-black text-slate-700 dark:text-slate-200 uppercase tracking-widest">Global Role</p>
                                            <div className="relative">
                                                <select
                                                    required
                                                    value={createForm.role_id}
                                                    onChange={(e) => setCreateForm({ ...createForm, role_id: e.target.value })}
                                                    className="w-full bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3 text-sm font-semibold text-slate-900 dark:text-white focus:ring-2 focus:ring-indigo-500 transition-all outline-none appearance-none cursor-pointer"
                                                >
                                                    <option value="" disabled>Select a Role</option>
                                                    {roles.map(role => (
                                                        <option key={role.id} value={role.id}>{role.name}</option>
                                                    ))}
                                                </select>
                                                <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={16} />
                                            </div>
                                        </div>
                                    </div>
                                </section>
                            </div>

                            <div className="p-8 bg-slate-50/50 dark:bg-slate-800/30 border-t border-slate-100 dark:border-slate-800 flex justify-end gap-4">
                                <button
                                    type="button"
                                    onClick={() => setShowCreateModal(false)}
                                    className="px-8 py-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-500 rounded-xl text-[10px] font-black uppercase tracking-widest hover:bg-slate-100 transition-all"
                                >
                                    Discard
                                </button>
                                <button
                                    type="submit"
                                    disabled={isSaving || !createForm.username || !createForm.email || !createForm.password || !createForm.role_id}
                                    className="flex items-center gap-2 px-10 py-3 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-[10px] font-black uppercase tracking-widest transition-all shadow-lg active:scale-95 disabled:opacity-50"
                                >
                                    {isSaving ? <Loader2 className="animate-spin" size={16} /> : <CheckCircle2 size={16} />}
                                    Create Account
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
};

export default UserManagement;


