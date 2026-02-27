/**
 * MD2HTML - Markdown 转微信公众号 HTML 工具
 */

class MD2HTML {
    constructor() {
        this.currentSettings = {
            theme: 'default',
            codeTheme: 'github',
            fontSize: 'medium',
            background: 'warm'
        };

        this.previewMode = 'mobile'; // 'pc' or 'mobile' - 默认移动端预览
        this.debounceTimer = null;
        this.isDragging = false;
        this.init();
    }

    init() {
        this.bindElements();
        this.bindEvents();
        this.loadSavedContent();
        this.loadSavedSettings();
        this.updateStats();
        this.updatePreview();
        this.initResizer();
        // 设置默认预览模式为移动端
        this.togglePreviewMode(this.previewMode);
    }

    bindElements() {
        // Main elements
        this.editor = document.getElementById('editor');
        this.preview = document.getElementById('preview');
        this.previewWrapper = document.querySelector('.preview-wrapper');
        this.editorPanel = document.getElementById('editorPanel');
        this.previewPanel = document.getElementById('previewPanel');
        this.resizer = document.getElementById('resizer');

        // Buttons
        this.settingsBtn = document.getElementById('settingsBtn');
        this.copyBtn = document.getElementById('copyBtn');
        this.clearBtn = document.getElementById('clearBtn');
        this.downloadBtn = document.getElementById('downloadBtn');

        // Settings panel
        this.settingsOverlay = document.getElementById('settingsOverlay');
        this.settingsPanel = document.getElementById('settingsPanel');
        this.closeSettings = document.getElementById('closeSettings');

        // Preview mode toggle
        this.previewModeToggle = document.getElementById('previewModeToggle');

        // Settings containers
        this.themeGrid = document.getElementById('themeGrid');
        this.codeThemeGrid = document.getElementById('codeThemeGrid');
        this.fontSizeOptions = document.getElementById('fontSizeOptions');
        this.backgroundOptions = document.getElementById('backgroundOptions');

        // Stats
        this.charCount = document.getElementById('charCount');
        this.totalCount = document.getElementById('totalCount');
        this.lineCount = document.getElementById('lineCount');

        // Others
        this.currentThemeBadge = document.getElementById('currentThemeBadge');
        this.toast = document.getElementById('toast');
        this.copyApiEndpoint = document.getElementById('copyApiEndpoint');
        this.apiExample = document.getElementById('apiExample');
    }

    bindEvents() {
        // Editor input
        this.editor.addEventListener('input', () => {
            this.saveContent();
            this.updateStats();
            this.debounceUpdate();
        });

        // Button events
        this.settingsBtn.addEventListener('click', () => this.openSettings());
        this.copyBtn.addEventListener('click', () => this.copyHTML());
        this.clearBtn.addEventListener('click', () => this.clearEditor());
        this.downloadBtn.addEventListener('click', () => this.downloadHTML());

        // Settings panel
        this.closeSettings.addEventListener('click', () => this.closeSettingsPanel());
        this.settingsOverlay.addEventListener('click', () => this.closeSettingsPanel());

        // Theme selection
        this.themeGrid.addEventListener('click', (e) => {
            const card = e.target.closest('.theme-card');
            if (card) {
                this.selectTheme(card.dataset.theme);
            }
        });

        // Code theme selection
        this.codeThemeGrid.addEventListener('click', (e) => {
            const item = e.target.closest('.code-theme-item');
            if (item) {
                this.selectCodeTheme(item.dataset.codeTheme);
            }
        });

        // Font size selection
        this.fontSizeOptions.addEventListener('click', (e) => {
            const option = e.target.closest('.radio-option');
            if (option) {
                this.selectFontSize(option.dataset.fontSize);
            }
        });

        // Background selection
        this.backgroundOptions.addEventListener('click', (e) => {
            const option = e.target.closest('.radio-option');
            if (option) {
                this.selectBackground(option.dataset.background);
            }
        });

        // Preview mode toggle
        this.previewModeToggle.addEventListener('click', (e) => {
            const btn = e.target.closest('.mode-btn');
            if (btn) {
                this.togglePreviewMode(btn.dataset.mode);
            }
        });

        // API endpoint copy
        this.copyApiEndpoint.addEventListener('click', () => {
            const endpoint = window.location.origin + '/api/convert';
            navigator.clipboard.writeText(endpoint).then(() => {
                this.showToast('API 端点已复制', 'success');
            });
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + S - Copy HTML
            if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                e.preventDefault();
                this.copyHTML();
            }
            // Ctrl/Cmd + , - Open settings
            if ((e.ctrlKey || e.metaKey) && e.key === ',') {
                e.preventDefault();
                this.openSettings();
            }
            // Esc - Close settings
            if (e.key === 'Escape') {
                this.closeSettingsPanel();
            }
        });

        // Tab key in editor
        this.editor.addEventListener('keydown', (e) => {
            if (e.key === 'Tab') {
                e.preventDefault();
                const start = this.editor.selectionStart;
                const end = this.editor.selectionEnd;
                this.editor.value = this.editor.value.substring(0, start) + '    ' + this.editor.value.substring(end);
                this.editor.selectionStart = this.editor.selectionEnd = start + 4;
                this.saveContent();
                this.debounceUpdate();
            }
        });

        // Sync scroll between editor and preview
        this.initSyncScroll();
    }

    // Initialize synchronized scrolling
    initSyncScroll() {
        let isEditorScrolling = false;
        let isPreviewScrolling = false;

        // Editor scroll -> Preview scroll
        this.editor.addEventListener('scroll', () => {
            if (isPreviewScrolling) return;
            isEditorScrolling = true;

            const editorScrollRatio = this.editor.scrollTop / (this.editor.scrollHeight - this.editor.clientHeight);
            const previewScrollTop = editorScrollRatio * (this.previewWrapper.scrollHeight - this.previewWrapper.clientHeight);

            this.previewWrapper.scrollTop = previewScrollTop;

            requestAnimationFrame(() => {
                isEditorScrolling = false;
            });
        });

        // Preview scroll -> Editor scroll
        this.previewWrapper.addEventListener('scroll', () => {
            if (isEditorScrolling) return;
            isPreviewScrolling = true;

            const previewScrollRatio = this.previewWrapper.scrollTop / (this.previewWrapper.scrollHeight - this.previewWrapper.clientHeight);
            const editorScrollTop = previewScrollRatio * (this.editor.scrollHeight - this.editor.clientHeight);

            this.editor.scrollTop = editorScrollTop;

            requestAnimationFrame(() => {
                isPreviewScrolling = false;
            });
        });
    }

    // Initialize resizer
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
            const newWidth = Math.max(320, Math.min(startWidth + delta, window.innerWidth * 0.5));
            this.editorPanel.style.flex = 'none';
            this.editorPanel.style.width = newWidth + 'px';
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

        // Touch support
        this.resizer.addEventListener('touchstart', startDrag, { passive: true });
        document.addEventListener('touchmove', doDrag, { passive: true });
        document.addEventListener('touchend', endDrag);
    }

    // Debounce update
    debounceUpdate() {
        clearTimeout(this.debounceTimer);
        this.debounceTimer = setTimeout(() => {
            this.updatePreview();
        }, 250);
    }

    // Update statistics
    updateStats() {
        const text = this.editor.value;

        // Character count (excluding spaces)
        const chars = text.replace(/\s/g, '').length;

        // Total characters
        const total = text.length;

        // Line count
        const lines = text ? text.split('\n').length : 0;

        this.charCount.textContent = chars;
        this.totalCount.textContent = total;
        this.lineCount.textContent = lines;
    }

    // Update preview
    async updatePreview() {
        const markdown = this.editor.value;

        if (!markdown.trim()) {
            this.preview.innerHTML = `
                <section style="padding: 60px 40px; text-align: center;">
                    <div style="color: #A1A1AA; font-size: 14px; margin-bottom: 8px;">
                        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="opacity: 0.5; margin-bottom: 16px;">
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                            <circle cx="12" cy="12" r="3"></circle>
                        </svg>
                        <p style="margin: 0; color: #71717A;">在左侧输入 Markdown 内容</p>
                        <p style="margin: 4px 0 0; color: #A1A1AA; font-size: 12px;">实时预览将在此显示</p>
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
                    markdown: markdown,
                    theme: this.currentSettings.theme,
                    code_theme: this.currentSettings.codeTheme,
                    font_size: this.currentSettings.fontSize,
                    background: this.currentSettings.background
                })
            });

            const data = await response.json();

            if (data.success) {
                this.preview.innerHTML = data.html;
            } else {
                this.preview.innerHTML = `
                    <section style="padding: 24px; color: #EF4444;">
                        <p style="margin: 0;">转换错误: ${data.error}</p>
                    </section>
                `;
            }
        } catch (error) {
            console.error('转换失败:', error);
            this.preview.innerHTML = `
                <section style="padding: 24px; color: #EF4444;">
                    <p style="margin: 0;">网络错误，请检查服务是否正常运行</p>
                </section>
            `;
        }
    }

    // Select theme
    selectTheme(theme) {
        this.currentSettings.theme = theme;
        this.updateThemeUI();
        this.saveSettings();
        this.updatePreview();
        this.updateApiExample();

        const themeName = CONFIG.themes[theme]?.name || theme;
        this.currentThemeBadge.textContent = themeName;
        this.showToast(`已切换到「${themeName}」`, 'success');
    }

    // Update theme UI
    updateThemeUI() {
        // Update theme cards
        this.themeGrid.querySelectorAll('.theme-card').forEach(card => {
            card.classList.toggle('active', card.dataset.theme === this.currentSettings.theme);
        });

        // Update code theme items
        this.codeThemeGrid.querySelectorAll('.code-theme-item').forEach(item => {
            item.classList.toggle('active', item.dataset.codeTheme === this.currentSettings.codeTheme);
        });

        // Update font size options
        this.fontSizeOptions.querySelectorAll('.radio-option').forEach(option => {
            option.classList.toggle('active', option.dataset.fontSize === this.currentSettings.fontSize);
        });

        // Update background options
        this.backgroundOptions.querySelectorAll('.radio-option').forEach(option => {
            option.classList.toggle('active', option.dataset.background === this.currentSettings.background);
        });
    }

    // Select code theme
    selectCodeTheme(codeTheme) {
        this.currentSettings.codeTheme = codeTheme;
        this.updateCodeThemeLink(codeTheme);
        this.updateThemeUI();
        this.saveSettings();
        this.updatePreview();
        this.updateApiExample();
        this.showToast(`代码高亮已切换到「${CONFIG.codeThemes[codeTheme].name}」`, 'success');
    }

    // Update code theme CSS link
    updateCodeThemeLink(codeTheme) {
        const link = document.getElementById('codeThemeLink');
        if (link) {
            link.href = `https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/${codeTheme}.min.css`;
        }
    }

    // Select font size
    selectFontSize(fontSize) {
        this.currentSettings.fontSize = fontSize;
        this.updateThemeUI();
        this.saveSettings();
        this.updatePreview();
        this.updateApiExample();
        this.showToast(`字体大小已切换到「${CONFIG.fontSizes[fontSize].name}」`, 'success');
    }

    // Select background
    selectBackground(background) {
        this.currentSettings.background = background;
        this.updateThemeUI();
        this.saveSettings();
        this.updatePreview();
        this.updateApiExample();
        this.showToast(`背景已切换到「${CONFIG.backgrounds[background].name}」`, 'success');
    }

    // Update API example with current settings
    updateApiExample() {
        const example = {
            markdown: "# Hello World",
            theme: this.currentSettings.theme,
            code_theme: this.currentSettings.codeTheme,
            font_size: this.currentSettings.fontSize,
            background: this.currentSettings.background
        };
        this.apiExample.textContent = JSON.stringify(example, null, 2);
    }

    // Toggle preview mode
    togglePreviewMode(mode) {
        this.previewMode = mode;

        // Update toggle buttons
        this.previewModeToggle.querySelectorAll('.mode-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.mode === mode);
        });

        // Update preview wrapper
        if (mode === 'mobile') {
            this.previewWrapper.classList.add('mobile-mode');
        } else {
            this.previewWrapper.classList.remove('mobile-mode');
        }
    }

    // Open settings
    openSettings() {
        this.settingsOverlay.classList.add('active');
        this.settingsPanel.classList.add('active');
        this.updateThemeUI();
    }

    // Close settings
    closeSettingsPanel() {
        this.settingsOverlay.classList.remove('active');
        this.settingsPanel.classList.remove('active');
    }

    // Copy HTML
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
        } catch (err) {
            try {
                await navigator.clipboard.writeText(html);
                this.showToast('已复制（纯文本格式）', 'success');
            } catch (e) {
                this.showToast('复制失败，请手动复制', 'error');
            }
        }
    }

    // Clear editor
    clearEditor() {
        if (this.editor.value && !confirm('确定要清空内容吗？')) {
            return;
        }
        this.editor.value = '';
        localStorage.removeItem('md2html_content');
        this.updateStats();
        this.updatePreview();
        this.showToast('内容已清空', 'success');
    }

    // Download HTML
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

    // Save content to local storage
    saveContent() {
        localStorage.setItem('md2html_content', this.editor.value);
    }

    // Load saved content
    loadSavedContent() {
        const saved = localStorage.getItem('md2html_content');

        if (saved) {
            this.editor.value = saved;
        } else {
            this.editor.value = `# Markdown 转微信公众号工具

这是一个简单易用的 Markdown 转换工具，专为微信公众号文章排版设计。

## 功能特点

- **丰富的主题** - 提供多种精美主题，满足不同风格需求
- **实时预览** - 边写边看，所见即所得
- **一键复制** - 直接复制到微信公众号编辑器
- **API 支持** - 支持通过 API 调用进行批量转换

## 代码示例

\`\`\`python
def hello_world():
    print("Hello, WeChat!")
\`\`\`

## 表格示例

| 功能 | 状态 |
|------|------|
| Markdown 解析 | 已支持 |
| 主题切换 | 已支持 |
| API 调用 | 已支持 |

> 点击右上角「设置」按钮，可以切换主题、字体大小等选项。

---

开始你的创作吧！`;
        }
    }

    // Save settings
    saveSettings() {
        localStorage.setItem('md2html_settings', JSON.stringify(this.currentSettings));
    }

    // Load saved settings
    loadSavedSettings() {
        const saved = localStorage.getItem('md2html_settings');

        if (saved) {
            try {
                const settings = JSON.parse(saved);
                this.currentSettings = { ...this.currentSettings, ...settings };
            } catch (e) {
                console.error('加载设置失败:', e);
            }
        }

        // Update theme badge
        const themeName = CONFIG.themes[this.currentSettings.theme]?.name || '默认主题';
        this.currentThemeBadge.textContent = themeName;

        // Restore code theme
        this.updateCodeThemeLink(this.currentSettings.codeTheme);

        // Update API example with current settings
        this.updateApiExample();
    }

    // Show toast notification
    showToast(message, type = 'success') {
        this.toast.textContent = message;
        this.toast.className = 'toast show ' + type;

        setTimeout(() => {
            this.toast.classList.remove('show');
        }, 2500);
    }
}

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    window.md2html = new MD2HTML();
});
