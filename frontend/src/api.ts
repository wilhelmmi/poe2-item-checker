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
