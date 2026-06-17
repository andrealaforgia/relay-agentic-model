export const meta = {
  name: 'edd-relay',
  description: 'Human-gated EDD relay (Owner > Interpreter > Analyst > Examiner > Builder). mode:"roadmap" slices a problem into potentially shippable iterations for Owner approval; mode:"iteration" drives one iteration to a shippable increment. Every message is recorded in an auditable ledger that spans all runs.',
  whenToUse: 'mode:"roadmap" to plan and get Owner approval; mode:"iteration" to deliver one increment. The Owner gates (validate roadmap, per-iteration feedback + continue?) happen conversationally BETWEEN runs.',
  phases: [
    { title: 'Roadmap', detail: 'Interpreter slices the problem into ordered, potentially shippable iterations' },
    { title: 'Specify', detail: 'Analyst frames each behaviour; Examiner authors expectations' },
    { title: 'Build-Verify', detail: 'Examiner <-> Builder EDD loop: expectations -> evidence -> judgement' },
    { title: 'Deliver', detail: 'Interpreter packages the shippable increment and asks the Owner whether to continue' },
  ],
}

// ---------------------------------------------------------------------------
// TOPOLOGY  --  the rules live in topology.json (single source of truth) and
// are passed in via args.topology by the runner. The inline default keeps this
// file self-contained for a quick standalone run; topology.json wins when given.
// ---------------------------------------------------------------------------
const TOPOLOGY = (args && args.topology) || {
  chain: ['owner', 'interpreter', 'analyst', 'examiner', 'builder'],
  allowed: {
    'owner>interpreter': ['problem', 'clarification', 'roadmap-verdict', 'feedback', 'decision'],
    'interpreter>owner': ['roadmap', 'increment', 'continue-query', 'result', 'question'],
    'interpreter>analyst': ['behaviour-to-implement', 'clarification'],
    'analyst>interpreter': ['question', 'behaviour-status'],
    'analyst>examiner': ['behaviour'],
    'examiner>analyst': ['behaviour-status'],
    'examiner>builder': ['expectation', 'verdict'],
    'builder>examiner': ['evidence'],
  },
}
const CHAIN = TOPOLOGY.chain
const ALLOWED = TOPOLOGY.allowed

function adjacent(a, b) {
  const i = CHAIN.indexOf(a)
  const j = CHAIN.indexOf(b)
  return i !== -1 && j !== -1 && Math.abs(i - j) === 1
}

// ---------------------------------------------------------------------------
// LEDGER  --  append-only, in-memory, single-threaded. Seeded from args.seqStart
// so numbering continues across runs. Returned at the end; the runner persists
// it to ledger/ledger.jsonl via ledger.mjs. This central append() enforces
// topology + per-edge vocabulary for every message this run produces.
// ---------------------------------------------------------------------------
const ledger = []
let seq = (args && args.seqStart) || 0

function append({ from, to, type, body, refs = [], in_reply_to = null }) {
  if (!adjacent(from, to)) {
    throw new Error(`topology violation: ${from} may not speak to ${to}`)
  }
  const key = `${from}>${to}`
  if (!ALLOWED[key] || !ALLOWED[key].includes(type)) {
    throw new Error(`vocabulary violation: '${type}' is not allowed on edge ${key}`)
  }
  const msg = {
    seq: seq++,
    from,
    to,
    type,
    body: typeof body === 'string' ? body : JSON.stringify(body),
    refs,
    in_reply_to,
  }
  ledger.push(msg)
  return msg
}

// ---------------------------------------------------------------------------
// EDGE-LOCKED PROMPTS  --  each agent is told its two neighbours and nothing
// about the rest of the chain. Edit prompts here; this file is the source of
// truth for them.
// ---------------------------------------------------------------------------
const PROMPTS = {
  roadmap: (problem, ownerFeedback, prior) => `You are the INTERPRETER in a relay chain. You speak with exactly two parties:
the PROBLEM OWNER (a human, on your left) and the ANALYST (on your right). Right now you are facing the Owner.

Produce a ROADMAP: slice the Owner's problem into a short, ORDERED list of ITERATIONS. Each iteration must
deliver a POTENTIALLY SHIPPABLE INCREMENT — a thin vertical slice that is demonstrable and useful on its own,
NOT a horizontal layer (no "iteration 1: the database"). Order by value and risk: the earliest iterations
should prove the riskiest assumptions and deliver the most value first. For each iteration give: a goal, the
shippable increment the Owner will be able to see/use at its end, and the discrete BEHAVIOURS it contains.
Keep it lean — prefer fewer, genuinely shippable slices. No code, tests, or technology choices. Surface any
assumption you had to make.

OWNER'S PROBLEM:
${problem}
${ownerFeedback ? `\nThe Owner reviewed your PREVIOUS roadmap and asked you to revise it. Their feedback:\n${ownerFeedback}\n\nPREVIOUS ROADMAP (revise it, don't start from scratch):\n${prior}` : ''}`,

  analyst: (behaviour) => `You are the ANALYST in a relay chain. You speak with exactly two parties:
the INTERPRETER (on your left) and the EXAMINER (on your right). You never speak to anyone else.

The Interpreter handed you one BEHAVIOUR TO IMPLEMENT. Sharpen it into a single crisp BEHAVIOUR
for the Examiner: unambiguous, observable, and free of solution detail. Add the minimal context
(inputs, actors, boundaries) the Examiner needs to author expectations. Still NO code, tests,
or technology choices — you describe *what is true when the behaviour holds*, not how.

BEHAVIOUR TO IMPLEMENT:
${behaviour}`,

  examinerSpec: (behaviour) => `You are the EXAMINER in a relay chain practising Expectation-Driven Development.
You speak with exactly two parties: the ANALYST (on your left) and the BUILDER (on your right).

The Analyst handed you one BEHAVIOUR. Author a small set of EXPECTATIONS for the Builder:
plain-language statements of what the system should do, including the relational and edge-case
nuance that formal tests struggle to capture (e.g. "when the cart has multiple items, the total
reflects the sum of price x quantity for every item"). Each expectation must be checkable by
EVIDENCE. Do not write code or tests yourself. 3-6 expectations is typical.

BEHAVIOUR:
${behaviour}`,

  builder: (expectations, history) => `You are the BUILDER in a relay chain. You speak with exactly one party:
the EXAMINER (on your left). You receive EXPECTATIONS and you respond only with EVIDENCE.

Implement a solution in the current working directory that satisfies the OUTSTANDING EXPECTATIONS
below. You do NOT need to write automated tests — Expectation-Driven Development governs correctness.
For every expectation, produce EVIDENCE that it now holds. Strongly prefer EXECUTED evidence: run the
code and capture the real command + real output. Use GENERATIVE evidence (a narration of what would
happen) only when execution is genuinely impossible, and label it as such.

OUTSTANDING EXPECTATIONS:
${expectations.map((e, i) => `  E${i + 1}. ${e}`).join('\n')}
${history ? `\nEXAMINER FEEDBACK FROM THE PREVIOUS ROUND:\n${history}` : ''}`,

  examinerJudge: (expectations, evidence) => `You are the EXAMINER judging the Builder's EVIDENCE against the
EXPECTATIONS you set. Be a critical editor, not a cheerleader: challenge gaps, demand executed evidence
where the Builder only narrated, and mark an expectation 'satisfied' only when the evidence convincingly
shows it holds. Set behaviour_status to 'satisfied' only if every expectation is satisfied; otherwise
'needs_work' and say precisely what the Builder must address next.

EXPECTATIONS:
${expectations.map((e, i) => `  E${i + 1}. ${e}`).join('\n')}

BUILDER'S EVIDENCE:
${evidence}`,

  delivery: (iteration, summary) => `You are the INTERPRETER reporting to the Problem Owner (the human) at the END of an
iteration. Speak in the Owner's terms. Describe the POTENTIALLY SHIPPABLE INCREMENT now delivered: what the
Owner can concretely see or do, grounded in the evidence the Examiner accepted — no code dumps, no downstream
jargon. State any caveats and whether anything learned this iteration should reshape the remaining roadmap.
Then ask, plainly and explicitly, whether to CONTINUE to the next iteration or STOP.

ITERATION GOAL:
${iteration.goal}
INTENDED INCREMENT:
${iteration.increment}

BEHAVIOUR OUTCOMES THIS ITERATION:
${summary}`,
}

// ---------------------------------------------------------------------------
// STRUCTURED OUTPUT SCHEMAS
// ---------------------------------------------------------------------------
const S_ROADMAP = {
  type: 'object',
  required: ['iterations'],
  properties: {
    iterations: {
      type: 'array',
      items: {
        type: 'object',
        required: ['id', 'goal', 'increment', 'behaviours'],
        properties: {
          id: { type: 'string' },
          goal: { type: 'string' },
          increment: { type: 'string', description: 'the potentially shippable increment delivered at the end of this iteration' },
          behaviours: {
            type: 'array',
            items: {
              type: 'object',
              required: ['id', 'statement'],
              properties: { id: { type: 'string' }, statement: { type: 'string' } },
            },
          },
        },
      },
    },
    assumptions: { type: 'array', items: { type: 'string' } },
  },
}

const S_ANALYST = {
  type: 'object',
  required: ['statement'],
  properties: { statement: { type: 'string' }, context: { type: 'string' } },
}

const S_SPEC = {
  type: 'object',
  required: ['expectations'],
  properties: {
    expectations: {
      type: 'array',
      items: {
        type: 'object',
        required: ['id', 'statement'],
        properties: {
          id: { type: 'string' },
          statement: { type: 'string' },
          rationale: { type: 'string' },
        },
      },
    },
  },
}

const S_BUILD = {
  type: 'object',
  required: ['evidence'],
  properties: {
    changes: { type: 'array', items: { type: 'string' } },
    evidence: {
      type: 'array',
      items: {
        type: 'object',
        required: ['expectation_id', 'kind', 'narrative'],
        properties: {
          expectation_id: { type: 'string' },
          kind: { type: 'string', enum: ['executed', 'generative'] },
          narrative: { type: 'string' },
          command: { type: 'string' },
          output: { type: 'string' },
        },
      },
    },
  },
}

const S_JUDGE = {
  type: 'object',
  required: ['verdicts', 'behaviour_status'],
  properties: {
    verdicts: {
      type: 'array',
      items: {
        type: 'object',
        required: ['expectation_id', 'status', 'reason'],
        properties: {
          expectation_id: { type: 'string' },
          status: { type: 'string', enum: ['satisfied', 'unmet'] },
          reason: { type: 'string' },
        },
      },
    },
    behaviour_status: { type: 'string', enum: ['satisfied', 'needs_work'] },
    feedback: { type: 'string' },
  },
}

const S_DELIVERY = {
  type: 'object',
  required: ['increment_summary', 'continue_question'],
  properties: {
    increment_summary: { type: 'string' },
    caveats: { type: 'array', items: { type: 'string' } },
    roadmap_impact: { type: 'string' },
    continue_question: { type: 'string' },
  },
}

// ---------------------------------------------------------------------------
// One iteration's relay: behaviours-to-implement -> Analyst -> Examiner spec
// -> Examiner<->Builder EDD loop. Sequential per behaviour so concurrent
// Builders never fight over files. Returns per-behaviour outcomes.
// ---------------------------------------------------------------------------
async function runBehaviour(b, maxRounds, tag) {
  phase('Specify')
  const analystOut = await agent(PROMPTS.analyst(b.statement), {
    label: `analyst:${tag}:${b.id}`, phase: 'Specify', schema: S_ANALYST,
  })
  const behaviour = analystOut.context ? `${analystOut.statement}\n\nContext: ${analystOut.context}` : analystOut.statement
  append({ from: 'analyst', to: 'examiner', type: 'behaviour', body: behaviour, refs: [b.id] })

  const spec = await agent(PROMPTS.examinerSpec(behaviour), {
    label: `examiner:spec:${tag}:${b.id}`, phase: 'Specify', schema: S_SPEC,
  })
  for (const e of spec.expectations) {
    append({ from: 'examiner', to: 'builder', type: 'expectation', body: e.statement, refs: [b.id, e.id] })
  }

  phase('Build-Verify')
  let outstanding = spec.expectations.map((e) => e.statement)
  let status = 'needs_work'
  let feedback = ''
  let round = 0
  while (status === 'needs_work' && round < maxRounds) {
    round++
    const build = await agent(PROMPTS.builder(outstanding, feedback), {
      label: `builder:${tag}:${b.id}:r${round}`, phase: 'Build-Verify', schema: S_BUILD,
    })
    const evidenceLines = []
    for (const ev of build.evidence) {
      const rendered = `[${ev.kind}] ${ev.narrative}${ev.command ? `\n$ ${ev.command}` : ''}${ev.output ? `\n${ev.output}` : ''}`
      append({ from: 'builder', to: 'examiner', type: 'evidence', body: rendered, refs: [ev.expectation_id] })
      evidenceLines.push(`${ev.expectation_id}: ${rendered}`)
    }
    const judge = await agent(PROMPTS.examinerJudge(outstanding, evidenceLines.join('\n\n')), {
      label: `examiner:judge:${tag}:${b.id}:r${round}`, phase: 'Build-Verify', schema: S_JUDGE,
    })
    for (const v of judge.verdicts) {
      append({ from: 'examiner', to: 'builder', type: 'verdict', body: `${v.status}: ${v.reason}`, refs: [v.expectation_id] })
    }
    status = judge.behaviour_status
    feedback = judge.feedback || ''
    const unmet = new Set(judge.verdicts.filter((v) => v.status === 'unmet').map((v) => v.expectation_id))
    if (unmet.size > 0) {
      outstanding = spec.expectations.filter((e) => unmet.has(e.id)).map((e) => e.statement)
      if (outstanding.length === 0) outstanding = spec.expectations.map((e) => e.statement)
    }
    log(`[${tag}] behaviour ${b.id} round ${round}: ${status}`)
  }
  append({ from: 'examiner', to: 'analyst', type: 'behaviour-status', body: `${status} after ${round} round(s)`, refs: [b.id] })
  return { id: b.id, statement: b.statement, status, rounds: round }
}

// ---------------------------------------------------------------------------
// ENTRY  --  one of two modes per run. The Owner gates between runs.
// ---------------------------------------------------------------------------
const mode = (args && args.mode) || 'roadmap'

if (mode === 'roadmap') {
  // -------- RUN TYPE A: produce a roadmap for the Owner to validate ---------
  const problem = args && args.problem
  if (!problem) throw new Error('roadmap mode needs args.problem')
  phase('Roadmap')
  const prior = args.priorRoadmap ? JSON.stringify(args.priorRoadmap, null, 2) : ''
  const planned = await agent(PROMPTS.roadmap(problem, args.ownerFeedback, prior), {
    label: 'interpreter:roadmap', phase: 'Roadmap', schema: S_ROADMAP,
  })
  const rendered = planned.iterations
    .map((it, i) => `${it.id || `I${i + 1}`}. ${it.goal}\n   ships: ${it.increment}\n   behaviours: ${it.behaviours.map((b) => b.statement).join('; ')}`)
    .join('\n')
  append({ from: 'interpreter', to: 'owner', type: 'roadmap', body: rendered })
  return { mode, roadmap: planned, messages: ledger }
}

if (mode === 'iteration') {
  // -------- RUN TYPE B: deliver ONE potentially shippable increment ---------
  const roadmap = args && args.roadmap
  const k = (args && args.iterationIndex) || 0
  if (!roadmap || !roadmap.iterations || !roadmap.iterations[k]) {
    throw new Error('iteration mode needs args.roadmap and a valid args.iterationIndex')
  }
  const maxRounds = (args && args.maxRounds) || 3
  const it = roadmap.iterations[k]
  const tag = it.id || `I${k + 1}`

  // Interpreter forwards this iteration's behaviours down the chain.
  for (const b of it.behaviours) {
    append({ from: 'interpreter', to: 'analyst', type: 'behaviour-to-implement', body: b.statement, refs: [b.id] })
  }
  log(`[${tag}] ${it.behaviours.length} behaviour(s) this iteration`)

  const outcomes = []
  for (const b of it.behaviours) {
    outcomes.push(await runBehaviour(b, maxRounds, tag))
  }

  // Status flows back up; Interpreter packages the increment and asks the Owner.
  phase('Deliver')
  const summary = outcomes.map((o) => `- [${o.status}] ${o.statement} (${o.rounds} round(s))`).join('\n')
  append({ from: 'analyst', to: 'interpreter', type: 'behaviour-status', body: summary, refs: [tag] })
  const delivery = await agent(PROMPTS.delivery(it, summary), {
    label: `interpreter:deliver:${tag}`, phase: 'Deliver', schema: S_DELIVERY,
  })
  const incrementBody = delivery.increment_summary +
    (delivery.caveats && delivery.caveats.length ? `\n\nCaveats:\n- ${delivery.caveats.join('\n- ')}` : '') +
    (delivery.roadmap_impact ? `\n\nRoadmap impact: ${delivery.roadmap_impact}` : '')
  append({ from: 'interpreter', to: 'owner', type: 'increment', body: incrementBody, refs: [tag] })
  append({ from: 'interpreter', to: 'owner', type: 'continue-query', body: delivery.continue_question, refs: [tag] })

  const allSatisfied = outcomes.every((o) => o.status === 'satisfied')
  return { mode, iteration: tag, increment: delivery, outcomes, allSatisfied, messages: ledger }
}

throw new Error(`unknown mode '${mode}' (expected 'roadmap' or 'iteration')`)
