let offset = 0;
let currentSearch = "";
let isLoading = false;
let hasMore = true;
let totalItems = 0;
let currentItemId = null;

const SONAGI_SYMBOL_SVG = `<svg width="80" height="80" viewBox="0 0 100 100" fill="#1991B9" stroke="none" xmlns="http://www.w3.org/2000/svg" style="opacity: 0.8;">
  <g transform="scale(4.166666666666667) translate(0, 24)">
    <path d="M 12.1047,-0.103256 L 12.2091,-0.111465 L 12.3129,-0.125137 L 12.4158,-0.144211 L 12.5176,-0.168655 L 12.618,-0.198395 L 12.7167,-0.233353 L 12.8135,-0.273422 L 12.908,-0.318497 L 13,-0.368454 L 13.0893,-0.423172 L 13.1756,-0.482483 L 13.2586,-0.546219 L 13.3383,-0.614227 L 13.4142,-0.686295 L 23.3137,-10.5858 L 23.3858,-10.6617 L 23.4538,-10.7414 L 23.5175,-10.8244 L 23.5768,-10.9107 L 23.6315,-11 L 23.6815,-11.092 L 23.7266,-11.1865 L 23.7666,-11.2833 L 23.8016,-11.382 L 23.8313,-11.4824 L 23.8558,-11.5842 L 23.8749,-11.6871 L 23.8885,-11.7909 L 23.8967,-11.8953 L 23.8995,-12 L 23.8967,-12.1047 L 23.8885,-12.2091 L 23.8749,-12.3129 L 23.8558,-12.4158 L 23.8313,-12.5176 L 23.8016,-12.618 L 23.7666,-12.7167 L 23.7266,-12.8135 L 23.6815,-12.908 L 23.6315,-13 L 23.5768,-13.0893 L 23.5175,-13.1756 L 23.4538,-13.2586 L 23.3858,-13.3383 L 23.3137,-13.4142 L 13.4142,-23.3137 L 13.3383,-23.3858 L 13.2586,-23.4538 L 13.1756,-23.5175 L 13.0893,-23.5768 L 13,-23.6315 L 12.908,-23.6815 L 12.8135,-23.7266 L 12.7167,-23.7666 L 12.618,-23.8016 L 12.5176,-23.8313 L 12.4158,-23.8558 L 12.3129,-23.8749 L 12.2091,-23.8885 L 12.1047,-23.8967 L 12,-23.8995 L 11.8953,-23.8967 L 11.7909,-23.8885 L 11.6871,-23.8749 L 11.5842,-23.8558 L 11.4824,-23.8313 L 11.382,-23.8016 L 11.2833,-23.7666 L 11.1865,-23.7266 L 11.092,-23.6815 L 11,-23.6315 L 10.9107,-23.5768 L 10.8244,-23.5175 L 10.7414,-23.4538 L 10.6617,-23.3858 L 10.5858,-23.3137 L 0.686295,-13.4142 L 0.614227,-13.3383 L 0.546219,-13.2586 L 0.482483,-13.1756 L 0.423172,-13.0893 L 0.368454,-13 L 0.318497,-12.908 L 0.273422,-12.8135 L 0.233353,-12.7167 L 0.198395,-12.618 L 0.168655,-12.5176 L 0.144211,-12.4158 L 0.125137,-12.3129 L 0.111465,-12.2091 L 0.103256,-12.1047 L 0.10051,-12 L 0.103256,-11.8953 L 0.111465,-11.7909 L 0.125137,-11.6871 L 0.144211,-11.5842 L 0.168655,-11.4824 L 0.198395,-11.382 L 0.233353,-11.2833 L 0.273422,-11.1865 L 0.318497,-11.092 L 0.368454,-11 L 0.423172,-10.9107 L 0.482483,-10.8244 L 0.546219,-10.7414 L 0.614227,-10.6617 L 0.686295,-10.5858 L 10.5858,-0.686295 L 10.6617,-0.614227 L 10.7414,-0.546219 L 10.8244,-0.482483 L 10.9107,-0.423172 L 11,-0.368454 L 11.092,-0.318497 L 11.1865,-0.273422 L 11.2833,-0.233353 L 11.382,-0.198395 L 11.4824,-0.168655 L 11.5842,-0.144211 L 11.6871,-0.125137 L 11.7909,-0.111465 L 11.8953,-0.103256 L 12,-0.10051 z M 11.8168,-4.50479 L 11.6341,-4.51917 L 11.4525,-4.54308 L 11.2723,-4.57648 L 11.0941,-4.61925 L 10.9184,-4.6713 L 10.7457,-4.73247 L 10.5764,-4.80258 L 10.411,-4.88147 L 10.25,-4.9689 L 10.0938,-5.06465 L 9.94275,-5.16843 L 9.79738,-5.27998 L 9.65804,-5.39899 L 9.52512,-5.52512 L 9.39899,-5.65804 L 9.27998,-5.79738 L 9.16843,-5.94275 L 9.06465,-6.09375 L 8.9689,-6.25 L 8.88147,-6.41103 L 8.80258,-6.57642 L 8.73247,-6.7457 L 8.6713,-6.91843 L 8.61925,-7.09413 L 8.57648,-7.27231 L 8.54308,-7.45247 L 8.51917,-7.63414 L 8.50479,-7.81682 L 8.5,-8 L 8.50479,-8.18317 L 8.51917,-8.36584 L 8.54308,-8.54752 L 8.57648,-8.72768 L 8.61925,-8.90585 L 8.6713,-9.08156 L 8.73247,-9.25429 L 8.80258,-9.42357 L 11.8173,-16.0813 L 11.8218,-16.0908 L 11.8268,-16.1 L 11.8323,-16.1089 L 11.8382,-16.1176 L 11.8446,-16.1259 L 11.8514,-16.1338 L 11.8586,-16.1414 L 11.8662,-16.1486 L 11.8741,-16.1554 L 11.8824,-16.1618 L 11.8911,-16.1677 L 11.9,-16.1732 L 11.9092,-16.1782 L 11.9186,-16.1827 L 11.9283,-16.1867 L 11.9382,-16.1902 L 11.9482,-16.1932 L 11.9584,-16.1956 L 11.9687,-16.1975 L 11.9791,-16.1989 L 11.9895,-16.1997 L 12,-16.2 L 12.0105,-16.1997 L 12.0209,-16.1989 L 12.0313,-16.1975 L 12.0416,-16.1956 L 12.0518,-16.1932 L 12.0618,-16.1902 L 12.0717,-16.1867 L 12.0813,-16.1827 L 12.0908,-16.1782 L 12.1,-16.1732 L 12.1089,-16.1677 L 12.1176,-16.1618 L 12.1259,-16.1554 L 12.1338,-16.1486 L 12.1414,-16.1414 L 12.1486,-16.1338 L 12.1554,-16.1259 L 12.1618,-16.1176 L 12.1677,-16.1089 L 12.1732,-16.1 L 12.1782,-16.0908 L 12.1827,-16.0813 L 15.1974,-9.42357 L 15.2675,-9.25429 L 15.3287,-9.08156 L 15.3807,-8.90585 L 15.4235,-8.72768 L 15.4569,-8.54752 L 15.4808,-8.36584 L 15.4952,-8.18317 L 15.5,-8 L 15.4952,-7.81682 L 15.4808,-7.63414 L 15.4569,-7.45247 L 15.4235,-7.27231 L 15.3807,-7.09413 L 15.3287,-6.91843 L 15.2675,-6.7457 L 15.1974,-6.57642 L 15.1185,-6.41103 L 15.0311,-6.25 L 14.9353,-6.09375 L 14.8316,-5.94275 L 14.72,-5.79738 L 14.601,-5.65804 L 14.4749,-5.52512 L 14.3419,-5.39899 L 14.2026,-5.27998 L 14.0572,-5.16843 L 13.9062,-5.06465 L 13.75,-4.9689 L 13.589,-4.88147 L 13.4236,-4.80258 L 13.2543,-4.73247 L 13.0816,-4.6713 L 12.9059,-4.61925 L 12.7277,-4.57648 L 12.5475,-4.54308 L 12.3658,-4.51917 L 12.1832,-4.50479 L 12,-4.5 z"/>
  </g>
</svg>`;

const FOLDER_ICON_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#bbb" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z" /></svg>`;

const HEAVY_EXTS = ["psd", "ai", "fig", "blend", "c4d", "mp4", "mov", "pdf", "zip"];
const FONT_EXTS = ["ttf", "otf", "woff", "woff2"];
const FONT_SAMPLE_EN = "AaBbCcDd 0123 The quick brown fox";
const FONT_SAMPLE_KO = "가나다라 마바사아 한글 미리보기";

window.onload = () => {
    const urlParams = new URLSearchParams(window.location.search);
    const querySearch = urlParams.get("search");
    if (querySearch) {
        currentSearch = querySearch;
        document.getElementById("search").value = currentSearch;
    }

    loadSidebarFilters();
    loadItems();
};

async function loadSidebarFilters() {
    try {
        const [tagsRes, extsRes] = await Promise.all([fetch("/api/tags"), fetch("/api/exts")]);

        const tags = await tagsRes.json();
        const exts = await extsRes.json();

        const tagList = document.getElementById("tag-list");
        tagList.innerHTML = "";
        for (const t of tags) {
            const li = document.createElement("li");
            const label = document.createElement("span");
            label.textContent = `# ${t.tag}`;
            const count = document.createElement("span");
            count.className = "count";
            count.textContent = t.count;
            li.appendChild(label);
            li.appendChild(count);
            li.onclick = () => setFilter(t.tag);
            tagList.appendChild(li);
        }

        const extList = document.getElementById("ext-list");
        extList.innerHTML = "";
        for (const e of exts) {
            const li = document.createElement("li");
            const label = document.createElement("span");
            label.textContent = `. ${e.ext.toUpperCase()}`;
            const count = document.createElement("span");
            count.className = "count";
            count.textContent = e.count;
            li.appendChild(label);
            li.appendChild(count);
            li.onclick = () => setFilter(e.ext);
            extList.appendChild(li);
        }
    } catch (e) {
        console.error("Failed to load sidebar filters:", e);
    }
}

function setFilter(term) {
    document.getElementById("search").value = term;
    searchItems();
}

async function loadItems(reset = false) {
    if (reset) {
        offset = 0;
        hasMore = true;
        document.getElementById("gallery").innerHTML = "";
    }

    if (isLoading || !hasMore) return;
    isLoading = true;
    document.getElementById("loading").style.display = "flex";

    try {
        const res = await fetch(
            `/api/items?limit=50&offset=${offset}&search=${encodeURIComponent(currentSearch)}`,
        );
        const data = await res.json();

        totalItems = data.total;
        const items = data.items;

        const gallery = document.getElementById("gallery");
        const stats = document.getElementById("stats");

        if (offset === 0) {
            stats.innerHTML = "";

            const foundSpan = document.createElement("span");
            foundSpan.innerHTML = `Found <strong>${totalItems}</strong> items`;
            stats.appendChild(foundSpan);

            if (currentSearch) {
                const searchSpan = document.createElement("span");
                searchSpan.textContent = ` for "${currentSearch}"`;
                stats.appendChild(searchSpan);
            }

            if (totalItems === 0) {
                gallery.innerHTML =
                    '<div class="no-results">No items found matching your search.</div>';
            }
        }

        if (items.length < 50) {
            hasMore = false;
        }

        for (const item of items) {
            const card = document.createElement("div");
            card.className = "card";
            card.onclick = () => openModal(item.id);

            const imgSrc = item.has_thumbnail
                ? `/api/image/${item.id}/thumbnail`
                : `/api/image/${item.id}/original`;

            const imgContainer = document.createElement("div");
            imgContainer.className = "img-container";

            const img = document.createElement("img");
            img.loading = "lazy";

            img.onerror = function () {
                this.style.display = "none";
                const placeholder = document.createElement("div");
                placeholder.className = "placeholder-icon";
                if (item.ext && FONT_EXTS.includes(item.ext.toLowerCase())) {
                    placeholder.innerHTML = FOLDER_ICON_SVG;
                    placeholder.classList.add("font-card-placeholder");
                    // @font-face 동적 로딩 후 샘플 텍스트 렌더링
                    const fontId = `font-card-${item.id}`;
                    const style = document.createElement("style");
                    style.textContent = `@font-face { font-family: "${fontId}"; src: url("/api/image/${item.id}/original"); }`;
                    document.head.appendChild(style);
                    document.fonts.load(`14px "${fontId}"`).then(() => {
                        placeholder.innerHTML = `<span class="font-card-sample" style="font-family:'${fontId}',sans-serif">${FONT_SAMPLE_EN}</span>`;
                    });
                } else if (item.ext && HEAVY_EXTS.includes(item.ext.toLowerCase())) {
                    placeholder.innerHTML = SONAGI_SYMBOL_SVG;
                } else {
                    placeholder.innerHTML = FOLDER_ICON_SVG;
                }
                this.parentElement.appendChild(placeholder);
            };
            img.src = imgSrc;
            imgContainer.appendChild(img);

            const info = document.createElement("div");
            info.className = "card-info";

            const title = document.createElement("h3");
            title.className = "card-title";
            title.textContent = item.name || "Untitled";

            const tagsContainer = document.createElement("div");
            if (item.ext) {
                const extSpan = document.createElement("span");
                extSpan.className = "tag tag-ext";
                extSpan.textContent = item.ext.toUpperCase();
                tagsContainer.appendChild(extSpan);
            }

            for (const t of item.tags.slice(0, 3)) {
                const tagSpan = document.createElement("span");
                tagSpan.className = "tag";
                tagSpan.textContent = t;
                tagsContainer.appendChild(tagSpan);
            }

            info.appendChild(title);
            info.appendChild(tagsContainer);
            card.appendChild(imgContainer);
            card.appendChild(info);
            gallery.appendChild(card);
        }

        offset += 50;
    } catch (e) {
        console.error(e);
        const stats = document.getElementById("stats");
        stats.innerHTML = '<span style="color:red;">Error loading items. Please try again.</span>';
    } finally {
        isLoading = false;
        document.getElementById("loading").style.display = "none";
    }
}

function searchItems() {
    currentSearch = document.getElementById("search").value;
    const newUrl = new URL(window.location.href);
    if (currentSearch) {
        newUrl.searchParams.set("search", currentSearch);
    } else {
        newUrl.searchParams.delete("search");
    }
    window.history.pushState({}, "", newUrl.toString());
    loadItems(true);
}

window.onscroll = () => {
    if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 500) {
        loadItems();
    }
};

async function openModal(itemId) {
    currentItemId = itemId;
    const lightbox = document.getElementById("lightbox");
    const imgContainer = document.getElementById("modal-img-wrapper");

    lightbox.classList.add("active");
    imgContainer.innerHTML = '<img id="modal-img" src="">';
    const img = document.getElementById("modal-img");

    document.getElementById("modal-title").textContent = "Loading...";
    document.getElementById("modal-ext").textContent = "...";
    document.getElementById("modal-date").textContent = "";
    document.getElementById("modal-url").textContent = "";
    document.getElementById("modal-url").removeAttribute("href");
    document.getElementById("modal-tags").innerHTML = "";
    document.getElementById("modal-annotation").textContent = "";
    toggleEditMode(false);

    img.onerror = function () {
        this.style.display = "none";
        imgContainer.innerHTML = `<div class="modal-placeholder">${SONAGI_SYMBOL_SVG}</div>`;
    };

    try {
        const res = await fetch(`/api/items/${itemId}`);
        const item = await res.json();

        document.getElementById("modal-title").textContent = item.name || "Untitled";
        document.getElementById("edit-name").value = item.name || "";
        document.getElementById("modal-ext").textContent = (item.ext || "Unknown").toUpperCase();

        if (item.created_at) {
            document.getElementById("modal-date").textContent = new Date(
                item.created_at,
            ).toLocaleString();
        }

        const urlEl = document.getElementById("modal-url");
        if (item.url && (item.url.startsWith("http://") || item.url.startsWith("https://"))) {
            urlEl.textContent = item.url;
            urlEl.href = item.url;
            urlEl.target = "_blank";
            urlEl.rel = "noopener noreferrer";
        } else {
            urlEl.textContent = "N/A";
            urlEl.removeAttribute("href");
        }

        const tagsContainer = document.getElementById("modal-tags");
        tagsContainer.innerHTML = "";
        document.getElementById("edit-tags").value = item.tags.join(", ");
        for (const t of item.tags) {
            const span = document.createElement("span");
            span.className = "tag";
            span.textContent = t;
            tagsContainer.appendChild(span);
        }

        document.getElementById("modal-annotation").textContent =
            item.annotation || "No notes available.";

        const originalLink = document.getElementById("modal-original-link");
        originalLink.href = `/api/image/${itemId}/original`;
        originalLink.target = "_blank";
        originalLink.rel = "noopener noreferrer";

        // 폰트 파일이면 @font-face 동적 로딩으로 미리보기 렌더링
        if (item.ext && FONT_EXTS.includes(item.ext.toLowerCase())) {
            img.style.display = "none";
            const fontId = `font-modal-${itemId}`;
            const existingStyle = document.getElementById(`style-${fontId}`);
            if (!existingStyle) {
                const style = document.createElement("style");
                style.id = `style-${fontId}`;
                style.textContent = `@font-face { font-family: "${fontId}"; src: url("/api/image/${itemId}/original"); }`;
                document.head.appendChild(style);
            }
            imgContainer.innerHTML = `<div class="font-modal-preview" id="font-preview-${fontId}">
                <p class="font-preview-loading">Loading font...</p>
            </div>`;
            document.fonts.load(`32px "${fontId}"`).then(() => {
                const preview = document.getElementById(`font-preview-${fontId}`);
                if (preview) {
                    preview.innerHTML = `
                        <p class="font-preview-en" style="font-family:'${fontId}',sans-serif">${FONT_SAMPLE_EN}</p>
                        <p class="font-preview-ko" style="font-family:'${fontId}',sans-serif">${FONT_SAMPLE_KO}</p>
                        <p class="font-preview-lg" style="font-family:'${fontId}',sans-serif">Aa Bb Cc</p>
                    `;
                }
            }).catch(() => {
                const preview = document.getElementById(`font-preview-${fontId}`);
                if (preview) preview.innerHTML = `<p class="font-preview-error">Failed to load font preview.</p>`;
            });
        } else {
            img.src = `/api/image/${itemId}/original`;
        }
    } catch (e) {
        console.error("Failed to fetch item details", e);
        document.getElementById("modal-title").textContent = "Error loading details";
        document.getElementById("modal-ext").textContent = "Error";
        document.getElementById("modal-date").textContent = "Error";
        const urlEl = document.getElementById("modal-url");
        urlEl.textContent = "N/A";
        urlEl.removeAttribute("href");
    }
}

function closeModal() {
    document.getElementById("lightbox").classList.remove("active");
    document.getElementById("modal-img-wrapper").innerHTML = "";
    currentItemId = null;
}

document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
});

// CRUD Functions
function toggleEditMode(show) {
    document.getElementById("edit-mode").style.display = show ? "block" : "none";
    if (show) {
        document.getElementById("modal-title").style.display = "none";
        document.getElementById("modal-tags").style.display = "none";
    } else {
        document.getElementById("modal-title").style.display = "block";
        document.getElementById("modal-tags").style.display = "flex";
    }
}

async function _saveEdits() {
    if (!currentItemId) return;
    const newName = document.getElementById("edit-name").value;
    const newTags = document
        .getElementById("edit-tags")
        .value.split(",")
        .map((t) => t.trim())
        .filter((t) => t);

    try {
        await fetch(`/api/items/${currentItemId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: newName, tags: newTags }),
        });
        openModal(currentItemId); // reload modal data
        loadSidebarFilters(); // reload tags in sidebar
        loadItems(true); // reload grid
    } catch (_e) {
        alert("Failed to update asset");
    }
}

async function _deleteAsset() {
    if (!currentItemId) return;
    if (!confirm("Are you sure you want to delete this asset? This cannot be undone.")) return;

    try {
        await fetch(`/api/items/${currentItemId}`, { method: "DELETE" });
        closeModal();
        loadSidebarFilters();
        loadItems(true);
    } catch (_e) {
        alert("Failed to delete asset");
    }
}

async function _uploadAsset() {
    const fileInput = document.getElementById("file-upload");
    const tagsInput = document.getElementById("upload-tags");
    if (!fileInput.files.length) return alert("Please select a file");

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    formData.append("tags", tagsInput.value);

    try {
        document.getElementById("loading").style.display = "flex";
        await fetch("/api/upload", {
            method: "POST",
            body: formData,
        });
        fileInput.value = "";
        tagsInput.value = "";
        loadSidebarFilters();
        loadItems(true);
    } catch (_e) {
        alert("Failed to upload asset");
    } finally {
        document.getElementById("loading").style.display = "none";
    }
}
