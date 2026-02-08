const selectAll = document.getElementById("selectAll");
const selectAllBtn = document.getElementById("selectAllBtn");
const selectNoneBtn = document.getElementById("selectNoneBtn");
const rowCheckboxes = Array.from(document.querySelectorAll(".row-checkbox"));

if (selectAll) {
    selectAll.addEventListener("change", () => {
        rowCheckboxes.forEach(cb => {
            cb.checked = selectAll.checked;
        });
    });
}
if (selectAllBtn) {
    selectAllBtn.addEventListener("click", () => {
        rowCheckboxes.forEach(cb => (cb.checked = true));
        if (selectAll) selectAll.checked = true;
    });
}
if (selectNoneBtn) {
    selectNoneBtn.addEventListener("click", () => {
        rowCheckboxes.forEach(cb => (cb.checked = false));
        if (selectAll) selectAll.checked = false;
    });
}
