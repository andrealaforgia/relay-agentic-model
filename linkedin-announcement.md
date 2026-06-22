🤖 I just watched a video game get built end-to-end without writing a line of code myself — and without one all-knowing AI doing everything.

Instead, I split the work across a small team of specialized AI agents that can ONLY talk to their immediate neighbour. Here's the method 👇

THE CHAIN
👤 Problem Owner (me) → 🗣️ Interpreter → 🧭 Analyst → ✅ Examiner → 🔨 Builder

Each role has one job and may only speak to the agent on its left and right:
• Interpreter talks to me in plain language — needs, never tech.
• Analyst turns those needs into observable behaviours.
• Examiner turns behaviours into expectations and judges the evidence.
• Builder writes the actual code and reports only what now works.

Why the strict neighbours-only rule? It forces clean abstraction boundaries. Implementation detail physically cannot leak up to the human; the human's problem framing cannot leak down into code. Every handoff is a translation — and every translation gets checked.

The engine underneath is Expectation-Driven Development. The Examiner writes plain-language expectations ("the piece falls one cell per tick"), and the Builder must return EXECUTED evidence — real runs, real screenshots, real pixel reads — proving each one holds. The surprise: the code can ship with zero unit tests. The expectations plus the evidence ARE the proof.

Everything is auditable. Every message is one line in an append-only ledger AND a file in a mailbox. You can replay the whole conversation, message by message, and trace exactly how a decision travelled from "I want a 3D Tetris" down to a specific commit.

There's also a 5th agent OUTSIDE the chain: 🛡️ the Sentinel — a Communication Auditor that reads the entire ledger, flags when any agent breaks its contract (e.g. the Builder leaking file names upward), and can message the offending agent directly to keep the team honest. And it earns its keep: mid-run it caught the Builder leaking code internals upward and nudged the Interpreter back to problem-level language — things one mega-prompt would never surface.

Under the hood, each agent is its own AI session in its own window. A tiny dispatcher watches the ledger and wakes an agent only when it has work — so they sit idle (and cost nothing) until needed, then spring to life.

The test drive? The swarm built "ThreeDeeBlocks" — a 3D Tetris clone compiled to WebAssembly — across 20+ behaviours, autonomously, leaving a complete, tamper-evident trail of every expectation, every piece of evidence, and every course-correction along the way.

The big idea isn't a smarter agent. It's a TEAM of narrow agents communicating under strict, auditable contracts. Specialization + clean boundaries + a paper trail you can actually inspect.

It changes the human's job too: I stopped writing code and started stating problems and approving increments — the editor, not the author.

Would you trust a swarm like this on your codebase? 👇

#AI #ArtificialIntelligence #SoftwareEngineering #SoftwareDevelopment
