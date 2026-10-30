{
const sleep=(ms)=>new Promise((resolve)=>setTimeout(resolve,ms));
const G=9.80665,TAU=Math.PI*2,GEAR_HEIGHT=1.6,FEET=3.28084;
const PLANE={wingLoading:250,clMax:1.3,clSlope:5,alphaStall:.26,cd0:.026,induced:.11,thrustToWeight:.32};
Object.assign(flight,{gamma:0,alpha:0,rollRate:0,onGround:false,hold:true,groundHeight:0,stalled:false,crashTimer:0,spawn:null,hinted:true});
let lastStallToast=0;
viewer.scene.globe.depthTestAgainstTerrain=hasIon;

/* ---------- flight model: point-mass with lift, drag, thrust, stall and ground roll ---------- */
const airDensity=(height)=>1.225*Math.exp(-Math.max(0,height)/8500);
const liftCoefficient=(alpha)=>{const over=Math.abs(alpha)-PLANE.alphaStall;if(over<=0)return PLANE.clSlope*alpha;return Math.sign(alpha)*PLANE.clMax*Math.max(.55,1-over*6);};
function sampleGround(){if(!hasIon)return 0;const height=viewer.scene.globe.getHeight(new Cesium.Cartographic(radians(flight.lon),radians(flight.lat)));return Number.isFinite(height)?height:flight.groundHeight;}
async function resolveGround(lat,lon){
  if(!hasIon)return 0;
  for(let i=0;i<40&&viewer.scene.terrainProvider instanceof Cesium.EllipsoidTerrainProvider;i++)await sleep(250);
  try{const [point]=await Cesium.sampleTerrainMostDetailed(viewer.scene.terrainProvider,[new Cesium.Cartographic(radians(lon),radians(lat))]);if(Number.isFinite(point.height))return point.height;}catch(_){}
  return flight.groundHeight||0;
}
function crash(reason){showToast(`${reason} - RESETTING`);flight.crashTimer=2.4;flight.speed=0;flight.throttle=0;}
function touchdown(floor){
  const sink=-flight.speed*Math.sin(flight.gamma);
  if(sink>5.5||Math.abs(flight.bank)>.4||flight.gamma<-.3){crash(sink>5.5?'HARD IMPACT':'CRASHED');return;}
  Object.assign(flight,{onGround:true,gamma:0,altitude:floor,bank:0,rollRate:0,stalled:false,alpha:clamp(flight.alpha,0,.22)});
  showToast(sink>3?'HARD LANDING':'TOUCHDOWN');
}
function respawn(){
  if(flight.spawn){placeOnRunway(flight.spawn.airport,flight.spawn.runway);return;}
  Object.assign(flight,{altitude:flight.groundHeight+300,speed:80,gamma:0,alpha:.08,bank:0,rollRate:0,throttle:.6,onGround:false});
}
updateFlight=function(dt){
  if(!flight.started||flight.paused)return;
  if(flight.hold){updatePlane();return;}
  if(flight.crashTimer>0){flight.crashTimer-=dt;if(flight.crashTimer<=0)respawn();updatePlane();updateHud();return;}
  if(!flight.hinted){flight.hinted=true;if(flight.onGround)showToast('HOLD W FOR POWER - ROTATE WITH UP ARROW AT ~120 KT - B BRAKES');}
  const rollIn=(keys.has('ArrowRight')?1:0)-(keys.has('ArrowLeft')?1:0),pitchIn=(keys.has('ArrowUp')?1:0)-(keys.has('ArrowDown')?1:0),throttleIn=(keys.has('KeyW')?1:0)-(keys.has('KeyS')?1:0);
  flight.throttle=clamp(flight.throttle+throttleIn*dt*.4,0,1);
  const ground=sampleGround();flight.groundHeight=ground;
  const floor=ground+GEAR_HEIGHT,rho=airDensity(flight.altitude),speed=flight.speed,q=.5*rho*speed*speed;
  const thrust=G*PLANE.thrustToWeight*(.04+.96*flight.throttle)*Math.pow(rho/1.225,.75);
  const wave=.12*Math.pow(Math.max(0,speed-170)/60,2);
  let alpha=flight.alpha;
  if(flight.onGround){
    const authority=clamp((speed-20)/40,0,1);
    if(pitchIn>0)alpha+=dt*.16*authority;else alpha-=dt*(pitchIn<0?.5:.8);
    alpha=clamp(alpha,0,.22);
    const cl=liftCoefficient(alpha),lift=q*cl/PLANE.wingLoading,drag=q*(PLANE.cd0+PLANE.induced*cl*cl+wave)/PLANE.wingLoading;
    const rolling=(keys.has('KeyB')?.55:.022)*G,accel=thrust-drag;
    if(speed<.5&&accel<=rolling)flight.speed=0;else flight.speed=Math.max(0,speed+(accel-rolling)*dt);
    flight.heading=(flight.heading+rollIn*.5*clamp(speed/6,0,1)*clamp(1.15-speed/70,.2,1)*dt+TAU)%TAU;
    flight.bank-=flight.bank*Math.min(1,dt*6);flight.rollRate=0;flight.gamma=0;flight.altitude=floor;flight.alpha=alpha;
    if(lift>G*1.02){flight.onGround=false;flight.gamma=.01;flight.altitude=floor+.3;showToast('AIRBORNE');}
  }else{
    const bank=flight.bank,cosBank=Math.max(.2,Math.cos(bank));
    const nTrim=Math.cos(flight.gamma)/cosBank-.8*flight.gamma;
    const alphaTrim=clamp(nTrim*G*PLANE.wingLoading/(Math.max(q,60)*PLANE.clSlope),-.05,PLANE.alphaStall*.9);
    const authority=clamp(speed/70,.35,1.2);
    if(pitchIn!==0)alpha+=pitchIn*dt*.22*authority;else alpha+=(alphaTrim-alpha)*Math.min(1,dt*1.6);
    if(alpha>PLANE.alphaStall+.02)alpha-=dt*.8;
    alpha=clamp(alpha,-.14,.36);
    const cl=liftCoefficient(alpha),lift=clamp(q*cl/PLANE.wingLoading,-4*G,8*G),drag=q*(PLANE.cd0+PLANE.induced*cl*cl+wave)/PLANE.wingLoading;
    flight.stalled=alpha>PLANE.alphaStall;
    const effective=Math.max(speed,25);
    flight.gamma=clamp(flight.gamma+(lift*Math.cos(bank)-G*Math.cos(flight.gamma))/effective*dt,-1.45,1.45);
    flight.heading=(flight.heading+lift*Math.sin(bank)/(effective*Math.max(.25,Math.cos(flight.gamma)))*dt+TAU)%TAU;
    flight.speed=Math.max(8,speed+(thrust*Math.cos(alpha)-drag-G*Math.sin(flight.gamma))*dt);
    flight.altitude+=speed*Math.sin(flight.gamma)*dt;
    const eff=clamp(speed/75,.25,1.15);
    flight.rollRate+=(rollIn*1.5*eff-flight.rollRate)*Math.min(1,dt*6);
    flight.bank=clamp(bank+flight.rollRate*dt,-1.35,1.35);
    if(rollIn===0&&Math.abs(flight.bank)<.45)flight.bank-=flight.bank*Math.min(1,dt*.35);
    flight.alpha=alpha;
    if(flight.stalled&&performance.now()-lastStallToast>4000){lastStallToast=performance.now();showToast('STALL - LOWER THE NOSE');}
    if(floor-flight.altitude>3)crash('TERRAIN IMPACT');
    else if(flight.altitude<=floor){if(flight.gamma<=.02)touchdown(floor);else flight.altitude=floor;}
  }
  flight.verticalSpeed=flight.onGround?0:flight.speed*Math.sin(flight.gamma);
  flight.pitch=clamp(flight.gamma+flight.alpha,-1.5,1.5);
  const horizontal=flight.speed*Math.cos(flight.gamma),north=Math.cos(flight.heading)*horizontal*dt,east=Math.sin(flight.heading)*horizontal*dt;
  flight.lat=clamp(flight.lat+north/111320,-85,85);flight.lon+=east/(111320*Math.max(.08,Math.cos(radians(flight.lat))));
  if(flight.lon>180)flight.lon-=360;if(flight.lon<-180)flight.lon+=360;
  updatePlane();updateHud();
};
const baseHud=updateHud;
updateHud=function(){baseHud();ui.altitude.textContent=String(Math.max(0,Math.round((flight.altitude-flight.groundHeight-GEAR_HEIGHT)*FEET))).padStart(4,'0');};

/* ---------- airport selection: start on a real runway threshold ---------- */
async function fetchRunways(ident){try{const response=await fetch(`/api/airports/${encodeURIComponent(ident)}/runways`);if(!response.ok)return[];return (await response.json()).runways||[];}catch(_){return[];}}
async function placeOnRunway(airport,runway){
  flight.hold=true;
  Object.assign(flight,{lat:runway.lat,lon:runway.lon,heading:radians(runway.heading_deg),speed:0,throttle:0,gamma:0,alpha:0,bank:0,rollRate:0,verticalSpeed:0,pitch:0,onGround:true,stalled:false,crashTimer:0,hinted:false,spawn:{airport,runway}});
  const ground=await resolveGround(runway.lat,runway.lon);
  flight.groundHeight=ground;flight.altitude=ground+GEAR_HEIGHT;
  updatePlane();updateHud();
  if(aircraft){aircraft.viewFrom=new Cesium.Cartesian3(-Math.sin(flight.heading)*70,-Math.cos(flight.heading)*70,24);}
  viewer.trackedEntity=undefined;setFollow(true);
  loadRealWorldScene();refreshAirports(true);
  flight.hold=false;
}
async function placeAirborne(airport){
  flight.hold=true;
  const ground=await resolveGround(airport.lat,airport.lon);
  Object.assign(flight,{lat:airport.lat,lon:airport.lon,heading:0,groundHeight:ground,altitude:ground+350,speed:85,throttle:.55,gamma:0,alpha:.07,pitch:.07,bank:0,rollRate:0,verticalSpeed:0,onGround:false,stalled:false,crashTimer:0,hinted:true,spawn:null});
  updatePlane();updateHud();setFollow(true);loadRealWorldScene();refreshAirports(true);
  flight.hold=false;
}
function showRunwayChoices(airport,runways,active){
  ui.results.innerHTML='';
  const title=document.createElement('div');title.className='result';title.innerHTML=`<strong>${escapeHtml(airport.ident)} RUNWAYS</strong><em>${escapeHtml(airport.name||'')}</em>`;ui.results.append(title);
  for(const runway of runways.slice(0,12)){
    const button=document.createElement('button');button.className='result'+(runway===active?' active':'');
    button.innerHTML=`<strong>RWY ${escapeHtml(runway.ident)}</strong><em>${Math.round(runway.heading_deg)} deg / ${Math.round(runway.length_m*FEET).toLocaleString()} ft</em>`;
    button.addEventListener('click',()=>{placeOnRunway(airport,runway).then(()=>showToast(`RUNWAY ${runway.ident} - ${airport.ident}`));});
    ui.results.append(button);
  }
}
jumpToAirport=async function(airport){
  ui.results.innerHTML='<div class="result">Loading runways...</div>';
  const runways=await fetchRunways(airport.ident);
  if(runways.length){
    await placeOnRunway(airport,runways[0]);
    showRunwayChoices(airport,runways,runways[0]);
    showToast(`${airport.ident} - RUNWAY ${runways[0].ident}`);
  }else{
    await placeAirborne(airport);
    ui.results.innerHTML='';
    showToast(`NO RUNWAY DATA FOR ${airport.ident} - AIRBORNE START`);
  }
};
const airportClicks=new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
airportClicks.setInputAction((event)=>{
  const picked=viewer.scene.pick(event.position),props=picked&&picked.id&&picked.id.properties;
  if(!props||!props.airport)return;
  if(flight.started&&!flight.paused){showToast('PAUSE (P) TO PICK AN AIRPORT ON THE MAP');return;}
  jumpToAirport(props.airport.getValue(Cesium.JulianDate.now()));
},Cesium.ScreenSpaceEventType.LEFT_CLICK);

/* ---------- scene loading: serialise reloads so building textures never race ---------- */
let buildingEpoch=0,buildingIndex=0,pendingBuildings=[],flushScheduled=false,sceneRunning=false,scenePending=null;
const baseSceneLoader=loadRealWorldScene;
loadRealWorldScene=async function(...args){
  if(sceneRunning){scenePending=args;return;}
  sceneRunning=true;buildingEpoch++;buildingIndex=0;pendingBuildings=[];
  try{await baseSceneLoader(...args);clipIonBuildings();}finally{sceneRunning=false;}
  if(scenePending){const next=scenePending;scenePending=null;return loadRealWorldScene(...next);}
};
function clipIonBuildings(){
  if(!ionBuildingsTileset||!Cesium.ClippingPolygonCollection)return;
  try{
    const ring=[],cosLat=Math.max(.05,Math.cos(radians(flight.lat)));
    for(let i=0;i<24;i++){const a=i/24*TAU;ring.push(flight.lon+Math.cos(a)*650/(111320*cosLat),flight.lat+Math.sin(a)*650/111320);}
    ionBuildingsTileset.clippingPolygons=new Cesium.ClippingPolygonCollection({polygons:[new Cesium.ClippingPolygon({positions:Cesium.Cartesian3.fromDegreesArray(ring)})]});
  }catch(_){}
}
viewer.clock.onTick.addEventListener(()=>{if(buildingsVisible&&!buildingSource.show)buildingSource.show=true;});

/* ---------- buildings: satellite imagery on the roofs, textured facades on the walls ---------- */
const TEXTURED_BUILDINGS=140,tileCache=new Map(),roofCache=new Map(),facadeCache=new Map();
const mix=(a,b,t)=>a.map((v,i)=>Math.round(v*(1-t)+b[i]*t)),rgb=(c)=>`rgb(${c[0]},${c[1]},${c[2]})`;
const mercator=(lon,lat,z)=>{const size=256*Math.pow(2,z),s=Math.sin(radians(lat));return[(lon+180)/360*size,(.5-Math.log((1+s)/(1-s))/(4*Math.PI))*size];};
function loadTile(z,x,y){
  const key=`${z}/${x}/${y}`;if(tileCache.has(key))return tileCache.get(key);
  const promise=(async()=>{const response=await fetch(`https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${z}/${y}/${x}`,{mode:'cors'});if(!response.ok)throw Error('tile');return createImageBitmap(await response.blob());})();
  tileCache.set(key,promise);promise.catch(()=>tileCache.delete(key));
  if(tileCache.size>80)tileCache.delete(tileCache.keys().next().value);
  return promise;
}
async function roofImage(item){
  if(roofCache.has(item.id))return roofCache.get(item.id);
  const lons=item.footprint.map((p)=>p[0]),lats=item.footprint.map((p)=>p[1]);
  const west=Math.min(...lons),east=Math.max(...lons),south=Math.min(...lats),north=Math.max(...lats);
  let z=19,a=mercator(west,north,z),b=mercator(east,south,z);
  if(b[0]-a[0]>220||b[1]-a[1]>220){z=18;a=mercator(west,north,z);b=mercator(east,south,z);}
  const w=Math.max(2,b[0]-a[0]),h=Math.max(2,b[1]-a[1]);
  const tx0=Math.floor(a[0]/256),tx1=Math.floor(b[0]/256),ty0=Math.floor(a[1]/256),ty1=Math.floor(b[1]/256);
  if((tx1-tx0+1)*(ty1-ty0+1)>9)return null;
  const cw=Math.min(128,Math.max(8,Math.round(w))),ch=Math.min(128,Math.max(8,Math.round(h)));
  const canvas=document.createElement('canvas');canvas.width=cw;canvas.height=ch;const ctx=canvas.getContext('2d');
  const jobs=[];
  for(let tx=tx0;tx<=tx1;tx++)for(let ty=ty0;ty<=ty1;ty++)jobs.push(loadTile(z,tx,ty).then((bitmap)=>ctx.drawImage(bitmap,(tx*256-a[0])*cw/w,(ty*256-a[1])*ch/h,256*cw/w,256*ch/h)));
  await Promise.all(jobs);
  const probe=document.createElement('canvas');probe.width=probe.height=1;const pctx=probe.getContext('2d');pctx.drawImage(canvas,0,0,1,1);
  const d=pctx.getImageData(0,0,1,1).data,result={canvas,color:[d[0],d[1],d[2]]};
  if(roofCache.size>600)roofCache.delete(roofCache.keys().next().value);
  roofCache.set(item.id,result);return result;
}
function buildingStyle(item){
  const kind=String(item.name||'').toLowerCase();
  if(item.height_m>=45)return'glass';
  if(/house|residential|detached|bungalow|terrace|villa|cabin/.test(kind))return'house';
  if(/industrial|warehouse|factory|hangar|storage|garage|shed|barn|hall/.test(kind))return'plain';
  return'office';
}
const BAYS={glass:[3,3.9],house:[4.5,2.8],plain:[8,6],office:[6,3.6]};
function facadeCanvas(style,color){
  const key=`${style}:${color.map((v)=>Math.round(v/24)).join(',')}`;if(facadeCache.has(key))return facadeCache.get(key);
  const canvas=document.createElement('canvas');canvas.width=canvas.height=128;const g=canvas.getContext('2d');
  const wall=style==='glass'?[70,98,120]:mix(color,[205,198,186],.6);
  g.fillStyle=rgb(wall);g.fillRect(0,0,128,128);
  const glass=(x,y,w,h)=>{const grad=g.createLinearGradient(x,y,x+w,y+h);grad.addColorStop(0,'#5c7a90');grad.addColorStop(1,'#1f2c37');g.fillStyle=grad;g.fillRect(x,y,w,h);};
  if(style==='glass'){glass(0,0,128,128);g.strokeStyle='rgba(210,225,235,.55)';g.lineWidth=2;g.strokeRect(1,1,126,126);g.beginPath();g.moveTo(64,0);g.lineTo(64,128);g.stroke();}
  else if(style==='house'){g.fillStyle='#f2efe6';g.fillRect(32,30,64,70);glass(37,35,54,60);g.strokeStyle='#f2efe6';g.lineWidth=3;g.beginPath();g.moveTo(64,35);g.lineTo(64,95);g.moveTo(37,65);g.lineTo(91,65);g.stroke();}
  else if(style==='plain'){g.strokeStyle=rgb(mix(wall,[40,40,40],.25));g.lineWidth=2;for(let x=0;x<128;x+=16){g.beginPath();g.moveTo(x,0);g.lineTo(x,128);g.stroke();}glass(8,14,112,22);}
  else{g.fillStyle=rgb(mix(wall,[255,255,255],.35));g.fillRect(16,22,96,80);glass(20,26,88,70);g.strokeStyle=rgb(mix(wall,[30,30,30],.35));g.lineWidth=3;g.beginPath();g.moveTo(64,26);g.lineTo(64,96);g.stroke();}
  g.fillStyle='rgba(0,0,0,.14)';g.fillRect(0,122,128,6);
  facadeCache.set(key,canvas);return canvas;
}
function closedRing(ring){const out=ring.slice(),a=out[0],b=out[out.length-1];if(a[0]!==b[0]||a[1]!==b[1])out.push(a);return out;}
function ringLength(ring){let total=0;for(let i=1;i<ring.length;i++){const dx=(ring[i][0]-ring[i-1][0])*111320*Math.cos(radians(ring[i][1])),dy=(ring[i][1]-ring[i-1][1])*111320;total+=Math.hypot(dx,dy);}return total;}
function addPlainBuilding(item){
  buildingSource.entities.add({id:item.id,name:item.name,polygon:{hierarchy:footprintPositions(item.footprint),height:0,extrudedHeight:item.height_m,perPositionHeight:false,heightReference:Cesium.HeightReference.CLAMP_TO_GROUND,extrudedHeightReference:Cesium.HeightReference.RELATIVE_TO_GROUND,material:Cesium.Color.fromCssColorString('#8ca4ae').withAlpha(.72),outline:false}});
}
function buildTexturedEntities(item,base,roof){
  const ring=closedRing(item.footprint),style=buildingStyle(item),color=roof?roof.color:[150,155,160];
  const min=Number(item.min_height_m)||0,bottom=base+min-(min>0?0:4),top=base+item.height_m;
  const [bay,floorHeight]=BAYS[style],repeat=new Cesium.Cartesian2(Math.max(1,Math.round(ringLength(ring)/bay)),Math.max(1,Math.round((top-bottom)/floorHeight)));
  buildingSource.entities.add({id:`${item.id}-walls`,name:item.name,wall:{positions:Cesium.Cartesian3.fromDegreesArray(ring.flat()),minimumHeights:new Array(ring.length).fill(bottom),maximumHeights:new Array(ring.length).fill(top),material:new Cesium.ImageMaterialProperty({image:facadeCanvas(style,color),repeat})}});
  buildingSource.entities.add({id:`${item.id}-roof`,name:item.name,polygon:{hierarchy:footprintPositions(item.footprint),height:top+.05,material:roof?new Cesium.ImageMaterialProperty({image:roof.canvas}):Cesium.Color.fromBytes(color[0],color[1],color[2]),outline:false}});
}
async function processBuildings(epoch,items){
  let bases=items.map(()=>0);
  if(hasIon){try{const samples=await Cesium.sampleTerrainMostDetailed(viewer.scene.terrainProvider,items.map((item)=>new Cesium.Cartographic(radians(item.lon),radians(item.lat))));bases=samples.map((p)=>Number.isFinite(p.height)?p.height:0);}catch(_){}}
  if(epoch!==buildingEpoch)return;
  let next=0;
  const worker=async()=>{
    while(next<items.length){
      const index=next++;if(epoch!==buildingEpoch)return;
      let roof=null;try{roof=await roofImage(items[index]);}catch(_){}
      if(epoch!==buildingEpoch)return;
      buildTexturedEntities(items[index],bases[index],roof);
    }
  };
  await Promise.all(Array.from({length:6},worker));
}
window.skylineAddBuilding=function(item){
  if(buildingIndex++>=TEXTURED_BUILDINGS){addPlainBuilding(item);return;}
  pendingBuildings.push(item);
  if(flushScheduled)return;
  flushScheduled=true;
  setTimeout(()=>{flushScheduled=false;const items=pendingBuildings;pendingBuildings=[];processBuildings(buildingEpoch,items);},0);
};

/* ---------- start the session on a runway ---------- */
(async()=>{
  while(!aircraft||!catalog||document.getElementById('loading'))await sleep(150);
  try{await jumpToAirport({ident:'KSEA',name:'Seattle-Tacoma International Airport',lat:47.4489,lon:-122.3094,elevation_ft:433});}catch(_){}
  flight.hold=false;
})();
}
