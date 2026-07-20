import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { App, candidateTargetSlot } from './App'

const build = { build_id:'deadrabb1t-chaos-dot-lich-starter-v2',version:2,name:'ED Contagion Chaos DoT Lich Starter',author:'DEADRABB1T',source_url:'https://example.test',source_variant:'default-variant',archetype:'chaos dot',core_skills:[],offensive_priorities:[],defensive_priorities:[],item_priorities:[],low_value_stats:[],constraints:[] }
const parsedItem = { raw_text:'item',unknown_lines:[],item_class:'Wands',rarity:'Rare',name:'Doom',base_type:'Wand',required_level:null,required_strength:null,required_dexterity:null,required_intelligence:null,item_level:null,quality:null,granted_skill:null,sockets:[],armour:null,armour_augmented:false,evasion:null,evasion_augmented:false,energy_shield:null,energy_shield_augmented:false,spirit:null,identified:true,corrupted:false,modifiers:[] }
const parsedResponse = { item:parsedItem,warnings:[],line_break_suggestion:null,auto_format_status:'unchanged' }
const evaluation = { parse:{item:parsedItem,warnings:[],line_break_suggestion:null},build,target_slot:'wand',target_slots:['wand'],equipped:parsedItem,equipped_slots:{wand:parsedItem},evaluation:{recommendation:'better',confidence:'high',reasons:['Mehr relevante Werte.'],warnings:[],verdict:'upgrade',current_item_name:'Doom',new_item_name:'Hope',gains:['Mehr Chaos-Schaden.'],losses:['Weniger Mana.'],impacts:{damage:'better',defensive:'similar',resistances:'similar',utility:'worse'},clear_recommendation:'Neues Item ausrüsten.'},provider:'fake',model:'mock',provider_status:'success',provider_error:null,disclaimer:'Keine Markt- oder Craftingbewertung.' }

function response(data: unknown, ok=true) { return Promise.resolve(new Response(JSON.stringify(data),{status:ok?200:500,headers:{'Content-Type':'application/json'}})) }

describe('API-only comparison', () => {
  afterEach(()=>{cleanup();vi.unstubAllGlobals()})
  it('does not expose profile loading or editing', async () => {
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>input==='/api/builds'?response([build]):response({})))
    render(<App/>);await screen.findByText(/Quelle und Variante/)
    expect(screen.queryByRole('button',{name:'Profil laden'})).toBeNull()
    expect(screen.queryByText('Profil und ausgerüstete Items')).toBeNull()
  })
  it('reviews a linked build with citations before confirming and activating it', async () => {
    const custom={...build,build_id:'custom-abc-v1',version:1,name:'Imported Chaos Build',author:'Guide Author'}
    const preview={preview_id:'preview-1',source_url:'https://guide.example/build',provider:'openai',model:'test',expires_at:'2099-01-01T00:00:00Z',citations:[{url:'https://guide.example/build',title:'Original guide'}],analysis:{name:custom.name,author:custom.author,source_variant:'Endgame',archetype:'Chaos DoT',core_skills:['Essence Drain'],offensive_priorities:['Chaos Damage'],defensive_priorities:['Energy Shield'],item_priorities:['Chaos skill levels'],low_value_stats:['Accuracy'],constraints:['Mana sustain'],uncertainties:['Exact breakpoint']}}
    const fetchMock=vi.fn((input:RequestInfo|URL)=>input==='/api/builds'?response([build]):input==='/api/builds/active'?response({build_id:build.build_id}):input==='/api/builds/previews'?response(preview):String(input).includes('/confirm')?response(custom):response({build_id:custom.build_id}))
    vi.stubGlobal('fetch',fetchMock);render(<App/>);await screen.findByText(/Quelle und Variante/)
    fireEvent.change(screen.getByLabelText('Build-URL'),{target:{value:'https://guide.example/build'}})
    fireEvent.click(screen.getByRole('button',{name:'Build automatisch analysieren'}))
    expect(await screen.findByText('Imported Chaos Build')).toBeTruthy()
    expect(screen.getByRole('link',{name:'Original guide'}).getAttribute('href')).toBe('https://guide.example/build')
    expect(screen.getByText('Exact breakpoint')).toBeTruthy()
    fireEvent.click(screen.getByRole('button',{name:'Vorschau bestätigen und aktivieren'}))
    expect(await screen.findByText(/wurde gespeichert und aktiviert/)).toBeTruthy()
    expect((screen.getByLabelText('Aktiver Build') as HTMLSelectElement).value).toBe(custom.build_id)
  })
  it('keeps only the newest build analysis when responses arrive out of order', async () => {
    let resolveFirst:(value:Response)=>void=()=>undefined;let resolveSecond:(value:Response)=>void=()=>undefined
    const first=new Promise<Response>(resolve=>{resolveFirst=resolve});const second=new Promise<Response>(resolve=>{resolveSecond=resolve});let calls=0
    const makePreview=(name:string,id:string)=>({preview_id:id,source_url:`https://${id}.example/build`,provider:'openai',model:'test',expires_at:'2099-01-01T00:00:00Z',citations:[{url:`https://${id}.example/build`,title:name}],analysis:{name,author:'Author',source_variant:'default',archetype:'Chaos',core_skills:['Skill'],offensive_priorities:['Damage'],defensive_priorities:['Defence'],item_priorities:['Levels'],low_value_stats:[],constraints:[],uncertainties:[]}})
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>input==='/api/builds'?response([build]):input==='/api/builds/active'?response({build_id:build.build_id}):input==='/api/builds/previews'?(++calls===1?first:second):response({})))
    render(<App/>);await screen.findByText(/Quelle und Variante/);const url=screen.getByLabelText('Build-URL');const form=screen.getByRole('button',{name:'Build automatisch analysieren'}).closest('form')!
    fireEvent.change(url,{target:{value:'https://first.example/build'}});fireEvent.submit(form)
    fireEvent.change(url,{target:{value:'https://second.example/build'}});fireEvent.submit(form)
    resolveSecond(new Response(JSON.stringify(makePreview('Newest build','second')),{status:200,headers:{'Content-Type':'application/json'}}));expect((await screen.findAllByText('Newest build')).length).toBeGreaterThan(0)
    resolveFirst(new Response(JSON.stringify(makePreview('Stale build','first')),{status:200,headers:{'Content-Type':'application/json'}}));await waitFor(()=>expect(screen.queryByText('Stale build')).toBeNull())
  })
  it('keeps the latest active build during rapid out-of-order saves', async () => {
    const second={...build,build_id:'build-two',name:'Build Two'};const third={...build,build_id:'build-three',name:'Build Three'}
    let resolveTwo:(value:Response)=>void=()=>undefined;let resolveThree:(value:Response)=>void=()=>undefined
    const saveTwo=new Promise<Response>(resolve=>{resolveTwo=resolve});const saveThree=new Promise<Response>(resolve=>{resolveThree=resolve})
    const fetchMock=vi.fn((input:RequestInfo|URL,init?:RequestInit)=>input==='/api/builds'?response([build,second,third]):input==='/api/builds/active'&&init?.method==='PUT'?(JSON.parse(init.body as string).build_id===second.build_id?saveTwo:saveThree):response({build_id:build.build_id}))
    vi.stubGlobal('fetch',fetchMock);render(<App/>);await screen.findByText(/Quelle und Variante/);const selector=screen.getByLabelText('Aktiver Build') as HTMLSelectElement
    fireEvent.change(selector,{target:{value:second.build_id}});fireEvent.change(selector,{target:{value:third.build_id}})
    resolveThree(new Response(JSON.stringify({build_id:third.build_id}),{status:200,headers:{'Content-Type':'application/json'}}));await waitFor(()=>expect(selector.value).toBe(third.build_id))
    resolveTwo(new Response(JSON.stringify({build_id:second.build_id}),{status:500,headers:{'Content-Type':'application/json'}}));await waitFor(()=>expect(selector.value).toBe(third.build_id));expect(screen.queryByText(/Aktiver Build konnte nicht gespeichert/)).toBeNull()
  })
  it.each([
    ['Wands','wand'],['Foci','focus'],['Helmets','helmet'],['Body Armours','body_armour'],
    ['Gloves','gloves'],['Boots','boots'],['Belts','belt'],['Amulets','amulet'],['Staves','wand'],
  ])('maps candidate class %s to %s', (itemClass,targetSlot) => {
    expect(candidateTargetSlot(itemClass,'wand')).toBe(targetSlot)
  })
  it('uses the selected ring position and otherwise defaults to ring_1', () => {
    expect(candidateTargetSlot('Rings','ring_2')).toBe('ring_2')
    expect(candidateTargetSlot('Rings','wand')).toBe('ring_1')
  })
  it('shows the versioned build and sends build and target slot', async () => {
    const fetchMock=vi.fn((input:RequestInfo|URL, _init?:RequestInit)=>input==='/api/builds'?response([build]):input==='/api/items/parse'?response(parsedResponse):response(evaluation))
    vi.stubGlobal('fetch',fetchMock); render(<App/>); await screen.findByText(/Quelle und Variante/)
    fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'),{target:{value:'item'}})
    fireEvent.click(screen.getByRole('button',{name:'Mit ausgerüstetem Item vergleichen'}))
    expect(await screen.findByText(/Candidate ist besser/)).toBeTruthy()
    expect(screen.getByText('Doom')).toBeTruthy(); expect(screen.getByText('Hope')).toBeTruthy()
    expect(screen.getByText('Mehr Chaos-Schaden.')).toBeTruthy(); expect(screen.getByText('Weniger Mana.')).toBeTruthy()
    expect(screen.getByText('Neues Item ausrüsten.')).toBeTruthy()
    const body=JSON.parse(fetchMock.mock.calls.find(call=>call[0]==='/api/items/evaluate')![1]!.body as string)
    expect(body).toMatchObject({target_slot:'wand',build_id:build.build_id,raw_text:'item'})
    expect(screen.queryByText('Trade')).toBeNull()
  })
  it('shows no fallback recommendation when provider is unavailable', async () => {
    const unavailable={...evaluation,evaluation:null,provider:null,model:null,provider_status:'unavailable',provider_error:{code:'provider_not_configured',message:'Nicht konfiguriert.'}}
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>input==='/api/builds'?response([build]):input==='/api/items/parse'?response(parsedResponse):response(unavailable)))
    render(<App/>); await screen.findByText(/Quelle und Variante/); fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'),{target:{value:'item'}}); fireEvent.click(screen.getByRole('button',{name:'Mit ausgerüstetem Item vergleichen'}))
    expect(await screen.findByText(/Keine Empfehlung/)).toBeTruthy(); expect(screen.queryByText('Candidate ist besser')).toBeNull()
  })
  it('automatically compares boots with the boots slot while the editor stays on wand', async () => {
    const boots={...parsedItem,item_class:'Boots'}
    const parse={item:boots,warnings:[],line_break_suggestion:null,auto_format_status:'unchanged'}
    const bootsEvaluation={...evaluation,parse:{...evaluation.parse,item:boots},target_slot:'boots',target_slots:['boots'],equipped:boots,equipped_slots:{boots}}
    const fetchMock=vi.fn((input:RequestInfo|URL,_init?:RequestInit)=>input==='/api/builds'?response([build]):input==='/api/items/parse'?response(parse):response(bootsEvaluation))
    vi.stubGlobal('fetch',fetchMock);render(<App/>);await screen.findByText(/Quelle und Variante/)
    fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'),{target:{value:'boots'}})
    fireEvent.click(screen.getByRole('button',{name:'Mit ausgerüstetem Item vergleichen'}))
    expect(await screen.findByText(/Zielslot: boots/)).toBeTruthy()
    const body=JSON.parse(fetchMock.mock.calls.find(call=>call[0]==='/api/items/evaluate')![1]!.body as string)
    expect(body.target_slot).toBe('boots')
    expect((screen.getByLabelText('Equipment-Slot') as HTMLSelectElement).value).toBe('wand')
  })
  it('does not evaluate unsupported candidate classes', async () => {
    const parse={item:{...parsedItem,item_class:'Quivers'},warnings:[],line_break_suggestion:null,auto_format_status:'unchanged'}
    const fetchMock=vi.fn((input:RequestInfo|URL)=>input==='/api/builds'?response([build]):response(parse))
    vi.stubGlobal('fetch',fetchMock);render(<App/>);await screen.findByText(/Quelle und Variante/)
    fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'),{target:{value:'staff'}})
    fireEvent.click(screen.getByRole('button',{name:'Mit ausgerüstetem Item vergleichen'}))
    expect(await screen.findByText(/Quivers wird nicht als Equipment-Slot unterstützt/)).toBeTruthy()
    expect(fetchMock.mock.calls.some(call=>call[0]==='/api/items/evaluate')).toBe(false)
  })
  it('invalidates a recommendation when comparison context changes', async () => {
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>input==='/api/builds'?response([build]):input==='/api/items/parse'?response(parsedResponse):response(evaluation)))
    render(<App/>); await screen.findByText(/Quelle und Variante/); fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'),{target:{value:'item'}}); fireEvent.click(screen.getByRole('button',{name:'Mit ausgerüstetem Item vergleichen'})); await screen.findByText(/Candidate ist besser/); fireEvent.change(screen.getByLabelText('Equipment-Slot'),{target:{value:'boots'}}); await waitFor(()=>expect(screen.queryByText(/Candidate ist besser/)).toBeNull())
  })
  it('autoformats safe input without offering an undo action', async () => {
    const original='Item Class: Wands Rarity: Magic Apt Wand'
    const formatted='Item Class: Wands\nRarity: Magic\nApt Wand'
    const safe={item:{...parsedItem,raw_text:original},warnings:[],line_break_suggestion:{suggested_text:formatted,insertions:[]},auto_format_status:'safe'}
    const fetchMock=vi.fn((input:RequestInfo|URL,_init?:RequestInit)=>input==='/api/builds'?response([build]):input==='/api/items/parse'?response(safe):response({...evaluation,parse:{...evaluation.parse,item:{...parsedItem,raw_text:formatted}}}))
    vi.stubGlobal('fetch',fetchMock);render(<App/>);await screen.findByText(/Quelle und Variante/)
    const textarea=screen.getByLabelText('Englischen Itemtext einfügen') as HTMLTextAreaElement
    fireEvent.change(textarea,{target:{value:original}});fireEvent.click(screen.getByRole('button',{name:'Mit ausgerüstetem Item vergleichen'}))
    expect(await screen.findByText(/Sichere Zeilenumbrüche/)).toBeTruthy();expect(textarea.value).toBe(formatted)
    const evaluateCall=fetchMock.mock.calls.find(call=>call[0]==='/api/items/evaluate')
    expect(JSON.parse(evaluateCall![1]!.body as string).raw_text).toBe(formatted)
    expect(screen.queryByRole('button',{name:'Formatierung rückgängig machen'})).toBeNull()
  })
  it('recognizes a safely formatted collapsed staff and shows both hand slots', async () => {
    const original='"Item Class: Staves Rarity: Magic Vorpal Ashen Staff of Siphoning -------- Requires: Level 44 -------- Item Level: 66 -------- Grants Skill: Level 14 Firebolt -------- { Prefix Modifier "Vorpal" (Tier: 3) — Damage, Elemental, Lightning } Gain 44(43-48)% of Damage as Extra Lightning Damage { Suffix Modifier "of Siphoning" (Tier: 3) — Mana } Gain 23(21-27) Mana per enemy killed"'
    const formatted='Item Class: Staves\nRarity: Magic\nVorpal Ashen Staff of Siphoning\n--------\nGain 44% of Damage as Extra Lightning Damage'
    const safe={item:{...parsedItem,item_class:null,raw_text:original},warnings:[],line_break_suggestion:{suggested_text:formatted,insertions:[]},auto_format_status:'safe'}
    const staff={...parsedItem,item_class:'Staves',raw_text:formatted}
    const staffEvaluation={...evaluation,parse:{...evaluation.parse,item:staff},target_slot:'wand',target_slots:['wand','focus'],equipped_slots:{wand:parsedItem,focus:null}}
    const fetchMock=vi.fn((input:RequestInfo|URL,_init?:RequestInit)=>input==='/api/builds'?response([build]):input==='/api/items/parse'?response(safe):response(staffEvaluation))
    vi.stubGlobal('fetch',fetchMock);render(<App/>);await screen.findByText(/Quelle und Variante/)
    fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'),{target:{value:original}})
    fireEvent.click(screen.getByRole('button',{name:'Mit ausgerüstetem Item vergleichen'}))
    expect(await screen.findByText(/Zielslots: wand \+ focus/)).toBeTruthy()
    const body=JSON.parse(fetchMock.mock.calls.find(call=>call[0]==='/api/items/evaluate')![1]!.body as string)
    expect(body).toMatchObject({target_slot:'wand',raw_text:formatted})
  })
  it('does not evaluate ambiguous input and exposes an editable proposal', async () => {
    const ambiguous={item:parsedItem,warnings:[],line_break_suggestion:{suggested_text:'manual\nproposal',insertions:[]},auto_format_status:'ambiguous'}
    const fetchMock=vi.fn((input:RequestInfo|URL)=>input==='/api/builds'?response([build]):response(ambiguous))
    vi.stubGlobal('fetch',fetchMock);render(<App/>);await screen.findByText(/Quelle und Variante/)
    fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'),{target:{value:'rare collapsed'}});fireEvent.click(screen.getByRole('button',{name:'Mit ausgerüstetem Item vergleichen'}))
    expect(await screen.findByText(/mehrdeutig/)).toBeTruthy();expect(screen.getByLabelText('Manueller Formatierungsvorschlag')).toBeTruthy()
    expect(fetchMock.mock.calls.some(call=>call[0]==='/api/items/evaluate')).toBe(false)
  })
  it('formats a complete equipment paste immediately', async () => {
    const original='Item Class: Foci Rarity: Rare Empyrean Emblem Runed Focus'
    const formatted='Item Class: Foci\nRarity: Rare\nEmpyrean Emblem\nRuned Focus'
    const safe={item:{...parsedItem,raw_text:original},warnings:[],line_break_suggestion:{suggested_text:formatted,insertions:[]},auto_format_status:'safe'}
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>input==='/api/builds'?response([build]):response(safe)))
    render(<App/>);await screen.findByText(/Quelle und Variante/)
    const textarea=screen.getByLabelText('Itemtext des Slots') as HTMLTextAreaElement
    fireEvent.paste(textarea,{clipboardData:{getData:()=>original}})
    await waitFor(()=>expect(textarea.value).toBe(formatted))
    expect(screen.getByText('Equipment-Text wurde automatisch formatiert.')).toBeTruthy()
  })
  it('equips the compared candidate into the exact target slot', async () => {
    const parse={item:parsedItem,warnings:[],line_break_suggestion:null,auto_format_status:'unchanged'}
    const equipped={slots:{wand:{id:'new-item',item:{...parsedItem,raw_text:'item'}},focus:null}}
    const fetchMock=vi.fn((input:RequestInfo|URL,_init?:RequestInit)=>input==='/api/builds'?response([build]):input==='/api/items/parse'?response(parse):input==='/api/items/evaluate'?response(evaluation):response(equipped))
    vi.stubGlobal('fetch',fetchMock);render(<App/>);await screen.findByText(/Quelle und Variante/)
    fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'),{target:{value:'item'}})
    fireEvent.click(screen.getByRole('button',{name:'Mit ausgerüstetem Item vergleichen'}));await screen.findByText(/Candidate ist besser/)
    fireEvent.click(screen.getByRole('button',{name:'Candidate ausrüsten'}))
    expect(await screen.findByText(/Candidate wurde in wand ausgerüstet/)).toBeTruthy()
    const saveCall=fetchMock.mock.calls.find(call=>call[0]==='/api/equipment/equip')
    expect(JSON.parse(saveCall![1]!.body as string)).toEqual({raw_text:'item',ring_slot:'ring_1'})
    expect(screen.queryByText(/Candidate ist besser/)).toBeNull()
  })
  it('does not send a second equipment mutation on a rapid equip double click', async () => {
    const parse={item:parsedItem,warnings:[],line_break_suggestion:null,auto_format_status:'unchanged'}
    let finishSave:(value:Response)=>void=()=>undefined
    const pendingSave=new Promise<Response>(resolve=>{finishSave=resolve})
    const fetchMock=vi.fn((input:RequestInfo|URL,_init?:RequestInit)=>input==='/api/builds'?response([build]):input==='/api/builds/active'?response({build_id:build.build_id}):input==='/api/items/parse'?response(parse):input==='/api/items/evaluate'?response(evaluation):pendingSave)
    vi.stubGlobal('fetch',fetchMock);render(<App/>);await screen.findByText(/Quelle und Variante/)
    fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'),{target:{value:'item'}})
    fireEvent.click(screen.getByRole('button',{name:'Mit ausgerüstetem Item vergleichen'}));await screen.findByText(/Candidate ist besser/)
    const equip=screen.getByRole('button',{name:'Candidate ausrüsten'})
    fireEvent.click(equip);fireEvent.click(equip)
    expect(fetchMock.mock.calls.filter(call=>call[0]==='/api/equipment/equip')).toHaveLength(1)
    finishSave(new Response(JSON.stringify({slots:{wand:{id:'new-item',item:parsedItem},focus:null}}),{status:200,headers:{'Content-Type':'application/json'}}))
    expect(await screen.findByText(/Candidate wurde in wand ausgerüstet/)).toBeTruthy()
  })
  it('updates the selected slot after a complete equipment import', async () => {
    const importedSlots:Record<string,{id:string;item:typeof parsedItem}|null>=Object.fromEntries(['wand','focus','helmet','body_armour','gloves','boots','belt','ring_1','ring_2','amulet'].map(slot=>[slot,null]))
    importedSlots.wand={id:'wand-item',item:{...parsedItem,raw_text:'formatted wand'}}
    const fetchMock=vi.fn((input:RequestInfo|URL)=>input==='/api/builds'?response([build]):response({slots:importedSlots}))
    vi.stubGlobal('fetch',fetchMock);render(<App/>);await screen.findByText(/Quelle und Variante/)
    const file={size:100,text:async()=>JSON.stringify({schema_version:2})} as File
    fireEvent.change(screen.getByLabelText('Equipment-Datei importieren'),{target:{files:[file]}})
    expect(await screen.findByText(/Komplettes Equipment importiert: 1 von 10 Slots belegt/)).toBeTruthy()
    expect((screen.getByLabelText('Itemtext des Slots') as HTMLTextAreaElement).value).toBe('formatted wand')
    expect(fetchMock.mock.calls.filter(call=>call[0]==='/api/equipment')).toHaveLength(1)
  })
})
