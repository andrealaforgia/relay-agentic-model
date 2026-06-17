#!/usr/bin/env node
// Persistence chokepoint for the engagement ledger.
// Both writers go through here: the between-runs driver (Owner gate messages)
// and the workflow (its returned relay messages). Rules come from topology.json,
// the single source of truth shared with orchestrator.workflow.js.
//
// Usage:
//   node ledger.mjs count                      -> next seq (= current message count); pass as args.seqStart
//   node ledger.mjs append '<json message>'    -> validate + append one message (Owner gates)
//   node ledger.mjs append-batch <file.json>   -> validate + append a run's returned `messages` array
//   node ledger.mjs verify                      -> re-validate the whole ledger (topology, vocab, seq order)
//   node ledger.mjs show                        -> human-readable replay

import { readFileSync, writeFileSync, existsSync, appendFileSync } from 'node:fs'

const HERE = new URL('.', import.meta.url)
const TOPO = JSON.parse(readFileSync(new URL('topology.json', HERE), 'utf8'))
const LEDGER = new URL('ledger/ledger.jsonl', HERE)

const idx = (n) => TOPO.chain.indexOf(n)
const adjacent = (a, b) => idx(a) !== -1 && idx(b) !== -1 && Math.abs(idx(a) - idx(b)) === 1

function validate(m) {
  if (!adjacent(m.from, m.to)) throw new Error(`topology violation: ${m.from} may not speak to ${m.to}`)
  const key = `${m.from}>${m.to}`
  const allowed = TOPO.allowed[key]
  if (!allowed || !allowed.includes(m.type)) throw new Error(`vocabulary violation: '${m.type}' not allowed on edge ${key}`)
}

function lines() {
  if (!existsSync(LEDGER)) return []
  return readFileSync(LEDGER, 'utf8').split('\n').filter(Boolean)
}
const count = () => lines().length

function write(m) {
  const out = {
    seq: m.seq != null ? m.seq : count(),
    from: m.from,
    to: m.to,
    type: m.type,
    body: typeof m.body === 'string' ? m.body : JSON.stringify(m.body),
    refs: m.refs || [],
    in_reply_to: m.in_reply_to != null ? m.in_reply_to : null,
  }
  appendFileSync(LEDGER, JSON.stringify(out) + '\n')
  return out
}

const [cmd, arg] = process.argv.slice(2)

try {
  dispatch(cmd, arg)
} catch (e) {
  console.error(`rejected: ${e.message}`)
  process.exit(1)
}

function dispatch(cmd, arg) {
if (cmd === 'count') {
  console.log(count())
} else if (cmd === 'append') {
  const m = JSON.parse(arg)
  validate(m)
  const out = write(m)
  console.log(`#${out.seq} ${out.from}>${out.to} [${out.type}]`)
} else if (cmd === 'append-batch') {
  const arr = JSON.parse(readFileSync(arg, 'utf8'))
  const msgs = Array.isArray(arr) ? arr : arr.messages
  if (!Array.isArray(msgs)) throw new Error('append-batch expects a JSON array, or an object with a `messages` array')
  const base = count()
  msgs.forEach((m, i) => {
    validate(m)
    if (m.seq == null) m.seq = base + i
  })
  msgs.forEach(write)
  console.log(`appended ${msgs.length}; ledger now ${count()} messages`)
} else if (cmd === 'verify') {
  let prev = -1
  let ok = true
  lines().forEach((l, i) => {
    const m = JSON.parse(l)
    try {
      validate(m)
    } catch (e) {
      ok = false
      console.error(`line ${i}: ${e.message}`)
    }
    if (m.seq !== prev + 1) {
      ok = false
      console.error(`line ${i}: seq gap/disorder (got ${m.seq}, expected ${prev + 1})`)
    }
    prev = m.seq
  })
  console.log(ok ? `OK: ${count()} messages, topology + vocabulary + sequence intact` : 'FAILED')
  if (!ok) process.exit(1)
} else if (cmd === 'show') {
  lines().forEach((l) => {
    const m = JSON.parse(l)
    console.log(`#${m.seq} ${m.from} > ${m.to} [${m.type}]${m.refs && m.refs.length ? ' {' + m.refs.join(',') + '}' : ''}\n    ${m.body.replace(/\n/g, '\n    ')}`)
  })
} else {
  console.error('usage: ledger.mjs count | append <json> | append-batch <file> | verify | show')
  process.exit(1)
}
}
