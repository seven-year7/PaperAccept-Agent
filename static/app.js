// SuperBizAgent 前端应用
const RAG_TENANT_STORAGE_KEY = 'ragTenantId';
const RAG_DOMAIN_EXPLICIT_KEY = 'ragDomainExplicitSelected';
const RAG_UPLOAD_MAX_BYTES = 10 * 1024 * 1024; // 与后端 /api/upload 一致

class SuperBizAgentApp {
    constructor() {
        // 与页面同源；勿用 file:// 直接打开 HTML（应访问 http://host:port/）
        let apiOrigin = 'http://localhost:9900';
        try {
            if (window.location && window.location.protocol !== 'file:' && window.location.origin) {
                apiOrigin = window.location.origin;
            }
        } catch (_) { /* ignore */ }
        this.apiBaseUrl = `${apiOrigin}/api`;
        this.sessionId = this.generateSessionId();
        this.isStreaming = false;
        this.currentChatHistory = []; // 当前对话的消息历史
        this.chatHistories = this.loadChatHistories(); // 所有历史对话
        this.isCurrentChatFromHistory = false; // 标记当前对话是否是从历史记录加载的
        
        this.initializeElements();
        this.bindEvents();
        this.updateDomainChip();
        this.updateUI();
        this.initMarkdown();
        this.checkAndSetCentered();
        this.renderChatHistory();
    }

    // 初始化Markdown配置
    initMarkdown() {
        // 等待 marked 库加载完成
        const checkMarked = () => {
            if (typeof marked !== 'undefined') {
                try {
                    // 配置marked选项
                    marked.setOptions({
                        breaks: true,  // 支持GFM换行
                        gfm: true,     // 启用GitHub风格的Markdown
                        headerIds: false,
                        mangle: false
                    });

                    // 配置代码高亮
                    if (typeof hljs !== 'undefined') {
                        marked.setOptions({
                            highlight: function(code, lang) {
                                if (lang && hljs.getLanguage(lang)) {
                                    try {
                                        return hljs.highlight(code, { language: lang }).value;
                                    } catch (err) {
                                        console.error('代码高亮失败:', err);
                                    }
                                }
                                return code;
                            }
                        });
                    }
                    console.log('Markdown 渲染库初始化成功');
                } catch (e) {
                    console.error('Markdown 配置失败:', e);
                }
            } else {
                // 如果 marked 还没加载，等待一段时间后重试
                setTimeout(checkMarked, 100);
            }
        };
        checkMarked();
    }

    // 安全地渲染 Markdown
    renderMarkdown(content) {
        if (!content) return '';
        
        // 检查 marked 是否可用
        if (typeof marked === 'undefined') {
            console.warn('marked 库未加载，使用纯文本显示');
            return this.escapeHtml(content);
        }
        
        try {
            const html = marked.parse(content);
            return html;
        } catch (e) {
            console.error('Markdown 渲染失败:', e);
            return this.escapeHtml(content);
        }
    }

    // 高亮代码块
    highlightCodeBlocks(container) {
        if (typeof hljs !== 'undefined' && container) {
            try {
                container.querySelectorAll('pre code').forEach((block) => {
                    if (!block.classList.contains('hljs')) {
                        hljs.highlightElement(block);
                    }
                });
            } catch (e) {
                console.error('代码高亮失败:', e);
            }
        }
    }

    // 初始化DOM元素
    initializeElements() {
        // 侧边栏元素
        this.sidebar = document.querySelector('.sidebar');
        this.newChatBtn = document.getElementById('newChatBtn');
        
        // 输入区域元素
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.toolsBtn = document.getElementById('toolsBtn');
        this.toolsMenu = document.getElementById('toolsMenu');
        this.selectDomainItem = document.getElementById('selectDomainItem');
        this.uploadFileItem = document.getElementById('uploadFileItem');
        this.uploadPdfItem = document.getElementById('uploadPdfItem');
        this.fileInput = document.getElementById('fileInput');
        this.pdfFileInput = document.getElementById('pdfFileInput');
        this.domainModal = document.getElementById('domainModal');
        this.domainModalBackdrop = document.getElementById('domainModalBackdrop');
        this.domainModalCancel = document.getElementById('domainModalCancel');
        this.domainModalConfirm = document.getElementById('domainModalConfirm');
        this.domainPresetSelect = document.getElementById('domainPresetSelect');
        this.domainCustomInput = document.getElementById('domainCustomInput');
        this.domainChip = document.getElementById('domainChip');
        this.domainChipLabel = document.getElementById('domainChipLabel');
        
        // 聊天区域元素
        this.chatMessages = document.getElementById('chatMessages');
        this.loadingOverlay = document.getElementById('loadingOverlay');
        this.chatContainer = document.querySelector('.chat-container');
        this.welcomeGreeting = document.getElementById('welcomeGreeting');
        this.chatHistoryList = document.getElementById('chatHistoryList');
        
        // 初始化时检查是否需要居中
        this.checkAndSetCentered();
    }

    // 绑定事件监听器
    bindEvents() {
        // 新建对话
        if (this.newChatBtn) {
            this.newChatBtn.addEventListener('click', () => this.newChat());
        }
        
        // 发送消息
        if (this.sendButton) {
            this.sendButton.addEventListener('click', () => this.sendMessage());
        }
        
        if (this.messageInput) {
            this.messageInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });
        }
        
        // 工具按钮和菜单
        if (this.toolsBtn) {
            this.toolsBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleToolsMenu();
            });
        }
        
        // 工具菜单项点击事件
        if (this.selectDomainItem) {
            this.selectDomainItem.addEventListener('click', () => {
                this.openDomainModal();
                this.closeToolsMenu();
            });
        }

        if (this.uploadFileItem) {
            this.uploadFileItem.addEventListener('click', () => {
                if (this.fileInput) {
                    this.fileInput.click();
                }
                this.closeToolsMenu();
            });
        }
        if (this.uploadPdfItem) {
            this.uploadPdfItem.addEventListener('click', () => {
                if (this.pdfFileInput) {
                    this.pdfFileInput.click();
                }
                this.closeToolsMenu();
            });
        }

        if (this.domainModalConfirm) {
            this.domainModalConfirm.addEventListener('click', () => this.saveDomainFromModal());
        }
        if (this.domainModalCancel) {
            this.domainModalCancel.addEventListener('click', () => this.closeDomainModal());
        }
        if (this.domainModalBackdrop) {
            this.domainModalBackdrop.addEventListener('click', () => this.closeDomainModal());
        }
        
        // 点击外部关闭工具菜单
        document.addEventListener('click', (e) => {
            if (this.toolsBtn && this.toolsMenu && 
                !this.toolsBtn.contains(e.target) && 
                !this.toolsMenu.contains(e.target)) {
                this.closeToolsMenu();
            }
        });
        
        if (this.fileInput) {
            this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e, 'text'));
        }
        if (this.pdfFileInput) {
            this.pdfFileInput.addEventListener('change', (e) => this.handleFileSelect(e, 'pdf'));
        }
    }

    /**
     * RAG 领域（原 tenant_id）：与 ChatRequest.TenantId、上传 tenant_id、论文 TenantId 对齐。
     */
    getRagTenantId() {
        try {
            const raw = localStorage.getItem(RAG_TENANT_STORAGE_KEY);
            if (raw != null && String(raw).trim() !== '') {
                return String(raw).trim();
            }
        } catch (_) { /* ignore */ }
        return 'default';
    }

    isRagDomainExplicit() {
        try {
            return localStorage.getItem(RAG_DOMAIN_EXPLICIT_KEY) === '1';
        } catch (_) {
            return false;
        }
    }

    setRagDomainExplicitFlag() {
        try {
            localStorage.setItem(RAG_DOMAIN_EXPLICIT_KEY, '1');
        } catch (_) { /* ignore */ }
    }

    openDomainModal() {
        if (!this.domainModal) return;
        if (this.domainPresetSelect) this.domainPresetSelect.value = '';
        if (this.domainCustomInput) this.domainCustomInput.value = '';
        this.domainModal.classList.add('is-open');
        this.domainModal.setAttribute('aria-hidden', 'false');
    }

    closeDomainModal() {
        if (!this.domainModal) return;
        this.domainModal.classList.remove('is-open');
        this.domainModal.setAttribute('aria-hidden', 'true');
    }

    normalizeDomainSlug(text) {
        return String(text || '')
            .trim()
            .replace(/\s+/g, '_')
            .slice(0, 128);
    }

    saveDomainFromModal() {
        const preset = this.domainPresetSelect ? String(this.domainPresetSelect.value || '').trim() : '';
        const customRaw = this.domainCustomInput ? String(this.domainCustomInput.value || '').trim() : '';
        let slug = customRaw ? this.normalizeDomainSlug(customRaw) : preset;
        if (!slug) {
            this.showNotification('请选择预设或填写自定义领域', 'warning');
            return;
        }
        if (!/^[a-zA-Z0-9_-]+$/.test(slug)) {
            this.showNotification('领域仅允许字母、数字、下划线、连字符', 'error');
            return;
        }
        try {
            localStorage.setItem(RAG_TENANT_STORAGE_KEY, slug);
        } catch (e) {
            this.showNotification('无法保存领域（localStorage）', 'error');
            return;
        }
        this.setRagDomainExplicitFlag();
        this.updateDomainChip();
        this.closeDomainModal();
        this.showNotification(`已选择领域：${slug}（对话与上传将使用该领域）`, 'success');
    }

    updateDomainChip() {
        if (!this.domainChip || !this.domainChipLabel) return;
        const explicit = this.isRagDomainExplicit();
        const tid = this.getRagTenantId();
        if (explicit && tid && tid !== 'default') {
            this.domainChipLabel.textContent = `领域：${tid}`;
            this.domainChip.classList.add('domain-chip--ok');
        } else {
            this.domainChipLabel.textContent = '领域：未选择';
            this.domainChip.classList.remove('domain-chip--ok');
        }
    }

    async parseHttpError(response) {
        let msg = `HTTP ${response.status}`;
        try {
            const body = await response.json();
            if (body && body.detail !== undefined) {
                msg = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
            } else if (body && body.message) {
                msg = body.message;
            }
        } catch (_) { /* ignore */ }
        return msg;
    }

    /**
     * 论文工作流：在助手消息下挂载「确认检索 / 取消」，调用 POST /api/paper/confirm_search（与 SSE search_confirm 配套）。
     */
    _mountPaperSearchConfirm(assistantMessageElement, runId) {
        if (!assistantMessageElement || !runId) return;
        const wrapper = assistantMessageElement.querySelector('.message-content-wrapper');
        if (!wrapper) return;
        let panel = wrapper.querySelector('.paper-search-confirm-panel');
        if (panel && panel.dataset.paperRunId === runId) return;
        if (panel) panel.remove();

        panel = document.createElement('div');
        panel.className = 'paper-search-confirm-panel';
        panel.dataset.paperRunId = runId;

        const hint = document.createElement('p');
        hint.className = 'paper-confirm-hint';
        hint.textContent = '请确认是否按上述条件检索 arXiv（将调用确认接口，流程会继续）。';

        const rid = document.createElement('p');
        rid.className = 'paper-run-id';
        rid.textContent = `RunId（须原样提交）：${runId}`;

        const btnRow = document.createElement('div');
        btnRow.className = 'paper-confirm-buttons';

        const approveBtn = document.createElement('button');
        approveBtn.type = 'button';
        approveBtn.className = 'paper-confirm-btn paper-confirm-approve';
        approveBtn.textContent = '确认检索';

        const rejectBtn = document.createElement('button');
        rejectBtn.type = 'button';
        rejectBtn.className = 'paper-confirm-btn paper-confirm-reject';
        rejectBtn.textContent = '取消';

        approveBtn.addEventListener('click', () => {
            this._submitPaperSearchConfirm(runId, true, panel, approveBtn, rejectBtn);
        });
        rejectBtn.addEventListener('click', () => {
            const reason = window.prompt('取消原因（可选，将传给 Reason）', '') || '';
            this._submitPaperSearchConfirm(runId, false, panel, approveBtn, rejectBtn, reason);
        });

        btnRow.appendChild(approveBtn);
        btnRow.appendChild(rejectBtn);
        panel.appendChild(hint);
        panel.appendChild(rid);
        panel.appendChild(btnRow);
        assistantMessageElement.classList.add('message-paper-confirm-active');
        wrapper.appendChild(panel);
        this.scrollToBottom();
        requestAnimationFrame(() => {
            try {
                panel.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
            } catch (_) {
                panel.scrollIntoView({ block: 'nearest' });
            }
        });
    }

    async _submitPaperSearchConfirm(runId, approved, panel, approveBtn, rejectBtn, reason = '') {
        approveBtn.disabled = true;
        rejectBtn.disabled = true;
        try {
            const body = { RunId: runId, Approved: approved };
            if (!approved && reason.trim()) body.Reason = reason.trim();
            const r = await fetch(`${this.apiBaseUrl}/paper/confirm_search`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            if (!r.ok) {
                const errText = await this.parseHttpError(r);
                throw new Error(errText);
            }
            const msgEl = panel.closest('.message');
            if (msgEl) {
                msgEl.classList.remove('message-paper-confirm-active');
            }
            panel.remove();
            this.showNotification(
                approved ? '已确认，正在继续检索…' : '已取消本次检索。',
                approved ? 'success' : 'info'
            );
        } catch (e) {
            console.error('[PaperConfirm]', e);
            const errEl = document.createElement('p');
            errEl.className = 'paper-confirm-status paper-confirm-error';
            errEl.textContent = `提交失败：${e.message || e}`;
            panel.appendChild(errEl);
            approveBtn.disabled = false;
            rejectBtn.disabled = false;
        }
    }

    // 切换工具菜单显示/隐藏
    toggleToolsMenu() {
        if (this.toolsMenu && this.toolsBtn) {
            const wrapper = this.toolsBtn.closest('.tools-btn-wrapper');
            if (wrapper) {
                wrapper.classList.toggle('active');
            }
        }
    }

    // 关闭工具菜单
    closeToolsMenu() {
        if (this.toolsMenu && this.toolsBtn) {
            const wrapper = this.toolsBtn.closest('.tools-btn-wrapper');
            if (wrapper) {
                wrapper.classList.remove('active');
            }
        }
    }

    // 新建对话
    newChat() {
        if (this.isStreaming) {
            this.showNotification('请等待当前对话完成后再新建对话', 'warning');
            return;
        }
        
        // 如果当前有对话内容，且不是从历史记录加载的，才保存为新的历史对话
        // 如果是从历史记录加载的，只需要更新该历史记录
        if (this.currentChatHistory.length > 0) {
            if (this.isCurrentChatFromHistory) {
                // 当前对话是从历史记录加载的，更新该历史记录
                this.updateCurrentChatHistory();
            } else {
                // 当前对话是新对话，保存为新的历史对话
                this.saveCurrentChat();
            }
        }
        
        // 停止所有进行中的操作
        this.isStreaming = false;
        
        // 清空输入框
        if (this.messageInput) {
            this.messageInput.value = '';
        }
        
        // 清空当前对话历史
        this.currentChatHistory = [];
        
        // 重置标记
        this.isCurrentChatFromHistory = false;
        
        // 清空聊天记录
        if (this.chatMessages) {
            this.chatMessages.innerHTML = '';
        }
        
        // 生成新的会话ID
        this.sessionId = this.generateSessionId();
        
        this.updateUI();
        
        // 重新设置居中样式（确保对话框居中显示）
        this.checkAndSetCentered();
        
        // 确保容器有过渡动画
        if (this.chatContainer) {
            this.chatContainer.style.transition = 'all 0.5s ease';
        }
        
        // 更新历史对话列表
        this.renderChatHistory();
    }
    
    // 保存当前对话到历史记录（新建）
    saveCurrentChat() {
        if (this.currentChatHistory.length === 0) {
            return;
        }
        
        // 检查是否已存在相同ID的历史记录
        const existingIndex = this.chatHistories.findIndex(h => h.id === this.sessionId);
        if (existingIndex !== -1) {
            // 如果已存在，更新而不是新建
            this.updateCurrentChatHistory();
            return;
        }
        
        // 获取对话标题（使用第一条用户消息的前30个字符）
        const firstUserMessage = this.currentChatHistory.find(msg => msg.type === 'user');
        const title = firstUserMessage ? 
            (firstUserMessage.content.substring(0, 30) + (firstUserMessage.content.length > 30 ? '...' : '')) : 
            '新对话';
        
        const chatHistory = {
            id: this.sessionId,
            title: title,
            messages: [...this.currentChatHistory],
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
        };
        
        // 添加到历史记录列表的开头
        this.chatHistories.unshift(chatHistory);
        
        // 限制历史记录数量（最多保存50条）
        if (this.chatHistories.length > 50) {
            this.chatHistories = this.chatHistories.slice(0, 50);
        }
        
        // 保存到localStorage
        this.saveChatHistories();
    }
    
    // 更新当前对话的历史记录
    updateCurrentChatHistory() {
        if (this.currentChatHistory.length === 0) {
            return;
        }
        
        const existingIndex = this.chatHistories.findIndex(h => h.id === this.sessionId);
        if (existingIndex === -1) {
            // 如果不存在，调用保存方法
            this.saveCurrentChat();
            return;
        }
        
        // 更新现有的历史记录
        const history = this.chatHistories[existingIndex];
        history.messages = [...this.currentChatHistory];
        history.updatedAt = new Date().toISOString();
        
        // 如果标题需要更新（第一条消息改变了）
        const firstUserMessage = this.currentChatHistory.find(msg => msg.type === 'user');
        if (firstUserMessage) {
            const newTitle = firstUserMessage.content.substring(0, 30) + (firstUserMessage.content.length > 30 ? '...' : '');
            if (history.title !== newTitle) {
                history.title = newTitle;
            }
        }
        
        // 保存到localStorage
        this.saveChatHistories();
    }
    
    // 加载历史对话列表
    loadChatHistories() {
        try {
            const stored = localStorage.getItem('chatHistories');
            return stored ? JSON.parse(stored) : [];
        } catch (e) {
            console.error('加载历史对话失败:', e);
            return [];
        }
    }
    
    // 保存历史对话列表到localStorage
    saveChatHistories() {
        try {
            localStorage.setItem('chatHistories', JSON.stringify(this.chatHistories));
        } catch (e) {
            console.error('保存历史对话失败:', e);
        }
    }
    
    // 渲染历史对话列表
    renderChatHistory() {
        if (!this.chatHistoryList) {
            return;
        }
        
        this.chatHistoryList.innerHTML = '';
        
        if (this.chatHistories.length === 0) {
            return;
        }
        
        this.chatHistories.forEach((history, index) => {
            const historyItem = document.createElement('div');
            historyItem.className = 'history-item';
            historyItem.dataset.historyId = history.id;
            
            historyItem.innerHTML = `
                <div class="history-item-content">
                    <span class="history-item-title">${this.escapeHtml(history.title)}</span>
                </div>
                <button class="history-item-delete" data-history-id="${history.id}" title="删除">
                    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                    </svg>
                </button>
            `;
            
            // 点击历史项加载对话
            historyItem.addEventListener('click', (e) => {
                if (!e.target.closest('.history-item-delete')) {
                    this.loadChatHistory(history.id);
                }
            });
            
            // 删除历史对话
            const deleteBtn = historyItem.querySelector('.history-item-delete');
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.deleteChatHistory(history.id);
            });
            
            this.chatHistoryList.appendChild(historyItem);
        });
    }
    
    // 加载历史对话
    async loadChatHistory(historyId) {
        const history = this.chatHistories.find(h => h.id === historyId);
        if (!history) {
            return;
        }
        
        // 如果当前有对话内容，且不是同一个对话，先保存
        if (this.currentChatHistory.length > 0 && this.sessionId !== historyId) {
            if (this.isCurrentChatFromHistory) {
                // 如果当前对话也是从历史记录加载的，更新它
                this.updateCurrentChatHistory();
            } else {
                // 如果当前对话是新对话，保存为新历史
                this.saveCurrentChat();
            }
        }
        
        try {
            // 从后端获取会话历史
            const response = await fetch(`/api/chat/session/${historyId}`);
            if (response.ok) {
                const data = await response.json();
                const backendHistory = data.history || [];
                
                // 更新会话ID
                this.sessionId = history.id;
                this.isCurrentChatFromHistory = true;
                
                // 清空并重新渲染消息
                if (this.chatMessages) {
                    this.chatMessages.innerHTML = '';
                    
                    // 如果后端有历史记录，使用后端的（Redis history_jsonl：role + content）
                    if (backendHistory.length > 0) {
                        this.currentChatHistory = backendHistory.map((msg) => ({
                            type: this._normalizeChatMessageType(msg.role ?? msg.type),
                            content: msg.content != null ? String(msg.content) : '',
                            timestamp:
                                msg.timestamp != null && String(msg.timestamp) !== ''
                                    ? String(msg.timestamp)
                                    : new Date().toISOString(),
                        }));
                        this.currentChatHistory.forEach((msg) => {
                            this.addMessage(msg.type, msg.content, false, false);
                        });
                    } else {
                        // 否则使用 localStorage（可能含旧字段 role / 大小写 type）
                        this.currentChatHistory = (history.messages || []).map((msg) => ({
                            type: this._normalizeChatMessageType(msg.type ?? msg.role),
                            content: msg.content != null ? String(msg.content) : '',
                            timestamp:
                                msg.timestamp != null && String(msg.timestamp) !== ''
                                    ? String(msg.timestamp)
                                    : new Date().toISOString(),
                        }));
                        this.currentChatHistory.forEach((msg) => {
                            this.addMessage(msg.type, msg.content, false, false);
                        });
                    }
                }
            } else {
                // 如果后端请求失败，使用localStorage的历史记录
                console.warn('从后端加载历史失败，使用本地缓存');
                this.sessionId = history.id;
                this.isCurrentChatFromHistory = true;
                
                if (this.chatMessages) {
                    this.chatMessages.innerHTML = '';
                    this.currentChatHistory = (history.messages || []).map((msg) => ({
                        type: this._normalizeChatMessageType(msg.type ?? msg.role),
                        content: msg.content != null ? String(msg.content) : '',
                        timestamp:
                            msg.timestamp != null && String(msg.timestamp) !== ''
                                ? String(msg.timestamp)
                                : new Date().toISOString(),
                    }));
                    this.currentChatHistory.forEach((msg) => {
                        this.addMessage(msg.type, msg.content, false, false);
                    });
                }
            }
        } catch (error) {
            console.error('加载会话历史失败:', error);
            // 出错时使用localStorage的历史记录
            this.sessionId = history.id;
            this.isCurrentChatFromHistory = true;
            
            if (this.chatMessages) {
                this.chatMessages.innerHTML = '';
                this.currentChatHistory = (history.messages || []).map((msg) => ({
                    type: this._normalizeChatMessageType(msg.type ?? msg.role),
                    content: msg.content != null ? String(msg.content) : '',
                    timestamp:
                        msg.timestamp != null && String(msg.timestamp) !== ''
                            ? String(msg.timestamp)
                            : new Date().toISOString(),
                }));
                this.currentChatHistory.forEach((msg) => {
                    this.addMessage(msg.type, msg.content, false, false);
                });
            }
        }
        
        // 更新UI
        this.checkAndSetCentered();
        this.renderChatHistory();
    }
    
    // 删除历史对话
    async deleteChatHistory(historyId) {
        try {
            // 调用后端API清空会话
            const response = await fetch('/api/chat/clear', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: historyId
                })
            });

            if (!response.ok) {
                throw new Error('清空会话失败');
            }

            const result = await response.json();
            
            if (result.status === 'success') {
                // 从本地存储中删除
                this.chatHistories = this.chatHistories.filter(h => h.id !== historyId);
                this.saveChatHistories();
                this.renderChatHistory();
                
                // 如果删除的是当前对话，清空当前对话
                if (this.sessionId === historyId) {
                    this.currentChatHistory = [];
                    if (this.chatMessages) {
                        this.chatMessages.innerHTML = '';
                    }
                    this.sessionId = this.generateSessionId();
                    this.checkAndSetCentered();
                }
                
                this.showNotification('会话已清空', 'success');
            } else {
                throw new Error(result.message || '清空会话失败');
            }
        } catch (error) {
            console.error('删除历史对话失败:', error);
            this.showNotification('删除失败: ' + error.message, 'error');
        }
    }

    // 更新UI
    updateUI() {
        // 更新发送按钮状态
        if (this.sendButton) {
            this.sendButton.disabled = this.isStreaming;
        }
        
        // 更新输入框状态
        if (this.messageInput) {
            this.messageInput.disabled = this.isStreaming;
            this.messageInput.placeholder = '向私人论文助手提问';
        }
        this.updateDomainChip();
    }

    // 生成随机会话ID
    generateSessionId() {
        return 'session_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
    }

    // 发送消息
    async sendMessage() {
        let message = '';
        if (this.messageInput) {
            message = this.messageInput.value.trim();
        }
        
        if (!message) {
            this.showNotification('请输入消息内容', 'warning');
            return;
        }

        if (!this.isRagDomainExplicit()) {
            this.showNotification('请先在工具菜单中选择知识领域', 'warning');
            return;
        }

        if (this.isStreaming) {
            this.showNotification('请等待当前对话完成', 'warning');
            return;
        }

        // 显示用户消息
        this.addMessage('user', message);
        
        // 清空输入框
        if (this.messageInput) {
            this.messageInput.value = '';
        }

        // 设置发送状态
        this.isStreaming = true;
        this.updateUI();

        try {
            await this.sendStreamMessage(message);
        } catch (error) {
            console.error('发送消息失败:', error);
            this.addMessage('assistant', '抱歉，发送消息时出现错误：' + error.message);
        } finally {
            this.isStreaming = false;
            this.updateUI();
            
            // 如果当前对话是从历史记录加载的，更新历史记录
            if (this.isCurrentChatFromHistory && this.currentChatHistory.length > 0) {
                this.updateCurrentChatHistory();
                this.renderChatHistory(); // 更新历史对话列表显示
            }
        }
    }

    // 发送流式消息（唯一对话路径：POST /api/chat_stream）
    async sendStreamMessage(message) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/chat_stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    Id: this.sessionId,
                    Question: message,
                    TenantId: this.getRagTenantId(),
                })
            });

            if (!response.ok) {
                throw new Error(await this.parseHttpError(response));
            }
            
            // 创建助手消息元素
            const assistantMessageElement = this.addMessage('assistant', '', true);
            let fullResponse = '';

            // 处理流式响应
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let currentEvent = '';

            try {
                while (true) {
                    const { done, value } = await reader.read();
                    
                    if (done) {
                        // 流结束，使用统一的处理方法
                        this.handleStreamComplete(assistantMessageElement, fullResponse);
                        break;
                    }

                    // 解码数据并添加到缓冲区
                    buffer += decoder.decode(value, { stream: true });
                    
                    // 按行分割处理
                    const lines = buffer.split('\n');
                    // 保留最后一行（可能不完整）
                    buffer = lines.pop() || '';
                    
                    for (const line of lines) {
                        if (line.trim() === '') continue;
                        
                        console.log('[SSE调试] 收到行:', line);
                        
                        // 解析SSE格式
                        if (line.startsWith('id:')) {
                            console.log('[SSE调试] 解析到ID');
                            continue;
                        } else if (line.startsWith('event:')) {
                            // 兼容 "event:message" 和 "event: message" 两种格式
                            currentEvent = line.substring(6).trim();
                            console.log('[SSE调试] 解析到事件类型:', currentEvent);
                            // 注意：后端统一使用 "message" 事件名，真正的类型在 data 的 JSON 中
                            continue;
                        } else if (line.startsWith('data:')) {
                            // 兼容 "data:xxx" 和 "data: xxx" 两种格式
                            const rawData = line.substring(5).trim();
                            console.log('[SSE调试] 解析到数据, currentEvent:', currentEvent, ', rawData:', rawData);
                            
                            // 兼容旧格式 [DONE] 标记
                            if (rawData === '[DONE]') {
                                // 流结束标记，将内容转换为Markdown渲染
                                this.handleStreamComplete(assistantMessageElement, fullResponse);
                                return;
                            }
                            
                            // 处理 SSE 数据
                            try {
                                // 尝试解析为 SseMessage 格式的 JSON
                                const sseMessage = JSON.parse(rawData);
                                console.log('[SSE调试] 解析JSON成功:', sseMessage);
                                
                                if (sseMessage && typeof sseMessage.type === 'string') {
                                    if (sseMessage.type === 'content') {
                                        const content = sseMessage.data || '';
                                        fullResponse += content;
                                        console.log('[SSE调试] 添加内容:', content);
                                        
                                        // 实时渲染 Markdown
                                        if (assistantMessageElement) {
                                            const messageContent = assistantMessageElement.querySelector('.message-content');
                                            messageContent.innerHTML = this.renderMarkdown(fullResponse);
                                            // 高亮代码块
                                            this.highlightCodeBlocks(messageContent);
                                            this.scrollToBottom();
                                        }
                                    } else if (sseMessage.type === 'search_confirm') {
                                        const d = sseMessage.data || {};
                                        const runId = d.run_id || '';
                                        console.log('[SSE调试] search_confirm run_id=', runId);
                                        this._mountPaperSearchConfirm(assistantMessageElement, runId);
                                    } else if (
                                        sseMessage.type === 'route' ||
                                        sseMessage.type === 'phase' ||
                                        sseMessage.type === 'reading_progress' ||
                                        sseMessage.type === 'writing'
                                    ) {
                                        // 论文工作流元事件，非助手 Markdown 正文
                                    } else if (sseMessage.type === 'done') {
                                        console.log('[SSE调试] 收到done标记，流结束');
                                        this.handleStreamComplete(assistantMessageElement, fullResponse);
                                        return;
                                    } else if (sseMessage.type === 'error') {
                                        console.error('[SSE调试] 收到错误:', sseMessage.data);
                                        const ed = sseMessage.data;
                                        const errStr =
                                            typeof ed === 'string'
                                                ? ed
                                                : ed && typeof ed.message === 'string'
                                                  ? ed.message
                                                  : JSON.stringify(ed || '未知错误');
                                        if (assistantMessageElement) {
                                            const messageContent = assistantMessageElement.querySelector('.message-content');
                                            messageContent.innerHTML = this.renderMarkdown('错误: ' + errStr);
                                        }
                                        return;
                                    }
                                } else {
                                    // 不是标准 SseMessage 格式，尝试兼容处理
                                    console.log('[SSE调试] 非标准格式，尝试兼容处理');
                                    fullResponse += rawData;
                                    if (assistantMessageElement) {
                                        const messageContent = assistantMessageElement.querySelector('.message-content');
                                        messageContent.innerHTML = this.renderMarkdown(fullResponse);
                                        this.highlightCodeBlocks(messageContent);
                                        this.scrollToBottom();
                                    }
                                }
                            } catch (e) {
                                // JSON 解析失败，尝试兼容旧格式
                                console.log('[SSE调试] JSON解析失败，使用兼容模式:', e.message);
                                if (rawData === '') {
                                    fullResponse += '\n';
                                } else {
                                    fullResponse += rawData;
                                }
                                
                                if (assistantMessageElement) {
                                    const messageContent = assistantMessageElement.querySelector('.message-content');
                                    messageContent.innerHTML = this.renderMarkdown(fullResponse);
                                    this.highlightCodeBlocks(messageContent);
                                    this.scrollToBottom();
                                }
                            }
                        }
                    }
                }
            } finally {
                reader.releaseLock();
            }
        } catch (error) {
            throw error;
        }
    }

    /**
     * 统一为 CSS 可用的 type：仅 `user` 与 `assistant`（小写）。
     * 历史/接口里可能出现 Assistant、BOT、旧版 bot、拼写变体等，不规范化则 `.message.assistant` 不命中、气泡丢失。
     */
    _normalizeChatMessageType(type) {
        const t = String(type ?? '').trim().toLowerCase();
        if (t === 'user' || t === 'human') {
            return 'user';
        }
        return 'assistant';
    }

    // 添加消息到聊天界面
    addMessage(type, content, isStreaming = false, saveToHistory = true) {
        const normalizedType = this._normalizeChatMessageType(type);
        const text = content == null ? '' : String(content);

        // 检查是否是第一条消息，如果是则移除居中样式
        const isFirstMessage = this.chatMessages && this.chatMessages.querySelectorAll('.message').length === 0;
        
        // 保存消息到当前对话历史（如果不是流式消息且需要保存）
        if (!isStreaming && saveToHistory && text) {
            this.currentChatHistory.push({
                type: normalizedType,
                content: text,
                timestamp: new Date().toISOString()
            });
        }
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${normalizedType}${isStreaming ? ' streaming' : ''}`;

        // 如果是 assistant 消息，添加头像图标
        if (normalizedType === 'assistant') {
            const messageAvatar = document.createElement('div');
            messageAvatar.className = 'message-avatar';
            messageAvatar.innerHTML = `
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" fill="white"/>
                </svg>
            `;
            messageDiv.appendChild(messageAvatar);
        }

        // 创建消息内容包装器
        const messageContentWrapper = document.createElement('div');
        messageContentWrapper.className = 'message-content-wrapper';

        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        // assistant 且非流式：Markdown；用户或流式中空占位：纯文本
        if (normalizedType === 'assistant' && !isStreaming) {
            messageContent.innerHTML = this.renderMarkdown(text);
            // 高亮代码块
            this.highlightCodeBlocks(messageContent);
        } else {
            messageContent.textContent = text;
        }

        messageContentWrapper.appendChild(messageContent);
        messageDiv.appendChild(messageContentWrapper);

        if (this.chatMessages) {
            this.chatMessages.appendChild(messageDiv);
            
            // 如果是第一条消息，移除居中样式并添加动画
            if (isFirstMessage && this.chatContainer) {
                this.chatContainer.classList.remove('centered');
                // 添加动画类
                this.chatContainer.style.transition = 'all 0.5s ease';
            }
            
            this.scrollToBottom();
        }

        return messageDiv;
    }

    // 添加带加载动画的消息
    addLoadingMessage(content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant';

        // 添加头像图标
        const messageAvatar = document.createElement('div');
        messageAvatar.className = 'message-avatar';
        messageAvatar.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" fill="white"/>
            </svg>
        `;
        messageDiv.appendChild(messageAvatar);

        // 创建消息内容包装器
        const messageContentWrapper = document.createElement('div');
        messageContentWrapper.className = 'message-content-wrapper';

        const messageContent = document.createElement('div');
        messageContent.className = 'message-content loading-message-content';
        
        // 创建文本和动画容器
        const textSpan = document.createElement('span');
        textSpan.textContent = content;
        
        // 创建旋转动画图标
        const loadingIcon = document.createElement('span');
        loadingIcon.className = 'loading-spinner-icon';
        loadingIcon.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z" fill="currentColor" opacity="0.2"/>
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10c1.54 0 3-.36 4.28-1l-1.5-2.6C13.64 19.62 12.84 20 12 20c-4.41 0-8-3.59-8-8s3.59-8 8-8c.84 0 1.64.38 2.18 1l1.5-2.6C13 2.36 12.54 2 12 2z" fill="currentColor"/>
            </svg>
        `;
        
        messageContent.appendChild(textSpan);
        messageContent.appendChild(loadingIcon);
        messageContentWrapper.appendChild(messageContent);
        messageDiv.appendChild(messageContentWrapper);

        if (this.chatMessages) {
            this.chatMessages.appendChild(messageDiv);
            
            // 如果是第一条消息，移除居中样式
            const isFirstMessage = this.chatMessages.querySelectorAll('.message').length === 1;
            if (isFirstMessage && this.chatContainer) {
                this.chatContainer.classList.remove('centered');
                this.chatContainer.style.transition = 'all 0.5s ease';
            }
            
            this.scrollToBottom();
        }

        return messageDiv;
    }
    
    // 检查并设置居中样式
    checkAndSetCentered() {
        if (this.chatMessages && this.chatContainer) {
            const hasMessages = this.chatMessages.querySelectorAll('.message').length > 0;
            if (!hasMessages) {
                this.chatContainer.classList.add('centered');
            } else {
                this.chatContainer.classList.remove('centered');
            }
        }
    }

    // 滚动到底部
    scrollToBottom() {
        if (this.chatMessages) {
            this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
        }
    }

    // 处理流式传输完成
    handleStreamComplete(assistantMessageElement, fullResponse) {
        if (assistantMessageElement) {
            assistantMessageElement.classList.remove('streaming');
            const messageContent = assistantMessageElement.querySelector('.message-content');
            if (messageContent) {
                messageContent.innerHTML = this.renderMarkdown(fullResponse);
                // 高亮代码块
                this.highlightCodeBlocks(messageContent);
            }
        }
        // 保存流式消息到历史记录
        if (fullResponse) {
            this.currentChatHistory.push({
                type: 'assistant',
                content: fullResponse,
                timestamp: new Date().toISOString()
            });
            // 如果当前对话是从历史记录加载的，更新历史记录
            if (this.isCurrentChatFromHistory) {
                this.updateCurrentChatHistory();
                this.renderChatHistory();
            }
        }
    }

    // 显示通知
    showNotification(message, type = 'info') {
        // 创建通知元素
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            border-radius: 8px;
            color: white;
            font-weight: 500;
            z-index: 10000;
            animation: slideIn 0.3s ease;
            max-width: 300px;
        `;

        // 根据类型设置颜色（Google Material Design配色）
        const colors = {
            info: '#1a73e8',
            success: '#34a853',
            warning: '#fbbc04',
            error: '#ea4335'
        };
        notification.style.backgroundColor = colors[type] || colors.info;

        // 添加到页面
        document.body.appendChild(notification);

        // 3秒后自动移除
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, 3000);
    }

    // 处理文件选择
    handleFileSelect(event, mode = 'text') {
        const file = event.target.files[0];
        if (file) {
            if (mode === 'pdf') {
                if (!this.validatePdfFileType(file)) {
                    this.showNotification('只支持上传 PDF 格式的文件', 'error');
                    if (this.pdfFileInput) this.pdfFileInput.value = '';
                    return;
                }
                this.uploadPdfFile(file);
                return;
            }
            if (!this.validateTextFileType(file)) {
                this.showNotification('只支持上传 TXT 或 Markdown (.md) 格式的文件', 'error');
                if (this.fileInput) this.fileInput.value = '';
                return;
            }
            this.uploadFile(file);
        }
    }

    /** 单次 POST /api/upload（不含遮罩与 isStreaming） */
    async _postUploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('tenant_id', this.getRagTenantId());
        const response = await fetch(`${this.apiBaseUrl}/upload`, {
            method: 'POST',
            body: formData,
        });
        if (!response.ok) {
            throw new Error(await this.parseHttpError(response));
        }
        const data = await response.json();
        if (!((data.code === 200 || data.message === 'success') && data.data)) {
            throw new Error(data.message || '上传失败');
        }
        return data;
    }

    /** 单次 POST /api/upload/pdf（不含遮罩与 isStreaming） */
    async _postUploadPdfFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('tenant_id', this.getRagTenantId());
        const response = await fetch(`${this.apiBaseUrl}/upload/pdf`, {
            method: 'POST',
            body: formData,
        });
        if (!response.ok) {
            throw new Error(await this.parseHttpError(response));
        }
        const data = await response.json();
        if (!((data.code === 200 || data.message === 'success') && data.data)) {
            throw new Error(data.message || 'PDF 上传失败');
        }
        return data;
    }

    // 验证文本文件类型
    validateTextFileType(file) {
        const fileName = String(file.name || '').trim().toLowerCase();
        const allowedExtensions = ['.txt', '.md', '.markdown'];
        return allowedExtensions.some((ext) => fileName.endsWith(ext));
    }

    // 验证 PDF 文件类型
    validatePdfFileType(file) {
        const fileName = String(file.name || '').trim().toLowerCase();
        return fileName.endsWith('.pdf');
    }

    // 上传文件到知识库（输入栏「上传文件」菜单：立即单文件上传）
    async uploadFile(file) {
        if (!this.isRagDomainExplicit()) {
            this.showNotification('请先在工具菜单中选择知识领域，再上传嵌入', 'warning');
            return;
        }

        if (!this.validateTextFileType(file)) {
            this.showNotification('只支持上传 TXT 或 Markdown (.md) 格式的文件', 'error');
            return;
        }

        if (file.size > RAG_UPLOAD_MAX_BYTES) {
            this.showNotification(`文件不能超过 ${Math.round(RAG_UPLOAD_MAX_BYTES / (1024 * 1024))}MB（与后端一致）`, 'error');
            return;
        }

        this.isStreaming = true;
        this.updateUI();
        this.showUploadOverlay(true, file.name);

        try {
            await this._postUploadFile(file);
            const tid = this.getRagTenantId();
            const successMessage = `「${file.name}」已嵌入知识库（领域: ${tid}）。对话将使用同一领域检索。`;
            this.addMessage('assistant', successMessage, false, true);
        } catch (error) {
            console.error('文件上传失败:', error);
            this.showNotification('文件上传失败: ' + error.message, 'error');
        } finally {
            if (this.fileInput) {
                this.fileInput.value = '';
            }
            this.isStreaming = false;
            this.showUploadOverlay(false);
            this.updateUI();
        }
    }

    // 上传 PDF 到知识库（输入栏「上传 PDF」菜单：立即单文件上传）
    async uploadPdfFile(file) {
        if (!this.isRagDomainExplicit()) {
            this.showNotification('请先在工具菜单中选择知识领域，再上传嵌入', 'warning');
            return;
        }

        if (!this.validatePdfFileType(file)) {
            this.showNotification('只支持上传 PDF 格式的文件', 'error');
            return;
        }

        if (file.size > RAG_UPLOAD_MAX_BYTES) {
            this.showNotification(`文件不能超过 ${Math.round(RAG_UPLOAD_MAX_BYTES / (1024 * 1024))}MB（与后端一致）`, 'error');
            return;
        }

        this.isStreaming = true;
        this.updateUI();
        this.showUploadOverlay(true, file.name);

        try {
            await this._postUploadPdfFile(file);
            const tid = this.getRagTenantId();
            const successMessage = `「${file.name}」PDF 已嵌入知识库（领域: ${tid}）。对话将使用同一领域检索。`;
            this.addMessage('assistant', successMessage, false, true);
        } catch (error) {
            console.error('PDF 上传失败:', error);
            this.showNotification('PDF 上传失败: ' + error.message, 'error');
        } finally {
            if (this.pdfFileInput) {
                this.pdfFileInput.value = '';
            }
            this.isStreaming = false;
            this.showUploadOverlay(false);
            this.updateUI();
        }
    }

    // 格式化文件大小
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    }

    // HTML转义
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // 显示/隐藏加载遮罩层
    showLoadingOverlay(show) {
        if (this.loadingOverlay) {
            if (show) {
                this.loadingOverlay.style.display = 'flex';
                const loadingText = this.loadingOverlay.querySelector('.loading-text');
                const loadingSubtext = this.loadingOverlay.querySelector('.loading-subtext');
                if (loadingText) loadingText.textContent = '处理中，请稍候…';
                if (loadingSubtext) loadingSubtext.textContent = '后端正在处理，请耐心等待';
                // 防止页面滚动
                document.body.style.overflow = 'hidden';
            } else {
                this.loadingOverlay.style.display = 'none';
                // 恢复页面滚动
                document.body.style.overflow = '';
            }
        }
    }

    // 显示/隐藏上传遮罩层
    showUploadOverlay(show, fileName = '') {
        if (this.loadingOverlay) {
            if (show) {
                this.loadingOverlay.style.display = 'flex';
                // 更新文字为上传中
                const loadingText = this.loadingOverlay.querySelector('.loading-text');
                const loadingSubtext = this.loadingOverlay.querySelector('.loading-subtext');
                if (loadingText) loadingText.textContent = '正在嵌入知识库…';
                if (loadingSubtext) loadingSubtext.textContent = fileName ? String(fileName) : '请稍候';
                // 防止页面滚动
                document.body.style.overflow = 'hidden';
            } else {
                this.loadingOverlay.style.display = 'none';
                // 恢复页面滚动
                document.body.style.overflow = '';
            }
        }
    }
}

// 添加CSS动画
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// 初始化应用
document.addEventListener('DOMContentLoaded', () => {
    new SuperBizAgentApp();
});
