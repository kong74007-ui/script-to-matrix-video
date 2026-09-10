/* Reference-specific media compositor. Radial sampling adapts the installed
 * HyperFrames cinematic-zoom registry primitive; no RGB color offsets.
 * HF 0.8.33 invokes hf-seek again AFTER injected frame images decode. Read
 * those images in render, native video in preview; never control playback.
 * All camera/blur parameters are pure functions of reference frame number.
 */
window.initYellowBanner = function () {
  'use strict';
  const duration=302/30;
  const canvas=document.getElementById('media-canvas');
  const gl=canvas.getContext('webgl',{alpha:true,premultipliedAlpha:false,preserveDrawingBuffer:true});
  if(!gl)throw new Error('yellow-banner-zoom requires WebGL');
  const vertex='attribute vec2 p;varying vec2 uv;void main(){uv=vec2((p.x+1.)*.5,(1.-p.y)*.5);gl_Position=vec4(p,0.,1.);}';
  const fragment=`precision highp float;
    varying vec2 uv;uniform sampler2D tex;uniform float band;uniform float zoom;
    uniform float strength;uniform float portrait;
    vec4 sampleAt(vec2 p){
      vec2 q=(p-vec2(.5))/zoom+vec2(.5);
      float h=mix(.31640625*band,1.,portrait);
      if(q.y<.5-h*.5||q.y>.5+h*.5)return vec4(0.);
      vec2 sourceUV=vec2(q.x,.5+(q.y-.5)/band);
      if(portrait>.5)sourceUV=q;
      return texture2D(tex,clamp(sourceUV,vec2(.001),vec2(.999)));
    }
    void main(){
      float visibleHeight=mix(.31640625*band*zoom,1.,portrait);
      if(abs(uv.y-.5)>visibleHeight*.5){gl_FragColor=vec4(0.);return;}
      vec2 d=uv-vec2(.5);vec4 color=vec4(0.);
      for(int i=0;i<24;i++){
        float f=float(i)/23.;vec4 c=sampleAt(uv-d*strength*f);
        color.rgb+=c.rgb*c.a;color.a+=c.a;
      }
      color/=24.;if(color.a>0.)color.rgb/=color.a;
      gl_FragColor=color;
    }`;
  function shader(type,source){const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw new Error(gl.getShaderInfoLog(s));return s;}
  const program=gl.createProgram();gl.attachShader(program,shader(gl.VERTEX_SHADER,vertex));gl.attachShader(program,shader(gl.FRAGMENT_SHADER,fragment));gl.linkProgram(program);
  if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw new Error(gl.getProgramInfoLog(program));
  gl.useProgram(program);const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,1,1]),gl.STATIC_DRAW);
  const p=gl.getAttribLocation(program,'p');gl.enableVertexAttribArray(p);gl.vertexAttribPointer(p,2,gl.FLOAT,false,0,0);
  const texture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,texture);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
  gl.uniform1i(gl.getUniformLocation(program,'tex'),0);gl.viewport(0,0,1080,1920);
  const uniforms=Object.fromEntries(['band','zoom','strength','portrait'].map(k=>[k,gl.getUniformLocation(program,k)]));
  const clamp=x=>Math.max(0,Math.min(1,x));const out=x=>1-Math.pow(1-clamp(x),3);
  function poseAt(time){
    const f=Math.max(0,Math.min(301.999,time*30));
    if(f<86){
      const enter=out(f/25);const push=clamp((f-25)/55);const exit=Math.pow(clamp((f-80)/5),3);
      return {slot:1,band:.44+.56*enter,zoom:(1+.18*push)*(1+1.6*exit),strength:.72*Math.pow(1-clamp(f/20),2)+.78*exit,portrait:0};
    }
    if(f<183){
      const local=f-86;const enter=Math.pow(1-clamp(local/15),3);const exit=Math.pow(clamp((f-178)/4),3);
      return {slot:2,band:1,zoom:1+.38*enter+.9*exit,strength:.75*enter+.8*exit,portrait:1};
    }
    const local=f-183;
    return {slot:3,band:local<1?1.1:.42+.58*out((local-1)/24),zoom:local<1?1.25:1,strength:.76*Math.pow(1-clamp(local/23),2),portrait:0};
  }
  let time=0;
  function sourceFor(video){
    const sibling=video.nextElementSibling;
    if(sibling&&sibling.classList.contains('__render_frame__')&&sibling.complete&&sibling.naturalWidth>0)return sibling;
    return video.readyState>=2?video:null;
  }
  function drawAt(next){
    if(Number.isFinite(next))time=next;
    const pose=poseAt(time);const source=sourceFor(document.getElementById('media'+pose.slot));
    if(!source)return;
    gl.useProgram(program);gl.bindTexture(gl.TEXTURE_2D,texture);gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,false);
    gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,source);
    for(const key of Object.keys(uniforms))gl.uniform1f(uniforms[key],pose[key]);
    gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT);gl.drawArrays(gl.TRIANGLE_STRIP,0,4);
  }
  const tl=gsap.timeline({paused:true,onUpdate:()=>drawAt(tl.time())});
  tl.to({progress:0},{progress:1,duration,ease:'none'},0);
  window.__yellowBannerTimeline=tl;
  window.addEventListener('hf-seek',event=>drawAt(event.detail.time));
  for(const video of document.querySelectorAll('.source'))for(const event of ['loadeddata','seeked','timeupdate'])video.addEventListener(event,()=>drawAt(time));
  // Snapshot injection does not trigger hf-seek after decode; this redraw is
  // only asset readiness, never a separate animation clock.
  const observed=new WeakSet();
  function observeFrame(img){if(!img.matches?.('img.__render_frame__'))return;if(!observed.has(img)){observed.add(img);img.addEventListener('load',()=>drawAt(time));}if(img.complete&&img.naturalWidth)drawAt(time);}
  new MutationObserver(records=>{for(const record of records){if(record.type==='attributes')observeFrame(record.target);for(const node of record.addedNodes)if(node.nodeType===1)observeFrame(node);}}).observe(document.getElementById('root'),{childList:true,subtree:true,attributes:true,attributeFilter:['src']});
  window.__yellowBannerPoseAt=poseAt;
  document.fonts.ready.then(()=>{
    const ctx=document.createElement('canvas').getContext('2d');
    for(const [id,max,weight,width,family] of [['title',81,900,804,'BannerSans'],['subtitle1',63,900,894,'BannerSans'],['subtitle2',63,900,894,'BannerSans'],['sourceLabel',45,800,442,'BannerSans'],['cta',45,700,866,'BannerSerif']]){
      const el=document.getElementById(id);let size=max;ctx.font=weight+' '+size+'px '+family;
      while(ctx.measureText(el.textContent).width>width&&size>28){size--;ctx.font=weight+' '+size+'px '+family;}el.style.fontSize=size+'px';
    }
    const body=document.getElementById('body');
    function lineCount(text,size){ctx.font='750 '+size+'px BannerSans';let count=0;for(const line of text.split('\n')){let width=0;count++;for(const char of line){const w=ctx.measureText(char).width;if(width+w>787.5){count++;width=w;}else width+=w;}}return count;}
    let size=48;while(lineCount(body.textContent,size)*size*1.15625>173&&size>28)size--;
    body.style.fontSize=size+'px';body.style.lineHeight=(size*1.15625)+'px';drawAt(time);
  });
};
