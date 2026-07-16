import { FormEvent, useEffect, useRef, useState } from 'react'

import { checkItem, evaluateItem, EvaluateResponse, FactsCheck, loadEquipment, loadProfile, parseItem, ParseResponse, Profile, saveEquipment, saveProfile } from './api'

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
  const [aiResult, setAiResult] = useState<EvaluateResponse | null>(null)
  const [aiError, setAiError] = useState<string | null>(null)
  const [evaluating, setEvaluating] = useState(false)
  const aiRequest = useRef<AbortController | null>(null)
  const comparisonContext = useRef(0)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [equipmentSlot, setEquipmentSlot] = useState('wand')
  const [equipmentText, setEquipmentText] = useState('')
  const [managementMessage, setManagementMessage] = useState<string | null>(null)

  useEffect(() => {
    invalidateComparison()
  }, [managementMessage])

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
    aiRequest.current?.abort(); aiRequest.current = null
    setAiResult(null); setAiError(null); setEvaluating(false)
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    activeRequest.current?.abort()
    checkRequest.current?.abort()
    checkRequest.current = null
    aiRequest.current?.abort(); aiRequest.current = null
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
    setAiResult(null); setAiError(null); setEvaluating(false)
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
    aiRequest.current?.abort(); aiRequest.current = null
    submittedText.current = null
    setRawText(suggestionDraft)
    setSuggestionDraft(null)
    setResult(null)
    setError(null)
    setLoading(false)
    setNeedsReanalysis(true)
    setFactsCheck(null)
    setAiResult(null); setAiError(null); setEvaluating(false)
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

  async function runAiEvaluation() {
    aiRequest.current?.abort()
    const controller = new AbortController()
    const submitted = rawText
    const submittedSlot = equipmentSlot
    const submittedContext = comparisonContext.current
    aiRequest.current = controller
    setAiResult(null); setAiError(null); setEvaluating(true)
    try {
      const response = await evaluateItem(submitted, controller.signal, submittedSlot)
      if (aiRequest.current === controller && rawText === submitted && equipmentSlot === submittedSlot && comparisonContext.current === submittedContext) {
        setAiResult(response)
        setFactsCheck(response.local_check)
      }
    } catch (reason) {
      if (!controller.signal.aborted && aiRequest.current === controller) {
        setAiError(reason instanceof Error ? reason.message : 'Unbekannter Fehler.')
      }
    } finally {
      if (aiRequest.current === controller) setEvaluating(false)
    }
  }

  function invalidateComparison() {
    comparisonContext.current += 1
    aiRequest.current?.abort(); aiRequest.current = null
    setEvaluating(false); setAiResult(null); setAiError(null); setFactsCheck(null)
  }

  function changeEquipmentSlot(slot: string) {
    invalidateComparison()
    setEquipmentSlot(slot); setEquipmentText('')
  }

  const parseComplete = result !== null && !result.warnings.some(warning => [
    'input_missing_line_breaks', 'missing_item_identity', 'no_modifiers_detected',
  ].includes(warning.code))

  return <main onChangeCapture={invalidateComparison} onClickCapture={event => { const label = (event.target as HTMLElement).textContent; if (['Profil laden', 'Profil speichern', 'Slot laden', 'Slot speichern'].includes(label ?? '')) { invalidateComparison(); setManagementMessage('Management-Aktion läuft …') } }}><p className="eyebrow">Manuelle Parse-Vorschau</p><h1>PoE 2 Gear &amp; Trade Checker</h1>
    <section><h2>Profil und Equipment</h2><div className="actions"><button type="button" onClick={async () => { try { setProfile(await loadProfile()); setManagementMessage(null) } catch (reason) { setManagementMessage(String(reason)) } }}>Profil laden</button><button type="button" onClick={async () => { try { const data = await loadEquipment(); setEquipmentText(data.slots[equipmentSlot]?.item.raw_text ?? ''); setManagementMessage(null) } catch (reason) { setManagementMessage(String(reason)) } }}>Slot laden</button></div>{profile && <ProfileForm profile={profile} setProfile={setProfile} save={async () => { try { setProfile(await saveProfile(profile)); setManagementMessage('Profil gespeichert.') } catch (reason) { setManagementMessage(String(reason)) } }}/>}<label>Equipment-Slot<select value={equipmentSlot} onChange={event => changeEquipmentSlot(event.target.value)}>{['wand','focus','helmet','body_armour','gloves','boots','belt','ring_1','ring_2','amulet'].map(slot => <option key={slot}>{slot}</option>)}</select></label><label>Itemtext des Slots<textarea rows={8} value={equipmentText} onChange={event => setEquipmentText(event.target.value)}/></label><button type="button" onClick={async () => { try { await saveEquipment(equipmentSlot, equipmentText); setManagementMessage('Equipment gespeichert.') } catch (reason) { setManagementMessage(String(reason)) } }}>Slot speichern</button>{managementMessage && <p role="status">{managementMessage}</p>}</section>
    <form onSubmit={submit}><label htmlFor="itemtext">Englischen Itemtext einfügen</label><textarea id="itemtext" value={rawText} onChange={event => edit(event.target.value)} rows={15}/><button disabled={loading}>{loading ? 'Analysiere …' : needsReanalysis ? 'Erneut analysieren' : 'Analysieren'}</button></form>
    {loading && <p role="status">Itemtext wird analysiert …</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {suggestionDraft !== null && <section className="suggestion" aria-labelledby="suggestion-heading" aria-live="polite"><h2 id="suggestion-heading">Sicherer Zeilenumbruch-Vorschlag</h2><p role="status">Nur eindeutig erkennbare Grenzen wurden ergänzt. Bitte prüfe und bearbeite den Entwurf vor einer erneuten Analyse.</p><label htmlFor="suggestion">Editierbarer Vorschlag</label><textarea id="suggestion" rows={15} value={suggestionDraft} onChange={event => setSuggestionDraft(event.target.value)}/><div className="actions"><button type="button" onClick={acceptSuggestion}>Vorschlag übernehmen</button><button type="button" onClick={discardSuggestion}>Verwerfen</button></div></section>}
    {result && <Preview result={result}/>} {parseComplete && <div className="actions"><button type="button" onClick={runFactsCheck} disabled={checking}>{checking ? 'Prüfe Fakten …' : 'Faktencheck ausführen'}</button><button type="button" onClick={runAiEvaluation} disabled={evaluating}>{evaluating ? 'Bewerte mit AI …' : 'AI-Bewertung ausführen'}</button></div>}
    {checking && <p role="status">Lokaler Faktencheck läuft …</p>}
    {checkError && <p className="error" role="alert">{checkError}</p>}
    {aiError && <p className="error" role="alert">{aiError}</p>}
    {aiResult && <section className="ai-evaluation"><h2>Lokaler Equipmentvergleich</h2>{aiResult.local_comparison.recommended_target && <p>Empfohlener Zielslot: {aiResult.local_comparison.recommended_target}</p>}{aiResult.local_comparison.comparisons.map(comparison => <article key={comparison.target_slot}><h3>{comparison.target_slot}: {comparison.category}</h3><p>Candidate Score: {comparison.candidate.score} · Equipped Score: {comparison.equipped?.score ?? '—'} · Delta: {comparison.delta ?? '—'}</p><ul>{comparison.candidate.evidence.map(evidence => <li key={evidence.rule_id}><code>{evidence.rule_id}</code>: {evidence.points >= 0 ? '+' : ''}{evidence.points} – {evidence.message}</li>)}{comparison.hard_checks.checks.filter(check => check.status !== 'pass').map(check => <li key={check.code}><code>{check.code}</code>: {check.status} – {check.message}</li>)}</ul></article>)}<p>{aiResult.disclaimer}</p>{aiResult.provider_error && <p className="error">{aiResult.provider_error.message} <code>{aiResult.provider_error.code}</code></p>}{aiResult.evaluation && <><h2>AI-Erklärung</h2><p>Provider: {aiResult.provider} · Modell: {aiResult.model} · Confidence: {aiResult.evaluation.confidence}</p><AiPanel title="Build-Eignung" outcome={aiResult.evaluation.build.suitability} section={aiResult.evaluation.build}/><AiPanel title="Trade" outcome={aiResult.evaluation.trade.recommendation} section={aiResult.evaluation.trade}/><AiPanel title="Crafting" outcome={aiResult.evaluation.crafting.recommendation} section={aiResult.evaluation.crafting}/><h3>Confidence-Gründe</h3><ul>{aiResult.evaluation.confidence_reasons.map(reason => <li key={reason}>{reason}</li>)}</ul></>}</section>}
    {aiResult && <section><h2>Delta Bands</h2><ul>{aiResult.local_comparison.comparisons.map(comparison => <li key={comparison.target_slot}>{comparison.target_slot}: {comparison.delta_band ?? 'unknown'}</li>)}</ul></section>}
    {aiResult && aiResult.local_comparison.comparisons.some(comparison => comparison.equipped) && <section><h2>Equipped Evidence</h2>{aiResult.local_comparison.comparisons.map(comparison => comparison.equipped && <article key={comparison.target_slot}><h3>{comparison.target_slot}</h3><ul>{comparison.equipped.evidence.map(evidence => <li key={evidence.rule_id}><code>{evidence.rule_id}</code>: {evidence.points >= 0 ? '+' : ''}{evidence.points} – {evidence.message}</li>)}</ul></article>)}</section>}
    {!checking && factsCheck === null && checkWarnings.length > 0 && <aside className="warnings"><h2>Faktencheck nicht verfügbar</h2><ul>{checkWarnings.map(warning => <li key={warning}>{warning}</li>)}</ul></aside>}
    {factsCheck && <section className="facts-check"><h2>Lokaler Faktencheck</h2><p>{factsCheck.disclaimer}</p><h3>Item-Fakten</h3><dl className="facts"><Value label="Slot-Hinweis" value={factsCheck.facts.slot_hint}/><Value label="Item Level" value={factsCheck.facts.item_level}/><Value label="Required Level" value={factsCheck.facts.required_level}/><Value label="Required Str/Dex/Int" value={[factsCheck.facts.required_strength, factsCheck.facts.required_dexterity, factsCheck.facts.required_intelligence].map(value => value ?? '—')}/><Value label="Quality" value={factsCheck.facts.quality}/><Value label="Sockets" value={factsCheck.facts.sockets}/><Value label="Armour (augmented)" value={`${factsCheck.facts.armour ?? '—'} (${factsCheck.facts.armour_augmented})`}/><Value label="Evasion (augmented)" value={`${factsCheck.facts.evasion ?? '—'} (${factsCheck.facts.evasion_augmented})`}/><Value label="Energy Shield (augmented)" value={`${factsCheck.facts.energy_shield ?? '—'} (${factsCheck.facts.energy_shield_augmented})`}/><Value label="Spirit" value={factsCheck.facts.spirit}/><Value label="Granted Skill" value={factsCheck.facts.granted_skill}/><Value label="Identified / Corrupted" value={`${factsCheck.facts.identified} / ${factsCheck.facts.corrupted}`}/><Value label="Bekannte Modifier" value={factsCheck.facts.known_modifier_count}/><Value label="Unbekannte Modifier" value={factsCheck.facts.unknown_modifier_count}/></dl><div className="mods">{factsCheck.facts.modifiers.map((modifier, index) => <article key={`${index}-${modifier.raw_text}`}><strong>{modifier.raw_text}</strong><p>{modifier.source} · {modifier.affix_type ?? '—'} · {modifier.name ?? '—'} · Tier {modifier.tier ?? '—'} · Tags {modifier.tags.join(', ') || '—'}</p><p>{modifier.normalized_key} · Relevanz: {modifier.relevance ?? 'unbekannt'} · Regel: {modifier.config_rule ?? 'keine'}</p><p>Werte: {modifier.current_values.join(', ') || '—'} · Ranges: {modifier.roll_ranges.map(range => range.join('–')).join(', ') || '—'} · Rollposition: {modifier.roll_position === null ? '—' : modifier.roll_position.toFixed(2)}</p><p>Flags: crafted={String(modifier.crafted)}, desecrated={String(modifier.desecrated)}, rune={String(modifier.rune)}, implicit={String(modifier.implicit)}, unique={String(modifier.unique)}</p></article>)}</div><AssessmentPanel title="Lokale Verkaufsempfehlung" assessment={factsCheck.trade}/><AssessmentPanel title="Crafting" assessment={factsCheck.crafting}/>{factsCheck.warnings.length > 0 && <p>Warnungen: {factsCheck.warnings.join(', ')}</p>}</section>}</main>
}

const numericProfileFields: { key: keyof Profile; label: string }[] = [
  { key: 'character_level', label: 'Character Level' }, { key: 'life', label: 'Life' },
  { key: 'energy_shield', label: 'Energy Shield' }, { key: 'mana', label: 'Mana' },
  { key: 'spirit', label: 'Spirit' }, { key: 'spirit_required', label: 'Spirit Required' },
  { key: 'spirit_reserved', label: 'Spirit Reserved' }, { key: 'strength', label: 'Strength' },
  { key: 'dexterity', label: 'Dexterity' }, { key: 'intelligence', label: 'Intelligence' },
  { key: 'fire_resistance', label: 'Fire Resistance' }, { key: 'cold_resistance', label: 'Cold Resistance' },
  { key: 'lightning_resistance', label: 'Lightning Resistance' }, { key: 'chaos_resistance', label: 'Chaos Resistance' },
  { key: 'resistance_cap', label: 'Resistance Cap' },
]

function ProfileForm({ profile, setProfile, save }: { profile: Profile; setProfile: (profile: Profile) => void; save: () => Promise<void> }) {
  return <form onSubmit={event => { event.preventDefault(); void save() }}><label>Name<input value={profile.name} onChange={event => setProfile({ ...profile, name: event.target.value })}/></label><label>Build Stage<input value={profile.build_stage} onChange={event => setProfile({ ...profile, build_stage: event.target.value })}/></label>{numericProfileFields.map(({ key, label }) => <label key={key}>{label}<input type="number" value={(profile[key] as number | null) ?? ''} onChange={event => setProfile({ ...profile, [key]: key === 'resistance_cap' ? (event.target.value === '' ? 75 : Number(event.target.value)) : (event.target.value === '' ? null : Number(event.target.value)) })}/></label>)}<label>Notes<textarea value={profile.notes} onChange={event => setProfile({ ...profile, notes: event.target.value })}/></label><button>Profil speichern</button></form>
}

function AiPanel({ title, outcome, section }: { title: string; outcome: string; section: { reasons: string[]; warnings: string[] } }) {
  return <article><h3>{title}</h3><p>{outcome}</p><ul>{section.reasons.map(reason => <li key={reason}>{reason}</li>)}{section.warnings.map(warning => <li key={warning}>Warnung: {warning}</li>)}</ul></article>
}

function AssessmentPanel({ title, assessment }: { title: string; assessment: FactsCheck['trade'] }) {
  return <article><h3>{title}</h3><p>{assessment.outcome} · Confidence: {assessment.confidence}</p><ul>{assessment.confidence_reasons.map(reason => <li key={reason}>{reason}</li>)}{assessment.evidence.map(evidence => <li key={evidence.rule_id}><code>{evidence.rule_id}</code>: {evidence.message} ({evidence.matched_facts.join(', ')})</li>)}</ul></article>
}
