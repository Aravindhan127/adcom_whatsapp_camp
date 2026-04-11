/**
 * WebSocket Service for Adcom Standalone
 * Handles real-time updates for Chat, Notifications, and Campaign Progress.
 */

type MessageHandler = (data: any) => void;

class WebSocketService {
    private socket: WebSocket | null = null;
    private handlers: Map<string, Set<MessageHandler>> = new Map();
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 5;
    private reconnectInterval = 3000;
    private baseUrl: string;

    constructor() {
        // Derive WS URL from the backend API URL
        const apiBase = import.meta.env.VITE_API_BACKEND_URL_WHATSAPP || 'http://localhost:8000';
        this.baseUrl = apiBase.replace(/^http/, 'ws') + '/api/ws/chat';
    }

    /**
     * Connect to the WebSocket server
     */
    connect() {
        if (this.socket?.readyState === WebSocket.OPEN) return;

        console.log(`Connecting to WebSocket: ${this.baseUrl}`);
        this.socket = new WebSocket(this.baseUrl);

        this.socket.onopen = () => {
            console.log('WebSocket connected successfully');
            this.reconnectAttempts = 0;
            this.emit('connection_status', { connected: true });
        };

        this.socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type) {
                    this.emit(data.type, data);
                }
                // Also emit as generic message
                this.emit('message', data);
            } catch (err) {
                console.error('Error parsing WebSocket message:', err);
            }
        };

        this.socket.onclose = (event) => {
            console.log('WebSocket connection closed:', event.reason);
            this.emit('connection_status', { connected: false });
            this.attemptReconnect();
        };

        this.socket.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    /**
     * Attempt to reconnect with exponential backoff
     */
    private attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Attempting reconnect ${this.reconnectAttempts}/${this.maxReconnectAttempts} in ${this.reconnectInterval}ms...`);
            setTimeout(() => this.connect(), this.reconnectInterval);
        } else {
            console.error('Max reconnection attempts reached');
        }
    }

    /**
     * Subscribe to a specific message type
     */
    subscribe(type: string, handler: MessageHandler) {
        if (!this.handlers.has(type)) {
            this.handlers.set(type, new Set());
        }
        this.handlers.get(type)?.add(handler);

        // Auto-connect if not already
        if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
            this.connect();
        }

        // Return unsubscribe function
        return () => this.unsubscribe(type, handler);
    }

    /**
     * Unsubscribe from a specific message type
     */
    unsubscribe(type: string, handler: MessageHandler) {
        this.handlers.get(type)?.delete(handler);
    }

    /**
     * Internal emitter
     */
    private emit(type: string, data: any) {
        this.handlers.get(type)?.forEach(handler => handler(data));
    }

    /**
     * Close connection manually
     */
    disconnect() {
        if (this.socket) {
            this.socket.close();
        }
    }
}

export const wsService = new WebSocketService();
    
