document.addEventListener('DOMContentLoaded',()=>{
  const levels=[...document.querySelectorAll('.cinema-section[data-level]')];
  const dots=[...document.querySelectorAll('.level-nav a')];
  if(!levels.length||!dots.length)return;
  const io=new IntersectionObserver(entries=>{entries.forEach(e=>{if(e.isIntersecting){dots.forEach(d=>d.classList.toggle('active',d.dataset.level===e.target.dataset.level));}})},{threshold:.45});
  levels.forEach(x=>io.observe(x));
});
