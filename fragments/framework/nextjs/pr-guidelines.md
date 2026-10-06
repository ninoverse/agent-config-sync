---
title: Route table
scope: on-demand
when: Opening PRs
---

A PR that adds a route, or changes how one renders, carries the route's lines
from `pnpm build`'s route table in its description, after *Testing*:

```markdown
## Routes

| Route | Before | After |
|-------|--------|-------|
| `/blog/[slug]` | — | ● from `generateStaticParams` |
| `/account` | ○ | ƒ: reads `cookies()` |
```

The symbols are the build's own. ○ is prerendered as static content, ● is
prerendered from `generateStaticParams`, ◐ is a static shell with dynamic parts
streamed in, and ƒ is rendered on every request.

A route that moves to ƒ says why, in its row. It now needs a server for every
visit, and a static export (`output: 'export'`) can no longer build it.
