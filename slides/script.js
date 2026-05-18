// Minimal slide controller: arrow-key + click nav, "n" toggles speaker notes.

(function () {
  const slides = Array.from(document.querySelectorAll("section.slide"));
  const counter = document.getElementById("counter");
  const notesPanel = document.getElementById("notes");
  const notesBody = document.getElementById("notes-body");
  const prevBtn = document.getElementById("prev");
  const nextBtn = document.getElementById("next");

  function indexFromHash() {
    const m = /^#s=(\d+)$/.exec(window.location.hash);
    if (!m) return 0;
    const i = parseInt(m[1], 10) - 1;
    return Number.isFinite(i) && i >= 0 && i < slides.length ? i : 0;
  }

  let current = indexFromHash();

  function renderNotes(slide) {
    const note = slide.querySelector("aside.notes");
    notesBody.innerHTML = note ? note.innerHTML : "<p class='muted'>No notes for this slide.</p>";
  }

  function show(i) {
    if (i < 0 || i >= slides.length) return;
    slides[current].classList.remove("active");
    current = i;
    slides[current].classList.add("active");
    counter.textContent = `${current + 1} / ${slides.length}`;
    history.replaceState(null, "", `#s=${current + 1}`);
    renderNotes(slides[current]);
  }

  function next() { show(Math.min(current + 1, slides.length - 1)); }
  function prev() { show(Math.max(current - 1, 0)); }

  window.addEventListener("keydown", (e) => {
    // Don't capture keys while typing in form fields (just in case).
    const tag = (e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea") return;
    switch (e.key) {
      case "ArrowRight":
      case "PageDown":
      case " ":
        e.preventDefault();
        next();
        break;
      case "ArrowLeft":
      case "PageUp":
        e.preventDefault();
        prev();
        break;
      case "Home":
        e.preventDefault();
        show(0);
        break;
      case "End":
        e.preventDefault();
        show(slides.length - 1);
        break;
      case "n":
      case "N":
        notesPanel.classList.toggle("open");
        break;
    }
  });

  prevBtn.addEventListener("click", prev);
  nextBtn.addEventListener("click", next);

  show(current);
})();
