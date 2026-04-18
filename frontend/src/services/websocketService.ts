/**
 * WebSocket Service for Adcom Standalone
 * Handles real-time updates for Chat, Notifications, and Campaign Progress.
 *
 * FE-FIX FE-3: Implemented true exponential backoff with jitter.
 *              Never gives up permanently — resets after successful reconnect.
 */

type MessageHandler = (data: any) => void;

class WebSocketService {
    private socket: WebSocket | null = null;
    private handlers: Map<string, Set<MessageHandler>> = new Map();
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 10;        // FE-FIX FE-3: increased from 5
    private baseReconnectDelay = 1000;        // Start at 1 second
    private maxReconnectDelay = 30000;        // Cap at 30 seconds
    private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    private baseUrl: string;
    private isConnecting = false;             // Prevent duplicate connect calls

    constructor() {
        const apiBase = (import.meta.env.VITE_API_BACKEND_URL_WHATSAPP || 'http://localhost:8000').replace(/\/$/, '');
        this.baseUrl = apiBase.replace(/^http/, 'ws') + '/api/ws/chat';
    }

    connect() {
        // Prevent multiple simultaneous connection attempts
        if (this.isConnecting) return;
        if (this.socket?.readyState === WebSocket.OPEN) return;
        if (this.socket?.readyState === WebSocket.CONNECTING) return;

        this.isConnecting = true;
        console.log(`[WS] Connecting to: ${this.baseUrl} (attempt ${this.reconnectAttempts + 1})`);
        this.socket = new WebSocket(this.baseUrl);

        this.socket.onopen = () => {
            console.log('[WS] Connected successfully.');
            this.isConnecting = false;
            this.reconnectAttempts = 0; // FE-FIX FE-3: reset on success
            if (this.reconnectTimer) {
                clearTimeout(this.reconnectTimer);
                this.reconnectTimer = null;
            }
            this.emit('connection_status', { connected: true });
        };

        this.socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type) {
                    this.emit(data.type, data);
                }
                this.emit('message', data);
            } catch (err) {
                console.error('[WS] Error parsing message:', err);
            }
        };

        this.socket.onclose = (event) => {
            console.log(`[WS] Connection closed. Code=${event.code} Reason="${event.reason}"`);
            this.isConnecting = false;
            this.emit('connection_status', { connected: false });
            this.scheduleReconnect();
        };

        this.socket.onerror = () => {
            // onclose fires after onerror, so reconnect is handled there
            this.isConnecting = false;
            console.warn('[WS] WebSocket error occurred.');
        };
    }

    /**
     * FE-FIX FE-3: True exponential backoff with jitter. Never gives up.
     * Delay = min(base * 2^attempt, maxDelay) + random jitter (0–1s)
     */
    private scheduleReconnect() {
        if (this.reconnectTimer) return; // Already scheduled

        const delay = Math.min(
            this.baseReconnectDelay * Math.pow(2, this.reconnectAttempts),
            this.maxReconnectDelay
        ) + Math.random() * 1000; // Add jitter to prevent stampede

        this.reconnectAttempts = Math.min(this.reconnectAttempts + 1, this.maxReconnectAttempts);
        console.log(`[WS] Reconnecting in ${Math.round(delay / 1000)}s (attempt ${this.reconnectAttempts})...`);

        this.reconnectTimer = setTimeout(() => {
            this.reconnectTimer = null;
            this.connect();
        }, delay);
    }

    subscribe(type: string, handler: MessageHandler) {
        if (!this.handlers.has(type)) {
            this.handlers.set(type, new Set());
        }
        this.handlers.get(type)?.add(handler);

        // Auto-connect if not already connected
        if (!this.socket || this.socket.readyState === WebSocket.CLOSED) {
            this.connect();
        }

        return () => this.unsubscribe(type, handler);
    }

    unsubscribe(type: string, handler: MessageHandler) {
        this.handlers.get(type)?.delete(handler);
    }

    private emit(type: string, data: any) {
        this.handlers.get(type)?.forEach(handler => {
            try {
                handler(data);
            } catch (err) {
                console.error(`[WS] Handler error for type '${type}':`, err);
            }
        });
    }

    disconnect() {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
    }
}

export const wsService = new WebSocketService();
