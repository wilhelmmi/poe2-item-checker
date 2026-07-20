import { FormEvent, useEffect, useRef, useState } from 'react'
import { analyzeBuild, BuildContext, BuildPreview, confirmBuild, deleteBuild, Equipment, equipEquipment, evaluateItem, EvaluateResponse, exportEquipmentFile, importEquipmentFile, loadActiveBuild, loadBuilds, loadEquipment, parseItem, saveActiveBuild } from './api'

const slots = ['wand','focus','helmet','body_armour','gloves','boots','belt','ring_1','ring_2','amulet']

const slotLabels: Record<string, string> = {
  wand: 'Zauberstab', focus: 'Fokus', helmet: 'Helm', body_armour: 'Körperrüstung',
  gloves: 'Handschuhe', boots: 'Stiefel', belt: 'Gürtel', ring_1: 'Ring 1', ring_2: 'Ring 2', amulet: 'Amulett',
}

const candidateSlots: Record<string,string> = {
  Wands: 'wand', Foci: 'focus', Helmets: 'helmet', 'Body Armours': 'body_armour',
  Gloves: 'gloves', Boots: 'boots', Belts: 'belt', Amulets: 'amulet',
  Staves: 'wand',
}

export function candidateTargetSlot(itemClass: string|null, currentSlot: string): string|null {
  if(itemClass==='Rings')return currentSlot==='ring_1'||currentSlot==='ring_2'?currentSlot:'ring_1'
  return itemClass ? candidateSlots[itemClass] ?? null : null
}

function impactLabel(value: 'better'|'similar'|'worse'): string { return value==='better'?'besser':value==='worse'?'schlechter':'ähnlich' }
function impactTone(value: 'better'|'similar'|'worse'): string { return value==='better'?'positive':value==='worse'?'negative':'neutral' }

export function App() {
  const [rawText,setRawText] = useState(''); const [slot,setSlot] = useState('ring_1')
  const [builds,setBuilds] = useState<BuildContext[]>([]); const [buildId,setBuildId] = useState<string|null>(null)
  const [buildUrl,setBuildUrl]=useState(''); const [buildPreview,setBuildPreview]=useState<BuildPreview|null>(null); const [analyzingBuild,setAnalyzingBuild]=useState(false); const [confirmingBuild,setConfirmingBuild]=useState(false)
  const [deletingBuild,setDeletingBuild]=useState(false)
  const [result,setResult] = useState<EvaluateResponse|null>(null); const [message,setMessage] = useState<string|null>(null); const [loading,setLoading] = useState(false); const [mutatingEquipment,setMutatingEquipment] = useState(false)
  const [formatNotice,setFormatNotice] = useState<string|null>(null); const [manualSuggestion,setManualSuggestion] = useState<string|null>(null)
  const [equipment,setEquipment] = useState<Equipment|null>(null); const [equipmentLoading,setEquipmentLoading]=useState(true); const [equipmentError,setEquipmentError]=useState<string|null>(null)
  const request = useRef<AbortController|null>(null); const equipmentRequest = useRef<AbortController|null>(null); const mutationRequest = useRef<AbortController|null>(null)
  const equipmentRevision=useRef(0)
  const buildAnalysisRequest=useRef<AbortController|null>(null); const activeBuildRequest=useRef<AbortController|null>(null); const activeBuildRevision=useRef(0)
  useEffect(() => { const loadController=new AbortController(); const initialRevision=activeBuildRevision.current; void loadBuilds().then(data => { if(loadController.signal.aborted)return; setBuilds(data); void loadActiveBuild(loadController.signal).then(active=>{if(!loadController.signal.aborted&&activeBuildRevision.current===initialRevision)setBuildId(active&&data.some(build=>build.build_id===active)?active:data[0]?.build_id??null)}).catch(()=>{if(activeBuildRevision.current===initialRevision)setBuildId(data[0]?.build_id??null)}) }).catch(e => {if(!loadController.signal.aborted)setMessage(e instanceof Error?e.message:String(e))}); return()=>{loadController.abort();buildAnalysisRequest.current?.abort();activeBuildRequest.current?.abort()} }, [])
  useEffect(() => { setEquipment(null); if(buildId)void refreshEquipment(buildId); else {setEquipmentLoading(false);setEquipmentError(null)} return()=>{equipmentRequest.current?.abort();mutationRequest.current?.abort()} }, [buildId])
  function invalidate() { request.current?.abort(); setResult(null); setFormatNotice(null); setManualSuggestion(null) }
  async function refreshEquipment(requestBuild=buildId) { if(!requestBuild||mutationRequest.current)return; equipmentRequest.current?.abort(); const controller=new AbortController(); const revision=equipmentRevision.current; equipmentRequest.current=controller; setEquipmentLoading(true); setEquipmentError(null); try { const data=await loadEquipment(requestBuild,controller.signal); if(equipmentRequest.current===controller&&equipmentRevision.current===revision&&!mutationRequest.current&&buildId===requestBuild)setEquipment(data) } catch(e) { if(!controller.signal.aborted&&equipmentRequest.current===controller&&equipmentRevision.current===revision&&!mutationRequest.current&&buildId===requestBuild)setEquipmentError(e instanceof Error?e.message:String(e)) } finally { if(equipmentRequest.current===controller){equipmentRequest.current=null;setEquipmentLoading(false)} } }
  function beginEquipmentMutation() { if(mutationRequest.current)return null; equipmentRevision.current+=1; equipmentRequest.current?.abort(); equipmentRequest.current=null; const controller=new AbortController(); mutationRequest.current=controller; setEquipmentLoading(false); setMutatingEquipment(true); return controller }
  function finishEquipmentMutation(controller:AbortController) { if(mutationRequest.current===controller){mutationRequest.current=null;setMutatingEquipment(false)} }
  async function compare(event: FormEvent) { event.preventDefault(); if(!buildId)return; request.current?.abort(); const controller=new AbortController(); const original=rawText; const submittedSlot=slot; const submittedBuild=buildId; request.current=controller; setLoading(true); setMessage(null); setResult(null); setManualSuggestion(null); try { let preflight=await parseItem(original,controller.signal); if(request.current!==controller)return; if(preflight.auto_format_status==='ambiguous'){setManualSuggestion(preflight.line_break_suggestion?.suggested_text??null);setMessage('Der Itemtext ist mehrdeutig. Bitte den Vorschlag prüfen oder Zeilenumbrüche manuell ergänzen.');return} const formatted=preflight.auto_format_status==='safe'&&preflight.line_break_suggestion?preflight.line_break_suggestion.suggested_text:original; if(formatted!==original){setRawText(formatted);setFormatNotice('Sichere Zeilenumbrüche wurden automatisch eingefügt.')} const targetSlot=candidateTargetSlot(preflight.item.item_class ?? formatted.match(/^Item Class:[ \t]*(.+)$/m)?.[1]?.trim() ?? null,submittedSlot); if(!targetSlot){setMessage(preflight.item.item_class?`Die Item Class ${preflight.item.item_class} wird nicht als Equipment-Slot unterstützt.`:'Die Item Class konnte nicht erkannt werden. Bitte prüfe den Itemtext.');return} const value=await evaluateItem(formatted,controller.signal,targetSlot,submittedBuild); if(request.current===controller&&slot===submittedSlot&&buildId===submittedBuild)setResult(value) } catch(e) { if(!controller.signal.aborted&&request.current===controller)setMessage(e instanceof Error?e.message:String(e)) } finally { if(request.current===controller)setLoading(false) } }
  async function importFile(file?:File) { const requestBuild=buildId;if(!file||!requestBuild)return; const controller=beginEquipmentMutation(); if(!controller)return; let resync=false; try { const imported=await importEquipmentFile(requestBuild,file,controller.signal); if(mutationRequest.current!==controller||buildId!==requestBuild)return; setEquipment(imported); setEquipmentError(null); invalidate(); const occupied=Object.values(imported.slots).filter(Boolean).length; const charmNotice=imported.ignoredCharms?` ${imported.ignoredCharms} Charms wurden erkannt, werden aber noch nicht als Equipment-Slots unterstützt.`:''; setMessage(`Komplettes Equipment importiert: ${occupied} von ${slots.length} Slots belegt.${charmNotice}`) } catch(e) { if(!controller.signal.aborted&&mutationRequest.current===controller&&buildId===requestBuild){resync=true;setMessage(String(e))} } finally { finishEquipmentMutation(controller); if(resync)void refreshEquipment() } }
  async function equipCandidate() { const requestBuild=buildId;if(!result?.evaluation||!requestBuild)return; const controller=beginEquipmentMutation(); if(!controller)return; const candidate=result; let resync=false; setMessage(null); try { const nextEquipment=await equipEquipment(requestBuild,candidate.parse.item.raw_text,candidate.target_slot,controller.signal); if(mutationRequest.current!==controller||buildId!==requestBuild)return; setEquipment(nextEquipment); setEquipmentError(null); setResult(null); setMessage(`Candidate wurde in ${(candidate.target_slots??[candidate.target_slot]).join(' + ')} ausgerüstet. Das vorherige Equipment dieser Slots ist nicht mehr ausgerüstet.`) } catch(e) { if(!controller.signal.aborted&&mutationRequest.current===controller&&buildId===requestBuild){resync=true;setMessage(e instanceof Error?e.message:String(e))} } finally { finishEquipmentMutation(controller); if(resync)void refreshEquipment() } }
  function selectRingTarget(nextSlot:string) { setSlot(nextSlot); if(result?.target_slot==='ring_1'||result?.target_slot==='ring_2')invalidate() }
  async function download() { if(!buildId)return;try { const data=await exportEquipmentFile(buildId); const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'})); const a=document.createElement('a');a.href=url;a.download='poe2-equipment-v2.json';a.click();URL.revokeObjectURL(url) } catch(e) { setMessage(String(e)) } }
  async function persistActiveBuild(value:string):Promise<boolean>{if(mutationRequest.current)return false;activeBuildRevision.current+=1;const revision=activeBuildRevision.current;activeBuildRequest.current?.abort();const controller=new AbortController();activeBuildRequest.current=controller;setBuildId(value);invalidate();try{await saveActiveBuild(value,controller.signal);return activeBuildRevision.current===revision&&!controller.signal.aborted}catch(e){if(activeBuildRevision.current===revision&&!controller.signal.aborted)setMessage(e instanceof Error?e.message:String(e));return false}finally{if(activeBuildRequest.current===controller)activeBuildRequest.current=null}}
  async function startBuildAnalysis(event:FormEvent){event.preventDefault();buildAnalysisRequest.current?.abort();const controller=new AbortController();buildAnalysisRequest.current=controller;setAnalyzingBuild(true);setBuildPreview(null);setMessage(null);try{const preview=await analyzeBuild(buildUrl,controller.signal);if(buildAnalysisRequest.current===controller&&!controller.signal.aborted)setBuildPreview(preview)}catch(e){if(buildAnalysisRequest.current===controller&&!controller.signal.aborted)setMessage(e instanceof Error?e.message:String(e))}finally{if(buildAnalysisRequest.current===controller){buildAnalysisRequest.current=null;setAnalyzingBuild(false)}}}
  async function acceptBuild(){if(!buildPreview||mutationRequest.current)return;setConfirmingBuild(true);setMessage(null);try{const build=await confirmBuild(buildPreview.preview_id);setBuilds(current=>current.some(item=>item.build_id===build.build_id)?current:[...current,build]);if(!await persistActiveBuild(build.build_id))return;setBuildPreview(null);setBuildUrl('');setMessage(`Build „${build.name}“ wurde gespeichert und aktiviert.`)}catch(e){setMessage(e instanceof Error?e.message:String(e))}finally{setConfirmingBuild(false)}}
  async function removeActiveBuild(){if(!activeBuild||deletingBuild||mutationRequest.current)return;if(!window.confirm(`Build „${activeBuild.name}“ wirklich löschen?`))return;activeBuildRevision.current+=1;const revision=activeBuildRevision.current;activeBuildRequest.current?.abort();const controller=new AbortController();activeBuildRequest.current=controller;setDeletingBuild(true);setMessage(null);try{const deleted=await deleteBuild(activeBuild.build_id,controller.signal);if(activeBuildRevision.current!==revision||controller.signal.aborted)return;setBuilds(current=>current.filter(build=>build.build_id!==deleted.deleted_build_id));setBuildId(deleted.active_build_id);invalidate();setMessage(`Build „${activeBuild.name}“ wurde gelöscht.`)}catch(e){if(activeBuildRevision.current!==revision||controller.signal.aborted)return;const reason=e instanceof Error?e.message:String(e);try{const [freshBuilds,freshActive]=await Promise.all([loadBuilds(),loadActiveBuild(controller.signal)]);if(activeBuildRevision.current!==revision||controller.signal.aborted)return;setBuilds(freshBuilds);const fallback=freshBuilds.find(build=>build.build_id===freshActive)??freshBuilds[0];setBuildId(fallback?.build_id??null);invalidate();setMessage(`${reason} Der Buildstatus wurde neu geladen.`)}catch{if(activeBuildRevision.current===revision&&!controller.signal.aborted)setMessage(`${reason} Der Buildstatus konnte nicht neu geladen werden.`)}}finally{if(activeBuildRequest.current===controller)activeBuildRequest.current=null;setDeletingBuild(false)}}
  const recommendation = result?.evaluation?.recommendation
  const activeBuild = builds.find(b=>b.build_id===buildId)
  const staffEquipped=equipment?.slots?.wand?.item.item_class==='Staves'
  const impactEntries = result?.evaluation ? [
    ['Damage', result.evaluation.impacts.damage], ['Defensive', result.evaluation.impacts.defensive],
    ['Resistances', result.evaluation.impacts.resistances], ['Utility', result.evaluation.impacts.utility],
  ] as const : []

  return <div className="app-shell">
    <header className="site-header">
      <div className="brand-mark" aria-hidden="true">II</div>
      <div><p className="eyebrow">Build Intelligence</p><h1>PoE 2 Item Checker</h1></div>
      <p className="header-note">Fundierte Itemvergleiche für deinen aktiven Build</p>
    </header>

    <main className="workspace">
      <div className="primary-column">
        <form className="panel candidate-panel" onSubmit={compare}>
          <div className="panel-heading"><div><p className="step-label">Item-Analyse</p><h2>Candidate vergleichen</h2></div><span className="slot-hint">Slot wird automatisch erkannt</span></div>
          <p className="section-intro">Füge den vollständigen englischen Itemtext aus dem Spiel ein. Der Vergleich erfolgt nur mit dem passenden ausgerüsteten Slot.</p>
          <label htmlFor="itemtext">Englischen Itemtext einfügen</label>
          <textarea id="itemtext" className="item-input" rows={15} placeholder={'Item Class: Wands\nRarity: Rare\n…'} value={rawText} onChange={e=>{setRawText(e.target.value);invalidate()}}/>
          <div className="form-footer"><span>{rawText.trim() ? `${rawText.length} Zeichen` : 'Bereit für deinen Itemtext'}</span><button className="primary-action" disabled={loading||!rawText.trim()||!buildId}>{loading?<><span className="spinner" aria-hidden="true"/>API vergleicht …</>:'Mit ausgerüstetem Item vergleichen'}</button></div>
        </form>

        {formatNotice&&<p className="notice" role="status">{formatNotice}</p>}
        {manualSuggestion&&<section className="panel"><p className="step-label">Eingabe prüfen</p><h2>Formatierung prüfen</h2><p>Dieser Vorschlag ist nicht als sicher eingestuft und wird nicht automatisch ausgewertet.</p><label>Manueller Formatierungsvorschlag<textarea rows={15} value={manualSuggestion} onChange={e=>setManualSuggestion(e.target.value)}/></label><button type="button" onClick={()=>{setRawText(manualSuggestion);setManualSuggestion(null);setMessage('Vorschlag übernommen. Bitte prüfen und Vergleich erneut starten.')}}>Geprüften Vorschlag übernehmen</button></section>}
        {message&&<p className="alert" role="alert">{message}</p>}

        {result&&<section className="panel ai-evaluation" aria-labelledby="comparison-title">
          <div className="panel-heading"><div><p className="step-label">AI-Auswertung</p><h2 id="comparison-title">Vergleich</h2></div>{result.evaluation&&<span className={`verdict-badge verdict-${result.evaluation.verdict}`}>{result.evaluation.verdict==='upgrade'?'Upgrade':result.evaluation.verdict==='downgrade'?'Downgrade':'Sidegrade'}</span>}</div>
          {result.provider_error&&<p className="alert">Keine Empfehlung: {result.provider_error.message} <code>{result.provider_error.code}</code></p>}
          {result.evaluation&&<>
            <div className="item-comparison"><article><span>Aktueller Slot</span><strong>{result.evaluation.current_item_name}</strong></article><div className="comparison-arrow" aria-hidden="true">→</div><article><span>Neues Item</span><strong>{result.evaluation.new_item_name}</strong></article></div>
            <div className="delta-grid"><article className="delta gains"><h3>Gewinne</h3>{result.evaluation.gains.length?<ul>{result.evaluation.gains.map(r=><li key={r}>{r}</li>)}</ul>:<p>Keine relevanten Gewinne.</p>}</article><article className="delta losses"><h3>Verluste</h3>{result.evaluation.losses.length?<ul>{result.evaluation.losses.map(r=><li key={r}>{r}</li>)}</ul>:<p>Keine relevanten Verluste.</p>}</article></div>
            <h3>Auswirkungen auf den Build</h3><div className="impact-grid">{impactEntries.map(([name,value])=><div className={`impact impact-${impactTone(value)}`} key={name}><span>{name}</span><strong>{impactLabel(value)}</strong></div>)}</div>
            <div className={`verdict-card recommendation-${recommendation}`}><span>Gesamturteil</span><strong>{result.evaluation.verdict==='upgrade'?'🟢 Upgrade – Candidate ist besser':result.evaluation.verdict==='downgrade'?'🔴 Downgrade – Candidate ist nicht besser':'🟡 Sidegrade / situationsabhängig – Empfehlung unsicher'}</strong><small>Confidence: {result.evaluation.confidence} · {(result.target_slots??[result.target_slot]).length>1?'Zielslots':'Zielslot'}: {(result.target_slots??[result.target_slot]).join(' + ')}</small></div>
            <div className="clear-recommendation"><h3>Klare Empfehlung</h3><p>{result.evaluation.clear_recommendation}</p></div>
            {result.evaluation.warnings.length>0&&<div className="warnings"><h3>Warnungen</h3><ul>{result.evaluation.warnings.map(w=><li key={w}>{w}</li>)}</ul></div>}
            <div className="result-footer"><button className="primary-action" type="button" disabled={mutatingEquipment} onClick={()=>void equipCandidate()}>{mutatingEquipment?'Equipment wird geändert …':'Candidate ausrüsten'}</button><span>Provider: {result.provider} · Modell: {result.model}</span></div>
          </>}<p className="disclaimer">{result.disclaimer}</p>
        </section>}
      </div>

      <aside className="sidebar" aria-label="Build und Equipment">
        <section className="panel compact-panel"><div className="panel-heading"><div><p className="step-label">Kontext</p><h2>Aktiver Build</h2></div><span className="status-dot" title="Aktiv"/></div>
          <label>Aktiver Build<select aria-label="Aktiver Build" value={buildId??''} disabled={deletingBuild||mutatingEquipment} onChange={e=>void persistActiveBuild(e.target.value)}><option value="" disabled>{builds.length?'Build wählen':'Keine Builds vorhanden'}</option>{builds.map(b=><option key={b.build_id} value={b.build_id}>{b.name} · v{b.version}</option>)}</select></label>
          {!activeBuild&&<p className="equipment-help">Füge einen Build-Link hinzu, um Equipment zu verwalten und Items zu vergleichen.</p>}{activeBuild&&<div className="active-build-card"><strong>{activeBuild.name}</strong><span>{activeBuild.archetype}</span><a href={activeBuild.source_url} target="_blank" rel="noreferrer">Quelle und Variante: {activeBuild.source_variant}</a><button className="danger-button" type="button" disabled={deletingBuild||mutatingEquipment} onClick={()=>void removeActiveBuild()}>{deletingBuild?'Build wird gelöscht …':'Build löschen'}</button></div>}
          <details className="build-import"><summary>Build-Link hinzufügen</summary><form onSubmit={startBuildAnalysis}><label>Öffentliche Build-URL<input aria-label="Build-URL" type="url" required maxLength={2048} placeholder="https://…" value={buildUrl} onChange={e=>setBuildUrl(e.target.value)}/></label><button disabled={analyzingBuild||!buildUrl.trim()}>{analyzingBuild?'Build wird analysiert …':'Build automatisch analysieren'}</button></form></details>
        </section>

        {buildPreview&&<section className="panel build-preview"><p className="step-label">Import-Vorschau</p><h2>Vorschau prüfen</h2><div className="preview-identity"><strong>{buildPreview.analysis.name}</strong><span>von {buildPreview.analysis.author}</span><span>{buildPreview.analysis.archetype} · {buildPreview.analysis.source_variant}</span></div>{([['Kernskills',buildPreview.analysis.core_skills],['Offensive Prioritäten',buildPreview.analysis.offensive_priorities],['Defensive Prioritäten',buildPreview.analysis.defensive_priorities],['Item-Prioritäten',buildPreview.analysis.item_priorities],['Schwach gewichtete Werte',buildPreview.analysis.low_value_stats],['Einschränkungen',buildPreview.analysis.constraints],['Unsicherheiten',buildPreview.analysis.uncertainties]] as [string,string[]][]).map(([title,items])=>items.length>0&&<div className="preview-group" key={title}><h3>{title}</h3><ul>{items.map((item,index)=><li key={`${item}-${index}`}>{item}</li>)}</ul></div>)}<div className="preview-group"><h3>Quellen</h3>{buildPreview.citations.length?<ul>{buildPreview.citations.map(c=><li key={c.url}><a href={c.url} target="_blank" rel="noreferrer">{c.title}</a></li>)}</ul>:<p>Der Provider hat keine anklickbaren Quellen geliefert.</p>}</div><p className="metadata">Provider: {buildPreview.provider} · Modell: {buildPreview.model}</p><button type="button" disabled={confirmingBuild||mutatingEquipment} onClick={()=>void acceptBuild()}>{confirmingBuild?'Build wird gespeichert …':'Vorschau bestätigen und aktivieren'}</button></section>}

        <section className="panel compact-panel equipment-panel"><div className="panel-heading"><div><p className="step-label">Equipment</p><h2>Aktuelles Equipment</h2></div><span className="equipment-count">{equipment?`${Object.values(equipment.slots).filter(Boolean).length}/${slots.length}`:'–'}</span></div>
          <p className="equipment-help">Für Ring-Candidates wählst du hier den Zielslot. Alle anderen Slots werden automatisch erkannt.</p>
          {equipmentLoading&&<div className="equipment-state" role="status"><span className="spinner" aria-hidden="true"/>Equipment wird geladen …</div>}
          {equipmentError&&<div className="equipment-state equipment-error" role="alert"><span>{equipmentError}</span><button type="button" disabled={mutatingEquipment} onClick={()=>void refreshEquipment()}>Erneut laden</button></div>}
          {!equipmentLoading&&!equipmentError&&equipment&&<>
            <div className="equipment-grid" role="list" aria-label="Aktuell ausgerüstete Items">
              {slots.filter(equipmentSlot=>!equipmentSlot.startsWith('ring_')).map(equipmentSlot=>{const entry=equipment.slots[equipmentSlot];const blocked=equipmentSlot==='focus'&&staffEquipped;return <article role="listitem" key={equipmentSlot} className={`equipment-card ${blocked?'is-blocked':''}`}>
                <span className="equipment-slot-label">{slotLabels[equipmentSlot]}</span>
                {blocked?<><strong>Durch Stab blockiert</strong><span className="equipment-base">Zweihandwaffe belegt beide Hände</span></>:entry?<><strong>{entry.item.name??entry.item.base_type??'Unbenanntes Item'}</strong><span className="equipment-base">{entry.item.base_type??entry.item.item_class??'Unbekannte Basis'}</span><span className={`rarity rarity-${(entry.item.rarity??'normal').toLowerCase()}`}>{entry.item.rarity??'Normal'}</span></>:<span className="equipment-empty">Nicht ausgerüstet</span>}
              </article>})}
            </div>
            <fieldset className="ring-target-group"><legend>Ring-Zielslot</legend><div className="ring-grid">
              {['ring_1','ring_2'].map(equipmentSlot=>{const entry=equipment.slots[equipmentSlot];return <label key={equipmentSlot} className={`equipment-card ${slot===equipmentSlot?'is-selected':''}`}>
                <input type="radio" name="ring-target" value={equipmentSlot} checked={slot===equipmentSlot} onChange={()=>selectRingTarget(equipmentSlot)} aria-label={`${slotLabels[equipmentSlot]} als Zielslot wählen`}/>
                <span className="equipment-slot-label">{slotLabels[equipmentSlot]}<small>{slot===equipmentSlot?'Zielslot':'auswählen'}</small></span>
                {entry?<><strong>{entry.item.name??entry.item.base_type??'Unbenanntes Item'}</strong><span className="equipment-base">{entry.item.base_type??entry.item.item_class??'Unbekannte Basis'}</span><span className={`rarity rarity-${(entry.item.rarity??'normal').toLowerCase()}`}>{entry.item.rarity??'Normal'}</span></>:<span className="equipment-empty">Nicht ausgerüstet</span>}
              </label>})}
            </div></fieldset>
          </>}
          <div className="equipment-file-actions"><label className={`file-button ${mutatingEquipment?'is-disabled':''}`}>Equipment importieren<input aria-label="Equipment-Datei importieren" disabled={mutatingEquipment||!buildId} type="file" accept="application/json,.json" onChange={e=>{void importFile(e.currentTarget.files?.[0]);e.currentTarget.value='' }}/></label><button className="text-button" type="button" disabled={!buildId} onClick={()=>void download()}>Equipment exportieren</button></div>
        </section>
      </aside>
    </main>
    <footer><span>PoE 2 Item Checker</span><span>Keine Markt- oder Trade-Bewertung</span></footer>
  </div>
}
