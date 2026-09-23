import {describe,it,expect} from 'vitest';
import {assertDataset,csv,filterNodes,neighborhood} from '../src/lib/data';
import type {Dataset,Client} from '../src/types';
const a='9223372036854775806',b='9223372036854775807';
const fixture={meta:{id:'test'},nodes:[{gid:a,is_seed:true,depth:0},{gid:b,is_seed:false,depth:4}],edges:[],transactions:[]} as unknown as Dataset;
describe('identifier integrity',()=>{
  it('keeps adjacent int64 GIDs distinct and searchable, including isolated nodes',()=>{const d=assertDataset(fixture);expect(new Set(d.nodes.map(n=>n.gid)).size).toBe(2);expect(filterNodes(d.nodes,{q:b})[0].gid).toBe(b);expect([...neighborhood(a,[],1,'both')]).toEqual([a])});
  it('rejects numeric IDs, including already rounded values',()=>{expect(()=>assertDataset({...fixture,nodes:[{gid:9223372036854775807} as unknown as Client]})).toThrow('Небезопасный GID')});
  it('exports every digit unchanged',()=>{const result=csv(fixture.nodes as unknown as Record<string,unknown>[],['gid','depth']);expect(result).toContain(a);expect(result).toContain(b)});
});
