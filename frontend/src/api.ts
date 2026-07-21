export type ParseWarning = { code: string; message: string; lines: number[]; raw_lines: string[] }
export type LineBreakInsertion = { offset: number; code: string; message: string }
export type LineBreakSuggestion = { suggested_text: string; insertions: LineBreakInsertion[] }
export type Modifier = {
  source: string
  affix_type: string | null
  name: string | null
  tier: number | null
  tags: string[]
  raw_text: string
  normalized_key: string
  values: number[]
  roll_ranges: number[][]
  crafted: boolean
  desecrated: boolean
  rune: boolean
  implicit: boolean
  unique: boolean
}
export type ParsedItem = {
  raw_text: string
  unknown_lines: string[]
  item_class: string | null
  rarity: string | null
  name: string | null
  base_type: string | null
  required_level: number | null
  required_strength: number | null
  required_dexterity: number | null
  required_intelligence: number | null
  item_level: number | null
  quality: number | null
  granted_skill: string | null
  sockets: string[]
  armour: number | null
  armour_augmented: boolean
  evasion: number | null
  evasion_augmented: boolean
  energy_shield: number | null
  energy_shield_augmented: boolean
  spirit: number | null
  identified: boolean
  corrupted: boolean
  modifiers: Modifier[]
}
export type ParseResponse = {
  item: ParsedItem
  warnings: ParseWarning[]
  line_break_suggestion: LineBreakSuggestion | null
  auto_format_status: 'unchanged' | 'safe' | 'ambiguous'
}
export type BuildContext = { build_id: string; version: number; name: string; author: string; source_url: string; source_variant: string; archetype: string; core_skills: string[]; offensive_priorities: string[]; defensive_priorities: string[]; item_priorities: string[]; low_value_stats: string[]; constraints: string[] }
export type BuildAnalysis = Omit<BuildContext, 'build_id'|'version'|'source_url'> & { uncertainties: string[] }
export type BuildPreview = { preview_id:string; source_url:string; analysis:BuildAnalysis; citations:{url:string;title:string}[]; provider:string; model:string; expires_at:string }
export type EvaluationResult = { recommendation: 'better' | 'not_better' | 'uncertain'; confidence: 'low' | 'medium' | 'high'; reasons: string[]; warnings: string[]; verdict: 'upgrade'|'sidegrade'|'downgrade'; current_item_name: string; new_item_name: string; gains: string[]; losses: string[]; impacts: { damage:'better'|'similar'|'worse'; defensive:'better'|'similar'|'worse'; resistances:'better'|'similar'|'worse'; utility:'better'|'similar'|'worse' }; clear_recommendation: string; recommended_target_slot?: string|null }
export type EvaluateResponse = {
  parse: ParseResponse; build: BuildContext; target_slot: string; equipped: ParsedItem | null; evaluation: EvaluationResult | null
  target_slots: string[]; comparison_slots: string[]; available_target_slots?: string[]; equipped_slots: Record<string, ParsedItem | null>
  provider: string | null; model: string | null; provider_status: 'success' | 'unavailable'
  provider_error: { code: string; message: string } | null; disclaimer: string
}
export type Profile = { name: string; build_stage: string; character_level: number | null; life: number | null; energy_shield: number | null; mana: number | null; spirit: number | null; spirit_required: number | null; spirit_reserved: number | null; strength: number | null; dexterity: number | null; intelligence: number | null; fire_resistance: number | null; cold_resistance: number | null; lightning_resistance: number | null; chaos_resistance: number | null; resistance_cap: number; notes: string }
export type Equipment = { slots: Record<string, { id: string; item: ParsedItem } | null>; charm_capacity?: number; available_charm_slots?: string[] }
export type EquipmentImportResult = Equipment
export type EquipmentExport = { schema_version: 3; profile: Profile; equipment_raw_text: Record<string, string | null> }
const equipmentSlots = ['wand', 'focus', 'helmet', 'body_armour', 'gloves', 'boots', 'belt', 'ring_1', 'ring_2', 'amulet', 'charm_1', 'charm_2', 'charm_3']

export async function parseItem(rawText: string, signal: AbortSignal): Promise<ParseResponse> {
  const response = await fetch('/api/items/parse', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ raw_text: rawText }),
    signal,
  })
  if (!response.ok) {
    if (response.status === 422) throw new Error('Die Eingabe ist ungültig. Bitte prüfe den Itemtext.')
    throw new Error(`Analyse fehlgeschlagen (${response.status}).`)
  }
  return response.json() as Promise<ParseResponse>
}

export async function evaluateItem(rawText: string, signal: AbortSignal, targetSlot: string, buildId: string): Promise<EvaluateResponse> {
  const response = await fetch('/api/items/evaluate', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ raw_text: rawText, target_slot: targetSlot, build_id: buildId }), signal,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: { message?: string } } | null
    throw new Error(body?.detail?.message ?? `AI-Bewertung fehlgeschlagen (${response.status}).`)
  }
  return response.json() as Promise<EvaluateResponse>
}

export async function loadBuilds(): Promise<BuildContext[]> { const response = await fetch('/api/builds'); if (!response.ok) throw new Error('Builds konnten nicht geladen werden.'); return response.json() as Promise<BuildContext[]> }
export async function loadActiveBuild(signal?:AbortSignal): Promise<string|null> { const response=await fetch('/api/builds/active',{signal}); if(!response.ok)throw new Error('Aktiver Build konnte nicht geladen werden.'); return (await response.json() as {build_id:string|null}).build_id }
export async function saveActiveBuild(buildId:string,signal?:AbortSignal): Promise<string> { const response=await fetch('/api/builds/active',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({build_id:buildId}),signal}); if(!response.ok)throw new Error('Aktiver Build konnte nicht gespeichert werden.'); return (await response.json() as {build_id:string}).build_id }
async function buildError(response:Response):Promise<Error>{const body=await response.json().catch(()=>null) as {detail?:{message?:string}}|null;return new Error(body?.detail?.message??`Build-Aktion fehlgeschlagen (${response.status}).`)}
export async function deleteBuild(buildId:string,signal?:AbortSignal):Promise<{deleted_build_id:string;active_build_id:string|null}>{const response=await fetch(`/api/builds/${encodeURIComponent(buildId)}`,{method:'DELETE',signal});if(!response.ok)throw await buildError(response);const data:unknown=await response.json().catch(()=>null);if(typeof data!=='object'||data===null||Array.isArray(data)){throw new Error('Der Server hat nach dem Löschen keinen gültigen Build-Status geliefert.')}const deleted=(data as {deleted_build_id?:unknown}).deleted_build_id;const active=(data as {active_build_id?:unknown}).active_build_id;if(typeof deleted!=='string'||!deleted.trim()||deleted!==buildId||!(active===null||typeof active==='string'&&!!active.trim())){throw new Error('Der Server hat nach dem Löschen keinen gültigen Build-Status geliefert.')}return {deleted_build_id:deleted,active_build_id:active as string|null}}
export async function analyzeBuild(sourceUrl:string,signal?:AbortSignal):Promise<BuildPreview>{const response=await fetch('/api/builds/previews',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source_url:sourceUrl}),signal});if(!response.ok)throw await buildError(response);return response.json() as Promise<BuildPreview>}
export async function confirmBuild(previewId:string):Promise<BuildContext>{const response=await fetch(`/api/builds/previews/${encodeURIComponent(previewId)}/confirm`,{method:'POST'});if(!response.ok)throw await buildError(response);return response.json() as Promise<BuildContext>}

export async function loadEquipment(buildId:string, signal?: AbortSignal): Promise<Equipment> { const response = await fetch(`/api/builds/${encodeURIComponent(buildId)}/equipment`,{signal}); if (!response.ok) throw new Error('Equipment konnte nicht geladen werden.'); const data:unknown=await response.json().catch(()=>null); if(!isEquipment(data))throw new Error('Equipment konnte nicht geladen werden: Der Server hat keinen gültigen Equipment-Zustand geliefert.'); return data }
export async function saveEquipment(buildId:string, slot: string, raw_text: string, signal?: AbortSignal): Promise<{ id: string; item: ParsedItem }> { const response = await fetch(`/api/builds/${encodeURIComponent(buildId)}/equipment/${slot}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ raw_text }), signal }); if (!response.ok) { const body = await response.json().catch(() => null) as { detail?: { code?: string } } | null; throw new Error(body?.detail?.code === 'ambiguous_item_format' ? 'Der Itemtext ist mehrdeutig und muss manuell formatiert werden.' : 'Equipment konnte nicht gespeichert werden.') } return response.json() as Promise<{ id: string; item: ParsedItem }> }

export async function equipEquipment(buildId:string, raw_text: string, targetSlot: string, signal?: AbortSignal): Promise<Equipment> {
  const response = await fetch(`/api/builds/${encodeURIComponent(buildId)}/equipment/equip`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ raw_text, target_slot: targetSlot }), signal })
  if (!response.ok) throw await managementError(response, 'Equipment konnte nicht ausgerüstet werden')
  const data:unknown=await response.json().catch(()=>null)
  if(!isEquipment(data))throw new Error('Equipment konnte nicht ausgerüstet werden: Der Server hat keinen gültigen Equipment-Zustand geliefert.')
  return data
}

async function managementError(response: Response, fallback: string): Promise<Error> {
  const body = await response.json().catch(() => null) as {
    detail?: { code?: string } | { loc?: unknown[]; type?: string }[]
  } | null
  const detail = body?.detail
  const code = !Array.isArray(detail) ? detail?.code : undefined
  if (fallback === 'Import fehlgeschlagen') {
    if (code === 'item_slot_mismatch') return new Error('Import fehlgeschlagen: Mindestens ein Item passt nicht zu seinem Equipment-Slot.')
    if (code === 'incomplete_item' || code === 'ambiguous_item_format') return new Error('Import fehlgeschlagen: Mindestens ein Itemtext ist ungültig oder unvollständig.')
    if (code === 'invalid_equipment_snapshot') return new Error('Import fehlgeschlagen: Der Equipment-Snapshot ist unvollständig oder enthält ungültige Slots.')
    if (Array.isArray(detail)) {
      const snapshotInvalid = detail.some(error => error.loc?.includes('equipment_raw_text'))
      return new Error(snapshotInvalid
        ? 'Import fehlgeschlagen: Der Equipment-Snapshot ist unvollständig oder enthält ungültige Slots.'
        : 'Import fehlgeschlagen: Die Datei entspricht nicht dem unterstützten Equipment-Schema.')
    }
  }
  return new Error(code ? `${fallback} (${code}).` : `${fallback} (${response.status}).`)
}

export function isEquipment(value: unknown): value is Equipment {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return false
  const slots = (value as { slots?: unknown }).slots
  if (typeof slots !== 'object' || slots === null || Array.isArray(slots)) return false
  const mapping = slots as Record<string, unknown>
  if (Object.keys(mapping).length !== equipmentSlots.length
      || !equipmentSlots.every(slot => Object.hasOwn(mapping, slot))) return false
  return equipmentSlots.every(slot => {
    const entry = mapping[slot]
    if (entry === null) return true
    if (typeof entry !== 'object' || Array.isArray(entry)) return false
    const equipmentItem = entry as { id?: unknown; item?: unknown }
    if (typeof equipmentItem.id !== 'string'
        || typeof equipmentItem.item !== 'object' || equipmentItem.item === null
        || Array.isArray(equipmentItem.item)) return false
    return typeof (equipmentItem.item as { raw_text?: unknown }).raw_text === 'string'
  })
}

function sameEquipment(left: Equipment, right: Equipment): boolean {
  return equipmentSlots.every(slot => {
    const leftItem = left.slots[slot]
    const rightItem = right.slots[slot]
    return leftItem === null && rightItem === null
      || leftItem !== null && rightItem !== null
        && leftItem.id === rightItem.id && leftItem.item.raw_text === rightItem.item.raw_text
  })
}

export async function importEquipmentFile(buildId:string, file: File, signal?: AbortSignal): Promise<EquipmentImportResult> {
  if (file.size > 2_000_000) throw new Error('Die Importdatei ist größer als 2 MB.')
  let data: unknown
  try { data = JSON.parse(await file.text()) } catch { throw new Error('Die Importdatei enthält kein gültiges JSON.') }
  const isObject = typeof data === 'object' && data !== null && !Array.isArray(data)
  const schemaVersion = isObject ? (data as { schema_version?: unknown }).schema_version : undefined
  const structuredSlots = ['wand','focus','helmet','body_armour','gloves','boots','belt','ring1','ring2','amulet']
  const objectData = isObject ? data as Record<string, unknown> : null
  const isStructuredEquipment = isObject && schemaVersion === undefined
    && structuredSlots.every(slot => Object.hasOwn(objectData!, slot))
  if (!isObject || (![1, 2, 3].includes(typeof schemaVersion === 'number' ? schemaVersion : 0) && !isStructuredEquipment)) {
    throw new Error('Unterstützt werden Equipment-Dateien mit schema_version 1, 2 oder 3 sowie strukturierte PoE2-Equipment-Dateien.')
  }
  const response = await fetch(`/api/builds/${encodeURIComponent(buildId)}/equipment/import`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data), signal,
  })
  if (!response.ok) throw await managementError(response, 'Import fehlgeschlagen')
  const imported: unknown = await response.json().catch(() => null)
  if (!isEquipment(imported)) {
    throw new Error('Import fehlgeschlagen: Der Server hat keine gültige Equipment-Antwort geliefert.')
  }
  const verified: unknown = await loadEquipment(buildId, signal)
  if (!isEquipment(verified)) {
    throw new Error('Import konnte nicht verifiziert werden: Der Server hat keinen gültigen Equipment-Zustand geliefert.')
  }
  if (!sameEquipment(imported, verified)) {
    throw new Error('Import konnte nicht verifiziert werden: Der gespeicherte Serverzustand weicht von der Importantwort ab.')
  }
  return verified
}

export async function exportEquipmentFile(buildId:string): Promise<EquipmentExport> {
  const response = await fetch(`/api/builds/${encodeURIComponent(buildId)}/equipment/export`)
  if (!response.ok) throw await managementError(response, 'Export fehlgeschlagen')
  const isPlainObject = (value: unknown): value is Record<string, unknown> => (
    typeof value === 'object' && value !== null && !Array.isArray(value)
  )
  const data: unknown = await response.json()
  if (!isPlainObject(data)) throw new Error('Der Server hat keinen vollständigen v3-Export geliefert.')
  const raw = data.equipment_raw_text
  if (data.schema_version !== 3 || !isPlainObject(data.profile) || !isPlainObject(raw)
      || Object.keys(raw).length !== equipmentSlots.length
      || !equipmentSlots.every(slot => Object.hasOwn(raw, slot) && (typeof raw[slot] === 'string' || raw[slot] === null))) {
    throw new Error('Der Server hat keinen vollständigen v3-Export geliefert.')
  }
  return data as EquipmentExport
}
