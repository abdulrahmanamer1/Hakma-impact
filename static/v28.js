(()=> {
  const animateNumber=(el)=>{
    const target=parseFloat(el.dataset.count||0);
    const start=performance.now(), duration=1100;
    const tick=(now)=>{
      const p=Math.min(1,(now-start)/duration), eased=1-Math.pow(1-p,3);
      const value=target*eased;
      el.textContent=Number.isInteger(target)?Math.round(value):value.toFixed(1);
      if(p<1) requestAnimationFrame(tick);
    }; requestAnimationFrame(tick);
  };
  const stats=new IntersectionObserver(entries=>{
    entries.forEach(e=>{if(e.isIntersecting){e.target.classList.add('visible'); const n=e.target.querySelector('[data-count]'); if(n&&!n.dataset.done){n.dataset.done='1';animateNumber(n)}}});
  },{threshold:.2});
  document.querySelectorAll('.ahvt-stat').forEach(x=>stats.observe(x));
  const reveals=new IntersectionObserver(entries=>entries.forEach(e=>{if(e.isIntersecting)e.target.classList.add('ahvt-visible')}),{threshold:.08});
  document.querySelectorAll('.ahvt-reveal').forEach(x=>reveals.observe(x));

  document.querySelectorAll('.ahvt-sortable').forEach(list=>{
    let dragged=null;
    list.querySelectorAll('[draggable=true]').forEach(item=>{
      item.addEventListener('dragstart',()=>{dragged=item;item.classList.add('ahvt-dragging')});
      item.addEventListener('dragend',async()=>{item.classList.remove('ahvt-dragging');list.querySelectorAll('.ahvt-drop-target').forEach(x=>x.classList.remove('ahvt-drop-target')); if(!dragged)return;
        const ids=[...list.querySelectorAll('[draggable=true]')].map(x=>x.id.replace(/^(admin|member|temp)-/,'')).filter(Boolean);
        try{await fetch('/admin/reorder',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({entity:list.dataset.entity,ids})})}catch(e){}
        dragged=null;
      });
      item.addEventListener('dragover',e=>{e.preventDefault();if(dragged&&dragged!==item){item.classList.add('ahvt-drop-target');const r=item.getBoundingClientRect();const before=e.clientY<r.top+r.height/2;list.insertBefore(dragged,before?item:item.nextSibling)}});
      item.addEventListener('dragleave',()=>item.classList.remove('ahvt-drop-target'));
    });
    // Touch reorder: long press + vertical movement, deliberately light-weight.
    let touchItem=null, startY=0;
    list.querySelectorAll('[draggable=true]').forEach(item=>{
      item.addEventListener('touchstart',e=>{touchItem=item;startY=e.touches[0].clientY},{passive:true});
      item.addEventListener('touchmove',e=>{
        if(!touchItem)return; const y=e.touches[0].clientY, dy=y-startY;
        if(Math.abs(dy)<18)return; e.preventDefault();
        const under=document.elementFromPoint(e.touches[0].clientX,y)?.closest('[draggable=true]');
        if(under&&under!==touchItem){const r=under.getBoundingClientRect();list.insertBefore(touchItem,y<r.top+r.height/2?under:under.nextSibling);startY=y}
      },{passive:false});
      item.addEventListener('touchend',async()=>{if(!touchItem)return; const ids=[...list.querySelectorAll('[draggable=true]')].map(x=>x.id.replace(/^(admin|member|temp)-/,'')).filter(Boolean); await fetch('/admin/reorder',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({entity:list.dataset.entity,ids})}).catch(()=>{});touchItem=null});
    });
  });
})();
// Universal media hardening: no broken-image icon, lazy loading, and graceful fallback.
document.querySelectorAll('img').forEach(img=>{
  img.loading=img.loading||'lazy';
  img.addEventListener('error',()=>{
    if(img.dataset.fallbackApplied)return;
    img.dataset.fallbackApplied='1';
    img.src='/assets/placeholder.svg';
  },{once:true});
});

// Light cinematic section reveal and natural touch scrolling; no forced snap that can trap users.
const homeSections=[...document.querySelectorAll('.h10-section')];
if(homeSections.length){
  const ro=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting)e.target.classList.add('ahvt-visible')}),{threshold:.08});
  homeSections.forEach(x=>ro.observe(x));
}
