import { afterEach, describe, expect, it, vi } from 'vitest'

import { exportEquipmentFile, importEquipmentFile } from './api'

afterEach(() => vi.unstubAllGlobals())

describe('Equipment-Dateien', () => {
  const slots = Object.fromEntries(
    ['wand', 'focus', 'helmet', 'body_armour', 'gloves', 'boots', 'belt', 'ring_1', 'ring_2', 'amulet']
      .map(slot => [slot, null]),
  )
  it('weist ungültiges JSON vor einem Request zurück', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const file = { size: 10, text: async () => '{broken' } as File
    await expect(importEquipmentFile(file)).rejects.toThrow('kein gültiges JSON')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('akzeptiert nur Schema v1 oder v2 vor einem Request', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const file = { size: 30, text: async () => JSON.stringify({ schema_version: 3 }) } as File
    await expect(importEquipmentFile(file)).rejects.toThrow('schema_version 1 oder 2')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('erkennt strukturierte PoE2-Equipment-Dateien ohne schema_version', async () => {
    const item = { item_class: 'Wands', rarity: 'Rare', name: 'Name', base: 'Base', mods: ['mod'] }
    const structured = { ...Object.fromEntries(
      ['wand','focus','helmet','body_armour','gloves','boots','belt','ring1','ring2','amulet']
        .map(slot => [slot, item]),
    ), charms: [{ rarity: 'Unique', name: 'Charm', base: 'Base Charm' }] }
    const equipment = { slots }
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(equipment), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(equipment), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    const file = { size: 500, text: async () => JSON.stringify(structured) } as File

    await expect(importEquipmentFile(file)).resolves.toEqual({ ...equipment, ignoredCharms: 1 })
    expect(JSON.parse(fetchMock.mock.calls[0][1].body as string)).toEqual(structured)
  })

  it('weist unvollständige strukturierte Dateien vor einem Request verständlich zurück', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const file = { size: 30, text: async () => JSON.stringify({ wand: {} }) } as File
    await expect(importEquipmentFile(file)).rejects.toThrow('strukturierte PoE2-Equipment-Dateien')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('liefert nur den durch GET verifizierten Importzustand', async () => {
    const equipment = { slots: { ...slots, wand: { id: 'wand-id', item: { raw_text: 'wand' } } } }
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(equipment), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(equipment), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    const file = { size: 100, text: async () => JSON.stringify({ schema_version: 1 }) } as File

    await expect(importEquipmentFile(file)).resolves.toEqual(equipment)
    expect(fetchMock.mock.calls.map(call => call[0])).toEqual(['/api/equipment/import', '/api/equipment'])
  })

  it('weist einen vom POST abweichenden Serverzustand klar zurück', async () => {
    const imported = { slots: { ...slots, wand: { id: 'post-id', item: { raw_text: 'wand' } } } }
    const verified = { slots: { ...slots, wand: null } }
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(imported), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(verified), { status: 200 })))
    const file = { size: 100, text: async () => JSON.stringify({ schema_version: 1 }) } as File

    await expect(importEquipmentFile(file)).rejects.toThrow('gespeicherte Serverzustand weicht')
  })

  it('weist eine fehlerhafte erfolgreiche Importantwort ohne TypeError zurück', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ slots: null }), {
      status: 200, headers: { 'Content-Type': 'application/json' },
    })))
    const file = { size: 100, text: async () => JSON.stringify({ schema_version: 1 }) } as File

    await expect(importEquipmentFile(file)).rejects.toThrow('keine gültige Equipment-Antwort')
  })

  it('weist einen fehlerhaften GET-Zustand mit klarer Verifikationsmeldung zurück', async () => {
    const imported = { slots }
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(imported), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ slots: { ...slots, wand: { id: 42, item: {} } } }), { status: 200 })))
    const file = { size: 100, text: async () => JSON.stringify({ schema_version: 1 }) } as File

    await expect(importEquipmentFile(file)).rejects.toThrow('keinen gültigen Equipment-Zustand')
  })

  it.each([
    [{ detail: { code: 'item_slot_mismatch' } }, 'passt nicht zu seinem Equipment-Slot'],
    [{ detail: { code: 'incomplete_item' } }, 'Itemtext ist ungültig oder unvollständig'],
    [{ detail: { code: 'invalid_equipment_snapshot' } }, 'Equipment-Snapshot ist unvollständig'],
    [{ detail: [{ loc: ['body', 'equipment_raw_text'], type: 'value_error' }] }, 'Equipment-Snapshot ist unvollständig'],
  ])('übersetzt Importfehler verständlich und ohne Serverdetails', async (body, message) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(body), {
      status: 422, headers: { 'Content-Type': 'application/json' },
    })))
    const file = { size: 100, text: async () => JSON.stringify({ schema_version: 2 }) } as File

    await expect(importEquipmentFile(file)).rejects.toThrow(message)
  })

  it('verlangt beim Download einen vollständigen v2-Export', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ schema_version: 1 }), { status: 200, headers: { 'Content-Type': 'application/json' } },
    )))
    await expect(exportEquipmentFile()).rejects.toThrow('keinen vollständigen v2-Export')
  })

  it('weist null als Top-Level-Export sicher zurück', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      'null', { status: 200, headers: { 'Content-Type': 'application/json' } },
    )))
    await expect(exportEquipmentFile()).rejects.toThrow('keinen vollständigen v2-Export')
  })

  it.each([
    ['fehlender Slot', { ...slots, wand: undefined }],
    ['zusätzlicher Slot', { ...slots, charm: null }],
    ['ungültiger Slotwert', { ...slots, wand: 42 }],
  ])('weist einen Export mit %s zurück', async (_label, equipment_raw_text) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      schema_version: 2, profile: {}, equipment_raw_text,
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })))
    await expect(exportEquipmentFile()).rejects.toThrow('keinen vollständigen v2-Export')
  })

  it('akzeptiert einen vollständigen v2-Export', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      schema_version: 2, profile: {}, equipment_raw_text: slots,
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })))
    await expect(exportEquipmentFile()).resolves.toMatchObject({ schema_version: 2, equipment_raw_text: slots })
  })
})
