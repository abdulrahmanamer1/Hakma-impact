(function(){
 document.getElementById('menuBtn')?.addEventListener('click',()=>document.getElementById('sidebar')?.classList.toggle('open'));
 document.getElementById('publicMenuBtn')?.addEventListener('click',()=>document.getElementById('publicNav')?.classList.toggle('open'));
 document.querySelectorAll('[data-read-notification]').forEach(el=>el.addEventListener('click',async()=>{await fetch('/notifications/read/'+el.dataset.readNotification,{method:'POST'});el.classList.add('read')}));
 window.markAllNotifications=async()=>{await fetch('/notifications/read-all',{method:'POST'});location.reload()};
})();
