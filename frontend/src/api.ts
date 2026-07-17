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
export type BuildContext = { build_id: string; version: number; name: string; author: string; source_url: string; source_variant: string; archetype: string; core_skills: string[]; offensive_priorities: string[]; defensive_priorities: string[]; constraints: string[] }
export type EvaluationResult = { recommendation: 'better' | 'not_better' | 'uncertain'; confidence: 'low' | 'medium' | 'high'; reasons: string[]; warnings: string[] }
export type EvaluateResponse = {
  parse: ParseResponse; build: BuildContext; target_slot: string; equipped: ParsedItem; evaluation: EvaluationResult | null
  provider: string | null; model: string | null; provider_status: 'success' | 'unavailable'
  provider_error: { code: string; message: string } | null; disclaimer: string
}
export type Profile = { name: string; build_stage: string; character_level: number | null; life: number | null; energy_shield: number | null; mana: number | null; spirit: number | null; spirit_required: number | null; spirit_reserved: number | null; strength: number | null; dexterity: number | null; intelligence: number | null; fire_resistance: number | null; cold_resistance: number | null; lightning_resistance: number | null; chaos_resistance: number | null; resistance_cap: number; notes: string }
export type Equipment = { slots: Record<string, { id: string; item: ParsedItem } | null> }
export type EquipmentExport = { schema_version: 2; profile: Profile; equipment_raw_text: Record<string, string | null> }
const equipmentSlots = ['wand', 'focus', 'helmet', 'body_armour', 'gloves', 'boots', 'belt', 'ring_1', 'ring_2', 'amulet']

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

export async function loadProfile(): Promise<Profile> { const response = await fetch('/api/profile'); if (!response.ok) throw new Error('Profil konnte nicht geladen werden.'); return response.json() as Promise<Profile> }
export async function saveProfile(profile: Profile): Promise<Profile> { const response = await fetch('/api/profile', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(profile) }); if (!response.ok) throw new Error('Profil konnte nicht gespeichert werden.'); return response.json() as Promise<Profile> }
export async function loadEquipment(signal?: AbortSignal): Promise<Equipment> { const response = await fetch('/api/equipment',{signal}); if (!response.ok) throw new Error('Equipment konnte nicht geladen werden.'); return response.json() as Promise<Equipment> }
export async function saveEquipment(slot: string, raw_text: string, signal?: AbortSignal): Promise<{ id: string; item: ParsedItem }> { const response = await fetch(`/api/equipment/${slot}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ raw_text }), signal }); if (!response.ok) { const body = await response.json().catch(() => null) as { detail?: { code?: string } } | null; throw new Error(body?.detail?.code === 'ambiguous_item_format' ? 'Der Itemtext ist mehrdeutig und muss manuell formatiert werden.' : 'Equipment konnte nicht gespeichert werden.') } return response.json() as Promise<{ id: string; item: ParsedItem }> }

async function managementError(response: Response, fallback: string): Promise<Error> {
  const body = await response.json().catch(() => null) as { detail?: { code?: string } } | null
  return new Error(body?.detail?.code ? `${fallback} (${body.detail.code}).` : `${fallback} (${response.status}).`)
}

export async function importEquipmentFile(file: File, signal?: AbortSignal): Promise<Equipment> {
  if (file.size > 2_000_000) throw new Error('Die Importdatei ist größer als 2 MB.')
  let data: unknown
  try { data = JSON.parse(await file.text()) } catch { throw new Error('Die Importdatei enthält kein gültiges JSON.') }
  if (typeof data !== 'object' || data === null || ![1, 2].includes((data as { schema_version?: number }).schema_version ?? 0)) {
    throw new Error('Nur Equipment-Dateien mit schema_version 1 oder 2 werden unterstützt.')
  }
  const response = await fetch('/api/equipment/import', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data), signal,
  })
  if (!response.ok) throw await managementError(response, 'Import fehlgeschlagen')
  return response.json() as Promise<Equipment>
}

export async function exportEquipmentFile(): Promise<EquipmentExport> {
  const response = await fetch('/api/equipment/export')
  if (!response.ok) throw await managementError(response, 'Export fehlgeschlagen')
  const isPlainObject = (value: unknown): value is Record<string, unknown> => (
    typeof value === 'object' && value !== null && !Array.isArray(value)
  )
  const data: unknown = await response.json()
  if (!isPlainObject(data)) throw new Error('Der Server hat keinen vollständigen v2-Export geliefert.')
  const raw = data.equipment_raw_text
  if (data.schema_version !== 2 || !isPlainObject(data.profile) || !isPlainObject(raw)
      || Object.keys(raw).length !== equipmentSlots.length
      || !equipmentSlots.every(slot => Object.hasOwn(raw, slot) && (typeof raw[slot] === 'string' || raw[slot] === null))) {
    throw new Error('Der Server hat keinen vollständigen v2-Export geliefert.')
  }
  return data as EquipmentExport
}
