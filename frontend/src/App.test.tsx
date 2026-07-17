import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from './App'
import { CheckResponse, EvaluateResponse, ParseResponse } from './api'

const parsed: ParseResponse = {
  item: {
    raw_text: 'Item Class: Rings', unknown_lines: ['Mystery'], item_class: 'Rings', rarity: 'Normal',
    name: 'Iron Ring', base_type: 'Iron Ring', required_level: null, required_strength: null,
    required_dexterity: null, required_intelligence: null, item_level: 1, quality: 0,
    granted_skill: null, sockets: [], armour: null, armour_augmented: false, evasion: null,
    evasion_augmented: false, energy_shield: null, energy_shield_augmented: false, spirit: null,
    identified: true, corrupted: false, modifiers: [],
  },
  warnings: [{ code: 'unknown_lines_preserved', message: 'Unbekannt erhalten.', lines: [2], raw_lines: ['Mystery'] }],
  line_break_suggestion: null,
}

const suggested: ParseResponse = {
  ...parsed,
  line_break_suggestion: {
    suggested_text: 'Item Class: Rings\nRarity: Normal\nIron Ring',
    insertions: [{ offset: 17, code: 'before_rarity', message: 'Grenze ergänzt.' }],
  },
}

const checked: CheckResponse = {
  parse: parsed,
  assessment: {
    facts: { item_class: 'Rings', rarity: 'Normal', name: 'Iron Ring', base_type: 'Iron Ring', slot_hint: null, item_level: 1, required_level: null, required_strength: null, required_dexterity: null, required_intelligence: null, quality: null, sockets: [], armour: null, armour_augmented: false, evasion: null, evasion_augmented: false, energy_shield: null, energy_shield_augmented: false, spirit: null, granted_skill: null, identified: true, corrupted: false, known_modifier_count: 0, unknown_modifier_count: 0, modifiers: [], warnings: [] },
    trade: { outcome: 'manual_review', confidence: 'low', confidence_reasons: ['Keine Regel.'], evidence: [] },
    crafting: { outcome: 'needs_review', confidence: 'low', confidence_reasons: ['Keine Regel.'], evidence: [] },
    warnings: ['slot_hint_unknown'], disclaimer: 'Keine garantierte Marktpreisermittlung.',
  },
}

const evaluated: EvaluateResponse = {
  parse: parsed, local_check: checked.assessment!, provider: 'fake', model: 'mock-model',
  disclaimer: 'Keine garantierte Live-Marktpreisermittlung.', provider_status: 'success', provider_error: null,
  hard_checks: { target_slot: null, checks: [{ code: 'requirement_level', status: 'unknown', message: 'Wert fehlt.', before: null, after: null, required: null }] },
  local_comparison: { recommended_target: 'wand', comparisons: [{ target_slot: 'wand', candidate: { score: 30, evidence: [{ rule_id: 'base', points: 30, message: 'Candidate' }], unknown_modifier_count: 0, completeness: 'complete', warnings: [], confidence: 'high', known_relevant_modifier_count: 1, rule_version: 2 }, equipped: { score: 20, evidence: [{ rule_id: 'base', points: 20, message: 'Equipped' }], unknown_modifier_count: 0, completeness: 'complete', warnings: [], confidence: 'high', known_relevant_modifier_count: 1, rule_version: 2 }, delta: 10, delta_band: 'positive', category: 'upgrade', warnings: [], hard_checks: { target_slot: 'wand', checks: [] }, evidence_groups: { candidate_winners: [{ rule_id: 'base', points: 30, message: 'Candidate' }], candidate_losers: [], equipped_winners: [{ rule_id: 'base', points: 20, message: 'Equipped' }], equipped_losers: [] } }] },
  evaluation: {
    build: { suitability: 'unknown_without_profile', reasons: ['Profil fehlt.'], warnings: [] },
    trade: { recommendation: 'manual_review', reasons: ['Keine Live-Daten.'], warnings: [] },
    crafting: { recommendation: 'needs_review', reasons: ['Prüfen.'], warnings: [] },
    confidence: 'low', confidence_reasons: ['Equipment fehlt.'], warnings: [],
  },
}

const evaluationFallback: EvaluateResponse = {
  parse: parsed, local_check: checked.assessment!, evaluation: null,
  provider: null, model: null, provider_status: 'unavailable',
  provider_error: { code: 'provider_not_configured', message: 'AI ist nicht konfiguriert.' },
  disclaimer: 'Lokaler Fallback wurde ausgeführt.',
  hard_checks: { target_slot: null, checks: [] },
  local_comparison: { recommended_target: null, comparisons: [] },
}
const profile = { name: 'Chaos DoT Lich', build_stage: 'early_endgame', character_level: 70,
  life: 1000, energy_shield: 2000, mana: 500, spirit: 120, spirit_required: 100,
  spirit_reserved: 90, strength: 20, dexterity: 30, intelligence: 100,
  fire_resistance: 75, cold_resistance: 75, lightning_resistance: 75,
  chaos_resistance: 20, resistance_cap: 75, notes: 'Test' }

function response(body: unknown, ok = true, status = 200) {
  return { ok, status, json: async () => body } as Response
}

function stubFetch(mock: ReturnType<typeof vi.fn>) {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    if (String(input).startsWith('/api/history?')) return Promise.resolve(response({ items: [], total: 0, limit: 20, offset: 0 }))
    return mock(input, init)
  }))
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('manual parse preview', () => {
  it('lädt History initial und paginiert mit total/offset', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({ items: [], total: 25, limit: 20, offset: 0 }))
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    const next = await screen.findByRole('button', { name: 'Weiter' })
    expect((next as HTMLButtonElement).disabled).toBe(false)
    fireEvent.click(next)
    await waitFor(() => expect(fetchMock.mock.calls.some(call => String(call[0]).includes('offset=20'))).toBe(true))
  })

  it('sendet Restore erst nach separater destruktiver Bestätigung', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({}, true, 204))
    stubFetch(fetchMock)
    render(<App />)
    const file = { name: 'sicherung.json', size: 30, text: async () => JSON.stringify({ schema_version: 1 }) } as File
    fireEvent.change(screen.getByLabelText('Vollbackup wiederherstellen'), { target: { files: [file] } })
    expect(await screen.findByText(/sicherung.json/)).toBeTruthy()
    expect(fetchMock).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Restore endgültig bestätigen' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/backup/restore', expect.objectContaining({ method: 'POST' })))
  })

  it('shows a successful preview and warning', async () => {
    stubFetch(vi.fn().mockResolvedValue(response(parsed)))
    render(<App />)
    fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'), { target: { value: 'item' } })
    fireEvent.click(screen.getByRole('button', { name: 'Analysieren' }))
    expect(await screen.findByText('Erkannte Struktur')).toBeTruthy()
    expect(screen.getByText(/Unbekannt erhalten/)).toBeTruthy()
    expect(screen.getByText('Item Class: Rings')).toBeTruthy()
  })

  it('shows an API error without an old preview', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response(parsed))
      .mockResolvedValueOnce(response(parsed, false, 500))
    stubFetch(fetchMock)
    render(<App />)
    const input = screen.getByLabelText('Englischen Itemtext einfügen')
    fireEvent.change(input, { target: { value: 'first' } })
    fireEvent.click(screen.getByRole('button', { name: 'Analysieren' }))
    await screen.findByText('Erkannte Struktur')
    fireEvent.change(input, { target: { value: 'second' } })
    fireEvent.click(screen.getByRole('button', { name: 'Analysieren' }))
    expect((await screen.findByRole('alert')).textContent).toContain('Analyse fehlgeschlagen')
    expect(screen.queryByText('Erkannte Struktur')).toBeNull()
  })

  it('does not show a delayed response after the text was edited', async () => {
    let resolveRequest: (value: Response) => void = () => undefined
    stubFetch(vi.fn().mockReturnValue(new Promise<Response>(resolve => { resolveRequest = resolve })))
    render(<App />)
    const input = screen.getByLabelText('Englischen Itemtext einfügen')
    fireEvent.change(input, { target: { value: 'submitted' } })
    fireEvent.click(screen.getByRole('button', { name: 'Analysieren' }))
    expect(screen.getByRole('status')).toBeTruthy()
    fireEvent.change(input, { target: { value: 'edited' } })
    resolveRequest(response(parsed))
    await waitFor(() => expect(screen.queryByRole('status')).toBeNull())
    expect(screen.queryByText('Erkannte Struktur')).toBeNull()
  })

  it('keeps the suggestion separate, editable, and reparses only after acceptance', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(suggested))
    stubFetch(fetchMock)
    render(<App />)
    const mainInput = screen.getByLabelText('Englischen Itemtext einfügen') as HTMLTextAreaElement
    fireEvent.change(mainInput, { target: { value: 'collapsed' } })
    fireEvent.click(screen.getByRole('button', { name: 'Analysieren' }))
    const draft = await screen.findByLabelText('Editierbarer Vorschlag') as HTMLTextAreaElement
    expect(mainInput.value).toBe('collapsed')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    fireEvent.change(draft, { target: { value: 'edited\ndraft' } })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: 'Vorschlag übernehmen' }))
    expect(mainInput.value).toBe('edited\ndraft')
    expect(screen.queryByText('Erkannte Struktur')).toBeNull()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: 'Erneut analysieren' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    expect(JSON.parse(fetchMock.mock.calls[1][1].body as string)).toEqual({ raw_text: 'edited\ndraft' })
  })

  it('discards a suggestion without changing or reparsing the original', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(suggested))
    stubFetch(fetchMock)
    render(<App />)
    const mainInput = screen.getByLabelText('Englischen Itemtext einfügen') as HTMLTextAreaElement
    fireEvent.change(mainInput, { target: { value: 'collapsed' } })
    fireEvent.click(screen.getByRole('button', { name: 'Analysieren' }))
    await screen.findByLabelText('Editierbarer Vorschlag')
    fireEvent.click(screen.getByRole('button', { name: 'Verwerfen' }))
    expect(screen.queryByLabelText('Editierbarer Vorschlag')).toBeNull()
    expect(mainInput.value).toBe('collapsed')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('runs the facts check only after an explicit action and shows separate panels', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(response(parsed)).mockResolvedValueOnce(response(checked))
    stubFetch(fetchMock)
    render(<App />)
    fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'), { target: { value: 'item' } })
    fireEvent.click(screen.getByRole('button', { name: 'Analysieren' }))
    await screen.findByRole('button', { name: 'Faktencheck ausführen' })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: 'Faktencheck ausführen' }))
    expect(await screen.findByText('Lokaler Faktencheck')).toBeTruthy()
    expect(screen.getByText('Lokale Verkaufsempfehlung')).toBeTruthy()
    expect(screen.getByText('Crafting')).toBeTruthy()
    expect(fetchMock.mock.calls[1][0]).toBe('/api/items/check')
  })

  it('clears a delayed facts check when the text changes', async () => {
    let resolveCheck: (value: Response) => void = () => undefined
    const fetchMock = vi.fn().mockResolvedValueOnce(response(parsed)).mockReturnValueOnce(new Promise<Response>(resolve => { resolveCheck = resolve }))
    stubFetch(fetchMock)
    render(<App />)
    const input = screen.getByLabelText('Englischen Itemtext einfügen')
    fireEvent.change(input, { target: { value: 'item' } })
    fireEvent.click(screen.getByRole('button', { name: 'Analysieren' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Faktencheck ausführen' }))
    fireEvent.change(input, { target: { value: 'changed' } })
    resolveCheck(response(checked))
    await waitFor(() => expect(screen.queryByText('Lokaler Faktencheck')).toBeNull())
  })

  it('shows a facts-check API error without a result panel', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(response(parsed)).mockResolvedValueOnce(response(parsed, false, 500))
    stubFetch(fetchMock)
    render(<App />)
    fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'), { target: { value: 'item' } })
    fireEvent.click(screen.getByRole('button', { name: 'Analysieren' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Faktencheck ausführen' }))
    expect((await screen.findByRole('alert')).textContent).toContain('Faktencheck fehlgeschlagen')
    expect(screen.queryByText('Lokaler Faktencheck')).toBeNull()
  })

  it('runs AI evaluation only after its explicit action', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(response(parsed)).mockResolvedValueOnce(response(evaluated))
    stubFetch(fetchMock)
    render(<App />)
    fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'), { target: { value: 'item' } })
    fireEvent.click(screen.getByRole('button', { name: 'Analysieren' }))
    const button = await screen.findByRole('button', { name: 'AI-Bewertung ausführen' })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    fireEvent.click(button)
    expect(await screen.findByText('Lokaler Equipmentvergleich')).toBeTruthy()
    expect(screen.getByText('wand: positive')).toBeTruthy()
    expect(fetchMock.mock.calls[1][0]).toBe('/api/items/evaluate')
    expect(screen.getByText(/mock-model/)).toBeTruthy()
  })

  it('shows the local fallback when the provider is unavailable', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(response(parsed)).mockResolvedValueOnce(response(evaluationFallback))
    stubFetch(fetchMock)
    render(<App />)
    fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'), { target: { value: 'item' } })
    fireEvent.click(screen.getByRole('button', { name: 'Analysieren' }))
    fireEvent.click(await screen.findByRole('button', { name: 'AI-Bewertung ausführen' }))
    expect(await screen.findByText('Lokaler Faktencheck')).toBeTruthy()
    expect(screen.getByText(/AI ist nicht konfiguriert/)).toBeTruthy()
    expect(screen.getByText(/provider_not_configured/)).toBeTruthy()
  })

  it('ignores a delayed AI response after a new parse starts', async () => {
    let resolveEvaluation: (value: Response) => void = () => undefined
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response(parsed))
      .mockReturnValueOnce(new Promise<Response>(resolve => { resolveEvaluation = resolve }))
      .mockResolvedValueOnce(response(parsed))
    stubFetch(fetchMock)
    render(<App />)
    const input = screen.getByLabelText('Englischen Itemtext einfügen')
    fireEvent.change(input, { target: { value: 'first' } })
    fireEvent.click(screen.getByRole('button', { name: 'Analysieren' }))
    fireEvent.click(await screen.findByRole('button', { name: 'AI-Bewertung ausführen' }))
    fireEvent.click(screen.getByRole('button', { name: 'Analysieren' }))
    resolveEvaluation(response(evaluated))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
    expect(screen.queryByText('Lokaler Equipmentvergleich')).toBeNull()
  })

  it('ignores a delayed AI response after accepting a line-break suggestion', async () => {
    let resolveEvaluation: (value: Response) => void = () => undefined
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response(suggested))
      .mockReturnValueOnce(new Promise<Response>(resolve => { resolveEvaluation = resolve }))
    stubFetch(fetchMock)
    render(<App />)
    fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'), { target: { value: 'collapsed' } })
    fireEvent.click(screen.getByRole('button', { name: 'Analysieren' }))
    await screen.findByLabelText('Editierbarer Vorschlag')
    fireEvent.click(screen.getByRole('button', { name: 'AI-Bewertung ausführen' }))
    fireEvent.click(screen.getByRole('button', { name: 'Vorschlag übernehmen' }))
    resolveEvaluation(response(evaluated))
    await waitFor(() => expect(screen.queryByText('Lokaler Equipmentvergleich')).toBeNull())
    expect(screen.queryByText('Lokaler Faktencheck')).toBeNull()
  })

  it('invalidates an existing AI result and facts when the target slot changes', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(response(parsed)).mockResolvedValueOnce(response(evaluated))
    stubFetch(fetchMock)
    render(<App />)
    fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'), { target: { value: 'item' } })
    fireEvent.click(screen.getByRole('button', { name: 'Analysieren' }))
    fireEvent.click(await screen.findByRole('button', { name: 'AI-Bewertung ausführen' }))
    await screen.findByText('Lokaler Equipmentvergleich')
    expect(screen.getByText('Lokaler Faktencheck')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Equipment-Slot'), { target: { value: 'boots' } })
    expect(screen.queryByText('Lokaler Equipmentvergleich')).toBeNull()
    expect(screen.queryByText('Lokaler Faktencheck')).toBeNull()
  })

  it('ignores a delayed AI response when the target slot changes', async () => {
    let resolveEvaluation: (value: Response) => void = () => undefined
    const fetchMock = vi.fn().mockResolvedValueOnce(response(parsed)).mockReturnValueOnce(new Promise<Response>(resolve => { resolveEvaluation = resolve }))
    stubFetch(fetchMock)
    render(<App />)
    fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'), { target: { value: 'item' } })
    fireEvent.click(screen.getByRole('button', { name: 'Analysieren' }))
    fireEvent.click(await screen.findByRole('button', { name: 'AI-Bewertung ausführen' }))
    fireEvent.change(screen.getByLabelText('Equipment-Slot'), { target: { value: 'boots' } })
    resolveEvaluation(response(evaluated))
    await waitFor(() => expect(screen.queryByText('Lokaler Equipmentvergleich')).toBeNull())
  })

  it('edits every hard-check profile field and preserves nullable numbers', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(response(profile)).mockResolvedValueOnce(response({ ...profile, life: null }))
    stubFetch(fetchMock)
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Profil laden' }))
    await screen.findByLabelText('Spirit Required')
    for (const label of ['Life', 'Energy Shield', 'Mana', 'Spirit', 'Spirit Reserved', 'Fire Resistance', 'Cold Resistance', 'Lightning Resistance', 'Chaos Resistance', 'Resistance Cap', 'Build Stage', 'Notes']) {
      expect(screen.getByLabelText(label)).toBeTruthy()
    }
    fireEvent.change(screen.getByLabelText('Life'), { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: 'Profil speichern' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    expect(JSON.parse(fetchMock.mock.calls[1][1].body as string).life).toBeNull()
  })

  it('shows equipped evidence and invalidates comparison when profile context loads', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(response(parsed)).mockResolvedValueOnce(response(evaluated)).mockResolvedValueOnce(response(profile))
    stubFetch(fetchMock)
    render(<App />)
    fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'), { target: { value: 'item' } })
    fireEvent.click(screen.getByRole('button', { name: 'Analysieren' }))
    fireEvent.click(await screen.findByRole('button', { name: 'AI-Bewertung ausführen' }))
    expect(await screen.findByText('Equipped Evidence')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Profil laden' }))
    expect(screen.queryByText('Lokaler Equipmentvergleich')).toBeNull()
  })

  it('invalidates an evaluation started while a profile load is pending', async () => {
    let resolveProfile: (value: Response) => void = () => undefined
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      if (input === '/api/profile') return new Promise<Response>(resolve => { resolveProfile = resolve })
      if (input === '/api/items/parse') return Promise.resolve(response(parsed))
      if (input === '/api/items/evaluate') return Promise.resolve(response(evaluated))
      return Promise.reject(new Error('unexpected request'))
    })
    stubFetch(fetchMock)
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Profil laden' }))
    fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'), { target: { value: 'item' } })
    fireEvent.click(screen.getByRole('button', { name: 'Analysieren' }))
    fireEvent.click(await screen.findByRole('button', { name: 'AI-Bewertung ausführen' }))
    await screen.findByText('Lokaler Equipmentvergleich')
    resolveProfile(response(profile))
    await waitFor(() => expect(screen.queryByText('Lokaler Equipmentvergleich')).toBeNull())
  })

  it('ignores an older import response and permits selecting the same file again', async () => {
    let resolveFirst: (value: Response) => void = () => undefined
    let imports = 0
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      if (input === '/api/equipment/import') {
        imports += 1
        if (imports === 1) return new Promise<Response>(resolve => { resolveFirst = resolve })
        return Promise.resolve(response({ slots: {} }))
      }
      if (input === '/api/profile') return Promise.resolve(response(profile))
      return Promise.reject(new Error('unexpected request'))
    })
    stubFetch(fetchMock)
    render(<App />)
    const input = screen.getByLabelText('Equipment-Datei importieren') as HTMLInputElement
    const file = { size: 20, text: async () => JSON.stringify({ schema_version: 1 }) } as File
    fireEvent.change(input, { target: { files: [file] } })
    fireEvent.change(input, { target: { files: [file] } })
    expect(await screen.findByText('Equipment-Datei erfolgreich importiert.')).toBeTruthy()
    resolveFirst(response({ detail: { code: 'stale_failure' } }, false, 422))
    await waitFor(() => expect(screen.queryByText(/stale_failure/)).toBeNull())
    await waitFor(() => expect(input.value).toBe(''))
    expect(imports).toBe(2)
  })

  it('does not let an older profile load overwrite a successfully imported profile', async () => {
    let resolveOldProfile: (value: Response) => void = () => undefined
    let profileLoads = 0
    const importedProfile = { ...profile, name: 'Importiertes Profil' }
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      if (input === '/api/equipment/import') return Promise.resolve(response({ slots: {} }))
      if (input === '/api/profile') {
        profileLoads += 1
        if (profileLoads === 1) return new Promise<Response>(resolve => { resolveOldProfile = resolve })
        return Promise.resolve(response(importedProfile))
      }
      return Promise.reject(new Error('unexpected request'))
    })
    stubFetch(fetchMock)
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Profil laden' }))
    const input = screen.getByLabelText('Equipment-Datei importieren')
    const file = { size: 20, text: async () => JSON.stringify({ schema_version: 1 }) } as File
    fireEvent.change(input, { target: { files: [file] } })
    expect(await screen.findByDisplayValue('Importiertes Profil')).toBeTruthy()
    resolveOldProfile(response({ ...profile, name: 'Veraltetes Profil' }))
    await waitFor(() => expect(screen.queryByDisplayValue('Veraltetes Profil')).toBeNull())
    expect(screen.getByDisplayValue('Importiertes Profil')).toBeTruthy()
  })

  it('preserves a local profile edit made while a profile load is pending', async () => {
    let resolvePending: (value: Response) => void = () => undefined
    let loads = 0
    stubFetch(vi.fn((input: RequestInfo | URL) => {
      if (input !== '/api/profile') return Promise.reject(new Error('unexpected request'))
      loads += 1
      if (loads === 1) return Promise.resolve(response(profile))
      return new Promise<Response>(resolve => { resolvePending = resolve })
    }))
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Profil laden' }))
    const name = await screen.findByLabelText('Name')
    fireEvent.click(screen.getByRole('button', { name: 'Profil laden' }))
    fireEvent.change(name, { target: { value: 'Lokale Änderung' } })
    resolvePending(response({ ...profile, name: 'Verspäteter Load' }))
    await waitFor(() => expect(screen.queryByDisplayValue('Verspäteter Load')).toBeNull())
    expect(screen.getByDisplayValue('Lokale Änderung')).toBeTruthy()
  })

  it('preserves a local profile edit made while a profile save is pending', async () => {
    let resolveSave: (value: Response) => void = () => undefined
    stubFetch(vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (input === '/api/profile' && init?.method === 'PUT') {
        return new Promise<Response>(resolve => { resolveSave = resolve })
      }
      if (input === '/api/profile') return Promise.resolve(response(profile))
      return Promise.reject(new Error('unexpected request'))
    }))
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Profil laden' }))
    const name = await screen.findByLabelText('Name')
    fireEvent.click(screen.getByRole('button', { name: 'Profil speichern' }))
    fireEvent.change(name, { target: { value: 'Nach Save editiert' } })
    resolveSave(response({ ...profile, name: 'Verspätetes Save-Ergebnis' }))
    await waitFor(() => expect(screen.queryByDisplayValue('Verspätetes Save-Ergebnis')).toBeNull())
    expect(screen.getByDisplayValue('Nach Save editiert')).toBeTruthy()
  })

  it('preserves local equipment text entered while a slot load is pending', async () => {
    let resolveSlot: (value: Response) => void = () => undefined
    stubFetch(vi.fn((input: RequestInfo | URL) => {
      if (input === '/api/equipment') return new Promise<Response>(resolve => { resolveSlot = resolve })
      return Promise.reject(new Error('unexpected request'))
    }))
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Slot laden' }))
    const text = screen.getByLabelText('Itemtext des Slots')
    fireEvent.change(text, { target: { value: 'Lokaler Itemtext' } })
    resolveSlot(response({ slots: { wand: { item: { raw_text: 'Verspäteter Slottext' } } } }))
    await waitFor(() => expect(screen.queryByDisplayValue('Verspäteter Slottext')).toBeNull())
    expect(screen.getByDisplayValue('Lokaler Itemtext')).toBeTruthy()
  })
})
