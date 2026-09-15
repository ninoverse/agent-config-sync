---
title: Behavioral guidelines
scope: always
---

**Maintain the Build:** Never leave the codebase in a state where build, lint,
or tests fail. Run the relevant commands in *Build and test commands* to verify
your work before concluding a task.

**Tradeoff:** Bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

- State your assumptions explicitly. If uncertain, stop and ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, propose it. Push back when warranted.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked. No abstractions for single-use code.
- No "flexibility" or error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

- Don't "improve" adjacent code, comments, or formatting.
- Match existing style exactly.
- Remove imports/variables/functions that YOUR changes made unused. Don't remove pre-existing dead code unless asked.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

- Transform tasks into verifiable goals (e.g., "Add validation" → "Write tests for invalid inputs, then make them pass").
- For multi-step tasks, state a brief plan and verify each step independently.
