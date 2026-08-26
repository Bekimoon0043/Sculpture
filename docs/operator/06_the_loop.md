# 06 — The loop: how to keep building LuxuryForm

**Who this is for:** you, in VS Code, with Claude Code open. No coding
background needed. This file explains the repeating cycle that moves the
platform forward one gated step at a time, and exactly what you type.

---

## The idea in one paragraph

The platform is built in **slices**. A slice is a chunk of work small enough
to finish, prove and commit in one sitting. Every slice runs through the same
five steps, in the same order, every time. That repetition is the point: it is
what stops an AI from wandering off, quietly inventing capability, or telling
you something works when it does not. You do not have to remember the rules —
the commands carry them.

---

## The five steps

Open the project folder in VS Code, open Claude Code, and type these. One at a
time. Wait for each to finish.

| # | You type | What happens | You do |
|---|---|---|---|
| 1 | `/lf-orient` | It reads the repo and tells you exactly where the build stands and what is next. It changes nothing. | Read it. Check it matches what you remember. |
| 2 | `/lf-next` | It plans the next slice: files, gate, costs, risks, and anything it thinks is wrong. It writes no code. | **Approve, correct, or reject.** This is your main decision point. |
| 3 | `/lf-build` | It writes the code and the tests. | Wait. If it reports a failure, that is it working correctly. |
| 4 | `/lf-gate` | It runs the gate and shows you the real output — PASS or FAIL. | Do the visual check it hands you. |
| 5 | `/lf-close` | It updates the docs, commits, pushes, and tells you what to run next time. | Read the handover. |

Then back to step 1 for the next slice.

**The one rule that makes this work:** never skip step 2 and never approve a
plan you do not understand. Ask it to explain any line. "Explain step 3 of that
plan to me as if I have never seen a CAD program" is a perfectly good reply, and
it will answer it.

---

## The other four commands, for when you need them

| You type | When |
|---|---|
| `/lf-broke` *(then paste the error)* | Anything fails — a build, a container, a red error in the terminal. It diagnoses from the real logs instead of guessing. |
| `/lf-spend` *(then say what you want to run)* | Before anything that costs money. It gives you the dollar figure and what it buys, and waits for your yes. |
| `/lf-drift` | Once a week. It regenerates the Hub status and finds places where the documentation has drifted away from what the code actually does. |
| *(no command — just ask)* | Anything else. The commands are shortcuts for the repeating work, not a cage. |

---

## What to expect, honestly

- **A FAIL at step 4 is normal and good.** The gate exists to catch things
  before you do. A slice that fails its gate twice and passes on the third try
  is a healthy slice. A slice that passes first time every time means the gate
  is too weak.
- **"I cannot do this" is a valid answer** and you should trust it more than an
  answer that sounds impressive. The rule in `CLAUDE.md` is that anything that
  cannot be done goes into `LIMITATIONS.md` and a real alternative gets built.
  Read `LIMITATIONS.md` occasionally; it is the most honest file in the repo.
- **Most work costs $0.** The offline gates, fixture replay and the whole Phase
  6 assembly core run without touching a paid API. Live money is spent only when
  a real design is produced, and only after `/lf-spend` shows you the number.

---

## Where "what is left" is written down

**`NEXT.md`**, in the root of the repository. Open it any time — it is written
in plain language. It has three parts:

1. **Blockers** — things only you can unblock. Right now the important one is
   signing off the numbers in `PHASE_6_SLICE_A_ENVELOPES.md`; no Phase 6 code
   gets written until you do, because those numbers decide what the machine
   believes your workshop can actually build.
2. **The work queue** — the slices, in order, each with its gate.
3. **Debts** — small honest problems, listed so they stay visible.

`/lf-close` rewrites this file at the end of every slice. If it ever disagrees
with what you have been told in chat, `NEXT.md` and the code are right and the
chat is wrong.

---

## If you only remember one thing

Type `/lf-orient` at the start of every session. Everything else follows from
what it tells you.
