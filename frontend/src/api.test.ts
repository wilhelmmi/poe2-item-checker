import { afterEach, describe, expect, it, vi } from 'vitest'

import { exportEquipmentFile, importEquipmentFile, parseBackupFile, persistEvaluation } from './api'

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

describe('History und Vollbackup', () => {
  it('speichert einen Candidate nur über die explizite History-Aktion', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', {
      status: 201, headers: { 'Content-Type': 'application/json' },
    }))
    vi.stubGlobal('fetch', fetchMock)
    await persistEvaluation('Item Class: Rings', 'ring_1', new AbortController().signal)
    expect(fetchMock).toHaveBeenCalledWith('/api/history', expect.objectContaining({ method: 'POST' }))
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      raw_text: 'Item Class: Rings', target_slot: 'ring_1', use_profile: true,
    })
  })

  it('weist ein syntaktisch ungültiges Backup vor dem Restore-Request zurück', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const file = { size: 10, text: async () => '{broken' } as File
    await expect(parseBackupFile(file)).rejects.toThrow('kein gültiges JSON')
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
