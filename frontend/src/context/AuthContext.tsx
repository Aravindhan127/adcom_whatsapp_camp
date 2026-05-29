import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { whatsappApi } from '../services/whatsappApi';

interface AuthContextType {
    isAuthenticated: boolean;
    user: any | null;
    role: string | null;
    permissions: string[];
    isLoading: boolean;
    login: (token: string, role: string, permissions: string[], userData?: any) => void;
    logout: () => void;
    hasPermission: (slug: string) => boolean;
    refreshAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
    const [user, setUser] = useState<any | null>(null);
    const [role, setRole] = useState<string | null>(null);
    const [permissions, setPermissions] = useState<string[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(true);

    const refreshAuth = async () => {
        const token = localStorage.getItem('token');
        if (token) {
            try {
                const profile = await whatsappApi.getMe();
                setUser(profile);
                setRole(profile.role);
                setPermissions(profile.permissions || []);
                localStorage.setItem('role', profile.role);
            } catch (error) {
                console.error('Failed to refresh session:', error);
            }
        }
    };

    useEffect(() => {
        const initializeAuth = async () => {
            const token = localStorage.getItem('token');
            if (token) {
                try {
                    // Fetch fresh profile and permissions on load
                    await refreshAuth();
                    setIsAuthenticated(true);
                } catch (error) {
                    console.error('Failed to restore session:', error);
                    logout();
                }
            } else {
                logout();
            }
            setIsLoading(false);
        };

        initializeAuth();
    }, []);

    const login = (token: string, newRole: string, newPermissions: string[], userData: any = null) => {
        localStorage.setItem('token', token);
        localStorage.setItem('role', newRole);
        setIsAuthenticated(true);
        setRole(newRole);
        setPermissions(newPermissions);
        setUser(userData);
    };

    const logout = () => {
        localStorage.removeItem('token');
        localStorage.removeItem('role');
        setIsAuthenticated(false);
        setRole(null);
        setPermissions([]);
        setUser(null);
    };

    const hasPermission = (slug: string) => {
        // Evaluate permissions strictly based on assigned roles from the database
        return permissions.includes(slug);
    };

    return (
        <AuthContext.Provider value={{ isAuthenticated, user, role, permissions, isLoading, login, logout, hasPermission, refreshAuth }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};
