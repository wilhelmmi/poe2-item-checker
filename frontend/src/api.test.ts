import { afterEach, describe, expect, it, vi } from 'vitest'

import { deleteBuild, equipEquipment, exportEquipmentFile, importEquipmentFile, isEquipment, loadEquipment, recognizeItemImage } from './api'

afterEach(() => vi.unstubAllGlobals())

describe('Equipment-Dateien', () => {
  const slots = Object.fromEntries(
    ['wand', 'focus', 'helmet', 'body_armour', 'gloves', 'boots', 'belt', 'ring_1', 'ring_2', 'amulet', 'charm_1', 'charm_2', 'charm_3']
      .map(slot => [slot, null]),
  )
  it('löscht Builds über die kodierte Build-ID', async () => {
    const fetchMock=vi.fn().mockResolvedValue(new Response(JSON.stringify({deleted_build_id:'custom-a/b',active_build_id:'builtin'}),{status:200}))
    vi.stubGlobal('fetch',fetchMock)
    await expect(deleteBuild('custom-a/b')).resolves.toEqual({deleted_build_id:'custom-a/b',active_build_id:'builtin'})
    expect(fetchMock).toHaveBeenCalledWith('/api/builds/custom-a%2Fb',expect.objectContaining({method:'DELETE'}))
  })
  it.each([
    ['ungültiges JSON', 'not-json'],
    ['fehlende ID', JSON.stringify({active_build_id:'builtin'})],
    ['leere aktive ID', JSON.stringify({deleted_build_id:'custom-a',active_build_id:' '})],
    ['abweichende gelöschte ID', JSON.stringify({deleted_build_id:'custom-b',active_build_id:'builtin'})],
  ])('weist %s nach einer erfolgreichen Löschantwort zurück', async (_label,body) => {
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(body,{status:200})))
    await expect(deleteBuild('custom-a')).rejects.toThrow('keinen gültigen Build-Status')
  })
  it('weist ungültiges JSON vor einem Request zurück', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const file = { size: 10, text: async () => '{broken' } as File
    await expect(importEquipmentFile('build-a',file)).rejects.toThrow('kein gültiges JSON')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('akzeptiert nur Schema v1, v2 oder v3 vor einem Request', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const file = { size: 30, text: async () => JSON.stringify({ schema_version: 4 }) } as File
    await expect(importEquipmentFile('build-a',file)).rejects.toThrow('schema_version 1, 2 oder 3')
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

    await expect(importEquipmentFile('build-a',file)).resolves.toEqual(equipment)
    expect(JSON.parse(fetchMock.mock.calls[0][1].body as string)).toEqual(structured)
  })

  it('weist unvollständige strukturierte Dateien vor einem Request verständlich zurück', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const file = { size: 30, text: async () => JSON.stringify({ wand: {} }) } as File
    await expect(importEquipmentFile('build-a',file)).rejects.toThrow('strukturierte PoE2-Equipment-Dateien')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('liefert nur den durch GET verifizierten Importzustand', async () => {
    const equipment = { slots: { ...slots, wand: { id: 'wand-id', item: { raw_text: 'wand' } } } }
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(equipment), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(equipment), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    const file = { size: 100, text: async () => JSON.stringify({ schema_version: 1 }) } as File

    await expect(importEquipmentFile('build-a',file)).resolves.toEqual(equipment)
    expect(fetchMock.mock.calls.map(call => call[0])).toEqual(['/api/builds/build-a/equipment/import', '/api/builds/build-a/equipment'])
  })

  it('weist einen vom POST abweichenden Serverzustand klar zurück', async () => {
    const imported = { slots: { ...slots, wand: { id: 'post-id', item: { raw_text: 'wand' } } } }
    const verified = { slots: { ...slots, wand: null } }
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(imported), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(verified), { status: 200 })))
    const file = { size: 100, text: async () => JSON.stringify({ schema_version: 1 }) } as File

    await expect(importEquipmentFile('build-a',file)).rejects.toThrow('gespeicherte Serverzustand weicht')
  })

  it('weist eine fehlerhafte erfolgreiche Importantwort ohne TypeError zurück', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ slots: null }), {
      status: 200, headers: { 'Content-Type': 'application/json' },
    })))
    const file = { size: 100, text: async () => JSON.stringify({ schema_version: 1 }) } as File

    await expect(importEquipmentFile('build-a',file)).rejects.toThrow('keine gültige Equipment-Antwort')
  })

  it('weist einen fehlerhaften GET-Zustand mit klarer Verifikationsmeldung zurück', async () => {
    const imported = { slots }
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(imported), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ slots: { ...slots, wand: { id: 42, item: {} } } }), { status: 200 })))
    const file = { size: 100, text: async () => JSON.stringify({ schema_version: 1 }) } as File

    await expect(importEquipmentFile('build-a',file)).rejects.toThrow('keinen gültigen Equipment-Zustand')
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

    await expect(importEquipmentFile('build-a',file)).rejects.toThrow(message)
  })

  it('verlangt beim Download einen vollständigen v3-Export', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ schema_version: 1 }), { status: 200, headers: { 'Content-Type': 'application/json' } },
    )))
    await expect(exportEquipmentFile('build-a')).rejects.toThrow('keinen vollständigen v3-Export')
  })

  it('weist null als Top-Level-Export sicher zurück', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      'null', { status: 200, headers: { 'Content-Type': 'application/json' } },
    )))
    await expect(exportEquipmentFile('build-a')).rejects.toThrow('keinen vollständigen v3-Export')
  })

  it.each([
    ['fehlender Slot', { ...slots, wand: undefined }],
    ['zusätzlicher Slot', { ...slots, charm: null }],
    ['ungültiger Slotwert', { ...slots, wand: 42 }],
  ])('weist einen Export mit %s zurück', async (_label, equipment_raw_text) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      schema_version: 3, profile: {}, equipment_raw_text,
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })))
    await expect(exportEquipmentFile('build-a')).rejects.toThrow('keinen vollständigen v3-Export')
  })

  it('akzeptiert einen vollständigen v3-Export', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      schema_version: 3, profile: {}, equipment_raw_text: slots,
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })))
    await expect(exportEquipmentFile('build-a')).resolves.toMatchObject({ schema_version: 3, equipment_raw_text: slots })
  })

  it('validiert Equipment-Zustände strukturell', () => {
    expect(isEquipment({ slots })).toBe(true)
    expect(isEquipment({ slots: { ...slots, wand: { id: 42, item: { raw_text: 'wand' } } } })).toBe(false)
    expect(isEquipment({ slots: { ...slots, charm: null } })).toBe(false)
  })

  it('weist eine ungültige Load-Antwort klar zurück', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ slots: null }), { status: 200 })))
    await expect(loadEquipment('build-a')).rejects.toThrow('keinen gültigen Equipment-Zustand')
  })

  it('weist eine ungültige Equip-Antwort klar zurück', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ slots: { wand: null } }), { status: 200 })))
    await expect(equipEquipment('build-a','item', 'ring_1')).rejects.toThrow('keinen gültigen Equipment-Zustand')
  })
})

describe('Screenshot-OCR', () => {
  it('sendet das Bild als Multipart ohne Content-Type manuell zu setzen', async () => {
    const fetchMock=vi.fn().mockResolvedValue(new Response(JSON.stringify({text:'Item Class: Wands'}),{status:200}))
    vi.stubGlobal('fetch',fetchMock)
    const file=new File(['png'], 'item.png', {type:'image/png'})
    await expect(recognizeItemImage(file)).resolves.toEqual({text:'Item Class: Wands'})
    expect(fetchMock).toHaveBeenCalledWith('/api/items/ocr',expect.objectContaining({method:'POST',body:expect.any(FormData)}))
    expect((fetchMock.mock.calls[0][1] as RequestInit).headers).toBeUndefined()
  })

  it('weist falsche Bildtypen lokal zurück', async () => {
    const fetchMock=vi.fn()
    vi.stubGlobal('fetch',fetchMock)
    await expect(recognizeItemImage(new File(['x'],'item.gif',{type:'image/gif'}))).rejects.toThrow('PNG-, JPEG- und WebP')
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
