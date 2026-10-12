// The phase indicator switches the phase on view. The buttons top right open
// the agenda and the guides, each a sheet over the whole page that its close
// button, or Escape, closes. A link to any id on the page opens the view that
// holds it; a view published as its own file is fetched the first time it is
// shown. The calendar shows one month, and its arrows step through the others.
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
    // A view opens where the reader is; a link to an id inside one goes to it.
    if (anchor && !views.has(anchor)) (document.getElementById(anchor) || section).scrollIntoView();
  }

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
