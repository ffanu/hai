(function () {
    const state = document.getElementById('hai-admin-state');
    const dot = document.getElementById('hai-admin-state-dot');
    const refresh = document.getElementById('hai-admin-refresh');
    const updated = document.getElementById('hai-admin-updated');

    const nodes = {
        chats: document.getElementById('hai-admin-chats'),
        historyDetail: document.getElementById('hai-admin-history-detail'),
        documents: document.getElementById('hai-admin-documents'),
        libraryDetail: document.getElementById('hai-admin-library-detail'),
        realtime: document.getElementById('hai-admin-realtime'),
        realtimeDetail: document.getElementById('hai-admin-realtime-detail'),
        ratelimit: document.getElementById('hai-admin-ratelimit'),
        ratelimitDetail: document.getElementById('hai-admin-ratelimit-detail'),
        usage: document.getElementById('hai-admin-usage'),
        usageDetail: document.getElementById('hai-admin-usage-detail'),
        privacy: document.getElementById('hai-admin-privacy'),
        storage: document.getElementById('hai-admin-storage'),
        analytics: document.getElementById('hai-admin-analytics')
    };

    function setState(text, tone) {
        if (state) state.textContent = text;
        if (dot) dot.dataset.tone = tone || 'loading';
    }

    function number(value) {
        const numeric = Number(value || 0);
        return new Intl.NumberFormat('id-ID').format(Number.isFinite(numeric) ? numeric : 0);
    }

    function bytes(value) {
        const numeric = Number(value || 0);
        if (!Number.isFinite(numeric) || numeric <= 0) return '0 B';
        const units = ['B', 'KB', 'MB', 'GB'];
        let size = numeric;
        let unit = 0;
        while (size >= 1024 && unit < units.length - 1) {
            size /= 1024;
            unit += 1;
        }
        return `${size >= 10 || unit === 0 ? size.toFixed(0) : size.toFixed(1)} ${units[unit]}`;
    }

    function setText(node, value) {
        if (node) node.textContent = value;
    }

    function renderPrivacy(privacy) {
        const flags = [
            ['aggregate_only', 'Aggregate only'],
            ['no_chat_content', 'Tidak menampilkan isi chat'],
            ['no_document_text', 'Tidak menampilkan teks dokumen'],
            ['no_device_ids', 'Tidak menampilkan device ID'],
            ['no_secrets', 'Tidak menampilkan secret/token']
        ];
        if (!nodes.privacy) return;
        nodes.privacy.innerHTML = flags.map(([key, label]) => {
            const ok = Boolean(privacy && privacy[key]);
            return `<li class="${ok ? 'is-ok' : 'is-warn'}"><span>${ok ? '✓' : '!'}</span>${label}</li>`;
        }).join('');
    }

    function renderStorage(storage) {
        if (!nodes.storage) return;
        const rows = [
            ['History file', bytes(storage?.history_file_bytes)],
            ['Library file', bytes(storage?.library_file_bytes)],
            ['Rate limit file', bytes(storage?.rate_limit_file_bytes)],
            ['Realtime event files', number(storage?.realtime_event_files)]
        ];
        nodes.storage.innerHTML = rows
            .map(([label, value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`)
            .join('');
    }

    function renderAnalytics(analytics) {
        if (!nodes.analytics) return;
        const rows = [
            ['Chat aktif 24 jam', number(analytics?.active_chats_24h)],
            ['Chat aktif 7 hari', number(analytics?.active_chats_7d)],
            ['Pesan pengguna', number(analytics?.user_messages)],
            ['Pesan AI', number(analytics?.assistant_messages)],
            ['Lampiran', number(analytics?.attachment_messages)],
            ['Artifact gambar', number(analytics?.image_artifacts)],
            ['Referensi sumber', number(analytics?.source_references)],
            ['Rata-rata pesan/chat', number(analytics?.avg_messages_per_chat)]
        ];
        nodes.analytics.innerHTML = rows
            .map(([label, value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`)
            .join('');
    }

    function render(payload) {
        const history = payload.history || {};
        const library = payload.library || {};
        const realtime = payload.realtime || {};
        const rateLimit = payload.rate_limit || {};
        const analytics = payload.analytics || {};

        setText(nodes.chats, number(history.chats));
        setText(nodes.historyDetail, `${number(history.messages)} pesan · ${number(history.devices_with_chats)} device aktif chat`);
        setText(nodes.usage, number(analytics.active_chats_24h));
        setText(nodes.usageDetail, `${number(analytics.user_messages)} user · ${number(analytics.assistant_messages)} AI · 24 jam terakhir`);
        setText(nodes.documents, number(library.documents));
        setText(nodes.libraryDetail, `${number(library.indexed_chunks)} chunk · ${number(library.text_chars)} karakter index`);
        setText(nodes.realtime, number(realtime.event_files));
        setText(nodes.realtimeDetail, `Replay TTL ${number(realtime.ttl_seconds)} detik · WSS ${realtime.wss_ready ? 'ready' : 'belum aktif'}`);
        setText(nodes.ratelimit, number(rateLimit.bucket_count));
        setText(nodes.ratelimitDetail, `${rateLimit.storage || 'unknown'} · shared ${rateLimit.shared_across_workers ? 'aktif' : 'nonaktif'}`);
        renderPrivacy(payload.privacy || {});
        renderStorage(payload.storage || {});
        renderAnalytics(analytics);

        const when = payload.generated_at ? new Date(Number(payload.generated_at)).toLocaleString('id-ID') : new Date().toLocaleString('id-ID');
        setText(updated, `Update terakhir: ${when}`);
        setState('Overview production sehat dan aggregate-only.', 'ok');
    }

    async function loadOverview() {
        setState('Memuat overview production…', 'loading');
        if (refresh) refresh.disabled = true;
        try {
            const response = await fetch('/api/admin/overview', {
                headers: { Accept: 'application/json' },
                credentials: 'same-origin'
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const payload = await response.json();
            if (!payload || payload.ok !== true) throw new Error(payload?.message || 'Overview belum tersedia');
            render(payload);
        } catch (error) {
            console.error('admin overview failed', error);
            setState('Overview belum bisa dimuat. Coba refresh lagi.', 'error');
        } finally {
            if (refresh) refresh.disabled = false;
        }
    }

    refresh?.addEventListener('click', loadOverview);
    loadOverview();
}());
