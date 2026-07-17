import { FormEvent, useEffect, useRef, useState } from 'react'

import { checkItem, evaluateItem, EvaluateResponse, exportBackup, exportEquipmentFile, FactsCheck, HistoryEntry, HistoryStatus, importEquipmentFile, loadEquipment, loadHistory, loadProfile, parseBackupFile, parseItem, ParseResponse, persistEvaluation, Profile, recompareHistory, restoreBackup, SaleData, saveEquipment, saveProfile, updateHistory } from './api'

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
  const managementGeneration = useRef(0)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [equipmentSlot, setEquipmentSlot] = useState('wand')
  const [equipmentText, setEquipmentText] = useState('')
  const [managementMessage, setManagementMessage] = useState<string | null>(null)
  const [historyRefresh, setHistoryRefresh] = useState(0)
  const [saveMessage, setSaveMessage] = useState<string | null>(null)
  const saveRequest = useRef<AbortController | null>(null)

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

  async function saveCheckedCandidate() {
    saveRequest.current?.abort()
    const controller = new AbortController()
    const submitted = rawText
    const slot = equipmentSlot
    saveRequest.current = controller
    setSaveMessage('Speichere geprüften Candidate …')
    try {
      await persistEvaluation(submitted, slot, controller.signal)
      if (saveRequest.current === controller && rawText === submitted && equipmentSlot === slot) {
        setSaveMessage('Candidate in der lokalen History gespeichert.')
        setHistoryRefresh(value => value + 1)
      }
    } catch (reason) {
      if (!controller.signal.aborted && saveRequest.current === controller) setSaveMessage(reason instanceof Error ? reason.message : 'Speichern fehlgeschlagen.')
    }
  }

  function invalidateComparison() {
    comparisonContext.current += 1
    aiRequest.current?.abort(); aiRequest.current = null
    setEvaluating(false); setAiResult(null); setAiError(null); setFactsCheck(null)
  }

  function changeEquipmentSlot(slot: string) {
    managementGeneration.current += 1
    invalidateComparison()
    setEquipmentSlot(slot); setEquipmentText('')
  }

  function beginManagement(): number {
    invalidateComparison()
    const generation = ++managementGeneration.current
    setManagementMessage('Management-Aktion läuft …')
    return generation
  }

  function applyLocalProfile(next: Profile) {
    managementGeneration.current += 1
    setProfile(next)
  }

  function applyLocalEquipmentText(next: string) {
    managementGeneration.current += 1
    setEquipmentText(next)
  }

  async function loadManagedProfile() {
    const generation = beginManagement()
    try {
      const loaded = await loadProfile()
      if (managementGeneration.current !== generation) return
      setProfile(loaded); setManagementMessage(null)
    } catch (reason) {
      if (managementGeneration.current === generation) setManagementMessage(String(reason))
    }
  }

  async function saveManagedProfile() {
    if (!profile) return
    const generation = beginManagement()
    try {
      const saved = await saveProfile(profile)
      if (managementGeneration.current !== generation) return
      setProfile(saved); setManagementMessage('Profil gespeichert.')
    } catch (reason) {
      if (managementGeneration.current === generation) setManagementMessage(String(reason))
    }
  }

  async function loadManagedSlot() {
    const generation = beginManagement()
    try {
      const data = await loadEquipment()
      if (managementGeneration.current !== generation) return
      setEquipmentText(data.slots[equipmentSlot]?.item.raw_text ?? ''); setManagementMessage(null)
    } catch (reason) {
      if (managementGeneration.current === generation) setManagementMessage(String(reason))
    }
  }

  async function saveManagedSlot() {
    const generation = beginManagement()
    try {
      await saveEquipment(equipmentSlot, equipmentText)
      if (managementGeneration.current === generation) setManagementMessage('Equipment gespeichert.')
    } catch (reason) {
      if (managementGeneration.current === generation) setManagementMessage(String(reason))
    }
  }

  async function importFile(file: File | undefined) {
    if (!file) return
    const generation = beginManagement()
    try {
      await importEquipmentFile(file)
      if (managementGeneration.current !== generation) return
      const loadedProfile = await loadProfile()
      if (managementGeneration.current !== generation) return
      setProfile(loadedProfile)
      setEquipmentText('')
      setManagementMessage('Equipment-Datei erfolgreich importiert.')
    } catch (reason) {
      if (managementGeneration.current !== generation) return
      setManagementMessage(reason instanceof Error ? reason.message : 'Import fehlgeschlagen.')
    }
  }

  async function downloadExport() {
    const generation = beginManagement()
    try {
      const data = await exportEquipmentFile()
      if (managementGeneration.current !== generation) return
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
      const link = document.createElement('a')
      link.href = url; link.download = 'poe2-equipment-v2.json'; link.click()
      URL.revokeObjectURL(url)
      setManagementMessage('Vollständiger v2-Export erstellt.')
    } catch (reason) {
      if (managementGeneration.current === generation) {
        setManagementMessage(reason instanceof Error ? reason.message : 'Export fehlgeschlagen.')
      }
    }
  }

  const parseComplete = result !== null && !result.warnings.some(warning => [
    'input_missing_line_breaks', 'missing_item_identity', 'no_modifiers_detected',
  ].includes(warning.code))

  return <main onChangeCapture={invalidateComparison}><p className="eyebrow">Manuelle Parse-Vorschau</p><h1>PoE 2 Gear &amp; Trade Checker</h1>
    <HistoryPanel refresh={historyRefresh} onRestore={() => { setHistoryRefresh(value => value + 1); void loadManagedProfile() }}/>
    <section><h2>Profil und Equipment</h2><div className="actions"><button type="button" onClick={() => { void loadManagedProfile() }}>Profil laden</button><button type="button" onClick={() => { void loadManagedSlot() }}>Slot laden</button><label className="file-button">Equipment-Datei importieren<input aria-label="Equipment-Datei importieren" type="file" accept="application/json,.json" onChange={event => { const input = event.currentTarget; void importFile(input.files?.[0]).finally(() => { input.value = '' }) }}/></label><button type="button" onClick={() => { void downloadExport() }}>v2-Export herunterladen</button></div>{profile && <ProfileForm profile={profile} setProfile={applyLocalProfile} save={saveManagedProfile}/>}<label>Equipment-Slot<select value={equipmentSlot} onChange={event => changeEquipmentSlot(event.target.value)}>{['wand','focus','helmet','body_armour','gloves','boots','belt','ring_1','ring_2','amulet'].map(slot => <option key={slot}>{slot}</option>)}</select></label><label>Itemtext des Slots<textarea rows={8} value={equipmentText} onChange={event => applyLocalEquipmentText(event.target.value)}/></label><button type="button" onClick={() => { void saveManagedSlot() }}>Slot speichern</button>{managementMessage && <p role="status">{managementMessage}</p>}</section>
    <form onSubmit={submit}><label htmlFor="itemtext">Englischen Itemtext einfügen</label><textarea id="itemtext" value={rawText} onChange={event => edit(event.target.value)} rows={15}/><button disabled={loading}>{loading ? 'Analysiere …' : needsReanalysis ? 'Erneut analysieren' : 'Analysieren'}</button></form>
    {loading && <p role="status">Itemtext wird analysiert …</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {suggestionDraft !== null && <section className="suggestion" aria-labelledby="suggestion-heading" aria-live="polite"><h2 id="suggestion-heading">Sicherer Zeilenumbruch-Vorschlag</h2><p role="status">Nur eindeutig erkennbare Grenzen wurden ergänzt. Bitte prüfe und bearbeite den Entwurf vor einer erneuten Analyse.</p><label htmlFor="suggestion">Editierbarer Vorschlag</label><textarea id="suggestion" rows={15} value={suggestionDraft} onChange={event => setSuggestionDraft(event.target.value)}/><div className="actions"><button type="button" onClick={acceptSuggestion}>Vorschlag übernehmen</button><button type="button" onClick={discardSuggestion}>Verwerfen</button></div></section>}
    {result && <Preview result={result}/>} {parseComplete && <div className="actions"><button type="button" onClick={runFactsCheck} disabled={checking}>{checking ? 'Prüfe Fakten …' : 'Faktencheck ausführen'}</button><button type="button" onClick={runAiEvaluation} disabled={evaluating}>{evaluating ? 'Bewerte mit AI …' : 'AI-Bewertung ausführen'}</button></div>}
    {checking && <p role="status">Lokaler Faktencheck läuft …</p>}
    {checkError && <p className="error" role="alert">{checkError}</p>}
    {aiError && <p className="error" role="alert">{aiError}</p>}
    {aiResult && <div className="actions"><button type="button" onClick={() => { void saveCheckedCandidate() }}>Geprüften Candidate speichern</button>{saveMessage && <p role="status">{saveMessage}</p>}</div>}
    {aiResult && <section className="ai-evaluation"><h2>Lokaler Equipmentvergleich</h2>{aiResult.local_comparison.recommended_target && <p>Empfohlener Zielslot: {aiResult.local_comparison.recommended_target}</p>}{aiResult.local_comparison.comparisons.map(comparison => <article key={comparison.target_slot}><h3>{comparison.target_slot}: {comparison.category}</h3><p>Candidate Score: {comparison.candidate.score} · Equipped Score: {comparison.equipped?.score ?? '—'} · Delta: {comparison.delta ?? '—'}</p><p>Regelversion v{comparison.candidate.rule_version} · Vollständigkeit: {comparison.candidate.completeness} · Confidence: {comparison.candidate.confidence} · unbekannte Modifier: {comparison.candidate.unknown_modifier_count}</p><EvidenceList title="Candidate – Gewinner" evidence={comparison.evidence_groups.candidate_winners}/><EvidenceList title="Candidate – Verlierer" evidence={comparison.evidence_groups.candidate_losers}/><EvidenceList title="Equipped – Gewinner" evidence={comparison.evidence_groups.equipped_winners}/><EvidenceList title="Equipped – Verlierer" evidence={comparison.evidence_groups.equipped_losers}/><h4>Harte Prüfungen</h4><ul>{comparison.hard_checks.checks.map(check => <li key={check.code} className={`check-${check.status}`}><code>{check.code}</code>: {check.status} – {check.message}</li>)}</ul></article>)}<p>{aiResult.disclaimer}</p>{aiResult.provider_error && <p className="error">{aiResult.provider_error.message} <code>{aiResult.provider_error.code}</code></p>}{aiResult.evaluation && <><h2>AI-Erklärung</h2><p>Provider: {aiResult.provider} · Modell: {aiResult.model} · Confidence: {aiResult.evaluation.confidence}</p><AiPanel title="Build-Eignung" outcome={aiResult.evaluation.build.suitability} section={aiResult.evaluation.build}/><AiPanel title="Trade" outcome={aiResult.evaluation.trade.recommendation} section={aiResult.evaluation.trade}/><AiPanel title="Crafting" outcome={aiResult.evaluation.crafting.recommendation} section={aiResult.evaluation.crafting}/><h3>Confidence-Gründe</h3><ul>{aiResult.evaluation.confidence_reasons.map(reason => <li key={reason}>{reason}</li>)}</ul></>}</section>}
    {aiResult && <section><h2>Delta Bands</h2><ul>{aiResult.local_comparison.comparisons.map(comparison => <li key={comparison.target_slot}>{comparison.target_slot}: {comparison.delta_band ?? 'unknown'}</li>)}</ul></section>}
    {aiResult && aiResult.local_comparison.comparisons.some(comparison => comparison.equipped) && <section><h2>Equipped Evidence</h2>{aiResult.local_comparison.comparisons.map(comparison => comparison.equipped && <article key={comparison.target_slot}><h3>{comparison.target_slot}</h3><ul>{comparison.equipped.evidence.map(evidence => <li key={evidence.rule_id}><code>{evidence.rule_id}</code>: {evidence.points >= 0 ? '+' : ''}{evidence.points} – {evidence.message}</li>)}</ul></article>)}</section>}
    {!checking && factsCheck === null && checkWarnings.length > 0 && <aside className="warnings"><h2>Faktencheck nicht verfügbar</h2><ul>{checkWarnings.map(warning => <li key={warning}>{warning}</li>)}</ul></aside>}
    {factsCheck && <section className="facts-check"><h2>Lokaler Faktencheck</h2><p>{factsCheck.disclaimer}</p><h3>Item-Fakten</h3><dl className="facts"><Value label="Slot-Hinweis" value={factsCheck.facts.slot_hint}/><Value label="Item Level" value={factsCheck.facts.item_level}/><Value label="Required Level" value={factsCheck.facts.required_level}/><Value label="Required Str/Dex/Int" value={[factsCheck.facts.required_strength, factsCheck.facts.required_dexterity, factsCheck.facts.required_intelligence].map(value => value ?? '—')}/><Value label="Quality" value={factsCheck.facts.quality}/><Value label="Sockets" value={factsCheck.facts.sockets}/><Value label="Armour (augmented)" value={`${factsCheck.facts.armour ?? '—'} (${factsCheck.facts.armour_augmented})`}/><Value label="Evasion (augmented)" value={`${factsCheck.facts.evasion ?? '—'} (${factsCheck.facts.evasion_augmented})`}/><Value label="Energy Shield (augmented)" value={`${factsCheck.facts.energy_shield ?? '—'} (${factsCheck.facts.energy_shield_augmented})`}/><Value label="Spirit" value={factsCheck.facts.spirit}/><Value label="Granted Skill" value={factsCheck.facts.granted_skill}/><Value label="Identified / Corrupted" value={`${factsCheck.facts.identified} / ${factsCheck.facts.corrupted}`}/><Value label="Bekannte Modifier" value={factsCheck.facts.known_modifier_count}/><Value label="Unbekannte Modifier" value={factsCheck.facts.unknown_modifier_count}/></dl><div className="mods">{factsCheck.facts.modifiers.map((modifier, index) => <article key={`${index}-${modifier.raw_text}`}><strong>{modifier.raw_text}</strong><p>{modifier.source} · {modifier.affix_type ?? '—'} · {modifier.name ?? '—'} · Tier {modifier.tier ?? '—'} · Tags {modifier.tags.join(', ') || '—'}</p><p>{modifier.normalized_key} · Relevanz: {modifier.relevance ?? 'unbekannt'} · Regel: {modifier.config_rule ?? 'keine'}</p><p>Werte: {modifier.current_values.join(', ') || '—'} · Ranges: {modifier.roll_ranges.map(range => range.join('–')).join(', ') || '—'} · Rollposition: {modifier.roll_position === null ? '—' : modifier.roll_position.toFixed(2)}</p><p>Flags: crafted={String(modifier.crafted)}, desecrated={String(modifier.desecrated)}, rune={String(modifier.rune)}, implicit={String(modifier.implicit)}, unique={String(modifier.unique)}</p></article>)}</div><AssessmentPanel title="Lokale Verkaufsempfehlung" assessment={factsCheck.trade}/><AssessmentPanel title="Crafting" assessment={factsCheck.crafting}/>{factsCheck.warnings.length > 0 && <p>Warnungen: {factsCheck.warnings.join(', ')}</p>}</section>}</main>
}

const emptySale: SaleData = { listed_at: null, listed_currency: null, listed_amount: null, sold_at: null, sold_currency: null, sold_amount: null, notes: '' }

function HistoryPanel({ refresh, onRestore }: { refresh: number; onRestore: () => void }) {
  const [filters, setFilters] = useState({ slot: '', category: '', status: '', base_type: '', rarity: '' })
  const [entries, setEntries] = useState<HistoryEntry[]>([])
  const [selected, setSelected] = useState<HistoryEntry | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const limit = 20
  const [pendingBackup, setPendingBackup] = useState<{ name: string; data: unknown } | null>(null)
  const [mutating, setMutating] = useState(false)
  const request = useRef<AbortController | null>(null)
  const mutation = useRef<AbortController | null>(null)
  const mutationGeneration = useRef(0)

  async function reload() {
    request.current?.abort()
    const controller = new AbortController(); request.current = controller
    try {
      const page = await loadHistory({ ...filters, limit: String(limit), offset: String(offset) }, controller.signal)
      if (request.current === controller) { setEntries(page.items); setTotal(page.total); setSelected(current => page.items.find(item => item.id === current?.id) ?? null); setMessage(null) }
    } catch (reason) {
      if (!controller.signal.aborted && request.current === controller) setMessage(reason instanceof Error ? reason.message : 'History konnte nicht geladen werden.')
    }
  }

  useEffect(() => {
    void reload()
    return () => request.current?.abort()
  }, [refresh, offset])

  async function saveEntry() {
    if (!selected || mutating) return
    mutation.current?.abort(); const controller = new AbortController(); mutation.current = controller
    const generation = ++mutationGeneration.current; const id = selected.id; setMutating(true)
    try { const saved = await updateHistory(id, { status: selected.status, ...(selected.sale ?? emptySale) }, controller.signal); if (mutationGeneration.current !== generation || selected.id !== id) return; setSelected(saved); await reload(); if (mutationGeneration.current === generation) setMessage('History-Metadaten gespeichert.') } catch (reason) { if (!controller.signal.aborted && mutationGeneration.current === generation) setMessage(String(reason)) } finally { if (mutationGeneration.current === generation) setMutating(false) }
  }

  async function recompare() {
    if (!selected || mutating) return
    mutation.current?.abort(); const controller = new AbortController(); mutation.current = controller
    const generation = ++mutationGeneration.current; const id = selected.id; setMutating(true)
    try { const created = await recompareHistory(id, controller.signal); if (mutationGeneration.current !== generation || selected.id !== id) return; await reload(); setSelected(created); setMessage('Neuer append-only Vergleich wurde angelegt.') } catch (reason) { if (!controller.signal.aborted && mutationGeneration.current === generation) setMessage(String(reason)) } finally { if (mutationGeneration.current === generation) setMutating(false) }
  }

  async function downloadBackup() {
    try { const data = await exportBackup(); const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })); const link = document.createElement('a'); link.href = url; link.download = 'poe2-checker-backup-v1.json'; link.click(); URL.revokeObjectURL(url); setMessage('Vollbackup erstellt.') } catch (reason) { setMessage(String(reason)) }
  }

  async function selectBackup(file: File | undefined) {
    if (!file) return
    try { setPendingBackup({ name: file.name, data: await parseBackupFile(file) }); setMessage(null) } catch (reason) { setPendingBackup(null); setMessage(reason instanceof Error ? reason.message : 'Backup ungültig.') }
  }

  async function confirmRestore() {
    if (!pendingBackup || mutating) return
    mutation.current?.abort(); const controller = new AbortController(); mutation.current = controller
    const generation = ++mutationGeneration.current; setMutating(true)
    try { await restoreBackup(pendingBackup.data, controller.signal); if (mutationGeneration.current !== generation) return; setPendingBackup(null); setSelected(null); setOffset(0); onRestore(); await reload(); setMessage('Backup vollständig wiederhergestellt.') } catch (reason) { if (!controller.signal.aborted && mutationGeneration.current === generation) setMessage(reason instanceof Error ? reason.message : 'Restore fehlgeschlagen.') } finally { if (mutationGeneration.current === generation) setMutating(false) }
  }

  function saleChange(field: keyof SaleData, value: string) {
    if (!selected) return
    const nullable = field === 'notes' ? value : value || null
    setSelected({ ...selected, sale: { ...(selected.sale ?? emptySale), [field]: nullable } })
  }

  function invalidateMutation() {
    mutationGeneration.current += 1; mutation.current?.abort(); mutation.current = null; setMutating(false)
  }

  function selectEntry(entry: HistoryEntry) { invalidateMutation(); setSelected(entry) }

  function changeFilter(field: keyof typeof filters, value: string) {
    invalidateMutation(); request.current?.abort(); setFilters({ ...filters, [field]: value }); setOffset(0)
  }

  return <section className="history"><h2>Lokale Vergleichshistorie</h2><div className="actions"><button type="button" onClick={() => { void downloadBackup() }}>Vollbackup herunterladen</button><label className="file-button">Restore-Datei auswählen<input aria-label="Vollbackup wiederherstellen" type="file" accept="application/json,.json" onChange={event => { const input = event.currentTarget; void selectBackup(input.files?.[0]).finally(() => { input.value = '' }) }}/></label></div>{pendingBackup && <aside className="warnings"><strong>Achtung: Restore ersetzt Profil, Equipment und die gesamte History.</strong><p>Datei: {pendingBackup.name}. Lade idealerweise vorher ein aktuelles Vollbackup herunter.</p><button type="button" disabled={mutating} onClick={() => { void confirmRestore() }}>Restore endgültig bestätigen</button><button type="button" disabled={mutating} onClick={() => setPendingBackup(null)}>Abbrechen</button></aside>}<div className="history-filters"><label>Slot<input value={filters.slot} onChange={event => changeFilter('slot', event.target.value)}/></label><label>Category<input value={filters.category} onChange={event => changeFilter('category', event.target.value)}/></label><label>Status<select value={filters.status} onChange={event => changeFilter('status', event.target.value)}><option value="">alle</option>{['checked','equipped','stored','listed','sold','vendor'].map(status => <option key={status}>{status}</option>)}</select></label><label>Base Type<input value={filters.base_type} onChange={event => changeFilter('base_type', event.target.value)}/></label><label>Rarity<input value={filters.rarity} onChange={event => changeFilter('rarity', event.target.value)}/></label><button type="button" onClick={() => { void reload() }}>Filtern</button></div>{message && <p role="status">{message}</p>}{entries.length === 0 ? <p>Noch keine gespeicherten Candidates.</p> : <ul className="history-list">{entries.map(entry => <li key={entry.id}><button type="button" onClick={() => selectEntry(entry)}>{entry.item.name ?? entry.item.base_type ?? 'Unnamed Item'} · {entry.target_slot} · {entry.category} · {entry.status} · v{entry.rule_version} · {new Date(entry.created_at).toLocaleString('de-DE')}</button></li>)}</ul>}<div className="actions"><button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>Zurück</button><span>{total === 0 ? 0 : offset + 1}–{Math.min(offset + entries.length, total)} von {total}</span><button type="button" disabled={offset + limit >= total} onClick={() => setOffset(offset + limit)}>Weiter</button></div>{selected && <article className="history-detail"><fieldset disabled={mutating}><h3>{selected.item.name ?? selected.item.base_type}</h3><p>Candidate Score {selected.candidate_score} · Equipped Score {selected.equipped_score ?? '—'} · Delta {selected.delta ?? '—'} · {selected.confidence}/{selected.completeness}</p><label>Status<select value={selected.status} onChange={event => setSelected({ ...selected, status: event.target.value as HistoryStatus })}>{['checked','equipped','stored','listed','sold','vendor'].map(status => <option key={status}>{status}</option>)}</select></label><label>Listed At<input type="datetime-local" value={toLocalDateTime(selected.sale?.listed_at)} onChange={event => saleChange('listed_at', toIsoDateTime(event.target.value))}/></label><label>Listed Amount<input type="number" step="0.0001" value={selected.sale?.listed_amount ?? ''} onChange={event => saleChange('listed_amount', event.target.value)}/></label><label>Listed Currency<input value={selected.sale?.listed_currency ?? ''} onChange={event => saleChange('listed_currency', event.target.value)}/></label><label>Sold At<input type="datetime-local" value={toLocalDateTime(selected.sale?.sold_at)} onChange={event => saleChange('sold_at', toIsoDateTime(event.target.value))}/></label><label>Sold Amount<input type="number" step="0.0001" value={selected.sale?.sold_amount ?? ''} onChange={event => saleChange('sold_amount', event.target.value)}/></label><label>Sold Currency<input value={selected.sale?.sold_currency ?? ''} onChange={event => saleChange('sold_currency', event.target.value)}/></label><label>Notizen<textarea value={selected.sale?.notes ?? ''} onChange={event => saleChange('notes', event.target.value)}/></label><div className="actions"><button disabled={mutating} type="button" onClick={() => { void saveEntry() }}>Metadaten speichern</button><button disabled={mutating} type="button" onClick={() => { void recompare() }}>Mit aktuellen Regeln vergleichen</button></div></fieldset></article>}</section>
}

function toLocalDateTime(value: string | null | undefined): string { if (!value) return ''; const date = new Date(value); const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000); return local.toISOString().slice(0, 16) }
function toIsoDateTime(value: string): string { return value ? new Date(value).toISOString() : '' }

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

function EvidenceList({ title, evidence }: { title: string; evidence: { rule_id: string; points: number; message: string }[] }) {
  return <section className="evidence-group"><h4>{title}</h4>{evidence.length ? <ul>{evidence.map(entry => <li key={entry.rule_id}><code>{entry.rule_id}</code>: {entry.points >= 0 ? '+' : ''}{entry.points} – {entry.message}</li>)}</ul> : <p>Keine.</p>}</section>
}

function AssessmentPanel({ title, assessment }: { title: string; assessment: FactsCheck['trade'] }) {
  return <article><h3>{title}</h3><p>{assessment.outcome} · Confidence: {assessment.confidence}</p><ul>{assessment.confidence_reasons.map(reason => <li key={reason}>{reason}</li>)}{assessment.evidence.map(evidence => <li key={evidence.rule_id}><code>{evidence.rule_id}</code>: {evidence.message} ({evidence.matched_facts.join(', ')})</li>)}</ul></article>
}
