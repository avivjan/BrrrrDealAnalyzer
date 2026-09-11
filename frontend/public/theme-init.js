// Pre-paint appearance. Applies the stored look and mode to <html> before the
// stylesheet renders, so there is no flash of the wrong theme. The keys
// ('bw.look', 'bw.theme') and the default look ('luxury') are duplicated from
// src/design/theme.ts and src/design/looks.ts on purpose; theme.test.ts holds
// the three in step. Wrapped in try/catch: storage may be locked.
//
// Lives in its own file (not inline in index.html) so the Content-Security-
// Policy can say `script-src 'self'` without a hash that changes on every edit.
try{var L=['obsidian','aurora','brutal','luxury'];var k=localStorage.getItem('bw.look');var c=localStorage.getItem('bw.theme');var d=c==='light'?false:c==='dark'?true:c==='system'?matchMedia('(prefers-color-scheme: dark)').matches:true;var e=document.documentElement;e.dataset.look=L.indexOf(k)>=0?k:'luxury';e.classList.toggle('dark',d);e.style.colorScheme=d?'dark':'light';if(localStorage.getItem('bw.motion')==='reduced'){e.dataset.motion='reduced';}}catch(_){var r=document.documentElement;r.dataset.look='luxury';r.classList.add('dark');r.style.colorScheme='dark';}
