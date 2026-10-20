// The phase indicator switches the phase on view. The buttons top right open
// the agenda and the guides, each a sheet over the whole page that its close
// button, or Escape, closes. A link to any id on the page opens the view that
// holds it; a view published as its own file is fetched the first time it is
// shown, and a folded card opens when a link names it. The calendar shows one
// month, and its arrows step through the others. A section's Open all opens, or
// closes, every folded card in it.
(() => {
  const owner = JSON.parse(document.getElementById('anchors').textContent);
  const main = document.getElementById('phases');
  const views = new Map([...document.querySelectorAll('section.phase')].map((s) => [s.dataset.phase, s]));
  const sheets = [...document.querySelectorAll('dialog.sheet')];
  // The phase tabs, and the buttons top right.
  const tabs = [...document.querySelectorAll('header a[data-phase]')];
  // The phase on view, under any sheet.
  let phase = main.dataset.open;

  const months = [...document.querySelectorAll('header .month')];
  for (const button of document.querySelectorAll('header .month [data-step]')) {
    button.addEventListener('click', () => {
      const step = button.dataset.step;
      const next = months[months.indexOf(button.closest('.month')) + Number(step)];
      for (const month of months) month.hidden = month !== next;
      // Keep the focus on an arrow, the same way where the new month has one.
      (next.querySelector(`[data-step="${step}"]`) || next.querySelector('[data-step]')).focus();
    });
  }

  async function load(section) {
    if (!section.dataset.src) return;
    try {
      const response = await fetch(section.dataset.src);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      section.innerHTML = await response.text();
      delete section.dataset.src;
    } catch (error) {
      section.innerHTML = '';
      const note = document.createElement('p');
      note.className = 'loadfail';
      note.textContent = `This view didn't load (${error.message}). `;
      const retry = document.createElement('button');
      retry.type = 'button';
      retry.textContent = 'Try again';
      retry.addEventListener('click', () => show(location.hash));
      note.append(retry);
      section.append(note);
    }
  }

  function mark(key) {
    for (const tab of tabs) {
      if (tab.dataset.phase === key) tab.setAttribute('aria-current', 'true');
      else tab.removeAttribute('aria-current');
    }
  }

  async function show(hash) {
    const anchor = decodeURIComponent(hash.replace(/^#/, ''));
    const key = views.has(anchor) ? anchor : owner[anchor];
    if (anchor && !key) {
      // An id outside every view, in the header.
      document.getElementById(anchor)?.scrollIntoView();
      return;
    }
    const section = views.get(key || phase);
    const sheet = section.closest('dialog');
    for (const other of sheets) if (other !== sheet && other.open) other.close();
    if (sheet) {
      if (!sheet.open) {
        sheet.showModal();
        sheet.scrollTop = 0;
      }
    } else {
      phase = section.dataset.phase;
      for (const [name, view] of views) if (!view.closest('dialog')) view.hidden = name !== phase;
    }
    mark(section.dataset.phase);
    await load(section);
    start(section);
    // A view opens where the reader is; a link to an id inside one goes to it,
    // opening the card it names, or the folds around it.
    if (anchor && !views.has(anchor)) {
      const target = document.getElementById(anchor);
      const fold = target?.querySelector(':scope > details.fold');
      if (fold) fold.open = true;
      for (let around = target?.parentElement?.closest('details'); around; around = around.parentElement?.closest('details')) around.open = true;
      (target || section).scrollIntoView();
    }
  }

  // A board opens at its first column with work left, beside its rows' names, the
  // first time its view is on screen and so has a width.
  function start(section) {
    for (const box of section.querySelectorAll('.scroll[data-start]')) {
      if (!box.offsetWidth) continue;
      const cells = box.querySelector('tr').cells;
      box.scrollLeft = cells[box.dataset.start].offsetLeft - cells[0].offsetWidth;
      delete box.dataset.start;
    }
  }
  // A scroll doesn't bubble either: a box scrolled from its start shades the edge of
  // what stays in view.
  document.addEventListener('scroll', (event) => {
    const box = event.target;
    if (box.classList?.contains('scroll')) box.classList.toggle('scrolled', box.scrollLeft > 0);
  }, true);

  // Open all says what a click does: open the section's folded cards while any is
  // closed, and close them once all are open.
  function label(button) {
    const folds = [...button.closest('.block').querySelectorAll('details.fold')];
    button.textContent = folds.some((fold) => !fold.open) ? 'Open all' : 'Close all';
  }
  document.addEventListener('click', (event) => {
    const button = event.target.closest('button.open-all');
    if (!button) return;
    const folds = [...button.closest('.block').querySelectorAll('details.fold')];
    const open = folds.some((fold) => !fold.open);
    for (const fold of folds) fold.open = open;
    label(button);
  });
  // A toggle doesn't bubble, so the document listens as it comes down.
  document.addEventListener('toggle', (event) => {
    const button = event.target.closest?.('.block')?.querySelector('button.open-all');
    if (button) label(button);
  }, true);

  for (const sheet of sheets) {
    sheet.querySelector('.close').addEventListener('click', () => sheet.close());
    // Closed by its button or by Escape: back to the phase beneath it, and the
    // address with it, without a step in the history.
    sheet.addEventListener('close', () => {
      const anchor = decodeURIComponent(location.hash.replace(/^#/, ''));
      const key = views.has(anchor) ? anchor : owner[anchor];
      if (key && views.get(key).closest('dialog') === sheet) history.replaceState(null, '', `#${phase}`);
      if (!sheets.some((other) => other.open)) mark(phase);
    });
  }

  addEventListener('hashchange', () => show(location.hash));
  show(location.hash);
})();
