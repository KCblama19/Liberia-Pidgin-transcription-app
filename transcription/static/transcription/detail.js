const detailConfigEl = document.getElementById("detail-config");
const detailConfig = detailConfigEl ? JSON.parse(detailConfigEl.textContent) : {};

// ======================
// Global References
// ======================
const audio = document.getElementById("audioPlayer");
const body = document.getElementById("transcriptBody");
const searchInput = document.getElementById("searchInput");
const typeFilter = document.getElementById("typeFilter");
const speakerFilter = document.getElementById("speakerFilter");
const exportBtn = document.getElementById("exportBtn");
const exportMenu = document.getElementById("exportMenu");
const exportConfirmBtn = document.getElementById("exportConfirmBtn");
const translateBtn = document.getElementById("translateBtn");
const translateStatus = document.getElementById("translateStatus");
const saveStatus = document.getElementById("saveStatus");
const toggleOriginal = document.getElementById("toggleOriginal");
const toggleEnglish = document.getElementById("toggleEnglish");
const loopToggle = document.getElementById("loopToggle");
const jumpPrev = document.getElementById("jumpPrev");
const jumpNext = document.getElementById("jumpNext");

// Scroll-to-top button
const scrollToTopBtn = document.createElement("button");
scrollToTopBtn.id = "scrollToTopBtn";
scrollToTopBtn.type = "button";
scrollToTopBtn.textContent = "To top";
scrollToTopBtn.className =
    "fixed bottom-6 right-6 z-50 hidden rounded-full bg-blue-600 px-4 py-2 text-white shadow-lg hover:bg-blue-700";
document.body.appendChild(scrollToTopBtn);

scrollToTopBtn.addEventListener("click", () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
});

window.addEventListener("scroll", () => {
    scrollToTopBtn.classList.toggle("hidden", window.scrollY < 300);
});

// ======================
// Format seconds to HH:MM:SS
// ======================
function formatTime(sec) {
    sec = Math.floor(sec);
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    return (h ? String(h).padStart(2, "0") + ":" : "") +
           String(m).padStart(2, "0") + ":" +
           String(s).padStart(2, "0");
}

// Fill timestamp chips
document.querySelectorAll(".timestamp-chip").forEach(t => {
    t.textContent = formatTime(t.dataset.seconds);
});

// ======================
// Segment Click Handling: jump to audio time
// ======================
body?.addEventListener("click", e => {
    if (e.target.closest("textarea, input, select, a")) {
        return;
    }
    const isTimestamp = e.target.closest(".timestamp-chip");
    if (e.target.closest("button") && !isTimestamp) {
        return;
    }
    const row = e.target.closest(".segment-row");
    if (!row) return;

    const seconds = row.dataset.start;
    if (!seconds) return;

    if (!audio) return;
    const target = Math.min(parseFloat(seconds), audio.duration || Infinity);
    const rowStart = parseFloat(row.dataset.start || "0");
    const rowEnd = parseFloat(row.dataset.end || rowStart);

    const isWithinRow = audio.currentTime >= rowStart && audio.currentTime <= rowEnd;

    if (isWithinRow) {
        if (!audio.paused) {
            audio.pause();
        } else {
            audio.play();
        }
        return;
    }

    audio.currentTime = target;
    audio.play();
});

// ======================
// Export Dropdown Handling
// ======================
exportBtn?.addEventListener("click", (e) => {
    e.stopPropagation();
    exportMenu.classList.toggle("hidden");
});

document.addEventListener("click", (e) => {
    if (!exportBtn || !exportMenu) return;
    if (!exportBtn.contains(e.target) && !exportMenu.contains(e.target)) {
        exportMenu.classList.add("hidden");
    }
});

exportConfirmBtn?.addEventListener("click", () => {
    const format = document.getElementById("exportFormat").value;
    const timestamps = document.getElementById("exportTimestamps").checked ? "1" : "0";
    const speakers = document.getElementById("exportSpeakers").checked ? "1" : "0";

    const url = `${detailConfig.exportUrl}?format=${format}&timestamps=${timestamps}&speakers=${speakers}&filename=${encodeURIComponent(detailConfig.filename || "transcript")}`;
    window.location.href = url;
});

// ======================
// Transcript Filtering Logic
// ======================
const segmentRows = Array.from(document.querySelectorAll(".segment-row"));
const VIRTUAL_LIMIT = 200;
let virtualMode = segmentRows.length > VIRTUAL_LIMIT;
let loadedCount = Math.min(VIRTUAL_LIMIT, segmentRows.length);

function applyVirtualization() {
    if (!virtualMode) return;
    segmentRows.forEach((row, idx) => {
        row.classList.toggle("hidden", idx >= loadedCount);
    });
}

function loadMoreSegments() {
    loadedCount = Math.min(loadedCount + 200, segmentRows.length);
    applyVirtualization();
}

const segmentIndex = segmentRows.map(row => ({
    row: row,
    text: row.dataset.text.toLowerCase(),
    type: row.dataset.type,
    speaker: row.dataset.speaker
}));
const segments = segmentRows.map(row => ({
    row,
    start: parseFloat(row.dataset.start || "0"),
    end: parseFloat(row.dataset.end || "0"),
}));

applyVirtualization();

window.addEventListener("scroll", () => {
    if (!virtualMode) return;
    const nearBottom = window.innerHeight + window.scrollY > document.body.offsetHeight - 800;
    if (nearBottom) {
        loadMoreSegments();
    }
});

let matchRows = [];
let matchIndex = -1;

function highlightMatches(query) {
    matchRows = [];
    matchIndex = -1;
    segmentRows.forEach(r => {
        r.classList.remove("ring-2", "ring-yellow-200");
    });
    if (!query) return;
    segmentIndex.forEach(item => {
        if (item.text.includes(query)) {
            item.row.classList.add("ring-2", "ring-yellow-200");
            matchRows.push(item.row);
        }
    });
}

function jumpToMatch(dir) {
    if (!matchRows.length) return;
    matchIndex = (matchIndex + dir + matchRows.length) % matchRows.length;
    const row = matchRows[matchIndex];
    row.scrollIntoView({ behavior: "smooth", block: "center" });
    row.classList.add("ring-2", "ring-yellow-400");
    setTimeout(() => row.classList.remove("ring-yellow-400"), 600);
}

function setSaveStatus(text) {
    if (!saveStatus) return;
    saveStatus.textContent = text;
}

function updateColumnVisibility() {
    const showOriginal = toggleOriginal?.checked ?? true;
    const showEnglish = toggleEnglish?.checked ?? true;
    requestAnimationFrame(() => {
        document.querySelectorAll(".col-original").forEach(el => {
            el.classList.toggle("hidden", !showOriginal);
        });
        document.querySelectorAll(".col-english").forEach(el => {
            el.classList.toggle("hidden", !showEnglish);
        });
    });
}

toggleOriginal?.addEventListener("change", updateColumnVisibility);
toggleEnglish?.addEventListener("change", updateColumnVisibility);
updateColumnVisibility();

// ======================
// Auto-save logic
// ======================
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
    return null;
}

const csrfToken = getCookie("csrftoken");
const saveTimers = new Map();

function scheduleSave(textarea) {
    const row = textarea.closest(".segment-row");
    if (!row) return;
    const index = row.dataset.index;
    const field = textarea.dataset.field;
    const value = textarea.value;

    if (saveTimers.has(textarea)) {
        clearTimeout(saveTimers.get(textarea));
    }

    saveTimers.set(
        textarea,
        setTimeout(async () => {
            try {
                await fetch(detailConfig.saveUrl, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": csrfToken || "",
                    },
                    body: JSON.stringify({ index, field, value }),
                });
                textarea.classList.add("ring-2", "ring-green-200");
                setTimeout(() => textarea.classList.remove("ring-2", "ring-green-200"), 600);
                setSaveStatus(`Saved at ${new Date().toLocaleTimeString()}`);
            } catch (err) {
                textarea.classList.add("ring-2", "ring-red-200");
                setTimeout(() => textarea.classList.remove("ring-2", "ring-red-200"), 1000);
                setSaveStatus("Save failed");
            }
        }, 500)
    );
}

document.querySelectorAll(".auto-save").forEach(textarea => {
    textarea.addEventListener("input", () => scheduleSave(textarea));
});

// ======================
// Speaker rename (client-side only)
// ======================
document.querySelectorAll(".rename-speaker").forEach(btn => {
    btn.addEventListener("click", () => {
        const current = btn.dataset.speaker || "UNKNOWN";
        const next = prompt("Rename speaker:", current);
        if (!next || next.trim() === current) return;
        document.querySelectorAll(".segment-row").forEach(row => {
            if (row.dataset.speaker === current) {
                row.dataset.speaker = next.trim();
                const chip = row.querySelector("span");
                if (chip) chip.textContent = next.trim();
            }
        });
    });
});

// ======================
// LLM Translate Button
// ======================
translateBtn.addEventListener("click", async () => {
    translateStatus.textContent = "Translation is not enabled yet.";
    return;
});

// ======================
// Playback helpers (optimized)
// ======================
let activeSegmentRow = null;
let activeIndex = -1;
let lastScrollIndex = -1;
let rafPending = false;

function findActiveIndex(current, startIndex) {
    if (!segments.length) return -1;
    let i = Math.max(0, Math.min(startIndex, segments.length - 1));

    if (current >= segments[i].start && current <= segments[i].end) {
        return i;
    }

    for (let j = i + 1; j < segments.length; j++) {
        if (current < segments[j].start) return j - 1;
        if (current >= segments[j].start && current <= segments[j].end) return j;
    }

    for (let j = i - 1; j >= 0; j--) {
        if (current >= segments[j].start && current <= segments[j].end) return j;
        if (current > segments[j].end) return j;
    }

    return -1;
}

function updateActiveSegment() {
    const current = audio.currentTime || 0;
    const nextIndex = findActiveIndex(current, activeIndex === -1 ? 0 : activeIndex);
    if (nextIndex !== activeIndex) {
        if (activeSegmentRow) activeSegmentRow.classList.remove("bg-blue-100");
        activeIndex = nextIndex;
        activeSegmentRow = nextIndex >= 0 ? segments[nextIndex].row : null;
        if (activeSegmentRow) {
            if (virtualMode && activeIndex >= loadedCount) {
                loadedCount = activeIndex + 1;
                applyVirtualization();
            }
            activeSegmentRow.classList.add("bg-blue-100");
            if (lastScrollIndex !== activeIndex) {
                lastScrollIndex = activeIndex;
                activeSegmentRow.scrollIntoView({ behavior: "smooth", block: "center" });
            }
        }
    }

    if (loopToggle?.checked && activeSegmentRow) {
        const start = segments[activeIndex].start;
        const end = segments[activeIndex].end;
        if (current >= end) {
            audio.currentTime = start;
            audio.play();
        }
    }
}

audio?.addEventListener("timeupdate", () => {
    if (rafPending) return;
    rafPending = true;
    requestAnimationFrame(() => {
        rafPending = false;
        updateActiveSegment();
    });
});

jumpPrev.addEventListener("click", () => jumpToMatch(-1));
jumpNext.addEventListener("click", () => jumpToMatch(1));

function applyFilters() {
    const q = searchInput.value.toLowerCase();
    const type = typeFilter.value;
    const speaker = speakerFilter.value;

    requestAnimationFrame(() => {
        segmentIndex.forEach(item => {
            const matchText = item.text.includes(q);
            const matchType = type === "all" || item.type === type;
            const matchSpeaker = speaker === "all" || item.speaker === speaker;

            const display = (matchText && matchType && matchSpeaker) ? "" : "none";
            item.row.style.display = display;
        });

        highlightMatches(q);
    });
}

let filterTimeout;
[searchInput, typeFilter, speakerFilter].forEach(el =>
    el.addEventListener("input", () => {
        clearTimeout(filterTimeout);
        filterTimeout = setTimeout(applyFilters, 150);
    })
);
