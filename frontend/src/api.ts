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
}
export type ModifierFacts = { source: string; affix_type: string | null; name: string | null; tier: number | null; tags: string[]; raw_text: string; normalized_key: string; current_values: number[]; roll_ranges: number[][]; roll_position: number | null; relevance: string | null; config_rule: string | null; crafted: boolean; desecrated: boolean; rune: boolean; implicit: boolean; unique: boolean }
export type ItemFacts = { item_class: string; rarity: string; name: string; base_type: string | null; slot_hint: string | null; item_level: number | null; required_level: number | null; required_strength: number | null; required_dexterity: number | null; required_intelligence: number | null; quality: number | null; sockets: string[]; armour: number | null; armour_augmented: boolean; evasion: number | null; evasion_augmented: boolean; energy_shield: number | null; energy_shield_augmented: boolean; spirit: number | null; granted_skill: string | null; identified: boolean; corrupted: boolean; known_modifier_count: number; unknown_modifier_count: number; modifiers: ModifierFacts[]; warnings: string[] }
export type Evidence = { rule_id: string; message: string; matched_facts: string[] }
export type Assessment = { outcome: string; confidence: string; confidence_reasons: string[]; evidence: Evidence[] }
export type FactsCheck = { facts: ItemFacts; trade: Assessment; crafting: Assessment; warnings: string[]; disclaimer: string }
export type CheckResponse = { parse: ParseResponse; assessment: FactsCheck | null }
export type AiSection = { reasons: string[]; warnings: string[] }
export type EvaluationResult = {
  build: AiSection & { suitability: string }
  trade: AiSection & { recommendation: string }
  crafting: AiSection & { recommendation: string }
  confidence: string
  confidence_reasons: string[]
  warnings: string[]
}
export type EvaluateResponse = {
  parse: ParseResponse; local_check: FactsCheck; evaluation: EvaluationResult | null
  provider: string | null; model: string | null; provider_status: 'success' | 'unavailable'
  provider_error: { code: string; message: string } | null; disclaimer: string
  hard_checks: { target_slot: string | null; checks: { code: string; status: 'pass' | 'fail' | 'unknown'; message: string; before: number | null; after: number | null; required: number | null }[] }
  local_comparison: { recommended_target: string | null; comparisons: { target_slot: string; candidate: ScoredItem; equipped: ScoredItem | null; delta: number | null; delta_band: string | null; category: string; warnings: string[]; hard_checks: EvaluateResponse['hard_checks']; evidence_groups: { candidate_winners: ScoreEvidence[]; candidate_losers: ScoreEvidence[]; equipped_winners: ScoreEvidence[]; equipped_losers: ScoreEvidence[] } }[] }
}
export type ScoreEvidence = { rule_id: string; points: number; message: string; value?: number | null; cap?: number | null }
export type ScoredItem = { score: number; evidence: ScoreEvidence[]; unknown_modifier_count: number; completeness: 'complete' | 'partial'; warnings: string[]; confidence: 'high' | 'medium' | 'low'; known_relevant_modifier_count: number; rule_version: number }
export type Profile = { name: string; build_stage: string; character_level: number | null; life: number | null; energy_shield: number | null; mana: number | null; spirit: number | null; spirit_required: number | null; spirit_reserved: number | null; strength: number | null; dexterity: number | null; intelligence: number | null; fire_resistance: number | null; cold_resistance: number | null; lightning_resistance: number | null; chaos_resistance: number | null; resistance_cap: number; notes: string }
export type Equipment = { slots: Record<string, { id: string; item: ParsedItem } | null> }
export type EquipmentExport = { schema_version: 2; profile: Profile; equipment_raw_text: Record<string, string | null> }
export type HistoryStatus = 'checked' | 'equipped' | 'stored' | 'listed' | 'sold' | 'vendor'
export type SaleData = { listed_at: string | null; listed_currency: string | null; listed_amount: string | null; sold_at: string | null; sold_currency: string | null; sold_amount: string | null; notes: string }
export type HistoryEntry = { id: string; item_id: string; parent_evaluation_id: string | null; target_slot: string | null; status: HistoryStatus; category: string; delta_band: string | null; candidate_score: number; equipped_score: number | null; delta: number | null; confidence: string; completeness: string; rule_version: number; created_at: string; updated_at: string; item: ParsedItem; sale: SaleData | null; snapshot: Record<string, unknown> }
export type HistoryPage = { items: HistoryEntry[]; total: number; limit: number; offset: number }
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

export async function checkItem(rawText: string, signal: AbortSignal): Promise<CheckResponse> {
  const response = await fetch('/api/items/check', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ raw_text: rawText }), signal,
  })
  if (!response.ok) throw new Error(`Faktencheck fehlgeschlagen (${response.status}).`)
  return response.json() as Promise<CheckResponse>
}

export async function evaluateItem(rawText: string, signal: AbortSignal, targetSlot?: string): Promise<EvaluateResponse> {
  const response = await fetch('/api/items/evaluate', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ raw_text: rawText, target_slot: targetSlot }), signal,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: { message?: string } } | null
    throw new Error(body?.detail?.message ?? `AI-Bewertung fehlgeschlagen (${response.status}).`)
  }
  return response.json() as Promise<EvaluateResponse>
}

export async function loadProfile(): Promise<Profile> { const response = await fetch('/api/profile'); if (!response.ok) throw new Error('Profil konnte nicht geladen werden.'); return response.json() as Promise<Profile> }
export async function saveProfile(profile: Profile): Promise<Profile> { const response = await fetch('/api/profile', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(profile) }); if (!response.ok) throw new Error('Profil konnte nicht gespeichert werden.'); return response.json() as Promise<Profile> }
export async function loadEquipment(): Promise<Equipment> { const response = await fetch('/api/equipment'); if (!response.ok) throw new Error('Equipment konnte nicht geladen werden.'); return response.json() as Promise<Equipment> }
export async function saveEquipment(slot: string, raw_text: string): Promise<void> { const response = await fetch(`/api/equipment/${slot}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ raw_text }) }); if (!response.ok) throw new Error('Equipment konnte nicht gespeichert werden.') }

async function managementError(response: Response, fallback: string): Promise<Error> {
  const body = await response.json().catch(() => null) as { detail?: { code?: string } } | null
  return new Error(body?.detail?.code ? `${fallback} (${body.detail.code}).` : `${fallback} (${response.status}).`)
}

export async function importEquipmentFile(file: File): Promise<Equipment> {
  if (file.size > 2_000_000) throw new Error('Die Importdatei ist größer als 2 MB.')
  let data: unknown
  try { data = JSON.parse(await file.text()) } catch { throw new Error('Die Importdatei enthält kein gültiges JSON.') }
  if (typeof data !== 'object' || data === null || ![1, 2].includes((data as { schema_version?: number }).schema_version ?? 0)) {
    throw new Error('Nur Equipment-Dateien mit schema_version 1 oder 2 werden unterstützt.')
  }
  const response = await fetch('/api/equipment/import', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
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

export async function persistEvaluation(rawText: string, targetSlot: string, signal: AbortSignal): Promise<HistoryEntry> {
  const response = await fetch('/api/history', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ raw_text: rawText, target_slot: targetSlot, use_profile: true }), signal })
  if (!response.ok) throw await managementError(response, 'Speichern fehlgeschlagen')
  return response.json() as Promise<HistoryEntry>
}

export async function loadHistory(filters: Record<string, string>, signal?: AbortSignal): Promise<HistoryPage> {
  const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value !== ''))
  const response = await fetch(`/api/history?${query}`, { signal })
  if (!response.ok) throw await managementError(response, 'History konnte nicht geladen werden')
  return response.json() as Promise<HistoryPage>
}

export async function updateHistory(id: string, data: { status: HistoryStatus } & SaleData, signal?: AbortSignal): Promise<HistoryEntry> {
  const response = await fetch(`/api/history/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data), signal })
  if (!response.ok) throw await managementError(response, 'History konnte nicht aktualisiert werden')
  return response.json() as Promise<HistoryEntry>
}

export async function recompareHistory(id: string, signal?: AbortSignal): Promise<HistoryEntry> {
  const response = await fetch(`/api/history/${id}/recompare`, { method: 'POST', signal })
  if (!response.ok) throw await managementError(response, 'Erneuter Vergleich fehlgeschlagen')
  return response.json() as Promise<HistoryEntry>
}

export async function exportBackup(): Promise<unknown> {
  const response = await fetch('/api/backup')
  if (!response.ok) throw await managementError(response, 'Backup fehlgeschlagen')
  return response.json() as Promise<unknown>
}

export async function parseBackupFile(file: File): Promise<unknown> {
  if (file.size > 10_000_000) throw new Error('Die Backup-Datei ist größer als 10 MB.')
  let data: unknown
  try { data = JSON.parse(await file.text()) } catch { throw new Error('Die Backup-Datei enthält kein gültiges JSON.') }
  if (typeof data !== 'object' || data === null || (data as { schema_version?: unknown }).schema_version !== 1) throw new Error('Nur Vollbackups mit schema_version 1 werden unterstützt.')
  return data
}

export async function restoreBackup(data: unknown, signal?: AbortSignal): Promise<void> {
  const response = await fetch('/api/backup/restore', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data), signal })
  if (!response.ok) throw await managementError(response, 'Restore fehlgeschlagen')
}
