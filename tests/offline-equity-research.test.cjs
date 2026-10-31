const {test}=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const {consumeOfflineEquityResearch:consume}=require(process.env.OFFLINE_EQUITY_MODULE);
const fixture=JSON.parse(fs.readFileSync(process.env.OFFLINE_EQUITY_FIXTURE,"utf8"));
const now=Date.parse(fixture.timestamp);
test("Python contract accepted with absent RVOL and locked authority",()=>{
 const r=consume(fixture,now);assert.equal(r.ok,true);assert.equal(r.value.relativeVolume,null);assert.equal(r.value.authorityLocked,true);
});
for(const [field,value] of [["schema_version","wrong"],["scope","LIVE"],["price",NaN],["price",true],["relative_volume",5],["relative_volume_status","COMPARABLE_HISTORY"],["wire_request_count",0],["provider_rights_status","APPROVED"],["timestamp","2026-10-19T12:00:00"],["session","CLOSED"],["source",null],["symbol","../secret"]]){
 test(`refuses invalid ${field}=${value}`,()=>assert.equal(consume({...fixture,[field]:value},now).ok,false));
}
for(const capability of ["live_orders","paper_orders","discord","network_authorized"]){
 test(`refuses ${capability} grant`,()=>assert.equal(consume({...fixture,capabilities:{...fixture.capabilities,[capability]:true}},now).ok,false));
}
test("unknown authority field is refused",()=>assert.equal(consume({...fixture,capabilities:{...fixture.capabilities,unattended:true}},now).ok,false));
test("HTTP success cannot mask old data",()=>assert.equal(consume(fixture,now+181000).reason,"STALE_OR_FUTURE"));
test("future data refused",()=>assert.equal(consume(fixture,now-1000).reason,"STALE_OR_FUTURE"));
test("missing input refused",()=>assert.equal(consume(null,now).ok,false));
