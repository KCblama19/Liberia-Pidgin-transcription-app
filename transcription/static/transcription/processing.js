const cards = Array.from(document.querySelectorAll("[data-transcription-id]"));
const isMultiEl = document.getElementById("isMulti");
const isMulti = isMultiEl ? JSON.parse(isMultiEl.textContent) : false;
const retryAllBtn = document.getElementById("retryAllBtn");
const cancelAllBtn = document.getElementById("cancelAllBtn");
const toggleFinishedBtn = document.getElementById("toggleFinishedBtn");

let hideFinished = false;

const confirmOverlay = document.getElementById("confirmOverlay");
const confirmTitle = document.getElementById("confirmTitle");
const confirmMessage = document.getElementById("confirmMessage");
const confirmCancel = document.getElementById("confirmCancel");
const confirmOk = document.getElementById("confirmOk");
let confirmAction = null;

function openConfirm({ title, message, onConfirm }) {
    if (!confirmOverlay) return;
    confirmTitle.textContent = title;
    confirmMessage.textContent = message;
    confirmAction = onConfirm;
    confirmOverlay.classList.remove("hidden");
    confirmOverlay.classList.add("flex");
}

function closeConfirm() {
    confirmAction = null;
    if (!confirmOverlay) return;
    confirmOverlay.classList.add("hidden");
    confirmOverlay.classList.remove("flex");
}

confirmCancel?.addEventListener("click", closeConfirm);
confirmOverlay?.addEventListener("click", (e) => {
    if (e.target === confirmOverlay) closeConfirm();
});
confirmOk?.addEventListener("click", () => {
    if (typeof confirmAction === "function") confirmAction();
    closeConfirm();
});

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
    return null;
}

const csrfToken = getCookie("csrftoken");

const maxFakeProgress = 90;
const smoothStep = 2;

function setProgress(card, value) {
    const progressBar = card.querySelector(".progress-bar");
    const progressText = card.querySelector(".progress-text");
    const next = Math.max(0, Math.min(99, value));
    progressBar.dataset.progress = String(next);
    progressBar.style.width = next + "%";
    progressText.textContent = Math.floor(next) + "%";
}

function smoothToward(card, target) {
    const progressBar = card.querySelector(".progress-bar");
    const current = parseFloat(progressBar.dataset.progress || "0");
    if (current >= target) return;
    const next = Math.min(target, current + smoothStep);
    setProgress(card, next);
}

function tick(card) {
    const progressBar = card.querySelector(".progress-bar");
    const current = parseFloat(progressBar.dataset.progress || "0");
    if (current < maxFakeProgress) {
        let next = current + Math.random() * 2;
        if (next > maxFakeProgress) next = maxFakeProgress;
        setProgress(card, next);
    }
}

async function pollOne(card) {
    const id = card.dataset.transcriptionId;
    const statusText = card.querySelector(".status-text");
    const statusBadge = card.querySelector(".status-badge");
    const progressBar = card.querySelector(".progress-bar");
    const progressText = card.querySelector(".progress-text");
    const viewLink = card.querySelector(".view-link");
    const cancelBtn = card.querySelector(".cancel-btn");
    const retryBtn = card.querySelector(".retry-btn");
    const errorText = card.querySelector(".error-text");
    const etaText = card.querySelector(".eta-text");
    const elapsedText = card.querySelector(".elapsed-text");
    const stageText = card.querySelector(".stage-text");

    try {
        const res = await fetch(`/transcription/${id}/status/`);
        const data = await res.json();

        if (data.file_name) {
            const fileNameEl = card.querySelector("p.font-semibold");
            if (fileNameEl) fileNameEl.textContent = data.file_name;
        }
        if (data.uploaded_at && !card.dataset.uploadedAt) {
            card.dataset.uploadedAt = data.uploaded_at;
        }
        if (data.status) {
            card.dataset.status = data.status;
        }

        if (data.status === "done") {
            progressBar.style.width = "100%";
            progressText.textContent = "100%";
            statusText.textContent = "Processing Complete!";
            statusBadge.textContent = "Done";
            statusBadge.className = "status-badge text-xs font-semibold px-2 py-1 rounded bg-green-100 text-green-700";
            progressBar.className = "progress-bar bg-green-500 h-4 rounded-full w-0 transition-all";
            viewLink.classList.remove("hidden");
            if (cancelBtn) cancelBtn.classList.add("hidden");
            if (retryBtn) retryBtn.classList.add("hidden");
            if (errorText) errorText.classList.add("hidden");
            if (etaText) etaText.classList.add("hidden");
            if (elapsedText) elapsedText.classList.add("hidden");
            if (stageText) stageText.classList.add("hidden");
            if (hideFinished) card.classList.add("hidden");

            if (!isMulti) {
                setTimeout(() => (window.location.href = data.redirect_url), 500);
                return;
            }
        } else if (data.status === "cancelled") {
            statusText.textContent = "Cancelled";
            statusBadge.textContent = "Cancelled";
            statusBadge.className = "status-badge text-xs font-semibold px-2 py-1 rounded bg-gray-200 text-gray-700";
            progressBar.className = "progress-bar bg-gray-300 h-4 rounded-full w-0 transition-all";
            if (cancelBtn) cancelBtn.classList.add("hidden");
            if (retryBtn) retryBtn.classList.remove("hidden");
            if (errorText) errorText.classList.add("hidden");
            if (etaText) etaText.classList.add("hidden");
            if (elapsedText) elapsedText.classList.add("hidden");
            if (stageText) stageText.classList.add("hidden");
            if (hideFinished) card.classList.add("hidden");
        } else if (data.status === "error") {
            statusText.textContent = "Error";
            statusBadge.textContent = "Error";
            statusBadge.className = "status-badge text-xs font-semibold px-2 py-1 rounded bg-red-100 text-red-700";
            progressBar.className = "progress-bar bg-red-500 h-4 rounded-full w-0 transition-all";
            if (cancelBtn) cancelBtn.classList.add("hidden");
            if (retryBtn) retryBtn.classList.remove("hidden");
            if (errorText) {
                errorText.textContent = data.error_message || "An unexpected error occurred.";
                errorText.classList.remove("hidden");
            }
            if (etaText) etaText.classList.add("hidden");
            if (elapsedText) elapsedText.classList.add("hidden");
            if (stageText) stageText.classList.add("hidden");
            if (hideFinished) card.classList.add("hidden");
        } else {
            const realProgress = Math.min(Number(data.progress || 0), 99);
            if (realProgress > 0) {
                smoothToward(card, realProgress);
            } else {
                tick(card);
            }
            statusText.textContent = "Processing your audio...";
            statusBadge.textContent = "Processing";
            statusBadge.className = "status-badge text-xs font-semibold px-2 py-1 rounded bg-blue-100 text-blue-700";
            progressBar.className = "progress-bar bg-blue-600 h-4 rounded-full w-0 transition-all";
            if (retryBtn) retryBtn.classList.add("hidden");
            if (errorText) errorText.classList.add("hidden");
            card.classList.remove("hidden");

            if (data.current_stage) {
                stageText.textContent = data.current_stage.replace(/_/g, " ");
                stageText.classList.remove("hidden");
            } else {
                stageText.classList.add("hidden");
            }

            if (data.progress && data.progress > 0) {
                if (!card.dataset.startedAt) {
                    card.dataset.startedAt = String(Date.now());
                }
                const elapsedMs = Date.now() - (Number(card.dataset.startedAt) || Date.now());
                const remainingPct = Math.max(0, 100 - Number(data.progress));
                const etaMs = remainingPct > 0 ? (elapsedMs * (remainingPct / Number(data.progress))) : 0;
                if (etaMs > 0) {
                    const etaMin = Math.max(1, Math.round(etaMs / 60000));
                    etaText.textContent = `Estimated time remaining: ${etaMin} min`;
                    etaText.classList.remove("hidden");
                } else {
                    etaText.classList.add("hidden");
                }
            } else {
                etaText.classList.add("hidden");
            }

            if (card.dataset.uploadedAt) {
                const elapsedMs = Date.now() - Date.parse(card.dataset.uploadedAt);
                const elapsedMin = Math.max(1, Math.round(elapsedMs / 60000));
                elapsedText.textContent = `Elapsed: ${elapsedMin} min`;
                elapsedText.classList.remove("hidden");
            } else {
                elapsedText.classList.add("hidden");
            }
        }
    } catch (err) {
        console.error("Error polling status:", err);
    } finally {
        const nextDelay = document.visibilityState === "hidden" ? 3000 : 1000;
        setTimeout(() => pollOne(card), nextDelay);
    }
}

cards.forEach(card => pollOne(card));

function reorderCards() {
    const container = document.querySelector(".space-y-4");
    if (!container) return;
    const items = Array.from(container.querySelectorAll("[data-transcription-id]"));
    items.sort((a, b) => {
        const statusOrder = { processing: 0, pending: 0, uploaded: 0, done: 1, error: 2, cancelled: 3 };
        const aStatus = (a.dataset.status || "processing").toLowerCase();
        const bStatus = (b.dataset.status || "processing").toLowerCase();
        const aWeight = statusOrder[aStatus] ?? 4;
        const bWeight = statusOrder[bStatus] ?? 4;
        if (aWeight !== bWeight) return aWeight - bWeight;
        const aProgress = Number(a.querySelector(".progress-bar")?.dataset.progress || "0");
        const bProgress = Number(b.querySelector(".progress-bar")?.dataset.progress || "0");
        return bProgress - aProgress;
    });
    items.forEach(item => container.appendChild(item));
}

setInterval(reorderCards, 3000);

document.querySelectorAll(".cancel-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
        const id = btn.dataset.cancelId;
        if (!id) return;
        openConfirm({
            title: "Cancel Transcription",
            message: "Cancel this transcription?",
            onConfirm: async () => {
                try {
                    await fetch(`/transcription/${id}/cancel/`, {
                        method: "POST",
                        headers: {
                            "X-CSRFToken": csrfToken || "",
                        },
                    });
                } catch (err) {
                    console.error("Error cancelling transcription:", err);
                }
            },
        });
    });
});

document.querySelectorAll(".retry-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
        const id = btn.dataset.retryId;
        if (!id) return;
        openConfirm({
            title: "Retry Transcription",
            message: "Retry this transcription?",
            onConfirm: async () => {
                try {
                    await fetch(`/transcription/${id}/processing/`, {
                        method: "POST",
                        headers: {
                            "X-CSRFToken": csrfToken || "",
                        },
                    });
                } catch (err) {
                    console.error("Error retrying transcription:", err);
                }
            },
        });
    });
});

retryAllBtn?.addEventListener("click", async () => {
    openConfirm({
        title: "Retry All Failed",
        message: "Retry all failed or cancelled transcriptions?",
        onConfirm: async () => {
            const targets = cards.filter(c => ["error", "cancelled"].includes((c.dataset.status || "").toLowerCase()));
            for (const card of targets) {
                const id = card.dataset.transcriptionId;
                try {
                    await fetch(`/transcription/${id}/processing/`, {
                        method: "POST",
                        headers: {
                            "X-CSRFToken": csrfToken || "",
                        },
                    });
                } catch (err) {
                    console.error("Error retrying transcription:", err);
                }
            }
        },
    });
});

cancelAllBtn?.addEventListener("click", async () => {
    openConfirm({
        title: "Cancel All",
        message: "Cancel all active transcriptions?",
        onConfirm: async () => {
            const targets = cards.filter(c => ["processing", "pending", "uploaded"].includes((c.dataset.status || "processing").toLowerCase()));
            for (const card of targets) {
                const id = card.dataset.transcriptionId;
                try {
                    await fetch(`/transcription/${id}/cancel/`, {
                        method: "POST",
                        headers: {
                            "X-CSRFToken": csrfToken || "",
                        },
                    });
                } catch (err) {
                    console.error("Error cancelling transcription:", err);
                }
            }
        },
    });
});

toggleFinishedBtn?.addEventListener("click", () => {
    hideFinished = !hideFinished;
    toggleFinishedBtn.textContent = hideFinished ? "Show Finished" : "Hide Finished";
    cards.forEach(card => {
        const status = (card.dataset.status || "processing").toLowerCase();
        const isFinished = ["done", "error", "cancelled"].includes(status);
        if (hideFinished && isFinished) {
            card.classList.add("hidden");
        } else {
            card.classList.remove("hidden");
        }
    });
});
