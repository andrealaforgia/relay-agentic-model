#!/usr/bin/env node
// Filesystem mailbox relay for the EDD working model.
// Each agent runs in its own Claude session on the same machine and talks to its
// neighbours ONLY through this CLI. All state is plain files you can inspect:
//
//   relay/ledger.jsonl              append-only audit trail (single source of truth)
//   relay/mailbox/<role>/inbox/     messages waiting for <role>, one JSON file each
//   relay/mailbox/<role>/done/      messages <role> has processed (ack moves them here)
//   relay/.seq.lock                 mkdir lock guarding seq-assign + append + drop
//
// Rules (adjacency + per-edge vocabulary) live in relay/topology.json and are
// enforced here on every send — the single chokepoint, exactly like the old append().
//
// Commands:
//   node relay/relay.mjs init
//   node relay/relay.mjs send --as <role> --to <role> --type <type> [--body "..."|--body-file F|-] [--refs a,b] [--reply <seq>]
//   node relay/relay.mjs inbox --as <role>            list pending messages
//   node relay/relay.mjs next  --as <role>            print the oldest pending message (JSON)
//   node relay/relay.mjs ack   --as <role> --seq <n>  move that message to done/
//   node relay/relay.mjs show                         human-readable replay of the ledger
//   node relay/relay.mjs verify                       re-check topology, vocabulary, sequence

import { readFileSync, writeFileSync, existsSync, appendFileSync, mkdirSync, rmdirSync, readdirSync, renameSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const HERE = new URL('.', import.meta.url)
const p = (rel) => fileURLToPath(new URL(rel, HERE))
const TOPO = JSON.parse(readFileSync(p('topology.json'), 'utf8'))
const LEDGER = p('ledger.jsonl')
const LOCK = p('.seq.lock')
const ROLES = TOPO.mailboxRoles

const idx = (n) => TOPO.chain.indexOf(n)
const adjacent = (a, b) => idx(a) !== -1 && idx(b) !== -1 && Math.abs(idx(a) - idx(b)) === 1

function validate(from, to, type) {
  if (!adjacent(from, to)) throw new Error(`topology violation: ${from} may not speak to ${to}`)
  const key = `${from}>${to}`
  const allowed = TOPO.allowed[key]
  if (!allowed || !allowed.includes(type)) throw new Error(`vocabulary violation: '${type}' is not allowed on edge ${key}`)
}

// ---- argument parsing ------------------------------------------------------
function parseArgs(argv) {
  const a = {}
  for (let i = 0; i < argv.length; i++) {
    if (argv[i].startsWith('--')) {
      const k = argv[i].slice(2)
      const v = argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[++i] : true
      a[k] = v
    } else if (argv[i] === '-') {
      a.stdin = true
    }
  }
  return a
}

// ---- lock ------------------------------------------------------------------
function sleep(ms) { Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms) }
function withLock(fn) {
  for (let i = 0; i < 400; i++) {
    try {
      mkdirSync(LOCK) // atomic create; throws EEXIST if held
      try { return fn() } finally { rmdirSync(LOCK) }
    } catch (e) {
      if (e.code === 'EEXIST') { sleep(25); continue }
      throw e
    }
  }
  throw new Error('could not acquire .seq.lock (held too long — is a send wedged?)')
}

// ---- ledger helpers --------------------------------------------------------
function ledgerLines() {
  if (!existsSync(LEDGER)) return []
  return readFileSync(LEDGER, 'utf8').split('\n').filter(Boolean)
}
const pad = (n) => String(n).padStart(4, '0')

function inboxDir(role) { return p(`mailbox/${role}/inbox`) }
function doneDir(role) { return p(`mailbox/${role}/done`) }

function pendingFiles(role) {
  const dir = inboxDir(role)
  if (!existsSync(dir)) return []
  return readdirSync(dir).filter((f) => f.endsWith('.json')).sort()
}

// ---- commands --------------------------------------------------------------
function cmdInit() {
  for (const r of ROLES) { mkdirSync(inboxDir(r), { recursive: true }); mkdirSync(doneDir(r), { recursive: true }) }
  if (!existsSync(LEDGER)) writeFileSync(LEDGER, '')
  console.log(`initialised relay for roles: ${ROLES.join(', ')}`)
}

function readBody(a) {
  if (a['body-file']) return readFileSync(a['body-file'], 'utf8')
  if (a.stdin || a.body === undefined) return readFileSync(0, 'utf8')
  return String(a.body)
}

function cmdSend(a) {
  const from = a.as, to = a.to, type = a.type
  if (!from || !to || !type) throw new Error('send needs --as <role> --to <role> --type <type>')
  validate(from, to, type)
  const body = readBody(a).replace(/\n+$/, '')
  const refs = a.refs ? String(a.refs).split(',').map((s) => s.trim()).filter(Boolean) : []
  const in_reply_to = a.reply !== undefined ? Number(a.reply) : null
  return withLock(() => {
    const seq = ledgerLines().length
    const msg = { seq, from, to, type, body, refs, in_reply_to }
    appendFileSync(LEDGER, JSON.stringify(msg) + '\n')
    // deliver into the recipient's inbox (owner has no mailbox — it's the human)
    if (ROLES.includes(to)) {
      mkdirSync(inboxDir(to), { recursive: true })
      writeFileSync(p(`mailbox/${to}/inbox/${pad(seq)}-${from}-${type}.json`), JSON.stringify(msg, null, 2))
    }
    console.log(`#${seq} ${from} > ${to} [${type}]${ROLES.includes(to) ? '' : ' (no mailbox: in-session)'}`)
    return msg
  })
}

function cmdInbox(a) {
  const role = a.as
  if (!role) throw new Error('inbox needs --as <role>')
  const files = pendingFiles(role)
  if (!files.length) { console.log(`(${role} inbox empty)`); return }
  for (const f of files) {
    const m = JSON.parse(readFileSync(p(`mailbox/${role}/inbox/${f}`), 'utf8'))
    const oneline = m.body.replace(/\n/g, ' ').slice(0, 80)
    console.log(`#${m.seq} from ${m.from} [${m.type}]${m.refs.length ? ' {' + m.refs.join(',') + '}' : ''}: ${oneline}`)
  }
}

function cmdNext(a) {
  const role = a.as
  if (!role) throw new Error('next needs --as <role>')
  const files = pendingFiles(role)
  if (!files.length) { console.log(JSON.stringify({ empty: true })); return }
  console.log(readFileSync(p(`mailbox/${role}/inbox/${files[0]}`), 'utf8'))
}

function cmdAck(a) {
  const role = a.as, seq = a.seq
  if (!role || seq === undefined) throw new Error('ack needs --as <role> --seq <n>')
  const want = pad(Number(seq)) + '-'
  const file = pendingFiles(role).find((f) => f.startsWith(want))
  if (!file) throw new Error(`no pending message #${seq} in ${role}'s inbox`)
  mkdirSync(doneDir(role), { recursive: true })
  renameSync(p(`mailbox/${role}/inbox/${file}`), p(`mailbox/${role}/done/${file}`))
  console.log(`acked #${seq} (${role})`)
}

function cmdShow() {
  for (const l of ledgerLines()) {
    const m = JSON.parse(l)
    console.log(`#${m.seq} ${m.from} > ${m.to} [${m.type}]${m.refs && m.refs.length ? ' {' + m.refs.join(',') + '}' : ''}\n    ${m.body.replace(/\n/g, '\n    ')}`)
  }
}

function cmdVerify() {
  let prev = -1, ok = true
  ledgerLines().forEach((l, i) => {
    const m = JSON.parse(l)
    try { validate(m.from, m.to, m.type) } catch (e) { ok = false; console.error(`line ${i}: ${e.message}`) }
    if (m.seq !== prev + 1) { ok = false; console.error(`line ${i}: seq gap/disorder (got ${m.seq}, expected ${prev + 1})`) }
    prev = m.seq
  })
  console.log(ok ? `OK: ${ledgerLines().length} messages, topology + vocabulary + sequence intact` : 'FAILED')
  if (!ok) process.exit(1)
}

// ---- dispatch --------------------------------------------------------------
const [cmd, ...rest] = process.argv.slice(2)
const a = parseArgs(rest)
try {
  switch (cmd) {
    case 'init': cmdInit(); break
    case 'send': cmdSend(a); break
    case 'inbox': cmdInbox(a); break
    case 'next': cmdNext(a); break
    case 'ack': cmdAck(a); break
    case 'show': cmdShow(); break
    case 'verify': cmdVerify(); break
    default:
      console.error('usage: relay.mjs init | send | inbox | next | ack | show | verify')
      process.exit(1)
  }
} catch (e) {
  console.error(`rejected: ${e.message}`)
  process.exit(1)
}
