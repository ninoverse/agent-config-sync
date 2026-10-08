// The phase indicator switches the phase on view. A link to any id on the page
// opens the phase that holds it; a phase published as its own file is fetched
// the first time it is shown.
(() => {
  const owner = JSON.parse(document.getElementById('anchors').textContent);
  const main = document.getElementById('phases');
  const phases = new Map([...main.querySelectorAll('section.phase')].map((s) => [s.dataset.phase, s]));
  const tabs = [...document.querySelectorAll('nav.phases a[data-phase]')];

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
      note.textContent = `This phase didn't load (${error.message}). `;
      const retry = document.createElement('button');
      retry.type = 'button';
      retry.textContent = 'Try again';
      retry.addEventListener('click', () => show(location.hash));
      note.append(retry);
      section.append(note);
    }
  }

  async function show(hash) {
    const anchor = decodeURIComponent(hash.replace(/^#/, ''));
    const key = phases.has(anchor) ? anchor : owner[anchor];
    if (anchor && !key) {
      // An id outside every phase, such as the glossary.
      const target = document.getElementById(anchor);
      if (target && target.tagName === 'DETAILS') target.open = true;
      target?.scrollIntoView();
      return;
    }
    const phase = key || main.dataset.open;
    for (const [name, section] of phases) section.hidden = name !== phase;
    for (const tab of tabs) {
      if (tab.dataset.phase === phase) tab.setAttribute('aria-current', 'true');
      else tab.removeAttribute('aria-current');
    }
    const section = phases.get(phase);
    await load(section);
    // A phase opens where the reader is, below the indicator they just used.
    if (anchor && !phases.has(anchor)) (document.getElementById(anchor) || section).scrollIntoView();
  }

  addEventListener('hashchange', () => show(location.hash));
  show(location.hash);
})();
