import { FocusEvent, MouseEvent, ReactNode, useEffect, useId, useRef, useState } from 'react'
import { ParsedItem } from './api'

type Props = {
  item: ParsedItem
  className?: string
  children: ReactNode
  asListItem?: boolean
  onCardClick?: () => void
}

const sourceLabels: Record<string,string> = {
  implicit: 'Implizit', explicit: 'Modifikatoren', enchant: 'Verzauberung',
  rune: 'Runen', crafted: 'Hergestellt', unique: 'Einzigartig', desecrated: 'Entweiht',
}

function rarityClass(rarity:string|null) {
  return `rarity-${(rarity ?? 'normal').toLowerCase().replace(/[^a-z]/g,'')}`
}

function DetailSection({title,children}:{title:string;children:ReactNode}) {
  return <section className="item-detail-section"><h4>{title}</h4>{children}</section>
}

export function ItemDetailsContent({item}:{item:ParsedItem}) {
  const requirements=[item.required_level!==null&&`Level ${item.required_level}`,item.required_strength!==null&&`${item.required_strength} Stärke`,item.required_dexterity!==null&&`${item.required_dexterity} Geschick`,item.required_intelligence!==null&&`${item.required_intelligence} Intelligenz`].filter(Boolean)
  const defences=[
    item.quality!==null&&{text:`Qualität: +${item.quality}%`,augmented:false},
    item.armour!==null&&{text:`Rüstung: ${item.armour}`,augmented:item.armour_augmented},
    item.evasion!==null&&{text:`Ausweichen: ${item.evasion}`,augmented:item.evasion_augmented},
    item.energy_shield!==null&&{text:`Energieschild: ${item.energy_shield}`,augmented:item.energy_shield_augmented},
    item.spirit!==null&&{text:`Spirit: ${item.spirit}`,augmented:false},
  ].filter((value):value is {text:string;augmented:boolean}=>Boolean(value))
  const skill=item.granted_skill?.trim() || null
  const modifiers=item.modifiers.filter(mod=>mod.source!=='granted_skill'&&(!skill||!mod.raw_text.toLowerCase().includes(skill.toLowerCase())))
  const groups=modifiers.reduce<Record<string,typeof modifiers>>((result,modifier)=>{const source=modifier.rune?'rune':modifier.crafted?'crafted':modifier.desecrated?'desecrated':modifier.implicit?'implicit':modifier.unique?'unique':modifier.source||'explicit';(result[source]??=[]).push(modifier);return result},{})
  return <div className={`item-details-content ${rarityClass(item.rarity)}`}>
    <header className="item-detail-header"><strong>{item.name??item.base_type??'Unbenanntes Item'}</strong>{item.name&&item.base_type&&item.name!==item.base_type&&<span>{item.base_type}</span>}</header>
    {defences.length>0&&<DetailSection title="Werte">{defences.map(value=><p key={value.text} className={value.augmented?'item-value-augmented':undefined}>{value.text}</p>)}</DetailSection>}
    {requirements.length>0&&<DetailSection title="Benötigt">{requirements.map(value=><p key={String(value)}>{value}</p>)}</DetailSection>}
    {item.sockets.length>0&&<DetailSection title="Sockel"><p>{item.sockets.join(' ')}</p></DetailSection>}
    {item.item_level!==null&&<DetailSection title="Gegenstandsstufe"><p>{item.item_level}</p></DetailSection>}
    {skill&&<DetailSection title="Gewährte Fertigkeit"><p className="item-skill">{skill}</p></DetailSection>}
    {Object.entries(groups).map(([source,mods])=><DetailSection key={source} title={sourceLabels[source]??source}><div className={`item-mods mod-${source}`}>{mods.map((mod,index)=><p key={`${mod.normalized_key}-${index}`}>{mod.raw_text}</p>)}</div></DetailSection>)}
    {!item.identified&&<p className="item-status unidentified">Nicht identifiziert</p>}
    {item.corrupted&&<p className="item-status corrupted">Korrumpiert</p>}
  </div>
}

export function EquipmentItemDetails({item,className='',children,asListItem=false,onCardClick}:Props) {
  const [hovered,setHovered]=useState(false)
  const [open,setOpen]=useState(false)
  const id=useId()
  const root=useRef<HTMLElement|null>(null)
  const closeButton=useRef<HTMLButtonElement|null>(null)
  useEffect(()=>{if(!open)return;closeButton.current?.focus();const close=(event:KeyboardEvent)=>{if(event.key==='Escape')setOpen(false);if(event.key==='Tab'){event.preventDefault();closeButton.current?.focus()}};document.addEventListener('keydown',close);return()=>{document.removeEventListener('keydown',close);root.current?.querySelector<HTMLButtonElement>('.item-details-button')?.focus()}},[open])
  const content=<ItemDetailsContent item={item}/>
  const common={ref:root as never,className:`equipment-card equipment-card-with-details ${className}`,onClick:(event:MouseEvent<HTMLElement>)=>{if(onCardClick&&!((event.target as HTMLElement).closest('button')))onCardClick()},onMouseEnter:()=>setHovered(true),onMouseLeave:()=>setHovered(false),onFocusCapture:()=>setHovered(true),onBlurCapture:(event:FocusEvent<HTMLElement>)=>{if(!event.currentTarget.contains(event.relatedTarget as Node))setHovered(false)}}
  const body=<>{children}<button type="button" className="item-details-button" aria-haspopup="dialog" onClick={()=>setOpen(true)}>Details anzeigen</button>{hovered&&!open&&<div id={id} className="item-hover-details" role="tooltip">{content}</div>}{open&&<div className="item-details-backdrop" role="presentation" onMouseDown={event=>{if(event.target===event.currentTarget)setOpen(false)}}><div className="item-details-dialog" role="dialog" aria-modal="true" aria-label={`Details zu ${item.name??item.base_type??'Item'}`}><button ref={closeButton} type="button" className="item-details-close" aria-label="Itemdetails schließen" onClick={()=>setOpen(false)}>×</button>{content}</div></div>}</>
  return asListItem?<article {...common} role="listitem" tabIndex={0} aria-describedby={id}>{body}</article>:<div {...common}>{body}</div>
}
