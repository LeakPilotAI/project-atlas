const {test} = require('node:test');
const assert = require('node:assert/strict');
const ui = require('../backend/app/static/quality_dips_selected_paper.js');
function view(){return {schema:'ATLAS_EXIT_HISTORY_V1',status:'ACKNOWLEDGED',startup_authorized:false,total_cash:null,total_net:null,accounts:{},rows:
 ['STRATEGY_EXIT','USER_SHUTDOWN','STOP_LOSS','TAKE_PROFIT','RISK_SHUTDOWN','UNKNOWN'].map((reason,i)=>({reason,lane:i%2?'HYPERLIQUID':'QUALITY_DIPS',currency:i%2?'USDC':'USD',session_id:'session-'+i,operation_id:'exit-'+i,quantity:'0.25',remaining:'0',gross:'2.5',costs:'0.1',net:'2.4',execution:'SIMULATED',stop_command_id:reason==='USER_SHUTDOWN'?'bound-stop':null}))};}
test('all categories retain cross-session USD USDC evidence and do not consolidate',()=>{
 const s=ui.renderTradeHistory(view());for(const word of ['All trades','Strategy exits','User shutdown exits','Risk exits','Unresolved exits','USD','USDC','USER_SHUTDOWN','session-5'])assert.ok(s.includes(word));
 assert.ok(s.includes('never removes exits'));assert.ok(!s.includes('Total equity'));
});
test('user filter excludes strategy exits without changing original financial rows',()=>{
 const v=view(),before=JSON.stringify(v),s=ui.renderTradeHistory(v,'USER');assert.ok(s.includes('<td>USER_SHUTDOWN</td>'));assert.ok(!s.includes('<td>STRATEGY_EXIT</td>'));assert.equal(JSON.stringify(v),before);
});
test('strategy risk and unresolved filters have distinct verified rows',()=>{
 assert.ok(ui.renderTradeHistory(view(),'STRATEGY').includes('<td>TAKE_PROFIT</td>'));
 assert.ok(!ui.renderTradeHistory(view(),'STRATEGY').includes('<td>USER_SHUTDOWN</td>'));
 assert.ok(ui.renderTradeHistory(view(),'RISK').includes('<td>STOP_LOSS</td>'));
 assert.ok(ui.renderTradeHistory(view(),'UNRESOLVED').includes('<td>UNKNOWN</td>'));
});
test('incomplete financial history never displays fabricated closed trades',()=>{
 const open=view();open.unresolved=[{lane:'QUALITY_DIPS',position_id:'p',state:'POSITION_OPEN_NOT_AN_EXIT',quantity:'0.6'}];assert.match(ui.renderTradeHistory(open,'UNRESOLVED'),/not a completed exit/);
 const v=view();v.status='INCOMPLETE';assert.match(ui.renderTradeHistory(v),/INCOMPLETE/);assert.ok(!ui.renderTradeHistory(v).includes('<td>USER_SHUTDOWN</td>'));
});
test('malformed reason currency or unbound user exit refuses',()=>{
 for(const change of [{reason:'OTHER'},{currency:'USD'}, {stop_command_id:null}]){const v=view();Object.assign(v.rows[1],change);assert.match(ui.renderTradeHistory(v),/UNKNOWN/);}
});
test('untrusted session labels are escaped',()=>{const v=view();v.rows[0].session_id='<img src=x>';assert.ok(!ui.renderTradeHistory(v).includes('<img'));assert.ok(ui.renderTradeHistory(v).includes('&lt;img'));});
