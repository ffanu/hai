// Constants for parameter presets and DOM elements
const PARAMETER_PRESETS = {
    precise: { temperature: 0 },
    balanced: { temperature: 0.5 },
    creative: { temperature: 1 }
};

// Add these default tag constants
let START_TAG = '<think>';  // Default start tag
let END_TAG = '</think>';     // Default end tag


// Add this at the top with other constants
const DEFAULT_END_TAG = ['</think>', '<|end_of_thought|>']; // Add any other common end tags here

const allowedFileTypes = [
    'text/plain', 
    'text/csv',
    'text/comma-separated-values',
    'application/csv',
    'application/vnd.ms-excel',
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'image/jpeg',
    'image/png',
    'image/webp'
];
const HAI_MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024;
const HAI_INLINE_IMAGE_TARGET_BYTES = 1536 * 1024;
const HAI_MAX_ATTACHMENTS = 3;
const HAI_SUPPORTED_DOCUMENT_EXTENSIONS = ['.pdf', '.txt', '.csv', '.docx', '.xlsx'];
const HAI_SUPPORTED_IMAGE_MIME = ['image/png', 'image/jpeg', 'image/webp'];
const HAI_LIBRARY_GROUNDING_LIMIT = 3;
const HAI_ICON_VERSION = '20261007-phase324';
const HAI_STREAM_STALL_FINALIZE_MS = 24000;
const HAI_LIBRARY_GROUNDING_STORAGE_KEY = 'hai_library_grounding_mode';
const HAI_LIBRARY_CONTEXT_STORAGE_KEY = 'hai_library_context_mode';
const HAI_PDF_WORKER_SRC = document.querySelector('meta[name="hai-pdf-worker-src"]')?.content || '/static/js/pdf.worker.min.js';

if (window.pdfjsLib) {
    window.pdfjsLib.GlobalWorkerOptions = window.pdfjsLib.GlobalWorkerOptions || {};
    window.pdfjsLib.GlobalWorkerOptions.workerSrc = HAI_PDF_WORKER_SRC;
}

function haiIconSrc(iconName) {
    return `/static/images/icons/${iconName}.svg?v=${HAI_ICON_VERSION}`;
}

function haiIconImg(iconName, altText = '') {
    return `<img src="${haiIconSrc(iconName)}" alt="${altText}" class="icon-svg">`;
}

// DOM element references
const userInput = document.getElementById('user-input');
const submitButton = document.getElementById('submit-button');
const uploadFiles = document.getElementById('upload-files');
const composerForm = document.querySelector('.bottom-panel form');
const bottomPanel = document.querySelector('.bottom-panel');
const chatWrapper = document.querySelector('.middle-panel');
const chatMessages = document.getElementById('chat-messages');
const selectItems = document.getElementById('select-items');
const selectSelected = document.querySelector('.select-selected');
const warningMessage = document.getElementById('warning-message');
const haiStatus = document.getElementById('hai-status');
const quickPromptRow = document.querySelector('.hai-quick-row');
const attachmentTray = document.getElementById('hai-attachment-tray');
const queueStatus = document.getElementById('hai-queue-status');
const settingsPopup = document.getElementById('settings-popup');
const apiKeyInput = document.getElementById('api-key');
const baseUrlInput = document.getElementById('base-url');
const chatHistory = document.getElementById('chat-history');
const historySearchInput = document.getElementById('history-search');
const haiLibraryPanel = document.getElementById('hai-library-panel');
const haiLibraryList = document.getElementById('hai-library-list');
const haiLibraryCount = document.getElementById('hai-library-count');
const haiLibrarySearch = document.getElementById('hai-library-search');
const haiLibraryUploadButton = document.getElementById('hai-library-upload');
const haiLibraryGroundingToggle = document.getElementById('hai-library-grounding-toggle');
const haiLibraryContextToggle = document.getElementById('hai-library-context-toggle');
const newChatButton = document.getElementById('new-chat');
const renameChatButton = document.getElementById('rename-chat');
const copyChatLinkButton = document.getElementById('copy-chat-link');
const haiTopHeading = document.getElementById('hai-top-heading');
const haiTopSubtitle = document.getElementById('hai-top-subtitle');
const haiConnectionPill = document.getElementById('hai-connection-pill');
const leftSide = document.querySelector('.left-side');
const closeSidebarBtn = document.getElementById('close-sidebar');
const rightSide = document.querySelector('.right-side');
const dropZone = document.querySelector('.middle-panel');
const artifactPanel = document.getElementById('hai-artifact-panel');
const artifactBackdrop = document.getElementById('hai-artifact-backdrop');
const artifactTitle = document.getElementById('hai-artifact-title');
const artifactBody = document.getElementById('hai-artifact-body');
const artifactCloseButton = document.getElementById('hai-artifact-close');
const artifactCopyButton = document.getElementById('hai-artifact-copy');
const artifactDownloadLink = document.getElementById('hai-artifact-download');
const settingsCloseButton = document.getElementById('settings-close');
const settingsSaveButton = document.getElementById('settings-save');
const userSettingButton = document.getElementById('user-setting');
const additionalSettingButton = document.getElementById('additional-setting');
const additionalSettingsCloseButton = document.getElementById('additional-settings-close');
const additionalSettingsSaveButton = document.getElementById('additional-settings-save');
const fileInput = document.createElement('input');
const libraryFileInput = document.createElement('input');
const db = new Dexie('chatDatabase');
fileInput.type = 'file';
fileInput.accept = 'image/png,image/jpeg,image/webp,text/plain,text/csv,application/csv,application/pdf,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,.txt,.csv,.pdf,.docx,.xlsx';
fileInput.style.display = 'none';
fileInput.multiple = true;
document.body.appendChild(fileInput);
libraryFileInput.type = 'file';
libraryFileInput.accept = 'text/plain,text/csv,application/csv,application/pdf,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,.txt,.csv,.pdf,.docx,.xlsx';
libraryFileInput.style.display = 'none';
document.body.appendChild(libraryFileInput);

// Global state variables
let MODEL_PARAMETERS = {};
let SYSTEM_CONTENT = '';
let conversationHistory = [];
let selectedModel = 'harmonika-ai';
let newConversationStarted = false;
let conversations = {};
let currentConversationId = null;
let currentController = null;
let currentArtifactPayload = null;
let pendingAttachment = null;
let pendingAttachments = [];
let queuedComposerMessage = null;
let isDispatchingQueuedMessage = false;
let isPrivateChat = false;
let hasImageAttached = false;
let isDeepQueryMode = false;
let streamStartTime = null;
let streamDuration = null;
let hasScrolledForThinkBlock = false;
let serverHistoryReady = false;
let serverHistorySyncTimer = null;
let isPushingServerHistory = false;
let serverHistoryLastUpdated = 0;
let historySyncDegradedNotified = false;
let attachmentDragDepth = 0;
let scrollBottomButton = null;
let autoScrollLockedToBottom = true;
let lastProgrammaticScrollAt = 0;
let haiLibraryDocuments = [];
let haiLibraryLoading = false;
let haiLibrarySearchResults = [];
let haiLibrarySearchQuery = '';
let haiLibrarySearchLoading = false;
let haiLibrarySearchTimer = null;
let haiLibraryGroundingMode = 'auto';
let haiLibraryContextMode = 'snippet';
const DELETED_CONVERSATIONS_KEY = 'haiDeletedConversations';
const HAI_MEMORY_KEY = 'haiMemoryItems';
const HAI_MEMORY_MAX_ITEMS = 12;

function updateComposerMetrics() {
    if (!bottomPanel) return;
    const rect = bottomPanel.getBoundingClientRect();
    const height = Math.max(72, Math.ceil(rect.height || 0));
    document.documentElement.style.setProperty('--hai-composer-height', `${height}px`);
}

if ('ResizeObserver' in window && bottomPanel) {
    const composerResizeObserver = new ResizeObserver(() => updateComposerMetrics());
    composerResizeObserver.observe(bottomPanel);
}

window.addEventListener('resize', updateComposerMetrics, { passive: true });
window.requestAnimationFrame(updateComposerMetrics);

const CHAT_PATH_RE = /^\/c\/([A-Za-z0-9._-]+)\/?$/;
function urlConversationId() {
    const match = window.location.pathname.match(CHAT_PATH_RE);
    return match ? decodeURIComponent(match[1]) : '';
}
function setConversationUrl(id, replace = false) {
    const next = id ? `/c/${encodeURIComponent(id)}` : '/';
    if (window.location.pathname === next) return;
    window.history[replace ? 'replaceState' : 'pushState']({ conversationId: id || '' }, '', next);
}
function makeConversationId() {
    return Date.now().toString();
}

async function loadHaiMemoryItems() {
    try {
        const record = await db.settings.get(HAI_MEMORY_KEY);
        return Array.isArray(record?.value) ? record.value : [];
    } catch (error) {
        console.warn('Could not load HAI memory:', error);
        return [];
    }
}

async function saveHaiMemoryItems(items) {
    try {
        await db.settings.put({ key: HAI_MEMORY_KEY, value: items.slice(0, HAI_MEMORY_MAX_ITEMS) });
    } catch (error) {
        console.warn('Could not save HAI memory:', error);
    }
}

function extractMemoryCandidates(text = '') {
    const value = String(text || '').replace(/\s+/g, ' ').trim();
    if (!value || value.length > 500) return [];
    const candidates = [];
    const rules = [
        { re: /\b(?:nama saya|namaku|saya bernama)\s+([^.,!?]{2,60})/i, make: m => `Nama pengguna: ${m[1].trim()}` },
        { re: /\b(?:panggil saya|panggil aku)\s+([^.,!?]{2,40})/i, make: m => `Panggilan pengguna: ${m[1].trim()}` },
        { re: /\b(?:saya suka|aku suka|saya senang dengan)\s+([^.,!?]{2,90})/i, make: m => `Preferensi/minat pengguna: ${m[1].trim()}` },
        { re: /\b(?:saya tidak suka|aku tidak suka)\s+([^.,!?]{2,90})/i, make: m => `Hal yang tidak disukai pengguna: ${m[1].trim()}` },
        { re: /\b(?:usaha saya|bisnis saya)\s+([^.,!?]{2,100})/i, make: m => `Usaha/bisnis pengguna: ${m[1].trim()}` },
        { re: /\b(?:pekerjaan saya|saya bekerja sebagai|profesi saya)\s+([^.,!?]{2,100})/i, make: m => `Pekerjaan/profesi pengguna: ${m[1].trim()}` },
        { re: /\b(?:saya tinggal di|domisili saya di)\s+([^.,!?]{2,80})/i, make: m => `Domisili pengguna: ${m[1].trim()}` },
        { re: /\b(?:gunakan bahasa|jawab pakai bahasa)\s+([^.,!?]{2,60})/i, make: m => `Preferensi bahasa jawaban: ${m[1].trim()}` }
    ];
    rules.forEach(rule => {
        const match = value.match(rule.re);
        if (match) candidates.push(rule.make(match));
    });
    return candidates
        .map(item => item.replace(/\s+/g, ' ').trim())
        .filter(item => item.length >= 8 && item.length <= 180);
}

async function rememberFromUserText(text = '') {
    const candidates = extractMemoryCandidates(text);
    if (!candidates.length) return;
    const existing = await loadHaiMemoryItems();
    const now = Date.now();
    const byKey = new Map(existing.map(item => [String(item.text || '').toLowerCase(), item]));
    candidates.forEach(text => {
        byKey.set(text.toLowerCase(), { text, updated: now });
    });
    const next = [...byKey.values()]
        .filter(item => item?.text)
        .sort((a, b) => Number(b.updated || 0) - Number(a.updated || 0))
        .slice(0, HAI_MEMORY_MAX_ITEMS);
    await saveHaiMemoryItems(next);
}

function userTextForMemory(content) {
    if (typeof content === 'string') return content;
    if (Array.isArray(content)) return userTextForIntent(content);
    if (content && typeof content === 'object') return content.content || content.text || content.raw || '';
    return '';
}

function attachmentSummaryText(attachments = []) {
    const list = Array.isArray(attachments) ? attachments : (attachments ? [attachments] : []);
    return list
        .map(attachment => {
            const name = attachment?.name || 'Lampiran';
            const type = attachment?.type === 'image' ? 'gambar' : 'dokumen';
            const size = attachment?.sizeLabel || attachment?.mime || '';
            return `- ${name}${size ? ` (${type}, ${size})` : ` (${type})`}`;
        })
        .join('\n');
}

function plainTextFromMessageContent(content, message = null) {
    if (typeof content === 'string') return content;
    if (Array.isArray(content)) return userTextForIntent(content);
    if (content && typeof content === 'object') {
        const text = content.raw || content.content || content.text || message?.raw || '';
        const attachments = content.attachments || (content.attachment ? [content.attachment] : []);
        const attachmentText = attachmentSummaryText(attachments);
        return [text, attachmentText ? `Lampiran:\n${attachmentText}` : ''].filter(Boolean).join('\n\n');
    }
    if (message?.raw) return message.raw;
    return '';
}

async function getHaiMemoryContext() {
    const items = await loadHaiMemoryItems();
    return items
        .slice(0, HAI_MEMORY_MAX_ITEMS)
        .map(item => `- ${String(item.text || '').trim()}`)
        .filter(Boolean)
        .join('\n');
}

const HAI_WELCOME_HTML = `
    <div class="hai-empty-state">
        <img src="/static/images/hai-logo.png" alt="">
        <h1>Selamat datang di Harmonika AI</h1>
        <p>Tempat bertanya, menulis, mencari ide, membaca dokumen, dan membuat visual.</p>
        <div class="hai-capabilities" aria-label="Kemampuan Harmonika AI">
            <span><i class="fa fa-comments-o" aria-hidden="true"></i> Chat umum</span>
            <span><i class="fa fa-globe" aria-hidden="true"></i> Web</span>
            <span><i class="fa fa-paperclip" aria-hidden="true"></i> File</span>
            <span><i class="fa fa-picture-o" aria-hidden="true"></i> Gambar</span>
        </div>
        <div class="hai-suggestions">
            <button type="button" data-hai-prompt="Jelaskan dengan bahasa sederhana: ">
                <strong>Jelaskan sesuatu</strong>
            </button>
            <button type="button" data-hai-prompt="Buatkan ide dan rencana untuk: ">
                <strong>Buat ide</strong>
            </button>
            <button type="button" data-hai-prompt="Bantu debug kode berikut dan jelaskan solusinya: ">
                <strong>Bantu coding</strong>
            </button>
            <button type="button" data-hai-intent="image" data-hai-prompt="Buatkan gambar dengan deskripsi: ">
                <strong>Buat gambar</strong>
            </button>
        </div>
    </div>`;

function showHaiWelcome() {
    if (!chatMessages.children.length) {
        chatMessages.innerHTML = HAI_WELCOME_HTML;
    }
    updateQuickPromptVisibility();
}

function ensureHaiWelcomeWhenEmpty() {
    if (!currentController && chatMessages && chatMessages.childElementCount === 0) {
        showHaiWelcome();
    }
    updateQuickPromptVisibility();
}

function updateQuickPromptVisibility() {
    const hasRenderedMessages = Boolean(chatMessages?.querySelector('.user-message-container, .assistant-message-container'));
    const hasWelcome = Boolean(chatMessages?.querySelector('.hai-empty-state'));
    const showQuickPrompts = Boolean(hasWelcome && !hasRenderedMessages && !currentController);
    document.body.classList.toggle('hai-chat-empty', showQuickPrompts);
    document.body.classList.toggle('hai-chat-active', !showQuickPrompts);
    quickPromptRow?.setAttribute('aria-hidden', showQuickPrompts ? 'false' : 'true');
    syncTopbarTitle(showQuickPrompts);
}

function syncTopbarTitle(forceWelcome = false) {
    if (!haiTopHeading || !haiTopSubtitle) return;
    const hasMessages = Boolean(chatMessages?.querySelector('.user-message-container, .assistant-message-container')) || conversationHistory.length > 0;
    const activeConversation = currentConversationId ? conversations[currentConversationId] : null;
    const activeTitle = cleanConversationTitle(activeConversation?.title || 'Chat Baru');
    const showConversationTitle = Boolean(!forceWelcome && currentConversationId && hasMessages);

    if (showConversationTitle) {
        const title = activeTitle === 'Chat Baru' ? 'Percakapan baru' : activeTitle;
        haiTopHeading.textContent = title;
        haiTopSubtitle.textContent = 'Percakapan aktif';
        document.title = `${title} · Harmonika AI`;
    } else {
        haiTopHeading.textContent = 'Harmonika AI';
        haiTopSubtitle.textContent = 'Asisten pintar untuk ide, belajar, kerja, coding, dan gambar.';
        document.title = 'Harmonika AI';
    }
}

function setHaiStatus(message = '', type = 'info') {
    if (!haiStatus) return;
    haiStatus.textContent = message || '';
    haiStatus.dataset.statusType = type || 'info';
    if (haiConnectionPill && haiConnectionPill.dataset.state === 'live') {
        haiConnectionPill.dataset.intent = type === 'image' ? 'image' : 'text';
    }
    haiStatus.classList.toggle('is-visible', Boolean(message));
    ['info', 'image', 'error', 'queue', 'stopping', 'success'].forEach(statusType => {
        haiStatus.classList.toggle(`is-${statusType}`, type === statusType);
    });
}

const HAI_CONNECTION_STATES = {
    ready: 'Siap',
    live: 'Realtime',
    reconnecting: 'Menyambung ulang',
    replay: 'Dipulihkan',
    history: 'Riwayat lokal',
    stopped: 'Dihentikan',
    error: 'Gangguan'
};

function setHaiConnectionState(state = 'ready', label = '') {
    if (!haiConnectionPill) return;
    const normalized = Object.prototype.hasOwnProperty.call(HAI_CONNECTION_STATES, state) ? state : 'ready';
    const text = label || HAI_CONNECTION_STATES[normalized] || HAI_CONNECTION_STATES.ready;
    haiConnectionPill.dataset.state = normalized;
    haiConnectionPill.dataset.intent = (
        /gambar|kanvas|render|desain/i.test(text)
        || haiStatus?.classList?.contains('is-image')
    ) ? 'image' : 'text';
    haiConnectionPill.setAttribute('aria-label', `Status koneksi Harmonika AI: ${text}`);
    const labelNode = haiConnectionPill.querySelector('.hai-connection-label');
    if (labelNode) labelNode.textContent = text;
}

const HAI_LIVE_STATUS = {
    connecting: ['Menyiapkan stream jawaban realtime…', 'info'],
    textThinking: ['Harmonika AI sedang berpikir…', 'info'],
    textWriting: ['Harmonika AI sedang mengetik jawaban…', 'info'],
    webReading: ['Mencari dan membaca referensi web…', 'info'],
    webWriting: ['Harmonika AI sedang menulis dengan referensi web…', 'info'],
    codeWriting: ['Harmonika AI sedang menulis kode…', 'info'],
    imagePreparing: ['Menyiapkan kanvas gambar…', 'image'],
    imageDesigning: ['Harmonika AI sedang mendesain gambar…', 'image'],
    imageRendering: ['Harmonika AI sedang merender gambar…', 'image'],
    queueReady: ['Pesan berikutnya sudah masuk antrean.', 'queue'],
    queueSending: ['Mengirim pesan dari antrean…', 'queue'],
    stoppingText: ['Menghentikan jawaban…', 'stopping'],
    stoppingImage: ['Menghentikan pembuatan gambar…', 'stopping'],
    stopped: ['Jawaban dihentikan.', 'stopping']
};

function setHaiLiveStatus(state, fallbackType = 'info') {
    if (['connecting', 'textThinking', 'textWriting', 'webReading', 'webWriting', 'codeWriting', 'imagePreparing', 'imageDesigning', 'imageRendering'].includes(state)) {
        setHaiConnectionState('live');
    } else if (state === 'stopped') {
        setHaiConnectionState('stopped');
    }
    const value = HAI_LIVE_STATUS[state];
    if (!value) {
        setHaiStatus(String(state || ''), fallbackType);
        return;
    }
    setHaiStatus(value[0], value[1]);
}

const HAI_IMAGE_INTENT_RE = /\b(buat|buatkan|membuat|bikin|generate|hasilkan|desain|rancang|render|ciptakan|gambarkan|create|draw)\b[^.?!\n]{0,120}\b(gambar|gamar|gamber|gmbar|image|foto|photo|poster|render|visual|ilustrasi|illustration|thumbnail|logo|banner|svg)\b/i;
const HAI_IMAGE_INTENT_RE2 = /\b(gambar|gamar|gamber|gmbar|image|foto|photo|poster|visual|ilustrasi|illustration|thumbnail|logo|banner|svg)\b[^.?!\n]{0,100}\b(buat|buatkan|membuat|bikin|generate|hasilkan|desain|ciptakan|create|draw)\b/i;
const HAI_IMAGE_CMD_RE = /^(gambar|image|foto|photo|poster|visual|ilustrasi|logo|banner|svg)\s*[:,-]/i;
const HAI_IMAGE_STEPS = [
    { title: 'Mengonversi prompt…', detail: 'Memahami deskripsi dan gaya visual yang diminta.' },
    { title: 'Merakit komposisi…', detail: 'Menyusun bentuk, tata letak, dan elemen utama.' },
    { title: 'Mewarnai piksel…', detail: 'Mengatur warna, kontras, dan detail visual.' },
    { title: 'Menyelesaikan render…', detail: 'Menyiapkan thumbnail gambar untuk ditampilkan.' }
];

function detectHaiIntent(text = '') {
    const value = String(text || '').trim();
    return {
        type: (HAI_IMAGE_INTENT_RE.test(value) || HAI_IMAGE_INTENT_RE2.test(value) || HAI_IMAGE_CMD_RE.test(value)) ? 'image' : 'text'
    };
}

function streamLivebarCopy(intent = 'text', phase = 'thinking') {
    const normalizedIntent = String(intent || 'text').toLowerCase() === 'image' ? 'image' : 'text';
    if (normalizedIntent === 'image') {
        return phase === 'image-rendering'
            ? {
                icon: 'image-rendering',
                title: 'Mendesain gambar',
                detail: 'Thumbnail akan muncul di chat saat render selesai.',
                tone: 'image'
            }
            : {
                icon: 'image-rendering',
                title: 'Menyiapkan gambar',
                detail: 'Membaca deskripsi dan menyusun komposisi.',
                tone: 'image'
            };
    }
    if (phase === 'code-writing') {
        return {
            icon: 'robot-typing',
            title: 'Menulis kode',
            detail: 'Blok kode akan tampil dengan highlight dan tombol salin.',
            tone: 'text'
        };
    }
    return phase === 'writing'
        ? {
            icon: 'robot-typing',
            title: 'Sedang mengetik',
            detail: 'Jawaban tampil bertahap.',
            tone: 'text'
        }
        : {
            icon: 'robot-typing',
            title: 'Menyiapkan jawaban',
            detail: 'Sebentar lagi mulai diketik.',
            tone: 'text'
        };
}

function ensureAssistantStreamLivebar(container, intent = 'text', phase = 'thinking') {
    if (!container) return null;
    const copy = streamLivebarCopy(intent, phase);
    let livebar = container.querySelector(':scope > .hai-stream-livebar');
    if (!livebar) {
        livebar = document.createElement('div');
        livebar.className = 'hai-stream-livebar';
        livebar.setAttribute('role', 'status');
        livebar.setAttribute('aria-live', 'polite');
        container.insertBefore(livebar, container.firstElementChild || null);
    }
    livebar.dataset.tone = copy.tone;
    livebar.dataset.phase = phase;
    livebar.innerHTML = `
        <span class="hai-stream-livebar-icon" aria-hidden="true">
            <img src="${haiIconSrc(copy.icon)}" alt="">
        </span>
        <span class="hai-stream-livebar-copy">
            <strong>${escapeHtml(copy.title)}</strong>
            <small>${escapeHtml(copy.detail)}</small>
        </span>
        <span class="hai-stream-livebar-dots" aria-hidden="true"><i></i><i></i><i></i></span>
    `;
    return livebar;
}

function renderAssistantTypingPlaceholder(messageElement) {
    if (!messageElement) return;
    messageElement.innerHTML = `
        <div class="hai-typing" role="status" aria-live="polite">
            <span class="hai-typing-robot hai-typing-robot-gif" aria-hidden="true">
                <img src="${haiIconSrc('robot-typing')}" alt="" class="hai-typing-robot-img">
                <span class="hai-robot-antenna"></span>
                <span class="hai-robot-face"><i></i><i></i></span>
                <span class="hai-robot-mouth"></span>
            </span>
            <span class="hai-typing-copy">
                <strong class="hai-typing-label">Menyiapkan jawaban</strong>
                <small class="hai-typing-sub">Jawaban akan muncul bertahap.</small>
                <span class="hai-typing-lines" aria-hidden="true"><i></i><i></i><i></i></span>
            </span>
            <span class="hai-typing-dots" aria-hidden="true"><i></i><i></i><i></i></span>
        </div>`;
    messageElement.dataset.loading = 'typing';
}

function setAssistantWaiting(container, messageElement, options = {}) {
    const intent = options.intent || 'text';
    const label = options.label || (intent === 'image'
        ? 'Harmonika AI sedang mendesain gambar…'
        : 'Harmonika AI sedang mengetik jawaban…');
    if (container) {
        container.classList.add('is-streaming');
        container.classList.toggle('is-image-streaming', intent === 'image');
        container.classList.toggle('is-image-preparing', intent === 'image');
        container.classList.toggle('is-thinking', intent !== 'image');
        container.classList.remove('is-writing', 'is-code-writing', 'is-rendering', 'is-image-designing');
        container.dataset.intent = intent;
        container.dataset.streamPhase = intent === 'image' ? 'image-preparing' : 'thinking';
    }
    ensureAssistantStreamLivebar(container, intent, intent === 'image' ? 'image-preparing' : 'thinking');
    chatMessages?.setAttribute('aria-busy', 'true');
    container?.querySelector('.hai-image-generating')?.remove();
    if (intent === 'image') {
        const skeleton = document.createElement('div');
        skeleton.className = 'hai-image-generating';
        skeleton.setAttribute('role', 'status');
        skeleton.setAttribute('aria-live', 'polite');
        skeleton.innerHTML = `
            <div class="hai-image-generating-preview" aria-hidden="true">
                <div class="hai-image-preview-grid"><span></span><span></span><span></span><span></span></div>
                <div class="hai-image-preview-orb"></div>
                <div class="hai-image-preview-scan"></div>
            </div>
            <div class="hai-image-generating-copy">
                <strong>${escapeHtml(label)}</strong>
                <small>Menyiapkan kanvas, komposisi, warna, dan thumbnail hasil gambar.</small>
                <ol class="hai-image-steps" aria-label="Tahapan pembuatan gambar"></ol>
                <div class="hai-image-progressbar" aria-hidden="true"><span></span></div>
            </div>`;
        container?.insertBefore(skeleton, messageElement || null);
        startImageProgress(container);
        if (messageElement && !messageElement.textContent.trim()) {
            messageElement.innerHTML = '';
            messageElement.dataset.loading = 'image';
        }
    } else if (messageElement && !messageElement.textContent.trim()) {
        renderAssistantTypingPlaceholder(messageElement);
    }
}

function setAssistantStreamPhase(container, phase = 'thinking') {
    if (!container) return;
    container.dataset.streamPhase = phase;
    container.classList.toggle('is-thinking', phase === 'thinking');
    container.classList.toggle('is-writing', phase === 'writing');
    container.classList.toggle('is-code-writing', phase === 'code-writing');
    container.classList.toggle('is-image-preparing', phase === 'image-preparing');
    container.classList.toggle('is-image-designing', phase === 'image-designing');
    container.classList.toggle('is-rendering', phase === 'image-rendering');
}

function isLikelyStreamingCode(text = '') {
    const value = String(text || '');
    return /```/.test(value) ||
        /(?:^|\n)\s{0,3}(?:const|let|var|function|class|def|import|from|package|public\s+class|SELECT|INSERT|UPDATE|DELETE|CREATE|<script|<div|<template)\b/i.test(value);
}

function markAssistantFirstVisibleChunk(container, intent = 'text', options = {}) {
    const normalizedIntent = String(intent || 'text').toLowerCase() === 'image' ? 'image' : 'text';
    if (normalizedIntent === 'image') {
        setAssistantStreamPhase(container, options.phase || 'image-rendering');
        ensureAssistantStreamLivebar(container, 'image', 'image-rendering');
        if (options.progressStep !== false) {
            setImageProgressStep(container, Number.isFinite(options.progressStep) ? options.progressStep : 2);
        }
        setHaiLiveStatus(options.status || 'imageDesigning');
        return;
    }
    setAssistantStreamPhase(container, 'writing');
    ensureAssistantStreamLivebar(container, 'text', 'writing');
    const message = container?.querySelector?.('.assistant-message');
    if (message) message.dataset.loading = 'writing';
    setHaiLiveStatus(options.status || 'textWriting');
}

function clearAssistantWaiting(container) {
    if (container) {
        stopImageProgress(container);
        container.classList.remove('is-streaming', 'is-image-streaming', 'is-image-preparing', 'is-image-designing', 'is-thinking', 'is-writing', 'is-code-writing', 'is-rendering');
        delete container.dataset.intent;
        delete container.dataset.streamPhase;
        container.querySelector(':scope > .hai-stream-livebar')?.remove();
        container.querySelector('.hai-image-generating')?.remove();
        container.querySelector('.assistant-message')?.removeAttribute('data-loading');
    }
    if (!document.querySelector('.assistant-message-container.is-streaming')) {
        chatMessages?.setAttribute('aria-busy', 'false');
    }
}

function isAssistantWaitingPlaceholder(messageElement) {
    if (!messageElement) return false;
    const text = messageElement.textContent.trim();
    return Boolean(
        messageElement.querySelector('.hai-typing') ||
        text === 'Harmonika AI sedang menyusun jawaban…' ||
        text === 'Harmonika AI sedang mengetik jawaban…' ||
        text === 'Harmonika AI sedang mendesain gambar…'
    );
}

function renderImageProgress(container, activeIndex = 0) {
    const list = container?.querySelector('.hai-image-steps');
    if (!list) return;
    list.innerHTML = HAI_IMAGE_STEPS.map((step, index) => `
        <li class="${index < activeIndex ? 'is-complete' : ''} ${index === activeIndex ? 'is-active' : ''}">
            <span>${escapeHtml(step.title)}</span>
            <small>${escapeHtml(step.detail)}</small>
        </li>
    `).join('');
}

function setImageProgressStep(container, stepIndex = 0) {
    if (!container) return;
    const nextIndex = Math.max(0, Math.min(HAI_IMAGE_STEPS.length - 1, stepIndex));
    container.dataset.imageStep = String(nextIndex);
    renderImageProgress(container, nextIndex);
}

function startImageProgress(container) {
    if (!container) return;
    stopImageProgress(container);
    setImageProgressStep(container, 0);
    container._haiImageProgressTimer = window.setInterval(() => {
        const current = Number(container.dataset.imageStep || 0);
        if (current < HAI_IMAGE_STEPS.length - 1) {
            setImageProgressStep(container, current + 1);
        }
    }, 3600);
}

function stopImageProgress(container) {
    if (container?._haiImageProgressTimer) {
        window.clearInterval(container._haiImageProgressTimer);
        container._haiImageProgressTimer = null;
    }
}

function hasCompleteImageArtifact(text = '') {
    const value = String(text || '');
    return /```(?:svg)?\s*[\s\S]*?<svg[\s\S]*?<\/svg>[\s\S]*?```/i.test(value);
}

function messageContentRaw(content = '') {
    if (typeof content === 'string') return content;
    if (content && typeof content.raw === 'string') return content.raw;
    return '';
}

function shouldAllowImageArtifacts(raw = '', intent = '') {
    const value = String(raw || '');
    return String(intent || '').toLowerCase() === 'image' ||
        hasCompleteImageArtifact(value) ||
        /hai-(?:member-)?image-artifact|hai-legacy-image|\/api\/files\/[^)\s"']+\/preview/i.test(value);
}

function markdownContentForStoredMessage(msg = {}) {
    const raw = messageContentRaw(msg.content);
    if (msg.content && typeof msg.content === 'object') {
        return {
            ...msg.content,
            raw,
            allowImageArtifacts: Boolean(msg.content.allowImageArtifacts) || shouldAllowImageArtifacts(raw, msg.intent)
        };
    }
    return {
        raw,
        reasoningExpanded: false,
        allowImageArtifacts: shouldAllowImageArtifacts(raw, msg.intent)
    };
}

function getChatBottomDistance() {
    if (!chatWrapper) return 0;
    return Math.max(0, chatWrapper.scrollHeight - chatWrapper.scrollTop - chatWrapper.clientHeight);
}

function updateScrollBottomAffordance() {
    if (!scrollBottomButton) return;
    const shouldShow = getChatBottomDistance() > 180;
    scrollBottomButton.disabled = !shouldShow;
    scrollBottomButton.classList.toggle('is-visible', shouldShow);
    scrollBottomButton.setAttribute('aria-hidden', shouldShow ? 'false' : 'true');
}

function isNearChatBottom(threshold = 160) {
    return getChatBottomDistance() < threshold;
}

function scrollChatToBottom(behavior = 'smooth') {
    autoScrollLockedToBottom = true;
    lastProgrammaticScrollAt = Date.now();
    chatWrapper.scrollTo({
        top: chatWrapper.scrollHeight,
        behavior
    });
    window.requestAnimationFrame(updateScrollBottomAffordance);
}

function setAssistantError(messageElement, text) {
    if (!messageElement) return;
    const safeText = String(text || 'Jawaban dihentikan.');
    // React 18 root rendering can be async; put a safe text fallback in the DOM
    // immediately so fast Stop/Error states never leave an empty assistant bubble.
    messageElement.textContent = safeText;
    if (!messageElement.reactRoot) {
        messageElement.reactRoot = ReactDOM.createRoot(messageElement);
    }
    const node = React.createElement(MarkdownContent, {
            content: {
                raw: safeText,
                reasoningExpanded: false
            },
            messageEndTag: END_TAG
        });
    if (typeof ReactDOM.flushSync === 'function') {
        ReactDOM.flushSync(() => messageElement.reactRoot.render(node));
    } else {
        messageElement.reactRoot.render(node);
    }
}

function ensureAssistantErrorBubble(container, messageElement, text) {
    if (!container || !messageElement) return;
    clearAssistantWaiting(container);
    container.dataset.error = 'true';
    setAssistantError(messageElement, text);
    appendAssistantActionButtonsIfMissing(container, messageElement, text);
}

async function persistAssistantErrorMessage(messageId, text, options = {}) {
    const message = {
        messageId,
        role: 'assistant',
        content: text,
        endTag: options.endTag || END_TAG,
        thinkingTime: streamDuration,
        isError: true
    };
    if (options.intent) message.intent = options.intent;
    conversationHistory.push(message);
    if (!isPrivateChat && currentConversationId && conversations[currentConversationId]) {
        conversations[currentConversationId].messages = [...conversationHistory];
        await saveConversationsToStorage();
        updateChatHistory();
    }
    return message;
}

function renderAssistantMarkdown(messageElement, raw, messageEndTag = END_TAG, reasoningExpanded = false, immediate = false) {
    if (!messageElement) return;
    if (!messageElement.reactRoot) {
        messageElement.reactRoot = ReactDOM.createRoot(messageElement);
    }
    const containerIntent = messageElement
        .closest?.('.assistant-message-container')
        ?.dataset
        ?.intent || '';
    const allowImageArtifacts = shouldAllowImageArtifacts(raw, containerIntent);
    messageElement._pendingMarkdownRender = { raw, messageEndTag, reasoningExpanded, allowImageArtifacts };
    const renderNow = () => {
        const pending = messageElement._pendingMarkdownRender;
        messageElement._markdownRenderFrame = null;
        if (!pending) return;
        messageElement.reactRoot.render(
            React.createElement(MarkdownContent, {
                content: {
                    raw: pending.raw,
                    reasoningExpanded: pending.reasoningExpanded,
                    allowImageArtifacts: pending.allowImageArtifacts
                },
                messageEndTag: pending.messageEndTag
            })
        );
    };
    if (immediate) {
        if (messageElement._markdownRenderFrame) {
            cancelAnimationFrame(messageElement._markdownRenderFrame);
            messageElement._markdownRenderFrame = null;
        }
        if (typeof ReactDOM.flushSync === 'function') {
            ReactDOM.flushSync(renderNow);
        } else {
            renderNow();
        }
        return;
    }
    if (!messageElement._markdownRenderFrame) {
        messageElement._markdownRenderFrame = requestAnimationFrame(renderNow);
    }
}

function userExplicitlyAskedSingleSentence(promptText = '') {
    const text = String(promptText || '').toLowerCase();
    return /(\btepat\s+)?\b(satu|1)\s+kalimat\b/.test(text) ||
        /\bjawab(?:an)?\s+(?:tepat\s+)?(?:dalam\s+)?(?:satu|1)\s+kalimat\b/.test(text);
}

function trimAssistantToSingleSentenceIfRequested(responseText = '', promptText = '') {
    const raw = String(responseText || '');
    if (!userExplicitlyAskedSingleSentence(promptText)) return raw;
    const withoutReasoning = stripPublicReasoningBlocks(raw).trim();
    if (!withoutReasoning) return raw;
    const sentenceMatch = withoutReasoning.match(/^[\s\S]*?[.!?](?=\s|$)/);
    const firstSentence = (sentenceMatch ? sentenceMatch[0] : withoutReasoning.split(/\n+/)[0] || withoutReasoning).trim();
    if (!firstSentence || firstSentence.length >= withoutReasoning.length) return raw;
    const prefixMatch = raw.match(/^[\s\S]*?(?:<\/think>\s*)/i);
    return `${prefixMatch ? prefixMatch[0] : ''}${firstSentence}`;
}

function normalizeAssistantPublicQualityText(responseText = '') {
    let raw = String(responseText || '');
    if (!raw.trim()) return raw;

    // Conservative cleanup for recurring malformed Indonesian tokens observed in
    // production output. Keep the list tiny and exact so factual meaning is not
    // rewritten by the UI.
    const replacements = [
        [/\bantarafakat\b/gi, 'antara'],
        [/\bmulut\s+ke\s+mulang\b/gi, 'mulut ke mulut']
    ];
    replacements.forEach(([pattern, replacement]) => {
        raw = raw.replace(pattern, replacement);
    });

    // Remove immediately repeated identical sentences/paragraphs only. This
    // keeps normal emphasis/list content intact while preventing visible double
    // answers from leaking to public chat.
    const sentences = raw.match(/[^.!?\n]+[.!?]+(?:\s+|$)|[^.!?\n]+(?:\n|$)/g);
    if (!sentences || sentences.length < 2) return raw;
    const cleaned = [];
    let previous = '';
    sentences.forEach(sentence => {
        const current = String(sentence || '');
        const normalized = current
            .toLowerCase()
            .replace(/\s+/g, ' ')
            .replace(/[^\p{L}\p{N} ]/gu, '')
            .trim();
        if (normalized && normalized === previous && normalized.length > 20) {
            return;
        }
        cleaned.push(current);
        if (normalized) previous = normalized;
    });
    return cleaned.join('').trimEnd();
}

function normalizeHaiStreamChunk(rawChunk = '') {
    const raw = String(rawChunk || '');
    if (!raw) return '';
    // Backend may send SSE comment frames before/while waiting for the AI engine.
    // The web UI still consumes plain text chunks, so remove HAI control comments
    // before appending content to the visible assistant bubble/history.
    return raw
        .split(/\r?\n/)
        .filter(line => !/^:\s*hai-(?:open|ping|heartbeat)\b/i.test(line.trim()))
        .join('\n')
        .replace(/^\n+/, '');
}

async function fetchRealtimeReplayText(responseId) {
    const cleanId = String(responseId || '').trim();
    if (!cleanId) return null;
    setHaiConnectionState('reconnecting');
    try {
        const replayResponse = await fetch(`/api/realtime/events?response_id=${encodeURIComponent(cleanId)}&after_sequence=0`, {
            headers: { 'Accept': 'application/json' },
            credentials: 'same-origin'
        });
        if (!replayResponse.ok) {
            setHaiConnectionState('history');
            return null;
        }
        const payload = await replayResponse.json();
        const events = Array.isArray(payload?.events) ? payload.events : [];
        const text = events
            .filter(event => event?.type === 'response.output_text.delta')
            .map(event => event?.data?.text || '')
            .join('');
        const completed = payload?.status === 'completed' || events.some(event => event?.type === 'response.completed');
        if (payload?.ok && completed && text.trim()) {
            setHaiConnectionState('replay');
        } else {
            setHaiConnectionState('history');
        }
        return {
            ok: Boolean(payload?.ok && completed && text.trim()),
            text,
            status: payload?.status || (completed ? 'completed' : 'unknown'),
            count: Number(payload?.count || events.length || 0)
        };
    } catch (error) {
        console.warn('Realtime replay recovery failed:', error);
        setHaiConnectionState('history');
        return null;
    }
}

function decodeUtf8Base64Url(value = '') {
    try {
        const normalized = String(value).replace(/-/g, '+').replace(/_/g, '/');
        const padded = normalized + '='.repeat((4 - normalized.length % 4) % 4);
        const binary = atob(padded);
        const bytes = Uint8Array.from(binary, char => char.charCodeAt(0));
        return new TextDecoder().decode(bytes);
    } catch (error) {
        console.warn('Invalid HAI sources header:', error);
        return '';
    }
}

function normalizeHaiSources(sources) {
    if (!Array.isArray(sources)) return [];
    const seen = new Set();
    return sources
        .filter(item => item && typeof item === 'object')
        .map(item => {
            const url = String(item.url || '').trim();
            const validUrl = /^https?:\/\//i.test(url) ? url : '';
            let host = '';
            if (validUrl) {
                try {
                    host = new URL(validUrl).hostname.replace(/^www\./, '');
                } catch (_) {}
            }
            const title = String(item.title || host || item.source || 'Sumber').trim().slice(0, 180);
            const source = String(item.source || host || 'web').trim().slice(0, 40);
            const key = validUrl || `${title}|${source}|${String(item.snippet || '').slice(0, 80)}`.toLowerCase();
            if (!key || seen.has(key)) return null;
            seen.add(key);
            return {
                title,
                url: validUrl,
                snippet: String(item.snippet || '').slice(0, 260),
                source,
                domain: String(item.domain || host || '').slice(0, 120)
            };
        })
        .filter(Boolean)
        .slice(0, 6);
}

function parseHaiSourcesHeader(headerValue) {
    if (!headerValue) return [];
    try {
        return normalizeHaiSources(JSON.parse(decodeUtf8Base64Url(headerValue)));
    } catch (error) {
        console.warn('Could not parse HAI sources:', error);
        return [];
    }
}

function parseHaiLibraryGroundingHeader(headerValue) {
    if (!headerValue) return { mode: haiLibraryGroundingMode, contextMode: haiLibraryContextMode, used: false, count: 0 };
    try {
        const payload = JSON.parse(decodeUtf8Base64Url(headerValue));
        return {
            mode: normalizeLibraryGroundingMode(payload?.mode || haiLibraryGroundingMode),
            contextMode: normalizeLibraryContextMode(payload?.context_mode || payload?.contextMode || haiLibraryContextMode),
            used: Boolean(payload?.used),
            count: Math.max(0, Number(payload?.count || 0) || 0),
            contextChars: Math.max(0, Number(payload?.context_chars || payload?.contextChars || 0) || 0),
            retrieval_mode: String(payload?.retrieval_mode || '').slice(0, 80),
            reason: String(payload?.reason || '').slice(0, 80)
        };
    } catch (error) {
        console.warn('Could not parse HAI library grounding:', error);
        return { mode: haiLibraryGroundingMode, contextMode: haiLibraryContextMode, used: false, count: 0 };
    }
}

function messageSources(message) {
    if (!message || typeof message !== 'object') return [];
    if (Array.isArray(message.sources)) return normalizeHaiSources(message.sources);
    if (message.content && typeof message.content === 'object' && Array.isArray(message.content.sources)) {
        return normalizeHaiSources(message.content.sources);
    }
    return [];
}

function sourceHost(url) {
    try {
        return new URL(url).hostname.replace(/^www\./, '');
    } catch (_) {
        return '';
    }
}

function sourceFaviconUrl(url) {
    const host = sourceHost(url);
    return host && host !== 'web' ? `https://${host}/favicon.ico` : '';
}

function createSourceIcon(source, index, compact = false) {
    const icon = document.createElement('span');
    icon.className = compact ? 'hai-source-icon is-stacked' : 'hai-source-icon';
    icon.style.setProperty('--source-index', String(index));
    const host = source.domain || sourceHost(source.url);
    const initial = (host || source.source || source.title || 'S').slice(0, 1).toUpperCase();
    icon.textContent = initial;
    icon.classList.add('is-fallback');
    const favicon = sourceFaviconUrl(source.url);
    if (favicon) {
        const img = document.createElement('img');
        img.alt = '';
        img.loading = 'lazy';
        img.referrerPolicy = 'no-referrer';
        img.onload = () => {
            icon.textContent = '';
            icon.classList.remove('is-fallback');
            icon.appendChild(img);
        };
        img.onerror = () => {
            img.remove();
            icon.textContent = initial;
            icon.classList.add('is-fallback');
        };
        img.src = favicon;
    }
    return icon;
}

function createSourceDetailsPanel(sources) {
    const panel = document.createElement('div');
    panel.className = 'hai-source-details';
    panel.hidden = true;
    panel.setAttribute('role', 'list');
    sources.forEach((source, index) => {
        const item = document.createElement(source.url ? 'a' : 'article');
        item.className = 'hai-source-detail-item';
        item.setAttribute('role', 'listitem');
        if (source.url) {
            item.href = source.url;
            item.target = '_blank';
            item.rel = 'noopener noreferrer nofollow';
            item.setAttribute('aria-label', `Buka referensi ${index + 1}: ${source.title}`);
        } else {
            item.classList.add('is-static');
        }

        const icon = createSourceIcon(source, index);
        const body = document.createElement('span');
        body.className = 'hai-source-detail-body';

        const title = document.createElement('strong');
        title.textContent = source.title || `Referensi ${index + 1}`;
        body.appendChild(title);

        const meta = document.createElement('small');
        meta.textContent = source.domain || sourceHost(source.url) || source.source || 'referensi';
        body.appendChild(meta);

        if (source.snippet) {
            const snippet = document.createElement('em');
            snippet.textContent = source.snippet;
            body.appendChild(snippet);
        }

        item.appendChild(icon);
        item.appendChild(body);
        panel.appendChild(item);
    });
    return panel;
}

function appendSourceChips(messageContainer, sources) {
    if (!messageContainer) return;
    const cleanSources = normalizeHaiSources(sources);
    messageContainer.querySelector('.hai-source-chips')?.remove();
    if (!cleanSources.length) return;

    const list = document.createElement('div');
    list.className = `hai-source-chips ${cleanSources.length > 2 ? 'is-compact-stack' : 'is-chip-row'}`;
    list.setAttribute('aria-label', 'Sumber referensi');

    const label = document.createElement('span');
    label.className = 'hai-source-label';
    label.textContent = 'Referensi';
    list.appendChild(label);

    if (cleanSources.length > 2) {
        const stack = document.createElement('div');
        stack.className = 'hai-source-stack';
        cleanSources.forEach((source, index) => {
            const link = document.createElement(source.url ? 'a' : 'span');
            link.className = 'hai-source-stack-link';
            if (source.url) {
                link.href = source.url;
                link.target = '_blank';
                link.rel = 'noopener noreferrer nofollow';
                link.setAttribute('aria-label', `Buka sumber ${index + 1}: ${source.title}`);
            } else {
                link.classList.add('is-static');
            }
            link.title = `${source.title}${source.domain || source.source ? ` · ${source.domain || source.source}` : ''}`;
            link.appendChild(createSourceIcon(source, index, true));
            stack.appendChild(link);
        });
        list.appendChild(stack);
        const count = document.createElement('button');
        count.className = 'hai-source-count';
        count.type = 'button';
        count.textContent = `${cleanSources.length} sumber`;
        count.setAttribute('aria-expanded', 'false');
        list.appendChild(count);
        const details = createSourceDetailsPanel(cleanSources);
        const detailsId = `hai-source-details-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
        details.id = detailsId;
        count.setAttribute('aria-controls', detailsId);
        list.appendChild(details);
        count.addEventListener('click', () => {
            const open = details.hidden;
            details.hidden = !open;
            list.classList.toggle('is-expanded', open);
            count.setAttribute('aria-expanded', String(open));
            count.textContent = open ? 'Tutup sumber' : `${cleanSources.length} sumber`;
        });
    } else {
        cleanSources.forEach((source, index) => {
            const chip = document.createElement(source.url ? 'a' : 'span');
            chip.className = 'hai-source-chip';
            if (source.url) {
                chip.href = source.url;
                chip.target = '_blank';
                chip.rel = 'noopener noreferrer nofollow';
            } else {
                chip.classList.add('is-static');
            }
            chip.title = `${source.title}${source.domain || source.source ? ` · ${source.domain || source.source}` : ''}`;
            chip.appendChild(createSourceIcon(source, index));
            const text = document.createElement('span');
            text.className = 'hai-source-text';
            const title = document.createElement('strong');
            title.textContent = source.title;
            const host = document.createElement('small');
            host.textContent = source.domain || sourceHost(source.url) || source.source || 'referensi';
            text.appendChild(title);
            text.appendChild(host);
            chip.appendChild(text);
            list.appendChild(chip);
        });
    }

    const buttons = messageContainer.querySelector('.message-buttons');
    if (buttons) {
        messageContainer.insertBefore(list, buttons);
    } else {
        messageContainer.appendChild(list);
    }
}

function applyHaiPrompt(prefix, intent = 'text') {
    if (!prefix || currentController) return;
    const current = userInput.value.trim();
    userInput.value = current && !current.startsWith(prefix) ? `${prefix}${current}` : (current || prefix);
    userInput.placeholder = intent === 'image'
        ? 'Deskripsikan gambar yang ingin dibuat…'
        : 'Tanya Harmonika AI…';
    adjustTextareaHeight(userInput);
    userInput.focus();
}

// CodeBlock component's highlighting logic
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function libraryDocMeta(doc = {}) {
    const bits = [];
    const size = Number(doc.size_bytes || 0);
    if (size > 0) bits.push(formatFileSize(size));
    const chars = Number(doc.text_chars || 0);
    if (chars > 0) bits.push(`${chars.toLocaleString('id-ID')} karakter`);
    return bits.join(' · ');
}

function normalizeLibraryGroundingMode(mode = 'auto') {
    const value = String(mode || 'auto').toLowerCase();
    return ['auto', 'force', 'off'].includes(value) ? value : 'auto';
}

function libraryGroundingLabel(mode = haiLibraryGroundingMode) {
    return {
        auto: 'Otomatis',
        force: 'Selalu',
        off: 'Mati'
    }[normalizeLibraryGroundingMode(mode)] || 'Otomatis';
}

function normalizeLibraryContextMode(mode = 'snippet') {
    const value = String(mode || 'snippet').toLowerCase();
    return value === 'full' ? 'full' : 'snippet';
}

function libraryContextLabel(mode = haiLibraryContextMode) {
    return normalizeLibraryContextMode(mode) === 'full' ? 'Penuh' : 'Cuplikan';
}

function setLibraryContextMode(mode = 'snippet') {
    haiLibraryContextMode = normalizeLibraryContextMode(mode);
    try {
        localStorage.setItem(HAI_LIBRARY_CONTEXT_STORAGE_KEY, haiLibraryContextMode);
    } catch (_) {}
    if (haiLibraryContextToggle) {
        haiLibraryContextToggle.textContent = libraryContextLabel(haiLibraryContextMode);
        haiLibraryContextToggle.dataset.mode = haiLibraryContextMode;
        haiLibraryContextToggle.setAttribute('aria-pressed', haiLibraryContextMode === 'full' ? 'true' : 'false');
        haiLibraryContextToggle.setAttribute('aria-label', `Mode konteks Library: ${libraryContextLabel(haiLibraryContextMode)}`);
        haiLibraryContextToggle.title = haiLibraryContextMode === 'full'
            ? 'Backend memakai konteks dokumen lebih panjang secara server-side, tetap tidak masuk history.'
            : 'Backend memakai cuplikan relevan agar chat umum tetap ringan.';
    }
    haiLibraryPanel?.dataset && (haiLibraryPanel.dataset.context = haiLibraryContextMode);
}

function cycleLibraryContextMode() {
    const next = haiLibraryContextMode === 'full' ? 'snippet' : 'full';
    setLibraryContextMode(next);
    showToast(`Konteks Library: ${libraryContextLabel(next)}.`, 'info');
}

function setLibraryGroundingMode(mode = 'auto') {
    haiLibraryGroundingMode = normalizeLibraryGroundingMode(mode);
    try {
        localStorage.setItem(HAI_LIBRARY_GROUNDING_STORAGE_KEY, haiLibraryGroundingMode);
    } catch (_) {}
    if (haiLibraryGroundingToggle) {
        haiLibraryGroundingToggle.textContent = libraryGroundingLabel(haiLibraryGroundingMode);
        haiLibraryGroundingToggle.dataset.mode = haiLibraryGroundingMode;
        haiLibraryGroundingToggle.setAttribute('aria-pressed', haiLibraryGroundingMode === 'off' ? 'false' : 'true');
        haiLibraryGroundingToggle.setAttribute('aria-label', `Mode pemakaian Library ke chat: ${libraryGroundingLabel(haiLibraryGroundingMode)}`);
        haiLibraryGroundingToggle.title = haiLibraryGroundingMode === 'off'
            ? 'Library tidak dikirim sebagai konteks chat.'
            : (haiLibraryGroundingMode === 'force'
                ? 'Library selalu dicoba sebagai konteks chat terbaru.'
                : 'Library dipakai otomatis bila relevan dengan pertanyaan.');
    }
    haiLibraryPanel?.dataset && (haiLibraryPanel.dataset.grounding = haiLibraryGroundingMode);
}

function cycleLibraryGroundingMode() {
    const next = haiLibraryGroundingMode === 'auto'
        ? 'force'
        : (haiLibraryGroundingMode === 'force' ? 'off' : 'auto');
    setLibraryGroundingMode(next);
    showToast(`Library ke chat: ${libraryGroundingLabel(next)}.`, 'info');
}

function renderLibraryPanel(state = '') {
    if (!haiLibraryPanel || !haiLibraryList) return;
    const rawQuery = String(haiLibrarySearch?.value || '').trim();
    const query = rawQuery.toLowerCase();
    const localDocs = query
        ? haiLibraryDocuments.filter(doc => {
            const haystack = `${doc.name || ''} ${doc.preview || ''} ${doc.snippet || ''}`.toLowerCase();
            return haystack.includes(query);
        })
        : haiLibraryDocuments;
    const hasBackendSearch = query && haiLibrarySearchQuery === query;
    const docs = hasBackendSearch ? haiLibrarySearchResults : localDocs;
    if (haiLibraryCount) {
        haiLibraryCount.textContent = String(haiLibraryDocuments.length || 0);
    }
    setLibraryGroundingMode(haiLibraryGroundingMode);
    setLibraryContextMode(haiLibraryContextMode);
    haiLibraryPanel.classList.toggle('is-loading', Boolean(haiLibraryLoading || haiLibrarySearchLoading));
    if (state === 'loading') {
        haiLibraryList.innerHTML = '<div class="hai-library-empty">Memuat library…</div>';
        return;
    }
    if (haiLibrarySearchLoading && query && !docs.length) {
        haiLibraryList.innerHTML = '<div class="hai-library-empty">Mencari isi dokumen…</div>';
        return;
    }
    if (!docs.length) {
        haiLibraryList.innerHTML = `<div class="hai-library-empty">${query ? 'Tidak ada dokumen cocok.' : 'Library belum berisi dokumen.'}</div>`;
        return;
    }
    haiLibraryList.innerHTML = docs.map(doc => `
        <article class="hai-library-item" data-doc-id="${escapeAttr(doc.id || '')}">
            <button type="button" class="hai-library-use" data-doc-id="${escapeAttr(doc.id || '')}">
                <strong>${escapeHtml(doc.name || 'Dokumen')}</strong>
                <small>${escapeHtml([libraryDocMeta(doc), doc.snippet ? 'Hasil pencarian isi dokumen' : ''].filter(Boolean).join(' · ') || 'Siap dicari')}</small>
                ${(doc.snippet || doc.preview) ? `<span>${escapeHtml(doc.snippet || doc.preview)}</span>` : ''}
            </button>
            <button type="button" class="hai-library-delete" data-doc-id="${escapeAttr(doc.id || '')}" aria-label="Hapus ${escapeAttr(doc.name || 'dokumen')}">&times;</button>
        </article>
    `).join('');
    haiLibraryList.querySelectorAll('.hai-library-use').forEach(button => {
        button.addEventListener('click', () => {
            const doc = haiLibraryDocuments.find(item => item.id === button.dataset.docId) || docs.find(item => item.id === button.dataset.docId);
            if (!doc) return;
            applyHaiPrompt(`Gunakan dokumen Library "${doc.name}" untuk menjawab: `);
        });
    });
    haiLibraryList.querySelectorAll('.hai-library-delete').forEach(button => {
        button.addEventListener('click', () => deleteLibraryDocument(button.dataset.docId));
    });
}

async function searchLibraryPanel(query = '') {
    const cleanQuery = String(query || '').replace(/\s+/g, ' ').trim();
    const normalizedQuery = cleanQuery.toLowerCase();
    if (!haiLibraryPanel) return;
    if (!cleanQuery) {
        haiLibrarySearchQuery = '';
        haiLibrarySearchResults = [];
        haiLibrarySearchLoading = false;
        renderLibraryPanel();
        return;
    }
    if (!haiLibraryDocuments.length) {
        haiLibrarySearchQuery = normalizedQuery;
        haiLibrarySearchResults = [];
        haiLibrarySearchLoading = false;
        renderLibraryPanel();
        return;
    }
    haiLibrarySearchLoading = true;
    renderLibraryPanel();
    try {
        const response = await fetch('/api/library/search', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: cleanQuery.slice(0, 500), limit: 8 })
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || !payload?.ok || !Array.isArray(payload.results)) {
            throw new Error(payload?.message || 'Pencarian Library belum bisa diproses.');
        }
        if (String(haiLibrarySearch?.value || '').trim().toLowerCase() !== normalizedQuery) return;
        haiLibrarySearchQuery = normalizedQuery;
        haiLibrarySearchResults = payload.results;
    } catch (error) {
        console.warn('Library panel search failed:', error);
        if (String(haiLibrarySearch?.value || '').trim().toLowerCase() === normalizedQuery) {
            haiLibrarySearchQuery = '';
            haiLibrarySearchResults = [];
        }
    } finally {
        if (String(haiLibrarySearch?.value || '').trim().toLowerCase() === normalizedQuery) {
            haiLibrarySearchLoading = false;
            renderLibraryPanel();
        }
    }
}

function scheduleLibraryPanelSearch(delay = 250) {
    if (haiLibrarySearchTimer) {
        clearTimeout(haiLibrarySearchTimer);
        haiLibrarySearchTimer = null;
    }
    const query = String(haiLibrarySearch?.value || '').trim();
    if (!query) {
        haiLibrarySearchQuery = '';
        haiLibrarySearchResults = [];
        haiLibrarySearchLoading = false;
        renderLibraryPanel();
        return;
    }
    renderLibraryPanel();
    haiLibrarySearchTimer = setTimeout(() => searchLibraryPanel(query), delay);
}

async function loadLibraryDocuments() {
    if (!haiLibraryPanel) return;
    haiLibraryLoading = true;
    renderLibraryPanel('loading');
    try {
        const response = await fetch('/api/library/documents', {
            method: 'GET',
            credentials: 'same-origin',
            cache: 'no-store'
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || !payload?.ok) {
            throw new Error(payload?.message || 'Library belum bisa dimuat.');
        }
        haiLibraryDocuments = Array.isArray(payload.documents) ? payload.documents : [];
    } catch (error) {
        console.warn('Library load failed:', error);
        haiLibraryDocuments = [];
        if (haiLibraryList) {
            haiLibraryList.innerHTML = '<div class="hai-library-empty">Library belum bisa dimuat.</div>';
        }
    } finally {
        haiLibraryLoading = false;
        renderLibraryPanel();
        if (String(haiLibrarySearch?.value || '').trim()) {
            scheduleLibraryPanelSearch(0);
        }
    }
}

async function uploadLibraryDocument(file) {
    if (!file) return;
    if (file.size > HAI_MAX_ATTACHMENT_BYTES) {
        showToast(`${file.name}: ukuran file maksimal 10 MB.`, 'error');
        return;
    }
    if (!isSupportedDocumentFile(file) || isSupportedImageFile(file)) {
        showToast(`${file.name}: Library saat ini mendukung PDF, TXT, CSV, DOCX, dan XLSX.`, 'error');
        return;
    }
    const form = new FormData();
    form.append('file', file, file.name || 'document');
    haiLibraryLoading = true;
    renderLibraryPanel('loading');
    try {
        const response = await fetch('/api/library/documents', {
            method: 'POST',
            credentials: 'same-origin',
            body: form
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || !payload?.ok) {
            throw new Error(payload?.message || `Upload library gagal (${response.status})`);
        }
        if (payload.document) {
            haiLibraryDocuments = [payload.document, ...haiLibraryDocuments.filter(doc => doc.id !== payload.document.id)];
        }
        showToast('Dokumen ditambahkan ke Library.', 'success');
    } catch (error) {
        console.error('Library upload failed:', error);
        showToast(error.message || 'Upload library gagal.', 'error');
    } finally {
        haiLibraryLoading = false;
        renderLibraryPanel();
        if (String(haiLibrarySearch?.value || '').trim()) {
            scheduleLibraryPanelSearch(0);
        }
    }
}

async function deleteLibraryDocument(docId) {
    const cleanId = String(docId || '');
    if (!cleanId) return;
    const doc = haiLibraryDocuments.find(item => item.id === cleanId);
    if (!window.confirm(`Hapus "${doc?.name || 'dokumen'}" dari Library?`)) return;
    try {
        const response = await fetch(`/api/library/documents/${encodeURIComponent(cleanId)}`, {
            method: 'DELETE',
            credentials: 'same-origin'
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || payload?.deleted !== true) {
            throw new Error(payload?.message || 'Dokumen tidak bisa dihapus.');
        }
        haiLibraryDocuments = haiLibraryDocuments.filter(item => item.id !== cleanId);
        haiLibrarySearchResults = haiLibrarySearchResults.filter(item => item.id !== cleanId);
        renderLibraryPanel();
        if (String(haiLibrarySearch?.value || '').trim()) {
            scheduleLibraryPanelSearch(0);
        }
        showToast(`${doc?.name || 'Dokumen'} dihapus dari Library.`, 'success');
    } catch (error) {
        console.error('Library delete failed:', error);
        showToast(error.message || 'Dokumen tidak bisa dihapus.', 'error');
    }
}

function libraryContextBlock(results = []) {
    const docs = results
        .filter(item => item && (item.snippet || item.preview))
        .slice(0, HAI_LIBRARY_GROUNDING_LIMIT);
    if (!docs.length) return '';
    const body = docs.map((doc, index) => {
        const title = doc.name || `Dokumen ${index + 1}`;
        const snippet = doc.snippet || doc.preview || '';
        return `[Library: ${title}]\n${snippet}`;
    }).join('\n\n---\n\n');
    return [
        'Konteks Library Harmonika AI per device. Gunakan hanya bila relevan dengan pertanyaan terbaru; jangan sebut ID internal dokumen.',
        body
    ].join('\n\n');
}

async function searchLibraryForContext(query = '') {
    const cleanQuery = String(query || '').replace(/\s+/g, ' ').trim();
    if (!cleanQuery || cleanQuery.length < 3 || !haiLibraryDocuments.length) return '';
    try {
        const response = await fetch('/api/library/search', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: cleanQuery.slice(0, 500), limit: HAI_LIBRARY_GROUNDING_LIMIT })
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || !payload?.ok || !Array.isArray(payload.results)) return '';
        return libraryContextBlock(payload.results);
    } catch (error) {
        console.warn('Library context search skipped:', error);
        return '';
    }
}

async function appendLibraryContextToMessageContent(messageContent, query = '') {
    // Phase 258: grounding moved server-side so user history never stores
    // private Library context and regenerate/edit paths stay consistent.
    return messageContent;
}

// Add this function near other utility functions
function startStreamTimer() {
    if (streamStartTime === null) {
        // Only start if not already running
        streamStartTime = Date.now();
        // Don't reset streamDuration to null anymore
        // streamDuration = null;  <- Remove this line
    }
}

function stopStreamTimer() {
    if (streamStartTime) {
        // Add elapsed time to existing duration
        streamDuration = (streamDuration || 0) + (Date.now() - streamStartTime);
        console.log(streamDuration)
        streamStartTime = null;
        return streamDuration;
    }
    return null;
}

function checkForEndTag(content) {
    return DEFAULT_END_TAG.some(tag => content.includes(tag)) || content.includes(END_TAG);
}

function formatUserMessage(input) {
    if (Array.isArray(input)) {
        return input.map(part => {
            if (part?.type === 'text') {
                return formatUserMessage(part.text || '');
            }
            if (part?.type === 'image_url' && part.image_url?.url) {
                const src = String(part.image_url.url).replace(/"/g, '&quot;');
                return `<img class="message-inline-image" src="${src}" alt="Gambar terlampir">`;
            }
            return '';
        }).filter(Boolean).join('<br>');
    }

    if (input && typeof input === 'object') {
        const attachmentList = Array.isArray(input.attachments)
            ? input.attachments
            : (input.attachment ? [input.attachment] : []);
        if (attachmentList.length) {
            const text = formatUserMessage(input.content || input.text || '');
            const chips = attachmentList.map(attachment => {
                const icon = attachment.type === 'image' ? 'image' : 'document';
                const name = escapeHtml(attachment.name || 'Lampiran');
                const size = escapeHtml(attachment.sizeLabel || attachment.mime || '');
                return `<span class="hai-user-attachment-chip"><img src="${haiIconSrc(icon)}" alt="" class="icon-svg"><span><strong>${name}</strong>${size ? `<small>${size}</small>` : ''}</span></span>`;
            }).join('');
            return `${text ? `${text}<br>` : ''}<span class="hai-user-attachments">${chips}</span>`;
        }
        return formatUserMessage(input.content || input.raw || '');
    }

    return String(input ?? '')
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\n/g, '<br>');
}

function formatFileSize(bytes = 0) {
    const value = Number(bytes) || 0;
    if (value >= 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`;
    if (value >= 1024) return `${(value / 1024).toFixed(1)} KB`;
    return `${value} B`;
}

function fileExtension(fileName = '') {
    const match = String(fileName || '').toLowerCase().match(/\.[a-z0-9]+$/);
    return match ? match[0] : '';
}

function isSupportedImageFile(file) {
    return HAI_SUPPORTED_IMAGE_MIME.includes(String(file.type || '').toLowerCase())
        || ['.png', '.jpg', '.jpeg', '.webp'].includes(fileExtension(file.name));
}

function isSupportedDocumentFile(file) {
    const mime = String(file.type || '').toLowerCase();
    const ext = fileExtension(file.name);
    return allowedFileTypes.includes(mime) || HAI_SUPPORTED_DOCUMENT_EXTENSIONS.includes(ext);
}

function attachmentKindLabel(attachment) {
    if (attachment?.type === 'image') return 'Gambar siap dianalisis AI';
    if (attachment?.mime?.includes('spreadsheet') || fileExtension(attachment?.name) === '.xlsx') return 'Spreadsheet siap dibaca';
    if (attachment?.mime === 'application/pdf' || fileExtension(attachment?.name) === '.pdf') return 'PDF siap dibaca';
    return 'Dokumen siap dibaca';
}

function clearPendingAttachment() {
    pendingAttachment = null;
    pendingAttachments = [];
    hasImageAttached = false;
    if (attachmentTray) {
        attachmentTray.innerHTML = '';
        attachmentTray.classList.remove('is-visible', 'is-processing', 'has-error');
    }
    userInput.placeholder = "Tanya Harmonika AI…";
    refreshComposerState();
}

function syncPendingAttachmentAlias() {
    pendingAttachment = pendingAttachments[0] || null;
    hasImageAttached = pendingAttachments.some(attachment => attachment?.type === 'image');
}

function updateAttachmentPlaceholder() {
    if (!pendingAttachments.length) {
        userInput.placeholder = "Tanya Harmonika AI…";
    } else if (pendingAttachments.length > 1) {
        userInput.placeholder = `Tanyakan tentang ${pendingAttachments.length} lampiran ini…`;
    } else {
        userInput.placeholder = pendingAttachments[0].type === 'image'
            ? 'Tanyakan tentang gambar ini…'
            : 'Tanyakan tentang dokumen ini…';
    }
}

function attachmentChipHtml(attachment, status = 'ready', index = 0, removable = true) {
    const icon = attachment.type === 'image' ? 'image' : 'document';
    const preview = attachment.type === 'image' && attachment.base64
        ? `<img src="${escapeAttr(attachment.base64)}" alt="Pratinjau lampiran" class="hai-attachment-thumb">`
        : `<span class="hai-attachment-icon"><img src="${haiIconSrc(icon)}" alt="" class="icon-svg"></span>`;
    const statusText = status === 'processing' ? 'Memproses…' : attachmentKindLabel(attachment);
    return `
        <div class="hai-attachment-chip" role="status">
            ${preview}
            <span class="hai-attachment-info">
                <strong>${escapeHtml(attachment.name || 'Lampiran')}</strong>
                <small>${escapeHtml(`${attachment.sizeLabel || ''}${attachment.sizeLabel ? ' · ' : ''}${statusText}`)}</small>
            </span>
            ${removable ? `<button type="button" class="hai-attachment-remove" data-index="${index}" aria-label="Hapus lampiran">&times;</button>` : ''}
        </div>`;
}

function renderPendingAttachments(extraProcessingAttachments = []) {
    syncPendingAttachmentAlias();
    if (!attachmentTray) return;
    const processingList = Array.isArray(extraProcessingAttachments) ? extraProcessingAttachments : [];
    if (!pendingAttachments.length && !processingList.length) {
        clearPendingAttachment();
        return;
    }
    attachmentTray.className = `hai-attachment-tray is-visible ${processingList.length ? 'is-processing' : ''}`;
    const totalVisibleAttachments = pendingAttachments.length + processingList.length;
    const counterHtml = `
        <span class="hai-attachment-counter" aria-label="${totalVisibleAttachments} dari ${HAI_MAX_ATTACHMENTS} lampiran">
            ${totalVisibleAttachments}/${HAI_MAX_ATTACHMENTS}
        </span>`;
    attachmentTray.innerHTML = [
        ...pendingAttachments.map((attachment, index) => attachmentChipHtml(attachment, 'ready', index, true)),
        ...processingList.map((attachment, index) => attachmentChipHtml(attachment, 'processing', pendingAttachments.length + index, false)),
        counterHtml
    ].join('');
    attachmentTray.querySelectorAll('.hai-attachment-remove').forEach(button => {
        button.addEventListener('click', () => {
            const index = Number(button.dataset.index);
            if (Number.isInteger(index)) {
                pendingAttachments.splice(index, 1);
                renderPendingAttachments();
            }
        });
    });
    updateAttachmentPlaceholder();
    refreshComposerState();
}

function renderPendingAttachment(attachment, status = 'ready') {
    if (!attachment) return;
    if (status === 'processing') {
        renderPendingAttachments([attachment]);
        return;
    }
    pendingAttachments = [attachment];
    renderPendingAttachments();
}

function showAttachmentProcessing(file) {
    renderPendingAttachments([{
        type: file.type?.startsWith('image/') ? 'image' : 'document',
        name: file.name,
        sizeLabel: formatFileSize(file.size),
        mime: file.type
    }]);
}

function cloneAttachmentForQueue(attachment) {
    if (!attachment) return null;
    return { ...attachment };
}

function cloneAttachmentsForQueue(attachments = pendingAttachments) {
    return (attachments || []).map(attachment => ({ ...attachment }));
}

function addPendingAttachment(attachment) {
    if (!attachment) return false;
    if (pendingAttachments.length >= HAI_MAX_ATTACHMENTS) {
        showToast(`Maksimum ${HAI_MAX_ATTACHMENTS} lampiran per pesan.`, 'error');
        return false;
    }
    const duplicate = pendingAttachments.some(item =>
        item.name === attachment.name && item.sizeLabel === attachment.sizeLabel && item.mime === attachment.mime
    );
    if (duplicate) {
        showToast('Lampiran ini sudah ada di composer.', 'info');
        return false;
    }
    pendingAttachments.push(attachment);
    renderPendingAttachments();
    return true;
}

function updateQueueStatus() {
    if (!queueStatus) return;
    if (!queuedComposerMessage) {
        queueStatus.textContent = '';
        queueStatus.classList.remove('is-visible');
        refreshComposerState();
        return;
    }
    const attachments = queuedComposerMessage.attachments || (queuedComposerMessage.attachment ? [queuedComposerMessage.attachment] : []);
    const attachmentLabel = attachments.length
        ? (attachments.length > 1 ? `${attachments.length} lampiran` : (attachments[0]?.name || 'Lampiran'))
        : '';
    const messageLabel = queuedComposerMessage.message ? queuedComposerMessage.message.slice(0, 80) : '';
    const label = [messageLabel, attachmentLabel].filter(Boolean).join(' · ');
    queueStatus.textContent = `Masuk antrean: ${label}`;
    queueStatus.classList.add('is-visible');
    refreshComposerState();
}

function queueCurrentComposerDraft() {
    const message = userInput.value.trim();
    const attachments = cloneAttachmentsForQueue();
    if (!message && !attachments.length) return false;
    queuedComposerMessage = { message, attachments };
    userInput.value = '';
    adjustTextareaHeight(userInput);
    clearPendingAttachment();
    updateQueueStatus();
    setHaiStatus('');
    return true;
}

function clearQueuedComposerMessage() {
    queuedComposerMessage = null;
    updateQueueStatus();
}

function runQueuedComposerMessageSoon() {
    if (!queuedComposerMessage || currentController || isDispatchingQueuedMessage) return;
    const queued = queuedComposerMessage;
    clearQueuedComposerMessage();
    isDispatchingQueuedMessage = true;
    setHaiLiveStatus('queueSending');
    window.setTimeout(() => {
        userInput.value = queued.message || '';
        pendingAttachments = cloneAttachmentsForQueue(queued.attachments || (queued.attachment ? [queued.attachment] : []));
        renderPendingAttachments();
        adjustTextareaHeight(userInput);
        sendMessage({ preventDefault() {} }).finally(() => {
            isDispatchingQueuedMessage = false;
        });
    }, 180);
}

const options = {
    throwOnError: false
};
  
marked.use(markedKatex(options));

// Helper function to replace LaTeX syntax while preserving quoted content
function replaceLatexSyntax(content) {
    // Split content by code blocks
    const parts = content.split(/(```[\s\S]*?```)/g);
    
    return parts.map(part => {
        // If this part is a code block (starts with ```), return it unchanged
        if (part.startsWith('```')) {
            return part;
        }
        
        // Split by quotes to preserve content within them
        const quoteParts = part.split(/(`[^`]*`)/g);
        
        return quoteParts.map(quotePart => {
            // If this part is within quotes (starts and ends with `), return it unchanged
            if (quotePart.startsWith('`') && quotePart.endsWith('`')) {
                return quotePart;
            }
            
            // Otherwise, apply LaTeX replacements
            return quotePart
                .replace(/\\\[\s*([\s\S]*?)\s*\\\]/g, '$$$$$1$$$$')  // Replace \[...\] with $$...$$ (allowing whitespace)
                .replace(/\\\(\s*([\s\S]*?)\s*\\\)/g, '$$$1$')        // Replace \(...\) with $...$ (allowing whitespace)
                .replace(/(?<!\\)\\\[/g, '\\\\[')           // Replace \[ with \\[ (but not \\[)
                .replace(/(?<!\\)\\\]/g, '\\\\]');          // Replace \] with \\] (but not \\])
        }).join('');
    }).join('');
}

function escapeAttr(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function isSmallScreenForArtifact() {
    return window.matchMedia('(max-width: 980px)').matches;
}

function closeHaiArtifactPanel() {
    currentArtifactPayload = null;
    document.body.classList.remove('hai-artifact-open');
    artifactPanel?.classList.remove('is-open');
    artifactPanel?.setAttribute('aria-hidden', 'true');
    if (artifactBackdrop) artifactBackdrop.hidden = true;
    if (artifactBody) artifactBody.innerHTML = '';
    if (artifactDownloadLink) {
        artifactDownloadLink.hidden = true;
        artifactDownloadLink.removeAttribute('href');
        artifactDownloadLink.removeAttribute('download');
    }
}

function openHaiArtifactPanel(payload = {}) {
    if (!artifactPanel || !artifactBody) {
        if (payload.type === 'image' && payload.src) {
            openHaiImageModal(payload.src, payload.title || 'Pratinjau gambar');
        }
        return;
    }
    const type = payload.type || 'text';
    const title = payload.title || (type === 'image' ? 'Gambar Harmonika AI' : 'Artefak Harmonika AI');
    currentArtifactPayload = payload;
    artifactTitle.textContent = title;
    artifactBody.innerHTML = '';
    artifactBody.className = `hai-artifact-panel-body is-${type}`;

    if (type === 'image') {
        const frame = document.createElement('div');
        frame.className = 'hai-artifact-image-frame';
        const img = document.createElement('img');
        img.src = payload.src || '';
        img.alt = title;
        img.loading = 'lazy';
        frame.appendChild(img);
        artifactBody.appendChild(frame);
    } else if (type === 'code') {
        const meta = document.createElement('div');
        meta.className = 'hai-artifact-meta';
        meta.textContent = payload.language ? `Kode · ${payload.language}` : 'Kode';
        const pre = document.createElement('pre');
        pre.className = 'hai-artifact-code';
        const code = document.createElement('code');
        code.textContent = payload.content || '';
        pre.appendChild(code);
        artifactBody.appendChild(meta);
        artifactBody.appendChild(pre);
    } else {
        const pre = document.createElement('pre');
        pre.className = 'hai-artifact-code';
        pre.textContent = payload.content || '';
        artifactBody.appendChild(pre);
    }

    if (artifactDownloadLink) {
        const href = payload.downloadHref || payload.src || '';
        if (href) {
            artifactDownloadLink.href = href;
            artifactDownloadLink.download = payload.downloadName || (type === 'image' ? 'harmonika-ai-image.svg' : 'harmonika-ai-artifact.txt');
            artifactDownloadLink.hidden = false;
        } else {
            artifactDownloadLink.hidden = true;
        }
    }

    document.body.classList.add('hai-artifact-open');
    artifactPanel.classList.add('is-open');
    artifactPanel.setAttribute('aria-hidden', 'false');
    if (artifactBackdrop) artifactBackdrop.hidden = false;
    if (isSmallScreenForArtifact()) {
        artifactPanel.scrollIntoView({ block: 'end', behavior: 'smooth' });
    }
}

artifactCloseButton?.addEventListener('click', closeHaiArtifactPanel);
artifactBackdrop?.addEventListener('click', closeHaiArtifactPanel);
artifactCopyButton?.addEventListener('click', () => {
    const payload = currentArtifactPayload;
    if (!payload) return;
    const text = payload.copyText || payload.content || '';
    if (!text && payload.src) {
        showToast('Pratinjau gambar tidak punya teks untuk disalin.', 'error');
        return;
    }
    navigator.clipboard.writeText(text)
        .then(() => showToast('Artefak disalin.', 'success'))
        .catch(() => showToast('Gagal menyalin artefak.', 'error'));
});

function legacyImageCardHtml(label, thumbUrl, previewUrl) {
    const safeLabel = escapeHtml(label || 'Gambar Harmonika AI');
    const safeThumb = escapeAttr(thumbUrl || previewUrl || '');
    const safePreview = escapeAttr(previewUrl || thumbUrl || '');
    if (!safeThumb && !safePreview) return '';
    return `<figure class="hai-legacy-image"><button type="button" class="hai-legacy-thumb" data-hai-preview="${safePreview || safeThumb}" title="Lihat gambar"><img src="${safeThumb || safePreview}" alt="${safeLabel}" loading="lazy" referrerpolicy="no-referrer"></button><figcaption><strong>${safeLabel}</strong><span>Klik thumbnail untuk lihat pratinjau</span></figcaption></figure>`;
}

function sanitizeMarkdownHtml(html) {
    const template = document.createElement('template');
    template.innerHTML = String(html ?? '');
    const blockedTags = new Set([
        'script', 'style', 'iframe', 'object', 'embed', 'form', 'input', 'textarea', 'select',
        'link', 'meta', 'base', 'foreignobject', 'animate', 'animatetransform', 'animatemotion', 'set'
    ]);
    const urlAttrs = new Set(['href', 'src', 'xlink:href', 'data-hai-preview']);
    const isSafeUrl = (value) => {
        const url = String(value || '').trim();
        if (!url) return true;
        if (url.startsWith('#') || url.startsWith('/') || url.startsWith('./') || url.startsWith('../')) return true;
        if (/^(https?:|mailto:|tel:|data:image\/(?:png|jpeg|jpg|webp|gif|svg\+xml);|blob:)/i.test(url)) return true;
        return false;
    };

    template.content.querySelectorAll('*').forEach(node => {
        const tag = node.tagName.toLowerCase();
        if (blockedTags.has(tag)) {
            node.remove();
            return;
        }

        [...node.attributes].forEach(attr => {
            const name = attr.name.toLowerCase();
            if (name.startsWith('on') || name === 'srcdoc' || name === 'style') {
                node.removeAttribute(attr.name);
                return;
            }
            if (urlAttrs.has(name) && !isSafeUrl(attr.value)) {
                node.removeAttribute(attr.name);
            }
        });

        if (tag === 'a') {
            node.setAttribute('rel', 'noopener noreferrer nofollow');
            const href = node.getAttribute('href') || '';
            if (href.startsWith('/api/files/') && node.hasAttribute('download')) {
                node.removeAttribute('target');
            } else {
                node.setAttribute('target', '_blank');
            }
        }
    });

    return template.innerHTML;
}

function replaceLegacyImageMarkdown(content) {
    let text = String(content ?? '');
    const seen = new Set();
    const remember = (key, html) => {
        if (seen.has(key)) return '';
        seen.add(key);
        return html;
    };

    text = text.replace(/\[!\[([^\]]*)\]\((https:\/\/(?:chat|hai)\.harmonika\.id\/[^)\s]*(?:thumb-poster|poster|image|download)[^)\s]*)\)\]\((https:\/\/(?:chat|hai)\.harmonika\.id\/[^)\s]*)\)/gi, (m, alt, thumb, view) => {
        const key = `${thumb}|${view}`;
        const poster = thumb.replace(/thumb-poster\.jpg\b/i, 'poster.png');
        return remember(key, legacyImageCardHtml(alt || 'Gambar Harmonika AI', thumb, poster || view));
    });

    let posterUrl = '';
    text = text.replace(/\[!\[[^\]]*\]\([^)]*harmonika-icons\/download\.svg[^)]*\)\]\((https:\/\/(?:chat|hai)\.harmonika\.id\/download\/[^)\s]+\/poster\.(?:png|jpe?g|webp|svg))\)/gi, (m, url) => {
        posterUrl = url;
        return '';
    });
    text = text.replace(/\[!\[[^\]]*\]\([^)]*harmonika-icons\/eye\.svg[^)]*\)\]\((https:\/\/(?:chat|hai)\.harmonika\.id\/media\/[^)\s]+)\)/gi, '');
    text = text.replace(/!?\[!\[[^\]]*\]\([^)]*harmonika-icons\/[^)]*\)\]\([^)]*\)/gi, '');
    text = text.replace(/!\[[^\]]*\]\([^)]*harmonika-icons\/[^)]*\)/gi, '');

    text = text.replace(/!\[([^\]]*)\]\((https:\/\/(?:chat|hai)\.harmonika\.id\/download\/[^)\s]+\/(?:thumb-poster\.jpg|poster\.(?:png|jpe?g|webp|svg)))\)/gi, (m, alt, url) => {
        const preview = posterUrl || url.replace(/thumb-poster\.jpg\b/i, 'poster.png');
        return remember(url, legacyImageCardHtml(alt || 'Gambar Harmonika AI', url, preview));
    });

    text = text.replace(/(?:^|[ \t])https:\/\/(?:chat|hai)\.harmonika\.id\/(?:media|download|downloads?|files?)\/[^\s<)]+/gmi, '');
    text = text.replace(/\n{3,}/g, '\n\n');
    return text;
}

function stripImageMarkdownForTextMode(content) {
    let text = String(content ?? '');
    // Text/web answers must never expose legacy media/download previews or inline
    // image artifacts. Official image generation is gated by X-HAI-Intent=image.
    text = text.replace(/\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)/gi, '');
    text = text.replace(/!\[[^\]]*\]\([^)]*\)/gi, '');
    text = text.replace(/(?:^|[ \t])https:\/\/(?:chat|hai)\.harmonika\.id\/(?:media|download|downloads?|files?)\/[^\s<)]+/gmi, '');
    text = text.replace(/\n{3,}/g, '\n\n');
    return text;
}

function stripPublicReasoningBlocks(content) {
    let output = String(content || '');
    const startToken = START_TAG || '<think>';
    const endTokens = Array.from(new Set([END_TAG, ...DEFAULT_END_TAG].filter(Boolean)));
    let guard = 0;
    while (guard < 20) {
        guard += 1;
        const startIndex = output.indexOf(startToken);
        if (startIndex === -1) break;
        let bestEnd = -1;
        let bestToken = '';
        endTokens.forEach(token => {
            const index = output.indexOf(token, startIndex + startToken.length);
            if (index !== -1 && (bestEnd === -1 || index < bestEnd)) {
                bestEnd = index;
                bestToken = token;
            }
        });
        if (bestEnd === -1) {
            output = output.slice(0, startIndex);
            break;
        }
        output = output.slice(0, startIndex) + output.slice(bestEnd + bestToken.length);
    }
    return output.replace(new RegExp(`${escapeRegExp(startToken)}|${endTokens.map(escapeRegExp).join('|')}`, 'gi'), '');
}

// Modify the preprocessMarkdown function
function preprocessMarkdown(content, expanded = false, messageEndTag = null, allowImageArtifacts = false) {
    // Replace LaTeX syntax before processing
    content = replaceLatexSyntax(content);
    content = allowImageArtifacts ? replaceLegacyImageMarkdown(content) : stripImageMarkdownForTextMode(content);

    // Public Harmonika AI should not expose internal reasoning/developer traces.
    // Keep the raw message in history for compatibility, but render only the answer.
    content = stripPublicReasoningBlocks(content).trimStart();
    
    // Check for both start and end tags to form a complete thought process block
    const startIndex = content.indexOf(START_TAG);
    const endIndex = content.indexOf(END_TAG);
    
    // If we have both start and end tags in the correct order
    if (startIndex !== -1 && endIndex !== -1 && endIndex > startIndex) {
        // Extract the hidden text between the tags
        const hiddenText = content.substring(startIndex + START_TAG.length, endIndex).trim();
        // Get the remainder after the end tag
        let remainder = content.substring(endIndex + END_TAG.length);
        
        // Process remainder for proper formatting
        if (remainder.startsWith('\n') && !remainder.startsWith('\n\n')) {
            remainder = '\n' + remainder;
        } else if (!remainder.startsWith('\n')) {
            remainder = '\n\n' + remainder;
        }
        
        // Get duration from current stream or from message history
        let durationText = '';
        if (streamDuration) {
            durationText = ` (${(streamDuration/1000).toFixed(1)}s)`;
        } else {
            // Try to find this message in conversation history
            const message = conversationHistory.find(msg => 
                msg.role === 'assistant' && 
                (typeof msg.content === 'object' ? msg.content.raw : msg.content) === content
            );
            if (message?.thinkingTime) {
                durationText = ` (${(message.thinkingTime/1000).toFixed(1)}s)`;
            }
        }
        
        const shouldShow = expanded !== null ? expanded : !isDeepQueryMode;
        
        if (shouldShow) {
            return `<div class="think-block">
    <button type="button" class="think-toggle" data-hai-think-toggle="true">
        <span>Thought Process${durationText}</span>
        <i class="fa fa-chevron-up" aria-hidden="true"></i>
    </button>
    <div class="think-content" style="display: block;">${escapeHtml(hiddenText).replace(/\n/g, '<br>')}</div>
</div>` + remainder;
        } else {
            return `<div class="think-block">
    <button type="button" class="think-toggle" data-hai-think-toggle="true">
        <span>Thought Process${durationText}</span>
        <i class="fa fa-chevron-down" aria-hidden="true"></i>
    </button>
    <div class="think-content" style="display: none;">${escapeHtml(hiddenText).replace(/\n/g, '<br>')}</div>
</div>` + remainder;
        }
    }

    // If no complete thought process block, escape both start and end tags
    return content.replace(new RegExp(`${escapeRegExp(START_TAG)}|${escapeRegExp(END_TAG)}`, 'gi'), (match) => escapeHtml(match));
}

// Helper function to escape special characters in regex
function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

const CodeBlock = React.memo(({ language, content, fileName, allowImageArtifacts = false }) => {
    const [copied, setCopied] = React.useState(false);
    const isSvgArtifact = React.useMemo(() => {
        const lang = (language || '').split(':')[0].toLowerCase();
        const text = String(content || '').trim();
        return allowImageArtifacts && (lang === 'svg' || /^<svg[\s>]/i.test(text)) && /^<svg[\s\S]*<\/svg>\s*$/i.test(text) && !/<\s*(script|foreignObject|iframe|object|embed|link|meta)\b/i.test(text) && !/\son[a-z]+\s*=/i.test(text) && !/javascript:/i.test(text);
    }, [language, content, allowImageArtifacts]);

    const svgDataUrl = React.useMemo(() => {
        if (!isSvgArtifact) return '';
        return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(String(content || '').trim())}`;
    }, [isSvgArtifact, content]);

    const copyCode = () => {
        navigator.clipboard.writeText(content)
            .then(() => {
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
            })
            .catch(console.error);
    };

    const highlightedCode = React.useMemo(() => {
        try {
            const finalLanguage = (language || 'bash').split(':')[0].toLowerCase();
            return hljs.highlight(content, { 
                language: finalLanguage,
                ignoreIllegals: true 
            }).value;
        } catch (e) {
            console.warn('Failed to highlight code:', e);
            return escapeHtml(content);
        }
    }, [content, language]);

    // Get display language name
    const displayLanguage = React.useMemo(() => {
        if (fileName) return fileName;
        return (language || 'bash').split(':')[0].toLowerCase();
    }, [language, fileName]);

    if (isSvgArtifact) {
        const openSvgCanvas = () => openHaiArtifactPanel({
            type: 'image',
            title: 'Gambar Harmonika AI',
            src: svgDataUrl,
            content: String(content || '').trim(),
            copyText: String(content || '').trim(),
            downloadHref: svgDataUrl,
            downloadName: 'harmonika-ai-image.svg'
        });
        return React.createElement('figure', { className: 'hai-svg-artifact' },
            React.createElement('button', {
                type: 'button',
                className: 'hai-svg-thumb',
                onClick: openSvgCanvas,
                title: 'Buka gambar di kanvas'
            }, React.createElement('img', {
                src: svgDataUrl,
                alt: 'Gambar Harmonika AI',
                loading: 'lazy'
            })),
            React.createElement('figcaption', null,
                React.createElement('strong', null, 'Gambar Harmonika AI'),
                React.createElement('span', null, 'Klik thumbnail untuk buka kanvas')
            ),
            React.createElement('div', { className: 'hai-svg-actions' },
                React.createElement('button', {
                    type: 'button',
                    onClick: openSvgCanvas
                }, 'Kanvas'),
                React.createElement('a', {
                    href: svgDataUrl,
                    download: 'harmonika-ai-image.svg'
                }, 'Unduh SVG'),
                React.createElement('button', {
                    type: 'button',
                    onClick: copyCode
                }, copied ? 'Tersalin' : 'Salin SVG')
            )
        );
    }

    const canOpenCanvas = String(content || '').length > 380;
    return React.createElement('div', { className: 'code-block' },
        React.createElement('div', { className: 'code-title' },
            React.createElement('span', null, displayLanguage),
            React.createElement('div', { className: 'code-title-actions' },
                canOpenCanvas && React.createElement('button', {
                    className: 'copy-button code-canvas-button',
                    onClick: () => openHaiArtifactPanel({
                        type: 'code',
                        title: fileName || `Artefak ${displayLanguage}`,
                        language: displayLanguage,
                        content: String(content || ''),
                        copyText: String(content || ''),
                        downloadHref: `data:text/plain;charset=utf-8,${encodeURIComponent(String(content || ''))}`,
                        downloadName: fileName || `harmonika-ai-${displayLanguage || 'code'}.txt`
                    }),
                    title: 'Buka kode di kanvas',
                    type: 'button',
                    'aria-label': 'Buka kode di kanvas'
                }, 'Kanvas'),
                React.createElement('button', {
                    className: `copy-button${copied ? ' is-copied' : ''}`,
                    onClick: copyCode,
                    title: copied ? 'Kode tersalin' : 'Salin kode',
                    type: 'button',
                    'aria-label': copied ? 'Kode tersalin' : 'Salin kode'
                }, React.createElement('img', {
                    src: haiActionIconSrc(copied ? 'check' : 'copy'),
                    alt: '',
                    'aria-hidden': 'true',
                    className: 'icon-svg'
                }))
            )
        ),
        React.createElement('pre', { className: 'code-pre' },
            React.createElement('code', {
                className: `language-${(language || 'bash').split(':')[0]} hljs`,
                dangerouslySetInnerHTML: { __html: highlightedCode }
            })
        )
    );
});

function openHaiImageModal(src, alt = 'Pratinjau gambar', downloadHref = '') {
    if (!src) return;
    document.querySelector('.hai-image-modal')?.remove();
    const modal = document.createElement('div');
    modal.className = 'hai-image-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-label', alt);
    const safeSrc = src.replace(/"/g, '&quot;');
    const safeAlt = alt.replace(/"/g, '&quot;');
    const safeDownload = String(downloadHref || '').replace(/"/g, '&quot;');
    modal.innerHTML = `
        <div class="hai-image-modal-card" role="document">
            <img src="${safeSrc}" alt="${safeAlt}">
            <div class="hai-image-modal-actions">
                <span>${safeAlt}</span>
                ${safeDownload ? `<a href="${safeDownload}" download>Unduh PNG</a>` : ''}
                <button type="button" aria-label="Tutup pratinjau">Tutup</button>
            </div>
        </div>`;
    modal.addEventListener('click', () => modal.remove());
    modal.querySelector('.hai-image-modal-card')?.addEventListener('click', event => {
        event.stopPropagation();
        const action = event.target.closest('a,button');
        if (action?.tagName === 'BUTTON') {
            modal.remove();
        }
    });
    document.body.appendChild(modal);
}

document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
        closeHaiArtifactPanel();
        document.querySelector('.hai-image-modal')?.remove();
    }
});

document.addEventListener('click', event => {
    const target = event.target.closest?.('[data-hai-preview]');
    if (!target) return;
    event.preventDefault();
    const src = target.getAttribute('data-hai-preview');
    const figure = target.closest('.hai-legacy-image');
    const title = target.querySelector('img')?.alt || figure?.querySelector('strong')?.textContent || 'Pratinjau gambar';
    const downloadHref = figure?.querySelector('a[download]')?.getAttribute('href') || '';
    openHaiImageModal(src, title, downloadHref);
});

document.addEventListener('click', event => {
    const container = event.target.closest?.('.assistant-message-container, .user-message-container');
    document.querySelectorAll('.assistant-message-container.is-actions-active, .user-message-container.is-actions-active').forEach(node => {
        if (node !== container && !node.contains(event.target)) {
            node.classList.remove('is-actions-active');
        }
    });
    if (!container || event.target.closest?.('.message-buttons')) {
        return;
    }
    container.classList.add('is-actions-active');
});

// Add this before the MarkdownContent component
const TokenCache = {
    tokens: null,
    content: '',
    getTokens: (content) => {
        // Only re-parse if content has changed
        if (content !== TokenCache.content) {
            TokenCache.tokens = marked.lexer(content);
            TokenCache.content = content;
        }
        return TokenCache.tokens;
    }
};

// Modify the MarkdownContent component
const MarkdownContent = React.memo(({ content, messageEndTag }) => {
    const contentRef = React.useRef(null);
    const [selectionState, setSelectionState] = React.useState(null);
    const lastTokensRef = React.useRef([]);
    const [renderedTokens, setRenderedTokens] = React.useState([]);
    
    // Modified saveSelection: capture additional information for selection direction
    const saveSelection = React.useCallback(() => {
        if (!contentRef.current) return null;

        const selection = window.getSelection();
        if (!selection.rangeCount) return null;

        const range = selection.getRangeAt(0);
        if (!contentRef.current.contains(range.commonAncestorContainer)) return null;

        // Helper: return all text nodes within contentRef
        const getAllTextNodes = (node) => {
            const textNodes = [];
            const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT, null, false);
            let currentNode;
            while (currentNode = walker.nextNode()) {
                textNodes.push(currentNode);
            }
            return textNodes;
        };

        const allTextNodes = getAllTextNodes(contentRef.current);
        const startNodeIndex = allTextNodes.indexOf(range.startContainer);
        const endNodeIndex = allTextNodes.indexOf(range.endContainer);
        const anchorNodeIndex = allTextNodes.indexOf(selection.anchorNode);
        const focusNodeIndex = allTextNodes.indexOf(selection.focusNode);

        // Validate that both the range and selection indices are within bounds
        if (
            startNodeIndex === -1 ||
            endNodeIndex === -1 ||
            anchorNodeIndex === -1 ||
            focusNodeIndex === -1
        ) {
            return null;
        }

        return {
            startNodeIndex,
            endNodeIndex,
            startOffset: range.startOffset,
            endOffset: range.endOffset,
            anchorNodeIndex,
            anchorOffset: selection.anchorOffset,
            focusNodeIndex,
            focusOffset: selection.focusOffset,
            text: range.toString()
        };
    }, []);

    // Modified restoreSelection: use setBaseAndExtent to restore selection direction if available
    const restoreSelection = React.useCallback((savedSelection) => {
        if (!savedSelection || !contentRef.current) return;
        try {
            const allTextNodes = [];
            const walker = document.createTreeWalker(
                contentRef.current,
                NodeFilter.SHOW_TEXT,
                null,
                false
            );
            let currentNode;
            while (currentNode = walker.nextNode()) {
                allTextNodes.push(currentNode);
            }

            const {
                anchorNodeIndex,
                anchorOffset,
                focusNodeIndex,
                focusOffset
            } = savedSelection;

            if (
                anchorNodeIndex < 0 ||
                anchorNodeIndex >= allTextNodes.length ||
                focusNodeIndex < 0 ||
                focusNodeIndex >= allTextNodes.length
            ) {
                return;
            }

            const selection = window.getSelection();
            selection.removeAllRanges();

            // Use setBaseAndExtent (supported in most modern browsers) to keep the selection direction intact
            if (typeof selection.setBaseAndExtent === 'function') {
                selection.setBaseAndExtent(
                    allTextNodes[anchorNodeIndex],
                    anchorOffset,
                    allTextNodes[focusNodeIndex],
                    focusOffset
                );
            } else {
                // Fallback: If setBaseAndExtent is not available, fall back to using a range.
                const range = document.createRange();
                range.setStart(
                    allTextNodes[savedSelection.startNodeIndex],
                    savedSelection.startOffset
                );
                range.setEnd(
                    allTextNodes[savedSelection.endNodeIndex],
                    savedSelection.endOffset
                );
                selection.addRange(range);
            }
        } catch (e) {
            console.warn('Could not restore selection:', e);
        }
    }, []);

    React.useEffect(() => {
        const savedSelection = saveSelection();
        if (savedSelection) {
            setSelectionState(savedSelection);
        }
    }, [content, saveSelection]);

    React.useEffect(() => {
        if (selectionState) {
            requestAnimationFrame(() => {
                restoreSelection(selectionState);
            });
        }
    }, [selectionState, restoreSelection]);

    // Modify this effect to pre-process the markdown content before tokenization
    React.useEffect(() => {
        // If the content is an object (with a raw field and a toggle flag), use them.
        let rawContent, expanded, allowImageArtifacts;
        if (typeof content === 'object' && content !== null) {
            rawContent = content.raw;
            expanded = content.reasoningExpanded;
            allowImageArtifacts = Boolean(content.allowImageArtifacts);
        } else {
            rawContent = content;
            expanded = false;
            allowImageArtifacts = false;
        }
        
        // Pass the messageEndTag to preprocessMarkdown
        const processedContent = preprocessMarkdown(rawContent, expanded, messageEndTag, allowImageArtifacts);
        
        // Get tokens from the preprocessed markdown instead of raw content
        const tokens = TokenCache.getTokens(processedContent);
        
        // Only update if tokens have actually changed
        if (!areTokensEqual(tokens, lastTokensRef.current)) {
            lastTokensRef.current = tokens;
            setRenderedTokens(tokens.map((token, index) => {
                if (token.type === 'code') {
                    const [lang, ...pathParts] = (token.lang || '').split(':');
                    const filePath = pathParts.join(':');
                    
                    return {
                        type: 'code',
                        key: `code-${index}`,
                        props: {
                            language: lang || 'bash',
                            content: token.text.replace(/<span class="hljs-[^"]*">/g, '').replace(/<\/span>/g, ''),
                            fileName: filePath || token.fileName,
                            allowImageArtifacts
                        }
                    };
                } else if (token.type === 'list') {
                    return {
                        type: 'list',
                        key: `list-${index}`,
                        token: token
                    };
                } else {
                    return {
                        type: 'other',
                        key: `content-${index}`,
                        html: sanitizeMarkdownHtml(marked.parser([token])),
                        className: token.type
                    };
                }
            }));
        }
    }, [content, messageEndTag]);

    const renderTokenComponent = React.useCallback((tokenData) => {
        switch (tokenData.type) {
            case 'code':
                return React.createElement(CodeBlock, {
                    key: tokenData.key,
                    ...tokenData.props
                });
            case 'list':
                return React.createElement(MarkdownList, {
                    key: tokenData.key,
                    token: tokenData.token
                });
            default:
                return React.createElement('div', {
                    key: tokenData.key,
                    className: `markdown-block ${tokenData.className}`,
                    dangerouslySetInnerHTML: { __html: tokenData.html }
                });
        }
    }, []);

    return React.createElement('div', {
        ref: contentRef,
        className: 'markdown-content',
        onMouseUp: () => {
            const savedSelection = saveSelection();
            if (savedSelection) {
                setSelectionState(savedSelection);
            }
        }
    }, renderedTokens.map(renderTokenComponent));
});

// Add this helper function
function areTokensEqual(tokensA, tokensB) {
    if (tokensA === tokensB) return true;
    if (!tokensA || !tokensB) return false;
    if (tokensA.length !== tokensB.length) return false;

    return tokensA.every((tokenA, index) => {
        const tokenB = tokensB[index];
        if (tokenA.type !== tokenB.type) return false;
        
        // For code blocks, compare content and language
        if (tokenA.type === 'code') {
            return tokenA.text === tokenB.text && tokenA.lang === tokenB.lang;
        }
        
        // For lists, compare raw content
        if (tokenA.type === 'list') {
            return tokenA.raw === tokenB.raw;
        }
        
        // For other tokens, compare raw content
        return tokenA.raw === tokenB.raw;
    });
}

// Modify the MarkdownList component
const MarkdownList = React.memo(({ token }) => {
    const listRef = React.useRef(null);
    const [processedHtml, setProcessedHtml] = React.useState('');
    
    React.useEffect(() => {
        // Create a temporary div to parse the HTML
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = sanitizeMarkdownHtml(marked.parser([token]));
        
        // Process all code blocks within the list
        const codeBlocks = tempDiv.querySelectorAll('pre code');
        codeBlocks.forEach((codeElement) => {
            const language = (codeElement.className.match(/language-(\w+)/) || [])[1] || 'bash';
            const content = codeElement.textContent;
            
            try {
                // Apply syntax highlighting
                const highlightedCode = hljs.highlight(content, {
                    language: language,
                    ignoreIllegals: true
                }).value;
                
                // Create wrapper elements
                const codeBlockDiv = document.createElement('div');
                codeBlockDiv.className = 'code-block';
                
                const codeTitleDiv = document.createElement('div');
                codeTitleDiv.className = 'code-title';
                codeTitleDiv.innerHTML = `
                    <span>${language}</span>
                    <button class="copy-button" type="button" title="Salin kode" aria-label="Salin kode">
                        <img src="${haiIconSrc('copy')}" alt="" aria-hidden="true" class="icon-svg">
                    </button>
                `;
                
                const preElement = document.createElement('pre');
                preElement.className = 'code-pre';
                
                const newCodeElement = document.createElement('code');
                newCodeElement.className = `language-${language} hljs`;
                newCodeElement.innerHTML = highlightedCode;
                
                // Assemble the elements
                preElement.appendChild(newCodeElement);
                codeBlockDiv.appendChild(codeTitleDiv);
                codeBlockDiv.appendChild(preElement);
                
                // Replace the original pre element with our new structure
                codeElement.parentElement.replaceWith(codeBlockDiv);
            } catch (e) {
                console.warn('Failed to highlight code in list:', e);
            }
        });
        
        // Update the state with processed HTML
        setProcessedHtml(sanitizeMarkdownHtml(tempDiv.innerHTML));
    }, [token.raw]); // Re-run when token content changes
    
    React.useEffect(() => {
        if (listRef.current) {
            // Add click handlers for copy buttons
            const copyButtons = listRef.current.querySelectorAll('.copy-button');
            copyButtons.forEach(button => {
                button.onclick = () => {
                    const codeBlock = button.closest('.code-block');
                    const codeElement = codeBlock.querySelector('code');
                    const content = codeElement.textContent;
                    
                    copyToClipboard(content, button);
                };
            });
        }
    }, [processedHtml]); // Re-run when HTML changes
    
    return React.createElement('div', {
        ref: listRef,
        className: 'markdown-block list',
        dangerouslySetInnerHTML: { __html: processedHtml }
    });
}, (prevProps, nextProps) => prevProps.token.raw === nextProps.token.raw);

// Sidebar setup
const sidebarButtons = document.createElement('div');
sidebarButtons.className = 'sidebar-buttons';
sidebarButtons.style.display = 'none';

const sidebarBackdrop = document.createElement('div');
sidebarBackdrop.className = 'hai-sidebar-backdrop';

const showSidebarBtn = document.createElement('button');
showSidebarBtn.className = 'sidebar-button';
showSidebarBtn.innerHTML = `<img src="${haiIconSrc('sidebar')}" alt="Buka/tutup sidebar" class="icon-svg">`;

const newChatSidebarBtn = document.createElement('button');
newChatSidebarBtn.className = 'sidebar-button';
newChatSidebarBtn.innerHTML = `<img src="${haiIconSrc('chat')}" alt="Chat Baru" class="icon-svg">`;

sidebarButtons.appendChild(showSidebarBtn);
sidebarButtons.appendChild(newChatSidebarBtn);
rightSide.insertBefore(sidebarButtons, rightSide.firstChild);
document.body.appendChild(sidebarBackdrop);

// Utility functions
function copyToClipboard(text, button = null) {
    navigator.clipboard.writeText(text).then(() => {
        console.log('Text copied successfully');
        if (button) {
            const icon = button.querySelector('.icon-svg');
            button.classList.add('is-copied');
            icon.src = haiActionIconSrc('check');
            if (button.classList.contains('copy-button')) {
                button.title = 'Kode tersalin';
                button.setAttribute('aria-label', 'Kode tersalin');
            }
            setTimeout(() => {
                icon.src = haiActionIconSrc('copy');
                if (button.classList.contains('copy-button')) {
                    button.title = 'Salin kode';
                    button.setAttribute('aria-label', 'Salin kode');
                }
                button.classList.remove('is-copied');
            }, 2000);
        }
    }).catch(err => {
        console.error('Failed to copy text: ', err);
        // Fallback for older browsers
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        try {
            document.execCommand('copy');
            console.log('Text copied successfully (fallback)');
            if (button) {
                const icon = button.querySelector('.icon-svg');
                button.classList.add('is-copied');
                icon.src = haiActionIconSrc('check');
                if (button.classList.contains('copy-button')) {
                    button.title = 'Kode tersalin';
                    button.setAttribute('aria-label', 'Kode tersalin');
                }
                setTimeout(() => {
                    icon.src = haiActionIconSrc('copy');
                    if (button.classList.contains('copy-button')) {
                        button.title = 'Salin kode';
                        button.setAttribute('aria-label', 'Salin kode');
                    }
                    button.classList.remove('is-copied');
                }, 2000);
            }
        } catch (err) {
            console.error('Failed to copy text (fallback): ', err);
        }
        document.body.removeChild(textarea);
    });
}

// Markdown configuration
marked.setOptions({
    breaks: true,
    gfm: true,
    headerIds: false,
    mangle: false
});

// Function to initialize highlight.js
function initializeHighlighting() {
    document.querySelectorAll('pre code').forEach((block) => {
        hljs.highlightBlock(block);
    });
}

// Code block title function
function wrapCodeBlocksWithTitle(element, markdownText) {
    const preElements = element.querySelectorAll('pre');
    const codeBlockRegex = /```([a-zA-Z0-9+#]+)?(?::[\w\/.-]+)?\n([\s\S]*?)```/g;
    let codeBlocks = [...markdownText.matchAll(codeBlockRegex)];
    
    preElements.forEach((pre, index) => {
        // Skip if already wrapped
        if (pre.parentElement.classList.contains('code-block')) return;
        
        const code = pre.querySelector('code');
        if (!code) return;

        // Get language from the class name that highlight.js adds
        let languageClass = code.className.match(/language-(\w+)/);
        let language = languageClass ? languageClass[1] : 'sh';
        
        // Highlight the code block
        hljs.highlightBlock(code);

        // Create wrapper
        const wrapper = document.createElement('div');
        wrapper.className = 'code-block';
        wrapper.innerHTML = `
            <div class="code-title">
                <span>${language}</span>
                <button class="copy-button" type="button" title="Salin kode" aria-label="Salin kode">
                    <img src="${haiIconSrc('copy')}" alt="" aria-hidden="true" class="icon-svg">
                </button>
            </div>
        `;

        // Move the pre element inside wrapper
        pre.parentNode.insertBefore(wrapper, pre);
        wrapper.appendChild(pre);
        
        // Click event listener to copy button
        const copyButton = wrapper.querySelector('.copy-button');
        copyButton.addEventListener('click', () => {
            const codeText = code.textContent.replace(/\n$/, '');
            copyToClipboard(codeText, copyButton);
        });
    });
}

// Define database schema
db.version(2).stores({
    settings: 'key',
    conversations: 'id,title,messages,createdAt',
    currentConversation: 'key'
}).upgrade(tx => {
    // Upgrade existing messages to new format
    return tx.conversations.toCollection().modify(conversation => {
        if (conversation.messages) {
            conversation.messages = conversation.messages.map(msg => {
                if (msg.role === 'assistant' && !msg.endTag) {
                    msg.endTag = '</think>'; // Default end tag for existing messages
                }
                return msg;
            });
        }
    });
});

db.version(3).stores({
    settings: 'key',
    conversations: 'id,title,updated,createdAt',
    currentConversation: 'key'
});

function normalizeConversationRecord(id, conversation = {}) {
    const now = Date.now();
    return {
        id,
        title: cleanConversationTitle(conversation.title || 'Chat Baru'),
        messages: Array.isArray(conversation.messages) ? conversation.messages : [],
        createdAt: Number(conversation.createdAt || id || now) || now,
        updated: Number(conversation.updated || conversation.createdAt || id || now) || now
    };
}

function cleanConversationTitle(title) {
    return String(title || 'Chat Baru')
        .replace(/^["'“”‘’]+|["'“”‘’]+$/g, '')
        .replace(/\s+/g, ' ')
        .trim()
        .slice(0, 80) || 'Chat Baru';
}

function deriveLocalConversationTitle(message = '') {
    const cleaned = String(message || '')
        .replace(/^(browser\s+qa|qa|smoke)[\s:_-]+/i, '')
        .replace(/^(jawab|jelaskan|buatkan|buat|tolong|mohon)\s+/i, '')
        .replace(/^(dalam\s+)?satu\s+kalimat\s*:?\s*/i, '')
        .replace(/\s+/g, ' ')
        .trim();
    if (!cleaned) return 'Chat Baru';
    const compact = cleaned.length > 48 ? `${cleaned.slice(0, 45).trim()}…` : cleaned;
    return cleanConversationTitle(compact);
}

function conversationSortValue(id, conversation = {}) {
    return Number(conversation.updated || conversation.createdAt || id || 0) || 0;
}

function formatConversationMeta(id, conversation = {}) {
    const value = conversationSortValue(id, conversation);
    if (!value) return '';
    const date = new Date(value);
    const now = new Date();
    if (date.toDateString() === now.toDateString()) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function conversationSearchText(id, conversation = {}) {
    const messages = Array.isArray(conversation.messages) ? conversation.messages.slice(-8) : [];
    const messageText = messages.map(msg => {
        const content = msg?.content;
        if (typeof content === 'string') return content;
        if (content && typeof content.raw === 'string') return content.raw;
        if (Array.isArray(content)) {
            return content.map(item => item?.text || '').join(' ');
        }
        return '';
    }).join(' ');
    return `${id} ${conversation.title || ''} ${messageText}`.toLowerCase();
}

function loadDeletedConversationTombstones() {
    try {
        const value = JSON.parse(localStorage.getItem(DELETED_CONVERSATIONS_KEY) || '{}');
        return value && typeof value === 'object' ? value : {};
    } catch (_) {
        return {};
    }
}

function saveDeletedConversationTombstones(tombstones) {
    const entries = Object.entries(tombstones || {})
        .map(([id, updated]) => [id, Number(updated || 0)])
        .filter(([id, updated]) => /^[A-Za-z0-9._-]{1,80}$/.test(id) && updated > 0)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 400);
    localStorage.setItem(DELETED_CONVERSATIONS_KEY, JSON.stringify(Object.fromEntries(entries)));
}

function markConversationDeleted(conversationId, updated = Date.now()) {
    const tombstones = loadDeletedConversationTombstones();
    tombstones[conversationId] = Math.max(Number(tombstones[conversationId] || 0), Number(updated || Date.now()));
    saveDeletedConversationTombstones(tombstones);
}

function renderHistoryEmpty(message, subtext = '') {
    const empty = document.createElement('div');
    empty.className = 'hai-history-empty';
    empty.innerHTML = `<i class="fa fa-comments-o" aria-hidden="true"></i><strong>${escapeHtml(message)}</strong>${subtext ? `<span>${escapeHtml(subtext)}</span>` : ''}`;
    chatHistory.appendChild(empty);
}

async function renameConversation(conversationId = currentConversationId) {
    if (!conversationId || !conversations[conversationId]) {
        showToast('Belum ada chat aktif untuk diubah judulnya.', 'error');
        return;
    }
    const currentTitle = cleanConversationTitle(conversations[conversationId].title || 'Chat Baru');
    const nextTitle = window.prompt('Ubah judul chat:', currentTitle);
    if (nextTitle === null) return;
    const cleanedTitle = cleanConversationTitle(nextTitle);
    if (!cleanedTitle || cleanedTitle === currentTitle) return;

    conversations[conversationId].title = cleanedTitle;
    conversations[conversationId].updated = Date.now();
    if (conversationId === currentConversationId) {
        conversationHistory = [...(conversations[conversationId].messages || conversationHistory)];
    }
    await saveConversationsToStorage();
    updateChatHistory();
    syncTopbarTitle();
    showToast('Judul chat diperbarui.', 'success');
}

async function copyCurrentChatLink() {
    if (!currentConversationId) {
        if (!isPrivateChat) {
            startNewChat();
        }
    }
    if (!currentConversationId) {
        showToast('Belum ada chat untuk disalin linknya.', 'error');
        return;
    }
    setConversationUrl(currentConversationId, true);
    try {
        await navigator.clipboard.writeText(window.location.href);
        showToast('Link chat disalin.', 'success');
    } catch (error) {
        copyToClipboard(window.location.href);
        showToast('Link chat disalin.', 'success');
    }
}

function stripHistoryImagesFromMessage(message) {
    const clean = JSON.parse(JSON.stringify(message || {}));
    if (Array.isArray(clean.content)) {
        clean.content = clean.content.map(part => {
            if (part?.type === 'image_url') {
                return {
                    type: 'image_url',
                    image_url: { url: '[image omitted from history]' }
                };
            }
            if (part?.type === 'text') {
                return {
                    type: 'text',
                    text: String(part.text || '').slice(0, 4000)
                };
            }
            return part;
        });
    }
    return clean;
}

function stripHistoryImagesFromChat(chat) {
    const clean = normalizeConversationRecord(chat.id, chat);
    clean.messages = (clean.messages || []).map(stripHistoryImagesFromMessage);
    return clean;
}

function serverHistoryPayload(options = {}) {
    const stripImages = Boolean(options.stripImages);
    const deletedTombstones = loadDeletedConversationTombstones();
    return {
        active: currentConversationId || '',
        baseUpdated: serverHistoryLastUpdated || 0,
        deleted: Object.entries(deletedTombstones)
            .map(([id, updated]) => ({ id, updated: Number(updated || 0) }))
            .filter(item => item.id && item.updated > 0)
            .slice(0, 400),
        chats: Object.entries(conversations)
            .map(([id, conversation]) => stripImages
                ? stripHistoryImagesFromChat({ ...conversation, id })
                : normalizeConversationRecord(id, conversation))
            .sort((a, b) => Number(b.updated || 0) - Number(a.updated || 0))
            .slice(0, 200)
    };
}

async function pullServerHistory() {
    try {
        const response = await fetch('/api/history', {
            method: 'GET',
            credentials: 'same-origin',
            cache: 'no-store'
        });
        if (!response.ok) return null;
        const data = await response.json();
        if (!data || !Array.isArray(data.chats)) return null;

        let changed = false;
        if (Array.isArray(data.deleted)) {
            const tombstones = loadDeletedConversationTombstones();
            for (const item of data.deleted) {
                if (!item?.id) continue;
                const updated = Number(item.updated || 0);
                if (updated <= 0) continue;
                tombstones[item.id] = Math.max(Number(tombstones[item.id] || 0), updated);
                const localChat = conversations[item.id];
                if (localChat && updated >= conversationSortValue(item.id, localChat)) {
                    delete conversations[item.id];
                    await db.conversations.delete(item.id);
                    if (currentConversationId === item.id) {
                        currentConversationId = null;
                        conversationHistory = [];
                    }
                    changed = true;
                }
            }
            saveDeletedConversationTombstones(tombstones);
        }

        const deletedTombstones = loadDeletedConversationTombstones();
        data.chats.forEach(serverChat => {
            if (!serverChat || !serverChat.id) return;
            const deletedAt = Number(deletedTombstones[serverChat.id] || 0);
            if (deletedAt >= Number(serverChat.updated || 0)) return;
            const localChat = conversations[serverChat.id];
            const normalizedServer = normalizeConversationRecord(serverChat.id, serverChat);
            if (!localChat || conversationSortValue(serverChat.id, normalizedServer) > conversationSortValue(serverChat.id, localChat)) {
                conversations[serverChat.id] = normalizedServer;
                changed = true;
            }
        });

        if (data.active && conversations[data.active] && !currentConversationId) {
            currentConversationId = data.active;
        }
        serverHistoryLastUpdated = Number(data.updated || serverHistoryLastUpdated || 0);

        if (changed) {
            for (const [id, conversation] of Object.entries(conversations)) {
                await db.conversations.put(normalizeConversationRecord(id, conversation));
            }
        }

        serverHistoryReady = true;
        return data;
    } catch (error) {
        console.warn('Server history pull skipped:', error);
        return null;
    }
}

async function pushServerHistoryNow() {
    if (isPushingServerHistory) return;
    isPushingServerHistory = true;
    try {
        let response = await fetch('/api/history', {
            method: 'PUT',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(serverHistoryPayload())
        });
        if (response.status === 413) {
            response = await fetch('/api/history', {
                method: 'PUT',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(serverHistoryPayload({ stripImages: true }))
            });
            if (response.ok && !historySyncDegradedNotified) {
                historySyncDegradedNotified = true;
                showToast('Riwayat disimpan tanpa data gambar besar agar tetap ringan.', 'success');
            }
        }
        if (response.status === 409) {
            await pullServerHistory();
            response = await fetch('/api/history', {
                method: 'PUT',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(serverHistoryPayload({ stripImages: true }))
            });
        }
        if (!response.ok) {
            let retryAfter = 0;
            try {
                const errorData = await response.json();
                retryAfter = Number(errorData?.retry_after || 0);
            } catch (_) {}
            if (response.status === 429 && retryAfter > 0) {
                window.clearTimeout(serverHistorySyncTimer);
                serverHistorySyncTimer = window.setTimeout(() => pushServerHistoryNow(), retryAfter * 1000);
            }
            throw new Error(`history_sync_failed_${response.status}`);
        }
        const data = await response.json().catch(() => null);
        serverHistoryLastUpdated = Number(data?.updated || serverHistoryLastUpdated || 0);
        serverHistoryReady = true;
    } catch (error) {
        console.warn('Server history sync skipped:', error);
    } finally {
        isPushingServerHistory = false;
    }
}

function scheduleServerHistorySync() {
    window.clearTimeout(serverHistorySyncTimer);
    serverHistorySyncTimer = window.setTimeout(() => {
        pushServerHistoryNow();
    }, serverHistoryReady ? 600 : 1200);
}

// Save conversations to IndexedDB
async function saveConversationsToStorage() {
    try {
        // Save all conversations
        for (const [id, conversation] of Object.entries(conversations)) {
            const normalized = normalizeConversationRecord(id, conversation);
            if (id === currentConversationId) {
                normalized.updated = Date.now();
            }
            conversations[id] = normalized;
            await db.conversations.put(normalized);
        }
        
        // Save current conversation ID
        await db.currentConversation.put({
            key: 'currentId',
            value: currentConversationId
        });
        scheduleServerHistorySync();
    } catch (error) {
        console.error('Error saving conversations:', error);
    }
}

// Load conversations from IndexedDB
async function loadConversationsFromStorage() {
    try {
        // Load conversations
        const storedConversations = await db.conversations.toArray();
        conversations = {};
        storedConversations.forEach(conv => {
            conversations[conv.id] = normalizeConversationRecord(conv.id, conv);
        });

        const serverData = await pullServerHistory();

        let pathConversationId = urlConversationId();
        const deletedTombstones = loadDeletedConversationTombstones();

        let createdFromPath = false;
        if (pathConversationId && deletedTombstones[pathConversationId]) {
            setConversationUrl('', true);
            pathConversationId = '';
        } else if (pathConversationId && !conversations[pathConversationId]) {
            conversations[pathConversationId] = normalizeConversationRecord(pathConversationId, {
                title: 'Chat Baru',
                messages: []
            });
            createdFromPath = true;
        }

        // Load current conversation ID
        const currentIdRecord = await db.currentConversation.get('currentId');
        const serverActiveId = serverData && serverData.active && conversations[serverData.active] ? serverData.active : '';
        const nextConversationId = pathConversationId || (currentIdRecord && conversations[currentIdRecord.value] ? currentIdRecord.value : '') || serverActiveId;
        if (nextConversationId && conversations[nextConversationId]) {
            currentConversationId = nextConversationId;
            conversationHistory = [...conversations[currentConversationId].messages];
            setConversationUrl(currentConversationId, true);
            
            // Clear and rebuild chat messages
            chatMessages.innerHTML = '';
            
            conversationHistory.forEach(msg => {
                if (msg.role === 'user') {
                    const messageContainer = document.createElement('div');
                    messageContainer.className = 'user-message-container';
                    
                    const messageDiv = document.createElement('div');
                    messageDiv.classList.add('user-message');
                    // Preserve line breaks by replacing them with <br> tags
                    messageDiv.innerHTML = formatUserMessage(msg.content);
                    
                    messageContainer.appendChild(messageDiv);
                    
                    // Create button container
                    const buttonContainer = document.createElement('div');
                    buttonContainer.className = 'message-buttons';
                    
                    // Add edit button first
                    const editButton = document.createElement('button');
                    editButton.className = 'message-edit-button';
                    editButton.innerHTML = haiIconImg('pencil', 'Edit pesan');
                    editButton.onclick = () => handleMessageEdit(messageDiv, msg.content, 'user');
                    
                    // Add copy button after edit button
                    const copyButton = document.createElement('button');
                    copyButton.className = 'message-copy-button';
                    copyButton.innerHTML = haiIconImg('copy', 'Salin pesan');
                    copyButton.onclick = () => copyToClipboard(msg.content, copyButton);
                    
                    // Add delete button
                    const deleteButton = document.createElement('button');
                    deleteButton.className = 'message-delete-button';
                    deleteButton.innerHTML = haiIconImg('trash', 'Hapus pesan');
                    deleteButton.onclick = () => handleMessageDelete(messageDiv, msg.content, 'user');
                    
                    // Append buttons in the new order
                    buttonContainer.appendChild(editButton);
                    buttonContainer.appendChild(copyButton);
                    buttonContainer.appendChild(deleteButton);
                    messageContainer.appendChild(buttonContainer);
                    
                    chatMessages.appendChild(messageContainer);
                } else if (msg.role === 'assistant') {
                    const messageContainer = document.createElement('div');
                    messageContainer.className = 'assistant-message-container';
                    if (msg.messageId) {
                        messageContainer.dataset.messageId = msg.messageId;
                    }
                    if (msg.isError) {
                        messageContainer.dataset.error = 'true';
                    }
                    
                    const messageDiv = document.createElement('div');
                    messageDiv.classList.add('assistant-message');
                    
                    // Create React root for assistant message
                    if (!messageDiv.reactRoot) {
                        messageDiv.reactRoot = ReactDOM.createRoot(messageDiv);
                    }
                    
                    // Pass both content and stored end tag
                    messageDiv.reactRoot.render(
                        React.createElement(MarkdownContent, {
                            content: markdownContentForStoredMessage(msg),
                            messageEndTag: msg.endTag
                        })
                    );
                    
                    messageContainer.appendChild(messageDiv);
                    appendSourceChips(messageContainer, messageSources(msg));
                    if (msg.isError) {
                        appendAssistantActionButtonsIfMissing(
                            messageContainer,
                            messageDiv,
                            typeof msg.content === 'object' ? msg.content.raw : msg.content
                        );
                        chatMessages.appendChild(messageContainer);
                        return;
                    }

                    streamDuration = null;
                    
                    // Create button container
                    const buttonContainer = document.createElement('div');
                    buttonContainer.className = 'message-buttons';
                    
                    const editButton = document.createElement('button');
                    editButton.className = 'message-edit-button';
                    editButton.innerHTML = haiIconImg('pencil', 'Edit pesan');
                    editButton.onclick = () => handleMessageEdit(messageDiv, 
                        typeof msg.content === 'object' ? msg.content.raw : msg.content, 
                        'assistant'
                    );
                    
                    const copyButton = document.createElement('button');
                    copyButton.className = 'message-copy-button';
                    copyButton.innerHTML = haiIconImg('copy', 'Salin pesan');
                    copyButton.onclick = () => copyToClipboard(
                        typeof msg.content === 'object' ? msg.content.raw : msg.content, 
                        copyButton
                    );
                    
                    const deleteButton = document.createElement('button');
                    deleteButton.className = 'message-delete-button';
                    deleteButton.innerHTML = haiIconImg('trash', 'Hapus pesan');
                    deleteButton.onclick = () => handleMessageDelete(messageDiv, 
                        typeof msg.content === 'object' ? msg.content.raw : msg.content, 
                        'assistant'
                    );
                    
                    const continueButton = document.createElement('button');
                    continueButton.className = 'message-continue-button';
                    continueButton.innerHTML = haiIconImg('continue', 'Lanjutkan jawaban');
                    continueButton.onclick = () => handleContinueGeneration(messageDiv, 
                        typeof msg.content === 'object' ? msg.content.raw : msg.content
                    );
                    
                    buttonContainer.appendChild(editButton);
                    buttonContainer.appendChild(copyButton);
                    buttonContainer.appendChild(deleteButton);
                    buttonContainer.appendChild(continueButton);
                    messageContainer.appendChild(buttonContainer);
                    
                    chatMessages.appendChild(messageContainer);
                }
            });
            if (!conversationHistory.length) showHaiWelcome();
            if (createdFromPath) {
                saveConversationsToStorage();
                updateChatHistory();
            }
        } else {
            showHaiWelcome();
        }
        
        updateChatHistory();
        
    } catch (error) {
        console.error('Error loading conversations:', error);
        showHaiWelcome();
    } finally {
        ensureHaiWelcomeWhenEmpty();
    }
}

async function fetchModels() {
    try {
        const response = await fetch('/fetch-models');
        const models = await response.json();
        selectItems.innerHTML = '';

        // Create search input
        const modelSearch = document.createElement('input');
        modelSearch.type = 'text';
        modelSearch.id = 'model-search';
        modelSearch.placeholder = 'Cari model...';
        modelSearch.style.cssText = `
            width: 100%;
            padding: 10px;
            margin-bottom: 10px;
            background-color: #262626;
            color: #D5D5D5;
            border: none;
            border-radius: 5px;
        `;
        selectItems.appendChild(modelSearch);

        const safeModels = (Array.isArray(models) && models.length ? models : ['harmonika-ai']);

        // Sorted model options
        safeModels.sort().forEach(model => {
            const option = document.createElement('div');
            option.textContent = model;
            option.setAttribute('data-value', model);
            option.classList.add('model-option');
            selectItems.appendChild(option);
        });

        let highlightedIndex = -1;

        const getVisibleOptions = () => [...selectItems.querySelectorAll('.model-option')]
            .filter(option => option.style.display !== 'none');

        const clearHighlight = () => {
            selectItems.querySelectorAll('.model-option')
                .forEach(option => option.classList.remove('highlighted'));
        };

        const highlightOption = (index, visibleOptions) => {
            clearHighlight();
            highlightedIndex = index;
            visibleOptions[index].classList.add('highlighted');
            visibleOptions[index].scrollIntoView({ block: 'nearest' });
            if (index === 0) {
                selectItems.scrollTop -= 50;
            }
        };

        // Search functionality
        modelSearch.addEventListener('input', function() {
            const query = this.value.toLowerCase().split(' ');
            const options = selectItems.querySelectorAll('.model-option');
            clearHighlight();

            options.forEach(option => {
                const text = option.textContent.toLowerCase();
                option.style.display = query.every(keyword => text.includes(keyword)) ? 'block' : 'none';
            });

            const visibleOptions = getVisibleOptions();
            if (visibleOptions.length > 0) {
                highlightOption(0, visibleOptions);
            }
        });

        // Keyboard navigation
        modelSearch.addEventListener('keydown', function(e) {
            if (['ArrowDown', 'ArrowUp', 'Enter'].includes(e.key)) {
                e.preventDefault();
                
                const visibleOptions = getVisibleOptions();
                if (!visibleOptions.length) return;

                switch (e.key) {
                    case 'ArrowDown':
                        highlightOption((highlightedIndex + 1) % visibleOptions.length, visibleOptions);
                        break;

                    case 'ArrowUp':
                        highlightOption((highlightedIndex - 1 + visibleOptions.length) % visibleOptions.length, visibleOptions);
                        break;

                    case 'Enter':
                        if (highlightedIndex >= 0) {
                            visibleOptions[highlightedIndex].click();
                        }
                        break;
                }
            }
        });

        modelSearch.focus();

    } catch (error) {
        console.error('Error fetching models:', error);
    }
}

// Set selected model function
async function setSelectedModel(model) {
    selectedModel = model;
    await db.settings.put({ key: 'selectedModel', value: model });
    // Update both the text content and innerHTML to ensure proper display
    selectSelected.textContent = model;
    selectSelected.innerHTML = `${model} <i class="fa fa-angle-down" aria-hidden="true"></i>`;
}

window.onload = async function() {
    try {
        // Load settings from IndexedDB
        const apiKeyRecord = await db.settings.get('apiKey');
        const baseUrlRecord = await db.settings.get('baseUrl');
        const selectedModelRecord = await db.settings.get('selectedModel');
        
        // Set the input values if records exist
        if (apiKeyRecord?.value) {
            document.getElementById('api-key').value = apiKeyRecord.value;
        }
        if (baseUrlRecord?.value) {
            document.getElementById('base-url').value = baseUrlRecord.value;
        }

        // Load additional settings and continue with other initialization
        loadAdditionalSettings();
        try {
            setLibraryGroundingMode(localStorage.getItem(HAI_LIBRARY_GROUNDING_STORAGE_KEY) || 'auto');
        } catch (_) {
            setLibraryGroundingMode('auto');
        }
        try {
            setLibraryContextMode(localStorage.getItem(HAI_LIBRARY_CONTEXT_STORAGE_KEY) || 'snippet');
        } catch (_) {
            setLibraryContextMode('snippet');
        }
        await loadConversationsFromStorage();
        await loadLibraryDocuments();
        await fetchModels();

        await setSelectedModel(selectedModelRecord?.value || 'harmonika-ai');

        userInput.focus();
    } catch (error) {
        console.error('Error in window.onload:', error);
        showHaiWelcome();
    } finally {
        window.setTimeout(ensureHaiWelcomeWhenEmpty, 120);
    }
};

function toggleDropdown(select) {
    const items = select.nextElementSibling;
    if (items.style.display === 'block') {
        items.style.display = 'none';
        select.setAttribute('aria-expanded', 'false');
    } else {
        items.style.display = 'block';
        select.setAttribute('aria-expanded', 'true');
        items.scrollTop = 0;
        const modelSearch = items.querySelector('#model-search');
        modelSearch.value = '';
        modelSearch.focus();

        const options = items.querySelectorAll('.model-option');
        options.forEach(option => {
            option.style.display = 'block';
        });
    }
}

selectSelected?.addEventListener('keydown', event => {
    if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        toggleDropdown(selectSelected);
    }
});

selectSelected?.addEventListener('click', () => toggleDropdown(selectSelected));
composerForm?.addEventListener('submit', sendMessage);
userSettingButton?.addEventListener('click', openPopup);
additionalSettingButton?.addEventListener('click', openAdditionalPopup);
settingsCloseButton?.addEventListener('click', closePopup);
settingsSaveButton?.addEventListener('click', saveSettings);
additionalSettingsCloseButton?.addEventListener('click', closeAdditionalPopup);
additionalSettingsSaveButton?.addEventListener('click', saveAdditionalSettings);

selectItems.addEventListener('click', function(event) {
    if (event.target.tagName === 'DIV' && event.target.classList.contains('model-option')) {
        // Clear any existing highlights
        const allOptions = selectItems.querySelectorAll('.model-option');
        allOptions.forEach(option => option.classList.remove('highlighted'));
        
        // Update highlighted index to match the clicked option
        const visibleOptions = [...selectItems.querySelectorAll('.model-option')]
            .filter(option => option.style.display !== 'none');
        highlightedIndex = visibleOptions.indexOf(event.target);
        
        // Highlight to clicked option
        event.target.classList.add('highlighted');
        
        // Update the selected model
        const selected = event.target.closest('.custom-select').querySelector('.select-selected');
        selected.innerHTML = `${event.target.textContent} <i class="fa fa-angle-down" aria-hidden="true"></i>`;
        selected.setAttribute('data-value', event.target.getAttribute('data-value'));
        setSelectedModel(event.target.getAttribute('data-value'));
        selectItems.style.display = 'none';
        selected.setAttribute('aria-expanded', 'false');
        userInput.focus();
    }
});

document.addEventListener('click', function(event) {
    const thinkButton = event.target.closest?.('[data-hai-think-toggle="true"]');
    if (thinkButton) {
        event.preventDefault();
        toggleThinkBlock(thinkButton);
        return;
    }

    if (!event.target.closest('.custom-select')) {
        document.querySelectorAll('.select-items').forEach(function(items) {
            items.style.display = 'none';
            items.previousElementSibling?.setAttribute('aria-expanded', 'false');
            const modelSearch = items.querySelector('#model-search');
            modelSearch.value = '';
        });
    }

    if (!event.target.closest('.popup-content') && !event.target.closest('#user-setting')) {
        settingsPopup.style.display = 'none';
    }
});

function composerHasDraft() {
    return Boolean(userInput?.value?.trim()) || pendingAttachments.length > 0;
}

function flashComposerEmptyHint() {
    if (!composerForm) return;
    composerForm.classList.remove('is-empty-nudge');
    void composerForm.offsetWidth;
    composerForm.classList.add('is-empty-nudge');
    setHaiStatus('Tulis pesan atau lampirkan file dulu.', 'info');
    window.setTimeout(() => {
        composerForm.classList.remove('is-empty-nudge');
        if (!currentController) setHaiStatus('');
    }, 1600);
}

function refreshComposerState() {
    const hasDraft = composerHasDraft();
    const isGenerating = Boolean(currentController);
    composerForm?.classList.toggle('has-draft', hasDraft);
    composerForm?.classList.toggle('is-generating', isGenerating);
    composerForm?.classList.toggle('is-queue-ready', isGenerating && hasDraft);
    submitButton?.classList.toggle('is-ready', hasDraft);
    submitButton?.classList.toggle('is-stop', isGenerating && !hasDraft);
    submitButton?.classList.toggle('is-queue', isGenerating && hasDraft);

    if (isGenerating) {
        if (hasDraft) {
            submitButton.setAttribute('aria-label', 'Masukkan pesan ke antrean');
            submitButton.innerHTML = '<i class="fa fa-clock-o fa-inverse" aria-hidden="true"></i>';
            composerForm?.setAttribute('data-submit-hint', 'Antrekan');
        } else {
            const mode = submitButton.dataset.generatingMode || 'text';
            submitButton.setAttribute('aria-label', mode === 'image' ? 'Hentikan pembuatan gambar' : 'Hentikan jawaban');
            submitButton.innerHTML = '<i class="fa fa-stop-circle-o fa-inverse" aria-hidden="true"></i>';
            composerForm?.setAttribute('data-submit-hint', 'Stop');
        }
    } else {
        submitButton.setAttribute('aria-label', 'Kirim pesan');
        submitButton.innerHTML = '<i class="fa fa-arrow-circle-up fa-inverse" aria-hidden="true"></i>';
        composerForm?.setAttribute('data-submit-hint', hasDraft ? 'Kirim' : 'Tulis pesan');
    }
}

function toggleSubmitButtonIcon(isGenerating, mode = 'text') {
    submitButton.dataset.generatingMode = isGenerating ? mode : '';
    if (isGenerating) {
        submitButton.setAttribute('aria-label', mode === 'image' ? 'Hentikan pembuatan gambar' : 'Hentikan jawaban');
        submitButton.innerHTML = '<i class="fa fa-stop-circle-o fa-inverse" aria-hidden="true"></i>';
        setHaiLiveStatus(mode === 'image' ? 'imageDesigning' : 'textThinking');
        submitButton.onclick = (e) => {
            e.preventDefault();
            if (currentController) {
                if (userInput.value.trim() || pendingAttachments.length) {
                    queueCurrentComposerDraft();
                    return;
                }
                setHaiLiveStatus(mode === 'image' ? 'stoppingImage' : 'stoppingText');
                currentController.abort();
            }
        };
    } else {
        submitButton.setAttribute('aria-label', 'Kirim pesan');
        submitButton.innerHTML = '<i class="fa fa-arrow-circle-up fa-inverse" aria-hidden="true"></i>';
        submitButton.onclick = null;
        setHaiStatus('');
        const connectionState = haiConnectionPill?.dataset?.state || '';
        if (['replay', 'history', 'error', 'stopped'].includes(connectionState)) {
            window.setTimeout(() => {
                if (!currentController) setHaiConnectionState('ready');
            }, connectionState === 'replay' ? 4200 : 2000);
        } else {
            setHaiConnectionState('ready');
        }
    }
    refreshComposerState();
}

function showToast(message, type = 'error') {
    const normalizedType = ['success', 'info', 'error'].includes(type) ? type : 'info';
    const iconClass = {
        success: 'fa-check-circle',
        info: 'fa-info-circle',
        error: 'fa-exclamation-circle'
    }[normalizedType];
    // Remove any existing toast
    const existingToast = document.querySelector('.toast');
    if (existingToast) {
        existingToast.remove();
    }

    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast ${normalizedType}`;
    toast.setAttribute('role', normalizedType === 'error' ? 'alert' : 'status');
    toast.setAttribute('aria-live', normalizedType === 'error' ? 'assertive' : 'polite');
    toast.setAttribute('aria-atomic', 'true');
    const icon = document.createElement('i');
    icon.className = `fa ${iconClass} toast-icon`;
    icon.setAttribute('aria-hidden', 'true');
    const text = document.createElement('span');
    text.className = 'toast-message';
    text.textContent = String(message ?? '');
    toast.appendChild(icon);
    toast.appendChild(text);

    // Toast to document
    document.body.appendChild(toast);

    // Trigger reflow and add show class
    toast.offsetHeight;
    toast.classList.add('show');

    // Remove toast after 3 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Update the cleanMessageForAPI function
function cleanMessageForAPI(message) {
    if (message?.isError) {
        return null;
    }
    const sanitizeApiContent = (content) => {
        if (!Array.isArray(content)) return content;
        const cleanParts = content
            .map((part) => {
                if (!part || typeof part !== 'object') return null;
                if (part.type === 'text') {
                    const text = String(part.text || '').trim();
                    return text ? { type: 'text', text } : null;
                }
                if (part.type === 'image_url') {
                    const url = String(part.image_url?.url || '');
                    if (!url || url === '[image omitted from history]' || url.startsWith('data:image/')) return null;
                    return { type: 'image_url', image_url: { url } };
                }
                return null;
            })
            .filter(Boolean);
        if (cleanParts.length === 0) return '';
        if (!cleanParts.some((part) => part.type === 'image_url')) {
            return cleanParts
                .filter((part) => part.type === 'text')
                .map((part) => part.text)
                .join('\n\n')
                .trim();
        }
        return cleanParts;
    };
    // Handle messages with content objects (usually assistant messages)
    if (message.role === 'assistant' && typeof message.content === 'object') {
        const cleanedContent = sanitizeApiContent(message.content.raw);
        if (!cleanedContent) return null;
        return {
            role: message.role,
            content: cleanedContent
        };
    }
    
    // Handle user messages with content objects
    if (message.role === 'user' && typeof message.content === 'object') {
        // If it's an image message
        if (Array.isArray(message.content)) {
            const cleanedContent = sanitizeApiContent(message.content);
            if (!cleanedContent) return null;
            return {
                role: message.role,
                content: cleanedContent
            };
        }
        // If it's a regular message with content object
        if (message.raw) {
            const cleanedContent = sanitizeApiContent(message.raw);
            if (!cleanedContent) return null;
            return {
                role: message.role,
                content: cleanedContent
            };
        }
        const cleanedContent = sanitizeApiContent(message.content.raw || message.content.content || message.content);
        if (!cleanedContent) return null;
        return {
            role: message.role,
            content: cleanedContent
        };
    }

    // For simple string content messages
    const { messageId, endTag, thinkingTime, sources, attachments, artifacts, isError, ...cleanMessage } = message;
    cleanMessage.content = sanitizeApiContent(cleanMessage.content);
    if (!cleanMessage.content) return null;
    return cleanMessage;
}

// Update the sendMessage function to use cleanMessageForAPI
async function sendMessage(event) {
    event?.preventDefault?.();
    if (currentController) {
        queueCurrentComposerDraft();
        return;
    }
    const inputValue = userInput.value.trim();
    
    const turnAttachments = cloneAttachmentsForQueue();
    
    // Check if there's no text input and no attached file/image
    if (inputValue === '' && !turnAttachments.length) {
        flashComposerEmptyHint();
        return;
    }
    const haiIntent = detectHaiIntent(inputValue);
    let turnIntent = haiIntent.type;

    if (!selectedModel || selectSelected.textContent === 'Select Model') {
        await setSelectedModel('harmonika-ai');
    }

    // Reset stream timer variables before starting new message
    streamStartTime = null;
    streamDuration = null;

    const isNewChat = !currentConversationId || !conversations[currentConversationId];
    
    if (!isPrivateChat && isNewChat) {
        currentConversationId = Date.now().toString();
        conversations[currentConversationId] = {
            messages: [],
            title: deriveLocalConversationTitle(inputValue)
        };
        saveConversationsToStorage();
        updateChatHistory();
    } else if (!isPrivateChat && currentConversationId && conversations[currentConversationId] && conversations[currentConversationId].title === 'Chat Baru') {
        conversations[currentConversationId].title = deriveLocalConversationTitle(inputValue);
        saveConversationsToStorage();
        updateChatHistory();
    }

    const requestConversationId = currentConversationId;
    const requestStartedInPrivate = isPrivateChat;
    const requestHistoryAtStart = conversationHistory.map(message => ({ ...message }));
    const memoryContext = await getHaiMemoryContext();

    chatMessages.querySelector('.hai-empty-state')?.remove();
    updateQuickPromptVisibility();
    scrollChatToBottom('smooth');
    
    const displayUserContent = turnAttachments.length
        ? {
            content: inputValue || (turnAttachments.length > 1 ? `${turnAttachments.length} lampiran terlampir` : (turnAttachments[0].type === 'image' ? 'Gambar terlampir' : 'Dokumen terlampir')),
            attachments: turnAttachments.map(attachment => ({
                type: attachment.type,
                name: attachment.name,
                sizeLabel: attachment.sizeLabel,
                mime: attachment.mime
            }))
        }
        : inputValue;

    // Create user message container
    const userMessageContainer = document.createElement('div');
    userMessageContainer.className = 'user-message-container';
    const userMessageDiv = document.createElement('div');
    userMessageDiv.classList.add('user-message');
    // Preserve line breaks by replacing them with <br> tags
    userMessageDiv.innerHTML = formatUserMessage(displayUserContent);
    userMessageContainer.appendChild(userMessageDiv);

    // Add buttons for user message
    const buttonContainer = document.createElement('div');
    buttonContainer.className = 'message-buttons';

    const userEditButton = document.createElement('button');
    userEditButton.className = 'message-edit-button';
    userEditButton.innerHTML = haiIconImg('pencil', 'Edit pesan');
    userEditButton.onclick = () => handleMessageEdit(userMessageDiv, displayUserContent, 'user');

    const userCopyButton = document.createElement('button');
    userCopyButton.className = 'message-copy-button';
    userCopyButton.innerHTML = haiIconImg('copy', 'Salin pesan');
    userCopyButton.onclick = () => copyToClipboard(
        inputValue || turnAttachments.map(attachment => attachment.name).filter(Boolean).join(', '),
        userCopyButton
    );

    const userDeleteButton = document.createElement('button');
    userDeleteButton.className = 'message-delete-button';
    userDeleteButton.innerHTML = haiIconImg('trash', 'Hapus pesan');
    userDeleteButton.onclick = () => handleMessageDelete(userMessageDiv, displayUserContent, 'user');

    buttonContainer.appendChild(userEditButton);
    buttonContainer.appendChild(userCopyButton);
    buttonContainer.appendChild(userDeleteButton);
    userMessageContainer.appendChild(buttonContainer);

    const assistantMessageContainer = document.createElement('div');
    assistantMessageContainer.className = 'assistant-message-container';
    const assistantMessage = document.createElement('div');
    assistantMessage.classList.add('assistant-message');
    assistantMessageContainer.appendChild(assistantMessage);
    setAssistantWaiting(assistantMessageContainer, assistantMessage, {
        intent: haiIntent.type,
        label: haiIntent.type === 'image'
            ? 'Harmonika AI sedang mendesain gambar…'
            : 'Harmonika AI sedang mengetik jawaban…'
    });

    // Inside the sendMessage function, where you create the assistant message:
    const messageId = Date.now().toString(); // Generate unique ID
    assistantMessageContainer.dataset.messageId = messageId;

    chatMessages.appendChild(userMessageContainer);
    chatMessages.appendChild(assistantMessageContainer);
    syncTopbarTitle();
    scrollChatToBottom('smooth');

    userInput.value = '';
    clearPendingAttachment();
    refreshComposerState();

    let pendingUserMessage = null;
    let messageForAPI = inputValue;
    let messageContent;
    let fullResponse = '';
    let visibleAssistantResponse = '';
    let pendingAssistantResponse = '';
    let assistantTypewriterTimer = null;
    let stopAssistantTypewriter = () => {};
    let flushAssistantTypewriter = async () => {};
    let drainAssistantTypewriter = async () => {};

    try {
        currentController = new AbortController();
        toggleSubmitButtonIcon(true, haiIntent.type);
        setHaiLiveStatus(haiIntent.type === 'image' ? 'imagePreparing' : 'connecting');
        
        // Start the timer here
        startStreamTimer();
        
        // Clean conversation history for API
        const apiConversationHistory = requestHistoryAtStart.map(cleanMessageForAPI).filter(Boolean);
        
        stopAssistantTypewriter = () => {
            if (assistantTypewriterTimer) {
                window.clearInterval(assistantTypewriterTimer);
                assistantTypewriterTimer = null;
            }
        };

        const renderAssistantTypewriterFrame = (shouldStickToBottom = true, force = false) => {
            if (turnIntent === 'image') return;
            if (!pendingAssistantResponse && !force) {
                stopAssistantTypewriter();
                return;
            }
            const queueLength = pendingAssistantResponse.length;
            const take = force
                ? queueLength
                : Math.max(8, Math.min(queueLength, queueLength > 420 ? 54 : (queueLength > 160 ? 32 : 18)));
            if (take > 0) {
                visibleAssistantResponse += pendingAssistantResponse.slice(0, take);
                pendingAssistantResponse = pendingAssistantResponse.slice(take);
                renderAssistantMarkdown(assistantMessage, visibleAssistantResponse, END_TAG, false);
                if (shouldStickToBottom) {
                    scrollChatToBottom('auto');
                }
            }
            if (!pendingAssistantResponse) {
                stopAssistantTypewriter();
            }
        };

        const scheduleAssistantTypewriter = (chunk, shouldStickToBottom = true) => {
            if (turnIntent === 'image') return false;
            const text = String(chunk || '');
            if (!text) return true;
            pendingAssistantResponse += text;
            if (!assistantTypewriterTimer) {
                assistantTypewriterTimer = window.setInterval(() => {
                    renderAssistantTypewriterFrame(shouldStickToBottom, false);
                }, 26);
            }
            renderAssistantTypewriterFrame(shouldStickToBottom, false);
            return true;
        };

        flushAssistantTypewriter = async () => {
            if (turnIntent === 'image') return;
            stopAssistantTypewriter();
            if (pendingAssistantResponse) {
                renderAssistantTypewriterFrame(true, true);
            }
            if (visibleAssistantResponse !== fullResponse && fullResponse.trim()) {
                visibleAssistantResponse = fullResponse;
                pendingAssistantResponse = '';
                renderAssistantMarkdown(assistantMessage, visibleAssistantResponse, END_TAG, false);
            }
        };

        drainAssistantTypewriter = async (maxWaitMs = 1400) => {
            if (turnIntent === 'image') return;
            const startedAt = Date.now();
            while (pendingAssistantResponse && Date.now() - startedAt < maxWaitMs) {
                stopAssistantTypewriter();
                renderAssistantTypewriterFrame(true, false);
                await new Promise((resolve) => window.setTimeout(resolve, 24));
            }
            await flushAssistantTypewriter();
        };
        
        const imageAttachments = turnAttachments.filter(attachment => attachment?.type === 'image' && attachment.base64);
        const documentAttachments = turnAttachments.filter(attachment => attachment?.type === 'document');
        const defaultPrompt = turnAttachments.length > 1
            ? 'Baca semua lampiran ini dan jawab sesuai isinya.'
            : (imageAttachments.length ? 'Jelaskan isi gambar ini.' : 'Baca dan jelaskan dokumen ini.');
        const documentContext = documentAttachments.map(attachment =>
            `[Document: ${attachment.name}]\n\n${attachment.content || ''}`
        ).join('\n\n---\n\n');
        
        // Attachments are staged in the composer and sent only when user presses Send.
        if (imageAttachments.length) {
            const textForImages = [
                inputValue || defaultPrompt,
                documentContext
            ].filter(Boolean).join('\n\n');
            messageContent = [
                { type: "text", text: textForImages },
                ...imageAttachments.map(attachment => ({
                    type: "image_url",
                    image_url: {
                        url: attachment.base64
                    }
                }))
            ];
            pendingUserMessage = {
                role: "user",
                content: displayUserContent,
                raw: [
                    { type: "text", text: textForImages },
                    ...imageAttachments.map(() => ({ type: "image_url", image_url: { url: "[image omitted from history]" } }))
                ]
            };
        } else if (documentAttachments.length) {
            const fullDocumentMessage = `${inputValue || defaultPrompt}\n\n${documentContext}`;
            messageContent = fullDocumentMessage;
            pendingUserMessage = {
                role: "user",
                content: displayUserContent,
                raw: fullDocumentMessage
            };
        } else {
            messageContent = inputValue;
        }

        messageForAPI = await appendLibraryContextToMessageContent(
            messageContent,
            inputValue || userTextForIntent(messageContent)
        );

        const requestBody = {
            message: messageForAPI,
            model: selectedModel,
            systemContent: SYSTEM_CONTENT,
            parameters: MODEL_PARAMETERS,
            isNewChat: isNewChat,
            conversation: apiConversationHistory,
            isDeepQueryMode: isDeepQueryMode,
            startTag: START_TAG,
            memoryContext,
            libraryGrounding: haiLibraryGroundingMode,
            libraryContextMode: haiLibraryContextMode
        };

        if (!pendingUserMessage) {
            pendingUserMessage = {
                role: "user",
                content: inputValue
            };
        }
        rememberFromUserText(userTextForMemory(displayUserContent));
        
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody),
            signal: currentController.signal
        });

        if (!response.ok || !response.body) {
            let errorMessage = `Harmonika AI belum bisa menjawab. Kode: ${response.status}`;
            try {
                const errorData = await response.json();
                if (errorData?.message) errorMessage = errorData.message;
            } catch (_) {}
            throw new Error(errorMessage);
        }

        let hasReceivedChunk = false;
        let imageArtifactRendered = false;
        const realtimeResponseId = response.headers.get('X-HAI-Response-ID') || '';
        const responseSources = parseHaiSourcesHeader(response.headers.get('X-HAI-Sources'));
        const libraryGrounding = parseHaiLibraryGroundingHeader(response.headers.get('X-HAI-Library-Grounding'));
        if (libraryGrounding.used) {
            const contextLabel = libraryGrounding.contextMode === 'full' ? 'konteks penuh' : 'cuplikan';
            setHaiStatus(`Library dipakai: ${libraryGrounding.count} ${contextLabel} dokumen.`, 'info');
        }

        const serverIntent = (response.headers.get('X-HAI-Intent') || '').toLowerCase();
        if (serverIntent === 'image' || serverIntent === 'text') {
            turnIntent = serverIntent;
            assistantMessageContainer.dataset.intent = turnIntent;
            if (!hasReceivedChunk) {
                setAssistantWaiting(assistantMessageContainer, assistantMessage, {
                    intent: turnIntent,
                    label: turnIntent === 'image'
                        ? 'Harmonika AI sedang mendesain gambar…'
                        : 'Harmonika AI sedang mengetik jawaban…'
                });
                toggleSubmitButtonIcon(true, turnIntent);
                setHaiLiveStatus(
                    turnIntent === 'image'
                        ? 'imagePreparing'
                        : (responseSources.length ? 'webReading' : 'connecting')
                );
            }
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        // Prepend START_TAG to response when in deep query mode
        if (isDeepQueryMode) {
            fullResponse += START_TAG;
            visibleAssistantResponse += START_TAG;
        }

        // Create React root for assistant message
        if (!assistantMessage.reactRoot) {
            assistantMessage.reactRoot = ReactDOM.createRoot(assistantMessage);
        }

        let streamSettled = false;
        let lastVisibleChunkAt = Date.now();
        const finalizeAssistantStream = async (reason = 'done') => {
            if (streamSettled) return;
            streamSettled = true;
            if (reason === 'done') {
                await drainAssistantTypewriter();
            } else {
                await flushAssistantTypewriter();
            }
            if (turnIntent === 'image' && fullResponse.trim() && !imageArtifactRendered) {
                renderAssistantMarkdown(assistantMessage, fullResponse, END_TAG, false, true);
                imageArtifactRendered = true;
            }
            clearAssistantWaiting(assistantMessageContainer);
            currentController = null;
            toggleSubmitButtonIcon(false);
            hasScrolledForThinkBlock = false;

            if (streamStartTime) {
                const duration = stopStreamTimer();
                console.log(`Stream ${reason === 'stall' ? 'finalized after heartbeat stall' : 'completed'} in ${duration}ms`);
            }

            if (!fullResponse.trim()) {
                fullResponse = 'Maaf, jawaban kosong. Silakan coba kirim ulang pertanyaan.';
                renderAssistantMarkdown(assistantMessage, fullResponse, END_TAG, false, true);
            }
            const qualityResponse = normalizeAssistantPublicQualityText(fullResponse);
            if (qualityResponse !== fullResponse) {
                fullResponse = qualityResponse;
                renderAssistantMarkdown(assistantMessage, fullResponse, END_TAG, false, true);
            }
            const oneSentenceResponse = trimAssistantToSingleSentenceIfRequested(fullResponse, inputValue || userTextForIntent(messageContent));
            if (oneSentenceResponse !== fullResponse) {
                fullResponse = oneSentenceResponse;
                renderAssistantMarkdown(assistantMessage, fullResponse, END_TAG, false, true);
            }
            appendAssistantActionButtonsIfMissing(assistantMessageContainer, assistantMessage, fullResponse);
            appendSourceChips(assistantMessageContainer, responseSources);

            const assistantMessageObj = {
                role: "assistant",
                content: fullResponse,
                endTag: END_TAG,
                thinkingTime: streamDuration,
                sources: responseSources,
                intent: turnIntent,
                libraryGrounding
            };
            if (reason === 'stall') {
                assistantMessageObj.finalizedByClient = true;
            }

            const finalConversationHistory = [...requestHistoryAtStart];
            if (pendingUserMessage) {
                finalConversationHistory.push(pendingUserMessage);
                pendingUserMessage = null;
            }
            finalConversationHistory.push(assistantMessageObj);

            if (currentConversationId === requestConversationId) {
                conversationHistory = [...finalConversationHistory];
            }

            if (!requestStartedInPrivate && requestConversationId && conversations[requestConversationId]) {
                conversations[requestConversationId].messages = [...finalConversationHistory];
                await saveConversationsToStorage();

                if (isNewChat || finalConversationHistory.length <= 2) {
                    try {
                        const titleResponse = await fetch('/generate-title', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({
                                message: messageContent,
                                model: selectedModel,
                                assistantResponse: fullResponse.slice(0, 500)
                            })
                        });

                        const titleData = await titleResponse.json();
                        if (titleData.title && conversations[requestConversationId]) {
                            conversations[requestConversationId].title = cleanConversationTitle(titleData.title);
                            if (currentConversationId === requestConversationId) syncTopbarTitle();
                        }
                    } catch (error) {
                        console.error('Error generating title:', error);
                    }
                }

                await saveConversationsToStorage();
                updateChatHistory();
            }

            runQueuedComposerMessageSoon();
        };

        while (true) {
            try {
                const { done, value } = await reader.read();
                if (done) {
                    await finalizeAssistantStream('done');
                    break;
                }

                const chunk = normalizeHaiStreamChunk(decoder.decode(value, { stream: true }));
                if (!chunk) {
                    const stalledAfterContent = (
                        turnIntent !== 'image' &&
                        hasReceivedChunk &&
                        fullResponse.trim().length > 8 &&
                        Date.now() - lastVisibleChunkAt > HAI_STREAM_STALL_FINALIZE_MS
                    );
                    if (stalledAfterContent) {
                        try {
                            await reader.cancel();
                        } catch (_) {}
                        await finalizeAssistantStream('stall');
                        break;
                    }
                    continue;
                }
                lastVisibleChunkAt = Date.now();
                const shouldStickToBottom = autoScrollLockedToBottom || isNearChatBottom();
                fullResponse += chunk;
                if (!hasReceivedChunk) {
                    hasReceivedChunk = true;
                    if (turnIntent === 'image') {
                        markAssistantFirstVisibleChunk(assistantMessageContainer, 'image', {
                            progressStep: 2,
                            status: 'imageDesigning'
                        });
                    } else {
                        markAssistantFirstVisibleChunk(assistantMessageContainer, 'text', {
                            status: responseSources.length ? 'webWriting' : 'textWriting'
                        });
                    }
                }
                
                // Check if this chunk contains the end tag
                if (streamStartTime && checkForEndTag(fullResponse)) {
                    const duration = stopStreamTimer();
                    console.log(`End tag detected. Thinking completed in ${duration}ms`);
                }
                
                if (turnIntent === 'image' && !hasCompleteImageArtifact(fullResponse)) {
                    setAssistantStreamPhase(assistantMessageContainer, 'image-rendering');
                    setImageProgressStep(assistantMessageContainer, 3);
                    setHaiLiveStatus('imageRendering');
                    if (shouldStickToBottom) {
                        scrollChatToBottom('auto');
                    }
                    continue;
                }

                if (turnIntent === 'image' && !imageArtifactRendered) {
                    setImageProgressStep(assistantMessageContainer, HAI_IMAGE_STEPS.length - 1);
                    clearAssistantWaiting(assistantMessageContainer);
                    imageArtifactRendered = true;
                    assistantMessageContainer.classList.add('is-done');
                    renderAssistantMarkdown(assistantMessage, fullResponse, END_TAG, false, true);
                } else {
                    if (turnIntent !== 'image' && isLikelyStreamingCode(fullResponse)) {
                        setAssistantStreamPhase(assistantMessageContainer, 'code-writing');
                        ensureAssistantStreamLivebar(assistantMessageContainer, 'text', 'code-writing');
                        setHaiLiveStatus('codeWriting');
                    }
                    // Keep a ChatGPT-like typewriter effect even when the backend
                    // sends larger chunks. The saved history still uses fullResponse.
                    scheduleAssistantTypewriter(chunk, shouldStickToBottom);
                }

                // Add this right after the render:
                if (assistantMessage.querySelector('.think-block') && !hasScrolledForThinkBlock) {
                    hasScrolledForThinkBlock = true;
                    scrollChatToBottom('smooth');
                } else if (shouldStickToBottom) {
                    scrollChatToBottom('auto');
                }

            } catch (error) {
                if (error.name === 'AbortError') {
                    stopAssistantTypewriter();
                    clearAssistantWaiting(assistantMessageContainer);
                    // Only stop timer if it hasn't been stopped by end tag detection
                    if (streamStartTime) {
                        const duration = stopStreamTimer();
                        console.log(`Stream aborted after ${duration}ms`);
                    }
                    
                    console.log('Stream aborted by user');
                    currentController = null;
                    toggleSubmitButtonIcon(false);
                    setHaiLiveStatus('stopped');
                    window.setTimeout(() => setHaiStatus(''), 1400);
                    const publicAbortText = stripPublicReasoningBlocks(fullResponse || '').trim();
                    if (turnIntent === 'image' && !imageArtifactRendered) {
                        fullResponse = 'Pembuatan gambar dihentikan.';
                        setAssistantError(assistantMessage, fullResponse);
                    } else if (!publicAbortText) {
                        fullResponse = 'Jawaban dihentikan.';
                        setAssistantError(assistantMessage, fullResponse);
                    } else {
                        fullResponse = publicAbortText;
                        renderAssistantMarkdown(assistantMessage, fullResponse, END_TAG, false, true);
                    }
                    
                    // Add buttons to assistant message when stopped
                    const buttonContainer = document.createElement('div');
                    buttonContainer.className = 'message-buttons';

                    const assistantEditButton = document.createElement('button');
                    assistantEditButton.className = 'message-edit-button';
                    assistantEditButton.innerHTML = haiIconImg('pencil', 'Edit pesan');
                    assistantEditButton.onclick = () => handleMessageEdit(assistantMessage, fullResponse, 'assistant');

                    const assistantCopyButton = document.createElement('button');
                    assistantCopyButton.className = 'message-copy-button';
                    assistantCopyButton.innerHTML = haiIconImg('copy', 'Salin pesan');
                    assistantCopyButton.onclick = () => copyToClipboard(fullResponse, assistantCopyButton);

                    const deleteButton = document.createElement('button');
                    deleteButton.className = 'message-delete-button';
                    deleteButton.innerHTML = haiIconImg('trash', 'Hapus pesan');
                    deleteButton.onclick = () => handleMessageDelete(assistantMessage, fullResponse, 'assistant');

                    const continueButton = document.createElement('button');
                    continueButton.className = 'message-continue-button';
                    continueButton.innerHTML = haiIconImg('continue', 'Lanjutkan jawaban');
                    continueButton.onclick = () => handleContinueGeneration(assistantMessage, fullResponse);

                    buttonContainer.appendChild(assistantEditButton);
                    buttonContainer.appendChild(assistantCopyButton);
                    buttonContainer.appendChild(deleteButton);
                    buttonContainer.appendChild(continueButton);
                    assistantMessageContainer.appendChild(buttonContainer);
                    
                    const stoppedConversationHistory = [
                        ...requestHistoryAtStart,
                        pendingUserMessage || { role: "user", content: displayUserContent },
                        { 
                        messageId,
                        role: "assistant", 
                        content: {
                            raw: fullResponse,
                            reasoningExpanded: false,
                            allowImageArtifacts: shouldAllowImageArtifacts(fullResponse, turnIntent)
                        },
                        endTag: END_TAG,
                        thinkingTime: streamDuration,  // Add thinking time here too
                        intent: turnIntent
                        }
                    ];
                    if (currentConversationId === requestConversationId) {
                        conversationHistory = [...stoppedConversationHistory];
                    }
                    
                    if (!requestStartedInPrivate && requestConversationId && conversations[requestConversationId]) {
                        conversations[requestConversationId].messages = [...stoppedConversationHistory];
                        saveConversationsToStorage();
                    }
                    
                    runQueuedComposerMessageSoon();
                    return;
                }
                const replay = await fetchRealtimeReplayText(realtimeResponseId);
                if (replay?.ok) {
                    fullResponse = replay.text;
                    renderAssistantMarkdown(assistantMessage, fullResponse, END_TAG, false, true);
                    await finalizeAssistantStream('replay');
                    setHaiConnectionState('replay');
                    window.setTimeout(() => {
                        if (!currentController) setHaiConnectionState('ready');
                    }, 4200);
                    break;
                }
                throw error;
            }
        }
    } catch (error) {
        // Stop the timer in case of error
        stopStreamTimer();
        stopAssistantTypewriter();
        if (error.name === 'AbortError') {
            clearAssistantWaiting(assistantMessageContainer);
            currentController = null;
            toggleSubmitButtonIcon(false);
            setHaiLiveStatus('stopped');
            window.setTimeout(() => setHaiStatus(''), 1400);
            if (!assistantMessage.textContent.trim() || isAssistantWaitingPlaceholder(assistantMessage) || !stripPublicReasoningBlocks(fullResponse || assistantMessage.textContent || '').trim()) {
                const abortResponseText = turnIntent === 'image' ? 'Pembuatan gambar dihentikan.' : 'Jawaban dihentikan.';
                assistantMessageContainer.dataset.error = 'true';
                setAssistantError(assistantMessage, abortResponseText);
                appendAssistantActionButtonsIfMissing(assistantMessageContainer, assistantMessage, abortResponseText);
                const abortConversationHistory = [...requestHistoryAtStart];
                if (pendingUserMessage) {
                    abortConversationHistory.push(pendingUserMessage);
                } else {
                    abortConversationHistory.push({ role: "user", content: displayUserContent });
                }
                abortConversationHistory.push({
                    messageId,
                    role: "assistant",
                    content: abortResponseText,
                    endTag: END_TAG,
                    thinkingTime: streamDuration,
                    isError: true,
                    intent: turnIntent
                });
                if (currentConversationId === requestConversationId) {
                    conversationHistory = [...abortConversationHistory];
                }
                if (!requestStartedInPrivate && requestConversationId && conversations[requestConversationId]) {
                    conversations[requestConversationId].messages = [...abortConversationHistory];
                    saveConversationsToStorage();
                    updateChatHistory();
                }
                syncTopbarTitle();
            } else {
                const publicAbortText = stripPublicReasoningBlocks(fullResponse || assistantMessage.textContent || '').trim();
                if (publicAbortText && !assistantMessage.textContent.trim()) {
                    fullResponse = publicAbortText;
                    renderAssistantMarkdown(assistantMessage, fullResponse, END_TAG, false, true);
                }
            }
            runQueuedComposerMessageSoon();
            return;
        }
        console.error('Error:', error);
        clearAssistantWaiting(assistantMessageContainer);
        const errorResponseText = `Maaf, ${error.message || 'koneksi ke Harmonika AI terputus. Coba lagi sebentar.'}`;
        assistantMessageContainer.dataset.error = 'true';
        setAssistantError(assistantMessage, errorResponseText);
        appendAssistantActionButtonsIfMissing(assistantMessageContainer, assistantMessage, errorResponseText);
        currentController = null;
        toggleSubmitButtonIcon(false);
        setHaiStatus(error.message || 'Koneksi bermasalah. Coba lagi.', 'error');
        window.setTimeout(() => setHaiStatus(''), 3200);
        hasImageAttached = false;
        const errorConversationHistory = [...requestHistoryAtStart];
        if (pendingUserMessage) {
            errorConversationHistory.push(pendingUserMessage);
        } else {
            errorConversationHistory.push({ role: "user", content: displayUserContent });
        }
        errorConversationHistory.push({
            messageId,
            role: "assistant",
            content: errorResponseText,
            endTag: END_TAG,
            thinkingTime: streamDuration,
            isError: true,
            intent: turnIntent
        });
        if (currentConversationId === requestConversationId) {
            conversationHistory = [...errorConversationHistory];
        }
        if (!requestStartedInPrivate && requestConversationId && conversations[requestConversationId]) {
            conversations[requestConversationId].messages = [...errorConversationHistory];
            saveConversationsToStorage();
            updateChatHistory();
        }
        syncTopbarTitle();
        runQueuedComposerMessageSoon();
    }

    updateScrollBottomAffordance();
}

function openPopup() {
    showToast('API Harmonika AI sudah dikonfigurasi otomatis.', 'success');
    return;
    settingsPopup.style.display = 'flex';
    settingsPopup.setAttribute('aria-hidden', 'false');
}

function closePopup() {
    settingsPopup.style.display = 'none';
    settingsPopup.setAttribute('aria-hidden', 'true');
}

// Save settings function
async function saveSettings() {
    const baseUrl = baseUrlInput.value.trim().replace(/\/+$/, ''); // Remove trailing slashes
    const apiKey = apiKeyInput.value;
    const saveButton = settingsSaveButton || document.getElementById('settings-save');
    if (!saveButton) return;
    
    saveButton.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Memuat model...';
    saveButton.disabled = true;

    try {
        // Save to IndexedDB
        await db.settings.put({ key: 'apiKey', value: apiKey });
        await db.settings.put({ key: 'baseUrl', value: baseUrl });

        await fetch('/save-settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                apiKey: apiKey,
                baseUrl: baseUrl
            })
        });

        await fetchModels();

        await setSelectedModel('harmonika-ai');
        
        saveButton.innerHTML = 'Simpan pengaturan';
        saveButton.disabled = false;
        closePopup();
        
    } catch (error) {
        console.error('Error saving settings:', error);
        saveButton.innerHTML = 'Simpan pengaturan';
        saveButton.disabled = false;
    }
}

function adjustTextareaHeight(textarea) {
    requestAnimationFrame(() => {
        textarea.style.height = '44px';
        const newHeight = Math.max(44, textarea.scrollHeight);
        textarea.style.height = newHeight + 'px';
        submitButton.style.height = newHeight + 'px';
        uploadFiles.style.height = newHeight + 'px';
    });
}

userInput.addEventListener('keydown', function(event) {
    if (event.isComposing) return;
    if (event.key === 'Enter') {
        event.preventDefault();
        
        if (event.shiftKey) {
            const start = this.selectionStart;
            const end = this.selectionEnd;
            this.value = this.value.substring(0, start) + '\n' + this.value.substring(end);
            this.selectionStart = this.selectionEnd = start + 1;
            adjustTextareaHeight(this);
        } else {
            sendMessage(event);
            this.style.height = '44px';
            submitButton.style.height = '44px';
            uploadFiles.style.height = '44px';
        }
    }
});

userInput.addEventListener('input', function() {
    adjustTextareaHeight(this);
    refreshComposerState();
});
refreshComposerState();

function startNewChat() {
    clearPendingAttachment();
    clearQueuedComposerMessage();
    userInput.placeholder = "Tanya Harmonika AI…";
    
    // Abort any ongoing stream before starting new chat
    if (currentController) {
        currentController.abort();
        currentController = null;
        toggleSubmitButtonIcon(false);
    }
    
    // Store current scroll position
    const currentScroll = chatHistory.scrollTop;
    
    chatMessages.innerHTML = '';
    conversationHistory = [];
    if (!isPrivateChat) {
        currentConversationId = makeConversationId();
        conversations[currentConversationId] = normalizeConversationRecord(currentConversationId, {
            messages: [],
            title: 'Chat Baru'
        });
        setConversationUrl(currentConversationId, false);
        updateChatHistory();
        saveConversationsToStorage();
    } else {
        setConversationUrl('', false);
    }
    updateScrollBottomAffordance();
    showHaiWelcome();
    syncTopbarTitle(true);
    
    // Restore scroll position
    chatHistory.scrollTop = currentScroll;

    // Focus on the input bar
    userInput.focus();
}

newChatButton.addEventListener('click', startNewChat);
renameChatButton?.addEventListener('click', () => renameConversation());
copyChatLinkButton?.addEventListener('click', copyCurrentChatLink);
historySearchInput?.addEventListener('input', updateChatHistory);

window.addEventListener('popstate', () => {
    if (currentController) {
        currentController.abort();
        currentController = null;
        toggleSubmitButtonIcon(false);
    }
    const id = urlConversationId();
    if (id && conversations[id]) {
        switchConversation(id, false);
    } else if (!id) {
        currentConversationId = null;
        conversationHistory = [];
        chatMessages.innerHTML = '';
        showHaiWelcome();
        updateChatHistory();
        syncTopbarTitle(true);
    }
});

// Helper function to format dates
function formatDate(timestamp) {
    const date = new Date(Number(timestamp));
    const now = new Date();
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    const weekAgo = new Date(now);
    weekAgo.setDate(weekAgo.getDate() - 7);

    if (date.toDateString() === now.toDateString()) {
        return 'Hari ini';
    } else if (date.toDateString() === yesterday.toDateString()) {
        return 'Kemarin';
    } else if (date > weekAgo) {
        return '7 hari terakhir';
    } else {
        return 'Lebih lama';
    }
}

// Update chat history function
function updateChatHistory() {
    // Store current scroll position
    const currentScroll = chatHistory.scrollTop;
    
    chatHistory.innerHTML = '';

    const searchQuery = (historySearchInput?.value || '').trim().toLowerCase();
    const sortedConversations = Object.entries(conversations)
        .filter(([id, conversation]) => !searchQuery || conversationSearchText(id, conversation).includes(searchQuery))
        .sort(([idA, conversationA], [idB, conversationB]) => conversationSortValue(idB, conversationB) - conversationSortValue(idA, conversationA));

    if (Object.keys(conversations).length === 0) {
        chatMessages.innerHTML = '';
        conversationHistory = [];
        currentConversationId = null;
        setConversationUrl('', true);
        showHaiWelcome();
        renderHistoryEmpty('Belum ada riwayat', 'Mulai chat baru untuk menyimpan percakapan.');
        return;
    }

    if (sortedConversations.length === 0) {
        renderHistoryEmpty('Tidak ada hasil', 'Coba kata kunci lain.');
        return;
    }

    const groupedConversations = {
        'Hari ini': [],
        'Kemarin': [],
        '7 hari terakhir': [],
        'Lebih lama': []
    };

    sortedConversations.forEach(([id, conversation]) => {
        const group = formatDate(conversationSortValue(id, conversation));
        groupedConversations[group].push([id, conversation]);
    });

    const fragment = document.createDocumentFragment();

    Object.entries(groupedConversations).forEach(([group, conversations]) => {
        if (conversations.length > 0) {
            const groupHeader = document.createElement('div');
            groupHeader.className = 'conversation-group-header';
            groupHeader.textContent = group;
            fragment.appendChild(groupHeader);

            conversations.forEach(([id, conversation]) => {
                const chatDiv = document.createElement('div');
                chatDiv.id = `conversation-${id}`;
                chatDiv.className = 'conversation-item';
                if (id === currentConversationId) {
                    chatDiv.classList.add('active');
                }

                const textWrap = document.createElement('div');
                textWrap.className = 'conversation-text';

                const textSpan = document.createElement('span');
                textSpan.textContent = cleanConversationTitle(conversation.title || 'Chat Baru');
                textSpan.title = textSpan.textContent;

                const metaSpan = document.createElement('small');
                metaSpan.textContent = formatConversationMeta(id, conversation);

                textWrap.appendChild(textSpan);
                textWrap.appendChild(metaSpan);
                chatDiv.appendChild(textWrap);

                const renameButton = document.createElement('button');
                renameButton.className = 'rename-button';
                renameButton.type = 'button';
                renameButton.title = 'Ubah judul chat';
                renameButton.setAttribute('aria-label', `Ubah judul chat ${textSpan.textContent}`);
                renameButton.innerHTML = '<i class="fa fa-pencil" aria-hidden="true"></i>';
                renameButton.onclick = (e) => {
                    e.stopPropagation();
                    renameConversation(id);
                };
                chatDiv.appendChild(renameButton);

                const deleteButton = document.createElement('button');
                deleteButton.className = 'delete-button';
                deleteButton.type = 'button';
                deleteButton.title = 'Hapus chat';
                deleteButton.setAttribute('aria-label', `Hapus chat ${textSpan.textContent}`);
                deleteButton.innerHTML = '<i class="fa fa-times" aria-hidden="true"></i>';
                deleteButton.onclick = (e) => {
                    e.stopPropagation();
                    deleteConversation(id, e);
                };
                chatDiv.appendChild(deleteButton);

                chatDiv.onclick = () => switchConversation(id);

                fragment.appendChild(chatDiv);
            });
        }
    });

    chatHistory.appendChild(fragment);
    syncTopbarTitle();
    
    // Restore scroll position
    chatHistory.scrollTop = currentScroll;
}

// Update the switchConversation function to use the message's stored end tag
async function switchConversation(conversationId, pushUrl = true) {
    if (currentConversationId === conversationId) return;
    clearPendingAttachment();
    clearQueuedComposerMessage();
    
    // Abort any ongoing stream before switching
    if (currentController) {
        currentController.abort();
        currentController = null;
        toggleSubmitButtonIcon(false);
    }
    
    if (currentConversationId) {
        conversations[currentConversationId].messages = [...conversationHistory];
        // Update the old conversation in IndexedDB
        conversations[currentConversationId].updated = Date.now();
        await db.conversations.put(normalizeConversationRecord(currentConversationId, conversations[currentConversationId]));
        scheduleServerHistorySync();
    }
    
    currentConversationId = conversationId;
    if (pushUrl) setConversationUrl(currentConversationId, false);
    // Update currentConversation in IndexedDB
    await db.currentConversation.put({
        key: 'currentId',
        value: conversationId
    });
    
    conversationHistory = [...conversations[conversationId].messages];
    chatMessages.innerHTML = '';
    syncTopbarTitle();
    
    conversationHistory.forEach(msg => {
        if (msg.role === 'assistant') {
            const messageContainer = document.createElement('div');
            messageContainer.className = 'assistant-message-container';
            if (msg.messageId) {
                messageContainer.dataset.messageId = msg.messageId;
            }
            if (msg.isError) {
                messageContainer.dataset.error = 'true';
            }
            
            const messageDiv = document.createElement('div');
            messageDiv.classList.add('assistant-message');
            
            // Create React root for assistant message
            if (!messageDiv.reactRoot) {
                messageDiv.reactRoot = ReactDOM.createRoot(messageDiv);
            }
            
            // Set streamDuration to this message's thinking time
            streamDuration = msg.thinkingTime;
            
            // Pass the content object with raw content and expanded state
            messageDiv.reactRoot.render(
                React.createElement(MarkdownContent, { 
                    content: markdownContentForStoredMessage(msg),
                    messageEndTag: msg.endTag
                })
            );
            
            // Reset streamDuration to null after rendering
            streamDuration = null;
            
            messageContainer.appendChild(messageDiv);
            appendSourceChips(messageContainer, messageSources(msg));
            if (msg.isError) {
                appendAssistantActionButtonsIfMissing(
                    messageContainer,
                    messageDiv,
                    typeof msg.content === 'object' ? msg.content.raw : msg.content
                );
                chatMessages.appendChild(messageContainer);
                return;
            }

            // Create button container
            const buttonContainer = document.createElement('div');
            buttonContainer.className = 'message-buttons';

            const editButton = document.createElement('button');
            editButton.className = 'message-edit-button';
            editButton.innerHTML = haiIconImg('pencil', 'Edit pesan');
            editButton.onclick = () => handleMessageEdit(messageDiv, 
                typeof msg.content === 'object' ? msg.content.raw : msg.content, 
                'assistant'
            );

            const copyButton = document.createElement('button');
            copyButton.className = 'message-copy-button';
            copyButton.innerHTML = haiIconImg('copy', 'Salin pesan');
            copyButton.onclick = () => copyToClipboard(
                typeof msg.content === 'object' ? msg.content.raw : msg.content, 
                copyButton
            );

            const deleteButton = document.createElement('button');
            deleteButton.className = 'message-delete-button';
            deleteButton.innerHTML = haiIconImg('trash', 'Hapus pesan');
            deleteButton.onclick = () => handleMessageDelete(messageDiv, 
                typeof msg.content === 'object' ? msg.content.raw : msg.content, 
                'assistant'
            );

            const continueButton = document.createElement('button');
            continueButton.className = 'message-continue-button';
            continueButton.innerHTML = haiIconImg('continue', 'Lanjutkan jawaban');
            continueButton.onclick = () => handleContinueGeneration(messageDiv, 
                typeof msg.content === 'object' ? msg.content.raw : msg.content
            );

            buttonContainer.appendChild(editButton);
            buttonContainer.appendChild(copyButton);
            buttonContainer.appendChild(deleteButton);
            buttonContainer.appendChild(continueButton);
            messageContainer.appendChild(buttonContainer);
            
            chatMessages.appendChild(messageContainer);
        } else {
            // Handle user messages as before...
            const messageContainer = document.createElement('div');
            messageContainer.className = 'user-message-container';
            const messageDiv = document.createElement('div');
            messageDiv.classList.add('user-message');
            // Preserve line breaks by replacing them with <br> tags
            messageDiv.innerHTML = formatUserMessage(msg.content);
            messageContainer.appendChild(messageDiv);

            // Add buttons for user message
            const buttonContainer = document.createElement('div');
            buttonContainer.className = 'message-buttons';

            const editButton = document.createElement('button');
            editButton.className = 'message-edit-button';
            editButton.innerHTML = haiIconImg('pencil', 'Edit pesan');
            editButton.onclick = () => handleMessageEdit(messageDiv, msg.content, 'user');

            const copyButton = document.createElement('button');
            copyButton.className = 'message-copy-button';
            copyButton.innerHTML = haiIconImg('copy', 'Salin pesan');
            copyButton.onclick = () => copyToClipboard(msg.content, copyButton);

            const deleteButton = document.createElement('button');
            deleteButton.className = 'message-delete-button';
            deleteButton.innerHTML = haiIconImg('trash', 'Hapus pesan');
            deleteButton.onclick = () => handleMessageDelete(messageDiv, msg.content, 'user');

            buttonContainer.appendChild(editButton);
            buttonContainer.appendChild(copyButton);
            buttonContainer.appendChild(deleteButton);
            messageContainer.appendChild(buttonContainer);

            chatMessages.appendChild(messageContainer);
        }
    });
    updateQuickPromptVisibility();
    
    updateChatHistory();
}

async function deleteConversation(conversationId, clickEvent = null) {
    clickEvent?.stopPropagation?.();
    const title = cleanConversationTitle(conversations[conversationId]?.title || 'chat ini');
    if (!window.confirm(`Hapus "${title}" dari riwayat chat?`)) {
        return;
    }
    
    const sortedConversationIds = Object.keys(conversations)
        .sort((a, b) => conversationSortValue(b, conversations[b]) - conversationSortValue(a, conversations[a]));
    
    const currentIndex = sortedConversationIds.indexOf(conversationId);
    
    // Delete from IndexedDB
    try {
        markConversationDeleted(conversationId, Date.now());
        await db.conversations.delete(conversationId);
        
        // Delete from memory
        delete conversations[conversationId];
        
        const remainingConversationIds = Object.keys(conversations)
            .sort((a, b) => conversationSortValue(b, conversations[b]) - conversationSortValue(a, conversations[a]));
        
        let nextConversationId = null;
        if (remainingConversationIds.length > 0) {
            nextConversationId = remainingConversationIds[currentIndex] || remainingConversationIds[currentIndex - 1];
        }
        
        if (conversationId === currentConversationId) {
            chatMessages.innerHTML = '';
            conversationHistory = [];
            currentConversationId = null;
            
            // Update currentConversation in IndexedDB
            await db.currentConversation.put({
                key: 'currentId',
                value: null
            });
            
            if (nextConversationId && conversations[nextConversationId]) {
                await switchConversation(nextConversationId);
            } else {
                setConversationUrl('', true);
                showHaiWelcome();
            }
        }
        
        await db.currentConversation.put({
            key: 'currentId',
            value: currentConversationId || null
        });
        scheduleServerHistorySync();
        updateChatHistory();
        showToast('Chat dihapus dari riwayat.', 'success');
    } catch (error) {
        console.error('Error deleting conversation:', error);
        showToast('Gagal menghapus chat. Coba lagi.', 'error');
    }
}

function isMobileLayout() {
    return window.matchMedia('(max-width: 820px), (max-height: 520px) and (orientation: landscape)').matches;
}

function setSidebarVisible(visible, focusComposer = true) {
    const mobile = isMobileLayout();
    document.body.classList.toggle('hai-sidebar-open', Boolean(visible && mobile));
    document.body.classList.toggle('hai-sidebar-collapsed', !visible);
    sidebarButtons.style.display = visible ? 'none' : 'flex';
    rightSide.classList.toggle('sidebar-hidden', !visible);
    rightSide.style.flex = visible ? '' : '100';
    if (focusComposer) {
        userInput.focus();
    }
}

closeSidebarBtn.addEventListener('click', () => {
    setSidebarVisible(false);
});

showSidebarBtn.addEventListener('click', () => {
    setSidebarVisible(true);
});

sidebarBackdrop.addEventListener('click', () => {
    setSidebarVisible(false, false);
});

window.addEventListener('resize', () => {
    if (!isMobileLayout()) {
        document.body.classList.remove('hai-sidebar-open');
    }
});

if (isMobileLayout()) {
    setSidebarVisible(false, false);
}

newChatSidebarBtn.addEventListener('click', startNewChat);

scrollBottomButton = document.createElement('button');
scrollBottomButton.type = 'button';
scrollBottomButton.className = 'scroll-bottom-button';
scrollBottomButton.innerHTML = '<i class="fa fa-arrow-down" aria-hidden="true"></i><span>Ke terbaru</span>';
scrollBottomButton.disabled = true;
scrollBottomButton.setAttribute('aria-label', 'Lompat ke pesan terbaru');
scrollBottomButton.setAttribute('aria-hidden', 'true');
chatWrapper.appendChild(scrollBottomButton);

chatWrapper.addEventListener('scroll', () => {
    if (Date.now() - lastProgrammaticScrollAt > 220) {
        autoScrollLockedToBottom = isNearChatBottom(220);
    }
    updateScrollBottomAffordance();
}, { passive: true });

window.addEventListener('resize', () => {
    updateScrollBottomAffordance();
});

scrollBottomButton.addEventListener('click', () => {
    scrollChatToBottom('smooth');
});

function togglePrivateChat() {
    isPrivateChat = !isPrivateChat;
    const privateButton = document.getElementById('private-chat');
    const icon = privateButton.querySelector('i');
    
    if (isPrivateChat) {
        // Clear chat messages and history
        chatMessages.innerHTML = '';
        conversationHistory = [];
        currentConversationId = null;
        
        // Update icon and button style
        icon.classList.remove('fa-user-circle-o');
        icon.classList.add('fa-user-circle');
        privateButton.classList.add('active');
        
        // Hide chat history in left sidebar when in private mode
        chatHistory.style.display = 'none';
    } else {
        // Clear private chat messages
        chatMessages.innerHTML = '';
        conversationHistory = [];
        
        // Update icon and button style
        icon.classList.remove('fa-user-circle');
        icon.classList.add('fa-user-circle-o');
        privateButton.classList.remove('active');
        
        // Show chat history and restore previous conversations
        chatHistory.style.display = 'flex';
        loadConversationsFromStorage();
    }
    
    updateScrollBottomAffordance();
    
    // Maintain focus on input bar
    userInput.focus();
}
document.getElementById('private-chat').addEventListener('click', togglePrivateChat);

// Toggle password visibility
document.querySelector('.toggle-password').addEventListener('click', function() {
    const apiKeyInput = document.getElementById('api-key');
    const icon = this.querySelector('i');
    
    if (apiKeyInput.type === 'password') {
        apiKeyInput.type = 'text';
        icon.classList.remove('fa-eye');
        icon.classList.add('fa-eye-slash');
    } else {
        apiKeyInput.type = 'password';
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
    }
});

// Message edit function
async function handleMessageEdit(messageDiv, content, role) {
    if (currentController) {
        showToast('Harmonika AI masih menjawab. Klik Stop dulu sebelum mengedit pesan.', 'error');
        return;
    }
    const originalMessageContainer = messageDiv.closest(`.${role}-message-container`);
    const messageIndex = findMessageIndexForElement(messageDiv, content, role);
    const originalMessage = messageIndex !== -1 ? conversationHistory[messageIndex] : null;
    const messageEndTag = originalMessage?.endTag || END_TAG;
    
    // Create edit container with the new styling
    const editContainer = document.createElement('div');
    editContainer.className = 'edit-container';
    
    // Create textarea with proper styling
    const textarea = document.createElement('textarea');
    textarea.className = 'edit-textarea';
    textarea.spellcheck = false;
    
    // Extract raw content if it's an object (assistant message)
    const contentToEdit = plainTextFromMessageContent(content, originalMessage);
    textarea.value = contentToEdit;
    
    // Create buttons container with updated structure
    const buttonContainer = document.createElement('div');
    buttonContainer.className = 'edit-buttons';
    
    // Create right buttons container
    const rightButtonsContainer = document.createElement('div');
    rightButtonsContainer.className = 'edit-buttons-right';
    
    // Create Save button (now goes in right container)
    const saveButton = document.createElement('button');
    saveButton.className = 'edit-button edit-save-button';
    saveButton.type = 'button';
    saveButton.textContent = 'Simpan';
    saveButton.title = 'Simpan perubahan';
    saveButton.setAttribute('aria-label', 'Simpan perubahan pesan');
    
    // Create Cancel button
    const cancelButton = document.createElement('button');
    cancelButton.className = 'edit-button edit-cancel-button';
    cancelButton.type = 'button';
    cancelButton.textContent = 'Batal';
    cancelButton.title = 'Batal edit';
    cancelButton.setAttribute('aria-label', 'Batal edit pesan');
    
    // Create Send button (only for user messages)
    const sendButton = document.createElement('button');
    sendButton.className = 'edit-button edit-send-button';
    sendButton.type = 'button';
    sendButton.textContent = 'Kirim';
    sendButton.title = 'Kirim ulang pesan';
    sendButton.setAttribute('aria-label', 'Kirim ulang pesan yang diedit');
    sendButton.style.display = role === 'user' ? 'flex' : 'none';
    
    if (role === 'user') {
        buttonContainer.appendChild(saveButton);
        rightButtonsContainer.appendChild(cancelButton);
        rightButtonsContainer.appendChild(sendButton);
    } else {
        rightButtonsContainer.appendChild(cancelButton);
        rightButtonsContainer.appendChild(saveButton);
    }
    
    buttonContainer.appendChild(rightButtonsContainer);
    editContainer.appendChild(textarea);
    editContainer.appendChild(buttonContainer);
    originalMessageContainer.replaceWith(editContainer);

    // Auto-adjust textarea height
    function adjustTextareaHeight() {
        const scrollPos = textarea.scrollTop;
        textarea.style.height = 'auto';
        const newHeight = Math.max(120, textarea.scrollHeight);
        textarea.style.height = newHeight + 'px';
        textarea.scrollTop = scrollPos;
    }
    
    textarea.addEventListener('input', function(e) {
        const chatWrapper = document.querySelector('.middle-panel');
        const scrollPos = chatWrapper.scrollTop;
        adjustTextareaHeight();
        chatWrapper.scrollTop = scrollPos;
    });
    
    adjustTextareaHeight();
    
    // Focus the textarea and place cursor at the end
    textarea.focus();
    textarea.setSelectionRange(textarea.value.length, textarea.value.length);

    // Send button handler
    sendButton.onclick = async () => {
        const newContent = textarea.value;
        clearMessagesAfter(editContainer);
        
        // Create user message container with preserved line breaks
        const userMessageContainer = document.createElement('div');
        userMessageContainer.className = 'user-message-container';
        const userMessageDiv = document.createElement('div');
        userMessageDiv.classList.add('user-message');
        userMessageDiv.innerHTML = formatUserMessage(newContent);
        userMessageContainer.appendChild(userMessageDiv);

        // Add buttons for user message
        const buttonContainer = document.createElement('div');
        buttonContainer.className = 'message-buttons';

        const editButton = document.createElement('button');
        editButton.className = 'message-edit-button';
        editButton.innerHTML = haiIconImg('pencil', 'Edit pesan');
        editButton.onclick = () => handleMessageEdit(userMessageDiv, newContent, 'user');

        const copyButton = document.createElement('button');
        copyButton.className = 'message-copy-button';
        copyButton.innerHTML = haiIconImg('copy', 'Salin pesan');
        copyButton.onclick = () => copyToClipboard(newContent, copyButton);

        const deleteButton = document.createElement('button');
        deleteButton.className = 'message-delete-button';
        deleteButton.innerHTML = haiIconImg('trash', 'Hapus pesan');
        deleteButton.onclick = () => handleMessageDelete(userMessageDiv, newContent, 'user');

        buttonContainer.appendChild(editButton);
        buttonContainer.appendChild(copyButton);
        buttonContainer.appendChild(deleteButton);
        userMessageContainer.appendChild(buttonContainer);

        // Replace edit container with user message
        editContainer.replaceWith(userMessageContainer);
        
        // Clean conversation history for API
        let apiConversationHistory = conversationHistory.slice(0, messageIndex).map(cleanMessageForAPI).filter(Boolean);
        
        conversationHistory = conversationHistory.slice(0, messageIndex);
        await sendEditedMessage(newContent, apiConversationHistory);
    };

    // Cancel button handler
    cancelButton.onclick = () => {
        const messageContainer = document.createElement('div');
        messageContainer.className = `${role}-message-container`;
        
        // Preserve messageId if it exists
        if (originalMessage?.messageId) {
            messageContainer.dataset.messageId = originalMessage.messageId;
        }
        
        const newMessageDiv = document.createElement('div');
        newMessageDiv.classList.add(`${role}-message`);
        
        if (role === 'assistant') {
            // Create React root for assistant message
            if (!newMessageDiv.reactRoot) {
                newMessageDiv.reactRoot = ReactDOM.createRoot(newMessageDiv);
            }
            // Render using MarkdownContent with original content and state
            newMessageDiv.reactRoot.render(
                React.createElement(MarkdownContent, {
                    content: typeof originalMessage?.content === 'object' ? 
                        originalMessage.content : {
                            raw: contentToEdit,
                            reasoningExpanded: false
                        },
                    messageEndTag: messageEndTag
                })
            );
        } else {
            // Preserve line breaks for user messages when canceling edits
            newMessageDiv.innerHTML = formatUserMessage(contentToEdit); // Change this line
        }
        
        messageContainer.appendChild(newMessageDiv);
        
        // Add buttons...
        const buttonContainer = document.createElement('div');
        buttonContainer.className = 'message-buttons';

        const editButton = document.createElement('button');
        editButton.className = 'message-edit-button';
        editButton.innerHTML = haiIconImg('pencil', 'Edit pesan');
        editButton.onclick = () => handleMessageEdit(newMessageDiv, contentToEdit, role);

        const copyButton = document.createElement('button');
        copyButton.className = 'message-copy-button';
        copyButton.innerHTML = haiIconImg('copy', 'Salin pesan');
        copyButton.onclick = () => copyToClipboard(contentToEdit, copyButton);

        const deleteButton = document.createElement('button');
        deleteButton.className = 'message-delete-button';
        deleteButton.innerHTML = haiIconImg('trash', 'Hapus pesan');
        deleteButton.onclick = () => handleMessageDelete(messageDiv, contentToEdit, role);

        if (role === 'assistant') {
            const continueButton = document.createElement('button');
            continueButton.className = 'message-continue-button';
            continueButton.innerHTML = haiIconImg('continue', 'Lanjutkan jawaban');
            continueButton.onclick = () => handleContinueGeneration(newMessageDiv, contentToEdit);
            
            buttonContainer.appendChild(editButton);
            buttonContainer.appendChild(copyButton);
            buttonContainer.appendChild(deleteButton);
            buttonContainer.appendChild(continueButton);
        } else {
            buttonContainer.appendChild(editButton);
            buttonContainer.appendChild(copyButton);
            buttonContainer.appendChild(deleteButton);
        }

        messageContainer.appendChild(buttonContainer);
        editContainer.replaceWith(messageContainer);
    };

    // Save button handler
    saveButton.onclick = () => {
        const newContent = textarea.value;
        
        if (messageIndex !== -1) {
            if (role === 'assistant') {
                conversationHistory[messageIndex] = {
                    ...originalMessage,
                    content: {
                        raw: newContent,
                        reasoningExpanded: false
                    }
                };
            } else {
                conversationHistory[messageIndex] = {
                    ...originalMessage,
                    content: newContent
                };
            }
            
            if (!isPrivateChat && currentConversationId) {
                conversations[currentConversationId].messages = [...conversationHistory];
                saveConversationsToStorage();
            }
        }
        
        const messageContainer = document.createElement('div');
        messageContainer.className = `${role}-message-container`;
        
        // Preserve messageId if it exists
        if (originalMessage?.messageId) {
            messageContainer.dataset.messageId = originalMessage.messageId;
        }
        
        const newMessageDiv = document.createElement('div');
        newMessageDiv.classList.add(`${role}-message`);
        
        if (role === 'assistant') {
            // Create React root for assistant message
            if (!newMessageDiv.reactRoot) {
                newMessageDiv.reactRoot = ReactDOM.createRoot(newMessageDiv);
            }
            // Render using MarkdownContent with new content but preserve expanded state
            newMessageDiv.reactRoot.render(
                React.createElement(MarkdownContent, {
                    content: {
                        raw: newContent,
                        reasoningExpanded: false
                    },
                    messageEndTag: messageEndTag
                })
            );
        } else {
            // Preserve line breaks for user messages when saving edits
            newMessageDiv.innerHTML = formatUserMessage(newContent);
        }
        
        messageContainer.appendChild(newMessageDiv);
        
        // Add buttons
        const buttonContainer = document.createElement('div');
        buttonContainer.className = 'message-buttons';

        const editButton = document.createElement('button');
        editButton.className = 'message-edit-button';
        editButton.innerHTML = haiIconImg('pencil', 'Edit pesan');
        editButton.onclick = () => handleMessageEdit(newMessageDiv, newContent, role);

        const copyButton = document.createElement('button');
        copyButton.className = 'message-copy-button';
        copyButton.innerHTML = haiIconImg('copy', 'Salin pesan');
        copyButton.onclick = () => copyToClipboard(newContent, copyButton);

        const deleteButton = document.createElement('button');
        deleteButton.className = 'message-delete-button';
        deleteButton.innerHTML = haiIconImg('trash', 'Hapus pesan');
        deleteButton.onclick = () => handleMessageDelete(newMessageDiv, newContent, role);

        if (role === 'assistant') {
            const continueButton = document.createElement('button');
            continueButton.className = 'message-continue-button';
            continueButton.innerHTML = haiIconImg('continue', 'Lanjutkan jawaban');
            continueButton.onclick = () => handleContinueGeneration(newMessageDiv, newContent);
            
            buttonContainer.appendChild(editButton);
            buttonContainer.appendChild(copyButton);
            buttonContainer.appendChild(deleteButton);
            buttonContainer.appendChild(continueButton);
        } else {
            buttonContainer.appendChild(editButton);
            buttonContainer.appendChild(copyButton);
            buttonContainer.appendChild(deleteButton);
        }

        messageContainer.appendChild(buttonContainer);
        editContainer.replaceWith(messageContainer);
    };
}

// Also update the findMessageIndex function to handle content objects:
function findMessageIndex(content, role) {
    return conversationHistory.findIndex(msg => {
        if (msg.role !== role) return false;
        
        const msgContent = plainTextFromMessageContent(msg.content, msg);
        const searchContent = plainTextFromMessageContent(content);
        
        return msgContent === searchContent;
    });
}

function findMessageIndexForElement(messageDiv, content, role) {
    const messageContainer = messageDiv?.closest?.(`.${role}-message-container`);
    const messageId = messageContainer?.dataset?.messageId;
    if (messageId) {
        const idIndex = conversationHistory.findIndex(msg => msg.role === role && String(msg.messageId || '') === String(messageId));
        if (idIndex !== -1) return idIndex;
    }
    return findMessageIndex(content, role);
}

function assistantRawContent(message) {
    if (!message) return '';
    if (typeof message.content === 'object' && message.content !== null) {
        return message.content.raw || message.content.content || '';
    }
    return message.content || '';
}

function userTextForIntent(content) {
    if (typeof content === 'string') return content;
    if (Array.isArray(content)) {
        return content
            .filter(part => part && part.type === 'text')
            .map(part => part.text || '')
            .join(' ');
    }
    if (content && typeof content === 'object') {
        if (Array.isArray(content.content)) return userTextForIntent(content.content);
        return content.raw || content.content || '';
    }
    return '';
}

const HAI_ACTION_ICON_VERSION = HAI_ICON_VERSION;

function haiActionIconSrc(iconName) {
    return `/static/images/icons/${iconName}.svg?v=${HAI_ACTION_ICON_VERSION}`;
}

function createMessageActionButton(className, iconName, label) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = className;
    button.title = label;
    button.setAttribute('aria-label', label);
    button.innerHTML = `<img src="${haiActionIconSrc(iconName)}" alt="" aria-hidden="true" class="icon-svg">`;
    return button;
}

function createAssistantActionButtons(messageDiv, content) {
    const buttonContainer = document.createElement('div');
    buttonContainer.className = 'message-buttons';

    const editButton = createMessageActionButton('message-edit-button', 'pencil', 'Edit pesan');
    editButton.onclick = () => handleMessageEdit(messageDiv, content, 'assistant');

    const copyButton = createMessageActionButton('message-copy-button', 'copy', 'Salin pesan');
    copyButton.onclick = () => copyToClipboard(content, copyButton);

    const deleteButton = createMessageActionButton('message-delete-button', 'trash', 'Hapus pesan');
    deleteButton.onclick = () => handleMessageDelete(messageDiv, content, 'assistant');

    const regenerateButton = createMessageActionButton('message-regenerate-button', 'regenerate', 'Buat ulang jawaban');
    regenerateButton.onclick = () => handleRegenerateResponse(regenerateButton);

    const continueButton = createMessageActionButton('message-continue-button', 'continue', 'Lanjutkan jawaban');
    continueButton.onclick = () => handleContinueGeneration(messageDiv, content);

    buttonContainer.appendChild(editButton);
    buttonContainer.appendChild(copyButton);
    buttonContainer.appendChild(deleteButton);
    buttonContainer.appendChild(regenerateButton);
    buttonContainer.appendChild(continueButton);
    return buttonContainer;
}

function createAssistantErrorActionButtons(messageDiv, content) {
    const buttonContainer = document.createElement('div');
    buttonContainer.className = 'message-buttons';

    const copyButton = createMessageActionButton('message-copy-button', 'copy', 'Salin pesan');
    copyButton.onclick = () => copyToClipboard(content, copyButton);

    const deleteButton = createMessageActionButton('message-delete-button', 'trash', 'Hapus pesan');
    deleteButton.onclick = () => handleMessageDelete(messageDiv, content, 'assistant');

    const regenerateButton = createMessageActionButton('message-regenerate-button', 'regenerate', 'Buat ulang jawaban');
    regenerateButton.onclick = () => handleRegenerateResponse(regenerateButton);

    buttonContainer.appendChild(copyButton);
    buttonContainer.appendChild(deleteButton);
    buttonContainer.appendChild(regenerateButton);
    return buttonContainer;
}

function appendAssistantActionButtonsIfMissing(container, messageDiv, content) {
    if (!container || container.querySelector('.message-buttons')) return;
    const isError = container.dataset?.error === 'true';
    container.appendChild(isError
        ? createAssistantErrorActionButtons(messageDiv, content)
        : createAssistantActionButtons(messageDiv, content));
    enhanceMessageActionButtons(container);
}

function enhanceMessageActionButtons(root = chatMessages) {
    const actionLabels = [
        ['.message-edit-button', 'Edit pesan', 'pencil'],
        ['.message-copy-button', 'Salin pesan', 'copy'],
        ['.message-delete-button', 'Hapus pesan', 'trash'],
        ['.message-regenerate-button', 'Buat ulang jawaban', 'regenerate'],
        ['.message-continue-button', 'Lanjutkan jawaban', 'continue']
    ];
    const scope = root?.querySelectorAll ? root : document;
    actionLabels.forEach(([selector, label, iconName]) => {
        const buttons = [];
        if (root?.matches?.(selector)) buttons.push(root);
        scope.querySelectorAll?.(selector).forEach(button => buttons.push(button));
        buttons.forEach(button => {
            button.type = 'button';
            button.title = label;
            button.setAttribute('aria-label', label);
            button.querySelectorAll?.('img.icon-svg').forEach(icon => {
                icon.alt = '';
                icon.setAttribute('aria-hidden', 'true');
                const expectedSrc = haiActionIconSrc(iconName);
                if (!String(icon.getAttribute('src') || '').includes(expectedSrc)) {
                    icon.src = expectedSrc;
                }
            });
            button.dataset.actionLabel = label;
        });
    });
}

function enhanceRegenerateButtons(root = chatMessages) {
    const buttonContainers = [];
    if (root.matches?.('.assistant-message-container .message-buttons')) {
        buttonContainers.push(root);
    }
    root.querySelectorAll?.('.assistant-message-container .message-buttons').forEach(buttonContainer => {
        buttonContainers.push(buttonContainer);
    });
    buttonContainers.forEach(buttonContainer => {
        if (buttonContainer.querySelector('.message-regenerate-button')) return;
        const regenerateButton = createMessageActionButton('message-regenerate-button', 'regenerate', 'Buat ulang jawaban');
        regenerateButton.onclick = () => handleRegenerateResponse(regenerateButton);
        const continueButton = buttonContainer.querySelector('.message-continue-button');
        buttonContainer.insertBefore(regenerateButton, continueButton || null);
    });
    enhanceMessageActionButtons(root);
}

const regenerateButtonObserver = new MutationObserver(mutations => {
    for (const mutation of mutations) {
        mutation.addedNodes.forEach(node => {
            if (node.nodeType === Node.ELEMENT_NODE) {
                enhanceRegenerateButtons(node);
                enhanceMessageActionButtons(node);
            }
        });
    }
});
regenerateButtonObserver.observe(chatMessages, { childList: true, subtree: true });
window.setTimeout(() => {
    enhanceRegenerateButtons();
    enhanceMessageActionButtons();
}, 0);

// Helper function to clear messages after a specific element
function clearMessagesAfter(element) {
    let nextElement = element.nextElementSibling;
    while (nextElement) {
        nextElement.remove();
        nextElement = element.nextElementSibling;
    }
}

let lastActionWasAbort = false; // Flag to track if the last action was an abort

async function sendEditedMessage(newContent, apiConversationHistory) {
    if (currentController) {
        showToast('Harmonika AI masih menjawab. Klik Stop dulu sebelum mengedit pesan.', 'error');
        return;
    }
    let assistantMessageContainer;
    let assistantMessage;
    let messageId = Date.now().toString();
    let continuedResponse = '';
    const turnIntent = detectHaiIntent(newContent).type;

    // Reset stream timer variables before starting new message
    streamStartTime = null;
    streamDuration = null;

    try {
        currentController = new AbortController();
        toggleSubmitButtonIcon(true);
        startStreamTimer();

        // Check if we should generate a title
        const shouldGenerateTitle = !isPrivateChat && 
            currentConversationId && 
            (!conversations[currentConversationId].title || conversationHistory.length <= 2);

        // Update history and render the assistant placeholder before the network
        // request so edit-send failures still leave a visible, recoverable state.
        const lastUserMessageIndex = conversationHistory.length - 1;
        if (lastUserMessageIndex >= 0 && conversationHistory[lastUserMessageIndex].role === "user") {
            conversationHistory[lastUserMessageIndex].content = newContent;
        } else {
            conversationHistory.push({
                role: "user",
                content: newContent
            });
        }

        assistantMessageContainer = document.createElement('div');
        assistantMessageContainer.className = 'assistant-message-container';
        assistantMessageContainer.dataset.messageId = messageId;
        assistantMessage = document.createElement('div');
        assistantMessage.classList.add('assistant-message');
        assistantMessageContainer.appendChild(assistantMessage);
        setAssistantWaiting(assistantMessageContainer, assistantMessage, {
            intent: turnIntent,
            label: turnIntent === 'image'
                ? 'Harmonika AI sedang mendesain ulang gambar…'
                : 'Harmonika AI sedang mengetik ulang jawaban…'
        });
        chatMessages.appendChild(assistantMessageContainer);
        scrollChatToBottom('smooth');

        const requestBody = {
            message: newContent,
            model: selectedModel,
            systemContent: SYSTEM_CONTENT,
            parameters: MODEL_PARAMETERS,
            conversation: apiConversationHistory,
            isDeepQueryMode: isDeepQueryMode,
            startTag: START_TAG,
            memoryContext: await getHaiMemoryContext(),
            libraryGrounding: haiLibraryGroundingMode,
            libraryContextMode: haiLibraryContextMode
        };

        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody),
            signal: currentController.signal
        });

        if (!response.ok || !response.body) {
            let errorMessage = `Harmonika AI belum bisa menjawab. Kode: ${response.status}`;
            try {
                const errorData = await response.json();
                if (errorData?.message) errorMessage = errorData.message;
            } catch (_) {}
            throw new Error(errorMessage);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let hasReceivedChunk = false;
        
        // Prepend START_TAG to response when in deep query mode
        if (isDeepQueryMode) {
            continuedResponse += START_TAG;
        }

        while (true) {
            const { done, value } = await reader.read();
            if (done) {
                clearAssistantWaiting(assistantMessageContainer);
                currentController = null;
                toggleSubmitButtonIcon(false);
                hasScrolledForThinkBlock = false;

                // Only stop timer if it hasn't been stopped by end tag detection
                if (streamStartTime) {
                    const duration = stopStreamTimer();
                    console.log(`Stream completed in ${duration}ms`);
                }
                
                // Finalize the response
                conversationHistory.push({
                    messageId,
                    role: "assistant",
                    content: {
                        raw: continuedResponse,
                        reasoningExpanded: false
                    },
                    endTag: END_TAG,
                    thinkingTime: streamDuration
                });

                // Generate title if needed
                if (shouldGenerateTitle) {
                    try {
                        const titleResponse = await fetch('/generate-title', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({
                                message: newContent,
                                model: selectedModel,
                                assistantResponse: continuedResponse.slice(0, 500)
                            })
                        });
                        
                        const titleData = await titleResponse.json();
                        if (titleData.title) {
                            conversations[currentConversationId].title = cleanConversationTitle(titleData.title);
                            syncTopbarTitle();
                        }
                    } catch (error) {
                        console.error('Error generating title:', error);
                    }
                }

                // Save to storage if not in private chat
                if (!isPrivateChat && currentConversationId) {
                    conversations[currentConversationId].messages = [...conversationHistory];
                    await saveConversationsToStorage();
                    updateChatHistory();
                }

                // Create and append buttons
                const buttonContainer = document.createElement('div');
                buttonContainer.className = 'message-buttons';

                const assistantEditButton = document.createElement('button');
                assistantEditButton.className = 'message-edit-button';
                assistantEditButton.innerHTML = haiIconImg('pencil', 'Edit pesan');
                assistantEditButton.onclick = () => handleMessageEdit(assistantMessage, continuedResponse, 'assistant');

                const assistantCopyButton = document.createElement('button');
                assistantCopyButton.className = 'message-copy-button';
                assistantCopyButton.innerHTML = haiIconImg('copy', 'Salin pesan');
                assistantCopyButton.onclick = () => copyToClipboard(continuedResponse, assistantCopyButton);

                const assistantDeleteButton = document.createElement('button');
                assistantDeleteButton.className = 'message-delete-button';
                assistantDeleteButton.innerHTML = haiIconImg('trash', 'Hapus pesan');
                assistantDeleteButton.onclick = () => handleMessageDelete(assistantMessage, continuedResponse, 'assistant');

                const continueButton = document.createElement('button');
                continueButton.className = 'message-continue-button';
                continueButton.innerHTML = haiIconImg('continue', 'Lanjutkan jawaban');
                continueButton.onclick = () => handleContinueGeneration(assistantMessage, continuedResponse);

                buttonContainer.appendChild(assistantEditButton);
                buttonContainer.appendChild(assistantCopyButton);
                buttonContainer.appendChild(assistantDeleteButton);
                buttonContainer.appendChild(continueButton);
                assistantMessageContainer.appendChild(buttonContainer);

                break;
            }

            const chunk = normalizeHaiStreamChunk(decoder.decode(value, { stream: true }));
                if (!chunk) continue;
            continuedResponse += chunk;
            if (!hasReceivedChunk) {
                hasReceivedChunk = true;
                markAssistantFirstVisibleChunk(assistantMessageContainer, turnIntent, {
                    status: turnIntent === 'image' ? 'imageDesigning' : 'textWriting',
                    progressStep: 2
                });
            }

            // Check if this chunk contains the end tag
            if (streamStartTime && checkForEndTag(continuedResponse)) {
                const duration = stopStreamTimer();
                console.log(`End tag detected. Thinking completed in ${duration}ms`);
            }

            // Update React component
            renderAssistantMarkdown(assistantMessage, continuedResponse, END_TAG, false);

            if (assistantMessage.querySelector('.think-block') && !hasScrolledForThinkBlock) {
                hasScrolledForThinkBlock = true;
                chatWrapper.scrollTo({
                    top: chatWrapper.scrollHeight,
                    behavior: 'smooth'
                });
            }
        }
    } catch (error) {
        if (error.name === 'AbortError') {
            console.log('Stream aborted by user');
            toggleSubmitButtonIcon(false);
            currentController = null;
            clearAssistantWaiting(assistantMessageContainer);

            // Only stop timer if it hasn't been stopped by end tag detection
            if (streamStartTime) {
                const duration = stopStreamTimer();
                console.log(`Stream aborted after ${duration}ms`);
            }
            if (!String(continuedResponse || '').trim()) {
                continuedResponse = 'Jawaban dihentikan.';
                setAssistantError(assistantMessage, continuedResponse);
            }
            
            // When aborting, only save the partial assistant response
            conversationHistory.push({
                messageId,
                role: "assistant",
                content: {
                    raw: continuedResponse,
                    reasoningExpanded: false
                },
                endTag: END_TAG,
                thinkingTime: streamDuration
            });

            // Save to storage if not in private chat
            if (!isPrivateChat && currentConversationId) {
                conversations[currentConversationId].messages = [...conversationHistory];
                await saveConversationsToStorage();
            }

            // Add buttons to assistant message when stopped
            const buttonContainer = document.createElement('div');
            buttonContainer.className = 'message-buttons';

            const assistantEditButton = document.createElement('button');
            assistantEditButton.className = 'message-edit-button';
            assistantEditButton.innerHTML = haiIconImg('pencil', 'Edit pesan');
            assistantEditButton.onclick = () => handleMessageEdit(assistantMessage, continuedResponse, 'assistant');

            const assistantCopyButton = document.createElement('button');
            assistantCopyButton.className = 'message-copy-button';
            assistantCopyButton.innerHTML = haiIconImg('copy', 'Salin pesan');
            assistantCopyButton.onclick = () => copyToClipboard(continuedResponse, assistantCopyButton);

            const deleteButton = document.createElement('button');
            deleteButton.className = 'message-delete-button';
            deleteButton.innerHTML = haiIconImg('trash', 'Hapus pesan');
            deleteButton.onclick = () => handleMessageDelete(assistantMessage, continuedResponse, 'assistant');

            const continueButton = document.createElement('button');
            continueButton.className = 'message-continue-button';
            continueButton.innerHTML = haiIconImg('continue', 'Lanjutkan jawaban');
            continueButton.onclick = () => handleContinueGeneration(assistantMessage, continuedResponse);

            buttonContainer.appendChild(assistantEditButton);
            buttonContainer.appendChild(assistantCopyButton);
            buttonContainer.appendChild(deleteButton);
            buttonContainer.appendChild(continueButton);
            assistantMessageContainer.appendChild(buttonContainer);

            return;
        }
        console.error('Error sending edited message:', error);
        currentController = null;
        toggleSubmitButtonIcon(false);
        if (streamStartTime) stopStreamTimer();
        const errorResponseText = `Maaf, ${error.message || 'edit pesan gagal. Coba lagi.'}`;
        ensureAssistantErrorBubble(assistantMessageContainer, assistantMessage, errorResponseText);
        setHaiStatus(error.message || 'Edit pesan gagal. Coba lagi.', 'error');
        window.setTimeout(() => setHaiStatus(''), 3200);
        await persistAssistantErrorMessage(messageId, errorResponseText, { intent: turnIntent });
        scrollChatToBottom('smooth');
        return;
    }
}

async function handleRegenerateResponse(button) {
    if (currentController) {
        showToast('Harmonika AI masih menjawab. Klik Stop dulu sebelum regenerate.', 'error');
        return;
    }

    const oldAssistantContainer = button.closest('.assistant-message-container');
    const lastAssistantContainer = [...chatMessages.querySelectorAll('.assistant-message-container')].pop();
    if (!oldAssistantContainer || oldAssistantContainer !== lastAssistantContainer) {
        showToast('Regenerate hanya tersedia untuk jawaban terakhir agar riwayat tetap rapi.', 'error');
        return;
    }

    const lastAssistantIndex = (() => {
        for (let index = conversationHistory.length - 1; index >= 0; index--) {
            if (conversationHistory[index]?.role === 'assistant') return index;
        }
        return -1;
    })();
    if (lastAssistantIndex <= 0) {
        showToast('Belum ada jawaban yang bisa dibuat ulang.', 'error');
        return;
    }

    let userIndex = -1;
    for (let index = lastAssistantIndex - 1; index >= 0; index--) {
        if (conversationHistory[index]?.role === 'user') {
            userIndex = index;
            break;
        }
    }
    if (userIndex < 0) {
        showToast('Prompt sebelumnya tidak ditemukan untuk regenerate.', 'error');
        return;
    }

    const userMessage = conversationHistory[userIndex];
    const baseMessageForAPI = userMessage.raw || userMessage.content?.raw || userMessage.content?.content || userMessage.content;
    const apiConversationHistory = conversationHistory.slice(0, userIndex).map(cleanMessageForAPI).filter(Boolean);
    const requestHistoryBase = conversationHistory.slice(0, userIndex + 1).map(message => ({ ...message }));
    const requestConversationId = currentConversationId;
    const requestStartedInPrivate = isPrivateChat;
    const promptText = userTextForIntent(baseMessageForAPI);
    const messageForAPI = await appendLibraryContextToMessageContent(baseMessageForAPI, promptText);
    let turnIntent = detectHaiIntent(promptText).type;
    let fullResponse = '';
    let imageArtifactRendered = false;
    const messageId = Date.now().toString();

    const assistantMessageContainer = document.createElement('div');
    assistantMessageContainer.className = 'assistant-message-container';
    assistantMessageContainer.dataset.messageId = messageId;
    const assistantMessage = document.createElement('div');
    assistantMessage.classList.add('assistant-message');
    assistantMessageContainer.appendChild(assistantMessage);
        setAssistantWaiting(assistantMessageContainer, assistantMessage, {
            intent: turnIntent,
            label: turnIntent === 'image'
                ? 'Harmonika AI sedang mendesain ulang gambar…'
            : 'Harmonika AI sedang mengetik ulang jawaban…'
    });
    oldAssistantContainer.replaceWith(assistantMessageContainer);
    conversationHistory = [...requestHistoryBase];
    if (!requestStartedInPrivate && requestConversationId && conversations[requestConversationId]) {
        conversations[requestConversationId].messages = [...conversationHistory];
        saveConversationsToStorage();
    }
    scrollChatToBottom('smooth');

    try {
        currentController = new AbortController();
        toggleSubmitButtonIcon(true, turnIntent);
        setHaiStatus(turnIntent === 'image' ? 'Mendesain ulang gambar…' : 'Membuat ulang jawaban…', turnIntent === 'image' ? 'image' : 'info');
        startStreamTimer();

        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: messageForAPI,
                model: selectedModel,
                systemContent: SYSTEM_CONTENT,
                parameters: MODEL_PARAMETERS,
                isNewChat: false,
                conversation: apiConversationHistory,
                isDeepQueryMode: isDeepQueryMode,
                startTag: START_TAG,
                memoryContext: await getHaiMemoryContext(),
                libraryGrounding: haiLibraryGroundingMode,
                libraryContextMode: haiLibraryContextMode
            }),
            signal: currentController.signal
        });

        if (!response.ok || !response.body) {
            let errorMessage = `Harmonika AI belum bisa regenerate. Kode: ${response.status}`;
            try {
                const errorData = await response.json();
                if (errorData?.message) errorMessage = errorData.message;
            } catch (_) {}
            throw new Error(errorMessage);
        }

        const serverIntent = (response.headers.get('X-HAI-Intent') || '').toLowerCase();
        const responseSources = parseHaiSourcesHeader(response.headers.get('X-HAI-Sources'));
        const libraryGrounding = parseHaiLibraryGroundingHeader(response.headers.get('X-HAI-Library-Grounding'));
        if (libraryGrounding.used) {
            const contextLabel = libraryGrounding.contextMode === 'full' ? 'konteks penuh' : 'cuplikan';
            setHaiStatus(`Library dipakai: ${libraryGrounding.count} ${contextLabel} dokumen.`, 'info');
        }
        if (serverIntent === 'image' || serverIntent === 'text') {
            turnIntent = serverIntent;
            setAssistantWaiting(assistantMessageContainer, assistantMessage, {
                intent: turnIntent,
                label: turnIntent === 'image'
                    ? 'Harmonika AI sedang mendesain ulang gambar…'
                    : 'Harmonika AI sedang mengetik ulang jawaban…'
            });
            toggleSubmitButtonIcon(true, turnIntent);
            if (turnIntent === 'text' && responseSources.length) {
                setHaiStatus('Harmonika AI sedang menulis dengan referensi web…', 'info');
            }
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let hasReceivedChunk = false;
        if (isDeepQueryMode) {
            fullResponse += START_TAG;
        }
        if (!assistantMessage.reactRoot) {
            assistantMessage.reactRoot = ReactDOM.createRoot(assistantMessage);
        }

        while (true) {
            const { done, value } = await reader.read();
            if (done) {
                if (turnIntent === 'image' && fullResponse.trim() && !imageArtifactRendered) {
                    renderAssistantMarkdown(assistantMessage, fullResponse, END_TAG, false, true);
                    imageArtifactRendered = true;
                }
                clearAssistantWaiting(assistantMessageContainer);
                currentController = null;
                toggleSubmitButtonIcon(false);
                if (streamStartTime) stopStreamTimer();
                if (!fullResponse.trim()) {
                    fullResponse = 'Maaf, jawaban regenerate kosong. Silakan coba lagi.';
                    setAssistantError(assistantMessage, fullResponse);
                }
                const qualityResponse = normalizeAssistantPublicQualityText(fullResponse);
                if (qualityResponse !== fullResponse) {
                    fullResponse = qualityResponse;
                    renderAssistantMarkdown(assistantMessage, fullResponse, END_TAG, false, true);
                }
                const oneSentenceResponse = trimAssistantToSingleSentenceIfRequested(fullResponse, promptText);
                if (oneSentenceResponse !== fullResponse) {
                    fullResponse = oneSentenceResponse;
                    renderAssistantMarkdown(assistantMessage, fullResponse, END_TAG, false, true);
                }

                const assistantMessageObj = {
                    messageId,
                    role: 'assistant',
                    content: fullResponse,
                    endTag: END_TAG,
                    thinkingTime: streamDuration,
                    sources: responseSources,
                    intent: turnIntent,
                    libraryGrounding
                };
                const finalConversationHistory = [...requestHistoryBase, assistantMessageObj];
                if (currentConversationId === requestConversationId) {
                    conversationHistory = [...finalConversationHistory];
                }
                if (!requestStartedInPrivate && requestConversationId && conversations[requestConversationId]) {
                    conversations[requestConversationId].messages = [...finalConversationHistory];
                    saveConversationsToStorage();
                    updateChatHistory();
                }
                appendAssistantActionButtonsIfMissing(assistantMessageContainer, assistantMessage, fullResponse);
                appendSourceChips(assistantMessageContainer, responseSources);
                enhanceRegenerateButtons(assistantMessageContainer);
                break;
            }

            const chunk = normalizeHaiStreamChunk(decoder.decode(value, { stream: true }));
                if (!chunk) continue;
            const shouldStickToBottom = autoScrollLockedToBottom || isNearChatBottom();
            fullResponse += chunk;
            if (!hasReceivedChunk) {
                hasReceivedChunk = true;
                markAssistantFirstVisibleChunk(assistantMessageContainer, turnIntent, {
                    status: turnIntent === 'image'
                        ? 'imageDesigning'
                        : responseSources.length
                            ? 'webWriting'
                            : 'textWriting',
                    progressStep: 2
                });
            }

            if (streamStartTime && checkForEndTag(fullResponse)) {
                stopStreamTimer();
            }

            if (turnIntent === 'image' && !hasCompleteImageArtifact(fullResponse)) {
                setImageProgressStep(assistantMessageContainer, 3);
                setHaiStatus('Harmonika AI sedang merender ulang gambar…', 'image');
                if (shouldStickToBottom) scrollChatToBottom('auto');
                continue;
            }

            if (turnIntent === 'image' && !imageArtifactRendered) {
                setImageProgressStep(assistantMessageContainer, HAI_IMAGE_STEPS.length - 1);
                clearAssistantWaiting(assistantMessageContainer);
                imageArtifactRendered = true;
                assistantMessageContainer.classList.add('is-done');
                renderAssistantMarkdown(assistantMessage, fullResponse, END_TAG, false, true);
            } else {
                renderAssistantMarkdown(assistantMessage, fullResponse, END_TAG, false);
            }
            if (shouldStickToBottom) scrollChatToBottom('auto');
        }
    } catch (error) {
        if (error.name === 'AbortError') {
            currentController = null;
            toggleSubmitButtonIcon(false);
            clearAssistantWaiting(assistantMessageContainer);
            if (streamStartTime) stopStreamTimer();
            if (turnIntent === 'image' && !imageArtifactRendered) {
                fullResponse = 'Regenerate gambar dihentikan.';
                setAssistantError(assistantMessage, fullResponse);
            } else if (!fullResponse.trim()) {
                fullResponse = 'Regenerate dihentikan.';
                setAssistantError(assistantMessage, fullResponse);
            }
        } else {
            console.error('Error regenerating response:', error);
            currentController = null;
            toggleSubmitButtonIcon(false);
            clearAssistantWaiting(assistantMessageContainer);
            stopStreamTimer();
            fullResponse = `Maaf, ${error.message || 'regenerate gagal. Coba lagi.'}`;
            assistantMessageContainer.dataset.error = 'true';
            setAssistantError(assistantMessage, fullResponse);
            setHaiStatus(error.message || 'Regenerate gagal. Coba lagi.', 'error');
            window.setTimeout(() => setHaiStatus(''), 3200);
        }
        const isErrorResponse = assistantMessageContainer.dataset.error === 'true';
        const stoppedHistory = [...requestHistoryBase, {
            messageId,
            role: 'assistant',
            content: fullResponse || 'Regenerate dihentikan.',
            endTag: END_TAG,
            thinkingTime: streamDuration,
            isError: isErrorResponse,
            intent: turnIntent
        }];
        if (currentConversationId === requestConversationId) conversationHistory = [...stoppedHistory];
        if (!requestStartedInPrivate && requestConversationId && conversations[requestConversationId]) {
            conversations[requestConversationId].messages = [...stoppedHistory];
            saveConversationsToStorage();
        }
        appendAssistantActionButtonsIfMissing(assistantMessageContainer, assistantMessage, fullResponse || 'Regenerate dihentikan.');
        enhanceRegenerateButtons(assistantMessageContainer);
    }
}

// Continue generation handler
async function handleContinueGeneration(messageDiv, previousResponse) {
    if (currentController) {
        showToast('Harmonika AI masih menjawab. Klik Stop dulu sebelum melanjutkan jawaban.', 'error');
        return;
    }
    const assistantMessageContainer = messageDiv.closest('.assistant-message-container');
    const buttonContainer = assistantMessageContainer?.querySelector('.message-buttons');
    if (!assistantMessageContainer || !buttonContainer) {
        showToast('Kontrol jawaban tidak ditemukan. Muat ulang chat lalu coba lagi.', 'error');
        return;
    }
    
    // Get the current expanded state and previous duration before continuing
    const messageIndex = findMessageIndex(previousResponse, 'assistant');
    const currentMessage = conversationHistory[messageIndex];
    const currentExpandedState = currentMessage && typeof currentMessage.content === 'object' ? 
        currentMessage.content.reasoningExpanded : false;
    
    // Get previous thinking time from the message history
    const previousThinkingTime = currentMessage?.thinkingTime || 0;
    
    // Set streamDuration to the previous duration to continue accumulating
    streamDuration = previousThinkingTime;
    
    // Disable the continue button while generating
    const continueButton = buttonContainer.querySelector('.message-continue-button');
    if (!continueButton) {
        showToast('Tombol lanjutkan belum tersedia untuk jawaban ini.', 'error');
        return;
    }
    continueButton.style.opacity = '0.5';
    continueButton.style.pointerEvents = 'none';
    
    try {
        currentController = new AbortController();
        toggleSubmitButtonIcon(true);
        
        // Start timer to continue accumulating from previous duration
        startStreamTimer();
        
        // Clean conversation history for API
        const apiConversationHistory = conversationHistory.map(cleanMessageForAPI).filter(Boolean);

        // Check if we should generate a title
        const shouldGenerateTitle = !isPrivateChat && 
            currentConversationId && 
            (!conversations[currentConversationId].title || conversationHistory.length <= 2);
        
        const response = await fetch('/continue_generation', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                conversation: apiConversationHistory,
                model: selectedModel,
                systemContent: SYSTEM_CONTENT,
                parameters: MODEL_PARAMETERS,
                memoryContext: await getHaiMemoryContext(),
                libraryGrounding: haiLibraryGroundingMode,
                libraryContextMode: haiLibraryContextMode
            }),
            signal: currentController.signal
        });

        if (!response.ok || !response.body) {
            let errorMessage = `Harmonika AI belum bisa melanjutkan. Kode: ${response.status}`;
            try {
                const errorData = await response.json();
                if (errorData?.message) errorMessage = errorData.message;
            } catch (_) {}
            throw new Error(errorMessage);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let continuedResponse = previousResponse;
        
        // Prepend START_TAG to response when in deep query mode
        if (isDeepQueryMode && continuedResponse === previousResponse) {
            continuedResponse = START_TAG + previousResponse;
        }

        // Create or get React root for the message
        if (!messageDiv.reactRoot) {
            messageDiv.reactRoot = ReactDOM.createRoot(messageDiv);
        }

        while (true) {
            try {
                const { done, value } = await reader.read();
                if (done) {
                    currentController = null;
                    toggleSubmitButtonIcon(false);
                    
                    // Only stop timer if it hasn't been stopped by end tag detection
                    if (streamStartTime) {
                        const duration = stopStreamTimer();
                        console.log(`Stream completed in ${duration}ms`);
                    }
                    
                    // Update message in conversation history with new duration
                    if (messageIndex !== -1) {
                        conversationHistory[messageIndex] = {
                            ...currentMessage,
                            content: {
                                raw: continuedResponse,
                                reasoningExpanded: currentExpandedState
                            },
                            thinkingTime: streamDuration
                        };
                    }
                    
                    // Generate title if needed
                    if (shouldGenerateTitle) {
                        try {
                            const titleResponse = await fetch('/generate-title', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json'
                                },
                                body: JSON.stringify({
                                    message: conversationHistory[0]?.content || '',
                                    model: selectedModel,
                                    assistantResponse: continuedResponse.slice(0, 500)
                                })
                            });
                            
                            const titleData = await titleResponse.json();
                            if (titleData.title) {
                                conversations[currentConversationId].title = cleanConversationTitle(titleData.title);
                                syncTopbarTitle();
                            }
                        } catch (error) {
                            console.error('Error generating title:', error);
                        }
                    }
                    
                    // Update buttons with new content
                    const editButton = buttonContainer.querySelector('.message-edit-button');
                    const copyButton = buttonContainer.querySelector('.message-copy-button');
                    const deleteButton = buttonContainer.querySelector('.message-delete-button');
                    
                    editButton.onclick = () => handleMessageEdit(messageDiv, continuedResponse, 'assistant');
                    copyButton.onclick = () => copyToClipboard(continuedResponse, copyButton);
                    deleteButton.onclick = () => handleMessageDelete(messageDiv, continuedResponse, 'assistant');
                    continueButton.onclick = () => handleContinueGeneration(messageDiv, continuedResponse);
                    
                    // Save to conversation history
                    if (messageIndex !== -1) {
                        conversationHistory[messageIndex] = {
                            ...currentMessage,
                            content: {
                                raw: continuedResponse,
                                reasoningExpanded: currentExpandedState
                            }
                        };
                    } else if (conversationHistory.length > 0 && conversationHistory[conversationHistory.length - 1].role === "assistant") {
                        conversationHistory[conversationHistory.length - 1].content = {
                            raw: continuedResponse,
                            reasoningExpanded: currentExpandedState
                        };
                    } else {
                        conversationHistory.push({
                            role: "assistant",
                            content: {
                                raw: continuedResponse,
                                reasoningExpanded: currentExpandedState
                            }
                        });
                    }
                    
                    // Save to storage if not in private chat
                    if (!isPrivateChat && currentConversationId) {
                        conversations[currentConversationId].messages = [...conversationHistory];
                        await saveConversationsToStorage();
                        updateChatHistory(); // Update UI to reflect any title changes
                    }
                    
                    // Re-enable continue button
                    continueButton.style.opacity = '1';
                    continueButton.style.pointerEvents = 'auto';
                    break;
                }

                const chunk = normalizeHaiStreamChunk(decoder.decode(value, { stream: true }));
                if (!chunk) continue;
                continuedResponse += chunk;
                
                // Check if this chunk contains the end tag
                if (streamStartTime && checkForEndTag(continuedResponse)) {
                    const duration = stopStreamTimer();
                    console.log(`End tag detected. Thinking completed in ${duration}ms`);
                }
                
                // Update React component with new content, batched per animation frame
                renderAssistantMarkdown(messageDiv, continuedResponse, currentMessage?.endTag || END_TAG, currentExpandedState);

                if (messageDiv.querySelector('.think-block') && !hasScrolledForThinkBlock) {
                    hasScrolledForThinkBlock = true;
                    chatWrapper.scrollTo({
                        top: chatWrapper.scrollHeight,
                        behavior: 'smooth'
                    });
                }

            } catch (error) {
                if (error.name === 'AbortError') {
                    console.log('Stream aborted by user');
                    currentController = null;
                    toggleSubmitButtonIcon(false);
                    
                    // Update buttons with partial content
                    const editButton = buttonContainer.querySelector('.message-edit-button');
                    const copyButton = buttonContainer.querySelector('.message-copy-button');
                    const deleteButton = buttonContainer.querySelector('.message-delete-button');
                    
                    editButton.onclick = () => handleMessageEdit(messageDiv, continuedResponse, 'assistant');
                    copyButton.onclick = () => copyToClipboard(continuedResponse, copyButton);
                    deleteButton.onclick = () => handleMessageDelete(messageDiv, continuedResponse, 'assistant');
                    continueButton.onclick = () => handleContinueGeneration(messageDiv, continuedResponse);
                    
                    // Update React component with partial content
                    renderAssistantMarkdown(messageDiv, continuedResponse, currentMessage?.endTag || END_TAG, currentExpandedState, true);
                    
                    // Save partial response to conversation history
                    if (messageIndex !== -1) {
                        conversationHistory[messageIndex] = {
                            ...currentMessage,
                            content: {
                                raw: continuedResponse,
                                reasoningExpanded: currentExpandedState
                            }
                        };
                    } else if (conversationHistory.length > 0 && conversationHistory[conversationHistory.length - 1].role === "assistant") {
                        conversationHistory[conversationHistory.length - 1].content = {
                            raw: continuedResponse,
                            reasoningExpanded: currentExpandedState
                        };
                    } else {
                        conversationHistory.push({
                            role: "assistant",
                            content: {
                                raw: continuedResponse,
                                reasoningExpanded: currentExpandedState
                            }
                        });
                    }
                    
                    // Save to storage if not in private chat
                    if (!isPrivateChat && currentConversationId) {
                        conversations[currentConversationId].messages = [...conversationHistory];
                        await saveConversationsToStorage();
                    }
                    
                    // Re-enable continue button
                    continueButton.style.opacity = '1';
                    continueButton.style.pointerEvents = 'auto';
                    return;
                }
                throw error;
            }
        }
    } catch (error) {
        if (error.name === 'AbortError') {
            console.log('Continue request aborted by user');
            currentController = null;
            toggleSubmitButtonIcon(false);
            if (streamStartTime) stopStreamTimer();
            continueButton.style.opacity = '1';
            continueButton.style.pointerEvents = 'auto';
            setHaiStatus('Jawaban dihentikan.', 'stopping');
            window.setTimeout(() => setHaiStatus(''), 1800);
            return;
        }
        console.error('Error:', error);
        currentController = null;
        toggleSubmitButtonIcon(false);
        if (streamStartTime) stopStreamTimer();
        continueButton.style.opacity = '1';
        continueButton.style.pointerEvents = 'auto';
        const errorMessage = `Maaf, ${error.message || 'jawaban belum bisa dilanjutkan. Coba lagi.'}`;
        const errorMessageId = Date.now().toString();
        const errorContainer = document.createElement('div');
        errorContainer.className = 'assistant-message-container';
        errorContainer.dataset.messageId = errorMessageId;
        errorContainer.dataset.error = 'true';
        const errorDiv = document.createElement('div');
        errorDiv.classList.add('assistant-message');
        errorContainer.appendChild(errorDiv);
        assistantMessageContainer.after(errorContainer);
        ensureAssistantErrorBubble(errorContainer, errorDiv, errorMessage);
        setHaiStatus(error.message || 'Lanjutkan jawaban gagal. Coba lagi.', 'error');
        window.setTimeout(() => setHaiStatus(''), 3200);
        await persistAssistantErrorMessage(errorMessageId, errorMessage);
        scrollChatToBottom('smooth');
    }
}

function openAdditionalPopup() {
    const popup = document.getElementById('additional-settings-popup');
    popup.style.display = 'flex';
    popup.setAttribute('aria-hidden', 'false');
}

function closeAdditionalPopup() {
    const popup = document.getElementById('additional-settings-popup');
    popup.style.display = 'none';
    popup.setAttribute('aria-hidden', 'true');
}

// User settings popup close function
document.addEventListener('click', function(event) {
    if (!event.target.closest('.popup-content') && 
        !event.target.closest('#user-setting') && 
        !event.target.closest('#additional-setting')) {
        settingsPopup.style.display = 'none';
        settingsPopup.setAttribute('aria-hidden', 'true');
        const additionalPopup = document.getElementById('additional-settings-popup');
        additionalPopup.style.display = 'none';
        additionalPopup.setAttribute('aria-hidden', 'true');
    }
});

// Load additional settings
async function loadAdditionalSettings() {
    try {
        const systemContentRecord = await db.settings.get('systemContent');
        const parametersRecord = await db.settings.get('modelParameters');
        const modeRecord = await db.settings.get('parameterMode');
        const startTagRecord = await db.settings.get('startTag');
        const endTagRecord = await db.settings.get('endTag');
        
        const savedSystemContent = systemContentRecord?.value || '';
        const savedParameters = parametersRecord?.value || '';
        const savedMode = modeRecord?.value || 'balanced';
        const savedStartTag = (startTagRecord?.value || '<think>').trim();
        const savedEndTag = endTagRecord?.value || '</think>';
        
        document.getElementById('system-content').value = savedSystemContent;
        document.getElementById('model-parameters').value = savedParameters;
        document.getElementById('start-tag').value = savedStartTag;
        document.getElementById('end-tag').value = savedEndTag;
        
        SYSTEM_CONTENT = savedSystemContent;
        START_TAG = savedStartTag;
        END_TAG = savedEndTag;
        
        const buttons = document.querySelectorAll('.parameter-button');
        buttons.forEach(button => {
            button.classList.remove('active');
            if (button.dataset.mode === savedMode) {
                button.classList.add('active');
            }
        });
        
        const parametersField = document.getElementById('model-parameters');
        parametersField.style.display = savedMode === 'custom' ? 'block' : 'none';
        
        if (savedMode === 'custom') {
            MODEL_PARAMETERS = parseParameters(savedParameters);
        } else {
            MODEL_PARAMETERS = PARAMETER_PRESETS[savedMode];
        }
    } catch (error) {
        console.error('Error loading additional settings:', error);
    }
}

function parseParameters(paramString) {
    const params = {};
    if (!paramString) return params;

    paramString.split(',').forEach(pair => {
        const [key, value] = pair.trim().split('=');
        if (key && value) {
            // Convert string value to number if possible
            params[key.trim()] = isNaN(value) ? value : Number(value);
        }
    });
    return params;
}

async function saveAdditionalSettings() {
    try {
        const systemContent = document.getElementById('system-content').value;
        const parameters = document.getElementById('model-parameters').value;
        const startTag = document.getElementById('start-tag').value;
        const endTag = document.getElementById('end-tag').value;
        const activeButton = document.querySelector('.parameter-button.active');
        const mode = activeButton ? activeButton.dataset.mode : 'balanced';
        
        await db.settings.put({ key: 'systemContent', value: systemContent });
        await db.settings.put({ key: 'modelParameters', value: parameters });
        await db.settings.put({ key: 'parameterMode', value: mode });
        await db.settings.put({ key: 'startTag', value: startTag });
        await db.settings.put({ key: 'endTag', value: endTag });
        
        SYSTEM_CONTENT = systemContent;
        START_TAG = startTag;
        END_TAG = endTag;
        
        if (mode === 'custom') {
            MODEL_PARAMETERS = parseParameters(parameters);
        } else {
            MODEL_PARAMETERS = PARAMETER_PRESETS[mode];
        }
        
        closeAdditionalPopup();
        userInput.focus();
    } catch (error) {
        console.error('Error saving additional settings:', error);
    }
}

// Event listeners for parameter buttons
document.addEventListener('DOMContentLoaded', function() {
    const buttons = document.querySelectorAll('.parameter-button');
    const parametersField = document.getElementById('model-parameters');
    
    buttons.forEach(button => {
        button.addEventListener('click', function() {
            // Remove active class from all buttons
            buttons.forEach(btn => btn.classList.remove('active'));
            // Add active class to clicked button
            this.classList.add('active');
            
            const mode = this.dataset.mode;
            
            // Show/hide custom parameters field
            parametersField.style.display = mode === 'custom' ? 'block' : 'none';
            
            // Update parameters based on mode
            if (mode !== 'custom') {
                MODEL_PARAMETERS = PARAMETER_PRESETS[mode];
                localStorage.setItem('parameterMode', mode);
            }
        });
    });
});

// Export as markdown function
function exportMarkdown() {
    if (!currentConversationId && !isPrivateChat) {
        return; // No chat to export
    }

    // Get current timestamp for filename
    const date = new Date();
    const timestamp = date.toISOString().replace(/[:.]/g, '-');
    
    // Prepare chat content
    let chatContent = '';
    
    // Add metadata
    chatContent += '# Ekspor Chat\n\n';
    chatContent += '## Metadata\n\n';
    chatContent += `- Tanggal: ${date.toISOString()}\n`;
    chatContent += `- Model: ${selectedModel || 'Tidak ditentukan'}\n`;
    chatContent += `- Prompt sistem: ${SYSTEM_CONTENT || 'Tidak ada'}\n`;
    chatContent += `- Parameter: ${JSON.stringify(MODEL_PARAMETERS, null, 2).replace(/[{}"]/g, '').replace(/,\n/g, '\n').split('\n').map(line => '  ' + line).join('\n')}\n\n`;
    
    // Add messages header
    chatContent += '## Pesan\n\n';
    
    // Add messages
    const roleLabel = (role = '') => ({
        user: 'Pengguna',
        assistant: 'Harmonika AI',
        system: 'Sistem'
    }[String(role).toLowerCase()] || role);
    conversationHistory.forEach(msg => {
        const role = roleLabel(msg.role);
        const content = plainTextFromMessageContent(msg.content, msg);
        chatContent += `### ${role}\n\n${content}\n\n`;
    });
    
    // Create blob and download
    const blob = new Blob([chatContent], { type: 'text/markdown' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ekspor-chat-${timestamp}.md`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
}

// Export as JSON function
function exportJSON() {
    if (!currentConversationId && !isPrivateChat) {
        return; // No chat to export
    }

    // Get current timestamp for filename
    const date = new Date();
    const timestamp = date.toISOString().replace(/[:.]/g, '-');
    
    // Clean messages for export by removing endTag and thinkingTime
    const cleanMessages = conversationHistory.map(msg => {
        const { endTag, thinkingTime, ...cleanMessage } = msg;
        return cleanMessage;
    });
    
    // Prepare chat content
    const exportData = {
        metadata: {
            tanggal: date.toISOString(),
            model: selectedModel || 'Tidak ditentukan',
            prompt_sistem: SYSTEM_CONTENT || 'Tidak ada',
            parameter: MODEL_PARAMETERS
        },
        pesan: cleanMessages
    };
    
    // Create blob and download
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ekspor-chat-${timestamp}.json`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
}

// Export button event listeners
document.getElementById('export-markdown').addEventListener('click', exportMarkdown);
document.getElementById('export-json').addEventListener('click', exportJSON);

// Functions for file parsing
async function parsePDF(file) {
    const arrayBuffer = await file.arrayBuffer();
    const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
    let content = '';
    
    for (let i = 1; i <= pdf.numPages; i++) {
        const page = await pdf.getPage(i);
        const textContent = await page.getTextContent();
        content += textContent.items.map(item => item.str).join(' ') + '\n';
    }
    
    return content.trim();
}

async function parseDocx(arrayBuffer) {
    try {
        const result = await mammoth.extractRawText({ arrayBuffer });
        return result.value;
    } catch (error) {
        console.error('Error parsing DOCX:', error);
        throw error;
    }
}

async function parseDocumentOnServer(file) {
    const form = new FormData();
    form.append('file', file, file.name || 'attachment');
    const response = await fetch('/api/attachments/parse', {
        method: 'POST',
        body: form,
        credentials: 'same-origin'
    });
    let payload = null;
    try {
        payload = await response.json();
    } catch (_) {}
    if (!response.ok || !payload?.ok) {
        throw new Error(payload?.message || payload?.error || `Gagal membaca file (${response.status})`);
    }
    return String(payload.file?.text || '').trim();
}

function parseTxt(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target.result);
        reader.onerror = (e) => reject(e.target.error);
        reader.readAsText(file);
    });
}

// Click handler for upload button
uploadFiles.addEventListener('click', () => {
    fileInput.click();
});

haiLibraryUploadButton?.addEventListener('click', () => {
    libraryFileInput.click();
});

libraryFileInput.addEventListener('change', async (event) => {
    const file = event.target?.files?.[0];
    if (file) {
        await uploadLibraryDocument(file);
    }
    event.target.value = '';
});

haiLibraryGroundingToggle?.addEventListener('click', cycleLibraryGroundingMode);
haiLibraryContextToggle?.addEventListener('click', cycleLibraryContextMode);

haiLibrarySearch?.addEventListener('input', () => {
    scheduleLibraryPanelSearch();
});

// Function to toggle upload button loading state
function toggleUploadButtonIcon(isProcessing) {
    if (isProcessing) {
        uploadFiles.innerHTML = '<i class="fa fa-spinner fa-spin fa-inverse"></i>';
        uploadFiles.disabled = true;
    } else {
        uploadFiles.innerHTML = '<i class="fa fa-paperclip fa-inverse"></i>';
        uploadFiles.disabled = false;
    }
}

// File select function
async function handleFileSelect(event) {
    const incomingFiles = Array.from(event.target?.files || event.dataTransfer?.files || []);
    if (!incomingFiles.length) return;

    const remainingSlots = Math.max(0, HAI_MAX_ATTACHMENTS - pendingAttachments.length);
    if (!remainingSlots) {
        showToast(`Maksimum ${HAI_MAX_ATTACHMENTS} lampiran per pesan.`, 'error');
        if (event.target) event.target.value = '';
        return;
    }
    if (incomingFiles.length > remainingSlots) {
        showToast(`Hanya ${remainingSlots} lampiran lagi yang bisa ditambahkan.`, 'info');
    }

    const files = incomingFiles.slice(0, remainingSlots);
    const beforeCount = pendingAttachments.length;
    try {
        toggleUploadButtonIcon(true);
        for (const file of files) {
            if (file.size > HAI_MAX_ATTACHMENT_BYTES) {
                showToast(`${file.name}: ukuran file maksimal 10 MB.`, 'error');
                continue;
            }

            if (isSupportedImageFile(file)) {
                await handleImageFile(file, { append: true });
                continue;
            }

            if (!isSupportedDocumentFile(file)) {
                showToast(`${file.name}: format belum didukung. Gunakan PDF, TXT, CSV, DOCX, XLSX, PNG, JPEG, atau WebP.`, 'error');
                continue;
            }

            showAttachmentProcessing(file);
            const content = await parseDocumentOnServer(file);
            addPendingAttachment({
                type: 'document',
                name: file.name,
                sizeLabel: formatFileSize(file.size),
                mime: file.type || 'document',
                content
            });
        }
        const addedCount = pendingAttachments.length - beforeCount;
        if (addedCount > 1) {
            showToast(`${addedCount} lampiran siap dikirim.`, 'success');
        }
        userInput.focus();
    } catch (error) {
        console.error('Error handling file:', error);
        showToast(error.message || 'Gagal memproses file. Silakan coba lagi.', 'error');
        renderPendingAttachments();
    } finally {
        toggleUploadButtonIcon(false);
        renderPendingAttachments();
        if (event.target) event.target.value = '';
    }
}

// Handle file drop function
async function handleFileDrop(event) {
    event.preventDefault();
    attachmentDragDepth = 0;
    dropZone.classList.remove('drag-over');
    await handleFileSelect(event);
}

// Function to toggle file content visibility
function toggleFileContent(fileIndicator) {
    const existingContent = fileIndicator.querySelector('.file-content');
    
    if (existingContent) {
        existingContent.remove();
        return;
    }
    
    const content = fileIndicator.dataset.content;
    const contentDiv = document.createElement('div');
    contentDiv.className = 'file-content';
    contentDiv.textContent = content;
    
    fileIndicator.appendChild(contentDiv);
}

// Drag and drop event listeners
dropZone.addEventListener('dragenter', (e) => {
    e.preventDefault();
    attachmentDragDepth += 1;
    dropZone.classList.add('drag-over');
});

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
});

dropZone.addEventListener('dragleave', (e) => {
    e.preventDefault();
    attachmentDragDepth = Math.max(0, attachmentDragDepth - 1);
    if (attachmentDragDepth === 0 || !dropZone.contains(e.relatedTarget)) {
        attachmentDragDepth = 0;
        dropZone.classList.remove('drag-over');
    }
});

dropZone.addEventListener('drop', handleFileDrop);

// New function to handle message deletion
function handleMessageDelete(messageDiv, content, role) {
    if (currentController) {
        showToast('Harmonika AI masih menjawab. Klik Stop dulu sebelum menghapus pesan.', 'error');
        return;
    }
    const confirmLabel = role === 'assistant'
        ? 'Hapus jawaban ini dari riwayat chat?'
        : 'Hapus pesan ini dari riwayat chat?';
    if (!window.confirm(confirmLabel)) {
        return;
    }
    const messageContainer = messageDiv.closest(`.${role}-message-container`);
    
    // Find the index of this message in the conversation
    const messageIndex = findMessageIndex(content, role);
    
    if (messageIndex !== -1) {
        // Remove the message from conversation history
        conversationHistory.splice(messageIndex, 1);
        
        // If not in private chat mode, update the conversations object and save to storage
        if (!isPrivateChat && currentConversationId) {
            conversations[currentConversationId].messages = [...conversationHistory];
            saveConversationsToStorage();
        }
    }
    
    // Remove all messages after this one from the UI and conversation history
    clearMessagesAfter(messageContainer);
    if (messageIndex !== -1) {
        conversationHistory = conversationHistory.slice(0, messageIndex);
        
        // Update storage if not in private mode
        if (!isPrivateChat && currentConversationId) {
            conversations[currentConversationId].messages = [...conversationHistory];
            saveConversationsToStorage();
        }
    }
    
    // Remove this message from the UI
    messageContainer.remove();
}

// Function to handle image files
async function handleImageFile(file, options = {}) {
    try {
        // Show loading state
        if (!options.append) toggleUploadButtonIcon(true);
        showAttachmentProcessing(file);
        
        // Compress image if needed
        const compressedImage = await compressImage(file);
        const base64Image = await convertImageToBase64(compressedImage);
        const added = addPendingAttachment({
            type: 'image',
            name: file.name,
            sizeLabel: formatFileSize(compressedImage.size),
            mime: compressedImage.type || file.type || 'image',
            base64: base64Image
        });
        if (!added) renderPendingAttachments();

        // Focus the input field
        userInput.focus();

    } catch (error) {
        console.error('Error handling image:', error);
        renderPendingAttachments();
        showToast('Gagal memproses gambar. Silakan coba lagi.', 'error');
    } finally {
        if (!options.append) toggleUploadButtonIcon(false);
    }
}

// Function to convert image to base64
function convertImageToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = error => reject(error);
        reader.readAsDataURL(file);
    });
}

// File input event listener
fileInput.addEventListener('change', handleFileSelect);

document.addEventListener('click', event => {
    const promptButton = event.target.closest?.('[data-hai-prompt]');
    if (!promptButton) return;
    applyHaiPrompt(promptButton.getAttribute('data-hai-prompt') || '', promptButton.getAttribute('data-hai-intent') || 'text');
});


// Deep query toggle function
function toggleDeepQuery() {
    isDeepQueryMode = !isDeepQueryMode;
    const deepQueryButton = document.getElementById('deep-query');
    const icon = deepQueryButton.querySelector('i');
    
    if (isDeepQueryMode) {
        icon.style.color = '#55cc55';
        userInput.placeholder = "Tulis pertanyaan mendalam…";
        deepQueryButton.classList.add('active'); // Add active class
    } else {
        icon.style.color = ''; // Reset to default color
        userInput.placeholder = "Tanya Harmonika AI…";
        deepQueryButton.classList.remove('active'); // Remove active class
    }

    userInput.focus();
}

// Event listener for deep query button
document.getElementById('deep-query').addEventListener('click', toggleDeepQuery);

// Event listener for paste
document.addEventListener('paste', handlePaste);

// Function to handle paste events
async function handlePaste(event) {
    // Get clipboard items
    const items = event.clipboardData?.items;
    if (!items) return;

    // Look for image items
    for (const item of items) {
        if (item.type.startsWith('image/')) {
            event.preventDefault();
            
            // Convert clipboard item to file
            const file = item.getAsFile();
            if (!file) continue;
            if (pendingAttachments.length >= HAI_MAX_ATTACHMENTS) {
                showToast(`Maksimum ${HAI_MAX_ATTACHMENTS} lampiran per pesan.`, 'error');
                break;
            }

            // Generate a filename for the pasted image
            const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
            const filename = `pasted-image-${timestamp}.png`;
            
            // Create a new file with the custom filename
            const renamedFile = new File([file], filename, { type: file.type });
            
            // Handle the image file
            await handleImageFile(renamedFile);
            break;
        }
    }
}

// Function to compress images
async function compressImage(file) {
    return new Promise((resolve, reject) => {
        // Browser vision requests are sent inline as base64 JSON, so the
        // transmitted body grows ~33%. Keep image payloads well below the
        // public upload limit to avoid 413 errors on normal phone photos.
        const maxSizeBytes = HAI_INLINE_IMAGE_TARGET_BYTES;
        if (file.size <= maxSizeBytes) {
            resolve(file);
            return;
        }
        
        const img = new Image();
        img.src = URL.createObjectURL(file);
        
        img.onload = async () => {
            URL.revokeObjectURL(img.src);
            
            // Initial compression settings
            let currentQuality = 0.86;
            let currentMaxDimension = 1600;
            let compressedFile = null;
            let attempts = 0;
            const maxAttempts = 8;
            
            while (attempts < maxAttempts) {
                attempts++;
                
                // Calculate dimensions
                let width = img.width;
                let height = img.height;
                
                if (width > currentMaxDimension || height > currentMaxDimension) {
                    if (width > height) {
                        height = Math.round((height / width) * currentMaxDimension);
                        width = currentMaxDimension;
                    } else {
                        width = Math.round((width / height) * currentMaxDimension);
                        height = currentMaxDimension;
                    }
                }
                
                // Create canvas
                const canvas = document.createElement('canvas');
                canvas.width = width;
                canvas.height = height;
                
                const ctx = canvas.getContext('2d');
                
                // Use better quality rendering
                ctx.imageSmoothingEnabled = true;
                ctx.imageSmoothingQuality = 'high';
                
                // Set white background
                ctx.fillStyle = 'white';
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                
                // Draw image
                ctx.drawImage(img, 0, 0, width, height);
                
                // Convert to blob
                const blob = await new Promise(resolve => {
                    canvas.toBlob(
                        blob => resolve(blob),
                        'image/jpeg',
                        currentQuality
                    );
                });
                
                if (!blob) {
                    reject(new Error('Failed to compress image'));
                    return;
                }
                
                // Create file from blob
                compressedFile = new File([blob], file.name, {
                    type: 'image/jpeg',
                    lastModified: Date.now()
                });
                
                // Check if we're under the size limit
                if (compressedFile.size <= maxSizeBytes) {
                    break;
                }
                
                // Adjust parameters for next attempt
                if (currentQuality > 0.6) {
                    // First reduce quality
                    currentQuality -= 0.1;
                } else {
                    // Then reduce dimensions
                    currentMaxDimension = Math.round(currentMaxDimension * 0.8);
                    // Reset quality for the new dimension
                    currentQuality = Math.min(0.9, currentQuality + 0.2);
                }
            }
            
            if (compressedFile) {
                resolve(compressedFile);
            } else {
                reject(new Error('Failed to compress image'));
            }
        };
        
        img.onerror = () => reject(new Error('Failed to load image'));
    });
}

// Add this function to update the toggle state of a message
async function updateMessageToggleState(messageId, expanded) {
    // Find the message in conversation history
    const messageIndex = conversationHistory.findIndex(msg => msg.messageId === messageId);
    if (messageIndex !== -1 && conversationHistory[messageIndex].role === 'assistant') {
        // Update the message object to store both content and state
        const message = conversationHistory[messageIndex];
        conversationHistory[messageIndex] = {
            ...message,
            content: {
                raw: typeof message.content === 'object' ? message.content.raw : message.content,
                reasoningExpanded: expanded
            }
        };

        // If not in private mode, update storage
        if (!isPrivateChat && currentConversationId) {
            conversations[currentConversationId].messages = [...conversationHistory];
            await saveConversationsToStorage();
        }
    }
}

// Update the toggleThinkBlock function to use messageId
function toggleThinkBlock(button) {
    const contentDiv = button.nextElementSibling;
    const thinkBlock = button.closest('.think-block');
    const messageContainer = button.closest('.assistant-message-container');
    const messageId = messageContainer?.dataset.messageId;
    const icon = button.querySelector('i');

    if (contentDiv.style.display === 'none' || contentDiv.style.display === '') {
        contentDiv.style.display = 'block';
        icon.classList.remove('fa-chevron-down');
        icon.classList.add('fa-chevron-up');
        if (messageId) {
            updateMessageToggleState(messageId, true);
        }
    } else {
        contentDiv.style.display = 'none';
        icon.classList.remove('fa-chevron-up');
        icon.classList.add('fa-chevron-down');
        if (messageId) {
            updateMessageToggleState(messageId, false);
        }
    }
}

function renderMessage(message) {
    const raw = messageContentRaw(message?.content);
    return React.createElement(MarkdownContent, {
        content: typeof message?.content === 'object' ? {
            ...message.content,
            allowImageArtifacts: Boolean(message.content.allowImageArtifacts) || shouldAllowImageArtifacts(raw, message.intent)
        } : {
            raw,
            reasoningExpanded: false,
            allowImageArtifacts: shouldAllowImageArtifacts(raw, message?.intent)
        },
        messageEndTag: message.endTag
    });
}

window.addEventListener('pagehide', () => {
    if (!isPrivateChat && Object.keys(conversations).length > 0) {
        const payload = JSON.stringify(serverHistoryPayload({ stripImages: true }));
        if (navigator.sendBeacon) {
            const blob = new Blob([payload], { type: 'application/json' });
            navigator.sendBeacon('/api/history', blob);
        } else {
            fetch('/api/history', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: payload,
                keepalive: true
            }).catch(() => {});
        }
    }
});
