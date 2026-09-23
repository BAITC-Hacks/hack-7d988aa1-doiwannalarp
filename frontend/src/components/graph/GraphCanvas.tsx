import {useEffect,useMemo,useRef,useState} from 'react';
import Graph from 'graphology';
import Sigma from 'sigma';
import {EdgeCurvedArrowProgram} from '@sigma/edge-curve';
import {createNodeBorderProgram} from '@sigma/node-border';
import {Plus,Minus,Maximize,MousePointer2} from 'lucide-react';
import type {Client,Edge} from '../../types';
import {clusterColor,money,roles,shortGid} from '../../lib/data';
import {useData} from '../../app/context';
import {EmptyState,ErrorState} from '../shared';

const BorderProgram=createNodeBorderProgram({borders:[{size:{attribute:'borderSize',defaultValue:0,mode:'pixels'},color:{attribute:'borderColor',defaultValue:'#17283E'}},{size:{value:2,mode:'pixels'},color:{value:'#FFFFFF'}},{size:{fill:true},color:{attribute:'color'}}]});
interface Props{nodes:Client[];edges:Edge[];selected?:string;onSelect:(gid:string)=>void;onEdge?:(e:Edge)=>void;onExpand?:(gid:string)=>void;color?:'role'|'cluster';local?:boolean}
export function GraphCanvas({nodes,edges,selected,onSelect,onEdge,onExpand,color='role',local=false}:Props){
  const container=useRef<HTMLDivElement>(null);const renderer=useRef<Sigma|null>(null);const callbacks=useRef({onSelect,onEdge,onExpand});callbacks.current={onSelect,onEdge,onExpand};
  const {settings}=useData();const [error,setError]=useState('');const [hover,setHover]=useState<Edge>();
  const graph=useMemo(()=>{const g=new Graph({type:'directed',allowSelfLoops:true});const ids=new Set(nodes.map(n=>n.gid));const adjacent=new Set<string>();if(selected)edges.forEach(e=>{if(e.src===selected)adjacent.add(e.dst);if(e.dst===selected)adjacent.add(e.src)});
    const sorted=[...nodes].sort((a,b)=>a.gid.localeCompare(b.gid));const others=sorted.filter(n=>n.gid!==selected);
    sorted.forEach((n,i)=>{const position=others.indexOf(n);const angle=position*2.399963229728653;const radius=2+Math.sqrt(position+1)*1.35;const x=local&&nodes.length<100?(n.gid===selected?0:Math.cos(angle)*radius):(n.x??Math.cos(i*2.399)*Math.sqrt(i+1));const y=local&&nodes.length<100?(n.gid===selected?0:Math.sin(angle)*radius):(n.y??Math.sin(i*2.399)*Math.sqrt(i+1));const active=!selected||n.gid===selected||adjacent.has(n.gid);g.addNode(n.gid,{x,y,label:(n.is_seed?'◉ ':'')+shortGid(n.gid),size:n.gid===selected?15:Math.max(4,Math.min(10,5+(n.priority_score??0)*5)),color:!active?'#DDE4EF':color==='cluster'&&n.cluster_id!=null?clusterColor(n.cluster_id):n.role?roles[n.role].color:'#7B879B',borderColor:n.gid===selected?'#15243D':'#356DF3',borderSize:n.gid===selected?3:n.is_seed?2:0,type:'border',forceLabel:n.gid===selected,zIndex:n.gid===selected?10:0})});
    const max=Math.max(1,...edges.map(e=>e.sum_kzt));edges.forEach((e,i)=>{if(!ids.has(e.src)||!ids.has(e.dst))return;g.addDirectedEdgeWithKey(String(i),e.src,e.dst,{type:'curved',curvature:0.18,size:.6+2*Math.log1p(e.sum_kzt)/Math.log1p(max),color:!selected||e.src===selected||e.dst===selected?'#9FAEC4':'#E5EAF2',label:money(e.sum_kzt,true)+' · '+e.n_tx+' переводов',original:e})});return g;
  },[nodes,edges,selected,color,local]);
  useEffect(()=>{if(!container.current||!nodes.length)return;setError('');let sigma:Sigma|undefined;
    try{sigma=new Sigma(graph,container.current,{nodeProgramClasses:{border:BorderProgram},edgeProgramClasses:{curved:EdgeCurvedArrowProgram},defaultNodeType:'border',defaultEdgeType:'curved',enableEdgeEvents:true,renderEdgeLabels:false,renderLabels:settings.labels,labelFont:'system-ui',labelSize:12,labelColor:{color:'#15243D'},labelDensity:local?.7:.06,labelRenderedSizeThreshold:local?4:8,stagePadding:48,zIndex:true,minCameraRatio:.02,maxCameraRatio:5});renderer.current=sigma;
      sigma.on('clickNode',({node})=>callbacks.current.onSelect(node));sigma.on('doubleClickNode',e=>{e.preventSigmaDefault();callbacks.current.onExpand?.(e.node)});sigma.on('clickEdge',({edge})=>callbacks.current.onEdge?.(graph.getEdgeAttribute(edge,'original')));sigma.on('enterEdge',({edge})=>setHover(graph.getEdgeAttribute(edge,'original')));sigma.on('leaveEdge',()=>setHover(undefined));
    }catch(e){setError('WebGL недоступен. Используйте таблицу клиентов и список связей в карточке. '+(e instanceof Error?e.message:''))}
    return()=>{sigma?.kill();renderer.current=null};
  },[graph,settings.labels,local,nodes.length]);
  if(!nodes.length)return <EmptyState title="Нет узлов для отображения"><p>Очистите фильтры или выберите другой узел.</p></EmptyState>;
  return <div className="graph-canvas"><div ref={container} className="sigma-container" aria-label="Направленная транзакционная сеть"/>{error&&<div className="graph-fallback"><ErrorState message={error}/></div>}
    <div className="graph-hint"><MousePointer2 size={13}/>Выберите узел или связь · двойной клик раскрывает соседей</div>
    {hover&&<div className="edge-tooltip"><span className="gid">{shortGid(hover.src)} → {shortGid(hover.dst)}</span><strong>{money(hover.sum_kzt)}</strong><span>{hover.n_tx} переводов</span></div>}
    <div className="graph-zoom"><button aria-label="Приблизить" title="Приблизить" onClick={()=>renderer.current?.getCamera().animatedZoom({duration:0})}><Plus size={17}/></button><button aria-label="Отдалить" title="Отдалить" onClick={()=>renderer.current?.getCamera().animatedUnzoom({duration:0})}><Minus size={17}/></button><button aria-label="Вписать в экран" title="Вписать в экран" onClick={()=>renderer.current?.getCamera().animatedReset({duration:0})}><Maximize size={16}/></button></div>
  </div>;
}
