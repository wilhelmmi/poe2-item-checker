import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from './App'
import { CheckResponse, ParseResponse } from './api'

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

function response(body: unknown, ok = true, status = 200) {
  return { ok, status, json: async () => body } as Response
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('manual parse preview', () => {
  it('shows a successful preview and warning', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(parsed)))
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
    vi.stubGlobal('fetch', fetchMock)
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
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise<Response>(resolve => { resolveRequest = resolve })))
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
    vi.stubGlobal('fetch', fetchMock)
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
    vi.stubGlobal('fetch', fetchMock)
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
    vi.stubGlobal('fetch', fetchMock)
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
    vi.stubGlobal('fetch', fetchMock)
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
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'), { target: { value: 'item' } })
    fireEvent.click(screen.getByRole('button', { name: 'Analysieren' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Faktencheck ausführen' }))
    expect((await screen.findByRole('alert')).textContent).toContain('Faktencheck fehlgeschlagen')
    expect(screen.queryByText('Lokaler Faktencheck')).toBeNull()
  })
})
