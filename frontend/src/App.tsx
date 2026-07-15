import { FormEvent, useRef, useState } from 'react'

import { checkItem, FactsCheck, parseItem, ParseResponse } from './api'

function Value({ label, value }: { label: string; value: unknown }) {
  if (value === null || value === undefined || value === '') return null
  return <div><dt>{label}</dt><dd>{Array.isArray(value) ? value.join(', ') : String(value)}</dd></div>
}

export function Preview({ result }: { result: ParseResponse }) {
  const { item, warnings } = result
  return <section className="preview" aria-live="polite">
    {warnings.length > 0 && <aside className="warnings"><h2>Hinweise</h2><ul>{warnings.map(warning => <li key={warning.code}>{warning.message} {warning.lines.length > 0 && `(Zeilen ${warning.lines.join(', ')})`} <code>{warning.code}</code>{warning.raw_lines.length > 0 && <pre>{warning.raw_lines.join('\n')}</pre>}</li>)}</ul></aside>}
    <h2>Erkannte Struktur</h2>
    <dl className="facts">
      <Value label="Item Class" value={item.item_class}/><Value label="Rarity" value={item.rarity}/>
      <Value label="Name" value={item.name}/><Value label="Base Type" value={item.base_type}/>
      <Value label="Required Level" value={item.required_level}/><Value label="Required Str" value={item.required_strength}/>
      <Value label="Required Dex" value={item.required_dexterity}/><Value label="Required Int" value={item.required_intelligence}/>
      <Value label="Item Level" value={item.item_level}/><Value label="Quality" value={item.quality}/>
      <Value label="Armour" value={item.armour}/><Value label="Armour augmented" value={item.armour_augmented}/>
      <Value label="Evasion" value={item.evasion}/><Value label="Evasion augmented" value={item.evasion_augmented}/>
      <Value label="Energy Shield" value={item.energy_shield}/><Value label="Energy Shield augmented" value={item.energy_shield_augmented}/>
      <Value label="Spirit" value={item.spirit}/><Value label="Granted Skill" value={item.granted_skill}/>
      <Value label="Sockets" value={item.sockets}/><Value label="Identified" value={item.identified}/>
      <Value label="Corrupted" value={item.corrupted}/>
    </dl>
    <h3>Modifier</h3>
    {item.modifiers.length === 0 ? <p>Keine Modifier erkannt.</p> : <div className="mods">{item.modifiers.map((modifier, index) =>
      <article key={`${index}-${modifier.raw_text}`}><strong>{modifier.raw_text}</strong><p>{modifier.source} · {modifier.affix_type ?? 'kein Affix-Typ'} · {modifier.name ?? 'kein Name'} · {modifier.normalized_key}{modifier.tier !== null ? ` · Tier ${modifier.tier}` : ''}</p><p>Tags: {modifier.tags.join(', ') || '—'} · Werte: {modifier.values.join(', ') || '—'} · Roll ranges: {modifier.roll_ranges.map(range => range.join('–')).join(', ') || '—'}</p><p>Flags: crafted={String(modifier.crafted)}, desecrated={String(modifier.desecrated)}, rune={String(modifier.rune)}, implicit={String(modifier.implicit)}, unique={String(modifier.unique)}</p></article>)}</div>}
    <h3>Unbekannte Zeilen</h3>
    {item.unknown_lines.length ? <pre>{item.unknown_lines.join('\n')}</pre> : <p>Keine unbekannten Zeilen erhalten.</p>}
    <h3>Originaltext</h3><pre>{item.raw_text}</pre>
  </section>
}

export function App() {
  const [rawText, setRawText] = useState('')
  const [result, setResult] = useState<ParseResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [suggestionDraft, setSuggestionDraft] = useState<string | null>(null)
  const [needsReanalysis, setNeedsReanalysis] = useState(false)
  const activeRequest = useRef<AbortController | null>(null)
  const checkRequest = useRef<AbortController | null>(null)
  const submittedText = useRef<string | null>(null)
  const [factsCheck, setFactsCheck] = useState<FactsCheck | null>(null)
  const [checkError, setCheckError] = useState<string | null>(null)
  const [checking, setChecking] = useState(false)
  const [checkWarnings, setCheckWarnings] = useState<string[]>([])

  function edit(nextText: string) {
    activeRequest.current?.abort()
    checkRequest.current?.abort()
    checkRequest.current = null
    activeRequest.current = null
    submittedText.current = null
    setRawText(nextText)
    setResult(null)
    setError(null)
    setLoading(false)
    setSuggestionDraft(null)
    setNeedsReanalysis(false)
    setFactsCheck(null)
    setCheckError(null)
    setChecking(false)
    setCheckWarnings([])
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    activeRequest.current?.abort()
    checkRequest.current?.abort()
    checkRequest.current = null
    const controller = new AbortController()
    const submitted = rawText
    activeRequest.current = controller
    submittedText.current = submitted
    setResult(null)
    setSuggestionDraft(null)
    setError(null)
    setLoading(true)
    setFactsCheck(null)
    setCheckError(null)
    setCheckWarnings([])
    setChecking(false)
    try {
      const next = await parseItem(submitted, controller.signal)
      if (activeRequest.current === controller && submittedText.current === submitted) {
        setResult(next)
        setSuggestionDraft(next.line_break_suggestion?.suggested_text ?? null)
        setNeedsReanalysis(false)
      }
    } catch (reason) {
      if (!controller.signal.aborted && activeRequest.current === controller) {
        setResult(null)
        setError(reason instanceof Error ? reason.message : 'Unbekannter Fehler.')
      }
    } finally {
      if (activeRequest.current === controller) setLoading(false)
    }
  }

  function acceptSuggestion() {
    if (suggestionDraft === null) return
    activeRequest.current?.abort()
    activeRequest.current = null
    checkRequest.current?.abort()
    checkRequest.current = null
    submittedText.current = null
    setRawText(suggestionDraft)
    setSuggestionDraft(null)
    setResult(null)
    setError(null)
    setLoading(false)
    setNeedsReanalysis(true)
    setFactsCheck(null)
  }

  function discardSuggestion() {
    setSuggestionDraft(null)
  }

  async function runFactsCheck() {
    checkRequest.current?.abort()
    const controller = new AbortController()
    const submitted = rawText
    checkRequest.current = controller
    setFactsCheck(null)
    setCheckError(null)
    setChecking(true)
    try {
      const response = await checkItem(submitted, controller.signal)
      if (checkRequest.current === controller && rawText === submitted) {
        setFactsCheck(response.assessment)
        setCheckWarnings(response.parse.warnings.map(warning => `${warning.code}: ${warning.message}`))
      }
    } catch (reason) {
      if (!controller.signal.aborted && checkRequest.current === controller) {
        setCheckError(reason instanceof Error ? reason.message : 'Unbekannter Fehler.')
      }
    } finally {
      if (checkRequest.current === controller) setChecking(false)
    }
  }

  const parseComplete = result !== null && !result.warnings.some(warning => [
    'input_missing_line_breaks', 'missing_item_identity', 'no_modifiers_detected',
  ].includes(warning.code))

  return <main><p className="eyebrow">Manuelle Parse-Vorschau</p><h1>PoE 2 Gear &amp; Trade Checker</h1>
    <form onSubmit={submit}><label htmlFor="itemtext">Englischen Itemtext einfügen</label><textarea id="itemtext" value={rawText} onChange={event => edit(event.target.value)} rows={15}/><button disabled={loading}>{loading ? 'Analysiere …' : needsReanalysis ? 'Erneut analysieren' : 'Analysieren'}</button></form>
    {loading && <p role="status">Itemtext wird analysiert …</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {suggestionDraft !== null && <section className="suggestion" aria-labelledby="suggestion-heading" aria-live="polite"><h2 id="suggestion-heading">Sicherer Zeilenumbruch-Vorschlag</h2><p role="status">Nur eindeutig erkennbare Grenzen wurden ergänzt. Bitte prüfe und bearbeite den Entwurf vor einer erneuten Analyse.</p><label htmlFor="suggestion">Editierbarer Vorschlag</label><textarea id="suggestion" rows={15} value={suggestionDraft} onChange={event => setSuggestionDraft(event.target.value)}/><div className="actions"><button type="button" onClick={acceptSuggestion}>Vorschlag übernehmen</button><button type="button" onClick={discardSuggestion}>Verwerfen</button></div></section>}
    {result && <Preview result={result}/>} {parseComplete && <button type="button" onClick={runFactsCheck} disabled={checking}>{checking ? 'Prüfe Fakten …' : 'Faktencheck ausführen'}</button>}
    {checking && <p role="status">Lokaler Faktencheck läuft …</p>}
    {checkError && <p className="error" role="alert">{checkError}</p>}
    {!checking && factsCheck === null && checkWarnings.length > 0 && <aside className="warnings"><h2>Faktencheck nicht verfügbar</h2><ul>{checkWarnings.map(warning => <li key={warning}>{warning}</li>)}</ul></aside>}
    {factsCheck && <section className="facts-check"><h2>Lokaler Faktencheck</h2><p>{factsCheck.disclaimer}</p><h3>Item-Fakten</h3><dl className="facts"><Value label="Slot-Hinweis" value={factsCheck.facts.slot_hint}/><Value label="Item Level" value={factsCheck.facts.item_level}/><Value label="Required Level" value={factsCheck.facts.required_level}/><Value label="Required Str/Dex/Int" value={[factsCheck.facts.required_strength, factsCheck.facts.required_dexterity, factsCheck.facts.required_intelligence].map(value => value ?? '—')}/><Value label="Quality" value={factsCheck.facts.quality}/><Value label="Sockets" value={factsCheck.facts.sockets}/><Value label="Armour (augmented)" value={`${factsCheck.facts.armour ?? '—'} (${factsCheck.facts.armour_augmented})`}/><Value label="Evasion (augmented)" value={`${factsCheck.facts.evasion ?? '—'} (${factsCheck.facts.evasion_augmented})`}/><Value label="Energy Shield (augmented)" value={`${factsCheck.facts.energy_shield ?? '—'} (${factsCheck.facts.energy_shield_augmented})`}/><Value label="Spirit" value={factsCheck.facts.spirit}/><Value label="Granted Skill" value={factsCheck.facts.granted_skill}/><Value label="Identified / Corrupted" value={`${factsCheck.facts.identified} / ${factsCheck.facts.corrupted}`}/><Value label="Bekannte Modifier" value={factsCheck.facts.known_modifier_count}/><Value label="Unbekannte Modifier" value={factsCheck.facts.unknown_modifier_count}/></dl><div className="mods">{factsCheck.facts.modifiers.map((modifier, index) => <article key={`${index}-${modifier.raw_text}`}><strong>{modifier.raw_text}</strong><p>{modifier.source} · {modifier.affix_type ?? '—'} · {modifier.name ?? '—'} · Tier {modifier.tier ?? '—'} · Tags {modifier.tags.join(', ') || '—'}</p><p>{modifier.normalized_key} · Relevanz: {modifier.relevance ?? 'unbekannt'} · Regel: {modifier.config_rule ?? 'keine'}</p><p>Werte: {modifier.current_values.join(', ') || '—'} · Ranges: {modifier.roll_ranges.map(range => range.join('–')).join(', ') || '—'} · Rollposition: {modifier.roll_position === null ? '—' : modifier.roll_position.toFixed(2)}</p><p>Flags: crafted={String(modifier.crafted)}, desecrated={String(modifier.desecrated)}, rune={String(modifier.rune)}, implicit={String(modifier.implicit)}, unique={String(modifier.unique)}</p></article>)}</div><AssessmentPanel title="Lokale Verkaufsempfehlung" assessment={factsCheck.trade}/><AssessmentPanel title="Crafting" assessment={factsCheck.crafting}/>{factsCheck.warnings.length > 0 && <p>Warnungen: {factsCheck.warnings.join(', ')}</p>}</section>}</main>
}

function AssessmentPanel({ title, assessment }: { title: string; assessment: FactsCheck['trade'] }) {
  return <article><h3>{title}</h3><p>{assessment.outcome} · Confidence: {assessment.confidence}</p><ul>{assessment.confidence_reasons.map(reason => <li key={reason}>{reason}</li>)}{assessment.evidence.map(evidence => <li key={evidence.rule_id}><code>{evidence.rule_id}</code>: {evidence.message} ({evidence.matched_facts.join(', ')})</li>)}</ul></article>
}
