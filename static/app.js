(function(){
 document.getElementById('menuBtn')?.addEventListener('click',()=>document.getElementById('sidebar')?.classList.toggle('open'));
 document.getElementById('publicMenuBtn')?.addEventListener('click',()=>document.getElementById('publicNav')?.classList.toggle('open'));
 document.querySelectorAll('[data-read-notification]').forEach(el=>el.addEventListener('click',async()=>{await fetch('/notifications/read/'+el.dataset.readNotification,{method:'POST'});el.classList.add('read')}));
 window.markAllNotifications=async()=>{await fetch('/notifications/read-all',{method:'POST'});location.reload()};
})();


/* AHVT V30: unified image resilience */
document.addEventListener('error', function (event) {
  const el = event.target;
  if (!el || el.tagName !== 'IMG' || el.dataset.ahvtFallback === '1') return;
  el.dataset.ahvtFallback = '1';
  el.src = '/assets/placeholder.svg';
  el.classList.add('ahvt-image-fallback');
}, true);
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('img').forEach(function (img) {
    if (!img.hasAttribute('loading')) img.setAttribute('loading', 'lazy');
    if (!img.hasAttribute('decoding')) img.setAttribute('decoding', 'async');
  });
});

/* AHVT V44 — animated dashboard counters */
document.addEventListener('DOMContentLoaded', function(){
  document.querySelectorAll('.ahvt-stat-final strong[data-count]').forEach(function(el){
    const target=Math.max(0,Number(el.dataset.count||0));
    const start=performance.now(), duration=900;
    function tick(now){const p=Math.min(1,(now-start)/duration);const eased=1-Math.pow(1-p,3);el.textContent=Math.round(target*eased).toLocaleString('ar-IQ');if(p<1)requestAnimationFrame(tick);}
    requestAnimationFrame(tick);
  });
});
