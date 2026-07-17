import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'

const build = { build_id:'deadrabb1t-chaos-dot-lich-starter-v1',version:1,name:'ED Contagion Chaos DoT Lich Starter',author:'DEADRABB1T',source_url:'https://example.test',source_variant:'default-variant',archetype:'chaos dot',core_skills:[],offensive_priorities:[],defensive_priorities:[],constraints:[] }
const parsedItem = { raw_text:'item',unknown_lines:[],item_class:'Wands',rarity:'Rare',name:'Doom',base_type:'Wand',required_level:null,required_strength:null,required_dexterity:null,required_intelligence:null,item_level:null,quality:null,granted_skill:null,sockets:[],armour:null,armour_augmented:false,evasion:null,evasion_augmented:false,energy_shield:null,energy_shield_augmented:false,spirit:null,identified:true,corrupted:false,modifiers:[] }
const evaluation = { parse:{item:parsedItem,warnings:[],line_break_suggestion:null},build,target_slot:'wand',equipped:parsedItem,evaluation:{recommendation:'better',confidence:'high',reasons:['Mehr relevante Werte.'],warnings:[]},provider:'fake',model:'mock',provider_status:'success',provider_error:null,disclaimer:'Keine Markt- oder Craftingbewertung.' }

function response(data: unknown, ok=true) { return Promise.resolve(new Response(JSON.stringify(data),{status:ok?200:500,headers:{'Content-Type':'application/json'}})) }

describe('API-only comparison', () => {
  afterEach(()=>{cleanup();vi.unstubAllGlobals()})
  it('shows the versioned build and sends build and target slot', async () => {
    const fetchMock=vi.fn((input:RequestInfo|URL, _init?:RequestInit)=>input==='/api/builds'?response([build]):response(evaluation))
    vi.stubGlobal('fetch',fetchMock); render(<App/>); await screen.findByText(/Quelle und Variante/)
    fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'),{target:{value:'item'}})
    fireEvent.click(screen.getByRole('button',{name:'Mit ausgerüstetem Item vergleichen'}))
    expect(await screen.findByText('Candidate ist besser')).toBeTruthy()
    const body=JSON.parse(fetchMock.mock.calls.find(call=>call[0]==='/api/items/evaluate')![1]!.body as string)
    expect(body).toMatchObject({target_slot:'wand',build_id:build.build_id,raw_text:'item'})
    expect(screen.queryByText('Trade')).toBeNull()
  })
  it('shows no fallback recommendation when provider is unavailable', async () => {
    const unavailable={...evaluation,evaluation:null,provider:null,model:null,provider_status:'unavailable',provider_error:{code:'provider_not_configured',message:'Nicht konfiguriert.'}}
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>input==='/api/builds'?response([build]):response(unavailable)))
    render(<App/>); await screen.findByText(/Quelle und Variante/); fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'),{target:{value:'item'}}); fireEvent.click(screen.getByRole('button',{name:'Mit ausgerüstetem Item vergleichen'}))
    expect(await screen.findByText(/Keine Empfehlung/)).toBeTruthy(); expect(screen.queryByText('Candidate ist besser')).toBeNull()
  })
  it('invalidates a recommendation when comparison context changes', async () => {
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>input==='/api/builds'?response([build]):response(evaluation)))
    render(<App/>); await screen.findByText(/Quelle und Variante/); fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'),{target:{value:'item'}}); fireEvent.click(screen.getByRole('button',{name:'Mit ausgerüstetem Item vergleichen'})); await screen.findByText('Candidate ist besser'); fireEvent.change(screen.getByLabelText('Equipment-Slot'),{target:{value:'boots'}}); await waitFor(()=>expect(screen.queryByText('Candidate ist besser')).toBeNull())
  })
})
