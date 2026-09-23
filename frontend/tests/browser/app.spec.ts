import {test,expect} from '@playwright/test';
test('real dataset, all routes, GID search, boundary, exports and desktop layout',async({page,request})=>{
  const response=await request.get('/api/dataset');expect(response.ok()).toBeTruthy();const d=await response.json();
  expect(d.nodes.length).toBe(2248);expect(d.transactions.length).toBe(4840);expect(d.nodes.every((n:any)=>typeof n.gid==='string')).toBeTruthy();
  const sum=d.transactions.reduce((s:number,t:any)=>s+t.sum_kzt,0);expect(sum).toBeCloseTo(d.meta.total_sum,2);
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setViewportSize({width:1440,height:900});await page.goto('/graph');await expect(page.getByText('Окружение узла',{exact:true})).toBeVisible();await expect(page.locator('.sigma-container canvas').first()).toBeVisible();await page.screenshot({path:'test-results/graph-1440.png'});
  const isolated=d.nodes.find((n:any)=>n.in_deg===0&&n.out_deg===0);await page.getByRole('textbox',{name:'Поиск по GID',exact:true}).fill(isolated.gid);await page.locator('.search-results button').filter({hasText:isolated.gid}).click();await expect(page).toHaveURL(new RegExp('gid='+isolated.gid));await expect(page.locator('.inspector-gid')).toContainText(isolated.gid);
  const boundary=d.nodes.find((n:any)=>n.depth===4);await page.goto('/graph?gid='+boundary.gid);await expect(page.locator('.inspector').getByText(/Отсутствие исходящих переводов не доказывает/)).toBeVisible();
  await expect(page.locator('.inspector').getByRole('heading',{name:'Причины приоритета'})).toBeVisible();
  await expect(page.locator('.inspector').getByText(boundary.why,{exact:true})).toBeAttached();
  await expect(page.locator('.inspector').getByText(boundary.recommended_action,{exact:true})).toBeAttached();
  for(const route of ['/overview','/clients?depth=4','/clients/'+boundary.gid,'/transactions?gid='+boundary.gid,'/clusters','/clusters/'+boundary.cluster_id,'/analytics','/data','/settings']){await page.goto(route);await expect(page.locator('h1')).toBeVisible();expect(await page.locator('body').innerText()).not.toContain('Небезопасный GID')}
  await page.goto('/clients?depth=4');await page.locator('tbody .gid').first().click();await page.getByRole('link',{name:'Клиенты',exact:true}).last().click();await expect(page).toHaveURL(/depth=4/);
  const csv=await (await request.get('/api/exports/nodes_roles.csv')).text();expect(csv).toContain(boundary.gid);expect(csv.trim().split('\n')).toHaveLength(d.nodes.length+1);
  await page.setViewportSize({width:1920,height:1080});await page.goto('/graph');await expect(page.locator('.sigma-container canvas').first()).toBeVisible();await page.screenshot({path:'test-results/graph-1920.png'});
  await page.getByRole('button',{name:'Вся сеть',exact:true}).click();await expect(page.locator('.graph-caption')).toContainText('2 248'.replace(' ','\u00a0'));await expect(page.locator('.sigma-container canvas').first()).toBeVisible();expect(errors).toEqual([]);
});

test('MoneyGraph branding and filtered transaction totals match the downloaded CSV',async({page,request})=>{
  const d=await (await request.get('/api/dataset')).json();
  const gid=d.transactions[0].src;
  const expected=d.transactions.filter((t:any)=>t.src===gid||t.dst===gid);
  const total=expected.reduce((sum:number,t:any)=>sum+t.sum_kzt,0);
  const formatted=new Intl.NumberFormat('ru-RU',{maximumFractionDigits:2}).format(total)+' KZT';
  await page.goto('/transactions?gid='+gid);
  await expect(page).toHaveTitle('MoneyGraph — транзакционная сеть');
  await expect(page.locator('.brand strong')).toHaveText('MoneyGraph');
  await expect(page.locator('.table-summary')).toContainText(formatted);
  const downloadEvent=page.waitForEvent('download');
  await page.getByRole('button',{name:'Экспорт выборки',exact:true}).click();
  const download=await downloadEvent;
  expect(download.suggestedFilename()).toBe('transactions_filtered.csv');
  const stream=await download.createReadStream();
  if(!stream)throw Error('Download stream is unavailable');
  let content='';
  for await(const chunk of stream)content+=chunk.toString();
  const lines=content.replace(/^\ufeff/,'').trim().split(/\r?\n/);
  expect(lines[0]).toBe('"date","src","dst","sum_kzt"');
  expect(lines.length-1).toBe(expected.length);
  expect(content).toContain(gid);
  const downloadedTotal=lines.slice(1).reduce((sum,line)=>sum+Number(line.split(',').at(-1)!.replaceAll('"','')),0);
  expect(downloadedTotal).toBeCloseTo(total,2);
});
