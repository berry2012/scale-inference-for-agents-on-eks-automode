// SummitAssistant Chat UI Application

class ChatApp {
    constructor() {
        this.apiUrl = this.getApiUrl();
        this.messages = [];
        this.isTyping = false;
        
        this.initElements();
        this.attachEventListeners();
        this.checkConnection();
    }

    getApiUrl() {
        // Use relative path /api/ which nginx will proxy to SummitAssistant service
        const hostname = window.location.hostname;
        if (hostname === 'localhost' || hostname === '127.0.0.1') {
            // For local development, connect directly to SummitAssistant
            return 'http://localhost:8080';
        }
        // For production, use the /api/ path that nginx proxies
        return '/api';
    }

    initElements() {
        this.messagesContainer = document.getElementById('messages');
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.typingIndicator = document.getElementById('typingIndicator');
        this.statusIndicator = document.getElementById('statusIndicator');
        this.statusText = document.getElementById('statusText');
        this.charCount = document.getElementById('charCount');
    }

    attachEventListeners() {
        // Send button click
        this.sendButton.addEventListener('click', () => this.sendMessage());

        // Enter key to send (Shift+Enter for new line)
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Auto-resize textarea
        this.messageInput.addEventListener('input', () => {
            this.autoResizeTextarea();
            this.updateCharCount();
            this.updateSendButton();
        });

        // Quick actions
        document.querySelectorAll('.quick-action').forEach(button => {
            button.addEventListener('click', (e) => {
                const action = e.target.dataset.action;
                this.handleQuickAction(action);
            });
        });
    }

    autoResizeTextarea() {
        this.messageInput.style.height = 'auto';
        this.messageInput.style.height = this.messageInput.scrollHeight + 'px';
    }

    updateCharCount() {
        const count = this.messageInput.value.length;
        this.charCount.textContent = `${count} / 2000`;
    }

    updateSendButton() {
        const hasText = this.messageInput.value.trim().length > 0;
        this.sendButton.disabled = !hasText || this.isTyping;
    }

    async checkConnection() {
        try {
            const response = await fetch(`${this.apiUrl}/health`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });

            if (response.ok) {
                this.setStatus('connected', 'Connected');
            } else {
                this.setStatus('error', 'Connection Error');
            }
        } catch (error) {
            console.error('Connection check failed:', error);
            this.setStatus('error', 'Disconnected');
            this.showErrorMessage('Unable to connect to SummitAssistant. Please check if the server is running.');
        }
    }

    setStatus(status, text) {
        this.statusIndicator.className = `status-indicator ${status}`;
        this.statusText.textContent = text;
    }

    async sendMessage() {
        const text = this.messageInput.value.trim();
        if (!text || this.isTyping) return;

        // Add user message to UI
        this.addMessage('user', text);

        // Clear input
        this.messageInput.value = '';
        this.autoResizeTextarea();
        this.updateCharCount();
        this.updateSendButton();

        // Show typing indicator
        this.showTyping();

        try {
            // Send to API
            const response = await fetch(`${this.apiUrl}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text })
            });

            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }

            const data = await response.json();
            
            // Hide typing indicator
            this.hideTyping();

            // Add assistant response
            this.addMessage('assistant', data.response || 'I apologize, but I encountered an error processing your request.');

        } catch (error) {
            console.error('Send message error:', error);
            this.hideTyping();
            this.addMessage('assistant', 'I apologize, but I\'m having trouble connecting to the server. Please try again later.');
        }
    }

    addMessage(role, text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;

        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'message-avatar';
        avatarDiv.innerHTML = this.getAvatarIcon(role);

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';

        const textDiv = document.createElement('div');
        textDiv.className = 'message-text';
        
        // Convert markdown-like formatting to HTML
        textDiv.innerHTML = this.formatMessage(text);

        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = new Date().toLocaleTimeString();

        contentDiv.appendChild(textDiv);
        contentDiv.appendChild(timeDiv);

        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(contentDiv);

        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();

        this.messages.push({ role, text, timestamp: new Date() });
    }

    formatMessage(text) {
        // Simple markdown-like formatting
        let formatted = text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\n/g, '<br>');

        // Convert bullet points
        if (formatted.includes('- ')) {
            const lines = formatted.split('<br>');
            let inList = false;
            formatted = lines.map(line => {
                if (line.trim().startsWith('- ')) {
                    if (!inList) {
                        inList = true;
                        return '<ul><li>' + line.trim().substring(2) + '</li>';
                    }
                    return '<li>' + line.trim().substring(2) + '</li>';
                } else if (inList && line.trim()) {
                    inList = false;
                    return '</ul>' + line;
                } else if (inList && !line.trim()) {
                    return '';
                }
                return line;
            }).join('');
            if (inList) formatted += '</ul>';
        }

        return formatted;
    }

    getAvatarIcon(role) {
        if (role === 'user') {
            return `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                    <circle cx="12" cy="7" r="4"></circle>
                </svg>
            `;
        }
        return `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <circle cx="12" cy="12" r="10"></circle>
                <path d="M8 14s1.5 2 4 2 4-2 4-2"></path>
                <line x1="9" y1="9" x2="9.01" y2="9"></line>
                <line x1="15" y1="9" x2="15.01" y2="9"></line>
            </svg>
        `;
    }

    showTyping() {
        this.isTyping = true;
        this.typingIndicator.style.display = 'flex';
        this.updateSendButton();
        this.scrollToBottom();
    }

    hideTyping() {
        this.isTyping = false;
        this.typingIndicator.style.display = 'none';
        this.updateSendButton();
    }

    scrollToBottom() {
        setTimeout(() => {
            this.messagesContainer.parentElement.scrollTop = 
                this.messagesContainer.parentElement.scrollHeight;
        }, 100);
    }

    handleQuickAction(action) {
        const templates = {
            schedule: 'Schedule a meeting for tomorrow at 2 PM with alice@example.com and bob@example.com. The meeting is about Q1 planning.',
            summarize: 'Please summarize the following meeting notes: [paste your meeting notes here]',
            search: 'Show me all meetings from the past week with alice@example.com'
        };

        if (templates[action]) {
            this.messageInput.value = templates[action];
            this.autoResizeTextarea();
            this.updateCharCount();
            this.updateSendButton();
            this.messageInput.focus();
        }
    }

    showErrorMessage(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.textContent = message;
        
        this.messagesContainer.appendChild(errorDiv);
        this.scrollToBottom();

        setTimeout(() => {
            errorDiv.remove();
        }, 5000);
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new ChatApp();
});
