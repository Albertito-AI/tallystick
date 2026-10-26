/** Independent settlement evaluator for the v0.1 bounded contract.
 * Copyright 2026 Albert Tan Sin Hon. Apache-2.0.
 * Receives one {market,facts,as_of} object, or an array of such objects, on stdin.
 * It deliberately does not import or execute the Python implementation.
 */
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const states = new Map([
  ['provisional', 0], ['corroborated', 1], ['official', 2], ['final', 3],
]);
const metrics = new Set(['corner.awarded', 'goal.scored']);
const stamp = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?Z$/;

function utcMicros(text) {
  if (typeof text !== 'string') throw new Error('timestamp must be a UTC string');
  const m = stamp.exec(text);
  if (!m) throw new Error('timestamp must use the UTC Z form');
  const [year, month, day, hour, minute, second] = m.slice(1, 7).map(Number);
  const check = new Date(0);
  check.setUTCFullYear(year, month - 1, day);
  check.setUTCHours(hour, minute, second, 0);
  const millis = check.getTime();
  if (!Number.isFinite(millis) || year < 1 || month < 1 || month > 12 ||
      check.getUTCFullYear() !== year || check.getUTCMonth() !== month - 1 ||
      check.getUTCDate() !== day || check.getUTCHours() !== hour ||
      check.getUTCMinutes() !== minute || check.getUTCSeconds() !== second) {
    throw new Error('invalid UTC timestamp');
  }
  return BigInt(millis) * 1000n + BigInt((m[7] || '').padEnd(6, '0'));
}

function validateMarket(market) {
  if (!market || typeof market !== 'object' || Array.isArray(market)) {
    throw new Error('market must be an object');
  }
  const s = market.settlement;
  if (typeof market.market_id !== 'string' || !market.market_id ||
      typeof market.event_id !== 'string' || !market.event_id || !s ||
      !metrics.has(s.fact_type) || !Number.isSafeInteger(s.period) ||
      s.period < 0 || s.period > 20 || !Number.isSafeInteger(s.threshold) || s.threshold < 1 ||
      !['official', 'final'].includes(s.min_state)) {
    throw new Error('invalid bounded settlement market');
  }
  utcMicros(market.correction_deadline);
}

function validateFact(fact) {
  if (!fact || typeof fact !== 'object' || Array.isArray(fact) ||
      fact.schema_version !== '0.1' || typeof fact.fact_id !== 'string' ||
      !fact.fact_id || typeof fact.observation_id !== 'string' || !fact.observation_id ||
      typeof fact.event_id !== 'string' || !fact.event_id ||
      !['corner.awarded', 'goal.scored', 'period.closed', 'event.abandoned'].includes(fact.kind) ||
      !Number.isSafeInteger(fact.period) || fact.period < 0 || fact.period > 20 ||
      !Number.isSafeInteger(fact.value) || fact.value < 0 || !states.has(fact.state) ||
      !Array.isArray(fact.source_ids) || fact.source_ids.length === 0 ||
      new Set(fact.source_ids).size !== fact.source_ids.length ||
      fact.source_ids.some(x => typeof x !== 'string' || !x) ||
      typeof fact.licence_id !== 'string' || !fact.licence_id ||
      !(fact.supersedes === null || typeof fact.supersedes === 'string') ||
      !(fact.reason === null || typeof fact.reason === 'string')) {
    throw new Error('invalid fact representation');
  }
  if (fact.kind === 'period.closed' ? !metrics.has(fact.metric) || fact.value > 100000 :
      fact.metric !== null || ![0, 1].includes(fact.value)) {
    throw new Error('invalid fact metric or value');
  }
  if (utcMicros(fact.occurred_at) > utcMicros(fact.received_at)) {
    throw new Error('fact received before its declared occurrence');
  }
  utcMicros(fact.correction_deadline);
}

function activeHistory(facts, asOf) {
  const ids = new Map();
  const latest = new Map();
  const visible = new Map();
  const visibleValueChanges = new Map();
  for (const fact of facts) {
    validateFact(fact);
    if (ids.has(fact.fact_id)) throw new Error('duplicate fact identity');
    const old = latest.get(fact.observation_id);
    if (!old) {
      if (fact.supersedes !== null) throw new Error('missing superseded fact');
    } else {
      if (fact.supersedes !== old.fact_id) throw new Error('branching fact history');
      for (const k of ['event_id', 'kind', 'period', 'subject', 'occurred_at',
        'metric', 'correction_deadline', 'licence_id']) {
        if (fact[k] !== old[k]) throw new Error('changed observation identity');
      }
      if (old.state === 'final') throw new Error('revision of final observation');
      if (utcMicros(fact.received_at) < utcMicros(old.received_at)) {
        throw new Error('revision received before predecessor');
      }
      if (fact.value !== old.value) {
        if (!fact.reason?.trim() ||
            utcMicros(fact.received_at) >= utcMicros(fact.correction_deadline)) {
          throw new Error('invalid correction');
        }
      } else if (states.get(fact.state) < states.get(old.state)) {
        throw new Error('unchanged revision cannot lower evidence state');
      }
    }
    if (fact.state === 'final' &&
        utcMicros(fact.received_at) < utcMicros(fact.correction_deadline)) {
      throw new Error('premature final state');
    }
    ids.set(fact.fact_id, fact);
    latest.set(fact.observation_id, fact);
    if (utcMicros(fact.received_at) <= asOf) {
      visible.set(fact.observation_id, fact);
      if (old && fact.value !== old.value) {
        visibleValueChanges.set(fact.observation_id, utcMicros(fact.received_at));
      }
    }
  }
  return { heads: [...visible.values()], valueChanges: visibleValueChanges };
}

export function evaluate({ market, facts, as_of }) {
  validateMarket(market);
  if (!Array.isArray(facts)) throw new Error('facts must be an array');
  const now = utcMicros(as_of ?? new Date().toISOString());
  const snapshot = activeHistory(facts, now);
  const eventFacts = snapshot.heads.filter(f => f.event_id === market.event_id);
  const s = market.settlement;
  const corners = eventFacts.filter(f => f.kind === s.fact_type && f.period === s.period);
  const closures = eventFacts.filter(f => f.kind === 'period.closed' &&
    f.metric === s.fact_type && f.period === s.period);
  const abandoned = eventFacts.filter(f => f.kind === 'event.abandoned');
  const relevant = [...corners, ...closures, ...abandoned];
  const ids = relevant.map(f => f.fact_id).sort();
  const result = (status, outcome, count, reasons, factIds = ids) => ({
    market_id: market.market_id, status, outcome, count, reasons, fact_ids: factIds,
  });
  const pending = reason => result('pending', null, null, [reason]);
  if (eventFacts.length === 0) return result('pending', null, null, ['no_event_facts'], []);
  if (relevant.some(f => utcMicros(f.correction_deadline) !== utcMicros(market.correction_deadline))) {
    return pending('correction_deadline_mismatch');
  }
  const confirmedAbandonment = abandoned.filter(f => f.value === 1 && states.get(f.state) >= 2);
  if (confirmedAbandonment.length) {
    return result('void', null, null, ['event_abandoned'],
      confirmedAbandonment.map(f => f.fact_id).sort());
  }
  if (abandoned.some(f => f.value === 1 && states.get(f.state) < 2)) {
    return pending('unconfirmed_abandonment');
  }
  if (closures.length === 0) return pending('missing_closure');
  if (closures.length !== 1) return pending('ambiguous_closure');
  const required = states.get(s.min_state);
  if (states.get(closures[0].state) < required) return pending('insufficient_closure_state');
  if (corners.some(f => states.get(f.state) < required)) return pending('insufficient_fact_state');
  const count = corners.reduce((sum, f) => sum + f.value, 0);
  if (count !== closures[0].value) return pending('closure_count_mismatch');
  const closedAt = utcMicros(closures[0].received_at);
  // Track visible value changes independently while folding the history. Equal
  // totals can conceal offsetting corrections; later promotions do not erase them.
  if (corners.some(f => snapshot.valueChanges.has(f.observation_id) &&
      snapshot.valueChanges.get(f.observation_id) > closedAt)) {
    return pending('stale_closure');
  }
  return result('settled', count >= s.threshold ? 'over' : 'under', count, [],
    [...corners, closures[0]].map(f => f.fact_id).sort());
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    const raw = readFileSync(0, 'utf8');
    if (Buffer.byteLength(raw) > 16 * 1024 * 1024) throw new Error('input too large');
    const data = JSON.parse(raw);
    const output = Array.isArray(data) ? data.map(evaluate) : evaluate(data);
    process.stdout.write(`${JSON.stringify(output)}\n`);
  } catch (error) {
    process.stderr.write(`conformance error: ${error.message}\n`);
    process.exitCode = 2;
  }
}
