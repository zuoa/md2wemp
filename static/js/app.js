/**
 * MD2WE - Markdown 转微信公众号 HTML 工具
 */

class MD2WE {
    constructor() {
        this.currentSettings = {
            theme: 'default',
            codeTheme: 'github',
            fontSize: 'medium',
            background: 'warm',
            aiConfigCollapsed: false,
            wechatAppKey: '',
            wechatAppSecret: '',
            wechatAuthor: '',
            wechatSourceUrl: '',
            wechatProfiles: [],
            wechatSelectedProfileId: '',
            aiTextBaseUrl: '',
            aiTextModel: '',
            aiTextApiKey: '',
            aiImageBaseUrl: '',
            aiImageModel: '',
            aiImageApiKey: '',
            titleFocusPrompt: '',
            summaryFocusPrompt: '',
            imageFocusPrompt: '',
            wechatTitleFocusPrompt: '',
            wechatDigestFocusPrompt: '',
            wechatCoverFocusPrompt: ''
        };

        this.previewMode = 'mobile';
        this.debounceTimer = null;
        this.isDragging = false;
        this.previewRequestId = 0;
        this.mermaidSequence = 0;
        this.generatedImageDataUrl = '';
        this.generatedImagePrompt = '';
        this.generatedSummary = '';
        this.selectedTitleSuggestion = '';
        this.selectedWechatTitleSuggestion = '';
        this.currentShareLink = '';
        this.shareRequestInFlight = false;
        this.wechatRequestInFlight = false;
        this.wechatCoverImageDataUrl = '';
        this.editorLines = [''];
        this.editorLineOffsets = [0];
        this.selectionSyncFrame = null;
        this.editorDragSelection = null;
        this.aiCryptoPublicKeyPromise = null;
        this.init();
    }

    init() {
        this.bindElements();
        this.bindEvents();
        this.initMermaid();
        this.loadSavedContent();
        this.loadSavedSettings();
        this.updateStats();
        this.updateAssistantAvailability();
        this.resetShareState();
        this.updatePreview();
        this.initResizer();
        this.togglePreviewMode(this.previewMode);
    }

    bindElements() {
        this.editor = document.getElementById('editor');
        this.editorSyntaxLayer = document.getElementById('editorSyntaxLayer');
        this.editorSyntax = document.getElementById('editorSyntax');
        this.editorSelectionOverlay = document.getElementById('editorSelectionOverlay');
        this.editorCaret = document.getElementById('editorCaret');
        this.preview = document.getElementById('preview');
        this.previewWrapper = document.querySelector('.preview-wrapper');
        this.editorPanel = document.getElementById('editorPanel');
        this.previewPanel = document.getElementById('previewPanel');
        this.resizer = document.getElementById('resizer');

        this.settingsBtn = document.getElementById('settingsBtn');
        this.publishSettingsBtn = document.getElementById('publishSettingsBtn');
        this.assistantBtn = document.getElementById('assistantBtn');
        this.clearBtn = document.getElementById('clearBtn');
        this.downloadBtn = document.getElementById('downloadBtn');
        this.shareBtn = document.getElementById('shareBtn');
        this.copyPreviewBtn = document.getElementById('copyPreviewBtn');
        this.wechatDraftBtn = document.getElementById('wechatDraftBtn');
        this.headerSummary = document.getElementById('headerSummary');
        this.summaryTheme = document.getElementById('summaryTheme');
        this.summaryCodeTheme = document.getElementById('summaryCodeTheme');
        this.summaryFontSize = document.getElementById('summaryFontSize');
        this.summaryPreviewMode = document.getElementById('summaryPreviewMode');
        this.summaryAIStatus = document.getElementById('summaryAIStatus');
        this.summaryAIChip = document.getElementById('summaryAIChip');

        this.settingsOverlay = document.getElementById('settingsOverlay');
        this.settingsPanel = document.getElementById('settingsPanel');
        this.closeSettings = document.getElementById('closeSettings');
        this.publishSettingsOverlay = document.getElementById('publishSettingsOverlay');
        this.publishSettingsPanel = document.getElementById('publishSettingsPanel');
        this.closePublishSettings = document.getElementById('closePublishSettings');
        this.assistantOverlay = document.getElementById('assistantOverlay');
        this.assistantPanel = document.getElementById('assistantPanel');
        this.closeAssistant = document.getElementById('closeAssistant');
        this.shareOverlay = document.getElementById('shareOverlay');
        this.shareModal = document.getElementById('shareModal');
        this.closeShare = document.getElementById('closeShare');
        this.refreshShareBtn = document.getElementById('refreshShareBtn');
        this.shareStatus = document.getElementById('shareStatus');
        this.shareQr = document.getElementById('shareQr');
        this.shareQrPlaceholder = document.getElementById('shareQrPlaceholder');
        this.shareUrlInput = document.getElementById('shareUrlInput');
        this.copyShareLinkBtn = document.getElementById('copyShareLinkBtn');
        this.openShareLinkBtn = document.getElementById('openShareLinkBtn');
        this.wechatOverlay = document.getElementById('wechatOverlay');
        this.wechatModal = document.getElementById('wechatModal');
        this.closeWechat = document.getElementById('closeWechat');
        this.wechatStatus = document.getElementById('wechatStatus');
        this.wechatProfileSelect = document.getElementById('wechatProfileSelect');
        this.newWechatProfileBtn = document.getElementById('newWechatProfileBtn');
        this.wechatProfileNameInput = document.getElementById('wechatProfileNameInput');
        this.wechatAppKeyInput = document.getElementById('wechatAppKeyInput');
        this.wechatAppSecretInput = document.getElementById('wechatAppSecretInput');
        this.wechatAuthorInput = document.getElementById('wechatAuthorInput');
        this.wechatSourceUrlInput = document.getElementById('wechatSourceUrlInput');
        this.wechatHeaderTemplate = document.getElementById('wechatHeaderTemplate');
        this.wechatFooterTemplate = document.getElementById('wechatFooterTemplate');
        this.wechatQrCodeUrl = document.getElementById('wechatQrCodeUrl');
        this.wechatDraftProfileSelect = document.getElementById('wechatDraftProfileSelect');
        this.manageWechatProfilesBtn = document.getElementById('manageWechatProfilesBtn');
        this.wechatProfileSummary = document.getElementById('wechatProfileSummary');
        this.wechatCoverInput = document.getElementById('wechatCoverInput');
        this.wechatCoverPreview = document.getElementById('wechatCoverPreview');
        this.wechatCoverPlaceholder = document.getElementById('wechatCoverPlaceholder');
        this.wechatCoverPreviewImage = document.getElementById('wechatCoverPreviewImage');
        this.clearWechatCoverBtn = document.getElementById('clearWechatCoverBtn');
        this.wechatGenerateCoverBtn = document.getElementById('wechatGenerateCoverBtn');
        this.saveWechatConfigBtn = document.getElementById('saveWechatConfigBtn');
        this.resetWechatConfigBtn = document.getElementById('resetWechatConfigBtn');
        this.wechatTitleInput = document.getElementById('wechatTitleInput');
        this.wechatTitleFocusInput = document.getElementById('wechatTitleFocusInput');
        this.wechatGenerateTitleBtn = document.getElementById('wechatGenerateTitleBtn');
        this.wechatTitleSuggestions = document.getElementById('wechatTitleSuggestions');
        this.wechatDigestInput = document.getElementById('wechatDigestInput');
        this.wechatDigestFocusInput = document.getElementById('wechatDigestFocusInput');
        this.wechatGenerateDigestBtn = document.getElementById('wechatGenerateDigestBtn');
        this.applyWechatTitleSuggestionBtn = document.getElementById('applyWechatTitleSuggestionBtn');
        this.copyWechatTitleSuggestionBtn = document.getElementById('copyWechatTitleSuggestionBtn');
        this.wechatCoverFocusInput = document.getElementById('wechatCoverFocusInput');
        this.wechatMediaIdInput = document.getElementById('wechatMediaIdInput');
        this.wechatSubmitBtn = document.getElementById('wechatSubmitBtn');

        this.previewModeToggle = document.getElementById('previewModeToggle');

        this.themeGrid = document.getElementById('themeGrid');
        this.codeThemeGrid = document.getElementById('codeThemeGrid');
        this.fontSizeOptions = document.getElementById('fontSizeOptions');
        this.backgroundOptions = document.getElementById('backgroundOptions');
        this.aiTextBaseUrlInput = document.getElementById('aiTextBaseUrlInput');
        this.aiTextModelInput = document.getElementById('aiTextModelInput');
        this.aiTextApiKeyInput = document.getElementById('aiTextApiKeyInput');
        this.aiImageBaseUrlInput = document.getElementById('aiImageBaseUrlInput');
        this.aiImageModelInput = document.getElementById('aiImageModelInput');
        this.aiImageApiKeyInput = document.getElementById('aiImageApiKeyInput');
        this.aiConfigTabs = document.getElementById('aiConfigTabs');
        this.aiConfigCard = document.getElementById('aiConfigCard');
        this.aiConfigSummary = document.getElementById('aiConfigSummary');
        this.aiConfigToggleBtn = document.getElementById('aiConfigToggleBtn');
        this.saveAiConfigBtn = document.getElementById('saveAiConfigBtn');
        this.resetAiConfigBtn = document.getElementById('resetAiConfigBtn');

        this.charCount = document.getElementById('charCount');
        this.wordCount = document.getElementById('wordCount');
        this.totalCount = document.getElementById('totalCount');
        this.readingTime = document.getElementById('readingTime');
        this.headingCount = document.getElementById('headingCount');
        this.imageCount = document.getElementById('imageCount');
        this.lineCount = document.getElementById('lineCount');

        this.currentThemeBadge = document.getElementById('currentThemeBadge');
        this.toast = document.getElementById('toast');
        this.copyApiEndpoint = document.getElementById('copyApiEndpoint');
        this.apiExample = document.getElementById('apiExample');

        this.suggestTitlesBtn = document.getElementById('suggestTitlesBtn');
        this.generateSummaryBtn = document.getElementById('generateSummaryBtn');
        this.generateImageBtn = document.getElementById('generateImageBtn');
        this.exportImageBtn = document.getElementById('exportImageBtn');
        this.applyTitleSuggestionBtn = document.getElementById('applyTitleSuggestionBtn');
        this.copyTitleSuggestionBtn = document.getElementById('copyTitleSuggestionBtn');
        this.copySummaryBtn = document.getElementById('copySummaryBtn');
        this.insertImageAtTopBtn = document.getElementById('insertImageAtTopBtn');
        this.insertGeneratedImageBtn = document.getElementById('insertGeneratedImageBtn');
        this.downloadGeneratedImageBtn = document.getElementById('downloadGeneratedImageBtn');
        this.titleFocusInput = document.getElementById('titleFocusInput');
        this.summaryFocusInput = document.getElementById('summaryFocusInput');
        this.imageFocusInput = document.getElementById('imageFocusInput');
        this.titleSuggestionsList = document.getElementById('titleSuggestionsList');
        this.summaryOutput = document.getElementById('summaryOutput');
        this.generatedImageState = document.getElementById('generatedImageState');
        this.generatedImagePanel = document.getElementById('generatedImagePanel');
        this.generatedImagePreview = document.getElementById('generatedImagePreview');
        this.generatedImagePromptText = document.getElementById('generatedImagePrompt');
        this.assistantAIStatusBadge = document.getElementById('assistantAIStatusBadge');
    }

    bindEvents() {
        this.editor.addEventListener('mousedown', (event) => this.handleEditorMouseDown(event));
        this.editor.addEventListener('input', () => {
            this.saveContent();
            this.invalidateShareState();
            this.updateStats();
            this.updateEditorSyntax();
            this.debounceUpdate();
        });
        this.editor.addEventListener('select', () => this.scheduleEditorSelectionSync());
        this.editor.addEventListener('focus', () => this.scheduleEditorSelectionSync());
        this.editor.addEventListener('blur', () => this.scheduleEditorSelectionSync());
        this.editor.addEventListener('keyup', () => this.scheduleEditorSelectionSync());

        this.editor.addEventListener('keydown', (e) => {
            if (e.key === 'Tab') {
                e.preventDefault();
                const start = this.editor.selectionStart;
                const end = this.editor.selectionEnd;
                this.editor.value = `${this.editor.value.substring(0, start)}    ${this.editor.value.substring(end)}`;
                this.editor.selectionStart = this.editor.selectionEnd = start + 4;
                this.saveContent();
                this.invalidateShareState();
                this.updateStats();
                this.updateEditorSyntax();
                this.debounceUpdate();
            }
        });

        document.addEventListener('mousemove', (event) => this.handleEditorMouseMove(event));
        document.addEventListener('mouseup', () => this.handleEditorMouseUp());
        window.addEventListener('resize', () => this.scheduleEditorSelectionSync());

        this.settingsBtn.addEventListener('click', () => this.openSettings());
        this.publishSettingsBtn.addEventListener('click', () => this.openPublishSettingsPanel());
        this.assistantBtn.addEventListener('click', () => this.openAssistant());
        this.clearBtn.addEventListener('click', () => this.clearEditor());
        this.downloadBtn.addEventListener('click', () => this.downloadHTML());
        this.shareBtn.addEventListener('click', () => this.openShareModal());
        this.copyPreviewBtn.addEventListener('click', () => this.copyHTML());
        this.wechatDraftBtn.addEventListener('click', () => this.openWechatModal());

        this.closeSettings.addEventListener('click', () => this.closeSettingsPanel());
        this.settingsOverlay.addEventListener('click', () => this.closeSettingsPanel());
        this.closePublishSettings.addEventListener('click', () => this.closePublishSettingsPanel());
        this.publishSettingsOverlay.addEventListener('click', () => this.closePublishSettingsPanel());
        this.closeAssistant.addEventListener('click', () => this.closeAssistantPanel());
        this.assistantOverlay.addEventListener('click', () => this.closeAssistantPanel());
        this.closeShare.addEventListener('click', () => this.closeShareModal());
        this.shareOverlay.addEventListener('click', () => this.closeShareModal());
        this.closeWechat.addEventListener('click', () => this.closeWechatModal());
        this.wechatOverlay.addEventListener('click', () => this.closeWechatModal());
        this.wechatProfileSelect.addEventListener('change', () => this.handleWechatProfileSelectChange(this.wechatProfileSelect.value));
        this.wechatDraftProfileSelect.addEventListener('change', () => this.handleWechatProfileSelectChange(this.wechatDraftProfileSelect.value));
        this.newWechatProfileBtn.addEventListener('click', () => this.startNewWechatProfile());
        this.manageWechatProfilesBtn.addEventListener('click', () => this.openWechatProfileSettings());
        this.refreshShareBtn.addEventListener('click', () => this.generateShareLink());
        this.copyShareLinkBtn.addEventListener('click', () => this.copyShareLink());
        this.openShareLinkBtn.addEventListener('click', () => this.openShareLink());
        this.shareUrlInput.addEventListener('focus', () => this.shareUrlInput.select());
        this.wechatCoverInput.addEventListener('change', (event) => this.handleWechatCoverChange(event));
        this.clearWechatCoverBtn.addEventListener('click', () => this.clearWechatCover());
        this.wechatGenerateCoverBtn.addEventListener('click', () => this.runWechatAIImage());
        this.saveWechatConfigBtn.addEventListener('click', () => this.saveWechatConfig());
        this.resetWechatConfigBtn.addEventListener('click', () => this.resetWechatConfig());
        this.wechatGenerateTitleBtn.addEventListener('click', () => this.runWechatAITitle());
        this.wechatGenerateDigestBtn.addEventListener('click', () => this.runWechatAIDigest());
        this.applyWechatTitleSuggestionBtn.addEventListener('click', () => this.applySelectedWechatTitleSuggestion());
        this.copyWechatTitleSuggestionBtn.addEventListener('click', () => this.copySelectedWechatTitleSuggestion());
        this.wechatSubmitBtn.addEventListener('click', () => this.pushWechatDraft());
        this.wechatMediaIdInput.addEventListener('focus', () => this.wechatMediaIdInput.select());
        this.wechatTitleFocusInput.addEventListener('input', () => this.saveWechatPromptSettings());
        this.wechatDigestFocusInput.addEventListener('input', () => this.saveWechatPromptSettings());
        this.wechatCoverFocusInput.addEventListener('input', () => this.saveWechatPromptSettings());

        this.themeGrid.addEventListener('click', (e) => {
            const card = e.target.closest('.theme-card');
            if (card) {
                this.selectTheme(card.dataset.theme);
            }
        });

        this.codeThemeGrid.addEventListener('click', (e) => {
            const item = e.target.closest('.code-theme-item');
            if (item) {
                this.selectCodeTheme(item.dataset.codeTheme);
            }
        });

        this.fontSizeOptions.addEventListener('click', (e) => {
            const option = e.target.closest('.radio-option');
            if (option) {
                this.selectFontSize(option.dataset.fontSize);
            }
        });

        this.backgroundOptions.addEventListener('click', (e) => {
            const option = e.target.closest('.radio-option');
            if (option) {
                this.selectBackground(option.dataset.background);
            }
        });

        this.saveAiConfigBtn.addEventListener('click', () => this.saveAIConfig());
        this.resetAiConfigBtn.addEventListener('click', () => this.resetAIConfig());
        this.aiConfigTabs.addEventListener('click', (e) => {
            const tab = e.target.closest('.ai-config-tab');
            if (!tab) {
                return;
            }
            this.switchAIConfigTab(tab.dataset.tab);
        });
        this.aiConfigToggleBtn.addEventListener('click', () => this.toggleAIConfigCard());

        this.previewModeToggle.addEventListener('click', (e) => {
            const btn = e.target.closest('.mode-btn');
            if (btn) {
                this.togglePreviewMode(btn.dataset.mode);
            }
        });

        this.copyApiEndpoint.addEventListener('click', async () => {
            const endpoint = `${window.location.origin}/api/convert`;
            await navigator.clipboard.writeText(endpoint);
            this.showToast('API 端点已复制', 'success');
        });

        this.suggestTitlesBtn.addEventListener('click', () => {
            this.runAIAction(this.suggestTitlesBtn, '生成中...', 'text', () => this.fetchTitleSuggestions());
        });

        this.generateSummaryBtn.addEventListener('click', () => {
            this.runAIAction(this.generateSummaryBtn, '生成中...', 'text', () => this.fetchSummary());
        });

        this.generateImageBtn.addEventListener('click', () => {
            this.runAIAction(this.generateImageBtn, '生成中...', 'image', () => this.fetchImage());
        });

        this.titleFocusInput.addEventListener('input', () => this.saveAssistantPrompts());
        this.summaryFocusInput.addEventListener('input', () => this.saveAssistantPrompts());
        this.imageFocusInput.addEventListener('input', () => this.saveAssistantPrompts());
        this.applyTitleSuggestionBtn.addEventListener('click', () => this.applySelectedTitleSuggestion());
        this.copyTitleSuggestionBtn.addEventListener('click', () => this.copySelectedTitleSuggestion());
        this.exportImageBtn.addEventListener('click', () => this.exportLongImage());
        this.copySummaryBtn.addEventListener('click', () => this.copySummary());
        this.insertImageAtTopBtn.addEventListener('click', () => this.insertGeneratedImageAtTop());
        this.insertGeneratedImageBtn.addEventListener('click', () => this.insertGeneratedImage());
        this.downloadGeneratedImageBtn.addEventListener('click', () => this.downloadGeneratedImage());

        this.initDrawerGestures(this.settingsPanel, () => this.closeSettingsPanel());
        this.initDrawerGestures(this.publishSettingsPanel, () => this.closePublishSettingsPanel());
        this.initDrawerGestures(this.assistantPanel, () => this.closeAssistantPanel());

        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                e.preventDefault();
                this.copyHTML();
            }

            if ((e.ctrlKey || e.metaKey) && e.key === ',') {
                e.preventDefault();
                this.openSettings();
            }

            if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'a') {
                e.preventDefault();
                this.openAssistant();
            }

            if (e.key === 'Escape') {
                this.closeAllDrawers();
                this.closeShareModal();
                this.closeWechatModal();
            }
        });

        this.initSyncScroll();
    }

    initMermaid() {
        if (!window.mermaid) {
            return;
        }

        window.mermaid.initialize({
            startOnLoad: false,
            securityLevel: 'loose',
            theme: 'neutral'
        });
    }

    initSyncScroll() {
        let isEditorScrolling = false;
        let isPreviewScrolling = false;

        this.editor.addEventListener('scroll', () => {
            if (isPreviewScrolling) return;

            isEditorScrolling = true;
            this.syncEditorSyntaxScroll();
            this.scheduleEditorSelectionSync();
            const editorScrollable = this.editor.scrollHeight - this.editor.clientHeight;
            const previewScrollElement = this.getPreviewScrollElement();
            const previewScrollable = previewScrollElement.scrollHeight - previewScrollElement.clientHeight;
            const ratio = editorScrollable > 0 ? this.editor.scrollTop / editorScrollable : 0;
            previewScrollElement.scrollTop = ratio * previewScrollable;

            requestAnimationFrame(() => {
                isEditorScrolling = false;
            });
        });

        this.previewWrapper.addEventListener('scroll', (event) => {
            if (isEditorScrolling) return;

            const target = this.getPreviewScrollElementFromEvent(event);
            if (!target) return;

            isPreviewScrolling = true;
            const previewScrollable = target.scrollHeight - target.clientHeight;
            const editorScrollable = this.editor.scrollHeight - this.editor.clientHeight;
            const ratio = previewScrollable > 0 ? target.scrollTop / previewScrollable : 0;
            this.editor.scrollTop = ratio * editorScrollable;
            this.syncEditorSyntaxScroll();
            this.scheduleEditorSelectionSync();

            requestAnimationFrame(() => {
                isPreviewScrolling = false;
            });
        }, true);
    }

    updateEditorSyntax() {
        if (!this.editorSyntax) {
            return;
        }

        const text = this.editor.value || '';
        this.editorLines = text.split('\n');
        this.editorLineOffsets = [];

        let offset = 0;
        this.editorLines.forEach((line) => {
            this.editorLineOffsets.push(offset);
            offset += line.length + 1;
        });

        const html = this.editorLines.map((line) => this.renderEditorLine(line)).join('');
        this.editorSyntax.innerHTML = html || '<span class="editor-line editor-line-empty"></span>';
        this.syncEditorSyntaxScroll();
        this.scheduleEditorSelectionSync();
    }

    renderEditorLine(line) {
        if (!line) {
            return '<span class="editor-line editor-line-empty"></span>';
        }

        const headingMatch = line.match(/^(#{1,4})(\s+)(.*)$/);
        if (headingMatch) {
            const level = headingMatch[1].length;
            const marker = this.escapeHTML(headingMatch[1]);
            const spacing = this.escapeHTML(headingMatch[2]);
            const content = this.escapeHTML(headingMatch[3] || '');
            return `<span class="editor-line editor-line-heading editor-line-h${level}"><span class="editor-heading-marker">${marker}</span><span class="editor-heading-space">${spacing}</span><span class="editor-heading-text">${content}</span></span>`;
        }

        return `<span class="editor-line">${this.escapeHTML(line)}</span>`;
    }

    syncEditorSyntaxScroll() {
        if (!this.editorSyntax) {
            return;
        }

        this.editorSyntax.style.transform = `translate(${-this.editor.scrollLeft}px, ${-this.editor.scrollTop}px)`;
    }

    handleEditorMouseDown(event) {
        if (event.button !== 0 || !this.editorSyntax) {
            return;
        }

        event.preventDefault();
        this.editor.focus();

        const anchorOffset = event.shiftKey
            ? this.editor.selectionStart
            : this.getEditorOffsetFromPoint(event.clientX, event.clientY);
        const focusOffset = this.getEditorOffsetFromPoint(event.clientX, event.clientY);
        this.editorDragSelection = { anchorOffset };
        this.setEditorSelection(anchorOffset, focusOffset);
    }

    handleEditorMouseMove(event) {
        if (!this.editorDragSelection) {
            return;
        }

        const focusOffset = this.getEditorOffsetFromPoint(event.clientX, event.clientY);
        this.setEditorSelection(this.editorDragSelection.anchorOffset, focusOffset);
    }

    handleEditorMouseUp() {
        this.editorDragSelection = null;
    }

    setEditorSelection(anchorOffset, focusOffset) {
        const direction = focusOffset < anchorOffset ? 'backward' : 'forward';
        this.editor.setSelectionRange(
            Math.min(anchorOffset, focusOffset),
            Math.max(anchorOffset, focusOffset),
            direction
        );
        this.scheduleEditorSelectionSync();
    }

    scheduleEditorSelectionSync() {
        if (this.selectionSyncFrame) {
            cancelAnimationFrame(this.selectionSyncFrame);
        }

        this.selectionSyncFrame = requestAnimationFrame(() => {
            this.selectionSyncFrame = null;
            this.updateEditorSelectionVisuals();
        });
    }

    updateEditorSelectionVisuals() {
        if (!this.editorSelectionOverlay || !this.editorCaret || !this.editorSyntaxLayer) {
            return;
        }

        this.editorSelectionOverlay.innerHTML = '';
        this.editorCaret.classList.remove('is-visible');

        if (document.activeElement !== this.editor) {
            return;
        }

        const selectionStart = this.editor.selectionStart;
        const selectionEnd = this.editor.selectionEnd;

        if (selectionStart === selectionEnd) {
            this.renderEditorCaret(selectionStart);
            return;
        }

        this.renderEditorSelection(selectionStart, selectionEnd);
    }

    renderEditorSelection(selectionStart, selectionEnd) {
        const start = this.resolveEditorOffset(selectionStart);
        const end = this.resolveEditorOffset(selectionEnd);
        const layerRect = this.editorSyntaxLayer.getBoundingClientRect();

        for (let lineIndex = start.lineIndex; lineIndex <= end.lineIndex; lineIndex += 1) {
            const lineText = this.editorLines[lineIndex] || '';
            const segmentStart = lineIndex === start.lineIndex ? start.column : 0;
            const segmentEnd = lineIndex === end.lineIndex ? end.column : lineText.length;

            if (segmentStart < segmentEnd) {
                const range = this.createEditorRange(lineIndex, segmentStart, segmentEnd);
                if (range) {
                    Array.from(range.getClientRects()).forEach((rect) => {
                        this.appendSelectionRect(rect, layerRect);
                    });
                }
            }

            if (lineIndex < end.lineIndex) {
                const newlineRect = this.getEditorCaretRect(lineIndex, lineText.length);
                if (newlineRect) {
                    this.appendSelectionRect({
                        left: newlineRect.left,
                        top: newlineRect.top,
                        width: 8,
                        height: newlineRect.height
                    }, layerRect);
                }
            }
        }
    }

    appendSelectionRect(rect, layerRect) {
        if (!rect || rect.width <= 0 || rect.height <= 0) {
            return;
        }

        const selectionRect = document.createElement('div');
        selectionRect.className = 'editor-selection-rect';
        selectionRect.style.left = `${rect.left - layerRect.left}px`;
        selectionRect.style.top = `${rect.top - layerRect.top}px`;
        selectionRect.style.width = `${rect.width}px`;
        selectionRect.style.height = `${rect.height}px`;
        this.editorSelectionOverlay.appendChild(selectionRect);
    }

    renderEditorCaret(offset) {
        const position = this.resolveEditorOffset(offset);
        const rect = this.getEditorCaretRect(position.lineIndex, position.column);
        const layerRect = this.editorSyntaxLayer.getBoundingClientRect();

        if (!rect) {
            return;
        }

        this.editorCaret.style.left = `${rect.left - layerRect.left}px`;
        this.editorCaret.style.top = `${rect.top - layerRect.top}px`;
        this.editorCaret.style.height = `${rect.height}px`;
        this.editorCaret.classList.add('is-visible');
    }

    getEditorCaretRect(lineIndex, column) {
        const lineElement = this.getEditorLineElement(lineIndex);
        if (!lineElement) {
            return null;
        }

        const lineText = this.editorLines[lineIndex] || '';
        if (lineText.length > 0) {
            if (column < lineText.length) {
                const range = this.createEditorRange(lineIndex, column, column + 1);
                const rect = range ? range.getBoundingClientRect() : null;
                if (rect && rect.height > 0) {
                    return {
                        left: rect.left,
                        top: rect.top,
                        height: rect.height
                    };
                }
            }

            if (column > 0) {
                const range = this.createEditorRange(lineIndex, column - 1, column);
                const rect = range ? range.getBoundingClientRect() : null;
                if (rect && rect.height > 0) {
                    return {
                        left: rect.right,
                        top: rect.top,
                        height: rect.height
                    };
                }
            }
        }

        const lineRect = lineElement.getBoundingClientRect();
        return {
            left: lineRect.left,
            top: lineRect.top,
            height: lineRect.height || this.editor.getBoundingClientRect().height
        };
    }

    getEditorOffsetFromPoint(clientX, clientY) {
        const lineIndex = this.getEditorLineIndexFromPoint(clientY);
        const lineElement = this.getEditorLineElement(lineIndex);
        const lineText = this.editorLines[lineIndex] || '';

        if (!lineElement) {
            return this.editor.value.length;
        }

        const lineBounds = this.getEditorLineContentBounds(lineIndex);
        if (clientX <= lineBounds.left) {
            return this.getEditorGlobalOffset(lineIndex, 0);
        }

        if (clientX >= lineBounds.right) {
            return this.getEditorGlobalOffset(lineIndex, lineText.length);
        }

        const domPoint = this.getDomPointFromCoordinates(clientX, clientY);
        if (domPoint && lineElement.contains(domPoint.node)) {
            const column = this.getEditorColumnFromDomPoint(lineElement, domPoint.node, domPoint.offset);
            return this.getEditorGlobalOffset(lineIndex, column);
        }

        const column = this.findNearestEditorColumn(lineIndex, clientX);
        return this.getEditorGlobalOffset(lineIndex, column);
    }

    getEditorLineIndexFromPoint(clientY) {
        const lineElements = this.editorSyntax.children;
        if (!lineElements.length) {
            return 0;
        }

        for (let index = 0; index < lineElements.length; index += 1) {
            const rect = lineElements[index].getBoundingClientRect();
            if (clientY < rect.top) {
                return Math.max(0, index - 1);
            }

            if (clientY <= rect.bottom) {
                return index;
            }
        }

        return lineElements.length - 1;
    }

    getEditorLineContentBounds(lineIndex) {
        const lineText = this.editorLines[lineIndex] || '';
        const lineElement = this.getEditorLineElement(lineIndex);
        const lineRect = lineElement.getBoundingClientRect();

        if (!lineText.length) {
            return { left: lineRect.left, right: lineRect.left };
        }

        const startRect = this.getEditorCaretRect(lineIndex, 0);
        const endRect = this.getEditorCaretRect(lineIndex, lineText.length);

        return {
            left: startRect ? startRect.left : lineRect.left,
            right: endRect ? endRect.left : lineRect.right
        };
    }

    getDomPointFromCoordinates(clientX, clientY) {
        if (document.caretPositionFromPoint) {
            const position = document.caretPositionFromPoint(clientX, clientY);
            if (position) {
                return { node: position.offsetNode, offset: position.offset };
            }
        }

        if (document.caretRangeFromPoint) {
            const range = document.caretRangeFromPoint(clientX, clientY);
            if (range) {
                return { node: range.startContainer, offset: range.startOffset };
            }
        }

        return null;
    }

    getEditorColumnFromDomPoint(lineElement, node, offset) {
        const range = document.createRange();
        range.setStart(lineElement, 0);
        range.setEnd(node, offset);
        return Math.min(range.toString().length, (this.editorLines[this.getEditorLineIndex(lineElement)] || '').length);
    }

    findNearestEditorColumn(lineIndex, clientX) {
        const lineText = this.editorLines[lineIndex] || '';
        let bestColumn = 0;
        let bestDistance = Number.POSITIVE_INFINITY;

        for (let column = 0; column <= lineText.length; column += 1) {
            const rect = this.getEditorCaretRect(lineIndex, column);
            if (!rect) {
                continue;
            }

            const distance = Math.abs(rect.left - clientX);
            if (distance < bestDistance) {
                bestDistance = distance;
                bestColumn = column;
            }
        }

        return bestColumn;
    }

    createEditorRange(lineIndex, startColumn, endColumn) {
        const lineElement = this.getEditorLineElement(lineIndex);
        if (!lineElement) {
            return null;
        }

        const startPoint = this.getEditorDomPointForColumn(lineElement, startColumn);
        const endPoint = this.getEditorDomPointForColumn(lineElement, endColumn);
        const range = document.createRange();
        range.setStart(startPoint.node, startPoint.offset);
        range.setEnd(endPoint.node, endPoint.offset);
        return range;
    }

    getEditorDomPointForColumn(lineElement, column) {
        const walker = document.createTreeWalker(lineElement, NodeFilter.SHOW_TEXT);
        let consumed = 0;
        let lastNode = null;

        while (walker.nextNode()) {
            const currentNode = walker.currentNode;
            const length = currentNode.textContent.length;

            if (column <= consumed + length) {
                return {
                    node: currentNode,
                    offset: column - consumed
                };
            }

            consumed += length;
            lastNode = currentNode;
        }

        if (lastNode) {
            return {
                node: lastNode,
                offset: lastNode.textContent.length
            };
        }

        return {
            node: lineElement,
            offset: 0
        };
    }

    getEditorLineElement(lineIndex) {
        return this.editorSyntax.children[lineIndex] || null;
    }

    getEditorLineIndex(lineElement) {
        return Array.prototype.indexOf.call(this.editorSyntax.children, lineElement);
    }

    getEditorGlobalOffset(lineIndex, column) {
        const lineOffset = this.editorLineOffsets[lineIndex] || 0;
        const lineLength = (this.editorLines[lineIndex] || '').length;
        return lineOffset + Math.min(column, lineLength);
    }

    resolveEditorOffset(offset) {
        const clampedOffset = Math.max(0, Math.min(offset, this.editor.value.length));

        for (let lineIndex = this.editorLineOffsets.length - 1; lineIndex >= 0; lineIndex -= 1) {
            const lineOffset = this.editorLineOffsets[lineIndex];
            if (clampedOffset >= lineOffset) {
                return {
                    lineIndex,
                    column: Math.min(clampedOffset - lineOffset, (this.editorLines[lineIndex] || '').length)
                };
            }
        }

        return { lineIndex: 0, column: 0 };
    }

    getPreviewScrollElement() {
        if (this.previewMode === 'mobile') {
            return this.preview.querySelector('section') || this.previewWrapper;
        }
        return this.previewWrapper;
    }

    getPreviewScrollElementFromEvent(event) {
        const target = event.target;
        if (!(target instanceof HTMLElement)) {
            return null;
        }

        if (target === this.previewWrapper) {
            return this.previewWrapper;
        }

        if (this.previewMode === 'mobile' && this.preview.contains(target)) {
            return target;
        }

        return null;
    }

    initResizer() {
        let startX = 0;
        let startWidth = 0;

        const startDrag = (e) => {
            this.isDragging = true;
            this.resizer.classList.add('dragging');
            startX = e.clientX || e.touches[0].clientX;
            startWidth = this.editorPanel.offsetWidth;
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
        };

        const doDrag = (e) => {
            if (!this.isDragging) return;
            const clientX = e.clientX || (e.touches && e.touches[0].clientX);
            if (!clientX) return;

            const delta = clientX - startX;
            const newWidth = Math.max(320, Math.min(startWidth + delta, window.innerWidth * 0.55));
            this.editorPanel.style.flex = 'none';
            this.editorPanel.style.width = `${newWidth}px`;
        };

        const endDrag = () => {
            if (!this.isDragging) return;
            this.isDragging = false;
            this.resizer.classList.remove('dragging');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
        };

        this.resizer.addEventListener('mousedown', startDrag);
        document.addEventListener('mousemove', doDrag);
        document.addEventListener('mouseup', endDrag);

        this.resizer.addEventListener('touchstart', startDrag, { passive: true });
        document.addEventListener('touchmove', doDrag, { passive: true });
        document.addEventListener('touchend', endDrag);
    }

    debounceUpdate() {
        clearTimeout(this.debounceTimer);
        this.debounceTimer = setTimeout(() => {
            this.updatePreview();
        }, 280);
    }

    updateStats() {
        const text = this.editor.value;
        const chineseChars = (text.match(/[\u4e00-\u9fff]/g) || []).length;
        const englishWords = (text.match(/\b[a-zA-Z]+(?:['’-][a-zA-Z]+)*\b/g) || []).length;
        const total = text.length;
        const lines = text ? text.split('\n').length : 0;
        const headings = (text.match(/^\s{0,3}#{1,6}\s+/gm) || []).length;
        const images = (text.match(/!\[[^\]]*\]\(([^)]+)\)/g) || []).length;

        const chineseMinutes = chineseChars / 300;
        const englishMinutes = englishWords / 200;
        const readMinutes = text.trim() ? Math.max(1, Math.ceil(chineseMinutes + englishMinutes)) : 0;

        this.charCount.textContent = chineseChars;
        this.wordCount.textContent = englishWords;
        this.totalCount.textContent = total;
        this.readingTime.textContent = `${readMinutes} 分钟`;
        this.headingCount.textContent = headings;
        this.imageCount.textContent = images;
        this.lineCount.textContent = lines;
    }

    async updatePreview() {
        const markdown = this.editor.value;
        const requestId = ++this.previewRequestId;

        if (!markdown.trim()) {
            this.preview.innerHTML = `
                <section style="padding: 64px 40px; text-align: center;">
                    <div style="color: #A1A1AA; font-size: 14px; margin-bottom: 8px;">
                        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="opacity: 0.5; margin-bottom: 16px;">
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                            <circle cx="12" cy="12" r="3"></circle>
                        </svg>
                        <p style="margin: 0; color: #71717A;">在左侧输入 Markdown 内容</p>
                        <p style="margin: 4px 0 0; color: #A1A1AA; font-size: 12px;">实时预览将在此显示，Mermaid 图表会自动渲染为 SVG</p>
                    </div>
                </section>
            `;
            return;
        }

        try {
            const response = await fetch('/api/convert', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    markdown,
                    theme: this.currentSettings.theme,
                    code_theme: this.currentSettings.codeTheme,
                    font_size: this.currentSettings.fontSize,
                    background: this.currentSettings.background
                })
            });

            const data = await response.json();
            if (requestId !== this.previewRequestId) {
                return;
            }

            if (!response.ok || !data.success) {
                throw new Error(data.error || '转换失败');
            }

            this.preview.innerHTML = data.html;
            await this.renderMermaidDiagrams(this.preview);
        } catch (error) {
            console.error('转换失败:', error);
            this.preview.innerHTML = `
                <section style="padding: 24px; color: #EF4444;">
                    <p style="margin: 0;">转换错误: ${this.escapeHTML(error.message)}</p>
                </section>
            `;
        }
    }

    async renderMermaidDiagrams(container) {
        const nodes = Array.from(container.querySelectorAll('.md2-mermaid[data-mermaid]'));
        if (!nodes.length) {
            return;
        }

        if (!window.mermaid) {
            nodes.forEach((node) => {
                node.innerHTML = '<div class="md2-mermaid-error">Mermaid 脚本未加载，无法渲染图表。</div>';
            });
            return;
        }

        for (const node of nodes) {
            const encoded = node.dataset.mermaid;
            const source = this.decodeBase64Utf8(encoded);
            const renderId = `md2-mermaid-${Date.now()}-${this.mermaidSequence++}`;

            try {
                const result = await window.mermaid.render(renderId, source);
                node.innerHTML = result.svg;
                node.removeAttribute('data-mermaid');
            } catch (error) {
                console.error('Mermaid 渲染失败:', error);
                node.innerHTML = `
                    <div class="md2-mermaid-error">Mermaid 渲染失败，请检查语法。

${this.escapeHTML(source)}</div>
                `;
            }
        }
    }

    selectTheme(theme) {
        this.currentSettings.theme = theme;
        this.updateThemeUI();
        this.saveSettings();
        this.invalidateShareState();
        this.updatePreview();
        this.updateApiExample();
        this.updateHeaderSummary();

        const themeName = CONFIG.themes[theme]?.name || theme;
        this.currentThemeBadge.textContent = themeName;
        this.showToast(`已切换到「${themeName}」`, 'success');
    }

    updateThemeUI() {
        this.themeGrid.querySelectorAll('.theme-card').forEach((card) => {
            card.classList.toggle('active', card.dataset.theme === this.currentSettings.theme);
        });

        this.codeThemeGrid.querySelectorAll('.code-theme-item').forEach((item) => {
            item.classList.toggle('active', item.dataset.codeTheme === this.currentSettings.codeTheme);
        });

        this.fontSizeOptions.querySelectorAll('.radio-option').forEach((option) => {
            option.classList.toggle('active', option.dataset.fontSize === this.currentSettings.fontSize);
        });

        this.backgroundOptions.querySelectorAll('.radio-option').forEach((option) => {
            option.classList.toggle('active', option.dataset.background === this.currentSettings.background);
        });
    }

    selectCodeTheme(codeTheme) {
        this.currentSettings.codeTheme = codeTheme;
        this.updateCodeThemeLink(codeTheme);
        this.updateThemeUI();
        this.saveSettings();
        this.invalidateShareState();
        this.updatePreview();
        this.updateApiExample();
        this.showToast(`代码高亮已切换到「${CONFIG.codeThemes[codeTheme].name}」`, 'success');
    }

    updateCodeThemeLink(codeTheme) {
        const link = document.getElementById('codeThemeLink');
        if (link) {
            link.href = `https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/${codeTheme}.min.css`;
        }
    }

    selectFontSize(fontSize) {
        this.currentSettings.fontSize = fontSize;
        this.updateThemeUI();
        this.saveSettings();
        this.invalidateShareState();
        this.updatePreview();
        this.updateApiExample();
        this.showToast(`字体大小已切换到「${CONFIG.fontSizes[fontSize].name}」`, 'success');
    }

    selectBackground(background) {
        this.currentSettings.background = background;
        this.updateThemeUI();
        this.saveSettings();
        this.invalidateShareState();
        this.updatePreview();
        this.updateApiExample();
        this.showToast(`背景已切换到「${CONFIG.backgrounds[background].name}」`, 'success');
    }

    updateApiExample() {
        const example = {
            markdown: '# Hello World',
            theme: this.currentSettings.theme,
            code_theme: this.currentSettings.codeTheme,
            font_size: this.currentSettings.fontSize,
            background: this.currentSettings.background
        };
        this.apiExample.textContent = JSON.stringify(example, null, 2);
    }

    togglePreviewMode(mode) {
        this.previewMode = mode;

        this.previewModeToggle.querySelectorAll('.mode-btn').forEach((btn) => {
            btn.classList.toggle('active', btn.dataset.mode === mode);
        });

        if (mode === 'mobile') {
            this.previewWrapper.classList.add('mobile-mode');
        } else {
            this.previewWrapper.classList.remove('mobile-mode');
        }

        this.updateHeaderSummary();
    }

    openSettings() {
        this.openDrawer(this.settingsPanel, this.settingsOverlay, this.settingsBtn);
        this.updateThemeUI();
    }

    closeSettingsPanel() {
        this.closeDrawer(this.settingsPanel, this.settingsOverlay, this.settingsBtn);
    }

    openPublishSettingsPanel() {
        this.openDrawer(this.publishSettingsPanel, this.publishSettingsOverlay, this.publishSettingsBtn);
        this.populateWechatProfileEditor();
    }

    closePublishSettingsPanel() {
        this.closeDrawer(this.publishSettingsPanel, this.publishSettingsOverlay, this.publishSettingsBtn);
    }

    openAssistant() {
        this.openDrawer(this.assistantPanel, this.assistantOverlay, this.assistantBtn);
    }

    closeAssistantPanel() {
        this.closeDrawer(this.assistantPanel, this.assistantOverlay, this.assistantBtn);
    }

    openDrawer(panel, overlay, triggerBtn) {
        this.closeShareModal();
        this.closeAllDrawers();
        this.closeWechatModal();
        panel.style.removeProperty('transform');
        panel.classList.add('active');
        overlay.classList.add('active');
        if (triggerBtn) {
            triggerBtn.classList.add('active');
        }
        this.updatePageLockState();
    }

    closeDrawer(panel, overlay, triggerBtn) {
        panel.classList.remove('active');
        overlay.classList.remove('active');
        panel.style.removeProperty('transform');
        if (triggerBtn) {
            triggerBtn.classList.remove('active');
        }
        this.updatePageLockState();
    }

    closeAllDrawers() {
        this.closeDrawer(this.settingsPanel, this.settingsOverlay, this.settingsBtn);
        this.closeDrawer(this.publishSettingsPanel, this.publishSettingsOverlay, this.publishSettingsBtn);
        this.closeDrawer(this.assistantPanel, this.assistantOverlay, this.assistantBtn);
    }

    updatePageLockState() {
        const hasOpenLayer = this.settingsPanel.classList.contains('active')
            || this.publishSettingsPanel.classList.contains('active')
            || this.assistantPanel.classList.contains('active')
            || this.shareModal.classList.contains('active')
            || this.wechatModal.classList.contains('active');
        document.body.classList.toggle('drawer-open', hasOpenLayer);
    }

    openShareModal() {
        if (!this.editor.value.trim()) {
            this.showToast('请先输入内容', 'error');
            return;
        }

        this.closeAllDrawers();
        this.shareOverlay.classList.add('active');
        this.shareModal.classList.add('active');
        this.updatePageLockState();
        this.generateShareLink();
    }

    closeShareModal() {
        this.shareOverlay.classList.remove('active');
        this.shareModal.classList.remove('active');
        this.updatePageLockState();
    }

    openWechatModal() {
        if (!this.editor.value.trim()) {
            this.showToast('请先输入内容', 'error');
            return;
        }

        this.closeAllDrawers();
        this.closeShareModal();
        this.wechatOverlay.classList.add('active');
        this.wechatModal.classList.add('active');
        this.populateWechatSettings();
        this.refreshWechatDraftMeta();
        this.resetWechatDraftState('先选择一个发布账号，再确认标题、摘要和封面后即可推送。默认优先使用正文第一张图作为封面。');
        this.updatePageLockState();
    }

    closeWechatModal() {
        this.wechatOverlay.classList.remove('active');
        this.wechatModal.classList.remove('active');
        this.updatePageLockState();
    }

    initDrawerGestures(panel, onClose) {
        let startX = 0;
        let startY = 0;
        let isTracking = false;
        let currentOffset = 0;

        panel.addEventListener('touchstart', (event) => {
            if (!panel.classList.contains('active') || event.touches.length !== 1) {
                return;
            }

            startX = event.touches[0].clientX;
            startY = event.touches[0].clientY;
            isTracking = true;
            currentOffset = 0;
            panel.style.transition = 'none';
        }, { passive: true });

        panel.addEventListener('touchmove', (event) => {
            if (!isTracking || event.touches.length !== 1) {
                return;
            }

            const deltaX = event.touches[0].clientX - startX;
            const deltaY = event.touches[0].clientY - startY;
            const isMobile = window.innerWidth <= 768;
            const primaryDelta = isMobile ? Math.max(0, deltaY) : Math.max(0, deltaX);
            const secondaryDelta = isMobile ? Math.abs(deltaX) : Math.abs(deltaY);

            if (secondaryDelta > primaryDelta) {
                return;
            }

            currentOffset = primaryDelta;
            const translateValue = isMobile
                ? `translateY(${Math.min(currentOffset, panel.offsetHeight)}px)`
                : `translateX(${Math.min(currentOffset, panel.offsetWidth)}px)`;

            panel.style.transform = translateValue;
        }, { passive: true });

        panel.addEventListener('touchend', () => {
            if (!isTracking) {
                return;
            }

            isTracking = false;
            panel.style.transition = '';
            const threshold = window.innerWidth <= 768 ? 96 : 88;

            if (currentOffset > threshold) {
                onClose();
            } else {
                panel.style.removeProperty('transform');
            }
        });
    }

    async copyHTML() {
        const html = this.preview.innerHTML;

        if (!html || html.includes('在左侧输入')) {
            this.showToast('请先输入内容', 'error');
            return;
        }

        try {
            await navigator.clipboard.write([
                new ClipboardItem({
                    'text/html': new Blob([html], { type: 'text/html' }),
                    'text/plain': new Blob([html], { type: 'text/plain' })
                })
            ]);
            this.showToast('已复制，可直接粘贴到微信公众号', 'success');
        } catch (error) {
            try {
                await navigator.clipboard.writeText(html);
                this.showToast('已复制（纯文本格式）', 'success');
            } catch (fallbackError) {
                this.showToast('复制失败，请手动复制', 'error');
            }
        }
    }

    clearEditor() {
        if (this.editor.value && !confirm('确定要清空内容吗？')) {
            return;
        }

        this.editor.value = '';
        this.generatedSummary = '';
        this.generatedImageDataUrl = '';
        this.generatedImagePrompt = '';
        localStorage.removeItem('md2we_content');
        localStorage.removeItem('md2html_content');
        this.resetAssistantOutputs();
        this.resetShareState();
        this.updateStats();
        this.updateEditorSyntax();
        this.updateAssistantAvailability();
        this.updatePreview();
        this.showToast('内容已清空', 'success');
    }

    downloadHTML() {
        const html = this.preview.innerHTML;
        if (!html || html.includes('在左侧输入')) {
            this.showToast('请先输入内容', 'error');
            return;
        }

        const fullHTML = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>微信公众号文章</title>
</head>
<body style="margin: 0; padding: 0;">
${html}
</body>
</html>`;

        const blob = new Blob([fullHTML], { type: 'text/html;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `article_${Date.now()}.html`;
        a.click();
        URL.revokeObjectURL(url);
        this.showToast('HTML 文件已下载', 'success');
    }

    resetShareState(message = '点击“分享”后将生成可访问页面和二维码。') {
        this.currentShareLink = '';
        this.shareStatus.textContent = message;
        this.shareUrlInput.value = '';
        this.shareQr.innerHTML = '';
        this.shareQrPlaceholder.textContent = message.includes('二维码') ? message : '二维码生成中...';
        this.shareQrPlaceholder.classList.remove('hidden');
        this.copyShareLinkBtn.disabled = true;
        this.openShareLinkBtn.disabled = true;
    }

    invalidateShareState() {
        if (this.shareRequestInFlight) {
            return;
        }

        if (!this.currentShareLink && !this.shareUrlInput.value) {
            return;
        }

        this.resetShareState('内容已更新，请重新生成分享链接和二维码。');
    }

    renderShareResult(data) {
        this.currentShareLink = data.share_url || '';
        this.shareStatus.textContent = data.created_at_label
            ? `《${data.title || '未命名文章'}》已生成分享页，创建时间 ${data.created_at_label}。`
            : `《${data.title || '未命名文章'}》已生成分享页，扫码或打开链接即可查看。`;
        this.shareUrlInput.value = this.currentShareLink;
        this.copyShareLinkBtn.disabled = !this.currentShareLink;
        this.openShareLinkBtn.disabled = !this.currentShareLink;

        if (data.qr_svg) {
            this.shareQr.innerHTML = data.qr_svg;
            this.shareQrPlaceholder.classList.add('hidden');
        } else {
            this.shareQr.innerHTML = '';
            this.shareQrPlaceholder.textContent = CONFIG.qrEnabled
                ? '二维码生成失败，请复制链接访问。'
                : '当前环境未安装二维码依赖，链接已生成，可直接复制访问。';
            this.shareQrPlaceholder.classList.remove('hidden');
        }
    }

    async generateShareLink() {
        if (!this.editor.value.trim()) {
            this.showToast('请先输入内容', 'error');
            return;
        }

        if (this.shareRequestInFlight) {
            return;
        }

        this.shareRequestInFlight = true;
        this.shareBtn.disabled = true;
        this.refreshShareBtn.disabled = true;
        this.resetShareState('正在生成分享链接和二维码...');

        try {
            const response = await fetch('/api/share', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    markdown: this.editor.value,
                    theme: this.currentSettings.theme,
                    code_theme: this.currentSettings.codeTheme,
                    font_size: this.currentSettings.fontSize,
                    background: this.currentSettings.background
                })
            });

            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || '分享生成失败');
            }

            this.renderShareResult(data);
            this.showToast('分享链接已生成', 'success');
        } catch (error) {
            console.error('分享生成失败:', error);
            this.resetShareState(error.message || '分享生成失败，请稍后重试。');
            this.shareQrPlaceholder.textContent = error.message || '分享生成失败，请稍后重试。';
            this.showToast(error.message || '分享生成失败', 'error');
        } finally {
            this.shareBtn.disabled = false;
            this.refreshShareBtn.disabled = false;
            this.shareRequestInFlight = false;
        }
    }

    async copyShareLink() {
        if (!this.currentShareLink) {
            return;
        }

        try {
            await navigator.clipboard.writeText(this.currentShareLink);
            this.showToast('分享链接已复制', 'success');
        } catch (error) {
            this.showToast('复制链接失败', 'error');
        }
    }

    openShareLink() {
        if (!this.currentShareLink) {
            return;
        }

        window.open(this.currentShareLink, '_blank', 'noopener,noreferrer');
    }

    resetWechatDraftState(message) {
        this.wechatStatus.textContent = message;
        this.wechatMediaIdInput.value = '';
    }

    updateWechatCoverPreview() {
        if (this.wechatCoverImageDataUrl) {
            this.wechatCoverPreviewImage.src = this.wechatCoverImageDataUrl;
            this.wechatCoverPreviewImage.classList.remove('hidden');
            this.wechatCoverPlaceholder.classList.add('hidden');
            return;
        }

        this.wechatCoverPreviewImage.removeAttribute('src');
        this.wechatCoverPreviewImage.classList.add('hidden');
        this.wechatCoverPlaceholder.textContent = '未选择封面。留空时优先取正文第一张图，没有则自动生成默认封面。';
        this.wechatCoverPlaceholder.classList.remove('hidden');
    }

    populateWechatSettings() {
        this.populateWechatProfileEditor();
        this.populateWechatDraftProfile();
        this.wechatTitleFocusInput.value = this.currentSettings.wechatTitleFocusPrompt || '';
        this.wechatDigestFocusInput.value = this.currentSettings.wechatDigestFocusPrompt || '';
        this.wechatCoverFocusInput.value = this.currentSettings.wechatCoverFocusPrompt || '';
        this.updateWechatTitleActionState();
        this.updateWechatCoverPreview();
    }

    saveWechatPromptSettings() {
        this.currentSettings.wechatTitleFocusPrompt = this.wechatTitleFocusInput.value.trim();
        this.currentSettings.wechatDigestFocusPrompt = this.wechatDigestFocusInput.value.trim();
        this.currentSettings.wechatCoverFocusPrompt = this.wechatCoverFocusInput.value.trim();
        this.saveSettings();
    }

    saveWechatConfig(showToast = true) {
        const appKey = this.wechatAppKeyInput.value.trim();
        const appSecret = this.wechatAppSecretInput.value.trim();
        const profileName = this.wechatProfileNameInput.value.trim();
        if (!appKey || !appSecret) {
            this.showToast('请填写 AppKey 和 AppSecret', 'error');
            return;
        }

        const profiles = this.getWechatProfiles();
        const currentId = this.currentSettings.wechatSelectedProfileId || this.wechatProfileSelect.value;
        const profileId = currentId || this.createWechatProfileId();
        const nextProfile = this.normalizeWechatProfile({
            id: profileId,
            name: profileName || this.wechatAuthorInput.value.trim() || `公众号 ${profiles.length + 1}`,
            app_key: appKey,
            app_secret: appSecret,
            author: this.wechatAuthorInput.value.trim(),
            source_url: this.wechatSourceUrlInput.value.trim(),
            header_template: this.wechatHeaderTemplate?.value.trim() || '',
            footer_template: this.wechatFooterTemplate?.value.trim() || '',
            qr_code_url: this.wechatQrCodeUrl?.value.trim() || ''
        }, profiles.length);

        const nextProfiles = profiles.filter((profile) => profile.id !== profileId);
        nextProfiles.push(nextProfile);
        this.currentSettings.wechatProfiles = nextProfiles;
        this.currentSettings.wechatSelectedProfileId = profileId;
        this.currentSettings.wechatAppKey = nextProfile.app_key;
        this.currentSettings.wechatAppSecret = nextProfile.app_secret;
        this.currentSettings.wechatAuthor = nextProfile.author;
        this.currentSettings.wechatSourceUrl = nextProfile.source_url;
        this.saveWechatPromptSettings();
        this.saveSettings();
        this.populateWechatProfileEditor();
        this.populateWechatDraftProfile();
        if (showToast) {
            this.showToast('公众号账号已保存到本地', 'success');
        }
    }

    resetWechatConfig() {
        const currentId = this.currentSettings.wechatSelectedProfileId || this.wechatProfileSelect.value;
        if (!currentId) {
            this.startNewWechatProfile();
            this.showToast('当前没有可删除的账号', 'success');
            return;
        }

        this.currentSettings.wechatProfiles = this.getWechatProfiles().filter((profile) => profile.id !== currentId);
        this.currentSettings.wechatSelectedProfileId = this.currentSettings.wechatProfiles[0]?.id || '';
        const selectedProfile = this.getSelectedWechatProfile();
        this.currentSettings.wechatAppKey = selectedProfile?.app_key || '';
        this.currentSettings.wechatAppSecret = selectedProfile?.app_secret || '';
        this.currentSettings.wechatAuthor = selectedProfile?.author || '';
        this.currentSettings.wechatSourceUrl = selectedProfile?.source_url || '';
        this.saveSettings();
        this.populateWechatSettings();
        this.clearWechatCover(false);
        this.showToast('当前公众号账号已删除', 'success');
    }

    async handleWechatCoverChange(event) {
        const file = event.target.files?.[0];
        if (!file) {
            return;
        }

        try {
            const dataUrl = await this.readFileAsDataURL(file);
            this.wechatCoverImageDataUrl = dataUrl;
            this.updateWechatCoverPreview();
            this.showToast('封面已载入，推送时将优先使用', 'success');
        } catch (error) {
            console.error('读取封面失败:', error);
            this.showToast('读取封面失败', 'error');
            this.clearWechatCover(false);
        }
    }

    clearWechatCover(showToast = true) {
        this.wechatCoverImageDataUrl = '';
        if (this.wechatCoverInput) {
            this.wechatCoverInput.value = '';
        }
        this.updateWechatCoverPreview();
        if (showToast) {
            this.showToast('已清空当前封面，将自动选择正文图片或生成默认封面', 'success');
        }
    }

    readFileAsDataURL(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = () => reject(reader.error || new Error('文件读取失败'));
            reader.readAsDataURL(file);
        });
    }

    deriveWechatTitle() {
        const markdown = this.editor.value;
        const headingMatch = markdown.match(/^\s{0,3}#\s+(.+?)\s*$/m);
        if (headingMatch) {
            return headingMatch[1].trim();
        }

        const firstLine = markdown.split('\n').map((line) => line.trim()).find(Boolean);
        return firstLine || '未命名文章';
    }

    extractPlainTextFromMarkdown(markdown) {
        return markdown
            .replace(/```[\s\S]*?```/g, ' ')
            .replace(/`([^`]+)`/g, '$1')
            .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '$1 ')
            .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '$1 ')
            .replace(/^\s{0,3}#{1,6}\s*/gm, '')
            .replace(/^\s{0,3}>\s?/gm, '')
            .replace(/^\s*[-*+]\s+/gm, '')
            .replace(/^\s*\d+\.\s+/gm, '')
            .replace(/[>*_~|-]+/g, ' ')
            .replace(/\n{2,}/g, '\n')
            .trim();
    }

    refreshWechatDraftMeta() {
        const title = this.deriveWechatTitle();
        const digest = this.extractPlainTextFromMarkdown(this.editor.value).slice(0, 120);
        this.wechatTitleInput.value = title;
        this.wechatDigestInput.value = digest;
        this.resetWechatTitleSuggestions();
    }

    getWechatConfigPayload() {
        const selectedProfile = this.getSelectedWechatProfile();
        return {
            app_key: (selectedProfile?.app_key || this.currentSettings.wechatAppKey || '').trim(),
            app_secret: (selectedProfile?.app_secret || this.currentSettings.wechatAppSecret || '').trim()
        };
    }

    resetWechatTitleSuggestions(message = '点击后将在这里显示 3-5 个可选标题。') {
        this.selectedWechatTitleSuggestion = '';
        this.wechatTitleSuggestions.className = 'assistant-card-body muted wechat-title-suggestions';
        this.wechatTitleSuggestions.textContent = message;
        this.updateWechatTitleActionState();
    }

    renderWechatTitleSuggestions(suggestions) {
        if (!suggestions.length) {
            this.resetWechatTitleSuggestions('未生成可用标题。');
            return;
        }

        const wrapper = document.createElement('div');
        wrapper.className = 'title-suggestion-list';

        this.selectedWechatTitleSuggestion = suggestions[0] || '';
        suggestions.forEach((title) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'title-suggestion';
            button.textContent = title;
            if (title === this.selectedWechatTitleSuggestion) {
                button.classList.add('is-selected');
            }
            button.addEventListener('click', () => this.selectWechatTitleSuggestion(title));
            wrapper.appendChild(button);
        });

        this.wechatTitleSuggestions.className = 'assistant-card-body wechat-title-suggestions';
        this.wechatTitleSuggestions.innerHTML = '';
        this.wechatTitleSuggestions.appendChild(wrapper);
        this.updateWechatTitleActionState();
    }

    selectWechatTitleSuggestion(title) {
        this.selectedWechatTitleSuggestion = title;
        this.wechatTitleSuggestions.querySelectorAll('.title-suggestion').forEach((button) => {
            button.classList.toggle('is-selected', button.textContent === title);
        });
        this.updateWechatTitleActionState();
    }

    updateWechatTitleActionState() {
        this.applyWechatTitleSuggestionBtn.disabled = !this.selectedWechatTitleSuggestion;
        this.copyWechatTitleSuggestionBtn.disabled = !this.selectedWechatTitleSuggestion;
    }

    applySelectedWechatTitleSuggestion() {
        if (!this.selectedWechatTitleSuggestion) {
            return;
        }
        this.wechatTitleInput.value = this.selectedWechatTitleSuggestion;
        this.showToast('已采用该标题', 'success');
    }

    async copySelectedWechatTitleSuggestion() {
        if (!this.selectedWechatTitleSuggestion) {
            return;
        }
        await navigator.clipboard.writeText(this.selectedWechatTitleSuggestion);
        this.showToast('标题已复制', 'success');
    }

    async runWechatAITitle() {
        this.runAIAction(this.wechatGenerateTitleBtn, '生成中...', 'text', async () => {
            const data = await this.callAIEndpoint('/api/ai/title-suggestions', {
                markdown: this.editor.value,
                focus_prompt: this.wechatTitleFocusInput.value.trim()
            });
            this.renderWechatTitleSuggestions(data.suggestions || []);
            this.showToast('公众号标题建议已生成', 'success');
        });
    }

    async runWechatAIDigest() {
        this.runAIAction(this.wechatGenerateDigestBtn, '生成中...', 'text', async () => {
            const data = await this.callAIEndpoint('/api/ai/summary', {
                markdown: this.editor.value,
                focus_prompt: this.wechatDigestFocusInput.value.trim()
            });
            this.wechatDigestInput.value = data.summary || '';
            this.showToast('公众号摘要已生成', 'success');
        });
    }

    async runWechatAIImage() {
        this.runAIAction(this.wechatGenerateCoverBtn, '生成中...', 'image', async () => {
            const data = await this.callAIEndpoint('/api/ai/generate-image', {
                markdown: this.editor.value,
                focus_prompt: `用于微信公众号文章分享封面，构图完整，视觉克制，有传播感。${this.wechatCoverFocusInput.value.trim() ? ` ${this.wechatCoverFocusInput.value.trim()}` : ''}`
            });
            this.wechatCoverImageDataUrl = data.image_url || '';
            this.updateWechatCoverPreview();
            this.showToast('公众号封面已生成，可预览后决定是否保留', 'success');
        });
    }

    async pushWechatDraft() {
        if (!this.editor.value.trim()) {
            this.showToast('请先输入内容', 'error');
            return;
        }

        const wechatConfig = this.getWechatConfigPayload();
        if (!wechatConfig.app_key || !wechatConfig.app_secret) {
            this.showToast('请先填写公众号 AppKey 和 AppSecret', 'error');
            return;
        }

        if (this.wechatRequestInFlight) {
            return;
        }

        this.saveWechatConfig(false);
        this.wechatRequestInFlight = true;
        this.wechatSubmitBtn.disabled = true;
        this.wechatDraftBtn.disabled = true;
        this.resetWechatDraftState('正在推送到公众号草稿箱，请稍候...');

        try {
            const response = await fetch('/api/wechat/draft', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    markdown: this.editor.value,
                    theme: this.currentSettings.theme,
                    code_theme: this.currentSettings.codeTheme,
                    font_size: this.currentSettings.fontSize,
                    background: this.currentSettings.background,
                    wechat_config: wechatConfig,
                    meta: {
                        title: this.wechatTitleInput.value.trim(),
                        digest: this.wechatDigestInput.value.trim(),
                        author: this.wechatAuthorInput.value.trim(),
                        content_source_url: this.wechatSourceUrlInput.value.trim(),
                        cover_image: this.wechatCoverImageDataUrl,
                        header_template: this.wechatHeaderTemplate?.value.trim() || '',
                        footer_template: this.wechatFooterTemplate?.value.trim() || '',
                        qr_code_url: this.wechatQrCodeUrl?.value.trim() || ''
                    }
                })
            });

            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || '公众号草稿推送失败');
            }

            this.wechatMediaIdInput.value = data.media_id || '';
            this.wechatStatus.textContent = `《${data.title || '未命名文章'}》已推送到公众号草稿箱，已上传 ${data.uploaded_image_count || 0} 张正文图片。`;
            this.showToast('公众号草稿推送成功', 'success');
        } catch (error) {
            console.error('公众号草稿推送失败:', error);
            this.resetWechatDraftState(error.message || '公众号草稿推送失败，请稍后重试。');
            this.showToast(error.message || '公众号草稿推送失败', 'error');
        } finally {
            this.wechatRequestInFlight = false;
            this.wechatSubmitBtn.disabled = false;
            this.wechatDraftBtn.disabled = false;
        }
    }

    async exportLongImage() {
        if (!window.html2canvas) {
            this.showToast('长图导出脚本未加载', 'error');
            return;
        }

        const html = this.preview.innerHTML;
        if (!html || html.includes('在左侧输入')) {
            this.showToast('请先输入内容', 'error');
            return;
        }

        const originalLabel = this.exportImageBtn.textContent;
        this.exportImageBtn.textContent = '导出中...';
        this.exportImageBtn.disabled = true;

        const sandbox = document.createElement('div');
        sandbox.style.position = 'fixed';
        sandbox.style.left = '-10000px';
        sandbox.style.top = '0';
        sandbox.style.width = this.previewMode === 'mobile' ? '430px' : '860px';
        sandbox.style.background = '#ffffff';
        sandbox.style.padding = '0';
        sandbox.style.zIndex = '-1';
        sandbox.innerHTML = `<div style="width: 100%;">${html}</div>`;
        document.body.appendChild(sandbox);

        const target = sandbox.firstElementChild;
        target.querySelectorAll('section').forEach((section) => {
            section.style.maxHeight = 'none';
            section.style.overflow = 'visible';
        });

        try {
            const canvas = await window.html2canvas(target, {
                scale: 2,
                backgroundColor: '#ffffff',
                useCORS: true
            });
            const dataUrl = canvas.toDataURL('image/png');
            const a = document.createElement('a');
            a.href = dataUrl;
            a.download = `article-long-image-${Date.now()}.png`;
            a.click();
            this.showToast('长图已导出', 'success');
        } catch (error) {
            console.error('长图导出失败:', error);
            this.showToast('长图导出失败', 'error');
        } finally {
            document.body.removeChild(sandbox);
            this.exportImageBtn.textContent = originalLabel;
            this.exportImageBtn.disabled = false;
            this.updateAssistantAvailability();
        }
    }

    async callAIEndpoint(path, body) {
        const aiPayload = await this.buildAIConfigTransportPayload();
        const response = await fetch(path, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                ...body,
                ...aiPayload
            })
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.error || 'AI 请求失败');
        }
        return data;
    }

    async buildAIConfigTransportPayload() {
        const aiConfig = this.getAIConfigPayload();
        if (!CONFIG.aiCrypto?.enabled) {
            return { ai_config: aiConfig };
        }

        if (!window.crypto?.subtle || !CONFIG.aiCrypto?.publicKeyPem) {
            throw new Error('当前环境不支持 AI 参数加密，请升级浏览器或检查服务端配置');
        }

        return {
            ai_config_encrypted: await this.encryptAIConfigPayload(aiConfig)
        };
    }

    async encryptAIConfigPayload(aiConfig) {
        const publicKey = await this.getAICryptoPublicKey();
        const symmetricKey = await window.crypto.subtle.generateKey(
            {
                name: 'AES-GCM',
                length: 256
            },
            true,
            ['encrypt']
        );
        const iv = window.crypto.getRandomValues(new Uint8Array(12));
        const plaintext = new TextEncoder().encode(JSON.stringify(aiConfig));
        const ciphertext = await window.crypto.subtle.encrypt(
            {
                name: 'AES-GCM',
                iv
            },
            symmetricKey,
            plaintext
        );
        const rawSymmetricKey = await window.crypto.subtle.exportKey('raw', symmetricKey);
        const encryptedKey = await window.crypto.subtle.encrypt(
            {
                name: 'RSA-OAEP'
            },
            publicKey,
            rawSymmetricKey
        );

        return {
            version: CONFIG.aiCrypto.version,
            encrypted_key: this.encodeArrayBufferBase64(encryptedKey),
            iv: this.encodeArrayBufferBase64(iv),
            ciphertext: this.encodeArrayBufferBase64(ciphertext)
        };
    }

    async getAICryptoPublicKey() {
        if (!this.aiCryptoPublicKeyPromise) {
            this.aiCryptoPublicKeyPromise = window.crypto.subtle.importKey(
                'spki',
                this.decodePemToArrayBuffer(CONFIG.aiCrypto.publicKeyPem),
                {
                    name: 'RSA-OAEP',
                    hash: 'SHA-256'
                },
                false,
                ['encrypt']
            );
        }

        return this.aiCryptoPublicKeyPromise;
    }

    async runAIAction(button, busyText, capability, action) {
        if (!this.hasAICapability(capability)) {
            const capabilityLabel = capability === 'image' ? '图片 AI' : '文本 AI';
            this.showToast(`未配置${capabilityLabel}，AI 功能不可用`, 'error');
            return;
        }

        if (!this.editor.value.trim()) {
            this.showToast('请先输入文章内容', 'error');
            return;
        }

        const originalLabel = button.textContent;
        button.textContent = busyText;
        button.disabled = true;
        button.classList.add('is-busy');

        try {
            await action();
        } catch (error) {
            console.error('AI 操作失败:', error);
            this.showToast(error.message || 'AI 操作失败', 'error');
        } finally {
            button.textContent = originalLabel;
            button.disabled = false;
            button.classList.remove('is-busy');
            this.updateAssistantAvailability();
        }
    }

    async fetchTitleSuggestions() {
        const data = await this.callAIEndpoint('/api/ai/title-suggestions', {
            markdown: this.editor.value,
            focus_prompt: this.titleFocusInput.value.trim()
        });

        this.renderTitleSuggestions(data.suggestions || []);
        this.showToast('标题建议已生成', 'success');
    }

    renderTitleSuggestions(suggestions) {
        if (!suggestions.length) {
            this.selectedTitleSuggestion = '';
            this.titleSuggestionsList.className = 'assistant-card-body muted';
            this.titleSuggestionsList.textContent = '未生成可用标题。';
            this.updateAssistantAvailability();
            return;
        }

        const wrapper = document.createElement('div');
        wrapper.className = 'title-suggestion-list';

        this.selectedTitleSuggestion = suggestions[0] || '';
        suggestions.forEach((title) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'title-suggestion';
            button.textContent = title;
            if (title === this.selectedTitleSuggestion) {
                button.classList.add('is-selected');
            }
            button.addEventListener('click', () => this.selectTitleSuggestion(title));
            wrapper.appendChild(button);
        });

        this.titleSuggestionsList.className = 'assistant-card-body';
        this.titleSuggestionsList.innerHTML = '';
        this.titleSuggestionsList.appendChild(wrapper);
        this.updateAssistantAvailability();
    }

    selectTitleSuggestion(title) {
        this.selectedTitleSuggestion = title;
        this.titleSuggestionsList.querySelectorAll('.title-suggestion').forEach((button) => {
            button.classList.toggle('is-selected', button.textContent === title);
        });
        this.updateAssistantAvailability();
    }

    applyTitleSuggestion(title) {
        const markdown = this.editor.value;
        const headingPattern = /^\s{0,3}#\s+(.+?)\s*$/m;

        if (headingPattern.test(markdown)) {
            this.editor.value = markdown.replace(headingPattern, `# ${title}`);
        } else {
            this.editor.value = `# ${title}\n\n${markdown.trimStart()}`;
        }

        this.saveContent();
        this.invalidateShareState();
        this.updateStats();
        this.updateEditorSyntax();
        this.updatePreview();
        this.showToast('标题已替换', 'success');
    }

    applySelectedTitleSuggestion() {
        if (!this.selectedTitleSuggestion) {
            return;
        }
        this.applyTitleSuggestion(this.selectedTitleSuggestion);
    }

    async copySelectedTitleSuggestion() {
        if (!this.selectedTitleSuggestion) {
            return;
        }

        await navigator.clipboard.writeText(this.selectedTitleSuggestion);
        this.showToast('标题已复制', 'success');
    }

    async fetchSummary() {
        const data = await this.callAIEndpoint('/api/ai/summary', {
            markdown: this.editor.value,
            focus_prompt: this.summaryFocusInput.value.trim()
        });

        this.generatedSummary = data.summary || '';
        this.summaryOutput.className = 'assistant-card-body';
        this.summaryOutput.textContent = this.generatedSummary || '未生成摘要。';
        this.updateAssistantAvailability();
        this.showToast('文章摘要已生成', 'success');
    }

    async copySummary() {
        if (!this.generatedSummary) {
            return;
        }

        await navigator.clipboard.writeText(this.generatedSummary);
        this.showToast('摘要已复制', 'success');
    }

    async fetchImage() {
        this.generatedImageState.className = 'assistant-card-body muted';
        this.generatedImageState.textContent = '正在生成配图，请稍候...';
        this.generatedImagePanel.classList.add('hidden');

        const data = await this.callAIEndpoint('/api/ai/generate-image', {
            markdown: this.editor.value,
            focus_prompt: this.imageFocusInput.value.trim()
        });

        this.generatedImageDataUrl = data.image_url || '';
        this.generatedImagePrompt = data.revised_prompt || '';

        this.generatedImagePreview.src = this.generatedImageDataUrl;
        this.generatedImagePromptText.textContent = this.generatedImagePrompt || '已生成适配当前文章的 16:9 配图。';
        this.generatedImageState.textContent = '';
        this.generatedImagePanel.classList.remove('hidden');
        this.updateAssistantAvailability();
        this.showToast('配图已生成', 'success');
    }

    insertGeneratedImage() {
        if (!this.generatedImageDataUrl) {
            return;
        }

        const imageMarkdown = `\n\n![AI 配图](${this.generatedImageDataUrl})\n`;
        this.editor.value = `${this.editor.value.trimEnd()}${imageMarkdown}`;
        this.saveContent();
        this.invalidateShareState();
        this.updateStats();
        this.updateEditorSyntax();
        this.updatePreview();
        this.showToast('配图已插入文末', 'success');
    }

    insertGeneratedImageAtTop() {
        if (!this.generatedImageDataUrl) {
            return;
        }

        const imageMarkdown = `\n\n![AI 配图](${this.generatedImageDataUrl})\n`;
        const headingPattern = /^(\s{0,3}#\s+.+?\s*)$/m;

        if (headingPattern.test(this.editor.value)) {
            this.editor.value = this.editor.value.replace(headingPattern, `$1${imageMarkdown}`);
        } else {
            this.editor.value = `![AI 配图](${this.generatedImageDataUrl})\n\n${this.editor.value.trimStart()}`;
        }

        this.saveContent();
        this.invalidateShareState();
        this.updateStats();
        this.updateEditorSyntax();
        this.updatePreview();
        this.showToast('配图已插入文首', 'success');
    }

    downloadGeneratedImage() {
        if (!this.generatedImageDataUrl) {
            return;
        }

        const a = document.createElement('a');
        a.href = this.generatedImageDataUrl;
        a.download = `generated-cover-${Date.now()}.png`;
        a.click();
        this.showToast('配图已下载', 'success');
    }

    updateAssistantAvailability() {
        this.suggestTitlesBtn.disabled = !this.hasAICapability('text');
        this.generateSummaryBtn.disabled = !this.hasAICapability('text');
        this.generateImageBtn.disabled = !this.hasAICapability('image');

        this.applyTitleSuggestionBtn.disabled = !this.selectedTitleSuggestion;
        this.copyTitleSuggestionBtn.disabled = !this.selectedTitleSuggestion;
        this.copySummaryBtn.disabled = !this.generatedSummary;
        this.insertImageAtTopBtn.disabled = !this.generatedImageDataUrl;
        this.insertGeneratedImageBtn.disabled = !this.generatedImageDataUrl;
        this.downloadGeneratedImageBtn.disabled = !this.generatedImageDataUrl;
    }

    resetAssistantOutputs() {
        this.selectedTitleSuggestion = '';
        this.titleSuggestionsList.className = 'assistant-card-body muted';
        this.titleSuggestionsList.textContent = '生成后将在这里显示 3-5 个备选标题。';
        this.summaryOutput.className = 'assistant-card-body muted';
        this.summaryOutput.textContent = '点击“一键摘要”生成适合文章导语、封面说明或摘要栏的文案。';
        this.generatedImageState.className = 'assistant-card-body muted';
        this.generatedImageState.textContent = '尚未生成配图。';
        this.generatedImagePanel.classList.add('hidden');
        this.generatedImagePreview.removeAttribute('src');
        this.generatedImagePromptText.textContent = '';
    }

    saveContent() {
        try {
            localStorage.setItem('md2we_content', this.editor.value);
        } catch (error) {
            console.warn('保存内容失败:', error);
        }
    }

    loadSavedContent() {
        const saved = localStorage.getItem('md2we_content') || localStorage.getItem('md2html_content');

        if (saved) {
            this.editor.value = saved;
            try {
                localStorage.setItem('md2we_content', saved);
            } catch (error) {
                console.warn('迁移内容失败:', error);
            }
            return;
        }

        this.editor.value = `# 欢迎使用 \`MD2WE\` Markdown 转微信公众号工具

\`MD2WE\` 是一个面向微信公众号排版的 Markdown 编辑器。  
你可以用熟悉的 Markdown 写作，再直接生成适合公众号发布的排版内容，同时支持 \`Mermaid\` 图表、AI 标题建议、AI 摘要、AI 配图、分享页和公众号草稿推送。

项目地址：<https://github.com/zuoa/md2we>

---

## 为什么做这个工具

很多文章明明已经用 Markdown 写好了，但发到公众号之前，往往还要再处理一次：

- 手动调整段落和标题样式
- 重新整理代码块和引用
- 处理流程图、配图和封面
- 再单独生成分享链接
- 最后复制粘贴到公众号后台

\`MD2WE\` 的目标，就是把这条链路尽量缩短。

> 写作时专注内容，发布时尽量少折腾格式。

---

## 你可以用它做什么

### 1. 基础排版

支持常见 Markdown 结构：

- 一级、二级、三级标题
- **粗体**、*斜体*、\`行内代码\`
- 引用、分割线、无序列表、有序列表
- 表格、代码块、任务清单
- 链接与图片

### 2. 公众号友好的输出

适合公众号场景的能力包括：

- 多种排版主题
- 多种代码高亮方案
- 一键复制 HTML
- 下载 HTML
- 导出长图
- 生成分享页和二维码
- 推送到公众号草稿箱

### 3. AI 创作辅助

如果你配置了 AI，还可以直接在编辑器里完成这些工作：

- 生成标题建议
- 生成文章摘要
- 生成配图
- 辅助补全文案思路

---

## 一个简单的发布流程

1. 用 Markdown 写完内容
2. 选择合适的排版主题
3. 检查代码块、引用和图表效果
4. 让 AI 帮你生成标题和摘要
5. 生成分享页
6. 推送到公众号草稿箱

---

## 待办清单示例

- [x] 支持 Markdown 转公众号排版
- [x] 支持 Mermaid 图表渲染
- [x] 支持 AI 标题建议
- [x] 支持 AI 摘要生成
- [x] 支持 AI 配图
- [x] 支持分享页和二维码
- [x] 支持公众号草稿推送
- [ ] 继续打磨更多细节体验

---

## 引用示例

> 如果一篇文章最终要发到公众号，那么“写作”和“发布”最好不要是两套割裂的流程。  
> \`MD2WE\` 想解决的，就是这中间重复、机械、低效的部分。

---

## 代码块示例

\`\`\`python
def build_article(title: str, summary: str) -> dict:
    return {
        "title": title,
        "summary": summary,
        "status": "draft",
    }

article = build_article("用 Markdown 写公众号", "减少重复排版工作")
print(article)
\`\`\`

\`\`\`bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 app.py
\`\`\`

---

## Mermaid 流程图示例

\`\`\`mermaid
flowchart TD
    A[开始写作] --> B[输入 Markdown]
    B --> C[实时预览]
    C --> D[选择主题]
    D --> E[AI 生成标题/摘要/配图]
    E --> F[生成分享页]
    F --> G[推送公众号草稿]
    G --> H[完成发布]
\`\`\`

---

## Mermaid 时序图示例

\`\`\`mermaid
sequenceDiagram
    participant U as 用户
    participant E as 编辑器
    participant AI as AI 服务
    participant W as 微信公众号

    U->>E: 编写 Markdown
    E->>AI: 请求标题建议/摘要/配图
    AI-->>E: 返回结果
    U->>E: 确认排版和封面
    E->>W: 推送草稿
    W-->>U: 草稿创建成功
\`\`\`

---

## Mermaid 甘特图示例

\`\`\`mermaid
gantt
    title 一篇公众号文章的制作流程
    dateFormat  YYYY-MM-DD
    section 写作
    确定主题           :a1, 2026-02-20, 1d
    完成初稿           :a2, after a1, 2d
    section 排版
    调整样式           :b1, after a2, 1d
    插入图表与代码     :b2, after b1, 1d
    section 发布
    生成摘要与封面     :c1, after b2, 1d
    推送公众号草稿     :c2, after c1, 1d
\`\`\`

---

## 表格示例

| 功能 | 说明 | 适合场景 |
| :-- | :-- | :-- |
| 主题排版 | 多种文章样式可切换 | 技术文章、教程、观点文 |
| 代码高亮 | 支持代码块美化 | 开发教程 |
| Mermaid | 渲染流程图、时序图、甘特图 | 产品方案、技术设计 |
| AI 助手 | 标题、摘要、配图 | 提升发布效率 |
| 分享页 | 自动生成链接和二维码 | 二次传播 |
| 草稿推送 | 直接推送公众号后台 | 减少重复操作 |

---

## 一段适合公众号的正文示例

很多时候，真正消耗时间的不是写文章，而是“把文章发出去”这件事。

你已经用 Markdown 写完了标题、正文、代码和图表，但到了发布环节，还是得重新整理格式、调整样式、处理配图、生成封面，最后再复制到公众号后台。这个过程很碎，也很容易打断写作节奏。

\`MD2WE\` 的思路是：尽量让写作和发布留在同一条链路里完成。

---

## 快捷键示例

常用操作可以配合快捷键提高效率：

- \`Ctrl/Cmd + S\`：复制 HTML
- 保持本地自动保存，减少内容丢失风险
- 先预览，再生成分享页或推送草稿

---

## 一个简短结尾

如果你平时会：

- 写技术文章
- 发产品更新
- 做教程内容
- 运营微信公众号

那么这类工具通常能帮你省下不少重复劳动。

欢迎试试 \`MD2WE\`。  
也欢迎继续完善你自己的默认演示文档，让新用户一打开就知道这个项目能做什么。
`;
    }

    saveSettings() {
        localStorage.setItem('md2we_settings', JSON.stringify(this.currentSettings));
    }

    loadSavedSettings() {
        const saved = localStorage.getItem('md2we_settings') || localStorage.getItem('md2html_settings');
        if (saved) {
            try {
                const settings = JSON.parse(saved);
                this.currentSettings = { ...this.currentSettings, ...settings };
                localStorage.setItem('md2we_settings', JSON.stringify(this.currentSettings));
            } catch (error) {
                console.error('加载设置失败:', error);
            }
        }

        this.migrateWechatProfiles();

        const themeName = CONFIG.themes[this.currentSettings.theme]?.name || '默认主题';
        this.currentThemeBadge.textContent = themeName;
        this.updateCodeThemeLink(this.currentSettings.codeTheme);
        this.populateAISettings();
        this.populateAssistantPrompts();
        this.updateApiExample();
        this.updateHeaderSummary();
        this.resetAssistantOutputs();
        this.updateEditorSyntax();
    }

    migrateWechatProfiles() {
        const rawProfiles = Array.isArray(this.currentSettings.wechatProfiles) ? this.currentSettings.wechatProfiles : [];
        const normalizedProfiles = rawProfiles
            .map((profile, index) => this.normalizeWechatProfile(profile, index))
            .filter(Boolean);

        const hasLegacyConfig = Boolean(
            (this.currentSettings.wechatAppKey || '').trim()
            && (this.currentSettings.wechatAppSecret || '').trim()
        );

        if (!normalizedProfiles.length && hasLegacyConfig) {
            normalizedProfiles.push(this.normalizeWechatProfile({
                id: this.createWechatProfileId(),
                name: (this.currentSettings.wechatAuthor || '').trim() || '默认公众号',
                app_key: this.currentSettings.wechatAppKey,
                app_secret: this.currentSettings.wechatAppSecret,
                author: this.currentSettings.wechatAuthor,
                source_url: this.currentSettings.wechatSourceUrl
            }, 0));
        }

        this.currentSettings.wechatProfiles = normalizedProfiles;
        if (!normalizedProfiles.some((profile) => profile.id === this.currentSettings.wechatSelectedProfileId)) {
            this.currentSettings.wechatSelectedProfileId = normalizedProfiles[0]?.id || '';
        }
    }

    createWechatProfileId() {
        return `wechat-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    }

    normalizeWechatProfile(profile, index = 0) {
        if (!profile || typeof profile !== 'object') {
            return null;
        }

        const appKey = String(profile.app_key || profile.appKey || '').trim();
        const appSecret = String(profile.app_secret || profile.appSecret || '').trim();
        if (!appKey || !appSecret) {
            return null;
        }

        return {
            id: String(profile.id || `wechat-profile-${index + 1}`),
            name: String(profile.name || profile.author || `公众号 ${index + 1}`).trim(),
            app_key: appKey,
            app_secret: appSecret,
            author: String(profile.author || '').trim(),
            source_url: String(profile.source_url || profile.sourceUrl || '').trim()
        };
    }

    getWechatProfiles() {
        return Array.isArray(this.currentSettings.wechatProfiles) ? this.currentSettings.wechatProfiles : [];
    }

    getSelectedWechatProfile() {
        return this.getWechatProfiles().find((profile) => profile.id === this.currentSettings.wechatSelectedProfileId) || null;
    }

    getWechatProfileSummary(profile) {
        if (!profile) {
            return '请先在设置中新增至少一个公众号账号。';
        }

        const maskedAppKey = profile.app_key ? `${profile.app_key.slice(0, 4)}...${profile.app_key.slice(-4)}` : '未设置';
        const authorText = profile.author || '未设置作者';
        const sourceText = profile.source_url ? ` · 原文链接已配置` : '';
        return `${profile.name} · ${maskedAppKey} · 作者 ${authorText}${sourceText}`;
    }

    renderWechatProfileOptions() {
        const profiles = this.getWechatProfiles();
        const settingsOptions = ['<option value="">新建账号</option>', ...profiles.map((profile) => `<option value="${profile.id}">${profile.name}</option>`)];
        const draftOptions = ['<option value="">请选择账号</option>', ...profiles.map((profile) => `<option value="${profile.id}">${profile.name}</option>`)];

        this.wechatProfileSelect.innerHTML = settingsOptions.join('');
        this.wechatDraftProfileSelect.innerHTML = draftOptions.join('');
    }

    populateWechatProfileEditor() {
        const profile = this.getSelectedWechatProfile();
        this.renderWechatProfileOptions();
        this.wechatProfileSelect.value = profile?.id || '';
        this.wechatProfileNameInput.value = profile?.name || '';
        this.wechatAppKeyInput.value = profile?.app_key || '';
        this.wechatAppSecretInput.value = profile?.app_secret || '';
        this.wechatAuthorInput.value = profile?.author || '';
        this.wechatSourceUrlInput.value = profile?.source_url || '';
        if (this.wechatHeaderTemplate) {
            this.wechatHeaderTemplate.value = profile?.header_template || '';
        }
        if (this.wechatFooterTemplate) {
            this.wechatFooterTemplate.value = profile?.footer_template || '';
        }
        if (this.wechatQrCodeUrl) {
            this.wechatQrCodeUrl.value = profile?.qr_code_url || '';
        }
    }

    populateWechatDraftProfile() {
        const profile = this.getSelectedWechatProfile();
        this.renderWechatProfileOptions();
        this.wechatDraftProfileSelect.value = profile?.id || '';
        this.wechatProfileSummary.textContent = this.getWechatProfileSummary(profile);
    }

    handleWechatProfileSelectChange(profileId) {
        this.currentSettings.wechatSelectedProfileId = profileId || '';
        const selectedProfile = this.getSelectedWechatProfile();
        this.currentSettings.wechatAppKey = selectedProfile?.app_key || '';
        this.currentSettings.wechatAppSecret = selectedProfile?.app_secret || '';
        this.currentSettings.wechatAuthor = selectedProfile?.author || '';
        this.currentSettings.wechatSourceUrl = selectedProfile?.source_url || '';
        this.saveSettings();
        this.populateWechatProfileEditor();
        this.populateWechatDraftProfile();
    }

    startNewWechatProfile() {
        this.currentSettings.wechatSelectedProfileId = '';
        this.saveSettings();
        this.populateWechatProfileEditor();
        this.populateWechatDraftProfile();
        this.showToast('已切换到新建账号表单', 'success');
    }

    openWechatProfileSettings() {
        this.closeWechatModal();
        this.openPublishSettingsPanel();
        this.populateWechatProfileEditor();
        this.populateWechatDraftProfile();
    }

    populateAISettings() {
        const defaults = CONFIG.aiDefaults || {};
        this.aiTextBaseUrlInput.value = this.currentSettings.aiTextBaseUrl || defaults.text?.base_url || '';
        this.aiTextModelInput.value = this.currentSettings.aiTextModel || defaults.text?.model || '';
        this.aiTextApiKeyInput.value = this.currentSettings.aiTextApiKey || '';
        this.aiImageBaseUrlInput.value = this.currentSettings.aiImageBaseUrl || defaults.image?.base_url || '';
        this.aiImageModelInput.value = this.currentSettings.aiImageModel || defaults.image?.model || '';
        this.aiImageApiKeyInput.value = this.currentSettings.aiImageApiKey || '';
        this.updateAIConfigSummary();
        this.updateAIConfigCollapseUI();
        this.switchAIConfigTab('text');
    }

    populateAssistantPrompts() {
        this.titleFocusInput.value = this.currentSettings.titleFocusPrompt || '';
        this.summaryFocusInput.value = this.currentSettings.summaryFocusPrompt || '';
        this.imageFocusInput.value = this.currentSettings.imageFocusPrompt || '';
    }

    saveAssistantPrompts() {
        this.currentSettings.titleFocusPrompt = this.titleFocusInput.value.trim();
        this.currentSettings.summaryFocusPrompt = this.summaryFocusInput.value.trim();
        this.currentSettings.imageFocusPrompt = this.imageFocusInput.value.trim();
        this.saveSettings();
    }

    getAIConfigSummaryText() {
        const defaults = CONFIG.aiDefaults || {};
        const textModel = (this.aiTextModelInput?.value || this.currentSettings.aiTextModel || defaults.text?.model || '未设置').trim();
        const imageModel = (this.aiImageModelInput?.value || this.currentSettings.aiImageModel || defaults.image?.model || '未设置').trim();
        const textConfigured = Boolean((this.aiTextApiKeyInput?.value || this.currentSettings.aiTextApiKey || '').trim() || CONFIG.aiEnabled);
        const imageConfigured = Boolean((this.aiImageApiKeyInput?.value || this.currentSettings.aiImageApiKey || '').trim() || CONFIG.aiEnabled);
        return `文本: ${textModel} · ${textConfigured ? '已配置' : '未配置'} ｜ 图片: ${imageModel} · ${imageConfigured ? '已配置' : '未配置'}`;
    }

    updateAIConfigSummary() {
        if (this.aiConfigSummary) {
            this.aiConfigSummary.textContent = this.getAIConfigSummaryText();
        }
    }

    updateAIConfigCollapseUI() {
        const isCollapsed = Boolean(this.currentSettings.aiConfigCollapsed);
        this.aiConfigCard.classList.toggle('collapsed', isCollapsed);
        this.aiConfigToggleBtn.textContent = isCollapsed ? '展开' : '收起';
    }

    toggleAIConfigCard(forceValue) {
        const nextValue = typeof forceValue === 'boolean'
            ? forceValue
            : !this.currentSettings.aiConfigCollapsed;
        this.currentSettings.aiConfigCollapsed = nextValue;
        this.saveSettings();
        this.updateAIConfigSummary();
        this.updateAIConfigCollapseUI();
    }

    switchAIConfigTab(tabName) {
        this.aiConfigTabs.querySelectorAll('.ai-config-tab').forEach((tab) => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });

        this.assistantPanel.querySelectorAll('.ai-config-panel').forEach((panel) => {
            panel.classList.toggle('active', panel.dataset.panel === tabName);
        });
    }

    getAIConfigPayload() {
        return {
            text: {
                base_url: (this.aiTextBaseUrlInput?.value || this.currentSettings.aiTextBaseUrl || '').trim(),
                model: (this.aiTextModelInput?.value || this.currentSettings.aiTextModel || '').trim(),
                api_key: (this.aiTextApiKeyInput?.value || this.currentSettings.aiTextApiKey || '').trim()
            },
            image: {
                base_url: (this.aiImageBaseUrlInput?.value || this.currentSettings.aiImageBaseUrl || '').trim(),
                model: (this.aiImageModelInput?.value || this.currentSettings.aiImageModel || '').trim(),
                api_key: (this.aiImageApiKeyInput?.value || this.currentSettings.aiImageApiKey || '').trim()
            }
        };
    }

    hasAICapability(capability = 'any') {
        const config = this.getAIConfigPayload();
        const hasText = Boolean(config.text.api_key || CONFIG.aiEnabled);
        const hasImage = Boolean(config.image.api_key || CONFIG.aiEnabled);

        if (capability === 'text') {
            return hasText;
        }
        if (capability === 'image') {
            return hasImage;
        }
        return hasText || hasImage;
    }

    saveAIConfig() {
        this.currentSettings.aiTextBaseUrl = this.aiTextBaseUrlInput.value.trim();
        this.currentSettings.aiTextModel = this.aiTextModelInput.value.trim();
        this.currentSettings.aiTextApiKey = this.aiTextApiKeyInput.value.trim();
        this.currentSettings.aiImageBaseUrl = this.aiImageBaseUrlInput.value.trim();
        this.currentSettings.aiImageModel = this.aiImageModelInput.value.trim();
        this.currentSettings.aiImageApiKey = this.aiImageApiKeyInput.value.trim();
        this.saveSettings();
        this.updateAIConfigSummary();
        this.toggleAIConfigCard(true);
        this.updateAssistantAvailability();
        this.updateHeaderSummary();
        this.showToast('AI 配置已保存到本地', 'success');
    }

    resetAIConfig() {
        this.currentSettings.aiTextBaseUrl = '';
        this.currentSettings.aiTextModel = '';
        this.currentSettings.aiTextApiKey = '';
        this.currentSettings.aiImageBaseUrl = '';
        this.currentSettings.aiImageModel = '';
        this.currentSettings.aiImageApiKey = '';
        this.saveSettings();
        this.populateAISettings();
        this.toggleAIConfigCard(false);
        this.updateAssistantAvailability();
        this.updateHeaderSummary();
        this.showToast('AI 配置已恢复默认', 'success');
    }

    updateHeaderSummary() {
        const hasLocalConfig = Boolean(
            (this.currentSettings.aiTextApiKey || '').trim() ||
            (this.currentSettings.aiImageApiKey || '').trim()
        );
        const hasAvailableAI = this.hasAICapability();
        this.summaryTheme.textContent = CONFIG.themes[this.currentSettings.theme]?.name || '默认主题';
        this.summaryCodeTheme.textContent = CONFIG.codeThemes[this.currentSettings.codeTheme]?.name || 'GitHub';
        this.summaryFontSize.textContent = CONFIG.fontSizes[this.currentSettings.fontSize]?.name?.replace(/\(.+\)/, '') || '中号字体';
        this.summaryPreviewMode.textContent = this.previewMode === 'mobile' ? '移动端' : '桌面端';
        this.summaryAIStatus.textContent = hasLocalConfig ? '本地配置' : (CONFIG.aiEnabled ? '服务端默认' : '未配置');
        this.summaryAIChip.classList.toggle('is-ready', hasAvailableAI);
        this.summaryAIChip.classList.toggle('is-offline', !hasAvailableAI);

        if (this.assistantAIStatusBadge) {
            this.assistantAIStatusBadge.textContent = hasLocalConfig ? 'AI 本地配置已启用' : (CONFIG.aiEnabled ? 'AI 已连接' : '未配置 OPENAI_API_KEY');
            this.assistantAIStatusBadge.classList.toggle('is-ready', hasAvailableAI);
            this.assistantAIStatusBadge.classList.toggle('is-offline', !hasAvailableAI);
        }
    }

    showToast(message, type = 'success') {
        this.toast.textContent = message;
        this.toast.className = `toast show ${type}`;

        clearTimeout(this.toastTimer);
        this.toastTimer = setTimeout(() => {
            this.toast.classList.remove('show');
        }, 2600);
    }

    decodeBase64Utf8(base64String) {
        const binary = window.atob(base64String);
        const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
        return new TextDecoder().decode(bytes);
    }

    decodePemToArrayBuffer(pemText) {
        const base64 = (pemText || '')
            .replace(/-----BEGIN PUBLIC KEY-----/g, '')
            .replace(/-----END PUBLIC KEY-----/g, '')
            .replace(/\s+/g, '');
        const binary = window.atob(base64);
        return Uint8Array.from(binary, (char) => char.charCodeAt(0)).buffer;
    }

    encodeArrayBufferBase64(buffer) {
        const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
        let binary = '';

        bytes.forEach((byte) => {
            binary += String.fromCharCode(byte);
        });

        return window.btoa(binary);
    }

    escapeHTML(value) {
        return value
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.md2we = new MD2WE();
});
