import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { App, candidateTargetSlot } from './App'
import { ParsedItem } from './api'

const build = { build_id:'deadrabb1t-chaos-dot-lich-starter-v2',version:2,name:'ED Contagion Chaos DoT Lich Starter',author:'DEADRABB1T',source_url:'https://example.test',source_variant:'default-variant',archetype:'chaos dot',core_skills:[],offensive_priorities:[],defensive_priorities:[],item_priorities:[],low_value_stats:[],constraints:[] }
const parsedItem = { raw_text:'item',unknown_lines:[],item_class:'Wands',rarity:'Rare',name:'Doom',base_type:'Wand',required_level:null,required_strength:null,required_dexterity:null,required_intelligence:null,item_level:null,quality:null,granted_skill:null,sockets:[],armour:null,armour_augmented:false,evasion:null,evasion_augmented:false,energy_shield:null,energy_shield_augmented:false,spirit:null,identified:true,corrupted:false,modifiers:[] }
const parsedResponse = { item:parsedItem,warnings:[],line_break_suggestion:null,auto_format_status:'unchanged' }
const evaluation = { parse:{item:parsedItem,warnings:[],line_break_suggestion:null},build,target_slot:'wand',target_slots:['wand'],comparison_slots:['wand'],equipped:parsedItem,equipped_slots:{wand:parsedItem},evaluation:{recommendation:'better',confidence:'high',reasons:['Mehr relevante Werte.'],warnings:[],verdict:'upgrade',current_item_name:'Doom',new_item_name:'Hope',gains:['Mehr Chaos-Schaden.'],losses:['Weniger Mana.'],impacts:{damage:'better',defensive:'similar',resistances:'similar',utility:'worse'},clear_recommendation:'Neues Item ausrüsten.',recommended_target_slot:'wand'},provider:'fake',model:'mock',provider_status:'success',provider_error:null,disclaimer:'Keine Markt- oder Craftingbewertung.' }
const emptySlots=()=>Object.fromEntries(['wand','focus','helmet','body_armour','gloves','boots','belt','ring_1','ring_2','amulet','charm_1','charm_2','charm_3'].map(slot=>[slot,null]))
const emptyEquipment=()=>({slots:emptySlots()})

function response(data: unknown, ok=true) { return Promise.resolve(new Response(JSON.stringify(data),{status:ok?200:500,headers:{'Content-Type':'application/json'}})) }

describe('API-only comparison', () => {
  afterEach(()=>{cleanup();vi.unstubAllGlobals()})
  it('does not expose profile loading or editing', async () => {
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>input==='/api/builds'?response([build]):response({})))
    render(<App/>);await screen.findByText(/Quelle und Variante/)
    expect(screen.queryByRole('button',{name:'Profil laden'})).toBeNull()
    expect(screen.queryByText('Profil und ausgerüstete Items')).toBeNull()
  })
  it('renders the redesigned workspace with localized slot labels and stable values', async () => {
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>input==='/api/builds'?response([build]):String(input).endsWith('/equipment')?response(emptyEquipment()):response({build_id:build.build_id})))
    render(<App/>);await screen.findByText(/Quelle und Variante/)
    expect(screen.getByRole('heading',{name:'Candidate vergleichen'})).toBeTruthy()
    expect(screen.getByRole('complementary',{name:'Build und Equipment'})).toBeTruthy()
    expect(await screen.findByRole('heading',{name:'Aktuelles Equipment'})).toBeTruthy()
    expect(await screen.findByText('Zauberstab')).toBeTruthy();expect(screen.getByText('Körperrüstung')).toBeTruthy()
    expect(screen.getAllByText('Nicht ausgerüstet')).toHaveLength(11)
    expect(screen.getAllByText('Durch aktuellen Gürtel gesperrt')).toHaveLength(2)
    expect(screen.getByRole('list',{name:'Aktuell ausgerüstete Items'})).toBeTruthy();expect(screen.getAllByRole('listitem')).toHaveLength(8)
    expect(screen.getByRole('group',{name:'Ringe'})).toBeTruthy();expect(screen.getByRole('group',{name:'Charms'})).toBeTruthy()
    expect(screen.queryByLabelText('Equipment-Slot')).toBeNull();expect(screen.queryByText('Slot speichern')).toBeNull()
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
  it('blocks preview confirmation while an equipment import is pending', async () => {
    const preview={preview_id:'preview-race',source_url:'https://guide.example/race',provider:'openai',model:'test',expires_at:'2099-01-01T00:00:00Z',citations:[],analysis:{name:'Race Build',author:'Author',source_variant:'default',archetype:'Chaos',core_skills:['Skill'],offensive_priorities:['Damage'],defensive_priorities:['Defence'],item_priorities:['Levels'],low_value_stats:[],constraints:[],uncertainties:[]}}
    let resolveImport:(value:Response)=>void=()=>undefined
    const pendingImport=new Promise<Response>(resolve=>{resolveImport=resolve})
    const fetchMock=vi.fn((input:RequestInfo|URL)=>input==='/api/builds'?response([build]):input==='/api/builds/active'?response({build_id:build.build_id}):input==='/api/builds/previews'?response(preview):String(input).endsWith('/equipment/import')?pendingImport:String(input).endsWith('/equipment')?response(emptyEquipment()):String(input).includes('/confirm')?response({...build,build_id:'unexpected'}):response({build_id:build.build_id}))
    vi.stubGlobal('fetch',fetchMock);render(<App/>);await screen.findByLabelText('Aktuell ausgerüstete Items')
    fireEvent.change(screen.getByLabelText('Build-URL'),{target:{value:'https://guide.example/race'}})
    fireEvent.click(screen.getByRole('button',{name:'Build automatisch analysieren'}))
    const confirm=await screen.findByRole('button',{name:'Vorschau bestätigen und aktivieren'}) as HTMLButtonElement
    const file={size:100,text:async()=>JSON.stringify({schema_version:2})} as File
    fireEvent.change(screen.getByLabelText('Equipment-Datei importieren'),{target:{files:[file]}})
    await waitFor(()=>expect(confirm.disabled).toBe(true));fireEvent.click(confirm)
    expect(fetchMock.mock.calls.some(call=>String(call[0]).includes('/confirm'))).toBe(false)
    resolveImport(new Response(JSON.stringify(emptyEquipment()),{status:200,headers:{'Content-Type':'application/json'}}))
    await screen.findByText(/Komplettes Equipment importiert/)
    await waitFor(()=>expect(confirm.disabled).toBe(false))
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
  it('cancels custom build deletion without sending a request', async () => {
    const custom={...build,build_id:'custom-delete-v1',name:'Delete Me'};vi.stubGlobal('confirm',vi.fn(()=>false))
    const fetchMock=vi.fn((input:RequestInfo|URL,_init?:RequestInit)=>input==='/api/builds'?response([build,custom]):input==='/api/builds/active'?response({build_id:custom.build_id}):String(input).endsWith('/equipment')?response(emptyEquipment()):response({}))
    vi.stubGlobal('fetch',fetchMock);render(<App/>);await screen.findByRole('button',{name:'Build löschen'});fireEvent.click(screen.getByRole('button',{name:'Build löschen'}))
    expect(fetchMock.mock.calls.some(([input,init])=>String(input).includes('/api/builds/custom-')&&(init as RequestInit|undefined)?.method==='DELETE')).toBe(false)
  })
  it('deletes the active custom build and switches to the server fallback', async () => {
    const custom={...build,build_id:'custom-delete-v1',name:'Delete Me'};vi.stubGlobal('confirm',vi.fn(()=>true))
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL,init?:RequestInit)=>input==='/api/builds'?response([build,custom]):input==='/api/builds/active'?response({build_id:custom.build_id}):String(input).endsWith('/equipment')?response(emptyEquipment()):init?.method==='DELETE'?response({deleted_build_id:custom.build_id,active_build_id:build.build_id}):response({})))
    render(<App/>);await screen.findByRole('button',{name:'Build löschen'});fireEvent.click(screen.getByRole('button',{name:'Build löschen'}))
    expect(await screen.findByText(/wurde gelöscht/)).toBeTruthy();expect((screen.getByLabelText('Aktiver Build') as HTMLSelectElement).value).toBe(build.build_id);expect(screen.queryByText('Delete Me')).toBeNull()
  })
  it('keeps the custom build visible when deletion fails', async () => {
    const custom={...build,build_id:'custom-delete-v1',name:'Delete Me'};vi.stubGlobal('confirm',vi.fn(()=>true))
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL,init?:RequestInit)=>input==='/api/builds'?response([build,custom]):input==='/api/builds/active'?response({build_id:custom.build_id}):String(input).endsWith('/equipment')?response(emptyEquipment()):init?.method==='DELETE'?response({detail:{message:'Löschen fehlgeschlagen.'}},false):response({})))
    render(<App/>);await screen.findByRole('button',{name:'Build löschen'});fireEvent.click(screen.getByRole('button',{name:'Build löschen'}))
    expect(await screen.findByText(/Löschen fehlgeschlagen.*Buildstatus wurde neu geladen/)).toBeTruthy();expect(screen.getByRole('button',{name:'Build löschen'})).toBeTruthy()
  })
  it('resynchronizes builds after an invalid successful delete response', async () => {
    const custom={...build,build_id:'custom-delete-v1',name:'Delete Me'};let buildLoads=0;vi.stubGlobal('confirm',vi.fn(()=>true))
    const fetchMock=vi.fn((input:RequestInfo|URL,init?:RequestInit)=>input==='/api/builds'?response(++buildLoads===1?[build,custom]:[build]):input==='/api/builds/active'?response({build_id:build.build_id}):String(input).endsWith('/equipment')?response(emptyEquipment()):init?.method==='DELETE'?response({deleted_build_id:'wrong-id',active_build_id:build.build_id}):response({}))
    vi.stubGlobal('fetch',fetchMock);render(<App/>);await screen.findByText(/Quelle und Variante/);fireEvent.change(screen.getByLabelText('Aktiver Build'),{target:{value:custom.build_id}});await screen.findByRole('button',{name:'Build löschen'});fireEvent.click(screen.getByRole('button',{name:'Build löschen'}))
    expect(await screen.findByText(/keinen gültigen Build-Status.*Buildstatus wurde neu geladen/)).toBeTruthy();expect((screen.getByLabelText('Aktiver Build') as HTMLSelectElement).value).toBe(build.build_id);expect(screen.queryByText('Delete Me')).toBeNull()
  })
  it('ignores a stale active-build save after deleting that custom build', async () => {
    const custom={...build,build_id:'custom-delete-v1',name:'Delete Me'};let resolveSave:(value:Response)=>void=()=>undefined;const pendingSave=new Promise<Response>(resolve=>{resolveSave=resolve});vi.stubGlobal('confirm',vi.fn(()=>true))
    const fetchMock=vi.fn((input:RequestInfo|URL,init?:RequestInit)=>input==='/api/builds'?response([build,custom]):input==='/api/builds/active'&&init?.method==='PUT'?pendingSave:input==='/api/builds/active'?response({build_id:build.build_id}):String(input).endsWith('/equipment')?response(emptyEquipment()):init?.method==='DELETE'?response({deleted_build_id:custom.build_id,active_build_id:build.build_id}):response({}))
    vi.stubGlobal('fetch',fetchMock);render(<App/>);await screen.findByText(/Quelle und Variante/);fireEvent.change(screen.getByLabelText('Aktiver Build'),{target:{value:custom.build_id}});await screen.findByRole('button',{name:'Build löschen'});fireEvent.click(screen.getByRole('button',{name:'Build löschen'}));expect(await screen.findByText(/wurde gelöscht/)).toBeTruthy()
    resolveSave(new Response(JSON.stringify({build_id:custom.build_id}),{status:200,headers:{'Content-Type':'application/json'}}));await waitFor(()=>expect((screen.getByLabelText('Aktiver Build') as HTMLSelectElement).value).toBe(build.build_id));expect(screen.queryByText(/gespeichert/)).toBeNull()
  })
  it.each([
    ['Wands','wand'],['Foci','focus'],['Helmets','helmet'],['Body Armours','body_armour'],
    ['Gloves','gloves'],['Boots','boots'],['Belts','belt'],['Amulets','amulet'],['Staves','wand'],
    ['Rings','ring_1'],['Charms','charm_1'],
  ])('maps candidate class %s to %s', (itemClass,targetSlot) => {
    expect(candidateTargetSlot(itemClass,'wand')).toBe(targetSlot)
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
    const fetchMock=vi.fn((input:RequestInfo|URL,_init?:RequestInit)=>input==='/api/builds'?response([build]):String(input).endsWith('/equipment')?response(emptyEquipment()):input==='/api/items/parse'?response(parse):response(bootsEvaluation))
    vi.stubGlobal('fetch',fetchMock);render(<App/>);await screen.findByText(/Quelle und Variante/)
    fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'),{target:{value:'boots'}})
    fireEvent.click(screen.getByRole('button',{name:'Mit ausgerüstetem Item vergleichen'}))
    expect(await screen.findByText(/Zielslot: boots/)).toBeTruthy()
    const body=JSON.parse(fetchMock.mock.calls.find(call=>call[0]==='/api/items/evaluate')![1]!.body as string)
    expect(body.target_slot).toBe('boots')
    expect(screen.queryByLabelText(/als Zielslot wählen/)).toBeNull()
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
  it('does not expose a manual ring comparison context', async () => {
    const ring={...parsedItem,item_class:'Rings'};const ringParse={...parsedResponse,item:ring};const ringEvaluation={...evaluation,parse:{...evaluation.parse,item:ring},target_slot:'ring_1',target_slots:['ring_1']}
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>input==='/api/builds'?response([build]):String(input).endsWith('/equipment')?response(emptyEquipment()):input==='/api/items/parse'?response(ringParse):response(ringEvaluation)))
    render(<App/>); await screen.findByText(/Quelle und Variante/); fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'),{target:{value:'item'}}); fireEvent.click(screen.getByRole('button',{name:'Mit ausgerüstetem Item vergleichen'})); await screen.findByText(/Candidate ist besser/); expect(screen.queryByLabelText(/als Zielslot wählen/)).toBeNull()
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
  it('loads and renders the complete equipment overview on startup', async () => {
    const slots:Record<string,{id:string;item:typeof parsedItem}|null>=emptySlots();slots.wand={id:'wand',item:parsedItem}
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>input==='/api/builds'?response([build]):String(input).endsWith('/equipment')?response({slots}):response({build_id:build.build_id})))
    render(<App/>)
    expect(await screen.findByText('Doom')).toBeTruthy();expect(screen.getByText('Wand')).toBeTruthy();expect(screen.getByText('Rare')).toBeTruthy();expect(screen.getByText('1/13')).toBeTruthy()
  })
  it('shows game-like item details on hover and keyboard focus without raw JSON', async () => {
    const detailed:ParsedItem={...parsedItem,rarity:'Rare',name:'Doom Weaver',base_type:'Attuned Wand',quality:20,energy_shield:41,energy_shield_augmented:true,spirit:30,required_level:44,required_intelligence:72,item_level:66,sockets:['S','S'],granted_skill:'Level 14 Firebolt',corrupted:true,modifiers:[
      {source:'implicit',affix_type:null,name:null,tier:null,tags:[],raw_text:'18% increased Spell Damage',normalized_key:'spell_damage',values:[18],roll_ranges:[],crafted:false,desecrated:false,rune:false,implicit:true,unique:false},
      {source:'explicit',affix_type:'prefix',name:'Flaming',tier:3,tags:['fire'],raw_text:'Level 14 Firebolt',normalized_key:'granted_skill',values:[14],roll_ranges:[],crafted:false,desecrated:false,rune:false,implicit:false,unique:false},
      {source:'explicit',affix_type:'suffix',name:'of Siphoning',tier:3,tags:['mana'],raw_text:'Gain 23 Mana per enemy killed',normalized_key:'mana_kill',values:[23],roll_ranges:[],crafted:false,desecrated:false,rune:false,implicit:false,unique:false},
    ]}
    const itemSlots:Record<string,{id:string;item:ParsedItem}|null>=emptySlots();itemSlots.wand={id:'wand',item:detailed}
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>input==='/api/builds'?response([build]):String(input).endsWith('/equipment')?response({slots:itemSlots}):response({build_id:build.build_id})))
    render(<App/>);const card=(await screen.findByText('Doom Weaver')).closest('article')!
    fireEvent.mouseEnter(card);expect(screen.getByRole('tooltip')).toBeTruthy();expect(screen.getByText('Qualität: +20%')).toBeTruthy();expect(screen.getByText('Energieschild: 41').classList.contains('item-value-augmented')).toBe(true);expect(screen.getByText('Level 44')).toBeTruthy();expect(screen.getByText('Gegenstandsstufe')).toBeTruthy();expect(screen.getByText('Gain 23 Mana per enemy killed')).toBeTruthy();expect(screen.getByText('Korrumpiert')).toBeTruthy()
    expect(screen.getAllByText('Level 14 Firebolt')).toHaveLength(1);expect(screen.queryByText(/"raw_text"/)).toBeNull();expect(screen.getByRole('tooltip').querySelector('.rarity-rare')).toBeTruthy()
    fireEvent.mouseLeave(card);expect(screen.queryByRole('tooltip')).toBeNull();fireEvent.focus(card);expect(screen.getByRole('tooltip')).toBeTruthy()
  })
  it('opens pinned ring details and closes them with Escape', async () => {
    const itemSlots:Record<string,{id:string;item:ParsedItem}|null>=emptySlots();itemSlots.ring_1={id:'ring-1',item:{...parsedItem,item_class:'Rings',name:'Skull Knot',base_type:'Amethyst Ring'}};itemSlots.ring_2={id:'ring-2',item:{...parsedItem,item_class:'Rings',name:'Pandemonium Nail',base_type:'Topaz Ring'}}
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>input==='/api/builds'?response([build]):String(input).endsWith('/equipment')?response({slots:itemSlots}):response({build_id:build.build_id})))
    render(<App/>);await screen.findByText('Skull Knot');expect(screen.queryByLabelText(/als Zielslot wählen/)).toBeNull()
    const details=screen.getAllByRole('button',{name:'Details anzeigen'});fireEvent.click(details[0]);expect(screen.getByRole('dialog',{name:'Details zu Skull Knot'})).toBeTruthy();expect(document.activeElement).toBe(screen.getByRole('button',{name:'Itemdetails schließen'}))
    fireEvent.keyDown(document,{key:'Tab'});expect(document.activeElement).toBe(screen.getByRole('button',{name:'Itemdetails schließen'}));fireEvent.keyDown(document,{key:'Escape'});expect(screen.queryByRole('dialog')).toBeNull();expect(document.activeElement).toBe(details[0]);expect(screen.getByText('Pandemonium Nail')).toBeTruthy()
  })
  it('does not offer item details for empty or blocked equipment slots', async () => {
    const itemSlots:Record<string,{id:string;item:ParsedItem}|null>=emptySlots();itemSlots.wand={id:'staff',item:{...parsedItem,item_class:'Staves',name:'Ashen Staff',base_type:'Ashen Staff'}}
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>input==='/api/builds'?response([build]):String(input).endsWith('/equipment')?response({slots:itemSlots}):response({build_id:build.build_id})))
    render(<App/>);await screen.findByText('Durch Stab blockiert');expect(screen.getAllByRole('button',{name:'Details anzeigen'})).toHaveLength(1)
  })
  it('equips the compared candidate into the exact target slot', async () => {
    const parse={item:parsedItem,warnings:[],line_break_suggestion:null,auto_format_status:'unchanged'}
    const equipped={slots:{...emptySlots(),wand:{id:'new-item',item:{...parsedItem,raw_text:'item'}}}}
    const fetchMock=vi.fn((input:RequestInfo|URL,_init?:RequestInit)=>input==='/api/builds'?response([build]):input==='/api/items/parse'?response(parse):input==='/api/items/evaluate'?response(evaluation):response(equipped))
    vi.stubGlobal('fetch',fetchMock);render(<App/>);await screen.findByText(/Quelle und Variante/)
    fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'),{target:{value:'item'}})
    fireEvent.click(screen.getByRole('button',{name:'Mit ausgerüstetem Item vergleichen'}));await screen.findByText(/Candidate ist besser/)
    fireEvent.click(screen.getByRole('button',{name:'Candidate ausrüsten'}))
    expect(await screen.findByText(/Candidate wurde in wand ausgerüstet/)).toBeTruthy()
    const saveCall=fetchMock.mock.calls.find(call=>String(call[0]).endsWith('/equipment/equip'))
    expect(JSON.parse(saveCall![1]!.body as string)).toEqual({raw_text:'item',target_slot:'wand'})
    expect(screen.queryByText(/Candidate ist besser/)).toBeNull()
  })
  it('does not send a second equipment mutation on a rapid equip double click', async () => {
    const parse={item:parsedItem,warnings:[],line_break_suggestion:null,auto_format_status:'unchanged'}
    let finishSave:(value:Response)=>void=()=>undefined
    const pendingSave=new Promise<Response>(resolve=>{finishSave=resolve})
    const fetchMock=vi.fn((input:RequestInfo|URL,_init?:RequestInit)=>input==='/api/builds'?response([build]):input==='/api/builds/active'?response({build_id:build.build_id}):String(input).endsWith('/equipment')?response(emptyEquipment()):input==='/api/items/parse'?response(parse):input==='/api/items/evaluate'?response(evaluation):pendingSave)
    vi.stubGlobal('fetch',fetchMock);render(<App/>);await screen.findByText(/Quelle und Variante/)
    fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'),{target:{value:'item'}})
    fireEvent.click(screen.getByRole('button',{name:'Mit ausgerüstetem Item vergleichen'}));await screen.findByText(/Candidate ist besser/)
    const equip=screen.getByRole('button',{name:'Candidate ausrüsten'})
    fireEvent.click(equip);fireEvent.click(equip)
    expect((screen.getByLabelText('Aktiver Build') as HTMLSelectElement).disabled).toBe(true)
    expect(fetchMock.mock.calls.filter(call=>String(call[0]).endsWith('/equipment/equip'))).toHaveLength(1)
    finishSave(new Response(JSON.stringify({slots:{...emptySlots(),wand:{id:'new-item',item:parsedItem}}}),{status:200,headers:{'Content-Type':'application/json'}}))
    expect(await screen.findByText(/Candidate wurde in wand ausgerüstet/)).toBeTruthy()
  })
  it('blocks build switching while an equipment import is pending', async () => {
    let resolveImport:(value:Response)=>void=()=>undefined
    const pendingImport=new Promise<Response>(resolve=>{resolveImport=resolve})
    const fetchMock=vi.fn((input:RequestInfo|URL)=>input==='/api/builds'?response([build]):input==='/api/builds/active'?response({build_id:build.build_id}):String(input).endsWith('/equipment/import')?pendingImport:String(input).endsWith('/equipment')?response(emptyEquipment()):response({build_id:build.build_id}))
    vi.stubGlobal('fetch',fetchMock);render(<App/>);await screen.findByLabelText('Aktuell ausgerüstete Items')
    const file={size:100,text:async()=>JSON.stringify({schema_version:2})} as File
    fireEvent.change(screen.getByLabelText('Equipment-Datei importieren'),{target:{files:[file]}})
    expect((screen.getByLabelText('Aktiver Build') as HTMLSelectElement).disabled).toBe(true)
    expect((screen.getByRole('button',{name:'Build löschen'}) as HTMLButtonElement).disabled).toBe(true)
    resolveImport(new Response(JSON.stringify(emptyEquipment()),{status:200,headers:{'Content-Type':'application/json'}}))
    await screen.findByText(/Komplettes Equipment importiert/)
  })
  it('updates the selected slot after a complete equipment import', async () => {
    const importedSlots:Record<string,{id:string;item:typeof parsedItem}|null>=Object.fromEntries(['wand','focus','helmet','body_armour','gloves','boots','belt','ring_1','ring_2','amulet','charm_1','charm_2','charm_3'].map(slot=>[slot,null]))
    importedSlots.wand={id:'wand-item',item:{...parsedItem,raw_text:'formatted wand'}}
    const fetchMock=vi.fn((input:RequestInfo|URL)=>input==='/api/builds'?response([build]):response({slots:importedSlots}))
    vi.stubGlobal('fetch',fetchMock);render(<App/>);await screen.findByText(/Quelle und Variante/)
    const file={size:100,text:async()=>JSON.stringify({schema_version:2})} as File
    fireEvent.change(screen.getByLabelText('Equipment-Datei importieren'),{target:{files:[file]}})
    expect(await screen.findByText(/Komplettes Equipment importiert: 1 von 13 Slots belegt/)).toBeTruthy()
    expect(screen.getByText('Doom')).toBeTruthy();expect(screen.getByText('Wand')).toBeTruthy()
    expect(fetchMock.mock.calls.filter(call=>String(call[0]).endsWith('/equipment'))).toHaveLength(2)
  })

  it('marks the focus slot as blocked when a staff is equipped', async () => {
    const staff={...parsedItem,item_class:'Staves',name:'Ashen Staff',base_type:'Ashen Staff'}
    const slots:Record<string,{id:string;item:typeof staff}|null>=emptySlots();slots.wand={id:'staff',item:staff}
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>input==='/api/builds'?response([build]):String(input).endsWith('/equipment')?response({slots}):response({build_id:build.build_id})))
    render(<App/>);expect(await screen.findAllByText('Ashen Staff')).toHaveLength(2)
    expect(screen.getByText('Durch Stab blockiert')).toBeTruthy();expect(screen.getByText('Zweihandwaffe belegt beide Hände')).toBeTruthy()
  })

  it('offers a retry when the initial equipment load fails', async () => {
    let equipmentCalls=0
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>input==='/api/builds'?response([build]):String(input).endsWith('/equipment')?(++equipmentCalls===1?response({},false):response(emptyEquipment())):response({build_id:build.build_id})))
    render(<App/>);expect(await screen.findByText('Equipment konnte nicht geladen werden.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button',{name:'Erneut laden'}))
    expect(await screen.findByLabelText('Aktuell ausgerüstete Items')).toBeTruthy();expect(equipmentCalls).toBe(2)
  })

  it('ignores a stale initial load after equipping a candidate', async () => {
    let resolveInitial:(value:Response)=>void=()=>undefined;const initial=new Promise<Response>(resolve=>{resolveInitial=resolve})
    const newItem={...parsedItem,name:'New Wand'};const oldItem={...parsedItem,name:'Old Wand'}
    const newSlots:Record<string,{id:string;item:typeof parsedItem}|null>=emptySlots();newSlots.wand={id:'new',item:newItem}
    const oldSlots:Record<string,{id:string;item:typeof parsedItem}|null>=emptySlots();oldSlots.wand={id:'old',item:oldItem}
    const fetchMock=vi.fn((input:RequestInfo|URL)=>input==='/api/builds'?response([build]):String(input).endsWith('/equipment')?initial:input==='/api/items/parse'?response(parsedResponse):input==='/api/items/evaluate'?response(evaluation):String(input).endsWith('/equipment/equip')?response({slots:newSlots}):response({build_id:build.build_id}))
    vi.stubGlobal('fetch',fetchMock);render(<App/>);await screen.findByText(/Quelle und Variante/)
    fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'),{target:{value:'item'}});fireEvent.click(screen.getByRole('button',{name:'Mit ausgerüstetem Item vergleichen'}));await screen.findByText(/Candidate ist besser/)
    fireEvent.click(screen.getByRole('button',{name:'Candidate ausrüsten'}));expect(await screen.findByText('New Wand')).toBeTruthy()
    resolveInitial(new Response(JSON.stringify({slots:oldSlots}),{status:200,headers:{'Content-Type':'application/json'}}))
    await waitFor(()=>expect(screen.queryByText('Old Wand')).toBeNull())
  })

  it('ignores a stale initial load after importing equipment', async () => {
    let resolveInitial:(value:Response)=>void=()=>undefined;const initial=new Promise<Response>(resolve=>{resolveInitial=resolve});let equipmentGets=0
    const importedItem={...parsedItem,name:'Imported Wand'};const staleItem={...parsedItem,name:'Stale Wand'}
    const importedSlots:Record<string,{id:string;item:typeof parsedItem}|null>=emptySlots();importedSlots.wand={id:'imported',item:importedItem}
    const staleSlots:Record<string,{id:string;item:typeof parsedItem}|null>=emptySlots();staleSlots.wand={id:'stale',item:staleItem}
    const fetchMock=vi.fn((input:RequestInfo|URL)=>input==='/api/builds'?response([build]):String(input).endsWith('/equipment')?(++equipmentGets===1?initial:response({slots:importedSlots})):String(input).endsWith('/equipment/import')?response({slots:importedSlots}):response({build_id:build.build_id}))
    vi.stubGlobal('fetch',fetchMock);render(<App/>);await screen.findByText(/Quelle und Variante/)
    await waitFor(()=>expect(equipmentGets).toBe(1))
    const file={size:100,text:async()=>JSON.stringify({schema_version:2})} as File;fireEvent.change(screen.getByLabelText('Equipment-Datei importieren'),{target:{files:[file]}})
    expect(await screen.findByText('Imported Wand')).toBeTruthy();resolveInitial(new Response(JSON.stringify({slots:staleSlots}),{status:200,headers:{'Content-Type':'application/json'}}))
    await waitFor(()=>expect(screen.queryByText('Stale Wand')).toBeNull())
  })

  it('lets the backend choose the second ring without a manual selector', async () => {
    const ring={...parsedItem,item_class:'Rings'};const ringParse={...parsedResponse,item:ring};const ringEvaluation={...evaluation,parse:{...evaluation.parse,item:ring},target_slot:'ring_2',target_slots:['ring_2'],comparison_slots:['ring_1','ring_2'],equipped_slots:{ring_1:ring,ring_2:ring},evaluation:{...evaluation.evaluation,recommended_target_slot:'ring_2'}}
    const fetchMock=vi.fn((input:RequestInfo|URL,_init?:RequestInit)=>input==='/api/builds'?response([build]):String(input).endsWith('/equipment')?response(emptyEquipment()):input==='/api/items/parse'?response(ringParse):input==='/api/items/evaluate'?response(ringEvaluation):response({build_id:build.build_id}))
    vi.stubGlobal('fetch',fetchMock);render(<App/>);await screen.findByLabelText('Aktuell ausgerüstete Items')
    fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'),{target:{value:'item'}});fireEvent.click(screen.getByRole('button',{name:'Mit ausgerüstetem Item vergleichen'}));expect(await screen.findByText(/Zielslot: ring_2/)).toBeTruthy()
    const body=JSON.parse(fetchMock.mock.calls.find(call=>call[0]==='/api/items/evaluate')![1]!.body as string);expect(body.target_slot).toBe('ring_1')
  })

  it('refetches committed server state after an import reports failure', async () => {
    const committed={...parsedItem,name:'Committed Wand'};const slots:Record<string,{id:string;item:typeof parsedItem}|null>=emptySlots();slots.wand={id:'committed',item:committed};let equipmentGets=0
    const fetchMock=vi.fn((input:RequestInfo|URL)=>input==='/api/builds'?response([build]):String(input).endsWith('/equipment')?(++equipmentGets===1?response(emptyEquipment()):response({slots})):String(input).endsWith('/equipment/import')?response({detail:{code:'incomplete_item'}},false):response({build_id:build.build_id}))
    vi.stubGlobal('fetch',fetchMock);render(<App/>);await screen.findByLabelText('Aktuell ausgerüstete Items')
    const file={size:100,text:async()=>JSON.stringify({schema_version:2})} as File;fireEvent.change(screen.getByLabelText('Equipment-Datei importieren'),{target:{files:[file]}})
    expect(await screen.findByText('Committed Wand')).toBeTruthy();expect(equipmentGets).toBe(2)
  })

  it('shows retry when resync after a failed equip also fails', async () => {
    let equipmentGets=0
    const fetchMock=vi.fn((input:RequestInfo|URL)=>input==='/api/builds'?response([build]):String(input).endsWith('/equipment')?(++equipmentGets===1?response(emptyEquipment()):response({},false)):input==='/api/items/parse'?response(parsedResponse):input==='/api/items/evaluate'?response(evaluation):String(input).endsWith('/equipment/equip')?response({},false):response({build_id:build.build_id}))
    vi.stubGlobal('fetch',fetchMock);render(<App/>);await screen.findByLabelText('Aktuell ausgerüstete Items');fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'),{target:{value:'item'}});fireEvent.click(screen.getByRole('button',{name:'Mit ausgerüstetem Item vergleichen'}));await screen.findByText(/Candidate ist besser/)
    fireEvent.click(screen.getByRole('button',{name:'Candidate ausrüsten'}));expect(await screen.findByRole('button',{name:'Erneut laden'})).toBeTruthy();expect(equipmentGets).toBe(2)
  })

  it('disables equipment retry while a mutation is running', async () => {
    let resolveEquip:(value:Response)=>void=()=>undefined;const pendingEquip=new Promise<Response>(resolve=>{resolveEquip=resolve});let equipmentGets=0
    const fetchMock=vi.fn((input:RequestInfo|URL)=>input==='/api/builds'?response([build]):String(input).endsWith('/equipment')?(equipmentGets++,response({},false)):input==='/api/items/parse'?response(parsedResponse):input==='/api/items/evaluate'?response(evaluation):String(input).endsWith('/equipment/equip')?pendingEquip:response({build_id:build.build_id}))
    vi.stubGlobal('fetch',fetchMock);render(<App/>);await screen.findByRole('button',{name:'Erneut laden'});fireEvent.change(screen.getByLabelText('Englischen Itemtext einfügen'),{target:{value:'item'}});fireEvent.click(screen.getByRole('button',{name:'Mit ausgerüstetem Item vergleichen'}));await screen.findByText(/Candidate ist besser/)
    fireEvent.click(screen.getByRole('button',{name:'Candidate ausrüsten'}));const retry=screen.getByRole('button',{name:'Erneut laden'}) as HTMLButtonElement;expect(retry.disabled).toBe(true);fireEvent.click(retry);expect(equipmentGets).toBe(1)
    resolveEquip(new Response(JSON.stringify(emptyEquipment()),{status:200,headers:{'Content-Type':'application/json'}}));await screen.findByText(/Candidate wurde in wand ausgerüstet/)
  })
})
