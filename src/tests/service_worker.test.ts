import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { expect, it, vi } from 'vitest'

it('never serves stale health, capability or authentication from the shell cache', () => {
  const handlers: Record<string,(e:unknown)=>void>={}
  vm.runInNewContext(readFileSync('public/sw.js','utf8'),{
    self:{location:{origin:'https://example.test'},addEventListener:(name:string,handler:(e:unknown)=>void)=>{handlers[name]=handler}},
    URL,
  })
  for(const path of ['/api/unified','/api/v1/cv/health','/api/engineering-session']){
    const respondWith=vi.fn()
    handlers.fetch({request:{method:'GET',url:'https://example.test'+path},respondWith})
    expect(respondWith).not.toHaveBeenCalled()
  }
})
